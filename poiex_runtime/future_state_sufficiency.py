"""Receiver-native future-state sufficiency and hidden-alias audit.

Present-state equality is not enough to authorize state compression. A coarse
class is safe only for a declared continuation kernel when every underlying
admissible state in that class has the same labelled future/action kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping


@dataclass(frozen=True)
class UnderlyingOperationalState:
    state_id: str
    coarse_state: str
    present_output: str
    continuation_kernel: Mapping[str, str]
    residual_coordinates: Mapping[str, str] = field(default_factory=dict)

    def kernel_key(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((str(k), str(v)) for k, v in self.continuation_kernel.items()))


@dataclass(frozen=True)
class CoarseStateAudit:
    coarse_state: str
    member_state_ids: tuple[str, ...]
    present_outputs: tuple[str, ...]
    distinct_kernel_count: int
    status: str
    rival_kernel_groups: tuple[tuple[str, ...], ...]
    minimal_residual_coordinates: tuple[str, ...]


@dataclass(frozen=True)
class FutureStateSufficiencyResult:
    classes: tuple[CoarseStateAudit, ...]
    unsafe_class_count: int
    safe_class_count: int
    global_future_exactness_claimed: bool
    negative_seal: str
    additional_negative_seals: tuple[str, ...]


def _minimal_residual_coordinates(states: tuple[UnderlyingOperationalState, ...]) -> tuple[str, ...]:
    if len({state.kernel_key() for state in states}) <= 1:
        return ()

    keys = sorted({key for state in states for key in state.residual_coordinates})
    sufficient: list[str] = []
    for key in keys:
        groups: dict[str, set[tuple[tuple[str, str], ...]]] = {}
        missing = False
        for state in states:
            if key not in state.residual_coordinates:
                missing = True
                break
            groups.setdefault(str(state.residual_coordinates[key]), set()).add(state.kernel_key())
        if not missing and all(len(kernels) == 1 for kernels in groups.values()):
            sufficient.append(key)
    return tuple(sufficient)


def audit_future_state_sufficiency(
    states: Iterable[UnderlyingOperationalState],
) -> FutureStateSufficiencyResult:
    state_list = tuple(states)
    ids = [state.state_id for state in state_list]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate state_id")

    grouped: dict[str, list[UnderlyingOperationalState]] = {}
    for state in state_list:
        grouped.setdefault(state.coarse_state, []).append(state)

    audits: list[CoarseStateAudit] = []
    for coarse_state, members_raw in sorted(grouped.items()):
        members = tuple(sorted(members_raw, key=lambda item: item.state_id))
        kernels: dict[tuple[tuple[str, str], ...], list[str]] = {}
        for state in members:
            kernels.setdefault(state.kernel_key(), []).append(state.state_id)

        rival_groups = tuple(
            tuple(sorted(group))
            for _, group in sorted(kernels.items(), key=lambda item: repr(item[0]))
        )
        status = (
            "SAFE_FOR_DECLARED_KERNEL"
            if len(kernels) <= 1
            else "STATE_ALIAS_UNSAFE"
        )
        audits.append(
            CoarseStateAudit(
                coarse_state=coarse_state,
                member_state_ids=tuple(state.state_id for state in members),
                present_outputs=tuple(sorted({state.present_output for state in members})),
                distinct_kernel_count=len(kernels),
                status=status,
                rival_kernel_groups=rival_groups,
                minimal_residual_coordinates=_minimal_residual_coordinates(members),
            )
        )

    unsafe = sum(audit.status == "STATE_ALIAS_UNSAFE" for audit in audits)
    safe = len(audits) - unsafe
    return FutureStateSufficiencyResult(
        classes=tuple(audits),
        unsafe_class_count=unsafe,
        safe_class_count=safe,
        global_future_exactness_claimed=False,
        negative_seal="PRESENT_EQUIVALENCE != FUTURE_ACTION_KERNEL_EQUIVALENCE",
        additional_negative_seals=(
            "FINITE_NO_COLLISION != FUTURE_EXACTNESS",
            "SAME_COMMON_FACTOR != SAME_FUTURE_KERNEL",
            "CENSORED_H != NEVER_EVENT",
            "SAFE_FOR_DECLARED_KERNEL != GLOBAL_FUTURE_EXACTNESS",
        ),
    )
