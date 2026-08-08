---
name: research-integrity
description: Required for research-plane, backtesting, indicator, data-pipeline, warmup, timestamp, caching, or cross-instrument alignment work in Strategy OS. Hunts quantitative leakage — look-ahead, OOS contamination, survivorship — rather than doing generic code review.
---

# Research integrity

A wrong number here does not crash. It looks like an edge, gets approved, and eventually trades.

## The audit

Work through these against the actual diff. Name each as CLEAN, AT RISK or VIOLATED with the line
that decides it.

| # | Leak | What to check |
|---|---|---|
| 1 | Look-ahead | Any `shift(-n)`, centred window, `bfill`, full-sample quantile/`max`/`mean`, or reindex that can see forward |
| 2 | Incomplete bars | Signals must fire on **completed** candles only |
| 3 | Warmup | Are indicators still NaN/unsettled where a signal is allowed? Is warmup trimmed by declared count for graphs? |
| 4 | Timestamp semantics | tz-awareness, IST vs UTC, bar-open vs bar-close labelling, DST |
| 5 | OOS contamination | Does any fold see its own future? Was a parameter chosen using OOS data? |
| 6 | Survivorship | Is the visible set mistaken for the universe? Is exclusion disclosed and counted? |
| 7 | Forward fill | Filling across an invalid gap manufactures data that never existed |
| 8 | Cache provenance | Does the key carry instrument, interval, **data version, parameters and code identity**? A key missing a dimension returns a stale answer confidently |
| 9 | Provider inconsistency | Two providers disagreeing on the same bar must not be silently blended |
| 10 | Cross-instrument alignment | Aligning two series must never use an observation unavailable at that timestamp — this is look-ahead wearing a join |
| 11 | Reproducibility | Same inputs → same outputs. Seeds, ordering, and the resolved graph version all recorded |

## What is already established — cite, do not redo

- `compute_signals` computes over the FULL series before folds are cut, deliberately. Correct
  **iff every indicator is causal**.
- Both hand-written strategies are proven causal
  (`tests/test_handwritten_strategy_causality.py`); graphs are proven by C11. **A new indicator or
  strategy lands with the same proof.**
- Next-bar-open fills, adverse direction-aware slippage, and the shared event-blackout table are
  already correct in the backtester.
- Pre-2026-08 findings are unusable as baselines — DSR deflation never engaged.

## Evidence for a fix

Reproduce the wrong number → write the regression test → **watch it fail** → fix → verify the
expected numerical result → show no new leakage. Then dispatch **`research-leakage-reviewer`**.
