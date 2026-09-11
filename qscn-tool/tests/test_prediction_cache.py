import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qscn import db
from qscn.config import Settings
from qscn.prediction_cache import prepare_project_predictions, prediction_cache_key
from qscn.storage import sha256_file, write_json


def settings_for(root: Path) -> Settings:
    return Settings(
        data_dir=root / "data", builtin_database_dir=root / "builtins",
        frontend_dir=root / "frontend", redis_url="redis://unused",
        max_upload_bytes=1024, max_extracted_bytes=2048,
        max_genomes=10, max_archive_files=10, worker_ttl=60,
        min_free_bytes=1,
    )


def write_prediction(directory: Path, sample_id: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{sample_id}.faa").write_text(
        ">contig_1 # 1 # 9 # 1 # ID=1_1;partial=00\nMAAA\n", encoding="utf-8"
    )
    (directory / f"{sample_id}.fna").write_text(">contig_1\nATGGCCGCC\n", encoding="utf-8")
    (directory / f"{sample_id}.gff").write_text(
        "contig\tProdigal\tCDS\t1\t9\t.\t+\t0\tID=1_1;partial=00\n",
        encoding="utf-8",
    )
    gene = {
        "sample_id": sample_id, "gene_id": "contig_1",
        "original_sequence_id": "contig_1", "contig_id": "contig",
        "start": 1, "end": 9, "strand": "+", "partial_5prime": False,
        "partial_3prime": False, "partial_code": "00",
        "prodigal_internal_id": "1_1",
    }
    write_json(directory / f"{sample_id}.predicted_genes.json", [gene])
    (directory / f"{sample_id}.predicted_genes.tsv").write_text("sample_id\n", encoding="utf-8")
    write_json(directory / f"{sample_id}.prodigal.json", {"predicted_gene_count": 1})


class PredictionCacheTest(unittest.TestCase):
    def test_cache_key_tracks_input_and_prodigal_version_but_not_display_name(self):
        sample = {"sample_id": "sample", "display_name": "Original", "sha256": "a" * 64}
        original = prediction_cache_key([sample], "Prodigal 2.6.3")
        sample["display_name"] = "Renamed"
        self.assertEqual(prediction_cache_key([sample], "Prodigal 2.6.3"), original)
        sample["sha256"] = "b" * 64
        self.assertNotEqual(prediction_cache_key([sample], "Prodigal 2.6.3"), original)
        sample["sha256"] = "a" * 64
        self.assertNotEqual(prediction_cache_key([sample], "Prodigal future"), original)

    def test_legacy_run_is_absorbed_then_cache_is_reused_and_corruption_rebuilds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = settings_for(root)
            settings.ensure_directories()
            fasta = root / "sample.fna"
            fasta.write_text(">contig\nATGGCCGCC\n", encoding="utf-8")
            samples = [{
                "sample_id": "sample", "display_name": "Original",
                "fasta_path": str(fasta), "sha256": sha256_file(fasta),
            }]
            project = {
                "id": "project", "name": "P", "archive_path": "/archive.zip",
                "archive_sha256": "archive-sha", "input_kind": "genome",
                "status": "ready", "samples_json": json.dumps(samples),
                "created_at": db.now(), "updated_at": db.now(),
            }
            legacy_dir = settings.projects_dir / "project" / "runs" / "legacy" / "predictions"
            write_prediction(legacy_dir, "sample")
            write_json(legacy_dir.parent / "run_manifest.json", {
                "archive_sha256": "archive-sha", "prodigal_mode": "single",
                "tools": {"prodigal": "Prodigal 2.6.3"},
                "samples": [{"sample_id": "sample", "sha256": samples[0]["sha256"]}],
            })
            run = {
                "id": "legacy", "project_id": "project", "database_version_id": "db:1",
                "input_kind": "genome", "completeness_mode": "v2",
                "capability_rule_version": "3.0", "capability_rules_json": "[]",
                "sequence_evalue": None, "hit_rule_version": "1.0",
                "hit_thresholds_json": None, "analysis_scope_version": "1.0",
                "analysis_scope_json": "{}", "status": "complete", "stage": "complete",
                "progress": 1, "rq_job_id": None, "error": None, "error_code": None,
                "error_params_json": None, "created_at": db.now(), "updated_at": db.now(),
            }
            with patch("qscn.db.settings", settings), patch("qscn.prediction_cache.settings", settings):
                db.initialize()
                db.insert("projects", project)
                db.insert("runs", run)
                _, _, adopted = prepare_project_predictions(
                    project, "current", samples,
                    settings.projects_dir / "project" / "runs" / "current" / "predictions",
                    "Prodigal 2.6.3", lambda *_: self.fail("legacy adoption reran Prodigal"),
                )
                self.assertEqual(adopted["source"], "legacy_run")
                self.assertEqual(adopted["source_run_id"], "legacy")
                samples[0]["display_name"] = "Renamed only"
                _, _, reused = prepare_project_predictions(
                    project, "next", samples,
                    settings.projects_dir / "project" / "runs" / "next" / "predictions",
                    "Prodigal 2.6.3", lambda *_: self.fail("cache hit reran Prodigal"),
                )
                self.assertTrue(reused["reused"])
                self.assertEqual(reused["cache_key"], adopted["cache_key"])

                cache = settings.projects_dir / "project" / "gene-predictions" / prediction_cache_key(samples, "Prodigal 2.6.3")
                (cache / "sample.faa").write_text("corrupt\n", encoding="utf-8")
                calls = []

                def regenerate(sample, _kind, destination):
                    calls.append(sample["sample_id"])
                    write_prediction(destination, sample["sample_id"])

                with patch("qscn.prediction_cache.run_prodigal", side_effect=regenerate):
                    _, _, rebuilt = prepare_project_predictions(
                        project, "rebuilt", samples,
                        settings.projects_dir / "project" / "runs" / "rebuilt" / "predictions",
                        "Prodigal 2.6.3", lambda *_: None,
                    )
                self.assertEqual(calls, ["sample"])
                self.assertFalse(rebuilt["reused"])
                self.assertEqual(rebuilt["source"], "generated")

    def test_failed_prediction_does_not_publish_partial_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = settings_for(root)
            settings.ensure_directories()
            fasta = root / "sample.fna"
            fasta.write_text(">contig\nATG\n", encoding="utf-8")
            sample = {"sample_id": "sample", "fasta_path": str(fasta), "sha256": sha256_file(fasta)}
            project = {"id": "project", "archive_sha256": "sha"}
            with patch("qscn.db.settings", settings), patch("qscn.prediction_cache.settings", settings), patch(
                "qscn.prediction_cache.run_prodigal", side_effect=RuntimeError("failed")
            ):
                db.initialize()
                with self.assertRaisesRegex(RuntimeError, "failed"):
                    prepare_project_predictions(
                        project, "run", [sample], root / "run-predictions",
                        "Prodigal future", lambda *_: None,
                    )
            cache_root = settings.projects_dir / "project" / "gene-predictions"
            self.assertFalse(any(path.is_dir() for path in cache_root.iterdir()))


if __name__ == "__main__":
    unittest.main()
