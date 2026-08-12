# Task 5B report — closed authorization and USER/research IDOR boundaries

## Delivered scope

- Replaced permissive action checks with a closed role-and-scope vocabulary. Unknown actions and unowned USER/research resources deny.
- Added request action classification for both `/api` and `/api/v1`, with durable user principals denied on legacy process-global runner endpoints until Task 5C scopes them structurally.
- Kept existing owner-only connection collection behavior intact; it remains Task 5C scope.
- Confirmed project/graph access uses organization predicates in SQL before materializing an object. Cross-tenant and absent graph-draft probes have the same public 404 response.
- Bound runtime configuration reads and writes to `owner_id_for(principal)`. The live runner refreshes only for its own legacy owner.
- Converted review note, saved-view, and snapshot creator attribution to the resolved `principal.user_id` for durable sessions. Historic `owner` values remain valid.
- Restricted durable users to revising/deleting their own review notes and saved views. Cross-user and foreign artifacts resolve as not found.
- Added migration `0029` for the creator envelope. It preserves legacy bytes, restores snapshot triggers, recovers an interrupted SQLite table recreation only with a durable payload proof, and refuses unproven/tampered temporary tables.
- Versioned candidate decision evidence: schema v1 remains restricted to historic `actor: owner`; user-attributed decisions write schema v2 with the deciding user id.

## Tests and evidence

- New `tests/test_cross_tenant_idor.py` uses real durable-session principals across two organizations and both API mounts. It covers closed policy behavior, role/scope intersection, SQL ownership predicates, foreign-equals-absent behavior, create input scope rejection, and review creator attribution.
- Focused post-review gate: `73 passed` across migration retry/refusal, actor projections, candidate evidence, review routes/state, and IDOR coverage.
- Independent adversarial review: PASS. The reviewer ran a fresh focused gate with `230 passed`, plus `compileall` and `git diff --check` exit 0.

## Deferred scope

- Task 5C owns money runner/ledger, credential/account controls, and conversion of legacy process-global runner endpoints.
- Task 6 owns WebSocket fan-out and answer-changing cache partitioning.
- No frontend files changed. The protected broker/provider files were neither edited nor staged by this task.
