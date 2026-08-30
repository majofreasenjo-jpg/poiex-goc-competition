# Clean-room provenance boundary

Project: POIEX / GOC Google Attack Runtime V0.6
Created: 2026-08-26

This repository is a new implementation created for the current POIEX execution track.
Method-level ideas were derived from the POIEX capability genome and G-HO-001 specification.
No source code is copied from an internal method lane, an internal method lane, Agentogenesis, CSSC, Institutional Genome, an internal method lane, or other prior projects.
No source-project validation, maturity, canon, or empirical evidence transfers into this repository.

Truth ceiling at creation:
- local clean-room implementation only
- no Google Cloud deployment evidence
- no competition submission evidence
- no production security certification
- no claim of contest success probability

Firewalls:
METHOD_TRANSFER != EVIDENCE_TRANSFER
SOURCE_MATURITY != TARGET_MATURITY
BUILT != DEPLOYED
LOCAL_PASS != DEPLOYED_VALIDATION

V0.6 extension: shared RuntimeStore/Firestore adapter contract and planner/orchestrator boundary were implemented in this same clean-room repository. No cloud evidence is inherited from the architecture decision.

## Session recovery import - 2026-08-27
The V0.8 working repository was reconstructed from the preserved V0.6 Git bundle plus the verified V0.7 release ZIP because the V0.7 Git bundle was not mounted in the current runtime. Historical V0.7 commit hashes remain provenance references recorded in the release artifacts and POIEX workbook; they were not synthetically recreated. This recovery import does not promote any cloud, framework-runtime, or external-validation claim. New V0.8 work resumes explicit test-first red-to-green history from this recovery point.

## V0.9 deployment-closure extension — 2026-08-27

V0.9 continues from an explicit recovery commit made from the preserved V0.6 Git history plus the verified V0.8 release tree. The original V0.7/V0.8 historical hash references remain documentary provenance only where their bundles were not mounted; they are not synthetically recreated.

V0.9 adds clean-room deployment mechanics, not source-lane code or evidence:

- mandatory Google runtime dependencies;
- a receiver-native synthetic GOC HTTP service;
- Google Cloud preflight/project-preparation/deploy/eval/evidence-capture scripts;
- a new-repository publication helper that requires a genuinely new empty GitHub remote.

The remote GOC service accepts no arbitrary production mutation target and no authority-bearing fields from the model/caller. It remains a synthetic competition demonstration surface.

Additional firewalls:

- `LOCAL_HTTP_CONTRACT_PASS != CLOUD_RUN_PASS`
- `DEPENDENCIES_DECLARED != IMAGE_BUILT`
- `ADK_SESSION_MEMORY != INSTITUTIONAL_MEMORY`
- `SYNTHETIC_DEMO_ONLY != PRODUCTION_CONTROL`
- `CLOUD_ARTIFACT_CAPTURED != CLAIM_PROMOTED`

## V0.9.1 owner-bootstrap hardening — 2026-08-27

V0.9.1 is a Track-A deployment-closure hardening only. It does not import code, evidence, maturity, canon or validation from any other lane.

Test-first lineage added in this cycle:

- `b37390c4ae55843d142688a38f55eeeb5085fe17` — RED: Cloud Shell one-entry owner bootstrap contract frozen before implementation.
- `f6d2d216426df8c3c3516c95b7a931028e844c3b` — RED: deployment scaffolding required to occur in a disposable Git worktree.
- `7ba2e589b0576b36851a8059dffe2a3cde225446` — GREEN implementation of one-entry Cloud Shell bootstrap and staged deployment path.
- `79bc09d05da1392607f6a679a1bd964ee56ea705` — RED regression discovered by integration simulation: generated closure artifacts dirtied the canonical repository.
- `65e49448376b752e193cecfefbdea78ae2d64fd9` — GREEN fix: closure evidence directory ignored by canonical Git status; full suite green.

A fake-CLI integration simulation exercised the complete `--plan` path using non-network local command shims. It proved only shell/control-flow behavior: active-project inference, read-only project plan, detached deployment worktree, staged scaffold mutation, staged test rerun, and two-service dry-run while the canonical repo remained clean.

Additional firewalls:

- `FAKE_CLI_PLAN_PASS != REAL_GOOGLE_CLOUD_PASS`
- `CANONICAL_TESTED_TREE != GENERATED_DEPLOYMENT_SCAFFOLD`
- `SCAFFOLD_DIFF_CAPTURED != DEPLOYED_BEHAVIOR_VALIDATED`
- `OWNER_APPLY_COMMAND_PREPARED != OWNER_APPLY_EXECUTED`
- `CLOUDSHELL_BOOTSTRAP_READY != CLOUD_DEPLOYMENT_EVIDENCE`
