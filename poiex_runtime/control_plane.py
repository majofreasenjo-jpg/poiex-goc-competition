from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Callable, Optional, Set

from .authority_provenance import verify_authority_provenance
from .models import (
    ActionIntent,
    EvidenceSourceType,
    ExecutionReceipt,
    IdentityContext,
    ReplayManifest,
)
from .store import RuntimeStore


class ControlPlane:
    def __init__(
        self,
        store: RuntimeStore,
        clock: Optional[Callable[[], datetime]] = None,
        *,
        require_authority_provenance: bool = False,
        trusted_authority_roots: Optional[Set[str]] = None,
    ):
        self.store = store
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.require_authority_provenance = require_authority_provenance
        self.trusted_authority_roots = set(trusted_authority_roots or set())

    def promote_observed_capability(
        self,
        agent_id: str,
        capability: str,
        evidence_id: str,
    ) -> None:
        agent = self.store.get_agent(agent_id)
        if agent is None:
            raise ValueError("unknown agent")
        evidence = self.store.get_evidence(evidence_id)
        if evidence is None:
            raise ValueError("missing evidence")
        if evidence.subject_id != agent_id or evidence.claim != capability:
            raise ValueError("evidence does not bind subject and claim")
        if evidence.source_type is not EvidenceSourceType.RUNTIME_OBSERVATION:
            raise ValueError("only runtime observation may create OBSERVED capability")
        agent.observed_capabilities[capability] = evidence_id
        self.store.put_agent(agent)

    def _receipt(
        self,
        *,
        run_id: str,
        identity: IdentityContext,
        lease_id: Optional[str],
        intent: ActionIntent,
        evidence_refs: list[str],
        target_id: Optional[str],
        target_hash: Optional[str],
        result_hash: Optional[str],
        decision: str,
        reasons: list[str],
    ) -> ExecutionReceipt:
        receipt = ExecutionReceipt(
            receipt_id=f"rcpt-{uuid.uuid4().hex}",
            run_id=run_id,
            agent_id=identity.agent_id,
            session_id=identity.session_id,
            lease_id=lease_id,
            registry_evidence_refs=list(evidence_refs),
            target_id=target_id,
            target_hash=target_hash,
            intent_id=intent.intent_id,
            intent_hash=intent.intent_hash,
            executor_result_hash=result_hash,
            decision=decision,
            reasons=list(reasons),
            created_at=self.clock(),
            trace_id=f"trace-{uuid.uuid4().hex}",
        )
        self.store.put_receipt(receipt)
        return receipt

    def execute(
        self,
        identity: IdentityContext,
        lease_id: str,
        intent: ActionIntent,
    ) -> ExecutionReceipt:
        run_id = f"run-{uuid.uuid4().hex}"
        now = self.clock()
        reasons: list[str] = []

        agent = self.store.get_agent(identity.agent_id)
        if not identity.authenticated:
            reasons.append("IDENTITY_NOT_AUTHENTICATED")
        if agent is None:
            reasons.append("IDENTITY_UNKNOWN")
        if intent.agent_id != identity.agent_id:
            reasons.append("IDENTITY_INTENT_MISMATCH")
        if reasons:
            return self._receipt(
                run_id=run_id,
                identity=identity,
                lease_id=lease_id,
                intent=intent,
                evidence_refs=[],
                target_id=intent.target_id,
                target_hash=intent.target_hash,
                result_hash=None,
                decision="BLOCK",
                reasons=reasons,
            )

        evidence_id = agent.observed_capabilities.get(intent.action_type)
        evidence = self.store.get_evidence(evidence_id) if evidence_id else None
        if evidence is None or evidence.source_type is not EvidenceSourceType.RUNTIME_OBSERVATION:
            reasons.append("CAPABILITY_NOT_OBSERVED")

        lease = self.store.get_lease(lease_id)
        if lease is None:
            reasons.append("AUTHORITY_LEASE_MISSING")
        else:
            if lease.agent_id != identity.agent_id:
                reasons.append("AUTHORITY_AGENT_MISMATCH")
            if intent.action_type not in lease.scope:
                reasons.append("AUTHORITY_OUT_OF_SCOPE")
            if lease.revoked_at is not None and lease.revoked_at <= now:
                reasons.append("AUTHORITY_REVOKED")
            if lease.expires_at <= now:
                reasons.append("AUTHORITY_EXPIRED")
            if lease.epoch != agent.current_epoch:
                reasons.append("AUTHORITY_EPOCH_STALE")
            if self.require_authority_provenance:
                provenance = verify_authority_provenance(
                    store=self.store,
                    lease=lease,
                    now=now,
                    trusted_root_issuers=self.trusted_authority_roots,
                )
                reasons.extend(provenance.reasons)

        target = self.store.get_target(intent.target_id)
        if target is None:
            reasons.append("TARGET_UNKNOWN")
        else:
            if intent.target_hash != target.target_hash:
                reasons.append("TARGET_HASH_MISMATCH")
            if intent.action_type not in target.allowed_actions:
                reasons.append("TARGET_ACTION_NOT_ALLOWED")

        if reasons:
            return self._receipt(
                run_id=run_id,
                identity=identity,
                lease_id=lease_id,
                intent=intent,
                evidence_refs=[evidence_id] if evidence_id else [],
                target_id=intent.target_id,
                target_hash=intent.target_hash,
                result_hash=None,
                decision="BLOCK",
                reasons=reasons,
            )

        result_hash = self.store.execute_synthetic_action(
            run_id,
            {
                "agent_id": identity.agent_id,
                "action_type": intent.action_type,
                "target_id": target.target_id,
                "target_hash": target.target_hash,
                "parameters": intent.parameters,
            },
        )
        return self._receipt(
            run_id=run_id,
            identity=identity,
            lease_id=lease_id,
            intent=intent,
            evidence_refs=[evidence_id],
            target_id=target.target_id,
            target_hash=target.target_hash,
            result_hash=result_hash,
            decision="ALLOW",
            reasons=["ALL_MATERIAL_GATES_PASS"],
        )

    def replay(self, receipt_id: str) -> ReplayManifest:
        receipt = self.store.get_receipt(receipt_id)
        if receipt is None:
            raise ValueError("unknown receipt")

        mismatches: list[str] = []
        agent = self.store.get_agent(receipt.agent_id)
        if agent is None:
            mismatches.append("MISSING_AGENT")

        if receipt.lease_id and self.store.get_lease(receipt.lease_id) is None:
            mismatches.append("MISSING_LEASE")

        for evidence_id in receipt.registry_evidence_refs:
            if self.store.get_evidence(evidence_id) is None:
                mismatches.append(f"MISSING_EVIDENCE:{evidence_id}")

        if receipt.target_id:
            target = self.store.get_target(receipt.target_id)
            if target is None:
                mismatches.append("MISSING_TARGET")
            elif receipt.target_hash != target.target_hash:
                mismatches.append("TARGET_HASH_CHANGED")

        if receipt.decision == "ALLOW":
            if not receipt.executor_result_hash:
                mismatches.append("MISSING_EXECUTOR_RESULT_HASH")
            elif not self.store.has_synthetic_action(
                receipt.run_id, receipt.executor_result_hash
            ):
                mismatches.append("EXECUTOR_RESULT_NOT_RECONSTRUCTABLE")

        status = "PASS" if not mismatches else "FAIL"
        return ReplayManifest(
            run_id=receipt.run_id,
            receipt_id=receipt.receipt_id,
            reconstruction_status=status,
            mismatches=mismatches,
            trace_id=receipt.trace_id,
        )
