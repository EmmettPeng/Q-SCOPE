import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from qscn import db
from qscn.config import Settings
from qscn.pipeline import (
    _enrich_saved_genome_hits,
    _write_sif,
    build_export,
    create_interpretation,
    execute_run,
    get_export_status,
    get_interpretation_artifact,
)
from qscn.schemas import CAPABILITY_RULE_VERSION, DatabaseManifest
from qscn.storage import write_json


class InterpretationExportTest(unittest.TestCase):
    def test_saved_genome_hits_are_enriched_without_rescanning(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            predictions = base / "predictions"
            predictions.mkdir()
            (predictions / "MAG.1.gff").write_text(
                "contig\tProdigal\tCDS\t4\t99\t.\t-\t0\tID=1_1;partial=01\n",
                encoding="utf-8",
            )
            (predictions / "MAG.1.faa").write_text(
                ">contig_1 # 4 # 99 # -1 # ID=1_1;partial=01\nMAAA\n",
                encoding="utf-8",
            )
            enriched = _enrich_saved_genome_hits(
                base,
                [{"sample_id": "MAG.1"}],
                [{"sample_id": "MAG.1", "sequence_id": "contig_1", "contig_id": None,
                  "partial_5prime": None, "partial_3prime": None}],
            )
        self.assertEqual(enriched[0]["contig_id"], "contig")
        self.assertEqual((enriched[0]["gene_start"], enriched[0]["gene_end"]), (4, 99))
        self.assertEqual(enriched[0]["gene_strand"], "-")
        self.assertFalse(enriched[0]["partial_5prime"])
        self.assertTrue(enriched[0]["partial_3prime"])

    def test_reinterpretation_reuses_hits_and_writes_whitelisted_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = Settings(
                data_dir=root / "data",
                builtin_database_dir=root / "builtins",
                frontend_dir=root / "frontend",
                redis_url="redis://unused",
                max_upload_bytes=1024,
                max_extracted_bytes=2048,
                max_genomes=10,
                max_archive_files=10,
                worker_ttl=60,
            )
            manifest = DatabaseManifest.model_validate({
                "database_id": "test", "name": "Test", "version": "1", "source": "source",
                "classification_scheme": "native", "threshold_policy": {"type": "ga"},
                "schema_version": "2.0",
                "components": [
                    {"profile_id": "A", "display_name": "Alpha"},
                    {"profile_id": "B", "display_name": "Beta"},
                    {"profile_id": "C", "display_name": "C"},
                    {"profile_id": "D", "display_name": "D"},
                ],
                "pathways": [{
                    "pathway_id": "p", "name": "P", "signal_name": "S",
                    "sending_profiles": ["A"], "receiving_profiles": ["B"],
                    "references": ["doi:1", "doi:1"],
                }, {
                    "pathway_id": "other", "name": "Other", "signal_name": "Other signal",
                    "sending_profiles": ["C"], "receiving_profiles": ["D"],
                }],
            })
            manifest_path = root / "manifest.json"
            manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
            hmm_path = root / "profiles.hmm"
            hmm_path.write_text("HMMER3/f\nNAME A\n//\n", encoding="utf-8")
            samples = [
                {"sample_id": "a", "display_name": "A", "fasta_path": "/a.faa"},
                {"sample_id": "b", "display_name": "B", "fasta_path": "/b.faa"},
            ]
            rules = [
                {"pathway_id": "p", "role": "sending", "strategy": "all", "required_profiles": []},
                {"pathway_id": "p", "role": "receiving", "strategy": "all", "required_profiles": []},
                {"pathway_id": "other", "role": "sending", "strategy": "all", "required_profiles": []},
                {"pathway_id": "other", "role": "receiving", "strategy": "all", "required_profiles": []},
            ]
            with patch("qscn.db.settings", settings), patch("qscn.pipeline.settings", settings), patch("qscn.prediction_cache.settings", settings):
                db.initialize()
                timestamp = db.now()
                db.insert("projects", {
                    "id": "project", "name": "P", "archive_path": "/input.zip",
                    "archive_sha256": "sha", "input_kind": "protein", "status": "ready",
                    "samples_json": json.dumps(samples), "created_at": timestamp, "updated_at": timestamp,
                })
                db.insert("databases", {
                    "version_id": "test:1", "database_id": "test", "name": "Test", "version": "1",
                    "source": "source", "classification_scheme": "native", "checksum": "checksum",
                    "hmm_path": str(hmm_path), "manifest_path": str(manifest_path), "threshold_type": "ga",
                    "default_evalue": None, "builtin": 0, "created_at": timestamp,
                })
                db.insert("runs", {
                    "id": "run", "project_id": "project", "database_version_id": "test:1",
                    "input_kind": "protein", "capability_rule_version": CAPABILITY_RULE_VERSION,
                    "capability_rules_json": json.dumps(rules), "sequence_evalue": None,
                    "status": "complete", "stage": "complete", "progress": 1, "rq_job_id": None,
                    "error": None, "created_at": timestamp, "updated_at": timestamp,
                })
                base = settings.projects_dir / "project" / "runs" / "run"
                write_json(base / "hits.json", [
                    {"hit_id": "h1", "sample_id": "a", "profile_id": "A"},
                    {"hit_id": "h2", "sample_id": "b", "profile_id": "B"},
                    {"hit_id": "h3", "sample_id": "a", "profile_id": "C"},
                ])
                with patch("qscn.pipeline.run_hmmscan") as scan:
                    result = create_interpretation(
                        "run", rules,
                        {"mode": "pathways", "requested_values": ["p"]},
                    )
                    scan.assert_not_called()
                self.assertEqual(result["network"]["summary"]["total_edges"], 1)
                self.assertEqual(result["analysis_scope"]["resolved_pathway_ids"], ["p"])
                self.assertEqual({item["pathway_id"] for item in result["capabilities"]}, {"p"})
                self.assertEqual(len(result["hits"]), 3)
                self.assertEqual(result["component_definitions"]["A"]["display_label"], "Alpha(A)")
                self.assertEqual(result["hits"][0]["profile_display_label"], "Alpha(A)")
                self.assertEqual(
                    result["capabilities"][0]["observed_components_labels"], ["Alpha(A)"]
                )
                self.assertEqual(
                    result["network"]["edges"][0]["sender_component_labels"], ["Alpha(A)"]
                )
                self.assertNotIn("supporting_hit_ids", result["network"]["edges"][0])
                interpretation_id = result["interpretation_id"]
                self.assertEqual(
                    db.get("interpretations", interpretation_id)["completeness_mode"], "v2"
                )
                self.assertEqual(
                    json.loads(db.get("interpretations", interpretation_id)["analysis_scope_json"])["mode"],
                    "pathways",
                )
                sif = get_interpretation_artifact("run", interpretation_id, "network.sif")
                self.assertEqual(
                    sif.read_text(encoding="utf-8"),
                    "a\tpotential_communication__pathway=p\tb\n",
                )
                edge_header = get_interpretation_artifact(
                    "run", interpretation_id, "network-edges.tsv"
                ).read_text(encoding="utf-8").splitlines()[0]
                self.assertIn("references", edge_header)
                self.assertNotIn("supporting_hit_ids", edge_header)
                interpretation_dir = base / "interpretations" / interpretation_id
                self.assertTrue((interpretation_dir / "summary.json").is_file())
                self.assertTrue((base / "hits.ndjson").is_file())
                write_json(base / "run_manifest.json", {"run_id": "run"})
                analysis_zip = build_export("run", interpretation_id, "analysis")
                self.assertFalse(analysis_zip.with_suffix(".zip.partial").exists())
                with zipfile.ZipFile(analysis_zip) as archive:
                    names = set(archive.namelist())
                self.assertIn("run_manifest.json", names)
                self.assertIn(f"interpretations/{interpretation_id}/summary.json", names)
                self.assertNotIn("hits.json", names)
                self.assertNotIn(f"interpretations/{interpretation_id}/results.json", names)
                self.assertEqual(get_export_status("run", interpretation_id, "analysis")["status"], "complete")
                self.assertEqual(build_export("run", interpretation_id, "analysis"), analysis_zip)
                with self.assertRaisesRegex(ValueError, "unknown"):
                    get_interpretation_artifact("run", interpretation_id, "../results.json")

    def test_sif_preserves_pathway_edges_and_writes_isolated_nodes_deterministically(self):
        nodes = [
            {"sample_id": "z"}, {"sample_id": "a"}, {"sample_id": "b"},
        ]
        edges = [
            {"id": "3", "source_sample": "b", "target_sample": "b", "pathway_id": "self"},
            {"id": "2", "source_sample": "a", "target_sample": "b", "pathway_id": "QS / α"},
            {"id": "1", "source_sample": "a", "target_sample": "b", "pathway_id": "other"},
            {"id": "duplicate", "source_sample": "a", "target_sample": "b", "pathway_id": "other"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "network.sif"
            _write_sif(path, nodes, edges)
            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines, [
            "a\tpotential_communication__pathway=QS%20%2F%20%CE%B1\tb",
            "a\tpotential_communication__pathway=other\tb",
            "b\tpotential_communication__pathway=self\tb",
            "z",
        ])
        self.assertTrue(all(len(line.split("\t")) in {1, 3} for line in lines))

    def test_genome_pipeline_finishes_all_predictions_before_scanning_with_monotonic_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = Settings(
                data_dir=root / "data", builtin_database_dir=root / "builtins",
                frontend_dir=root / "frontend", redis_url="redis://unused",
                max_upload_bytes=1024, max_extracted_bytes=2048,
                max_genomes=10, max_archive_files=10, worker_ttl=60,
            )
            manifest = DatabaseManifest.model_validate({
                "database_id": "test", "name": "Test", "version": "1", "source": "source",
                "classification_scheme": "native", "threshold_policy": {"type": "ga"},
                "pathways": [{"pathway_id": "p", "name": "P", "signal_name": "S", "sending_profiles": ["A"]}],
            })
            manifest_path = root / "manifest.json"
            manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
            hmm_path = root / "profiles.hmm"
            hmm_path.write_text("HMMER3/f\nNAME A\n//\n", encoding="utf-8")
            samples = [
                {"sample_id": sample_id, "display_name": sample_id.upper(), "fasta_path": str(root / f"{sample_id}.fna"), "sha256": f"sha-{sample_id}"}
                for sample_id in ("a", "b")
            ]
            events: list[str] = []
            progress: list[float] = []

            def fake_prodigal(sample, _kind, output_dir):
                events.append(f"predict:{sample['sample_id']}")
                sample_id = sample["sample_id"]
                protein = output_dir / f"{sample_id}.faa"
                genes = output_dir / f"{sample_id}.predicted_genes.json"
                protein.parent.mkdir(parents=True, exist_ok=True)
                protein.write_text(">contig_1 # 1 # 9 # 1 # ID=1_1;partial=00\nMAAA\n", encoding="utf-8")
                (output_dir / f"{sample_id}.fna").write_text(">contig_1\nATGGCCGCC\n", encoding="utf-8")
                (output_dir / f"{sample_id}.gff").write_text("contig\tProdigal\tCDS\t1\t9\t.\t+\t0\tID=1_1;partial=00\n", encoding="utf-8")
                parsed = [{"sample_id": sample_id, "gene_id": "contig_1", "original_sequence_id": "contig_1", "contig_id": "contig", "start": 1, "end": 9, "strand": "+", "partial_5prime": False, "partial_3prime": False, "partial_code": "00", "prodigal_internal_id": "1_1"}]
                write_json(genes, parsed)
                (output_dir / f"{sample_id}.predicted_genes.tsv").write_text("sample_id\n", encoding="utf-8")
                write_json(output_dir / f"{sample_id}.prodigal.json", {"predicted_gene_count": 1})
                return {"protein_path": str(protein), "genes_path": str(genes)}

            def fake_scan(sample_id, *_args):
                events.append(f"scan:{sample_id}")
                return [], {"sample_id": sample_id, "peak_rss_kb": 1}

            with patch("qscn.db.settings", settings), patch("qscn.pipeline.settings", settings), patch("qscn.prediction_cache.settings", settings):
                db.initialize()
                timestamp = db.now()
                db.insert("projects", {
                    "id": "project", "name": "P", "archive_path": "/input.zip",
                    "archive_sha256": "sha", "input_kind": "genome", "status": "ready",
                    "samples_json": json.dumps(samples), "created_at": timestamp, "updated_at": timestamp,
                })
                db.insert("databases", {
                    "version_id": "test:1", "database_id": "test", "name": "Test", "version": "1",
                    "source": "source", "classification_scheme": "native", "checksum": "checksum",
                    "hmm_path": str(hmm_path), "manifest_path": str(manifest_path), "threshold_type": "ga",
                    "default_evalue": None, "builtin": 0, "created_at": timestamp,
                })
                db.insert("runs", {
                    "id": "run", "project_id": "project", "database_version_id": "test:1",
                    "input_kind": "genome", "capability_rule_version": CAPABILITY_RULE_VERSION,
                    "capability_rules_json": json.dumps([{"pathway_id": "p", "role": "sending", "strategy": "all", "required_profiles": []}]), "sequence_evalue": None,
                    "hit_rule_version": "1.0", "hit_thresholds_json": None,
                    "analysis_scope_version": "1.0", "analysis_scope_json": json.dumps({"version": "1.0", "mode": "all", "requested_values": [], "resolved_pathway_ids": []}),
                    "status": "queued", "stage": "queued", "progress": 0, "rq_job_id": None,
                    "error": None, "error_code": None, "error_params_json": None,
                    "created_at": timestamp, "updated_at": timestamp,
                })
                original_update = __import__("qscn.pipeline", fromlist=["_update_run"])._update_run

                def capture_update(run_id, stage, value, *args, **kwargs):
                    progress.append(value)
                    return original_update(run_id, stage, value, *args, **kwargs)

                with (
                    patch("qscn.prediction_cache.run_prodigal", side_effect=fake_prodigal),
                    patch("qscn.pipeline.run_hmmscan", side_effect=fake_scan),
                    patch("qscn.pipeline.tool_version", return_value="test"),
                    patch("qscn.pipeline._update_run", side_effect=capture_update),
                ):
                    execute_run("run")
                    first_progress = list(progress)
                    progress.clear()
                    second = dict(db.get("runs", "run"))
                    second.update({
                        "id": "run-2", "status": "queued", "stage": "queued",
                        "progress": 0, "rq_job_id": None, "created_at": db.now(),
                        "updated_at": db.now(),
                    })
                    second.pop("rowid", None)
                    db.insert("runs", second)
                    execute_run("run-2")
                    first_manifest = json.loads((settings.projects_dir / "project" / "runs" / "run" / "run_manifest.json").read_text())
                    second_manifest = json.loads((settings.projects_dir / "project" / "runs" / "run-2" / "run_manifest.json").read_text())
            self.assertEqual(events, ["predict:a", "predict:b", "scan:a", "scan:b", "scan:a", "scan:b"])
            self.assertEqual(first_progress, sorted(first_progress))
            self.assertEqual(progress, sorted(progress))
            self.assertEqual(progress[-1], 1.0)
            self.assertFalse(first_manifest["gene_prediction"]["reused"])
            self.assertTrue(second_manifest["gene_prediction"]["reused"])
            self.assertEqual(second_manifest["gene_prediction"]["source"], "project_cache")


if __name__ == "__main__":
    unittest.main()
