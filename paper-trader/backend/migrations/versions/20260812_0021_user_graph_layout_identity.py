"""Scope graph and presentation identities by their USER-plane owner."""
from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

LEGACY_OWNER_ID = "owner"

REBUILD_TABLES = (
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

# 0021 owns these historical MONEY rebuilds.  Do not import current ORM metadata:
# a retry must restore the 0020 authority indexes even after later model changes.
MONEY_INDEX_MANIFEST = {
    "ir_paper_deployments": (
        "CREATE INDEX ix_ir_paper_deployments_state ON ir_paper_deployments (state)",
        "CREATE INDEX ix_ir_paper_deployments_project_id ON ir_paper_deployments (project_id)",
        "CREATE INDEX ix_ir_paper_deployments_deployment_id ON ir_paper_deployments (deployment_id)",
        "CREATE INDEX ix_ir_paper_deployments_instrument_key ON ir_paper_deployments (instrument_key)",
        "CREATE INDEX ix_ir_paper_deployments_owner_id ON ir_paper_deployments (owner_id)",
        "CREATE INDEX ix_ir_paper_deployments_owner_account ON ir_paper_deployments (owner_id, broker_account_id)",
        "CREATE UNIQUE INDEX uq_ir_paper_deployment_active ON ir_paper_deployments (deployment_id, instrument_key, interval) WHERE state IN ('staged','paper_active','paused')",
    ),
    "ir_shadow_deployments": (
        "CREATE INDEX ix_ir_shadow_deployments_state ON ir_shadow_deployments (state)",
        "CREATE INDEX ix_ir_shadow_deployments_project_id ON ir_shadow_deployments (project_id)",
        "CREATE INDEX ix_ir_shadow_deployments_deployment_id ON ir_shadow_deployments (deployment_id)",
        "CREATE INDEX ix_ir_shadow_deployments_instrument_key ON ir_shadow_deployments (instrument_key)",
        "CREATE INDEX ix_ir_shadow_deployments_owner_id ON ir_shadow_deployments (owner_id)",
        "CREATE INDEX ix_ir_shadow_deployments_owner_account ON ir_shadow_deployments (owner_id, broker_account_id)",
        "CREATE UNIQUE INDEX uq_ir_shadow_deployment_active ON ir_shadow_deployments (deployment_id, instrument_key, interval) WHERE state IN ('staged','shadow_active','paused')",
    ),
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
    temporary = f"{table}__0021"
    names = _names()
    if table in names and temporary in names:
        op.execute(sa.text(f"DROP TABLE {temporary}"))
    elif table not in names and temporary in names:
        op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))


def _recover_all() -> None:
    """Promote completed rebuilds before inspecting source-revision columns."""
    for table in REBUILD_TABLES:
        _recover(table)


def _restore_money_indexes(table: str) -> None:
    """Restore 0020 MONEY authority indexes without changing their SQL text."""
    bind = op.get_bind()
    existing = set(bind.execute(sa.text(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=:table"
    ), {"table": table}).scalars())
    for ddl in MONEY_INDEX_MANIFEST[table]:
        name = re.search(r"INDEX\s+([A-Za-z0-9_]+)\s+ON", ddl, flags=re.I).group(1)
        if name not in existing:
            op.execute(sa.text(ddl))
            existing.add(name)


def _rebuild(table: str, ddl: str, columns: str, select: str) -> None:
    _recover(table)
    if "owner_id" in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}:
        return
    temporary = f"{table}__0021"
    op.execute(sa.text(ddl.replace("__TABLE__", temporary)))
    op.execute(sa.text(
        f"INSERT INTO {temporary} ({columns}) SELECT {select} FROM {table}"))
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))


