"""Deterministic receiver-native fault harness for the GOC competition vertical slice.

The fault taxonomy is implemented locally against GOC contracts. Passing these cases
is evidence about this runtime only; it is not imported evidence from any source lane
and is not production/cloud validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .control_plane import ControlPlane
from .models import (
    ActionIntent,
    AgentRecord,
    AuthorityLease,
    EvidenceItem,
    IdentityContext,
    MaterialTarget,
)
from .planner_contract import PlannerProposal, proposal_to_intent
from .store import MemoryStore


@dataclass(frozen=True)
class FaultOutcome:
    fault_id: str
    safe_outcome: bool
    observed_result: str


@dataclass(frozen=True)
class FaultMatrixReport:
    cases: tuple[FaultOutcome, ...]
    execution_environment: str = "LOCAL_RECEIVER_NATIVE"
    external_validation: bool = False
    cloud_deployment_evidence: bool = False

    @property
    def all_safe(self) -> bool:
        return all(case.safe_outcome for case in self.cases)


def _seed(*, now: datetime, observed: bool = True):
    store = MemoryStore()
    cp = ControlPlane(store, clock=lambda: now)
    agent = AgentRecord(
        agent_id="agent-maint-01",
        role="maintenance_outage_coordinator",
        declared_capabilities={"issue_synthetic_work_order"},
        current_epoch=7,
    )
    store.put_agent(agent)
    if observed:
        evidence = EvidenceItem.runtime_observation(
            evidence_id="ev-runtime-001",
            subject_id=agent.agent_id,
            claim="issue_synthetic_work_order",
            observed_at=now,
            trace_id="trace-obs-001",
        )
        store.put_evidence(evidence)
        cp.promote_observed_capability(
            agent.agent_id, "issue_synthetic_work_order", evidence.evidence_id
        )
    target = MaterialTarget.create(
        target_id="pump-A",
        target_type="synthetic_equipment",
        canonical_ref="plant-demo/pump-A",
        version=3,
        allowed_actions={"issue_synthetic_work_order"},
    )
    store.put_target(target)
    lease = AuthorityLease(
        lease_id="lease-001",
        agent_id=agent.agent_id,
        scope={"issue_synthetic_work_order"},
        epoch=7,
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=20),
        revoked_at=None,
        issuer="maintenance-owner",
    )
    store.put_lease(lease)
    identity = IdentityContext(
        agent_id=agent.agent_id,
        session_id="session-001",
        authenticated=True,
    )
    return store, cp, agent, target, lease, identity


def _intent(*, now, agent, target, action_type="issue_synthetic_work_order"):
    return ActionIntent.create(
        intent_id=f"intent-{action_type}",
        agent_id=agent.agent_id,
        action_type=action_type,
        target_id=target.target_id,
        target_hash=target.target_hash,
        parameters={"work_order": "WO-FAULT"},
        requested_at=now,
    )


def run_receiver_native_fault_matrix() -> FaultMatrixReport:
    now = datetime(2026, 8, 27, 13, 45, tzinfo=timezone.utc)
    cases: list[FaultOutcome] = []

    # Prompt-level attempt to mint authority fields is rejected by the typed proposal.
    try:
        PlannerProposal(  # type: ignore[call-arg]
            action_type="issue_synthetic_work_order",
            target_id="pump-A",
            parameters={},
            lease_id="forged-lease",
        )
        prompt_safe = False
        prompt_result = "FORGED_FIELD_ACCEPTED"
    except TypeError:
        prompt_safe = True
        prompt_result = "FORGED_AUTHORITY_FIELD_REJECTED"
    cases.append(FaultOutcome("PROMPT_AUTHORITY_ESCALATION", prompt_safe, prompt_result))

    # Capability escalation cannot bypass observed-capability and lease/target scope gates.
    store, cp, agent, target, lease, identity = _seed(now=now)
    escalated = _intent(now=now, agent=agent, target=target, action_type="shutdown_asset")
    receipt = cp.execute(identity, lease.lease_id, escalated)
    cases.append(
        FaultOutcome(
            "CAPABILITY_ESCALATION",
            receipt.decision == "BLOCK" and store.synthetic_mutation_count == 0,
            ",".join(receipt.reasons),
        )
    )

    # Planner target substitution is rejected before ActionIntent construction.
    store, cp, agent, target, lease, identity = _seed(now=now)
    proposal = PlannerProposal(
        action_type="issue_synthetic_work_order",
        target_id="pump-B",
        parameters={},
    )
    try:
        proposal_to_intent(
            proposal,
            intent_id="intent-target-sub",
            trusted_agent_id=agent.agent_id,
            trusted_target=target,
            requested_at=now,
        )
        target_safe = False
        target_result = "SUBSTITUTION_ACCEPTED"
    except ValueError:
        target_safe = True
        target_result = "REJECTED_BEFORE_INTENT"
    cases.append(FaultOutcome("TARGET_SUBSTITUTION", target_safe, target_result))

    # Declared/memory-injected capability is not enough to become OBSERVED.
    store, cp, agent, target, lease, identity = _seed(now=now, observed=False)
    receipt = cp.execute(identity, lease.lease_id, _intent(now=now, agent=agent, target=target))
    cases.append(
        FaultOutcome(
            "MEMORY_DECLARATION_POISONING",
            receipt.decision == "BLOCK" and "CAPABILITY_NOT_OBSERVED" in receipt.reasons,
            ",".join(receipt.reasons),
        )
    )

    # Revocation at the decision instant wins over a racing action request.
    store, cp, agent, target, lease, identity = _seed(now=now)
    lease.revoked_at = now
    store.put_lease(lease)
    receipt = cp.execute(identity, lease.lease_id, _intent(now=now, agent=agent, target=target))
    cases.append(
        FaultOutcome(
            "REVOCATION_RACE",
            receipt.decision == "BLOCK" and "AUTHORITY_REVOKED" in receipt.reasons,
            ",".join(receipt.reasons),
        )
    )

    # Receipt target tamper must be visible during replay.
    store, cp, agent, target, lease, identity = _seed(now=now)
    receipt = cp.execute(identity, lease.lease_id, _intent(now=now, agent=agent, target=target))
    stored_receipt = store.receipts[receipt.receipt_id]
    stored_receipt.target_hash = "tampered-target-hash"
    replay = cp.replay(receipt.receipt_id)
    cases.append(
        FaultOutcome(
            "RECEIPT_TARGET_TAMPER",
            replay.reconstruction_status == "FAIL" and "TARGET_HASH_CHANGED" in replay.mismatches,
            ",".join(replay.mismatches),
        )
    )

    # Deleting evidence after an allowed action must break reconstruction.
    store, cp, agent, target, lease, identity = _seed(now=now)
    receipt = cp.execute(identity, lease.lease_id, _intent(now=now, agent=agent, target=target))
    for evidence_id in receipt.registry_evidence_refs:
        store.evidence.pop(evidence_id, None)
    replay = cp.replay(receipt.receipt_id)
    cases.append(
        FaultOutcome(
            "REPLAY_EVIDENCE_LOSS",
            replay.reconstruction_status == "FAIL"
            and any(item.startswith("MISSING_EVIDENCE:") for item in replay.mismatches),
            ",".join(replay.mismatches),
        )
    )

    # An old lease cannot survive a policy/epoch advance.
    store, cp, agent, target, lease, identity = _seed(now=now)
    agent.current_epoch = 8
    store.put_agent(agent)
    receipt = cp.execute(identity, lease.lease_id, _intent(now=now, agent=agent, target=target))
    cases.append(
        FaultOutcome(
            "POLICY_EPOCH_DOWNGRADE",
            receipt.decision == "BLOCK" and "AUTHORITY_EPOCH_STALE" in receipt.reasons,
            ",".join(receipt.reasons),
        )
    )

    return FaultMatrixReport(cases=tuple(cases))
