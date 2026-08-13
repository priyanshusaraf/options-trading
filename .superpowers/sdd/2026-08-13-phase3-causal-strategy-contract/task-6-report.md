# Task 6 report: execution-plane immutable admission persistence

Risk classification: **Critical**. A receipt that can be forged, mutated, or read under another
owner could later grant research, backtest, deployment, or execution authority to strategy bytes
that were never causally admitted.

## Scope delivered

- Added migration `0034` and owner-scoped, immutable `strategy_admissions` records.
- Added `put`, `get`, and `require_current`. They canonicalize receipt bytes, recompute the
  address, and compare every persisted identity field before accepting a retry or use.
- Added database-level SQLite and PostgreSQL immutability. PostgreSQL uses SQLSTATE `55000` and
  startup validates the exact trigger contract rather than only a trigger name.
- Added nullable, format-checked `admission_address` references to all nine execution consumers.
  Null remains the explicit `LEGACY_UNADMITTED` state.
- Classified `strategy_admissions` as USER. Consumer tables keep their current planes.

Causal admission remains proof of Phase 3 causality only. This task does not create complete
Strategy Preflight, provider, role binding, data-truth, resource, derivatives, or live authority.

## RED/GREEN evidence

Observed RED before implementation:

```text
.venv/bin/python -m pytest -q tests/test_strategy_admission_repository.py
4 failed: ModuleNotFoundError: app.core.strategy_admissions
```

Focused GREEN after implementation:

```text
.venv/bin/python -m pytest -q tests/test_postgres_execution_schema.py \
  tests/test_strategy_admission_repository.py tests/test_db_planes.py
36 passed, 1 skipped

.venv/bin/python -m pytest -q \
  tests/test_strategy_admission_repository.py \
  tests/test_schema_migrations.py::test_revision_0034_adds_immutable_admissions_and_nullable_consumer_references \
  tests/test_schema_migrations.py::test_models_and_migrations_agree \
  tests/test_postgres_execution_schema.py::test_postgresql_create_profile_installs_immutable_fact_triggers \
  tests/test_postgres_execution_schema.py::test_postgresql_immutable_trigger_validator_rejects_one_missing_trigger \
  tests/test_postgres_execution_schema.py::test_strategy_admission_trigger_validator_rejects_same_name_inert_contract \
  tests/test_db_planes.py
20 passed
```

The tests name the concrete failure hypotheses: cross-owner lookup, exact duplicate/retry,
same-key conflicting bytes, forged canonical address, direct SQL UPDATE/DELETE, nullable consumer
columns, migration head/schema parity, trigger SQLSTATE, disabled/conditional PostgreSQL trigger,
and USER-plane classification.

Compilation and whitespace checks passed. Protected-file SHA-256 values remained exactly:

```text
app/engine/kite_venue.py             2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240
app/engine/venue.py                  c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae
app/providers/brokers.py             d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38
tests/test_broker_registry.py        13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3
```

Live PostgreSQL 16 proof after the service was supplied:

```text
PT_TEST_POSTGRES_URL='postgresql+psycopg://priyanshusaraf@127.0.0.1:55432/strategy_os_test' \
  .venv/bin/python -m pytest -q \
  tests/test_strategy_admission_repository.py::test_postgresql_raw_receipt_mutation_is_sqlstate_55000_and_retains_bytes \
  tests/test_postgres_execution_schema.py::test_optional_postgres_fresh_schema_is_complete_and_idempotent
2 passed
```

The receipt test creates one unique schema, writes through the repository, issues raw SQL UPDATE
and DELETE, observes SQLSTATE `55000` for both, rolls back each transaction, and reads the
byte-identical receipt afterward. The schema is dropped during cleanup. No broad backend or
historical-migration matrix was run; Task 12 owns the Phase 3 boundary suite.

## Freeze state

Independent final review returned **SPEC PASS / QUALITY PASS** with no remaining finding. The
slice remains intentionally uncommitted and unstaged for the scoped parent commit.
