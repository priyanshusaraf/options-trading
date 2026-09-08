"""Add immutable research-plane Component IR v2 graph evidence."""
from __future__ import annotations


VERSION = "0008"


def upgrade(connection, table) -> None:
    table.create(connection, checkfirst=True)
    if connection.dialect.name == "sqlite":
        for operation in ("UPDATE", "DELETE"):
            connection.exec_driver_sql(
                f"CREATE TRIGGER IF NOT EXISTS trg_research_ir_v2_graph_versions_no_{operation.lower()} "
                f"BEFORE {operation} ON research_ir_v2_graph_versions BEGIN "
                "SELECT RAISE(ABORT, 'research_ir_v2_graph_versions is immutable'); END"
            )
        return

    connection.exec_driver_sql(
        "CREATE OR REPLACE FUNCTION research_ir_v2_graph_versions_refuse_mutation() "
        "RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'research_ir_v2_graph_versions is immutable' "
        "USING ERRCODE = '55000'; END; $$ LANGUAGE plpgsql"
    )
    connection.exec_driver_sql(
        "CREATE TRIGGER research_ir_v2_graph_versions_refuse_mutation BEFORE UPDATE OR DELETE "
        "ON research_ir_v2_graph_versions FOR EACH ROW EXECUTE FUNCTION "
        "research_ir_v2_graph_versions_refuse_mutation()"
    )


def downgrade(_connection, _table) -> None:
    raise RuntimeError("0008 refuses destructive removal of IR v2 graph evidence")
