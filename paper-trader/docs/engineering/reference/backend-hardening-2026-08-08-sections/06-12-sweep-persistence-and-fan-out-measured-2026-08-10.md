Reference: [section index](../backend-hardening-2026-08-08.md). Read with its scope; this is not a new assignment.

## 12. Sweep persistence and fan-out, measured (2026-08-10)

Tasks 5 and 6 of the scalable-sweep plan. Machine: this Mac (M1 Pro, 4 performance + 4
efficiency cores), mock/synthetic provider, 5,000-bar 15-minute datasets, `trend_impulse_v3`,
benchmarks in the session scratchpad.

### One SQLite writer sustains both tiers

Persistence moved from two transactions per cell (`_store` + `_bump`) to one transaction per
batch of ten, with `run.done` **derived** from the durable result count inside that same
transaction. Compute stubbed; realistic row payloads.

| rows | transactions | seconds | rows/s | ms/txn | one row per txn |
|---:|---:|---:|---:|---:|---:|
| 500 | 51 | 0.09 | 5,880 | 1.67 | — |
| 5,000 | 501 | 0.76 | 6,582 | 1.52 | — |
| 16,000 | 1,601 | 2.64 | 6,056 | 1.65 | 11.99 s |
| 50,000 | 5,001 | 9.69 | 5,158 | 1.94 | 54.02 s |

2.64 s of persistence against 22 min of compute for the NSE-cash universe. It is not the
bottleneck at either tier and does not need a second writer.

### Fan-out gives 2x, and the reason is measured

Pinned (warm) run, 500 cells, one strategy:

| workers | seconds | ms/cell | speedup | efficiency |
|---:|---:|---:|---:|---:|
| 1 | 48.65 | 97.3 | 1.00x | 100% |
| 2 | 24.50 | 49.0 | 1.99x | 99% |
| 4 | 23.35 | 46.7 | 2.08x | 52% |
| 8 | 26.76 | 53.5 | 1.82x | 23% |

The same box reaches **3.78x at 4 workers on a pure-CPU fan-out**, so 8x was never available
here — but 2.08x is below even that ceiling, and the cause is the parent, not the machine.
Parent-thread wall time during a 4-worker pinned run:

| stage | ms/cell | share |
|---|---:|---:|
| `_prepare_dataset` (store read: decompress + re-address + manifest check) | 37.94 | 73.4% |
| `_plan_dataset` (execution address + result-cache lookup + pickle) | 2.70 | 5.2% |
| `submit` | 0.08 | 0.2% |
| waiting on workers | 7.86 | 15.2% |

Uncontended, the pinned `_prepare_dataset` is 22.5 ms/cell; a cold run adds
`dataset_store.put` at 23.9 ms/cell. **The owner's 16-core / 1.4-minute warm target is not
reached by fan-out alone.** The next lever is sized: send workers the dataset *address* rather
than its candles, so the store read happens in parallel — parent cost ~41 -> ~3.5 ms/cell. It
requires reproducing the five fail-closed refusals of `_pinned_dataset` worker-side, so it is a
`dataset_store` design decision, not a mechanical change.

Parent RSS over a 400-cell 4-worker run: 193.9 -> 196.5 MB (6.3 KB/cell). Datasets are
streamed, at most `workers x 2` in flight; accumulating would have been 2.10 MB/cell.

### A method note that cost a suppression

The bit-identity gate between serial and parallel output was **vacuous against float drift on
the mock provider**: `MockProvider` rounds every OHLC value to two decimals, so a worker that
"normalised" prices with `round(x, 2)` produced identical numbers and the gate stayed green.
It only reddens against a provider that fills the mantissa
(`test_backtest_parallel.FullPrecisionMockProvider`), where it fails on `curve_json` first.
Any numerical guard built on mock candles needs the same witness.

## 13. Tiered sweep benchmark (Task 7, 2026-08-10)

`backend/scripts/sweep_benchmark.py`. Deterministic, offline, drives the shipped
`sweep.start_sweep` rather than a model of it. `tests/test_sweep_benchmark_harness.py` keeps it
from rotting into a script nobody runs.

### Per-cell stage cost, 5,000-bar datasets, 12 repeats

| stage | p50 ms | p95 ms | p99 ms |
|---|---:|---:|---:|
| identity (`ordered_dataset_address`) | 11.46 | 12.01 | 12.01 |
| frame (`prepare_signal_frame`) | 8.25 | 10.19 | 10.19 |
| signals | 2.39 | 2.81 | 8.09 |
| simulate (spot) | 25.17 | 25.46 | 30.38 |
| premium (synthetic) | 33.18 | 35.30 | 63.27 |
| **TOTAL** | **80.32** | | |

Independently reproduces §10's 84.7 ms on a different synthetic series, which is the point of
measuring it twice.

### Projected tiers — projections, not capacity

| tier | cells | bars | compute serial | I/O floor | cold | store |
|---|---:|---:|---:|---:|---:|---:|
| 100 × 5 | 500 | 2.5 M | 40 s | 200 s | 0.07 h | 0.1 GB |
| 1,000 × 5 | 5,000 | 25 M | 402 s | 2,000 s | 0.67 h | 0.9 GB |
| 10,000 × 5 | 50,000 | 250 M | 4,016 s | 20,000 s | **6.67 h** | 9.5 GB |

**These multiply a measured per-cell cost; they are not measured end-to-end runs.** That
distinction is not pedantry — it is exactly where the earlier 16-core projection went wrong
(§12: the parent thread, not the cells, set the ceiling). Real NSE/BSE universe sizing is in
`superpowers/specs/2026-08-10-full-universe-backtest-design.md` §2.

### Operation counts, end-to-end

A speed number with an unbounded operation count underneath it is not a speed claim, so the
harness drives a real sweep and counts:

```
12 instruments x 2 intervals -> 16 cells, 0 errors
provider reads       16   (= unique datasets; no cell refetches another's data)
write transactions    3   budget 3  (ceil(cells/10) + 1)   OK
```

### Two harness guards, both proven able to fail

- **Full-mantissa inputs.** The harness generates its own series rather than using
  `MockProvider`, whose 2-decimal rounding already hid a worker-side `round(x, 2)` from a
  bit-identity gate once (§12). Rounding the harness's own candles to 2 dp reddens that test.
- **The I/O floor is tied to the adapter it models.** The 0.40 s constant is asserted against
  `KiteProvider._MIN_INTERVAL["historical"]`, so a throttle change reddens the guard instead of
  silently invalidating every cold-run projection in the design notes. Changing the constant to
  0.25 reddens it.
