from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
import zipfile
import stat
from pathlib import PurePosixPath
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from . import db
from .config import settings
from .schemas import DatabaseManifest
from .storage import is_within, safe_id, sha256_file, sha256_paths, write_json
from .execution import ExternalCommandError, run_external


PATHWAY_TABLE_HEADERS = (
    "Pathway",
    "Signal_type",
    "Signal_Sending",
    "Signal_Receiving",
    "References",
)

PATHWAY_TABLE_TEMPLATE = """Pathway\tSignal_type\tSignal_Sending\tSignal_Receiving\tReferences
LuxM_LuxN_system\tHSLs\tLuxM\tLuxN\thttps://doi.org/10.1128/jb.183.12.3537-3547.2001;https://doi.org/10.1128/JB.181.18.5766-5770.1999
LuxI_LuxR_system\tHSLs\tLuxI\tLuxR\thttps://doi.org/10.1007/s10867-010-9186-4;https://doi.org/10.1073/pnas.93.18.9505
"""


class DatabaseError(ValueError):
    def __init__(
        self,
        message: str,
        public_code: str = "database_import_failed",
        **params: Any,
    ) -> None:
        super().__init__(message)
        self.public_code = public_code
        self.params = params


def custom_database_id(name: str) -> str:
    slug = safe_id(name, "")
    if slug:
        return f"custom-{slug.lower()}"
    digest = hashlib.sha256(name.strip().encode("utf-8")).hexdigest()[:12]
    return f"custom-{digest}"


def _split_table_values(value: str) -> list[str]:
    return list(dict.fromkeys(part.strip() for part in value.split(";") if part.strip()))


