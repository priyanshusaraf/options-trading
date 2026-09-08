"""Persist exact per-leg Paper charge authority without relabelling history.

The six columns are nullable and have no defaults or backfill. NULL remains a
historical unknown. Active writers must be quiesced for migration and binary
cutover; downgrade is restore/forward-repair only.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


POSITION_COLUMNS = (
    "paper_entry_charge_schedule_id",
    "paper_entry_charge_schedule_address",
)
TRADE_COLUMNS = (
    "paper_entry_charge_schedule_id",
    "paper_entry_charge_schedule_address",
    "paper_exit_charge_schedule_id",
    "paper_exit_charge_schedule_address",
)


def _address(column: str, dialect: str) -> str:
    if dialect == "postgresql":
        return f"{column} IS NULL OR {column} ~ '^sha256:[0-9a-f]{{64}}$'"
    return (
        f"{column} IS NULL OR (length({column}) = 71 AND "
        f"substr({column}, 1, 7) = 'sha256:' AND "
        f"substr({column}, 8) = lower(substr({column}, 8)) AND "
        f"substr({column}, 8) NOT GLOB '*[^0-9a-f]*')"
    )


def _refuse_partial_catalog(connection) -> None:
    inspector = sa.inspect(connection)
    expected = {
        "positions": set(POSITION_COLUMNS),
        "trades": set(TRADE_COLUMNS),
    }
    for table_name, columns in expected.items():
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        present = columns & actual
        if present:
            raise RuntimeError(
                "0045 refuses partial/unproven Paper charge authority schema; "
                "clean restore or forward repair required"
            )


def _install_entry_intent_immutability(connection, table_name: str, dialect: str) -> None:
    trigger = f"{table_name}_refuse_entry_intent_id_rebind"
    message = f"{table_name} entry_intent_id is immutable"
    if dialect == "sqlite":
        connection.exec_driver_sql(
            f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {table_name} "
            "WHEN NEW.entry_intent_id IS NOT OLD.entry_intent_id BEGIN "
            f"SELECT RAISE(ABORT, '{message}'); END")
        return
    function = f"{trigger}_fn"
    connection.exec_driver_sql(
        f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
        "IF NEW.entry_intent_id IS DISTINCT FROM OLD.entry_intent_id THEN "
        f"RAISE EXCEPTION '{message}'; END IF; RETURN NEW; "
        "END; $$ LANGUAGE plpgsql")
    connection.exec_driver_sql(
        f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {table_name} "
        f"FOR EACH ROW EXECUTE FUNCTION {function}()")


def upgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("0045 unsupported database dialect")
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200045)")
    _refuse_partial_catalog(connection)

    # Existing Paper equity/futures charge segments (for example NSE_INTRADAY and
    # NFO_FUT) are canonical persisted values, but PostgreSQL enforces the old
    # VARCHAR(8) declaration that SQLite silently tolerated. Expand in this same
    # unaccepted revision so all three required product families can persist.
    for table_name in ("positions", "trades"):
        if dialect == "sqlite":
            with op.batch_alter_table(table_name) as batch:
                batch.alter_column(
                    "exchange", existing_type=sa.String(8), type_=sa.String(16),
                    existing_nullable=False)
        else:
            op.alter_column(
                table_name, "exchange", existing_type=sa.String(8),
                type_=sa.String(16), existing_nullable=False)

    op.add_column(
        "positions",
        sa.Column("paper_entry_charge_schedule_id", sa.String(96), nullable=True),
    )
    op.add_column(
        "positions",
        sa.Column(
            "paper_entry_charge_schedule_address",
            sa.String(71),
            sa.CheckConstraint(
                "(paper_entry_charge_schedule_id IS NULL) = "
                "(paper_entry_charge_schedule_address IS NULL)",
                name="ck_positions_paper_entry_charge_pair",
            ),
            sa.CheckConstraint(
                _address("paper_entry_charge_schedule_address", dialect),
                name="ck_positions_paper_entry_charge_address",
            ),
            sa.CheckConstraint(
                "mode = 'paper' OR (paper_entry_charge_schedule_id IS NULL AND "
                "paper_entry_charge_schedule_address IS NULL)",
                name="ck_positions_paper_charge_mode",
            ),
            sa.CheckConstraint(
                "mode != 'paper' OR paper_entry_charge_schedule_id IS NULL OR "
                "entry_intent_id IS NOT NULL",
                name="ck_positions_paper_entry_intent_required",
            ),
            nullable=True,
        ),
    )

    op.add_column(
        "trades",
        sa.Column("paper_entry_charge_schedule_id", sa.String(96), nullable=True),
    )
    op.add_column(
        "trades",
        sa.Column(
            "paper_entry_charge_schedule_address",
            sa.String(71),
            sa.CheckConstraint(
                "(paper_entry_charge_schedule_id IS NULL) = "
                "(paper_entry_charge_schedule_address IS NULL)",
                name="ck_trades_paper_entry_charge_pair",
            ),
            sa.CheckConstraint(
                _address("paper_entry_charge_schedule_address", dialect),
                name="ck_trades_paper_entry_charge_address",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "trades",
        sa.Column("paper_exit_charge_schedule_id", sa.String(96), nullable=True),
    )
    op.add_column(
        "trades",
        sa.Column(
            "paper_exit_charge_schedule_address",
            sa.String(71),
            sa.CheckConstraint(
                "(paper_exit_charge_schedule_id IS NULL) = "
                "(paper_exit_charge_schedule_address IS NULL)",
                name="ck_trades_paper_exit_charge_pair",
            ),
            sa.CheckConstraint(
                _address("paper_exit_charge_schedule_address", dialect),
                name="ck_trades_paper_exit_charge_address",
            ),
            sa.CheckConstraint(
                "mode = 'paper' OR (paper_entry_charge_schedule_id IS NULL AND "
                "paper_entry_charge_schedule_address IS NULL AND "
                "paper_exit_charge_schedule_id IS NULL AND "
                "paper_exit_charge_schedule_address IS NULL)",
                name="ck_trades_paper_charge_mode",
            ),
            sa.CheckConstraint(
                "mode != 'paper' OR paper_entry_charge_schedule_id IS NULL OR "
                "entry_intent_id IS NOT NULL",
                name="ck_trades_paper_entry_intent_required",
            ),
            nullable=True,
        ),
    )
    for table_name in ("positions", "trades"):
        _install_entry_intent_immutability(connection, table_name, dialect)


def downgrade() -> None:
    raise RuntimeError(
        "0045 refuses destructive downgrade; retain Paper charge authority, "
        "quiesce writers, and use verified restore or forward repair"
    )
