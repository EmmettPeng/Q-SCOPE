import unittest

from qscn.completeness import (
    allow_one_missing_rules,
    calculate_capabilities,
    strict_rules,
    validate_rules,
)
from qscn.schemas import DatabaseManifest


def manifest() -> DatabaseManifest:
    return DatabaseManifest.model_validate({
        "database_id": "test", "name": "Test", "version": "1", "source": "test",
        "classification_scheme": "test", "threshold_policy": {"type": "ga"},
        "pathways": [
            {
                "pathway_id": "p", "name": "P", "signal_name": "S",
                "sending_profiles": ["A", "B", "C"], "receiving_profiles": ["D"],
            },
            {
                "pathway_id": "large", "name": "Large", "signal_name": "L",
                "sending_profiles": [f"P{i}" for i in range(11)],
            },
        ],
    })


class CapabilityRulesTest(unittest.TestCase):
    def test_failed_candidate_hits_do_not_create_component_evidence(self):
        calls = calculate_capabilities(
            manifest(),
            [
                {"hit_id": "failed", "sample_id": "s", "profile_id": "A", "pass": False},
                {"hit_id": "passed", "sample_id": "s", "profile_id": "B", "pass": True},
            ],
            ["s"],
        )
        sending = next(call for call in calls if call["pathway_id"] == "p" and call["role"] == "sending")
        self.assertEqual(sending["observed_components"], ["B"])
        self.assertEqual(sending["supporting_hit_ids"], ["passed"])

    def test_strict_and_allow_one_missing_presets(self):
        strict = strict_rules(manifest())
        self.assertTrue(all(rule.strategy == "all" for rule in strict))
        shortcut = allow_one_missing_rules(manifest())
        mapped = {(rule.pathway_id, rule.role): rule for rule in shortcut}
        self.assertEqual(mapped[("p", "sending")].minimum_count, 2)
        self.assertEqual(mapped[("p", "receiving")].strategy, "all")
        self.assertEqual(mapped[("large", "sending")].minimum_count, 10)

    def test_strict_count_and_required_profile_strategies(self):
        hits = [
            {"hit_id": "h1", "sample_id": "s", "profile_id": "A"},
            {"hit_id": "h2", "sample_id": "s", "profile_id": "A"},
            {"hit_id": "h3", "sample_id": "s", "profile_id": "B"},
        ]
        strict = calculate_capabilities(manifest(), hits, ["s"])
        sending = next(call for call in strict if call["pathway_id"] == "p" and call["role"] == "sending")
        self.assertFalse(sending["capable"])
        self.assertEqual(sending["observed_components"], ["A", "B"])

        rules = [rule.model_dump() for rule in strict_rules(manifest())]
        for rule in rules:
            if rule["pathway_id"] == "p" and rule["role"] == "sending":
                rule.update(strategy="minimum_count", minimum_count=2)
        counted = calculate_capabilities(manifest(), hits, ["s"], rules)
        self.assertTrue(next(call for call in counted if call["pathway_id"] == "p" and call["role"] == "sending")["capable"])

        for rule in rules:
            if rule["pathway_id"] == "p" and rule["role"] == "sending":
                rule.update(strategy="required_profiles", minimum_count=None, required_profiles=["A", "C"])
        required = calculate_capabilities(manifest(), hits, ["s"], rules)
        sending = next(call for call in required if call["pathway_id"] == "p" and call["role"] == "sending")
        self.assertFalse(sending["capable"])
        self.assertEqual(sending["missing_required_profiles"], ["C"])

    def test_zero_hits_and_single_component_role_never_pass_implicitly(self):
        calls = calculate_capabilities(manifest(), [], ["s"])
        self.assertTrue(all(not call["capable"] for call in calls))
        rules = [rule.model_dump() for rule in strict_rules(manifest())]
        for rule in rules:
            if rule["pathway_id"] == "p" and rule["role"] == "receiving":
                rule.update(strategy="minimum_count", minimum_count=1)
        with self.assertRaisesRegex(ValueError, "single-component"):
            validate_rules(manifest(), rules)

    def test_invalid_rule_sets_are_rejected(self):
        rules = strict_rules(manifest())
        with self.assertRaisesRegex(ValueError, "missing rules"):
            validate_rules(manifest(), rules[:-1])
        invalid = [rule.model_dump() for rule in rules]
        invalid[0].update(strategy="minimum_count", minimum_count=99)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            validate_rules(manifest(), invalid)
        invalid = [rule.model_dump() for rule in rules]
        invalid[0].update(strategy="required_profiles", required_profiles=["NOT_IN_ROLE"])
        with self.assertRaisesRegex(ValueError, "not part"):
            validate_rules(manifest(), invalid)


if __name__ == "__main__":
    unittest.main()
