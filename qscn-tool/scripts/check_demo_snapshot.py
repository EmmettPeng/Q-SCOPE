#!/usr/bin/env python3
"""Validate the committed static demo without loading application dependencies."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "frontend/public/demo/demo-snapshot.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
metadata = payload["metadata"]
project = payload["projects"][0]
run = payload["run"]
results = payload["results"]
tree_run = payload["analysis_tree"]["databases"][0]["runs"][0]

assert metadata["snapshot_format_version"] == "1.0"
assert metadata["source_manifest_sha256"] == digest(ROOT / "examples/pd10/manifest.json")
assert metadata["source_hits_sha256"] == digest(ROOT / "examples/pd10/hits.json")
assert project["id"] == run["project_id"] == payload["analysis_tree"]["project_id"]
assert run["id"] == tree_run["id"] == results["run_id"]
assert results["interpretation_id"] in {item["id"] for item in run["interpretations"]}
assert len(results["samples"]) == project["samples"].__len__() == 10
assert len(results["hits"]) > 0
result_database_id = results["database"]["version_id"]
database = next(item for item in payload["databases"] if item["version_id"] == result_database_id)
assert len(payload["profiles"][result_database_id]) == database["profile_count"]
assert not any(key in payload for key in ("archive", "predictions", "sqlite", "hmm"))
print(f"Validated {SNAPSHOT} ({SNAPSHOT.stat().st_size:,} bytes)")
