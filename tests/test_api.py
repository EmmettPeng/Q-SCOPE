import asyncio
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import UploadFile
from qscn import SCHEMA_VERSION, db
from qscn.api import (
    _run_progress_detail,
    create_database,
    create_run,
    database_pathway_template,
    health,
    reconcile_interrupted_runs,
)
from qscn.config import Settings
from qscn.schemas import DatabaseManifest, RunRequest


def test_settings(root: Path) -> Settings:
    return Settings(
        data_dir=root / "data", builtin_database_dir=root, frontend_dir=root,
        redis_url="redis://unused", max_upload_bytes=1024,
        max_extracted_bytes=4096, max_genomes=10, max_archive_files=10,
        worker_ttl=60, min_free_bytes=1,
    )


class V03SchemaTest(unittest.TestCase):
    def test_database_api_accepts_new_two_file_mode_and_legacy_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = test_settings(root)
            settings.ensure_directories()
            hmm_bytes = b"HMMER3/f\nNAME A\nGA 10 10;\n//\n"
            table_bytes = b"Pathway\tSignal_type\tSignal_Sending\tSignal_Receiving\tReferences\nP\tS\tA\t\t\n"
            legacy_manifest = {
                "database_id": "legacy", "name": "Legacy", "version": "1", "source": "test",
                "classification_scheme": "test", "threshold_policy": {"type": "ga"},
                "pathways": [{
                    "pathway_id": "P", "name": "P", "signal_name": "S",
                    "sending_profiles": ["A"], "receiving_profiles": [],
                }],
            }
            legacy_bytes = io.BytesIO()
            with zipfile.ZipFile(legacy_bytes, "w") as bundle:
                bundle.writestr("profiles.hmm", hmm_bytes)
                bundle.writestr("manifest.json", json.dumps(legacy_manifest))

            def fake_hmmpress(command, timeout):
                pressed = Path(command[1])
                for suffix in (".h3f", ".h3i", ".h3m", ".h3p"):
                    Path(str(pressed) + suffix).write_text("index", encoding="utf-8")
                return SimpleNamespace(returncode=0, stderr="")

            with (
                patch("qscn.db.settings", settings),
                patch("qscn.api.settings", settings),
                patch("qscn.databases.settings", settings),
                patch("qscn.databases.run_external", side_effect=fake_hmmpress),
            ):
                db.initialize()
                tabular = asyncio.run(create_database(
                    archive=None,
                    hmm_file=UploadFile(filename="profiles.hmm", file=io.BytesIO(hmm_bytes)),
                    pathway_file=UploadFile(filename="pathways.txt", file=io.BytesIO(table_bytes)),
                    name="Tabular", version="1", source="", classification_scheme="",
                    threshold_type="ga", default_full_evalue=None, default_domain_i_evalue=None,
                ))
                legacy_bytes.seek(0)
                legacy = asyncio.run(create_database(
                    archive=UploadFile(filename="legacy.zip", file=legacy_bytes),
                    hmm_file=None, pathway_file=None, name=None, version=None, source=None,
                    classification_scheme=None, threshold_type=None,
                    default_full_evalue=None, default_domain_i_evalue=None,
                ))
            self.assertEqual(tabular["database_id"], "custom-tabular")
            self.assertEqual(tabular["source"], "User provided")
            self.assertEqual(legacy["database_id"], "legacy")

    def test_database_template_is_downloadable_tsv_with_two_qsp_examples(self):
        response = database_pathway_template()
        content = response.body.decode("utf-8")
        self.assertIn("text/tab-separated-values", response.media_type)
        self.assertIn("qscn-pathways-template.tsv", response.headers["content-disposition"])
        self.assertEqual(content.splitlines()[0], "Pathway\tSignal_type\tSignal_Sending\tSignal_Receiving\tReferences")
        self.assertEqual(len(content.splitlines()), 3)
        self.assertIn("LuxM_LuxN_system", content)
        self.assertIn("LuxI_LuxR_system", content)
        self.assertIn(";", content)

    def test_run_progress_detail_reports_phase_sample_counts(self):
        run = {
            "project_id": "project", "input_kind": "genome",
            "stage": "predicting:b", "progress": 0.175,
        }
        project = {"samples_json": json.dumps([
            {"sample_id": "a"}, {"sample_id": "b"}, {"sample_id": "c"}, {"sample_id": "d"},
        ])}
        with patch("qscn.api.db.get", return_value=project):
            detail = _run_progress_detail(run)
        self.assertEqual(detail["phase"], "predicting")
        self.assertEqual(detail["current_sample_id"], "b")
        self.assertEqual(detail["completed_samples"], 2)
        self.assertEqual(detail["total_samples"], 4)
        self.assertAlmostEqual(detail["phase_progress"], 0.5)

    def test_fresh_schema_is_versioned(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = test_settings(Path(temp))
            with patch("qscn.db.settings", settings):
                db.initialize()
                with db.connect() as connection:
                    row = connection.execute(
                        "SELECT value FROM application_metadata WHERE key='schema_version'"
                    ).fetchone()
            self.assertEqual(row["value"], SCHEMA_VERSION)

    def test_legacy_volume_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = test_settings(Path(temp))
            with patch("qscn.db.settings", settings):
                with db.connect() as connection:
                    connection.execute("CREATE TABLE projects (id TEXT PRIMARY KEY)")
                    connection.execute("INSERT INTO projects VALUES ('old')")
                with self.assertRaisesRegex(db.SchemaVersionError, "fresh volume"):
                    db.initialize()
                with db.connect() as connection:
                    self.assertEqual(connection.execute("SELECT id FROM projects").fetchone()["id"], "old")

    def test_health_exposes_release_schema_and_build(self):
        result = health()
        self.assertEqual(result["schema_version"], SCHEMA_VERSION)
        self.assertEqual(result["version"], "0.3.1")

    def test_restart_marks_only_orphaned_running_jobs_interrupted(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = test_settings(Path(temp))
            with patch("qscn.db.settings", settings):
                db.initialize()
                timestamp = db.now()
                db.insert("projects", {
                    "id": "project", "name": "P", "archive_path": "/input.zip",
                    "archive_sha256": "sha", "input_kind": "protein", "status": "ready",
                    "samples_json": "[]", "created_at": timestamp, "updated_at": timestamp,
                })
                for run_id, job_id in (("orphan", "gone"), ("active", "live")):
                    db.insert("runs", {
                        "id": run_id, "project_id": "project", "database_version_id": "db",
                        "input_kind": "protein", "capability_rule_version": "2.0",
                        "capability_rules_json": "[]", "sequence_evalue": None,
                        "hit_rule_version": "1.0", "hit_thresholds_json": None,
                        "analysis_scope_version": "1.0", "analysis_scope_json": json.dumps({
                            "version": "1.0", "mode": "all", "requested_values": [],
                            "resolved_pathway_ids": [],
                        }), "status": "running", "stage": "scanning", "progress": 0.5,
                        "rq_job_id": job_id, "error": None, "error_code": None,
                        "error_params_json": None, "created_at": timestamp, "updated_at": timestamp,
                    })
                active_job = type("JobState", (), {"get_status": lambda self, refresh=True: "started"})()
                def fetch_job(job_id, connection):
                    if job_id == "gone":
                        raise RuntimeError("missing")
                    return active_job

                with (
                    patch("qscn.api.settings", settings),
                    patch("qscn.api.Redis.from_url", return_value=object()),
                    patch("qscn.api.Job.fetch", side_effect=fetch_job),
                ):
                    reconcile_interrupted_runs()
                self.assertEqual(db.get("runs", "orphan")["status"], "failed")
                self.assertEqual(db.get("runs", "orphan")["error_code"], "analysis_interrupted")
                self.assertEqual(db.get("runs", "active")["status"], "running")


class RunCreationTest(unittest.TestCase):
    def test_legacy_evalue_override_maps_to_both_hit_thresholds(self):
        manifest = DatabaseManifest.model_validate({
            "database_id": "db", "name": "DB", "version": "1", "source": "test",
            "classification_scheme": "native",
            "threshold_policy": {"type": "evalue", "default_evalue": 1e-5},
            "pathways": [{
                "pathway_id": "p", "name": "P", "signal_name": "S",
                "sending_profiles": ["A"], "receiving_profiles": ["B"],
            }],
        })
        request = RunRequest(
            input_kind="protein", database_version_id="db:1", sequence_evalue_override=1e-8,
            analysis_scope={"mode": "signals", "requested_values": ["S"]},
        )
        with tempfile.TemporaryDirectory() as temp:
            settings = test_settings(Path(temp))
            with patch("qscn.db.settings", settings):
                db.initialize()
                timestamp = db.now()
                db.insert("projects", {
                    "id": "project", "name": "P", "archive_path": "/input.zip",
                    "archive_sha256": "sha", "input_kind": "protein", "status": "ready",
                    "samples_json": "[{}]", "created_at": timestamp, "updated_at": timestamp,
                })
                database = {"version_id": "db:1", "threshold_type": "evalue", "default_evalue": 1e-5}
                with (
                    patch("qscn.api.get_database", return_value=database),
                    patch("qscn.api.load_manifest", return_value=manifest),
                    patch("qscn.api._enqueue"), patch("qscn.api.get_run", return_value={"status": "queued"}),
                ):
                    create_run("project", request)
                with db.connect() as connection:
                    row = connection.execute(
                        "SELECT hit_rule_version, hit_thresholds_json, analysis_scope_json FROM runs"
                    ).fetchone()
                self.assertEqual(row["hit_rule_version"], "1.0")
                self.assertEqual(json.loads(row["hit_thresholds_json"]), {
                    "full_evalue_max": 1e-8, "domain_i_evalue_max": 1e-8,
                })
                self.assertEqual(json.loads(row["analysis_scope_json"])["resolved_pathway_ids"], ["p"])


if __name__ == "__main__":
    unittest.main()
