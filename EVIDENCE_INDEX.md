# Evidence Index — POIEX/GOC V0.11

Every claim below is backed by a file in this repository. Truth ceiling honored:
`DEPLOYED != VALIDATED`, `NOT_RUN != PASS`.

## 1. Canonical release (R5-01)
- `artifacts/r5_cloud_attestation/canonical_git_identity.txt` — commit/tag/log.
- `artifacts/r5_cloud_attestation/release_manifest.txt` — full release binding.
- `artifacts/r5_cloud_attestation/test_results.txt` — local suite **73/73**.
- `artifacts/r5_cloud_attestation/staged_test_results.txt` — clean-clone staged **73/73**.

## 2. Effective Gemini model (R5-02)
- `artifacts/r5_cloud_attestation/effective_model_evidence.txt` —
  effective `modelVersion = gemini-3.7-flash` (contest-eligible >=3.5), with the
  per-region availability probe proving only Vertex `global` serves >=3.5 here.

## 3. Public access != execution authority (R5-03)
- `artifacts/r5_cloud_attestation/iam_posture.md` — before/after IAM + falsifier verdicts.
- `artifacts/r5_cloud_attestation/iam_control_before.json` / `iam_control_after.json` —
  `allUsers` present → removed on the control plane.
- `artifacts/r5_cloud_attestation/iam_fleet_before.json` / `iam_fleet_after.json` —
  fleet stays public (advisory demo surface).

## 4. Cloud release binding (R5-04)
- `artifacts/r5_cloud_attestation/cloud_release_binding.txt` — service → revision →
  image digest → service account → commit.

## 5. Deployed falsifier matrix (R5-05)
- `artifacts/r5_cloud_attestation/deployed_falsifier_matrix.json` — **16 PASS / 0 FAIL /
  6 NOT_EVIDENCED**, each with expected/observed/result/revision/receipt/reason.
- `artifacts/r5_cloud_attestation/deployed_control_matrix.jsonl` — raw core + hardening responses.
- `artifacts/r5_cloud_attestation/deployed_public_falsifiers.jsonl` — raw PUBLIC-02..06 responses.

## 6. Inference vs validation vs autorater (R5-06)
- `artifacts/r5_cloud_attestation/autorater_summary.txt` — inference **13/13**;
  autorater ran (10/13 valid critiques, mean 0.836); 3 evaluator-side parse errors,
  **not** agent failures.
- `artifacts/r5_cloud_attestation/deployed_eval_traces_13cases.json` — deployed inference traces.
- Deterministic control validation = the falsifier matrix (§5), independent of any LLM judge.

## 7. Local governance suite
- `tests/` — 73 tests: core falsifiers, planner boundary, authority provenance,
  action independence/capacity, certified repair, future-state sufficiency, fault harness,
  cross-lane governance hardening, Firestore contract, deployment closure.

## Not evidenced on the deployed demo surface (honest gaps)
EXPIRED_AUTHORITY, OUT_OF_SCOPE, STALE_TARGET_VERSION, MISSING_CERTIFICATE,
IDENTITY_SUBSTITUTION, REPLAY_PREDECESSOR_LOSS — covered by the local 73/73 suite but
not exposed as dedicated cases on the deployed demo endpoint. Marked `NOT_EVIDENCED`,
never promoted to PASS.
