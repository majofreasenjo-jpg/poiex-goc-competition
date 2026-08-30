# POIEX / GOC — Governed Multi-Agent Enterprise Fleet

Clean-room submission for **Google All Things Agentic — Fortified Enterprise Fleet**.

> **Agents may reason and propose. Authority must be inherited, current, target-bound and replayable.**
> `EL AGENTE PIENSA; EL SISTEMA GOBIERNA.` — The agent thinks; the system governs.

## What this is

A **two-service** governed agent system, live on Google Cloud Run:

- **`poiex-agent-fleet`** — an advisory **Google ADK / Gemini 3.7 Flash** multi-agent
  fleet. A planning coordinator delegates to registry, authority, target and falsifier
  specialist stewards. **Every agent has `tools=[]`.** The fleet reasons and proposes;
  it cannot mint identity, authority, target hashes, gate decisions, receipts or execution.
- **`poiex-goc-control`** — a **deterministic governed control plane** (FastAPI). It owns
  the responsibility chain: identity → authority → registry truth → exact target → policy
  → execution admission → bounded synthetic action → receipt → replay → falsifier checks.
  State persists in **Firestore** (institutional memory, not session memory).

The LLM fleet is outside the material trusted computing base. A public/anonymous request
can reach the advisory fleet (demo surface) but **can never reach privileged execution**:
the control plane requires an authenticated service identity. `PUBLIC_ACCESS != EXECUTION_AUTHORITY`.

## Live deployment (attested)

| | |
|---|---|
| Project | `poiex-goc-fortified-2026` (region `us-east1`) |
| **Try it out** (public advisory demo) | `https://poiex-agent-fleet-unz7hjermq-ue.a.run.app` |
| Privileged control plane (authenticated only, not public) | `https://poiex-goc-control-unz7hjermq-ue.a.run.app` |
| Effective model | **gemini-3.7-flash** (verified in runtime `modelVersion`; Vertex `global`) |
| Fleet revision | `poiex-agent-fleet-00008-g4l` (public demo surface) |
| Control revision | `poiex-goc-control-00005-jdf` (authenticated only) |
| Release tag | `v0.11.0-rc2-submission-ready` |
| Local + staged tests | **73 / 73 GREEN** |
| Deployed falsifiers | **16 PASS / 0 FAIL / 6 not-evidenced-on-deployed-surface** |

## Fortified Enterprise Fleet — capability mapping

The track's recommended tech (Gemini Enterprise Agent Platform components) mapped honestly
to what this submission actually implements — see `DEVPOST_TECHNICAL_DESCRIPTION.md` for the
full table, including the one component (Model Armor / Agent Gateway as named managed
services) we do **not** use, disclosed rather than glossed over.

## Spin-up instructions (step-by-step)

**A. Run the deterministic suite locally (no cloud, ~1 minute)**
```bash
python -m venv .venv && . .venv/Scripts/activate   # or source .venv/bin/activate on Linux/Mac
pip install "google-adk[gcp]>=2.0.0,<3.0.0" "google-cloud-firestore>=2.20.0" \
            "fastapi>=0.115.0,<1.0.0" "uvicorn[standard]>=0.30.0,<1.0.0"
python -m unittest discover -s tests -v
# Expect: Ran 73 tests ... OK
```

**B. Deploy to Google Cloud (this exact codebase, reproducibly)**
```bash
gcloud auth login
bash scripts/google_cloudshell_bootstrap.sh --plan  --project <PROJECT_ID> --region us-east1
bash scripts/google_cloudshell_bootstrap.sh --apply --project <PROJECT_ID> --region us-east1
```
`--plan` performs no cloud mutation. `--apply` enables the required APIs, creates Firestore
and a least-privilege runtime service account, deploys both Cloud Run services from a
disposable tested worktree, runs the deployed eval, and captures evidence. The control
service is always deployed `--no-allow-unauthenticated`; only the advisory fleet is public.

**C. Exercise the live deployment**
```bash
FLEET_URL="https://poiex-agent-fleet-unz7hjermq-ue.a.run.app"
agents-cli run --url "$FLEET_URL" --mode adk --app-name app -v \
  "Analyze a synthetic maintenance outage work order for pump-A. Return a proposal only."
# response metadata includes "modelVersion": "gemini-3.7-flash"
```
Full attested command sequence (including authenticated control-plane calls and the
anonymous-403 zero-trust check): see `REPRODUCTION.md`.

## Key epistemic firewalls (never collapsed)

`DEPLOYED != VALIDATED` · `LOCAL_PASS != DEPLOYED_PASS` · `MODEL_CONFIGURED != MODEL_EFFECTIVE`
· `PUBLIC_ACCESS != EXECUTION_AUTHORITY` · `INFERENCE_COMPLETION != VALIDATION_SCORE`
· `EVALUATOR_FAILURE != AGENT_FAILURE` · `METHOD_TRANSFER != EVIDENCE_TRANSFER` · `NOT_RUN != PASS`

## Repository map

- `poiex_runtime/` — deterministic GOC control plane, gates, receipts, replay, hardening.
- `control_service/` — FastAPI Cloud Run service (`/v1/demo/run`, `/v1/hardening/run`).
- `app/`, `poiex_runtime/adk_planner.py` — advisory ADK/Gemini fleet.
- `tests/` — 73 deterministic + governance + hardening tests, plus the 13-case eval dataset.
- `scripts/` — Google preflight / deploy / evidence-capture / eval tooling.
- `docs/architecture.mmd` — architecture diagram · `docs/STACK_MANIFEST.md` — stack.
- `artifacts/r5_cloud_attestation/` — deployed evidence (effective model, IAM, falsifier matrix).
- `EVIDENCE_INDEX.md` · `REPRODUCTION.md` · `DEMO_SCRIPT.md` · `DEVPOST_TECHNICAL_DESCRIPTION.md`
- `PRE_EXISTING_WORK_DISCLOSURE.md` · `CONTEST_IP_FIREWALL_REPORT.md`

## Quick verify (local)

```bash
python -m unittest discover -s tests -v   # 73/73 green
```

See `REPRODUCTION.md` for the full Google Cloud plan/deploy/attest path.
