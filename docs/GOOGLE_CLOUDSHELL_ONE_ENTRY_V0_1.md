# Google Cloud Shell one-entry closure — V0.1

Purpose: reduce the remaining owner-side Google gate to one fail-closed entrypoint without putting credentials in chat or in Git.

## Non-negotiable truth ceilings

- `LOCAL_PLAN != CLOUD_DEPLOYMENT`
- `LOCAL_HTTP_CONTRACT_PASS != CLOUD_RUN_PASS`
- `AGENTS_CLI_INSTALLED != ADK_RUNTIME_EVIDENCE`
- `FIRESTORE_ADAPTER_CONTRACT != REAL_FIRESTORE`
- `DEPLOYED != VALIDATED`
- `ADK_SESSION_MEMORY != INSTITUTIONAL_MEMORY`

The canonical repository must be clean and restored from the verified Git bundle. The deployment script creates a disposable detached Git worktree, lets the current official Agents CLI generate Cloud Run plumbing there, captures the generated diff, installs dependencies there, reruns the full local test suite against that staged tree, and only then produces a dry-run or deploys. The canonical tested history is never modified by deployment scaffolding.

## Cloud Shell entry

From a clean restored repository in Google Cloud Shell:

```bash
bash scripts/google_cloudshell_bootstrap.sh --plan
```

`--plan` is the default and performs no cloud mutation and no tool installation. It resolves the active `gcloud` project when available, prints the project preparation plan, and runs the two-service deployment dry-run only if `uv` and `agents-cli` are already installed.

After reviewing the project ID, region, service account, Firestore database and dry-run:

```bash
bash scripts/google_cloudshell_bootstrap.sh --apply
```

`--apply` is the explicit owner mutation boundary. If needed it installs `uv` and the official `google-agents-cli` into the Cloud Shell user environment, checks/requests owner authentication, reruns plan and dry-run, prepares the project, deploys `poiex-agent-fleet` and `poiex-goc-control`, runs the deployed ADK evaluation, and captures Cloud Run/Firestore/service-account/GOC evidence.

To override project or region:

```bash
bash scripts/google_cloudshell_bootstrap.sh \
  --project YOUR_PROJECT_ID \
  --region us-east1 \
  --plan
```

Then repeat with `--apply` only after the plan is correct.

## Owner-side source restoration

Prefer restoring the verified history bundle instead of deploying from an extracted source-only ZIP:

```bash
git clone poiex_goc_google_runtime_v0_9_1_history.bundle poiex-goc
cd poiex-goc
git status --short
```

The status must be empty before `--apply`.

## Expected evidence

Successful application produces artifacts under `artifacts/google_closure/`, including the staged Agents CLI scaffold diff, staged test output, deployment metadata, ADK evaluation output, Cloud Run service descriptions, Firestore database description, runtime service account metadata, GOC scenario receipts, replay results and SHA-256 evidence manifest.

No successful script exit by itself authorizes a competition claim. Evidence must be inspected before any workbook or submission state is promoted.
