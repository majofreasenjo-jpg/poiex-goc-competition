# CONTEST IP FIREWALL REPORT — POIEX/GOC Competition Edition

Generated for the Google All Things Agentic submission (Fortified Enterprise Fleet).
Source of truth: canonical tag `v0.11.0-rc1-contest-cloud-attested` (private release).
This Competition Edition is an allowlist-only, sanitized export of that tag.
`CLOUD_GREEN != SUBMISSION_REPO_READY` — this edition is the submission-ready subset.

## Method
1. **Allowlist-only copy.** Only files required to understand, run, reproduce and verify
   the solution are included (source, tests, deploy/verify scripts, architecture docs,
   curated cloud-attestation evidence). Everything else in the private repo is excluded
   by omission, not by redaction.
2. **Proprietary-name sanitization.** Internal project / research-lane names were replaced
   with the generic token "an internal method lane".
3. **Drive-ID exclusion.** All Google Drive `artifact_id` provenance lines were stripped.
4. **Local-path scrub.** Absolute private-workspace paths were replaced with `<workspace>`.
5. **Secret scan.** Regex sweep for API keys, private keys, OAuth tokens, AWS keys.
6. **Clean-restore verification.** The full test suite runs GREEN inside the edition.

## Excluded (not in this edition)
- Research Genome / genealogies / root graphs — never in this repo; not added.
- Coalition Engine, Minimum-Repair / VOI proprietary internals — not in this repo.
- Other scientific lanes, proprietary formulas, private datasets, private roadmaps,
  ruling/governance internal documents, production adapters.
- Google Drive donor-provenance JSONs (`goc_v0_10_cross_lane_review.json`,
  `goc_v0_8_evidence.json`) — contained Drive doc IDs + internal lane names.
- Owner-internal packages: `ANTIGRAVITY_HANDOFF.md`, `artifacts/claude_preflight/`,
  historical per-version evidence dumps not needed to verify V0.11.
- Keys / secrets / tokens — none present (scan clean).

## Included (minimum sufficient)
- Full runnable source: `poiex_runtime/`, `control_service/`, `app/`.
- Full deterministic + governance + hardening test suite: `tests/` (73 tests).
- Google deploy / preflight / evidence-capture / eval scripts: `scripts/`.
- Architecture & contract docs (sanitized): `docs/`.
- Curated deployed cloud attestation: `artifacts/r5_cloud_attestation/`
  (effective-model proof, IAM before/after, deployed falsifier matrix, release binding).
- V0.11 hardening evidence summaries (no proprietary content).
- `PRE_EXISTING_WORK_DISCLOSURE.md`, this report, `COMPETITION_EDITION_MANIFEST.txt`,
  `SHA256SUMS.txt`.

## Scan results
- Proprietary-name scan .......... CLEAN (0 residual after sanitization)
- Google Drive doc-id scan ....... CLEAN (0; one synthetic `receipt-...` demo id is not a Drive id)
- Secret / key / token scan ...... CLEAN (0)
- Local absolute-path scan ....... CLEAN (0; scrubbed to `<workspace>`)
- Clean-restore test suite ....... 73/73 GREEN

## Verdict
CONTEST_IP_FIREWALL = PASS. The edition is self-contained, reproducible, free of
proprietary IP and secrets, and sufficient to verify the Google Cloud / ADK / Gemini /
falsifier claims.
