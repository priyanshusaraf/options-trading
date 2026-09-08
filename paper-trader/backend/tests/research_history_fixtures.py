"""Genuine PostgreSQL research-history construction (shared sandbox era).

Owner rule: a historical fixture must represent a database that could really
have existed at that version. These builders use ONLY:

1. the frozen pre-0004 table definitions that ``research.domain.migrate``
   itself owns (``_tables_through_0003``), and
2. the exact production upgrade steps and marker updates that
   ``_migrate_postgresql`` runs for a real cut-over database,

stopping at the requested era marker. No current-metadata hybrids, no
hand-written historical DDL, no dropped-table shortcuts.
"""
from __future__ import annotations

import sqlalchemy as sa

from research.domain import migrate

# (upgrade step, marker it stamps) — mirrors _migrate_postgresql exactly.
PRODUCTION_CHAIN = (
    (migrate._upgrade_outbox, "0004"),
    (migrate._upgrade_strategy_admissions, "0005"),
    (migrate._upgrade_ir_v2_admissions, "0006"),
    (migrate._upgrade_dataset_provenance, "0007"),
    (migrate._upgrade_ir_v2_graph_versions, "0008"),
    (migrate._upgrade_dataset_authority, "0009"),
)
SUPPORTED_STOP_MARKERS = ("0003",) + tuple(version for _, version in PRODUCTION_CHAIN)


def make_genuine_postgresql_research_state(engine, version: str) -> None:
    """Drive the production chain from marker '0003' up to ``version``."""
    if version not in SUPPORTED_STOP_MARKERS:
        raise ValueError(f"unsupported genuine-history stop marker {version!r}")
    with engine.begin() as connection:
        for table in migrate._tables_through_0003():
            table.create(connection)
        connection.exec_driver_sql(
            f'CREATE TABLE "{migrate.VERSION_TABLE}" '
            "(version VARCHAR(16) NOT NULL PRIMARY KEY)"
        )
        connection.execute(sa.text(
            f"INSERT INTO \"{migrate.VERSION_TABLE}\" (version) VALUES ('0003')"
        ))
    if version != "0003":
        # The secret-key function is installed by the DatasetManifest
        # before_create event hook on fresh installs; replaying the production
        # steps outside _migrate_postgresql must not depend on which internal
        # creation path fires that hook, so mirror the product's own
        # idempotent installation before any provenance-era DDL.
        from research.domain.models import _PHASE4_SECRET_FUNCTION

        for upgrade_step, marker in PRODUCTION_CHAIN:
            with engine.begin() as connection:
                # Raw constant on purpose: psycopg collapses its %% escapes
                # exactly as the before_create event hook's DDL() execution.
                connection.exec_driver_sql(_PHASE4_SECRET_FUNCTION)
                upgrade_step(connection)
                connection.execute(sa.text(
                    f"UPDATE \"{migrate.VERSION_TABLE}\" SET version = :version"
                ), {"version": marker})
            if marker == version:
                break
    with engine.connect() as connection:
        current = connection.execute(sa.text(
            f"SELECT version FROM \"{migrate.VERSION_TABLE}\""
        )).scalar_one()
    if current != version:
        raise RuntimeError(
            f"genuine history build stopped at {current!r}, expected {version!r}"
        )
