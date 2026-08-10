import re
import unittest
from pathlib import Path

from qscn.api import PUBLIC_ERROR_CODES


ROOT = Path(__file__).resolve().parents[1]


class WebCopyTest(unittest.TestCase):
    def test_frontend_dictionary_covers_every_public_backend_error(self):
        source = (ROOT / "frontend/src/copy/en.ts").read_text(encoding="utf-8")
        error_block = source.split("  errors: {", 1)[1].split("\n  },", 1)[0]
        frontend_codes = set(re.findall(r"\b([a-z][a-z0-9_]+):", error_block))
        self.assertEqual(frontend_codes - {"unexpected"}, PUBLIC_ERROR_CODES)


if __name__ == "__main__":
    unittest.main()
