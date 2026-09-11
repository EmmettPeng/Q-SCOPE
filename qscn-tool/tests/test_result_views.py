import unittest

from qscn.result_views import filtered_capabilities, filtered_edges, paged_hits, result_summary


class ResultViewsTest(unittest.TestCase):
    def setUp(self):
        self.hit = {
            "hit_id": "h1", "profile_id": "A", "hmm_coverage": 0.8,
            "sequence_coverage": 0.6, "gene_integrity_state": "complete",
        }
        self.sender = {
            "sample_id": "s1", "pathway_id": "p", "role": "sending", "capable": True,
            "rule_strategy": "all", "required_profiles": ["A"],
            "observed_components": ["A"], "supporting_hit_ids": ["h1"],
            "component_hit_ids": {"A": ["h1"]},
            "biological_annotations": [{"rule_id": "R1"}],
        }
        self.receiver = {
            **self.sender, "sample_id": "s2", "role": "receiving",
        }
        self.edge = {
            "id": "e1", "source_sample": "s1", "target_sample": "s2",
            "pathway_id": "p", "biological_rule_ids": ["R1"],
        }
        self.payload = {
            "hits": [self.hit], "capabilities": [self.sender, self.receiver],
            "biological_annotations": [{"rule_id": "R1", "supporting_hit_ids": ["h1"]}],
            "network": {"edges": [self.edge], "nodes": [], "summary": {}},
        }

    def test_summary_removes_large_collections_and_keeps_counts(self):
        summary = result_summary(self.payload)
        self.assertEqual(summary["hits"], [])
        self.assertEqual(summary["network"]["edges"], [])
        self.assertEqual(summary["result_counts"]["capabilities"], 2)
        self.assertEqual(summary["biological_rule_ids"], ["R1"])

    def test_evidence_filters_recompute_capability_and_edge_support(self):
        self.assertEqual(filtered_capabilities(self.payload, min_hmm_coverage=0.7)["total"], 2)
        self.assertEqual(filtered_capabilities(self.payload, min_hmm_coverage=0.9)["total"], 0)
        self.assertEqual(filtered_edges(self.payload, min_sequence_coverage=0.5)["total"], 1)
        self.assertEqual(filtered_edges(self.payload, min_sequence_coverage=0.7)["total"], 0)

    def test_hits_are_filtered_before_pagination(self):
        second = {**self.hit, "hit_id": "h2", "profile_id": "B", "hmm_coverage": 0.9}
        result = paged_hits({**self.payload, "hits": [self.hit, second]}, 0, 1, ["B"])
        self.assertEqual(result["baseline"], 1)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["hit_id"], "h2")


if __name__ == "__main__":
    unittest.main()
