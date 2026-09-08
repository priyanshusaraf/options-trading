# Confirmed backend risk register

## Priority register

| ID | Risk | Evidence status | User/business impact | Reachability | Release | Owner/gate |
| --- | --- | --- | --- | --- | --- | --- |
| CHAT2-R01 | Full-history qualification contaminates OOS | Confirmed RED twice, including current tree | Invalid independent-evidence claim can guide research admission | Current legacy research | V0 blocker | New research-validity correction capsule |
| CHAT2-R02 | Legacy sweep reachable under V0 | Confirmed policy RED twice | V0 research can bypass canonical point-in-time dataset authority | Authenticated API policy | V0 blocker | Release-profile/backtest boundary capsule |
| CHAT2-R03 | Published graph route omits ResourcePlan | Confirmed structural RED twice | Work/evidence may violate accepted resource bounds | Current canonical graph route | V0 blocker | Existing F03 named owner, protected input |
| CHAT2-R04 | Experiment ID collision reuses wrong recipe | Confirmed forced collision twice | Immutable run provenance can name wrong spec | Current research persistence; natural collision very unlikely | V0 hardening | Identity/persistence capsule; migration review if address changes |
| CHAT2-R05 | Cancel/complete yields CANCELLED full fill | Confirmed reducer RED twice | Position and user/operator truth can contradict a real fill | Code present, V0 execution denied | V1 critical | Execution/reconciliation capsule and critical review |
| CHAT2-R06 | Claim-race test does not terminate | Confirmed 45-second timeout at Chat 1 closure | Job safety/takeover evidence unavailable | Current dirty test path; runtime cause unknown | V0 evidence blocker | Active concurrency owner; PostgreSQL proof required |
| CHAT2-R07 | Completed observation can predate availability | Confirmed constructor RED; current Q03 contained | Future look-ahead or false causality | Future producer/consumer | Provider-capture blocker | Producer inventory and market-truth capsule |
| CHAT2-R08 | Optimization/DSR/PBO reconstruction under-proved | Static omissions plus incomplete durable matrix | Research evidence may not reproduce after evolution | Current robustness results | V0 hardening | Research-evidence capsule |
| CHAT2-R09 | IID bootstrap confidence assumption unstated | Static code and primary-method review | Confidence bound may be too narrow for dependent trades | Current qualification/validation | V0 label/test gap | Statistical method owner |
| CHAT2-R10 | Connected socket revocation unspecified | Static code; V0 route denied | Future private frames after revocation | Future execution profile | V1 security | Owner latency decision + auth/session capsule |
| CHAT2-R11 | P0/P1 workload isolation unmeasured | Static topology only | Future research load could delay protection/reconciliation | Not V0 reachable | V1 measurement | Resource-plan/runtime owner |
| CHAT2-R12 | Restore/reconstruction unproved on supported PostgreSQL | Missing environment evidence | Recovery may lose lineage or leave ambiguous state | Release/deployment boundary | V0 deployability/V1 | Deployability capsule and owner RPO/RTO |

## Current validation conflicts

- `test_paper_entry_remains_unlinked` failed during Chat 1 because inherited
  `broker.py` now creates a paper intent. The active convergence task must decide the
  intended lifecycle; Chat 2 does not change the test or code.
- The first SQLite backtest claim-race case timed out after inherited concurrency
  edits. An earlier shadow run passed before those edits. Current evidence controls.
- Chat 2’s first combined characterization command lacked two sibling fixtures.
  The explicit-conftest rerun confirmed both product failures; the harness error is
  not a product finding.

## Risk nonclaims

- No natural SHA-256 collision was observed; the forced collision proves missing
  byte equality, not practical cryptographic weakness.
- No current Q03 look-ahead from `available_at < completed_at` was observed.
- No live provider, broker, credential, customer, VPS or production database was
  accessed.
- No current cross-tenant leak was reproduced by this packet.
- No profitability, production capacity, legal data right or deployability claim is
  made.
