"""The three former singleton money rows must admit identical names per account."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import command

from app.db import migrate
from app.db.models import Base


def _engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'account-state.db'}")
    with engine.connect() as connection:
        connection.execute(sa.text("PRAGMA foreign_keys=ON"))
    return engine


def test_replacement_money_identities_are_account_or_owner_scoped():
    tables = Base.metadata.tables
    assert [column.name for column in tables["capital_state"].primary_key] == [
        "broker_account_id", "book"
    ]
    assert [column.name for column in tables["instrument_state"].primary_key] == [
        "owner_id", "instrument_key"
    ]
    assert [column.name for column in tables["daily_account_snapshot"].primary_key] == [
        "broker_account_id", "day"
    ]


def test_revision_0018_preserves_legacy_money_rows_under_legacy_scope(tmp_path):
    engine = _engine(tmp_path)
    migrate.init_schema(engine, create_all=lambda: Base.metadata.create_all(engine), legacy_migrate=lambda: None)
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0017")
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, book, initial_capital, cash, realized_pnl, account_baseline, anchored_at, updated_at) "
            "VALUES (7, 'paper', 100000.25, 90000.75, -9999.5, 100200.0, "
            "'2026-08-10 09:30:00', '2026-08-10 09:31:00')"))
        connection.execute(sa.text(
            "INSERT INTO instrument_state "
            "(instrument_key, enabled, live_interval, entries_blocked, strategy_key, priority_flag, "
            "product, overtrade_flag, params_json) "
            "VALUES ('NSE_EQ|ABC', 0, '30minute', 1, 'strategy.a', 1, 'equity_intraday', 1, '{\"x\": 1}')"))
        connection.execute(sa.text(
            "INSERT INTO daily_account_snapshot "
            "(day, account_net, account_available, updated_at) "
            "VALUES ('2026-08-10', 112345.67, 99876.54, '2026-08-10 15:30:00')"))
        command.upgrade(migrate.alembic_config(connection), "0018")

    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT broker_account_id, book, initial_capital, cash, realized_pnl, account_baseline, "
            "anchored_at, updated_at FROM capital_state WHERE book = 'paper'")) .one() == (
            "account.default", "paper", 100000.25, 90000.75, -9999.5, 100200.0,
            "2026-08-10 09:30:00", "2026-08-10 09:31:00")
        assert connection.execute(sa.text(
            "SELECT owner_id, instrument_key, enabled, live_interval, entries_blocked, strategy_key, "
            "priority_flag, product, overtrade_flag, params_json FROM instrument_state")) .one() == (
            "owner", "NSE_EQ|ABC", 0, "30minute", 1, "strategy.a", 1,
            "equity_intraday", 1, '{"x": 1}')
        assert connection.execute(sa.text(
            "SELECT broker_account_id, day, account_net, account_available, updated_at "
            "FROM daily_account_snapshot")) .one() == (
            "account.default", "2026-08-10", 112345.67, 99876.54, "2026-08-10 15:30:00")


def test_revision_0018_downgrade_refuses_lossy_account_collapse(tmp_path):
    engine = _engine(tmp_path)
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0018")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(broker_account_id, book, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES ('account.a', 'paper', 1, 1, 0, CURRENT_TIMESTAMP), "
            "('account.b', 'paper', 2, 2, 0, CURRENT_TIMESTAMP)"))
    import pytest
    with pytest.raises(RuntimeError, match="lossy"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0017")


@__import__("pytest").mark.parametrize(("table", "insert"), [
    ("capital_state", "('account.a', 'paper', 1, 1, 0, CURRENT_TIMESTAMP), "
                      "('account.b', 'paper', 2, 2, 0, CURRENT_TIMESTAMP)"),
    ("instrument_state", "('org.a', 'NSE_EQ|ABC', 1, '15minute', 0, 0, 'options', 0, '{}'), "
                         "('org.b', 'NSE_EQ|ABC', 1, '15minute', 0, 0, 'options', 0, '{}')"),
    ("daily_account_snapshot", "('account.a', '2026-08-10', 1, 1, CURRENT_TIMESTAMP), "
                               "('account.b', '2026-08-10', 2, 2, CURRENT_TIMESTAMP)"),
])
def test_revision_0018_downgrade_refuses_each_scoped_key_collision(tmp_path, table, insert):
    engine = _engine(tmp_path)
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0018")
    columns = {
        "capital_state": "broker_account_id, book, initial_capital, cash, realized_pnl, updated_at",
        "instrument_state": "owner_id, instrument_key, enabled, live_interval, entries_blocked, priority_flag, product, overtrade_flag, params_json",
        "daily_account_snapshot": "broker_account_id, day, account_net, account_available, updated_at",
    }[table]
    with engine.begin() as connection:
        connection.execute(sa.text(f"INSERT INTO {table} ({columns}) VALUES {insert}"))
    import pytest
    with pytest.raises(RuntimeError, match="lossy"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0017")


def test_revision_0018_downgrade_refuses_nonlegacy_tenancy_root_loss(tmp_path):
    engine = _engine(tmp_path)
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0018")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO organizations (organization_id, name, status, created_at, updated_at) "
            "VALUES ('org.second', 'Second', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
    import pytest
    with pytest.raises(RuntimeError, match="tenancy"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0017")


def test_upgraded_0018_database_exposes_actual_composite_keys_and_membership_foreign_keys(tmp_path):
    engine = _engine(tmp_path)
    migrate.init_schema(engine, create_all=lambda: Base.metadata.create_all(engine), legacy_migrate=lambda: None)
    inspector = sa.inspect(engine)
    assert inspector.get_pk_constraint("capital_state")["constrained_columns"] == ["broker_account_id", "book"]
    assert inspector.get_pk_constraint("instrument_state")["constrained_columns"] == ["owner_id", "instrument_key"]
    assert inspector.get_pk_constraint("daily_account_snapshot")["constrained_columns"] == ["broker_account_id", "day"]
    membership_targets = {fk["referred_table"] for fk in inspector.get_foreign_keys("memberships")}
    assert membership_targets == {"organizations", "users"}


def test_revision_0018_downgrade_round_trips_legacy_sentinel_to_null_book(tmp_path):
    engine = _engine(tmp_path)
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0018")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, broker_account_id, book, initial_capital, cash, realized_pnl, anchored_at, updated_at) "
            "VALUES (91, 'account.default', 'legacy', 10.5, 9.25, -1.25, "
            "'2026-08-11 09:00:00', '2026-08-11 09:01:00')"))
        command.downgrade(migrate.alembic_config(connection), "0017")
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT id, book, initial_capital, cash, realized_pnl, anchored_at, updated_at "
            "FROM capital_state WHERE id = 91")).one() == (
                91, None, 10.5, 9.25, -1.25,
                "2026-08-11 09:00:00", "2026-08-11 09:01:00")
