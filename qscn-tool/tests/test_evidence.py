import unittest

from qscn.completeness import calculate_capabilities
from qscn.evidence import (
    EVIDENCE_RULE_VERSION,
    annotate_hit_quality,
    attach_annotations,
    biological_annotations,
)
from qscn.network import build_network
from qscn.schemas import DatabaseManifest


def qsp_manifest() -> DatabaseManifest:
    return DatabaseManifest.model_validate({
        "database_id": "qsp",
        "name": "QSP",
        "version": "test",
        "source": "QSP",
        "classification_scheme": "QSP",
        "threshold_policy": {"type": "ga"},
        "pathways": [
            {
                "pathway_id": "LuxI_LuxR_system", "name": "LuxI LuxR",
                "signal_name": "HSLs", "sending_profiles": ["LuxI"],
                "receiving_profiles": ["LuxR"],
            },
            {
                "pathway_id": "c-di-GMP_pathway", "name": "c-di-GMP",
                "signal_name": "c-di-GMP", "sending_profiles": ["DGC"],
                "receiving_profiles": ["Clp"],
            },
            {
                "pathway_id": "Pqs_operon_system", "name": "Pqs",
                "signal_name": "PQS", "sending_profiles": ["PqsB", "PqsC", "PqsE"],
                "receiving_profiles": ["PqsR"],
            },
        ],
    })


class HitQualityEvidenceTest(unittest.TestCase):
    def test_evidence_rule_version_is_1_1(self):
        self.assertEqual(EVIDENCE_RULE_VERSION, "1.1")

    def test_quality_fields_are_additive_and_profile_agnostic(self):
        source = [
            {
                "hit_id": "h1", "sample_id": "s", "sequence_id": "protein",
                "profile_id": "LuxR", "pass": True, "hmm_coverage": 0.21,
                "sequence_coverage": 0.8, "partial_5prime": True,
                "partial_3prime": False,
            },
            {
                "hit_id": "h2", "sample_id": "s", "sequence_id": "protein",
                "profile_id": "CqsS", "pass": False, "hmm_coverage": 0.9,
                "sequence_coverage": 0.7, "partial_5prime": True,
                "partial_3prime": False,
            },
        ]
        annotated = annotate_hit_quality(source)
        self.assertTrue(annotated[0]["pass"])
        self.assertFalse(annotated[1]["pass"])
        self.assertEqual(annotated[0]["gene_integrity_state"], "partial_5p")
        self.assertEqual(annotated[0]["competing_profile_hits"], ["CqsS"])
        self.assertEqual(annotated[1]["competing_profile_hits"], ["LuxR"])
        self.assertNotIn("restricted_profile_luxr", annotated[0])
        self.assertNotIn("coverage_review_flag", annotated[0])
        self.assertNotIn("gene_integrity_state", source[0])


