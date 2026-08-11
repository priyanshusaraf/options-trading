# Task 1A.3 fix round 2 report

Starting commit: `adfa499`.

## Evidence added

- The 0021 contract snapshot now includes ordered primary-key columns. A reversed composite
  key therefore fails fresh-versus-upgraded parity instead of being hidden by normalization.
- A populated 0020 lineage uses literal project, graph, version, layout, archive, paper, and
  shadow values. Upgrade checks exact authored JSON, hash, timestamps, revision, visibility,
  legacy owner backfill, and by-value MONEY provenance after the graph FK is removed.
- The same populated legacy lineage round-trips `0020 -> 0021 -> 0020 -> 0021`; it compares
  exact rows and the complete normalized SQLite contracts, including MONEY indexes, foreign
  keys, and graph triggers.
- The downgrade crash matrix is now parameterized across all eleven custom rebuild tables and
  both durable SQLite states: source plus stale `__0021` table and source absent with completed
  `__0021` table. Each node starts populated, injects the interruption, retries, then checks
  0020 revision convergence, exact affected rows/contract, no temporary table, and the original
  foreign-key setting.

## RED/GREEN record

The first new run failed in the test fixture because it used the historical 0019 project insert
against 0020, where `projects.owner_id` is required. The fixture was corrected to model a real
0020 row. The matrix then exercised all 22 downgrade nodes; failures were limited to assertion
surface defects (catalogue seed rows and SQLite DDL whitespace), which were corrected without a
production change. No retained production defect was exposed.

## Verification

All commands used `/Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python`.

```text
pytest -q tests/test_schema_migrations.py --tb=short
```

The migration suite passed. The existing broker/provider files remained unedited and unstaged.

## Concern

This evidence change is migration-only. The existing tenant suite already covers same-identifier
graph/layout isolation and canonical identity; no runtime repository behavior was changed.
