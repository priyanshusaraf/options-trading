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

import re
import hashlib
import json
import importlib.util
from pathlib import Path

import sqlalchemy as sa
import pytest
from alembic import command
from sqlalchemy.exc import DatabaseError, IntegrityError

from app.db import migrate
from app.db.models import Base


#: The migration head, pinned in ONE place and deliberately a literal rather than a call to
#: `migrate.head_revision()`. Deriving it would make every assertion below compare the head to
#: itself and pass for any value — the vacuous shape. Bumping this by hand when a migration
#: lands is the point: it is the moment someone states that the new head is intended.
HEAD = "0029"


def test_revision_0029_preserves_legacy_review_creator_bytes_and_allows_user_ids(tmp_path):
    """The creator-envelope upgrade keeps historic evidence bytes and snapshot guards."""
    engine = _build_from_baseline_at_revision(tmp_path, "0029-review-creators.db", "0028")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0029")
        for table in ("project_review_notes", "project_review_saved_views", "project_review_snapshots"):
            sql = connection.execute(sa.text(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"),
                {"table": table}).scalar_one().lower()
            assert "length(created_by) between 1 and 64" in sql
        triggers = {row[0] for row in connection.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='project_review_snapshots'"))}
        assert triggers == {"project_review_snapshots_refuse_update", "project_review_snapshots_refuse_delete"}


@pytest.mark.parametrize("needle", (
    "DROP TABLE PROJECT_REVIEW_NOTES",
    "ALTER TABLE _ALEMBIC_TMP_PROJECT_REVIEW_NOTES RENAME TO PROJECT_REVIEW_NOTES",
))
def test_revision_0029_retries_interrupted_sqlite_recreate_without_losing_review_rows(tmp_path, needle):
    """A restart resumes both sides of Alembic's destructive SQLite boundary."""
    engine = _build_from_baseline_at_revision(tmp_path, f"0029-retry-{abs(hash(needle))}.db", "0028")
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO organizations VALUES ('org.0029','O','active','2026-08-12','2026-08-12')"))
        connection.execute(sa.text("INSERT INTO projects VALUES ('project.0029','org.0029','P','','active','2026-08-12','2026-08-12')"))
        connection.execute(sa.text(
            "INSERT INTO project_review_notes VALUES ('org.0029','note.0029','project.0029','event','experiment_run','legacy','owner',0,NULL,'2026-08-12','2026-08-12')"))
    stopped = False

    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if not stopped and needle in " ".join(statement.upper().split()):
            stopped = True
            raise RuntimeError("0029 interruption")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="interruption"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0029")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0029")
        assert connection.execute(sa.text(
            "SELECT created_by, body FROM project_review_notes WHERE note_id='note.0029'"
        )).one() == ("owner", "legacy")


def test_revision_0029_refuses_an_unproven_or_tampered_recreate_temp(tmp_path):
    """A temp-table name alone never authorizes recovery after the source drop."""
    engine = _build_from_baseline_at_revision(tmp_path, "0029-tampered-temp.db", "0028")
    with engine.begin() as connection:
        connection.execute(sa.text("ALTER TABLE project_review_notes RENAME TO _alembic_tmp_project_review_notes"))
        before = tuple(connection.execute(sa.text(
            "SELECT * FROM _alembic_tmp_project_review_notes ORDER BY rowid")))
        with pytest.raises(RuntimeError, match="unproven"):
            command.upgrade(migrate.alembic_config(connection), "0029")
        assert tuple(connection.execute(sa.text(
            "SELECT * FROM _alembic_tmp_project_review_notes ORDER BY rowid"))) == before


def test_revision_0028_adds_digest_only_user_sessions_and_empty_downgrade(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0028-contract.db", "0027")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0028")
        columns = {row[1] for row in connection.execute(sa.text(
            "PRAGMA table_info(user_sessions)"))}
        assert columns == {"session_id", "token_digest", "user_id", "organization_id",
                           "issued_at", "expires_at", "revoked_at"}
        sql = connection.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='user_sessions'"
        )).scalar_one().lower()
        assert "token" not in sql.replace("token_digest", "")
        assert ("organization_id", "user_id") == tuple(
            row[3] for row in connection.execute(sa.text("PRAGMA foreign_key_list(user_sessions)"))
            if row[2] == "memberships")
        command.downgrade(migrate.alembic_config(connection), "0027")
        assert "user_sessions" not in sa.inspect(connection).get_table_names()


@pytest.mark.parametrize("foreign_keys", (0, 1))
@pytest.mark.parametrize("needle,recoverable", (
    ("CREATE TABLE USER_SESSIONS__0028", True),
    ("INSERT OR REPLACE INTO _USER_SESSIONS_0028_CREATION_PROOFS", False),
    ("ALTER TABLE USER_SESSIONS__0028 RENAME TO USER_SESSIONS", True),
    ("DELETE FROM _USER_SESSIONS_0028_CREATION_PROOFS", True),
))
def test_revision_0028_restart_matrix_is_target_bound_and_preserves_fk_mode(
        tmp_path, foreign_keys, needle, recoverable):
    engine = _build_from_baseline_at_revision(
        tmp_path, f"0028-restart-{foreign_keys}-{abs(hash(needle))}.db", "0027")
    stopped = False

    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if not stopped and needle in " ".join(statement.upper().split()):
            stopped = True
            raise RuntimeError("0028 boundary")

    with engine.begin() as connection:
        raw = connection.connection.driver_connection
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={foreign_keys}")
    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="boundary"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0028")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        if not recoverable:
            before = tuple(connection.execute(sa.text(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all())
            with pytest.raises(RuntimeError, match="(unproven|malformed)"):
                command.upgrade(migrate.alembic_config(connection), "0028")
            assert tuple(connection.execute(sa.text(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all()) == before
            assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
            return
        command.upgrade(migrate.alembic_config(connection), "0028")
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        assert connection.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE name='_user_sessions_0028_creation_proofs'"
        )).first() is None


def test_revision_0028_refuses_tampered_proven_temp_without_mutation(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0028-temp-tamper.db", "0027")
    stopped = False

    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if not stopped and "ALTER TABLE USER_SESSIONS__0028 RENAME" in statement.upper():
            stopped = True
            raise RuntimeError("0028 interruption")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="interruption"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0028")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        connection.execute(sa.text("ALTER TABLE user_sessions__0028 ADD COLUMN attacker TEXT"))
        before = connection.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE name='user_sessions__0028'")) .scalar_one()
        with pytest.raises(RuntimeError, match="malformed"):
            command.upgrade(migrate.alembic_config(connection), "0028")
        assert connection.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE name='user_sessions__0028'")) .scalar_one() == before


def test_revision_0028_populated_downgrade_refuses_without_mutating(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0028-down-refusal.db", "0028")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO user_sessions VALUES ('session','a' || printf('%063d', 0),"
            "'owner-user','owner','2026-08-12','2099-08-12',NULL)"))
        with pytest.raises(RuntimeError, match="refuses"):
            command.downgrade(migrate.alembic_config(connection), "0027")
        assert connection.execute(sa.text("SELECT count(*) FROM user_sessions")).scalar_one() == 1


def test_revision_0028_refuses_exact_target_shaped_populated_session_table(tmp_path):
    """An attacker table must not become authentication authority by matching DDL."""
    engine = _build_from_baseline_at_revision(tmp_path, "0028-forged-target.db", "0027")
    migration_path = Path(__file__).parents[1] / "migrations" / "versions" / "20260812_0028_user_sessions.py"
    spec = importlib.util.spec_from_file_location("revision_0028", migration_path)
    revision_0028 = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(revision_0028)
    with engine.begin() as connection:
        connection.execute(sa.text(revision_0028.DDL.replace("__TABLE__", "user_sessions")))
        connection.execute(sa.text(
            f"CREATE INDEX {revision_0028.INDEX[0]} ON user_sessions ({revision_0028.INDEX[1]})"))
        connection.execute(sa.text(
            "INSERT INTO user_sessions VALUES ('attacker',:digest,'owner-user','owner',"
            "'2026-08-12','2099-08-12',NULL)"), {"digest": "a" * 64})
        before = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all())
        with pytest.raises(RuntimeError, match="unproved existing"):
            command.upgrade(migrate.alembic_config(connection), "0028")
        assert tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all()) == before
    assert migrate.schema_version(engine) == "0027"


def test_revision_0028_refuses_exact_target_shaped_empty_session_table(tmp_path):
    """Only a migration-local proof can promote even an otherwise exact empty target."""
    engine = _build_from_baseline_at_revision(tmp_path, "0028-forged-empty-target.db", "0027")
    migration_path = Path(__file__).parents[1] / "migrations" / "versions" / "20260812_0028_user_sessions.py"
    spec = importlib.util.spec_from_file_location("revision_0028_empty", migration_path)
    revision_0028 = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(revision_0028)
    with engine.begin() as connection:
        connection.execute(sa.text(revision_0028.DDL.replace("__TABLE__", "user_sessions")))
        connection.execute(sa.text(
            f"CREATE INDEX {revision_0028.INDEX[0]} ON user_sessions ({revision_0028.INDEX[1]})"))
        before = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all())
        with pytest.raises(RuntimeError, match="unproved existing"):
            command.upgrade(migrate.alembic_config(connection), "0028")
        assert tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all()) == before
    assert migrate.schema_version(engine) == "0027"


def test_revision_0028_preserves_populated_0027_payloads_exactly(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0028-populated-preservation.db", "0027")
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO organizations VALUES ('tenant.0028','Tenant','active','2026-08-12','2026-08-12')"))
        connection.execute(sa.text("INSERT INTO users VALUES ('user.0028','user.0028@example.test','User','active','2026-08-12','2026-08-12')"))
        connection.execute(sa.text("INSERT INTO memberships VALUES ('tenant.0028','user.0028','admin','active','2026-08-12','2026-08-12')"))
        connection.execute(sa.text("INSERT INTO broker_accounts VALUES ('account.0028','tenant.0028','kite','external','Account','active','2026-08-12','2026-08-12')"))
        before = {table: connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all()
                  for table in ("organizations", "users", "memberships", "broker_accounts", "positions")}
        command.upgrade(migrate.alembic_config(connection), "0028")
        after = {table: connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all()
                 for table in before}
        assert after == before


def test_revision_0028_fresh_and_upgraded_user_session_relations_are_identical(tmp_path):
    """Fresh and upgraded contracts match through every relational dimension."""
    fresh = _build_from_models(tmp_path)
    upgraded = _build_from_baseline(tmp_path)

    def contract(engine):
        inspector = sa.inspect(engine)
        columns = [(row["name"], str(row["type"]), row["nullable"], row["default"])
                   for row in inspector.get_columns("user_sessions")]
        foreign = [(tuple(row["constrained_columns"]), row["referred_table"],
                    tuple(row["referred_columns"]), row["options"].get("ondelete"))
                   for row in inspector.get_foreign_keys("user_sessions")]
        unique = [(row["name"], tuple(row["column_names"]))
                  for row in inspector.get_unique_constraints("user_sessions")]
        checks = [(row["name"], " ".join(row["sqltext"].split()))
                  for row in inspector.get_check_constraints("user_sessions")]
        primary = tuple(inspector.get_pk_constraint("user_sessions")["constrained_columns"])
        with engine.connect() as connection:
            indexes = connection.execute(sa.text(
                "SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name='user_sessions' "
                "AND sql IS NOT NULL ORDER BY name")).all()
        return {"columns": columns, "foreign": foreign, "unique": unique,
                "checks": checks, "primary": primary, "indexes": indexes}

    expected = {
        "columns": [
            ("session_id", "VARCHAR(64)", False, None),
            ("token_digest", "VARCHAR(64)", False, None),
            ("user_id", "VARCHAR(64)", False, None),
            ("organization_id", "VARCHAR(64)", False, None),
            ("issued_at", "DATETIME", False, None),
            ("expires_at", "DATETIME", False, None),
            ("revoked_at", "DATETIME", True, None),
        ],
        "foreign": [(("organization_id", "user_id"), "memberships",
                     ("organization_id", "user_id"), "RESTRICT")],
        "unique": [("uq_user_sessions_token_digest", ("token_digest",))],
        "checks": [("ck_user_sessions_token_digest",
                    "length(token_digest) = 64 AND token_digest = lower(token_digest) "
                    "AND token_digest NOT GLOB '*[^0-9a-f]*'")],
        "primary": ("session_id",),
        "indexes": [("ix_user_sessions_owner_active",
                     "CREATE INDEX ix_user_sessions_owner_active ON user_sessions "
                     "(organization_id, user_id, revoked_at, expires_at)")],
    }
    assert contract(upgraded) == contract(fresh) == expected


def test_revision_0027_adds_neutral_public_computation_contract_and_empty_downgrade(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0027-contract.db", "0026")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0027")
        columns = {row[1] for row in connection.execute(sa.text(
            "PRAGMA table_info(backtest_computations)"))}
        assert columns == {"execution_address", "dataset_address", "strategy_key",
                           "strategy_version", "policy_address", "schema_version",
                           "payload_json", "payload_digest"}
        assert connection.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE name='_backtest_0027_creation_proofs'")) .first() is None
        command.downgrade(migrate.alembic_config(connection), "0026")
        assert "backtest_computations" not in sa.inspect(connection).get_table_names()


@pytest.mark.parametrize("foreign_keys", (0, 1))
def test_revision_0027_recovers_a_proven_source_absent_creation_without_fk_mode_drift(tmp_path, foreign_keys):
    engine = _build_from_baseline_at_revision(tmp_path, "0027-recovery.db", "0026")
    stopped = False
    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if not stopped and "ALTER TABLE BACKTEST_COMPUTATIONS__0027 RENAME" in statement.upper():
            stopped = True
            raise RuntimeError("0027 injected interruption")
    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected interruption"):
            with engine.begin() as connection:
                raw = connection.connection.driver_connection
                raw.commit(); raw.execute(f"PRAGMA foreign_keys={foreign_keys}")
                command.upgrade(migrate.alembic_config(connection), "0027")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0027")
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
        assert "backtest_computations" in sa.inspect(connection).get_table_names()


def test_revision_0027_refuses_unproven_source_absent_temp_without_schema_mutation(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0027-forged.db", "0026")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE backtest_computations__0027 (attacker TEXT)"))
        before = connection.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE name='backtest_computations__0027'")) .scalar_one()
        with pytest.raises(RuntimeError, match="unproven"):
            command.upgrade(migrate.alembic_config(connection), "0027")
        assert connection.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE name='backtest_computations__0027'")) .scalar_one() == before
        assert "backtest_computations" not in sa.inspect(connection).get_table_names()


def test_revision_0027_recovers_after_table_rename_before_index_promotion(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0027-after-rename.db", "0026")
    stopped = False
    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if not stopped and "DROP INDEX IF EXISTS IX_BACKTEST_COMPUTATIONS_DATASET__0027" in statement.upper():
            stopped = True
            raise RuntimeError("0027 post-rename interruption")
    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="post-rename"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0027")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0027")
        names = {row[0] for row in connection.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='backtest_computations'"))}
        assert names == {"sqlite_autoindex_backtest_computations_1",
                         "ix_backtest_computations_dataset", "ix_backtest_computations_strategy"}


def test_revision_0027_refuses_schema_tampered_proven_temp_without_mutation(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0027-temp-tamper.db", "0026")
    stopped = False
    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if not stopped and "ALTER TABLE BACKTEST_COMPUTATIONS__0027 RENAME" in statement.upper():
            stopped = True
            raise RuntimeError("0027 proof interruption")
    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="proof interruption"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0027")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        connection.execute(sa.text("ALTER TABLE backtest_computations__0027 ADD COLUMN attacker TEXT"))
        with pytest.raises(RuntimeError, match="malformed"):
            command.upgrade(migrate.alembic_config(connection), "0027")
        assert "backtest_computations" not in sa.inspect(connection).get_table_names()
        assert "backtest_computations__0027" in sa.inspect(connection).get_table_names()


def test_revision_0027_refuses_forged_existing_target_schema_without_mutation(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0027-forged-target.db", "0026")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE backtest_computations (attacker TEXT)"))
        with pytest.raises(RuntimeError, match="non-target schema"):
            command.upgrade(migrate.alembic_config(connection), "0027")
        assert connection.execute(sa.text("PRAGMA table_info(backtest_computations)")).all() == [(0, "attacker", "TEXT", 0, None, 0)]


def test_revision_0027_downgrade_refuses_nonempty_artifact_without_mutation(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0027-down-refusal.db", "0027")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO backtest_computations VALUES (:e,:d,'s','v',:p,8,'{}',:h)"),
            {"e": "a" * 64, "d": "b" * 64, "p": "c" * 64, "h": "d" * 64})
        with pytest.raises(RuntimeError, match="refuses"):
            command.downgrade(migrate.alembic_config(connection), "0026")
        assert connection.execute(sa.text("SELECT count(*) FROM backtest_computations")).scalar_one() == 1


def test_revision_0027_nonempty_downgrade_preflight_performs_no_recovery_ddl(tmp_path):
    """A downgrade request must refuse before it cleans any proof/index state."""
    engine = _build_from_baseline_at_revision(tmp_path, "0027-down-preflight.db", "0027")
    statements = []
    def capture(_conn, _cursor, statement, _params, _context, _many):
        statements.append(" ".join(statement.upper().split()))
    sa.event.listen(engine, "before_cursor_execute", capture)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO backtest_computations VALUES (:e,:d,'s','v',:p,8,'{}',:h)"),
                {"e": "a" * 64, "d": "b" * 64, "p": "c" * 64, "h": "d" * 64})
            with pytest.raises(RuntimeError, match="refuses"):
                command.downgrade(migrate.alembic_config(connection), "0026")
    finally:
        sa.event.remove(engine, "before_cursor_execute", capture)
    assert not any("DROP TABLE BACKTEST_COMPUTATIONS" in statement
                   or "ALTER TABLE BACKTEST_COMPUTATIONS" in statement
                   or "DELETE FROM _BACKTEST_0027" in statement for statement in statements)


@pytest.mark.parametrize("foreign_keys", (0, 1))
@pytest.mark.parametrize("needle,recoverable", (
    ("CREATE TABLE BACKTEST_COMPUTATIONS__0027", True),
    # The proof write is the authentication boundary: without it a temp may
    # never promote itself by merely having target-looking columns.
    ("INSERT OR REPLACE INTO _BACKTEST_0027_CREATION_PROOFS", False),
    ("ALTER TABLE BACKTEST_COMPUTATIONS__0027 RENAME TO BACKTEST_COMPUTATIONS", True),
    ("DELETE FROM _BACKTEST_0027_CREATION_PROOFS", True),
))
def test_revision_0027_restart_matrix_is_target_bound_and_preserves_fk_mode(
        tmp_path, foreign_keys, needle, recoverable):
    engine = _build_from_baseline_at_revision(
        tmp_path, f"0027-restart-{foreign_keys}-{abs(hash(needle))}.db", "0026")
    stopped = False
    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if not stopped and needle in " ".join(statement.upper().split()):
            stopped = True
            raise RuntimeError("0027 boundary")
    with engine.begin() as connection:
        raw = connection.connection.driver_connection
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={foreign_keys}")
    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="boundary"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0027")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        if not recoverable:
            schema = tuple(connection.execute(sa.text(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all())
            with pytest.raises(RuntimeError, match="(unproven|malformed)"):
                command.upgrade(migrate.alembic_config(connection), "0027")
            assert tuple(connection.execute(sa.text(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all()) == schema
            assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
            return
        command.upgrade(migrate.alembic_config(connection), "0027")
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        assert connection.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE name='_backtest_0027_creation_proofs'")) .first() is None


def test_revision_0027_empty_downgrade_has_exact_0026_schema_parity(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0027-empty-down.db", "0027")
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0026")
        assert not {"backtest_computations", "backtest_computations__0027",
                    "_backtest_0027_creation_proofs"} & set(
                        sa.inspect(connection).get_table_names())
    assert migrate.schema_version(engine) == "0026"


def test_revision_0026_backfills_legacy_cells_and_refuses_duplicate_new_identity(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0026-resume-cells.db", "0025")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO backtest_runs (id,owner_id,created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies,queued_at) "
            "VALUES (941,'owner','2026-08-12','done','liquid','day',1,1,1,'','max','','','2026-08-12')"))
        connection.execute(sa.text(
            "INSERT INTO backtest_results (id,owner_id,run_id,instrument_key,name,segment,strategy_key,interval,trades,wins,win_rate,profit_factor,max_drawdown_pct,return_pct,net_pnl,gross_pnl,charges,expectancy,cagr,calmar,consistency,sharpe,max_consec_losses,time_underwater_pct,worst_trade_pnl,worst_mae_pct,notional,lots,affordable,option_cost,open_at_end,win_rate_realised,return_pct_realised,bh_return_pct,first_ts,last_ts,effective_days,clamped,bars,curve_json,bh_curve_json,trades_json,error,premium_trades,premium_win_rate,premium_net_pnl,premium_return_pct,premium_profit_factor,premium_max_drawdown_pct,premium_expectancy,premium_charges,premium_trades_json,premium_error,params_hash,last_candle_ts,schema_version,from_cache) "
            "VALUES (942,'owner',941,'NIFTY','NIFTY','NSE','s','day',0,0,0,NULL,0,0,0,0,0,0,NULL,NULL,NULL,NULL,0,0,0,0,0,0,1,0,0,0,0,NULL,0,0,0,0,0,'[]','[]','[]','',0,0,0,0,NULL,0,0,0,'[]','', '',0,1,0)"))
        command.upgrade(migrate.alembic_config(connection), "0026")
        assert connection.execute(sa.text("SELECT cell_key FROM backtest_results WHERE id=942")).scalar_one() == "legacy:942"


def test_revision_0026_successful_downgrade_removes_rebuild_proofs_and_matches_0025_schema(tmp_path):
    """A completed reversible downgrade leaves neither working state nor schema drift."""
    engine = _build_from_baseline_at_revision(tmp_path, "0026-clean-downgrade.db", "0026")
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0025")
        assert connection.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_backtest_0026_rebuild_proofs'"
        )).first() is None
        downgraded = connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE tbl_name IN ('backtest_runs','backtest_results') "
            "OR (type='index' AND tbl_name IN ('backtest_runs','backtest_results')) "
            "ORDER BY type,name")).all()
    expected = _build_from_baseline_at_revision(tmp_path, "0025-schema-parity.db", "0025")
    with expected.begin() as connection:
        baseline = connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE tbl_name IN ('backtest_runs','backtest_results') "
            "OR (type='index' AND tbl_name IN ('backtest_runs','backtest_results')) "
            "ORDER BY type,name")).all()
    assert downgraded == baseline


