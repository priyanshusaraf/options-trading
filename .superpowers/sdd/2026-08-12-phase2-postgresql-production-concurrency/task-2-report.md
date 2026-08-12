# Phase 2 Task 2 implementation report

Date: 2026-08-12

Status: implementation and affected verification complete; uncommitted and stopped for independent review.

## Baseline and scope

Work began from `8b2014a` and resumed after the Task 1 follow-up at
`d9b06561e01b72e0d68f9a6f26d14e1b8231adbf`. The implementation is in the shared
`codex-execution-foundation` worktree. Nothing has been staged or committed.

The change introduces one small dialect boundary in `app/db/concurrency.py`:

- SQLite uses short `BEGIN IMMEDIATE` reservations. The helper records the exact
  SQLAlchemy transaction it opened, allows an explicit `session.begin()` before its
  first SQL statement, permits repeat calls only in that marked transaction, and
  refuses an unsafe upgrade from an already-used deferred transaction.
- PostgreSQL uses transaction-scoped advisory locks for count-and-admit decisions,
  `FOR UPDATE SKIP LOCKED` for queue candidates, and `FOR UPDATE` for mutable rows.
- Repository code retains the business predicates, lease tokens, expiries,
  cancellation checks, and fencing updates. Dialect branches do not escape the
  concurrency module.
- The helper also owns the only steady-state dialect-specific JSON-array append:
  SQLite JSON1 and PostgreSQL JSONB expressions have identical idempotent semantics.
- Public SQLAlchemy session events record Core/ORM DML and flushed unit-of-work
  changes until the root transaction ends. Clean-snapshot restart and independent
  capital bootstrap consult this provenance, so they cannot mistake an already
  executed write for a disposable read transaction.

There is no fixed user cap. Admission remains bounded by the existing workload and
host configuration.

## Production callers changed or adjudicated

### Backtest

- `app/backtest/repository.py`: candidate selection now uses PostgreSQL
  `FOR UPDATE SKIP LOCKED`; the existing conditional claim remains the winner and
  fencing authority.
- `app/backtest/sweep.py`: all three admission/reclaim `BEGIN IMMEDIATE` calls use
  the centralized reservation helper. SQLite keeps its short writer reservation;
  PostgreSQL uses the matching advisory-lock scope.

### Research

- `research/domain/operations.py`: enqueue and active-item admission use the
  reservation helper. Long-lived clean SQLite read snapshots are ended before the
  reservation; sessions with pending writes fail closed.
- Claim candidates use `FOR UPDATE SKIP LOCKED` on PostgreSQL.
- Both fenced completion paths now append completed-run receipts portably and
  idempotently. The token, expiry, and cancellation predicates remain on the same
  atomic update.
- Owner-scoped latest/list reads are non-mutating observations. They do not allocate,
  claim, or publish a global singleton, so no reservation is required. All actual
  global/owner claim and admission decisions are covered above.

### Money, evidence, and account-scoped mutation

- `app/core/execution_book.py`: an existing capital read remains a read-only fast
  path. A missing row is bootstrapped in a separate short transaction serialized by
  broker account. The caller's clean read snapshot is ended before reread so SQLite
  sees the committed row. Pending caller writes are never rolled back; bootstrap
  refuses instead.
- `app/ledger/service.py::claim_manual_fill`: a conditional update gives the evidence
  claim one winner and reports the winning trade to losers.
- `app/ledger/service.py::write_snapshot`: existing snapshots use a version-qualified
  update. First insert uses a savepoint and maps only the competing unique-key loss to
  `VersionConflict`; unrelated integrity failures are not masked.
- `app/core/paper_authority.py::_for_update`: PostgreSQL locks the revision row and
  SQLite reserves the short writer lane before validating and mutating the revision.

### OAuth state and external I/O

The original callback-state consume operation was already a valid conditional-update
CAS. It is now an explicit seam with race proof. The callback commits the spent state
before broker exchange, so slow external I/O retains neither SQLite's writer lane nor
a PostgreSQL row lock. Credential storage runs in a fresh short transaction and
revalidates the active user session, user, organization, owner membership, connection,
and broker account. The revalidation predicates now sit on the credential `UPDATE`
itself. The connection's active status is checked at the same row-lock/write point,
so revoke-before-store refuses and store-before-revoke is followed by revoke clearing
the credential. Revocation or demotion during exchange yields a generic refusal,
writes no credential, and leaves the callback state spent.

### Deliberate exclusions

- Historical research migrations are one-time SQLite migration machinery, not
  steady-state shared-database callers.
- The public dataset-store SQLite index is intentionally local and is not a shared
  Strategy OS database plane.

## Behavioral RED evidence

Production changes followed behavioral RED before GREEN. The observed failures were:

1. PostgreSQL research admission attempted raw `BEGIN IMMEDIATE`.
2. PostgreSQL backtest candidate SQL lacked `FOR UPDATE SKIP LOCKED`.
3. Two real SQLite manual-fill sessions both won the same evidence claim:
   `['won', 'won']`.
4. The PostgreSQL capital seam read money state before reserving the account scope.
5. The paper-authority mutation select compiled without `FOR UPDATE` on PostgreSQL.
6. An existing SQLite capital read retained the writer lane; a concurrent writer did
   not proceed while the reader remained open.
7. A pre-existing deferred SQLite transaction was silently treated as reserved, and
   a missing-capital bootstrap could discard pending caller state.
8. Both live PostgreSQL research completion paths failed with
   `UndefinedFunction: json_each(text) does not exist`.
