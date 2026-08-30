# Google Competition Deployment Runbook V0.1

Status: `PREPARED / OWNER_CREDENTIAL_EXECUTION_REQUIRED`

## Truth ceiling

This runbook is preparation. No command in this file has been executed against the
owner's Google Cloud project from this environment. Deployment evidence exists only
when project/service/revision/database identifiers and deployed test outputs are
captured from the real environment.

## Current official stack requirements

- Gemini 3.5 or newer via Gemini API or Vertex AI.
- At least one Google agent framework; this project targets Google ADK.
- At least one Google Cloud infrastructure service; this project targets Cloud Run + Firestore.
- Fortified Enterprise Fleet is the selected track. Current Devpost clarification maps it to the Multi-Agent Nexus architecture criterion: strictly enforced agent separation plus failure-tolerant inter-agent routing.
- Submission deadline: 2026-08-31 17:00 Pacific Time.

## Preflight owner actions

1. Confirm Devpost eligibility and start/join the project.
2. Select a Google Cloud project with billing available.
3. Authenticate gcloud and model access using the intended project/account.
4. Create/confirm a Firestore database and a user-managed Cloud Run service identity with the minimum required Firestore access.
5. Do not place long-lived service-account JSON keys in the repository.
6. Do not set GOOGLE_APPLICATION_CREDENTIALS inside Cloud Run; use service identity.

## Local ADK verification path

From the clean-room repository, after installing current dependencies:

```bash
agents-cli cmd-info --json
agents-cli run "Propose a bounded synthetic maintenance work-order action. Do not execute it."
```

Capture the full verbose trace during the evidence run and verify:

- coordinator delegates to specialist sub-agents;
- specialist agents have no material executor tool;
- the final output is advisory/proposal-only;
- no agent claims a hard gate has passed.

## GOC persistence configuration

Required deployment variables:

```text
POIEX_GOC_STORE=firestore
POIEX_GOC_NAMESPACE=competition
GEMINI_MODEL=gemini-3.7-flash
```

Optional explicit values:

```text
FIRESTORE_DATABASE=(default)
```

`GOOGLE_CLOUD_PROJECT` should come from the Google execution environment/project
configuration where possible. The runtime refuses Cloud Run + MemoryStore.

## Cloud Run deploy path

Primary current agents-cli path:

```bash
agents-cli deploy --project <PROJECT_ID> --region <REGION>
```

Before execution, inspect the generated command/dry-run if available and confirm the
runtime service account and environment variables. If direct source deployment is
used instead, Google Cloud currently documents `gcloud run deploy --source .` as the
source-deploy path for an ADK service.

## Evidence capture required for G-EX-005

Capture, without secrets:

- Google Cloud project ID
- Cloud Run service name
- Cloud Run service URL
- active revision ID/name
- deployment timestamp
- configured runtime service account
- Firestore database ID
- GOC namespace
- one bounded registry document
- one AuthorityLease document
- one MaterialTarget document
- one ExecutionReceipt document from an allowed action
- Cloud Trace spans showing coordinator-to-specialist delegation when available
- five `/v1/hardening/run` deployed outputs: binding change, write-only memory, stale-stage input, observer reparameterization, new rival

## Deployed falsifier rerun required for G-EX-006

Re-run the same semantic gates after deployment:

- revoked authority => BLOCK, no mutation
- expired authority => BLOCK, no mutation
- stale epoch => BLOCK, no mutation
- out-of-scope authority => BLOCK, no mutation
- self-declaration cannot become OBSERVED
- wrong/stale target => BLOCK
- complete replay => PASS
- missing material predecessor => FAIL
- semantic binding changed => prior final-disposition artifact invalidated + recompute
- persisted history with no matched-state future split => readback not demonstrated
- stale pre-gate stage input without verified noninterference => BLOCK
- observer/config-only rerun with unchanged state and evidence roots => zero minted progress
- new admissible rival => global registry reopened; unchanged local certificates remain scope-local

No deployed PASS may be recorded from local results.