def _indexes_and_triggers() -> None:
    names = _names()
    if "projects" in names:
        op.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_projects_owner_id ON projects (owner_id)"))
    if "graph_artifacts" in names:
        op.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_graph_artifacts_project_id ON graph_artifacts (project_id)"))
    if "graph_versions" not in names:
        return
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_graph_versions_content_address ON graph_versions (content_address)"))
    for name, operation in (("graph_versions_refuse_update", "UPDATE"),
                            ("graph_versions_refuse_delete", "DELETE")):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
        op.execute(sa.text(
            f"CREATE TRIGGER {name} BEFORE {operation} ON graph_versions BEGIN "
            "SELECT RAISE(ABORT, 'graph versions are immutable'); END"))


def _upgrade_projects() -> None:
    # The global opaque id remains a primary key. This candidate key is for child FKs.
    _recover("projects")
    inspector = sa.inspect(op.get_bind())
    if any(tuple(item["column_names"]) == ("owner_id", "project_id")
           for item in inspector.get_unique_constraints("projects")):
        return
    op.execute(sa.text("""
        CREATE TABLE projects__0021 (
            project_id VARCHAR(64) NOT NULL PRIMARY KEY, owner_id VARCHAR(64) NOT NULL,
            name VARCHAR(128) NOT NULL, description TEXT NOT NULL DEFAULT '',
            status VARCHAR(16) NOT NULL DEFAULT 'active', created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            CONSTRAINT ck_projects_status CHECK (status IN ('active', 'archived')),
            CONSTRAINT uq_projects_owner_name UNIQUE (owner_id, name),
            CONSTRAINT uq_projects_owner_project UNIQUE (owner_id, project_id),
            FOREIGN KEY(owner_id) REFERENCES organizations (organization_id) ON DELETE RESTRICT
        )
    """))
    op.execute(sa.text("""
        INSERT INTO projects__0021
        (project_id,owner_id,name,description,status,created_at,updated_at)
        SELECT project_id,owner_id,name,description,status,created_at,updated_at FROM projects
    """))
    op.execute(sa.text("DROP TABLE projects"))
    op.execute(sa.text("ALTER TABLE projects__0021 RENAME TO projects"))


