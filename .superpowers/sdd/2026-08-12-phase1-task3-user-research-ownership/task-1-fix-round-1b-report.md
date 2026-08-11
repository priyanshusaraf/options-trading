# Task 1A.1 fix round 1B report

## Scope

- Hardened only revision `0020` and its schema migration coverage.
- Added revision-specific restart recovery for both upgrade `__0020` and downgrade
  `__0019` rebuild tables. A stale temporary table is discarded when its source is
  still authoritative; a completed temporary table is promoted when its source is
  absent.
- Restored the caller's actual SQLite foreign-key setting in `finally` on upgrade
  and downgrade, including injected failure paths.
- Refused an ownership collapse before destructive rollback work. The preflight
  rejects non-legacy owners and duplicate tenant-local project names.
- Preserved the existing generic migration-contract helper. The new 0020 parity
  helper separately compares columns, server defaults, checks, foreign keys,
  named indexes and SQL, and graph-version triggers.
- A read-only review found and the repair covered the final graph-version rename
  boundary: retry now restores `ix_graph_versions_content_address` when the table
  already has `visibility`.

## RED evidence

Before the production change, the verified interpreter reproduced these failures:

1. `test_revision_0020_downgrade_retry_after_graph_versions_temp_creation_restores_fk`
   found `PRAGMA foreign_keys = 0` after the injected graph-version temporary-table
   creation failure. Both `graph_versions` and `graph_versions__0019` remained.
2. `test_revision_0020_downgrade_retry_after_graph_versions_temp_creation_discards_stale_temp`
   retried into `sqlite3.OperationalError: table graph_versions__0019 already exists`.
3. `test_revision_0020_upgrade_failure_restores_an_already_disabled_foreign_key_state`
   found the caller's disabled state had been changed to enabled.
4. `test_revision_0020_downgrade_retry_promotes_completed_0019_temp_tables`
   failed preflight with `no such table: projects` when completed `__0019` tables
   were waiting for promotion.

The remaining required coverage exercises already-correct upgrade recovery and
historical data preservation, then remains green after the repair.

## Verification

Each new 0020 regression node was run independently with:

```text
/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python -m pytest -q <node> --tb=short
```

The independently run nodes cover graph and project stale-temp retries, completed
temp promotion, both project upgrade interruption boundaries, legacy row
preservation, fresh/upgraded contract parity, downgrade refusal, downgrade/reupgrade
convergence, and foreign-key caller-state restoration.

Required migration and tenant-isolation gate:

```text
50 passed
```

Original Task 1A.1 gate:

```text
168 passed
```

Also completed successfully:

```text
python -m compileall -q app migrations tests
git diff --check
```

The two pytest gates emit existing dependency warnings: SQLite's Python datetime
adapter deprecation and Starlette's `TestClient` deprecation.

## Boundaries and concerns

- No graph route or repository behavior changed.
- The four broker/provider files were left untouched and must not be staged.
- The duplicate-name downgrade guard is defensive: valid 0020 data cannot contain
  that duplicate because of its unique constraint, but the guard rejects a
  persisted partial/corrupt shape before it could collapse identities.
