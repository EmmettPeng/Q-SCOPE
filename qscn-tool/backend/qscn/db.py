from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from .config import settings
from . import SCHEMA_VERSION


class SchemaVersionError(RuntimeError):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS application_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  archive_path TEXT NOT NULL,
  archive_sha256 TEXT NOT NULL,
  input_kind TEXT,
  status TEXT NOT NULL,
  samples_json TEXT,
  origin TEXT NOT NULL DEFAULT 'user',
  example_id TEXT UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  database_version_id TEXT NOT NULL,
  input_kind TEXT NOT NULL,
  completeness_mode TEXT NOT NULL DEFAULT 'v2',
  capability_rule_version TEXT NOT NULL,
  capability_rules_json TEXT NOT NULL,
  sequence_evalue REAL,
  hit_rule_version TEXT NOT NULL DEFAULT 'legacy-0.2',
  hit_thresholds_json TEXT,
  analysis_scope_version TEXT NOT NULL DEFAULT '1.0',
  analysis_scope_json TEXT NOT NULL DEFAULT '{"version":"1.0","mode":"all","requested_values":[],"resolved_pathway_ids":[]}',
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  progress REAL NOT NULL DEFAULT 0,
  rq_job_id TEXT,
  error TEXT,
  error_code TEXT,
  error_params_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interpretations (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  completeness_mode TEXT NOT NULL DEFAULT 'v2',
  capability_rule_version TEXT NOT NULL,
  capability_rules_json TEXT NOT NULL,
  analysis_scope_version TEXT NOT NULL DEFAULT '1.0',
  analysis_scope_json TEXT NOT NULL DEFAULT '{"version":"1.0","mode":"all","requested_values":[],"resolved_pathway_ids":[]}',
  name TEXT,
  result_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS databases (
  version_id TEXT PRIMARY KEY,
  database_id TEXT NOT NULL,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  source TEXT NOT NULL,
  classification_scheme TEXT NOT NULL,
  checksum TEXT NOT NULL,
  hmm_path TEXT NOT NULL,
  manifest_path TEXT NOT NULL,
  threshold_type TEXT NOT NULL,
  default_evalue REAL,
  provenance_json TEXT NOT NULL DEFAULT '{}',
  builtin INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_project ON runs(project_id);
CREATE INDEX IF NOT EXISTS idx_interpretations_run ON interpretations(run_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_example_id
  ON projects(example_id) WHERE example_id IS NOT NULL;
"""


def now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def connect(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    settings.ensure_directories()
    connection = sqlite3.connect(path or settings.sqlite_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize() -> None:
    with connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        application_tables = tables & {"projects", "runs", "interpretations", "databases"}
        if application_tables and "application_metadata" not in tables:
            raise SchemaVersionError(
                "This data volume has no supported schema metadata. "
                "Start Q-SCOPE with a fresh volume. The existing volume was not modified."
            )
        if "application_metadata" in tables:
            row = connection.execute(
                "SELECT value FROM application_metadata WHERE key='schema_version'"
            ).fetchone()
            if row and row["value"] != SCHEMA_VERSION:
                raise SchemaVersionError(
                    f"Unsupported Q-SCOPE schema {row['value']}; this release requires schema {SCHEMA_VERSION}. "
                    "The existing volume was not modified."
                )
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT OR REPLACE INTO application_metadata (key,value) VALUES ('schema_version',?)",
            (SCHEMA_VERSION,),
        )


def insert(table: str, values: dict[str, Any]) -> None:
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    with connect() as connection:
        connection.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            tuple(values.values()),
        )


def update(table: str, row_id: str, values: dict[str, Any]) -> None:
    values = {**values, "updated_at": now()} if table in {"projects", "runs", "interpretations"} else values
    assignments = ", ".join(f"{column}=?" for column in values)
    with connect() as connection:
        connection.execute(
            f"UPDATE {table} SET {assignments} WHERE id=?",
            (*values.values(), row_id),
        )


def get(table: str, row_id: str) -> dict[str, Any] | None:
    key = "version_id" if table == "databases" else "id"
    with connect() as connection:
        row = connection.execute(
            f"SELECT * FROM {table} WHERE {key}=?", (row_id,)
        ).fetchone()
    return dict(row) if row else None


def list_rows(table: str, where: str = "", params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY created_at DESC"
    with connect() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def delete(table: str, row_id: str) -> None:
    key = "version_id" if table == "databases" else "id"
    with connect() as connection:
        connection.execute(f"DELETE FROM {table} WHERE {key}=?", (row_id,))


def decode_project(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    if result.get("samples_json"):
        result["samples"] = json.loads(result.pop("samples_json"))
    else:
        result.pop("samples_json", None)
        result["samples"] = []
    return result
