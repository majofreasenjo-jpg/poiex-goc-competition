"""Optional Google ADK multi-agent planning fleet.

All ADK agents are advisory-only. They may analyze and propose, but every agent has
``tools=[]`` and receives no executor, Firestore mutation surface, AuthorityLease
writer, or ControlPlane handle. Material action remains outside the LLM fleet.

G-EX-004 remains incomplete until this fleet is instantiated and exercised with the
current Google ADK package plus Gemini credentials in the clean-room project.
"""

from __future__ import annotations

import os

DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")


def _agent(*, Agent, Gemini, name: str, description: str, instruction: str):
    return Agent(
        name=name,
        description=description,
        model=Gemini(model=DEFAULT_GEMINI_MODEL),
        instruction=instruction,
        tools=[],
    )


def build_root_agent():
    try:
        from google.adk.agents import Agent
        from google.adk.models import Gemini
    except ImportError as exc:
        raise RuntimeError(
            "Google ADK is not installed. Install the project runtime dependencies first."
        ) from exc

    registry_steward = _agent(
        Agent=Agent,
        Gemini=Gemini,
        name="registry_steward",
        description="Analyzes agent registry claims, observed evidence, lineage, and missing evidence.",
        instruction=(
            "Analyze registry and evidence facts supplied in context. Distinguish DECLARED, "
            "OBSERVED, and INFERRED. Never promote a claim, issue authority, call a tool, or "
            "state that a material gate passed. Return advisory findings to the coordinator."
        ),
    )

    authority_steward = _agent(
        Agent=Agent,
        Gemini=Gemini,
        name="authority_steward",
        description="Analyzes lease scope, epoch, expiry, revocation, and authority conflicts.",
        instruction=(
            "Inspect supplied authority metadata for possible problems. You cannot issue, renew, "
            "revoke, or validate a lease and cannot execute actions. Return only advisory findings."
        ),
    )

    target_steward = _agent(
        Agent=Agent,
        Gemini=Gemini,
        name="target_steward",
        description="Analyzes target identity, action intent, version drift, and target substitution risk.",
        instruction=(
            "Analyze the proposed target and intent using only supplied context. Never mint a target "
            "hash or claim target binding passed. The deterministic control plane owns exact binding."
        ),
    )

    falsifier_steward = _agent(
        Agent=Agent,
        Gemini=Gemini,
        name="falsifier_steward",
        description="Searches for failure cases, missing predecessors, shortcut reasoning, and unsafe assumptions.",
        instruction=(
            "Try to falsify the proposed plan. Look for stale authority, unsupported capability, "
            "target mismatch, missing evidence, replay gaps, stale semantic bindings, write-only "
            "memory claims, stale pre-gate stage input, observer-only progress minting, newly admissible "
            "rival worlds, and hidden assumptions. Do not execute."
        ),
    )

    return Agent(
        name="poiex_planning_coordinator",
        description=(
            "Coordinates a bounded maintenance-outage planning fleet while leaving all material "
            "authorization and execution to the external deterministic GOC control plane."
        ),
        model=Gemini(model=DEFAULT_GEMINI_MODEL),
        instruction=(
            "You coordinate advisory specialists for a synthetic maintenance outage workflow. "
            "Delegate registry/evidence analysis, authority analysis, target/intent analysis, and "
            "falsification to the appropriate sub-agents when useful. If a required specialist "
            "delegation fails, times out, or returns no usable finding, do not impersonate that "
            "missing specialist and do not fill the gap from your own authority. Return "
            "ABSTAIN_SPECIALIST_FAILURE and name the missing specialist role. Produce a proposed "
            "synthetic action only when the required advisory inputs are present. You have no "
            "execution authority. Never claim that identity, authority, observed capability, target "
            "binding, execution, or replay has passed; those decisions belong to the external "
            "deterministic GOC control plane."
        ),
        sub_agents=[
            registry_steward,
            authority_steward,
            target_steward,
            falsifier_steward,
        ],
        tools=[],
    )
