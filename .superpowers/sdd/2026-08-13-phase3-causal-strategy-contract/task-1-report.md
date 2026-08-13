# Task 1 implementation report

## Outcome

Implemented closed immutable bounded-history and causal-recursive declarations while preserving
Component IR format version 1. Builder vocabulary and regime math are app-owned; research modules
are compatibility re-exports. Every vector kernel now has the mandatory three-argument
`(params, node_inputs, context_inputs)` transport with no runtime fallback. Recorded
`bar_timestamp` context comes only from a shared, monotonic, unique, timezone-aware DatetimeIndex.

Every current builder block has a literal admitted disposition, dependency list, component, and
registration seam. Recursive declarations have native immutable state machines for EMA/slope,
EMA z-score/cross/expansion, Wilder ATR, all RSI source and smoothing combinations, session opening
range, and expanding-median regime state. Tests cover exact initializer-update-step order,
two-session reset, numeric RSI parity across missing gaps, ATR partial/missing OHLC, non-finite
prefixes, canonical state encoding, and closed construction.

## Behavioral RED evidence

- `.venv/bin/pytest -q tests/test_ir_causal_contract.py research_tests/test_block_declared_inputs.py`
  initially failed collection with `ModuleNotFoundError: No module named 'app.ir.causal'`.
- Direct `CausalContract(...)` bypass test failed with `DID NOT RAISE` for `wall_clock` context.
- Timestamp context test failed with `DID NOT RAISE` for a RangeIndex.
- Recursive transition parity first failed because `ema_slope_up` was quarantined.
- Non-finite JSON encoding test failed with `DID NOT RAISE` for NaN.
- Expanding-z closure test failed because existing `KernelSpec.causal` values were `None`.
- Exact ATR gap regression failed on the final decision because previous close incorrectly crossed
  a missing bar.

## GREEN evidence

Command:

`cd paper-trader/backend && .venv/bin/pytest -q tests/test_ir_causal_contract.py research_tests/test_block_declared_inputs.py research_tests/test_every_block_is_reachable.py tests/test_ir_authoring.py tests/test_ir_runtime.py tests/test_ir_strategy_parity.py research_tests/test_regime.py research_tests/test_ir_block_components.py`

Result after the bounded Critical parity fix round: PASS, 259 collected outcomes, including 6
skips (`253 passed, 6 skipped`). Raw count is inventory only; the load-bearing evidence is exact
vector/state parity on the reproduced divergence fixtures.

Critical review fixes added after the first freeze:

- expanding-z EMA and Wilder recursive contracts match their shipped vector kernels across an
  interior NaN, including Wilder `min_periods` output timing;
- regime true range skips only unavailable candidates, matching pandas row-wise `max(skipna=True)`;
- ATR resets prior-close provenance across a missing close and matches the discriminating 4% and
  1.3× decisions;
- Wilder RSI matches numeric state and threshold decisions across its reproduced missing-gap case;
- current-bar body fraction has zero warmup while retaining bounded current-bar history;
- direct block disposition construction rejects fake contracts and non-tuple dependency closures.

Additional checks:

- `git diff --check`: PASS.
- Changed Python compilation with `.venv/bin/python -m py_compile`: PASS.
- Staged files: none.
- Protected hashes unchanged from baseline:
  - `app/engine/kite_venue.py`: `2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240`
  - `app/engine/venue.py`: `c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae`
  - `app/providers/brokers.py`: `d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38`
  - `tests/test_broker_registry.py`: `13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3`

## Research provenance

The bounded research gate inspected XState and Dagster as reference-only sources. Adopted only the
general patterns of pure deterministic state transitions and construction-time rejection. No code,
dependency, source file, actor runtime, or DAG framework was imported. Component IR remains v1.

## Deviations and Task 2 dependencies

- The task brief requested stopping uncommitted and unstaged, so no Task 1 commit was created.
- Task 2 still owns immutable `KernelRegistration`, transitive implementation identities,
  dependency-boundary enforcement, and production `PlatformRegistry` composition. Task 1 exposes
  `BLOCK_REGISTRATIONS` only as the minimal admitted callable seam and retains the existing
  expanding-z `LIBRARY`/`IMPLEMENTATIONS` compatibility shape until Task 2 replaces it.
