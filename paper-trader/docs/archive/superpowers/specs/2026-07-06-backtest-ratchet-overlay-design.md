# Backtest ratchet exit overlay + next-bar-open fills — design

**Date:** 2026-07-06
**Status:** approved (design approved in-session; decisions below chosen by owner)
**Goal:** make the platform backtester the *arbiter* of strategy performance by (a) adding the
v4 Pine ratchet risk engine (initial ATR stop → Chandelier trail → MFE-capture floor) as a
strategy-declared exit overlay, and (b) switching fills to next-bar-open for Pine parity —
then rerun `expanding_z_v4` on CRUDEOILM + the current watchlist and compare against the old
naked-signal numbers.

## Why (context)

The same strategy currently runs with three different risk stacks: TradingView (full ratchet,
zero costs), platform backtest (no risk engine at all — flags-only exits, `backtest/engine.py:201-204`),
live (premium −SL/+60% + step trail). The owner's confidence workflow (TV + platform confluence)
was therefore comparing incommensurable numbers. Verdict (recorded in session memory): canonical
v4 = ported entries/edge-expiry flags + the Pine ratchet as trade management. This spec implements
the backtest half only. Live engine, TV settings checklist, and Pine↔port golden parity tests are
**out of scope**.

## Owner decisions

1. **Fill model change is global** — all strategies fill at next-bar open (old signal-close fills
   were mildly optimistic; July edge-map baselines will shift on rerun; old rows stay in DB).
2. **Ratchet attaches via strategy declaration** — `Strategy.risk_model` class attribute;
   engine applies it whenever declared. Per-run config and v4 hardcoding were rejected.

## Changes

### 1. Strategy contract (`app/strategy/registry/base.py`, `expanding_z_v4.py`)

- `Strategy` gains `risk_model: dict | None = None` (class attribute; `None` = flags-only exits,
  current behaviour).
- `ExpandingZImpulseV4.risk_model` declares the Pine defaults:
  `{"atr_length": 14, "initial_risk_atr": 1.25, "trail_start_r": 1.75, "trail_atr": 3.0,
    "use_mfe_capture_floor": True, "capture_start_r": 1.25, "capture_pct": 0.35}`
- `trend_impulse_v3` and all other strategies declare nothing → unchanged semantics.

### 2. Fill model (`app/backtest/simulate()` — all strategies)

- Entry signal confirmed on bar *i* → position opens at bar *i+1* **open**. Signal on the last
  bar goes unfilled.
- Strategy-flag exits and ratchet-stop exits confirmed on bar *i* → fill at bar *i+1* open.
- Still-open position at end of data → `OPEN_AT_END` at last close (unchanged).
- MAE tracked from the fill bar (inclusive). `bars_held` = fill bar to fill bar.
- Position sizing/notional priced at the fill price (next open), not the signal close.

### 3. Ratchet exit engine (`app/backtest/engine.py`, active only when `risk_model` declared)

Pine-parity semantics (source: `strategies/expanding-z-impulse-v4.pine` lines 196–315):

- Engine computes its own Wilder ATR (RMA of true range, `atr_length`) from the OHLC frame —
  self-contained, no dependency on strategy-emitted columns.
- On the **fill bar**: freeze `entry_atr` = ATR at fill bar (pine:212); `risk_pts =
  initial_risk_atr × entry_atr`; initial stop = `fill_price ∓ risk_pts` (pine:215); high-water
  seeds at fill price (pine:214).
- Management (stop checks + MFE accrual from bar highs/lows) starts the bar **after** the fill
  bar (`bar_index > entryBar`, pine:233-241 — "no entry-bar MFE credit").
- `mfe_r = (high_water − fill)/risk_pts` (mirror for shorts). Candidates, all ratchet-only
  (stop never loosens, pine:295-300):
  - always: initial stop;
  - once `mfe_r ≥ trail_start_r`: Chandelier = `high_water ∓ trail_atr × current-bar ATR`
    (current ATR, not entry ATR — pine:274);
  - once `mfe_r ≥ capture_start_r` (if `use_mfe_capture_floor`): capture floor =
    `fill ± capture_pct × mfe_pts`.
- Stop hit is **close-confirmed** (`close ≤ stop` for longs, pine:305-309) — no intrabar fills;
  a wick through the stop that recovers by close survives. Exit fills next-bar open.
- Exit reason `RATCHET_STOP` (new `BTTrade.reason` value, distinct from `STRATEGY_EXIT`).
  If ratchet stop and strategy flag confirm on the same bar, the trade records `RATCHET_STOP`
  (protective layer wins the label; fill is identical).

### 4. Cache & versioning (`app/backtest/cache.py`)

- Bump `SCHEMA_VERSION` 5 → 6 (fill model changed for every strategy).
- Fold the declared `risk_model` dict (sorted, canonical repr) into the params-hash raw string so
  ratchet-param changes can never reuse stale cells.

### 5. Tests (`backend/tests/`)

- Ratchet math on synthetic OHLC: initial stop honoured; Chandelier activates only at ≥1.75R;
  capture floor only at ≥1.25R and locks 35% of peak; stop never loosens; close-confirmed (wick
  through stop does not exit); entry-bar MFE not credited.
- Fill model: entry at next open; last-bar signal unfilled; exit fill at next open; OPEN_AT_END
  unchanged; v3 trades identical to before *except* fill prices/times.
- Cache: params_hash changes when risk_model changes; schema bump invalidates old cells.
- Full suite + `scripts/dryrun.py` + `scripts/backtest_smoke.py` stay green (live engine untouched;
  smoke's net-of-charges invariant must hold under the new fill model).

### 6. Deliverable (after implementation)

Rerun `expanding_z_v4` (and `trend_impulse_v3` for reference) on CRUDEOILM + the currently
enabled watchlist at the sweep's standard timeframes (at minimum 15m/30m/60m); produce an
old-vs-new comparison table
(naked-signal/close-fills vs ratchet/open-fills, both net of charges) in chat. Old rows remain
in `backtest_results` under schema_version ≤ 5 for the comparison.

## Error handling & edge cases

- `risk_model` with `atr_length` longer than available warmup → ratchet inactive until ATR is
  defined; positions opened before ATR exists fall back to flags-only exits for that trade
  (log-free, deterministic).
- Zero/NaN ATR at fill bar → `risk_pts` undefined → ratchet disabled for that trade (flags-only),
  never a division by zero.
- Non-positive `risk_pts` guard mirrors pine (`longRiskPts > 0` checks, pine:268-269).

## Known non-parities (accepted, documented)

- Pine sizes with its own equity model; platform stays fixed 1-lot additive (owner's model).
- Pine's optional absZ contraction exit stays off (port default parity).
- TV data (continuous contract, roll gaps) ≠ Kite data; this spec does not attempt data parity —
  the arbiter uses Kite data by definition.
