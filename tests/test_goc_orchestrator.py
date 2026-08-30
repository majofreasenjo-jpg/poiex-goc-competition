import unittest
from datetime import datetime, timedelta, timezone

from poiex_runtime.control_plane import ControlPlane
from poiex_runtime.models import AgentRecord, AuthorityLease, EvidenceItem, IdentityContext, MaterialTarget
from poiex_runtime.orchestrator import GovernedOrchestrator
from poiex_runtime.planner_contract import PlannerProposal
from poiex_runtime.runtime_factory import build_store_from_env
from poiex_runtime.store import MemoryStore


class GOCOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 26, 22, 30, tzinfo=timezone.utc)
        self.store = MemoryStore()
        self.cp = ControlPlane(self.store, clock=lambda: self.now)
        self.orch = GovernedOrchestrator(self.store, self.cp)
        self.agent = AgentRecord(
            agent_id="agent-maint-01",
            role="maintenance_outage_coordinator",
            declared_capabilities={"issue_synthetic_work_order"},
            current_epoch=7,
        )
        self.store.put_agent(self.agent)
        evidence = EvidenceItem.runtime_observation(
            evidence_id="ev-runtime-001",
            subject_id=self.agent.agent_id,
            claim="issue_synthetic_work_order",
            observed_at=self.now,
            trace_id="trace-obs-001",
        )
        self.store.put_evidence(evidence)
        self.cp.promote_observed_capability(
            self.agent.agent_id,
            "issue_synthetic_work_order",
            evidence.evidence_id,
        )
        self.target = MaterialTarget.create(
            target_id="pump-A",
            target_type="synthetic_equipment",
            canonical_ref="plant-demo/pump-A",
            version=3,
            allowed_actions={"issue_synthetic_work_order"},
        )
        self.store.put_target(self.target)
        self.lease = AuthorityLease(
            lease_id="lease-001",
            agent_id=self.agent.agent_id,
            scope={"issue_synthetic_work_order"},
            epoch=7,
            issued_at=self.now - timedelta(minutes=5),
            expires_at=self.now + timedelta(minutes=20),
            revoked_at=None,
            issuer="synthetic-owner",
        )
        self.store.put_lease(self.lease)
        self.identity = IdentityContext(
            agent_id=self.agent.agent_id,
            session_id="session-001",
            authenticated=True,
        )

    def _proposal(self, target_id="pump-A"):
        return PlannerProposal(
            action_type="issue_synthetic_work_order",
            target_id=target_id,
            parameters={"work_order": "WO-DEMO-003"},
            rationale="synthetic demo proposal",
        )

    def test_end_to_end_governed_proposal_allows_and_replays(self):
        outcome = self.orch.execute_proposal(
            identity=self.identity,
            lease_id=self.lease.lease_id,
            proposal=self._proposal(),
            authorized_target_id="pump-A",
            intent_id="intent-003",
            requested_at=self.now,
        )
        self.assertEqual("ALLOW", outcome.receipt.decision)
        self.assertEqual("PASS", outcome.replay.reconstruction_status)

    def test_planner_cannot_substitute_domain_authorized_target(self):
        with self.assertRaises(ValueError):
            self.orch.execute_proposal(
                identity=self.identity,
                lease_id=self.lease.lease_id,
                proposal=self._proposal("pump-B"),
                authorized_target_id="pump-A",
                intent_id="intent-004",
                requested_at=self.now,
            )
        self.assertEqual(0, self.store.synthetic_mutation_count)

    def test_cloud_run_refuses_ephemeral_memory_store(self):
        with self.assertRaises(RuntimeError):
            build_store_from_env({"K_SERVICE": "poiex-demo", "POIEX_GOC_STORE": "memory"})

    def test_firestore_mode_passes_explicit_cloud_configuration(self):
        captured = {}

        def fake_factory(**kwargs):
            captured.update(kwargs)
            return MemoryStore()

        store = build_store_from_env(
            {
                "K_SERVICE": "poiex-demo",
                "POIEX_GOC_STORE": "firestore",
                "GOOGLE_CLOUD_PROJECT": "project-demo",
                "FIRESTORE_DATABASE": "(default)",
                "POIEX_GOC_NAMESPACE": "competition",
            },
            firestore_factory=fake_factory,
        )
        self.assertIsInstance(store, MemoryStore)
        self.assertEqual("project-demo", captured["project"])
        self.assertEqual("(default)", captured["database"])
        self.assertEqual("competition", captured["namespace"])


if __name__ == "__main__":
    unittest.main()
