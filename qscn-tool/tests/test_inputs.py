import tempfile
import unittest
import zipfile
from pathlib import Path

from qscn.inputs import InputError, preflight_archive
from qscn.schemas import InputKind
from qscn.config import Settings
from unittest.mock import patch


class ArchiveTest(unittest.TestCase):
    def _archive(self, root: Path, entries: dict[str, str]) -> Path:
        path = root / "input.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, value in entries.items():
                archive.writestr(name, value)
        return path

    def test_default_batch_limits_support_1000_samples(self):
        with patch.dict("os.environ", {}, clear=True):
            configured = Settings.from_env()
        self.assertEqual(configured.max_genomes, 1000)
        self.assertEqual(configured.max_archive_files, 2000)

    def test_valid_protein_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(root, {"a.faa": ">p1\nMPEPTIDE\n", "nested/b.faa": ">p2\nWLFQ\n"})
            samples = preflight_archive(archive, root / "out", InputKind.protein)
            self.assertEqual(len(samples), 2)
            self.assertEqual(sum(item["sequence_count"] for item in samples), 2)

    def test_archive_with_1000_samples_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entries = {"batch/": ""}
            entries.update(
                {f"batch/sample_{index:04d}.faa": f">p{index}\nE\n" for index in range(1000)}
            )
            archive = self._archive(root, entries)
            custom_settings = Settings(
                data_dir=root / "data", builtin_database_dir=root, frontend_dir=root,
                redis_url="redis://unused", max_upload_bytes=1_000_000,
                max_extracted_bytes=1_000_000, max_genomes=1000, max_archive_files=2000,
                worker_ttl=60, min_free_bytes=1,
            )
            with patch("qscn.inputs.settings", custom_settings):
                samples = preflight_archive(archive, root / "out", InputKind.protein)
            self.assertEqual(len(samples), 1000)

    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(root, {"../escape.faa": ">p1\nMKT\n"})
            with self.assertRaises(InputError):
                preflight_archive(archive, root / "out", InputKind.protein)

    def test_nucleotide_only_protein_is_rejected_as_ambiguous(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(root, {"a.faa": ">p1\nACGTNRYKMSWBDHV\n"})
            with self.assertRaises(InputError) as caught:
                preflight_archive(archive, root / "out", InputKind.protein)
            self.assertEqual(caught.exception.code, "ambiguous_sequence_alphabet")

    def test_sample_normalization_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(root, {
                "A sample.faa": ">p1\nMPEPTIDE\n",
                "A_sample.fa": ">p2\nWLFQ\n",
            })
            with self.assertRaises(InputError) as caught:
                preflight_archive(archive, root / "out", InputKind.protein)
            self.assertEqual(caught.exception.code, "sample_name_conflict")

    def test_same_sequence_id_is_allowed_in_different_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(root, {
                "a.faa": ">same\nMPEPTIDE\n", "b.faa": ">same\nWLFQ\n",
            })
            samples = preflight_archive(archive, root / "out", InputKind.protein)
            self.assertEqual(len(samples), 2)

    def test_compression_ratio_and_resource_limits_are_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "input.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
                handle.writestr("a.faa", ">p\n" + "E" * 20_000 + "\n")
            settings = Settings(
                data_dir=root / "data", builtin_database_dir=root, frontend_dir=root,
                redis_url="redis://unused", max_upload_bytes=100_000,
                max_extracted_bytes=100_000, max_genomes=10, max_archive_files=10,
                worker_ttl=60, max_compression_ratio=10, min_free_bytes=1,
            )
            with patch("qscn.inputs.settings", settings):
                with self.assertRaises(InputError) as caught:
                    preflight_archive(archive, root / "out", InputKind.protein)
            self.assertEqual(caught.exception.code, "archive_compression_ratio_exceeded")

    def test_mixed_or_invalid_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(root, {"a.faa": ">p1\nMKT\n", "note.txt": "no"})
            with self.assertRaises(InputError):
                preflight_archive(archive, root / "out", InputKind.protein)
            archive = self._archive(root, {"a.faa": ">p1\nMK?\n"})
            with self.assertRaises(InputError):
                preflight_archive(archive, root / "out", InputKind.protein)

    def test_duplicate_sequence_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self._archive(root, {"a.faa": ">same\nMKT\n>same\nAAA\n"})
            with self.assertRaises(InputError):
                preflight_archive(archive, root / "out", InputKind.protein)


if __name__ == "__main__":
    unittest.main()
