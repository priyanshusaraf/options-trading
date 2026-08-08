---
name: performance-benchmark
description: Required for any performance complaint, hot-path optimisation, or proposed language/runtime rewrite in Strategy OS. Enforces baseline-then-profile-then-optimise and refuses rewrites without measured evidence.
---

# Performance benchmark

> **No performance refactor without a baseline.**

## 1. Baseline

Write a benchmark that reproduces the complaint on a realistic workload — production-shaped row
counts and real recorded series, not a toy. Record: workload, wall time (min and median over
repeats), peak allocation, and the machine. Put the script in the session scratchpad, not the
repo, unless it earns a permanent home.

## 2. Profile

`cProfile`/`pstats`, `tracemalloc`, or a SQL statement log — whichever names the cost. **Find the
dominant cost.** Do not optimise the second-largest because it is more interesting.

## 3. Optimise the lowest-complexity bottleneck

In order of preference: better algorithm · push work into SQL · vectorise/NumPy · fewer
serialisations · better data layout · correct-keyed cache · Polars/DuckDB · process pool · Numba ·
compiled kernel.

## 4. Rerun the SAME benchmark

Same workload, same machine. Report before → after with the speedup and the memory delta. If the
change did not move the number you set out to move, it is not a performance fix.

## 5. Prove you did not change the answer

A faster wrong answer is a regression. Assert output equivalence at scale — byte-identical where
that is meaningful.

## Language rewrites

Do **not** propose Rust, C++ or Go because Python is theoretically faster. That proposal requires
a profile showing the *runtime* is the dominant cost, not the query shape, the I/O, the
serialisation or the algorithm. Every bottleneck measured in this repo so far has been
language-agnostic:

- `recent_trades` at 72k rows: 1398 ms → 2.1 ms by pushing filters and LIMIT into SQL.
- DB pool: 15 connections against a 40-thread worker pool; failures appear at ≳4 s hold.

V1 is not an HFT platform. Judge against 1/5/15-minute bar strategies and research throughput.
Record new baselines in `docs/engineering/reference/backend-hardening-2026-08-08.md`.
