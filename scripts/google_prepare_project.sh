#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${1:-${GOOGLE_CLOUD_PROJECT:-}}"
REGION="${2:-${GOOGLE_CLOUD_LOCATION:-us-east1}}"
MODE="${3:---plan}"
DATABASE="${FIRESTORE_DATABASE:-(default)}"
SERVICE_ACCOUNT_NAME="${POIEX_GOC_SERVICE_ACCOUNT_NAME:-poiex-goc-runtime}"
SA_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if [[ -z "$PROJECT_ID" ]]; then
  echo "usage: $0 PROJECT_ID [REGION] [--plan|--apply]" >&2
  exit 2
fi
if [[ "$MODE" != "--plan" && "$MODE" != "--apply" ]]; then
  echo "third argument must be --plan or --apply" >&2
  exit 2
fi

cat <<EOF
Google project preparation
  project: $PROJECT_ID
  region: $REGION
  firestore database: $DATABASE
  runtime service account: $SA_EMAIL
  mode: $MODE
EOF

if [[ "$MODE" == "--plan" ]]; then
  cat <<EOF
PLAN ONLY. No cloud mutation executed.
Would enable: run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com aiplatform.googleapis.com iam.googleapis.com iamcredentials.googleapis.com cloudtrace.googleapis.com
Would create Firestore Standard/Native database $DATABASE in $REGION only if missing.
Would create service account $SA_EMAIL only if missing.
Would grant runtime roles: roles/datastore.user roles/aiplatform.user roles/cloudtrace.agent.
Re-run with --apply to execute.
EOF
  exit 0
fi

gcloud config set project "$PROJECT_ID"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudtrace.googleapis.com \
  --project "$PROJECT_ID"

if ! gcloud firestore databases describe --project "$PROJECT_ID" --database "$DATABASE" >/dev/null 2>&1; then
  gcloud firestore databases create \
    --project "$PROJECT_ID" \
    --database "$DATABASE" \
    --location "$REGION" \
    --edition standard \
    --type firestore-native \
    --delete-protection
fi

if ! gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --project "$PROJECT_ID" \
    --display-name "POIEX GOC governed runtime"
fi

for role in roles/datastore.user roles/aiplatform.user roles/cloudtrace.agent; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:$SA_EMAIL" \
    --role "$role" \
    --condition=None \
    >/dev/null
done

echo "PROJECT_PREP=APPLIED"
