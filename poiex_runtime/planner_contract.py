"""Trusted boundary between probabilistic planning and governed execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

from .models import ActionIntent, MaterialTarget


@dataclass(frozen=True)
class PlannerProposal:
    """Untrusted planner output.

    Deliberately excludes lease IDs, authority claims, target hashes, evidence IDs,
    execution receipts and gate decisions. The planner can propose WHAT, not mint
    the credentials or evidence that authorize HOW.
    """

    action_type: str
    target_id: str
    parameters: Dict[str, Any]
    rationale: str = ""


def proposal_to_intent(
    proposal: PlannerProposal,
    *,
    intent_id: str,
    trusted_agent_id: str,
    trusted_target: MaterialTarget,
    requested_at: datetime,
) -> ActionIntent:
    """Bind an untrusted proposal to the current trusted target version/hash.

    Target identity is re-resolved outside the model. A planner cannot smuggle a
    stale or alternate target hash into the control plane.
    """

    if proposal.target_id != trusted_target.target_id:
        raise ValueError("planner proposal target does not match trusted target")
    return ActionIntent.create(
        intent_id=intent_id,
        agent_id=trusted_agent_id,
        action_type=proposal.action_type,
        target_id=trusted_target.target_id,
        target_hash=trusted_target.target_hash,
        parameters=dict(proposal.parameters),
        requested_at=requested_at,
    )
