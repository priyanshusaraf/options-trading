# Phase 2 Task 3 implementation report

Date: 2026-08-13

Status: implementation and affected verification complete; uncommitted and stopped for independent review.

## Delivered

- `PT_RESEARCH_DATABASE_URL` and `PT_LEDGER_DATABASE_URL` are authoritative. The old
  `PT_RESEARCH_DB_PATH` and `PT_LEDGER_DB_PATH` remain local SQLite fallbacks only.
  Explicit URLs always win. An enabled production plane refuses an absent URL or a
  SQLite URL.
- Research and ledger engines select behavior from the URL dialect. SQLite retains
  WAL, busy timeout, normal synchronous mode, and foreign-key PRAGMAs. PostgreSQL
  receives a bounded pre-ping pool and no SQLite arguments or statements.
- The execution, research, and ledger metadata remain separate. Startup compares all
  three authorities pairwise. Equal PostgreSQL database authorities are allowed only
  with explicit, non-overlapping `search_path` schemas. SQLite continues to compare
  resolved paths.
- Research and ledger PostgreSQL startup branches before historical SQLite code. An
  empty schema creates current plane metadata, validates it, and writes one plane-owned
  version marker. A current managed schema validates without DDL. A populated unmanaged,
  wrong-version, structurally tampered, or trigger-tampered schema refuses without
  adoption or historical migration.
- The shared private-plane validator checks exact table sets, marker shape, columns,
  type affinity and declared limits, nullability, server-default semantics, primary and
  foreign keys, unique constraints, exact bounded CHECK semantics, and indexes. Its
  canonicalizer accounts only for PostgreSQL's casts and `IN`/`ANY(ARRAY)` deparse alias;
  it retains Boolean structure. Live tamper proof rejects `CHECK(TRUE)`, `OR TRUE`, and
  CASE pass-through checks under the original names while accepting intact PG deparse.
- Research immutable tables now install dialect-scoped SQLite triggers and PostgreSQL
  trigger functions/triggers for `research_experiment_spec` and
  `research_optimization_trial`. Live PostgreSQL rejects direct update/delete and
  startup refuses missing, disabled, event-mask-altered, mislinked, or pass-through
  trigger/function contracts. Validation binds each enabled BEFORE ROW UPDATE+DELETE
  trigger to the exact relation, function, and canonical `RAISE EXCEPTION` body, and
  requires `pg_get_expr(tgqual, tgrelid)` to be NULL so no `WHEN` predicate can suppress it.
- Research API, read-side, nightly, and manual-run callers consume the URL authority.
  PostgreSQL existence checks use SQLAlchemy inspection rather than filesystem checks.
  Sidecar paths never derive from or expose a database URL. Startup initializes enabled
  planes through their own authorities.
- The ledger sessionmaker cache is authority-aware and resettable. Reconfiguration and
  reset dispose the replaced engine; failed initialization disposes the candidate engine.
- PostgreSQL physical identity normalizes credentials away and treats omitted port as
  5432. Shared-database isolation reads the effective final repeated `-c search_path`
  setting, accepts both libpq spellings, and requires one explicit non-public app schema.
- Core `Settings` and isolated `PlaneSettings` load both private URLs from the same `.env`
  authority. Main passes its resolved values explicitly; standalone research/ledger
  processes read `.env` without importing or binding the execution engine. Research
  routes, startup and read APIs share the same resolver.
- Research CLI diagnostics use a redacted authority label containing backend, host, port
  and database only. Username, password, and query values are never printed.

## RED evidence

Strict test-first development captured these failures before their production changes:

1. `tests/test_plane_database_profiles.py`: `7 failed`. Research and ledger URL
   resolvers did not exist; both `make_engine` functions wrapped PostgreSQL URLs in a
   SQLite URL; URL sidecars fell back to `research.db.operations.json`; URL/search-path
   distinctness and the ledger cache reset seam were absent.
2. `tests/test_postgres_plane_schemas.py`: `7 failed` against live PostgreSQL 16.
   Research executed `SELECT ... FROM sqlite_master`; ledger executed its matching
   SQLite introspection; ledger had no version marker; research metadata lacked native
   immutable triggers.
3. The focused same-name constraint mutation reported `2 failed`: both planes accepted
   a load-bearing CHECK replaced with `CHECK(TRUE)` under the original name.
4. The ledger cache follow-up reported `2 failed`: a replaced engine was not disposed,
   and no reusable pairwise three-authority guard existed.
5. A final physical-authority probe failed because different PostgreSQL usernames were
   incorrectly treated as different databases. The physical identity now excludes credentials
   and still requires explicit distinct search paths.
6. Mutation proof temporarily restored the weaker CHECK-anchor subset comparison. The targeted
   ledger test then failed because `CHECK(id = 1 OR TRUE)` was accepted under the original name.
   Restoring full semantic-signature equality made the test pass.
7. Review-round REDs reproduced five live PostgreSQL bypasses: ledger and research CASE
   pass-through checks, plus pass-through function, disabled trigger, and mislinked trigger.
8. Four authority REDs reproduced effective-last repeated search-path, default-port, missing
   core Settings fields, and production fallback defects. A separate read-side RED proved
   `_research_authority` ignored the Pydantic/.env resolver when process env was absent.
9. The redacted-label test failed before the helper existed. Manual and nightly output
   tests then exercised credential-bearing URLs and retained proof that neither output
   surface exposes usernames, passwords, query keys, or query values.
