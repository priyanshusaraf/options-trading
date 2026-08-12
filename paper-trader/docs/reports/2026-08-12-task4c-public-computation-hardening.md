# Task 4C: public computation hardening

## Decision

Shared backtest results are allowed only for a decoded, explicitly classified
`MARKET_PUBLIC` dataset and a checked-in public strategy catalog entry. The
catalog binds key, version, canonical defaults, registry module, and source-file
SHA-256. Generated strategies, IR strategies, runtime registration, private
datasets, legacy manifests, and unverifiable datasets do not query the shared
table.

The ownerless payload is a versioned v1 envelope containing an explicit result
allowlist. It never stores run, owner, row, cache-flag, or timestamp provenance.
Lookup compares expected dataset, strategy/version, policy, schema, payload
digest, and payload envelope before materialization.

Dataset publication recomputes the asserted content address before filesystem
I/O. A valid identical artifact is retained on retry; failures cannot delete an
already valid pair. A storage descriptor lets pinned workers use the storage
port without sweep code depending on local storage paths/classes.

Public lookup and publication are best-effort. Integrity and I/O failures are
bounded metrics and leave the owner-local computation intact.

## Evidence

Focused gate (exit 0):

```
PYTHONPATH=paper-trader/backend paper-trader/backend/.venv/bin/pytest -q \
  paper-trader/backend/tests/test_public_backtest_computation.py \
  paper-trader/backend/tests/test_dataset_store.py \
  paper-trader/backend/tests/test_backtest_parallel.py \
  paper-trader/backend/tests/test_backtest_pinned_worker_reads.py \
  paper-trader/backend/tests/test_backtest_tenant_isolation.py \
  paper-trader/backend/tests/test_backtest_cache.py \
  paper-trader/backend/tests/test_backtest_job_claims.py \
  paper-trader/backend/tests/test_schema_migrations.py
```

Result: focused suite exited 0.

Mutation gate (exit 0):

```
cd paper-trader/backend
PYTHONPATH=. .venv/bin/python scripts/public_backtest_computation_mutations.py
```

All 6 mutations reddened their focused guard and restored original bytes:
payload allowlist, catalog source authentication, asserted address, immutable
retry retention, parallel shared lookup, and downgrade preflight.

The broad repository suite still has a pre-existing historical-test conflict:
`test_account_scoped_state` downgrades the current head to `0017`, while the
committed `0023` migration deliberately refuses every downgrade because it would
restore a forbidden money-to-user-plane foreign key. This Task 4C change does
not alter that migration or bypass its refusal.