@pytest.mark.parametrize("foreign_keys", (0, 1))
@pytest.mark.parametrize("needle", (
    "INSERT INTO BACKTEST_RESULTS__0026_DOWN",
    "INSERT OR REPLACE INTO _BACKTEST_0026_REBUILD_PROOFS",
    "DROP TABLE BACKTEST_RESULTS",
    "ALTER TABLE BACKTEST_RESULTS__0026_DOWN RENAME TO BACKTEST_RESULTS",
    "DELETE FROM _BACKTEST_0026_REBUILD_PROOFS",
))
def test_revision_0026_downgrade_restart_matrix_preserves_legacy_parity_and_fk_mode(
        tmp_path, foreign_keys, needle):
    """Every durable downgrade boundary restarts from a source-bound manifest."""
    engine = _build_from_baseline_at_revision(
        tmp_path, f"0026-down-{foreign_keys}-{abs(hash(needle))}.db", "0026")
    with engine.begin() as connection:
        raw = connection.connection.driver_connection
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={foreign_keys}")
        before_runs = connection.execute(sa.text(
            "SELECT id,owner_id,status,scope,intervals,capital,total,done,note "
            "FROM backtest_runs ORDER BY id")).all()
        before_results = connection.execute(sa.text(
            "SELECT id,owner_id,run_id,instrument_key,strategy_key,interval,error "
            "FROM backtest_results ORDER BY id")).all()
    stopped = False
    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if not stopped and needle in " ".join(statement.upper().split()):
            stopped = True
            raise RuntimeError("0026 downgrade injected interruption")
    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected interruption"):
            with engine.begin() as connection:
                command.downgrade(migrate.alembic_config(connection), "0025")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        assert stopped
        command.downgrade(migrate.alembic_config(connection), "0025")
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
        assert connection.execute(sa.text(
            "SELECT id,owner_id,status,scope,intervals,capital,total,done,note "
            "FROM backtest_runs ORDER BY id")).all() == before_runs
        assert connection.execute(sa.text(
            "SELECT id,owner_id,run_id,instrument_key,strategy_key,interval,error "
            "FROM backtest_results ORDER BY id")).all() == before_results


def test_revision_0025_preserves_0024_rows_and_adds_portable_job_fields(tmp_path):
    """0025 must preserve evidence while giving every legacy run a queue timestamp."""
    engine = _build_from_baseline_at_revision(tmp_path, "0025-populated.db", "0024")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO backtest_runs (id,owner_id,created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies) "
            "VALUES (812,'owner','2026-08-12 01:02:03','done','liquid','day',12.5,4,4,'exact','max','NIFTY','s')"))
        before = connection.execute(sa.text("SELECT * FROM backtest_runs WHERE id=812")).one()
        command.upgrade(migrate.alembic_config(connection), "0025")
        after = connection.execute(sa.text("SELECT * FROM backtest_runs WHERE id=812")).one()
        assert after.id == before.id and after.owner_id == before.owner_id
        assert after.status == before.status and after.note == before.note
        assert str(after.queued_at).startswith("2026-08-12 01:02:03")
        assert after.claim_token is None and after.attempt_count == 0
        command.downgrade(migrate.alembic_config(connection), "0024")
        assert connection.execute(sa.text("SELECT * FROM backtest_runs WHERE id=812")).one() == before


def test_revision_0025_downgrade_refuses_persisted_claim_state_without_mutation(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0025-downgrade-refusal.db", "0025")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO backtest_runs (owner_id,created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies,queued_at,claim_token,attempt_count) "
            "VALUES ('owner','2026-08-12','running','liquid','day',1,1,0,'','max','','','2026-08-12','fence',1)"))
        schema = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all())
        with pytest.raises(RuntimeError, match="durable claim state"):
            command.downgrade(migrate.alembic_config(connection), "0024")
        assert tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all()) == schema


def test_revision_0025_recovers_only_a_proven_promoted_run_rebuild(tmp_path):
    """A restart may clean a proved promoted table, never an unauthenticated temp."""
    engine = _build_from_baseline_at_revision(tmp_path, "0025-recovery.db", "0024")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO backtest_runs (id,owner_id,created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies) "
            "VALUES (71,'owner','2026-08-12','done','liquid','day',1,1,1,'keep','max','','')"))
    interrupted = False
    def stop_after_promotion(_conn, _cursor, statement, params, _context, _many):
        nonlocal interrupted
        normalized = " ".join(statement.upper().split())
        values = tuple(params.values()) if isinstance(params, dict) else tuple(params or ())
        if (not interrupted and normalized.startswith("DELETE FROM _BACKTEST_0025_REBUILD_PROOFS")
                and ("backtest_runs" in values or "TABLE_NAME='BACKTEST_RUNS'" in normalized)):
            interrupted = True
            raise RuntimeError("interrupt after proved promotion")
    sa.event.listen(engine, "before_cursor_execute", stop_after_promotion)
    try:
        with pytest.raises(RuntimeError, match="interrupt after proved promotion"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0025")
    finally:
        sa.event.remove(engine, "before_cursor_execute", stop_after_promotion)
    with engine.begin() as connection:
        assert interrupted and "_backtest_0025_rebuild_proofs" in sa.inspect(connection).get_table_names()
        command.upgrade(migrate.alembic_config(connection), "0025")
        row = connection.execute(sa.text("SELECT id,note,queued_at FROM backtest_runs WHERE id=71")).one()
        assert row.id == 71 and row.note == "keep" and row.queued_at is not None


def test_revision_0025_refuses_unproven_or_forged_source_absent_temp_without_mutation(tmp_path):
    """A temp table never authenticates its own schema or payload proof."""
    engine = _build_from_baseline_at_revision(tmp_path, "0025-forged-temp.db", "0024")
    with engine.begin() as connection:
        connection.execute(sa.text("ALTER TABLE backtest_runs RENAME TO backtest_runs__good"))
        connection.execute(sa.text(
            "CREATE TABLE backtest_runs__0025 AS SELECT * FROM backtest_runs__good"))
        connection.execute(sa.text("DROP TABLE backtest_runs__good"))
        before = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all())
    with pytest.raises(RuntimeError, match="unproven completed rebuild"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0025")
    with engine.connect() as connection:
        assert migrate.schema_version(engine) == "0024"
        assert tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all()) == before


@pytest.mark.parametrize("foreign_keys", (0, 1))
def test_revision_0025_preserves_fk_mode_on_success_and_recovery_failure(tmp_path, foreign_keys):
    engine = _build_from_baseline_at_revision(tmp_path, f"0025-fk-{foreign_keys}.db", "0024")
    with engine.begin() as connection:
        raw = connection.connection.driver_connection
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={foreign_keys}")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0025")
    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
    # Downgrade has no claim state, then an injected rebuild failure must restore
    # the caller's SQLite enforcement mode and leave the prior revision stamped.
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0024")
    injected = False
    def stop_before_temp(_conn, _cursor, statement, _params, _context, _many):
        nonlocal injected
        if not injected and statement.lstrip().upper().startswith("CREATE TABLE BACKTEST_RUNS__0025"):
            injected = True
            raise RuntimeError("0025 injected rebuild failure")
    sa.event.listen(engine, "before_cursor_execute", stop_before_temp)
    try:
        with pytest.raises(RuntimeError, match="0025 injected rebuild failure"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0025")
    finally:
        sa.event.remove(engine, "before_cursor_execute", stop_before_temp)
    with engine.connect() as connection:
        assert injected and migrate.schema_version(engine) == "0024"
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys


@pytest.mark.parametrize("phase,needle", (
    ("after-copy", "INSERT INTO BACKTEST_RUNS__0025"),
    ("after-proof", "INSERT OR REPLACE INTO _BACKTEST_0025_REBUILD_PROOFS"),
    ("after-drop", "DROP TABLE BACKTEST_RUNS"),
    ("after-rename", "ALTER TABLE BACKTEST_RUNS__0025 RENAME TO BACKTEST_RUNS"),
))
def test_revision_0025_restart_matrix_recovers_each_durable_rebuild_phase(tmp_path, phase, needle):
    """Every interruption boundary must retry through the target-bound proof path."""
    engine = _build_from_baseline_at_revision(tmp_path, f"0025-{phase}.db", "0024")
    stopped = False
    def interrupt(_conn, _cursor, statement, params, _context, _many):
        nonlocal stopped
        normalized = " ".join(statement.upper().split())
        values = tuple(params.values()) if isinstance(params, dict) else tuple(params or ())
        matches = needle in normalized
        if phase == "after-proof":
            matches = needle in normalized and "backtest_runs" in values
        if not stopped and matches:
            stopped = True
            raise RuntimeError(f"stop {phase}")
    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match=f"stop {phase}"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0025")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        assert stopped
        command.upgrade(migrate.alembic_config(connection), "0025")
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        assert "queued_at" in {c["name"] for c in sa.inspect(connection).get_columns("backtest_runs")}
    assert migrate.schema_version(engine) == "0025"


@pytest.mark.parametrize("mutation", (
    "UPDATE backtest_runs__0025 SET note='tampered'",
    "ALTER TABLE backtest_runs__0025 ADD COLUMN attacker TEXT",
))
def test_revision_0025_refuses_row_or_schema_tampered_proven_temp_without_mutation(tmp_path, mutation):
    """A proof records both payload and canonical target schema, not a hint."""
    engine = _build_from_baseline_at_revision(tmp_path, "0025-temp-tamper.db", "0024")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO backtest_runs (id,owner_id,created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies) "
            "VALUES (97,'owner','2026-08-12','done','liquid','day',1,1,1,'original','max','','')"))
    stopped = False
    def stop_before_rename(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if not stopped and statement.upper().startswith("ALTER TABLE BACKTEST_RUNS__0025 RENAME"):
            stopped = True
            raise RuntimeError("leave proven temp")
    sa.event.listen(engine, "before_cursor_execute", stop_before_rename)
    try:
        with pytest.raises(RuntimeError, match="leave proven temp"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0025")
    finally:
        sa.event.remove(engine, "before_cursor_execute", stop_before_rename)
    with engine.begin() as connection:
        connection.execute(sa.text(mutation))
        before = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all())
    with pytest.raises(RuntimeError, match="malformed completed rebuild"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0025")
    with engine.connect() as connection:
        assert tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all()) == before
        assert migrate.schema_version(engine) == "0024"


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


def _build_from_baseline_at_revision(tmp_path, name: str, revision: str):
    """Build a historical database at the revision this test actually exercises.

    Historical rollback tests must not start at today's head: later revisions can
    intentionally refuse a downgrade for unrelated, data-safety reasons.
    """
    engine = _fresh_engine(tmp_path, name)
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), revision)
    return engine


def _upgrade_to_revision(engine, revision: str) -> str:
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), revision)
    return migrate.schema_version(engine)


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


def test_revision_0024_owns_backtest_evidence_and_preserves_fk_mode(tmp_path):
    """Legacy run/result bytes upgrade to the same owner without losing relation safety."""
    engine = _build_from_baseline_at_revision(tmp_path, "0024-fk-mode.db", "0023")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO backtest_runs (id,created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies) "
            "VALUES (991,'2026-08-12 10:00:00','done','liquid','day',123.0,1,1,'exact','max','NIFTY','trend_impulse_v3')"))
        connection.execute(sa.text(
            "INSERT INTO backtest_results (id,run_id,instrument_key,name,segment,strategy_key,interval,trades,wins,win_rate,profit_factor,max_drawdown_pct,return_pct,net_pnl,gross_pnl,charges,expectancy,cagr,calmar,consistency,sharpe,max_consec_losses,time_underwater_pct,worst_trade_pnl,worst_mae_pct,notional,lots,affordable,option_cost,open_at_end,win_rate_realised,return_pct_realised,bh_return_pct,first_ts,last_ts,effective_days,clamped,bars,curve_json,bh_curve_json,trades_json,error,premium_trades,premium_win_rate,premium_net_pnl,premium_return_pct,premium_profit_factor,premium_max_drawdown_pct,premium_expectancy,premium_charges,premium_trades_json,premium_error,params_hash,last_candle_ts,schema_version,from_cache,computed_at) "
            "VALUES (991,991,'NIFTY','exact','nse','trend_impulse_v3','day',1,1,100,NULL,0,1,1,1,0,1,NULL,NULL,NULL,NULL,0,0,0,0,1,1,1,1,0,100,1,NULL,1,2,1,0,2,'[]','[]','[]','',0,0,0,0,NULL,0,0,0,'[]','', 'hash',2,8,0,NULL)"))
        raw = connection.connection.driver_connection
        raw.commit(); raw.execute("PRAGMA foreign_keys=1")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0024")
        assert connection.execute(sa.text("SELECT owner_id FROM backtest_runs WHERE id=991")).scalar_one() == "owner"
        assert connection.execute(sa.text("SELECT owner_id FROM backtest_results WHERE id=991")).scalar_one() == "owner"
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == 1
    assert migrate.schema_version(engine) == "0024"


def _backtest_0024_contract(engine, table: str) -> dict:
    inspector = sa.inspect(engine)
    return {
        "columns": tuple((c["name"], str(c["type"]), bool(c["nullable"]),
                          str(c.get("default"))) for c in inspector.get_columns(table)),
        "pk": tuple(inspector.get_pk_constraint(table)["constrained_columns"]),
        "unique": tuple(sorted(tuple(c["column_names"])
                               for c in inspector.get_unique_constraints(table))),
        "foreign": tuple(sorted((tuple(c["constrained_columns"]),
                                 c["referred_table"], tuple(c["referred_columns"]),
                                 c.get("options", {}).get("ondelete"))
                                for c in inspector.get_foreign_keys(table))),
        "indexes": tuple(sorted((c["name"], tuple(c["column_names"]), bool(c.get("unique")))
                                for c in inspector.get_indexes(table))),
        "checks": tuple(sorted(c["sqltext"] for c in inspector.get_check_constraints(table))),
    }


def test_revision_0024_fresh_and_upgraded_contract_match_pk_unique_fk_actions_defaults_indexes(tmp_path):
    """Parity includes the relational contract, not just column names and index tuples."""
    # This is a historical 0024 contract test; do not accidentally compare it
    # against later job-coordinate fields now present at head.
    fresh = _build_from_baseline_at_revision(tmp_path, "0024-fresh-contract.db", "0024")
    upgraded = _build_from_baseline_at_revision(tmp_path, "0024-upgraded-contract.db", "0024")
    for table in ("backtest_runs", "backtest_results"):
        assert _backtest_0024_contract(upgraded, table) == _backtest_0024_contract(fresh, table)

    result_foreign = _backtest_0024_contract(upgraded, "backtest_results")["foreign"]
    assert (("owner_id", "run_id"), "backtest_runs", ("owner_id", "id"), "RESTRICT") in result_foreign
    assert (("owner_id",), "organizations", ("organization_id",), "RESTRICT") in result_foreign


