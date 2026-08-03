"""persist projects, graph artefacts and immutable graph versions

Revision ID: 0006
Revises: 0005
Created: 2026-08-03

The fixed repository catalogue becomes the first durable graph lineage. Existing
layout rows may only have been written through that closed catalogue route; any
other key is quarantined before layout ownership is enforced and restored on
downgrade.
"""
from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from alembic import op

from app.ir.hashing import canonical_json, content_address
from app.ir.strategies.expanding_z import GRAPH


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

CATALOGUE_PROJECT_ID = "project.repository_catalogue"
CATALOGUE_CONTENT_ADDRESS = (
    "sha256:d78b424e8247e26663728b19980e197fb5e84a4e21c08c4df00ac704db1ae02b"
)
POSITION_REBUILD_TABLE = "_0006_ir_graph_layout_positions"


def _seed_values() -> dict:
    assert GRAPH["identifier"] == "strategy.expanding_z_impulse"
    assert GRAPH["version"] == 4
    assert content_address(GRAPH) == CATALOGUE_CONTENT_ADDRESS
    return {
        "project_id": CATALOGUE_PROJECT_ID,
        "identifier": GRAPH["identifier"],
        "display_name": GRAPH["display_name"],
        "version": GRAPH["version"],
        "artifact_json": canonical_json(GRAPH),
        "content_address": CATALOGUE_CONTENT_ADDRESS,
        "now": dt.datetime.now(dt.UTC).replace(tzinfo=None),
    }


