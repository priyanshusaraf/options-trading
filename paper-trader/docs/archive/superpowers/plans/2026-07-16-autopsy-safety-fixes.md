# Plan: live-safety fixes from the 2026-07-15 VPS autopsy

**Date:** 2026-07-16 · **Status:** approved (owner: safety fixes jump the queue) ·
**Branch:** `feat/exits-journal` · **Author:** Fable 5 (architect) — Sonnet 5 implements, TDD

Source: multi-agent autopsy of the Jul 13–15 VPS journal + `vps-snapshots/2026-07-15/pt-snap-20260715.db`.
Findings R1 (critical), R2 (critical), R3 (high). Ranked report lives in the session workflow journal.

## Global constraints

- Work from `paper-trader/backend/`. TDD (test first, watch it fail, then code).
- Full suite green: `.venv/bin/python -m pytest`. Ledger invariant green:
  `.venv/bin/python scripts/dryrun.py 700`.
- The options path's behavior must not change except where a task explicitly says so.
- Every fix must emit a grep-able log marker (deploy verification on the VPS is
  marker-based — rsync tree + journalctl grep; there is no git on the VPS).
- New tunables go in `Settings` (`core/config.py`) and, if live-editable,
  `runtime_config` — per repo convention.
- One commit per task, message style matching `git log` (e.g. `fix(live): …`).

## Task 1 — per-instrument tick size on every exchange-stop price (R1)

**Evidence:** 2,437 "SL-M stop place failed" lines on Jul-15, all tick-size
rejections, only LT (tick 0.10, 1,820×) and MARUTI (tick 1.00, 617×). LT short ran
~2h51m with no exchange stop; MARUTI ran ~6× past its intended 1% stop (net −₹330,
−6.15%). Root cause: `app/engine/gtt.py:21` hardcodes `TICK_SIZE = 0.05`;
`app/engine/kite_order_client.py:109,120` round every SL-M trigger to that grid, and
`stop_gtt_params` (`gtt.py:35`) does the same for option GTTs.

**Required behavior:**
1. Every trigger/limit price sent to Zerodha (SL-M initial place, SL-M modify,
   the cancel+replace resync path, and GTT stop payloads) is rounded to the
   **instrument's real tick size**, sourced from the Kite instrument dump
   (`tick_size` column — the provider already loads the dump; cache lookups per
   session). Unknown symbol / mock provider → fall back to 0.05.
2. `round_to_tick` stays pure and keeps its `tick_size` parameter; fix the plumbing
   so callers pass the real tick. Design freedom on the mechanism (e.g. a
   `tick_source(tradingsymbol, exchange) -> float` callable injected into
   `KiteOrderClient`, wired from the provider in `live_broker` / broker factory) —
   but `modify_stop_order` must also land on the right grid (note: its current
   signature only has the order id; it may need the symbol or a pre-resolved tick).
3. Rounding must respect paise precision for ticks ≥ 1.0 (MARUTI: trigger must be a
   whole rupee; `round(..., 2)` on a 1.00 grid is exact — assert it).
4. On a successful re-place after a resync failure, log an explicit
   `SL-M resync recovered` marker (today recovery is silent — the autopsy could
   not confirm any recovery).

**Regression tests (must exist and fail before the fix):**
- tick 0.10 (LT-like): trigger 3837.4499… → placed trigger is a 0.10 multiple;
  a 0.05-only rounding (e.g. 3837.45) would be rejected — assert the exact value.
- tick 1.00 (MARUTI-like): trigger 12786.3 → 12786.0.
- default 0.05 unchanged for a standard symbol.
- modify/resync path uses the same grid as the initial place.
- unknown symbol falls back to 0.05.

## Task 2 — `intraday_leverage` becomes a binding notional cap (R2)

**Evidence:** all 7 Jul-15 instruments sized at margin/notional = exactly 5.0000
while every order's context recorded `intraday_leverage=2.5`. Not a broken fix:
`_intraday_margin_sizer` (`app/engine/runner.py:576-614`) correctly sizes qty to
consume `intraday_max_margin` (₹8k) of **real** Kite margin, and Zerodha genuinely
grants 5x MIS on these liquid names → ₹40k notional. `config.py:176` documents
`intraday_leverage` as "FALLBACK leverage estimate only". Owner intent: 2.5 was set
to halve risk; rupee risk per stop is therefore ~2× intended.

**Required behavior:**
1. In the live sizer (`_intraday_margin_sizer.sizer`), qty becomes
   `min(qty_for_margin(per_share, target_margin), equity_qty(target_margin, lev, cand.price))`
   — real margin still guards against broker rejection; `intraday_leverage` now
   **caps notional** at `target_margin × leverage`. Returned margin stays
   `qty × per_share` (the real margin actually blocked).
2. Fallback path (no quote / mock) unchanged: pure leverage model.
3. Update the `config.py` comment for `intraday_leverage`: it is now a binding
   notional cap AND the fallback estimate. It is already live-editable
   (`runtime_config.py:41`) — keep that.
4. Log marker on entries where the leverage cap binds (i.e. it reduced qty below
   the real-margin qty), e.g. `sized by leverage cap`, including both quantities.

**Tests:** with per-share margin implying 5x and lev=2.5 → leverage cap binds and
notional ≤ margin×2.5; with lev=10 → real-margin qty binds; fallback path scales
with lev; qty=0 edge (cap smaller than one share) doesn't crash the entry cycle.

## Task 3 — classify own-stop fills correctly in `reconcile_orphans` (R3)

**Evidence:** 4 of 8 Jul-15 trades booked `RECONCILED_EXTERNAL_EXIT` when the bot's
own trailed SL-M had filled (DLF: trailed 674.78→664.99, filled, then "cancel
failed: order does not exist"). Consequences: exit analytics corrupted AND
`runner.py:1355-1359` auto-blocks re-entry for the rest of the day on a false
"external exit".

**Required behavior:**
1. In `live_broker.reconcile_orphans` (`app/engine/live_broker.py:812`), before
   booking an equity orphan as `RECONCILED_EXTERNAL_EXIT`: if the position has a
   resting protective stop id (`pos.gtt_trigger_id`), query
   `self.client.status(oid)`. If it is COMPLETE with a fill: book the close at the
   order's **avg fill price** (not `last_premium`) with reason **`STOP_LOSS`**, skip
   the (pointless) cancel, and log marker `SL-M FILLED at exchange — booked STOP_LOSS`.
2. Only genuinely external closes keep `RECONCILED_EXTERNAL_EXIT` and the same-day
   re-entry auto-block. The runner must not block stop-fill exits — adjust the
   `reconcile_orphans` return contract (runner blocks exactly what's returned;
   return only the external ones) without breaking existing callers/tests.
3. `status()` read failure → conservative fallback: current behavior (external +
   block) plus a warn log.
4. Options-GTT orphans: keep current behavior (out of scope unless trivially the
   same mechanism).

**Tests:** stop order COMPLETE → reason STOP_LOSS, exit price = avg fill, no
re-entry block, no cancel attempt; stop OPEN → external + block + cancel as today;
status read raises → external + block + warn; paper broker unaffected.
