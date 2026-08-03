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
import pytest
from alembic import command
from sqlalchemy.exc import DatabaseError

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
    engine = sa.create_engine(f"sqlite:///{tmp_path / name}")

    @sa.event.listens_for(engine, "connect")
    def _enforce_runtime_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


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


def test_product_object_schema_owns_graph_versions_and_sparse_layouts(tmp_path):
    engine = _build_from_baseline(tmp_path)
    schema = _schema(engine)

    assert migrate.head_revision() == "0008"
    assert set(schema["projects"]["columns"]) == {
        "project_id", "name", "description", "status", "created_at", "updated_at",
    }
    assert set(schema["graph_artifacts"]["columns"]) == {
        "identifier", "project_id", "display_name", "draft_json", "draft_revision",
        "published_revision", "current_version", "created_at", "updated_at",
    }
    assert set(schema["graph_versions"]["columns"]) == {
        "graph_identifier", "version", "artifact_json", "content_address", "created_at",
    }
    assert set(schema["ir_graph_layouts"]["columns"]) == {
        "graph_identifier", "graph_version", "revision", "updated_at",
    }
    assert set(schema["ir_graph_layout_positions"]["columns"]) == {
        "graph_identifier", "graph_version", "instance_id", "x", "y",
    }
    assert set(schema["ir_graph_layout_groups"]["columns"]) == {
        "graph_identifier", "graph_version", "identifier", "display_name",
        "x", "y", "width", "height", "collapsed",
    }
    assert set(schema["ir_graph_layout_group_members"]["columns"]) == {
        "graph_identifier", "graph_version", "group_identifier", "instance_id",
    }
    assert set(schema["project_review_notes"]["columns"]) == {
        "note_id", "project_id", "event_id", "event_type", "body", "created_by",
        "revision", "deleted_at", "created_at", "updated_at",
    }
    assert set(schema["project_review_saved_views"]["columns"]) == {
        "view_id", "project_id", "name", "filters_json", "created_by", "revision",
        "deleted_at", "created_at", "updated_at",
    }
    assert any(
        name == "uq_project_review_saved_views_active_name"
        and columns == ("project_id", "name") and unique
        for name, columns, unique in schema["project_review_saved_views"]["indexes"]
    )
    assert set(schema["ir_graph_layout_orphan_archive"]["columns"]) == {
        "graph_identifier", "graph_version", "revision", "updated_at", "archived_at",
    }
    assert set(schema["ir_graph_layout_position_orphan_archive"]["columns"]) == {
        "graph_identifier", "graph_version", "instance_id", "x", "y",
    }

    graph_version_fks = sa.inspect(engine).get_foreign_keys("ir_graph_layouts")
    assert any(
        fk["referred_table"] == "graph_versions"
        and fk["constrained_columns"] == ["graph_identifier", "graph_version"]
        for fk in graph_version_fks
    )


def test_catalogue_graph_is_seeded_with_derived_identity(tmp_path):
    from app.ir.hashing import canonical_json, content_address
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    with engine.connect() as connection:
        artifact = connection.execute(sa.text(
            "SELECT project_id, draft_json, draft_revision, published_revision, "
            "current_version "
            "FROM graph_artifacts WHERE identifier = :identifier"
        ), {"identifier": GRAPH["identifier"]}).one()
        version = connection.execute(sa.text(
            "SELECT artifact_json, content_address FROM graph_versions "
            "WHERE graph_identifier = :identifier AND version = :version"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]}).one()

    assert artifact.project_id
    assert artifact.draft_json == canonical_json(GRAPH)
    assert artifact.draft_revision == 0
    assert artifact.published_revision == 0
    assert artifact.current_version == GRAPH["version"]
    assert version.artifact_json == canonical_json(GRAPH)
    assert version.content_address == content_address(GRAPH)


