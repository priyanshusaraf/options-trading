"""Separate graph addresses from source-domain strategy version labels.

Revision ID: 0040
Revises: 0039
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None

TABLES = ("deployments", "execution_intents", "positions", "trades", "backtest_results")
ENTRY_TABLES = ("deployments", "execution_intents", "positions", "backtest_results")


def _address_sql(column: str, dialect: str) -> str:
    if dialect == "postgresql":
        return f"{column} IS NULL OR {column} ~ '^sha256:[0-9a-f]{{64}}$'"
    return (
        f"{column} IS NULL OR (length({column}) = 71 AND "
        f"substr({column}, 1, 7) = 'sha256:' AND "
        f"substr({column}, 8) = lower(substr({column}, 8)) AND "
        f"substr({column}, 8) NOT GLOB '*[^0-9a-f]*')"
    )


def _coherence_sql(dialect: str) -> str:
    decimal = ("strategy_version ~ '^[0-9]+$'" if dialect == "postgresql"
               else "strategy_version IS NOT NULL AND length(strategy_version) > 0 "
                    "AND strategy_version NOT GLOB '*[^0-9]*'")
    like = "ir.%%" if dialect == "postgresql" else "ir.%"
    return (
        f"(attribution_state = 'VERIFIED_GRAPH' AND strategy_key LIKE '{like}' AND "
        f"{decimal} AND graph_address IS NOT NULL AND admission_address IS NOT NULL) "
        "OR (attribution_state = 'NON_GRAPH' AND graph_address IS NULL AND "
        f"(strategy_key IS NULL OR strategy_key NOT LIKE '{like}')) "
        "OR (attribution_state = 'LEGACY_UNVERIFIED' AND graph_address IS NULL)"
    )


def _add_columns_and_constraints(table: str, dialect: str) -> None:
    bind = op.get_bind()
    columns = {item["name"] for item in sa.inspect(bind).get_columns(table)}
    if dialect == "sqlite":
        if "graph_address" not in columns:
            op.add_column(table, sa.Column("graph_address", sa.String(71), nullable=True))
        if "attribution_state" not in columns:
            op.add_column(table, sa.Column(
                "attribution_state", sa.String(24), nullable=False,
                server_default=sa.text("'NON_GRAPH'")))
        bind.execute(sa.text(
            f"UPDATE {table} SET graph_address = NULL, "
            "attribution_state = 'LEGACY_UNVERIFIED'"))
        return
    if "graph_address" not in columns or "attribution_state" not in columns:
        with op.batch_alter_table(table) as batch:
            if "graph_address" not in columns:
                batch.add_column(sa.Column("graph_address", sa.String(71), nullable=True))
            if "attribution_state" not in columns:
                batch.add_column(sa.Column(
                    "attribution_state", sa.String(24), nullable=True,
                    server_default=sa.text("'NON_GRAPH'")))

    # Classify only the rows that existed before 0040. Their strategy_version bytes
    # remain untouched, and no address is inferred from those bytes.
    bind.execute(sa.text(
        f"UPDATE {table} SET graph_address = NULL, "
        "attribution_state = 'LEGACY_UNVERIFIED' "
        "WHERE attribution_state IS NULL OR attribution_state = 'NON_GRAPH'"
    ))

    op.alter_column(
        table, "attribution_state", existing_type=sa.String(24), nullable=False,
        server_default=sa.text("'NON_GRAPH'"))


def _install_insert_guard(table: str, dialect: str) -> None:
    bind = op.get_bind()
    trigger = f"{table}_refuse_legacy_attribution_insert"
    if dialect == "postgresql":
        function = f"{trigger}_fn"
        bind.execute(sa.text(
            f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
            "IF NEW.attribution_state = 'LEGACY_UNVERIFIED' OR "
            "(NEW.strategy_key LIKE 'ir.%%' AND NEW.attribution_state <> 'VERIFIED_GRAPH') THEN "
            "RAISE EXCEPTION 'GRAPH_ATTRIBUTION_UNVERIFIED'; END IF; RETURN NEW; "
            "END; $$ LANGUAGE plpgsql"
        ))
        bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger} ON {table}"))
        bind.execute(sa.text(
            f"CREATE TRIGGER {trigger} BEFORE INSERT ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"
        ))
        return
    bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger}"))
    bind.execute(sa.text(
        f"CREATE TRIGGER {trigger} BEFORE INSERT ON {table} "
        "WHEN NEW.attribution_state = 'LEGACY_UNVERIFIED' OR "
        "(NEW.strategy_key LIKE 'ir.%' AND NEW.attribution_state <> 'VERIFIED_GRAPH') BEGIN "
        "SELECT RAISE(ABORT, 'GRAPH_ATTRIBUTION_UNVERIFIED'); END"
    ))


def _install_validation_guard(table: str, dialect: str) -> None:
    bind = op.get_bind()
    trigger = f"{table}_validate_graph_attribution"
    if dialect == "postgresql":
        function = f"{trigger}_fn"
        bind.execute(sa.text(
            f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
            "IF NOT (((NEW.attribution_state = 'VERIFIED_GRAPH' "
            "AND NEW.strategy_key LIKE 'ir.%%' AND NEW.strategy_version ~ '^[0-9]+$' "
            "AND NEW.graph_address ~ '^sha256:[0-9a-f]{64}$' "
            "AND NEW.admission_address IS NOT NULL) OR "
            "(NEW.attribution_state = 'NON_GRAPH' AND NEW.graph_address IS NULL "
            "AND (NEW.strategy_key IS NULL OR NEW.strategy_key NOT LIKE 'ir.%%')) OR "
            "(NEW.attribution_state = 'LEGACY_UNVERIFIED' AND NEW.graph_address IS NULL))) THEN "
            "RAISE EXCEPTION 'GRAPH_ATTRIBUTION_MISMATCH'; END IF; RETURN NEW; "
            "END; $$ LANGUAGE plpgsql"))
        bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger} ON {table}"))
        bind.execute(sa.text(
            f"CREATE TRIGGER {trigger} BEFORE INSERT OR UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"))
        return
    valid = (
        "((NEW.attribution_state = 'VERIFIED_GRAPH' AND NEW.strategy_key LIKE 'ir.%' "
        "AND NEW.strategy_version IS NOT NULL AND length(NEW.strategy_version) > 0 "
        "AND NEW.strategy_version NOT GLOB '*[^0-9]*' "
        "AND NEW.graph_address IS NOT NULL AND length(NEW.graph_address) = 71 "
        "AND substr(NEW.graph_address,1,7) = 'sha256:' "
        "AND substr(NEW.graph_address,8) = lower(substr(NEW.graph_address,8)) "
        "AND substr(NEW.graph_address,8) NOT GLOB '*[^0-9a-f]*' "
        "AND NEW.admission_address IS NOT NULL) OR "
        "(NEW.attribution_state = 'NON_GRAPH' AND NEW.graph_address IS NULL "
        "AND (NEW.strategy_key IS NULL OR NEW.strategy_key NOT LIKE 'ir.%')) OR "
        "(NEW.attribution_state = 'LEGACY_UNVERIFIED' AND NEW.graph_address IS NULL))")
    for operation in ("insert", "update"):
        name = f"{trigger}_{operation}"
        bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
        bind.execute(sa.text(
            f"CREATE TRIGGER {name} BEFORE {operation.upper()} ON {table} "
            f"WHEN NOT {valid} BEGIN "
            "SELECT RAISE(ABORT, 'GRAPH_ATTRIBUTION_MISMATCH'); END"))


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError(f"0040 does not support {dialect!r}")
    for table in TABLES:
        _add_columns_and_constraints(table, dialect)
        _install_validation_guard(table, dialect)
    for table in ENTRY_TABLES:
        _install_insert_guard(table, dialect)


def downgrade() -> None:
    raise RuntimeError(
        "0040 refuses destructive graph-attribution downgrade; restore a verified "
        "pre-0040 backup or forward-repair the current schema"
    )