9. The OAuth callback-state CAS test could not import the not-yet-extracted consume
   seam.
10. In the real PostgreSQL snapshot race, two writers based on version 1 both returned
    version 2.
11. In the blocked-exchange identity race, demotion still returned 200 and stored the
    replacement credential.

The later helper-level REDs also distinguished an explicit transaction before first
SQL (safe and allowed) from SELECT-then-reserve (unsafe and refused), and proved the
missing-row capital path through a real SQLite session.

### Independent review round 1

Review blocked on two additional interleavings. Both were reproduced before the
follow-up production changes:

1. Direct `Session.execute(update(...))` does not populate `session.new`, `dirty`, or
   `deleted`. The clean-read helper, mutation helper, SQLite capital path, and live
   PostgreSQL capital path all failed to raise. The old capital implementation could
   roll back the caller's already-executed update.
2. A route-level OAuth callback was paused immediately before its credential update.
   A second real session committed connection revocation, then released the callback.
   On both SQLite and PostgreSQL the old implementation returned 200. This is the
   precise mutation caught by the new test: removing the active-status predicate from
   the credential update again permits a revoked row to acquire ciphertext.

The first focused RED run reported `3 failed`; the dual-dialect capital/OAuth RED run
reported `4 failed`. The fix uses public `Session` events for write provenance and a
single owner/account/status/auth-qualified credential update.

## GREEN evidence

Live PostgreSQL 16 was exercised at the dedicated test database supplied for this
task. The optional gate was not skipped.

The principal two-dialect integration module runs each race against file-backed
SQLite and a unique, test-owned PostgreSQL schema which it drops afterward. It covers:

- one claim winner;
- expired takeover and old-token fencing;
- cancellation fencing;
- bounded backtest admission;
- bounded research active-item admission;
- terminal research completion and both receipt paths;
- capital bootstrap;
- manual-fill evidence claim;
- snapshot update CAS and first-insert races;
- OAuth callback-state consumption; and
- OAuth callback credential/revoke linearization;
- paper-authority revision mutation.

Command:

```text
PT_TEST_POSTGRES_URL=postgresql+psycopg://priyanshusaraf@127.0.0.1:55432/strategy_os_test \
  .venv/bin/python -m pytest \
  tests/test_portable_concurrency_integration.py -q
```

Original result: `28 passed`. After independent-review coverage was added, this module
contains `32` dual-dialect cases and passed inside the retained affected gate below.

The final affected regression gate included the concurrency boundary tests, live
portable races, backtest claim suites, research operation suites, the complete ledger
test directory, capital books, paper authority, and connection routes.

```text
PT_TEST_POSTGRES_URL=postgresql+psycopg://priyanshusaraf@127.0.0.1:55432/strategy_os_test \
  .venv/bin/python -m pytest \
  tests/test_db_concurrency.py tests/test_postgres_claim_sql.py \
  tests/test_postgres_money_concurrency.py \
  research_tests/test_postgres_operation_concurrency.py \
  tests/test_portable_concurrency_integration.py tests/test_backtest_job_claims.py \
  research_tests/test_operation_claim_contract.py \
  research_tests/test_operation_repository.py tests/ledger \
  tests/test_capital_books.py tests/test_paper_authority.py \
  tests/test_connection_routes.py -q
```

Original result: `260 passed`, exit 0. After the review fixes, the same bounded command
reported `267 passed`, exit 0. An independent controller run before review reported
`100 passed` on its widened live gate.

Additional checks:

- `python -m compileall -q` on every changed production module: exit 0.
- `git diff --check`: exit 0.
- Steady-state raw-SQL inventory for `BEGIN IMMEDIATE`, `INSERT OR IGNORE/REPLACE`,
  `json_each`, and `json_insert`: only `app/db/concurrency.py` plus the explicitly
  excluded historical migration. The local dataset-store upsert remains within its
  deliberate local-index boundary.

A full `tests research_tests` run was attempted and reached 96%, but its output
exceeded the retained tool context and the completed process handle was no longer
available. Its final exit status and summary cannot be recovered, so this report does
not claim that broad run passed. It was not rerun after the controller asked to stop
additional testing. The bounded affected gates above completed with retained results.

## Protected worktree state

The four pre-existing dirty files were not edited by this task and remain byte-for-byte
at their recorded hashes:

- `app/engine/kite_venue.py`:
  `2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240`
- `app/engine/venue.py`:
  `c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae`
- `app/providers/brokers.py`:
  `d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38`
- `tests/test_broker_registry.py`:
  `13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3`

They have not been staged.

## Review concerns

- Pysqlite does not mark a SELECT as `driver_connection.in_transaction`, although
  SQLAlchemy has enlisted the connection. The centralized helper therefore uses the
  SQLAlchemy transaction's enlisted-connection state as a narrow fallback to reject
  SELECT-then-upgrade. Dedicated tests cover no-SQL explicit begin, SELECT refusal,
  helper-owned repeat calls, and clean-snapshot restart.
- Write provenance does not use that private fallback. It is recorded with public
  SQLAlchemy `do_orm_execute`, `before_flush`, and `after_transaction_end` events and
  is cleared only when the root transaction ends. Tests cover prior Core DML on both
  database dialects and both SQLite helper paths.
- PostgreSQL advisory locks intentionally serialize only matching admission scopes;
  row-level claim concurrency remains available through `SKIP LOCKED`.
- No ordinary migration matrix was added. Migration-only SQLite SQL remains scoped to
  the explicitly excluded historical path.

The files are ready for independent review and remain uncommitted.