10. Final re-review reproduced a live same-name/same-function/same-event trigger carrying
    `WHEN(FALSE)`. A direct immutable-spec UPDATE succeeded and startup accepted it. After
    `tgqual` became part of the exact catalog tuple, startup refused the same bypass.

Each RED failed on the missing contract, not on fixture setup or a mock assertion.

## GREEN evidence

Live PostgreSQL used the required disposable authority:

```text
PT_TEST_POSTGRES_URL=postgresql+psycopg://priyanshusaraf@127.0.0.1:55432/strategy_os_test \
  .venv/bin/python -m pytest \
  tests/test_plane_database_profiles.py tests/test_postgres_plane_schemas.py -q

51 collected; 38 passed, 13 skipped (wrong-plane parametrization skips), exit 0
```

Every live case creates a unique `task3_<plane>_<uuid>` schema, supplies it through an
explicit URL `search_path`, and drops it afterward. The live gate covers fresh create,
exact validation, stamping, idempotent restart, unmanaged and wrong-head refusal without
payload loss, relaxed-CHECK refusal, missing-trigger refusal, immutable update/delete,
two-owner identical research identifiers, foreign/absent research reads, research claim
race/cancel/expired takeover/old-token fencing, ledger owner/account isolation, snapshot
first-write and update races, and manual-fill claim races.

The affected historical SQLite and portable concurrency gate was run once:

```text
PT_TEST_POSTGRES_URL=postgresql+psycopg://priyanshusaraf@127.0.0.1:55432/strategy_os_test \
  .venv/bin/python -m pytest \
  tests/test_plane_database_profiles.py tests/test_postgres_plane_schemas.py \
  research_tests/test_guards.py research_tests/test_nightly.py \
  research_tests/test_operation_claim_contract.py \
  research_tests/test_operation_migration.py \
  research_tests/test_operation_migration_recovery.py \
  research_tests/test_operation_repository.py \
  research_tests/test_postgres_operation_concurrency.py tests/ledger \
  tests/test_ledger_drift_check.py tests/test_ledger_reconcile.py \
  tests/test_research_review_sources.py tests/test_research_tenant_isolation.py \
  tests/test_portable_concurrency_integration.py -q

251 collected; 238 passed, 13 skipped, exit 0
```

This includes ordinary historical research upgrade/preservation/recovery/idempotence and
unsafe-refusal proof, complete ledger tests, guards/nightly, owner-scoped read bridges,
operation claims, and Task 2 two-dialect races. A fresh startup/guard/nightly gate
reported `37 passed`, exit 0:

```text
.venv/bin/python -m pytest \
  tests/test_research_flag.py tests/test_startup_reconcile.py \
  tests/test_init_db_guard.py research_tests/test_guards.py \
  research_tests/test_nightly.py -q
```

No broad suite was attempted for Task 3. There is no broad result to claim or mark
inconclusive. One route test outside the retained gate was investigated independently:
it returns the existing `404 execution unavailable` because the fixture changes the
request owner without assigning the local runner/account to that owner. Task 3 did not
alter or weaken that money/account ownership guard.

Fresh final static verification:

- `python -m py_compile` on every changed production and focused-test module: exit 0.
- `git diff --check`: exit 0.

## Raw SQL inventory

- SQLite PRAGMAs in `research/domain/base.py` and `app/ledger/db.py` are registered only
  when the parsed dialect is SQLite.
- `research/domain/migrate.py` branches to `_migrate_postgresql` before interrupted-swap
  recovery, marker PRAGMAs, `sqlite_master`, rebuild migrations, and foreign-key PRAGMAs.
- `app/ledger/db.py` branches to `_migrate_postgresql` before its `PRAGMA table_info`,
  `sqlite_master`, rename/copy/drop scope migration.
- `research/domain/migrations/0002_owner_operations.py` and
  `0003_operation_item_checkpoints.py` retain their historical SQLite SQL and are reachable
  only from the SQLite research branch.
- Steady-state research operation reservation/JSON mutation continues through the Task 2
  concurrency port; Task 3 adds no scattered dialect SQL.

## Changed paths

- `.env.example`
- `app/api/ir_experiment_routes.py`
- `app/api/research_operation_routes.py`
- `app/api/research_review_routes.py`
- `app/core/research_read.py`
- `app/core/config.py`
- `app/db/plane_config.py`
- `app/db/plane_schema.py`
- `app/ledger/config.py`
- `app/ledger/db.py`
- `app/main.py`
- `research/config.py`
- `research/domain/base.py`
- `research/domain/migrate.py`
- `research/domain/models.py`
- `research/guards.py`
- `research/nightly.py`
- `scripts/research_run.py`
- `tests/test_plane_database_profiles.py`
- `tests/test_postgres_plane_schemas.py`
- `tests/test_research_tenant_isolation.py`
- `.superpowers/sdd/2026-08-12-phase2-postgresql-production-concurrency/progress.md`
- `.superpowers/sdd/2026-08-12-phase2-postgresql-production-concurrency/task-3-report.md`

## Protected inherited files

Task 3 did not edit or stage the four inherited dirty files. Their hashes still match the
Task 2 report:

- `app/engine/kite_venue.py`:
  `2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240`
- `app/engine/venue.py`:
  `c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae`
- `app/providers/brokers.py`:
  `d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38`
- `tests/test_broker_registry.py`:
  `13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3`

Nothing is staged or committed. The implementation is ready for independent review.
