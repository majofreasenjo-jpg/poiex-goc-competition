"""Domain-neutral governed orchestration boundary shared by POIEX and an internal method lane."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .control_plane import ControlPlane
from .models import ExecutionReceipt, IdentityContext, ReplayManifest
from .planner_contract import PlannerProposal, proposal_to_intent
from .store import RuntimeStore


@dataclass(frozen=True)
class GovernedOutcome:
    receipt: ExecutionReceipt
    replay: ReplayManifest


class GovernedOrchestrator:
    """Convert an untrusted planner proposal into a governed material action.

    The domain contract supplies ``authorized_target_id``. The planner is not allowed
    to silently change the target merely by mentioning another identifier.
    """

    def __init__(self, store: RuntimeStore, control_plane: ControlPlane):
        self.store = store
        self.control_plane = control_plane

    def execute_proposal(
        self,
        *,
        identity: IdentityContext,
        lease_id: str,
        proposal: PlannerProposal,
        authorized_target_id: str,
        intent_id: str,
        requested_at: datetime,
    ) -> GovernedOutcome:
        target = self.store.get_target(authorized_target_id)
        if target is None:
            raise ValueError("authorized target is not present in trusted registry")

        intent = proposal_to_intent(
            proposal,
            intent_id=intent_id,
            trusted_agent_id=identity.agent_id,
            trusted_target=target,
            requested_at=requested_at,
        )
        receipt = self.control_plane.execute(identity, lease_id, intent)
        replay = self.control_plane.replay(receipt.receipt_id)
        return GovernedOutcome(receipt=receipt, replay=replay)
