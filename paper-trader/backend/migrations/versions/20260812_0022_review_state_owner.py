"""own project review persistence by tenant

Revision ID: 0022
Revises: 0021
"""
from __future__ import annotations

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


def _recover(table: str) -> None:
    temporary = f"{table}__0022"
    names = _names()
    if table in names and temporary in names:
        op.execute(sa.text(f"DROP TABLE {temporary}"))
    elif table not in names and temporary in names:
        op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))


def _recover_all() -> None:
    for table in TABLES:
        _recover(table)


def _indexes_and_triggers() -> None:
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
    source_count = op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
    temporary = f"{table}__0022"
    op.execute(sa.text(UPGRADE_DDL[table].replace("__TABLE__", temporary)))
    op.execute(sa.text(
        f"INSERT INTO {temporary} (owner_id,{columns}) "
        f"SELECT project.owner_id,review.{columns.replace(',', ',review.')} "
        f"FROM {table} AS review JOIN projects AS project ON project.project_id=review.project_id"
    ))
    if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {temporary}")).scalar_one() != source_count:
        raise RuntimeError(f"0022 upgrade refused: {table} row preservation failed")
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))


def _downgrade_refusal() -> None:
    if "projects" not in _names():
        # A lower migration can be resuming its own completed projects rebuild.
        # It will restore the parent before any review ownership is queried.
        return
    for table in TABLES:
        if table not in _names() or "owner_id" not in {
            item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)
        }:
            continue
        if op.get_bind().execute(sa.text(
            f"SELECT 1 FROM {table} AS review LEFT JOIN projects AS project "
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
    op.execute(sa.text(DOWNGRADE_DDL[table].replace("__TABLE__", temporary)))
    op.execute(sa.text(f"INSERT INTO {temporary} ({columns}) SELECT {columns} FROM {table}"))
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))


def upgrade() -> None:
    enabled = _foreign_keys_enabled()
    _foreign_keys(False)
    try:
        _recover_all()
        _rebuild_upgrade("project_review_notes", "note_id,project_id,event_id,event_type,body,created_by,revision,deleted_at,created_at,updated_at")
        _rebuild_upgrade("project_review_saved_views", "view_id,project_id,name,filters_json,created_by,revision,deleted_at,created_at,updated_at")
        _rebuild_upgrade("project_review_snapshots", "snapshot_id,project_id,label,capture_key,manifest_json,content_address,created_by,capture_started_at,capture_completed_at")
        _indexes_and_triggers()
    finally:
        _foreign_keys(enabled)


def downgrade() -> None:
    enabled = _foreign_keys_enabled()
    _foreign_keys(False)
    try:
        _recover_all()
        _downgrade_refusal()
        _rebuild_downgrade("project_review_notes", "note_id,project_id,event_id,event_type,body,created_by,revision,deleted_at,created_at,updated_at")
        _rebuild_downgrade("project_review_saved_views", "view_id,project_id,name,filters_json,created_by,revision,deleted_at,created_at,updated_at")
        _rebuild_downgrade("project_review_snapshots", "snapshot_id,project_id,label,capture_key,manifest_json,content_address,created_by,capture_started_at,capture_completed_at")
        _legacy_indexes_and_triggers()
    finally:
        _foreign_keys(enabled)
