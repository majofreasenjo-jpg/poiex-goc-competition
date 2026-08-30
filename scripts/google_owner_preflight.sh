#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
REGION="${2:-${GOOGLE_CLOUD_LOCATION:-us-east1}}"
DATABASE="${FIRESTORE_DATABASE:-(default)}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "usage: $0 PROJECT_ID [REGION]" >&2
  exit 2
fi

mkdir -p artifacts/google_closure
OUT="artifacts/google_closure/preflight.txt"
: > "$OUT"

check_cmd() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    printf 'PASS command %s -> %s\n' "$name" "$(command -v "$name")" | tee -a "$OUT"
  else
    printf 'FAIL command %s missing\n' "$name" | tee -a "$OUT"
    return 1
  fi
}

fail=0
for cmd in python3 git gcloud agents-cli; do
  check_cmd "$cmd" || fail=1
done

python3 - <<'PY' | tee -a "$OUT"
import sys
print(f"python_version={sys.version.split()[0]}")
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ required")
PY

printf 'project=%s\nregion=%s\ndatabase=%s\n' "$PROJECT_ID" "$REGION" "$DATABASE" | tee -a "$OUT"

if command -v gcloud >/dev/null 2>&1; then
  echo "--- gcloud active account ---" | tee -a "$OUT"
  gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>&1 | tee -a "$OUT" || fail=1
  echo "--- project ---" | tee -a "$OUT"
  gcloud projects describe "$PROJECT_ID" --format='value(projectId,projectNumber)' 2>&1 | tee -a "$OUT" || fail=1
  echo "--- billing ---" | tee -a "$OUT"
  gcloud billing projects describe "$PROJECT_ID" --format='value(billingEnabled,billingAccountName)' 2>&1 | tee -a "$OUT" || fail=1
  echo "--- firestore ---" | tee -a "$OUT"
  gcloud firestore databases describe --project "$PROJECT_ID" --database "$DATABASE" --format='value(name,locationId,type)' 2>&1 | tee -a "$OUT" || true
fi

if command -v agents-cli >/dev/null 2>&1; then
  echo "--- agents-cli ---" | tee -a "$OUT"
  agents-cli --version 2>&1 | tee -a "$OUT" || fail=1
  agents-cli info --json 2>&1 | tee -a "$OUT" || fail=1
  agents-cli login --status 2>&1 | tee -a "$OUT" || fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  echo "PREFLIGHT=BLOCKED" | tee -a "$OUT"
  exit 1
fi

echo "PREFLIGHT=READY_FOR_CLOUD_PREP" | tee -a "$OUT"
