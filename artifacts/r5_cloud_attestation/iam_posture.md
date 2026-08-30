# R5-03 — PUBLIC_ACCESS != EXECUTION_AUTHORITY (deployed IAM posture)

## Architecture enforced
PUBLIC/SANDBOX DEMO -> ADVISORY AGENT FLEET -> IDENTITY+AUTHORITY+TARGET+POLICY GATES -> PRIVILEGE-BOUND GOC -> SYNTHETIC EXECUTOR

## Before (V0.10.5)
- poiex-agent-fleet: run.invoker = [allUsers, user:owner]
- poiex-goc-control: run.invoker = [allUsers, user:owner]   <-- privileged plane publicly invocable (DEFECT)

## After (R5)
- poiex-agent-fleet (advisory, tools=[]): run.invoker = [allUsers, user:owner]  -> public DEMO surface, intended. Cannot mint identity/authority/target/receipt/execution.
- poiex-goc-control (privileged GOC): run.invoker = [user:owner, serviceAccount:poiex-goc-runtime]  -> allUsers REMOVED. Anonymous = HTTP 403. Authenticated authorized identity = 200 + governed decisions.

## Falsifier verdicts (deployed, see deployed_falsifier_matrix.json)
PUBLIC-01 anonymous access ......... 403  PASS
PUBLIC-02 authority mint attempt ... forged fields inert; authority server-owned  PASS
PUBLIC-03 forged/revoked lease ..... BLOCK AUTHORITY_REVOKED  PASS
PUBLIC-04 direct executor call ..... 404 (no executor surface)  PASS
PUBLIC-05 forged target ............ REJECTED_BEFORE_INTENT  PASS
PUBLIC-06 planner escalation ....... REJECTED_BEFORE_INTENT  PASS

No public request can by itself mint a lease, authority, target certificate or privileged execution.
