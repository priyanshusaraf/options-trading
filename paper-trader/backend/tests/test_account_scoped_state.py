"""The three former singleton money rows must admit identical names per account."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import command

from app.db import migrate
from app.db.models import Base


def _migrated_null_ledger(tmp_path):
    engine = _engine(tmp_path)
    migrate.init_schema(engine, create_all=lambda: Base.metadata.create_all(engine), legacy_migrate=lambda: None)
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0017")
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, book, initial_capital, cash, realized_pnl, account_baseline, anchored_at, updated_at) "
            "VALUES (99, NULL, 100.25, 90.75, -9.5, 98.0, '2026-08-10 09:30:00', '2026-08-10 09:31:00')"))
        command.upgrade(migrate.alembic_config(connection), "0018")
    return engine


def _evidence_trade(owner_id: str, mode: str):
    import datetime as dt
    from app.db.models import Trade

    return Trade(owner_id=owner_id, deployment_id=None, instrument_key=f"NSE_EQ|{owner_id}-{mode}",
                 direction="LONG", option_type="EQ", tradingsymbol="X", exchange="NSE",
                 segment="equity_intraday", strike=0, expiry=dt.date(2026, 8, 11), qty=1,
                 entry_premium=1, entry_cost=1, entry_spot=1, entry_time=dt.datetime(2026, 8, 11, 9),
                 exit_premium=1, exit_charges=0, exit_spot=1, exit_time=dt.datetime(2026, 8, 11, 10),
                 exit_reason="TARGET", gross_pnl=0, charges_total=0, net_pnl=0, return_pct=0,
                 holding_minutes=60, win=False, held_overnight=False, overnight_pnl=0,
                 intraday_pnl=0, reinforcements=0, mode=mode, exit_price_estimated=False,
                 mfe=0, mae=0)


def _persist_evidence(session, *evidence: tuple[str, str]) -> None:
    """0017 fixtures predate the deployment seed; only owner/mode are evidence here."""
    session.connection().execute(sa.text("PRAGMA foreign_keys=OFF"))
    session.add_all([_evidence_trade(*item) for item in evidence])
    session.commit()
    session.connection().execute(sa.text("PRAGMA foreign_keys=ON"))


def test_raw_null_ledger_migrates_to_sentinel_then_runtime_claims_without_collision(tmp_path):
    """The raw pre-0018 NULL key remains exact money, then claims only its requested book."""
    from app.core.execution_book import LEGACY_UNATTRIBUTED_BOOK, LIVE, capital_for_book
    from app.db.models import CapitalState

    engine = _migrated_null_ledger(tmp_path)
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT id, broker_account_id, book, initial_capital, cash, realized_pnl, account_baseline, "
            "anchored_at, updated_at FROM capital_state WHERE id = 99")).one() == (
                99, "account.default", LEGACY_UNATTRIBUTED_BOOK, 100.25, 90.75, -9.5, 98.0,
                "2026-08-10 09:30:00", "2026-08-10 09:31:00")
    with sa.orm.Session(engine) as session:
        claimed = capital_for_book(session, LIVE, broker_account_id="account.default")
        assert (claimed.id, claimed.broker_account_id, claimed.book, claimed.cash,
                claimed.realized_pnl) == (99, "account.default", LIVE, 90.75, -9.5)
        assert session.query(CapitalState).filter_by(broker_account_id="account.default").count() == 1


@__import__("pytest").mark.parametrize(("evidence", "requested", "expected"), [
    (("owner", "live"), "live", "live"),
    (("owner", "paper"), "paper", "paper"),
    (("other-owner", "live"), "paper", "paper"),
])
def test_raw_null_ledger_claims_only_its_accounts_evidence(tmp_path, evidence, requested, expected):
    """Live/paper proof is owner-scoped; another owner's fills cannot claim this ledger."""
    from app.core.execution_book import capital_for_book
    from app.db.models import CapitalState

    engine = _migrated_null_ledger(tmp_path)
    with sa.orm.Session(engine) as session:
        _persist_evidence(session, evidence)
        row = capital_for_book(session, requested, broker_account_id="account.default")
        assert (row.id, row.book, row.cash, row.updated_at.isoformat(sep=" ")) == (
            99, expected, 90.75, "2026-08-10 09:31:00")
        assert session.query(CapitalState).filter_by(broker_account_id="account.default").count() == 1


