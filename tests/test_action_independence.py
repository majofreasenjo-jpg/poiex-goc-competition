import unittest

from poiex_runtime.action_independence import (
    ActionContractSignature,
    audit_action_independence,
)


class ActionIndependenceTests(unittest.TestCase):
    def test_labels_do_not_create_independent_action_classes(self):
        actions = [
            ActionContractSignature(
                action_id="specialist-A-propose",
                authority_scope="advisory_only",
                target_type="synthetic_work_order",
                required_evidence=("registry", "authority"),
                material_effect="planner_proposal",
            ),
            ActionContractSignature(
                action_id="specialist-B-propose",
                authority_scope="advisory_only",
                target_type="synthetic_work_order",
                required_evidence=("registry", "authority"),
                material_effect="planner_proposal",
            ),
        ]
        result = audit_action_independence(actions)
        self.assertEqual(2, result.raw_action_count)
        self.assertEqual(1, result.independent_effect_class_count)
        self.assertEqual(
            "ACTION_COUNT != INDEPENDENT_EFFECT_CLASS_COUNT",
            result.negative_seal,
        )

    def test_distinct_effect_contracts_remain_distinct(self):
        actions = [
            ActionContractSignature(
                action_id="registry-analysis",
                authority_scope="advisory_only",
                target_type="agent_record",
                required_evidence=("registry",),
                material_effect="registry_findings",
            ),
            ActionContractSignature(
                action_id="authority-analysis",
                authority_scope="advisory_only",
                target_type="authority_lease",
                required_evidence=("authority",),
                material_effect="authority_findings",
            ),
            ActionContractSignature(
                action_id="target-analysis",
                authority_scope="advisory_only",
                target_type="material_target",
                required_evidence=("target",),
                material_effect="target_findings",
            ),
        ]
        result = audit_action_independence(actions)
        self.assertEqual(3, result.independent_effect_class_count)
        self.assertEqual(3, len(result.effect_classes))


if __name__ == "__main__":
    unittest.main()
