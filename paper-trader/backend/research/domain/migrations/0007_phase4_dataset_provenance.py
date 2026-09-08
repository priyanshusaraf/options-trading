"""Add immutable owner-scoped Phase 4 dataset manifests."""
from __future__ import annotations


VERSION = "0007"


def upgrade(connection, table) -> None:
    table.create(connection, checkfirst=True)
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql(
            "CREATE TRIGGER IF NOT EXISTS research_dataset_manifests_refuse_secret_key "
            "BEFORE INSERT ON research_dataset_manifests WHEN EXISTS ("
            "SELECT 1 FROM json_tree(NEW.manifest_json) WHERE key IS NOT NULL AND ("
            " lower(key) LIKE '%token%' OR lower(key) LIKE '%secret%' OR "
            "lower(key) LIKE '%password%' OR lower(key) LIKE '%api_key%' OR "
            "lower(key) LIKE '%credential%' OR lower(key) LIKE '%authorization%'"
            " )) BEGIN SELECT RAISE(ABORT, 'research_dataset_manifests contains credential-bearing key'); END"
        )
        for operation in ("UPDATE", "DELETE"):
            connection.exec_driver_sql(
                f"CREATE TRIGGER IF NOT EXISTS trg_research_dataset_manifests_no_{operation.lower()} "
                f"BEFORE {operation} ON research_dataset_manifests BEGIN "
                "SELECT RAISE(ABORT, 'research_dataset_manifests is immutable'); END"
            )
        return

    connection.exec_driver_sql(
        "CREATE OR REPLACE FUNCTION research_dataset_manifests_refuse_mutation() "
        "RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'research_dataset_manifests is immutable'; "
        "END; $$ LANGUAGE plpgsql"
    )
    connection.exec_driver_sql(
        "CREATE TRIGGER research_dataset_manifests_refuse_mutation BEFORE UPDATE OR DELETE "
        "ON research_dataset_manifests FOR EACH ROW EXECUTE FUNCTION "
        "research_dataset_manifests_refuse_mutation()"
    )


def downgrade(_connection, _table) -> None:
    raise RuntimeError("0007 refuses destructive removal of dataset provenance")
