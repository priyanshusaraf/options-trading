# Content-addressed Backtest Cache Implementation Plan

> **For agentic workers:** use `superpowers:test-driven-development` task by task.

**Goal:** Make cache hits truthful and payload-complete without changing backtest results or adding a schema migration.

**Architecture:** A pure identity module hashes the exact ordered dataset and a closed execution manifest into the existing 64-character `params_hash`. Schema version 8 makes all legacy keys cold. Cache copying preserves every non-run-local column.

## Constraints

- Tests fail for each missing guard before implementation.
- Identity errors disable reuse; they do not abort simulation.
- The exact slippage value placed in identity is passed explicitly to spot simulation.
- No old timestamp-only fallback is allowed.
- Performance optimization is a separate next slice.

### Task 1: Ordered dataset identity

**Files:**
- Create `backend/app/backtest/identity.py`
- Create `backend/tests/test_backtest_identity.py`

- [ ] Test that earlier OHLCV mutation, timestamp mutation, insertion, deletion, and order changes alter the digest while the last timestamp may remain fixed.
- [ ] Test provider, instrument, interval, and requested/effective window sensitivity.
- [ ] Implement finite-value validation and streaming SHA-256 over IST microsecond timestamps plus exact packed floats.
- [ ] Run `pytest -q tests/test_backtest_identity.py`.

### Task 2: Complete execution identity

**Files:**
- Modify `backend/app/backtest/identity.py`
- Modify `backend/app/backtest/cache.py`
- Modify `backend/tests/test_backtest_identity.py`
- Modify `backend/tests/test_backtest_cache_risk_model.py`
- Modify `backend/tests/test_backtest_multistrategy.py`
- Modify `backend/tests/test_backtest_premium.py`

- [ ] Write sensitivity tests for strategy version and helper code, bound parameters, warmup/risk model, instrument economics, capital/window, resolved slippage, charge/event policies, every premium parameter/constant, and model source.
- [ ] Implement deterministic canonical manifests and a transitive module-source digest; an unavailable or `unknown` executable identity is non-reusable.
- [ ] Produce a full 64-hex result address and bump `SCHEMA_VERSION` to 8.
- [ ] Replace legacy-signature preservation assertions with v8 invalidation assertions.
- [ ] Run the focused identity/signature tests.

### Task 3: Wire lookup without assumption drift

**Files:**
- Modify `backend/app/backtest/sweep.py`
- Modify `backend/app/backtest/cache.py`
- Modify `backend/tests/test_backtest_cache.py`

- [ ] Write an integration test that revises an old candle under the same final timestamp and proves both simulators rerun.
- [ ] Write an unchanged-input test proving both simulators are skipped on a hit.
- [ ] Resolve slippage once, include it in identity, and pass that exact value into `simulate()`.
- [ ] Build the address after clipping the exact candle list; keep `last_candle_ts` as provenance only.
- [ ] Refuse reusable rows with transient premium failures; preserve the permanent no-options case.
- [ ] Run cache and sweep tests.

### Task 4: Exact cached artifact copy

**Files:**
- Modify `backend/app/backtest/cache.py`
- Modify `backend/app/backtest/sweep.py`
- Modify `backend/tests/test_backtest_cache.py`
- Modify `backend/tests/test_backtest_payload.py`

- [ ] Write a mapped-column contract test proving only `id`, `run_id`, and `from_cache` differ.
- [ ] Test exact equality of all serialized artifacts, especially `bh_curve_json` and `premium_trades_json`.
- [ ] Centralize cached field classification and preserve the source `computed_at`.
- [ ] Compare cold and warm summary/detail payloads after removing only run-local identities.
- [ ] Run focused payload/API tests.

### Task 5: Verification and evidence

- [ ] Run all backend and research tests.
- [ ] Run `scripts/backtest_smoke.py` and confirm `SWEEP OK`.
- [ ] Update the roadmap and backtest workstream with exact evidence only.
- [ ] Record scalable performance work as the next gate: 100×5 is the baseline tier, not the product ceiling.
