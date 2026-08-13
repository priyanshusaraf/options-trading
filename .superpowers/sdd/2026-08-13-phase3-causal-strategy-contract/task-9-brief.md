### Task 9: Backtest admission, cache identity, and next-bar execution

**Files:**
- Modify: `paper-trader/backend/app/api/backtest_routes.py`
- Modify: `paper-trader/backend/app/backtest/repository.py`
- Modify: `paper-trader/backend/app/backtest/identity.py`
- Modify: `paper-trader/backend/app/backtest/sweep.py`
- Modify: `paper-trader/backend/app/backtest/engine.py`
- Test: `paper-trader/backend/tests/test_backtest_admission.py`
- Test: `paper-trader/backend/tests/test_backtest_cache.py`
- Test: `paper-trader/backend/tests/test_backtest_fill_timing.py`

**Interfaces:**
- `enqueue_run(session, *, owner_id, scope, intervals, capital, total, admission_address, now=None, **values)` requires a current owner-scoped receipt.
- Add required keyword `admission_address: str` to the existing `execution_result_address` signature and include it in canonical identity.
- Results copy `BacktestRun.admission_address`.

- [ ] **Step 1: Write failing enqueue, cache, and same-bar tests**

```python
def test_backtest_without_admission_is_rejected(session):
    with pytest.raises(AdmissionRequired):
        enqueue_run(session, owner_id="owner-a", scope="NIFTY", intervals="5minute",
                    admission_address=None)

def test_admission_change_forces_cache_miss(base_manifest):
    first = execution_result_address(**base_manifest, admission_address=ADDRESS_A)
    second = execution_result_address(**base_manifest, admission_address=ADDRESS_B)
    assert first != second

def test_signal_on_t_cannot_fill_on_t(frame, admitted_strategy):
    trades = run_trades(frame, admitted_strategy)
    assert trades[0].entry_time == frame.index[1]
```

Add independent `bypass_backtest_enqueue` and `bypass_backtest_worker` mutations. Each removes only
its named check and must make its corresponding test fail without relying on the other check.

- [ ] **Step 2: Verify red**

Run: `cd paper-trader/backend && pytest -q tests/test_backtest_admission.py tests/test_backtest_cache.py tests/test_backtest_fill_timing.py`

Expected: new admission tests fail; existing timing behavior is recorded before mutation.

- [ ] **Step 3: Require admission at enqueue and re-verify in worker**

API resolves graph/version under owner, loads receipt, calls `verify_admission`, then enqueues.
Worker repeats verification before dataset/provider access. A failed item records stable code and no
result. Pass the address into every cache manifest and result row.

- [ ] **Step 4: Add a same-bar mutation probe**

Add a local mutation helper that changes the entry index from `signal_index + 1` to `signal_index`.
The timing test must fail under the mutation. Keep production code on the existing next-open path.

Run: `cd paper-trader/backend && pytest -q tests/test_backtest_admission.py tests/test_backtest_cache.py tests/test_backtest_fill_timing.py tests/test_backtest_pinned.py`

Expected: PASS; mutation subtest reports the same-bar mutant killed.

- [ ] **Step 5: Commit**

```bash
git add paper-trader/backend/app/api/backtest_routes.py paper-trader/backend/app/backtest/repository.py paper-trader/backend/app/backtest/identity.py paper-trader/backend/app/backtest/sweep.py paper-trader/backend/app/backtest/engine.py paper-trader/backend/tests/test_backtest_admission.py paper-trader/backend/tests/test_backtest_cache.py paper-trader/backend/tests/test_backtest_fill_timing.py
git commit -m "feat(backtest): bind results and cache reuse to causal admission"
```
