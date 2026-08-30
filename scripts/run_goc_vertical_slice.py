#!/usr/bin/env python3
"""Run a deterministic local GOC vertical slice for demo/evidence rehearsal."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from poiex_runtime.authority_provenance import AuthorityProvenanceRecord
from poiex_runtime.control_plane import ControlPlane
from poiex_runtime.models import AgentRecord, AuthorityLease, EvidenceItem, IdentityContext, MaterialTarget
from poiex_runtime.orchestrator import GovernedOrchestrator
from poiex_runtime.planner_contract import PlannerProposal
from poiex_runtime.store import MemoryStore


def main() -> None:
    now = datetime(2026, 8, 26, 22, 30, tzinfo=timezone.utc)
    store = MemoryStore()
    cp = ControlPlane(
        store,
        clock=lambda: now,
        require_authority_provenance=True,
        trusted_authority_roots={"plant-owner-root"},
    )
    orch = GovernedOrchestrator(store, cp)

    agent = AgentRecord(
        agent_id="agent-maint-01",
        role="maintenance_outage_coordinator",
        declared_capabilities={"issue_synthetic_work_order"},
        current_epoch=7,
    )
    store.put_agent(agent)
    evidence = EvidenceItem.runtime_observation(
        evidence_id="ev-runtime-001",
        subject_id=agent.agent_id,
        claim="issue_synthetic_work_order",
        observed_at=now,
        trace_id="trace-obs-001",
    )
    store.put_evidence(evidence)
    cp.promote_observed_capability(agent.agent_id, "issue_synthetic_work_order", evidence.evidence_id)
    target = MaterialTarget.create(
        target_id="pump-A",
        target_type="synthetic_equipment",
        canonical_ref="plant-demo/pump-A",
        version=3,
        allowed_actions={"issue_synthetic_work_order"},
    )
    store.put_target(target)
    root_provenance = AuthorityProvenanceRecord(
        provenance_id="prov-root",
        subject_id="synthetic-owner",
        issuer_id="plant-owner-root",
        scope={"issue_synthetic_work_order"},
        epoch=7,
        issued_at=now - timedelta(hours=1),
        revoked_at=None,
        parent_provenance_id=None,
    )
    child_provenance = AuthorityProvenanceRecord(
        provenance_id="prov-child",
        subject_id=agent.agent_id,
        issuer_id="synthetic-owner",
        scope={"issue_synthetic_work_order"},
        epoch=7,
        issued_at=now - timedelta(minutes=10),
        revoked_at=None,
        parent_provenance_id=root_provenance.provenance_id,
    )
    store.put_authority_provenance(root_provenance)
    store.put_authority_provenance(child_provenance)
    lease = AuthorityLease(
        lease_id="lease-001",
        agent_id=agent.agent_id,
        scope={"issue_synthetic_work_order"},
        epoch=7,
        issued_at=now - timedelta(minutes=5),
        expires_at=now + timedelta(minutes=20),
        revoked_at=None,
        issuer="synthetic-owner",
        provenance_id=child_provenance.provenance_id,
    )
    store.put_lease(lease)
    identity = IdentityContext(agent_id=agent.agent_id, session_id="session-001", authenticated=True)

    proposal = PlannerProposal(
        action_type="issue_synthetic_work_order",
        target_id="pump-A",
        parameters={"work_order": "WO-DEMO-VERTICAL-SLICE"},
        rationale="synthetic outage-coordination rehearsal",
    )
    allowed = orch.execute_proposal(
        identity=identity,
        lease_id=lease.lease_id,
        proposal=proposal,
        authorized_target_id="pump-A",
        intent_id="intent-demo-allow",
        requested_at=now,
    )

    lease.revoked_at = now - timedelta(seconds=1)
    store.put_lease(lease)
    blocked = orch.execute_proposal(
        identity=identity,
        lease_id=lease.lease_id,
        proposal=proposal,
        authorized_target_id="pump-A",
        intent_id="intent-demo-block",
        requested_at=now,
    )

    target_substitution = "NOT_RUN"
    try:
        orch.execute_proposal(
            identity=identity,
            lease_id=lease.lease_id,
            proposal=PlannerProposal(
                action_type="issue_synthetic_work_order",
                target_id="pump-B",
                parameters={},
            ),
            authorized_target_id="pump-A",
            intent_id="intent-demo-target-substitution",
            requested_at=now,
        )
    except ValueError as exc:
        target_substitution = f"REJECTED:{exc}"

    report = {
        "truth_ceiling": "LOCAL_MEMORYSTORE_DEMO_ONLY",
        "authority_provenance": {
            "required": True,
            "trusted_root": "plant-owner-root",
            "lineage": ["prov-child", "prov-root"],
        },
        "allowed": {
            "decision": allowed.receipt.decision,
            "replay": allowed.replay.reconstruction_status,
        },
        "revoked_authority": {
            "decision": blocked.receipt.decision,
            "reasons": blocked.receipt.reasons,
            "replay": blocked.replay.reconstruction_status,
        },
        "planner_target_substitution": target_substitution,
        "synthetic_mutation_count": store.synthetic_mutation_count,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
