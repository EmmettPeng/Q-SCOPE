import unittest

from qscn.guidance import GUIDANCE_VERSION, QSP_INTERPRETATION_GUIDANCE, guidance_for_database


class InterpretationGuidanceTest(unittest.TestCase):
    def test_qsp_catalog_has_all_versioned_functional_endpoints(self):
        guide = guidance_for_database("qsp")
        self.assertEqual(guide["version"], GUIDANCE_VERSION)
        endpoints = guide["endpoints"]
        self.assertEqual(len(endpoints), 11)
        self.assertEqual(len({item["endpoint_id"] for item in endpoints}), 11)
        self.assertTrue(all(item["required_profiles"] for item in endpoints))
        self.assertTrue(all(item["boundary"] and item["evidence_ids"] and item["references"] for item in endpoints))

        required = {item["endpoint_id"]: item["required_profiles"] for item in endpoints}
        self.assertEqual(required["qsp-lsr-uptake-processing"], ["LsrA", "LsrB", "LsrC", "LsrD", "LsrK"])
        self.assertEqual(required["qsp-pqs-hhq-core"], ["PqsA", "PqsB", "PqsC", "PqsD"])
        self.assertEqual(required["qsp-rpf-sensing-transduction"], ["RpfC"])
        self.assertEqual(required["qsp-luxpq-complete-reception"], ["LuxP", "LuxQ"])

    def test_non_qsp_databases_do_not_inherit_guidance(self):
        self.assertIsNone(guidance_for_database("kegg-m02024"))
        self.assertIsNone(guidance_for_database("custom-qsp-like"))

    def test_catalog_constant_is_not_mutated_by_public_copy(self):
        guide = guidance_for_database("qsp")
        guide["endpoints"].append({"endpoint_id": "bad"})
        self.assertEqual(len(QSP_INTERPRETATION_GUIDANCE), 11)


if __name__ == "__main__":
    unittest.main()
