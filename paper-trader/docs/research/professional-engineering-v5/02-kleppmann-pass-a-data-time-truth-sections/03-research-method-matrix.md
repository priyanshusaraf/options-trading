Reference: [section index](../02-KLEPPMANN-PASS-A-DATA-TIME-TRUTH.md). Read with its scope; this is not a new assignment.

## Research-method matrix

| Method | Actual implementation | Audit result |
| --- | --- | --- |
| Fixed-parameter temporal folds | Full causal signal frame split into contiguous windows; each window starts with no carried position | Exploratory temporal stability, not pristine OOS after full-history qualification |
| Nested optimization | Expanding IS selects one candidate per fold; next disjoint slice evaluates it; complete trials persist | Inner parameter selection is structured, but the outer full-history qualification already contaminates the path |
| PBO | CSCV over bounded contiguous performance blocks | Implemented and fail-closed on absent matrix; assumptions need broader method review |
| DSR | Uses trial count and cross-trial Sharpe variance; sibling search count is caller-supplied | Implemented; correctness depends on complete sibling-trial attribution |
| Bootstrap confidence | Seeded IID resampling of per-trade net P&L | Reproducible but dependence assumption unrecorded |
| Monte Carlo | No research Monte Carlo implementation found | N/A in current code; must remain visibly unavailable |
| Costs | Corrected effective schedule, base/stress slippage, capital, sizing, and charge address enter recipe | Strong identity; real contract-note/historical schedule coverage remains outside evidence |
| Reproduction | Immutable recipe, dataset content hash, build, seed, versions, and terminal evidence | Broken on spec-ID collision; otherwise strong for tested inputs |
| Search reconstruction | Trial params/objective/count/selection persist; search-space document, order, `is_sharpe`, and PBO matrix do not | PARTIAL; exact-build replay is required and not proven across migration |

## Rejected responses

- No Kafka, Samza, CDC platform, Redis authority, workflow engine, or universal event sourcing.
- No repository-wide schema or hash rewrite in Chat 1.
- No claim that a DDIA table-of-contents heading supplies a Strategy OS design.
- No formal proof project before the exact state machine and failure property are named.
- No synthetic historical instrument truth from today's provider dump.
- No statistical threshold increase as a substitute for OOS separation.

## Evidence and limits

Pass A inspected current code and existing tests but did not rerun broad product suites. The three characterization tests are deliberately red and live only under this audit directory. They prove their exact failure branches, not the safety of unrelated consumers.

Raw source, crawl, page, figure, symbol-map, and command evidence is under `.agent/runs/kleppmann-reaudit-v5/`. No provider connection, paid data, live runtime, schema migration, dependency, order, money, or deployment action occurred.
