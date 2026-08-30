# Google Fortified Enterprise Fleet — Demo Storyboard V0.3

Status: `SCRIPT_PREPARED / VIDEO_NOT_RECORDED`

Target: one continuous live demo, maximum four minutes, with visible Google Cloud
backend evidence. The final recording must reflect the real deployed system.

## Core story

Most enterprise agent demos prove that an LLM can call a tool. This demo proves that
an institutional agent fleet can be useful while being unable to grant itself power.

Friction: a maintenance outage has many specialized agents, long-lived state, changing
authority, evolving targets and operational obligations. The dangerous failure is not
only hallucination; it is a legitimate agent acting with stale authority or on the
wrong target.

Twist: the fleet can think collaboratively, but a deterministic GOC decides whether a
material action is admissible and records enough evidence to replay the decision.

## Four-minute live sequence

0:00-0:25 — Problem and unlikely hero
- Maintenance Outage Coordinator is the institutional "unlikely hero".
- Show the live Cloud Run URL/project briefly.

0:25-0:55 — Fleet and architecture
- Planning Coordinator delegates advisory work to Registry, Authority, Target and
  Falsifier stewards. If a required specialist is unavailable, show or state the fail-closed `ABSTAIN_SPECIALIST_FAILURE` rule; the coordinator does not impersonate it.
- State the invariant: "The agent thinks; the system governs."

0:55-1:35 — Positive action
- Show synthetic work-order proposal.
- Show registry OBSERVED evidence, live AuthorityLease, its delegation/provenance chain to a trusted root, and the exact MaterialTarget.
- Execute one bounded synthetic action.
- Show ExecutionReceipt and replay PASS.

1:35-2:10 — Revoked authority / provenance
- Revoke the active lease or one upstream provenance edge in the controlled demo path.
- Repeat the proposal.
- Show BLOCK and zero additional synthetic mutation.

2:10-2:40 — Target substitution
- Planner proposes/mentions a different target from the domain-authorized target.
- Trusted binding rejects the substitution before ActionIntent execution.

2:40-3:12 — Governance cannot be gamed
- Open one compact `/v1/hardening/run` evidence panel with five deployed rows.
- Highlight three in one sentence each: binding change => INVALIDATE_AND_RECOMPUTE; write-only history => READBACK_NOT_DEMONSTRATED; observer-only threshold change => NONMINT_VIOLATION.
- Keep stale-stage-input and new-rival reopening visible as rows, not separate narrative branches.
- State the scientific-method firewall on screen: METHOD_TRANSFER != EVIDENCE_TRANSFER.

3:12-3:37 — Production-readiness evidence
- Show both Cloud Run revisions, Firestore documents, and Cloud Trace spans for coordinator-to-specialist delegation.
- State local vs deployed evidence explicitly.

3:37-3:55 — Why this is reusable
- Same GOC primitives serve POIEX problem-solving and an internal method lane decision intelligence via
  domain adapters.
- Competition build is the first vertical slice of a reusable governed orchestration core.

3:55-4:00 — Close
- "Agents can propose. Evidence and authority decide. Every action can be replayed."

## Never claim in video unless evidenced

- production security certification
- calibrated win probability
- real industrial-control integration
- Firestore/Cloud Run validation before the deployed rerun
- inherited validation from proprietary internal source lanes (not included; see PRE_EXISTING_WORK_DISCLOSURE.md)
