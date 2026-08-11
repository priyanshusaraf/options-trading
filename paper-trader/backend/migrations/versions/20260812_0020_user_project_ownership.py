"""Own project roots and record private graph-version provenance."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

LEGACY_OWNER_ID = "owner"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _foreign_keys(enabled: bool) -> None:
    raw = op.get_bind().connection.driver_connection
    raw.commit()
    raw.execute(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def _recover(table: str) -> None:
    temporary = f"{table}__0020"
    names = _tables()
    if table in names and temporary in names:
        op.execute(sa.text(f"DROP TABLE {temporary}"))
    elif table not in names and temporary in names:
        op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))


def _project_indexes() -> None:
    op.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_projects_owner_id ON projects (owner_id)"))


def _graph_triggers() -> None:
    for name, operation in (("graph_versions_refuse_update", "UPDATE"),
                            ("graph_versions_refuse_delete", "DELETE")):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
        op.execute(sa.text(
            f"CREATE TRIGGER {name} BEFORE {operation} ON graph_versions BEGIN "
            "SELECT RAISE(ABORT, 'graph versions are immutable'); END"))


def _upgrade_projects() -> None:
    _recover("projects")
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("projects")}
    if "owner_id" in columns:
        _project_indexes()
        return
    op.execute(sa.text("""
        CREATE TABLE projects__0020 (
            project_id VARCHAR(64) NOT NULL PRIMARY KEY,
            owner_id VARCHAR(64) NOT NULL,
            name VARCHAR(128) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status VARCHAR(16) NOT NULL DEFAULT 'active',
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            CONSTRAINT ck_projects_status CHECK (status IN ('active', 'archived')),
            CONSTRAINT uq_projects_owner_name UNIQUE (owner_id, name),
            FOREIGN KEY(owner_id) REFERENCES organizations (organization_id) ON DELETE RESTRICT
        )
    """))
    op.execute(sa.text("""
        INSERT INTO projects__0020
        (project_id, owner_id, name, description, status, created_at, updated_at)
        SELECT project_id, 'owner', name, description, status, created_at, updated_at FROM projects
    """))
    op.execute(sa.text("DROP TABLE projects"))
    op.execute(sa.text("ALTER TABLE projects__0020 RENAME TO projects"))
    _project_indexes()


def _upgrade_graph_versions() -> None:
    _recover("graph_versions")
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("graph_versions")}
    if "visibility" in columns:
        _graph_triggers()
        return
    op.execute(sa.text("""
        CREATE TABLE graph_versions__0020 (
            graph_identifier VARCHAR(128) NOT NULL,
            version INTEGER NOT NULL,
            artifact_json TEXT NOT NULL,
            content_address VARCHAR(71) NOT NULL,
            visibility VARCHAR(16) NOT NULL DEFAULT 'PRIVATE',
            created_at DATETIME NOT NULL,
            PRIMARY KEY (graph_identifier, version),
            FOREIGN KEY(graph_identifier) REFERENCES graph_artifacts (identifier) ON DELETE RESTRICT,
            CONSTRAINT ck_graph_versions_version CHECK (version >= 1),
            CONSTRAINT ck_graph_versions_valid_json CHECK (json_valid(artifact_json)),
            CONSTRAINT ck_graph_versions_identifier_matches_json CHECK (json_extract(artifact_json, '$.identifier') IS graph_identifier),
            CONSTRAINT ck_graph_versions_version_matches_json CHECK (json_extract(artifact_json, '$.version') IS version),
            CONSTRAINT ck_graph_versions_private_visibility CHECK (visibility = 'PRIVATE')
        )
    """))
    op.execute(sa.text("""
        INSERT INTO graph_versions__0020
        (graph_identifier, version, artifact_json, content_address, visibility, created_at)
        SELECT graph_identifier, version, artifact_json, content_address, 'PRIVATE', created_at
        FROM graph_versions
    """))
    op.execute(sa.text("DROP TABLE graph_versions"))
    op.execute(sa.text("ALTER TABLE graph_versions__0020 RENAME TO graph_versions"))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_graph_versions_content_address ON graph_versions (content_address)"))
    _graph_triggers()


def upgrade() -> None:
    _foreign_keys(False)
    try:
        _upgrade_projects()
        _upgrade_graph_versions()
    finally:
        _foreign_keys(True)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text(
        "SELECT 1 FROM projects WHERE owner_id != :owner LIMIT 1"), {"owner": LEGACY_OWNER_ID}
    ).scalar() is not None:
        raise RuntimeError("project ownership downgrade refused: non-legacy owner would be lost")
    _foreign_keys(False)
    _recover("projects")
    _recover("graph_versions")
    op.execute(sa.text("""
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
    """))
    op.execute(sa.text("INSERT INTO graph_versions__0019 (graph_identifier,version,artifact_json,content_address,created_at) SELECT graph_identifier,version,artifact_json,content_address,created_at FROM graph_versions"))
    op.execute(sa.text("DROP TABLE graph_versions"))
    op.execute(sa.text("ALTER TABLE graph_versions__0019 RENAME TO graph_versions"))
    op.execute(sa.text("CREATE INDEX ix_graph_versions_content_address ON graph_versions (content_address)"))
    _graph_triggers()
    op.execute(sa.text("""
        CREATE TABLE projects__0019 (
            project_id VARCHAR(64) NOT NULL PRIMARY KEY, name VARCHAR(128) NOT NULL,
            description TEXT NOT NULL DEFAULT '', status VARCHAR(16) NOT NULL DEFAULT 'active',
            created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
            CONSTRAINT ck_projects_status CHECK (status IN ('active', 'archived'))
        )
    """))
    op.execute(sa.text("INSERT INTO projects__0019 (project_id,name,description,status,created_at,updated_at) SELECT project_id,name,description,status,created_at,updated_at FROM projects"))
    op.execute(sa.text("DROP TABLE projects"))
    op.execute(sa.text("ALTER TABLE projects__0019 RENAME TO projects"))
    _foreign_keys(True)
