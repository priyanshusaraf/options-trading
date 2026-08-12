"""own project review persistence by tenant

Revision ID: 0022
Revises: 0021
"""
from __future__ import annotations

import hashlib
import json
import re

import sqlalchemy as sa
from alembic import op


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


TABLES = (
    "project_review_notes",
    "project_review_saved_views",
    "project_review_snapshots",
)
PROOF_TABLE = "_review_0022_rebuild_proofs"


def _canonical_sql(sql: str) -> str:
    """Compare SQLite catalogue SQL without accepting a different contract."""
    return " ".join(sql.replace("\n", " ").replace('"', "").replace("`", "").split()).lower()


def _digest(value: str) -> str:
    return hashlib.sha256(_canonical_sql(value).encode()).hexdigest()


def _target_schema_digest(table: str) -> str:
    """The proof names the logical contract, not the transient table name."""
    return _digest(UPGRADE_DDL[table])

OWNER_COLUMNS = {
    "project_review_notes": (
        "owner_id", "note_id", "project_id", "event_id", "event_type", "body",
        "created_by", "revision", "deleted_at", "created_at", "updated_at",
    ),
    "project_review_saved_views": (
        "owner_id", "view_id", "project_id", "name", "filters_json", "created_by",
        "revision", "deleted_at", "created_at", "updated_at",
    ),
    "project_review_snapshots": (
        "owner_id", "snapshot_id", "project_id", "label", "capture_key", "manifest_json",
        "content_address", "created_by", "capture_started_at", "capture_completed_at",
    ),
}

LEGACY_COLUMNS = {
    "project_review_notes": (
        "note_id", "project_id", "event_id", "event_type", "body", "created_by",
        "revision", "deleted_at", "created_at", "updated_at",
    ),
    "project_review_saved_views": (
        "view_id", "project_id", "name", "filters_json", "created_by", "revision",
        "deleted_at", "created_at", "updated_at",
    ),
    "project_review_snapshots": (
        "snapshot_id", "project_id", "label", "capture_key", "manifest_json",
        "content_address", "created_by", "capture_started_at", "capture_completed_at",
    ),
}


UPGRADE_DDL = {
    "project_review_notes": """CREATE TABLE __TABLE__ (
        owner_id VARCHAR(64) NOT NULL, note_id VARCHAR(64) NOT NULL,
        project_id VARCHAR(64) NOT NULL, event_id VARCHAR(200) NOT NULL,
        event_type VARCHAR(32) NOT NULL, body TEXT NOT NULL, created_by VARCHAR(32) NOT NULL,
        revision INTEGER NOT NULL DEFAULT '0', deleted_at DATETIME,
        created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
        PRIMARY KEY (owner_id, note_id),
        CONSTRAINT fk_project_review_notes_owner_project FOREIGN KEY(owner_id, project_id) REFERENCES projects (owner_id, project_id) ON DELETE RESTRICT,
        CONSTRAINT ck_review_note_event_id CHECK (length(event_id) BETWEEN 1 AND 200),
        CONSTRAINT ck_review_note_event_type CHECK (event_type IN ('graph_version_published', 'experiment_run', 'finding_created', 'candidate_created', 'candidate_decided')),
        CONSTRAINT ck_review_note_body CHECK (length(body) BETWEEN 1 AND 4000),
        CONSTRAINT ck_review_note_owner CHECK (created_by = 'owner'),
        CONSTRAINT ck_review_note_revision CHECK (revision >= 0)
    )""",
    "project_review_saved_views": """CREATE TABLE __TABLE__ (
        owner_id VARCHAR(64) NOT NULL, view_id VARCHAR(64) NOT NULL,
        project_id VARCHAR(64) NOT NULL, name VARCHAR(80) NOT NULL, filters_json TEXT NOT NULL,
        created_by VARCHAR(32) NOT NULL, revision INTEGER NOT NULL DEFAULT '0', deleted_at DATETIME,
        created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
        PRIMARY KEY (owner_id, view_id),
        CONSTRAINT fk_project_review_saved_views_owner_project FOREIGN KEY(owner_id, project_id) REFERENCES projects (owner_id, project_id) ON DELETE RESTRICT,
        CONSTRAINT ck_review_view_name CHECK (length(name) BETWEEN 1 AND 80),
        CONSTRAINT ck_review_view_filters_json CHECK (json_valid(filters_json)),
        CONSTRAINT ck_review_view_owner CHECK (created_by = 'owner'),
        CONSTRAINT ck_review_view_revision CHECK (revision >= 0)
    )""",
    "project_review_snapshots": """CREATE TABLE __TABLE__ (
        owner_id VARCHAR(64) NOT NULL, snapshot_id VARCHAR(64) NOT NULL,
        project_id VARCHAR(64) NOT NULL, label VARCHAR(80) NOT NULL, capture_key VARCHAR(36) NOT NULL,
        manifest_json TEXT NOT NULL, content_address VARCHAR(71) NOT NULL, created_by VARCHAR(32) NOT NULL,
        capture_started_at DATETIME NOT NULL, capture_completed_at DATETIME NOT NULL,
        PRIMARY KEY (owner_id, snapshot_id),
        CONSTRAINT fk_project_review_snapshots_owner_project FOREIGN KEY(owner_id, project_id) REFERENCES projects (owner_id, project_id) ON DELETE RESTRICT,
        CONSTRAINT ck_review_snapshot_label CHECK (length(label) BETWEEN 1 AND 80),
        CONSTRAINT ck_review_snapshot_capture_key CHECK (length(capture_key) = 36),
        CONSTRAINT ck_review_snapshot_owner CHECK (created_by = 'owner'),
        CONSTRAINT ck_review_snapshot_manifest_json CHECK (json_valid(manifest_json)),
        CONSTRAINT ck_review_snapshot_schema_version CHECK (json_extract(manifest_json, '$.schema_version') = 1),
        CONSTRAINT ck_review_snapshot_project_matches_json CHECK (json_extract(manifest_json, '$.project_id') IS project_id),
        CONSTRAINT ck_review_snapshot_capture_window CHECK (capture_completed_at >= capture_started_at)
    )""",
}

