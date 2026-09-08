"""Repair research JSON constraints without changing authoritative payload bytes."""
from __future__ import annotations

from sqlalchemy import CheckConstraint


VERSION = "0010"

# The order is a durable restart protocol. SQLite changes one complete table at
# a time; PostgreSQL changes one array constraint at a time. Only prefixes of
# this order are resumable states.
JSON_SHAPE_SITES = (
    ("research_ir_v2_graph_versions", "ck_research_ir_v2_graph_versions_valid_json",
     "artifact_json", "object"),
    ("research_strategy_admission", "ck_research_strategy_admission_valid_json",
     "artifact_json", "object"),
    ("research_dataset_manifests", "ck_research_dataset_manifest_json",
     "manifest_json", "object"),
    ("research_dataset_manifests_v2", "ck_research_dataset_manifest_v2_segments_json",
     "segment_addresses_json", "array"),
    ("research_dataset_manifests_v2", "ck_research_dataset_manifest_v2_instruments_json",
     "instrument_addresses_json", "array"),
    ("research_dataset_manifests_v2", "ck_research_dataset_manifest_v2_fields_json",
     "fields_json", "array"),
    ("research_dataset_manifests_v2", "ck_research_dataset_manifest_v2_gaps_json",
     "gaps_json", "array"),
    ("research_dataset_manifests_v2", "ck_research_dataset_manifest_v2_dependencies_json",
     "dependency_addresses_json", "array"),
)


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _constraint_sql(table, name: str, dialect) -> str:
    constraint = next(
        item for item in table.constraints
        if isinstance(item, CheckConstraint) and item.name == name
    )
    return str(constraint.sqltext.compile(dialect=dialect))


def upgrade_postgresql(connection, tables, *, validate_state, after_boundary) -> None:
    """Advance only an exact 0009/new-prefix state to all eight new contracts."""
    completed = validate_state(connection)
    table_map = {table.name: table for table in tables}
    for index, (table_name, constraint_name, _column, _shape) in enumerate(
            JSON_SHAPE_SITES[completed:], start=completed):
        table = table_map[table_name]
        connection.exec_driver_sql(
            f"ALTER TABLE {_quoted(table_name)} DROP CONSTRAINT {_quoted(constraint_name)}"
        )
        connection.exec_driver_sql(
            f"ALTER TABLE {_quoted(table_name)} ADD CONSTRAINT {_quoted(constraint_name)} "
            f"CHECK ({_constraint_sql(table, constraint_name, connection.dialect)})"
        )
        validate_state(connection, expected=index + 1)
        after_boundary(index + 1)


def upgrade_sqlite(connection, tables, *, validate_state, rebuild_table,
                   restore_table_contracts, after_boundary) -> None:
    """Rebuild exact tables at committed restart boundaries without changing rows."""
    completed = validate_state(connection)
    table_map = {table.name: table for table in tables}
    boundaries = ((0, 1), (1, 2), (2, 3), (3, len(JSON_SHAPE_SITES)))
    for old_count, new_count in boundaries:
        if completed >= new_count:
            continue
        if completed != old_count:
            raise RuntimeError("0010 encountered an undeclared SQLite restart boundary")
        table_name = JSON_SHAPE_SITES[old_count][0]
        table = table_map[table_name]
        rebuild_table(connection, table, notify=False)
        restore_table_contracts(connection, table)
        validate_state(connection, expected=new_count)
        connection.commit()
        completed = new_count
        after_boundary(completed)


def downgrade(_connection, _tables) -> None:
    raise RuntimeError("0010 refuses destructive restoration of ambiguous JSON constraints")
