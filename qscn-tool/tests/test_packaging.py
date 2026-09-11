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
        self.assertEqual(compose.count("image: __QSCN_IMAGE__"), 2)
        self.assertIn('127.0.0.1:${QSCN_PORT:-8000}:8000', compose)
        self.assertNotIn("QSCN_IMAGE", (ROOT / "packaging/.env.template").read_text(encoding="utf-8"))
        self.assertIn("name: qscope_data", compose)
        self.assertIn("name: qscope_redis", compose)

    def test_launchers_are_safe_and_shell_launchers_parse(self):
        mac = ROOT / "packaging/macos/qscn.sh"
        linux = ROOT / "packaging/linux/qscn.sh"
        windows = ROOT / "packaging/windows/qscn.ps1"
        for launcher in (mac, linux):
            subprocess.run(["sh", "-n", str(launcher)], check=True)
            self.assertTrue(os.access(launcher, os.X_OK))
        for launcher in (mac, linux, windows):
            text = launcher.read_text(encoding="utf-8")
            self.assertNotIn("down -v", text)
            self.assertIn("qscope_data", text)
            self.assertIn("qscope_redis", text)
            self.assertIn("api/readiness", text)
            self.assertNotIn("QSCN_IMAGE=", text)

    def test_release_script_builds_three_platform_artifacts(self):
        script = (ROOT / "scripts/package_release.sh").read_text(encoding="utf-8")
        self.assertIn("Q-SCOPE-v${version}-windows.zip", script)
        self.assertIn("Q-SCOPE-v${version}-macos.zip", script)
        self.assertIn("Q-SCOPE-v${version}-linux.tar.gz", script)
        self.assertIn('cp "$repo_root/packaging/.env.template" "$target/.env.example"', script)

    def test_builtin_databases_remain_in_image_and_are_confirmed(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY databases ./database-source", dockerfile)
        self.assertIn("COPY examples ./examples", dockerfile)
        manifest = json.loads((ROOT / "examples/pd10/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["sample_count"], 10)
        self.assertTrue((ROOT / "examples/pd10/PD10.zip").is_file())
        self.assertTrue((ROOT / "examples/pd10/hits.json").is_file())
        self.assertIn("hmmpress /app/database-runtime/QSPdatabase.hmm", dockerfile)
        self.assertIn("hmmpress /app/database-runtime/kegg_m02024.hmm", dockerfile)
        provenance = json.loads((ROOT / "databases/provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["qsp"]["redistribution_status"], "confirmed")
        self.assertEqual(provenance["kegg-m02024"]["redistribution_status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
