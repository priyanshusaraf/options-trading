# Future-Strategy Roadmap — where to take this platform next

**Date:** 2026-06-21
**Audience:** the owner (trader + programmer). Text only — no code, no commitment.
**Premise:** the EMA50 + z-score signal looks strong; the platform around it
(data, execution, risk, backtest, analytics) is the moat. The biggest, most
*irreversible* lever is **recording data now that can't be bought later**.

---

## Now / Next / Later

### NOW (cheap, and costly to skip)
- **Record the whole watchlist's option chains** *(shipped 2026-06-21)* — the
  research cache now snapshots every option-bearing watchlist instrument during
  market hours, not just names a signal fired on. Kite sells **no** historical
  option chains / IV / OI / greeks, so every session not captured is gone forever.
  **Decision to make:** how wide to cast it — current = the enabled watchlist; the
  cheap upsell is to enable a broader "record-only" universe (more F&O names you
  *might* trade later) even if you never signal them. Effort: S.
- **Tag every trade with the fields analytics will need** *(see "learn-from-
  mistakes" below)* — MAE/MFE, regime, time-of-day bucket, signal z at entry,
  slippage vs mid. Logging them costs nothing now and is unrecoverable later.
  Effort: S–M.
- **Persist the underlying quote/candle tape you already pull** to parquet
  (`data/parquet/` exists) so backtests don't depend on Kite's rolling history
  window (15m → 200 days, day → 2000). Effort: S.

### NEXT (unlocks new research)
- **Pluggable-strategy seam** (below) — the single change that turns this from
  "the EMA-z bot" into "a strategy platform". Everything else compounds on it.
- **A real trade-analytics page** — where the edge comes from and where it bleeds.
- **Backtest realism upgrade** — walk-forward + out-of-sample, regime tagging,
  and (once enough chains are recorded) an *options* backtest, not just underlying.

### LATER (scale / multi-strategy)
- Multi-strategy capital allocation + risk budgeting across strategies.
- Paper-vs-live shadow comparison and performance attribution.
- A second data vendor for redundancy (the sibling `stock-market-analyst` project
  already wires yfinance/finnhub/fmp/fred/alpha_vantage — reuse, don't rebuild).

---

## New strategy candidates (ranked, with the trader's reasoning)

1. **Pure equities (cash), including liquid NON-F&O names.** The signal may be
   *cleaner* where there are no option-expiry/theta games and less HFT noise.
   Prereq: you already backtest the underlying; the gap is *cash* execution +
   sizing (no lot constraint) and a cash risk model. Fits the thesis as the
   "base edge" measurement even where you can't magnify with options. **Highest
   value-for-effort** — the backtest path mostly exists (`scope="full"`).
2. **Indices + liquid commodities (status quo), but sized by conviction.** Stick
   here for *live options* (liquidity + listed F&O), but add per-regime sizing.
   Lowest risk, incremental.
3. **Cointegrated / stat-arb pairs.** Different edge (mean-reversion of a spread,
   not trend), so it diversifies the book. Prereq you don't have yet: a pairs
   research pipeline (cointegration test, spread z-score, half-life), simultaneous
   two-leg execution, and pair-level risk. Bigger build; do it *after* the
   pluggable seam so it's a strategy module, not a fork. Magnification via options
   is awkward (you'd trade the legs), so likely cash/futures first.
4. **Event/vol strategies on the recorded option data** (once the IV/OI history
   accumulates) — e.g. IV-rank entries, earnings/expiry effects. Only becomes
   possible *because* you're recording chains now. Later.

---

## The pluggable-strategy refactor (design only)

Today the strategy is effectively hardcoded: `strategy/signals.py` is the single
source of truth, and both the live engine (`runner.scan_signals`) and the backtest
(`backtest/engine.simulate`) import it directly.

**The seam:** define a small `Strategy` interface — `compute(candles, params) ->
signal_frame` (entries/exits/state) plus metadata (name, valid intervals, default
params, param schema). Register implementations in a `STRATEGIES` registry keyed
by name. Then:
- The **live engine** reads the strategy *by name* per instrument (a column on the
  universe row), not by import — so different instruments can run different
  strategies, and adding one is registering a class, not editing the runner.
- The **backtest sweep** takes a `strategy` parameter and iterates
  instruments × intervals × **strategies**, storing the strategy name on
  `BacktestResult` (cache key already hashes params — add the strategy id).
- **Params** flow through the existing `runtime_config` mechanism, namespaced per
  strategy, so the Settings UI renders each strategy's knobs.
- **A/B / multi-strategy live:** capital allocation becomes per-strategy budgets
  feeding the existing allocator.

This is a *refactor*, not a rewrite — the EMA-z strategy becomes the first
registered module and behaviour is unchanged. It's the prerequisite for every
"new strategy" above.

---

## Learn-from-mistakes — the analytics that tell you where the edge is

Log these **per trade, starting now** (cheap now, impossible to backfill):
- **MAE / MFE** (max adverse / favourable excursion) — were stops too tight? targets too greedy?
- **Signal context at entry:** z, slope, trend, interval, time-of-day bucket, days-to-expiry, IV at entry.
- **Regime tag:** trending vs choppy (e.g. ADX or realized-vol bucket of the underlying).
- **Execution quality:** entry/exit vs mid at the time (slippage), charge drag per trade.
- **Outcome shape:** holding time, intraday vs overnight split (already captured), win/loss streak position, reinforcement count (captured).

Then a **post-trade analytics page** that slices net edge by: instrument, interval,
regime, time-of-day, holding-period bucket, intraday-vs-overnight, and reason
(`STOP_LOSS`/`TARGET`/`STRATEGY_EXIT`). The first questions it should answer:
*which instruments/regimes pay, where does charge+slippage eat the edge, and is the
−35/+60 stop/target actually optimal vs the MAE/MFE distribution?*

---

## Backtest realism path (today → trustworthy)

Today the sweep is an **underlying, signal-only** backtest with no stop/target,
no theta, and multi-day holds — it measures the *raw directional edge*, not the
live options P&L. Make it progressively real:
1. **Surface the caveat in the UI** (so a winner isn't mistaken for live P&L).
2. **Walk-forward / out-of-sample** discipline + a parameter-sweep overfitting
   guard (don't promote a cell that only shines in-sample).
3. **Apply the live exit model to the backtest** (premium stop/target proxy,
   max-hold, overnight rules) so backtest behaviour matches the bot.
4. **Options backtest** once enough chains are recorded — reprice via the recorded
   IV surface (or replay recorded chains directly). This is the payoff of the
   data-capture investment.

---

## Biggest risk / what I'd do first if it were my money

The single largest risk is **mistaking the backtest for the strategy's live P&L.**
The sweep holds the *underlying* for days with no stop and no theta; a real bought
option with a −35% stop, theta bleed, and overnight gaps behaves very differently —
the "extraordinary" curve is the *signal's* edge, not the *bot's* realized edge. So
first: **run the bot in paper on live Kite data for a meaningful sample, then
compare paper-realized P&L to the backtest** — that gap is your real edge after
options mechanics and costs. In parallel, **keep recording option chains from
today** so that within a few months you can backtest the *actual instrument you
trade* instead of a proxy. Only after that comparison looks honest would I touch
real-money execution (and only after the live-execution must-fix list is closed).
