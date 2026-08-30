"""Receiver-native governance hardening audits derived from cross-lane method deltas.

These auditors are clean-room GOC implementations. They do not import theorem,
scientific, empirical, or validation status from donor lanes.

Binding firewalls:
- METHOD_TRANSFER != EVIDENCE_TRANSFER
- CONTRACT_BINDING_CHANGE => LEGACY_DECISION_ARTIFACT_INVALID
- HISTORY_WRITE != CAUSAL_MEMORY_READBACK
- STALE_STAGE_INPUT != RECEIPTED_POST_STAGE_STATE
- OBSERVER_CONFIG_CHANGE != NEW_EVIDENCE_OR_PROGRESS
- NEW_ADMISSIBLE_RIVAL => GLOBAL_REGISTRY_REOPENED
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Mapping, Tuple

from .models import canonical_hash


@dataclass(frozen=True)
class GovernedBinding:
    authority_root: str
    scope: FrozenSet[str]
    target_hash: str
    policy_epoch: int
    binding_hash: str

    @classmethod
    def create(
        cls,
        *,
        authority_root: str,
        scope: set[str] | FrozenSet[str],
        target_hash: str,
        policy_epoch: int,
    ) -> "GovernedBinding":
        frozen_scope = frozenset(scope)
        binding_hash = canonical_hash(
            {
                "authority_root": authority_root,
                "scope": set(frozen_scope),
                "target_hash": target_hash,
                "policy_epoch": policy_epoch,
            }
        )
        return cls(
            authority_root=authority_root,
            scope=frozen_scope,
            target_hash=target_hash,
            policy_epoch=policy_epoch,
            binding_hash=binding_hash,
        )


@dataclass(frozen=True)
class BindingValidityReport:
    artifact_id: str
    status: str
    legacy_artifact_valid_for_final_disposition: bool
    reasons: Tuple[str, ...]
    current_binding_hash: str
    artifact_binding_hash: str


def audit_binding_validity(
    *,
    artifact_id: str,
    artifact_binding_hash: str,
    current_binding: GovernedBinding,
) -> BindingValidityReport:
    if artifact_binding_hash == current_binding.binding_hash:
        return BindingValidityReport(
            artifact_id=artifact_id,
            status="VALID_FOR_CURRENT_BINDING",
            legacy_artifact_valid_for_final_disposition=True,
            reasons=("BINDING_MATCH",),
            current_binding_hash=current_binding.binding_hash,
            artifact_binding_hash=artifact_binding_hash,
        )
    return BindingValidityReport(
        artifact_id=artifact_id,
        status="INVALIDATE_AND_RECOMPUTE",
        legacy_artifact_valid_for_final_disposition=False,
        reasons=(
            "SEMANTIC_BINDING_CHANGED",
            "LEGACY_ARTIFACT_INVALID_FOR_FINAL_DISPOSITION",
            "RECOMPUTATION_REQUIRED",
        ),
        current_binding_hash=current_binding.binding_hash,
        artifact_binding_hash=artifact_binding_hash,
    )


@dataclass(frozen=True)
class MemoryReadbackWitness:
    """Matched-current witness for a declared future decision/action kernel."""

    base_state: str
    memory_state: str
    future_kernel: Tuple[str, ...]


@dataclass(frozen=True)
class MemoryReadbackReport:
    status: str
    load_bearing_readback_observed: bool
    tested_base_states: Tuple[str, ...]
    split_base_states: Tuple[str, ...]
    claim_ceiling: str = "DECLARED_MATCHED_STATE_KERNEL_ONLY"


def audit_memory_readback(
    witnesses: Iterable[MemoryReadbackWitness],
) -> MemoryReadbackReport:
    rows = tuple(witnesses)
    if not rows:
        raise ValueError("at least one memory readback witness is required")

    grouped: dict[str, list[MemoryReadbackWitness]] = {}
    for row in rows:
        grouped.setdefault(row.base_state, []).append(row)

    split_states: list[str] = []
    for base_state, group in grouped.items():
        memory_values = {item.memory_state for item in group}
        kernels = {item.future_kernel for item in group}
        if len(memory_values) >= 2 and len(kernels) >= 2:
            split_states.append(base_state)

    if split_states:
        return MemoryReadbackReport(
            status="LOAD_BEARING_READBACK_OBSERVED",
            load_bearing_readback_observed=True,
            tested_base_states=tuple(sorted(grouped)),
            split_base_states=tuple(sorted(split_states)),
        )
    return MemoryReadbackReport(
        status="READBACK_NOT_DEMONSTRATED",
        load_bearing_readback_observed=False,
        tested_base_states=tuple(sorted(grouped)),
        split_base_states=(),
    )


@dataclass(frozen=True)
class StageFreshnessReport:
    status: str
    stage_input_admissible: bool
    expected_post_stage_hash: str
    consumed_input_hash: str
    verified_noninterference_certificate: bool
    reasons: Tuple[str, ...]


def audit_stage_input_freshness(
    *,
    expected_post_stage_hash: str,
    consumed_input_hash: str,
    verified_noninterference_certificate: bool = False,
) -> StageFreshnessReport:
    if consumed_input_hash == expected_post_stage_hash:
        return StageFreshnessReport(
            status="RECEIPTED_POST_STAGE_INPUT",
            stage_input_admissible=True,
            expected_post_stage_hash=expected_post_stage_hash,
            consumed_input_hash=consumed_input_hash,
            verified_noninterference_certificate=verified_noninterference_certificate,
            reasons=("STAGE_INPUT_MATCH",),
        )
    if verified_noninterference_certificate:
        return StageFreshnessReport(
            status="ADMIT_WITH_VERIFIED_NONINTERFERENCE",
            stage_input_admissible=True,
            expected_post_stage_hash=expected_post_stage_hash,
            consumed_input_hash=consumed_input_hash,
            verified_noninterference_certificate=True,
            reasons=("STAGE_INPUT_DIFFERS", "VERIFIED_NONINTERFERENCE_CERTIFICATE"),
        )
    return StageFreshnessReport(
        status="STALE_STAGE_INPUT_BLOCK",
        stage_input_admissible=False,
        expected_post_stage_hash=expected_post_stage_hash,
        consumed_input_hash=consumed_input_hash,
        verified_noninterference_certificate=False,
        reasons=(
            "STAGE_INPUT_DIFFERS_FROM_RECEIPTED_PREDECESSOR_OUTPUT",
            "NONINTERFERENCE_NOT_CERTIFIED",
        ),
    )


@dataclass(frozen=True)
class ObserverTransition:
    before_system_state_hash: str
    after_system_state_hash: str
    before_evidence_roots: FrozenSet[str]
    after_evidence_roots: FrozenSet[str]
    before_observer_config_hash: str
    after_observer_config_hash: str
    claimed_progress_units: int


@dataclass(frozen=True)
class ObserverNonmintReport:
    status: str
    admissible_progress_units: int
    system_state_changed: bool
    evidence_roots_changed: bool
    observer_config_changed: bool
    reasons: Tuple[str, ...]


def audit_observer_nonmint(transition: ObserverTransition) -> ObserverNonmintReport:
    if transition.claimed_progress_units < 0:
        raise ValueError("claimed_progress_units must be nonnegative")
    state_changed = (
        transition.before_system_state_hash != transition.after_system_state_hash
    )
    roots_changed = transition.before_evidence_roots != transition.after_evidence_roots
    config_changed = (
        transition.before_observer_config_hash != transition.after_observer_config_hash
    )

    if (
        transition.claimed_progress_units > 0
        and not state_changed
        and not roots_changed
        and config_changed
    ):
        return ObserverNonmintReport(
            status="NONMINT_VIOLATION",
            admissible_progress_units=0,
            system_state_changed=False,
            evidence_roots_changed=False,
            observer_config_changed=True,
            reasons=(
                "PURE_OBSERVER_REPARAMETERIZATION",
                "OBSERVER_CONFIG_CHANGE_CANNOT_MINT_PROGRESS",
            ),
        )

    return ObserverNonmintReport(
        status="PROGRESS_REQUIRES_DOWNSTREAM_ADJUDICATION",
        admissible_progress_units=transition.claimed_progress_units,
        system_state_changed=state_changed,
        evidence_roots_changed=roots_changed,
        observer_config_changed=config_changed,
        reasons=("NONMINT_GATE_NOT_VIOLATED",),
    )


@dataclass(frozen=True)
class RegistryCoverageCertificate:
    certificate_id: str
    registered_worlds: FrozenSet[str]
    local_pair_certificates: Mapping[str, FrozenSet[str]]


@dataclass(frozen=True)
class RegistryReopeningReport:
    global_status: str
    new_admissible_world: str
    locally_preserved_certificates: Tuple[str, ...]
    locally_invalidated_certificates: Tuple[str, ...]
    reasons: Tuple[str, ...]


def audit_open_world_reopening(
    certificate: RegistryCoverageCertificate,
    *,
    new_admissible_world: str,
) -> RegistryReopeningReport:
    if new_admissible_world in certificate.registered_worlds:
        return RegistryReopeningReport(
            global_status="NO_NEW_WORLD",
            new_admissible_world=new_admissible_world,
            locally_preserved_certificates=tuple(sorted(certificate.local_pair_certificates)),
            locally_invalidated_certificates=(),
            reasons=("WORLD_ALREADY_REGISTERED",),
        )

    # Global completeness is invalidated by the new admissible world. Pair-local
    # certificates remain locally valid because their declared world scope did not
    # change; they make no claim about the new world.
    preserved = tuple(sorted(certificate.local_pair_certificates))
    return RegistryReopeningReport(
        global_status="GLOBAL_REGISTRY_REOPENED",
        new_admissible_world=new_admissible_world,
        locally_preserved_certificates=preserved,
        locally_invalidated_certificates=(),
        reasons=(
            "NEW_ADMISSIBLE_RIVAL",
            "REGISTERED_COVERAGE_NOT_REALITY_CLOSURE",
            "LOCAL_CERTIFICATES_PRESERVED_WITHIN_DECLARED_SCOPE",
        ),
    )

_HARDENING_DEMO_CASES = {
    "binding_change",
    "write_only_memory",
    "stale_stage_input",
    "observer_reparameterization",
    "new_rival",
}


def run_hardening_demo_case(case: str) -> dict:
    """Run one frozen synthetic governance-hardening case for local/cloud replay.

    This surface performs no external mutation and owns no domain truth. It exists so
    the same receiver-native audit can be replayed after deployment.
    """

    if case not in _HARDENING_DEMO_CASES:
        raise ValueError(f"unsupported hardening case: {case}")

    base = {
        "schema": "GOC_CROSS_LANE_HARDENING_V0_10",
        "truth_ceiling": "SYNTHETIC_RECEIVER_NATIVE_ONLY",
        "case": case,
        "method_transfer_not_evidence_transfer": True,
    }

    if case == "binding_change":
        old = GovernedBinding.create(
            authority_root="plant-owner-root",
            scope={"issue_synthetic_work_order"},
            target_hash="pump-A-v3",
            policy_epoch=7,
        )
        current = GovernedBinding.create(
            authority_root="plant-owner-root",
            scope={"issue_synthetic_work_order", "inspect"},
            target_hash="pump-A-v3",
            policy_epoch=7,
        )
        report = audit_binding_validity(
            artifact_id="receipt-pre-binding-change",
            artifact_binding_hash=old.binding_hash,
            current_binding=current,
        )
        return {
            **base,
            "status": report.status,
            "artifact_valid": report.legacy_artifact_valid_for_final_disposition,
            "reasons": list(report.reasons),
        }

    if case == "write_only_memory":
        report = audit_memory_readback(
            [
                MemoryReadbackWitness(
                    base_state="same-current",
                    memory_state="history-A",
                    future_kernel=("ALLOW", "BLOCK"),
                ),
                MemoryReadbackWitness(
                    base_state="same-current",
                    memory_state="history-B",
                    future_kernel=("ALLOW", "BLOCK"),
                ),
            ]
        )
        return {
            **base,
            "status": report.status,
            "load_bearing_readback_observed": report.load_bearing_readback_observed,
            "claim_ceiling": report.claim_ceiling,
        }

    if case == "stale_stage_input":
        report = audit_stage_input_freshness(
            expected_post_stage_hash="post-gate-state",
            consumed_input_hash="original-plan-state",
            verified_noninterference_certificate=False,
        )
        return {
            **base,
            "status": report.status,
            "stage_input_admissible": report.stage_input_admissible,
            "reasons": list(report.reasons),
        }

    if case == "observer_reparameterization":
        report = audit_observer_nonmint(
            ObserverTransition(
                before_system_state_hash="system-state-A",
                after_system_state_hash="system-state-A",
                before_evidence_roots=frozenset({"root-1"}),
                after_evidence_roots=frozenset({"root-1"}),
                before_observer_config_hash="threshold-0.70",
                after_observer_config_hash="threshold-0.80",
                claimed_progress_units=1,
            )
        )
        return {
            **base,
            "status": report.status,
            "admissible_progress_units": report.admissible_progress_units,
            "reasons": list(report.reasons),
        }

    certificate = RegistryCoverageCertificate(
        certificate_id="registry-v1",
        registered_worlds=frozenset({"W-A", "W-B"}),
        local_pair_certificates={"pair-A-B": frozenset({"W-A", "W-B"})},
    )
    report = audit_open_world_reopening(certificate, new_admissible_world="W-X")
    return {
        **base,
        "status": report.global_status,
        "locally_preserved_certificates": list(report.locally_preserved_certificates),
        "locally_invalidated_certificates": list(report.locally_invalidated_certificates),
        "reasons": list(report.reasons),
    }
