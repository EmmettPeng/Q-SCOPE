import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from qscn import db
from qscn.config import Settings
from qscn.databases import (
    DatabaseError,
    GUIDANCE_TABLE_HEADERS,
    COMPONENT_TABLE_HEADERS,
    PATHWAY_TABLE_HEADERS,
    custom_database_id,
    hmm_profiles,
    import_custom_database,
    import_tabular_database,
    normalize_legacy_manifest,
    parse_guidance_table,
    parse_component_table,
    parse_pathway_table,
    validate_manifest_profiles,
)
from qscn.storage import sha256_file
from qscn.schemas import DatabaseManifest


ROOT = Path(__file__).resolve().parents[1]


class DatabaseTest(unittest.TestCase):
    def test_component_table_requires_complete_unique_hmm_profile_names(self):
        with tempfile.TemporaryDirectory() as temp:
            table = Path(temp) / "components.tsv"
            table.write_text(
                "\t".join(COMPONENT_TABLE_HEADERS) + "\nA\tAlpha\nB\tBeta\n",
                encoding="utf-8",
            )
            self.assertEqual(parse_component_table(table, ["A", "B"]), [
                {"profile_id": "A", "display_name": "Alpha"},
                {"profile_id": "B", "display_name": "Beta"},
            ])
            table.write_text("Profile_ID\tDisplay_Name\nA\tAlpha\n", encoding="utf-8")
            with self.assertRaisesRegex(DatabaseError, "every HMM profile"):
                parse_component_table(table, ["A", "B"])

    def test_pathway_table_parses_bom_crlf_semicolon_values_and_single_roles(self):
        with tempfile.TemporaryDirectory() as temp:
            table = Path(temp) / "pathways.txt"
            table.write_text(
                "\ufeffReferences\tSignal_Receiving\tPathway\tSignal_type\tSignal_Sending\r\n"
                " ref1 ; ref2;ref1 \t R1 ; R2;R1 \t Path A \t AI-1 \t S1 ; S2 ;S1 \r\n"
                "\tR3\tPath B\tAI-2\t\r\n",
                encoding="utf-8",
            )
            pathways = parse_pathway_table(table)
        self.assertEqual(pathways[0]["pathway_id"], "Path A")
        self.assertEqual(pathways[0]["sending_profiles"], ["S1", "S2"])
        self.assertEqual(pathways[0]["receiving_profiles"], ["R1", "R2"])
        self.assertEqual(pathways[0]["references"], ["ref1", "ref2"])
        self.assertEqual(pathways[1]["sending_profiles"], [])

    def test_pathway_table_rejects_headers_rows_duplicates_encoding_and_empty_roles(self):
        cases = {
            "headers": "Pathway\tSignal_type\tSignal_Sending\tSignal_Receiving\tExtra\nP\tS\tA\tB\t\n",
            "required_value": "Pathway\tSignal_type\tSignal_Sending\tSignal_Receiving\tReferences\nP\t\tA\t\t\n",
            "empty_roles": "Pathway\tSignal_type\tSignal_Sending\tSignal_Receiving\tReferences\nP\tS\t\t\t\n",
            "duplicate_pathway": "Pathway\tSignal_type\tSignal_Sending\tSignal_Receiving\tReferences\nP\tS\tA\t\t\np\tS\tA\t\t\n",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for reason, content in cases.items():
                table = root / f"{reason}.tsv"
                table.write_text(content, encoding="utf-8")
                with self.assertRaises(DatabaseError) as raised:
                    parse_pathway_table(table)
                self.assertEqual(raised.exception.public_code, "database_table_invalid")
                self.assertEqual(raised.exception.params["reason"], reason)
            invalid = root / "encoding.tsv"
            invalid.write_bytes(b"\xff\xfe")
            with self.assertRaises(DatabaseError) as raised:
                parse_pathway_table(invalid)
            self.assertEqual(raised.exception.params["reason"], "encoding")

    def test_custom_database_id_is_stable_for_ascii_and_unicode(self):
        self.assertEqual(custom_database_id("My QS DB"), "custom-my_qs_db")
        self.assertEqual(custom_database_id("群体感应库"), custom_database_id("群体感应库"))
        self.assertNotEqual(custom_database_id("群体感应库"), "custom-item")

    def test_builtin_provenance_checksums_and_license_status(self):
        registry = json.loads((ROOT / "databases/provenance.json").read_text(encoding="utf-8"))
        expected = {
            "qsp": ("QSPdatabase.hmm", "QSPdatabase.json"),
            "kegg-m02024": ("kegg_m02024.hmm", "kegg_m02024.json"),
        }
        for database_id, (hmm_name, metadata_name) in expected.items():
            item = registry[database_id]
            self.assertEqual(item["redistribution_status"], "confirmed")
            self.assertEqual(item["hmm_sha256"], sha256_file(ROOT / "databases" / hmm_name))
            self.assertEqual(item["metadata_sha256"], sha256_file(ROOT / "databases" / metadata_name))
        self.assertEqual(registry["qsp"]["source_url"], "https://github.com/chunxiao-dcx/QSP")
        self.assertIn("10.1016/j.watres.2023.119814", registry["qsp"]["source_version"])
        self.assertEqual(
            registry["kegg-m02024"]["source_url"],
            "https://www.kegg.jp/pathway/map02024",
        )
        self.assertIn("not taxonomic restrictions", registry["kegg-m02024"]["build_method"])

    def test_builtin_profile_counts_and_thresholds(self):
        qsp, qsp_ga = hmm_profiles(ROOT / "databases/QSPdatabase.hmm")
        kegg, kegg_ga = hmm_profiles(ROOT / "databases/kegg_m02024.hmm")
        self.assertEqual((len(qsp), len(qsp_ga)), (38, 38))
        self.assertEqual((len(kegg), len(kegg_ga)), (281, 0))

    def test_k07680_is_fixed_and_all_references_resolve(self):
        metadata = json.loads((ROOT / "databases/kegg_m02024.json").read_text())
        values = [item.get("Signal_Receiving", []) for item in metadata["pathways"]["Bacillus_ComQXPA_system"]]
        self.assertIn("K07680", [profile for group in values for profile in group])
        manifest = normalize_legacy_manifest(
            ROOT / "databases/kegg_m02024.json", "kegg", "KEGG", "1", "test", "KEGG", "evalue", 1e-5
        )
        validate_manifest_profiles(manifest, ROOT / "databases/kegg_m02024.hmm")
        self.assertEqual(manifest.threshold_policy.default_full_evalue, 1e-5)
        self.assertEqual(manifest.threshold_policy.default_domain_i_evalue, 1e-5)
        components = {item.profile_id: item.display_name for item in manifest.components}
        self.assertEqual(len(components), 281)
        self.assertEqual(components["K00494"], "LuxA")
        self.assertEqual(components["K01995"], "NA")

    def test_qsp_uses_the_same_component_schema_with_identity_names(self):
        manifest = normalize_legacy_manifest(
            ROOT / "databases/QSPdatabase.json", "qsp", "QSP", "2", "test", "QSP", "ga"
        )
        validate_manifest_profiles(manifest, ROOT / "databases/QSPdatabase.hmm")
        self.assertEqual(manifest.schema_version, "2.0")
        self.assertEqual(len(manifest.components), 38)
        self.assertTrue(all(item.profile_id == item.display_name for item in manifest.components))

    def test_schema_two_requires_a_complete_component_catalog(self):
        manifest = DatabaseManifest.model_validate({
            "schema_version": "2.0", "database_id": "test", "name": "Test",
            "version": "1", "source": "test", "classification_scheme": "test",
            "threshold_policy": {"type": "evalue", "default_evalue": 1e-5},
            "pathways": [{"pathway_id": "p", "name": "P", "signal_name": "S",
                          "sending_profiles": ["A"]}],
        })
        with tempfile.TemporaryDirectory() as temp:
            hmm = Path(temp) / "profiles.hmm"
            hmm.write_text("HMMER3/f\nNAME A\n//\n", encoding="utf-8")
            with self.assertRaisesRegex(DatabaseError, "requires component definitions"):
                validate_manifest_profiles(manifest, hmm)

    def test_custom_database_rejects_prebuilt_hmm_indexes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = Settings(
                data_dir=root / "data", builtin_database_dir=root, frontend_dir=root,
                redis_url="redis://unused", max_upload_bytes=1024,
                max_extracted_bytes=4096, max_genomes=10, max_archive_files=10,
                worker_ttl=60,
            )
            settings.ensure_directories()
            archive = root / "database.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("profiles.hmm", "HMMER3/f\nNAME A\n//\n")
                bundle.writestr("profiles.hmm.h3f", "generated")
                bundle.writestr("manifest.json", "{}")
            with patch("qscn.databases.settings", settings):
                with self.assertRaisesRegex(DatabaseError, "h3"):
                    import_custom_database(archive)

    def test_tabular_database_import_preserves_sources_builds_indexes_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = Settings(
                data_dir=root / "data", builtin_database_dir=root, frontend_dir=root,
                redis_url="redis://unused", max_upload_bytes=4096,
                max_extracted_bytes=8192, max_genomes=10, max_archive_files=10,
                worker_ttl=60, min_free_bytes=1,
            )
            settings.ensure_directories()
            hmm = root / "source.hmm"
            hmm.write_text("HMMER3/f\nNAME A\nGA 10 10;\n//\nHMMER3/f\nNAME B\nGA 10 10;\n//\n", encoding="utf-8")
            table = root / "source.tsv"
            table.write_text(
                "\t".join(PATHWAY_TABLE_HEADERS) + "\nP\tSignal\tA;B\t\thttps://example.test/ref\n",
                encoding="utf-8",
            )
            guidance = root / "guidance.tsv"
            guidance.write_text(
                "\t".join(GUIDANCE_TABLE_HEADERS)
                + "\n1.0\tcustom-1\tcore\tP\tsending\tCore\tA\tB\tCandidate core\tNo activity claim.\tE-01\thttps://example.test/evidence\n",
                encoding="utf-8",
            )

            def fake_hmmpress(command, timeout):
                pressed = Path(command[1])
                for suffix in (".h3f", ".h3i", ".h3m", ".h3p"):
                    Path(str(pressed) + suffix).write_text("index", encoding="utf-8")
                return SimpleNamespace(returncode=0, stderr="")

            with patch("qscn.db.settings", settings), patch("qscn.databases.settings", settings):
                db.initialize()
                with patch("qscn.databases.run_external", side_effect=fake_hmmpress) as pressed:
                    version_id = import_tabular_database(
                        hmm, table, guidance, name="Custom", version="1", threshold_type="ga"
                    )
                    repeated = import_tabular_database(
                        hmm, table, guidance, name="Custom", version="1", threshold_type="ga"
                    )
                row = db.get("databases", version_id)
            self.assertEqual(repeated, version_id)
            self.assertEqual(pressed.call_count, 1)
            stored_hmm = Path(row["hmm_path"])
            manifest = json.loads(Path(row["manifest_path"]).read_text(encoding="utf-8"))
            self.assertTrue(stored_hmm.with_name("pathways.tsv").exists())
            self.assertTrue(all(Path(str(stored_hmm) + suffix).exists() for suffix in (".h3f", ".h3i", ".h3m", ".h3p")))
            self.assertEqual(manifest["pathways"][0]["pathway_id"], "P")
            self.assertEqual(manifest["provenance"]["profile_count"], 2)
            self.assertEqual(manifest["provenance"]["metadata_reference_count"], 2)
            self.assertEqual(manifest["interpretation_guidance"]["version"], "custom-1")
            self.assertEqual(manifest["interpretation_guidance"]["endpoints"][0]["evidence_ids"], ["E-01"])
            self.assertEqual(len(manifest["provenance"]["guidance_sha256"]), 64)
            self.assertEqual(len(manifest["provenance"]["hmm_sha256"]), 64)
            self.assertEqual(len(manifest["provenance"]["metadata_sha256"]), 64)

    def test_tabular_database_enforces_ga_and_accepts_evalue_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = Settings(
                data_dir=root / "data", builtin_database_dir=root, frontend_dir=root,
                redis_url="redis://unused", max_upload_bytes=4096,
                max_extracted_bytes=8192, max_genomes=10, max_archive_files=10,
                worker_ttl=60, min_free_bytes=1,
            )
            settings.ensure_directories()
            hmm = root / "profiles.hmm"
            hmm.write_text("HMMER3/f\nNAME A\n//\n", encoding="utf-8")
            table = root / "pathways.txt"
            table.write_text(
                "\t".join(PATHWAY_TABLE_HEADERS) + "\nP\tS\tA\t\t\n", encoding="utf-8"
            )

            def fake_hmmpress(command, timeout):
                return SimpleNamespace(returncode=0, stderr="")

            with patch("qscn.db.settings", settings), patch("qscn.databases.settings", settings):
                db.initialize()
                with self.assertRaises(DatabaseError) as raised:
                    import_tabular_database(hmm, table, name="GA", version="1", threshold_type="ga")
                self.assertEqual(raised.exception.public_code, "database_threshold_invalid")
                self.assertFalse(list(settings.custom_databases_dir.glob("qscn-db-*")))
                with patch("qscn.databases.run_external", side_effect=fake_hmmpress):
                    version_id = import_tabular_database(
                        hmm, table, name="E-value", version="1", threshold_type="evalue",
                        default_full_evalue=1e-6, default_domain_i_evalue=1e-7,
                    )
                manifest = json.loads(Path(db.get("databases", version_id)["manifest_path"]).read_text())
            self.assertEqual(manifest["threshold_policy"]["default_full_evalue"], 1e-6)
            self.assertEqual(manifest["threshold_policy"]["default_domain_i_evalue"], 1e-7)

    def test_guidance_table_rejects_headers_mixed_versions_duplicates_and_bad_urls(self):
        with tempfile.TemporaryDirectory() as temp:
            table = Path(temp) / "guidance.tsv"
            valid = "\t".join(GUIDANCE_TABLE_HEADERS) + "\n"
            row = "1.0\t1\tendpoint-a\tP\tsending\tCore\tA\tB\tWording\tBoundary\tE-1\thttps://example.test/ref\n"
            table.write_text(valid + row, encoding="utf-8")
            parsed = parse_guidance_table(table)
            self.assertEqual(parsed["endpoints"][0]["required_profiles"], ["A"])
            for content, reason in (
                ("bad\theader\n", "headers"),
                (valid + row + row.replace("endpoint-a", "endpoint-b").replace("\t1\tendpoint-b", "\t2\tendpoint-b"), "mixed_versions"),
                (valid + row + row, "duplicate_endpoint"),
                (valid + row.replace("https://example.test/ref", "not-a-url"), "reference"),
                (valid + row.replace("\tA\tB\t", "\tA\tA\t"), "overlapping_profiles"),
            ):
                table.write_text(content, encoding="utf-8")
                with self.assertRaises(DatabaseError) as raised:
                    parse_guidance_table(table)
                self.assertEqual(raised.exception.params["reason"], reason)

            table.write_text(valid + row, encoding="utf-8")
            with self.assertRaises(DatabaseError) as raised:
                parse_guidance_table(table, [{
                    "pathway_id": "P", "sending_profiles": ["A", "C"],
                    "receiving_profiles": [],
                }])
            self.assertEqual(raised.exception.params["reason"], "unknown_profile")
            self.assertEqual(raised.exception.params["row"], 2)

    def test_tabular_import_rejects_non_tsv_guidance_before_copying(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            hmm = root / "profiles.hmm"
            pathways = root / "pathways.tsv"
            guidance = root / "guidance.csv"
            hmm.write_text("HMMER3/f\nNAME A\n//\n", encoding="utf-8")
            pathways.write_text("\t".join(PATHWAY_TABLE_HEADERS) + "\nP\tS\tA\t\t\n", encoding="utf-8")
            guidance.write_text("not accepted", encoding="utf-8")
            with self.assertRaises(DatabaseError) as raised:
                import_tabular_database(
                    hmm, pathways, guidance,
                    name="Custom", version="1", threshold_type="evalue",
                    default_full_evalue=1e-5, default_domain_i_evalue=1e-5,
                )
            self.assertEqual(raised.exception.public_code, "database_guidance_invalid")
            self.assertEqual(raised.exception.params["reason"], "file_type")

if __name__ == "__main__":
    unittest.main()
