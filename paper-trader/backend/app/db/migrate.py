"""Versioned schema migrations for the execution database.

This replaces the additive `ADD COLUMN` dict in `session.py` as the mechanism for
schema change. That dict still runs — it is the only thing that can carry a
database written before Alembic existed up to the baseline — but it is frozen
(see `tests/test_migrate_schema_frozen.py`). New columns, renames, type changes,
constraints and backfills are Alembic revisions from here on.

Three states a database can be in, and what happens to each
-----------------------------------------------------------
1. **Empty** (no tables) — a fresh dev/test database. `create_all()` builds the
   current model schema directly, then we STAMP head. No revision is executed,
   because the models already describe head. Fast, and it keeps the existing
   test-suite behaviour byte-for-byte.

2. **Populated, no `alembic_version`** — the owner's live `paper_trader.db`, and
   every database that existed before this commit. The frozen `_migrate_schema()`
   brings it to the baseline, we STAMP `0001`, then upgrade to head. Nothing is
   dropped and nothing is rebuilt: a pre-Alembic production ledger keeps every row.

3. **Populated, has `alembic_version`** — upgrade to head. The normal path forever
   after.

The invariant that makes (1) and (2) safe to coexist is that they must converge:
a database built by `create_all` and a database migrated up from the baseline must
have *identical* schemas. That is not assumed, it is asserted on every run of
`tests/test_schema_migrations.py`, which builds both and diffs them column by
column. If a future revision is written without the matching model change (or vice
versa), that test fails.
"""
from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect
from sqlalchemy import text as _sa_text

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ALEMBIC_INI = os.path.join(_BACKEND_DIR, "alembic.ini")
MIGRATIONS_DIR = os.path.join(_BACKEND_DIR, "migrations")
BASELINE_REVISION = "0001"
BASELINE_SCHEMA_SQL = os.path.join(MIGRATIONS_DIR, "baseline_schema.ddl")

# The tables that existed at revision 0001 — the documented inventory of the
# baseline. Adoption does not read this (it executes baseline_schema.ddl directly);
# it exists so the baseline's contents are reviewable in code, and
# `test_schema_migrations.py` asserts it still matches the DDL. A mismatch means
# the DDL was regenerated against newer models, which would silently move the
# floor every revision is measured from.
BASELINE_TABLES = frozenset({
    "backtest_results", "backtest_runs", "capital_state", "daily_account_snapshot",
    "earnings_events", "equity_snapshots", "generated_strategies", "instrument_state",
    "option_data", "order_journal", "positions", "runtime_config", "signal_events",
    "strategy_lifecycle", "trades", "universe_instruments", "watchlist_membership",
    "watchlists",
})


def alembic_config(connection=None) -> Config:
    """Alembic config bound to `connection` (never to a URL — see alembic.ini)."""
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("script_location", MIGRATIONS_DIR)
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def head_revision() -> str:
    """The newest revision on disk — what a fully-migrated database should report."""
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def schema_version(engine: Engine) -> str | None:
    """The revision this database is stamped at, or None if it is unmanaged.

    None is meaningful and is not an error: it means a pre-Alembic database that
    `init_schema` has not yet adopted.
    """
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def schema_state(engine: Engine) -> dict:
    """Schema version report for the health endpoint.

    `current` is what the database says; `head` is what this build expects. They
    differ exactly when a process is running against a database it has not
    migrated — which is a deploy-ordering fault worth seeing from outside.
    """
    current = schema_version(engine)
    head = head_revision()
    return {"current": current, "head": head, "up_to_date": current == head}


def _has_tables(engine: Engine) -> bool:
    names = set(inspect(engine).get_table_names())
    names.discard("alembic_version")
    return bool(names)


def upgrade_to_head(engine: Engine) -> str | None:
    """Run every pending revision. Returns the revision now stamped."""
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    return schema_version(engine)


