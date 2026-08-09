# Task 2: Pure Reducer and Transactional Store

## Scope

Created the pure execution-lifecycle reducer and its SQLAlchemy transactional
store. The change adds no broker calls, live-flag changes, exit changes, schema
changes, or frontend work.

## Red

Command run from `paper-trader/backend`:

```text
/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python -m pytest -q tests/test_execution_lifecycle.py
```

Observed result before implementation:

```text
E   ModuleNotFoundError: No module named 'app.engine.execution_lifecycle'
```

The initial relative `.venv/bin/python` path was unavailable in the isolated
worktree, so all verification used the existing repository virtual environment
by absolute path while importing code from the worktree.

## Green verification

Commands run from `paper-trader/backend`:

```text
/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python -m compileall -q app/engine/execution_lifecycle.py
/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python -m pytest tests/test_execution_lifecycle.py tests/test_execution_lifecycle_schema.py -v
```

Result:

```text
collected 13 items
tests/test_execution_lifecycle.py ..........
tests/test_execution_lifecycle_schema.py ...
13 passed in 1.91s
```

`git diff --check` also completed with exit status 0.

## Reducer rules

- Events are consumed in persisted insertion order (`ExecutionOrderEvent.id` in
  store reads); the pure reducer preserves the supplied order.
- A repeated `(source, source_event_id)` is ignored by the reducer. It does not
  create a second derived transition or anomaly.
- The first non-empty broker order ID is retained. A later different ID is kept
  only as an anomaly; it never replaces the original.
- Cumulative fill quantity only moves forward. A lower observation cannot shrink
  quantity or change the current cumulative average, and records an anomaly.
- For a higher cumulative fill, `last_fill_delta` is the positive difference.
  The incremental price comes from cumulative notional difference, so 25 at 100
  followed by 75 at 102 produces a 50-unit incremental fill at 103. The state
  carries the broker's latest cumulative average, 102; it never averages
  cumulative averages.
- `COMPLETE`, `CANCELLED`, `REJECTED`, and `FAILED` are terminal. Once terminal,
  later status changes cannot reopen the derived state and are anomalous.
- `SUBMIT_STARTED` without `ACKNOWLEDGED` sets `reconciliation_required`.
- Latencies derive only from persisted `observed_at` values: intent→submit,
  submit→acknowledgement, acknowledgement→terminal, and intent→terminal.
- Realised slippage is measured from the intent decision price. Buy slippage is
  average fill minus decision price; sell slippage reverses the sign. Basis points
  use the decision price denominator.

## Store and collision behavior

- `create_intent` creates a UUID4 hexadecimal client ID, derives the exact
  `pti-` broker tag, canonicalizes supplied JSON with sorted compact keys, stores
  the caller-supplied timestamp, and commits before returning.
- `append_event` canonicalizes payload JSON and commits before returning.
- On the unique `(client_intent_id, source, source_event_id)` collision,
  `append_event` rolls back, reloads the existing row, and returns it only when
  all durable event contents match, including timestamp and canonical payload.
  The same identity with different contents raises `ValueError`.
- `state_for` reduces the intent's events ordered by ID. `unresolved_entries`
  scopes intents by deployment, account, and connection and returns only those
  whose reduced state is non-terminal.
- Broker observation IDs SHA-256 a canonical JSON object with broker order ID,
  uppercase status, integer cumulative fill, average rounded to six decimals,
  and reason.

## Files

- `paper-trader/backend/app/engine/execution_lifecycle.py`
- `paper-trader/backend/tests/test_execution_lifecycle.py`

## Self-review

- Verified the reducer is independent of session and broker objects.
- Checked all writes commit before returning and the only duplicate recovery is
  constrained to identical source-event contents after rollback.
- Checked JSON canonicalization is used for intent context, event payloads, and
  broker-observation fingerprints.
- Ran the new reducer/store tests with the Task 1 schema tests and compiled the
  new module.

## Concerns

- The isolated worktree does not contain its own `.venv`; verification used the
  existing repository virtual environment by absolute path. No code or database
  outside this worktree was changed.
- Terminal recognition currently reflects the existing broker vocabulary
  (`COMPLETE`, `CANCELLED`, `REJECTED`, `FAILED`). A future connector that uses a
  different terminal status must normalize it before persistence or expand the
  reducer contract with tests.
