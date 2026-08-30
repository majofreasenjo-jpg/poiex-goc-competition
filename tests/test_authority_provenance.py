import unittest
from datetime import datetime, timedelta, timezone

from poiex_runtime.authority_provenance import AuthorityProvenanceRecord
from poiex_runtime.control_plane import ControlPlane
from poiex_runtime.models import (
    ActionIntent,
    AgentRecord,
    AuthorityLease,
    EvidenceItem,
    IdentityContext,
    MaterialTarget,
)
from poiex_runtime.store import MemoryStore


class AuthorityProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 27, 13, 45, tzinfo=timezone.utc)
        self.store = MemoryStore()
        self.agent = AgentRecord(
            agent_id="agent-maint-01",
            role="maintenance_outage_coordinator",
            declared_capabilities={"issue_synthetic_work_order"},
            current_epoch=7,
        )
        self.store.put_agent(self.agent)
        ev = EvidenceItem.runtime_observation(
            evidence_id="ev-runtime-001",
            subject_id=self.agent.agent_id,
            claim="issue_synthetic_work_order",
            observed_at=self.now,
            trace_id="trace-obs-001",
        )
        self.store.put_evidence(ev)
        ControlPlane(self.store, clock=lambda: self.now).promote_observed_capability(
            self.agent.agent_id,
            "issue_synthetic_work_order",
            ev.evidence_id,
        )
        self.target = MaterialTarget.create(
            target_id="pump-A",
            target_type="synthetic_equipment",
            canonical_ref="plant-demo/pump-A",
            version=3,
            allowed_actions={"issue_synthetic_work_order"},
        )
        self.store.put_target(self.target)
        self.identity = IdentityContext(
            agent_id=self.agent.agent_id,
            session_id="session-001",
            authenticated=True,
        )

    def _lease(self, provenance_id=None):
        lease = AuthorityLease(
            lease_id="lease-001",
            agent_id=self.agent.agent_id,
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(minutes=5),
            expires_at=self.now + timedelta(minutes=20),
            revoked_at=None,
            issuer="maintenance-owner",
            provenance_id=provenance_id,
        )
        self.store.put_lease(lease)
        return lease

    def _intent(self):
        return ActionIntent.create(
            intent_id="intent-001",
            agent_id=self.agent.agent_id,
            action_type="issue_synthetic_work_order",
            target_id=self.target.target_id,
            target_hash=self.target.target_hash,
            parameters={"work_order": "WO-001"},
            requested_at=self.now,
        )

    def test_required_provenance_missing_blocks_before_mutation(self):
        lease = self._lease(provenance_id=None)
        cp = ControlPlane(
            self.store,
            clock=lambda: self.now,
            require_authority_provenance=True,
            trusted_authority_roots={"plant-owner-root"},
        )
        receipt = cp.execute(self.identity, lease.lease_id, self._intent())
        self.assertEqual("BLOCK", receipt.decision)
        self.assertIn("AUTHORITY_PROVENANCE_MISSING", receipt.reasons)
        self.assertEqual(0, self.store.synthetic_mutation_count)

    def test_trusted_delegation_chain_allows(self):
        root = AuthorityProvenanceRecord(
            provenance_id="prov-root",
            subject_id="maintenance-owner",
            issuer_id="plant-owner-root",
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(hours=1),
            revoked_at=None,
            parent_provenance_id=None,
        )
        child = AuthorityProvenanceRecord(
            provenance_id="prov-child",
            subject_id=self.agent.agent_id,
            issuer_id="maintenance-owner",
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(minutes=10),
            revoked_at=None,
            parent_provenance_id=root.provenance_id,
        )
        self.store.put_authority_provenance(root)
        self.store.put_authority_provenance(child)
        lease = self._lease(provenance_id=child.provenance_id)
        cp = ControlPlane(
            self.store,
            clock=lambda: self.now,
            require_authority_provenance=True,
            trusted_authority_roots={"plant-owner-root"},
        )
        receipt = cp.execute(self.identity, lease.lease_id, self._intent())
        self.assertEqual("ALLOW", receipt.decision)
        self.assertEqual(1, self.store.synthetic_mutation_count)

    def test_revoked_parent_provenance_blocks(self):
        root = AuthorityProvenanceRecord(
            provenance_id="prov-root",
            subject_id="maintenance-owner",
            issuer_id="plant-owner-root",
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(hours=1),
            revoked_at=self.now - timedelta(minutes=2),
            parent_provenance_id=None,
        )
        child = AuthorityProvenanceRecord(
            provenance_id="prov-child",
            subject_id=self.agent.agent_id,
            issuer_id="maintenance-owner",
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(minutes=10),
            revoked_at=None,
            parent_provenance_id=root.provenance_id,
        )
        self.store.put_authority_provenance(root)
        self.store.put_authority_provenance(child)
        lease = self._lease(provenance_id=child.provenance_id)
        cp = ControlPlane(
            self.store,
            clock=lambda: self.now,
            require_authority_provenance=True,
            trusted_authority_roots={"plant-owner-root"},
        )
        receipt = cp.execute(self.identity, lease.lease_id, self._intent())
        self.assertEqual("BLOCK", receipt.decision)
        self.assertIn("AUTHORITY_PROVENANCE_REVOKED", receipt.reasons)
        self.assertEqual(0, self.store.synthetic_mutation_count)

    def test_provenance_cycle_blocks(self):
        a = AuthorityProvenanceRecord(
            provenance_id="prov-a",
            subject_id=self.agent.agent_id,
            issuer_id="maintenance-owner",
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(minutes=10),
            revoked_at=None,
            parent_provenance_id="prov-b",
        )
        b = AuthorityProvenanceRecord(
            provenance_id="prov-b",
            subject_id="maintenance-owner",
            issuer_id=self.agent.agent_id,
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(minutes=20),
            revoked_at=None,
            parent_provenance_id="prov-a",
        )
        self.store.put_authority_provenance(a)
        self.store.put_authority_provenance(b)
        lease = self._lease(provenance_id=a.provenance_id)
        cp = ControlPlane(
            self.store,
            clock=lambda: self.now,
            require_authority_provenance=True,
            trusted_authority_roots={"plant-owner-root"},
        )
        receipt = cp.execute(self.identity, lease.lease_id, self._intent())
        self.assertEqual("BLOCK", receipt.decision)
        self.assertIn("AUTHORITY_PROVENANCE_CYCLE", receipt.reasons)
        self.assertEqual(0, self.store.synthetic_mutation_count)


if __name__ == "__main__":
    unittest.main()
