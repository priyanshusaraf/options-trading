---
description: Alembic migrations, schema, persistence, transaction boundaries
paths:
  - "paper-trader/backend/migrations/**"
  - "paper-trader/backend/app/db/**"
  - "paper-trader/backend/app/ledger/**"
---

# Migrations and persistence

Migration head is **0016** (`execution_intents.owner_id`, 2026-08-10). Verify with `.venv/bin/python -m app.db.migrate head`, never from a
document.

## Rules

- Every schema change uses Alembic, proves upgrade from the current schema **and** from a
  production-shaped prior schema, proves downgrade or documents why rollback is restore-based,
  and keeps model and migration schemas equal.
- **Never rewrite the money record.** Migrations may add columns and backfill nothing; historical
  rows keep their documented NULLs. `build_sha` has three distinguishable values — a SHA,
  `'unknown'`, and NULL — and collapsing the last two destroys attribution.
- `init_db(reset=True)` resets **only** in mock mode and refuses otherwise. That guard is
  load-bearing; do not relax it.
- Before a risky migration, push the preceding verified slice and capture the current head, a
  prior-schema fixture, and the restore path.
- Destructive operations on a populated database are an **owner gate**.

## Traps already paid for

- **`Model(col=None)` applies the column default, not NULL.** A test seeding "legacy NULLs" this
  way silently creates normal rows and every assertion about the legacy shape goes vacuous. Write
  unset shapes with direct SQL.
- **Python's `or` is falsy for the empty string; SQL `COALESCE` matches only NULL.** Porting a
  Python `x or default` normalisation to SQL needs `COALESCE(NULLIF(col,''), default)`.
- SQLite reads `LIMIT -1` as *no limit*. Bound page parameters below as well as above.
- The connection pool is `pool_size=5 + max_overflow=10` = **15 connections** against FastAPI's
  40-thread sync worker pool. Measured: any query holding a connection ≳4s under full concurrency
  starts failing requests. Keep queries short; do not raise the pool without reading
  `docs/engineering/reference/backend-hardening-2026-08-08.md` §4.2 — it is an owner decision
  because of the 1 GB droplet's OOM history.
- Analytics must aggregate in **SQL**, never by materialising tables. That defect caused the
  2026-07-23 outage and survived in a second place until 2026-08-08.
