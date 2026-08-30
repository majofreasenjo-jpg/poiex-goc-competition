import copy
import unittest
from datetime import datetime, timedelta, timezone

from poiex_runtime.control_plane import ControlPlane
from poiex_runtime.models import (
    AgentRecord,
    AuthorityLease,
    EvidenceItem,
    EvidenceSourceType,
    IdentityContext,
    MaterialTarget,
    ActionIntent,
)
from poiex_runtime.store import MemoryStore


class CoreFalsifierTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 26, 20, 0, tzinfo=timezone.utc)
        self.store = MemoryStore()
        self.cp = ControlPlane(self.store, clock=lambda: self.now)
        self.agent = AgentRecord(
            agent_id="agent-maint-01",
            role="maintenance_outage_coordinator",
            declared_capabilities={"issue_synthetic_work_order"},
            current_epoch=7,
        )
        self.store.put_agent(self.agent)
        runtime_evidence = EvidenceItem.runtime_observation(
            evidence_id="ev-runtime-001",
            subject_id=self.agent.agent_id,
            claim="issue_synthetic_work_order",
            observed_at=self.now,
            trace_id="trace-obs-001",
        )
        self.store.put_evidence(runtime_evidence)
        self.cp.promote_observed_capability(
            self.agent.agent_id,
            "issue_synthetic_work_order",
            runtime_evidence.evidence_id,
        )
        self.target_a = MaterialTarget.create(
            target_id="pump-A",
            target_type="synthetic_equipment",
            canonical_ref="plant-demo/pump-A",
            version=3,
            allowed_actions={"issue_synthetic_work_order"},
        )
        self.target_b = MaterialTarget.create(
            target_id="pump-B",
            target_type="synthetic_equipment",
            canonical_ref="plant-demo/pump-B",
            version=3,
            allowed_actions={"issue_synthetic_work_order"},
        )
        self.store.put_target(self.target_a)
        self.store.put_target(self.target_b)
        self.identity = IdentityContext(
            agent_id=self.agent.agent_id,
            session_id="session-001",
            authenticated=True,
        )
        self.valid_lease = AuthorityLease(
            lease_id="lease-001",
            agent_id=self.agent.agent_id,
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(minutes=10),
            expires_at=self.now + timedelta(minutes=30),
            revoked_at=None,
            issuer="synthetic-owner",
        )
        self.store.put_lease(self.valid_lease)

    def intent_for(self, target):
        return ActionIntent.create(
            intent_id="intent-001",
            agent_id=self.agent.agent_id,
            action_type="issue_synthetic_work_order",
            target_id=target.target_id,
            target_hash=target.target_hash,
            parameters={"work_order":"WO-DEMO-001"},
            requested_at=self.now,
        )

    def test_positive_control_allows_bounded_synthetic_action(self):
        receipt = self.cp.execute(
            self.identity, self.valid_lease.lease_id, self.intent_for(self.target_a)
        )
        self.assertEqual("ALLOW", receipt.decision)
        self.assertEqual(1, self.store.synthetic_mutation_count)

    def test_f_g1_revoked_authority_blocks_with_zero_mutation(self):
        revoked = copy.deepcopy(self.valid_lease)
        revoked.revoked_at = self.now - timedelta(seconds=1)
        self.store.put_lease(revoked)
        receipt = self.cp.execute(
            self.identity, revoked.lease_id, self.intent_for(self.target_a)
        )
        self.assertEqual("BLOCK", receipt.decision)
        self.assertIn("AUTHORITY_REVOKED", receipt.reasons)
        self.assertEqual(0, self.store.synthetic_mutation_count)

    def test_f_g1_expired_authority_blocks(self):
        expired = copy.deepcopy(self.valid_lease)
        expired.expires_at = self.now - timedelta(seconds=1)
        self.store.put_lease(expired)
        receipt = self.cp.execute(
            self.identity, expired.lease_id, self.intent_for(self.target_a)
        )
        self.assertEqual("BLOCK", receipt.decision)
        self.assertIn("AUTHORITY_EXPIRED", receipt.reasons)
        self.assertEqual(0, self.store.synthetic_mutation_count)

    def test_f_g1_epoch_mismatch_blocks(self):
        stale = copy.deepcopy(self.valid_lease)
        stale.epoch = 6
        self.store.put_lease(stale)
        receipt = self.cp.execute(
            self.identity, stale.lease_id, self.intent_for(self.target_a)
        )
        self.assertEqual("BLOCK", receipt.decision)
        self.assertIn("AUTHORITY_EPOCH_STALE", receipt.reasons)
        self.assertEqual(0, self.store.synthetic_mutation_count)

    def test_f_g1_out_of_scope_authority_blocks(self):
        out_of_scope = copy.deepcopy(self.valid_lease)
        out_of_scope.scope = {"inspect_synthetic_work_order"}
        self.store.put_lease(out_of_scope)
        receipt = self.cp.execute(
            self.identity, out_of_scope.lease_id, self.intent_for(self.target_a)
        )
        self.assertEqual("BLOCK", receipt.decision)
        self.assertIn("AUTHORITY_OUT_OF_SCOPE", receipt.reasons)
        self.assertEqual(0, self.store.synthetic_mutation_count)

    def test_f_g2_self_claim_never_promotes_to_observed(self):
        self.agent.declared_capabilities.add("diagnose_synthetic_fault")
        self.store.put_agent(self.agent)
        self_claim = EvidenceItem(
            evidence_id="ev-self-001",
            subject_id=self.agent.agent_id,
            claim="diagnose_synthetic_fault",
            source_type=EvidenceSourceType.SELF_DECLARATION,
            observed_at=self.now,
            payload_hash="self-claim",
            trace_id="trace-self-001",
        )
        self.store.put_evidence(self_claim)
        with self.assertRaises(ValueError):
            self.cp.promote_observed_capability(
                self.agent.agent_id,
                "diagnose_synthetic_fault",
                self_claim.evidence_id,
            )
        resolved = self.store.get_agent(self.agent.agent_id)
        self.assertNotIn("diagnose_synthetic_fault", resolved.observed_capabilities)

    def test_f_g3_wrong_target_hash_blocks(self):
        intent = self.intent_for(self.target_a)
        intent.target_id = self.target_b.target_id
        receipt = self.cp.execute(self.identity, self.valid_lease.lease_id, intent)
        self.assertEqual("BLOCK", receipt.decision)
        self.assertIn("TARGET_HASH_MISMATCH", receipt.reasons)
        self.assertEqual(0, self.store.synthetic_mutation_count)

    def test_f_g3_stale_target_version_blocks(self):
        stale_copy = copy.deepcopy(self.target_a)
        stale_copy.version = 2
        stale_copy.target_hash = stale_copy.compute_hash()
        intent = self.intent_for(stale_copy)
        receipt = self.cp.execute(self.identity, self.valid_lease.lease_id, intent)
        self.assertEqual("BLOCK", receipt.decision)
        self.assertIn("TARGET_HASH_MISMATCH", receipt.reasons)
        self.assertEqual(0, self.store.synthetic_mutation_count)

    def test_f_g4_complete_replay_passes(self):
        receipt = self.cp.execute(
            self.identity, self.valid_lease.lease_id, self.intent_for(self.target_a)
        )
        replay = self.cp.replay(receipt.receipt_id)
        self.assertEqual("PASS", replay.reconstruction_status)
        self.assertEqual([], replay.mismatches)

    def test_f_g4_missing_predecessor_fails_replay(self):
        receipt = self.cp.execute(
            self.identity, self.valid_lease.lease_id, self.intent_for(self.target_a)
        )
        del self.store.leases[self.valid_lease.lease_id]
        replay = self.cp.replay(receipt.receipt_id)
        self.assertEqual("FAIL", replay.reconstruction_status)
        self.assertIn("MISSING_LEASE", replay.mismatches)


if __name__ == "__main__":
    unittest.main()
