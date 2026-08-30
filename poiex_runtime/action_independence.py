"""Receiver-native action-independence audit for GOC.

Agent/action labels are not counted as independent capabilities merely because they
are distinct names. Independence is bounded by distinct observable contracts/effects.
This is a receiver-native safety primitive, not a transfer of source-lane proof status.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ActionContractSignature:
    action_id: str
    authority_scope: str
    target_type: str
    required_evidence: tuple[str, ...]
    material_effect: str

    def effect_key(self) -> tuple[str, str, tuple[str, ...], str]:
        return (
            self.authority_scope,
            self.target_type,
            tuple(sorted(self.required_evidence)),
            self.material_effect,
        )


@dataclass(frozen=True)
class ActionIndependenceResult:
    raw_action_count: int
    independent_effect_class_count: int
    effect_classes: tuple[tuple[str, ...], ...]
    negative_seal: str


def audit_action_independence(
    actions: Iterable[ActionContractSignature],
) -> ActionIndependenceResult:
    grouped: dict[tuple[str, str, tuple[str, ...], str], list[str]] = {}
    raw = 0
    for action in actions:
        raw += 1
        grouped.setdefault(action.effect_key(), []).append(action.action_id)

    classes = tuple(
        tuple(sorted(ids))
        for _, ids in sorted(grouped.items(), key=lambda item: repr(item[0]))
    )
    return ActionIndependenceResult(
        raw_action_count=raw,
        independent_effect_class_count=len(classes),
        effect_classes=classes,
        negative_seal="ACTION_COUNT != INDEPENDENT_EFFECT_CLASS_COUNT",
    )
