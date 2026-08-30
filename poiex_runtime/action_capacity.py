"""Receiver-native multi-action capacity profile audit.

Distinct action/effect classes do not imply multiple growing control directions.
Growth is reported only inside an explicitly tested finite scale envelope; no
finite series is promoted to an unbounded-capacity claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ActionCapacitySeries:
    action_id: str
    scales: tuple[int, ...]
    image_ranks: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.scales or len(self.scales) != len(self.image_ranks):
            raise ValueError("scales and image_ranks must be nonempty and equal length")
        if any(scale <= 0 for scale in self.scales):
            raise ValueError("scales must be positive")
        if any(rank < 0 for rank in self.image_ranks):
            raise ValueError("image ranks cannot be negative")
        if any(a >= b for a, b in zip(self.scales, self.scales[1:])):
            raise ValueError("scales must be strictly increasing")


@dataclass(frozen=True)
class ActionCapacityAudit:
    distinct_action_count: int
    growing_direction_count_in_tested_envelope: int
    growing_actions: tuple[str, ...]
    bounded_or_flat_actions: tuple[str, ...]
    nonmonotone_actions: tuple[str, ...]
    unbounded_capacity_claimed: bool
    negative_seal: str
    additional_negative_seals: tuple[str, ...]


def audit_action_capacity(series: Iterable[ActionCapacitySeries]) -> ActionCapacityAudit:
    items = tuple(series)
    ids = [item.action_id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate action_id")

    growing: list[str] = []
    flat: list[str] = []
    nonmonotone: list[str] = []

    for item in sorted(items, key=lambda entry: entry.action_id):
        monotone = all(a <= b for a, b in zip(item.image_ranks, item.image_ranks[1:]))
        if not monotone:
            nonmonotone.append(item.action_id)
            continue
        if item.image_ranks[-1] > item.image_ranks[0]:
            growing.append(item.action_id)
        else:
            flat.append(item.action_id)

    return ActionCapacityAudit(
        distinct_action_count=len(items),
        growing_direction_count_in_tested_envelope=len(growing),
        growing_actions=tuple(growing),
        bounded_or_flat_actions=tuple(flat),
        nonmonotone_actions=tuple(nonmonotone),
        unbounded_capacity_claimed=False,
        negative_seal="DISTINCT_ACTION_CLASSES != MULTIPLE_GROWING_CONTROL_DIRECTIONS",
        additional_negative_seals=(
            "FINITE_ENVELOPE_GROWTH != UNBOUNDED_CAPACITY",
            "LARGE_STATE_SPACE != LARGE_EFFECTIVE_CONTROL_CAPACITY",
        ),
    )