class BiologicalEvidenceTest(unittest.TestCase):
    def test_final_bio_catalog_is_emitted_with_literature_and_never_adjudicates(self):
        manifest = qsp_manifest()
        observed_by_call = {
            ("LuxM_LuxN_system", "sending"): ["LuxM"],
            ("LuxM_LuxN_system", "receiving"): ["LuxN"],
            ("LuxI_LuxR_system", "receiving"): ["LuxR"],
            ("LuxS_LuxPQ_system", "sending"): ["LuxS"],
            ("LuxS_LuxPQ_system", "receiving"): ["LuxP", "LuxQ"],
            ("LsrABC_system", "receiving"): ["LsrA", "LsrB", "LsrK", "LsrR"],
            ("Rpf_system", "sending"): ["RpfF"],
            ("Rpf_system", "receiving"): ["RpfC", "RpfG"],
            ("c-di-GMP_pathway", "sending"): ["DGC"],
            ("c-di-GMP_pathway", "receiving"): ["Clp"],
            ("Cqs_system", "sending"): ["CqsA"],
            ("Cqs_system", "receiving"): ["CqsS"],
            ("Pqs_operon_system", "sending"): [
                "PqsA", "PqsB", "PqsC", "PqsD", "PqsE", "PhnA", "PhnB", "PqsH",
            ],
            ("Pqs_operon_system", "receiving"): ["PqsR"],
        }
        calls = []
        for (pathway_id, role), components in observed_by_call.items():
            calls.append({
                "sample_id": "s", "pathway_id": pathway_id, "role": role,
                "observed_components": components,
                "component_hit_ids": {component: [f"hit:{component}"] for component in components},
            })
        annotations = biological_annotations(manifest, calls)
        self.assertEqual({item["rule_id"] for item in annotations}, {
            f"BIO-{number:02d}" for number in range(1, 16)
        })
        self.assertTrue(all(item["references"] for item in annotations))
        self.assertTrue(all(not item["affects_base_capability"] for item in annotations))
        rpf_g = next(item for item in annotations if item["rule_id"] == "BIO-07")
        self.assertIn("retracted_activity_reference_excluded", rpf_g["details"])
        pqs_h = next(item for item in annotations if item["rule_id"] == "BIO-15")
        self.assertTrue(pqs_h["details"]["oxygen_dependent"])
        lsr = next(item for item in annotations if item["rule_id"] == "BIO-06")
        self.assertIn("https://doi.org/10.1046/j.1365-2958.2003.03781.x", lsr["references"])
        self.assertIn("https://doi.org/10.1128/JB.00014-07", lsr["references"])
        pqs_e = next(item for item in annotations if item["rule_id"] == "BIO-13")
        self.assertEqual(
            pqs_e["state"], "pqsE_biosynthesis_contribution_context_dependent"
        )
        self.assertEqual(pqs_e["details"]["haq_biosynthesis_contribution"], "strain_dependent")
        self.assertFalse(pqs_e["details"]["hhq_core_member"])
        self.assertIn("https://doi.org/10.1128/jb.00402-25", pqs_e["references"])

    def test_annotations_do_not_change_base_calls(self):
        manifest = qsp_manifest()
        hits = [
            {"hit_id": "luxr", "sample_id": "s", "profile_id": "LuxR", "pass": True},
            {"hit_id": "dgc", "sample_id": "s", "profile_id": "DGC", "pass": True},
            {"hit_id": "clp", "sample_id": "s", "profile_id": "Clp", "pass": True},
            {"hit_id": "pqs-b", "sample_id": "s", "profile_id": "PqsB", "pass": True},
            {"hit_id": "pqs-e", "sample_id": "s", "profile_id": "PqsE", "pass": True},
        ]
        calls = calculate_capabilities(manifest, hits, ["s"])
        before = {(call["pathway_id"], call["role"]): call["capable"] for call in calls}
        annotations = biological_annotations(manifest, calls)
        attach_annotations(calls, annotations)
        after = {(call["pathway_id"], call["role"]): call["capable"] for call in calls}
        self.assertEqual(before, after)
        self.assertTrue(all(not item["affects_base_capability"] for item in annotations))
        rules = {item["rule_id"] for item in annotations}
        self.assertTrue({"BIO-02", "BIO-03", "BIO-08", "BIO-09", "BIO-11", "BIO-13"} <= rules)
        partner = next(item for item in annotations if item["rule_id"] == "BIO-11")
        self.assertEqual(partner["details"]["partner_state"], "partner_missing")
        self.assertEqual(partner["details"]["missing_partners"], ["PqsC"])
        pqs_e = next(item for item in annotations if item["rule_id"] == "BIO-13")
        self.assertEqual(pqs_e["supporting_hit_ids"], ["pqs-e"])

    def test_custom_database_does_not_inherit_qsp_biology(self):
        manifest = qsp_manifest().model_copy(update={"database_id": "custom-qsp-like"})
        calls = calculate_capabilities(
            manifest,
            [{"hit_id": "h", "sample_id": "s", "profile_id": "LuxR"}],
            ["s"],
        )
        self.assertEqual(biological_annotations(manifest, calls), [])

    def test_network_preserves_base_edge_and_adds_boundary_metadata(self):
        manifest = qsp_manifest()
        hits = [
            {"hit_id": "dgc", "sample_id": "s", "profile_id": "DGC"},
            {"hit_id": "clp", "sample_id": "t", "profile_id": "Clp"},
        ]
        calls = calculate_capabilities(manifest, hits, ["s", "t"])
        annotations = biological_annotations(manifest, calls)
        attach_annotations(calls, annotations)
        network = build_network("qsp:test", "QSP", {"s": "S", "t": "T"}, calls)
        edge = next(item for item in network["edges"] if item["source_sample"] == "s")
        self.assertEqual(edge["evidence_level"], "potential_communication")
        self.assertIn("BIO-09", edge["biological_rule_ids"])
        self.assertIn("intracellular_second_messenger_context", edge["biological_states"])


if __name__ == "__main__":
    unittest.main()