EXPECTED_INDEX_SQL = {
    "project_review_notes": (
        "CREATE INDEX ix_project_review_notes_owner_project_event ON __TABLE__ (owner_id, project_id, event_id)",
    ),
    "project_review_saved_views": (
        "CREATE INDEX ix_project_review_saved_views_owner_project ON __TABLE__ (owner_id, project_id)",
        "CREATE UNIQUE INDEX uq_project_review_saved_views_active_name ON __TABLE__ (owner_id, project_id, name) WHERE deleted_at IS NULL",
    ),
    "project_review_snapshots": (
        "CREATE INDEX ix_project_review_snapshots_owner_project_completed ON __TABLE__ (owner_id, project_id, capture_completed_at)",
        "CREATE UNIQUE INDEX uq_project_review_snapshots_capture_key ON __TABLE__ (owner_id, project_id, capture_key)",
    ),
}

EXPECTED_TRIGGER_SQL = {
    "project_review_snapshots": (
        "CREATE TRIGGER project_review_snapshots_refuse_update BEFORE UPDATE ON __TABLE__ BEGIN SELECT RAISE(ABORT, 'review snapshots are immutable'); END",
        "CREATE TRIGGER project_review_snapshots_refuse_delete BEFORE DELETE ON __TABLE__ BEGIN SELECT RAISE(ABORT, 'review snapshots are immutable'); END",
    ),
}

