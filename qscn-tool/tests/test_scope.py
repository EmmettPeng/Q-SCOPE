import unittest

from qscn.schemas import AnalysisScopeRequest, DatabaseManifest
from qscn.scope import normalize_scope


class AnalysisScopeTest(unittest.TestCase):
    def setUp(self):
        self.manifest = DatabaseManifest.model_validate({
            "database_id": "db", "name": "DB", "version": "1", "source": "test",
            "classification_scheme": "native", "threshold_policy": {"type": "ga"},
            "pathways": [
                {"pathway_id": "p1", "name": "P1", "signal_name": "AI-2", "sending_profiles": ["A"]},
                {"pathway_id": "p2", "name": "P2", "signal_name": "DSF", "receiving_profiles": ["B"]},
                {"pathway_id": "p3", "name": "P3", "signal_name": "AI-2", "receiving_profiles": ["C"]},
            ],
        })

    def test_all_scope_resolves_every_pathway(self):
        scope = normalize_scope(self.manifest, None)
        self.assertEqual(scope["mode"], "all")
        self.assertEqual(scope["resolved_pathway_ids"], ["p1", "p2", "p3"])

    def test_pathway_scope_deduplicates_and_uses_manifest_order(self):
        scope = normalize_scope(self.manifest, {"mode": "pathways", "requested_values": ["p3", "p1", "p3"]})
        self.assertEqual(scope["requested_values"], ["p1", "p3"])
        self.assertEqual(scope["resolved_pathway_ids"], ["p1", "p3"])

    def test_signal_scope_expands_shared_native_signal(self):
        scope = normalize_scope(self.manifest, {"mode": "signals", "requested_values": ["AI-2"]})
        self.assertEqual(scope["resolved_pathway_ids"], ["p1", "p3"])

    def test_unknown_and_empty_scopes_are_rejected(self):
        with self.assertRaises(ValueError):
            normalize_scope(self.manifest, {"mode": "pathways", "requested_values": ["missing"]})
        with self.assertRaises(ValueError):
            AnalysisScopeRequest.model_validate({"mode": "signals", "requested_values": []})


if __name__ == "__main__":
    unittest.main()
