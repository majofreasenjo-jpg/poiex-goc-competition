"""Authenticated Cloud Run API for bounded synthetic GOC demonstrations.

This service exposes no arbitrary executor, shell, file, or external-system mutation
surface. It only runs frozen synthetic scenarios through the same deterministic GOC
control plane used by local falsifiers.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from poiex_runtime.cloud_demo import run_demo_case
from poiex_runtime.governance_hardening import run_hardening_demo_case
from poiex_runtime.planner_contract import PlannerProposal
from poiex_runtime.runtime_factory import build_store_from_env


app = FastAPI(title="POIEX GOC Synthetic Control Plane", version="0.10.0")


class ProposalPayload(BaseModel):
    action_type: str = Field(max_length=96)
    target_id: str = Field(max_length=128)
    parameters: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(default="", max_length=1000)


class DemoRequest(BaseModel):
    case: Literal["allow", "revoked_authority", "target_substitution", "policy_epoch_stale"]
    scenario_id: str = Field(min_length=1, max_length=64)
    proposal: Optional[ProposalPayload] = None


class HardeningRequest(BaseModel):
    case: Literal[
        "binding_change",
        "write_only_memory",
        "stale_stage_input",
        "observer_reparameterization",
        "new_rival",
    ]


@app.get("/health")
@app.get("/healthz")
def health() -> dict:
    mode = os.getenv("POIEX_GOC_STORE", "memory")
    return {
        "status": "ok",
        "service": "poiex-goc-control",
        "version": "0.10.0",
        "store_mode": mode,
        "truth_ceiling": "SYNTHETIC_DEMO_ONLY",
        "agent_execution_authority": False,
    }


@app.post("/v1/demo/run")
def run_demo(request: DemoRequest) -> dict:
    try:
        store = build_store_from_env()
        planner_proposal = None
        if request.proposal is not None:
            planner_proposal = PlannerProposal(
                action_type=request.proposal.action_type,
                target_id=request.proposal.target_id,
                parameters=dict(request.proposal.parameters),
                rationale=request.proposal.rationale,
            )
        return run_demo_case(
            store,
            case=request.case,
            now=datetime.now(timezone.utc),
            scenario_id=request.scenario_id,
            proposal=planner_proposal,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/hardening/run")
def run_hardening(request: HardeningRequest) -> dict:
    try:
        return run_hardening_demo_case(request.case)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
