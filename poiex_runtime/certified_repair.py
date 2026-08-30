"""Receiver-native certified repair and branch pruning for GOC.

A branch is pruned only by exact, replayable evidence: either a necessary
obligation has no admissible repair candidate, or a verified feasible dual
lower bound exceeds the remaining repair budget. Heuristic scores never prune.

The construction is a clean-room receiver-native adaptation of a generic
covering-dual method. No source-lane theorem status or instance evidence is
inherited.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Mapping, Optional


@dataclass(frozen=True)
class RepairObligation:
    obligation_id: str
    necessary: bool = True


@dataclass(frozen=True)
class RepairCandidate:
    candidate_id: str
    covers: tuple[str, ...]
    cost: Fraction = Fraction(1, 1)

    def __post_init__(self) -> None:
        if self.cost <= 0:
            raise ValueError("repair candidate cost must be positive")


@dataclass(frozen=True)
class CandidateDualLoad:
    candidate_id: str
    load: Fraction
    capacity: Fraction
    valid: bool


@dataclass(frozen=True)
class CertifiedRepairDecision:
    branch_id: str
    verdict: str
    lower_bound: Fraction
    remaining_budget: Fraction
    candidate_loads: tuple[CandidateDualLoad, ...]
    uncovered_necessary_obligations: tuple[str, ...]
    reasons: tuple[str, ...]
    negative_seals: tuple[str, ...]
    replayable: bool
    heuristic_score: Optional[float]


def _normalize_weights(
    obligations: Mapping[str, RepairObligation],
    obligation_weights: Mapping[str, Fraction],
) -> tuple[dict[str, Fraction], list[str]]:
    normalized: dict[str, Fraction] = {}
    errors: list[str] = []

    for obligation_id, raw_weight in obligation_weights.items():
        if obligation_id not in obligations:
            errors.append(f"UNKNOWN_OBLIGATION_WEIGHT:{obligation_id}")
            continue
        weight = Fraction(raw_weight)
        if weight < 0:
            errors.append(f"NEGATIVE_OBLIGATION_WEIGHT:{obligation_id}")
            continue
        if weight > 0 and not obligations[obligation_id].necessary:
            errors.append(f"NONNECESSARY_OBLIGATION_WEIGHTED:{obligation_id}")
            continue
        normalized[obligation_id] = weight

    for obligation_id in obligations:
        normalized.setdefault(obligation_id, Fraction(0, 1))

    return normalized, errors


def certify_repair_branch(
    *,
    branch_id: str,
    obligations: Iterable[RepairObligation],
    candidates: Iterable[RepairCandidate],
    obligation_weights: Mapping[str, Fraction],
    remaining_budget: Fraction,
    heuristic_score: Optional[float] = None,
) -> CertifiedRepairDecision:
    """Verify an exact covering-dual certificate and adjudicate pruning.

    For every candidate e, feasibility requires
        sum(weight[o] for o covered by e) <= cost[e].
    Any completion covering all necessary obligations must therefore cost at
    least sum(weight[o]). A branch can be certified infeasible when this lower
    bound exceeds its remaining budget.
    """

    budget = Fraction(remaining_budget)
    if budget < 0:
        raise ValueError("remaining budget cannot be negative")

    obligation_list = tuple(obligations)
    obligation_map = {item.obligation_id: item for item in obligation_list}
    if len(obligation_map) != len(obligation_list):
        raise ValueError("duplicate obligation_id")

    candidate_list = tuple(candidates)
    candidate_ids = {candidate.candidate_id for candidate in candidate_list}
    if len(candidate_ids) != len(candidate_list):
        raise ValueError("duplicate candidate_id")

    weights, errors = _normalize_weights(obligation_map, obligation_weights)

    unknown_cover_ids = sorted(
        {
            obligation_id
            for candidate in candidate_list
            for obligation_id in candidate.covers
            if obligation_id not in obligation_map
        }
    )
    errors.extend(f"CANDIDATE_COVERS_UNKNOWN_OBLIGATION:{item}" for item in unknown_cover_ids)

    necessary_ids = {
        obligation.obligation_id
        for obligation in obligation_list
        if obligation.necessary
    }
    covered_ids = {
        obligation_id
        for candidate in candidate_list
        for obligation_id in candidate.covers
        if obligation_id in necessary_ids
    }
    uncovered = tuple(sorted(necessary_ids - covered_ids))

    loads: list[CandidateDualLoad] = []
    for candidate in sorted(candidate_list, key=lambda item: item.candidate_id):
        load = sum(
            (weights.get(obligation_id, Fraction(0, 1)) for obligation_id in candidate.covers),
            Fraction(0, 1),
        )
        valid = load <= candidate.cost
        if not valid:
            errors.append(f"DUAL_LOAD_EXCEEDS_CANDIDATE_COST:{candidate.candidate_id}")
        loads.append(
            CandidateDualLoad(
                candidate_id=candidate.candidate_id,
                load=load,
                capacity=candidate.cost,
                valid=valid,
            )
        )

    lower_bound = sum(
        (weights[item] for item in sorted(necessary_ids)),
        Fraction(0, 1),
    )

    negative_seals = (
        "HEURISTIC_BAD_SCORE != CERTIFIED_INFEASIBLE_BRANCH",
        "LOCAL_REPAIR_CHEAPNESS != GLOBAL_REPAIR_FEASIBILITY",
        "DUAL_LOWER_BOUND != EXACT_MINIMUM_REPAIR_COST",
    )

    if errors:
        return CertifiedRepairDecision(
            branch_id=branch_id,
            verdict="INVALID_CERTIFICATE",
            lower_bound=lower_bound,
            remaining_budget=budget,
            candidate_loads=tuple(loads),
            uncovered_necessary_obligations=uncovered,
            reasons=tuple(sorted(set(errors))),
            negative_seals=negative_seals,
            replayable=False,
            heuristic_score=heuristic_score,
        )

    if uncovered:
        return CertifiedRepairDecision(
            branch_id=branch_id,
            verdict="CERTIFIED_PRUNE",
            lower_bound=lower_bound,
            remaining_budget=budget,
            candidate_loads=tuple(loads),
            uncovered_necessary_obligations=uncovered,
            reasons=tuple(
                f"NO_ADMISSIBLE_REPAIR_FOR_NECESSARY_OBLIGATION:{item}"
                for item in uncovered
            ),
            negative_seals=negative_seals,
            replayable=True,
            heuristic_score=heuristic_score,
        )

    if lower_bound > budget:
        verdict = "CERTIFIED_PRUNE"
        reasons = ("VERIFIED_DUAL_LOWER_BOUND_EXCEEDS_REMAINING_BUDGET",)
    else:
        verdict = "KEEP_SEARCH"
        reasons = ("NO_CERTIFIED_INFEASIBILITY",)

    return CertifiedRepairDecision(
        branch_id=branch_id,
        verdict=verdict,
        lower_bound=lower_bound,
        remaining_budget=budget,
        candidate_loads=tuple(loads),
        uncovered_necessary_obligations=uncovered,
        reasons=reasons,
        negative_seals=negative_seals,
        replayable=True,
        heuristic_score=heuristic_score,
    )
