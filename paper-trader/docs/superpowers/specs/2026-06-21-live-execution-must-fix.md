# Live-Execution — Must-Fix Before Real Money

**Date:** 2026-06-21 · **Updated:** 2026-06-22
**Status:** L1, L2, L3/L4, L5, L6 **CLOSED** (2026-06-22, test-first — see
"## RESOLVED" at the bottom). L8/L9/L11/L13 (MEDIUM/LOW) remain open. The original
OPEN findings are preserved below for context.

**Original status:** OPEN — these are gating items for Phase 3 (real-money execution)
**Scope:** `LiveBroker` / `OrderClient` / GTT / reconcile. **None of these bite in
paper mode today** (the default `PaperBroker` + `SafePaperKite` cannot place real
orders). They MUST be closed before `PT_EXECUTION=live` + `PT_LIVE_ACK` are ever
set. Do **not** auto-fix the live order path without owner sign-off — every change
here moves real capital.

> Found in the 2026-06-20/21 independent review. The candle/backtest **timestamp**
> bug (the "+5:30 / 8 pm trades") and the chart bugs were separate display issues
> and are **already fixed** (see `tests/test_timezone_epoch.py`). What remains
> below is the *order-execution* surface.

---

## CRITICAL — order lifecycle leaves untracked / mis-stated REAL positions

### L1 — A partial/timeout BUY creates a real, unmanaged position the bot doesn't record
- **Where:** `engine/live_broker.py` `open_position` (acts only on `res.status == "FILLED"`); `engine/order_executor.py` returns `PARTIAL` / `TIMEOUT`.
- **Trigger:** a market/limit BUY fills some lots, or fills right at the 30 s poll timeout. `execute_order` returns `PARTIAL`/`TIMEOUT`; `LiveBroker` returns `None` and writes **nothing** to the ledger.
- **Impact:** a **real long option position exists with no ledger row → no stop, no target, no trailing, no GTT**, and `reconcile_orphans` only books *closures* — it will never *adopt* this position. Silent, unbounded loss until noticed by hand.
- **Fix (needs sign-off):** after a non-FILLED open, query `client.status`/`account_positions`; if `filled_qty > 0`, record the **actual** partial position (real avg price + filled qty) AND place its GTT; alert. Add an "adopt partial" path.

### L2 — A partial/timeout SELL leaves the ledger long the full size → oversell risk
- **Where:** `engine/live_broker.py` `close_position` (returns `None` unless `FILLED`).
- **Trigger:** SELL of N fills part, then times out → `PARTIAL`; ledger still shows the full N open.
- **Impact:** next exit attempt SELLs the full N again → **oversell / naked short in the owner's account**; ledger drifts from reality.
- **Fix (needs sign-off):** on PARTIAL close, reduce ledger qty by `filled_qty`, re-place GTT for the remainder; on TIMEOUT, reconcile against `account_positions` before any re-send.

---

## HIGH

### L6 — GTT-vs-bot double-sell race
- **Where:** `live_broker.py` `close_position` cancels the GTT only *after* its SELL completes; the ownership check reads positions *before* the (up to 30 s) poll.
- **Trigger:** premium gaps down so the server-side GTT fires during the same window the risk loop sends its market SELL.
- **Impact:** both sells execute → **oversell into the owner's account**.
- **Fix:** cancel/disable the GTT **before** sending the close SELL (cancel-then-sell), and re-check account qty immediately pre-send.

### L3 / L4 — Exchange GTT not re-synced on manual-SL change or reinforcement
- **Where:** `update_stop_protection` (GTT modify) is called only from `_apply_trailing`. The manual SL/TP route (`routes.py set_position_sltp`) and `broker.reinforce_position` raise the stop but never sync the GTT.
- **Impact:** if the bot is down, the exchange backstop protects at the **stale, looser** stop — a bigger loss than the owner set.
- **Fix:** call `r.broker.update_stop_protection(pos, pos.last_premium)` after committing a new stop in both places. (Isolated; could be done with tests independent of the L1/L2 state-machine work.)

### L5 — Order poll holds the engine lock up to 30 s
- **Where:** `_risk_iteration`/`_signal_iteration` wrap the whole synchronous `execute_order` poll in `async with self._lock`.
- **Impact:** while one live order polls, the fast risk loop is fully blocked — no marks, no SL/TP firing on *any* other position for up to `timeout_seconds`.
- **Fix:** place under the lock, poll **without** it (or run the blocking poll in an executor); lower `timeout_seconds`.

### L10 — Order-client Kite token not refreshed mid-run
- **Where:** `broker_factory.py` sets the live order client's token once at construction; the daily token expires and is re-issued via the data provider each morning.
- **Impact:** across a day boundary every live order fails auth — worst case the bot **cannot SELL to exit** an open live position.
- **Fix:** share one token source / refresh the order client's token from the provider before each order (or rebuild the broker on re-auth).

---

## MEDIUM / LOW

