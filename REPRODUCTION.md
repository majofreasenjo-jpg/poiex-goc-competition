# Reproduction Instructions — POIEX/GOC V0.11

## A. Local (no cloud, ~1 minute)
```bash
# Python 3.11+; install the four Google runtime deps into a venv, then:
python -m unittest discover -s tests -v
# Expect: Ran 73 tests ... OK
```
Optionally run the hardening cases and the local governed slice:
```bash
python scripts/run_v0_10_governance_hardening.py
python scripts/run_goc_vertical_slice.py
python scripts/run_local_falsifiers.py
```

## B. Google Cloud PLAN (no mutation)
```bash
bash scripts/google_cloudshell_bootstrap.sh --plan \
  --project <PROJECT_ID> --region us-east1
```
Requires an authenticated `gcloud` and the official `google-agents-cli` (`uv tool install google-agents-cli`).
PLAN prints identity, project, billing, APIs, Firestore/IAM plan and a two-service dry-run.

## C. Google Cloud APPLY (owner mutation boundary)
```bash
bash scripts/google_cloudshell_bootstrap.sh --apply \
  --project <PROJECT_ID> --region us-east1
```
This enables APIs, creates Firestore + the runtime service account (least-privilege:
`datastore.user`, `aiplatform.user`, `cloudtrace.agent`), deploys both Cloud Run services
from a disposable tested worktree, runs the deployed eval and captures evidence.
- The fleet routes GenAI through `GOOGLE_CLOUD_LOCATION=global` with `GEMINI_MODEL=gemini-3.7-flash`
  (only `global` serves Gemini >=3.5 in this project — see `effective_model_evidence.txt`).
- The control plane is deployed `--no-allow-unauthenticated` and is **never** granted `allUsers`.

## D. Attest the live deployment
```bash
# effective model (fleet is the public demo surface):
agents-cli run --url <FLEET_URL> --mode adk --app-name app -v \
  "Analyze a synthetic maintenance outage work order for pump-A. Return a proposal only."
#   -> response metadata shows "modelVersion": "gemini-3.7-flash"

# anonymous MUST be blocked on the control plane:
curl -s -o /dev/null -w '%{http_code}\n' -X POST <CONTROL_URL>/v1/demo/run \
  -H 'Content-Type: application/json' -d '{"case":"allow","scenario_id":"anon"}'
#   -> 403

# authenticated authorized identity runs the governed matrix:
TOKEN=$(gcloud auth print-identity-token \
  --impersonate-service-account=poiex-goc-runtime@<PROJECT_ID>.iam.gserviceaccount.com \
  --audiences=<CONTROL_URL> --include-email)
curl -s -X POST <CONTROL_URL>/v1/demo/run -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"case":"revoked_authority","scenario_id":"a"}'
#   -> decision BLOCK, reasons ["AUTHORITY_REVOKED"], replay PASS
```
`scripts/google_capture_evidence.sh` runs the full core + hardening capture into a
SHA-256 manifest.

## E. Verify the Competition Edition itself
```bash
sha256sum -c SHA256SUMS.txt        # all files match
python -m unittest discover -s tests   # 73/73 green
```
