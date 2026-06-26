# Market Protection + Final Live-Execution Residuals — Design

**Date:** 2026-06-26
**Branch:** `feat/live-cockpit`
**Status:** Approved — implement test-first.
**Scope:** `KiteOrderClient` / `LiveBroker` / `order_executor` / `exit_monitor` / `config`.
All changes are gated behind `PT_EXECUTION=live` + `PT_LIVE_ACK` (conftest forces
these OFF in tests) so **paper-mode behavior is unchanged**. This closes the last
codeable items before a supervised 1-lot live pilot.

---

## Background / why now

Going live needs two things this pass delivers:

1. **Market protection is now mandatory.** Since **1 April 2026** (in effect today),
   Kite Connect **rejects any MARKET / SL-M order placed via API without non-zero
   market protection — across all segments, MCX included**. `market_protection=0`
   or unset → rejected; `-1` → automatic exchange-guideline protection; `>0..100`
   → an explicit cap %. It only affects MARKET/SL-M (LIMIT/SL untouched) and
   converts the market order into a band-capped limit (still subject to exchange
   LPP; a gap beyond the band can reject — the same limitation our GTT already has).
   The owner remembered this as a *commodity* problem (MCX is where it first bit),
   but the rule is now universal: **without it the bot cannot place a single market
   order on any segment** — a NIFTY market entry bounces just like a GOLDM one.
   Sources: Kite Connect orders API docs; Zerodha SEBI-algo-rules + market-protection
   forum threads.

2. **Four open residuals** (L8/L9/L11/L13) from
   `2026-06-21-live-execution-must-fix.md` plus the bigger **outstanding-order**
   residual are all codeable & testable now without a live account.

Out of scope (needs the live account, not codeable today): shadow-run calibration of
`account_equity(net)` against the real margins API, then the supervised 1-lot pilot.

---

## Items

### 1. Market protection on every MARKET order (mandatory)

- **Setting:** `market_protection_pct: float = -1.0` in `config.py` (adaptive-routing
  block). `-1` = automatic exchange guideline (compliant default, self-adjusts per
  segment, lets the order through). Owner may override to an explicit `0 < pct <= 100`.
- **Wiring:** `broker_factory.make_broker` passes it into
  `KiteOrderClient(..., market_protection=s.market_protection_pct)`.
- **Behavior:** `KiteOrderClient.place()` — when `req.order_type == "MARKET"`, set
  `kw["market_protection"] = mp` where `mp = self.market_protection if self.market_protection else -1.0`
  (a configured `0` is coerced to `-1` so we can **never** send an unprotected market
  order). LIMIT orders are not given the parameter. Applies to **entries and
  protective exits, every segment** (commodities included).
- **GTT untouched:** the GTT-triggered order is a LIMIT (`stop_gtt_params`), so it
  needs no market protection.
- **Default decision:** one `-1` setting for both directions (YAGNI). A protective
  exit ideally wants a *wide* band; `-1` uses the exchange's own band (the GTT
  backstop covers a violent gap). Split entry/exit protection only if the pilot shows
  exits being capped.
- **Tests** (`test_kite_order_client.py`): MARKET BUY carries `market_protection=-1`
  by default; a configured `%` is passed through; a configured `0` is coerced to `-1`;
  MARKET SELL (commodity exit) carries it too; **LIMIT carries no `market_protection`**;
  GTT placement is unaffected.

### 2. Outstanding-order tracking (eliminate the timed-out-but-still-working double-send)

- **Invariant:** *at most one working bot order per contract at any time.*
- **Client:** add `KiteOrderClient.cancel(order_id)` → `kite.cancel_order(variety, order_id)`
  (the `order.cancel` route is already in `LIVE_ALLOWED_ROUTES`).
- **Broker state:** `LiveBroker._inflight: dict[str, str]` maps `tradingsymbol → order_id`
  for an order whose outcome is **unknown** — a TIMEOUT (no fill) **or an ERROR after
  submission** (e.g. the status poll failed) — and that may therefore still be working.
  - Recorded when `_execute` yields TIMEOUT or an ERROR carrying an order id (an ERROR
    with no order id means nothing reached the exchange — not recorded).
  - Any terminal/filled outcome clears it for that symbol.
- **Guard before placing:** `open_position` / `close_position` call
  `_ensure_no_inflight(symbol)` first. If an id is recorded, query its status:
  terminal → reconcile (book a late fill if any) & clear; still working → **cancel it
  and confirm cancellation** (or one re-query to terminal) before placing the new
  order. Result: never two live orders for the same contract.
- **Tests** (`test_live_broker.py`): a TIMEOUT-still-working open records inflight; the
  next tick cancels it before re-placing; a TIMEOUT that the re-query shows filled
  does **not** record inflight (it is adopted as in L1); cancel is confirmed before the
  re-place.

### 3. L8 — orphan confirmation (N consecutive reads)

- `reconcile_orphans` requires a position to read orphaned on **N consecutive passes**
  (`orphan_confirm_count: int = 2`) before booking closed. `LiveBroker._orphan_seen:
  dict[str, int]` keyed by `instrument_key`: increment when orphaned, **reset to 0**
  when backed (or no longer present as orphan), book only when `count >= N`, clear on
  booking. Kills the phantom close from a single feed glitch.
- **Tests** (`test_live_broker.py`): one orphan read books nothing; N consecutive reads
  book; an intervening backed read resets the counter.

### 4. L9 — terminal-status mapping

- `execute_order` currently maps only `COMPLETE/REJECTED/CANCELLED` and polls anything
  else until TIMEOUT. Fix: capture the **raw status** in `OrderResult.reason`; treat any
  status that is not in an explicit *working* set and not `COMPLETE` as
  **terminal-to-reconcile** (don't burn the whole timeout); recognise `REJECT*` spellings.
  Conservative: enumerate the known working/pending Kite statuses; an unknown status
  that is not working is surfaced (logged + carried) rather than silently TIMEOUT.
- **Tests** (`test_order_executor.py`): an unmapped terminal status is surfaced quickly
  with its raw text, not silently polled to TIMEOUT; known working statuses still poll.

### 5. L11 — notify logging

- `LiveBroker._notify` — log inside the `except` (with the dropped text) so a
  money-critical alert that fails to send is at least in the logs.
- **Tests** (`test_live_broker.py`): when the notifier raises, `_notify` logs an error
  and does not propagate.

### 6. L13 — stop debounce on a transient 0.0

- `evaluate_exit` won't fire a real market `STOP_LOSS` when `current_premium <= 0`
  (a missing/bad tick — an option can't trade at ≤0; a genuine deep loss is a small
  positive that still trips the stop). `max_stale_seconds` already gates *stale* marks;
  this gates a *fresh-but-bad* zero tick.
- **Tests** (`test_exit_monitor.py`): `current_premium=0.0` does **not** fire STOP_LOSS;
  `0.05 <= stop` still fires; TARGET/STRATEGY_EXIT paths unchanged.

---

## Risk / safety notes

- Every item is behind the live gate; paper mode and the 313-test baseline are
  unchanged except where a test asserted the old (now-fixed) behavior.
- Item 1 is the only item that is *required* for the bot to function live at all;
  the rest harden the order path.
- Residual after this pass: only the live-account shadow calibration + supervised
  1-lot pilot remain. Recommendation stands: **1-lot, single-instrument, supervised**
  first session.

## Rollout

Shadow/observe → 1-lot single-instrument pilot with kill switch + daily-loss halt →
expand after N clean reconciliation sessions.
