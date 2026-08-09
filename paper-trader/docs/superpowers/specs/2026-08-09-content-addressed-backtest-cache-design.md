# Content-addressed backtest cache

**Date:** 2026-08-09  
**Status:** approved correctness slice  
**Decision rule:** a hit is valid only when the exact data and every executable assumption that produced the result have the same identity.

## Current defect

The current cache is not content-addressed. It matches the final candle timestamp plus a partial parameter signature. Revising any earlier OHLCV value can therefore return stale metrics. The signature also omits transitive strategy code, spot slippage, instrument economics, charge and event rules, and part of the premium model. Warm copies omit `bh_curve_json` and replace `computed_at`, so a hit is not payload-equivalent to its source.

## Accepted design

The existing `BacktestResult.params_hash` column is already 64 characters. It will store one full SHA-256 result address. No database migration is required for this slice.

The result address combines two pure identities:

1. **Dataset identity**
   - provider name, instrument key, interval, and requested/effective window metadata;
   - ordered candles exactly as simulated;
   - naive timestamps interpreted as IST, including microseconds;
   - unrounded IEEE-754 open, high, low, close, and volume values.

2. **Execution identity**
   - cache scheme and result-model version;
   - instrument key, segment, lot size, strike step, and options availability;
   - strategy key, full immutable version, bound parameters, warmup, and risk model;
   - a transitive executable digest over the complete source modules used by the strategy, IR kernels where present, spot backtest, premium backtest, metrics, ratchet, charges, event risk, and option pricing;
   - capital, requested window, resolved spot slippage, the enabled event-risk policy, applicable charge schedules, and the complete resolved premium parameter/constant set.

If exact source or numeric identity cannot be derived, the cell is computed normally but receives no reusable address. Cache failure must never prevent a backtest result.

`SCHEMA_VERSION` moves from 7 to 8. Every older row remains readable but cannot match a v8 address. `last_candle_ts` remains IST-correct provenance and a query prefilter; it is never sufficient identity.

## Reuse and payload rules

`find_reusable()` accepts only successful v8 rows with the full address. A transient `premium_error` is not reusable. The permanent no-options status may be reused only when the current instrument also declares `has_options=False`.

A cached row differs from its source in exactly three persisted fields:

- new `id`;
- destination `run_id`;
- `from_cache=True`.

Every other mapped column is copied byte-for-byte, including `curve_json`, `bh_curve_json`, `trades_json`, premium artifacts, identity fields, and the original `computed_at`. The computation timestamp records when simulation happened, not when a later run reused it.

One centralized field contract must make future model additions choose explicitly between cached payload and run-local state.

## Acceptance criteria

- Any candle edit, insertion, deletion, reordering, timestamp change, or volume change forces a miss even if the final timestamp is unchanged.
- Provider, interval, window/clamp, instrument economics, strategy version/code/params, slippage, charge/event rules, model code, and every premium assumption are identity-sensitive.
- An unchanged second sweep hits.
- A hit invokes neither simulator.
- Cold and warm rows are byte-equivalent except for `id`, `run_id`, and `from_cache`.
- Transient premium failures do not become permanent cache hits.
- Pre-v8 rows never hit.
- Focused and branch-wide suites plus the deterministic sweep smoke pass.

## Non-goals

This slice does not reduce provider reads, reuse datasets across strategies, batch progress commits, or set wall-clock targets. Those belong to the scalable sweep-performance slice immediately after cache correctness.