- **L8** — `reconcile_orphans` books a phantom close from a **single** `positions()` read; a transient Kite feed glitch >60 s looks identical to a real exit. Require N consecutive observations (or confirm via order history) before booking.
- **L9** — `order_executor` only treats `COMPLETE/REJECTED/CANCELLED` as terminal; an unmapped terminal status polls to TIMEOUT and is misclassified. Log the raw status; reconcile on TIMEOUT.
- **L11** — `LiveBroker._notify` swallows all exceptions; a money-critical alert ("OPEN not filled", "GTT NOT placed") can be silently dropped. Log inside the `except`.
- **L13** — `evaluate_exit` fires `STOP_LOSS` on any `premium <= stop` including a transient `0.0`; consider a 1-tick sanity/debounce before a real market exit.
- **L7 (engine clock)** — `KiteProvider.now()` returns naive **host-local** time, but `market_hours` is hard-IST. The candle/trade *display* epochs are fixed, but the engine's daily-loss day-bucket, overnight square-off timing, and staleness day-boundary still key off `provider.now()`. **Correct today only because the host is IST**; on a UTC/cloud host these misfire. Fix: `KiteProvider.now()` → IST.

---

## Test gaps that give false confidence
- `test_live_broker.py` covers only `COMPLETE` and `REJECTED`. **No PARTIAL/TIMEOUT-through-the-broker test** — and `test_open_returns_none_and_records_nothing_when_not_filled` *asserts the L1 behavior as correct*. Re-point these once L1/L2 are fixed.
- No test for GTT-sync-on-manual-SL / on-reinforcement (L3/L4), the double-exit race (L6), token expiry (L10), or the orphan false-positive (L8).

## Rollout reminder (from the design spec)
Even after these are fixed: shadow mode first (compute + margin-check the order, still paper-fill) → 1-lot single-instrument pilot with kill switch + daily-loss halt → expand only after N clean reconciliation sessions.

---

## RESOLVED — 2026-06-22 (test-first; all paper-tested, 313 tests green)

All fixes are gated behind `PT_EXECUTION=live` (conftest forces it OFF in the suite),
so none change paper behavior. Each was driven RED→GREEN.

- **L1 — partial/late BUY adopted** (`live_broker.py` `open_position` + new `_actual_fill`).
  A non-FILLED open now books the **actual filled qty at the real avg price** and places
  its GTT instead of returning None; a TIMEOUT re-queries the order once to catch a
  buzzer fill. Only a genuine zero-fill (REJECTED / nothing filled) records nothing.
  `pos.qty` = real fill, `pos.lot_size` = the true lot.
- **L2 — partial/late SELL never oversells** (`live_broker.py` `close_position` +
  new `PaperBroker.book_partial_close`). A partial sell books only the sold slice,
  shrinks the open position by that qty (entry cost split proportionally, cash
  invariant kept exact), and re-places a GTT on the remainder. A TIMEOUT re-queries
  to book a late fill so the ledger never overstates the position.
- **L3/L4 — GTT re-synced on every stop change.** `broker.reinforce_position` and the
  manual-SL route (`routes.py set_position_sltp`) now call `update_stop_protection`
  after committing the new stop, so the exchange backstop tracks the tightened stop.
- **L5 — order poll no longer freezes the loop / holds the lock long.**
  `order_poll_seconds`/`order_timeout_seconds` are settings (live default **10s**, was a
  hardcoded 30s), wired through `broker_factory`. `_risk_iteration` offloads the
  blocking pass via `asyncio.to_thread`, keeping WS/heartbeats/signal-scheduler alive
  (the lock is still held across the offload, so the single DB session stays
  single-threaded-at-a-time).
- **L6 — GTT-vs-bot double-sell race closed.** `close_position` now **cancels the GTT
  before** sending the SELL (cancel-then-sell) and **re-checks account qty immediately
  pre-send** — if the GTT already fired (account no longer backs us) it sends no order.
  On a non-fill after cancelling, the GTT is **re-placed** so the position is never
  left unprotected.

### Honest residuals (narrowed, not eliminated — review before unsupervised live)
- **L2/L1 TIMEOUT, order still working:** if a SELL times out while genuinely still
  OPEN (not filled, not terminal), the next risk tick can re-send — the ownership
  guard only blocks the re-send once a fill has actually dropped account qty. A truly
  concurrent double-fill is now bounded by the 10s timeout + fast MARKET fills, but a
  full fix needs tracking the outstanding order id and cancelling/awaiting it before
  any re-send. Same shape on the BUY side: a fill landing after the single re-query
  is still untracked until an adopt-open reconciler exists (today `reconcile_orphans`
  books only closures).
- **L5 intra-pass serialism:** within one risk pass, positions are still marked
  serially, so a slow close on position A delays B *within that pass* (the event loop
  and the next iteration are no longer blocked). Fine for the 1-lot single-instrument
  pilot; revisit per-position close parallelism before running many concurrent names.

## Test gaps — now closed
`test_live_broker.py` covers PARTIAL and TIMEOUT through the broker (open + close),
GTT-resync on reinforcement, the cancel-then-sell ordering, the pre-send abort when
the GTT fired, and backstop restore on a failed close. `test_position_sltp.py` covers
manual-SL GTT resync. `test_broker_factory.py` covers the bounded/configurable timeout.
`test_engine_loops.py` covers the event-loop-stays-responsive property. The old
`test_open_returns_none_and_records_nothing_when_not_filled` still holds (it asserts
the REJECTED zero-fill case, which is still correct).
