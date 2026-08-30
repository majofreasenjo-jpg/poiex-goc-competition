from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
from typing import Any, Dict, Optional, Set


def _json_default(value: Any):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Unsupported value for canonical serialization: {type(value)!r}")


def canonical_hash(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class EvidenceSourceType(str, Enum):
    RUNTIME_OBSERVATION = "RUNTIME_OBSERVATION"
    SELF_DECLARATION = "SELF_DECLARATION"
    OWNER_ASSERTION = "OWNER_ASSERTION"
    INFERRED = "INFERRED"


@dataclass
class AgentRecord:
    agent_id: str
    role: str
    declared_capabilities: Set[str] = field(default_factory=set)
    observed_capabilities: Dict[str, str] = field(default_factory=dict)
    inferred_capabilities: Set[str] = field(default_factory=set)
    status: str = "ACTIVE"
    current_epoch: int = 1


@dataclass
class IdentityContext:
    agent_id: str
    session_id: str
    authenticated: bool


@dataclass
class AuthorityLease:
    lease_id: str
    agent_id: str
    scope: Set[str]
    epoch: int
    issued_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime]
    issuer: str
    provenance_id: Optional[str] = None


@dataclass
class EvidenceItem:
    evidence_id: str
    subject_id: str
    claim: str
    source_type: EvidenceSourceType
    observed_at: datetime
    payload_hash: str
    trace_id: str

    @classmethod
    def runtime_observation(
        cls,
        evidence_id: str,
        subject_id: str,
        claim: str,
        observed_at: datetime,
        trace_id: str,
    ) -> "EvidenceItem":
        payload_hash = canonical_hash(
            {
                "subject_id": subject_id,
                "claim": claim,
                "observed_at": observed_at,
                "trace_id": trace_id,
                "source_type": EvidenceSourceType.RUNTIME_OBSERVATION.value,
            }
        )
        return cls(
            evidence_id=evidence_id,
            subject_id=subject_id,
            claim=claim,
            source_type=EvidenceSourceType.RUNTIME_OBSERVATION,
            observed_at=observed_at,
            payload_hash=payload_hash,
            trace_id=trace_id,
        )


@dataclass
class MaterialTarget:
    target_id: str
    target_type: str
    canonical_ref: str
    version: int
    allowed_actions: Set[str]
    target_hash: str

    @classmethod
    def create(
        cls,
        target_id: str,
        target_type: str,
        canonical_ref: str,
        version: int,
        allowed_actions: Set[str],
    ) -> "MaterialTarget":
        obj = cls(
            target_id=target_id,
            target_type=target_type,
            canonical_ref=canonical_ref,
            version=version,
            allowed_actions=set(allowed_actions),
            target_hash="",
        )
        obj.target_hash = obj.compute_hash()
        return obj

    def compute_hash(self) -> str:
        return canonical_hash(
            {
                "target_id": self.target_id,
                "target_type": self.target_type,
                "canonical_ref": self.canonical_ref,
                "version": self.version,
                "allowed_actions": self.allowed_actions,
            }
        )


@dataclass
class ActionIntent:
    intent_id: str
    agent_id: str
    action_type: str
    target_id: str
    target_hash: str
    parameters: Dict[str, Any]
    requested_at: datetime
    intent_hash: str

    @classmethod
    def create(
        cls,
        intent_id: str,
        agent_id: str,
        action_type: str,
        target_id: str,
        target_hash: str,
        parameters: Dict[str, Any],
        requested_at: datetime,
    ) -> "ActionIntent":
        payload = {
            "intent_id": intent_id,
            "agent_id": agent_id,
            "action_type": action_type,
            "target_id": target_id,
            "target_hash": target_hash,
            "parameters": parameters,
            "requested_at": requested_at,
        }
        return cls(
            intent_id=intent_id,
            agent_id=agent_id,
            action_type=action_type,
            target_id=target_id,
            target_hash=target_hash,
            parameters=dict(parameters),
            requested_at=requested_at,
            intent_hash=canonical_hash(payload),
        )


@dataclass
class ExecutionReceipt:
    receipt_id: str
    run_id: str
    agent_id: str
    session_id: str
    lease_id: Optional[str]
    registry_evidence_refs: list[str]
    target_id: Optional[str]
    target_hash: Optional[str]
    intent_id: str
    intent_hash: str
    executor_result_hash: Optional[str]
    decision: str
    reasons: list[str]
    created_at: datetime
    trace_id: str


@dataclass
class ReplayManifest:
    run_id: str
    receipt_id: str
    reconstruction_status: str
    mismatches: list[str]
    trace_id: str
