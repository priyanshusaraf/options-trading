---
description: Performance work, benchmarking, profiling, hot paths
paths:
  - "paper-trader/backend/app/engine/analytics.py"
  - "paper-trader/backend/app/backtest/**"
  - "paper-trader/backend/app/ir/runtime.py"
  - "paper-trader/backend/app/ir/resolve.py"
---

# Performance

**No performance refactor without a baseline.** Invoke
`.claude/skills/performance-benchmark`; it carries the required workflow.

benchmark → profile → find the dominant cost → optimise the lowest-complexity bottleneck →
rerun the same benchmark → report before/after on the same workload.

## Rules

- **Measure before claiming.** "Seems fine" and "should be faster" are both inadmissible.
- **Do not propose Rust/C++/Go because Python is theoretically slower.** A language rewrite needs
  a profile showing the runtime is the dominant cost. Every bottleneck measured in this repo so
  far has been a query shape or a pool size — both language-agnostic.
- Prefer, in order: better algorithm · vectorisation/NumPy · fewer serialisations · better data
  layout · caching with a correct key · Polars/DuckDB · process pool · Numba · compiled kernel.
- Judge against real use cases — 1/5/15-minute bar strategies, portfolio-scale bar strategies,
  research throughput. **V1 is not an HFT platform**; do not optimise toward microseconds without
  a stated requirement.

## Known baselines (2026-08-08, this machine)

- `recent_trades` at 72k rows: 1398 ms → **2.1 ms** after pushing filters and LIMIT into SQL;
  peak allocation 310.7 MB → 0.5 MB.
- DB pool: 40 concurrent workers, 50 ms hold → all OK, p95 181 ms; 5 s hold → **10 of 40 fail**
  with `QueuePool ... TimeoutError`.
- IR evaluation: p95 3.8 ms, 1.46% of the signal loop.

Record new baselines in `docs/engineering/reference/backend-hardening-2026-08-08.md`.
