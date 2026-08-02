"""The migration framework proves itself on every run.

The whole point of Phase A is that a schema change can now be expressed as a
reversible, versioned revision instead of an ADD COLUMN line. That only holds if
two things stay true forever, and neither is checked by any other test:

  1. A database built from the ORM models and a database migrated up from the
     pre-Alembic baseline end up with the SAME schema. If someone adds a column to
     `models.py` and forgets the revision (or writes a revision that does something
     subtly different), fresh installs and the owner's live ledger silently diverge
     — the class of bug that only surfaces as a production 500 weeks later.

  2. A pre-Alembic database is ADOPTED, not rebuilt. The live ledger holds real
     money rows; `init_schema` must stamp it, never drop it.
"""
from __future__ import annotations

import sqlalchemy as sa

from app.db import migrate
from app.db.models import Base


def _schema(engine) -> dict:
    """Comparable description of a database: columns (name/type/nullable/default)
    and indexes per table. `alembic_version` is excluded — it records *where* a
    database is, and the two sides of the comparison get there differently."""
    insp = sa.inspect(engine)
    out = {}
    for table in sorted(insp.get_table_names()):
        if table == "alembic_version":
            continue
        cols = {c["name"]: (str(c["type"]), bool(c["nullable"]), str(c.get("default")))
                for c in insp.get_columns(table)}
        idx = sorted((i["name"], tuple(i["column_names"]), bool(i.get("unique")))
                     for i in insp.get_indexes(table))
        out[table] = {"columns": cols, "indexes": idx}
    return out


def _fresh_engine(tmp_path, name: str):
    return sa.create_engine(f"sqlite:///{tmp_path / name}")


def _apply_baseline_ddl(engine) -> None:
    """Execute the checked-in baseline DDL, building a pre-Alembic database.

    Comment lines are stripped BEFORE splitting on `;`. Splitting first and then
    skipping chunks that start with `--` silently swallowed the first CREATE TABLE
    (it shares a chunk with the file header), which produced a confusing "no such
    table" from the index that followed it."""
    with open(migrate.BASELINE_SCHEMA_SQL) as fh:
        ddl = "\n".join(line for line in fh.read().splitlines()
                        if not line.strip().startswith("--"))
    statements = [s.strip() for s in ddl.split(";") if s.strip()]
    assert len(statements) > 20, \
        f"baseline DDL parsed to only {len(statements)} statements — parser is broken"
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(sa.text(stmt))


def _build_from_models(tmp_path):
    """State 1 — an empty database adopted by init_schema."""
    engine = _fresh_engine(tmp_path, "fresh.db")
    migrate.init_schema(engine,
                        create_all=lambda: Base.metadata.create_all(engine),
                        legacy_migrate=lambda: None)
    return engine


def _build_from_baseline(tmp_path):
    """State 2 — a synthetic PRE-ALEMBIC database, built by executing the checked-in
    baseline DDL, then adopted and migrated forward."""
    engine = _fresh_engine(tmp_path, "legacy.db")
    _apply_baseline_ddl(engine)
    migrate.init_schema(engine,
                        create_all=lambda: Base.metadata.create_all(engine),
                        legacy_migrate=lambda: None)
    return engine


def test_models_and_migrations_agree(tmp_path):
    """THE invariant. A fresh install and a migrated legacy database must be the
    same shape. A failure here means models.py and migrations/versions/ disagree —
    fix the revision, do not weaken this test."""
    fresh = _schema(_build_from_models(tmp_path))
    migrated = _schema(_build_from_baseline(tmp_path))

    assert set(migrated) == set(fresh), (
        "table sets differ between a fresh create_all and a migrated legacy DB: "
        f"only-in-migrated={sorted(set(migrated) - set(fresh))} "
        f"only-in-fresh={sorted(set(fresh) - set(migrated))}"
    )
    for table in fresh:
        assert migrated[table]["columns"] == fresh[table]["columns"], (
            f"column mismatch in {table!r} — models.py and the revision chain "
            f"disagree. Fresh: {fresh[table]['columns']}. "
            f"Migrated: {migrated[table]['columns']}"
        )
        assert migrated[table]["indexes"] == fresh[table]["indexes"], \
            f"index mismatch in {table!r}"


