"""Receiver-native authority provenance verification for GOC.

This module is a clean-room GOC implementation inspired by cross-lane work on
update-authority provenance. It does not import source-lane evidence or maturity.

METHOD_TRANSFER != EVIDENCE_TRANSFER.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, Set


@dataclass(frozen=True)
class AuthorityProvenanceRecord:
    """One delegation edge in the effective authority lineage.

    ``subject_id`` is the actor receiving authority from ``issuer_id``. A child
    record can reference the provenance record that gave its issuer the authority
    being delegated. The chain ends at a trusted root issuer.
    """

    provenance_id: str
    subject_id: str
    issuer_id: str
    scope: Set[str]
    epoch: int
    issued_at: datetime
    revoked_at: Optional[datetime]
    parent_provenance_id: Optional[str]


class ProvenanceReadableStore(Protocol):
    def get_authority_provenance(
        self, provenance_id: str
    ) -> Optional[AuthorityProvenanceRecord]: ...


@dataclass(frozen=True)
class AuthorityProvenanceResult:
    accepted: bool
    reasons: tuple[str, ...]
    lineage_ids: tuple[str, ...]


def verify_authority_provenance(
    *,
    store: ProvenanceReadableStore,
    lease,
    now: datetime,
    trusted_root_issuers: Set[str],
) -> AuthorityProvenanceResult:
    """Verify that a lease is backed by an unbroken, non-revoked delegation chain."""

    provenance_id = getattr(lease, "provenance_id", None)
    if not provenance_id:
        return AuthorityProvenanceResult(
            accepted=False,
            reasons=("AUTHORITY_PROVENANCE_MISSING",),
            lineage_ids=(),
        )

    reasons: list[str] = []
    lineage: list[str] = []
    visited: set[str] = set()
    current_id: Optional[str] = provenance_id
    child = None
    first = True

    while current_id is not None:
        if current_id in visited:
            reasons.append("AUTHORITY_PROVENANCE_CYCLE")
            break
        visited.add(current_id)
        lineage.append(current_id)

        record = store.get_authority_provenance(current_id)
        if record is None:
            reasons.append("AUTHORITY_PROVENANCE_RECORD_MISSING")
            break

        if record.issued_at > now:
            reasons.append("AUTHORITY_PROVENANCE_NOT_YET_VALID")
        if record.revoked_at is not None and record.revoked_at <= now:
            reasons.append("AUTHORITY_PROVENANCE_REVOKED")

        if first:
            if record.subject_id != lease.agent_id:
                reasons.append("AUTHORITY_PROVENANCE_SUBJECT_MISMATCH")
            if record.issuer_id != lease.issuer:
                reasons.append("AUTHORITY_PROVENANCE_ISSUER_MISMATCH")
            if record.epoch != lease.epoch:
                reasons.append("AUTHORITY_PROVENANCE_EPOCH_MISMATCH")
            if not set(lease.scope).issubset(record.scope):
                reasons.append("AUTHORITY_PROVENANCE_SCOPE_MISMATCH")
            first = False

        if child is not None:
            if child.issuer_id != record.subject_id:
                reasons.append("AUTHORITY_PROVENANCE_DELEGATION_GAP")
            if not child.scope.issubset(record.scope):
                reasons.append("AUTHORITY_PROVENANCE_SCOPE_ESCALATION")

        child = record

        if record.parent_provenance_id is None:
            if record.issuer_id not in trusted_root_issuers:
                reasons.append("AUTHORITY_PROVENANCE_UNTRUSTED_ROOT")
            break
        current_id = record.parent_provenance_id

    unique_reasons = tuple(dict.fromkeys(reasons))
    return AuthorityProvenanceResult(
        accepted=not unique_reasons,
        reasons=unique_reasons,
        lineage_ids=tuple(lineage),
    )
