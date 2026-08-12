### Task 3: PostgreSQL research and ledger planes

**Base commit:** `c079001`

**Primary files:**

- Modify `paper-trader/backend/research/config.py`
- Modify `paper-trader/backend/research/domain/base.py`
- Modify `paper-trader/backend/research/domain/migrate.py`
- Modify `paper-trader/backend/app/ledger/config.py`
- Modify `paper-trader/backend/app/ledger/db.py`
- Modify only the startup/plane configuration callers required to use these authorities
- Add focused SQLite/PostgreSQL plane, schema, isolation, and operation/claim tests

**Produces:** explicit database URL authorities for the research and ledger planes. Local mode
retains the existing separate SQLite files. PostgreSQL production may use separate databases or
separate PostgreSQL schemas, but the three logical planes remain structurally separate. Fresh
PostgreSQL creates the current schema, validates it, and stamps a small plane-owned version marker.
Existing custom historical migrations remain SQLite-only.

#### Required behavior

- Add `PT_RESEARCH_DATABASE_URL` and `PT_LEDGER_DATABASE_URL` as the authoritative URLs. Preserve
  `PT_RESEARCH_DB_PATH` and `PT_LEDGER_DB_PATH` only as local SQLite fallbacks when their URL is
  absent. Do not silently prefer a path over an explicit URL.
- Production configuration must reject absent or SQLite research/ledger URLs when that plane is
  enabled. Development/test may retain SQLite.
- Apply SQLite PRAGMAs only to SQLite. Configure PostgreSQL engines without SQLite connection
  arguments or statements.
- Preserve separate declarative metadata and session factories for execution, research, and
  ledger. Do not merge schemas or let one plane's initializer create another plane's tables.
- Replace steady-state SQLite-only startup inspection with dialect-aware SQLAlchemy inspection.
- Research PostgreSQL startup must support:
  1. empty database/schema: create current metadata, install required immutable triggers, validate,
     and stamp current research head;
  2. managed current head: validate without destructive DDL and start idempotently;
  3. populated unmanaged or wrong-version schema: refuse without mutation.
- Ledger PostgreSQL startup must have the same three branches and a small ledger-owned version
  marker. Historical SQLite scope migration remains SQLite-only.
- Port load-bearing research immutability for `research_experiment_spec` and
  `research_optimization_trial` to PostgreSQL trigger functions/triggers. Preserve existing SQLite
  trigger behavior.
- Validate a proportional current-schema contract for both PostgreSQL planes: required tables,
  columns/types/nullability/default semantics, primary/foreign/unique/check constraints, indexes,
  and required immutable triggers. Do not build an exotic downgrade/interruption matrix.
- Prove owner-scoped research and owner/account-scoped ledger behavior on real PostgreSQL. Foreign
  and absent identifiers must remain indistinguishable at repository/service boundaries.
- Re-run research operation claim/cancel/takeover and ledger snapshot/manual-fill concurrency on
  the explicit plane URLs. Reuse the Task 2 concurrency port; do not add scattered dialect SQL.
- Update research guards so distinctness is evaluated safely for URLs as well as SQLite paths.
  Equal execution/research/ledger database authorities must refuse unless distinct PostgreSQL
  schemas are explicitly present and different.
- Do not add a fixed 500-user or other product cap. Keep admission tied to measured workload and
  configured host budgets.

#### Test-first acceptance

- Capture REDs for PostgreSQL research/ledger engine creation, raw PRAGMA/sqlite_master paths,
  missing version markers, missing immutable triggers, and SQLite-only migration calls.
- Use the live PostgreSQL 16 test authority through
  `PT_TEST_POSTGRES_URL=postgresql+psycopg://priyanshusaraf@127.0.0.1:55432/strategy_os_test` with
  unique test-owned schemas which are dropped after each test.
- Prove fresh create → validate → stamp → idempotent second startup for each plane.
- Prove a populated unmanaged target and a tampered current target are refused without row loss.
- Prove two tenants with identical local identifiers cannot cross research or ledger scope.
- Keep existing historical SQLite migration suites green. Ordinary migration proof is
  proportional: upgrade/preservation/idempotence/basic unsafe refusal only.
- Run focused affected regression gates, compile changed modules, and `git diff --check`.
- A broad suite may be attempted once if useful, but an unavailable/truncated result must be
  reported as inconclusive rather than rerun repeatedly or claimed as passing.

#### Explicit exclusions

- No SQLite-to-PostgreSQL data copy or production cutover tool; that is Task 4.
- No account-worker lease/fencing model; that is Task 5.
- No transactional outbox, replicated WebSocket delivery, or frontend work.
- Do not touch or stage the four inherited protected files:
  `app/engine/kite_venue.py`, `app/engine/venue.py`, `app/providers/brokers.py`,
  `tests/test_broker_registry.py`.

#### Report

Write `.superpowers/sdd/2026-08-12-phase2-postgresql-production-concurrency/task-3-report.md`
with RED/GREEN evidence, exact live PostgreSQL commands/results, SQLite regression results, any
inconclusive broad run, raw SQL inventory, changed paths, and protected-file hashes. Stop
uncommitted for independent review.
