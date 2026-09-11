from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from . import db
from .analysis import parse_prodigal_protein_headers, run_prodigal
from .config import settings
from .schemas import InputKind
from .storage import read_json, sha256_file, write_json


PREDICTION_CACHE_FORMAT_VERSION = "1.0"
PRODIGAL_MODE = "single"
PREDICTION_SUFFIXES = (
    ".faa",
    ".fna",
    ".gff",
    ".predicted_genes.json",
    ".predicted_genes.tsv",
    ".prodigal.json",
)


def _sample_fingerprint(samples: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "sample_id": sample["sample_id"],
            "sha256": sample.get("sha256") or sha256_file(Path(sample["fasta_path"])),
        }
        for sample in sorted(samples, key=lambda item: item["sample_id"])
    ]


def prediction_cache_key(samples: list[dict[str, Any]], prodigal_version: str) -> str:
    payload = {
        "format_version": PREDICTION_CACHE_FORMAT_VERSION,
        "predictor": "prodigal",
        "predictor_version": prodigal_version,
        "mode": PRODIGAL_MODE,
        "samples": _sample_fingerprint(samples),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _expected_names(samples: list[dict[str, Any]]) -> set[str]:
    return {
        f"{sample['sample_id']}{suffix}"
        for sample in samples
        for suffix in PREDICTION_SUFFIXES
    }


def _file_records(directory: Path, names: set[str]) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "sha256": sha256_file(directory / name),
            "size": (directory / name).stat().st_size,
        }
        for name in sorted(names)
    ]


def _prediction_outputs_valid(directory: Path, samples: list[dict[str, Any]]) -> bool:
    names = _expected_names(samples)
    if not all((directory / name).is_file() for name in names):
        return False
    try:
        for sample in samples:
            sample_id = sample["sample_id"]
            genes = read_json(directory / f"{sample_id}.predicted_genes.json")
            if not isinstance(genes, list):
                return False
            parsed = parse_prodigal_protein_headers(
                directory / f"{sample_id}.faa",
                directory / f"{sample_id}.gff",
                sample_id,
            )
            if len(parsed) != len(genes):
                return False
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return False
    return True


