Reference: [section index](../CANONICAL-BENCHMARKS-AND-ADVERSARIAL-TESTS.md). Read with its scope; this is not a new assignment.

## Cross-benchmark adversarial matrix

| Failure hypothesis | Risk | Required direct proof |
| --- | --- | --- |
| Current membership/reference/event data leaks into historical research | Critical | Freeze point-in-time snapshots, mutate current facts, prove old decisions unchanged; omit one candidate and make the complete-population guard fail. |
| Two actors reserve the same capital | Critical | Independent PostgreSQL sessions race one account; one deterministic batch wins; remove account lock/fence and make regression fail. |
| Stale thesis/proposal approval executes | Critical | Mutate each material address and advance TTL; revalidation refuses before order/provider side effect. |
| Signal provider and broker price are semantically incompatible | Critical | Compare bid/ask-suitable fields; mutate mapping/age/skew/divergence and prove entry block plus exit availability. |
| Vendor chart state becomes executable identity | Critical | Change layout/style/blob while normalized semantics stay fixed; strategy hash must not change. Change normalized geometry; thesis revision must change. |
| Branch enters before data readiness | Critical | Delay subscription/lookback/provider recovery; entry refuses until `DATA_READY`; remove barrier and kill direct regression. |
| Open position follows new Strategy/thesis/Universe/selector revision | Critical | Publish successors while position is open; management remains on creating revisions and exact held contract. |
| Cross-tenant artifact/cache/socket access | Critical | Direct-object tests for every new object and revoked membership on existing socket. |
| Restart loses hot state and widens authority | Critical | Flush process/hot store; durable facts rehydrate; new entries block; exits and reconciliation remain. |
| Research fabricates absent OI/depth/chart history | Critical | Remove historical capability/data; eligibility becomes unsupported or prospective recording, never synthetic data. |
| Ranking or temporal routing is nondeterministic | Important | Permute input order/process scheduling; exact rank/ties/branch receipts remain stable. |
| Resource plan hides demand behind components/conditionals | Important | Expand lowered leaves and physical subscriptions; first over-limit member refuses; ordinary conditional cannot remove required temporal input. |
| Frontend reports transport as healthy/live | Important | Socket open with unauthenticated/stale provider; UI shows exact Unknown/auth/subscription/freshness state, never LIVE. |

## Test cadence

- Focused direct tests during each subphase.
- Subsystem suite at integrated contracts.
- PostgreSQL/migration/recovery and browser evidence at phase gates.
- Broad backend/research/frontend/build/smoke at Phase 13.
- One integrated independent review per Critical slice and final release.
- No arbitrary test-count or coverage target. Every new test names the realistic failure hypothesis above or another explicit product risk.
