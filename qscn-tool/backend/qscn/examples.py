from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, __release__, __version__, db
from .completeness import strict_rules
from .config import settings
from .databases import load_manifest
from .inputs import preflight_archive
from .pipeline import create_interpretation, project_dir, run_dir
from .schemas import ANALYSIS_SCOPE_VERSION, CAPABILITY_RULE_VERSION, HIT_RULE_VERSION, InputKind
from .scope import normalize_scope
from .storage import directory_size, sha256_file, write_json


PD10_ID = "pd10"
_LOCK = threading.Lock()


def _asset_dir() -> Path:
    return settings.builtin_examples_dir / PD10_ID


def _qsp_database() -> dict[str, Any]:
    rows = db.list_rows("databases", "database_id=? AND builtin=1", ("qsp",))
    if not rows:
        raise RuntimeError("bundled QSP database is unavailable")
    return rows[0]


def list_examples() -> list[dict[str, Any]]:
    row = next(iter(db.list_rows("projects", "example_id=?", (PD10_ID,))), None)
    manifest_path = _asset_dir() / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    return [{
        "example_id": PD10_ID,
        "name": "PD10",
        "description": "Ten-genome nucleotide community analysed with the bundled QSP database.",
        "available": (_asset_dir() / "PD10.zip").is_file() and (_asset_dir() / "hits.json").is_file(),
        "installed": row is not None,
        "project_id": row["id"] if row else None,
        "sample_count": manifest.get("sample_count", 10),
        "archive_sha256": manifest.get("archive_sha256"),
        "snapshot_sha256": manifest.get("hits_sha256"),
    }]


def restore_pd10() -> dict[str, Any]:
    with _LOCK:
        existing = next(iter(db.list_rows("projects", "example_id=?", (PD10_ID,))), None)
        if existing:
            return existing
        assets = _asset_dir()
        archive_source = assets / "PD10.zip"
        hits_source = assets / "hits.json"
        if not archive_source.is_file() or not hits_source.is_file():
            raise FileNotFoundError("PD10 bundled example assets are unavailable")

        project_id = str(uuid.uuid4())
        target = project_dir(project_id)
        archive_path = target / "input.zip"
        run_id = str(uuid.uuid4())
        timestamp = db.now()
        try:
            target.mkdir(parents=True)
            shutil.copy2(archive_source, archive_path)
            samples = preflight_archive(archive_path, target / "input", InputKind.genome)
            if len(samples) != 10:
                raise RuntimeError(f"PD10 example must contain 10 samples, found {len(samples)}")
            db.insert("projects", {
                "id": project_id,
                "name": "PD10",
                "archive_path": str(archive_path),
                "archive_sha256": sha256_file(archive_path),
                "input_kind": "genome",
                "status": "ready",
                "samples_json": json.dumps(samples, ensure_ascii=False),
                "origin": "bundled_example",
                "example_id": PD10_ID,
                "created_at": timestamp,
                "updated_at": timestamp,
            })
            database = _qsp_database()
            manifest = load_manifest(database)
            rules = strict_rules(manifest)
            scope = normalize_scope(manifest, None)
            db.insert("runs", {
                "id": run_id,
                "project_id": project_id,
                "database_version_id": database["version_id"],
                "input_kind": "genome",
                "completeness_mode": "v2",
                "capability_rule_version": CAPABILITY_RULE_VERSION,
                "capability_rules_json": json.dumps([item.model_dump(mode="json") for item in rules]),
                "sequence_evalue": None,
                "hit_rule_version": HIT_RULE_VERSION,
                "hit_thresholds_json": None,
                "analysis_scope_version": ANALYSIS_SCOPE_VERSION,
                "analysis_scope_json": json.dumps(scope),
                "status": "complete",
                "stage": "complete",
                "progress": 1.0,
                "rq_job_id": None,
                "error": None,
                "error_code": None,
                "error_params_json": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            })
            run_target = run_dir(run_id, project_id)
            run_target.mkdir(parents=True)
            shutil.copy2(hits_source, run_target / "hits.json")
            predictions_source = assets / "predictions"
            if predictions_source.is_dir():
                shutil.copytree(predictions_source, run_target / "predictions")
            payload = create_interpretation(run_id, rules, scope, "Bundled QSP analysis")
            write_json(run_target / "run_manifest.json", {
                "qscn_version": __version__, "qscn_release": __release__,
                "schema_version": SCHEMA_VERSION, "run_id": run_id,
                "project_id": project_id, "input_kind": "genome",
                "prodigal_mode": "single", "capability_rule_version": CAPABILITY_RULE_VERSION,
                "hit_rule_version": HIT_RULE_VERSION,
                "interpretation_guidance_version": payload.get("interpretation_guidance_version"),
                "capability_rules": [item.model_dump(mode="json") for item in rules],
                "analysis_scope": scope, "database_version_id": database["version_id"],
                "database_checksum": database["checksum"],
                "database_provenance": manifest.provenance.model_dump(mode="json"),
                "threshold_type": "ga", "hit_thresholds": None,
                "archive_sha256": sha256_file(archive_path),
                "samples": [{key: value for key, value in sample.items() if key != "fasta_path"} for sample in samples],
                "bundled_example": {"example_id": PD10_ID, "source_manifest": "manifest.json"},
                "output_bytes": directory_size(run_target), "created_at": timestamp,
            })
            return db.get("projects", project_id) or {}
        except Exception:
            if db.get("projects", project_id):
                db.delete("projects", project_id)
            shutil.rmtree(target, ignore_errors=True)
            raise


def install_default_examples() -> None:
    with db.connect() as connection:
        marker = connection.execute(
            "SELECT value FROM application_metadata WHERE key='pd10_default_installed'"
        ).fetchone()
    if marker:
        return
    manifest_path = _asset_dir() / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    archive_sha256 = manifest.get("archive_sha256")
    matching = next(
        (
            row for row in db.list_rows("projects")
            if archive_sha256 and row.get("archive_sha256") == archive_sha256
        ),
        None,
    )
    if matching:
        db.update("projects", matching["id"], {
            "origin": "bundled_example", "example_id": PD10_ID,
        })
    else:
        restore_pd10()
    with db.connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO application_metadata (key,value) VALUES (?,?)",
            ("pd10_default_installed", "1"),
        )
