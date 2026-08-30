"""Emit machine-readable local evidence for receiver-native cross-lane delta gates."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from poiex_runtime.action_independence import ActionContractSignature, audit_action_independence
from poiex_runtime.fault_harness import run_receiver_native_fault_matrix


def main() -> None:
    fault_report = run_receiver_native_fault_matrix()
    independence = audit_action_independence(
        [
            ActionContractSignature(
                action_id="registry_steward",
                authority_scope="advisory_only",
                target_type="agent_record",
                required_evidence=("registry",),
                material_effect="registry_findings",
            ),
            ActionContractSignature(
                action_id="authority_steward",
                authority_scope="advisory_only",
                target_type="authority_lease",
                required_evidence=("authority",),
                material_effect="authority_findings",
            ),
            ActionContractSignature(
                action_id="target_steward",
                authority_scope="advisory_only",
                target_type="material_target",
                required_evidence=("target",),
                material_effect="target_findings",
            ),
            ActionContractSignature(
                action_id="falsifier_steward",
                authority_scope="advisory_only",
                target_type="candidate_plan",
                required_evidence=("registry", "authority", "target"),
                material_effect="falsifier_findings",
            ),
        ]
    )
    payload = {
        "truth_ceiling": {
            "execution_environment": fault_report.execution_environment,
            "external_validation": fault_report.external_validation,
            "cloud_deployment_evidence": fault_report.cloud_deployment_evidence,
            "method_transfer_not_evidence_transfer": True,
        },
        "fault_matrix": {
            "all_safe": fault_report.all_safe,
            "case_count": len(fault_report.cases),
            "cases": [asdict(case) for case in fault_report.cases],
        },
        "action_independence": asdict(independence),
    }
    out = Path("artifacts/goc_v0_7_cross_lane_delta_evidence.json")
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