def _upgrade_user_graph_layouts() -> None:
    _rebuild("graph_artifacts", """
        CREATE TABLE __TABLE__ (
            owner_id VARCHAR(64) NOT NULL, identifier VARCHAR(128) NOT NULL,
            project_id VARCHAR(64) NOT NULL, display_name VARCHAR(128) NOT NULL,
            draft_json TEXT NOT NULL, draft_revision INTEGER NOT NULL DEFAULT '0',
            published_revision INTEGER, current_version INTEGER,
            created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
            PRIMARY KEY (owner_id, identifier),
            CONSTRAINT fk_graph_artifacts_owner_project FOREIGN KEY(owner_id, project_id)
                REFERENCES projects (owner_id, project_id) ON DELETE RESTRICT,
            CONSTRAINT ck_graph_artifacts_draft_revision CHECK (draft_revision >= 0),
            CONSTRAINT ck_graph_artifacts_published_revision CHECK (published_revision IS NULL OR (published_revision >= 0 AND published_revision <= draft_revision)),
            CONSTRAINT ck_graph_artifacts_publication_state CHECK ((current_version IS NULL) = (published_revision IS NULL))
        )
    """, "owner_id,identifier,project_id,display_name,draft_json,draft_revision,published_revision,current_version,created_at,updated_at",
    f"'{LEGACY_OWNER_ID}',identifier,project_id,display_name,draft_json,draft_revision,published_revision,current_version,created_at,updated_at")
    _rebuild("graph_versions", """
        CREATE TABLE __TABLE__ (
            owner_id VARCHAR(64) NOT NULL, graph_identifier VARCHAR(128) NOT NULL,
            version INTEGER NOT NULL, artifact_json TEXT NOT NULL, content_address VARCHAR(71) NOT NULL,
            visibility VARCHAR(16) NOT NULL DEFAULT 'PRIVATE', created_at DATETIME NOT NULL,
            PRIMARY KEY (owner_id,graph_identifier,version),
            FOREIGN KEY(owner_id, graph_identifier)
                REFERENCES graph_artifacts (owner_id, identifier) ON DELETE RESTRICT,
            CONSTRAINT ck_graph_versions_version CHECK (version >= 1),
            CONSTRAINT ck_graph_versions_valid_json CHECK (json_valid(artifact_json)),
            CONSTRAINT ck_graph_versions_identifier_matches_json CHECK (json_extract(artifact_json, '$.identifier') IS graph_identifier),
            CONSTRAINT ck_graph_versions_version_matches_json CHECK (json_extract(artifact_json, '$.version') IS version),
            CONSTRAINT ck_graph_versions_private_visibility CHECK (visibility = 'PRIVATE')
        )
    """, "owner_id,graph_identifier,version,artifact_json,content_address,visibility,created_at",
    f"'{LEGACY_OWNER_ID}',graph_identifier,version,artifact_json,content_address,visibility,created_at")
    _rebuild("ir_graph_layouts", """
        CREATE TABLE __TABLE__ (
            owner_id VARCHAR(64) NOT NULL, graph_identifier VARCHAR(128) NOT NULL,
            graph_version INTEGER NOT NULL, revision INTEGER NOT NULL, updated_at DATETIME NOT NULL,
            PRIMARY KEY(owner_id,graph_identifier,graph_version),
            CONSTRAINT fk_ir_graph_layouts_graph_version FOREIGN KEY(owner_id, graph_identifier, graph_version)
                REFERENCES graph_versions (owner_id, graph_identifier, version) ON DELETE RESTRICT
        )
    """, "owner_id,graph_identifier,graph_version,revision,updated_at",
    f"'{LEGACY_OWNER_ID}',graph_identifier,graph_version,revision,updated_at")
    _rebuild("ir_graph_layout_positions", """
        CREATE TABLE __TABLE__ (
            owner_id VARCHAR(64) NOT NULL, graph_identifier VARCHAR(128) NOT NULL,
            graph_version INTEGER NOT NULL, instance_id VARCHAR(128) NOT NULL,
            x FLOAT NOT NULL, y FLOAT NOT NULL,
            PRIMARY KEY(owner_id,graph_identifier,graph_version,instance_id),
            FOREIGN KEY(owner_id, graph_identifier, graph_version)
                REFERENCES ir_graph_layouts (owner_id, graph_identifier, graph_version) ON DELETE CASCADE
        )
    """, "owner_id,graph_identifier,graph_version,instance_id,x,y",
    f"'{LEGACY_OWNER_ID}',graph_identifier,graph_version,instance_id,x,y")
    _rebuild("ir_graph_layout_groups", """
        CREATE TABLE __TABLE__ (
            owner_id VARCHAR(64) NOT NULL, graph_identifier VARCHAR(128) NOT NULL,
            graph_version INTEGER NOT NULL, identifier VARCHAR(128) NOT NULL,
            display_name VARCHAR(128) NOT NULL, x FLOAT NOT NULL, y FLOAT NOT NULL,
            width FLOAT NOT NULL, height FLOAT NOT NULL, collapsed BOOLEAN NOT NULL DEFAULT 0,
            PRIMARY KEY(owner_id,graph_identifier,graph_version,identifier),
            CONSTRAINT fk_ir_graph_layout_groups_layout FOREIGN KEY(owner_id, graph_identifier, graph_version)
                REFERENCES ir_graph_layouts (owner_id, graph_identifier, graph_version) ON DELETE CASCADE,
            CONSTRAINT ck_ir_groups_identifier CHECK (length(identifier) > 0),
            CONSTRAINT ck_ir_groups_display_name CHECK (length(display_name) > 0),
            CONSTRAINT ck_ir_groups_width CHECK (width > 0),
            CONSTRAINT ck_ir_groups_height CHECK (height > 0)
        )
    """, "owner_id,graph_identifier,graph_version,identifier,display_name,x,y,width,height,collapsed",
    f"'{LEGACY_OWNER_ID}',graph_identifier,graph_version,identifier,display_name,x,y,width,height,collapsed")
    _rebuild("ir_graph_layout_group_members", """
        CREATE TABLE __TABLE__ (
            owner_id VARCHAR(64) NOT NULL, graph_identifier VARCHAR(128) NOT NULL,
            graph_version INTEGER NOT NULL, group_identifier VARCHAR(128) NOT NULL,
            instance_id VARCHAR(128) NOT NULL,
            PRIMARY KEY(owner_id,graph_identifier,graph_version,group_identifier,instance_id),
            CONSTRAINT fk_ir_graph_layout_group_members_group
                FOREIGN KEY(owner_id, graph_identifier, graph_version, group_identifier)
                REFERENCES ir_graph_layout_groups (owner_id, graph_identifier, graph_version, identifier) ON DELETE CASCADE
        )
    """, "owner_id,graph_identifier,graph_version,group_identifier,instance_id",
    f"'{LEGACY_OWNER_ID}',graph_identifier,graph_version,group_identifier,instance_id")
    _rebuild("ir_graph_layout_orphan_archive", """
        CREATE TABLE __TABLE__ (
            owner_id VARCHAR(64) NOT NULL, graph_identifier VARCHAR(128) NOT NULL,
            graph_version INTEGER NOT NULL, revision INTEGER NOT NULL, updated_at DATETIME NOT NULL,
            archived_at DATETIME NOT NULL, PRIMARY KEY(owner_id,graph_identifier,graph_version)
        )
    """, "owner_id,graph_identifier,graph_version,revision,updated_at,archived_at",
    f"'{LEGACY_OWNER_ID}',graph_identifier,graph_version,revision,updated_at,archived_at")
    _rebuild("ir_graph_layout_position_orphan_archive", """
        CREATE TABLE __TABLE__ (
            owner_id VARCHAR(64) NOT NULL, graph_identifier VARCHAR(128) NOT NULL,
            graph_version INTEGER NOT NULL, instance_id VARCHAR(128) NOT NULL,
            x FLOAT NOT NULL, y FLOAT NOT NULL,
            PRIMARY KEY(owner_id,graph_identifier,graph_version,instance_id)
        )
    """, "owner_id,graph_identifier,graph_version,instance_id,x,y",
    f"'{LEGACY_OWNER_ID}',graph_identifier,graph_version,instance_id,x,y")


