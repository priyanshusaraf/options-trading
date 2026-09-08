Reference: [section index](../0012-execution-state-ownership.md). Read with its scope; this is not a new assignment.

## 5. Owner gates

Explicit approval is required before any change that lets IR output place, modify, cancel,
route or size orders; influence positions or accounting; alter exits, reconciliation or risk
controls; become authoritative in paper, shadow-to-order or live execution; or change
live-money behaviour. In code, all of those begin at one line: moving `SOURCE_IR_GRAPH` out
of `SHADOW` in `AUTHORITY_BY_SOURCE`.

## 6. L1.3B — the execution book

### 6.1 The inventory, before any semantics changed

Every read and write of money state, and whether the execution mode was explicit, implicit,
absent or inconsistent **before** this slice.

| Money state | Where | Mode/book status before |
|---|---|---|
| open positions (`positions`) | `PaperBroker.open_positions` / `position_for` — the chokepoint for ~35 call sites in `runner.py`, `routes.py`, `live_broker.py` | **absent.** `mode` was written on every row and read by no position query. The docstring stated the assumption out loud: "at most ONE open position per instrument across the whole system" |
| closed trades (`trades`) | `analytics.py` (11 queries), `runner._today_net_realized`, `_today_round_trips`, `routes.py:96`, `routes.py:958` | **inconsistent.** Exactly two of fourteen filtered: `recent_trades(mode=…)` (optional) and the bot-vs-you feed (`mode == 'live'`, correct). The daily-loss breaker and the round-trip cap counted both books |
| cash + realised P&L (`capital_state`) | `broker.capital()`, `analytics.capital_dict`/`account_pnl`, `session.py` seed + repair, `scripts/reconcile_ledger.py` | **unrepresentable.** One row, `id=1`, hardcoded at six sites, mutated in place |
| equity curve (`equity_snapshots`) | written once in `broker.snapshot()`, read by `analytics.equity_curve` | **absent.** No discriminator column at all |
| orders / intents / fills (`order_journal`) | `LiveBroker` only (write, `recover_journal`, orphan scan) + `ledger/detect.py` | **implicit but sound** — the paper broker has no order client and never writes a row |
| account totals (`daily_account_snapshot`) | `routes.py:96` | cross-book by nature: it records the *real Kite account*, not a book |
| ledger reconciliation / drift | `should_reanchor(is_live=…)`, `plan_reanchor` | **explicit at the decision, absent at the data** — it branched on `is_live` and then read the single shared `capital_state` |
| restart / open-position reconstruction | `broker.open_positions()` via the risk lane; `_repair_open_position_lot_sizes` | **absent** |
| square-off and exits | `runner.py` lines 1796/1825/1863/1880/1909/2047 — all `broker.open_positions()` | **absent** |
| risk exposure / deployable capital | `runner.deployable_cash`, `_open_unrealized`, `capital.deployable_capital` | **absent** |
| analytics + journal/review feeds | `analytics.py`, `ledger/` lane | intentionally cross-book, but nowhere stated |

### 6.2 Is `mode` sufficient?

**The value is right; its reach was not.** `mode ∈ {paper, live}` already names the book on
the two tables that matter most, and this slice adds no second abstraction — the book *is*
the execution mode, given one name and one resolver.

What `mode` alone could not represent, precisely: invariants 3 and 4 are not query
predicates. `capital_state.cash` and `capital_state.realized_pnl` are **aggregates mutated in
place on a single row**, so there is no `WHERE` clause to add — a paper fill would debit the
live ledger's cash no matter how many reads were filtered. `equity_snapshots` had no
discriminator to filter on either. Those two tables are why the slice includes a migration
rather than only call-site changes.

### 6.3 Final semantics per query

Isolated (the book predicate is now mandatory, not opt-in): position lookup, open positions,
exit and square-off scans, restart reconstruction, deployable capital, the daily-loss breaker,
the round-trip cap, `capital_dict`, `account_pnl`, the equity curve, re-anchor and ledger
drift.

Deliberately cross-book, and now documented as such rather than merely unfiltered:
`universe_resolver`'s "is this instrument in use" guard (removing an instrument with *any*
open position is the hazard, whichever book holds it), the reporting surfaces in
`analytics.py` and `/api/analytics/*`, the journal/review feeds, and
`daily_account_snapshot`, which describes the real account rather than a book.

### 6.4 The one tension, resolved deliberately

`open_positions` previously argued for unscoped reads: a read that *misses* a position is a
position nobody marks, ratchets or exits, and hard invariant 2 says not getting out is worse
than any other failure. Book scoping makes that miss possible.

It is still correct, because the paper broker cannot exit a live position — it holds no order
client. "Exiting" one would write a close into the ledger while the contract stayed open at
Zerodha, turning a visible orphan into an invisible one. So the scope is enforced and the
residual is made **loud** instead: `foreign_book_positions()` reports open rows belonging to
the other book, surfaced at startup and on `/api/health`.

### 6.5 Authority is now a (source, mode) pair

`GRANTS` moves from `(source, authority)` to `(source, execution_mode, authority)`.
`(ir_graph, paper)` **is not granted** and `(ir_graph, live)` **is not granted**; IR remains
refused in every mode. An unknown, missing or malformed mode resolves to `live` — the safe
direction — and never to paper, so a misconfigured process fails closed rather than inheriting
whatever paper would permit.

The managed-shadow object is untouched. `ir_shadow_deployments` is not widened into a paper
deployment table: it is an observer attached to a deployment, with no capital, no orders, no
arm state and no authority. Paper authority, if ever granted, flows through the canonical
Deployment/execution-binding path — the subject of the next design, not this slice.
