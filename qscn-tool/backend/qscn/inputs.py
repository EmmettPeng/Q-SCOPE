from __future__ import annotations

import json
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .config import settings
from .schemas import InputKind
from .storage import safe_id, sha256_file, write_json


class InputError(ValueError):
    def __init__(self, message: str, code: str = "input_validation_failed") -> None:
        super().__init__(message)
        self.code = code


PROTEIN_SUFFIXES = {".faa", ".fas", ".fasta", ".fa"}
NUCLEOTIDE_SUFFIXES = {".fna", ".ffn", ".fasta", ".fa"}
PROTEIN_ALPHABET = set("ABCDEFGHIKLMNPQRSTVWXYZUOJ*")
NUCLEOTIDE_ALPHABET = set("ACGTUNRYKMSWBDHV")


def _ignored(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return any(part.startswith(".") or part == "__MACOSX" for part in parts)


def _validate_member(member: zipfile.ZipInfo) -> PurePosixPath:
    path = PurePosixPath(member.filename)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise InputError(f"unsafe archive path: {member.filename}")
    if len(path.parts) > 8:
        raise InputError(f"archive path is too deep: {member.filename}")
    if member.flag_bits & 0x1:
        raise InputError(f"encrypted archive entries are not accepted: {member.filename}")
    mode = member.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise InputError(f"symbolic links are not accepted: {member.filename}")
    file_type = stat.S_IFMT(mode)
    if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise InputError(f"special archive entries are not accepted: {member.filename}")
    if not member.is_dir() and member.file_size:
        ratio = member.file_size / max(1, member.compress_size)
        if ratio > settings.max_compression_ratio:
            raise InputError(
                f"archive member exceeds compression ratio limit: {member.filename}",
                "archive_compression_ratio_exceeded",
            )
    return path


def _read_fasta(path: Path, kind: InputKind) -> tuple[int, int, bool]:
    alphabet = PROTEIN_ALPHABET if kind == InputKind.protein else NUCLEOTIDE_ALPHABET
    seen: set[str] = set()
    records = 0
    residues = 0
    current_id: str | None = None
    current_length = 0
    nucleotide_only = True
    with path.open("r", encoding="utf-8", errors="strict") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_id is not None and current_length == 0:
                    raise InputError(f"empty sequence {current_id!r} in {path.name}")
                header = line[1:].strip()
                if not header:
                    raise InputError(f"empty FASTA header in {path.name}:{line_number}")
                current_id = header.split()[0]
                if current_id in seen:
                    raise InputError(f"duplicate sequence ID {current_id!r} in {path.name}")
                seen.add(current_id)
                records += 1
                current_length = 0
                continue
            if current_id is None:
                raise InputError(f"sequence before first header in {path.name}:{line_number}")
            sequence = "".join(line.split()).upper()
            invalid = sorted(set(sequence) - alphabet)
            if invalid:
                raise InputError(
                    f"invalid {'protein' if kind == InputKind.protein else 'nucleotide'} symbols "
                    f"in {path.name}:{line_number}: {''.join(invalid)}"
                )
            current_length += len(sequence)
            residues += len(sequence)
            nucleotide_only = nucleotide_only and set(sequence) <= NUCLEOTIDE_ALPHABET
    if current_id is not None and current_length == 0:
        raise InputError(f"empty sequence {current_id!r} in {path.name}")
    if records == 0:
        raise InputError(f"no FASTA records in {path.name}")
    return records, residues, nucleotide_only


def preflight_archive(archive_path: Path, destination: Path, kind: InputKind) -> list[dict[str, Any]]:
    if not zipfile.is_zipfile(archive_path):
        raise InputError("only valid ZIP archives are accepted")
    suffixes = PROTEIN_SUFFIXES if kind == InputKind.protein else NUCLEOTIDE_SUFFIXES
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) > settings.max_archive_files:
            raise InputError(f"archive contains more than {settings.max_archive_files} entries")
        extracted_size = sum(member.file_size for member in members if not member.is_dir())
        if extracted_size > settings.max_extracted_bytes:
            raise InputError("uncompressed archive exceeds the configured size limit")
        selected: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
        unexpected: list[str] = []
        archive_paths: set[str] = set()
        for member in members:
            path = _validate_member(member)
            canonical = str(path).casefold()
            if canonical in archive_paths:
                raise InputError(
                    f"duplicate or case-conflicting archive path: {member.filename}",
                    "sample_name_conflict",
                )
            archive_paths.add(canonical)
            if member.is_dir() or _ignored(member.filename):
                continue
            if path.suffix.lower() not in suffixes:
                unexpected.append(member.filename)
                continue
            selected.append((member, path))
        if unexpected:
            preview = ", ".join(unexpected[:5])
            raise InputError(f"archive contains files not valid for {kind.value}: {preview}")
        if not selected:
            raise InputError("archive contains no supported FASTA files")
        if len(selected) > settings.max_genomes:
            raise InputError(f"archive contains more than {settings.max_genomes} genomes")

        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        samples: list[dict[str, Any]] = []
        sample_ids: set[str] = set()
        extracted_actual = 0
        total_sequences = 0
        total_residues = 0
        all_nucleotide_only = True
        try:
            for index, (member, relative) in enumerate(selected, 1):
                sample_id = safe_id(relative.stem, f"sample_{index}")
                canonical_id = sample_id.casefold()
                if canonical_id in sample_ids:
                    raise InputError(
                        f"sample names collide after normalization: {relative.stem}",
                        "sample_name_conflict",
                    )
                sample_ids.add(canonical_id)
                output = destination / f"{sample_id}{relative.suffix.lower()}"
                with archive.open(member) as source, output.open("wb") as target:
                    while chunk := source.read(1024 * 1024):
                        extracted_actual += len(chunk)
                        if extracted_actual > settings.max_extracted_bytes:
                            raise InputError(
                                "actual extracted data exceeds the configured size limit",
                                "archive_resource_limit_exceeded",
                            )
                        target.write(chunk)
                records, residues, nucleotide_only = _read_fasta(output, kind)
                total_sequences += records
                total_residues += residues
                all_nucleotide_only = all_nucleotide_only and nucleotide_only
                if total_sequences > settings.max_total_sequences:
                    raise InputError(
                        "archive exceeds the configured sequence count limit",
                        "archive_resource_limit_exceeded",
                    )
                if total_residues > settings.max_total_residues:
                    raise InputError(
                        "archive exceeds the configured residue count limit",
                        "archive_resource_limit_exceeded",
                    )
                samples.append(
                    {
                        "sample_id": sample_id,
                        "display_name": relative.stem,
                        "original_path": str(relative),
                        "fasta_path": str(output),
                        "sequence_count": records,
                        "total_residues": residues,
                        "input_kind": kind.value,
                        "sha256": sha256_file(output),
                    }
                )
            if kind == InputKind.protein and all_nucleotide_only:
                raise InputError(
                    "protein input contains only nucleotide alphabet symbols; select genome input",
                    "ambiguous_sequence_alphabet",
                )
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise
    write_json(destination / "samples.json", samples)
    return samples


def rename_sample(samples: list[dict[str, Any]], sample_id: str, display_name: str) -> list[dict[str, Any]]:
    display_name = display_name.strip()
    if not display_name:
        raise InputError("display name cannot be empty")
    found = False
    for sample in samples:
        if sample["sample_id"] == sample_id:
            sample["display_name"] = display_name
            found = True
    if not found:
        raise InputError("sample not found")
    return samples