def test_raw_null_ledger_remains_unclaimed_when_live_and_paper_evidence_conflict(tmp_path):
    from app.core.execution_book import LEGACY_UNATTRIBUTED_BOOK, capital_for_book
    from app.db.models import CapitalState

    engine = _migrated_null_ledger(tmp_path)
    with sa.orm.Session(engine) as session:
        _persist_evidence(session, ("owner", "live"), ("owner", "paper"))
        fresh = capital_for_book(session, "live", broker_account_id="account.default")
        sentinel = session.get(CapitalState, ("account.default", LEGACY_UNATTRIBUTED_BOOK))
        assert fresh.id != 99 and (sentinel.id, sentinel.cash, sentinel.book) == (99, 90.75, LEGACY_UNATTRIBUTED_BOOK)
        assert session.query(CapitalState).filter_by(broker_account_id="account.default").count() == 2


def test_raw_null_ledger_does_not_collide_with_a_preexisting_named_live_row(tmp_path):
    from app.core.execution_book import LEGACY_UNATTRIBUTED_BOOK, capital_for_book
    from app.db.models import CapitalState

    engine = _migrated_null_ledger(tmp_path)
    with sa.orm.Session(engine) as session:
        session.add(CapitalState(broker_account_id="account.default", book="live",
                                 initial_capital=7, cash=6, realized_pnl=-1))
        session.commit()
        paper = capital_for_book(session, "paper", broker_account_id="account.default")
        assert (paper.id, paper.book) != (99, "paper")
        assert session.get(CapitalState, ("account.default", "live")).cash == 6
        assert session.get(CapitalState, ("account.default", LEGACY_UNATTRIBUTED_BOOK)).cash == 90.75
        assert session.query(CapitalState).filter_by(broker_account_id="account.default").count() == 3


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


def test_calendar_snapshot_same_day_isolated_by_the_runners_broker_account():
    from app.db.models import DailyAccountSnapshot
    from app.db.session import SessionLocal, init_db
    from app.engine.runner import EngineRunner

    init_db(reset=True)
    runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    try:
        runner.broker.broker_account_id = "account.second"
        runner._persist_daily_snapshot({"net": 222.0, "available": 111.0})
        day = runner.provider.now().date().isoformat()
        with SessionLocal() as session:
            assert session.get(DailyAccountSnapshot, ("account.second", day)).account_net == 222.0
            assert session.get(DailyAccountSnapshot, ("account.default", day)) is None
    finally:
        runner.broker.close()


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
        assert connection.execute(sa.text("SELECT COUNT(*) FROM organizations")).scalar() == 1
        assert connection.execute(sa.text("SELECT COUNT(*) FROM users")).scalar() == 1
        assert connection.execute(sa.text("SELECT COUNT(*) FROM memberships")).scalar() == 1
        assert connection.execute(sa.text("SELECT COUNT(*) FROM broker_accounts")).scalar() == 1
        assert connection.execute(sa.text(
            "SELECT organization_id, name, status FROM organizations")).one() == (
                "owner", "Legacy owner", "active")
        assert connection.execute(sa.text(
            "SELECT user_id, email_normalized, display_name, status FROM users")).one() == (
                "owner-user", "owner@legacy.local", "Legacy owner", "active")
        assert connection.execute(sa.text(
            "SELECT organization_id, user_id, role, status FROM memberships")).one() == (
                "owner", "owner-user", "owner", "active")
        assert connection.execute(sa.text(
            "SELECT broker_account_id, owner_id, broker, external_account_id, display_name, status "
            "FROM broker_accounts")).one() == (
                "account.default", "owner", "legacy", "default", "Default account", "active")


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


