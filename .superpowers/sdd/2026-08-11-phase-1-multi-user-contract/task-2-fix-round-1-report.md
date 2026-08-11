# Task 2 fix round 1 report

## Scope closed

- `0019` detects an already-rebuilt deployments table and can retry after a SQLite DDL interruption.
- The migration scopes IR divergence uniqueness by owner and durable account, restores its legacy index on downgrade, and removes all legacy scope defaults after backfill.
- The eleven account-money models require explicit `owner_id` and `broker_account_id` for ordinary ORM writes.
- Storage counts, runner trade counts, LiveBroker intent reads, lifecycle event writes, and database exit sweeps are account-scoped.
- Startup no longer invokes the global position-money repair.

## TDD evidence

- Clean detached `58bbbd9` test-only checkout: 12 failures. The retry proof failed at `UPDATE deployments ... account_id` after an injected interruption; each of the eleven models exposed a legacy Python default.
- Writable checkout focused suite: `107 passed` for schema migration, money isolation, storage, exit sweep, position repair, and lifecycle recovery tests.
- Follow-up scoped run: `40 passed` for schema migration, storage, and the full eleven-model omission guard.
- `python -m compileall -q app migrations` passed.
- `git diff --check` passed.

## Remaining verification signal

- The requested full command `pytest -q tests research_tests --tb=short` began but failed early, displaying failures at 1% and errors at 3%; the runner did not return its final traceback before termination. These are expected legacy fixtures that still omit now-required tenant scope and need a separate broad migration of historical tests.
- Full `compileall` including `scripts` fails on pre-existing `scripts/provider_conformance_mutations.py`: `from __future__ import annotations` is not at the beginning of the file. That file is not part of this change.
