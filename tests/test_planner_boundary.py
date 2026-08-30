import inspect
import unittest
from datetime import datetime, timezone
from pathlib import Path

from poiex_runtime.models import MaterialTarget
from poiex_runtime.planner_contract import PlannerProposal, proposal_to_intent


class PlannerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 26, 22, 0, tzinfo=timezone.utc)
        self.target = MaterialTarget.create(
            target_id="pump-A",
            target_type="synthetic_equipment",
            canonical_ref="plant-demo/pump-A",
            version=3,
            allowed_actions={"issue_synthetic_work_order"},
        )

    def test_planner_proposal_cannot_mint_authority_or_target_hash_fields(self):
        fields = set(PlannerProposal.__dataclass_fields__)
        forbidden = {
            "lease_id",
            "authority",
            "authority_epoch",
            "target_hash",
            "evidence_id",
            "receipt_id",
            "gate_decision",
        }
        self.assertTrue(fields.isdisjoint(forbidden))

    def test_trusted_layer_binds_current_target_hash(self):
        proposal = PlannerProposal(
            action_type="issue_synthetic_work_order",
            target_id="pump-A",
            parameters={"work_order": "WO-DEMO-002"},
        )
        intent = proposal_to_intent(
            proposal,
            intent_id="intent-002",
            trusted_agent_id="agent-maint-01",
            trusted_target=self.target,
            requested_at=self.now,
        )
        self.assertEqual(self.target.target_hash, intent.target_hash)
        self.assertEqual("agent-maint-01", intent.agent_id)

    def test_trusted_layer_rejects_planner_target_substitution(self):
        proposal = PlannerProposal(
            action_type="issue_synthetic_work_order",
            target_id="pump-B",
            parameters={},
        )
        with self.assertRaises(ValueError):
            proposal_to_intent(
                proposal,
                intent_id="intent-003",
                trusted_agent_id="agent-maint-01",
                trusted_target=self.target,
                requested_at=self.now,
            )

    def test_adk_scaffold_exposes_zero_material_tools(self):
        app_source = Path("app/agent.py").read_text()
        fleet_source = Path("poiex_runtime/adk_planner.py").read_text()
        compact = fleet_source.replace(" ", "")
        self.assertGreaterEqual(compact.count("tools=[]"), 2)
        self.assertNotIn("ControlPlane", app_source)
        self.assertNotIn("execute_synthetic_action", app_source)
        self.assertNotIn("execute_synthetic_action", fleet_source)

    def test_adk_scaffold_contains_specialized_advisory_fleet(self):
        source = Path("poiex_runtime/adk_planner.py").read_text()
        for name in (
            "registry_steward",
            "authority_steward",
            "target_steward",
            "falsifier_steward",
            "poiex_planning_coordinator",
        ):
            self.assertIn(name, source)
        self.assertIn("sub_agents=[", source)

    def test_coordinator_fails_closed_when_required_specialist_routing_fails(self):
        source = Path("poiex_runtime/adk_planner.py").read_text()
        self.assertIn("ABSTAIN_SPECIALIST_FAILURE", source)
        self.assertIn("do not impersonate", source.lower())
        self.assertIn("missing specialist", source.lower())


if __name__ == "__main__":
    unittest.main()