def _cache_valid(
    directory: Path,
    key: str,
    samples: list[dict[str, Any]],
    prodigal_version: str,
) -> dict[str, Any] | None:
    manifest_path = directory / "prediction_manifest.json"
    if not manifest_path.is_file() or not _prediction_outputs_valid(directory, samples):
        return None
    try:
        manifest = read_json(manifest_path)
        if (
            manifest.get("format_version") != PREDICTION_CACHE_FORMAT_VERSION
            or manifest.get("cache_key") != key
            or manifest.get("predictor") != "prodigal"
            or manifest.get("predictor_version") != prodigal_version
            or manifest.get("mode") != PRODIGAL_MODE
            or manifest.get("samples") != _sample_fingerprint(samples)
        ):
            return None
        expected = _expected_names(samples)
        records = manifest.get("files") or []
        if {record.get("name") for record in records} != expected:
            return None
        if any(
            sha256_file(directory / record["name"]) != record.get("sha256")
            for record in records
        ):
            return None
        return manifest
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _link_or_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def _copy_prediction_set(source: Path, destination: Path, samples: list[dict[str, Any]]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in sorted(_expected_names(samples)):
        _link_or_copy(source / name, destination / name)


@contextmanager
def _project_lock(cache_root: Path) -> Iterator[None]:
    cache_root.mkdir(parents=True, exist_ok=True)
    with (cache_root / ".lock").open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _legacy_source(
    project: dict[str, Any],
    current_run_id: str,
    samples: list[dict[str, Any]],
    prodigal_version: str,
) -> tuple[Path, str] | None:
    candidates = sorted(
        (
            row
            for row in db.list_rows("runs", "project_id=?", (project["id"],))
            if row["id"] != current_run_id
            and row["input_kind"] == InputKind.genome.value
            and row["status"] == "complete"
        ),
        key=lambda row: row["created_at"],
        reverse=True,
    )
    expected_samples = _sample_fingerprint(samples)
    for run in candidates:
        base = settings.projects_dir / project["id"] / "runs" / run["id"]
        manifest_path = base / "run_manifest.json"
        prediction_dir = base / "predictions"
        if not manifest_path.is_file() or not prediction_dir.is_dir():
            continue
        try:
            manifest = read_json(manifest_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        manifest_samples = [
            {"sample_id": item.get("sample_id"), "sha256": item.get("sha256")}
            for item in sorted(manifest.get("samples") or [], key=lambda item: item.get("sample_id", ""))
        ]
        if (
            manifest.get("archive_sha256") != project["archive_sha256"]
            or manifest.get("prodigal_mode") != PRODIGAL_MODE
            or (manifest.get("tools") or {}).get("prodigal") != prodigal_version
            or manifest_samples != expected_samples
            or not _prediction_outputs_valid(prediction_dir, samples)
        ):
            continue
        return prediction_dir, run["id"]
    return None


def _write_cache_manifest(
    directory: Path,
    key: str,
    samples: list[dict[str, Any]],
    prodigal_version: str,
    producer_run_id: str,
    source: str,
    source_run_id: str | None,
) -> dict[str, Any]:
    manifest = {
        "format_version": PREDICTION_CACHE_FORMAT_VERSION,
        "cache_key": key,
        "predictor": "prodigal",
        "predictor_version": prodigal_version,
        "mode": PRODIGAL_MODE,
        "samples": _sample_fingerprint(samples),
        "producer_run_id": producer_run_id,
        "source": source,
        "source_run_id": source_run_id,
        "created_at": db.now(),
        "files": _file_records(directory, _expected_names(samples)),
    }
    write_json(directory / "prediction_manifest.json", manifest)
    return manifest


def _materialize_run(cache_dir: Path, run_prediction_dir: Path) -> None:
    if run_prediction_dir.exists():
        shutil.rmtree(run_prediction_dir)
    run_prediction_dir.mkdir(parents=True)
    for source in sorted(cache_dir.iterdir(), key=lambda path: path.name):
        if source.is_file():
            _link_or_copy(source, run_prediction_dir / source.name)


def prepare_project_predictions(
    project: dict[str, Any],
    run_id: str,
    samples: list[dict[str, Any]],
    run_prediction_dir: Path,
    prodigal_version: str,
    on_predict: Callable[[int, dict[str, Any]], None],
) -> tuple[dict[str, Path], dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    key = prediction_cache_key(samples, prodigal_version)
    cache_root = settings.projects_dir / project["id"] / "gene-predictions"
    cache_dir = cache_root / key
    reused = True
    source = "project_cache"
    source_run_id: str | None = None

    with _project_lock(cache_root):
        manifest = _cache_valid(cache_dir, key, samples, prodigal_version)
        if manifest is None:
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            staging = cache_root / f".{key}.tmp-{uuid.uuid4().hex}"
            staging.mkdir(parents=True)
            try:
                legacy = _legacy_source(project, run_id, samples, prodigal_version)
                if legacy:
                    legacy_dir, source_run_id = legacy
                    _copy_prediction_set(legacy_dir, staging, samples)
                    source = "legacy_run"
                else:
                    reused = False
                    source = "generated"
                    for index, sample in enumerate(samples):
                        on_predict(index, sample)
                        run_prodigal(sample, InputKind.genome, staging)
                if not _prediction_outputs_valid(staging, samples):
                    raise ValueError("generated prediction cache is incomplete")
                manifest = _write_cache_manifest(
                    staging,
                    key,
                    samples,
                    prodigal_version,
                    run_id,
                    source,
                    source_run_id,
                )
                os.replace(staging, cache_dir)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        else:
            source_run_id = manifest.get("producer_run_id")

    _materialize_run(cache_dir, run_prediction_dir)
    protein_paths = {
        sample["sample_id"]: run_prediction_dir / f"{sample['sample_id']}.faa"
        for sample in samples
    }
    genes = {
        sample["sample_id"]: {
            item["gene_id"]: item
            for item in read_json(
                run_prediction_dir / f"{sample['sample_id']}.predicted_genes.json"
            )
        }
        for sample in samples
    }
    provenance = {
        "cache_format_version": PREDICTION_CACHE_FORMAT_VERSION,
        "cache_key": key,
        "reused": reused,
        "source": source,
        "source_run_id": source_run_id,
        "prediction_manifest_sha256": sha256_file(
            run_prediction_dir / "prediction_manifest.json"
        ),
        "predictor_version": prodigal_version,
        "mode": PRODIGAL_MODE,
    }
    return protein_paths, genes, provenance