@__import__("pytest").mark.parametrize(("table", "columns", "values", "expected"), [
    ("organizations", "organization_id, name, status, created_at, updated_at",
     "'org.second', 'Second', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP", "organizations"),
    ("users", "user_id, email_normalized, display_name, status, created_at, updated_at",
     "'user.second', 'second@example.test', 'Second', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP", "users"),
    ("broker_accounts", "broker_account_id, owner_id, broker, external_account_id, display_name, status, created_at, updated_at",
     "'account.second', 'owner', 'kite', 'second', 'Second', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP", "broker_accounts"),
    ("memberships", "organization_id, user_id, role, status, created_at, updated_at",
     "'owner', 'user.second', 'member', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP", "membership"),
])
def test_revision_0018_downgrade_refuses_each_nonlegacy_tenancy_root(tmp_path, table, columns, values, expected):
    engine = _engine(tmp_path)
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0018")
    with engine.begin() as connection:
        if table == "memberships":
            connection.execute(sa.text(
                "INSERT INTO organizations (organization_id, name, status, created_at, updated_at) "
                "VALUES ('owner', 'Legacy owner', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
            connection.execute(sa.text(
                "INSERT INTO users (user_id, email_normalized, display_name, status, created_at, updated_at) "
                "VALUES ('user.second', 'second@example.test', 'Second', 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
        connection.execute(sa.text(f"INSERT INTO {table} ({columns}) VALUES ({values})"))
    import pytest
    with pytest.raises(RuntimeError, match=expected):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0017")


def test_upgraded_0018_database_exposes_actual_composite_keys_and_membership_foreign_keys(tmp_path):
    engine = _engine(tmp_path)
    migrate.init_schema(engine, create_all=lambda: Base.metadata.create_all(engine), legacy_migrate=lambda: None)
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0017")
        command.upgrade(migrate.alembic_config(connection), "0018")
    inspector = sa.inspect(engine)
    assert inspector.get_pk_constraint("capital_state")["constrained_columns"] == ["broker_account_id", "book"]
    assert inspector.get_pk_constraint("instrument_state")["constrained_columns"] == ["owner_id", "instrument_key"]
    assert inspector.get_pk_constraint("daily_account_snapshot")["constrained_columns"] == ["broker_account_id", "day"]
    membership_targets = {fk["referred_table"] for fk in inspector.get_foreign_keys("memberships")}
    assert membership_targets == {"organizations", "users"}
    import pytest
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO memberships (organization_id, user_id, role, status, created_at, updated_at) "
                "VALUES ('missing.organization', 'owner-user', 'member', 'active', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))


@__import__("pytest").mark.parametrize(("legacy_book", "expected_book"), [
    (None, "legacy"),
    ("paper", "paper"),
])
def test_init_db_does_not_collide_with_a_preserved_id_one_legacy_capital_row(
        tmp_path, monkeypatch, legacy_book, expected_book):
    """Bootstrap leaves a migrated id=1 ledger untouched until a book is requested."""
    import app.db.session as session_module

    engine = _engine(tmp_path)
    migrate.init_schema(engine, create_all=lambda: Base.metadata.create_all(engine), legacy_migrate=lambda: None)
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0017")
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, book, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, :book, 123.0, 117.5, -5.5, '2026-08-11 09:01:00')"),
            {"book": legacy_book})
        command.upgrade(migrate.alembic_config(connection), "0018")

    isolated_sessions = sa.orm.sessionmaker(bind=engine, future=True, expire_on_commit=False)
    monkeypatch.setattr(session_module, "engine", engine)
    monkeypatch.setattr(session_module, "SessionLocal", isolated_sessions)
    session_module.init_db()

    with isolated_sessions() as session:
        rows = session.query(__import__("app.db.models", fromlist=["CapitalState"]).CapitalState).all()
        assert [(row.id, row.book, row.cash) for row in rows] == [(1, expected_book, 117.5)]


def test_upgrade_preserves_null_and_live_ledgers_and_paper_request_creates_a_third_row(tmp_path):
    """0017 permits a NULL ledger alongside live; 0018 must retain both exact values."""
    from app.core.execution_book import LEGACY_UNATTRIBUTED_BOOK, capital_for_book
    from app.db.models import CapitalState

    engine = _engine(tmp_path)
    migrate.init_schema(engine, create_all=lambda: Base.metadata.create_all(engine), legacy_migrate=lambda: None)
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0017")
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, book, initial_capital, cash, realized_pnl, account_baseline, anchored_at, updated_at) "
            "VALUES (41, NULL, 101.0, 91.0, -10.0, 99.0, '2026-08-10 09:30:00', '2026-08-10 09:31:00'), "
            "(42, 'live', 202.0, 192.0, -10.0, 198.0, '2026-08-10 10:30:00', '2026-08-10 10:31:00')"))
        command.upgrade(migrate.alembic_config(connection), "0018")

    with sa.orm.Session(engine) as session:
        before = {(row.id, row.book): (row.initial_capital, row.cash, row.realized_pnl,
                                        row.account_baseline, row.anchored_at.isoformat(sep=" "),
                                        row.updated_at.isoformat(sep=" "))
                  for row in session.query(CapitalState)}
        assert before == {
            (41, LEGACY_UNATTRIBUTED_BOOK): (101.0, 91.0, -10.0, 99.0,
                                              "2026-08-10 09:30:00", "2026-08-10 09:31:00"),
            (42, "live"): (202.0, 192.0, -10.0, 198.0,
                           "2026-08-10 10:30:00", "2026-08-10 10:31:00"),
        }
        paper = capital_for_book(session, "paper", broker_account_id="account.default")
        assert paper.book == "paper"
        assert session.get(CapitalState, ("account.default", LEGACY_UNATTRIBUTED_BOOK)).id == 41
        assert session.get(CapitalState, ("account.default", "live")).id == 42
        assert session.query(CapitalState).filter_by(broker_account_id="account.default").count() == 3


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
