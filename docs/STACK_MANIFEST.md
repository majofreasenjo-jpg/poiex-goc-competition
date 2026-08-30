# Stack Manifest — GOC V0.9

Status: `LOCAL_DEPLOYMENT_CLOSURE_PREPARED / NOT_DEPLOYED`

## Required runtime stack

- Python: 3.11+
- Google agent framework: Google ADK `google-adk[gcp]>=2.0.0,<3.0.0`
- Model: Gemini 3.7 Flash default, configurable with `GEMINI_MODEL`
- Google Cloud deployment: Cloud Run
- Durable institutional state: Firestore
- Deterministic HTTP service: FastAPI + Uvicorn

## Service A — ADK advisory fleet

- deployment name target: `poiex-agent-fleet`
- coordinator: `poiex_planning_coordinator`
- specialists: registry / authority / target / falsifier
- material tools exposed to agents: 0
- authority: none
- output: advisory proposal only

## Service B — deterministic GOC control

- deployment name target: `poiex-goc-control`
- runtime state: `RuntimeStore`
- local adapter: `MemoryStore`
- cloud adapter: `FirestoreStore`
- Cloud Run fail-closed rule: `K_SERVICE => POIEX_GOC_STORE=firestore`
- only material mutation: frozen reversible synthetic work-order result
- receipts/replay: deterministic

## Memory contract

`ADK_SESSION_MEMORY != INSTITUTIONAL_MEMORY`.

ADK session memory is not authoritative. Institutional facts live in deterministic Firestore records and must be explicitly reassembled. This prevents conversation persistence from silently becoming an authority source.

## V0.9 deployment closure assets

- `scripts/google_owner_preflight.sh`
- `scripts/google_prepare_project.sh`
- `scripts/google_deploy_cloud_run.sh`
- `scripts/google_run_deployed_eval.sh`
- `scripts/google_capture_evidence.sh`
- `scripts/github_publish_new_repo.sh`
- `control_service/main.py`
- `docs/GOOGLE_DEPLOYMENT_CLOSURE_KIT_V0_9.md`
- `docs/GOOGLE_OWNER_EXECUTION_COMMANDS_V0_3.md`
- `docs/architecture_v0_9.mmd`

## Evidence boundary

- local deterministic suite: 50/50 PASS
- local FastAPI contract: PASS
- bash syntax preflight: PASS
- mandatory dependencies declared: PASS
- current Agents CLI/API compatibility: documentation-checked, not runtime-executed
- real ADK/Gemini: NOT_EVIDENCED
- real Firestore: NOT_EVIDENCED
- Cloud Run: NOT_DEPLOYED
- deployed evaluation: NOT_RUN
- remote contest repo: NOT_EVIDENCED
- public demo video: NOT_CREATED
- Devpost submission: NOT_DONE


## V0.9.1 deployment closure additions

- Cloud Shell owner bootstrap: `scripts/google_cloudshell_bootstrap.sh`
- Canonical source mutation policy: deployment scaffold generated only in disposable detached Git worktree.
- Staged source validation: full `uv run python -m unittest discover -s tests -v` before deploy.
- Scaffold provenance: `artifacts/google_closure/<timestamp>-deploy/scaffold_diff.patch`.
- Official tooling refresh checked 2026-08-27 against current Agents CLI CLI/deployment/getting-started documentation.
- Real cloud state remains `NOT_EVIDENCED`.
