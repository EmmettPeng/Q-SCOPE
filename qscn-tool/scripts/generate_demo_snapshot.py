#!/usr/bin/env python3
"""Generate the browser-only PD10 snapshot from Q-SCOPE's public serializers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "output", nargs="?",
        default=ROOT / "frontend/public/demo/demo-snapshot.json",
        type=Path,
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="qscope-demo-") as temporary:
        os.environ["QSCN_DATA_DIR"] = temporary
        os.environ["QSCN_BUILTIN_DATABASE_DIR"] = str(ROOT / "databases")
        os.environ["QSCN_BUILTIN_EXAMPLES_DIR"] = str(ROOT / "examples")

        from qscn import SCHEMA_VERSION, __release__, __version__, db
        from qscn import api
        from qscn.databases import register_builtins
        from qscn.examples import install_default_examples

        api.settings.ensure_directories()
        db.initialize()
        register_builtins()
        install_default_examples()

        projects = api.projects()
        if len(projects) != 1 or projects[0].get("example_id") != "pd10":
            raise RuntimeError("expected exactly one installed PD10 project")
        project = projects[0]
        tree = api.project_analysis_tree(project["id"])
        run_id = tree["databases"][0]["runs"][0]["id"]
        run = api.get_run(run_id)
        interpretation_id = run["interpretations"][0]["id"]
        result = api.results(run_id, interpretation_id=interpretation_id, summary=False)
        databases = api.databases()
        profiles = {
            item["version_id"]: api.database_profiles(
                item["version_id"], query="", offset=0, limit=200,
            )["items"]
            for item in databases
        }
        # KEGG has more than the API page maximum, so request its second page.
        for item in databases:
            if item["profile_count"] > len(profiles[item["version_id"]]):
                profiles[item["version_id"]].extend(api.database_profiles(
                    item["version_id"], query="", offset=200, limit=200,
                )["items"])

        source_manifest = ROOT / "examples/pd10/manifest.json"
        snapshot = {
            "metadata": {
                "snapshot_format_version": "1.0",
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "qscope_version": __version__,
                "qscope_release": __release__,
                "schema_version": SCHEMA_VERSION,
                "database_version_id": result["database"]["version_id"],
                "capability_rule_version": result["capability_rule_version"],
                "hit_rule_version": result.get("hit_rule_version"),
                "evidence_rule_version": result.get("evidence_rule_version"),
                "source_manifest_sha256": sha256(source_manifest),
                "source_hits_sha256": sha256(ROOT / "examples/pd10/hits.json"),
            },
            "projects": projects,
            "databases": databases,
            "examples": api.examples(),
            "analysis_tree": tree,
            "run": run,
            "results": result,
            "profiles": profiles,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {args.output} ({args.output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