def _remove_money_graph_fk(table: str) -> None:
    """Keep MONEY provenance by value while preserving every other historical guard."""
    _recover(table)
    bind = op.get_bind()
    row = bind.execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"), {"table": table}).scalar_one()
    if "graph_versions" not in row:
        _restore_money_indexes(table)
        return
    temporary = f"{table}__0021"
    indexes = bind.execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=:table AND sql IS NOT NULL"),
        {"table": table}).scalars().all()
    ddl = re.sub(r",\s*(?:CONSTRAINT\s+\S+\s+)?FOREIGN KEY\s*\(\s*graph_identifier\s*,\s*graph_version\s*\)\s*REFERENCES\s+\"?graph_versions\"?\s*\(\s*graph_identifier\s*,\s*version\s*\)\s*ON DELETE RESTRICT", "", row, flags=re.I)
    if ddl == row:
        raise RuntimeError(f"0021 could not remove {table} graph provenance foreign key")
    ddl = re.sub(r"CREATE TABLE\s+[^ (]+", f"CREATE TABLE {temporary}", ddl, count=1, flags=re.I)
    op.execute(sa.text(ddl))
    op.execute(sa.text(f"INSERT INTO {temporary} SELECT * FROM {table}"))
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))
    for index in indexes:
        op.execute(sa.text(index))
    _restore_money_indexes(table)


