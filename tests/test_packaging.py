import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingTest(unittest.TestCase):
    def test_release_compose_uses_remote_image_localhost_and_stable_volumes(self):
        compose = (ROOT / "packaging/compose.yml").read_text(encoding="utf-8")
        self.assertNotIn("build:", compose)
        self.assertIn("ghcr.io/emmettpeng/qscn:0.3.2", compose)
        self.assertIn('127.0.0.1:${QSCN_PORT:-8000}:8000', compose)
        self.assertEqual(compose.count("${QSCN_IMAGE"), 2)
        self.assertIn("name: qscn_qscn_v03_data", compose)
        self.assertIn("name: qscn_qscn_v03_redis", compose)

    def test_launchers_are_safe_and_macos_shell_parses(self):
        mac = ROOT / "packaging/macos/qscn.sh"
        windows = ROOT / "packaging/windows/qscn.ps1"
        subprocess.run(["sh", "-n", str(mac)], check=True)
        self.assertTrue(os.access(mac, os.X_OK))
        for launcher in (mac, windows):
            text = launcher.read_text(encoding="utf-8")
            self.assertNotIn("down -v", text)
            self.assertIn("qscn_qscn_v03_data", text)
            self.assertIn("qscn_qscn_v03_redis", text)
            self.assertIn("api/readiness", text)

    def test_builtin_databases_remain_in_image_and_are_confirmed(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY databases ./database-source", dockerfile)
        self.assertIn("hmmpress /app/database-runtime/QSPdatabase.hmm", dockerfile)
        self.assertIn("hmmpress /app/database-runtime/kegg_m02024.hmm", dockerfile)
        provenance = json.loads((ROOT / "databases/provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["qsp"]["redistribution_status"], "confirmed")
        self.assertEqual(provenance["kegg-m02024"]["redistribution_status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