def parse_pathway_table(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            text = handle.read()
    except UnicodeDecodeError as error:
        raise DatabaseError(
            "pathway table must be UTF-8",
            "database_table_invalid",
            reason="encoding",
        ) from error
    if "\x00" in text:
        raise DatabaseError(
            "pathway table contains a NUL byte",
            "database_table_invalid",
            reason="encoding",
        )
    rows = list(csv.reader(text.splitlines(), delimiter="\t"))
    if not rows:
        raise DatabaseError(
            "pathway table is empty", "database_table_invalid", reason="empty_table"
        )
    headers = rows[0]
    if len(headers) != len(set(headers)) or set(headers) != set(PATHWAY_TABLE_HEADERS):
        raise DatabaseError(
            "pathway table headers do not match the template",
            "database_table_invalid",
            reason="headers",
        )
    pathways: list[dict[str, Any]] = []
    seen_pathways: set[str] = set()
    for row_number, values in enumerate(rows[1:], start=2):
        if not values or all(not value.strip() for value in values):
            continue
        if len(values) != len(headers):
            raise DatabaseError(
                f"pathway table row {row_number} has the wrong number of columns",
                "database_table_invalid",
                reason="columns",
                row=row_number,
            )
        row = {header: value.strip() for header, value in zip(headers, values)}
        pathway_name = row["Pathway"]
        signal_name = row["Signal_type"]
        if not pathway_name or not signal_name:
            raise DatabaseError(
                f"pathway table row {row_number} is missing Pathway or Signal_type",
                "database_table_invalid",
                reason="required_value",
                row=row_number,
            )
        folded = pathway_name.casefold()
        if folded in seen_pathways:
            raise DatabaseError(
                f"pathway table row {row_number} repeats a Pathway",
                "database_table_invalid",
                reason="duplicate_pathway",
                row=row_number,
            )
        seen_pathways.add(folded)
        sending = _split_table_values(row["Signal_Sending"])
        receiving = _split_table_values(row["Signal_Receiving"])
        if not sending and not receiving:
            raise DatabaseError(
                f"pathway table row {row_number} defines neither role",
                "database_table_invalid",
                reason="empty_roles",
                row=row_number,
            )
        pathways.append(
            {
                "pathway_id": pathway_name,
                "name": pathway_name,
                "signal_name": signal_name,
                "sending_profiles": sending,
                "receiving_profiles": receiving,
                "references": _split_table_values(row["References"]),
            }
        )
    if not pathways:
        raise DatabaseError(
            "pathway table contains no data rows",
            "database_table_invalid",
            reason="empty_table",
        )
    return pathways


def hmm_profiles(path: Path) -> tuple[list[str], set[str]]:
    profiles: list[str] = []
    ga_profiles: set[str] = set()
    current: str | None = None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("NAME"):
                current = line.split(maxsplit=1)[1].strip()
                profiles.append(current)
            elif line.startswith("GA") and current:
                ga_profiles.add(current)
    if not profiles:
        raise DatabaseError("HMM file contains no profiles")
    if len(profiles) != len(set(profiles)):
        raise DatabaseError("HMM profile names must be unique")
    return profiles, ga_profiles


def _legacy_field(items: list[dict[str, Any]], name: str, default: Any) -> Any:
    for item in items:
        if name in item:
            return item[name]
    return default


def normalize_legacy_manifest(
    metadata_path: Path,
    database_id: str,
    name: str,
    version: str,
    source: str,
    classification_scheme: str,
    threshold_type: str,
    default_evalue: float | None = None,
    provenance: dict[str, Any] | None = None,
) -> DatabaseManifest:
    raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    pathways = []
    for pathway_id, items in raw.items():
        references = list(dict.fromkeys(_legacy_field(items, "References", [])))
        pathways.append(
            {
                "pathway_id": pathway_id,
                "name": pathway_id.replace("_", " "),
                "signal_name": _legacy_field(items, "Signal_type", pathway_id),
                "sending_profiles": _legacy_field(items, "Signal_Sending", []),
                "receiving_profiles": _legacy_field(items, "Signal_Receiving", []),
                "references": references,
            }
        )
    return DatabaseManifest.model_validate(
        {
            "database_id": database_id,
            "name": name,
            "version": version,
            "source": source,
            "classification_scheme": classification_scheme,
            "threshold_policy": {
                "type": threshold_type,
                "default_evalue": default_evalue,
            },
            "pathways": pathways,
            "provenance": provenance or {},
        }
    )


def validate_manifest_profiles(manifest: DatabaseManifest, hmm_path: Path) -> None:
    profiles, ga_profiles = hmm_profiles(hmm_path)
    profile_set = set(profiles)
    referenced = {
        profile
        for pathway in manifest.pathways
        for profile in (*pathway.sending_profiles, *pathway.receiving_profiles)
    }
    missing = sorted(referenced - profile_set)
    if missing:
        raise DatabaseError(
            f"manifest references missing HMM profiles: {', '.join(missing)}",
            "database_profile_mismatch",
            profiles=missing[:10],
        )
    if manifest.threshold_policy.type == "ga" and ga_profiles != profile_set:
        absent = sorted(profile_set - ga_profiles)
        raise DatabaseError(
            f"GA policy requires GA on every profile: {', '.join(absent[:10])}",
            "database_threshold_invalid",
            profiles=absent[:10],
        )


def _store_database(
    manifest: DatabaseManifest,
    hmm_path: Path,
    manifest_path: Path,
    checksum: str,
    builtin: bool,
) -> str:
    version_id = f"{safe_id(manifest.database_id)}:{safe_id(manifest.version)}:{checksum[:12]}"
    values = {
        "version_id": version_id,
        "database_id": manifest.database_id,
        "name": manifest.name,
        "version": manifest.version,
        "source": manifest.source,
        "classification_scheme": manifest.classification_scheme,
        "checksum": checksum,
        "hmm_path": str(hmm_path),
        "manifest_path": str(manifest_path),
        "threshold_type": manifest.threshold_policy.type,
        "default_evalue": manifest.threshold_policy.default_evalue,
        "provenance_json": json.dumps(manifest.provenance.model_dump(mode="json")),
        "builtin": int(builtin),
        "created_at": db.now(),
    }
    with db.connect() as connection:
        existing = connection.execute(
            "SELECT version_id, checksum FROM databases WHERE database_id=? AND version=?",
            (manifest.database_id, manifest.version),
        ).fetchone()
        if existing and existing["checksum"] != checksum:
            raise DatabaseError(
                "database ID and version already exist with different content",
                "database_version_conflict",
            )
        connection.execute(
            "INSERT OR IGNORE INTO databases (version_id,database_id,name,version,source,classification_scheme,checksum,hmm_path,manifest_path,threshold_type,default_evalue,provenance_json,builtin,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(values.values()),
        )
    return version_id


def register_builtins() -> None:
    settings.ensure_directories()
    specs = (
        (
            "qsp",
            "QSP curated profiles",
            "builtin-v1",
            "QSP database supplied with QSCN",
            "QSP native classification",
            "QSPdatabase.hmm",
            "QSPdatabase.json",
            "ga",
            None,
        ),
        (
            "kegg-m02024",
            "KEGG QS module profiles",
            "m02024",
            "KEGG-derived database supplied with QSCN",
            "KEGG native QS classification",
            "kegg_m02024.hmm",
            "kegg_m02024.json",
            "evalue",
            1e-5,
        ),
    )
    derived_dir = settings.custom_databases_dir / "_builtin_manifests"
    derived_dir.mkdir(parents=True, exist_ok=True)
    provenance_path = settings.builtin_database_dir / "provenance.json"
    provenance_registry = (
        json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance_path.exists() else {}
    )
    for spec in specs:
        db_id, name, version, source, scheme, hmm_name, json_name, threshold, evalue = spec
        hmm_path = settings.builtin_database_dir / hmm_name
        metadata_path = settings.builtin_database_dir / json_name
        if not hmm_path.exists() or not metadata_path.exists():
            continue
        manifest = normalize_legacy_manifest(
            metadata_path, db_id, name, version, source, scheme, threshold, evalue,
            provenance_registry.get(db_id),
        )
        validate_manifest_profiles(manifest, hmm_path)
        manifest_path = derived_dir / f"{db_id}.manifest.json"
        write_json(manifest_path, manifest.model_dump(mode="json"))
        checksum = sha256_paths([hmm_path, metadata_path])
        _store_database(manifest, hmm_path, manifest_path, checksum, True)


def list_databases() -> list[dict[str, Any]]:
    result = []
    for row in db.list_rows("databases"):
        manifest = load_manifest(row)
        public = {key: value for key, value in row.items() if key not in {"hmm_path", "manifest_path"}}
        result.append(
            {
                **public,
                "builtin": bool(row["builtin"]),
                "threshold_policy": manifest.threshold_policy.model_dump(mode="json"),
                "pathway_count": len(manifest.pathways),
                "profile_count": len(hmm_profiles(Path(row["hmm_path"]))[0]),
                "pathways": [
                    {
                        "pathway_id": pathway.pathway_id,
                        "name": pathway.name,
                        "signal_name": pathway.signal_name,
                        "sending_count": len(pathway.sending_profiles),
                        "receiving_count": len(pathway.receiving_profiles),
                        "sending_profiles": pathway.sending_profiles,
                        "receiving_profiles": pathway.receiving_profiles,
                        "references": pathway.references,
                    }
                    for pathway in manifest.pathways
                ],
                "provenance": manifest.provenance.model_dump(mode="json"),
                "redistribution_status": manifest.provenance.redistribution_status,
            }
        )
    return result


def get_database(version_id: str) -> dict[str, Any]:
    row = db.get("databases", version_id)
    if not row:
        raise DatabaseError("database version not found")
    return row


def load_manifest(row_or_version: dict[str, Any] | str) -> DatabaseManifest:
    row = get_database(row_or_version) if isinstance(row_or_version, str) else row_or_version
    return DatabaseManifest.model_validate_json(Path(row["manifest_path"]).read_text(encoding="utf-8"))


def _install_database(
    destination: Path,
    manifest: DatabaseManifest,
    hmm_path: Path,
    manifest_path: Path,
    checksum: str,
) -> str:
    final_dir = (
        settings.custom_databases_dir
        / safe_id(manifest.database_id)
        / safe_id(manifest.version)
        / checksum[:12]
    )
    if final_dir.exists():
        shutil.rmtree(destination, ignore_errors=True)
        existing = [row for row in db.list_rows("databases", "checksum=?", (checksum,))]
        if existing:
            return existing[0]["version_id"]
        raise DatabaseError("database content exists without registry metadata")
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    hmm_relative = hmm_path.relative_to(destination)
    manifest_relative = manifest_path.relative_to(destination)
    shutil.move(str(destination), final_dir)
    final_hmm = final_dir / hmm_relative
    final_manifest = final_dir / manifest_relative
    try:
        completed = run_external(["hmmpress", str(final_hmm)], timeout=600)
        if completed.returncode != 0:
            raise DatabaseError(f"hmmpress failed: {completed.stderr[-1000:]}")
        return _store_database(manifest, final_hmm, final_manifest, checksum, False)
    except ExternalCommandError as error:
        shutil.rmtree(final_dir, ignore_errors=True)
        raise DatabaseError(str(error)) from error
    except Exception:
        shutil.rmtree(final_dir, ignore_errors=True)
        raise


def import_tabular_database(
    hmm_source: Path,
    pathway_source: Path,
    *,
    name: str,
    version: str,
    source: str = "User provided",
    classification_scheme: str = "User-defined classification",
    threshold_type: str,
    default_full_evalue: float | None = None,
    default_domain_i_evalue: float | None = None,
) -> str:
    if hmm_source.suffix.lower() != ".hmm" or pathway_source.suffix.lower() not in {".tsv", ".txt"}:
        raise DatabaseError(
            "choose one .hmm and one .tsv or .txt file",
            "database_files_required",
        )
    name = name.strip()
    version = version.strip()
    if not name or not version:
        raise DatabaseError(
            "database name and version are required",
            "database_metadata_invalid",
        )
    if threshold_type not in {"ga", "evalue"}:
        raise DatabaseError(
            "threshold type must be ga or evalue",
            "database_threshold_invalid",
        )
    if threshold_type == "evalue" and (
        default_full_evalue is None
        or default_domain_i_evalue is None
        or not math.isfinite(default_full_evalue)
        or not math.isfinite(default_domain_i_evalue)
        or default_full_evalue <= 0
        or default_domain_i_evalue <= 0
    ):
        raise DatabaseError(
            "E-value thresholds must be positive",
            "database_threshold_invalid",
        )
    if threshold_type == "ga" and (
        default_full_evalue is not None or default_domain_i_evalue is not None
    ):
        raise DatabaseError(
            "GA databases cannot define E-value thresholds",
            "database_threshold_invalid",
        )

    settings.ensure_directories()
    destination = Path(tempfile.mkdtemp(prefix="qscn-db-", dir=settings.custom_databases_dir))
    try:
        hmm_path = destination / "profiles.hmm"
        table_path = destination / f"pathways{pathway_source.suffix.lower()}"
        shutil.copyfile(hmm_source, hmm_path)
        shutil.copyfile(pathway_source, table_path)
        pathways = parse_pathway_table(table_path)
        profiles, _ = hmm_profiles(hmm_path)
        referenced_profiles = {
            profile
            for pathway in pathways
            for profile in (*pathway["sending_profiles"], *pathway["receiving_profiles"])
        }
        policy: dict[str, Any] = {"type": threshold_type}
        if threshold_type == "evalue":
            policy.update(
                {
                    "default_full_evalue": default_full_evalue,
                    "default_domain_i_evalue": default_domain_i_evalue,
                }
            )
        manifest = DatabaseManifest.model_validate(
            {
                "database_id": custom_database_id(name),
                "name": name,
                "version": version,
                "source": source.strip() or "User provided",
                "classification_scheme": classification_scheme.strip()
                or "User-defined classification",
                "threshold_policy": policy,
                "pathways": pathways,
                "provenance": {
                    "build_method": "User-supplied HMM and tab-separated Pathway table",
                    "profile_count": len(profiles),
                    "metadata_reference_count": len(referenced_profiles),
                    "hmm_sha256": sha256_file(hmm_path),
                    "metadata_sha256": sha256_file(table_path),
                },
            }
        )
        validate_manifest_profiles(manifest, hmm_path)
        manifest_path = destination / "manifest.json"
        write_json(manifest_path, manifest.model_dump(mode="json"))
        checksum = sha256_paths([hmm_path, table_path, manifest_path])
        return _install_database(destination, manifest, hmm_path, manifest_path, checksum)
    except ValidationError as error:
        raise DatabaseError(
            "database metadata is invalid", "database_metadata_invalid"
        ) from error
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def import_custom_database(archive_path: Path) -> str:
    destination = Path(tempfile.mkdtemp(prefix="qscn-db-", dir=settings.custom_databases_dir))
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) > settings.max_archive_files:
                raise DatabaseError("database archive contains too many entries")
            if sum(member.file_size for member in members if not member.is_dir()) > settings.max_extracted_bytes:
                raise DatabaseError("database archive exceeds the uncompressed size limit")
            if any(member.filename.lower().endswith((".h3f", ".h3i", ".h3m", ".h3p")) for member in members):
                raise DatabaseError("generated .h3* indexes are not accepted")
            canonical_paths: set[str] = set()
            extracted_actual = 0
            for member in members:
                relative = PurePosixPath(member.filename)
                if relative.is_absolute() or ".." in relative.parts or len(relative.parts) > 8:
                    raise DatabaseError("archive contains an unsafe path")
                canonical = str(relative).casefold()
                if canonical in canonical_paths:
                    raise DatabaseError("archive contains duplicate or case-conflicting paths")
                canonical_paths.add(canonical)
                mode = member.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                if member.flag_bits & 0x1:
                    raise DatabaseError("encrypted database entries are not accepted")
                if file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise DatabaseError("archive contains a symbolic link or special file")
                if member.file_size and member.file_size / max(1, member.compress_size) > settings.max_compression_ratio:
                    raise DatabaseError("database archive exceeds the compression ratio limit")
                if member.is_dir():
                    continue
                target = destination / member.filename
                if not is_within(target, destination):
                    raise DatabaseError("archive contains an unsafe path")
                if member.external_attr >> 16 & 0o170000 == 0o120000:
                    raise DatabaseError("archive contains a symbolic link")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as output:
                    while chunk := source.read(1024 * 1024):
                        extracted_actual += len(chunk)
                        if extracted_actual > settings.max_extracted_bytes:
                            raise DatabaseError("database archive exceeds the actual extraction limit")
                        output.write(chunk)
        hmms = list(destination.rglob("*.hmm"))
        manifests = [path for path in destination.rglob("manifest.json") if path.is_file()]
        if len(hmms) != 1 or len(manifests) != 1:
            raise DatabaseError("database ZIP must contain exactly one .hmm and one manifest.json")
        try:
            manifest = DatabaseManifest.model_validate_json(manifests[0].read_text(encoding="utf-8"))
        except (ValidationError, json.JSONDecodeError) as error:
            raise DatabaseError(f"invalid manifest: {error}") from error
        validate_manifest_profiles(manifest, hmms[0])
        checksum = sha256_paths([hmms[0], manifests[0]])
        return _install_database(destination, manifest, hmms[0], manifests[0], checksum)
    except zipfile.BadZipFile as error:
        shutil.rmtree(destination, ignore_errors=True)
        raise DatabaseError("only valid ZIP database bundles are accepted") from error
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def delete_database(version_id: str) -> None:
    row = get_database(version_id)
    if row["builtin"]:
        raise DatabaseError("built-in databases cannot be deleted")
    with db.connect() as connection:
        used = connection.execute(
            "SELECT 1 FROM runs WHERE database_version_id=? LIMIT 1", (version_id,)
        ).fetchone()
    if used:
        raise DatabaseError("database is referenced by an analysis run")
    path = (
        settings.custom_databases_dir
        / safe_id(row["database_id"])
        / safe_id(row["version"])
        / row["checksum"][:12]
    )
    db.delete("databases", version_id)
    shutil.rmtree(path, ignore_errors=True)
