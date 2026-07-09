# Pre-Live Audit — Deferred items (design-staged)

These findings are large or research-scope: responsibly building them on a live-money
order path needs its own design + review cycle, not a one-shot autonomous edit. Each is
specced here so implementation can start cleanly. The 21 tractable findings are already
fixed and committed (see `audit-fix-tracker.md`).

---

## H13 — No persisted order journal (in-flight state is process-memory only)

**Problem.** `_inflight` / `_pending_entries` / `order_fail_streak` / `last_entry_bar` live
only in `LiveBroker` instance dicts, wiped on every restart. An order placed just before a
crash — outcome unknown — is unrecoverable: no exchange-side lookup by the `pt-bot` tag, no
persisted record. C3/C8/H4/H8 hardened the *in-process* lifecycle; H13 is the *across-restart*
gap.

**Design.**
1. New table `order_journal`: `id, order_id, tradingsymbol, instrument_key, side, kind
   (options|equity), qty, intent (ENTRY|EXIT), context_json, status (WORKING|TERMINAL),
   placed_at, resolved_at`.
2. Write-through: in `LiveBroker._execute` (or its callers), persist a `WORKING` row *before*
   the poll, and mark it `TERMINAL` when `_actual_fill` resolves (filled/dead). One row per
   real order — options + equity, entries + exits.
3. Startup recovery: a `recover_journal()` that loads every `WORKING` row, re-queries
   `client.status(order_id)`, and routes it through the existing adoption/cancel logic
   (`adopt_pending_entries` for late fills; drop dead orders). Rebuilds `_inflight` /
   `_pending_entries` from the journal so a restart resumes mid-flight instead of forgetting.
4. Belt-and-suspenders: a Kite `orders()` sweep filtered by `tag == pt-bot` to catch orders
   the journal missed (e.g. a crash between placement and the journal write) — order the
   journal write *before* placement to shrink that window.

**Tests.** journal row written on place + marked terminal on fill; a `WORKING` row for a
since-filled order is adopted on recovery; a dead order is dropped; a tagged Kite order with
no journal row is surfaced.

**Effort:** large (schema + migration + write-through at ~4 sites + recovery + tests).
**Risk if unbuilt:** a crash in the ~10s order-poll window leaves an unrecoverable in-flight
order. Mitigated today by exchange-side GTT/SL-M backstops on *booked* positions and by C3's
in-process adoption — but not across a restart.

---

## H16 — Partial equity (MIS) close leaves the remainder unprotected + mis-books P&L

**Problem.** `close_equity_position` cancels the SL-M stop for the full qty (H4 now persists
that), then on a partial fill logs + records `_inflight` and returns — the unsold shares have
no stop, and the ledger still shows full qty, so the orphan reconciler later books the *full*
original qty at a stale mark (wrong P&L, remainder lost). The options path handles this
(`book_partial_close` + re-place GTT); equity does not.

**Why it isn't a quick mirror.** `book_partial_close` computes gross as
`(exit − entry) × qty` — the options/long formula, wrong for an MIS **short** (`(entry − exit)
× qty`) and it doesn't model MIS margin release. And re-protecting the remainder *requires*
first shrinking `pos.qty` (an SL-M for more than is held would oversell), so booking and
re-protection are coupled — you can't safely do one without the other.

