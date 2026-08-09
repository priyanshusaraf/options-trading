# Scalable Backtest Sweep Implementation Plan

> **For agentic workers:** use test-driven development task by task and preserve numerical output.

**Goal:** Establish measured 100 × 5, 500 × 5, and 1,000 × 5 sweep tiers with exact-result
parity and bounded provider/database operations.

**Design:**
[`2026-08-09-scalable-backtest-sweep-design.md`](../specs/2026-08-09-scalable-backtest-sweep-design.md)

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

### Task 3: Atomic batch persistence

- [ ] Add transaction-budget tests at 500, 2,500, and 5,000 cells without expensive simulation.
- [ ] Add rollback, terminal-consistency, and interrupted-run reconciliation tests.
- [ ] Return serialized result values from computation and persist batches of at most ten.
- [ ] Update progress from durable result count in the same transaction.

### Task 4: Pinned immutable warm path

- [ ] Specify an explicit source-run/dataset-address API; normal refresh never implies pinning.
- [ ] Prove pinned exact reruns make zero provider calls and preserve all result artifacts.
- [ ] Reject manifest mismatch instead of silently refreshing or cloning.

### Task 5: Tiered benchmark and evidence

- [ ] Add a deterministic offline benchmark with separate acquisition, identity, simulation,
      persistence, and total timings.
- [ ] Run 100 × 5, 500 × 5, and 1,000 × 5 tiers; record p50/p95/p99 and operation counts.
- [ ] Keep a smaller real-strategy parity test in the normal suite.
- [ ] Update roadmap/workstream claims using measured results only.
