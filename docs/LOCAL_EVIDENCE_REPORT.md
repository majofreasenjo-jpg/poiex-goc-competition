# Local evidence report - G-EX-001 to G-EX-003

Date: 2026-08-26
Scope: local clean-room only

## Red phase

The core falsifier tests were frozen before the implementation existed. The first run failed with `ModuleNotFoundError`, preserved in `artifacts/red_phase.txt` and commit `93641b2`.

## Green phase

After implementing the deterministic control plane, the local suite passes 10/10 tests. The core implementation commit is `ea528a8`.

Core outcomes:
- F-G1: revoked, expired, stale-epoch, and out-of-scope authority are blocked before synthetic mutation.
- F-G2: self-declaration cannot promote a capability to OBSERVED.
- F-G3: wrong and stale target hashes are blocked before mutation.
- F-G4: complete replay passes; replay with a missing lease predecessor fails.
- Positive control: a valid bounded synthetic action is allowed and creates exactly one synthetic mutation.

Machine-readable evidence is stored at `artifacts/falsifier_evidence.json`; F-G1 records all four mandatory local authority variants separately.

## ADK scaffold

An isolated Google ADK planner scaffold exists in `app/agent.py` with default model `gemini-3.7-flash` and no tools. This is architecture/code scaffolding only. It has not been executed with Google credentials and does not satisfy the Google framework/deployment hard gate by itself.

## Truth ceiling

LOCAL_PASS != DEPLOYED_VALIDATION
BUILT != DEPLOYED
SCAFFOLDED_ADK != EXECUTED_ADK
MEMORY_STORE != FIRESTORE_EVIDENCE

MR-G-001 remains CONDITIONAL.
MR-G-002 has local supporting evidence but remains CONDITIONAL until deployed rerun evidence exists.
GO_REVIEW remains 0.

## GOC V0.6 local shared-core hardening

The control plane now consumes a RuntimeStore protocol, with MemoryStore and a
FirestoreStore adapter contract. A domain-neutral GovernedOrchestrator binds untrusted
PlannerProposal objects to a domain-authorized trusted MaterialTarget before creating
an ActionIntent. Cloud Run configuration fails closed when POIEX_GOC_STORE is not
explicitly `firestore`, preventing accidental ephemeral governed state in deployment.

This is local implementation evidence only. The current runtime environment could not
install Google packages because package-network access was unavailable, so no ADK
runtime construction, Gemini inference, Firestore connection or Cloud Run deployment
was executed here.

## GOC V0.7 receiver-native cross-lane hardening

A second red-green cycle was frozen before the new mechanisms existed. Red commit:
`67be631` (`test: freeze cross-lane receiver-native falsifiers`). The preserved red
run fails on missing receiver-native modules, proving tests preceded implementation.

V0.7 adds:

- `AuthorityProvenanceRecord` and deterministic delegation/root verification;
- optional `require_authority_provenance` enforcement in the ControlPlane;
- Firestore adapter round-trip for provenance records and lease provenance binding;
- `ActionContractSignature` + effect-class audit with negative seal
  `ACTION_COUNT != INDEPENDENT_EFFECT_CLASS_COUNT`;
- an eight-case receiver-native fault matrix covering prompt authority escalation,
  capability escalation, target substitution, declaration poisoning, revocation race,
  receipt target tamper, replay evidence loss and epoch downgrade;
- a local vertical-slice rehearsal where authority provenance is required and the
  trusted root chain is explicit;
- a four-case ADK evaluation dataset prepared for credentialed `agents-cli eval run`.

The full local unit suite is 35/35 green. Machine-readable delta evidence is
`artifacts/goc_v0_7_cross_lane_delta_evidence.json`; vertical-slice evidence is
`artifacts/goc_v0_7_vertical_slice_local.json`.

Truth ceiling remains:

`LOCAL_RECEIVER_NATIVE_PASS != DEPLOYED_PASS`

`FIRESTORE_ADAPTER_PROVENANCE_PASS != REAL_FIRESTORE_PROVENANCE_EVIDENCE`

`ADK_EVAL_DATASET_PREPARED != ADK_EVAL_EXECUTED`

`SOURCE_LANE_METHOD_REIMPLEMENTED != SOURCE_LANE_EVIDENCE_TRANSFERRED`


## V0.9.1 owner-bootstrap closure

Local suite increased to 54/54 after freezing and implementing the Cloud Shell one-entry contract plus disposable deployment worktree provenance. This is deployment-readiness evidence only. No Google Cloud credential, Gemini inference, Firestore database, Cloud Run service, deployed eval or remote falsifier execution occurred in this environment.

New local invariants:
- default one-entry mode is `--plan`;
- canonical Git tree must be clean;
- deployment scaffold never mutates canonical tested history;
- generated scaffold diff is captured;
- exact staged tree is retested before deployment;
- `--apply` is the explicit owner mutation boundary.
