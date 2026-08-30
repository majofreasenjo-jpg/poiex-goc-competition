# Demo Script — POIEX/GOC (≤ 4:00, one continuous live take)

Status: `SCRIPT_PREPARED / VIDEO_NOT_RECORDED`. The recording must show the real deployed
system (live Cloud Run URLs, real 403/decisions). Have two terminals ready: (1) `agents-cli`
against the fleet URL, (2) `curl` against the control URL with the impersonated ID token.

**0:00–0:25 — The problem**
"Most agent demos prove an LLM can call a tool. The real enterprise risk is a legitimate
agent acting with stale authority or on the wrong target." Show the two live Cloud Run URLs
and the project `poiex-goc-fortified-2026`. State the invariant on screen:
**EL AGENTE PIENSA; EL SISTEMA GOBIERNA.**

**0:25–0:55 — The fleet (Gemini 3.7 Flash)**
Run the fleet query; show the coordinator delegating to Registry / Authority / Target /
Falsifier stewards. Point to the response metadata: `"modelVersion": "gemini-3.7-flash"`.
Say: "Every agent has `tools=[]`. They advise; they cannot act."

**0:55–1:35 — A governed positive action**
Authenticated `curl` → `/v1/demo/run {"case":"allow"}`. Show `decision: ALLOW`,
`ALL_MATERIAL_GATES_PASS`, a real `receipt_id`, and `replay: PASS`. Note `store_mode: firestore`.

**1:35–2:10 — Stale/revoked authority**
`{"case":"revoked_authority"}` → `BLOCK / AUTHORITY_REVOKED`.
`{"case":"policy_epoch_stale"}` → `BLOCK / AUTHORITY_EPOCH_STALE`. "Same fleet, same request —
the system refuses because authority is stale, not because the LLM hesitated."

**2:10–2:45 — Wrong target**
`{"case":"target_substitution"}` → `REJECTED_BEFORE_INTENT`. "The planner named a different
pump. The trusted binder rejects it before any intent is formed."

**2:45–3:15 — Public ≠ execution authority**
Anonymous `curl` to the control plane (no token) → **HTTP 403**. Then show a forged request
with fake `lease_id/authority/gate_decision` fields → the fields are inert, authority stays
server-owned. "Anyone can talk to the advisory fleet. Nobody anonymous can reach execution."

**3:15–3:45 — Cross-lane hardening**
`/v1/hardening/run` for `binding_change` → `INVALIDATE_AND_RECOMPUTE` and
`observer_reparameterization` → `NONMINT_VIOLATION`. "Changing a binding invalidates the old
decision; re-running an evaluator with unchanged evidence mints zero progress."

**3:45–4:00 — Close**
"Deterministic control, replayable receipts, Firestore institutional memory, and a fleet that
cannot grant itself power. 73/73 tests, 16/0 deployed falsifiers. The agent thinks; the system
governs." Show `EVIDENCE_INDEX.md`.
