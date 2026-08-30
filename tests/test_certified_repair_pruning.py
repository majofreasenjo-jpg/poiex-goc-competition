import unittest
from fractions import Fraction

from poiex_runtime.certified_repair import (
    RepairCandidate,
    RepairObligation,
    certify_repair_branch,
)


class CertifiedRepairPruningTests(unittest.TestCase):
    def test_exact_dual_certificate_prunes_only_when_bound_exceeds_budget(self):
        obligations = [
            RepairObligation("o1"),
            RepairObligation("o2"),
            RepairObligation("o3"),
        ]
        candidates = [
            RepairCandidate("a", ("o1", "o2"), Fraction(1, 1)),
            RepairCandidate("b", ("o2", "o3"), Fraction(1, 1)),
            RepairCandidate("c", ("o1", "o3"), Fraction(1, 1)),
        ]
        result = certify_repair_branch(
            branch_id="branch-tight",
            obligations=obligations,
            candidates=candidates,
            obligation_weights={"o1": Fraction(1, 2), "o2": Fraction(1, 2), "o3": Fraction(1, 2)},
            remaining_budget=Fraction(1, 1),
        )
        self.assertEqual("CERTIFIED_PRUNE", result.verdict)
        self.assertEqual(Fraction(3, 2), result.lower_bound)
        self.assertTrue(result.replayable)

    def test_feasible_dual_below_budget_cannot_prune_even_with_bad_heuristic(self):
        obligations = [RepairObligation("o1"), RepairObligation("o2")]
        candidates = [
            RepairCandidate("a", ("o1",), Fraction(1, 1)),
            RepairCandidate("b", ("o2",), Fraction(1, 1)),
        ]
        result = certify_repair_branch(
            branch_id="branch-keep",
            obligations=obligations,
            candidates=candidates,
            obligation_weights={"o1": Fraction(1, 1), "o2": Fraction(1, 1)},
            remaining_budget=Fraction(2, 1),
            heuristic_score=-999.0,
        )
        self.assertEqual("KEEP_SEARCH", result.verdict)
        self.assertIn("HEURISTIC_BAD_SCORE != CERTIFIED_INFEASIBLE_BRANCH", result.negative_seals)

    def test_invalid_dual_load_never_authorizes_pruning(self):
        obligations = [RepairObligation("o1"), RepairObligation("o2")]
        candidates = [RepairCandidate("a", ("o1", "o2"), Fraction(1, 1))]
        result = certify_repair_branch(
            branch_id="branch-invalid",
            obligations=obligations,
            candidates=candidates,
            obligation_weights={"o1": Fraction(1, 1), "o2": Fraction(1, 1)},
            remaining_budget=Fraction(1, 1),
        )
        self.assertEqual("INVALID_CERTIFICATE", result.verdict)
        self.assertFalse(result.replayable)

    def test_uncoverable_necessary_obligation_is_exact_infeasibility(self):
        obligations = [RepairObligation("o1"), RepairObligation("o2")]
        candidates = [RepairCandidate("a", ("o1",), Fraction(1, 1))]
        result = certify_repair_branch(
            branch_id="branch-uncoverable",
            obligations=obligations,
            candidates=candidates,
            obligation_weights={"o1": Fraction(0, 1), "o2": Fraction(0, 1)},
            remaining_budget=Fraction(100, 1),
        )
        self.assertEqual("CERTIFIED_PRUNE", result.verdict)
        self.assertIn("NO_ADMISSIBLE_REPAIR_FOR_NECESSARY_OBLIGATION:o2", result.reasons)


if __name__ == "__main__":
    unittest.main()
