from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from poiex_runtime.action_capacity import ActionCapacitySeries, audit_action_capacity
from poiex_runtime.certified_repair import RepairCandidate, RepairObligation, certify_repair_branch
from poiex_runtime.future_state_sufficiency import UnderlyingOperationalState, audit_future_state_sufficiency


def fraction_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def main() -> None:
    repair = certify_repair_branch(
        branch_id="demo-repair-branch",
        obligations=[RepairObligation("identity"), RepairObligation("authority"), RepairObligation("target")],
        candidates=[
            RepairCandidate("repair-a", ("identity", "authority"), Fraction(1, 1)),
            RepairCandidate("repair-b", ("authority", "target"), Fraction(1, 1)),
            RepairCandidate("repair-c", ("identity", "target"), Fraction(1, 1)),
        ],
        obligation_weights={
            "identity": Fraction(1, 2),
            "authority": Fraction(1, 2),
            "target": Fraction(1, 2),
        },
        remaining_budget=Fraction(1, 1),
        heuristic_score=0.01,
    )

    state_audit = audit_future_state_sufficiency(
        [
            UnderlyingOperationalState(
                state_id="lease-current",
                coarse_state="work-order-ready",
                present_output="READY",
                continuation_kernel={"continue": "ALLOW", "revoke": "BLOCK"},
                residual_coordinates={"authority_epoch": "7"},
            ),
            UnderlyingOperationalState(
                state_id="lease-stale",
                coarse_state="work-order-ready",
                present_output="READY",
                continuation_kernel={"continue": "BLOCK", "revoke": "BLOCK"},
                residual_coordinates={"authority_epoch": "6"},
            ),
        ]
    )

    capacity = audit_action_capacity(
        [
            ActionCapacitySeries("synthetic-control-a", (8, 16, 32, 64), (7, 15, 31, 63)),
            ActionCapacitySeries("synthetic-control-b", (8, 16, 32, 64), (2, 2, 2, 2)),
            ActionCapacitySeries("synthetic-control-c", (8, 16, 32, 64), (2, 2, 2, 2)),
            ActionCapacitySeries("synthetic-control-d", (8, 16, 32, 64), (1, 1, 1, 1)),
        ]
    )

    payload = {
        "schema": "GOC_V0_8_CERTIFIED_STATE_EVIDENCE",
        "environment": "LOCAL_ONLY",
        "source_evidence_transfer": False,
        "repair": {
            "verdict": repair.verdict,
            "lower_bound": fraction_text(repair.lower_bound),
            "remaining_budget": fraction_text(repair.remaining_budget),
            "replayable": repair.replayable,
            "candidate_loads": [
                {
                    "candidate_id": item.candidate_id,
                    "load": fraction_text(item.load),
                    "capacity": fraction_text(item.capacity),
                    "valid": item.valid,
                }
                for item in repair.candidate_loads
            ],
            "negative_seals": list(repair.negative_seals),
        },
        "future_state": {
            "unsafe_class_count": state_audit.unsafe_class_count,
            "safe_class_count": state_audit.safe_class_count,
            "global_future_exactness_claimed": state_audit.global_future_exactness_claimed,
            "class_status": state_audit.classes[0].status,
            "minimal_residual_coordinates": list(state_audit.classes[0].minimal_residual_coordinates),
            "negative_seal": state_audit.negative_seal,
            "additional_negative_seals": list(state_audit.additional_negative_seals),
        },
        "action_capacity": {
            "distinct_action_count": capacity.distinct_action_count,
            "growing_direction_count_in_tested_envelope": capacity.growing_direction_count_in_tested_envelope,
            "growing_actions": list(capacity.growing_actions),
            "unbounded_capacity_claimed": capacity.unbounded_capacity_claimed,
            "negative_seal": capacity.negative_seal,
            "additional_negative_seals": list(capacity.additional_negative_seals),
        },
        "truth_ceiling": [
            "LOCAL_PASS != DEPLOYED_PASS",
            "SOURCE_METHOD_REIMPLEMENTED != SOURCE_EVIDENCE_TRANSFERRED",
            "CERTIFIED_LOWER_BOUND != EXACT_MINIMUM_REPAIR_COST",
            "SAFE_FOR_DECLARED_KERNEL != GLOBAL_FUTURE_EXACTNESS",
            "FINITE_ENVELOPE_GROWTH != UNBOUNDED_CAPACITY",
        ],
    }

    output = Path("artifacts/goc_v0_8_certified_state_evidence.json")
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
