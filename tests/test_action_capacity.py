import unittest

from poiex_runtime.action_capacity import (
    ActionCapacitySeries,
    audit_action_capacity,
)


class ActionCapacityTests(unittest.TestCase):
    def test_distinct_actions_can_have_only_one_growing_direction(self):
        series = [
            ActionCapacitySeries("planner", (8, 16, 32, 64), (7, 15, 31, 63)),
            ActionCapacitySeries("registry", (8, 16, 32, 64), (2, 2, 2, 2)),
            ActionCapacitySeries("authority", (8, 16, 32, 64), (2, 2, 2, 2)),
            ActionCapacitySeries("target", (8, 16, 32, 64), (1, 1, 1, 1)),
        ]
        result = audit_action_capacity(series)
        self.assertEqual(4, result.distinct_action_count)
        self.assertEqual(1, result.growing_direction_count_in_tested_envelope)
        self.assertEqual(("planner",), result.growing_actions)
        self.assertEqual(
            "DISTINCT_ACTION_CLASSES != MULTIPLE_GROWING_CONTROL_DIRECTIONS",
            result.negative_seal,
        )

    def test_nonmonotone_rank_series_is_not_promoted_as_growing(self):
        series = [ActionCapacitySeries("unstable", (1, 2, 3), (1, 3, 2))]
        result = audit_action_capacity(series)
        self.assertEqual(0, result.growing_direction_count_in_tested_envelope)
        self.assertIn("unstable", result.nonmonotone_actions)

    def test_finite_window_never_claims_unbounded_capacity(self):
        series = [ActionCapacitySeries("a", (1, 2, 3), (1, 2, 3))]
        result = audit_action_capacity(series)
        self.assertFalse(result.unbounded_capacity_claimed)


if __name__ == "__main__":
    unittest.main()
