Reference: [section index](../backend-hardening-2026-08-08.md). Read with its scope; this is not a new assignment.

## 4. Performance — measured

All numbers from this machine, mock provider, temp databases. Scripts lived in the session
scratchpad and are not in the tree.

### 4.1 `recent_trades` — the 2026-07-23 outage shape, in a second place (FIXED)

The outage post-mortem fixed `equity_curve` and `signal_counts`. `recent_trades` sat 100
lines below `equity_curve` with the identical shape and was not fixed: it selected **every**
`Trade` row, filtered in Python, and applied `limit` with a list slice — so `limit` bounded
the response and never the read.

At **72,000 trades** (the row count the outage note cites for the live VPS):

| Call | Before | After | Speedup | Peak alloc before → after |
|---|---|---|---|---|
| `/api/trades?limit=100` | 1398.4 ms | 2.1 ms | **658×** | 310.7 MB → **0.5 MB** |
| dashboard, filtered, limit=50 | 1296.3 ms | 1.3 ms | **980×** | 310.7 MB → **0.3 MB** |

Output byte-identical at scale, filtered and unfiltered. 310 MB of allocation per call, on
a 1 GB droplet, under a 5-second dashboard poll, is the outage mechanism precisely.

Two independent bounds now, because either alone leaves a path back: the query is bounded
(`analytics._narrow` pushes filters and `LIMIT` into SQL) and the request is bounded
(`app/api/paging.py::MAX_PAGE`). Negative limits mattered: SQLite reads `LIMIT -1` as no
limit at all.

`instrument_stats` stays deliberately unlimited — a statistic over a subset of its own
population is wrong rather than partial — and is bounded by its indexed key instead.

### 4.2 The connection pool has a measured cliff (NOT yet changed — see §6)

`create_engine` sets `pool_pre_ping` and `pool_timeout=10` but **leaves pool sizing at the
SQLAlchemy default**: `pool_size=5`, `max_overflow=10` → **15 connections**. FastAPI runs
every `def` route (which is nearly all of them) in anyio's worker threadpool — **40 threads**
by default. The pool is the binding constraint, not SQLite.

Measured, 40 concurrent DB-touching workers:

| Per-request connection hold | Result |
|---|---|
| 50 ms | 40/40 ok, p95 181 ms |
| 1 s | 40/40 ok, 3.0 s wall |
| 3 s | 40/40 ok, 9.0 s wall — at the `pool_timeout` edge |
| **5 s** | **30/40 ok, 10 failed** with `QueuePool limit ... TimeoutError`, p95 10 s |

So any query holding a connection **≳4 s** under full threadpool concurrency starts
**failing requests**. Before §4.1, `recent_trades` held one for **1.4 s** at production row
counts — within reach, and the 2026-07-23 outage's terminal symptom was DB-pool collapse.

`/api/health` does genuinely touch the pool (`_probe_db`), so total exhaustion surfaces as
503 rather than a lying 200. What is missing is a **leading** indicator: saturation is only
visible once it is total.

---

## 5. Quant / research leakage

### 5.1 Causality of the hand-written strategies — audited, no defect, now guarded (`ce72249`)

The IR proves causality for graphs (C11). Nothing did for the hand-written strategies,
which are what the live engine executes and what every backtest number is measured on.
`trend_impulse_v3` — the default — had no causality proof at all.

This matters because of a deliberate design choice: `compute_signals` computes the signal
frame over the **full** candle series and only then cuts walk-forward folds, so
path-dependent EMA/ATR seeds stay consistent. Correct **iff** every indicator is causal;
otherwise each out-of-sample fold is scored using information from its own future and the
leak is invisible — the equity curve simply looks better.

**Result: both `expanding_z_v4` and `trend_impulse_v3` are causal**, on real recorded
series across four prefix lengths, asserted over every column they emit rather than only
the four canonical ones. The comparison is proven able to fail by injecting a one-bar
look-ahead.

### 5.2 Look-ahead discipline elsewhere — inspected, healthy

`backtest/engine.py` fills at **next bar open**, applies **adverse** slippage on both legs
direction-aware, shares the **same** event-blackout table as the live engine (so backtests
are not flattered by bars the live bot refuses), and trims warmup by declared count for
graph strategies so the two planes agree on which bars exist.

### 5.3 Not yet audited

Cache key dimensionality (does the `(instrument, interval)` backtest cache carry data and
parameter identity?); DSR/PBO deflation correctness — memory records `var_sr` computed
nowhere and the benchmark pinned at 0, making pre-2026-08 findings unusable as baselines,
and that has **not** been re-verified in this phase; survivorship in the sweep's visible
set (there is a disclosure mechanism — `skipped_breakdown` — but its completeness is
unverified); cross-instrument timestamp alignment (does not exist yet).

---

## 6. Architecture conclusions so far

| Decision | Verdict | Evidence |
|---|---|---|
| Python + FastAPI for the API | **Stay** | No measured bottleneck is language-shaped. The two real ones found so far were a query shape and a pool size; both are Python-agnostic. Do not revisit without a measurement that indicts the runtime |
| SQLite + WAL | **Stay with hardening** | Not the binding constraint at the concurrency measured; the 15-connection pool is. Migration trigger remains a measured lock-wait, not a headcount |
| Sync `def` routes on the anyio threadpool | **Stay, but size the pool to it** | §4.2 — 40 workers against 15 connections is an accidental default, not a decision |
| Process-wide provider singleton | **Refactor for V1** | Already a correctness hazard in tests (§3.1) and the concrete blocker for multiple connections per account |
| Process-global backtest sweep | **Unchanged, seam only** | G-3. Second concurrent user is refused outright; do not build queues now |
| The authority / execution-binding spine | **Preserve** | Nothing found in this phase argues against it. Not touched |

**Deliberately NOT changed: the connection pool.** Raising it is the obvious move and it is
not obviously safe. Each additional SQLite connection carries its own page cache, and the
target box is the 1 GB droplet that has OOM'd twice with the engine running — trading a
request-timeout ceiling for a memory ceiling on the machine that holds real positions is
not a change to make unilaterally. It is written up here as an owner-visible decision with
its measurement attached.

---
