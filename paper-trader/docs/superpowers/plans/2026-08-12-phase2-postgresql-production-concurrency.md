# Phase 2 PostgreSQL and Production Concurrency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a real PostgreSQL production profile, move shared work and execution ownership onto
portable database contracts, prove SQLite-to-PostgreSQL cutover and restore, and allow API/worker
capacity to scale without changing tenant identities or execution safety.

**Architecture:** Keep the modular monolith and its execution, research and ledger planes. SQLite
remains the local/test/single-node profile. PostgreSQL becomes the shared production authority.
Fresh PostgreSQL databases build and validate the current schema contract; they do not replay the
SQLite-specific historical rebuild migrations. Existing SQLite data moves through a separate,
read-only-source copy/cutover command with row, relationship and content-digest verification.

**Tech Stack:** Python 3.13, SQLAlchemy 2, Alembic, PostgreSQL 16+, psycopg 3, FastAPI, Pytest,
Docker Compose and GitHub Actions service containers where available.

## Global constraints

- Preserve Phase 1 tenant/account/authentication/actor boundaries and live-money invariants.
- No fixed user-count capacity constant. Admission uses measured workload dimensions.
- Exactly one fenced actor may submit orders for a broker account.
- PostgreSQL is authoritative for durable work and execution ownership. A notification channel is
  never the source of truth.
- SQLite remains supported for local/test/single-node use; dialect choice is explicit by URL.
- Do not run SQLite DDL/PRAGMA recovery migrations against PostgreSQL.
- Copy/cutover reads the SQLite source without mutating it and refuses on any count, relationship,
  identity, content-digest or schema-version mismatch.
- No frontend work in Phase 2. Preserve the four protected broker/provider working-tree files.
- Verification is proportional: deep failure proof for money, claims/fencing, authentication,
  tenant isolation, copy/cutover and irreversible loss; ordinary portability gets focused tests.

---

