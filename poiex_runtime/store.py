from __future__ import annotations

from typing import Dict, Optional, Protocol

from .authority_provenance import AuthorityProvenanceRecord
from .models import (
    AgentRecord,
    AuthorityLease,
    EvidenceItem,
    ExecutionReceipt,
    MaterialTarget,
    canonical_hash,
)


class RuntimeStore(Protocol):
    """Storage contract consumed by the deterministic control plane.

    Implementations may be local or cloud-backed, but they must preserve the same
    semantic objects. Storage choice never changes authorization semantics.
    """

    def put_agent(self, agent: AgentRecord) -> None: ...
    def get_agent(self, agent_id: str) -> Optional[AgentRecord]: ...
    def put_lease(self, lease: AuthorityLease) -> None: ...
    def get_lease(self, lease_id: str) -> Optional[AuthorityLease]: ...
    def put_authority_provenance(self, record: AuthorityProvenanceRecord) -> None: ...
    def get_authority_provenance(self, provenance_id: str) -> Optional[AuthorityProvenanceRecord]: ...
    def put_evidence(self, evidence: EvidenceItem) -> None: ...
    def get_evidence(self, evidence_id: str) -> Optional[EvidenceItem]: ...
    def put_target(self, target: MaterialTarget) -> None: ...
    def get_target(self, target_id: str) -> Optional[MaterialTarget]: ...
    def put_receipt(self, receipt: ExecutionReceipt) -> None: ...
    def get_receipt(self, receipt_id: str) -> Optional[ExecutionReceipt]: ...
    def execute_synthetic_action(self, run_id: str, payload: dict) -> str: ...
    def has_synthetic_action(self, run_id: str, expected_hash: str) -> bool: ...


class MemoryStore:
    """Deterministic local store used only for clean-room falsifier tests.

    This is not Firestore and does not count as Google Cloud deployment evidence.
    """

    def __init__(self):
        self.agents: Dict[str, AgentRecord] = {}
        self.leases: Dict[str, AuthorityLease] = {}
        self.authority_provenance: Dict[str, AuthorityProvenanceRecord] = {}
        self.evidence: Dict[str, EvidenceItem] = {}
        self.targets: Dict[str, MaterialTarget] = {}
        self.receipts: Dict[str, ExecutionReceipt] = {}
        self.synthetic_actions: Dict[str, dict] = {}
        self.synthetic_mutation_count = 0

    def put_agent(self, agent: AgentRecord) -> None:
        self.agents[agent.agent_id] = agent

    def get_agent(self, agent_id: str) -> Optional[AgentRecord]:
        return self.agents.get(agent_id)

    def put_lease(self, lease: AuthorityLease) -> None:
        self.leases[lease.lease_id] = lease

    def get_lease(self, lease_id: str) -> Optional[AuthorityLease]:
        return self.leases.get(lease_id)

    def put_authority_provenance(self, record: AuthorityProvenanceRecord) -> None:
        self.authority_provenance[record.provenance_id] = record

    def get_authority_provenance(self, provenance_id: str) -> Optional[AuthorityProvenanceRecord]:
        return self.authority_provenance.get(provenance_id)

    def put_evidence(self, evidence: EvidenceItem) -> None:
        self.evidence[evidence.evidence_id] = evidence

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceItem]:
        return self.evidence.get(evidence_id)

    def put_target(self, target: MaterialTarget) -> None:
        self.targets[target.target_id] = target

    def get_target(self, target_id: str) -> Optional[MaterialTarget]:
        return self.targets.get(target_id)

    def put_receipt(self, receipt: ExecutionReceipt) -> None:
        self.receipts[receipt.receipt_id] = receipt

    def get_receipt(self, receipt_id: str) -> Optional[ExecutionReceipt]:
        return self.receipts.get(receipt_id)

    def execute_synthetic_action(self, run_id: str, payload: dict) -> str:
        result = {
            "run_id": run_id,
            "synthetic": True,
            "reversible": True,
            "payload": payload,
        }
        result_hash = canonical_hash(result)
        self.synthetic_actions[run_id] = result
        self.synthetic_mutation_count += 1
        return result_hash

    def has_synthetic_action(self, run_id: str, expected_hash: str) -> bool:
        result = self.synthetic_actions.get(run_id)
        if result is None:
            return False
        return canonical_hash(result) == expected_hash
