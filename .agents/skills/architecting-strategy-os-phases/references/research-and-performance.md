# Research and performance

- Research changes must preserve completed-bar signals, causal indicators, timezone and timestamp semantics, warmup, OOS separation, survivorship disclosure, gap handling, provider consistency, reproducibility, and provenance-complete cache keys.
- Cross-instrument alignment may use only observations available at the aligned timestamp. A new indicator or strategy needs a causality proof.
- `compute_signals` intentionally evaluates the full candle series before folds are cut so path-dependent seeds agree. This is valid only while every indicator is causal; any new indicator or strategy must prove that prefix results do not change when future bars are appended.
- Preserve next-bar open fills, direction-aware adverse slippage on both legs, and the event-blackout table shared with live execution unless the governing contract explicitly changes them.
- Keep `app/market_data/candles.py` as the single candle-to-frame conversion path. Thin aliases may call it; do not fork a second converter.
- Keep research import direction one-way: `research` may import `app.ir`; `app.ir` must not import research, and research must not import broker, runner, or `db.session`. Research approval remains immutable admission consumed once, never a reload lease.
- Measure performance before changing it: record a realistic baseline, profile the dominant cost, choose the lowest-complexity fix, rerun the same benchmark, and prove output equivalence.
- Reject a language rewrite without a profile showing the runtime itself dominates. V1 targets bar-based strategies and research throughput, not HFT latency.