def test_revision_0024_preserves_populated_legacy_run_and_result_payloads_exactly(tmp_path):
    engine = _at_revision_0020(tmp_path, "0024-populated-exact.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
        connection.execute(sa.text(
            "INSERT INTO backtest_runs (id,created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies) "
            "VALUES (734,'2026-07-08 01:02:03','error','full','day,15minute',9876.5,7,3,'exact note','2025-01','NIFTY,BANKNIFTY','s1,s2')"))
        connection.execute(sa.text(
            "INSERT INTO backtest_results (id,run_id,instrument_key,name,segment,strategy_key,interval,trades,wins,win_rate,profit_factor,max_drawdown_pct,return_pct,net_pnl,gross_pnl,charges,expectancy,cagr,calmar,consistency,sharpe,max_consec_losses,time_underwater_pct,worst_trade_pnl,worst_mae_pct,notional,lots,affordable,option_cost,open_at_end,win_rate_realised,return_pct_realised,bh_return_pct,first_ts,last_ts,effective_days,clamped,bars,curve_json,bh_curve_json,trades_json,error,premium_trades,premium_win_rate,premium_net_pnl,premium_return_pct,premium_profit_factor,premium_max_drawdown_pct,premium_expectancy,premium_charges,premium_trades_json,premium_error,params_hash,last_candle_ts,schema_version,from_cache,computed_at) "
            "VALUES (735,734,'NIFTY','Nifty exact','NFO','s1','day',9,4,44.4,1.2,8.3,-2.1,-123.45,-100,23.45,-13.7,1.1,2.2,3.3,4.4,5,6.7,-8.9,-1.2,1234,2,1,222,0,45.6,-1.1,7.8,111,222,3,1,44,'[1]','[2]','[\"x\"]','exact error',2,50,4.5,5.6,1.1,2.2,3.3,4.4,'[]','premium error','hash-exact',123,8,1,'2026-07-08 04:05:06')"))
        before_run = connection.execute(sa.text("SELECT * FROM backtest_runs WHERE id=734")).one()
        before_result = connection.execute(sa.text("SELECT * FROM backtest_results WHERE id=735")).one()
        before_contract = {table: _backtest_0024_contract(engine, table)
                           for table in ("backtest_runs", "backtest_results")}
        command.upgrade(migrate.alembic_config(connection), "0024")
        after_run = connection.execute(sa.text("SELECT * FROM backtest_runs WHERE id=734")).one()
        after_result = connection.execute(sa.text("SELECT * FROM backtest_results WHERE id=735")).one()
    assert after_run.owner_id == after_result.owner_id == "owner"
    assert tuple(after_run)[0:1] + tuple(after_run)[2:] == tuple(before_run)
    assert tuple(after_result)[0:1] + tuple(after_result)[2:] == tuple(before_result)
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0023")
        assert connection.execute(sa.text("SELECT * FROM backtest_runs WHERE id=734")).one() == before_run
        assert connection.execute(sa.text("SELECT * FROM backtest_results WHERE id=735")).one() == before_result
        assert {table: _backtest_0024_contract(engine, table)
                for table in ("backtest_runs", "backtest_results")} == before_contract
        command.upgrade(migrate.alembic_config(connection), "0024")
        assert connection.execute(sa.text("SELECT owner_id FROM backtest_runs WHERE id=734")).scalar_one() == "owner"
        assert connection.execute(sa.text("SELECT owner_id FROM backtest_results WHERE id=735")).scalar_one() == "owner"


@pytest.mark.parametrize("foreign_keys", (0, 1))
def test_revision_0024_restores_callers_fk_mode_on_success_and_failure(tmp_path, foreign_keys):
    engine = _at_revision_0020(tmp_path, f"0024-fk-{foreign_keys}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
        raw = connection.connection.driver_connection
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={foreign_keys}")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0024")
    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys


@pytest.mark.parametrize("table", ("backtest_runs", "backtest_results"))
def test_revision_0024_refuses_unproven_completed_temp_without_mutation(tmp_path, table):
    engine = _at_revision_0020(tmp_path, f"0024-unproven-{table}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
        connection.execute(sa.text(f"ALTER TABLE {table} RENAME TO {table}__0024"))
        before = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all())
    with pytest.raises(RuntimeError, match="unproven completed rebuild"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0024")
    with engine.connect() as connection:
        assert tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all()) == before
        assert migrate.schema_version(engine) == "0023"


def test_revision_0024_refuses_self_consistent_but_noncanonical_completed_temp_contract(tmp_path):
    """A durable proof authenticates the 0024 contract, never an attacker temp's DDL."""
    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        # Start from a real owned table, then replace its source-absent recovery
        # candidate with a payload-equivalent but constraint-free table.  The
        # deliberately self-consistent proof models the bug: the old migration
        # trusted a digest taken from this temp itself.
        connection.execute(sa.text("ALTER TABLE backtest_runs RENAME TO backtest_runs__good"))
        connection.execute(sa.text(
            "CREATE TABLE backtest_runs__0024 AS "
            "SELECT * FROM backtest_runs__good"
        ))
        connection.execute(sa.text("DROP TABLE backtest_runs__good"))
        rows = connection.execute(sa.text(
            "SELECT * FROM backtest_runs__0024 ORDER BY rowid"
        )).all()
        row_digest = hashlib.sha256(json.dumps(
            [list(row) for row in rows], default=str, separators=(",", ":")
        ).encode()).hexdigest()
        schema_rows = connection.execute(sa.text(
            "SELECT type,name,sql FROM sqlite_master WHERE tbl_name='backtest_runs__0024' "
            "AND type IN ('table','index','trigger') ORDER BY type,name"
        )).all()
        normalized = []
        for row in schema_rows:
            sql = row.sql or ""
            name = row.name
            for logical in ("backtest_runs", "backtest_results"):
                sql = re.sub(re.escape(logical) + r"(?:__0024)?", f"__{logical}__", sql)
                name = re.sub(re.escape(logical) + r"(?:__0024)?", f"__{logical}__", name)
            normalized.append(
                f"{row.type}:{name}:" +
                " ".join(sql.replace('"', '').replace('`', '').split()).lower()
            )
        schema_digest = hashlib.sha256("\n".join(normalized).encode()).hexdigest()
        connection.execute(sa.text(
            "CREATE TABLE _backtest_0024_rebuild_proofs ("
            "table_name VARCHAR(64) PRIMARY KEY, row_count INTEGER NOT NULL, "
            "row_digest VARCHAR(64) NOT NULL, direction VARCHAR(8) NOT NULL, "
            "schema_digest VARCHAR(64) NOT NULL, phase VARCHAR(16) NOT NULL)"
        ))
        connection.execute(sa.text(
            "INSERT INTO _backtest_0024_rebuild_proofs VALUES "
            "('backtest_runs',:count,:digest,'up',:schema,'built')"
        ), {"count": len(rows), "digest": row_digest, "schema": schema_digest})
        connection.execute(sa.text("UPDATE alembic_version SET version_num='0023'"))
        before = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )).all())
    with pytest.raises(RuntimeError, match="malformed completed rebuild"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0024")
    with engine.connect() as connection:
        assert tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )).all()) == before
        assert migrate.schema_version(engine) == "0023"


@pytest.mark.parametrize("table", ("backtest_runs", "backtest_results"))
def test_revision_0024_discards_source_present_stale_temp(tmp_path, table):
    engine = _at_revision_0020(tmp_path, f"0024-stale-{table}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
        connection.execute(sa.text(f"CREATE TABLE {table}__0024 (attacker TEXT)"))
        command.upgrade(migrate.alembic_config(connection), "0024")
        assert f"{table}__0024" not in sa.inspect(connection).get_table_names()


def test_revision_0024_legacy_only_downgrade_is_lossless_and_reupgradeable(tmp_path):
    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0023")
        assert "owner_id" not in {c["name"] for c in sa.inspect(connection).get_columns("backtest_runs")}
        command.upgrade(migrate.alembic_config(connection), "0024")
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
    assert migrate.schema_version(engine) == "0024"


def test_revision_0024_downgrade_refuses_nonlegacy_owner_before_mutation(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0024-owner-refusal.db", "0024")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO organizations VALUES ('other','Other','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(sa.text(
            "INSERT INTO backtest_runs (owner_id,status,scope,intervals,capital,total,done,note,window,instruments,strategies,created_at) "
            "VALUES ('other','done','liquid','day',1,0,0,'','max','','',CURRENT_TIMESTAMP)"))
        before = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all())
    with pytest.raises(RuntimeError, match="owner collapse"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0023")
    with engine.connect() as connection:
        assert tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")).all()) == before
        assert migrate.schema_version(engine) == "0024"


@pytest.mark.parametrize("table", ("backtest_runs", "backtest_results"))
def test_revision_0024_post_rename_proof_retries_only_if_promoted_table_is_intact(tmp_path, table):
    engine = _at_revision_0020(tmp_path, f"0024-post-rename-{table}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
    stopped = False

    def interrupt(_conn, _cursor, statement, params, _context, _many):
        nonlocal stopped
        values = tuple(params.values()) if isinstance(params, dict) else tuple(params or ())
        if (not stopped and "DELETE FROM _BACKTEST_0024_REBUILD_PROOFS" in statement.upper()
                and table in values):
            stopped = True
            raise RuntimeError("interrupt after rename")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="interrupt after rename"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0024")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        assert stopped and table in sa.inspect(connection).get_table_names()
        command.upgrade(migrate.alembic_config(connection), "0024")
        assert "_backtest_0024_rebuild_proofs" not in sa.inspect(connection).get_table_names()


@pytest.mark.parametrize("table", ("backtest_runs", "backtest_results"))
@pytest.mark.parametrize("phase,needle", (
    ("after-insert", "INSERT OR REPLACE INTO _BACKTEST_0024_REBUILD_PROOFS"),
    ("after-proof", "DROP TABLE BACKTEST_"),
    ("after-drop", "ALTER TABLE BACKTEST_"),
))
def test_revision_0024_restart_matrix_recovers_each_table_at_every_durable_phase(
    tmp_path, table, phase, needle,
):
    """All pre-rename interruption points restart without bypassing recovery proof."""
    engine = _at_revision_0020(tmp_path, f"0024-{table}-{phase}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
    stopped = False

    def interrupt(_conn, _cursor, statement, params, _context, _many):
        nonlocal stopped
        statement = statement.upper()
        target = table.upper()
        matches = needle in statement and target in statement
        # The proof insertion carries the logical table only in bound params.
        if phase == "after-insert":
            values = tuple(params.values()) if isinstance(params, dict) else tuple(params or ())
            matches = needle in statement and table in values
        if not stopped and matches:
            stopped = True
            raise RuntimeError(f"interrupt {phase}")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match=f"interrupt {phase}"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0024")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    # For result-specific variants the run rebuild completes before the injected
    # interruption. Recovery must validate every candidate before changing either.
    with engine.begin() as connection:
        assert stopped
        command.upgrade(migrate.alembic_config(connection), "0024")
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
    assert migrate.schema_version(engine) == "0024"


@pytest.mark.parametrize("table,mutation", (
    ("backtest_runs", "UPDATE backtest_runs__0024 SET note='tampered'"),
    ("backtest_results", "UPDATE backtest_results__0024 SET error='tampered'"),
    ("backtest_runs", "ALTER TABLE backtest_runs__0024 ADD COLUMN attacker TEXT"),
    ("backtest_results", "ALTER TABLE backtest_results__0024 ADD COLUMN attacker TEXT"),
))
def test_revision_0024_refuses_row_or_schema_tampered_proven_temp_without_mutation(
    tmp_path, table, mutation,
):
    engine = _at_revision_0020(tmp_path, f"0024-{table}-tamper.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
        connection.execute(sa.text(
            "INSERT INTO backtest_runs (id,created_at,status,scope,intervals,capital,total,done,note,window,instruments,strategies) "
            "VALUES (880,CURRENT_TIMESTAMP,'done','liquid','day',1,1,1,'original','max','NIFTY','s1')"))
        if table == "backtest_results":
            connection.execute(sa.text(
                "INSERT INTO backtest_results (id,run_id,instrument_key,name,segment,strategy_key,interval,trades,wins,win_rate,profit_factor,max_drawdown_pct,return_pct,net_pnl,gross_pnl,charges,expectancy,cagr,calmar,consistency,sharpe,max_consec_losses,time_underwater_pct,worst_trade_pnl,worst_mae_pct,notional,lots,affordable,option_cost,open_at_end,win_rate_realised,return_pct_realised,bh_return_pct,first_ts,last_ts,effective_days,clamped,bars,curve_json,bh_curve_json,trades_json,error,premium_trades,premium_win_rate,premium_net_pnl,premium_return_pct,premium_profit_factor,premium_max_drawdown_pct,premium_expectancy,premium_charges,premium_trades_json,premium_error,params_hash,last_candle_ts,schema_version,from_cache,computed_at) "
                "VALUES (881,880,'NIFTY','Nifty','NFO','s1','day',1,1,100,NULL,0,1,1,1,0,1,NULL,NULL,NULL,NULL,0,0,0,0,1,1,1,1,0,100,1,NULL,1,2,1,0,2,'[]','[]','[]','original',0,0,0,0,NULL,0,0,0,'[]','', 'hash',2,8,0,NULL)"))
    stopped = False

    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if (not stopped and statement.upper().startswith(f"ALTER TABLE {table.upper()}__0024 RENAME")):
            stopped = True
            raise RuntimeError("stop with proven temp")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="stop with proven temp"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0024")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        assert stopped
        connection.execute(sa.text(mutation))
        before = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )).all())
    with pytest.raises(RuntimeError, match="malformed completed rebuild"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0024")
    with engine.connect() as connection:
        assert tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )).all()) == before


@pytest.mark.parametrize("foreign_keys", (0, 1))
def test_revision_0024_injected_failure_restores_fk_mode_and_version(tmp_path, foreign_keys):
    engine = _at_revision_0020(tmp_path, f"0024-failure-fk-{foreign_keys}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
        raw = connection.connection.driver_connection
        raw.commit(); raw.execute(f"PRAGMA foreign_keys={foreign_keys}")
    failed = False
    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal failed
        if not failed and statement.lstrip().upper().startswith("CREATE TABLE BACKTEST_RUNS__0024"):
            failed = True
            raise RuntimeError("injected 0024 failure")
    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected 0024 failure"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0024")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.connect() as connection:
        assert failed and migrate.schema_version(engine) == "0023"
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys


def test_revision_0024_retries_after_final_cleanup_before_stamp(tmp_path):
    engine = _at_revision_0020(tmp_path, "0024-final-cleanup.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
    stopped = False
    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if not stopped and statement.lstrip().upper().startswith(
                "DROP TABLE _BACKTEST_0024_REBUILD_PROOFS"):
            stopped = True
            raise RuntimeError("injected before stamp")
    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected before stamp"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0024")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        assert stopped and migrate.schema_version(engine) == "0023"
        command.upgrade(migrate.alembic_config(connection), "0024")
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []


@pytest.mark.parametrize("table", ("backtest_runs", "backtest_results"))
def test_revision_0024_downgrade_recovers_after_rename_before_proof_delete(tmp_path, table):
    engine = _build_from_baseline(tmp_path)
    stopped = False
    def interrupt(_conn, _cursor, statement, params, _context, _many):
        nonlocal stopped
        values = tuple(params.values()) if isinstance(params, dict) else tuple(params or ())
        if (not stopped and "DELETE FROM _BACKTEST_0024_REBUILD_PROOFS" in statement.upper()
                and table in values):
            stopped = True
            raise RuntimeError("interrupt downgrade after rename")
    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="interrupt downgrade after rename"):
            with engine.begin() as connection:
                command.downgrade(migrate.alembic_config(connection), "0023")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        assert stopped and migrate.schema_version(engine) == "0024"
        command.downgrade(migrate.alembic_config(connection), "0023")
        assert "owner_id" not in {c["name"] for c in sa.inspect(connection).get_columns(table)}
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []


def test_revision_0024_downgrade_refuses_cross_owner_before_stale_temp_cleanup(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0024-stale-owner-refusal.db", "0024")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO organizations VALUES ('other','Other','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(sa.text(
            "INSERT INTO backtest_runs (owner_id,status,scope,intervals,capital,total,done,note,window,instruments,strategies,created_at) "
            "VALUES ('other','done','liquid','day',1,0,0,'','max','','',CURRENT_TIMESTAMP)"))
        connection.execute(sa.text("CREATE TABLE backtest_results__0024 (attacker TEXT)"))
    with pytest.raises(RuntimeError, match="owner collapse"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0023")
    with engine.connect() as connection:
        assert "backtest_results__0024" in sa.inspect(connection).get_table_names()


def test_revision_0022_makes_every_review_table_owner_owned(tmp_path):
    """Historical review rows rebuild onto owner-first composite identities."""
    engine = _build_from_baseline(tmp_path)
    inspector = sa.inspect(engine)
    for table, key in (
        ("project_review_notes", ("owner_id", "note_id")),
        ("project_review_saved_views", ("owner_id", "view_id")),
        ("project_review_snapshots", ("owner_id", "snapshot_id")),
    ):
        assert [column["name"] for column in inspector.get_columns(table)][0] == "owner_id"
        assert tuple(inspector.get_pk_constraint(table)["constrained_columns"]) == key
        assert any(
            tuple(foreign_key["constrained_columns"]) == ("owner_id", "project_id")
            and tuple(foreign_key["referred_columns"]) == ("owner_id", "project_id")
            and foreign_key["options"].get("ondelete") == "RESTRICT"
            for foreign_key in inspector.get_foreign_keys(table)
        )


REVIEW_0022_TABLES = (
    "project_review_notes", "project_review_saved_views", "project_review_snapshots",
)


def _write_0022_completed_proof(connection, table: str) -> None:
    """Model the durable point after 0022 dropped its source but before rename."""
    rows = connection.execute(sa.text(f"SELECT * FROM {table}__0022 ORDER BY rowid")).all()
    row_digest = hashlib.sha256(json.dumps(
        [list(row) for row in rows], default=str, separators=(",", ":")
    ).encode()).hexdigest()
    table_sql = connection.execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"
    ), {"table": f"{table}__0022"}).scalar_one()
    schema_digest = hashlib.sha256(" ".join(
        table_sql.replace(f"{table}__0022", "__TABLE__").replace("\n", " ").replace('"', "").replace("`", "").split()
    ).lower().encode()).hexdigest()
    connection.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS _review_0022_rebuild_proofs ("
        "table_name VARCHAR(64) NOT NULL PRIMARY KEY, row_count INTEGER NOT NULL, "
        "row_digest VARCHAR(64) NOT NULL, direction VARCHAR(8) NOT NULL, "
        "schema_digest VARCHAR(64) NOT NULL, phase VARCHAR(16) NOT NULL)"
    ))
    connection.execute(sa.text(
        "INSERT INTO _review_0022_rebuild_proofs VALUES (:table,:count,:row_digest,'up',:schema_digest,'built')"
    ), {
        "table": table, "count": len(rows), "row_digest": row_digest,
        "schema_digest": schema_digest,
    })


def _populated_review_0021(engine) -> dict[str, tuple[tuple[object, ...], ...]]:
    """Literal legacy bytes prove 0022 copies review payloads without rewriting them."""
    manifest = (
        '{"captured_queues":{"active_findings":[],"pending_candidates":[],'
        '"review_needed_runs":[]},"events":[],"notes":[],"project_id":'
        '"project.review.legacy","schema_version":1,"source_errors":[]}'
    )
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO projects (project_id,owner_id,name,description,status,created_at,updated_at) "
            "VALUES ('project.review.legacy','owner','Review legacy','exact','active',"
            "'2026-08-12 09:10:11','2026-08-12 09:10:12')"
        ))
        connection.execute(sa.text(
            "INSERT INTO project_review_notes VALUES "
            "('note.legacy','project.review.legacy','graph:legacy:1','graph_version_published',"
            "'exact note bytes','owner',7,'2026-08-12 09:10:13','2026-08-12 09:10:11','2026-08-12 09:10:12')"
        ))
        connection.execute(sa.text(
            "INSERT INTO project_review_saved_views VALUES "
            "('view.legacy','project.review.legacy','Exact view',:filters,"
            "'owner',4,'2026-08-12 09:10:14','2026-08-12 09:10:11','2026-08-12 09:10:12')"
        ), {"filters": '{"limit":25}'})
        connection.execute(sa.text(
            "INSERT INTO project_review_snapshots VALUES "
            "('snapshot.legacy','project.review.legacy','Exact snapshot',"
            "'2ba56d22-7094-4a8d-9bf5-b84a4e8f083f',:manifest,:address,'owner',"
            "'2026-08-12 09:10:11','2026-08-12 09:10:12')"
        ), {"manifest": manifest, "address": "sha256:" + "a" * 64})
    with engine.connect() as connection:
        return {
            table: tuple(connection.execute(sa.text(f"SELECT * FROM {table}")).all())
            for table in REVIEW_0022_TABLES
        }


def test_revision_0022_populated_upgrade_preserves_review_bytes_and_schema_parity(tmp_path):
    upgraded = _at_revision_0020(tmp_path, "0022-populated-upgrade.db")
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0021")
    before = _populated_review_0021(upgraded)
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
    with upgraded.connect() as connection:
        for table, rows in before.items():
            actual = tuple(connection.execute(sa.text(
                f"SELECT * FROM {table} ORDER BY 1,2"
            )).all())
            assert [row[1:] for row in actual] == list(rows)
            assert {row[0] for row in actual} == {"owner"}

    fresh = _build_from_models(tmp_path)
    for table in REVIEW_0022_TABLES:
        assert _semantic_contract(_revision_0020_contract(upgraded, table)) == _semantic_contract(
            _revision_0020_contract(fresh, table)
        )


@pytest.mark.parametrize("table", REVIEW_0022_TABLES)
def test_revision_0022_upgrade_recovers_stale_and_completed_temp_tables(tmp_path, table):
    engine = _at_revision_0020(tmp_path, f"0022-{table}-recovery.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0021")
        connection.execute(sa.text(f"CREATE TABLE {table}__0022 (stale INTEGER)"))
        command.upgrade(migrate.alembic_config(connection), "0022")
        assert f"{table}__0022" not in sa.inspect(connection).get_table_names()

        # This is the durable post-DROP shape: the finished table is only waiting
        # for its rename. Re-running 0022 must promote it, not discard it.
        connection.execute(sa.text(f"ALTER TABLE {table} RENAME TO {table}__0022"))
        _write_0022_completed_proof(connection, table)
        connection.execute(sa.text("UPDATE alembic_version SET version_num='0021'"))
        command.upgrade(migrate.alembic_config(connection), "0022")
    inspector = sa.inspect(engine)
    assert table in inspector.get_table_names()
    assert f"{table}__0022" not in inspector.get_table_names()


