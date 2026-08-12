### Task 4: Verified SQLite-to-PostgreSQL copy and cutover

**Base commit:** `b5c71c1`

**Primary artifacts:**

- Create `paper-trader/backend/app/db/copy_contract.py`
- Create `paper-trader/backend/scripts/copy_sqlite_to_postgres.py`
- Add populated execution/research/ledger copy fixtures and tests
- Create `paper-trader/docs/operations/postgresql-cutover.md`
- Modify only narrowly required configuration/docs/test utilities

**Produces:** an offline or bounded-maintenance copy from three read-only SQLite sources into three
empty PostgreSQL destination schemas/databases. It copies dependency-ordered rows in bounded
batches, repairs generated sequences, validates every relationship/constraint, and emits a
canonical, verifiable JSON report. Cutover changes database authorities only after the report is
valid. Rollback changes service authorities back; it never reverse-copies partially written
PostgreSQL data automatically.

#### Required behavior

- Accept explicit execution, research, and ledger SQLite source paths plus PostgreSQL destination
  URLs. Never infer a production target from ambient defaults.
- Open each SQLite source in read-only mode. Refuse a missing source, a source changed during the
  copy, unsupported schema head, disabled FK enforcement evidence, or a source whose current
  relational contract is invalid.
- Require an empty destination schema/database for each plane. Refuse any user table, marker,
  leftover copy table, or other payload before mutation.
- Initialize the destination through the Task 1/3 current PostgreSQL schema authorities. Copy only
  after the fresh schema validates. The copy tool owns no alternate DDL.
- Copy every current table in each plane, including authentication sessions, broker/account money
  state, execution jobs/results, public computations, research operations/items/events/runs,
  ledger snapshots/artifacts/manual fills, and current version markers as appropriate. Internal
  source-only migration proof/temp tables must refuse or be explicitly excluded with evidence.
- Use metadata dependency order and bounded executemany batches. Preserve primary keys, composite
  tenant/account identities, timestamps, floats, text/JSON bytes, binary artifacts, hashes,
  cancellation/lease tokens, and immutable evidence exactly under a documented canonical
  representation.
- Repair PostgreSQL identity/serial sequences to at least the copied maximum for every generated
  integer key. Prove the next insert cannot collide.
- Validate after copy, before reporting success:
  - exact table/plane schema head and current-schema validation;
  - per-table row counts;
  - exact primary-key sets;
  - owner/account partition counts;
  - foreign-key/check/unique validity;
  - canonical per-row and per-table digests over all copied columns;
  - selected load-bearing content-address/immutable evidence recomputation;
  - destination sequences;
  - no foreign or absent tenant reads cross scope.
- Detect source change with a start/end snapshot contract appropriate to SQLite: read-only
  transaction plus file identity/size/mtime and SQLite `data_version`/schema marker evidence. If
  the source changes or cannot be proven stable, refuse the report and leave destination
  explicitly non-cutover-ready.
- Emit one deterministic JSON report containing tool/build version, UTC start/end, redacted source
  and destination identities, source/destination schema heads, table counts, PK/digest summaries,
  sequence results, validation results, and a final content address/signature field. Never include
  credentials, session bearer plaintext, decrypted broker credentials, or raw secrets.
- The operation must be resumable only by clearing/recreating the failed empty destination. Do not
  pretend partially copied state is safe to resume. A failed run exits nonzero and never emits a
  success report.
- No fixed user or 500-tier cap. Batches are bounded by configuration and report workload size.

#### Test-first acceptance

- Capture behavioral REDs for missing tool/contracts, nonempty target acceptance, incomplete table
  inventory, sequence collision, digest mismatch, FK violation, unsupported source head, and source
  mutation during copy.
- Use a fully populated two-tenant fixture with identical local identifiers where allowed. Include
  active/revoked sessions, two broker accounts, capital/execution state, backtest pending/running/
  completed/cancelled evidence, public/private computation rows, research immutable facts and
  durable operations, ledger artifact bytes and manual-fill claims.
- Run the copy into unique live PostgreSQL 16 schemas using the supplied test URL. Compare all
  source/destination rows and relationships through the copy verifier, then run existing owner/
  account isolation repository gates against the copied destination.
- Mutation gate: change one value, omit one table, corrupt one FK/reference, and skew one sequence;
  the verifier must fail each. Restore and pass.
- Prove a second invocation refuses the now-nonempty destination.
- Keep proof proportional but deep because this is irreversible-data/cutover work. Do not build
  downgrade or malicious-temp-table matrices unrelated to copy safety.
- Run focused copy/isolation/schema gates, compile changed modules, and `git diff --check`.
- Stop uncommitted for independent review. A long broad suite is optional once; never claim a
  truncated result or rerun repeatedly.

#### Cutover runbook

Document prerequisites, maintenance/freeze, backups, source hashes, destination creation,
command invocation, report verification, configuration switch, startup/health/adversarial tenant
checks, rollback-by-URL, and explicit prohibition on automatic reverse copy. Mark PostgreSQL as
production-ready only after a real restore/copy rehearsal succeeds.

#### Exclusions

- No online dual-write or CDC.
- No account-worker lease/fencing (Task 5).
- No outbox/shared WebSocket delivery (Task 6).
- No frontend work.
- Never touch/stage the four inherited protected files.

#### Report

Write `.superpowers/sdd/2026-08-12-phase2-postgresql-production-concurrency/task-4-report.md`
with exact RED/GREEN/mutation evidence, live PostgreSQL commands/results, copied inventory, report
example/redactions, any limitations, changed paths, and protected hashes. Stop uncommitted.