def test_legacy_database_is_adopted_not_rebuilt(tmp_path):
    """A pre-Alembic database keeps its rows. This is the live-ledger case: the
    owner's paper_trader.db holds 72 real trades and must survive adoption."""
    engine = _fresh_engine(tmp_path, "withdata.db")
    _apply_baseline_ddl(engine)
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO capital_state (id, initial_capital, cash, realized_pnl, "
            "updated_at) VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-02 10:00:00')"))

    assert migrate.schema_version(engine) is None, "precondition: unmanaged database"

    migrate.init_schema(engine,
                        create_all=lambda: Base.metadata.create_all(engine),
                        legacy_migrate=lambda: None)

    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state "
            "WHERE id = 1")).one()
    assert row == (50000.0, 49000.0, -1000.0), "adoption destroyed existing rows"
    assert migrate.schema_version(engine) == migrate.head_revision()


def test_empty_database_is_stamped_at_head(tmp_path):
    engine = _build_from_models(tmp_path)
    assert migrate.schema_version(engine) == migrate.head_revision()
    state = migrate.schema_state(engine)
    assert state["up_to_date"] is True
    assert state["current"] == state["head"]


def test_init_schema_is_idempotent(tmp_path):
    """Boot happens more than once. Re-running must be a no-op, not an error."""
    engine = _build_from_models(tmp_path)
    first = migrate.schema_version(engine)
    for _ in range(2):
        migrate.init_schema(engine,
                            create_all=lambda: Base.metadata.create_all(engine),
                            legacy_migrate=lambda: None)
    assert migrate.schema_version(engine) == first


def test_unmanaged_database_reports_no_version(tmp_path):
    """`None` means "pre-Alembic", and must be distinguishable from head. The
    health endpoint reports it, so it must never be confused with up-to-date."""
    engine = _fresh_engine(tmp_path, "bare.db")
    assert migrate.schema_version(engine) is None
    assert migrate.schema_state(engine)["up_to_date"] is False


def test_baseline_tables_constant_matches_the_baseline_ddl():
    """`BASELINE_TABLES` decides what adoption is allowed to create. If it drifts
    from the actual baseline, adoption either misses a table an old database needs
    or creates one a later revision is about to create — the exact collision that
    broke revision 0002 the first time it ran."""
    import re
    with open(migrate.BASELINE_SCHEMA_SQL) as fh:
        ddl = fh.read()
    in_ddl = set(re.findall(r"CREATE TABLE (\w+)", ddl))
    assert in_ddl == set(migrate.BASELINE_TABLES), (
        f"only-in-DDL={sorted(in_ddl - set(migrate.BASELINE_TABLES))} "
        f"only-in-constant={sorted(set(migrate.BASELINE_TABLES) - in_ddl)}"
    )


def test_baseline_ddl_is_shippable():
    """The baseline must reach the VPS. `scripts/deploy.sh` excludes `*.sql` (that
    is how ledger backups are kept off the box), so a `.sql` extension here would
    silently strip a checked-in source file from every deploy — and nothing else
    would notice, because runtime does not read it. See the file's own header."""
    import os
    assert os.path.exists(migrate.BASELINE_SCHEMA_SQL)
    assert not migrate.BASELINE_SCHEMA_SQL.endswith(".sql"), (
        "the baseline DDL must not use a .sql extension — deploy.sh excludes '*.sql' "
        "from the rsync, so this file would never ship"
    )


def test_every_revision_declares_a_downgrade():
    """A revision that cannot be rolled back is a one-way door on a live money
    ledger. `downgrade` may raise NotImplementedError for genuinely destructive
    changes, but it must be written and say so — never silently absent."""
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(migrate.alembic_config())
    for rev in script.walk_revisions():
        module = rev.module
        assert hasattr(module, "downgrade"), \
            f"revision {rev.revision} has no downgrade()"
        assert rev.doc, f"revision {rev.revision} has no docstring saying what it does"
