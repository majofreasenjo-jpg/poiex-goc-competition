#!/usr/bin/env python3
"""Emit machine-readable local evidence for V0.10 governance hardening."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from poiex_runtime.governance_hardening import run_hardening_demo_case


CASES = (
    "binding_change",
    "write_only_memory",
    "stale_stage_input",
    "observer_reparameterization",
    "new_rival",
)


def main() -> None:
    results = [run_hardening_demo_case(case) for case in CASES]
    payload = {
        "schema": "GOC_V0_10_CROSS_LANE_HARDENING_EVIDENCE",
        "truth_ceiling": "LOCAL_SYNTHETIC_RECEIVER_NATIVE_ONLY",
        "method_transfer_not_evidence_transfer": True,
        "case_count": len(results),
        "cases": results,
    }
    out = ROOT / "artifacts" / "goc_v0_10_cross_lane_hardening_evidence.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