def _restore_money_graph_fk(table: str) -> None:
    """Restore the exact 0020 graph FK on rollback; provenance columns never move."""
    _recover(table)
    if table not in _names():
        return
    bind = op.get_bind()
    row = bind.execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"), {"table": table}).scalar_one()
    if "graph_versions" in row:
        _restore_money_indexes(table)
        return
    temporary = f"{table}__0021"
    indexes = bind.execute(sa.text(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=:table AND sql IS NOT NULL"),
        {"table": table}).scalars().all()
    ddl = re.sub(r"\)\s*$", ", FOREIGN KEY(graph_identifier, graph_version) REFERENCES graph_versions(graph_identifier, version) ON DELETE RESTRICT)", row)
    ddl = re.sub(r"CREATE TABLE\s+[^ (]+", f"CREATE TABLE {temporary}", ddl, count=1, flags=re.I)
    op.execute(sa.text(ddl))
    op.execute(sa.text(f"INSERT INTO {temporary} SELECT * FROM {table}"))
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))
    for index in indexes:
        op.execute(sa.text(index))
    _restore_money_indexes(table)


def _downgrade_refusal() -> None:
    bind = op.get_bind()
    names = _names()
    graph_columns = ({item["name"] for item in sa.inspect(bind).get_columns("graph_artifacts")}
                     if "graph_artifacts" in names else set())
    if ("owner_id" in graph_columns and bind.execute(sa.text(
            "SELECT 1 FROM graph_artifacts GROUP BY identifier HAVING COUNT(*) > 1 LIMIT 1"
    )).scalar() is not None):
        raise RuntimeError("graph/layout ownership downgrade refused: graph identifiers would collide")
    project_columns = ({item["name"] for item in sa.inspect(bind).get_columns("projects")}
                       if "projects" in names else set())
    if "projects" in names and "owner_id" in project_columns and bind.execute(sa.text(
        "SELECT 1 FROM projects GROUP BY name HAVING COUNT(*) > 1 LIMIT 1"
    )).scalar() is not None:
        raise RuntimeError("project ownership downgrade refused: tenant-local project names would collide")
    if "projects" in names and "owner_id" in project_columns and bind.execute(sa.text(
        "SELECT 1 FROM projects WHERE owner_id != :owner LIMIT 1"),
        {"owner": LEGACY_OWNER_ID},
    ).scalar() is not None:
        raise RuntimeError("project ownership downgrade refused: non-legacy owner would be lost")
    for table in ("graph_artifacts", "graph_versions", "ir_graph_layouts",
                  "ir_graph_layout_positions", "ir_graph_layout_groups",
                  "ir_graph_layout_group_members", "ir_graph_layout_orphan_archive",
                  "ir_graph_layout_position_orphan_archive"):
        if table not in names:
            continue
        if "owner_id" not in {item["name"] for item in sa.inspect(bind).get_columns(table)}:
            continue
        if bind.execute(sa.text(
            f"SELECT 1 FROM {table} WHERE owner_id != :owner LIMIT 1"),
            {"owner": LEGACY_OWNER_ID}).scalar() is not None:
            raise RuntimeError("graph/layout ownership downgrade refused: non-legacy owner would be lost")
def _downgrade_table(table: str, ddl: str, columns: str) -> None:
    temporary = f"{table}__0021"
    _recover(table)
    if table not in _names():
        return
    if "owner_id" not in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}:
        return
    op.execute(sa.text(ddl.replace("__TABLE__", temporary)))
    op.execute(sa.text(f"INSERT INTO {temporary} ({columns}) SELECT {columns} FROM {table}"))
    op.execute(sa.text(f"DROP TABLE {table}"))
    op.execute(sa.text(f"ALTER TABLE {temporary} RENAME TO {table}"))


