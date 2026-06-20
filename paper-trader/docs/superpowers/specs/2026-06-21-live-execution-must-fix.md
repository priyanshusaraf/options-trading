# Live-Execution — Must-Fix Before Real Money

**Date:** 2026-06-21
**Status:** OPEN — these are gating items for Phase 3 (real-money execution)
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
