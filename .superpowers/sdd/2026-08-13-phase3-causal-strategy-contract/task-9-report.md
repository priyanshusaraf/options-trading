# Task 9 report: backtest admission, cache identity, and next-bar execution

Risk: **Critical**. This task makes causal admission a necessary backtest guard. It does not
claim complete Strategy Preflight: provider capability, market truth, dataset sufficiency,
resource planning, and execution readiness remain separate later-phase checks.

## Delivered

- `enqueue_run` requires an `admission_address` and verifies the owner-local persisted receipt
  against the exact immutable graph-version bytes and current app `REGISTRY` before it creates a
  durable run.
- The API requires the address. New admitted sweeps execute the one freshly verified IR graph,
  not a registry key; a request containing several strategy keys is refused. One run therefore
  cannot attribute several strategy artifacts to one receipt. Legacy rows remain readable; no
  address is inferred for them.

Multi-strategy ruling: the pre-existing sweep could enumerate several registry keys, but the Task 9
model has exactly one `BacktestRun.admission_address` and the admitted runtime is exactly one graph.
New multi-key admission is therefore refused (`ADMISSION_REQUIRED`), rather than silently choosing
one receipt or inventing a second address representation. This keeps legacy reads/exits unchanged.
- The worker repeats receipt/graph/registry verification before its first dataset or provider
  read. A refusal stores only its stable code and produces no result row.
- Run and result rows copy the admission address. Cache identity includes it, so a changed receipt
  cannot reuse an earlier result.
- The engine has a narrow real fill-index seam. A completed-bar entry uses `signal_index + 1` and
  fills at the next bar open.

## Mutation evidence

- `bypass_backtest_enqueue` removes only the enqueue verifier. The real missing-address guard then
  fails, so the mutant is killed.
- `bypass_backtest_worker` removes only worker re-verification. The real provider-before-refusal
  guard then fails, so the mutant is killed.
- The same-bar mutant replaces the production `_entry_fill_index(signal_index + 1)` with
  `signal_index`; the real trade-timing guard fails, so the mutant is killed.

## RED/GREEN evidence

Observed RED before production changes:

```text
cd paper-trader/backend && .venv/bin/pytest -q \
  tests/test_backtest_admission.py tests/test_backtest_cache.py \
  tests/test_backtest_fill_timing.py

FFFF.........
```

The failures were the expected missing `AdmissionRequired` and enqueue verifier seams plus the
missing required `admission_address` argument on `execution_result_address`.

Focused GREEN commands observed:

```text
cd paper-trader/backend && .venv/bin/pytest -q \
  tests/test_backtest_admission.py tests/test_backtest_fill_timing.py
# 7 passed

cd paper-trader/backend && .venv/bin/pytest -q tests/test_backtest_cache.py
# 8 passed

cd paper-trader/backend && .venv/bin/pytest -q tests/test_backtest_pinned.py
# 10 passed

cd paper-trader/backend && .venv/bin/pytest -q \
  tests/test_backtest_admission.py tests/test_backtest_fill_timing.py \
  tests/test_backtest_identity.py
# 66 passed

cd paper-trader/backend && .venv/bin/python -m py_compile \
  app/api/backtest_routes.py app/backtest/repository.py \
  app/backtest/identity.py app/backtest/sweep.py app/backtest/engine.py
# exit 0
```

Final named subsystem boundary at freeze:

```text
cd paper-trader/backend && .venv/bin/pytest -q \
  tests/test_backtest_admission.py tests/test_backtest_cache.py \
  tests/test_backtest_fill_timing.py tests/test_backtest_pinned.py
# 26 passed
```

`git diff --check` is clean. No broad or Phase 3 suite was run.

## Scope and hand-off

Changed production files are `app/api/backtest_routes.py`,
`app/backtest/repository.py`, `app/backtest/identity.py`, `app/backtest/sweep.py`, and
`app/backtest/engine.py`. Focused tests cover admission, cache identity, result copying,
next-bar timing, and the required mutations. Existing cache/pinned fixtures use a narrow verified
admission double so those tests remain about cache and pinned-dataset behavior; the admission
tests exercise the actual enqueue and worker gates.

The four protected inherited broker/venue files were not edited or staged. The worktree is left
unstaged for review and no commit was created.

## Fix round 1

- `start_sweep` now reloads the claimed run, then freshly verifies that run's exact receipt,
  graph bytes, and current registry immediately before provider construction or universe I/O.
  The reloaded verified runtime is the one passed to the worker. A staged stale-receipt test
  proves the third verification (after reservation) refuses with `RECEIPT_STALE`, writes no
  result, and calls neither the provider factory nor the universe resolver.
- Reclaim now writes an `AdmissionRequired` stable code exactly (for example `RECEIPT_STALE`),
  rather than a prose prefix. Its poison-provider test proves the factory is never constructed.
- `append_claimed_result_batch` reads the parent run address and requires every value to carry
  that exact address inside the existing fenced savepoint. A mismatched receipt raises
  `ARTEFACT_MISMATCH` and inserts no rows.
- The public computation payload remains provenance-neutral. Its materialized local value gains
  the address only after an exact execution-address hit; the execution address already commits
  the receipt. Consequently separate receipts create separate cache artifacts, while no public
  payload includes an admission address.
- The worker-bypass mutant's supplied runtime now contains its address and is proven to reach the
  provider tripwire, rather than failing early on an attribute error.

Fix-round RED observed before the production changes:

```text
cd paper-trader/backend && .venv/bin/pytest -q tests/test_backtest_admission.py
# 3 failed, 6 passed
# stale receipt reached poisoned provider; mismatched batch did not refuse;
# reclaim persisted "restart dispatch failed: RECEIPT_STALE"
```

Fix-round focused evidence:

```text
cd paper-trader/backend && .venv/bin/pytest -q tests/test_backtest_admission.py
# 9 passed

cd paper-trader/backend && .venv/bin/pytest -q tests/test_public_backtest_computation.py
# 19 passed

cd paper-trader/backend && .venv/bin/pytest -q \
  tests/test_backtest_admission.py tests/test_backtest_cache.py \
  tests/test_public_backtest_computation.py
# 36 passed

cd paper-trader/backend && git diff --check
# exit 0
```

The ledger remains review pending. No broad suite ran; all work remains unstaged. The protected
broker/venue files remain untouched.
