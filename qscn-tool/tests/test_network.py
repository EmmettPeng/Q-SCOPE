import unittest

from qscn.network import build_network, network_statistics


def call(sample, pathway, role, signal="AI-1", capable=True, components=None, references=None):
    return {
        "sample_id": sample,
        "pathway_id": pathway,
        "pathway_name": pathway.upper(),
        "signal_name": signal,
        "role": role,
        "capable": capable,
        "observed_components": components or [f"{role}-component"],
        "references": references or [],
    }


class NetworkTest(unittest.TestCase):
    def test_microbe_only_pathway_edges_and_isolates(self):
        calls = [
            call("a", "p1", "sending", references=["doi:1", "doi:1"]),
            call("a", "p1", "receiving"),
            call("b", "p1", "receiving"),
            call("a", "p2", "sending", signal="AI-1"),
            call("b", "p2", "receiving", signal="AI-1"),
        ]
        network = build_network("db:1", "source", {"a": "A", "b": "B", "c": "C"}, calls)
        self.assertEqual({node["kind"] for node in network["nodes"]}, {"genome"})
        self.assertEqual(len(network["nodes"]), 3)
        pairs = {(edge["pathway_id"], edge["source_sample"], edge["target_sample"]) for edge in network["edges"]}
        self.assertEqual(pairs, {("p1", "a", "a"), ("p1", "a", "b"), ("p2", "a", "b")})
        self.assertTrue(all("supporting_hit_ids" not in edge for edge in network["edges"]))
        p1 = next(edge for edge in network["edges"] if edge["pathway_id"] == "p1")
        self.assertEqual(p1["references"], ["doi:1"])
        self.assertEqual(network["summary"]["isolated_nodes"], 1)
        self.assertEqual(network["summary"]["self_edges"], 1)
        a = next(item for item in network["node_metrics"] if item["sample_id"] == "a")
        self.assertEqual((a["in_degree"], a["out_degree"], a["total_degree"]), (1, 3, 4))
        self.assertEqual(a["self_edge_count"], 1)
        self.assertEqual(a["unique_neighbors"], 1)
        self.assertEqual(len(network["legend"]), 1)

    def test_filtered_statistics_recalculate_self_edges(self):
        nodes = [{"sample_id": "a", "label": "A"}, {"sample_id": "b", "label": "B"}]
        edges = [
            {"source_sample": "a", "target_sample": "a", "self_communication": True, "pathway_id": "p", "signal_name": "s"},
            {"source_sample": "a", "target_sample": "b", "self_communication": False, "pathway_id": "p", "signal_name": "s"},
        ]
        summary, metrics = network_statistics(nodes, edges[1:])
        self.assertEqual(summary["total_edges"], 1)
        self.assertEqual(summary["self_edges"], 0)
        self.assertEqual(next(item for item in metrics if item["sample_id"] == "a")["total_degree"], 1)


if __name__ == "__main__":
    unittest.main()
