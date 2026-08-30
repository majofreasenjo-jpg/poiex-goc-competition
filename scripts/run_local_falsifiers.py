import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from poiex_runtime.control_plane import ControlPlane
from poiex_runtime.models import (
    ActionIntent,
    AgentRecord,
    AuthorityLease,
    EvidenceItem,
    EvidenceSourceType,
    IdentityContext,
    MaterialTarget,
)
from poiex_runtime.store import MemoryStore

NOW = datetime(2026, 8, 26, 20, 0, tzinfo=timezone.utc)


def setup():
    store = MemoryStore()
    cp = ControlPlane(store, clock=lambda: NOW)
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
        observed_at=NOW,
        trace_id="trace-obs-001",
    )
    store.put_evidence(evidence)
    cp.promote_observed_capability(agent.agent_id, evidence.claim, evidence.evidence_id)
    target = MaterialTarget.create(
        target_id="pump-A",
        target_type="synthetic_equipment",
        canonical_ref="plant-demo/pump-A",
        version=3,
        allowed_actions={"issue_synthetic_work_order"},
    )
    other = MaterialTarget.create(
        target_id="pump-B",
        target_type="synthetic_equipment",
        canonical_ref="plant-demo/pump-B",
        version=3,
        allowed_actions={"issue_synthetic_work_order"},
    )
    store.put_target(target)
    store.put_target(other)
    lease = AuthorityLease(
        lease_id="lease-001",
        agent_id=agent.agent_id,
        scope={"issue_synthetic_work_order"},
        epoch=7,
        issued_at=NOW - timedelta(minutes=10),
        expires_at=NOW + timedelta(minutes=30),
        revoked_at=None,
        issuer="synthetic-owner",
    )
    store.put_lease(lease)
    identity = IdentityContext(agent_id=agent.agent_id, session_id="session-001", authenticated=True)
    return store, cp, agent, evidence, target, other, lease, identity


def make_intent(target, target_id=None, target_hash=None, suffix="001"):
    return ActionIntent.create(
        intent_id=f"intent-{suffix}",
        agent_id="agent-maint-01",
        action_type="issue_synthetic_work_order",
        target_id=target_id or target.target_id,
        target_hash=target_hash or target.target_hash,
        parameters={"work_order": f"WO-DEMO-{suffix}"},
        requested_at=NOW,
    )


def record(case_id, result, expected, extra=None):
    payload = {
        "case_id": case_id,
        "result": result,
        "expected": expected,
        "pass": result == expected,
    }
    if extra:
        payload.update(extra)
    return payload


def main():
    evidence_rows = []

    fg1_variants = []
    for variant in ("REVOKED", "EXPIRED", "STALE_EPOCH", "OUT_OF_SCOPE"):
        store, cp, agent, ev, target, other, lease, identity = setup()
        if variant == "REVOKED":
            lease.revoked_at = NOW - timedelta(seconds=1)
            expected_reason = "AUTHORITY_REVOKED"
        elif variant == "EXPIRED":
            lease.expires_at = NOW - timedelta(seconds=1)
            expected_reason = "AUTHORITY_EXPIRED"
        elif variant == "STALE_EPOCH":
            lease.epoch = 6
            expected_reason = "AUTHORITY_EPOCH_STALE"
        else:
            lease.scope = {"inspect_synthetic_work_order"}
            expected_reason = "AUTHORITY_OUT_OF_SCOPE"
        store.put_lease(lease)
        rcpt = cp.execute(identity, lease.lease_id, make_intent(target, suffix=f"FG1-{variant}"))
        fg1_variants.append({
            "variant": variant,
            "decision": rcpt.decision,
            "reasons": rcpt.reasons,
            "expected_reason": expected_reason,
            "mutation_count": store.synthetic_mutation_count,
            "pass": rcpt.decision == "BLOCK" and expected_reason in rcpt.reasons and store.synthetic_mutation_count == 0,
            "receipt_id": rcpt.receipt_id,
        })
    fg1_pass = all(v["pass"] for v in fg1_variants)
    evidence_rows.append(record("F-G1", "BLOCK_ALL_VARIANTS" if fg1_pass else "UNEXPECTED", "BLOCK_ALL_VARIANTS", {
        "variants": fg1_variants,
    }))

    store, cp, agent, ev, target, other, lease, identity = setup()
    self_claim = EvidenceItem(
        evidence_id="ev-self-001",
        subject_id=agent.agent_id,
        claim="diagnose_synthetic_fault",
        source_type=EvidenceSourceType.SELF_DECLARATION,
        observed_at=NOW,
        payload_hash="self-claim",
        trace_id="trace-self-001",
    )
    store.put_evidence(self_claim)
    try:
        cp.promote_observed_capability(agent.agent_id, self_claim.claim, self_claim.evidence_id)
        fg2_result = "PROMOTED"
    except ValueError:
        fg2_result = "REJECTED"
    evidence_rows.append(record("F-G2", fg2_result, "REJECTED", {
        "observed_capabilities": sorted(store.get_agent(agent.agent_id).observed_capabilities),
    }))

    store, cp, agent, ev, target, other, lease, identity = setup()
    intent = make_intent(target, target_id=other.target_id, target_hash=target.target_hash, suffix="FG3")
    rcpt = cp.execute(identity, lease.lease_id, intent)
    evidence_rows.append(record("F-G3", rcpt.decision, "BLOCK", {
        "reasons": rcpt.reasons,
        "mutation_count": store.synthetic_mutation_count,
        "receipt_id": rcpt.receipt_id,
    }))

    store, cp, agent, ev, target, other, lease, identity = setup()
    rcpt = cp.execute(identity, lease.lease_id, make_intent(target, suffix="FG4"))
    complete = cp.replay(rcpt.receipt_id)
    del store.leases[lease.lease_id]
    broken = cp.replay(rcpt.receipt_id)
    fg4_result = "PASS_THEN_FAIL" if (
        complete.reconstruction_status == "PASS" and broken.reconstruction_status == "FAIL"
    ) else "UNEXPECTED"
    evidence_rows.append(record("F-G4", fg4_result, "PASS_THEN_FAIL", {
        "complete_status": complete.reconstruction_status,
        "broken_status": broken.reconstruction_status,
        "broken_mismatches": broken.mismatches,
        "receipt_id": rcpt.receipt_id,
    }))

    summary = {
        "schema": "POIEX_LOCAL_FALSIFIER_EVIDENCE_V0_5",
        "generated_at": NOW.isoformat(),
        "truth_ceiling": "LOCAL_CLEAN_ROOM_ONLY_NOT_DEPLOYED",
        "all_core_pass": all(row["pass"] for row in evidence_rows),
        "cases": evidence_rows,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
