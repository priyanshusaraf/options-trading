# Scalable Backtest Sweep Implementation Plan

> **For agentic workers:** use test-driven development task by task and preserve numerical output.

**Goal:** Establish measured 100 × 5, 1,000 × 5, and **10,000 × 5** sweep tiers with
exact-result parity and bounded provider/database operations.

**Design:**
[`2026-08-09-scalable-backtest-sweep-design.md`](../specs/2026-08-09-scalable-backtest-sweep-design.md)
· corrected by
[`2026-08-09-scale-and-cost-corrections-design.md`](../specs/2026-08-09-scale-and-cost-corrections-design.md)

> **Reordered 2026-08-09 by owner correction.** The tier ceiling rose to 10,000 × 5 ("a few
> minutes"), which is 50,000 datasets. Kite's 0.40 s historical throttle puts a **5 h 33 m**
> floor under fetching those live, so the target is unreachable by provider refresh at any level
> of code optimisation. The local content-addressed dataset store — originally Task 4 — is
> therefore promoted ahead of batch persistence, and measured multiprocess fan-out enters scope.
> Tasks below are renumbered in execution order.
>
> **The 6.61 ms/cell figure this note originally cited was wrong** and is superseded by the
> per-stage measurement in hardening record §10. It was taken on 600-bar datasets when a real
> 15-minute/200-day window is ~5,000 bars, and the premium replay books **zero trades** below
> ~5,000 bars, so it was timing an empty loop. A cell is **84.7 ms** (185.7 before `5ba1233`),
> which puts the 50,000-cell tier at **4,236 s serial** — ~20× over target, and that is what
> justifies fan-out.

### Task 1: Share exact dataset acquisition across strategies

- [x] Add a counting-provider test: `N × I × S` results use exactly `N × I` candle reads.
- [x] Add exact cold-result parity between independent and multi-strategy sweeps.
- [x] Add provider-error, thin-window, and out-of-range fan-out tests.
- [x] Extract an immutable prepared dataset and move acquisition outside the strategy loop.
- [x] Verify focused sweep, cache, window, and premium tests.

### Task 2: Share frame and signal preparation

- [x] Measure current DataFrame conversions and strategy signal evaluations.
- [x] Add spot/premium exact-parity tests for shared preparation.
- [x] Convert once per dataset and evaluate once per dataset/strategy.
- [x] Prove refresh-warm hits perform zero conversions and simulations after address validation.

### Task 3: Local content-addressed dataset store (promoted from Task 4)

The only path to 10,000 × 5. Datasets are fetched once, stored by the exact address
`identity.ordered_dataset_address` already computes, and read from disk thereafter.

**DONE — `e985d77`.** `app/backtest/dataset_store.py`, 10 tests, no migration.

- [x] Test that a stored dataset is served without any provider call, and that its bytes
      round-trip to an identical address.
- [x] Test that a refresh still reads once per dataset and that revised history is detected and
      stored as a new address rather than overwriting.
- [x] Test corruption containment: a stored dataset whose recomputed address disagrees is
      refused, not served.
- [x] Implement the store behind the existing prepared-dataset seam so `_one()` is unchanged.
- [x] Prove the store never becomes an implicit pin — a normal refresh still costs its reads.

> Measured: **38 bytes/bar** on a random walk (22 on the mock's smooth ramp — do not plan
> against that one), so ~10 GB at the full tier. The sweep **writes only**; there is no read
> path, which is what makes the no-implicit-pin contract hold by construction. Reading from
> the store is Task 4.
>
> Found on the way: `LogBus` has `warn`, not `warning`, and `sweep.py` used the wrong name in
> both of its degradation handlers — so a dataset that could not be addressed aborted the
> whole sweep instead of skipping. Guarded by `tests/test_logbus_method_names.py`.

### Task 4: Pinned immutable warm path

Where the store's payoff is collected: `start_sweep(pinned_datasets=…)` serves every cell from
the Task-3 store and makes **zero** provider reads.

- [x] Specify an explicit source-run/dataset-address API; normal refresh never implies pinning.
- [x] Prove pinned exact reruns make zero provider calls and preserve all result artifacts.
- [x] Reject manifest mismatch instead of silently refreshing or cloning.

> **API.** `sweep.resolve_pinned_datasets(provider, instruments, intervals, …)` turns "the
> datasets a previous sweep of this window fetched" into `{"NIFTY|15minute": <address>}` via the
> store's request index; the caller then passes that map to
> `start_sweep(pinned_datasets=…)`. Two separate calls on purpose — `start_sweep` never resolves
> anything itself, so pinning cannot happen by omission. Without the parameter the sweep is
> byte-for-byte what it was, provider reads included
> (`test_a_sweep_without_the_pin_parameter_reads_exactly_what_it_always_read`).
>
> **No `pinned_source_run_id`.** `BacktestResult` stores the *execution* address
> (`params_hash`), never the dataset address, so a run id cannot be resolved back to its
> datasets without a new column — and the migration head is frozen at `0014`. Index resolution
> above is the substitute: it reconstructs the same addresses from the request, not from the
> run. Add the column when a migration is next in scope.
>
> **Fail-closed, four ways.** A missing pin, an address absent from the store, a blob whose
> content no longer recomputes to its address, and a manifest describing another series all
> produce one explanatory result row and let the run continue. There is no code path from the
> pinned branch back to `provider.get_candles`. The fourth case is the one the store's own
> address check cannot catch — a 30-minute dataset recomputes to its own address perfectly, so
> `_pin_mismatch` compares interval, instrument identity, provider identity and requested window
> against the request as well.
>
> Suppression evidence: making a failed pin fall back to a fetch reddens all five fail-closed
> tests on `candle_reads == []`; making a normal refresh read the store reddens the Task-3
> no-implicit-pin test, the new no-pin-parameter test, **and**
> `test_revised_historical_candle_with_same_last_timestamp_is_cold` — i.e. it reintroduces the
> stale-history defect directly, which is exactly what the design says it would.

### Task 5: Atomic batch persistence (was Task 3)

- [x] Add transaction-budget tests at 500, 5,000, and 50,000 cells without expensive simulation.
- [x] Add rollback, terminal-consistency, and interrupted-run reconciliation tests.
- [x] Return serialized result values from computation and persist batches of at most ten.
- [x] Update progress from durable result count in the same transaction.
- [x] Measure whether one SQLite writer sustains the 50,000-row tier; report, do not assume.

> `_one` returns a values dict and writes nothing; `_commit_batch` inserts up to ten rows,
> sets `run.done` from `_durable_result_count` and applies any terminal status in ONE
> transaction. Progress is **derived, never incremented** — the old `_bump` was a second
> transaction, so a crash between the two left a run reporting rows it could not show
> (`test_an_interrupted_run_never_reports_more_than_it_stored` was red at `rows=0 done=33`).
> Cost is `floor(cells/10) + 1` transactions for the run phase, inside the `ceil(cells/10) + 1`
> budget, plus one for run creation.
>
> **Measured, one SQLite writer** (this Mac, WAL, `synchronous=NORMAL`, compute stubbed,
> realistic row payloads):
>
> | rows | txns | seconds | rows/s | ms/txn |
> |---:|---:|---:|---:|---:|
> | 500 | 51 | 0.09 | 5,880 | 1.67 |
> | 5,000 | 501 | 0.76 | 6,582 | 1.52 |
> | 16,000 | 1,601 | 2.64 | 6,056 | 1.65 |
> | 50,000 | 5,001 | 9.69 | 5,158 | 1.94 |
>
> It sustains both tiers with room to spare: 2.64 s of persistence against 22 min of compute
> for the 16,000-cell universe, and 9.69 s against 70 min at 50,000. One row per transaction
> measures 11.99 s / 54.02 s for the same tiers — 4.5–5.6× worse — and the pre-change code
> issued **two** transactions per cell.
>
> `reconcile_stale_runs()` (called by `start_sweep`) repairs a run left `running` by a dead
> process: status `error`, `done` reset to its durable row count.

> Found on the way: `test_backtest_cache.py`'s warm-copy guarantee moved from
> `_copy_from_cache` to `cached_result_values` + `_commit_batch`; the assertion is unchanged.

### Task 6: Measured multiprocess fan-out (new)

Justified by measurement, not preference: the provider throttle is known, and the measured
84.7 ms/cell puts the 50,000-cell tier at 4,236 s on one core — ~20× over the target. Peak
allocation is 2.10 MB/dataset, so workers must stream datasets, never accumulate them:
50,000 held at once would be ~105 GB.

- [x] Prove byte-identical results between serial and parallel execution on a frozen dataset.
- [x] Bound worker count and prove no worker observes another's frame.
- [x] Measure speedup per core count; keep serial as the reference implementation.

> **Design.** The parent keeps everything that is not pure arithmetic — the throttled provider
> read, `ordered_dataset_address`, the store write/read, and the reusable-result lookup. A
> worker receives a frozen candle tuple plus resolved params and returns already-serialized
> column values. No shared state, no DB session, no provider handle. The unit of work is a
> DATASET (not a cell), so the canonical frame is still built once per dataset. Results are
> re-sequenced into request order, so row ids do not depend on which core was free.
> `backtest_sweep_workers` defaults to **1** — the serial reference path — because the process
> that runs sweeps today is the live backend on a 1 GB VPS and a spawned worker costs ~200 MB
> resident before doing any work.
>
> **Bit-identity is the gate**, over every mapped column including `curve_json`, `bh_curve_json`,
> `trades_json` and `premium_trades_json`. It is proven non-vacuous: rounding candle prices to
> two decimals inside the worker reddens it on `curve_json` first — but only against
> `FullPrecisionMockProvider`. **The plain mock rounds OHLC to two decimals, so that suppression
> was a no-op against it and the gate would have been blind to exactly the drift it exists to
> catch.** Any future numerical guard on mock candles needs the same treatment.
>
> **Measured speedup — pinned/warm, 500 cells × 5,000 bars, one strategy** (M1 Pro, 4 P + 4 E
> cores; the same box does 3.78× on pure CPU fan-out at 4 workers, so that is the machine's
> ceiling, not 8×):
>
> | workers | seconds | ms/cell | speedup | efficiency |
> |---:|---:|---:|---:|---:|
> | 1 | 48.65 | 97.3 | 1.00× | 100% |
> | 2 | 24.50 | 49.0 | 1.99× | 99% |
> | 4 | 23.35 | 46.7 | 2.08× | 52% |
> | 8 | 26.76 | 53.5 | 1.82× | 23% |
>
> **The plateau is the parent, and it is measured.** Profiling the parent thread during a
> 4-worker pinned run: `_prepare_dataset` **37.9 ms/cell (73% of wall time)**, `_plan_dataset`
> 2.7 ms, waiting on workers only 7.9 ms. In a pinned run `_prepare_dataset` is the dataset-store
> read — decompress, recompute the address, check the manifest — 22.5 ms/cell uncontended. Cold
> runs add `dataset_store.put` at 23.9 ms/cell on top.
>
> **So the 16-core / 1.4-minute target is NOT reached by this change alone**, and the next lever
> is identified and sized: move the store read into the worker (send the address, not the
> candles), taking the parent from ~41 ms/cell to ~3.5 ms/cell. That is a change to the pinned
> fail-closed contract — five refusal paths in `_pinned_dataset` would have to be reproduced
> worker-side — and it belongs with the `dataset_store` owner.
>
> Streaming is proven: at most `workers × 2` datasets in flight, and parent RSS over a 400-cell
> 4-worker run moved 193.9 → 196.5 MB (6.3 KB/cell). Accumulating would have been 2.10 MB/cell.
>
> Fail-closed, worker-side: strategy resolution uses `resolve_strategy` and checks the parent's
> `strategy.version`. `get_strategy` in a spawned worker would silently substitute the DEFAULT
> strategy for a runtime-`register()`ed one — the run finishes green with the wrong logic's
> numbers filed under the requested key.

### Task 7: Tiered benchmark and evidence

- [ ] Add a deterministic offline benchmark with separate acquisition, identity, simulation,
      persistence, and total timings.
- [ ] Run 100 × 5, 1,000 × 5, and 10,000 × 5 tiers; record p50/p95/p99 and operation counts.
- [ ] Keep a smaller real-strategy parity test in the normal suite.
- [ ] Update roadmap/workstream claims using measured results only — including an honest
      statement of what the 10,000 × 5 tier costs cold, warm and pinned.
