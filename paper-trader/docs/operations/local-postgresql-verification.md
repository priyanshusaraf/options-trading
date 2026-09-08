# Local disposable PostgreSQL verification

Use the repository harness whenever a local test needs `PT_TEST_POSTGRES_URL`. Do not export or reconstruct that variable manually.

## Requirements

- Run from `paper-trader/backend` with the repository virtual environment.
- Install PostgreSQL 16 server tools. The harness searches `PATH`, Homebrew Intel and Apple Silicon prefixes, and the MacPorts PostgreSQL 16 prefix.
- Do not use this command for a persistent, shared, remote, or production database.

## Run a PostgreSQL-backed test

Pass the test command after `--`:

```bash
.venv/bin/python scripts/run_disposable_postgres.py -- \
  .venv/bin/python -m pytest -q tests/test_postgres_execution_leases.py
```

The harness creates a new temporary cluster and database, binds PostgreSQL only to `127.0.0.1` and a private socket directory, and gives the child process a fresh `PT_TEST_POSTGRES_URL`. It strips inherited PostgreSQL connection variables, including an existing `PT_TEST_POSTGRES_URL`, so the child cannot accidentally target a previously configured database.

The child exit code becomes the harness exit code. The harness attempts bounded shutdown and removes the temporary cluster after success, test failure, setup failure, SIGINT, or SIGTERM. It does not print the generated connection URL.

## Run the repository PostgreSQL contract set

```bash
.venv/bin/python scripts/run_disposable_postgres.py -- \
  .venv/bin/python -m pytest -q \
  tests/test_database_copy_contract.py \
  tests/test_portable_concurrency_integration.py \
  tests/test_postgres_execution_leases.py \
  tests/test_postgres_execution_schema.py \
  tests/test_postgres_outbox.py \
  tests/test_postgres_plane_schemas.py \
  tests/test_postgresql_restore_live.py \
  tests/test_strategy_admission_repository.py \
  research_tests/test_strategy_admissions.py
```

Inspect the pytest summary. A PostgreSQL test reported as skipped is not passing PostgreSQL evidence.

## Boundary and nonclaims

This command proves local behavior against a fresh PostgreSQL 16 process. It does not prove managed PostgreSQL, production roles or TLS, capacity, backup retention, recovery objectives, production readiness, deployment, or live authority. The disposable cluster is deleted and must never hold data that needs to survive the command.
