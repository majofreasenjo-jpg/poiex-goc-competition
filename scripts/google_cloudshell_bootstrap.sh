#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="--plan"
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
REGION="${GOOGLE_CLOUD_LOCATION:-us-east1}"

usage() {
  cat <<'USAGE'
usage: scripts/google_cloudshell_bootstrap.sh [--project PROJECT_ID] [--region REGION] [--plan|--apply]

Default mode is --plan. --plan performs no cloud mutation and does not install tools.
--apply is the explicit owner mutation boundary: it may install uv/google-agents-cli
in the Cloud Shell user environment, prepare the selected GCP project, deploy both
Cloud Run services, run the deployed eval, and capture evidence.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      PROJECT_ID="${2:-}"
      shift 2
      ;;
    --region)
      REGION="${2:-}"
      shift 2
      ;;
    --plan|--apply)
      MODE="$1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p artifacts/google_closure
LOG="artifacts/google_closure/cloudshell_bootstrap.txt"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

printf 'POIEX GOC Cloud Shell owner bootstrap\nmode=%s\nregion=%s\n' "$MODE" "$REGION"

if [[ ! -d .git ]]; then
  echo "BLOCK: canonical git history is required. Restore from the verified .bundle before deployment." >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "BLOCK: canonical repository is dirty. Deployment requires a clean tested commit." >&2
  git status --short >&2
  exit 1
fi
printf 'canonical_head=%s\n' "$(git rev-parse HEAD)"
printf 'canonical_tag=%s\n' "$(git describe --tags --exact-match 2>/dev/null || echo NONE)"

for cmd in python3 git gcloud; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "BLOCK: required command missing: $cmd" >&2
    echo "Use Google Cloud Shell, where gcloud is preinstalled and authenticated." >&2
    exit 1
  fi
done

python3 - <<'PY'
import sys
print(f"python_version={sys.version.split()[0]}")
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ required")
PY

if [[ -z "$PROJECT_ID" ]]; then
  PROJECT_ID="$(gcloud config get-value project 2>/dev/null || true)"
  if [[ "$PROJECT_ID" == "(unset)" ]]; then
    PROJECT_ID=""
  fi
fi
if [[ -z "$PROJECT_ID" ]]; then
  echo "BLOCK: no Google Cloud project is active. Pass --project PROJECT_ID or set gcloud config project." >&2
  exit 1
fi

export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
export GOOGLE_CLOUD_LOCATION="$REGION"
printf 'project=%s\nregion=%s\n' "$PROJECT_ID" "$REGION"

echo "--- active gcloud account ---"
gcloud auth list --filter=status:ACTIVE --format='value(account)' || true

echo "--- project preparation plan (no mutation) ---"
./scripts/google_prepare_project.sh "$PROJECT_ID" "$REGION" --plan

if [[ "$MODE" == "--plan" ]]; then
  if command -v agents-cli >/dev/null 2>&1 && command -v uv >/dev/null 2>&1; then
    echo "--- two-service deployment dry-run (no cloud mutation) ---"
    ./scripts/google_deploy_cloud_run.sh "$PROJECT_ID" "$REGION" --dry-run
    echo "CLOUDSHELL_BOOTSTRAP=PLAN_COMPLETE"
  else
    echo "PLAN NOTE: agents-cli/uv not installed; no tool installation occurs in --plan mode."
    echo "On explicit --apply the script will install uv/google-agents-cli in the Cloud Shell user environment."
    echo "Then it will rerun this plan and the deployment dry-run before any cloud mutation."
    echo "CLOUDSHELL_BOOTSTRAP=PLAN_COMPLETE_TOOL_INSTALL_PENDING"
  fi
  exit 0
fi

# --apply is the explicit owner mutation boundary.
if ! command -v uv >/dev/null 2>&1; then
  echo "--- installing uv in Cloud Shell user environment ---"
  python3 -m pip install --user uv
  USER_BASE="$(python3 -m site --user-base)"
  export PATH="$USER_BASE/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if ! command -v agents-cli >/dev/null 2>&1; then
  echo "--- installing official google-agents-cli ---"
  uv tool install google-agents-cli
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  hash -r
fi

agents-cli --version
if ! agents-cli login --status; then
  echo "Agents CLI does not see usable Google authentication; starting interactive owner login."
  agents-cli login -i
fi

echo "--- owner preflight ---"
./scripts/google_owner_preflight.sh "$PROJECT_ID" "$REGION"

echo "--- re-run project plan immediately before mutation ---"
./scripts/google_prepare_project.sh "$PROJECT_ID" "$REGION" --plan

echo "--- deployment dry-run immediately before mutation ---"
./scripts/google_deploy_cloud_run.sh "$PROJECT_ID" "$REGION" --dry-run

echo "--- APPLY project preparation ---"
./scripts/google_prepare_project.sh "$PROJECT_ID" "$REGION" --apply

echo "--- APPLY two-service deployment ---"
./scripts/google_deploy_cloud_run.sh "$PROJECT_ID" "$REGION" --apply

eval_rc=0
capture_rc=0

echo "--- deployed ADK evaluation ---"
./scripts/google_run_deployed_eval.sh "$PROJECT_ID" "$REGION" || eval_rc=$?

echo "--- deployed control/evidence capture ---"
./scripts/google_capture_evidence.sh "$PROJECT_ID" "$REGION" || capture_rc=$?

printf 'deployed_eval_rc=%s\ndeployed_capture_rc=%s\n' "$eval_rc" "$capture_rc"
if [[ "$eval_rc" -ne 0 || "$capture_rc" -ne 0 ]]; then
  echo "CLOUDSHELL_BOOTSTRAP=DEPLOYED_WITH_EVIDENCE_GAP"
  exit 1
fi

echo "CLOUDSHELL_BOOTSTRAP=DEPLOY_AND_CAPTURE_COMPLETE_PENDING_HUMAN_REVIEW"