DOWNGRADE_DDL = {
    "project_review_notes": """CREATE TABLE __TABLE__ (
        note_id VARCHAR(64) NOT NULL PRIMARY KEY, project_id VARCHAR(64) NOT NULL,
        event_id VARCHAR(200) NOT NULL, event_type VARCHAR(32) NOT NULL, body TEXT NOT NULL,
        created_by VARCHAR(32) NOT NULL, revision INTEGER NOT NULL DEFAULT '0', deleted_at DATETIME,
        created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
        CONSTRAINT ck_review_note_event_id CHECK (length(event_id) BETWEEN 1 AND 200),
        CONSTRAINT ck_review_note_event_type CHECK (event_type IN ('graph_version_published', 'experiment_run', 'finding_created', 'candidate_created', 'candidate_decided')),
        CONSTRAINT ck_review_note_body CHECK (length(body) BETWEEN 1 AND 4000),
        CONSTRAINT ck_review_note_owner CHECK (created_by = 'owner'),
        CONSTRAINT ck_review_note_revision CHECK (revision >= 0)
    )""",
    "project_review_saved_views": """CREATE TABLE __TABLE__ (
        view_id VARCHAR(64) NOT NULL PRIMARY KEY, project_id VARCHAR(64) NOT NULL,
        name VARCHAR(80) NOT NULL, filters_json TEXT NOT NULL, created_by VARCHAR(32) NOT NULL,
        revision INTEGER NOT NULL DEFAULT '0', deleted_at DATETIME, created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL, FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
        CONSTRAINT ck_review_view_name CHECK (length(name) BETWEEN 1 AND 80),
        CONSTRAINT ck_review_view_filters_json CHECK (json_valid(filters_json)),
        CONSTRAINT ck_review_view_owner CHECK (created_by = 'owner'),
        CONSTRAINT ck_review_view_revision CHECK (revision >= 0)
    )""",
    "project_review_snapshots": """CREATE TABLE __TABLE__ (
        snapshot_id VARCHAR(64) NOT NULL PRIMARY KEY, project_id VARCHAR(64) NOT NULL,
        label VARCHAR(80) NOT NULL, capture_key VARCHAR(36) NOT NULL, manifest_json TEXT NOT NULL,
        content_address VARCHAR(71) NOT NULL, created_by VARCHAR(32) NOT NULL,
        capture_started_at DATETIME NOT NULL, capture_completed_at DATETIME NOT NULL,
        FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,
        CONSTRAINT ck_review_snapshot_label CHECK (length(label) BETWEEN 1 AND 80),
        CONSTRAINT ck_review_snapshot_capture_key CHECK (length(capture_key) = 36),
        CONSTRAINT ck_review_snapshot_owner CHECK (created_by = 'owner'),
        CONSTRAINT ck_review_snapshot_manifest_json CHECK (json_valid(manifest_json)),
        CONSTRAINT ck_review_snapshot_schema_version CHECK (json_extract(manifest_json, '$.schema_version') = 1),
        CONSTRAINT ck_review_snapshot_project_matches_json CHECK (json_extract(manifest_json, '$.project_id') IS project_id),
        CONSTRAINT ck_review_snapshot_capture_window CHECK (capture_completed_at >= capture_started_at)
    )""",
}


def _names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _foreign_keys_enabled() -> bool:
    raw = op.get_bind().connection.driver_connection
    return bool(raw.execute("PRAGMA foreign_keys").fetchone()[0])


def _foreign_keys(enabled: bool) -> None:
    raw = op.get_bind().connection.driver_connection
    raw.commit()
    raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def _ensure_proofs() -> None:
    op.get_bind().execute(sa.text(
        f"CREATE TABLE IF NOT EXISTS {PROOF_TABLE} ("
        "table_name VARCHAR(64) NOT NULL PRIMARY KEY, row_count INTEGER NOT NULL, "
        "row_digest VARCHAR(64) NOT NULL, direction VARCHAR(8) NOT NULL, schema_digest VARCHAR(64) NOT NULL, "
        "phase VARCHAR(16) NOT NULL)"
    ))


def _row_proof(table: str) -> tuple[int, str]:
    rows = op.get_bind().execute(sa.text(f"SELECT * FROM {table} ORDER BY rowid")).all()
    return _rows_proof(rows)


def _rows_proof(rows) -> tuple[int, str]:
    canonical = json.dumps([list(row) for row in rows], default=str, separators=(",", ":"))
    return len(rows), hashlib.sha256(canonical.encode()).hexdigest()


def _upgrade_source_proof(table: str, columns: str) -> tuple[int, str]:
    """Bind the rebuilt bytes to the authoritative 0021 rows before DROP."""
    source_columns = ",".join(f"review.{column}" for column in columns.split(","))
    rows = op.get_bind().execute(sa.text(
        f"SELECT project.owner_id,{source_columns} FROM {table} AS review "
        "JOIN projects AS project ON project.project_id=review.project_id "
        "ORDER BY review.rowid"
    )).all()
    return _rows_proof(rows)


