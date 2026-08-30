# GOC Planner Boundary

Status: `LOCAL_CONTRACT_IMPLEMENTED / ADK_NOT_CREDENTIAL_EXECUTED`

The probabilistic planner is explicitly outside the trusted execution base.
`PlannerProposal` may contain only a proposed action type, target identifier,
parameters and rationale. It cannot mint:

- AuthorityLease or epoch
- target hash/version authority
- evidence IDs
- receipts
- gate decisions

`proposal_to_intent()` re-resolves the proposal against a trusted current
`MaterialTarget` and binds the current target hash outside the model. Target
substitution is rejected before an ActionIntent is created.

The ADK scaffold still has `tools=[]`. Static tests also assert that `app/agent.py`
does not import the deterministic ControlPlane or synthetic executor.

Truth ceiling:

`PLANNER_PROPOSAL != AUTHORIZED_INTENT`
`ADK_STATIC_BOUNDARY_PASS != ADK_RUNTIME_EVIDENCE`
