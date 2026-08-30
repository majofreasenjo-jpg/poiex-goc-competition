# POIEX/GOC — Devpost Technical Description

## Inspiration
Most enterprise agent demos prove an LLM can call a tool. The dangerous enterprise
failure is different: a *legitimate* agent acting with stale authority, on the wrong
target, or granting itself power. We built a fleet that is genuinely useful **while being
structurally unable to authorize itself**.

## What it does
POIEX/GOC is a governed multi-agent system for a synthetic maintenance-outage workflow.
A Google ADK / Gemini 3.7 Flash coordinator delegates to registry, authority, target and
falsifier specialist stewards. They analyze and propose — nothing more. A separate
deterministic control plane (the GOC) decides whether any material action is admissible,
runs it as a bounded synthetic executor, and records a replayable receipt. If a required
specialist is unavailable, the coordinator returns `ABSTAIN_SPECIALIST_FAILURE` instead of
impersonating it.

## How we built it
- **Two Cloud Run services.** `poiex-agent-fleet` (advisory ADK/Gemini, every agent
  `tools=[]`) and `poiex-goc-control` (FastAPI deterministic control plane).
- **Vertex AI / Gemini 3.7 Flash** via `GOOGLE_CLOUD_LOCATION=global` — empirically the
  only route serving Gemini >=3.5 in our project.
- **Firestore** as institutional memory: registry facts, authority leases + provenance,
  exact material targets, execution receipts, replay manifests. `ADK_SESSION_MEMORY != INSTITUTIONAL_MEMORY`.
- **Cloud Trace** for delegation spans; **Cloud Build** for source deploys.
- Deterministic responsibility chain: identity → authority → registry truth → exact target
  → policy → execution admission → synthetic action → receipt → replay → falsifier checks.

## The security boundary (what makes it "fortified")
`PUBLIC_ACCESS != EXECUTION_AUTHORITY`. The advisory fleet is publicly reachable as the
demo surface, but the privileged control plane requires an authenticated service identity.
We verified on the live deployment: anonymous requests to the control plane return **403**;
forged lease/authority/gate/target fields are inert; there is no direct executor endpoint;
a forged target is `REJECTED_BEFORE_INTENT`; a revoked lease `BLOCK`s. No public request can
mint a lease, authority, target certificate or privileged execution.

## Accomplishments / evidence
- **73/73** deterministic tests (local and clean-clone staged).
- **16 / 0 / 6** deployed falsifier matrix (PASS / FAIL / not-evidenced-on-surface).
- Effective model **gemini-3.7-flash** verified in live runtime metadata.
- **13/13** deployed inference; autorater ran (10/13 valid critiques, mean 0.836) with the
  3 evaluator parse-errors kept separate from agent behavior. `EVALUATOR_FAILURE != AGENT_FAILURE`.

## Fortified Enterprise Fleet — capability mapping (honest, not aspirational)

The track's recommended tech is the Gemini Enterprise Agent Platform (GEAP). We map each
recommended capability to what we actually built, and disclose the one gap rather than
imply coverage we don't have:

| GEAP capability | What we implement | Status |
|---|---|---|
| Agent Registry (discovery/versioning) | `registry_steward` + `poiex_runtime` agent-registry model (`DECLARED != OBSERVED`); self-implemented, not the managed GEAP product | Implemented (self-built) |
| Agent Runtime (long-running async execution) | Cloud Run services, autoscaling 0→10/20 instances | Implemented (Cloud Run, not GEAP Agent Runtime) |
| Memory Bank (persistent cross-session context) | Firestore-backed institutional memory: registry facts, authority leases + provenance, receipts, replay manifests | Implemented (self-built on Firestore) |
| Agent Identity (zero-trust access control) | Authenticated-service-identity requirement on the privileged control plane; anonymous → HTTP 403 (verified live) | Implemented (IAM-based, not GEAP Agent Identity) |
| Agent Gateway (unified routing/policy enforcement) | The GOC control plane itself is the single policy-enforcement point for all material actions | Implemented conceptually; not the named GEAP product |
| Model Armor (inline guardrails: prompt injection, tool poisoning, PII) | Strict Pydantic request schemas (bounded lengths, literal enums), forged/unknown fields structurally inert, no direct executor endpoint | **Partial** — schema-level guardrails only; we do **not** use the managed Model Armor service |
| Agent Observability (OpenTelemetry audit logs + reasoning traces) | `roles/cloudtrace.agent` bound; Cloud Trace delegation spans; every decision returns a receipt + replay | Implemented (Cloud Trace, receipts) |

We chose disclosure over inflation: `CORRECT_OUTPUT_VIA_FORBIDDEN_ROUTE = FAIL` applies to
claims about our own stack too.

## Challenges
Regional model availability (only Vertex `global` serves Gemini >=3.5 here); binding a
deployed revision honestly to a tested source; and refusing to let a green cloud demo become
a false "validated" claim: `DEPLOYED != VALIDATED`, `NOT_RUN != PASS`.

## What's next
Expose the six local-only falsifier fixtures on the deployed demo surface; add Cloud Trace
span assertions to the deployed matrix; harden the autorater critique-format handling.

## Built with
Google ADK · Gemini 3.7 Flash (Vertex AI) · Cloud Run · Firestore · Cloud Trace · Cloud Build
· FastAPI · Uvicorn · Pydantic · google-agents-cli.
