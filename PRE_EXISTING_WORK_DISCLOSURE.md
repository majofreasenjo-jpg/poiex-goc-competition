# Pre-existing Work Disclosure — POIEX/GOC

Google All Things Agentic requires honest disclosure of pre-existing work the submission
builds on. This is that disclosure.

## What is new for this competition
- The entire runnable artifact in this repository: the deterministic **GOC control plane**
  (`poiex_runtime/`, `control_service/`), the **advisory ADK/Gemini agent fleet**
  (`app/`, `poiex_runtime/adk_planner.py`), the **two-service Cloud Run architecture**,
  the **deterministic falsifier + governance-hardening test suite** (`tests/`), and the
  **Google deploy / preflight / evidence-capture tooling** (`scripts/`).
- All of the above is a **clean-room implementation** written for this submission
  (see `CLEAN_ROOM_PROVENANCE.md`). No external code was copied in.

## What pre-existed (method lineage, not code)
- The five receiver-native governance controls (semantic-binding invalidation,
  operational-memory readback, sequential stage freshness, observer/configuration
  non-mint, open-world registry reopening) were **derived from an internal, proprietary
  multi-lane method review** conducted by the author across several private research
  lanes. **Those lanes, their formulas, datasets, genealogies and evidence are NOT part
  of this submission** and are not included in this repository.
- Only the **methods** were transferred and **re-implemented from scratch** here against
  the Fortified Enterprise Fleet target. No scientific evidence, theorem status, canon
  status or validation from those private lanes is claimed or transferred:
  `METHOD_TRANSFER != EVIDENCE_TRANSFER`.

## Third-party components (used as-is, standard licenses)
- Google ADK (`google-adk`), Google GenAI / Gemini via Vertex AI.
- Google Cloud Firestore, Cloud Run, Cloud Trace, Cloud Build.
- FastAPI, Uvicorn, Pydantic, Starlette, the official `google-agents-cli`.

## Summary
The contest contribution is the governed multi-agent architecture and its clean-room
implementation. The proprietary research lanes that inspired the governance methods are
disclosed here at a high level and deliberately withheld; nothing in this repository
depends on them to build, run, deploy or verify.