def _write_proof(table: str, *, direction: str, expected: tuple[int, str]) -> None:
    _ensure_proofs()
    count, digest = expected
    logical_table = table.removesuffix("__0022")
    op.get_bind().execute(sa.text(
        f"INSERT OR REPLACE INTO {PROOF_TABLE} "
        "(table_name,row_count,row_digest,direction,schema_digest,phase) "
        "VALUES (:table,:count,:row_digest,:direction,:schema_digest,'built')"
    ), {
        "table": logical_table,
        "count": count,
        "row_digest": digest,
        "direction": direction,
        "schema_digest": _digest((UPGRADE_DDL if direction == "up" else DOWNGRADE_DDL)[logical_table]),
    })


def _discard_proof(table: str) -> None:
    if PROOF_TABLE in _names():
        op.get_bind().execute(sa.text(f"DELETE FROM {PROOF_TABLE} WHERE table_name=:table"), {"table": table})


def _clear_proofs() -> None:
    """Remove migration bookkeeping once every rebuild reached its named table."""
    if PROOF_TABLE in _names() and op.get_bind().execute(
        sa.text(f"SELECT COUNT(*) FROM {PROOF_TABLE}")
    ).scalar_one() == 0:
        op.execute(sa.text(f"DROP TABLE {PROOF_TABLE}"))


def _prove_temp(table: str, temporary: str, *, direction: str) -> None:
    if PROOF_TABLE not in _names():
        raise RuntimeError(f"0022 upgrade refused: unproven completed rebuild for {table}")
    proof = op.get_bind().execute(sa.text(
        f"SELECT row_count,row_digest,direction,schema_digest,phase FROM {PROOF_TABLE} WHERE table_name=:table"
    ), {"table": table}).one_or_none()
    if proof is None:
        raise RuntimeError(f"0022 upgrade refused: unproven completed rebuild for {table}")
    ddl = UPGRADE_DDL if direction == "up" else DOWNGRADE_DDL
    if proof.phase != "built" or proof.direction != direction or proof.schema_digest != _digest(ddl[table]):
        raise RuntimeError(f"0022 upgrade refused: malformed completed rebuild proof for {table}")
    expected_columns = OWNER_COLUMNS if direction == "up" else LEGACY_COLUMNS
    if tuple(item["name"] for item in sa.inspect(op.get_bind()).get_columns(temporary)) != expected_columns[table]:
        raise RuntimeError(f"0022 upgrade refused: malformed completed rebuild for {table}")
    if _row_proof(temporary) != (proof.row_count, proof.row_digest):
        raise RuntimeError(f"0022 upgrade refused: completed rebuild payload proof failed for {table}")


def _recover(table: str, *, direction: str) -> None:
    temporary = f"{table}__0022"
    names = _names()
    if table in names and temporary in names:
        op.execute(sa.text(f"DROP TABLE {temporary}"))
        _discard_proof(table)
    elif table not in names and temporary in names:
        temp_direction = "up" if "owner_id" in {
            item["name"] for item in sa.inspect(op.get_bind()).get_columns(temporary)
        } else "down"
        _prove_temp(table, temporary, direction=temp_direction)
        if temp_direction == "up":
            _validate_rebuild_temp(table, temporary)
            _finalize_temp(table, temporary)
            _validate_final_temp(table, temporary)
        else:
            _validate_legacy_temp(table, temporary)
        op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))
        _discard_proof(table)


def _recover_all(*, direction: str) -> None:
    for table in TABLES:
        _recover(table, direction=direction)


