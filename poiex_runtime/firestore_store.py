"""Firestore storage adapter for the governed control plane.

The adapter deliberately keeps Firestore outside authorization logic. It can be
contract-tested with an injected client without credentials. A real Firestore client
is created only when ``FirestoreStore.from_default_credentials`` is called.

LOCAL_ADAPTER_CONTRACT_PASS != FIRESTORE_DEPLOYMENT_EVIDENCE.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

from .authority_provenance import AuthorityProvenanceRecord
from .models import (
    AgentRecord,
    AuthorityLease,
    EvidenceItem,
    EvidenceSourceType,
    ExecutionReceipt,
    MaterialTarget,
    canonical_hash,
)


SCHEMA_VERSION = 2


def _require_mapping(data: Any, *, object_type: str) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError(f"invalid {object_type} document")
    return data


def _require_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field} must be datetime")
    return value


def _agent_to_doc(agent: AgentRecord) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "object_type": "AgentRecord",
        "agent_id": agent.agent_id,
        "role": agent.role,
        "declared_capabilities": sorted(agent.declared_capabilities),
        "observed_capabilities": dict(agent.observed_capabilities),
        "inferred_capabilities": sorted(agent.inferred_capabilities),
        "status": agent.status,
        "current_epoch": agent.current_epoch,
    }


def _agent_from_doc(data: Mapping[str, Any]) -> AgentRecord:
    data = _require_mapping(data, object_type="AgentRecord")
    return AgentRecord(
        agent_id=str(data["agent_id"]),
        role=str(data["role"]),
        declared_capabilities=set(data.get("declared_capabilities", [])),
        observed_capabilities=dict(data.get("observed_capabilities", {})),
        inferred_capabilities=set(data.get("inferred_capabilities", [])),
        status=str(data.get("status", "ACTIVE")),
        current_epoch=int(data.get("current_epoch", 1)),
    )


def _lease_to_doc(lease: AuthorityLease) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "object_type": "AuthorityLease",
        "lease_id": lease.lease_id,
        "agent_id": lease.agent_id,
        "scope": sorted(lease.scope),
        "epoch": lease.epoch,
        "issued_at": lease.issued_at,
        "expires_at": lease.expires_at,
        "revoked_at": lease.revoked_at,
        "issuer": lease.issuer,
        "provenance_id": lease.provenance_id,
    }


def _lease_from_doc(data: Mapping[str, Any]) -> AuthorityLease:
    data = _require_mapping(data, object_type="AuthorityLease")
    revoked = data.get("revoked_at")
    if revoked is not None:
        revoked = _require_datetime(revoked, field="revoked_at")
    return AuthorityLease(
        lease_id=str(data["lease_id"]),
        agent_id=str(data["agent_id"]),
        scope=set(data.get("scope", [])),
        epoch=int(data["epoch"]),
        issued_at=_require_datetime(data["issued_at"], field="issued_at"),
        expires_at=_require_datetime(data["expires_at"], field="expires_at"),
        revoked_at=revoked,
        issuer=str(data["issuer"]),
        provenance_id=data.get("provenance_id"),
    )


def _provenance_to_doc(record: AuthorityProvenanceRecord) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "object_type": "AuthorityProvenanceRecord",
        "provenance_id": record.provenance_id,
        "subject_id": record.subject_id,
        "issuer_id": record.issuer_id,
        "scope": sorted(record.scope),
        "epoch": record.epoch,
        "issued_at": record.issued_at,
        "revoked_at": record.revoked_at,
        "parent_provenance_id": record.parent_provenance_id,
    }


def _provenance_from_doc(data: Mapping[str, Any]) -> AuthorityProvenanceRecord:
    data = _require_mapping(data, object_type="AuthorityProvenanceRecord")
    revoked = data.get("revoked_at")
    if revoked is not None:
        revoked = _require_datetime(revoked, field="revoked_at")
    return AuthorityProvenanceRecord(
        provenance_id=str(data["provenance_id"]),
        subject_id=str(data["subject_id"]),
        issuer_id=str(data["issuer_id"]),
        scope=set(data.get("scope", [])),
        epoch=int(data["epoch"]),
        issued_at=_require_datetime(data["issued_at"], field="issued_at"),
        revoked_at=revoked,
        parent_provenance_id=data.get("parent_provenance_id"),
    )


def _evidence_to_doc(evidence: EvidenceItem) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "object_type": "EvidenceItem",
        "evidence_id": evidence.evidence_id,
        "subject_id": evidence.subject_id,
        "claim": evidence.claim,
        "source_type": evidence.source_type.value,
        "observed_at": evidence.observed_at,
        "payload_hash": evidence.payload_hash,
        "trace_id": evidence.trace_id,
    }


def _evidence_from_doc(data: Mapping[str, Any]) -> EvidenceItem:
    data = _require_mapping(data, object_type="EvidenceItem")
    return EvidenceItem(
        evidence_id=str(data["evidence_id"]),
        subject_id=str(data["subject_id"]),
        claim=str(data["claim"]),
        source_type=EvidenceSourceType(str(data["source_type"])),
        observed_at=_require_datetime(data["observed_at"], field="observed_at"),
        payload_hash=str(data["payload_hash"]),
        trace_id=str(data["trace_id"]),
    )


def _target_to_doc(target: MaterialTarget) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "object_type": "MaterialTarget",
        "target_id": target.target_id,
        "target_type": target.target_type,
        "canonical_ref": target.canonical_ref,
        "version": target.version,
        "allowed_actions": sorted(target.allowed_actions),
        "target_hash": target.target_hash,
    }


def _target_from_doc(data: Mapping[str, Any]) -> MaterialTarget:
    data = _require_mapping(data, object_type="MaterialTarget")
    target = MaterialTarget(
        target_id=str(data["target_id"]),
        target_type=str(data["target_type"]),
        canonical_ref=str(data["canonical_ref"]),
        version=int(data["version"]),
        allowed_actions=set(data.get("allowed_actions", [])),
        target_hash=str(data["target_hash"]),
    )
    if target.compute_hash() != target.target_hash:
        raise ValueError("stored MaterialTarget hash does not match its canonical fields")
    return target


def _receipt_to_doc(receipt: ExecutionReceipt) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "object_type": "ExecutionReceipt",
        "receipt_id": receipt.receipt_id,
        "run_id": receipt.run_id,
        "agent_id": receipt.agent_id,
        "session_id": receipt.session_id,
        "lease_id": receipt.lease_id,
        "registry_evidence_refs": list(receipt.registry_evidence_refs),
        "target_id": receipt.target_id,
        "target_hash": receipt.target_hash,
        "intent_id": receipt.intent_id,
        "intent_hash": receipt.intent_hash,
        "executor_result_hash": receipt.executor_result_hash,
        "decision": receipt.decision,
        "reasons": list(receipt.reasons),
        "created_at": receipt.created_at,
        "trace_id": receipt.trace_id,
    }


def _receipt_from_doc(data: Mapping[str, Any]) -> ExecutionReceipt:
    data = _require_mapping(data, object_type="ExecutionReceipt")
    return ExecutionReceipt(
        receipt_id=str(data["receipt_id"]),
        run_id=str(data["run_id"]),
        agent_id=str(data["agent_id"]),
        session_id=str(data["session_id"]),
        lease_id=data.get("lease_id"),
        registry_evidence_refs=list(data.get("registry_evidence_refs", [])),
        target_id=data.get("target_id"),
        target_hash=data.get("target_hash"),
        intent_id=str(data["intent_id"]),
        intent_hash=str(data["intent_hash"]),
        executor_result_hash=data.get("executor_result_hash"),
        decision=str(data["decision"]),
        reasons=list(data.get("reasons", [])),
        created_at=_require_datetime(data["created_at"], field="created_at"),
        trace_id=str(data["trace_id"]),
    )


class FirestoreStore:
    """Firestore-backed implementation of RuntimeStore.

    ``client`` only needs the public collection/document/set/get surface used by the
    Google Cloud Firestore Python client. Injecting a fake client proves adapter
    semantics locally without creating false cloud evidence.
    """

    def __init__(self, client: Any, *, namespace: str = "poiex_goc_v0_1"):
        if not namespace or "/" in namespace:
            raise ValueError("namespace must be a non-empty collection prefix")
        self.client = client
        self.namespace = namespace

    @classmethod
    def from_default_credentials(
        cls,
        *,
        project: Optional[str] = None,
        database: Optional[str] = None,
        namespace: str = "poiex_goc_v0_1",
    ) -> "FirestoreStore":
        try:
            from google.cloud import firestore
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-firestore is not installed; install the optional google dependencies"
            ) from exc
        kwargs: dict[str, Any] = {}
        if project:
            kwargs["project"] = project
        if database:
            kwargs["database"] = database
        return cls(firestore.Client(**kwargs), namespace=namespace)

    def _collection(self, kind: str):
        return self.client.collection(f"{self.namespace}_{kind}")

    def _put(self, kind: str, doc_id: str, payload: dict[str, Any]) -> None:
        self._collection(kind).document(doc_id).set(payload)

    def _get(self, kind: str, doc_id: str) -> Optional[Mapping[str, Any]]:
        snapshot = self._collection(kind).document(doc_id).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict()
        return _require_mapping(data, object_type=kind)

    def put_agent(self, agent: AgentRecord) -> None:
        self._put("agents", agent.agent_id, _agent_to_doc(agent))

    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        data = self._get("agents", agent_id)
        return _agent_from_doc(data) if data is not None else None

    def put_lease(self, lease: AuthorityLease) -> None:
        self._put("leases", lease.lease_id, _lease_to_doc(lease))

    def get_lease(self, lease_id: str) -> Optional[AuthorityLease]:
        data = self._get("leases", lease_id)
        return _lease_from_doc(data) if data is not None else None

    def put_authority_provenance(self, record: AuthorityProvenanceRecord) -> None:
        self._put("authority_provenance", record.provenance_id, _provenance_to_doc(record))

    def get_authority_provenance(self, provenance_id: str) -> Optional[AuthorityProvenanceRecord]:
        data = self._get("authority_provenance", provenance_id)
        return _provenance_from_doc(data) if data is not None else None

    def put_evidence(self, evidence: EvidenceItem) -> None:
        self._put("evidence", evidence.evidence_id, _evidence_to_doc(evidence))

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceItem]:
        data = self._get("evidence", evidence_id)
        return _evidence_from_doc(data) if data is not None else None

    def put_target(self, target: MaterialTarget) -> None:
        self._put("targets", target.target_id, _target_to_doc(target))

    def get_target(self, target_id: str) -> Optional[MaterialTarget]:
        data = self._get("targets", target_id)
        return _target_from_doc(data) if data is not None else None

    def put_receipt(self, receipt: ExecutionReceipt) -> None:
        self._put("receipts", receipt.receipt_id, _receipt_to_doc(receipt))

    def get_receipt(self, receipt_id: str) -> Optional[ExecutionReceipt]:
        data = self._get("receipts", receipt_id)
        return _receipt_from_doc(data) if data is not None else None

    def execute_synthetic_action(self, run_id: str, payload: dict) -> str:
        result = {
            "run_id": run_id,
            "synthetic": True,
            "reversible": True,
            "payload": payload,
        }
        result_hash = canonical_hash(result)
        stored = {
            "schema_version": SCHEMA_VERSION,
            "object_type": "SyntheticActionResult",
            **result,
            "result_hash": result_hash,
        }
        self._put("synthetic_actions", run_id, stored)
        return result_hash

    def has_synthetic_action(self, run_id: str, expected_hash: str) -> bool:
        data = self._get("synthetic_actions", run_id)
        if data is None:
            return False
        result = {
            "run_id": data.get("run_id"),
            "synthetic": data.get("synthetic"),
            "reversible": data.get("reversible"),
            "payload": data.get("payload"),
        }
        computed = canonical_hash(result)
        return computed == expected_hash == data.get("result_hash")