def test_graph_versions_refuse_direct_sql_update_and_delete(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    for statement in (
        "UPDATE graph_versions SET artifact_json = '{}' "
        "WHERE graph_identifier = :identifier AND version = :version",
        "DELETE FROM graph_versions "
        "WHERE graph_identifier = :identifier AND version = :version",
    ):
        with pytest.raises(DatabaseError, match="immutable"):
            with engine.begin() as connection:
                connection.execute(sa.text(statement), {
                    "identifier": GRAPH["identifier"],
                    "version": GRAPH["version"],
                })


def test_graph_version_insert_requires_json_identity_to_match_row_identity(tmp_path):
    from app.ir.hashing import canonical_json, content_address
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    mismatched = dict(GRAPH)
    mismatched["version"] = GRAPH["version"] + 1
    for row_version, document in (
        (GRAPH["version"] + 2, mismatched),
        (GRAPH["version"] + 3, {}),
    ):
        with pytest.raises(DatabaseError, match="CHECK constraint"):
            with engine.begin() as connection:
                connection.execute(sa.text(
                    "INSERT INTO graph_versions "
                    "(graph_identifier, version, artifact_json, content_address, created_at) "
                    "VALUES (:identifier, :version, :artifact_json, :address, "
                    "'2026-08-03 10:00:00')"
                ), {
                    "identifier": GRAPH["identifier"],
                    "version": row_version,
                    "artifact_json": canonical_json(document),
                    "address": content_address(document),
                })


def test_product_object_upgrade_attaches_valid_layout_and_removes_orphans(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0005")
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))
        for identifier, version in (
            (GRAPH["identifier"], GRAPH["version"]),
            ("strategy.orphan", 99),
        ):
            connection.execute(sa.text(
                "INSERT INTO ir_graph_layouts "
                "(graph_identifier, graph_version, revision, updated_at) "
                "VALUES (:identifier, :version, 1, '2026-08-03 10:00:00')"
            ), {"identifier": identifier, "version": version})
            connection.execute(sa.text(
                "INSERT INTO ir_graph_layout_positions "
                "(graph_identifier, graph_version, instance_id, x, y) "
                "VALUES (:identifier, :version, 'n_ema', 10.0, 20.0)"
            ), {"identifier": identifier, "version": version})

    assert migrate.upgrade_to_head(engine) == "0008"
    with engine.connect() as connection:
        layouts = connection.execute(sa.text(
            "SELECT graph_identifier, graph_version FROM ir_graph_layouts"
        )).all()
        positions = connection.execute(sa.text(
            "SELECT graph_identifier, graph_version, instance_id "
            "FROM ir_graph_layout_positions"
        )).all()
        capital = connection.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state WHERE id = 1"
        )).one()
        archived_layouts = connection.execute(sa.text(
            "SELECT graph_identifier, graph_version, revision "
            "FROM ir_graph_layout_orphan_archive"
        )).all()
        archived_positions = connection.execute(sa.text(
            "SELECT graph_identifier, graph_version, instance_id, x, y "
            "FROM ir_graph_layout_position_orphan_archive"
        )).all()

    assert layouts == [(GRAPH["identifier"], GRAPH["version"])]
    assert positions == [(GRAPH["identifier"], GRAPH["version"], "n_ema")]
    assert archived_layouts == [("strategy.orphan", 99, 1)]
    assert archived_positions == [("strategy.orphan", 99, "n_ema", 10.0, 20.0)]
    assert capital == (50000.0, 49000.0, -1000.0)

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0005")
    with engine.connect() as connection:
        restored_layout = connection.execute(sa.text(
            "SELECT revision FROM ir_graph_layouts "
            "WHERE graph_identifier = 'strategy.orphan' AND graph_version = 99"
        )).one()
        restored_position = connection.execute(sa.text(
            "SELECT instance_id, x, y FROM ir_graph_layout_positions "
            "WHERE graph_identifier = 'strategy.orphan' AND graph_version = 99"
        )).one()
    assert restored_layout == (1,)
    assert restored_position == ("n_ema", 10.0, 20.0)


