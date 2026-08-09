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

- [ ] Add transaction-budget tests at 500, 5,000, and 50,000 cells without expensive simulation.
- [ ] Add rollback, terminal-consistency, and interrupted-run reconciliation tests.
- [ ] Return serialized result values from computation and persist batches of at most ten.
- [ ] Update progress from durable result count in the same transaction.
- [ ] Measure whether one SQLite writer sustains the 50,000-row tier; report, do not assume.

### Task 6: Measured multiprocess fan-out (new)

Justified by measurement, not preference: the provider throttle is known, and the measured
84.7 ms/cell puts the 50,000-cell tier at 4,236 s on one core — ~20× over the target. Peak
allocation is 2.10 MB/dataset, so workers must stream datasets, never accumulate them:
50,000 held at once would be ~105 GB.

- [ ] Prove byte-identical results between serial and parallel execution on a frozen dataset.
- [ ] Bound worker count and prove no worker observes another's frame.
- [ ] Measure speedup per core count; keep serial as the reference implementation.

### Task 7: Tiered benchmark and evidence

- [ ] Add a deterministic offline benchmark with separate acquisition, identity, simulation,
      persistence, and total timings.
- [ ] Run 100 × 5, 1,000 × 5, and 10,000 × 5 tiers; record p50/p95/p99 and operation counts.
- [ ] Keep a smaller real-strategy parity test in the normal suite.
- [ ] Update roadmap/workstream claims using measured results only — including an honest
      statement of what the 10,000 × 5 tier costs cold, warm and pinned.
