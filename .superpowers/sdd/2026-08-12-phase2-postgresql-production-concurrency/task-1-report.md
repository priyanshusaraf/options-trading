# Task 1 report: PostgreSQL execution-plane profile

## Delivered

- `PT_DATABASE_URL` now selects the execution database. When absent, local and test use the
  legacy `PT_DB_PATH` SQLite boundary. `PT_PRODUCTION=1` requires a PostgreSQL URL and rejects
  SQLite explicitly.
- `app.db.engine` creates dialect-specific engines. SQLite retains its thread, WAL, foreign-key
  and busy-timeout profile. PostgreSQL gets a pre-ping pool with bounded size and no SQLite
  connection setup.
- Session startup uses the engine factory while retaining the exported `engine` and
  `SessionLocal` compatibility handles. The existing mock reset path is restricted to SQLite,
  so it cannot drop a PostgreSQL execution database.
- Empty PostgreSQL starts from the current ORM schema, validates all expected tables and columns,
  then stamps Alembic head. A managed PostgreSQL database at head is read-only at startup. A
  populated unmanaged database, or a managed database behind head, is refused instead of running
  SQLite historical migrations.
- Digest checks compile to PostgreSQL regular expressions instead of SQLite `GLOB` expressions.
  JSON guards retain their semantics on the legacy `TEXT` columns: PostgreSQL casts to `JSONB`,
  requires the expected string or numeric property, and compares it with the relational identity.
  PostgreSQL partial indexes now carry the same predicates as SQLite for active saved views,
  paper authorities and shadow authorities. PostgreSQL also installs immutable-fact triggers for
  execution order events, graph versions and review snapshots, matching the existing SQLite
  database guards.
- Added `psycopg[binary]` and a PostgreSQL 16 compose profile. The compose file requires a
  caller-supplied password and contains no production credential.
- Added a `PT_TEST_POSTGRES_URL` opt-in fresh-schema test. It drops only the supplied test
  database's execution tables before proving create, validate, stamp, and second-startup
  idempotence.

## Regression cleanup found during the gate

These failures reproduced in a clean detached `be533a2` worktree before any change:

- the non-mock `init_db` test stub lacked `api_token`;
- current ORM defaults did not match migration 0031's `universe_preferences` server defaults;
- `/api/health` omitted its existing schema-report helper.

The task fixes those narrow defects. The model default correction also keeps fresh PostgreSQL
creation aligned with the current relational contract.

## Evidence

From `paper-trader/backend`:

```text
.venv/bin/python -m pytest tests/test_database_profiles.py \
  tests/test_postgres_execution_schema.py tests/test_sqlite_busy_timeout.py \
  tests/test_migrate_schema_frozen.py tests/test_init_db_guard.py \
  tests/test_schema_migrations.py::test_models_and_migrations_agree \
  tests/test_health_schema_version.py
36 passed, 1 skipped
```

The skipped test is the explicit live PostgreSQL integration gate. This host has neither Docker
nor `psql`, and `PT_TEST_POSTGRES_URL` was not configured. It has not been presented as a live
PostgreSQL pass.

Additional SQLAlchemy PostgreSQL mock-engine compilation covered 45 execution tables. It rejects
generated `json_valid`, `json_extract`, `GLOB`, `PRAGMA`, `sqlite_master` and `rowid`; it also
requires native JSONB guards and all three PostgreSQL partial-index predicates. A paired SQLite
DDL test proves the existing JSON checks and partial-index predicates are unchanged. The mock
create profile also requires PostgreSQL immutable-fact functions and triggers for all three
existing SQLite-protected fact tables. Current-schema validation checks expected tables, column
types/nullability/defaults, primary keys, foreign keys (including actions), named unique and CHECK
constraint expressions, indexes and partial predicates. Focused tamper cases prove it rejects each
of those contract drifts without needing a recovery matrix. Managed-head PostgreSQL startup also
queries the database for every immutable-fact trigger and refuses to serve when one is missing.
The CHECK manifest uses a bounded PostgreSQL canonicalizer for this model's owned `CAST(... AS
JSONB)` versus reflected `::jsonb` syntax; a realistic PostgreSQL-inspector fixture proves that
an intact fresh schema passes while the same-name `CHECK (TRUE)` tamper remains rejected.

`git diff --check` completed with no output.

Final verification also compiled every changed production and focused-test module with
`python -m py_compile` successfully.

## Remaining verification

Run the opt-in PostgreSQL gate against an isolated disposable database:

```text
PT_TEST_POSTGRES_URL=postgresql+psycopg://... .venv/bin/python -m pytest \
  tests/test_postgres_execution_schema.py
```

Do not point this variable at a shared or production database because the test intentionally
creates and drops the execution schema.