def test_product_object_downgrade_refuses_non_seed_history(tmp_path):
    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO projects "
            "(project_id, name, description, status, created_at, updated_at) "
            "VALUES ('project.user', 'User project', '', 'active', "
            "'2026-08-03 10:00:00', '2026-08-03 10:00:00')"
        ))

    with pytest.raises(RuntimeError, match="non-seed"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0005")

    assert migrate.schema_version(engine) == "0008"

    with engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM projects WHERE project_id = 'project.user'"))
        connection.execute(sa.text(
            "UPDATE graph_artifacts SET draft_revision = 1 "
            "WHERE identifier = 'strategy.expanding_z_impulse'"
        ))
    with pytest.raises(RuntimeError, match="modified"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0005")

    assert migrate.schema_version(engine) == "0008"


def test_product_object_rollback_preserves_seed_layout_and_money_record(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layouts "
            "(graph_identifier, graph_version, revision, updated_at) "
            "VALUES (:identifier, :version, 1, '2026-08-03 10:00:00')"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_positions "
            "(graph_identifier, graph_version, instance_id, x, y) "
            "VALUES (:identifier, :version, 'n_ema', 10.0, 20.0)"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        command.downgrade(migrate.alembic_config(connection), "0005")

    tables = set(sa.inspect(engine).get_table_names())
    assert {"projects", "graph_artifacts", "graph_versions"}.isdisjoint(tables)
    with engine.connect() as connection:
        layout = connection.execute(sa.text(
            "SELECT revision FROM ir_graph_layouts "
            "WHERE graph_identifier = :identifier AND graph_version = :version"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]}).one()
        position = connection.execute(sa.text(
            "SELECT instance_id, x, y FROM ir_graph_layout_positions "
            "WHERE graph_identifier = :identifier AND graph_version = :version"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]}).one()
        capital = connection.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state WHERE id = 1"
        )).one()
    assert layout == (1,)
    assert position == ("n_ema", 10.0, 20.0)
    assert capital == (50000.0, 49000.0, -1000.0)

    assert migrate.upgrade_to_head(engine) == "0008"


def test_layout_migration_downgrades_without_touching_the_money_record(tmp_path):
    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0004")

    tables = set(sa.inspect(engine).get_table_names())
    assert migrate.schema_version(engine) == "0004"
    assert "ir_graph_layouts" not in tables
    assert "ir_graph_layout_positions" not in tables
    assert "trades" in tables
    with engine.connect() as connection:
        capital = connection.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state WHERE id = 1"
        )).one()
    assert capital == (50000.0, 49000.0, -1000.0)

    assert migrate.upgrade_to_head(engine) == "0008"


def test_visual_group_migration_rolls_back_without_touching_layout_or_money(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layouts "
            "(graph_identifier, graph_version, revision, updated_at) "
            "VALUES (:identifier, :version, 1, '2026-08-03 10:00:00')"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_positions "
            "(graph_identifier, graph_version, instance_id, x, y) "
            "VALUES (:identifier, :version, 'n_ema', 10.0, 20.0)"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_groups "
            "(graph_identifier, graph_version, identifier, display_name, "
            " x, y, width, height, collapsed) "
            "VALUES (:identifier, :version, 'g_signal', 'Signal', "
            " 1.0, 2.0, 300.0, 180.0, 0)"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_group_members "
            "(graph_identifier, graph_version, group_identifier, instance_id) "
            "VALUES (:identifier, :version, 'g_signal', 'n_ema')"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        command.downgrade(migrate.alembic_config(connection), "0006")

    tables = set(sa.inspect(engine).get_table_names())
    assert "ir_graph_layout_groups" not in tables
    assert "ir_graph_layout_group_members" not in tables
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT instance_id, x, y FROM ir_graph_layout_positions"
        )).one() == ("n_ema", 10.0, 20.0)
        assert connection.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state WHERE id = 1"
        )).one() == (50000.0, 49000.0, -1000.0)

    assert migrate.upgrade_to_head(engine) == "0008"


def test_review_state_migration_empty_rollback_preserves_existing_records(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))
        command.downgrade(migrate.alembic_config(connection), "0007")

    tables = set(sa.inspect(engine).get_table_names())
    assert migrate.schema_version(engine) == "0007"
    assert "project_review_notes" not in tables
    assert "project_review_saved_views" not in tables
    with engine.connect() as connection:
        capital = connection.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state WHERE id = 1"
        )).one()
        graph = connection.execute(sa.text(
            "SELECT content_address FROM graph_versions "
            "WHERE graph_identifier = :identifier AND version = :version"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]}).one()
    assert capital == (50000.0, 49000.0, -1000.0)
    assert graph.content_address.startswith("sha256:")
    assert migrate.upgrade_to_head(engine) == "0008"


def test_review_state_migration_refuses_populated_downgrade(tmp_path):
    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO project_review_notes "
            "(note_id, project_id, event_id, event_type, body, created_by, revision, "
            " deleted_at, created_at, updated_at) VALUES "
            "('note-1', 'project.repository_catalogue', 'run:1', 'experiment_run', "
            " 'Retain this note', 'owner', 0, NULL, "
            " '2026-08-03 10:00:00', '2026-08-03 10:00:00')"
        ))

    with pytest.raises(RuntimeError, match="review notes or saved views exist"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0007")

    assert migrate.schema_version(engine) == "0008"


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