def _indexes_and_triggers() -> None:
    # SQLite rewrites catalogue SQL during ALTER TABLE RENAME.  Recreate the
    # named objects on the final table so fresh and upgraded databases have the
    # same contract, including partial-index predicates and trigger SQL.
    for name in (
        "ix_project_review_notes_owner_project_event",
        "ix_project_review_saved_views_owner_project",
        "uq_project_review_saved_views_active_name",
        "ix_project_review_snapshots_owner_project_completed",
        "uq_project_review_snapshots_capture_key",
    ):
        op.execute(sa.text(f"DROP INDEX IF EXISTS {name}"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_project_review_notes_owner_project_event ON project_review_notes (owner_id, project_id, event_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_project_review_saved_views_owner_project ON project_review_saved_views (owner_id, project_id)"))
    op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_project_review_saved_views_active_name ON project_review_saved_views (owner_id, project_id, name) WHERE deleted_at IS NULL"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_project_review_snapshots_owner_project_completed ON project_review_snapshots (owner_id, project_id, capture_completed_at)"))
    op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_project_review_snapshots_capture_key ON project_review_snapshots (owner_id, project_id, capture_key)"))
    for name, operation in (("project_review_snapshots_refuse_update", "UPDATE"),
                            ("project_review_snapshots_refuse_delete", "DELETE")):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
        op.execute(sa.text(
            f"CREATE TRIGGER {name} BEFORE {operation} ON project_review_snapshots BEGIN "
            "SELECT RAISE(ABORT, 'review snapshots are immutable'); END"))


def _finalize_temp(table: str, temporary: str) -> None:
    if table == "project_review_notes":
        op.execute(sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_project_review_notes_owner_project_event ON {temporary} (owner_id, project_id, event_id)"))
    elif table == "project_review_saved_views":
        op.execute(sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_project_review_saved_views_owner_project ON {temporary} (owner_id, project_id)"))
        op.execute(sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS uq_project_review_saved_views_active_name ON {temporary} (owner_id, project_id, name) WHERE deleted_at IS NULL"))
    else:
        op.execute(sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_project_review_snapshots_owner_project_completed ON {temporary} (owner_id, project_id, capture_completed_at)"))
        op.execute(sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS uq_project_review_snapshots_capture_key ON {temporary} (owner_id, project_id, capture_key)"))
        for name, operation in (("project_review_snapshots_refuse_update", "UPDATE"),
                                ("project_review_snapshots_refuse_delete", "DELETE")):
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
            op.execute(sa.text(
                f"CREATE TRIGGER {name} BEFORE {operation} ON {temporary} BEGIN "
                "SELECT RAISE(ABORT, 'review snapshots are immutable'); END"))


def _catalogue_sql(kind: str, table: str) -> dict[str, str]:
    rows = op.get_bind().execute(sa.text(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type=:kind AND tbl_name=:table AND sql IS NOT NULL"
    ), {"kind": kind, "table": table}).all()
    return {row.name: _canonical_sql(row.sql) for row in rows}


def _index_name(sql: str) -> str:
    match = re.search(r"\bINDEX\s+(\w+)", sql, flags=re.IGNORECASE)
    if match is None:  # pragma: no cover - fixed migration-local DDL
        raise AssertionError(f"index DDL has no name: {sql}")
    return match.group(1)


def _validate_rebuild_temp(table: str, temporary: str) -> None:
    """Read-only validation required before a source-absent temp can be touched."""
    inspector = sa.inspect(op.get_bind())
    actual_table_sql = op.get_bind().execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"
    ), {"table": temporary}).scalar_one_or_none()
    if actual_table_sql is None or _canonical_sql(actual_table_sql) != _canonical_sql(
        UPGRADE_DDL[table].replace("__TABLE__", temporary)
    ):
        raise RuntimeError(f"0022 upgrade refused: malformed completed rebuild for {table}")
    # The catalogue statement above is the exact contract.  Keep the reflection
    # checks explicit as a defence against SQLite catalogue quirks.
    expected_pk = ("owner_id", {"project_review_notes": "note_id", "project_review_saved_views": "view_id", "project_review_snapshots": "snapshot_id"}[table])
    if tuple(inspector.get_pk_constraint(temporary)["constrained_columns"]) != expected_pk:
        raise RuntimeError(f"0022 upgrade refused: malformed completed rebuild for {table}")
    foreign_keys = inspector.get_foreign_keys(temporary)
    if not any(tuple(fk["constrained_columns"]) == ("owner_id", "project_id") and
               tuple(fk["referred_columns"]) == ("owner_id", "project_id") and
               fk["options"].get("ondelete") == "RESTRICT" for fk in foreign_keys):
        raise RuntimeError(f"0022 upgrade refused: malformed completed rebuild for {table}")
    if op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).first() is not None:
        raise RuntimeError(f"0022 upgrade refused: completed rebuild foreign-key check failed for {table}")


def _validate_final_temp(table: str, temporary: str) -> None:
    """Require all migration-owned indexes and snapshot triggers after finalization."""
    _validate_rebuild_temp(table, temporary)
    expected_indexes = {
        _index_name(sql): _canonical_sql(sql.replace("__TABLE__", temporary))
        for sql in EXPECTED_INDEX_SQL[table]
    }
    if _catalogue_sql("index", temporary) != expected_indexes:
        raise RuntimeError(f"0022 upgrade refused: malformed completed rebuild for {table}")
    expected_triggers = {
        sql.split()[2]: _canonical_sql(sql.replace("__TABLE__", temporary))
        for sql in EXPECTED_TRIGGER_SQL.get(table, ())
    }
    if _catalogue_sql("trigger", temporary) != expected_triggers:
        raise RuntimeError(f"0022 upgrade refused: malformed completed rebuild for {table}")


def _validate_legacy_temp(table: str, temporary: str) -> None:
    actual_table_sql = op.get_bind().execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"
    ), {"table": temporary}).scalar_one_or_none()
    if actual_table_sql is None or _canonical_sql(actual_table_sql) != _canonical_sql(
        DOWNGRADE_DDL[table].replace("__TABLE__", temporary)
    ):
        raise RuntimeError(f"0022 downgrade refused: malformed completed rebuild for {table}")
    inspector = sa.inspect(op.get_bind())
    identity = {"project_review_notes": "note_id", "project_review_saved_views": "view_id", "project_review_snapshots": "snapshot_id"}[table]
    if tuple(inspector.get_pk_constraint(temporary)["constrained_columns"]) != (identity,):
        raise RuntimeError(f"0022 downgrade refused: malformed completed rebuild for {table}")
    if not any(tuple(fk["constrained_columns"]) == ("project_id",) and
               tuple(fk["referred_columns"]) == ("project_id",) and
               fk["options"].get("ondelete") == "RESTRICT"
               for fk in inspector.get_foreign_keys(temporary)):
        raise RuntimeError(f"0022 downgrade refused: malformed completed rebuild for {table}")
    if op.get_bind().execute(sa.text("PRAGMA foreign_key_check")).first() is not None:
        raise RuntimeError(f"0022 downgrade refused: completed rebuild foreign-key check failed for {table}")


def _legacy_indexes_and_triggers() -> None:
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_project_review_notes_project_event ON project_review_notes (project_id, event_id)"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_project_review_saved_views_project ON project_review_saved_views (project_id)"))
    op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_project_review_saved_views_active_name ON project_review_saved_views (project_id, name) WHERE deleted_at IS NULL"))
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_project_review_snapshots_project_completed ON project_review_snapshots (project_id, capture_completed_at)"))
    op.execute(sa.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_project_review_snapshots_capture_key ON project_review_snapshots (project_id, capture_key)"))
    for name, operation in (("project_review_snapshots_refuse_update", "UPDATE"),
                            ("project_review_snapshots_refuse_delete", "DELETE")):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
        op.execute(sa.text(
            f"CREATE TRIGGER {name} BEFORE {operation} ON project_review_snapshots BEGIN "
            "SELECT RAISE(ABORT, 'review snapshots are immutable'); END"))


def _assert_no_dangling_source(table: str) -> None:
    if op.get_bind().execute(sa.text(
        f"SELECT 1 FROM {table} AS review LEFT JOIN projects AS project "
        "ON project.project_id = review.project_id WHERE project.project_id IS NULL LIMIT 1"
    )).scalar() is not None:
        raise RuntimeError(f"0022 upgrade refused: {table} contains a dangling project")


def _rebuild_upgrade(table: str, columns: str) -> None:
    if table not in _names():
        return
    if "owner_id" in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}:
        return
    _assert_no_dangling_source(table)
    expected_proof = _upgrade_source_proof(table, columns)
    temporary = f"{table}__0022"
    op.execute(sa.text(UPGRADE_DDL[table].replace("__TABLE__", temporary)))
    op.execute(sa.text(
        f"INSERT INTO {temporary} (owner_id,{columns}) "
        f"SELECT project.owner_id,review.{columns.replace(',', ',review.')} "
        f"FROM {table} AS review JOIN projects AS project ON project.project_id=review.project_id"
    ))
    if _row_proof(temporary) != expected_proof:
        raise RuntimeError(f"0022 upgrade refused: {table} source payload proof failed")
    _validate_rebuild_temp(table, temporary)
    _write_proof(temporary, direction="up", expected=expected_proof)
    op.execute(sa.text(f"DROP TABLE {table}"))
    _finalize_temp(table, temporary)
    _validate_final_temp(table, temporary)
    op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))
    _discard_proof(table)