def test_revision_0022_refuses_an_unproven_completed_review_temp_without_mutation(tmp_path):
    engine = _at_revision_0020(tmp_path, "0022-unproven-completed-temp.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0021")
        connection.execute(sa.text(
            "ALTER TABLE project_review_notes RENAME TO project_review_notes__0022"
        ))
    before_names = tuple(sa.inspect(engine).get_table_names())
    with pytest.raises(RuntimeError, match="(unproven|malformed) completed rebuild"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0022")
    assert migrate.schema_version(engine) == "0021"
    assert tuple(sa.inspect(engine).get_table_names()) == before_names


def test_revision_0022_refuses_a_proven_payload_with_a_malformed_temp_contract_without_ddl(tmp_path):
    engine = _at_revision_0020(tmp_path, "0022-malformed-proven-temp.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
        source_sql = connection.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='project_review_notes'"
        )).scalar_one()
        expected_schema_digest = hashlib.sha256(" ".join(
            source_sql.replace("CREATE TABLE project_review_notes (", "CREATE TABLE __TABLE__ (", 1)
            .replace("\n", " ").replace('"', "").replace("`", "").split()
        ).lower().encode()).hexdigest()
        connection.execute(sa.text(
            "CREATE TABLE project_review_notes__0022 AS SELECT * FROM project_review_notes"
        ))
        rows = connection.execute(sa.text(
            "SELECT * FROM project_review_notes__0022 ORDER BY rowid"
        )).all()
        row_digest = hashlib.sha256(json.dumps(
            [list(row) for row in rows], default=str, separators=(",", ":")
        ).encode()).hexdigest()
        connection.execute(sa.text("DROP TABLE project_review_notes"))
        connection.execute(sa.text(
            "CREATE TABLE _review_0022_rebuild_proofs (table_name VARCHAR(64) NOT NULL PRIMARY KEY, "
            "row_count INTEGER NOT NULL, row_digest VARCHAR(64) NOT NULL, "
            "direction VARCHAR(8) NOT NULL, schema_digest VARCHAR(64) NOT NULL, phase VARCHAR(16) NOT NULL)"
        ))
        connection.execute(sa.text(
            "INSERT INTO _review_0022_rebuild_proofs VALUES "
            "('project_review_notes',:count,:row_digest,'up',:schema_digest,'built')"
        ), {"count": len(rows), "row_digest": row_digest, "schema_digest": expected_schema_digest})
        connection.execute(sa.text("UPDATE alembic_version SET version_num='0021'"))
    before = tuple(engine.connect().execute(sa.text(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
    )).all())
    with pytest.raises(RuntimeError, match="malformed completed rebuild"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0022")
    with engine.connect() as connection:
        after = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )).all())
    assert migrate.schema_version(engine) == "0021"
    assert after == before


