#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
REGION="${2:-${GOOGLE_CLOUD_LOCATION:-us-east1}}"
MODE="${3:---dry-run}"
DATABASE="${FIRESTORE_DATABASE:-(default)}"
NAMESPACE="${POIEX_GOC_NAMESPACE:-competition}"
SERVICE_ACCOUNT_NAME="${POIEX_GOC_SERVICE_ACCOUNT_NAME:-poiex-goc-runtime}"
SA_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
AGENT_SERVICE="${POIEX_AGENT_SERVICE_NAME:-poiex-agent-fleet}"
CONTROL_SERVICE="${POIEX_GOC_CONTROL_SERVICE_NAME:-poiex-goc-control}"
# Contest-eligible Gemini. Empirically only the Vertex "global" location serves
# Gemini >=3.5 in this project (us-east1/us-central1 expose 2.5-flash only), so
# the advisory fleet routes its GenAI calls through GOOGLE_CLOUD_LOCATION=global.
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.7-flash}"
GENAI_LOCATION="${GENAI_LOCATION:-global}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CLOSURE_ROOT="$ROOT/artifacts/google_closure/$STAMP-deploy"
DEPLOY_WORKTREE="$(mktemp -d "${TMPDIR:-/tmp}/poiex-goc-deploy.XXXXXX")"

if [[ -z "$PROJECT_ID" ]]; then
  echo "usage: $0 PROJECT_ID [REGION] [--dry-run|--apply]" >&2
  exit 2
fi
if [[ "$MODE" != "--dry-run" && "$MODE" != "--apply" ]]; then
  echo "third argument must be --dry-run or --apply" >&2
  exit 2
fi
if [[ ! -d .git ]]; then
  echo "deployment requires canonical git history" >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "canonical repo is dirty; refusing deployment" >&2
  git status --short >&2
  exit 1
fi

mkdir -p "$CLOSURE_ROOT"
cleanup() {
  git worktree remove --force "$DEPLOY_WORKTREE" >/dev/null 2>&1 || true
  rm -rf "$DEPLOY_WORKTREE" >/dev/null 2>&1 || true
}
trap cleanup EXIT

git worktree add --detach "$DEPLOY_WORKTREE" HEAD >/dev/null
printf 'canonical_head=%s\ndeploy_worktree=%s\nmode=%s\n' "$(git rev-parse HEAD)" "$DEPLOY_WORKTREE" "$MODE" > "$CLOSURE_ROOT/deployment_provenance.txt"

./scripts/google_owner_preflight.sh "$PROJECT_ID" "$REGION"

gcloud config set project "$PROJECT_ID"
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
export GOOGLE_CLOUD_LOCATION="$REGION"
export GOOGLE_GENAI_USE_VERTEXAI=TRUE

pushd "$DEPLOY_WORKTREE" >/dev/null

echo "--- generate current Agents CLI Cloud Run plumbing in disposable worktree ---"
agents-cli scaffold enhance . --deployment-target cloud_run -y

if [[ -f Dockerfile ]]; then
  echo "--- patching Dockerfile to copy poiex_runtime and control_service ---"
  sed -i '/COPY \.\/app \.\/app/a COPY ./poiex_runtime ./poiex_runtime\nCOPY ./control_service ./control_service' Dockerfile
fi

git diff --binary > "$CLOSURE_ROOT/scaffold_diff.patch" || true
git status --short > "$CLOSURE_ROOT/scaffold_status.txt" || true

# Install project dependencies in the disposable worktree, then rerun the full
# target-native local suite against the exact staged source that will be deployed.
agents-cli install
uv run python -m unittest discover -s tests -v 2>&1 | tee "$CLOSURE_ROOT/staged_tests.txt"
agents-cli lint 2>&1 | tee "$CLOSURE_ROOT/staged_lint.txt" || true

if [[ "$MODE" == "--dry-run" ]]; then
  echo "--- ADK fleet deployment preview ---"
  agents-cli deploy \
    --project "$PROJECT_ID" \
    --region "$REGION" \
    --service-name "$AGENT_SERVICE" \
    --service-account "$SA_EMAIL" \
    --update-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$GENAI_LOCATION,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GEMINI_MODEL=$GEMINI_MODEL" \
    --no-confirm-project \
    --dry-run | tee "$CLOSURE_ROOT/agent_deploy_dry_run.txt"
  echo "--- deterministic GOC control service preview (privileged plane: authenticated only) ---"
  echo "gcloud run deploy $CONTROL_SERVICE --source $DEPLOY_WORKTREE --project $PROJECT_ID --region $REGION --service-account $SA_EMAIL --set-env-vars POIEX_GOC_STORE=firestore,FIRESTORE_DATABASE=$DATABASE,POIEX_GOC_NAMESPACE=$NAMESPACE,GOOGLE_CLOUD_PROJECT=$PROJECT_ID --command uv --args run,uvicorn,control_service.main:app,--host,0.0.0.0,--port,8080 --no-allow-unauthenticated" | tee "$CLOSURE_ROOT/control_deploy_dry_run.txt"
  echo "DEPLOY=DRY_RUN_ONLY"
  popd >/dev/null
  exit 0
fi

echo "--- deploy advisory ADK fleet from staged/tested worktree ---"
agents-cli deploy \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --service-name "$AGENT_SERVICE" \
  --service-account "$SA_EMAIL" \
  --update-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$GENAI_LOCATION,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GEMINI_MODEL=$GEMINI_MODEL" \
  --no-confirm-project

# Architecture boundary: PUBLIC/SANDBOX DEMO -> ADVISORY AGENT FLEET.
# The fleet is advisory-only (every agent tools=[]; it cannot mint identity,
# authority, target hashes, gate decisions, receipts or execution). Exposing it
# publicly is the demo entry surface, NOT privileged execution authority.
# PUBLIC_ACCESS != EXECUTION_AUTHORITY.
if [[ "${POIEX_AGENT_FLEET_PUBLIC:-true}" == "true" ]]; then
  gcloud run services add-iam-policy-binding "$AGENT_SERVICE" \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --project="$PROJECT_ID" \
    --region="$REGION"
fi

echo "--- deploy deterministic GOC control (privileged plane) from same staged/tested worktree ---"
# The privilege-bound GOC control plane requires an authenticated caller identity.
# No anonymous request can reach identity/authority/target/policy gates or the
# synthetic executor. It is deployed --no-allow-unauthenticated and NEVER granted
# allUsers run.invoker.
gcloud run deploy "$CONTROL_SERVICE" \
  --source "$DEPLOY_WORKTREE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --service-account "$SA_EMAIL" \
  --set-env-vars "POIEX_GOC_STORE=firestore,FIRESTORE_DATABASE=$DATABASE,POIEX_GOC_NAMESPACE=$NAMESPACE,GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
  --command uv \
  --args "run,uvicorn,control_service.main:app,--host,0.0.0.0,--port,8080" \
  --no-allow-unauthenticated

agents-cli deploy --list > "$CLOSURE_ROOT/agents_cli_deploy_list.txt" 2>&1 || true
popd >/dev/null

echo "DEPLOY=APPLIED_FROM_DISPOSABLE_TESTED_WORKTREE"
echo "DEPLOY_PROVENANCE_DIR=$CLOSURE_ROOT"
