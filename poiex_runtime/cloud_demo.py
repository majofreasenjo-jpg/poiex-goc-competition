"""Synthetic, receiver-native Cloud Run demo scenarios for the deterministic GOC.

The module deliberately accepts only PlannerProposal fields. Identity, authority,
observed capability, exact target binding, provenance roots, gate decisions, receipts,
and execution results are created or resolved by trusted deterministic code.

SYNTHETIC_DEMO_ONLY. This module is not an industrial control interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Optional

from .authority_provenance import AuthorityProvenanceRecord
from .control_plane import ControlPlane
from .models import AgentRecord, AuthorityLease, EvidenceItem, IdentityContext, MaterialTarget
from .orchestrator import GovernedOrchestrator
from .planner_contract import PlannerProposal
from .store import RuntimeStore


_ALLOWED_CASES = {
    "allow",
    "revoked_authority",
    "target_substitution",
    "policy_epoch_stale",
}
_SCENARIO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_ACTION = "issue_synthetic_work_order"
_TARGET_ID = "pump-A"
_TRUSTED_ROOT = "plant-owner-root"


@dataclass(frozen=True)
class DemoContext:
    control_plane: ControlPlane
    orchestrator: GovernedOrchestrator
    identity: IdentityContext
    lease_id: str
    authorized_target_id: str
    now: datetime


def _validate_scenario_id(value: str) -> str:
    if not _SCENARIO_RE.fullmatch(value):
        raise ValueError("scenario_id must be 1-64 safe identifier characters")
    return value


def bootstrap_synthetic_mission(
    store: RuntimeStore,
    *,
    now: datetime,
    scenario_id: str,
) -> DemoContext:
    """Seed the bounded synthetic institutional facts required by one demo run."""

    scenario_id = _validate_scenario_id(scenario_id)
    cp = ControlPlane(
        store,
        clock=lambda: now,
        require_authority_provenance=True,
        trusted_authority_roots={_TRUSTED_ROOT},
    )
    orch = GovernedOrchestrator(store, cp)

    agent = AgentRecord(
        agent_id="agent-maint-01",
        role="maintenance_outage_coordinator",
        declared_capabilities={_ACTION},
        current_epoch=7,
    )
    store.put_agent(agent)

    evidence = EvidenceItem.runtime_observation(
        evidence_id="ev-runtime-001",
        subject_id=agent.agent_id,
        claim=_ACTION,
        observed_at=now,
        trace_id=f"trace-observed-{scenario_id}",
    )
    store.put_evidence(evidence)
    cp.promote_observed_capability(agent.agent_id, _ACTION, evidence.evidence_id)

    target = MaterialTarget.create(
        target_id=_TARGET_ID,
        target_type="synthetic_equipment",
        canonical_ref="plant-demo/pump-A",
        version=3,
        allowed_actions={_ACTION},
    )
    store.put_target(target)

    root = AuthorityProvenanceRecord(
        provenance_id="prov-root",
        subject_id="synthetic-owner",
        issuer_id=_TRUSTED_ROOT,
        scope={_ACTION},
        epoch=7,
        issued_at=now - timedelta(hours=1),
        revoked_at=None,
        parent_provenance_id=None,
    )
    child = AuthorityProvenanceRecord(
        provenance_id="prov-child",
        subject_id=agent.agent_id,
        issuer_id="synthetic-owner",
        scope={_ACTION},
        epoch=7,
        issued_at=now - timedelta(minutes=10),
        revoked_at=None,
        parent_provenance_id=root.provenance_id,
    )
    store.put_authority_provenance(root)
    store.put_authority_provenance(child)

    lease = AuthorityLease(
        lease_id="lease-001",
        agent_id=agent.agent_id,
        scope={_ACTION},
        epoch=7,
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=20),
        revoked_at=None,
        issuer="synthetic-owner",
        provenance_id=child.provenance_id,
    )
    store.put_lease(lease)

    return DemoContext(
        control_plane=cp,
        orchestrator=orch,
        identity=IdentityContext(
            agent_id=agent.agent_id,
            session_id=f"session-{scenario_id}",
            authenticated=True,
        ),
        lease_id=lease.lease_id,
        authorized_target_id=_TARGET_ID,
        now=now,
    )


def _default_proposal(case: str, scenario_id: str) -> PlannerProposal:
    target_id = "pump-B" if case == "target_substitution" else _TARGET_ID
    return PlannerProposal(
        action_type=_ACTION,
        target_id=target_id,
        parameters={"work_order": f"WO-GOC-{scenario_id}"},
        rationale="synthetic governed maintenance-outage demonstration",
    )


def run_demo_case(
    store: RuntimeStore,
    *,
    case: str,
    now: datetime,
    scenario_id: str,
    proposal: Optional[PlannerProposal] = None,
) -> dict:
    """Run one bounded case and return a judge-readable result.

    The caller may supply an untrusted PlannerProposal, but cannot supply identity,
    lease, provenance, observed evidence, target hash, gate decision, or receipt.
    """

    if case not in _ALLOWED_CASES:
        raise ValueError(f"unsupported demo case: {case}")
    scenario_id = _validate_scenario_id(scenario_id)
    ctx = bootstrap_synthetic_mission(store, now=now, scenario_id=scenario_id)

    if case == "revoked_authority":
        lease = store.get_lease(ctx.lease_id)
        if lease is None:
            raise RuntimeError("demo lease disappeared after bootstrap")
        lease.revoked_at = now - timedelta(seconds=1)
        store.put_lease(lease)
    elif case == "policy_epoch_stale":
        agent = store.get_agent(ctx.identity.agent_id)
        if agent is None:
            raise RuntimeError("demo agent disappeared after bootstrap")
        agent.current_epoch += 1
        store.put_agent(agent)

    effective_proposal = proposal or _default_proposal(case, scenario_id)
    if case == "target_substitution" and proposal is None:
        effective_proposal = _default_proposal(case, scenario_id)

    try:
        outcome = ctx.orchestrator.execute_proposal(
            identity=ctx.identity,
            lease_id=ctx.lease_id,
            proposal=effective_proposal,
            authorized_target_id=ctx.authorized_target_id,
            intent_id=f"intent-{scenario_id}-{case}",
            requested_at=now,
        )
    except ValueError as exc:
        return {
            "schema": "GOC_CLOUD_DEMO_V0_9",
            "truth_ceiling": "SYNTHETIC_DEMO_ONLY",
            "case": case,
            "scenario_id": scenario_id,
            "decision": "REJECTED_BEFORE_INTENT",
            "reasons": [str(exc)],
            "authorized_target_id": ctx.authorized_target_id,
            "planner_target_id": effective_proposal.target_id,
            "receipt_id": None,
            "run_id": None,
            "replay": "NOT_CREATED",
        }

    return {
        "schema": "GOC_CLOUD_DEMO_V0_9",
        "truth_ceiling": "SYNTHETIC_DEMO_ONLY",
        "case": case,
        "scenario_id": scenario_id,
        "decision": outcome.receipt.decision,
        "reasons": list(outcome.receipt.reasons),
        "authorized_target_id": ctx.authorized_target_id,
        "planner_target_id": effective_proposal.target_id,
        "receipt_id": outcome.receipt.receipt_id,
        "run_id": outcome.receipt.run_id,
        "trace_id": outcome.receipt.trace_id,
        "replay": outcome.replay.reconstruction_status,
        "replay_mismatches": list(outcome.replay.mismatches),
    }