def _downgrade_user_graph_layouts() -> None:
    _downgrade_table("ir_graph_layout_group_members", "CREATE TABLE __TABLE__ (graph_identifier VARCHAR(128) NOT NULL,graph_version INTEGER NOT NULL,group_identifier VARCHAR(128) NOT NULL,instance_id VARCHAR(128) NOT NULL,PRIMARY KEY(graph_identifier,graph_version,group_identifier,instance_id),CONSTRAINT fk_ir_graph_layout_group_members_group FOREIGN KEY(graph_identifier,graph_version,group_identifier) REFERENCES ir_graph_layout_groups(graph_identifier,graph_version,identifier) ON DELETE CASCADE)", "graph_identifier,graph_version,group_identifier,instance_id")
    _downgrade_table("ir_graph_layout_groups", "CREATE TABLE __TABLE__ (graph_identifier VARCHAR(128) NOT NULL,graph_version INTEGER NOT NULL,identifier VARCHAR(128) NOT NULL,display_name VARCHAR(128) NOT NULL,x FLOAT NOT NULL,y FLOAT NOT NULL,width FLOAT NOT NULL,height FLOAT NOT NULL,collapsed BOOLEAN NOT NULL DEFAULT 0,PRIMARY KEY(graph_identifier,graph_version,identifier),CONSTRAINT fk_ir_graph_layout_groups_layout FOREIGN KEY(graph_identifier,graph_version) REFERENCES ir_graph_layouts(graph_identifier,graph_version) ON DELETE CASCADE,CONSTRAINT ck_ir_groups_identifier CHECK(length(identifier)>0),CONSTRAINT ck_ir_groups_display_name CHECK(length(display_name)>0),CONSTRAINT ck_ir_groups_width CHECK(width>0),CONSTRAINT ck_ir_groups_height CHECK(height>0))", "graph_identifier,graph_version,identifier,display_name,x,y,width,height,collapsed")
    _downgrade_table("ir_graph_layout_positions", "CREATE TABLE __TABLE__ (graph_identifier VARCHAR(128) NOT NULL,graph_version INTEGER NOT NULL,instance_id VARCHAR(128) NOT NULL,x FLOAT NOT NULL,y FLOAT NOT NULL,PRIMARY KEY(graph_identifier,graph_version,instance_id),FOREIGN KEY(graph_identifier,graph_version) REFERENCES ir_graph_layouts(graph_identifier,graph_version) ON DELETE CASCADE)", "graph_identifier,graph_version,instance_id,x,y")
    _downgrade_table("ir_graph_layouts", "CREATE TABLE __TABLE__ (graph_identifier VARCHAR(128) NOT NULL,graph_version INTEGER NOT NULL,revision INTEGER NOT NULL,updated_at DATETIME NOT NULL,PRIMARY KEY(graph_identifier,graph_version),CONSTRAINT fk_ir_graph_layouts_graph_version FOREIGN KEY(graph_identifier,graph_version) REFERENCES graph_versions(graph_identifier,version) ON DELETE RESTRICT)", "graph_identifier,graph_version,revision,updated_at")
    _downgrade_table("ir_graph_layout_position_orphan_archive", "CREATE TABLE __TABLE__ (graph_identifier VARCHAR(128) NOT NULL,graph_version INTEGER NOT NULL,instance_id VARCHAR(128) NOT NULL,x FLOAT NOT NULL,y FLOAT NOT NULL,PRIMARY KEY(graph_identifier,graph_version,instance_id))", "graph_identifier,graph_version,instance_id,x,y")
    _downgrade_table("ir_graph_layout_orphan_archive", "CREATE TABLE __TABLE__ (graph_identifier VARCHAR(128) NOT NULL,graph_version INTEGER NOT NULL,revision INTEGER NOT NULL,updated_at DATETIME NOT NULL,archived_at DATETIME NOT NULL,PRIMARY KEY(graph_identifier,graph_version))", "graph_identifier,graph_version,revision,updated_at,archived_at")
    _downgrade_table("graph_versions", "CREATE TABLE __TABLE__ (graph_identifier VARCHAR(128) NOT NULL,version INTEGER NOT NULL,artifact_json TEXT NOT NULL,content_address VARCHAR(71) NOT NULL,visibility VARCHAR(16) NOT NULL DEFAULT 'PRIVATE',created_at DATETIME NOT NULL,PRIMARY KEY(graph_identifier,version),FOREIGN KEY(graph_identifier) REFERENCES graph_artifacts(identifier) ON DELETE RESTRICT,CONSTRAINT ck_graph_versions_version CHECK(version>=1),CONSTRAINT ck_graph_versions_valid_json CHECK(json_valid(artifact_json)),CONSTRAINT ck_graph_versions_identifier_matches_json CHECK(json_extract(artifact_json,'$.identifier') IS graph_identifier),CONSTRAINT ck_graph_versions_version_matches_json CHECK(json_extract(artifact_json,'$.version') IS version),CONSTRAINT ck_graph_versions_private_visibility CHECK(visibility='PRIVATE'))", "graph_identifier,version,artifact_json,content_address,visibility,created_at")
    _downgrade_table("graph_artifacts", "CREATE TABLE __TABLE__ (identifier VARCHAR(128) NOT NULL PRIMARY KEY,project_id VARCHAR(64) NOT NULL,display_name VARCHAR(128) NOT NULL,draft_json TEXT NOT NULL,draft_revision INTEGER NOT NULL DEFAULT '0',published_revision INTEGER,current_version INTEGER,created_at DATETIME NOT NULL,updated_at DATETIME NOT NULL,FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE RESTRICT,CONSTRAINT ck_graph_artifacts_draft_revision CHECK(draft_revision>=0),CONSTRAINT ck_graph_artifacts_published_revision CHECK(published_revision IS NULL OR(published_revision>=0 AND published_revision<=draft_revision)),CONSTRAINT ck_graph_artifacts_publication_state CHECK((current_version IS NULL)=(published_revision IS NULL)))", "identifier,project_id,display_name,draft_json,draft_revision,published_revision,current_version,created_at,updated_at")


