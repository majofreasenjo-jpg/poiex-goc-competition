#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
REGION="${2:-${GOOGLE_CLOUD_LOCATION:-us-east1}}"
DATABASE="${FIRESTORE_DATABASE:-(default)}"
AGENT_SERVICE="${POIEX_AGENT_SERVICE_NAME:-poiex-agent-fleet}"
CONTROL_SERVICE="${POIEX_GOC_CONTROL_SERVICE_NAME:-poiex-goc-control}"
SERVICE_ACCOUNT_NAME="${POIEX_GOC_SERVICE_ACCOUNT_NAME:-poiex-goc-runtime}"
SA_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DIR="artifacts/google_closure/$STAMP"

if [[ -z "$PROJECT_ID" ]]; then
  echo "usage: $0 PROJECT_ID [REGION]" >&2
  exit 2
fi
mkdir -p "$DIR"

gcloud run services describe "$AGENT_SERVICE" --project "$PROJECT_ID" --region "$REGION" --format=json > "$DIR/agent_service.json"
gcloud run services describe "$CONTROL_SERVICE" --project "$PROJECT_ID" --region "$REGION" --format=json > "$DIR/control_service.json"
gcloud firestore databases describe --project "$PROJECT_ID" --database "$DATABASE" --format=json > "$DIR/firestore_database.json"
gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" --format=json > "$DIR/runtime_service_account.json"
agents-cli login --status > "$DIR/agents_cli_login_status.txt" 2>&1 || true
agents-cli deploy --list > "$DIR/agents_cli_deploy_list.txt" 2>&1 || true

AGENT_URL="$(gcloud run services describe "$AGENT_SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
CONTROL_URL="$(gcloud run services describe "$CONTROL_SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
TOKEN="$(gcloud auth print-identity-token)"

curl -fsS -H "Authorization: Bearer $TOKEN" "$CONTROL_URL/health" > "$DIR/control_health.json"

for case in allow revoked_authority target_substitution policy_epoch_stale; do
  curl -fsS \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"case\":\"$case\",\"scenario_id\":\"cloud-$case-$STAMP\"}" \
    "$CONTROL_URL/v1/demo/run" > "$DIR/goc_${case}.json"
done

for case in binding_change write_only_memory stale_stage_input observer_reparameterization new_rival; do
  curl -fsS \
    -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d "{\"case\":\"$case\"}" \
    "$CONTROL_URL/v1/hardening/run" > "$DIR/goc_hardening_${case}.json"
done

agents-cli run \
  --url "$AGENT_URL" \
  --mode adk \
  --app-name app \
  -v \
  "Analyze a synthetic maintenance outage work order. Delegate registry, authority, target and falsifier analysis. Return a proposal only. Do not claim execution, authorization, target binding, or replay passed." \
  > "$DIR/adk_verbose_delegation_trace.txt" 2>&1 || true

python3 - "$DIR" "$PROJECT_ID" "$REGION" "$DATABASE" "$AGENT_URL" "$CONTROL_URL" "$SA_EMAIL" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

directory = Path(sys.argv[1])
manifest = {
    "schema": "GOOGLE_CLOSURE_EVIDENCE_V0_10",
    "truth_ceiling": "CAPTURED_CLOUD_ARTIFACTS_REQUIRE_HUMAN_REVIEW_BEFORE_PROMOTION",
    "project_id": sys.argv[2],
    "region": sys.argv[3],
    "firestore_database": sys.argv[4],
    "agent_url": sys.argv[5],
    "control_url": sys.argv[6],
    "runtime_service_account": sys.argv[7],
    "files": {},
}
for path in sorted(directory.iterdir()):
    if not path.is_file() or path.name == "manifest.json":
        continue
    data = path.read_bytes()
    manifest["files"][path.name] = {
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }
(directory / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2, sort_keys=True))
PY

echo "EVIDENCE_DIR=$DIR"