def _downgrade_preflight() -> None:
    """Reject impossible legacy rows before recovery, PRAGMAs, or any DDL.

    A source table remains authoritative over a same-named temporary table.  If
    only the temporary table survives, its durable payload proof makes it the
    authoritative 0022 state for this read-only decision; recovery happens
    only after the decision succeeds.
    """
    if "projects" not in _names():
        # A lower migration can be resuming its own completed projects rebuild.
        # It will restore the parent before any review ownership is queried.
        return
    for table in TABLES:
        temporary = f"{table}__0022"
        names = _names()
        authoritative = table if table in names else temporary if temporary in names else None
        if authoritative is None:
            continue
        if authoritative == temporary:
            temp_direction = "up" if "owner_id" in {
                item["name"] for item in sa.inspect(op.get_bind()).get_columns(temporary)
            } else "down"
            _prove_temp(table, temporary, direction=temp_direction)
            if temp_direction == "up":
                _validate_rebuild_temp(table, temporary)
            else:
                _validate_legacy_temp(table, temporary)
        if "owner_id" not in {
            item["name"] for item in sa.inspect(op.get_bind()).get_columns(authoritative)
        }:
            continue
        if op.get_bind().execute(sa.text(
            f"SELECT 1 FROM {authoritative} AS review LEFT JOIN projects AS project "
            "ON project.project_id=review.project_id "
            "WHERE project.project_id IS NULL OR review.owner_id != project.owner_id LIMIT 1"
        )).scalar() is not None:
            raise RuntimeError("review ownership downgrade refused: rows cannot be represented by 0021")


