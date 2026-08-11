# Task 2 report: money repository account isolation

Date: 2026-08-11

## Contract delivered

- Revision `0019` replaces `deployments.account_id` with the durable
  `broker_account_id`, backfills `default` to `account.default`, and makes deployment
  names unique per owner.
- The eleven account-specific money tables carry a non-null broker-account foreign key
  and owner/account index. SQLite rebuilds preserve all legacy columns, payloads and
  timestamps. Downgrade refuses tenant-local names or non-legacy account rows that 0018
  cannot represent.
- Deployment, lifecycle, analytics, connection, IR deployment, retention, calendar,
  websocket, broker, reconciliation and export boundaries require trusted owner/account
  scope and apply both predicates in SQL.
- Paper and live brokers stamp owner/account on positions, trades, equity snapshots,
  journals, intents and events. Signal writes use the runner's trusted composition.
- Connection routes derive the sole active broker account from the authenticated owner;
  no request body accepts owner or broker-account identity.
- Legacy behavior suites use an explicit test-only compatibility proxy. The new isolation
  suite exercises the strict production APIs directly.

## TDD evidence

Initial behavioral RED:

- `tests/test_money_repository_isolation.py`: 15 intended failures, no collection
  failures. The failures exposed global deployment names/queries, missing account facts,
  guessed lifecycle-intent reads, analytics leakage, and unscoped broker writes.

Focused GREEN:

- `tests/test_money_repository_isolation.py`: 15 passed.
- Migration/schema/account isolation aggregate:
  `tests/test_schema_migrations.py tests/test_account_scoped_state.py
  tests/test_money_repository_isolation.py`: 62 passed.
- Book, calendar and websocket isolation: 39 passed.
- Live entry durability: 14 passed.
- Poisoned-position refusal and restart tag recovery: 9 passed.
- Cockpit: 39 passed.
- Execution lifecycle schema: 3 passed.
- Connection/split-routing/manual-ledger group: 85 passed.
- Connection store: 30 passed.
- Accounting, broker, route and recovery regression group: green; one independent
  order-dependent log-buffer assertion failed in a large explicit concatenation and
  passed when rerun alone. It is not a Task 2 scope failure.

The first full-suite run was an inventory, not an acceptance run. It exposed stale legacy
test call sites and one migration downgrade defect. All captured clusters were repaired and
are green in focused runs.

Final acceptance:

- Command: `.venv/bin/python -m pytest -q tests research_tests --tb=short`
- Result: exit 0; 4,171 collected, 4,165 passed and 6 skipped.
- Warnings: the existing Starlette `httpx` deprecation plus Python 3.13 SQLite datetime
  adapter deprecations; no errors or failures.

## Migration notes

- Head: `0019` (`20260811_0019_money_repository_account_scope.py`).
- Revisions 0015-0018 were not modified.
- The 0019 downgrade restores 0014's inline `entry_intent_id` references. It removes the
  reflected table-level duplicate so the immutable 0014 deep downgrade remains runnable on
  SQLite.
- Foreign-key enforcement is restored after every rebuild and append-only execution-event
  triggers are recreated.

## Known boundary

The current connection HTTP surface deliberately requires exactly one active broker account
for an owner. Selecting among multiple accounts is a later principal/composition feature; the
route refuses ambiguity with 409 rather than accepting an account id from an untrusted body.