### Task 1: Database URL and PostgreSQL execution-plane profile

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/db/engine.py`
- Modify: `backend/app/db/session.py`, `backend/app/db/migrate.py`
- Modify: `backend/requirements.txt`, `.env.example`
- Create: `docker-compose.postgres.yml`
- Create: `backend/tests/test_database_profiles.py`
- Create: `backend/tests/test_postgres_execution_schema.py`

**Produces:** one `PT_DATABASE_URL` authority; SQLite URL derived from `PT_DB_PATH` only at the
legacy compatibility boundary; dialect-specific connection settings; fresh PostgreSQL
create-current-schema + validate + stamp path; explicit refusal to adopt/replay a populated
unmanaged PostgreSQL database.

- [ ] Write behavioral tests for URL precedence, SQLite compatibility, PostgreSQL engine options,
  no SQLite PRAGMAs on PostgreSQL, production URL requirement and empty/populated startup states.
- [ ] Add psycopg and a local PostgreSQL 16 compose profile with a health check and no embedded
  production credentials.
- [ ] Make session/migration startup consume an injected engine factory instead of an import-time
  SQLite singleton. Keep the exported compatibility handles while callers are converted.
- [ ] On empty PostgreSQL, `Base.metadata.create_all`, validate the full current relational model,
  stamp head and prove a second startup is read-only/idempotent. Refuse a populated unmanaged DB.
- [ ] Run the current SQLite migration/profile gates plus PostgreSQL schema/auth/tenant/money smoke
  when `PT_TEST_POSTGRES_URL` is available. Commit the coherent profile.

### Task 2: Portable transaction, claim and query primitives

**Files:**
- Create: `backend/app/db/concurrency.py`
- Modify: `backend/app/backtest/{repository,sweep}.py`
- Modify: `backend/research/domain/operations.py`
- Modify scoped money/account claim/lease repositories found by the caller audit
- Test: backtest/research claim race and cancellation suites on both dialects

**Produces:** a small database concurrency port: SQLite short `BEGIN IMMEDIATE` reservation and
PostgreSQL row-lock/`FOR UPDATE SKIP LOCKED` reservation, with the same token/lease/fencing result.

- [ ] Capture PostgreSQL failures for every raw `BEGIN IMMEDIATE`, SQLite-only upsert and global
  latest/claim operation used in production.
- [ ] Move reservation/claim SQL behind focused helpers; do not scatter dialect branches.
- [ ] Run two-session races on SQLite and PostgreSQL proving one winner, token fencing,
  cancellation, takeover and bounded admission.
- [ ] Commit only after money/job mutation paths contain no unfenced dialect fallback.

### Task 3: PostgreSQL research and ledger planes

**Files:**
- Modify: `backend/research/domain/base.py`, `migrate.py`
- Modify: `backend/app/ledger/{config,db}.py`
- Modify plane configuration and startup
- Test: research and ledger PostgreSQL schema, owner/account isolation and operation/claim gates

**Produces:** explicit URLs for all three planes. Production may use separate databases or
separate PostgreSQL schemas; local mode keeps separate SQLite files. Fresh PostgreSQL uses current
metadata plus exact validation/version stamp. Existing custom SQLite migrations remain SQLite-only.

- [ ] Prove foreign/absent research and ledger behavior on PostgreSQL before enabling the profile.
- [ ] Port immutable triggers/checks/indexes to PostgreSQL-compatible SQLAlchemy DDL.
- [ ] Replace SQLite introspection in steady-state startup with SQLAlchemy inspection.
- [ ] Keep historical SQLite migration tests intact; add focused PostgreSQL current-schema gates.

### Task 4: Verified SQLite-to-PostgreSQL copy and cutover

**Files:**
- Create: `backend/scripts/copy_sqlite_to_postgres.py`
- Create: `backend/app/db/copy_contract.py`
- Create: copy fixtures/tests covering every execution, research and ledger table
- Create: `docs/operations/postgresql-cutover.md`

**Produces:** offline/bounded-maintenance copy with read-only SQLite source, empty PostgreSQL
destination, dependency-ordered batch inserts, sequence repair, and a signed/verifiable report of
schema versions, row counts, PK sets, relationships and canonical row digests.

- [ ] Refuse nonempty destination, unsupported source version, missing private plane, FK/check
  violation, digest mismatch or concurrent source change.
- [ ] Copy a fully populated two-tenant fixture including money, auth sessions, jobs, research,
  ledger artifacts and immutable hashes; compare exact public/private values and relationships.
- [ ] Add cutover/rollback instructions. Rollback changes service URLs; it never reverse-copies
  partially written production data automatically.

### Task 5: Shared account leases, fencing and replicated control APIs

**Files:**
- Add account-worker assignment/lease models and migration
- Create: `backend/app/execution/leases.py`
- Modify runner/cell startup and every broker-submit authority check
- Test duplicate-worker, expiry, takeover, reconciliation and crash-after-submit

**Produces:** one durable active lease per broker account with monotonically increasing fencing
token, owner/account/cell/worker identity, heartbeat/expiry and takeover history. Every broker
submission checks the current fence at the point of use.

- [ ] Two hosts race: one wins; the loser cannot submit or mutate execution state.
- [ ] Expiry/takeover requires journal replay and broker reconciliation before entries resume.
- [ ] API replicas resolve the active cell from shared authority, never process-global runner.
- [ ] Keep exits/risk reduction safe through explicitly reviewed emergency behavior.

### Task 6: Shared event delivery and cache invalidation

**Files:**
- Create a durable transactional outbox and dispatcher
- Add PostgreSQL LISTEN/NOTIFY wake-up adapter; retain polling fallback
- Modify WS manager gateway to consume scoped events across API replicas
- Test duplicate/out-of-order delivery, reconnect/catch-up and exact tenant/account channels

**Produces:** database outbox as authority and notification as a wake-up. Events include explicit
public/private classification and owner/account scope. A replica can disappear without losing an
event; duplicate delivery is idempotent.

### Task 7: Backup, restore, failure and workload proof

**Files:**
- Add PostgreSQL backup/PITR/restore runbooks and automated verification scripts
- Add multi-replica/API-worker/account-cell load harness and reports
- Update current-state documentation

**Acceptance:** restore into a clean environment and pass tenant/money/content digests; demonstrate
duplicate-worker fencing, API replica loss, job takeover, event catch-up and bounded overload.
Publish p50/p95/p99, throughput, connection-pool wait, lock wait, memory, WS bytes, recovery time
and cost by workload vector. No workload tier becomes a product ceiling.