def _rebuild_downgrade(table: str, columns: str) -> None:
    if table not in _names() or "owner_id" not in {
        item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)
    }:
        return
    temporary = f"{table}__0022"
    expected_proof = _rows_proof(op.get_bind().execute(sa.text(
        f"SELECT {columns} FROM {table} ORDER BY rowid"
    )).all())
    op.execute(sa.text(DOWNGRADE_DDL[table].replace("__TABLE__", temporary)))
    op.execute(sa.text(f"INSERT INTO {temporary} ({columns}) SELECT {columns} FROM {table}"))
    if _row_proof(temporary) != expected_proof:
        raise RuntimeError(f"0022 downgrade refused: {table} source payload proof failed")
    _validate_legacy_temp(table, temporary)
    _write_proof(temporary, direction="down", expected=expected_proof)
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))
    _discard_proof(table)


def upgrade() -> None:
    enabled = _foreign_keys_enabled()
    _foreign_keys(False)
    try:
        _recover_all(direction="up")
        _rebuild_upgrade("project_review_notes", "note_id,project_id,event_id,event_type,body,created_by,revision,deleted_at,created_at,updated_at")
        _rebuild_upgrade("project_review_saved_views", "view_id,project_id,name,filters_json,created_by,revision,deleted_at,created_at,updated_at")
        _rebuild_upgrade("project_review_snapshots", "snapshot_id,project_id,label,capture_key,manifest_json,content_address,created_by,capture_started_at,capture_completed_at")
        _indexes_and_triggers()
        _clear_proofs()
    finally:
        _foreign_keys(enabled)


def downgrade() -> None:
    # Do not recover a stale temporary table or even change FK mode until the
    # authoritative physical state is known to be representable by 0021.
    _downgrade_preflight()
    enabled = _foreign_keys_enabled()
    _foreign_keys(False)
    try:
        _recover_all(direction="down")
        _rebuild_downgrade("project_review_notes", "note_id,project_id,event_id,event_type,body,created_by,revision,deleted_at,created_at,updated_at")
        _rebuild_downgrade("project_review_saved_views", "view_id,project_id,name,filters_json,created_by,revision,deleted_at,created_at,updated_at")
        _rebuild_downgrade("project_review_snapshots", "snapshot_id,project_id,label,capture_key,manifest_json,content_address,created_by,capture_started_at,capture_completed_at")
        _legacy_indexes_and_triggers()
    finally:
        _foreign_keys(enabled)
