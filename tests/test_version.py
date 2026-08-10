import json
import unittest
from pathlib import Path

from qscn import SCHEMA_VERSION, __release__, __version__


ROOT = Path(__file__).resolve().parents[1]


class VersionConsistencyTest(unittest.TestCase):
    def test_demo_release_is_consistent(self):
        package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), __release__)
        self.assertEqual(package["version"], __version__)
        self.assertEqual(package["release"], __release__)
        self.assertIn(__release__, (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn(__release__, (ROOT / "frontend/src/copy/en.ts").read_text(encoding="utf-8"))
        self.assertEqual(SCHEMA_VERSION, "3")


if __name__ == "__main__":
    unittest.main()
