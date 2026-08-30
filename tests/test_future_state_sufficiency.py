import unittest

from poiex_runtime.future_state_sufficiency import (
    UnderlyingOperationalState,
    audit_future_state_sufficiency,
)


class FutureStateSufficiencyTests(unittest.TestCase):
    def test_same_present_state_with_rival_future_kernels_is_unsafe(self):
        states = [
            UnderlyingOperationalState(
                state_id="x",
                coarse_state="pump-ready",
                present_output="READY",
                continuation_kernel={"continue": "ALLOW", "revoke": "BLOCK"},
                residual_coordinates={"authority_epoch": "7"},
            ),
            UnderlyingOperationalState(
                state_id="y",
                coarse_state="pump-ready",
                present_output="READY",
                continuation_kernel={"continue": "BLOCK", "revoke": "BLOCK"},
                residual_coordinates={"authority_epoch": "6"},
            ),
        ]
        result = audit_future_state_sufficiency(states)
        self.assertEqual("STATE_ALIAS_UNSAFE", result.classes[0].status)
        self.assertIn("authority_epoch", result.classes[0].minimal_residual_coordinates)
        self.assertEqual(
            "PRESENT_EQUIVALENCE != FUTURE_ACTION_KERNEL_EQUIVALENCE",
            result.negative_seal,
        )

    def test_identical_declared_kernels_are_safe_only_for_declared_contract(self):
        states = [
            UnderlyingOperationalState(
                state_id="x",
                coarse_state="same",
                present_output="READY",
                continuation_kernel={"continue": "ALLOW", "revoke": "BLOCK"},
            ),
            UnderlyingOperationalState(
                state_id="y",
                coarse_state="same",
                present_output="READY",
                continuation_kernel={"continue": "ALLOW", "revoke": "BLOCK"},
            ),
        ]
        result = audit_future_state_sufficiency(states)
        self.assertEqual("SAFE_FOR_DECLARED_KERNEL", result.classes[0].status)
        self.assertFalse(result.global_future_exactness_claimed)

    def test_censored_and_never_event_are_not_collapsed(self):
        states = [
            UnderlyingOperationalState(
                state_id="censored",
                coarse_state="no-event-yet",
                present_output="NONE",
                continuation_kernel={"horizon": "CENSORED_H"},
            ),
            UnderlyingOperationalState(
                state_id="never",
                coarse_state="no-event-yet",
                present_output="NONE",
                continuation_kernel={"horizon": "NEVER_EVENT"},
            ),
        ]
        result = audit_future_state_sufficiency(states)
        self.assertEqual("STATE_ALIAS_UNSAFE", result.classes[0].status)
        self.assertIn("FINITE_NO_COLLISION != FUTURE_EXACTNESS", result.additional_negative_seals)


if __name__ == "__main__":
    unittest.main()