@pytest.mark.parametrize("table", REVIEW_0022_TABLES)
@pytest.mark.parametrize("state", ("stale", "completed"))
def test_revision_0022_downgrade_recovers_each_review_temp_before_legacy_rebuild(
    tmp_path, table, state,
):
    engine = _at_revision_0020(tmp_path, f"0022-downgrade-{table}-{state}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
        if state == "stale":
            connection.execute(sa.text(f"CREATE TABLE {table}__0022 (stale INTEGER)"))
        else:
            connection.execute(sa.text(f"ALTER TABLE {table} RENAME TO {table}__0022"))
            _write_0022_completed_proof(connection, table)
        command.downgrade(migrate.alembic_config(connection), "0021")
    inspector = sa.inspect(engine)
    assert migrate.schema_version(engine) == "0021"
    assert f"{table}__0022" not in inspector.get_table_names()
    assert "owner_id" not in {column["name"] for column in inspector.get_columns(table)}


def test_revision_0022_legacy_round_trip_and_downgrade_refusal_are_lossless(tmp_path):
    engine = _at_revision_0020(tmp_path, "0022-review-round-trip.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0021")
    legacy_rows = _populated_review_0021(engine)
    legacy_contract = {table: _revision_0020_contract(engine, table) for table in REVIEW_0022_TABLES}
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
    with engine.connect() as connection:
        owned_rows = {
            table: tuple(connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY 1,2")).all())
            for table in REVIEW_0022_TABLES
        }

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0021")
    with engine.connect() as connection:
        assert migrate.schema_version(engine) == "0021"
        assert "_review_0022_rebuild_proofs" not in sa.inspect(connection).get_table_names()
        assert {
            table: tuple(connection.execute(sa.text(f"SELECT * FROM {table}")).all())
            for table in REVIEW_0022_TABLES
        } == legacy_rows
    assert {table: _revision_0020_contract(engine, table) for table in REVIEW_0022_TABLES} == legacy_contract
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
    with engine.connect() as connection:
        assert {
            table: tuple(connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY 1,2")).all())
            for table in REVIEW_0022_TABLES
        } == owned_rows

        connection.execute(sa.text(
            "INSERT INTO organizations VALUES ('owner.other','Other','active',"
            "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
        connection.execute(sa.text(
            "INSERT INTO projects (project_id,owner_id,name,description,status,created_at,updated_at) "
            "VALUES ('project.review.other','owner.other','Other','','active',"
            "CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
        raw = connection.connection.driver_connection
        raw.commit()
        raw.execute("PRAGMA foreign_keys=OFF")
        connection.execute(sa.text(
            "INSERT INTO project_review_notes VALUES "
            "('owner','note.unrepresentable','project.review.other','run:1','experiment_run',"
            "'cannot downgrade','owner',0,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
        raw.commit()
        raw.execute("PRAGMA foreign_keys=ON")

    before = {table: _revision_0020_contract(engine, table) for table in REVIEW_0022_TABLES}
    with pytest.raises(RuntimeError, match="cannot be represented by 0021"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0021")
    assert migrate.schema_version(engine) == "0022"
    assert {table: _revision_0020_contract(engine, table) for table in REVIEW_0022_TABLES} == before


def test_revision_0022_downgrade_refusal_preflight_does_not_recover_a_stale_temp(tmp_path):
    engine = _at_revision_0020(tmp_path, "0022-downgrade-read-only-preflight.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
        connection.execute(sa.text(
            "INSERT INTO organizations VALUES ('owner.other','Other','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
        connection.execute(sa.text(
            "INSERT INTO projects (project_id,owner_id,name,description,status,created_at,updated_at) "
            "VALUES ('project.review.other','owner.other','Other','','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
        raw = connection.connection.driver_connection
        raw.commit()
        raw.execute("PRAGMA foreign_keys=OFF")
        connection.execute(sa.text(
            "INSERT INTO project_review_notes VALUES "
            "('owner','note.preflight','project.review.other','run:1','experiment_run','cannot downgrade',"
            "'owner',0,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
        raw.commit()
        raw.execute("PRAGMA foreign_keys=ON")
        connection.execute(sa.text("CREATE TABLE project_review_notes__0022 (stale INTEGER)"))
    before = tuple(engine.connect().execute(sa.text(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
    )).all())
    with pytest.raises(RuntimeError, match="cannot be represented by 0021"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0021")
    with engine.connect() as connection:
        after = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )).all())
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == 1
    assert migrate.schema_version(engine) == "0022"
    assert after == before


def test_revision_0022_upgrade_failure_restores_the_callers_foreign_key_state(tmp_path):
    engine = _at_revision_0020(tmp_path, "0022-fk-state.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0021")
        raw = connection.connection.driver_connection
        raw.commit()
        raw.execute("PRAGMA foreign_keys=OFF")

    failed = False

    def interrupt(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal failed
        if not failed and "CREATE TABLE project_review_notes__0022" in statement:
            failed = True
            raise RuntimeError("injected 0022 rebuild interruption")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected 0022 rebuild interruption"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0022")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == 0
        assert migrate.schema_version(engine) == "0021"


def test_revision_0022_upgrade_refuses_temp_payload_changed_after_copy_before_proof(tmp_path):
    engine = _at_revision_0020(tmp_path, "0022-source-bound-proof.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0021")
    _populated_review_0021(engine)
    corrupted = False

    def corrupt(_conn, cursor, statement, _parameters, _context, _executemany):
        nonlocal corrupted
        if not corrupted and "project_review_notes__0022" in statement and statement.lstrip().upper().startswith("INSERT"):
            corrupted = True
            cursor.connection.execute(
                "UPDATE project_review_notes__0022 SET body='tampered after copy' WHERE rowid=1"
            )

    sa.event.listen(engine, "after_cursor_execute", corrupt)
    try:
        with pytest.raises(RuntimeError, match="source payload proof failed"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0022")
    finally:
        sa.event.remove(engine, "after_cursor_execute", corrupt)
    assert corrupted
    assert migrate.schema_version(engine) == "0021"


def test_revision_0022_downgrade_retry_promotes_a_proven_legacy_temp_after_source_drop(tmp_path):
    engine = _at_revision_0020(tmp_path, "0022-down-proof-retry.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
    interrupted = False

    def interrupt(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal interrupted
        if not interrupted and statement.strip() == "DROP TABLE project_review_notes":
            interrupted = True
            raise RuntimeError("injected 0022 downgrade after source drop")

    sa.event.listen(engine, "after_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected 0022 downgrade after source drop"):
            with engine.begin() as connection:
                command.downgrade(migrate.alembic_config(connection), "0021")
    finally:
        sa.event.remove(engine, "after_cursor_execute", interrupt)
    with engine.connect() as connection:
        assert "project_review_notes" not in sa.inspect(connection).get_table_names()
        assert "project_review_notes__0022" in sa.inspect(connection).get_table_names()
        proof = connection.execute(sa.text(
            "SELECT direction FROM _review_0022_rebuild_proofs WHERE table_name='project_review_notes'"
        )).scalar_one()
        assert proof == "down"
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0021")
    with engine.connect() as connection:
        assert "owner_id" not in {column["name"] for column in sa.inspect(connection).get_columns("project_review_notes")}
    assert migrate.schema_version(engine) == "0021"


@pytest.mark.parametrize(("direction", "start", "target"), (
    ("upgrade", "0021", "0022"),
    ("downgrade", "0022", "0021"),
))
@pytest.mark.parametrize("foreign_keys", (0, 1))
def test_revision_0022_rebuild_failures_restore_foreign_key_mode_in_both_directions(
    tmp_path, direction, start, target, foreign_keys,
):
    engine = _at_revision_0020(tmp_path, f"0022-{direction}-fk-{foreign_keys}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), start)
        raw = connection.connection.driver_connection
        raw.commit()
        raw.execute(f"PRAGMA foreign_keys={foreign_keys}")
    failed = False

    def interrupt(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal failed
        if not failed and "CREATE TABLE project_review_notes__0022" in statement:
            failed = True
            raise RuntimeError(f"injected 0022 {direction} interruption")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match=f"injected 0022 {direction} interruption"):
            with engine.begin() as connection:
                if direction == "upgrade":
                    command.upgrade(migrate.alembic_config(connection), target)
                else:
                    command.downgrade(migrate.alembic_config(connection), target)
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
    assert migrate.schema_version(engine) == start


@pytest.mark.parametrize(("direction", "start", "target"), (
    ("upgrade", "0021", "0022"),
    ("downgrade", "0022", "0021"),
))
@pytest.mark.parametrize("foreign_keys", (0, 1))
def test_revision_0022_successful_rebuild_preserves_foreign_key_mode_in_both_directions(
    tmp_path, direction, start, target, foreign_keys,
):
    """A successful rebuild must return the caller's FK setting, not only failures."""
    engine = _at_revision_0020(tmp_path, f"0022-{direction}-success-fk-{foreign_keys}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), start)
        raw = connection.connection.driver_connection
        raw.commit()
        raw.execute(f"PRAGMA foreign_keys={foreign_keys}")
    with engine.begin() as connection:
        if direction == "upgrade":
            command.upgrade(migrate.alembic_config(connection), target)
        else:
            command.downgrade(migrate.alembic_config(connection), target)
    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
    assert migrate.schema_version(engine) == target


def test_product_object_schema_owns_graph_versions_and_sparse_layouts(tmp_path):
    engine = _build_from_baseline(tmp_path)
    schema = _schema(engine)

    assert migrate.head_revision() == HEAD
    assert set(schema["projects"]["columns"]) == {
        "project_id", "owner_id", "name", "description", "status", "created_at", "updated_at",
    }
    assert set(schema["graph_artifacts"]["columns"]) == {
        "owner_id", "identifier", "project_id", "display_name", "draft_json", "draft_revision",
        "published_revision", "current_version", "created_at", "updated_at",
    }
    assert set(schema["graph_versions"]["columns"]) == {
        "owner_id", "graph_identifier", "version", "artifact_json", "content_address", "visibility", "created_at",
    }
    assert set(schema["ir_graph_layouts"]["columns"]) == {
        "owner_id", "graph_identifier", "graph_version", "revision", "updated_at",
    }
    assert set(schema["ir_graph_layout_positions"]["columns"]) == {
        "owner_id", "graph_identifier", "graph_version", "instance_id", "x", "y",
    }
    assert set(schema["ir_graph_layout_groups"]["columns"]) == {
        "owner_id", "graph_identifier", "graph_version", "identifier", "display_name",
        "x", "y", "width", "height", "collapsed",
    }
    assert set(schema["ir_graph_layout_group_members"]["columns"]) == {
        "owner_id", "graph_identifier", "graph_version", "group_identifier", "instance_id",
    }
    assert set(schema["project_review_notes"]["columns"]) == {
        "owner_id", "note_id", "project_id", "event_id", "event_type", "body", "created_by",
        "revision", "deleted_at", "created_at", "updated_at",
    }
    assert set(schema["project_review_saved_views"]["columns"]) == {
        "owner_id", "view_id", "project_id", "name", "filters_json", "created_by", "revision",
        "deleted_at", "created_at", "updated_at",
    }
    assert set(schema["project_review_snapshots"]["columns"]) == {
        "owner_id", "snapshot_id", "project_id", "label", "capture_key", "manifest_json",
        "content_address", "created_by", "capture_started_at", "capture_completed_at",
    }
    assert any(
        name == "uq_project_review_saved_views_active_name"
        and columns == ("owner_id", "project_id", "name") and unique
        for name, columns, unique in schema["project_review_saved_views"]["indexes"]
    )
    assert any(
        name == "uq_project_review_snapshots_capture_key"
        and columns == ("owner_id", "project_id", "capture_key") and unique
        for name, columns, unique in schema["project_review_snapshots"]["indexes"]
    )
    assert set(schema["ir_graph_layout_orphan_archive"]["columns"]) == {
        "owner_id", "graph_identifier", "graph_version", "revision", "updated_at", "archived_at",
    }
    assert set(schema["ir_graph_layout_position_orphan_archive"]["columns"]) == {
        "owner_id", "graph_identifier", "graph_version", "instance_id", "x", "y",
    }

    graph_version_fks = sa.inspect(engine).get_foreign_keys("ir_graph_layouts")
    assert any(
        fk["referred_table"] == "graph_versions"
        and fk["constrained_columns"] == ["owner_id", "graph_identifier", "graph_version"]
        for fk in graph_version_fks
    )


def test_revision_0014_round_trips_without_rewriting_legacy_rows(tmp_path):
    """Lifecycle links are additive: 0014 must leave old journal facts untouched."""
    engine = _fresh_engine(tmp_path, "execution-lifecycle-round-trip.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0013")
        connection.execute(sa.text(
            "INSERT INTO order_journal "
            "(deployment_id, order_id, tradingsymbol, instrument_key, side, kind, intent, "
            "qty, status, filled_qty, avg_price, placed_at) "
            "VALUES (1, 'legacy-order', 'RELIANCE', 'NSE_EQ|INE002A01018', 'BUY', "
            "'options', 'ENTRY', 1, 'WORKING', 0, 0.0, '2026-08-09 09:15:00')"
        ))
        command.upgrade(migrate.alembic_config(connection), "0014")

    inspector = sa.inspect(engine)
    assert migrate.schema_version(engine) == "0014"
    assert {"execution_intents", "execution_order_events"} <= set(
        inspector.get_table_names())
    assert {column["name"] for column in inspector.get_columns("execution_intents")} == {
        "client_intent_id", "deployment_id",
        "broker", "account_scope",
        "connection_scope",
        "broker_tag", "intent", "instrument_key", "tradingsymbol", "exchange", "side",
        "product", "order_type", "requested_qty", "limit_price", "decision_price",
        "signal_at", "strategy_key", "strategy_version", "context_json", "created_at",
    }
    assert {column["name"] for column in inspector.get_columns("execution_order_events")} == {
        "id", "client_intent_id", "source",
        "source_event_id", "kind",
        "broker_order_id",
        "broker_status", "cumulative_filled_qty", "avg_price", "observed_at", "payload_json",
        "anomaly",
    }
    for table in ("positions", "trades"):
        assert "entry_intent_id" in {column["name"] for column in inspector.get_columns(table)}
        assert any(
            index["name"] == f"ix_{table}_entry_intent_id"
            and index["column_names"] == ["entry_intent_id"]
            for index in inspector.get_indexes(table)
        )
        with engine.connect() as connection:
            foreign_keys = connection.execute(sa.text(
                f"PRAGMA foreign_key_list({table})"
            )).mappings().all()
        assert any(
            foreign_key["from"] == "entry_intent_id"
            and foreign_key["table"] == "execution_intents"
            and foreign_key["to"] == "client_intent_id"
            and foreign_key["on_delete"] == "RESTRICT"
            for foreign_key in foreign_keys
        )
    assert any(
        constraint["name"] == "uq_execution_event_source_identity"
        and constraint["column_names"] == ["client_intent_id", "source", "source_event_id"]
        for constraint in inspector.get_unique_constraints("execution_order_events")
    )
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT order_id, status, filled_qty FROM order_journal "
            "WHERE order_id = 'legacy-order'"
        )).one() == ("legacy-order", "WORKING", 0)

    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO execution_intents "
            "(client_intent_id, deployment_id, broker, account_scope, connection_scope, "
            " broker_tag, intent, instrument_key, tradingsymbol, exchange, side, order_type, "
            " requested_qty, created_at) "
            "VALUES ('entry-000000000000000000000002', 1, 'upstox', 'account.default', "
            "'connection.default', 'entry-000000000000002', 'ENTRY', "
            "'NSE_EQ|INE002A01018', 'RELIANCE', 'NSE', 'BUY', 'MARKET', 1, "
            "'2026-08-09 09:15:00')"
        ))
        connection.execute(sa.text(
            "INSERT INTO execution_order_events "
            "(client_intent_id, source, source_event_id, kind, observed_at) "
            "VALUES ('entry-000000000000000000000002', 'broker', 'event-1', "
            "'INTENT_CREATED', '2026-08-09 09:15:00')"
        ))
        connection.execute(sa.text(
            "INSERT INTO positions "
            "(deployment_id, entry_intent_id, instrument_key, direction, option_type, "
            " tradingsymbol, exchange, segment, strike, expiry, lot_size, qty, entry_premium, "
            " entry_charges, entry_cost, entry_spot, entry_time, entry_reason, stop_price, "
            " target_price, last_premium, last_spot, high_water_premium, mfe, mae, "
            " reinforcement_count, held_overnight, overnight_pnl, session_close_premium, "
            " manual_target, no_take_profit, mode) "
            "VALUES (1, 'entry-000000000000000000000002', 'NSE_EQ|INE002A01018', 'LONG', "
            "'CE', 'RELIANCE', 'NSE', 'options', 1.0, '2026-08-28', 1, 1, 10.0, 0.0, "
            "10.0, 100.0, '2026-08-09 09:15:00', '', 5.0, 15.0, 10.0, 100.0, 10.0, "
            "0.0, 0.0, 0, 0, 0.0, 0.0, 0, 0, 'paper')"
        ))
        for statement in (
            "UPDATE execution_order_events SET kind = 'CHANGED' WHERE id = 1",
            "DELETE FROM execution_order_events WHERE id = 1",
        ):
            with pytest.raises(IntegrityError, match="execution_order_events are immutable"):
                connection.execute(sa.text(statement))

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0013")
    inspector = sa.inspect(engine)
    assert migrate.schema_version(engine) == "0013"
    assert "execution_intents" not in inspector.get_table_names()
    assert "execution_order_events" not in inspector.get_table_names()
    assert "entry_intent_id" not in {column["name"] for column in inspector.get_columns("positions")}
    assert "entry_intent_id" not in {column["name"] for column in inspector.get_columns("trades")}

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0014")
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT order_id, status, filled_qty FROM order_journal "
            "WHERE order_id = 'legacy-order'"
        )).one() == ("legacy-order", "WORKING", 0)


def test_revision_0019_preserves_every_account_money_payload_and_adds_real_scope(tmp_path):
    """0019 copies complete rows, not selected fields, and creates enforceable account scope."""
    engine = _fresh_engine(tmp_path, "money-account-scope.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0018")
        connection.execute(sa.text(
            "UPDATE deployments SET notes='deployment-marker', created_at='2026-08-11 09:00:01', "
            "updated_at='2026-08-11 09:00:02' WHERE id=1"))
        connection.execute(sa.text(
            "INSERT INTO execution_intents (client_intent_id,deployment_id,broker,account_scope,"
            "connection_scope,broker_tag,intent,instrument_key,tradingsymbol,exchange,side,product,"
            "order_type,requested_qty,limit_price,decision_price,signal_at,strategy_key,"
            "strategy_version,context_json,created_at,owner_id) VALUES "
            "('intent-marker',1,'kite','external-marker','kite:marker','tag-marker','ENTRY',"
            "'RELIANCE','RELIANCE','NSE','BUY','MIS','LIMIT',7,101.25,100.5,"
            "'2026-08-11 09:01:01','s','v','{}','2026-08-11 09:01:02','owner')"))
        connection.execute(sa.text(
            "INSERT INTO execution_order_events (id,client_intent_id,source,source_event_id,kind,"
            "broker_order_id,broker_status,cumulative_filled_qty,avg_price,observed_at,payload_json,"
            "anomaly,owner_id) VALUES (91,'intent-marker','broker','event-marker','ACKNOWLEDGED',"
            "'order-marker','OPEN',3,101.5,'2026-08-11 09:02:01','{}',"
            "'event-anomaly','owner')"))
        connection.execute(sa.text(
            "INSERT INTO positions (id,instrument_key,direction,option_type,tradingsymbol,exchange,"
            "segment,strategy_key,strike,expiry,lot_size,qty,entry_premium,entry_charges,entry_cost,"
            "entry_spot,entry_time,entry_reason,stop_price,target_price,last_premium,last_spot,"
            "high_water_premium,mfe,mae,reinforcement_count,held_overnight,overnight_pnl,"
            "session_close_premium,manual_target,no_take_profit,mode,deployment_id,strategy_version,"
            "entry_intent_id,owner_id) VALUES (92,'RELIANCE','LONG','EQ','RELIANCE','NSE',"
            "'equity_intraday','s',0,'2026-08-28',7,7,100.5,1.25,704.75,100.5,"
            "'2026-08-11 09:03:01','position-marker',90,120,101,101,102,5,-2,1,0,0,0,0,0,"
            "'live',1,'v','intent-marker','owner')"))
        connection.execute(sa.text(
            "INSERT INTO trades (id,instrument_key,direction,option_type,tradingsymbol,exchange,"
            "segment,strategy_key,strike,expiry,qty,entry_premium,entry_cost,entry_spot,entry_time,"
            "exit_premium,exit_charges,exit_spot,exit_time,exit_reason,gross_pnl,charges_total,"
            "net_pnl,return_pct,holding_minutes,win,held_overnight,overnight_pnl,intraday_pnl,"
            "reinforcements,mode,exit_price_estimated,mfe,mae,build_sha,deployment_id,"
            "strategy_version,entry_intent_id,owner_id) VALUES (93,'RELIANCE','LONG','EQ',"
            "'RELIANCE','NSE','equity_intraday','s',0,'2026-08-28',7,100.5,704.75,100.5,"
            "'2026-08-11 09:03:01',103.5,1.5,103.5,'2026-08-11 09:08:01','trade-marker',"
            "21,2.75,18.25,2.5,5,1,0,0,18.25,1,'live',0,5,-2,'sha-marker',1,'v',"
            "'intent-marker','owner')"))
        connection.execute(sa.text(
            "INSERT INTO equity_snapshots (id,time,equity,cash,invested,realized_pnl,open_count,"
            "segment,strategy_key,deployment_id,book,owner_id) VALUES (94,'2026-08-11 09:09:01',"
            "1234.5,1000.5,234,18.25,1,'equity_intraday','s',1,'live','owner')"))
        connection.execute(sa.text(
            "INSERT INTO order_journal (id,order_id,tradingsymbol,instrument_key,side,kind,intent,"
            "qty,context_json,status,resolution,filled_qty,avg_price,placed_at,deployment_id,owner_id)"
            " VALUES (95,'order-marker','RELIANCE','RELIANCE','BUY','equity','ENTRY',7,"
            "'{}','TERMINAL','FILLED',7,101.5,'2026-08-11 09:10:01',1,'owner')"))
        connection.execute(sa.text(
            "INSERT INTO signal_events (id,time,instrument_key,signal,z,slope,close,acted,note,"
            "deployment_id,owner_id) VALUES (96,'2026-08-11 09:11:01','RELIANCE','LONG_ENTRY',"
            "1.2,0.3,100.5,1,'signal-marker',1,'owner')"))
        connection.execute(sa.text(
            "INSERT INTO broker_connections (id,owner_id,broker,scope,label,capabilities_json,"
            "credential_ciphertext,credential_key_id,status,created_at,updated_at,"
            "last_authenticated_at,revoked_at) VALUES (97,'owner','kite','kite:marker',"
            "'connection-marker','[\"orders\"]','cipher-marker','key-marker','active',"
            "'2026-08-11 09:12:01','2026-08-11 09:12:02','2026-08-11 09:12:03',NULL)"))
        connection.execute(sa.text(
            "INSERT INTO projects (project_id,name,description,status,created_at,updated_at) VALUES "
            "('project-marker','Project','marker','active','2026-08-11 09:13:01',"
            "'2026-08-11 09:13:02')"))
        connection.execute(sa.text(
            "INSERT INTO graph_artifacts (identifier,project_id,display_name,draft_json,"
            "draft_revision,published_revision,current_version,created_at,updated_at) VALUES "
            "('graph-marker','project-marker','Graph','{}',1,1,1,'2026-08-11 09:13:03',"
            "'2026-08-11 09:13:04')"))
        connection.execute(sa.text(
            "INSERT INTO graph_versions (graph_identifier,version,artifact_json,content_address,"
            "created_at) VALUES ('graph-marker',1,json_object('identifier','graph-marker',"
            "'version',1),'sha256:graph-marker','2026-08-11 09:13:05')"))
        connection.execute(sa.text(
            "INSERT INTO ir_paper_deployments (id,project_id,graph_identifier,graph_version,"
            "graph_content_address,evidence_run_id,evidence_candidate_id,evidence_content_address,"
            "evidence_verified_at,deployment_id,instrument_key,interval,strategy_key,"
            "rollback_strategy_key,runtime_source,execution_mode,authority,admission_ok,"
            "admission_reason,state,revision,note,created_at,updated_at,owner_id) VALUES "
            "(98,'project-marker','graph-marker',1,'sha256:graph-marker',1,2,'sha256:graph-marker',"
            "'2026-08-11 09:14:01',1,'RELIANCE','5minute','s',NULL,'ir_graph','paper',"
            "'authoritative',1,'ok','staged',3,'paper-marker','2026-08-11 09:14:02',"
            "'2026-08-11 09:14:03','owner')"))
        connection.execute(sa.text(
            "INSERT INTO ir_shadow_deployments (id,project_id,graph_identifier,graph_version,"
            "graph_content_address,evidence_run_id,evidence_candidate_id,evidence_content_address,"
            "evidence_verified_at,deployment_id,instrument_key,interval,strategy_key,runtime_source,"
            "execution_mode,authority,admission_ok,admission_reason,state,revision,note,created_at,"
            "updated_at,owner_id) VALUES (99,'project-marker','graph-marker',1,"
            "'sha256:graph-marker',1,2,'sha256:graph-marker','2026-08-11 09:15:01',1,"
            "'RELIANCE','15minute','s','ir_graph','shadow','non_authoritative',1,'ok','staged',"
            "4,'shadow-marker','2026-08-11 09:15:02','2026-08-11 09:15:03','owner')"))
        connection.execute(sa.text(
            "INSERT INTO ir_shadow_divergences (id,observed_at,bar_time,instrument_key,"
            "authoritative_strategy_key,shadow_strategy_key,graph_address,authoritative_json,"
            "ir_json,warmup_state,declared_warmup,frame_id,frame_bars,frame_first_ts,frame_last_ts,"
            "reason,detail,eval_ms,market_open,owner_id) VALUES (100,'2026-08-11 09:16:01',"
            "'2026-08-11 09:15:00','RELIANCE','a','s','sha256:graph-marker','{}','{}','settled',"
            "10,'frame-marker',20,'2026-08-11 08:00:00','2026-08-11 09:15:00','VALUE',"
            "'divergence-marker',1.25,1,'owner')"))

        tables = {
            "deployments": 1, "execution_intents": "intent-marker",
            "execution_order_events": 91, "positions": 92, "trades": 93,
            "equity_snapshots": 94, "order_journal": 95, "signal_events": 96,
            "broker_connections": 97, "ir_paper_deployments": 98,
            "ir_shadow_deployments": 99, "ir_shadow_divergences": 100,
        }
        before = {}
        for table, key in tables.items():
            pk = "client_intent_id" if table == "execution_intents" else "id"
            before[table] = dict(connection.execute(sa.text(
                f"SELECT * FROM {table} WHERE {pk}=:key"), {"key": key}).mappings().one())

        command.upgrade(migrate.alembic_config(connection), HEAD)

        for table, key in tables.items():
            pk = "client_intent_id" if table == "execution_intents" else "id"
            after = dict(connection.execute(sa.text(
                f"SELECT * FROM {table} WHERE {pk}=:key"), {"key": key}).mappings().one())
            for column, value in before[table].items():
                if table == "deployments" and column == "account_id":
                    continue
                assert after[column] == value, f"0019 changed {table}.{column}"
            assert after["broker_account_id"] == "account.default"

    inspector = sa.inspect(engine)
    account_tables = (
        "positions", "trades", "equity_snapshots", "order_journal", "signal_events",
        "execution_intents", "execution_order_events", "broker_connections",
        "ir_paper_deployments", "ir_shadow_deployments", "ir_shadow_divergences",
    )
    for table in account_tables:
        column = next(c for c in inspector.get_columns(table)
                      if c["name"] == "broker_account_id")
        assert column["nullable"] is False
        assert any(
            fk["constrained_columns"] == ["broker_account_id"]
            and fk["referred_table"] == "broker_accounts"
            for fk in inspector.get_foreign_keys(table)
        )
        assert any(
            index["column_names"] == ["owner_id", "broker_account_id"]
            for index in inspector.get_indexes(table)
        )

    assert "account_id" not in {c["name"] for c in inspector.get_columns("deployments")}
    assert any(
        set(constraint["column_names"]) == {"owner_id", "name"}
        for constraint in inspector.get_unique_constraints("deployments")
    )


def test_revision_0019_removes_legacy_defaults_from_every_tenant_scope(tmp_path):
    """Defaults backfill old rows once; a new write must name its tenant explicitly."""
    engine = _build_from_baseline(tmp_path)
    inspector = sa.inspect(engine)
    scope_columns = {
        "deployments": ("owner_id", "broker_account_id"),
        "instrument_state": ("owner_id",),
        "capital_state": ("broker_account_id",),
        "daily_account_snapshot": ("broker_account_id",),
        **{table: ("owner_id", "broker_account_id") for table in (
            "positions", "trades", "equity_snapshots", "order_journal", "signal_events",
            "execution_intents", "execution_order_events", "broker_connections",
            "ir_paper_deployments", "ir_shadow_deployments", "ir_shadow_divergences",
        )},
    }
    for table, columns in scope_columns.items():
        actual = {column["name"]: column.get("default")
                  for column in inspector.get_columns(table)}
        for column in columns:
            assert actual[column] is None, f"{table}.{column} retains a legacy server default"


def test_revision_0019_refuses_lossy_tenant_name_downgrade(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0019-test_revision_0019_refuses_lossy_tenant_name_downgrade.db", "0019")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO organizations VALUES ('org-b','B','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(sa.text(
            "INSERT INTO broker_accounts (broker_account_id,owner_id,broker,external_account_id,"
            "display_name,status,created_at,updated_at) VALUES ('account.b','org-b','kite','b','B',"
            "'active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(sa.text(
            "INSERT INTO deployments (owner_id,broker_account_id,name,created_at,updated_at) "
            "VALUES ('org-b','account.b','default',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        with pytest.raises(RuntimeError, match="lossy"):
            command.downgrade(migrate.alembic_config(connection), "0018")


def test_revision_0019_retry_after_interrupted_positions_rebuild_preserves_rows_and_guards(tmp_path):
    """SQLite may retain DDL before an upgrade error; retrying must reach head safely."""
    engine = _fresh_engine(tmp_path, "0019-interrupted-retry.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_positions_temp(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and "_alembic_tmp_positions" in statement:
            failed = True
            raise RuntimeError("injected interruption after positions temp creation")

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0018")
        connection.execute(sa.text(
            "UPDATE deployments SET notes='survives-retry' WHERE id=1"))
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.upgrade(migrate.alembic_config(connection), HEAD)
        command.upgrade(migrate.alembic_config(connection), HEAD)

        assert connection.execute(sa.text(
            "SELECT notes, broker_account_id FROM deployments WHERE id=1")).one() == (
                "survives-retry", "account.default")
        with pytest.raises(IntegrityError):
            connection.execute(sa.text(
                "INSERT INTO execution_order_events "
                "(client_intent_id, source, source_event_id, kind, observed_at) "
                "VALUES ('missing', 'retry', 'event', 'ACK', CURRENT_TIMESTAMP)"))

    assert failed
    assert migrate.schema_version(engine) == HEAD
    with engine.connect() as connection:
        inspector = sa.inspect(connection)
        assert "_alembic_tmp_positions" not in inspector.get_table_names()
        assert any(index["column_names"] == ["owner_id", "broker_account_id"]
                   for index in inspector.get_indexes("positions"))
        assert any(fk["constrained_columns"] == ["broker_account_id"]
                   and fk["referred_table"] == "broker_accounts"
                   for fk in inspector.get_foreign_keys("positions"))
        triggers = {name for (name,) in connection.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ))}
        assert {"execution_order_events_refuse_update",
                "execution_order_events_refuse_delete"} <= triggers


def test_revision_0019_retry_after_deployments_rename_interruption_restores_indexes(tmp_path):
    """A DROP-before-RENAME interruption leaves only the custom temp table behind."""
    engine = _fresh_engine(tmp_path, "0019-deployments-rename-retry.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_deployments_rename(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and "ALTER TABLE deployments__0019 RENAME TO deployments" in statement:
            failed = True
            raise RuntimeError("injected interruption after deployments rename")

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0018")
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.upgrade(migrate.alembic_config(connection), HEAD)
        command.upgrade(migrate.alembic_config(connection), HEAD)

    inspector = sa.inspect(engine)
    assert failed
    assert migrate.schema_version(engine) == HEAD
    assert "deployments__0019" not in inspector.get_table_names()
    assert any(index["column_names"] == ["owner_id"]
               for index in inspector.get_indexes("deployments"))
    assert any(index["column_names"] == ["owner_id", "broker_account_id"]
               for index in inspector.get_indexes("deployments"))
    assert any(set(constraint["column_names"]) == {"owner_id", "name"}
               for constraint in inspector.get_unique_constraints("deployments"))


def test_revision_0019_discards_stale_custom_deployments_temp_before_retry(tmp_path):
    engine = _fresh_engine(tmp_path, "0019-deployments-temp-retry.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_deployments_temp(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and "CREATE TABLE deployments__0019" in statement:
            failed = True
            raise RuntimeError("injected interruption after deployments temp creation")

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0018")
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.upgrade(migrate.alembic_config(connection), HEAD)
        command.upgrade(migrate.alembic_config(connection), HEAD)

    assert failed
    assert migrate.schema_version(engine) == HEAD
    assert "deployments__0019" not in sa.inspect(engine).get_table_names()


def test_revision_0019_retry_after_positions_rename_restores_account_index(tmp_path):
    """Batch index creation happens after the table rename and must be recoverable."""
    engine = _fresh_engine(tmp_path, "0019-positions-rename-retry.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_positions_rename(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and "ALTER TABLE _alembic_tmp_positions RENAME TO positions" in statement:
            failed = True
            raise RuntimeError("injected interruption after positions rename")

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0018")
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.upgrade(migrate.alembic_config(connection), HEAD)
        command.upgrade(migrate.alembic_config(connection), HEAD)

    assert failed
    assert migrate.schema_version(engine) == HEAD
    inspector = sa.inspect(engine)
    assert any(index["column_names"] == ["owner_id", "broker_account_id"]
               for index in inspector.get_indexes("positions"))
    assert any(fk["constrained_columns"] == ["broker_account_id"]
               for fk in inspector.get_foreign_keys("positions"))


def _table_contract(engine, table: str) -> dict:
    """The complete SQLite-visible contract a retry must reproduce exactly."""
    inspector = sa.inspect(engine)
    with engine.connect() as connection:
        indexes = connection.execute(sa.text(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='index' AND tbl_name=:table AND sql IS NOT NULL ORDER BY name"
        ), {"table": table}).all()
    return {
        "columns": [(column["name"], str(column["type"]), bool(column["nullable"]),
                     str(column.get("default")))
                    for column in inspector.get_columns(table)],
        # Position is part of a composite identity.  Sorting this away lets a
        # migration silently reverse an otherwise identical key.
        "primary_key": tuple(inspector.get_pk_constraint(table)["constrained_columns"]),
        "foreign_keys": sorted((tuple(fk["constrained_columns"]), fk["referred_table"],
                                tuple(fk["referred_columns"]), fk.get("name"))
                               for fk in inspector.get_foreign_keys(table)),
        "unique": sorted((tuple(item["column_names"]), item.get("name"))
                         for item in inspector.get_unique_constraints(table)),
        "indexes": indexes,
    }


def test_revision_0020_downgrade_retry_after_graph_versions_temp_creation_restores_fk(tmp_path):
    """A failed 0020 rollback must leave enforcement on and retry from its temp table."""
    engine = _fresh_engine(tmp_path, "0020-graph-versions-downgrade-retry.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_graph_versions_temp_create(
            _conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and "CREATE TABLE graph_versions__0019" in statement:
            failed = True
            raise RuntimeError("injected interruption after graph_versions temp creation")

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0020")
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.downgrade(migrate.alembic_config(connection), "0019")

    with engine.connect() as connection:
        names = set(sa.inspect(connection).get_table_names())
        assert "graph_versions" in names
        assert "graph_versions__0019" in names
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == 1

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0019")

    assert failed
    assert migrate.schema_version(engine) == "0019"


def test_revision_0020_downgrade_retry_after_graph_versions_temp_creation_discards_stale_temp(tmp_path):
    """The source table remains authoritative when a rollback stops after CREATE."""
    engine = _fresh_engine(tmp_path, "0020-graph-versions-downgrade-create-retry.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_graph_versions_temp_create(
            _conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and "CREATE TABLE graph_versions__0019" in statement:
            failed = True
            raise RuntimeError("injected interruption after graph_versions temp creation")

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0020")
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.downgrade(migrate.alembic_config(connection), "0019")

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0019")

    assert failed
    assert migrate.schema_version(engine) == "0019"


def test_revision_0020_downgrade_retry_after_projects_temp_creation_discards_stale_temp(tmp_path):
    """The second rollback rebuild also discards its stale temp before retrying."""
    engine = _fresh_engine(tmp_path, "0020-projects-downgrade-create-retry.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_projects_temp_create(
            _conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and "CREATE TABLE projects__0019" in statement:
            failed = True
            raise RuntimeError("injected interruption after projects temp creation")

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0020")
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.downgrade(migrate.alembic_config(connection), "0019")

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0019")

    assert failed
    assert migrate.schema_version(engine) == "0019"


def _revision_0020_contract(engine, table: str) -> dict:
    """SQLite-visible migration contract; do not weaken the older retry helper."""
    inspector = sa.inspect(engine)
    with engine.connect() as connection:
        table_sql = connection.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"
        ), {"table": table}).scalar_one()
        indexes = connection.execute(sa.text(
            "SELECT name, sql FROM sqlite_master WHERE type='index' "
            "AND tbl_name=:table AND sql IS NOT NULL ORDER BY name"
        ), {"table": table}).all()
        triggers = connection.execute(sa.text(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger' "
            "AND tbl_name=:table ORDER BY name"
        ), {"table": table}).all()
    foreign_keys = []
    for match in re.finditer(
            r"(?:CONSTRAINT\s+(?P<name>\w+)\s+)?FOREIGN\s+KEY\s*\((?P<columns>[^)]*)\)"
            r"\s+REFERENCES\s+(?P<target>\w+)\s*\((?P<target_columns>[^)]*)\)"
            r"(?:\s+ON\s+DELETE\s+(?P<delete>\w+))?",
            table_sql, flags=re.I | re.S):
        foreign_keys.append((
            tuple(part.strip() for part in match.group("columns").split(",")),
            match.group("target"),
            tuple(part.strip() for part in match.group("target_columns").split(",")),
            match.group("name"),
            match.group("delete"),
        ))
    return {
        "columns": [(column["name"], str(column["type"]), bool(column["nullable"]),
                     str(column.get("default")))
                    for column in inspector.get_columns(table)],
        "primary_key": tuple(inspector.get_pk_constraint(table)["constrained_columns"]),
        "foreign_keys": sorted(foreign_keys),
        "unique": sorted((tuple(item["column_names"]), item.get("name"))
                         for item in inspector.get_unique_constraints(table)),
        "indexes": indexes,
        "checks": sorted((item.get("name"), item["sqltext"])
                         for item in inspector.get_check_constraints(table)),
        "triggers": triggers,
    }


def _at_revision_0019(tmp_path, name: str):
    engine = _fresh_engine(tmp_path, name)
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0019")
    return engine


def _insert_legacy_project_graph(connection) -> tuple:
    project = (
        "project.legacy", "Legacy Project", "legacy payload", "archived",
        "2026-08-11 09:10:11", "2026-08-11 12:13:14",
    )
    graph = (
        "graph.legacy", "project.legacy", "Legacy graph",
        '{"identifier":"graph.legacy","version":1}', 1, 1, 1,
        "2026-08-11 10:11:12", "2026-08-11 12:13:14",
    )
    version = (
        "graph.legacy", 1, '{"identifier":"graph.legacy","version":1}',
        "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "2026-08-11 12:13:14",
    )
    connection.execute(sa.text(
        "INSERT INTO projects "
        "(project_id,name,description,status,created_at,updated_at) "
        "VALUES (:project_id,:name,:description,:status,:created_at,:updated_at)"
    ), dict(zip(("project_id", "name", "description", "status", "created_at", "updated_at"), project)))
    connection.execute(sa.text(
        "INSERT INTO graph_artifacts "
        "(identifier,project_id,display_name,draft_json,draft_revision,published_revision,"
        "current_version,created_at,updated_at) VALUES "
        "(:identifier,:project_id,:display_name,:draft_json,:draft_revision,"
        ":published_revision,:current_version,:created_at,:updated_at)"
    ), dict(zip(("identifier", "project_id", "display_name", "draft_json", "draft_revision",
                 "published_revision", "current_version", "created_at", "updated_at"), graph)))
    connection.execute(sa.text(
        "INSERT INTO graph_versions "
        "(graph_identifier,version,artifact_json,content_address,created_at) VALUES "
        "(:graph_identifier,:version,:artifact_json,:content_address,:created_at)"
    ), dict(zip(("graph_identifier", "version", "artifact_json", "content_address", "created_at"), version)))
    return project, graph, version


def test_revision_0021_upgrade_backfills_owner_for_every_graph_and_layout_identity(tmp_path):
    """A real 0020 lineage needs owner-bearing keys before identifiers can overlap."""
    engine = _at_revision_0019(tmp_path, "0021-owner-identity-upgrade.db")
    with engine.begin() as connection:
        project, graph, version = _insert_legacy_project_graph(connection)
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layouts "
            "(graph_identifier,graph_version,revision,updated_at) VALUES "
            "('graph.legacy',1,7,'2026-08-11 12:14:15')"))
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_positions "
            "(graph_identifier,graph_version,instance_id,x,y) VALUES "
            "('graph.legacy',1,'node.legacy',12.5,24.5)"))
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_groups "
            "(graph_identifier,graph_version,identifier,display_name,x,y,width,height,collapsed) "
            "VALUES ('graph.legacy',1,'group.legacy','Legacy',1.0,2.0,3.0,4.0,1)"))
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_group_members "
            "(graph_identifier,graph_version,group_identifier,instance_id) VALUES "
            "('graph.legacy',1,'group.legacy','node.legacy')"))
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_orphan_archive "
            "(graph_identifier,graph_version,revision,updated_at,archived_at) VALUES "
            "('graph.orphan',3,8,'2026-08-11 12:15:16','2026-08-11 12:16:17')"))
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_position_orphan_archive "
            "(graph_identifier,graph_version,instance_id,x,y) VALUES "
            "('graph.orphan',3,'node.orphan',6.0,7.0)"))
        command.upgrade(migrate.alembic_config(connection), HEAD)

    inspector = sa.inspect(engine)
    owner_scoped = (
        "graph_artifacts", "graph_versions", "ir_graph_layouts",
        "ir_graph_layout_positions", "ir_graph_layout_groups",
        "ir_graph_layout_group_members", "ir_graph_layout_orphan_archive",
        "ir_graph_layout_position_orphan_archive",
    )
    for table in owner_scoped:
        assert "owner_id" in {
            column["name"] for column in inspector.get_columns(table)
        }, f"0021 must backfill an owner identity on {table}"

    # These are deliberately captured before the assertion surface grows into complete
    # 0021 preservation/parity coverage: the migration must retain canonical bytes and
    # layout values while adding provenance, never reserialise them.
    assert project[0] == "project.legacy"
    assert graph[3] == '{"identifier":"graph.legacy","version":1}'
    assert version[2] == graph[3]


def _revision_0021_contract(engine, table: str) -> dict:
    """The visible 0021 contract, including ordered columns and executable DDL."""
    return _revision_0020_contract(engine, table)


def _semantic_contract(contract: dict) -> dict:
    """SQLite's reflection preserves DDL whitespace; it is not schema meaning."""
    def compact(sql: str) -> str:
        return "".join(sql.split())

    normalized = dict(contract)
    normalized["checks"] = [(name, compact(sql)) for name, sql in contract["checks"]]
    normalized["indexes"] = [(name, compact(sql)) for name, sql in contract["indexes"]]
    normalized["triggers"] = [(name, compact(sql)) for name, sql in contract["triggers"]]
    return normalized


def _at_revision_0020(tmp_path, name: str):
    engine = _at_revision_0019(tmp_path, name)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0020")
    return engine


def _insert_populated_0020_graph_lineage(connection) -> dict[str, tuple[tuple[object, ...], ...]]:
    """Create literal 0020 values whose preservation a rebuild cannot fake."""
    stamp = "2026-08-12 09:10:11"
    graph_json = '{"identifier":"graph.legacy","version":1,"nodes":["n1"]}'
    address = "sha256:" + "c" * 64
    connection.execute(sa.text(
        "INSERT INTO broker_accounts VALUES ('account.legacy','owner','kite','external','Legacy','active',:t,:t)"
    ), {"t": stamp})
    connection.execute(sa.text(
        "INSERT INTO deployments (id,name,strategy_key,strategy_version,broker_account_id,universe_mode,params_json,status,armed,notes,created_at,updated_at,owner_id) "
        "VALUES (701,'legacy-deployment','legacy','v1','account.legacy','legacy','{}','active',0,'provenance',:t,:t,'owner')"
    ), {"t": stamp})
    connection.execute(sa.text(
        "INSERT INTO projects VALUES ('project.legacy','owner','Legacy Project','legacy payload','archived',:t,'2026-08-12 09:10:12')"
    ), {"t": stamp})
    connection.execute(sa.text(
        "INSERT INTO graph_artifacts VALUES ('graph.legacy','project.legacy','Exact legacy graph',:json,7,1,1,:t,'2026-08-12 09:10:12')"
    ), {"json": graph_json, "t": stamp})
    connection.execute(sa.text(
        "INSERT INTO graph_versions VALUES ('graph.legacy',1,:json,:address,'PRIVATE','2026-08-12 09:10:13')"
    ), {"json": graph_json, "address": address})
    connection.execute(sa.text("INSERT INTO ir_graph_layouts VALUES ('graph.legacy',1,9,'2026-08-12 09:10:14')"))
    connection.execute(sa.text("INSERT INTO ir_graph_layout_positions VALUES ('graph.legacy',1,'n1',12.25,24.5)"))
    connection.execute(sa.text(
        "INSERT INTO ir_graph_layout_groups VALUES ('graph.legacy',1,'group.1','Exact group',1.5,2.5,30.5,40.5,1)"))
    connection.execute(sa.text(
        "INSERT INTO ir_graph_layout_group_members VALUES ('graph.legacy',1,'group.1','n1')"))
    connection.execute(sa.text(
        "INSERT INTO ir_graph_layout_orphan_archive VALUES ('orphan.graph',3,11,'2026-08-12 09:10:15','2026-08-12 09:10:16')"))
    connection.execute(sa.text(
        "INSERT INTO ir_graph_layout_position_orphan_archive VALUES ('orphan.graph',3,'gone',6.25,7.75)"))
    for table, mode, authority, state, extra in (
        ("ir_paper_deployments", "paper", "authoritative", "paper_active", ",rollback_strategy_key"),
        ("ir_shadow_deployments", "shadow", "non_authoritative", "shadow_active", ""),
    ):
        columns = (
            "id,project_id,graph_identifier,graph_version,graph_content_address,evidence_run_id,"
            "evidence_candidate_id,evidence_content_address,evidence_verified_at,deployment_id,instrument_key,"
            "interval,strategy_key" + extra + ",runtime_source,execution_mode,authority,admission_ok,"
            "admission_reason,state,revision,note,created_at,updated_at,owner_id,broker_account_id"
        )
        values = (
            ":id,'project.legacy','graph.legacy',1,:address,91,92,'sha256:evidence',:t,701,"
            "'NSE:ABC','1m','graph.strategy'" + (",'rollback'" if extra else "") +
            ",'ir_graph',:mode,:authority,1,'accepted',:state,6,'exact money provenance',:t,:t,'owner','account.legacy'"
        )
        connection.execute(sa.text(f"INSERT INTO {table} ({columns}) VALUES ({values})"), {
            "id": 801 if mode == "paper" else 802, "address": address, "t": stamp,
            "mode": mode, "authority": authority, "state": state,
        })
    tables = AFFECTED_0021_TABLES
    return {
        table: tuple(connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all())
        for table in tables
    }


AFFECTED_0021_TABLES = (
    "projects",
    "graph_artifacts",
    "graph_versions",
    "ir_graph_layouts",
    "ir_graph_layout_positions",
    "ir_graph_layout_groups",
    "ir_graph_layout_group_members",
    "ir_graph_layout_orphan_archive",
    "ir_graph_layout_position_orphan_archive",
    "ir_paper_deployments",
    "ir_shadow_deployments",
)


def test_revision_0021_fresh_and_upgraded_contracts_match_for_every_affected_table(tmp_path):
    """Fresh and historical 0020 upgrades expose the same complete 0021 schema."""
    fresh = _build_from_models(tmp_path)
    upgraded = _at_revision_0020(tmp_path, "0021-complete-contract-upgrade.db")
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), HEAD)

    for table in AFFECTED_0021_TABLES:
        assert _semantic_contract(_revision_0021_contract(upgraded, table)) == _semantic_contract(
            _revision_0021_contract(fresh, table)
        )


def test_revision_0021_preserves_a_populated_0020_graph_layout_and_money_lineage(tmp_path):
    """0021 adds ownership without altering authored bytes or MONEY provenance."""
    engine = _at_revision_0020(tmp_path, "0021-populated-preservation.db")
    with engine.begin() as connection:
        before = _insert_populated_0020_graph_lineage(connection)
        command.upgrade(migrate.alembic_config(connection), HEAD)
        after = {
            table: tuple(connection.execute(sa.text(f"SELECT * FROM {table} WHERE " + (
                "project_id='project.legacy'" if table == "projects" else
                "identifier='graph.legacy'" if table == "graph_artifacts" else
                "graph_identifier IN ('graph.legacy','orphan.graph')" if table.startswith("ir_graph_layout") else
                "graph_identifier='graph.legacy'" if table == "graph_versions" else
                "id IN (801,802)"
            ) + " ORDER BY rowid")).all())
            for table in AFFECTED_0021_TABLES
        }

    assert after["projects"] == (before["projects"][-1],)
    for table in ("graph_artifacts", "graph_versions", "ir_graph_layouts",
                  "ir_graph_layout_positions", "ir_graph_layout_groups", "ir_graph_layout_group_members",
                  "ir_graph_layout_orphan_archive", "ir_graph_layout_position_orphan_archive"):
        assert all(row[0] == "owner" for row in after[table])
        assert tuple(row[1:] for row in after[table]) == before[table][-len(after[table]):]
    for table in ("ir_paper_deployments", "ir_shadow_deployments"):
        assert after[table] == before[table]
        assert not any(fk["referred_table"] == "graph_versions"
                       for fk in sa.inspect(engine).get_foreign_keys(table))
    version = after["graph_versions"][0]
    assert version[2:5] == (1, '{"identifier":"graph.legacy","version":1,"nodes":["n1"]}', "sha256:" + "c" * 64)


def test_revision_0021_populated_legacy_round_trip_restores_rows_and_contracts(tmp_path):
    """A sole legacy lineage can cross 0021 and return with its exact 0020 shape."""
    engine = _at_revision_0020(tmp_path, "0021-populated-round-trip.db")
    with engine.begin() as connection:
        before_rows = _insert_populated_0020_graph_lineage(connection)
        before_contracts = {table: _revision_0020_contract(engine, table) for table in AFFECTED_0021_TABLES}
        command.upgrade(migrate.alembic_config(connection), "0021")
        expected_0021_rows = {
            table: tuple(connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all())
            for table in AFFECTED_0021_TABLES
        }
        expected_0021_contracts = {
            table: _revision_0021_contract(engine, table) for table in AFFECTED_0021_TABLES
        }
        command.downgrade(migrate.alembic_config(connection), "0020")
        restored_rows = {
            table: tuple(connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all())
            for table in AFFECTED_0021_TABLES
        }
    assert migrate.schema_version(engine) == "0020"
    assert restored_rows == before_rows
    assert {
        table: _semantic_contract(_revision_0020_contract(engine, table))
        for table in AFFECTED_0021_TABLES
    } == {
        table: _semantic_contract(contract) for table, contract in before_contracts.items()
    }
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0021")
    assert migrate.schema_version(engine) == "0021"
    with engine.connect() as connection:
        assert {
            table: tuple(connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all())
            for table in AFFECTED_0021_TABLES
        } == expected_0021_rows
    assert {
        table: _revision_0021_contract(engine, table) for table in AFFECTED_0021_TABLES
    } == expected_0021_contracts


def test_revision_0021_downgrade_refuses_two_owner_same_identifier_before_ddl(tmp_path):
    """Two tenant-local graph identities cannot collapse into the 0020 global key."""
    engine = _at_revision_0020(tmp_path, "0021-identifier-collision.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0021")
        connection.execute(sa.text(
            "INSERT INTO organizations VALUES "
            "('owner.other','Other','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ))
        for owner, project in (("owner", "project.one"), ("owner.other", "project.two")):
            connection.execute(sa.text(
                "INSERT INTO projects (project_id,owner_id,name,description,status,created_at,updated_at) "
                "VALUES (:project,:owner,:project,'','active','2026-08-12 08:00:00','2026-08-12 08:00:00')"
            ), {"owner": owner, "project": project})
            connection.execute(sa.text(
                "INSERT INTO graph_artifacts "
                "(owner_id,identifier,project_id,display_name,draft_json,draft_revision,published_revision,"
                "current_version,created_at,updated_at) VALUES "
                "(:owner,'shared.graph',:project,'Shared',:draft,"
                "1,1,1,'2026-08-12 08:00:00','2026-08-12 08:00:00')"
            ), {"owner": owner, "project": project,
                "draft": '{"identifier":"shared.graph","version":1}'})
            connection.execute(sa.text(
                "INSERT INTO graph_versions "
                "(owner_id,graph_identifier,version,artifact_json,content_address,visibility,created_at) VALUES "
                "(:owner,'shared.graph',1,:artifact,:address,'PRIVATE',"
                "'2026-08-12 08:00:00')"
            ), {"owner": owner, "artifact": '{"identifier":"shared.graph","version":1}',
                "address": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"})

    before = {table: _revision_0021_contract(engine, table) for table in AFFECTED_0021_TABLES}
    with engine.connect() as connection:
        rows = connection.execute(sa.text(
            "SELECT owner_id,identifier,project_id FROM graph_artifacts ORDER BY owner_id"
        )).all()
        foreign_keys = connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one()

    with pytest.raises(RuntimeError, match="graph identifiers would collide"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0020")

    assert migrate.schema_version(engine) == "0021"
    assert {table: _revision_0021_contract(engine, table) for table in AFFECTED_0021_TABLES} == before
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT owner_id,identifier,project_id FROM graph_artifacts ORDER BY owner_id"
        )).all() == rows
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys


@pytest.mark.parametrize("table", (
    "projects",
    "graph_artifacts",
    "graph_versions",
    "ir_graph_layouts",
    "ir_graph_layout_positions",
    "ir_graph_layout_groups",
    "ir_graph_layout_group_members",
    "ir_graph_layout_orphan_archive",
    "ir_graph_layout_position_orphan_archive",
    "ir_paper_deployments",
    "ir_shadow_deployments",
))
def test_revision_0021_downgrade_post_rename_retry_recovers_before_owner_refusal(tmp_path, table):
    """A completed 0020 temp table is authoritative before downgrade refusal reads it."""
    engine = _at_revision_0020(tmp_path, f"0021-{table}-downgrade-post-rename.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0021")
    expected = _revision_0021_contract(_at_revision_0020(
        tmp_path, f"0021-{table}-downgrade-expected.db"), table)
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_rename(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and f"ALTER TABLE {table}__0021 RENAME TO {table}" in statement:
            failed = True
            raise RuntimeError(f"injected interruption after {table} downgrade rename")

    with pytest.raises(RuntimeError, match="injected interruption"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0020")

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0020")

    assert failed
    assert migrate.schema_version(engine) == "0020"
    assert _semantic_contract(_revision_0021_contract(engine, table)) == _semantic_contract(expected)
    assert not any(name.endswith("__0021") for name in sa.inspect(engine).get_table_names())


@pytest.mark.parametrize("table", AFFECTED_0021_TABLES)
@pytest.mark.parametrize(
    ("phase", "marker"),
    (("stale-temp", "CREATE TABLE {table}__0021"),
     ("completed-temp", "DROP TABLE {table}")),
)
def test_revision_0021_downgrade_retry_recovers_every_custom_rebuild_shape(tmp_path, table, phase, marker):
    """Both durable downgrade crash shapes converge with rows, DDL, version and FK state intact."""
    engine = _at_revision_0020(tmp_path, f"0021-{table}-{phase}-downgrade.db")
    with engine.begin() as connection:
        expected_rows = _insert_populated_0020_graph_lineage(connection)
        expected_contract = _revision_0020_contract(engine, table)
        command.upgrade(migrate.alembic_config(connection), "0021")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_shape(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and marker.format(table=table) in statement:
            failed = True
            raise RuntimeError(f"injected {phase} downgrade interruption for {table}")

    with pytest.raises(RuntimeError, match=f"injected {phase} downgrade interruption"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0020")
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0020")

    assert failed
    assert migrate.schema_version(engine) == "0020"
    assert _semantic_contract(_revision_0020_contract(engine, table)) == _semantic_contract(expected_contract)
    with engine.connect() as connection:
        assert tuple(connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all()) == expected_rows[table]
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == 1
    assert not any(name.endswith("__0021") for name in sa.inspect(engine).get_table_names())


@pytest.mark.parametrize("table", AFFECTED_0021_TABLES)
@pytest.mark.parametrize(
    ("phase", "marker"),
    (("stale-temp", "CREATE TABLE {table}__0021"),
     ("completed-temp", "DROP TABLE {table}")),
)
def test_revision_0021_upgrade_retry_recovers_each_custom_temp_shape(tmp_path, table, phase, marker):
    """Every custom rebuild converges from source+temp and source-absent+temp states."""
    expected_engine = _at_revision_0020(tmp_path, f"0021-{table}-{phase}-expected.db")
    with expected_engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), HEAD)
    expected = _revision_0021_contract(expected_engine, table)
    engine = _at_revision_0020(tmp_path, f"0021-{table}-{phase}.db")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_shape(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and marker.format(table=table) in statement:
            failed = True
            raise RuntimeError(f"injected {phase} interruption for {table}")

    with pytest.raises(RuntimeError, match=f"injected {phase} interruption"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), HEAD)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), HEAD)

    assert failed
    assert migrate.schema_version(engine) == HEAD
    assert _semantic_contract(_revision_0021_contract(engine, table)) == _semantic_contract(expected)
    assert not any(name.endswith("__0021") for name in sa.inspect(engine).get_table_names())


@pytest.mark.parametrize("table", ("ir_paper_deployments", "ir_shadow_deployments"))
def test_revision_0021_upgrade_money_post_rename_retry_restores_full_contract(tmp_path, table):
    """MONEY provenance rebuilds retain their partial authority indexes after a retry."""
    expected_engine = _at_revision_0020(tmp_path, f"0021-{table}-upgrade-expected.db")
    with expected_engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), HEAD)
    expected = _revision_0021_contract(expected_engine, table)

    engine = _at_revision_0020(tmp_path, f"0021-{table}-upgrade-post-rename.db")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_rename(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and f"ALTER TABLE {table}__0021 RENAME TO {table}" in statement:
            failed = True
            raise RuntimeError(f"injected interruption after {table} upgrade rename")

    with pytest.raises(RuntimeError, match="injected interruption"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), HEAD)

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), HEAD)

    assert failed
    assert migrate.schema_version(engine) == HEAD
    assert _revision_0021_contract(engine, table) == expected


@pytest.mark.parametrize("marker", (
    "CREATE TABLE projects__0020",
    "ALTER TABLE projects__0020 RENAME TO projects",
), ids=("project-temp-create", "project-post-rename"))
def test_revision_0020_upgrade_retry_recovers_project_rebuild_at_each_sqlite_boundary(tmp_path, marker):
    """Both durable SQLite interruption shapes converge to the 0020 project contract."""
    engine = _at_revision_0019(tmp_path, f"0020-{marker[:12]}.db")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_project_rebuild(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and marker in statement:
            failed = True
            raise RuntimeError(f"injected interruption at {marker}")

    with engine.begin() as connection:
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.upgrade(migrate.alembic_config(connection), HEAD)
        command.upgrade(migrate.alembic_config(connection), HEAD)

    assert failed
    assert migrate.schema_version(engine) == HEAD
    assert "projects__0020" not in set(sa.inspect(engine).get_table_names())
    assert any(index["name"] == "ix_projects_owner_id"
               for index in sa.inspect(engine).get_indexes("projects"))


def test_revision_0020_upgrade_retry_after_graph_versions_rename_restores_content_index(tmp_path):
    """A retry after the final graph-table rename must restore its named index."""
    engine = _at_revision_0019(tmp_path, "0020-graph-versions-post-rename.db")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_graph_versions_rename(
            _conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and "ALTER TABLE graph_versions__0020 RENAME TO graph_versions" in statement:
            failed = True
            raise RuntimeError("injected interruption after graph_versions rename")

    with engine.begin() as connection:
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.upgrade(migrate.alembic_config(connection), HEAD)
        command.upgrade(migrate.alembic_config(connection), HEAD)

    assert failed
    assert migrate.schema_version(engine) == HEAD
    assert any(index["name"] == "ix_graph_versions_content_address"
               for index in sa.inspect(engine).get_indexes("graph_versions"))


def test_revision_0020_upgrade_preserves_real_0019_project_and_graph_payloads(tmp_path):
    engine = _at_revision_0019(tmp_path, "0020-legacy-preservation.db")
    with engine.begin() as connection:
        project, graph, version = _insert_legacy_project_graph(connection)
        command.upgrade(migrate.alembic_config(connection), HEAD)
        migrated_project = connection.execute(sa.text(
            "SELECT project_id,owner_id,name,description,status,created_at,updated_at "
            "FROM projects WHERE project_id='project.legacy'"
        )).one()
        migrated_graph = connection.execute(sa.text(
            "SELECT identifier,project_id,display_name,draft_json,draft_revision,published_revision,"
            "current_version,created_at,updated_at FROM graph_artifacts WHERE identifier='graph.legacy'"
        )).one()
        migrated_version = connection.execute(sa.text(
            "SELECT graph_identifier,version,artifact_json,content_address,visibility,created_at "
            "FROM graph_versions WHERE graph_identifier='graph.legacy'"
        )).one()

    assert migrated_project == (project[0], "owner", *project[1:])
    assert migrated_graph == graph
    assert migrated_version == (*version[:4], "PRIVATE", version[4])


def test_revision_0020_fresh_and_upgraded_contracts_match_completely(tmp_path):
    """0020 owns its historical DDL; parity includes defaults, guards and index SQL."""
    fresh = _build_from_models(tmp_path)
    upgraded = _at_revision_0019(tmp_path, "0020-contract-upgrade.db")
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), HEAD)

    for table in ("projects", "graph_versions"):
        assert _revision_0020_contract(upgraded, table) == _revision_0020_contract(fresh, table)

    from app.db.models import GraphVersion, Project

    assert Project.__table__.c.description.default.arg == ""
    assert Project.__table__.c.status.default.arg == "active"
    assert Project.__table__.c.description.server_default.arg == ""
    assert Project.__table__.c.status.server_default.arg == "active"
    assert GraphVersion.__table__.c.visibility.default.arg == "PRIVATE"
    assert GraphVersion.__table__.c.visibility.server_default.arg == "PRIVATE"


def test_revision_0020_downgrade_refusal_preserves_owner_schema_data_version_and_fk_state(tmp_path):
    engine = _at_revision_0019(tmp_path, "0020-downgrade-refusal.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0020")
        connection.execute(sa.text(
            "INSERT INTO organizations VALUES "
            "('owner.other','Other','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(sa.text(
            "INSERT INTO projects "
            "(project_id,owner_id,name,description,status,created_at,updated_at) VALUES "
            "('project.other','owner.other','Shared','payload','active',"
            "'2026-08-11 10:00:00','2026-08-11 10:00:00')"))

    before = {table: _revision_0020_contract(engine, table)
              for table in ("projects", "graph_versions")}
    with engine.connect() as connection:
        rows = connection.execute(sa.text(
            "SELECT project_id,owner_id,name,description,status,created_at,updated_at "
            "FROM projects ORDER BY project_id"
        )).all()
        foreign_keys = connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one()

    with pytest.raises(RuntimeError, match="non-legacy owner"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0019")

    assert migrate.schema_version(engine) == "0020"
    assert {table: _revision_0020_contract(engine, table)
            for table in ("projects", "graph_versions")} == before
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT project_id,owner_id,name,description,status,created_at,updated_at "
            "FROM projects ORDER BY project_id"
        )).all() == rows
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys


def test_revision_0020_downgrade_refuses_two_valid_owner_same_name_before_destructive_ddl(tmp_path):
    engine = _at_revision_0019(tmp_path, "0020-downgrade-two-owner-same-name.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0020")
        connection.execute(sa.text("UPDATE projects SET name = 'Shared' WHERE owner_id = 'owner'"))
        connection.execute(sa.text(
            "INSERT INTO organizations VALUES "
            "('owner.other','Other','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(sa.text(
            "INSERT INTO projects "
            "(project_id,owner_id,name,description,status,created_at,updated_at) VALUES "
            "('project.other','owner.other','Shared','payload','active',"
            "'2026-08-11 10:00:00','2026-08-11 10:00:00')"))

    before = {table: _revision_0020_contract(engine, table)
              for table in ("projects", "graph_versions")}
    with engine.connect() as connection:
        rows = connection.execute(sa.text(
            "SELECT project_id,owner_id,name FROM projects ORDER BY project_id"
        )).all()
        foreign_keys = connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one()

    with pytest.raises(RuntimeError, match="tenant-local project names would collide"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0019")

    assert migrate.schema_version(engine) == "0020"
    assert {table: _revision_0020_contract(engine, table)
            for table in ("projects", "graph_versions")} == before
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT project_id,owner_id,name FROM projects ORDER BY project_id"
        )).all() == rows
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys


def test_revision_0020_downgrade_and_reupgrade_round_trip_legacy_owner_losslessly(tmp_path):
    engine = _at_revision_0019(tmp_path, "0020-downgrade-reupgrade.db")
    with engine.begin() as connection:
        project, graph, version = _insert_legacy_project_graph(connection)
        command.upgrade(migrate.alembic_config(connection), "0020")
        command.downgrade(migrate.alembic_config(connection), "0019")
        rolled_project = connection.execute(sa.text(
            "SELECT project_id,name,description,status,created_at,updated_at "
            "FROM projects WHERE project_id='project.legacy'"
        )).one()
        rolled_version = connection.execute(sa.text(
            "SELECT graph_identifier,version,artifact_json,content_address,created_at "
            "FROM graph_versions WHERE graph_identifier='graph.legacy'"
        )).one()
        command.upgrade(migrate.alembic_config(connection), "0020")
        restored_project = connection.execute(sa.text(
            "SELECT project_id,owner_id,name,description,status,created_at,updated_at "
            "FROM projects WHERE project_id='project.legacy'"
        )).one()
        restored_graph = connection.execute(sa.text(
            "SELECT identifier,project_id,display_name,draft_json,draft_revision,published_revision,"
            "current_version,created_at,updated_at FROM graph_artifacts WHERE identifier='graph.legacy'"
        )).one()
        restored_version = connection.execute(sa.text(
            "SELECT graph_identifier,version,artifact_json,content_address,visibility,created_at "
            "FROM graph_versions WHERE graph_identifier='graph.legacy'"
        )).one()

    assert rolled_project == project
    assert rolled_version == version
    assert restored_project == (project[0], "owner", *project[1:])
    assert restored_graph == graph
    assert restored_version == (*version[:4], "PRIVATE", version[4])


def test_revision_0020_upgrade_failure_restores_an_already_disabled_foreign_key_state(tmp_path):
    engine = _at_revision_0019(tmp_path, "0020-fk-caller-state.db")
    failed = False
    raw = engine.raw_connection()
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.commit()
    finally:
        raw.close()

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_project_create(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and "CREATE TABLE projects__0020" in statement:
            failed = True
            raise RuntimeError("injected interruption after project temp creation")

    with pytest.raises(RuntimeError, match="injected interruption"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), HEAD)

    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == 0
    assert failed


def test_revision_0020_downgrade_failure_restores_an_already_disabled_foreign_key_state(tmp_path):
    engine = _at_revision_0019(tmp_path, "0020-downgrade-fk-caller-state.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0020")
    failed = False
    raw = engine.raw_connection()
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.commit()
    finally:
        raw.close()

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_graph_versions_create(
            _conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and "CREATE TABLE graph_versions__0019" in statement:
            failed = True
            raise RuntimeError("injected interruption after graph_versions temp creation")

    with pytest.raises(RuntimeError, match="injected interruption"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0019")

    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == 0
    assert failed


def test_revision_0020_downgrade_retry_promotes_completed_0019_temp_tables(tmp_path):
    """A DROP-before-RENAME crash leaves rebuilt tables ready to promote, not recreate."""
    engine = _at_revision_0019(tmp_path, "0020-downgrade-promote-temp.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0020")

    raw = engine.raw_connection()
    try:
        raw.execute("PRAGMA foreign_keys=OFF")
        raw.execute("""
            CREATE TABLE graph_versions__0019 (
                graph_identifier VARCHAR(128) NOT NULL, version INTEGER NOT NULL,
                artifact_json TEXT NOT NULL, content_address VARCHAR(71) NOT NULL,
                created_at DATETIME NOT NULL, PRIMARY KEY (graph_identifier, version),
                FOREIGN KEY(graph_identifier) REFERENCES graph_artifacts(identifier) ON DELETE RESTRICT,
                CONSTRAINT ck_graph_versions_version CHECK (version >= 1),
                CONSTRAINT ck_graph_versions_valid_json CHECK (json_valid(artifact_json)),
                CONSTRAINT ck_graph_versions_identifier_matches_json CHECK (json_extract(artifact_json, '$.identifier') IS graph_identifier),
                CONSTRAINT ck_graph_versions_version_matches_json CHECK (json_extract(artifact_json, '$.version') IS version)
            )
        """)
        raw.execute("""
            INSERT INTO graph_versions__0019
            (graph_identifier,version,artifact_json,content_address,created_at)
            SELECT graph_identifier,version,artifact_json,content_address,created_at FROM graph_versions
        """)
        raw.execute("DROP TABLE graph_versions")
        raw.execute("""
            CREATE TABLE projects__0019 (
                project_id VARCHAR(64) NOT NULL PRIMARY KEY, name VARCHAR(128) NOT NULL,
                description TEXT NOT NULL DEFAULT '', status VARCHAR(16) NOT NULL DEFAULT 'active',
                created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
                CONSTRAINT ck_projects_status CHECK (status IN ('active', 'archived'))
            )
        """)
        raw.execute("""
            INSERT INTO projects__0019 (project_id,name,description,status,created_at,updated_at)
            SELECT project_id,name,description,status,created_at,updated_at FROM projects
        """)
        raw.execute("DROP TABLE projects")
        raw.execute("PRAGMA foreign_keys=ON")
        raw.commit()
    finally:
        raw.close()

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0019")

    inspector = sa.inspect(engine)
    assert migrate.schema_version(engine) == "0019"
    assert "owner_id" not in {column["name"] for column in inspector.get_columns("projects")}
    assert "visibility" not in {column["name"] for column in inspector.get_columns("graph_versions")}
    assert {"projects__0019", "graph_versions__0019"}.isdisjoint(inspector.get_table_names())


def _canonical_0019_contract(tmp_path, table: str) -> dict:
    engine = _fresh_engine(tmp_path, f"canonical-{table}.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0019")
    return _table_contract(engine, table)


@pytest.mark.parametrize("table", ("positions", "ir_shadow_divergences"))
def test_revision_0019_retry_after_account_table_rename_restores_full_contract(tmp_path, table):
    """A retry after RENAME must restore every legacy index, unique rule and FK."""
    expected = _canonical_0019_contract(tmp_path, table)
    engine = _fresh_engine(tmp_path, f"0019-{table}-rename-contract.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_rename(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and f"ALTER TABLE _alembic_tmp_{table} RENAME TO {table}" in statement:
            failed = True
            raise RuntimeError(f"injected interruption after {table} rename")

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0018")
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.upgrade(migrate.alembic_config(connection), "0019")
        command.upgrade(migrate.alembic_config(connection), "0019")

    assert failed
    assert _table_contract(engine, table) == expected


@pytest.mark.parametrize(
    ("table", "marker"),
    (("instrument_state", "CREATE TABLE _alembic_tmp_instrument_state"),
     ("capital_state", "ALTER TABLE _alembic_tmp_capital_state RENAME TO capital_state"),
     ("deployments", "CREATE TABLE deployments__0019")),
)
def test_revision_0019_retry_during_default_removal_restores_exact_contract(tmp_path, table, marker):
    """Default-removal batch rebuilds are recoverable at either SQLite DDL boundary."""
    expected = _canonical_0019_contract(tmp_path, table)
    engine = _fresh_engine(tmp_path, f"0019-{table}-default-contract.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    failed = False

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_default_rebuild(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal failed
        if not failed and marker in statement:
            failed = True
            raise RuntimeError(f"injected interruption during {table} default removal")

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0018")
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.upgrade(migrate.alembic_config(connection), "0019")
        command.upgrade(migrate.alembic_config(connection), "0019")

    assert failed
    assert migrate.schema_version(engine) == "0019"
    assert _table_contract(engine, table) == expected


def test_revision_0019_retry_after_deployments_default_removal_drop_promotes_generic_temp(tmp_path):
    """A retry must recover the default-removal batch before deployments reflection."""
    expected = _canonical_0019_contract(tmp_path, "deployments")
    engine = _fresh_engine(tmp_path, "0019-deployments-default-drop-retry.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    completed_custom_rebuild = False
    failed = False
    interrupted_table_names: set[str] | None = None
    interrupted_temp_ddl: str | None = None
    interrupted_temp_rows: list[dict[str, object]] = []

    @sa.event.listens_for(engine, "after_cursor_execute")
    def interrupt_after_default_removal_drop(
            _conn, _cursor, statement, _parameters, _context, _many):
        nonlocal completed_custom_rebuild, failed, interrupted_table_names
        nonlocal interrupted_temp_ddl, interrupted_temp_rows
        if "ALTER TABLE deployments__0019 RENAME TO deployments" in statement:
            completed_custom_rebuild = True
        if (completed_custom_rebuild and not failed
                and statement.strip() == "DROP TABLE deployments"):
            failed = True
            interrupted_table_names = {
                row[0] for row in _cursor.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
            interrupted_temp_ddl = _cursor.connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' "
                "AND name='_alembic_tmp_deployments'").fetchone()[0]
            temp_cursor = _cursor.connection.execute(
                "SELECT * FROM _alembic_tmp_deployments")
            columns = [column[0] for column in temp_cursor.description]
            interrupted_temp_rows = [
                dict(zip(columns, row)) for row in temp_cursor.fetchall()]
            raise RuntimeError("injected interruption after deployments default-removal drop")

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0018")
        with pytest.raises(RuntimeError, match="injected interruption"):
            command.upgrade(migrate.alembic_config(connection), "0019")
        assert failed
        assert interrupted_table_names is not None
        assert "deployments" not in interrupted_table_names
        assert "_alembic_tmp_deployments" in interrupted_table_names
        assert interrupted_temp_ddl is not None
        # Alembic rolls the test transaction back after the injected exception. Recreate
        # the exact batch table observed above to model a process interruption after
        # SQLite committed the DROP but before the RENAME.
        connection.execute(sa.text(interrupted_temp_ddl))
        if interrupted_temp_rows:
            columns = tuple(interrupted_temp_rows[0])
            connection.execute(sa.text(
                "INSERT INTO _alembic_tmp_deployments "
                f"({', '.join(columns)}) VALUES "
                f"({', '.join(f':{column}' for column in columns)})"),
                interrupted_temp_rows)
        command.upgrade(migrate.alembic_config(connection), "0019")

    assert migrate.schema_version(engine) == "0019"
    assert "_alembic_tmp_deployments" not in sa.inspect(engine).get_table_names()
    assert _table_contract(engine, "deployments") == expected


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
                    "(owner_id, graph_identifier, version, artifact_json, content_address, created_at) "
                    "VALUES ('owner', :identifier, :version, :artifact_json, :address, "
                    "'2026-08-03 10:00:00')"
                ), {
                    "identifier": GRAPH["identifier"],
                    "version": row_version,
                    "artifact_json": canonical_json(document),
                    "address": content_address(document),
                })


def test_product_object_upgrade_attaches_valid_layout_and_removes_orphans(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline_at_revision(tmp_path, "0006-test_product_object_upgrade_attaches_valid_layout_and_removes_orphans.db", "0006")
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

    assert _upgrade_to_revision(engine, "0006") == "0006"
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
    engine = _build_from_baseline_at_revision(tmp_path, "0006-test_product_object_downgrade_refuses_non_seed_history.db", "0006")
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

    assert migrate.schema_version(engine) == "0006"

    with engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM projects WHERE project_id = 'project.user'"))
        connection.execute(sa.text(
            "UPDATE graph_artifacts SET draft_revision = 1 "
            "WHERE identifier = 'strategy.expanding_z_impulse'"
        ))
    with pytest.raises(RuntimeError, match="modified"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0005")

    assert migrate.schema_version(engine) == "0006"


def test_product_object_rollback_preserves_seed_layout_and_money_record(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline_at_revision(tmp_path, "0006-test_product_object_rollback_preserves_seed_layout_and_money_record.db", "0006")
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

    assert _upgrade_to_revision(engine, "0006") == "0006"


def test_layout_migration_downgrades_without_touching_the_money_record(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0005-test_layout_migration_downgrades_without_touching_the_money_record.db", "0005")
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

    assert _upgrade_to_revision(engine, "0005") == "0005"


def test_visual_group_migration_rolls_back_without_touching_layout_or_money(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline_at_revision(tmp_path, "0007-test_visual_group_migration_rolls_back_without_touching_layout_or_money.db", "0007")
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

    assert _upgrade_to_revision(engine, "0007") == "0007"


def test_review_state_migration_empty_rollback_preserves_existing_records(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline_at_revision(tmp_path, "0008-test_review_state_migration_empty_rollback_preserves_existing_records.db", "0008")
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
    assert _upgrade_to_revision(engine, "0008") == "0008"


def test_review_state_migration_refuses_populated_downgrade(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0008-test_review_state_migration_refuses_populated_downgrade.db", "0008")
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


def test_review_snapshot_migration_empty_rollback_preserves_review_and_money(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "0009-test_review_snapshot_migration_empty_rollback_preserves_review_and_money.db", "0009")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))
        connection.execute(sa.text(
            "INSERT INTO project_review_notes "
            "(note_id, project_id, event_id, event_type, body, created_by, revision, "
            " deleted_at, created_at, updated_at) VALUES "
            "('note-keep', 'project.repository_catalogue', 'run:1', 'experiment_run', "
            " 'Keep this note', 'owner', 0, NULL, "
            " '2026-08-03 10:00:00', '2026-08-03 10:00:00')"
        ))
        command.downgrade(migrate.alembic_config(connection), "0008")

    assert migrate.schema_version(engine) == "0008"
    assert "project_review_snapshots" not in set(sa.inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT body FROM project_review_notes WHERE note_id = 'note-keep'"
        )).scalar_one() == "Keep this note"
        assert connection.execute(sa.text(
            "SELECT cash FROM capital_state WHERE id = 1"
        )).scalar_one() == 49000.0
    assert _upgrade_to_revision(engine, "0009") == "0009"


def test_review_snapshot_migration_refuses_populated_downgrade(tmp_path):
    from app.ir.hashing import canonical_json, content_address

    engine = _build_from_baseline_at_revision(tmp_path, "0009-test_review_snapshot_migration_refuses_populated_downgrade.db", "0009")
    manifest = {
        "schema_version": 1,
        "project_id": "project.repository_catalogue",
        "events": [],
        "captured_queues": {
            "review_needed_runs": [], "pending_candidates": [], "active_findings": [],
        },
        "notes": [],
        "source_errors": [],
    }
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO project_review_snapshots "
            "(snapshot_id, project_id, label, capture_key, manifest_json, content_address, "
            " created_by, capture_started_at, capture_completed_at) VALUES "
            "('snapshot.1', 'project.repository_catalogue', 'Daily', "
            " '2ba56d22-7094-4a8d-9bf5-b84a4e8f083f', :manifest, :address, 'owner', "
            " '2026-08-03 10:00:00', '2026-08-03 10:00:01')"
        ), {"manifest": canonical_json(manifest), "address": content_address(manifest)})

    with pytest.raises(RuntimeError, match="review snapshots exist"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0008")

    assert migrate.schema_version(engine) == "0009"


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


def test_revision_0023_preserves_populated_strategy_configuration_and_removes_money_fk(tmp_path):
    """0023 changes identities, never the operator's configuration payload bytes."""
    engine = _at_revision_0020(tmp_path, "0023-populated.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
        connection.execute(sa.text(
            "INSERT INTO watchlists VALUES (901,'legacy watch','trend_impulse_v3','active','15minute','exact','2026-08-12 10:00:00')"))
        connection.execute(sa.text(
            "INSERT INTO watchlist_membership VALUES ('NIFTY',901,'2026-08-12 10:01:00')"))
        connection.execute(sa.text(
            "INSERT INTO strategy_lifecycle VALUES (901,'strategy.legacy','running','generated',901,1.25,'exact','2026-08-12 10:02:00','2026-08-12 10:03:00')"))
        connection.execute(sa.text(
            "INSERT INTO generated_strategies (key,created_at,version,composition_json,source) VALUES "
            "('gen.legacy','2026-08-12 10:04:00','version.legacy','{\"key\":\"gen.legacy\"}','source')"))
        connection.execute(sa.text(
            "INSERT INTO runtime_config VALUES ('max_daily_loss','123.0','2026-08-12 10:05:00')"))
        before = {table: tuple(connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY 1")).all())
                  for table in ("watchlists", "watchlist_membership", "strategy_lifecycle",
                                "generated_strategies", "runtime_config")}
        command.upgrade(migrate.alembic_config(connection), "0023")
        inspector = sa.inspect(connection)
        assert not any(fk["constrained_columns"] == ["watchlist_id"]
                       for fk in inspector.get_foreign_keys("deployments"))
        for table, rows in before.items():
            if table == "generated_strategies":
                continue
            after = tuple(connection.execute(sa.text(
                "SELECT owner_id,key,version,composition_json,source,created_at FROM generated_strategies"
                if table == "generated_strategies" else f"SELECT * FROM {table} ORDER BY 1,2"
            )).all())
            without_owner = ([row[:1] + row[2:] for row in after]
                             if table in ("watchlists", "strategy_lifecycle")
                             else [row[1:] for row in after])
            assert without_owner == list(rows)
            assert {row[1] for row in after} == {"owner"} if table in ("watchlists", "strategy_lifecycle") else {row[0] for row in after} == {"owner"}
        assert connection.execute(sa.text(
            "SELECT owner_id,key,version,composition_json,source,created_at FROM generated_strategies"
        )).one() == ("owner", "gen.legacy", "version.legacy", '{"key":"gen.legacy"}',
                     "source", "2026-08-12 10:04:00")
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []


def test_revision_0023_downgrade_refuses_without_changing_schema_or_fk_mode(tmp_path):
    engine = _at_revision_0020(tmp_path, "0023-downgrade-refusal.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
    with engine.connect() as connection:
        before = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )).all())
        foreign_keys = connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one()
    with pytest.raises(RuntimeError, match="forbidden MONEY-to-USER"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0022")
    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
        assert tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )).all()) == before
        assert migrate.schema_version(engine) == "0023"


STRATEGY_CONFIG_0023_TABLES = (
    "watchlists", "watchlist_membership", "strategy_lifecycle", "generated_strategies",
    "runtime_config", "deployments",
)


def _seed_0023_strategy_config_payload(connection):
    connection.execute(sa.text(
        "INSERT INTO watchlists VALUES "
        "(923,'proof watch','trend_impulse_v3','active',NULL,'proof',CURRENT_TIMESTAMP)"))
    connection.execute(sa.text(
        "INSERT INTO watchlist_membership VALUES ('NIFTY',923,CURRENT_TIMESTAMP)"))
    connection.execute(sa.text(
        "INSERT INTO strategy_lifecycle VALUES "
        "(923,'proof.strategy','candidate','builtin',923,1.0,'proof',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    connection.execute(sa.text(
        "INSERT INTO generated_strategies (key,created_at,version,composition_json,source) "
        "VALUES ('gen_proof_restart',CURRENT_TIMESTAMP,'v','{}','proof')"))
    connection.execute(sa.text(
        "INSERT INTO runtime_config VALUES ('max_daily_loss','123',CURRENT_TIMESTAMP)"))


def test_revision_0023_fresh_and_upgraded_strategy_configuration_contracts_match(tmp_path):
    """Rows, constraints, keys, indexes, checks and triggers converge at head."""
    upgraded = _at_revision_0020(tmp_path, "0023-contract-upgraded.db")
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
    fresh = _build_from_models(tmp_path)
    for table in STRATEGY_CONFIG_0023_TABLES:
        assert _semantic_contract(_revision_0020_contract(upgraded, table)) == _semantic_contract(
            _revision_0020_contract(fresh, table)
        )


@pytest.mark.parametrize("table", STRATEGY_CONFIG_0023_TABLES)
def test_revision_0023_recovers_each_proven_completed_temp(tmp_path, table):
    """An interruption after source drop promotes only the migration-proven temp."""
    engine = _at_revision_0020(tmp_path, f"0023-recovery-{table}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
    raised = False

    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal raised
        if not raised and statement.lstrip().upper().startswith(
                f"ALTER TABLE {table.upper()}__0023 RENAME TO {table.upper()}"):
            raised = True
            raise RuntimeError(f"injected 0023 completed temp for {table}")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected 0023 completed temp"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0023")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
        assert table in sa.inspect(connection).get_table_names()
        assert f"{table}__0023" not in sa.inspect(connection).get_table_names()
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []


def test_revision_0023_refuses_unproven_completed_temp_without_mutation(tmp_path):
    engine = _at_revision_0020(tmp_path, "0023-unproven-temp.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
        connection.execute(sa.text("ALTER TABLE watchlists RENAME TO watchlists__0023"))
    before = tuple(engine.connect().execute(sa.text(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
    )).all())
    with pytest.raises(RuntimeError, match="(unproven|malformed) completed rebuild"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0023")
    assert tuple(engine.connect().execute(sa.text(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
    )).all()) == before


def test_revision_0023_preflights_every_completed_temp_before_promoting_any(tmp_path):
    """A bad later recovery candidate cannot partially promote an earlier good one."""
    engine = _at_revision_0020(tmp_path, "0023-recovery-preflight-all.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
    interrupted = False

    def stop_after_watchlist_drop(_conn, _cursor, statement, _params, _context, _many):
        nonlocal interrupted
        if not interrupted and statement.lstrip().upper().startswith(
                "ALTER TABLE WATCHLISTS__0023 RENAME TO WATCHLISTS"):
            interrupted = True
            raise RuntimeError("leave a proven watchlist temp")

    sa.event.listen(engine, "before_cursor_execute", stop_after_watchlist_drop)
    try:
        with pytest.raises(RuntimeError, match="proven watchlist"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0023")
    finally:
        sa.event.remove(engine, "before_cursor_execute", stop_after_watchlist_drop)
    with engine.begin() as connection:
        # This second source-absent temp has no durable proof. It sorts after
        # watchlists in TABLES, so sequential recovery would promote watchlists first.
        connection.execute(sa.text("ALTER TABLE runtime_config RENAME TO runtime_config__0023"))
    with pytest.raises(RuntimeError, match="(unproven|malformed) completed rebuild"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0023")
    names = sa.inspect(engine).get_table_names()
    assert interrupted and "watchlists" not in names and "watchlists__0023" in names
    assert "runtime_config" not in names and "runtime_config__0023" in names
    assert migrate.schema_version(engine) == "0022"


def test_revision_0023_refuses_proven_temp_when_its_schema_changes_after_proof(tmp_path):
    engine = _at_revision_0020(tmp_path, "0023-malformed-proven-temp.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
    raised = False

    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal raised
        if not raised and statement.lstrip().upper().startswith(
                "ALTER TABLE WATCHLISTS__0023 RENAME TO WATCHLISTS"):
            raised = True
            raise RuntimeError("injected completed watchlist temp")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected completed"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0023")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE INDEX attack_index ON watchlists__0023(name)"))
    with pytest.raises(RuntimeError, match="malformed completed rebuild"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0023")


def test_revision_0023_refuses_temp_schema_changed_after_create_before_proof(tmp_path):
    engine = _at_revision_0020(tmp_path, "0023-pre-proof-schema.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
    changed = False

    def mutate(_conn, cursor, statement, _params, _context, _many):
        nonlocal changed
        # The fixed target digest has already been captured after CREATE. Mutate while
        # the copy is under way, before the proof is persisted.
        if not changed and statement.lstrip().upper().startswith("INSERT INTO WATCHLISTS__0023"):
            changed = True
            cursor.connection.execute("CREATE INDEX attack_preproof ON watchlists__0023(name)")

    sa.event.listen(engine, "after_cursor_execute", mutate)
    try:
        with pytest.raises(RuntimeError, match="target schema proof failed for watchlists"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0023")
    finally:
        sa.event.remove(engine, "after_cursor_execute", mutate)
    assert changed and migrate.schema_version(engine) == "0022"


@pytest.mark.parametrize("table", ("watchlists", "watchlist_membership", "strategy_lifecycle",
                                   "generated_strategies", "runtime_config", "deployments"))
def test_revision_0023_refuses_payload_tampered_after_copy_before_proof(tmp_path, table):
    engine = _at_revision_0020(tmp_path, f"0023-source-proof-{table}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
        connection.execute(sa.text(
            "INSERT INTO watchlists VALUES (991,'proof watch','trend_impulse_v3','active',NULL,'exact',CURRENT_TIMESTAMP)"))
        if table == "watchlist_membership":
            connection.execute(sa.text(
                "INSERT INTO watchlist_membership VALUES ('NIFTY',991,CURRENT_TIMESTAMP)"))
        elif table == "strategy_lifecycle":
            connection.execute(sa.text(
                "INSERT INTO strategy_lifecycle VALUES (991,'proof.strategy','candidate','builtin',NULL,NULL,'exact',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        elif table == "generated_strategies":
            connection.execute(sa.text(
                "INSERT INTO generated_strategies (key,created_at,version,composition_json,source) VALUES "
                "('gen_proof',CURRENT_TIMESTAMP,'v','{}','exact')"))
        elif table == "runtime_config":
            connection.execute(sa.text(
                "INSERT INTO runtime_config VALUES ('max_daily_loss','123',CURRENT_TIMESTAMP)"))
        source_before = tuple(connection.execute(sa.text(
            f"SELECT * FROM {table} ORDER BY rowid")).all())
        source_columns_before = tuple(column["name"] for column in sa.inspect(connection).get_columns(table))
    corrupted = False

    def corrupt(_conn, cursor, statement, _params, _context, _many):
        nonlocal corrupted
        if not corrupted and f"{table}__0023" in statement.lower() and statement.lstrip().upper().startswith("INSERT"):
            corrupted = True
            value_column = {
                "watchlists": "notes='tampered'",
                "watchlist_membership": "instrument_key='TAMPERED'",
                "strategy_lifecycle": "note='tampered'",
                "generated_strategies": "source='tampered'",
                "runtime_config": "value='999'",
                "deployments": "name='tampered'",
            }[table]
            cursor.connection.execute(f"UPDATE {table}__0023 SET {value_column}")

    sa.event.listen(engine, "after_cursor_execute", corrupt)
    try:
        with pytest.raises(RuntimeError, match="source-bound payload proof failed"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0023")
    finally:
        sa.event.remove(engine, "after_cursor_execute", corrupt)
    with engine.connect() as connection:
        assert corrupted and migrate.schema_version(engine) == "0022"
        assert tuple(connection.execute(sa.text(
            f"SELECT * FROM {table} ORDER BY rowid")).all()) == source_before
        assert tuple(column["name"] for column in sa.inspect(connection).get_columns(table)) == source_columns_before


@pytest.mark.parametrize("foreign_keys", (0, 1))
def test_revision_0023_success_and_failure_restore_callers_foreign_key_mode(tmp_path, foreign_keys):
    engine = _at_revision_0020(tmp_path, f"0023-fk-{foreign_keys}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
        raw = connection.connection.driver_connection
        raw.commit()
        raw.execute(f"PRAGMA foreign_keys={foreign_keys}")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
    with engine.connect() as connection:
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys


@pytest.mark.parametrize("table", STRATEGY_CONFIG_0023_TABLES)
def test_revision_0023_discards_stale_temp_when_source_is_still_present(tmp_path, table):
    """A source-present temp is incomplete work, even if its name looks plausible."""
    engine = _at_revision_0020(tmp_path, f"0023-stale-{table}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
        connection.execute(sa.text(f"CREATE TABLE {table}__0023 (attacker_value TEXT)"))
        command.upgrade(migrate.alembic_config(connection), "0023")
        assert table in sa.inspect(connection).get_table_names()
        assert f"{table}__0023" not in sa.inspect(connection).get_table_names()


@pytest.mark.parametrize("foreign_keys", (0, 1))
def test_revision_0023_failure_restores_callers_foreign_key_mode_and_version(tmp_path, foreign_keys):
    engine = _at_revision_0020(tmp_path, f"0023-fk-failure-{foreign_keys}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
        raw = connection.connection.driver_connection
        raw.commit()
        raw.execute(f"PRAGMA foreign_keys={foreign_keys}")
    failed = False

    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal failed
        if not failed and statement.lstrip().upper().startswith("CREATE TABLE WATCHLISTS__0023"):
            failed = True
            raise RuntimeError("injected 0023 failure")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected 0023 failure"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0023")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.connect() as connection:
        assert failed
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
        assert migrate.schema_version(engine) == "0022"
        assert "owner_id" not in {column["name"] for column in sa.inspect(connection).get_columns("watchlists")}


def test_revision_0023_retries_after_final_proof_cleanup_before_alembic_stamp(tmp_path):
    """The all-DDL-complete, unstamped window is a clean no-op on retry."""
    engine = _at_revision_0020(tmp_path, "0023-final-cleanup-retry.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
    failed = False

    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal failed
        if not failed and statement.lstrip().upper().startswith("DROP TABLE _STRATEGY_CONFIG_0023_REBUILD_PROOFS"):
            failed = True
            raise RuntimeError("injected after final proof cleanup")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected after final proof cleanup"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0023")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    assert failed and migrate.schema_version(engine) == "0022"
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0023")
    assert migrate.schema_version(engine) == "0023"


@pytest.mark.parametrize("table", STRATEGY_CONFIG_0023_TABLES)
def test_revision_0023_retry_after_rename_before_proof_delete_cleans_all_proof_state(
        tmp_path, table):
    """A durable proof is recovery metadata, never a permanent application table."""
    engine = _at_revision_0020(tmp_path, f"0023-post-rename-proof-{table}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
        _seed_0023_strategy_config_payload(connection)
        source_count = connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        raw = connection.connection.driver_connection
        raw.commit()
        raw.execute("PRAGMA foreign_keys=1")

    interrupted = False

    def stop_before_proof_delete(_conn, _cursor, statement, params, _context, _many):
        nonlocal interrupted
        normalized = " ".join(statement.upper().split())
        parameter_values = tuple(params.values()) if isinstance(params, dict) else tuple(params or ())
        if (not interrupted and normalized.startswith(
                "DELETE FROM _STRATEGY_CONFIG_0023_REBUILD_PROOFS")
                and (table in parameter_values or f"TABLE_NAME='{table.upper()}'" in normalized)):
            interrupted = True
            raise RuntimeError(f"injected after {table} rename")

    sa.event.listen(engine, "before_cursor_execute", stop_before_proof_delete)
    try:
        with pytest.raises(RuntimeError, match=f"injected after {table} rename"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0023")
    finally:
        sa.event.remove(engine, "before_cursor_execute", stop_before_proof_delete)

    with engine.begin() as connection:
        names = sa.inspect(connection).get_table_names()
        assert interrupted and table in names and f"{table}__0023" not in names
        assert "_strategy_config_0023_rebuild_proofs" in names
        assert connection.execute(sa.text(
            "SELECT COUNT(*) FROM _strategy_config_0023_rebuild_proofs "
            "WHERE table_name=:table"), {"table": table}).scalar_one() == 1
        assert migrate.schema_version(engine) == "0022"
        command.upgrade(migrate.alembic_config(connection), "0023")
        assert connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one() == source_count
        assert f"{table}__0023" not in sa.inspect(connection).get_table_names()
        assert "_strategy_config_0023_rebuild_proofs" not in sa.inspect(connection).get_table_names()
        assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == 1
    assert migrate.schema_version(engine) == "0023"


@pytest.mark.parametrize("table", STRATEGY_CONFIG_0023_TABLES)
def test_revision_0023_retry_refuses_a_promoted_source_mutated_before_proof_cleanup(
        tmp_path, table):
    engine = _at_revision_0020(tmp_path, f"0023-promoted-source-tamper-{table}.db")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0022")
        _seed_0023_strategy_config_payload(connection)
    interrupted = False

    def stop_before_proof_delete(_conn, _cursor, statement, params, _context, _many):
        nonlocal interrupted
        normalized = " ".join(statement.upper().split())
        parameter_values = tuple(params.values()) if isinstance(params, dict) else tuple(params or ())
        if (not interrupted and normalized.startswith(
                "DELETE FROM _STRATEGY_CONFIG_0023_REBUILD_PROOFS")
                and (table in parameter_values or f"TABLE_NAME='{table.upper()}'" in normalized)):
            interrupted = True
            raise RuntimeError(f"leave promoted {table}")

    sa.event.listen(engine, "before_cursor_execute", stop_before_proof_delete)
    try:
        with pytest.raises(RuntimeError, match=f"leave promoted {table}"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0023")
    finally:
        sa.event.remove(engine, "before_cursor_execute", stop_before_proof_delete)

    mutation = {
        "watchlists": "UPDATE watchlists SET notes='tampered'",
        "watchlist_membership": "UPDATE watchlist_membership SET instrument_key='TAMPERED'",
        "strategy_lifecycle": "UPDATE strategy_lifecycle SET note='tampered'",
        "generated_strategies": "UPDATE generated_strategies SET source='tampered'",
        "runtime_config": "UPDATE runtime_config SET value='tampered'",
        "deployments": "UPDATE deployments SET name='tampered'",
    }[table]
    with engine.begin() as connection:
        connection.execute(sa.text(mutation))
        before = tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )).all())
        payload = tuple(connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all())
        foreign_keys = connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one()

    with pytest.raises(RuntimeError, match="malformed completed rebuild"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0023")

    with engine.connect() as connection:
        assert interrupted and migrate.schema_version(engine) == "0022"
        assert tuple(connection.execute(sa.text(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        )).all()) == before
        assert tuple(connection.execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all()) == payload
        assert connection.execute(sa.text("PRAGMA foreign_keys")).scalar_one() == foreign_keys