def stamp(engine: Engine, revision: str) -> None:
    """Record `revision` without executing it — for adopting an existing schema."""
    with engine.begin() as conn:
        command.stamp(alembic_config(conn), revision)


def _create_baseline_tables(engine: Engine) -> None:
    """Create any BASELINE table this database is missing — and nothing newer.

    Built from `baseline_schema.ddl`, NOT from the ORM models, and the distinction
    is the whole point. The models describe HEAD; a database being adopted is at the
    baseline and about to be walked forward by the revisions. Creating a "baseline"
    table from head-shaped models produces a table that already has every later
    revision's columns, and the revision that adds one then dies on `duplicate
    column name`. That is not theoretical — it is how revision 0002 failed the first
    time it met the adoption path.

    Why create anything at all: a database old enough to predate a table (one
    written before `watchlists` existed, say) never had it, and `_migrate_schema`
    only ever added COLUMNS. Before Alembic, `create_all` ran on every boot and
    quietly covered this; adoption happens once, so it has to be covered here.

    IF NOT EXISTS everywhere: for the normal case — a database that has all of them
    — this is a no-op.
    """
    with open(BASELINE_SCHEMA_SQL) as fh:
        ddl = "\n".join(line for line in fh.read().splitlines()
                        if not line.strip().startswith("--"))
    with engine.begin() as conn:
        for stmt in (s.strip() for s in ddl.split(";")):
            if not stmt:
                continue
            stmt = stmt.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1) \
                       .replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1) \
                       .replace("CREATE UNIQUE INDEX ",
                                "CREATE UNIQUE INDEX IF NOT EXISTS ", 1)
            conn.execute(_sa_text(stmt))


def init_schema(engine: Engine, *, create_all, legacy_migrate) -> str | None:
    """Bring `engine`'s database to head from any of the three states above.

    `create_all` and `legacy_migrate` are injected rather than imported so this
    module has no dependency on `session.py` (which imports it) — the import
    direction stays one-way.
    """
    current = schema_version(engine)
    if current is not None:                     # state 3 — already managed
        if current == head_revision():
            # Nothing to do. Returning early is not just a speed optimisation: it
            # is the difference between boot taking a WRITE lock on the database
            # and not touching it at all. `command.upgrade` opens a transaction
            # even when there are no pending revisions, and `init_db` runs on every
            # process start — so the no-op path was contending for the lock with
            # anything else already holding a session. In-suite that surfaced as
            # `database is locked` errors in unrelated tests; on the box it would
            # be a restart competing with the engine's own long-lived session.
            return current
        return upgrade_to_head(engine)

    if _has_tables(engine):
        # State 2 — a pre-Alembic database with real rows in it. Bring it to the
        # BASELINE (frozen ALTERs + any baseline table it never had), adopt it at
        # 0001, then let the revisions carry it forward from there.
        legacy_migrate()
        _create_baseline_tables(engine)
        stamp(engine, BASELINE_REVISION)
        return upgrade_to_head(engine)

    # State 1 — empty. The models already describe head; build and adopt.
    create_all()
    stamp(engine, head_revision())
    return schema_version(engine)


def _main(argv: list[str] | None = None) -> int:
    import argparse

    from app.db.session import engine as app_engine

    p = argparse.ArgumentParser(
        prog="python -m app.db.migrate",
        description="Execution-database migrations. Operates on PT_DB_PATH.")
    p.add_argument("action", choices=["current", "head", "upgrade", "history"],
                   help="current: what this DB is stamped at · head: what this build "
                        "expects · upgrade: apply pending revisions · history: list them")
    args = p.parse_args(argv)

    if args.action == "current":
        print(schema_version(app_engine) or "(unmanaged — no alembic_version table)")
    elif args.action == "head":
        print(head_revision())
    elif args.action == "upgrade":
        before = schema_version(app_engine)
        after = upgrade_to_head(app_engine)
        print(f"{before or '(unmanaged)'} -> {after}")
    else:
        command.history(alembic_config(), verbose=True)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(_main())