def _backup_active_positions(bind) -> None:
    op.create_table(
        POSITION_REBUILD_TABLE,
        sa.Column("graph_identifier", sa.String(128), nullable=False),
        sa.Column("graph_version", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.String(128), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("graph_identifier", "graph_version", "instance_id"),
    )
    bind.execute(sa.text(
        f"INSERT INTO {POSITION_REBUILD_TABLE} "
        "(graph_identifier, graph_version, instance_id, x, y) "
        "SELECT graph_identifier, graph_version, instance_id, x, y "
        "FROM ir_graph_layout_positions"
    ))


def _restore_active_positions(bind) -> None:
    bind.execute(sa.text(
        "INSERT OR REPLACE INTO ir_graph_layout_positions "
        "(graph_identifier, graph_version, instance_id, x, y) "
        f"SELECT graph_identifier, graph_version, instance_id, x, y FROM {POSITION_REBUILD_TABLE}"
    ))
    op.drop_table(POSITION_REBUILD_TABLE)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("project_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_projects_status"),
    )
    op.create_table(
        "graph_artifacts",
        sa.Column("identifier", sa.String(128), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(64),
            sa.ForeignKey("projects.project_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("draft_json", sa.Text(), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_revision", sa.Integer(), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "draft_revision >= 0", name="ck_graph_artifacts_draft_revision"
        ),
        sa.CheckConstraint(
            "published_revision IS NULL OR "
            "(published_revision >= 0 AND published_revision <= draft_revision)",
            name="ck_graph_artifacts_published_revision",
        ),
        sa.CheckConstraint(
            "(current_version IS NULL) = (published_revision IS NULL)",
            name="ck_graph_artifacts_publication_state",
        ),
    )
    op.create_index(
        "ix_graph_artifacts_project_id", "graph_artifacts", ["project_id"]
    )
    op.create_table(
        "graph_versions",
        sa.Column("graph_identifier", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("artifact_json", sa.Text(), nullable=False),
        sa.Column("content_address", sa.String(71), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["graph_identifier"], ["graph_artifacts.identifier"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("version >= 1", name="ck_graph_versions_version"),
        sa.CheckConstraint(
            "json_valid(artifact_json)", name="ck_graph_versions_valid_json"
        ),
        sa.CheckConstraint(
            "json_extract(artifact_json, '$.identifier') IS graph_identifier",
            name="ck_graph_versions_identifier_matches_json",
        ),
        sa.CheckConstraint(
            "json_extract(artifact_json, '$.version') IS version",
            name="ck_graph_versions_version_matches_json",
        ),
        sa.PrimaryKeyConstraint("graph_identifier", "version"),
    )
    op.create_index(
        "ix_graph_versions_content_address", "graph_versions", ["content_address"]
    )
    op.create_table(
        "ir_graph_layout_orphan_archive",
        sa.Column("graph_identifier", sa.String(128), nullable=False),
        sa.Column("graph_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("graph_identifier", "graph_version"),
    )
    op.create_table(
        "ir_graph_layout_position_orphan_archive",
        sa.Column("graph_identifier", sa.String(128), nullable=False),
        sa.Column("graph_version", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.String(128), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("graph_identifier", "graph_version", "instance_id"),
    )

    seed = _seed_values()
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO projects "
            "(project_id, name, description, status, created_at, updated_at) "
            "VALUES (:project_id, 'Repository catalogue', '', 'active', :now, :now)"
        ),
        seed,
    )
    bind.execute(
        sa.text(
            "INSERT INTO graph_artifacts "
            "(identifier, project_id, display_name, draft_json, draft_revision, "
            " published_revision, current_version, created_at, updated_at) "
            "VALUES (:identifier, :project_id, :display_name, :artifact_json, 0, "
            "        0, :version, :now, :now)"
        ),
        seed,
    )
    bind.execute(
        sa.text(
            "INSERT INTO graph_versions "
            "(graph_identifier, version, artifact_json, content_address, created_at) "
            "VALUES (:identifier, :version, :artifact_json, :content_address, :now)"
        ),
        seed,
    )

    bind.execute(sa.text(
        "INSERT INTO ir_graph_layout_orphan_archive "
        "(graph_identifier, graph_version, revision, updated_at, archived_at) "
        "SELECT layout.graph_identifier, layout.graph_version, layout.revision, "
        "layout.updated_at, CURRENT_TIMESTAMP FROM ir_graph_layouts layout "
        "WHERE NOT EXISTS (SELECT 1 FROM graph_versions gv "
        "WHERE gv.graph_identifier = layout.graph_identifier "
        "AND gv.version = layout.graph_version)"
    ))
    bind.execute(sa.text(
        "INSERT INTO ir_graph_layout_position_orphan_archive "
        "(graph_identifier, graph_version, instance_id, x, y) "
        "SELECT position.graph_identifier, position.graph_version, "
        "position.instance_id, position.x, position.y "
        "FROM ir_graph_layout_positions position "
        "WHERE EXISTS (SELECT 1 FROM ir_graph_layout_orphan_archive archived "
        "WHERE archived.graph_identifier = position.graph_identifier "
        "AND archived.graph_version = position.graph_version)"
    ))
    bind.execute(sa.text(
        "DELETE FROM ir_graph_layout_positions WHERE NOT EXISTS ("
        " SELECT 1 FROM graph_versions gv"
        " WHERE gv.graph_identifier = ir_graph_layout_positions.graph_identifier"
        " AND gv.version = ir_graph_layout_positions.graph_version)"
    ))
    bind.execute(sa.text(
        "DELETE FROM ir_graph_layouts WHERE NOT EXISTS ("
        " SELECT 1 FROM graph_versions gv"
        " WHERE gv.graph_identifier = ir_graph_layouts.graph_identifier"
        " AND gv.version = ir_graph_layouts.graph_version)"
    ))
    _backup_active_positions(bind)
    with op.batch_alter_table("ir_graph_layouts") as batch:
        batch.create_foreign_key(
            "fk_ir_graph_layouts_graph_version",
            "graph_versions",
            ["graph_identifier", "graph_version"],
            ["graph_identifier", "version"],
            ondelete="RESTRICT",
        )
    _restore_active_positions(bind)

    op.execute(
        "CREATE TRIGGER graph_versions_refuse_update "
        "BEFORE UPDATE ON graph_versions BEGIN "
        "SELECT RAISE(ABORT, 'graph versions are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER graph_versions_refuse_delete "
        "BEFORE DELETE ON graph_versions BEGIN "
        "SELECT RAISE(ABORT, 'graph versions are immutable'); END"
    )


def downgrade() -> None:
    seed = _seed_values()
    bind = op.get_bind()
    extra_projects = bind.scalar(sa.text(
        "SELECT COUNT(*) FROM projects WHERE project_id != :project_id"
    ), seed)
    extra_artifacts = bind.scalar(sa.text(
        "SELECT COUNT(*) FROM graph_artifacts WHERE identifier != :identifier"
    ), seed)
    extra_versions = bind.scalar(sa.text(
        "SELECT COUNT(*) FROM graph_versions WHERE "
        "graph_identifier != :identifier OR version != :version"
    ), seed)
    seed_project_is_pristine = bind.scalar(sa.text(
        "SELECT COUNT(*) FROM projects WHERE project_id = :project_id "
        "AND name = 'Repository catalogue' AND description = '' AND status = 'active'"
    ), seed)
    seed_artifact_is_pristine = bind.scalar(sa.text(
        "SELECT COUNT(*) FROM graph_artifacts WHERE identifier = :identifier "
        "AND project_id = :project_id AND display_name = :display_name "
        "AND draft_json = :artifact_json AND draft_revision = 0 "
        "AND published_revision = 0 AND current_version = :version"
    ), seed)
    seed_version_is_pristine = bind.scalar(sa.text(
        "SELECT COUNT(*) FROM graph_versions WHERE graph_identifier = :identifier "
        "AND version = :version AND artifact_json = :artifact_json "
        "AND content_address = :content_address"
    ), seed)
    if (
        extra_projects
        or extra_artifacts
        or extra_versions
        or seed_project_is_pristine != 1
        or seed_artifact_is_pristine != 1
        or seed_version_is_pristine != 1
    ):
        raise RuntimeError(
            "0006 downgrade refused: non-seed or modified project/graph data exists"
        )

    op.execute("DROP TRIGGER graph_versions_refuse_delete")
    op.execute("DROP TRIGGER graph_versions_refuse_update")
    _backup_active_positions(bind)
    with op.batch_alter_table("ir_graph_layouts") as batch:
        batch.drop_constraint(
            "fk_ir_graph_layouts_graph_version", type_="foreignkey"
        )
    _restore_active_positions(bind)
    bind.execute(sa.text(
        "INSERT OR IGNORE INTO ir_graph_layouts "
        "(graph_identifier, graph_version, revision, updated_at) "
        "SELECT graph_identifier, graph_version, revision, updated_at "
        "FROM ir_graph_layout_orphan_archive"
    ))
    bind.execute(sa.text(
        "INSERT OR IGNORE INTO ir_graph_layout_positions "
        "(graph_identifier, graph_version, instance_id, x, y) "
        "SELECT graph_identifier, graph_version, instance_id, x, y "
        "FROM ir_graph_layout_position_orphan_archive"
    ))
    op.drop_table("ir_graph_layout_position_orphan_archive")
    op.drop_table("ir_graph_layout_orphan_archive")
    op.drop_index("ix_graph_versions_content_address", table_name="graph_versions")
    op.drop_table("graph_versions")
    op.drop_index("ix_graph_artifacts_project_id", table_name="graph_artifacts")
    op.drop_table("graph_artifacts")
    op.drop_table("projects")
