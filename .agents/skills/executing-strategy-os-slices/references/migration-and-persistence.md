# Migration and persistence evidence

Never trust a documented migration number. Record the current head with `.venv/bin/python -m app.db.migrate head` from `paper-trader/backend`.

For every schema change:

- use Alembic and keep the model schema equal to the migrated schema;
- prove upgrade from the current schema and from a production-shaped prior schema;
- prove downgrade, or document and exercise a restore-based rollback;
- preserve historical money attribution and documented historical NULL values rather than backfilling them into a convenient default;
- keep `build_sha` values distinct: a SHA, `unknown`, and NULL are not interchangeable;
- capture the current head, prior-schema fixture, and restore path before a risky migration;
- stop at an owner gate before destructive work on a populated database.

The reset guard is structural: `init_db(reset=True)` is a mock-only reset and must refuse in every other mode.

Avoid traps already proven in this repository:

- `Model(col=None)` can apply a column default instead of writing a historical NULL; create legacy NULL fixtures with direct SQL.
- Python `x or default` is not SQL `COALESCE(x, default)` for an empty string; use `COALESCE(NULLIF(col,''), default)` when those semantics are required.
- SQLite treats `LIMIT -1` as unlimited, so bound page parameters below zero and above the maximum.
- The configured `pool_size=5` plus overflow is constrained by the small production host. Keep transactions and queries short; a pool increase is an owner decision after reading the current backend-hardening reference.
- Aggregate in SQL. Do not materialize full tables for analytics.

Evidence includes the exact head, upgrade fixtures, rollback or restore result, model comparison, affected focused tests, and the owner gate status.
