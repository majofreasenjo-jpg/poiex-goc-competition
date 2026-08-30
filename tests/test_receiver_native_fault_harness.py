import unittest

from poiex_runtime.fault_harness import run_receiver_native_fault_matrix


class ReceiverNativeFaultHarnessTests(unittest.TestCase):
    def test_fault_matrix_fails_closed_or_detects_tamper(self):
        report = run_receiver_native_fault_matrix()
        self.assertGreaterEqual(len(report.cases), 8)
        self.assertTrue(report.all_safe)
        by_id = {case.fault_id: case for case in report.cases}
        for required in (
            "PROMPT_AUTHORITY_ESCALATION",
            "CAPABILITY_ESCALATION",
            "TARGET_SUBSTITUTION",
            "MEMORY_DECLARATION_POISONING",
            "REVOCATION_RACE",
            "RECEIPT_TARGET_TAMPER",
            "REPLAY_EVIDENCE_LOSS",
            "POLICY_EPOCH_DOWNGRADE",
        ):
            self.assertIn(required, by_id)
            self.assertTrue(by_id[required].safe_outcome)

    def test_report_does_not_claim_external_validation(self):
        report = run_receiver_native_fault_matrix()
        self.assertEqual("LOCAL_RECEIVER_NATIVE", report.execution_environment)
        self.assertFalse(report.external_validation)
        self.assertFalse(report.cloud_deployment_evidence)


if __name__ == "__main__":
    unittest.main()
