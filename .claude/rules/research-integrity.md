---
description: Research plane, backtesting, indicators, data, cross-instrument alignment
paths:
  - "paper-trader/backend/research/**"
  - "paper-trader/backend/app/backtest/**"
  - "paper-trader/backend/app/market_data/**"
  - "paper-trader/backend/app/ir/kernels.py"
  - "paper-trader/backend/app/ir/runtime.py"
---

# Research integrity

A wrong number here is worse than a crash: it looks like an edge. Invoke
`.claude/skills/research-integrity` for anything touching signals, indicators, folds or data.

## The leakage checklist

Look-ahead · incomplete bars · future information inside indicators · warmup handling ·
future-aware synthetic data · timestamp normalisation · OOS contamination · parameter selection
using OOS information · survivorship · forward-filling across invalid gaps · cache keys missing
data/version/parameter dimensions · provider inconsistencies · cross-instrument alignment using
unavailable future observations · reproducibility.

## What is already true — do not re-derive, do not break

- **`compute_signals` computes over the FULL candle series before walk-forward folds are cut**,
  deliberately, so path-dependent EMA/ATR seeds stay consistent. This is correct **iff every
  indicator is causal**. Break causality and every OOS fold is scored using its own future,
  invisibly — the equity curve simply looks better.
- Both hand-written strategies are proven causal
  (`tests/test_handwritten_strategy_causality.py`), and graphs are proven causal by C11
  (`check_causality`). Any new strategy or indicator must land with the same proof.
- The backtester fills at **next bar open**, applies **adverse** slippage direction-aware on both
  legs, and shares the **same** event-blackout table as the live engine.
- `app/market_data/candles.py` is **THE** candle→frame converter. `runner._to_df` and
  `backtest._candles_to_df` are thin aliases. They were once byte-identical copies, so a data fix
  landed in one plane and missed the other. Do not re-fork it.
- **Pre-2026-08 research findings are unusable as baselines** — DSR deflation never engaged
  (`var_sr` computed nowhere, benchmark pinned at 0) while a docstring claimed otherwise. Rerun
  anything that matters.

## Research is isolated

`research/guards.py` stays fail-closed. `research/` imports `app.ir`; `app.ir` never imports
research. Research must not import broker, runner or `db.session`.

Research approval is **admission consumed once at activation**, not a lease (ADR 0013). Evidence
and decisions are immutable and write-once. Do not implement an evidence re-read on reload.

## Evidence for a fix here

Reproduce the wrong number → write the regression test and watch it fail → fix → verify the
expected numerical result → prove no leakage was introduced. Green tests alone are not evidence.
