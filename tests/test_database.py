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
    PATHWAY_TABLE_HEADERS,
    custom_database_id,
    hmm_profiles,
    import_custom_database,
    import_tabular_database,
    normalize_legacy_manifest,
    parse_pathway_table,
    validate_manifest_profiles,
)
from qscn.storage import sha256_file


ROOT = Path(__file__).resolve().parents[1]


class DatabaseTest(unittest.TestCase):
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
            self.assertEqual(item["redistribution_status"], "unconfirmed")
            self.assertEqual(item["hmm_sha256"], sha256_file(ROOT / "databases" / hmm_name))
            self.assertEqual(item["metadata_sha256"], sha256_file(ROOT / "databases" / metadata_name))

    def test_builtin_profile_counts_and_thresholds(self):
        qsp, qsp_ga = hmm_profiles(ROOT / "databases/QSPdatabase.hmm")
        kegg, kegg_ga = hmm_profiles(ROOT / "databases/kegg_m02024.hmm")
        self.assertEqual((len(qsp), len(qsp_ga)), (38, 38))
        self.assertEqual((len(kegg), len(kegg_ga)), (281, 0))

    def test_k07680_is_fixed_and_all_references_resolve(self):
        metadata = json.loads((ROOT / "databases/kegg_m02024.json").read_text())
        values = [item.get("Signal_Receiving", []) for item in metadata["Bacillus_ComQXPA_system"]]
        self.assertIn("K07680", [profile for group in values for profile in group])
        manifest = normalize_legacy_manifest(
            ROOT / "databases/kegg_m02024.json", "kegg", "KEGG", "1", "test", "KEGG", "evalue", 1e-5
        )
        validate_manifest_profiles(manifest, ROOT / "databases/kegg_m02024.hmm")
        self.assertEqual(manifest.threshold_policy.default_full_evalue, 1e-5)
        self.assertEqual(manifest.threshold_policy.default_domain_i_evalue, 1e-5)

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
                "\t".join(PATHWAY_TABLE_HEADERS) + "\nP\tSignal\tA\tB\thttps://example.test/ref\n",
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
                        hmm, table, name="Custom", version="1", threshold_type="ga"
                    )
                    repeated = import_tabular_database(
                        hmm, table, name="Custom", version="1", threshold_type="ga"
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

if __name__ == "__main__":
    unittest.main()
