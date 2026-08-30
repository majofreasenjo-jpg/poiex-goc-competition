import unittest
from datetime import datetime, timedelta, timezone

from poiex_runtime.authority_provenance import AuthorityProvenanceRecord
from poiex_runtime.control_plane import ControlPlane
from poiex_runtime.firestore_store import FirestoreStore
from poiex_runtime.models import (
    ActionIntent,
    AgentRecord,
    AuthorityLease,
    EvidenceItem,
    IdentityContext,
    MaterialTarget,
)


class FakeSnapshot:
    def __init__(self, value):
        self._value = value
        self.exists = value is not None

    def to_dict(self):
        return dict(self._value) if self._value is not None else None


class FakeDocument:
    def __init__(self, backing, key):
        self.backing = backing
        self.key = key

    def set(self, payload):
        self.backing[self.key] = dict(payload)

    def get(self):
        return FakeSnapshot(self.backing.get(self.key))


class FakeCollection:
    def __init__(self, backing):
        self.backing = backing

    def document(self, doc_id):
        return FakeDocument(self.backing, doc_id)


class FakeFirestoreClient:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return FakeCollection(self.collections.setdefault(name, {}))


class FirestoreStoreContractTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 26, 22, 0, tzinfo=timezone.utc)
        self.client = FakeFirestoreClient()
        self.store = FirestoreStore(self.client, namespace="contract")
        self.cp = ControlPlane(self.store, clock=lambda: self.now)
        self.agent = AgentRecord(
            agent_id="agent-maint-01",
            role="maintenance_outage_coordinator",
            declared_capabilities={"issue_synthetic_work_order"},
            current_epoch=7,
        )
        self.evidence = EvidenceItem.runtime_observation(
            evidence_id="ev-runtime-001",
            subject_id=self.agent.agent_id,
            claim="issue_synthetic_work_order",
            observed_at=self.now,
            trace_id="trace-obs-001",
        )
        self.target = MaterialTarget.create(
            target_id="pump-A",
            target_type="synthetic_equipment",
            canonical_ref="plant-demo/pump-A",
            version=3,
            allowed_actions={"issue_synthetic_work_order"},
        )
        self.lease = AuthorityLease(
            lease_id="lease-001",
            agent_id=self.agent.agent_id,
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(minutes=10),
            expires_at=self.now + timedelta(minutes=30),
            revoked_at=None,
            issuer="synthetic-owner",
        )
        self.identity = IdentityContext(
            agent_id=self.agent.agent_id,
            session_id="session-001",
            authenticated=True,
        )

    def _seed(self):
        self.store.put_agent(self.agent)
        self.store.put_evidence(self.evidence)
        self.cp.promote_observed_capability(
            self.agent.agent_id,
            "issue_synthetic_work_order",
            self.evidence.evidence_id,
        )
        self.store.put_target(self.target)
        self.store.put_lease(self.lease)

    def _intent(self):
        return ActionIntent.create(
            intent_id="intent-001",
            agent_id=self.agent.agent_id,
            action_type="issue_synthetic_work_order",
            target_id=self.target.target_id,
            target_hash=self.target.target_hash,
            parameters={"work_order": "WO-DEMO-001"},
            requested_at=self.now,
        )

    def test_round_trips_agent_evidence_lease_and_target(self):
        self.store.put_agent(self.agent)
        self.store.put_evidence(self.evidence)
        self.store.put_lease(self.lease)
        self.store.put_target(self.target)
        self.assertEqual(self.agent, self.store.get_agent(self.agent.agent_id))
        self.assertEqual(self.evidence, self.store.get_evidence(self.evidence.evidence_id))
        self.assertEqual(self.lease, self.store.get_lease(self.lease.lease_id))
        self.assertEqual(self.target, self.store.get_target(self.target.target_id))

    def test_round_trips_authority_provenance(self):
        record = AuthorityProvenanceRecord(
            provenance_id="prov-root",
            subject_id="synthetic-owner",
            issuer_id="plant-owner-root",
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(hours=1),
            revoked_at=None,
            parent_provenance_id=None,
        )
        self.store.put_authority_provenance(record)
        self.assertEqual(record, self.store.get_authority_provenance(record.provenance_id))

    def test_firestore_adapter_preserves_provenance_enforcement(self):
        root = AuthorityProvenanceRecord(
            provenance_id="prov-root",
            subject_id="synthetic-owner",
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
            issuer_id="synthetic-owner",
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(minutes=15),
            revoked_at=None,
            parent_provenance_id=root.provenance_id,
        )
        self.store.put_authority_provenance(root)
        self.store.put_authority_provenance(child)
        self.lease.provenance_id = child.provenance_id
        self._seed()
        cp = ControlPlane(
            self.store,
            clock=lambda: self.now,
            require_authority_provenance=True,
            trusted_authority_roots={"plant-owner-root"},
        )
        receipt = cp.execute(self.identity, self.lease.lease_id, self._intent())
        self.assertEqual("ALLOW", receipt.decision)


    def test_missing_document_returns_none(self):
        self.assertIsNone(self.store.get_agent("missing"))
        self.assertIsNone(self.store.get_lease("missing"))
        self.assertIsNone(self.store.get_evidence("missing"))
        self.assertIsNone(self.store.get_target("missing"))
        self.assertIsNone(self.store.get_receipt("missing"))

    def test_control_plane_allows_and_replays_with_adapter_contract(self):
        self._seed()
        receipt = self.cp.execute(self.identity, self.lease.lease_id, self._intent())
        self.assertEqual("ALLOW", receipt.decision)
        persisted = self.store.get_receipt(receipt.receipt_id)
        self.assertEqual(receipt, persisted)
        replay = self.cp.replay(receipt.receipt_id)
        self.assertEqual("PASS", replay.reconstruction_status)

    def test_revoked_authority_blocks_without_synthetic_action_document(self):
        self._seed()
        self.lease.revoked_at = self.now - timedelta(seconds=1)
        self.store.put_lease(self.lease)
        receipt = self.cp.execute(self.identity, self.lease.lease_id, self._intent())
        self.assertEqual("BLOCK", receipt.decision)
        actions = self.client.collections.get("contract_synthetic_actions", {})
        self.assertEqual({}, actions)

    def test_tampered_target_document_is_rejected_on_read(self):
        self.store.put_target(self.target)
        raw = self.client.collections["contract_targets"][self.target.target_id]
        raw["canonical_ref"] = "plant-demo/evil-target"
        with self.assertRaises(ValueError):
            self.store.get_target(self.target.target_id)

    def test_synthetic_result_hash_is_verified_on_replay(self):
        self._seed()
        receipt = self.cp.execute(self.identity, self.lease.lease_id, self._intent())
        raw = self.client.collections["contract_synthetic_actions"][receipt.run_id]
        raw["payload"] = {"tampered": True}
        replay = self.cp.replay(receipt.receipt_id)
        self.assertEqual("FAIL", replay.reconstruction_status)
        self.assertIn("EXECUTOR_RESULT_NOT_RECONSTRUCTABLE", replay.mismatches)


if __name__ == "__main__":
    unittest.main()
