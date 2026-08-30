#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
REGION="${2:-${GOOGLE_CLOUD_LOCATION:-us-east1}}"
AGENT_SERVICE="${POIEX_AGENT_SERVICE_NAME:-poiex-agent-fleet}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "usage: $0 PROJECT_ID [REGION]" >&2
  exit 2
fi

AGENT_URL="$(gcloud run services describe "$AGENT_SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="artifacts/google_closure/eval-$STAMP"
mkdir -p "$OUT"

agents-cli eval run \
  --dataset tests/eval/datasets/governed-fleet-dataset.json \
  --metrics final_response_quality \
  --url "$AGENT_URL" \
  --app-name app \
  --project "$PROJECT_ID" \
  --region us-central1 \
  --output "$OUT"

echo "DEPLOYED_EVAL_OUTPUT=$OUT"