def _downgrade_projects() -> None:
    _recover("projects")
    if "projects" not in _names():
        return
    op.execute(sa.text("""CREATE TABLE projects__0021 (project_id VARCHAR(64) NOT NULL PRIMARY KEY,owner_id VARCHAR(64) NOT NULL,name VARCHAR(128) NOT NULL,description TEXT NOT NULL DEFAULT '',status VARCHAR(16) NOT NULL DEFAULT 'active',created_at DATETIME NOT NULL,updated_at DATETIME NOT NULL,CONSTRAINT ck_projects_status CHECK(status IN ('active','archived')),CONSTRAINT uq_projects_owner_name UNIQUE(owner_id,name),FOREIGN KEY(owner_id) REFERENCES organizations(organization_id) ON DELETE RESTRICT)"""))
    op.execute(sa.text("INSERT INTO projects__0021 (project_id,owner_id,name,description,status,created_at,updated_at) SELECT project_id,owner_id,name,description,status,created_at,updated_at FROM projects"))
    op.execute(sa.text("DROP TABLE projects"))
    op.execute(sa.text("ALTER TABLE projects__0021 RENAME TO projects"))


def upgrade() -> None:
    enabled = _foreign_keys_enabled()
    _foreign_keys(False)
    try:
        _recover_all()
        _upgrade_projects()
        _upgrade_user_graph_layouts()
        _remove_money_graph_fk("ir_paper_deployments")
        _remove_money_graph_fk("ir_shadow_deployments")
        _indexes_and_triggers()
    finally:
        _foreign_keys(enabled)


def downgrade() -> None:
    enabled = _foreign_keys_enabled()
    _foreign_keys(False)
    try:
        # Recover first: a completed 0020 table has no owner column and must not
        # be queried by the 0021 refusal guard before it is promoted.
        _recover_all()
        # The old global schema cannot represent more than the legacy owner. Refuse before DDL.
        _downgrade_refusal()
        _downgrade_user_graph_layouts()
        _downgrade_projects()
        _restore_money_graph_fk("ir_paper_deployments")
        _restore_money_graph_fk("ir_shadow_deployments")
        _indexes_and_triggers()
    finally:
        _foreign_keys(enabled)
