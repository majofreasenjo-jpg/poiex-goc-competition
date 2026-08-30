import unittest

from poiex_runtime.governance_hardening import (
    GovernedBinding,
    MemoryReadbackWitness,
    ObserverTransition,
    RegistryCoverageCertificate,
    audit_binding_validity,
    audit_memory_readback,
    audit_observer_nonmint,
    audit_open_world_reopening,
    audit_stage_input_freshness,
)


class CrossLaneGovernanceHardeningTests(unittest.TestCase):
    def test_binding_change_invalidates_legacy_artifact(self):
        old = GovernedBinding.create(
            authority_root="root-A",
            scope={"issue_synthetic_work_order"},
            target_hash="target-v3",
            policy_epoch=7,
        )
        current = GovernedBinding.create(
            authority_root="root-A",
            scope={"issue_synthetic_work_order", "inspect"},
            target_hash="target-v3",
            policy_epoch=7,
        )
        report = audit_binding_validity(
            artifact_id="receipt-old",
            artifact_binding_hash=old.binding_hash,
            current_binding=current,
        )
        self.assertEqual("INVALIDATE_AND_RECOMPUTE", report.status)
        self.assertFalse(report.legacy_artifact_valid_for_final_disposition)
        self.assertIn("SEMANTIC_BINDING_CHANGED", report.reasons)

    def test_same_binding_preserves_artifact_locally(self):
        binding = GovernedBinding.create(
            authority_root="root-A",
            scope={"issue_synthetic_work_order"},
            target_hash="target-v3",
            policy_epoch=7,
        )
        report = audit_binding_validity(
            artifact_id="receipt-current",
            artifact_binding_hash=binding.binding_hash,
            current_binding=binding,
        )
        self.assertEqual("VALID_FOR_CURRENT_BINDING", report.status)
        self.assertTrue(report.legacy_artifact_valid_for_final_disposition)

    def test_history_write_without_readback_is_not_operational_memory(self):
        witnesses = [
            MemoryReadbackWitness(
                base_state="same-current",
                memory_state="history-A",
                future_kernel=("ALLOW", "BLOCK"),
            ),
            MemoryReadbackWitness(
                base_state="same-current",
                memory_state="history-B",
                future_kernel=("ALLOW", "BLOCK"),
            ),
        ]
        report = audit_memory_readback(witnesses)
        self.assertEqual("READBACK_NOT_DEMONSTRATED", report.status)
        self.assertFalse(report.load_bearing_readback_observed)

    def test_memory_readback_requires_matched_state_future_split(self):
        witnesses = [
            MemoryReadbackWitness(
                base_state="same-current",
                memory_state="epoch-7",
                future_kernel=("ALLOW", "ALLOW"),
            ),
            MemoryReadbackWitness(
                base_state="same-current",
                memory_state="epoch-8",
                future_kernel=("BLOCK", "BLOCK"),
            ),
        ]
        report = audit_memory_readback(witnesses)
        self.assertEqual("LOAD_BEARING_READBACK_OBSERVED", report.status)
        self.assertTrue(report.load_bearing_readback_observed)

    def test_stale_stage_input_blocks_without_noninterference_certificate(self):
        report = audit_stage_input_freshness(
            expected_post_stage_hash="post-gate-state",
            consumed_input_hash="original-plan-state",
            verified_noninterference_certificate=False,
        )
        self.assertEqual("STALE_STAGE_INPUT_BLOCK", report.status)
        self.assertFalse(report.stage_input_admissible)

    def test_verified_noninterference_can_admit_equivalent_stage_input(self):
        report = audit_stage_input_freshness(
            expected_post_stage_hash="post-gate-state",
            consumed_input_hash="original-plan-state",
            verified_noninterference_certificate=True,
        )
        self.assertEqual("ADMIT_WITH_VERIFIED_NONINTERFERENCE", report.status)
        self.assertTrue(report.stage_input_admissible)

    def test_observer_only_change_cannot_mint_progress(self):
        transition = ObserverTransition(
            before_system_state_hash="state-A",
            after_system_state_hash="state-A",
            before_evidence_roots=frozenset({"root-1"}),
            after_evidence_roots=frozenset({"root-1"}),
            before_observer_config_hash="threshold-0.7",
            after_observer_config_hash="threshold-0.8",
            claimed_progress_units=1,
        )
        report = audit_observer_nonmint(transition)
        self.assertEqual("NONMINT_VIOLATION", report.status)
        self.assertEqual(0, report.admissible_progress_units)

    def test_new_independent_evidence_root_can_support_progress(self):
        transition = ObserverTransition(
            before_system_state_hash="state-A",
            after_system_state_hash="state-A",
            before_evidence_roots=frozenset({"root-1"}),
            after_evidence_roots=frozenset({"root-1", "root-2"}),
            before_observer_config_hash="threshold-0.7",
            after_observer_config_hash="threshold-0.8",
            claimed_progress_units=1,
        )
        report = audit_observer_nonmint(transition)
        self.assertEqual("PROGRESS_REQUIRES_DOWNSTREAM_ADJUDICATION", report.status)
        self.assertEqual(1, report.admissible_progress_units)

    def test_new_rival_reopens_global_coverage_but_not_unchanged_local_pair(self):
        certificate = RegistryCoverageCertificate(
            certificate_id="registry-v1",
            registered_worlds=frozenset({"W-A", "W-B"}),
            local_pair_certificates={
                "pair-A-B": frozenset({"W-A", "W-B"}),
            },
        )
        report = audit_open_world_reopening(certificate, new_admissible_world="W-X")
        self.assertEqual("GLOBAL_REGISTRY_REOPENED", report.global_status)
        self.assertIn("pair-A-B", report.locally_preserved_certificates)
        self.assertNotIn("pair-A-B", report.locally_invalidated_certificates)

    def test_existing_world_does_not_fake_registry_expansion(self):
        certificate = RegistryCoverageCertificate(
            certificate_id="registry-v1",
            registered_worlds=frozenset({"W-A", "W-B"}),
            local_pair_certificates={},
        )
        report = audit_open_world_reopening(certificate, new_admissible_world="W-B")
        self.assertEqual("NO_NEW_WORLD", report.global_status)

    def test_frozen_hardening_demo_cases_emit_expected_statuses(self):
        from poiex_runtime.governance_hardening import run_hardening_demo_case

        expected = {
            "binding_change": "INVALIDATE_AND_RECOMPUTE",
            "write_only_memory": "READBACK_NOT_DEMONSTRATED",
            "stale_stage_input": "STALE_STAGE_INPUT_BLOCK",
            "observer_reparameterization": "NONMINT_VIOLATION",
            "new_rival": "GLOBAL_REGISTRY_REOPENED",
        }
        for case, status in expected.items():
            with self.subTest(case=case):
                result = run_hardening_demo_case(case)
                self.assertEqual(status, result["status"])
                self.assertEqual("SYNTHETIC_RECEIVER_NATIVE_ONLY", result["truth_ceiling"])

    def test_control_service_exposes_bounded_hardening_endpoint(self):
        from fastapi.testclient import TestClient
        from control_service.main import app

        client = TestClient(app)
        response = client.post('/v1/hardening/run', json={"case": "binding_change"})
        self.assertEqual(200, response.status_code)
        self.assertEqual("INVALIDATE_AND_RECOMPUTE", response.json()["status"])
        self.assertEqual("SYNTHETIC_RECEIVER_NATIVE_ONLY", response.json()["truth_ceiling"])


if __name__ == "__main__":
    unittest.main()