**Design.**
1. `book_partial_close_equity(pos, qty, exit_price, reason, now)`: direction-aware gross
   (LONG `(exit−entry)·qty`, SHORT `(entry−exit)·qty`), proportional entry-cost/charges split
   (mirror `book_partial_close`'s exact-invariant split), MIS margin released proportionally —
   modelled on the *full* `super().close_equity_position` math.
2. In the partial branch of the live `close_equity_position`: call it for `filled`, then
   `_place_equity_stop(pos)` on the now-shrunk remainder.
3. Assert the cash invariant holds to the paisa across a partial (the dry-run's guarantee).

**Effort:** medium (delicate real-money accounting — needs the full-close margin math traced
and a paisa-exact invariant test). **Interim mitigation now in place:** H10's ledger-drift
alarm will *detect* the drift a mis-booked partial causes, and C4 makes the reconciler act
only on a reliable account read.

---

## C6 — Backtest models the underlying, not option premium (the only thing live trades)

**Problem (roadmap #1).** The sweep runs the strategy on the underlying's OHLC; live buys a
~0.5-delta CE/PE with a −35%/+60% premium stop/target and a ratcheting trail. Theta decay,
IV crush, convexity, and spread are unmodelled, so a spot-derived "edge" is not evidence of a
tradeable options edge.

**Design (synthetic-premium backtester).**
1. For each underlying bar, synthesize the ATM(±) option premium with Black-Scholes
   (`options/pricing.py` already exists): inputs = spot, strike (nearest to target delta),
   time-to-expiry decremented per bar, an IV estimate (start with realized-vol proxy or a
   flat term structure; later, a fitted surface).
2. Re-run entries/exits on the *synthetic premium series* with the live −35%/+60% + ratchet
   rules, netting the real charge stack + a modelled bid/ask spread (e.g. `max_spread_pct`).
3. Model theta explicitly (premium decays even on a flat spot) and roll/expire at DTE cutoff.
4. Report both spot-edge and premium-edge so promotion decisions see the gap.

**Effort:** large (a second backtest engine path). **Value:** the highest-leverage validity
fix — without it, backtest returns don't predict live P&L. Aligns with the existing
`improvement-roadmap-2026-07` memo.

---

## H2 — Live trailing stop ≠ the backtest-validated ratchet

**Problem.** The backtest validates `backtest/ratchet.py` (ATR stop → chandelier → MFE floor,
a Pine v4 port). Live uses `engine/exit_monitor.trailing_stop` — a fixed percent-of-entry
step-lock on the *premium*, a disjoint state machine on a different quantity. So the
trade-management the strategy was "proven" with is not what runs live.

**Design.** Two coherent options:
- **(A) Unify on the validated ratchet:** port `RatchetState` into the live risk loop so live
  exits use the same ATR/chandelier/MFE machine (on the underlying, mapping to the premium
  stop). Preferred — makes the backtest predictive of live behavior.
- **(B) Validate the live logic:** add the live percent-step-lock as a selectable overlay in
  the backtester and only promote strategies backtested with the *same* exit they'll run live.
Either way: one exit state machine, used in both places. Pairs naturally with C6 (both operate
on premium).

**Effort:** medium–large. **Risk:** live risk-management has no validated track record.

---

## H9 — No walk-forward / out-of-sample gate; `min_trades=1` is promotable

**Problem.** `start_sweep` scores every (instrument × interval × strategy) cell on one shared
window with no train/test split; `/results` filters only on `min_trades ≥ 1`. Across a
600-cell grid, noise alone yields high-Sharpe cells, and a single lucky trade can top the sort
and be promoted.

**Design.**
1. Split each series into in-sample (train) and out-of-sample (holdout); score both; expose
   both in `BacktestResult`.
2. Promotion gate: require OOS trades ≥ N (e.g. 20), positive OOS expectancy, and IS↔OOS
   consistency (no blow-up on holdout).
3. Raise the default `min_trades` and add a UI "insufficient sample / no OOS" badge so a
   1-trade cell can never look promotable.
4. Optional: a simple multiple-comparisons caution (e.g. flag the top cells as needing
   independent confirmation given the grid size).

**Effort:** medium. **Value:** stops in-sample cherry-picking from reaching the live universe.

---

## P1 — Shared broker session, no per-operation isolation *(substantially resolved)*

The verifier rated P1 PLAUSIBLE and, on tracing, **refuted the dirty-serve corruption
mechanics** (SQLAlchemy 2.0 deactivates a failed transaction → `PendingRollbackError`, it does
not serve stale data). The real residual it named — *no rollback anywhere* — is **fixed by
H3** (both loop iterations now roll back on exception), and lock contention that triggers it is
reduced by **P2** (explicit `busy_timeout`). A full move to per-request scoped sessions is a
larger refactor the verifier did not deem necessary given the single `asyncio.Lock`
serialization; leaving it as a future cleanup, not a live-safety gap.
