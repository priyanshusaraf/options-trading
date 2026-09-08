"""One bounded PG16 logical backup/clean-restore proof across all three planes."""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.db import migrate
from app.db.models import (
    EXECUTION_OUTBOX_MODELS, AccountExecutionCommand, AccountExecutionLease,
    BacktestResult, BacktestRun, Base, BrokerAccount, CapitalState, Membership,
    Deployment, ExecutionIntent, Organization, Position, Trade, User, UserSession,
)
from app.backtest import repository as backtest_repository
from app.execution.leases import LeaseRepository, StaleLease
from app.events.outbox import OutboxRepository
from app.db.copy_contract import CopyRefusal, validate_semantic_ownership
from app.db.restore_contract import RestoreRefusal, capture_manifest, configured_restore_planes, verify_restore
from app.events.planes import execution_outbox, ledger_outbox, research_outbox
from app.ledger import models as ledger_models
from app.ledger.db import init_ledger_db, make_engine
from app.operations.postgresql_backup import postgres_process_spec, run_process_spec, sha256_file
from app.operations.postgresql_backup import resolve_postgresql16_tools
from research.domain import models as research_models
from research.domain.base import init_research_db, make_engine as make_research_engine


def _postgresql_0044_shape(engine) -> None:
    """Build the accepted pre-0045 catalog in one disposable database."""
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for table in ("positions", "trades"):
            trigger = f"{table}_refuse_entry_intent_id_rebind"
            connection.exec_driver_sql(
                f'DROP TRIGGER IF EXISTS "{trigger}" ON "{table}"')
            connection.exec_driver_sql(
                f'DROP FUNCTION IF EXISTS "{trigger}_fn"()')
    migrate.stamp(engine, "0044")
    with engine.begin() as connection:
        for table, columns in {
            "positions": (
                "paper_entry_charge_schedule_address",
                "paper_entry_charge_schedule_id",
            ),
            "trades": (
                "paper_exit_charge_schedule_address",
                "paper_exit_charge_schedule_id",
                "paper_entry_charge_schedule_address",
                "paper_entry_charge_schedule_id",
            ),
        }.items():
            for column in columns:
                connection.exec_driver_sql(
                    f'ALTER TABLE "{table}" DROP COLUMN "{column}"')


def test_pg16_revision_0045_fresh_upgrade_interruption_restart_and_lock(pg_sandbox):
    """FH-08/FH-09: real PG16 converges and never accepts a half migration."""
    from alembic import command

    fresh = pg_sandbox.engine("paper_charge_fresh")
    migrate.init_schema(
        fresh, create_all=lambda: Base.metadata.create_all(fresh),
        legacy_migrate=lambda: None, expected_tables=Base.metadata.tables)
    assert migrate.schema_version(fresh) == "0049"

    upgraded = pg_sandbox.engine("paper_charge_upgrade")
    _postgresql_0044_shape(upgraded)
    observed_sql = []

    def observe(_connection, _cursor, statement, _parameters, _context, _many):
        observed_sql.append(statement)

    sa.event.listen(upgraded, "before_cursor_execute", observe)
    try:
        with upgraded.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0045")
    finally:
        sa.event.remove(upgraded, "before_cursor_execute", observe)
    assert migrate.schema_version(upgraded) == "0045"
    assert any("pg_advisory_xact_lock" in statement for statement in observed_sql)
    assert {column["name"] for column in sa.inspect(upgraded).get_columns("trades")} >= {
        "paper_entry_charge_schedule_id", "paper_entry_charge_schedule_address",
        "paper_exit_charge_schedule_id", "paper_exit_charge_schedule_address",
    }
    with upgraded.connect() as connection:
        triggers = set(connection.execute(sa.text(
            "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"
        )).scalars())
    assert {
        "positions_refuse_entry_intent_id_rebind",
        "trades_refuse_entry_intent_id_rebind",
    } <= triggers
    # Historical-target repeat is idempotent and does not silently advance it.
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0045")
    assert migrate.schema_version(upgraded) == "0045"

    interrupted = pg_sandbox.engine("paper_charge_interrupted")
    _postgresql_0044_shape(interrupted)
    fired = False

    def interrupt(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal fired
        if not fired and "ALTER TABLE trades ADD COLUMN" in statement:
            fired = True
            raise RuntimeError("injected 0045 interruption")

    sa.event.listen(interrupted, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected 0045 interruption"):
            with interrupted.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0045")
    finally:
        sa.event.remove(interrupted, "before_cursor_execute", interrupt)
    assert fired and migrate.schema_version(interrupted) == "0044"
    assert "paper_entry_charge_schedule_id" not in {
        column["name"] for column in sa.inspect(interrupted).get_columns("positions")}
    with interrupted.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0045")
    assert migrate.schema_version(interrupted) == "0045"


@pytest.mark.parametrize("same_intent", [True, False])
def test_pg16_concurrent_paper_intents_serialize_before_money(
        pg_sandbox, monkeypatch, same_intent):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from app.core.instruments import get_instrument
    from app.engine import broker as broker_module
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider
    from tests.admitted_entry import persist_admitted_entry

    engine = pg_sandbox.engine(f"paper_intent_concurrency_{same_intent}")
    migrate.init_schema(
        engine, create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
        expected_tables=Base.metadata.tables)
    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    monkeypatch.setattr(broker_module, "SessionLocal", factory)
    opened_at = dt.datetime(2026, 8, 30, 10, 0)
    with factory() as session:
        session.add(Organization(
            organization_id="owner", name="Owner", status="active",
            created_at=opened_at, updated_at=opened_at))
        session.add(BrokerAccount(
            broker_account_id="account.default", owner_id="owner", broker="mock",
            external_account_id="default", display_name="Default", status="active",
            created_at=opened_at, updated_at=opened_at))
        session.add(Deployment(
            id=1, owner_id="owner", name="paper",
            broker_account_id="account.default", universe_mode="legacy",
            params_json="{}", status="active", armed=False, notes="",
            created_at=opened_at, updated_at=opened_at))
        session.add(CapitalState(
            broker_account_id="account.default", book="paper",
            initial_capital=100_000.0, cash=100_000.0, realized_pnl=0.0,
            updated_at=opened_at))
        session.commit()
        admission = persist_admitted_entry(session)
        intent_ids = ["a" * 32, "a" * 32 if same_intent else "b" * 32]
        for intent_id in sorted(set(intent_ids)):
            session.add(ExecutionIntent(
                client_intent_id=intent_id, deployment_id=1, owner_id="owner",
                broker_account_id="account.default", broker="mock",
                account_scope="default", connection_scope="paper",
                broker_tag=f"pti-{intent_id[:16]}", intent="ENTRY",
                instrument_key="NIFTY", tradingsymbol="NIFTY 50",
                exchange="NSE_INTRADAY", side="BUY", product="MIS",
                order_type="MARKET", requested_qty=200, limit_price=None,
                decision_price=100.0, signal_at=opened_at,
                strategy_key=admission["strategy_key"],
                strategy_version=admission["strategy_version"],
                admission_address=admission["admission_address"],
                graph_address=admission["graph_address"],
                attribution_state=admission["attribution_state"],
                context_json='{"schema":"paper-entry-lifecycle/1"}',
                created_at=opened_at))
        session.commit()
    barrier = threading.Barrier(2)

    def open_once(intent_id):
        broker = PaperBroker(
            MockProvider(), owner_id="owner", broker_account_id="account.default")
        try:
            intent = broker.s.get(ExecutionIntent, intent_id)
            barrier.wait(timeout=10)
            position = broker.open_equity_position(
                get_instrument("NIFTY"), "LONG", 100.0, 200, "NSE_INTRADAY",
                "PG CONCURRENT", opened_at, margin=4_000.0, params={},
                entry_intent_id=intent_id, recovery_intent=intent, **admission)
            return ("opened", position.entry_intent_id)
        except ValueError as exc:
            return ("refused", str(exc))
        finally:
            broker.s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(open_once, intent_ids))
    with factory() as session:
        positions = list(session.scalars(sa.select(Position).order_by(Position.id)))
        capital = session.get(CapitalState, ("account.default", "paper"))
        if same_intent:
            assert sorted(result[0] for result in results) == ["opened", "refused"]
            assert any(result == ("refused", "ENTRY_INTENT_ALREADY_USED")
                       for result in results)
            assert len(positions) == 1
        else:
            assert sorted(result[0] for result in results) == ["opened", "opened"]
            assert {position.entry_intent_id for position in positions} == {
                "a" * 32, "b" * 32}
        assert capital.cash == pytest.approx(
            100_000.0 - sum(position.entry_cost for position in positions))


@pytest.mark.parametrize(
    ("segment", "option_type", "entry_price", "exit_price", "qty", "margin"),
    [
        ("index_futures", "FUT", 24_000.0, 24_100.0, 50, 25_000.0),
    ],
)
def test_pg16_broker_reload_reconstructs_known_and_null_margined_receipts(
        pg_sandbox, segment, option_type, entry_price, exit_price, qty, margin):
    """V0-PCA-CR-001: fresh sessions read exact known and historical NULL legs."""
    from sqlalchemy.orm import Session
    from app.engine import charges
    from app.engine.broker import PaperBroker

    engine = pg_sandbox.engine(f"paper_receipt_{segment}")
    migrate.init_schema(
        engine, create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
        expected_tables=Base.metadata.tables)
    now = dt.datetime(2026, 8, 30, 10, 0)
    exchange = "NSE_INTRADAY" if segment == "equity_intraday" else "NFO_FUT"
    schedule_id = charges.ZERODHA_CHARGES_V1
    schedule_address = charges.charge_schedule_address(schedule_id)
    entry = charges.compute_charges(
        exchange, "BUY", entry_price, qty, schedule_id=schedule_id)
    exit_answer = charges.compute_charges(
        exchange, "SELL", exit_price, qty, schedule_id=schedule_id)
    with engine.begin() as connection:
        connection.execute(sa.insert(Organization), {
            "organization_id": "owner", "name": "Owner", "status": "active",
            "created_at": now, "updated_at": now})
        connection.execute(sa.insert(BrokerAccount), {
            "broker_account_id": "account.default", "owner_id": "owner",
            "broker": "mock", "external_account_id": "default",
            "display_name": "Default", "status": "active",
            "created_at": now, "updated_at": now})
        deployment_id = connection.execute(
            sa.insert(Deployment).returning(Deployment.id), {
                "owner_id": "owner", "name": "paper",
                "broker_account_id": "account.default", "universe_mode": "legacy",
                "params_json": "{}", "status": "active", "armed": False,
                "notes": "", "created_at": now, "updated_at": now,
            }).scalar_one()
        position_base = {
            "owner_id": "owner", "broker_account_id": "account.default",
            "deployment_id": deployment_id, "instrument_key": "NIFTY",
            "direction": "LONG", "option_type": option_type, "exchange": exchange,
            "segment": segment, "strike": 0.0, "expiry": now.date(),
            "lot_size": qty, "qty": qty, "entry_premium": entry_price,
            "entry_charges": entry["total"], "entry_cost": margin + entry["total"],
            "entry_spot": entry_price, "entry_time": now, "entry_reason": "reload",
            "stop_price": entry_price * 0.9, "target_price": entry_price * 1.1,
            "last_premium": entry_price, "last_spot": entry_price,
            "high_water_premium": entry_price, "mfe": 0.0, "mae": 0.0,
            "reinforcement_count": 0, "held_overnight": False,
            "overnight_pnl": 0.0, "session_close_premium": 0.0,
            "manual_target": False, "no_take_profit": False, "mode": "paper",
        }
        product = "MIS" if segment == "equity_intraday" else "NRML"
        intent_base = {
            "deployment_id": deployment_id, "owner_id": "owner",
            "broker_account_id": "account.default", "broker": "mock",
            "account_scope": "default", "connection_scope": "paper",
            "intent": "ENTRY", "instrument_key": "NIFTY", "exchange": exchange,
            "side": "BUY", "product": product, "order_type": "MARKET",
            "requested_qty": qty, "limit_price": None,
            "decision_price": entry_price, "signal_at": now,
            "strategy_key": None, "strategy_version": None,
            "admission_address": None, "graph_address": None,
            "attribution_state": "NON_GRAPH",
            "context_json": '{"schema":"paper-entry-lifecycle/1"}',
            "created_at": now,
        }
        position_intent_id = "1" * 32
        trade_intent_id = "2" * 32
        connection.execute(sa.insert(ExecutionIntent), [
            {**intent_base, "client_intent_id": position_intent_id,
             "broker_tag": "pti-" + "1" * 16,
             "tradingsymbol": f"{option_type}-KNOWN-POS"},
            {**intent_base, "client_intent_id": trade_intent_id,
             "broker_tag": "pti-" + "2" * 16,
             "tradingsymbol": f"{option_type}-KNOWN-TRADE"},
        ])
        known_position_id = connection.execute(sa.insert(Position).returning(Position.id), {
            **position_base, "tradingsymbol": f"{option_type}-KNOWN-POS",
            "entry_intent_id": position_intent_id,
            "paper_entry_charge_schedule_id": schedule_id,
            "paper_entry_charge_schedule_address": schedule_address,
        }).scalar_one()
        null_position_id = connection.execute(sa.insert(Position).returning(Position.id), {
            **position_base, "tradingsymbol": f"{option_type}-NULL-POS",
            "paper_entry_charge_schedule_id": None,
            "paper_entry_charge_schedule_address": None,
        }).scalar_one()
        trade_base = {
            "owner_id": "owner", "broker_account_id": "account.default",
            "deployment_id": deployment_id, "instrument_key": "NIFTY",
            "direction": "LONG", "option_type": option_type, "exchange": exchange,
            "segment": segment, "strike": 0.0, "expiry": now.date(), "qty": qty,
            "entry_premium": entry_price, "entry_cost": margin + entry["total"],
            "entry_spot": entry_price, "entry_time": now,
            "exit_premium": exit_price, "exit_charges": exit_answer["total"],
            "exit_spot": exit_price, "exit_time": now + dt.timedelta(minutes=30),
            "exit_reason": "reload", "gross_pnl": (exit_price - entry_price) * qty,
            "charges_total": entry["total"] + exit_answer["total"],
            "net_pnl": (exit_price - entry_price) * qty
                       - entry["total"] - exit_answer["total"],
            "return_pct": 0.0, "holding_minutes": 30.0, "win": True,
            "held_overnight": False, "overnight_pnl": 0.0, "intraday_pnl": 0.0,
            "reinforcements": 0, "mode": "paper", "exit_price_estimated": False,
            "mfe": 0.0, "mae": 0.0,
        }
        known_trade_id = connection.execute(sa.insert(Trade).returning(Trade.id), {
            **trade_base, "tradingsymbol": f"{option_type}-KNOWN-TRADE",
            "entry_intent_id": trade_intent_id,
            "paper_entry_charge_schedule_id": schedule_id,
            "paper_entry_charge_schedule_address": schedule_address,
            "paper_exit_charge_schedule_id": schedule_id,
            "paper_exit_charge_schedule_address": schedule_address,
        }).scalar_one()
        null_trade_id = connection.execute(sa.insert(Trade).returning(Trade.id), {
            **trade_base, "tradingsymbol": f"{option_type}-NULL-TRADE",
            "paper_entry_charge_schedule_id": None,
            "paper_entry_charge_schedule_address": None,
            "paper_exit_charge_schedule_id": None,
            "paper_exit_charge_schedule_address": None,
        }).scalar_one()

    with Session(engine) as session:
        broker = object.__new__(PaperBroker)
        broker.s = session
        broker.owner_id = "owner"
        broker.broker_account_id = "account.default"
        known_position = broker.charge_result_receipt(session.get(Position, known_position_id))
        null_position = broker.charge_result_receipt(session.get(Position, null_position_id))
        known_trade = broker.charge_result_receipt(session.get(Trade, known_trade_id))
        null_trade = broker.charge_result_receipt(session.get(Trade, null_trade_id))
        assert known_position["entry_authority_state"] == "KNOWN"
        assert null_position["entry_authority_state"] == "LEGACY_ENTRY_AUTHORITY_UNKNOWN"
        assert known_trade["entry_authority_state"] == "KNOWN"
        assert known_trade["exit_authority_state"] == "KNOWN"
        assert null_trade["entry_authority_state"] == "LEGACY_ENTRY_AUTHORITY_UNKNOWN"
        assert null_trade["exit_authority_state"] == "LEGACY_EXIT_AUTHORITY_UNKNOWN"
    for table, row_id, rebound in (
        ("positions", known_position_id, trade_intent_id),
        ("positions", known_position_id, None),
        ("trades", known_trade_id, position_intent_id),
        ("trades", known_trade_id, None),
        ("positions", null_position_id, position_intent_id),
        ("trades", null_trade_id, trade_intent_id),
    ):
        with pytest.raises(sa.exc.DBAPIError, match="entry_intent_id is immutable"):
            with engine.begin() as connection:
                connection.execute(sa.text(
                    f"UPDATE {table} SET entry_intent_id=:intent WHERE id=:id"),
                    {"intent": rebound, "id": row_id})
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT entry_intent_id FROM positions WHERE id=:id"),
            {"id": known_position_id}) == position_intent_id
        assert connection.scalar(sa.text(
            "SELECT entry_intent_id FROM trades WHERE id=:id"),
            {"id": known_trade_id}) == trade_intent_id
        assert connection.scalar(sa.text(
            "SELECT entry_intent_id FROM positions WHERE id=:id"),
            {"id": null_position_id}) is None
        assert connection.scalar(sa.text(
            "SELECT entry_intent_id FROM trades WHERE id=:id"),
            {"id": null_trade_id}) is None


def _plane_url(base: str, database: str, schema: str) -> str:
    return str(make_url(base).set(database=database).update_query_dict(
        {"options": f"-csearch_path={schema}"}))


def test_pg16_dump_restore_three_plane_generation_is_digest_identical(
        tmp_path, admitted_backtest_receipt):
    base = os.environ.get("PT_TEST_POSTGRES_URL")
    if not base:
        pytest.skip("PT_TEST_POSTGRES_URL is not configured")
    pg_dump, pg_restore = resolve_postgresql16_tools()
    nonce = uuid.uuid4().hex[:12]
    source_database = f"strategy_os_t7_src_{nonce}"
    target_database = f"strategy_os_t7_dst_{nonce}"
    admin = sa.create_engine(base, isolation_level="AUTOCOMMIT", future=True)
    try:
        with admin.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE "{source_database}"'))
            connection.execute(sa.text(f'CREATE DATABASE "{target_database}"'))
        source = {plane: _plane_url(base, source_database, plane)
                  for plane in ("execution", "research", "ledger")}
        target = {plane: _plane_url(base, target_database, plane)
                  for plane in ("execution", "research", "ledger")}
        source_admin = sa.create_engine(make_url(base).set(database=source_database), future=True)
        with source_admin.begin() as connection:
            for schema in source:
                connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
        source_admin.dispose()

        execution_engine = sa.create_engine(source["execution"], future=True)
        migrate.init_schema(
            execution_engine, create_all=lambda: Base.metadata.create_all(execution_engine),
            legacy_migrate=lambda: None, expected_tables=Base.metadata.tables)
        research_engine = make_research_engine(source["research"])
        init_research_db(research_engine)
        ledger_engine = make_engine(source["ledger"])
        init_ledger_db(ledger_engine)
        now = dt.datetime.now()
        with execution_engine.begin() as connection:
            connection.execute(sa.insert(Organization), [
                {"organization_id": "org-a", "name": "A", "status": "active",
                 "created_at": now, "updated_at": now},
                {"organization_id": "org-b", "name": "B", "status": "active",
                 "created_at": now, "updated_at": now},
            ])
            connection.execute(sa.insert(User), [
                {"user_id": "user-a", "email_normalized": "a@example.test",
                 "display_name": "A", "status": "active", "created_at": now, "updated_at": now},
                {"user_id": "user-b", "email_normalized": "b@example.test",
                 "display_name": "B", "status": "active", "created_at": now, "updated_at": now},
            ])
            connection.execute(sa.insert(Membership), [
                {"organization_id": "org-a", "user_id": "user-a", "role": "owner",
                 "status": "active", "created_at": now, "updated_at": now},
                {"organization_id": "org-b", "user_id": "user-b", "role": "owner",
                 "status": "active", "created_at": now, "updated_at": now},
            ])
            connection.execute(sa.insert(UserSession), [
                {"session_id": "active", "token_digest": "a" * 64, "user_id": "user-a",
                 "organization_id": "org-a", "issued_at": now,
                 "expires_at": now + dt.timedelta(days=1), "revoked_at": None},
                {"session_id": "revoked", "token_digest": "b" * 64, "user_id": "user-b",
                 "organization_id": "org-b", "issued_at": now - dt.timedelta(days=2),
                 "expires_at": now - dt.timedelta(days=1), "revoked_at": now},
            ])
            connection.execute(sa.insert(BrokerAccount), [
                {"broker_account_id": "acc-a", "owner_id": "org-a", "broker": "fake",
                 "external_account_id": "a", "display_name": "A", "status": "active",
                 "created_at": now, "updated_at": now},
                {"broker_account_id": "acc-b", "owner_id": "org-b", "broker": "fake",
                 "external_account_id": "b", "display_name": "B", "status": "active",
                 "created_at": now, "updated_at": now},
            ])
            deployment_id = connection.execute(sa.insert(Deployment).returning(Deployment.id), {
                "owner_id": "org-b", "name": "restore-paper",
                "broker_account_id": "acc-b", "universe_mode": "legacy",
                "params_json": "{}", "status": "active", "armed": False,
                "notes": "", "created_at": now, "updated_at": now,
            }).scalar_one()
            connection.execute(sa.insert(CapitalState), [
                {"broker_account_id": "acc-a", "book": "live", "initial_capital": 1000,
                 "cash": 1000, "realized_pnl": 0, "updated_at": now},
                {"broker_account_id": "acc-b", "book": "paper", "initial_capital": 2000,
                 "cash": 2000, "realized_pnl": 0, "updated_at": now},
            ])
            from app.engine.charges import (
                ZERODHA_CHARGES_V2, charge_schedule_address,
            )
            schedule_address = charge_schedule_address(ZERODHA_CHARGES_V2)
            restored_position_intent = "3" * 32
            restored_trade_intent = "4" * 32
            intent_base = {
                "deployment_id": deployment_id, "owner_id": "org-b",
                "broker_account_id": "acc-b", "broker": "fake",
                "account_scope": "b", "connection_scope": "paper",
                "intent": "ENTRY", "instrument_key": "NIFTY", "exchange": "NFO",
                "side": "BUY", "product": None, "order_type": "MARKET",
                "requested_qty": 75, "limit_price": None,
                "decision_price": 21.15, "signal_at": now,
                "strategy_key": None, "strategy_version": None,
                "admission_address": None, "graph_address": None,
                "attribution_state": "NON_GRAPH",
                "context_json": '{"schema":"paper-entry-lifecycle/1"}',
                "created_at": now,
            }
            connection.execute(sa.insert(ExecutionIntent), [
                {**intent_base, "client_intent_id": restored_position_intent,
                 "broker_tag": "pti-" + "3" * 16,
                 "tradingsymbol": "NIFTY-KNOWN"},
                {**intent_base, "client_intent_id": restored_trade_intent,
                 "broker_tag": "pti-" + "4" * 16,
                 "tradingsymbol": "NIFTY-KNOWN"},
            ])
            position_base = {
                "owner_id": "org-b", "broker_account_id": "acc-b",
                "deployment_id": deployment_id, "instrument_key": "NIFTY", "direction": "LONG",
                "option_type": "CE", "exchange": "NFO", "segment": "options",
                "strike": 24000.0, "expiry": now.date(), "lot_size": 75, "qty": 75,
                "entry_premium": 21.15, "entry_charges": 24.31, "entry_cost": 1610.56,
                "entry_spot": 24000.0, "entry_time": now, "entry_reason": "restore",
                "stop_price": 15.0, "target_price": 30.0, "last_premium": 21.15,
                "last_spot": 24000.0, "high_water_premium": 21.15,
                "mfe": 0.0, "mae": 0.0, "reinforcement_count": 0,
                "held_overnight": False, "overnight_pnl": 0.0,
                "session_close_premium": 0.0, "manual_target": False,
                "no_take_profit": False, "mode": "paper",
            }
            connection.execute(sa.insert(Position), [
                {**position_base, "tradingsymbol": "NIFTY-KNOWN",
                 "entry_intent_id": restored_position_intent,
                 "paper_entry_charge_schedule_id": ZERODHA_CHARGES_V2,
                 "paper_entry_charge_schedule_address": schedule_address},
                {**position_base, "tradingsymbol": "NIFTY-UNKNOWN",
                 "entry_intent_id": None,
                 "paper_entry_charge_schedule_id": None,
                 "paper_entry_charge_schedule_address": None},
            ])
            trade_base = {
                "owner_id": "org-b", "broker_account_id": "acc-b",
                "deployment_id": deployment_id, "instrument_key": "NIFTY", "direction": "LONG",
                "option_type": "CE", "exchange": "NFO", "segment": "options",
                "strike": 24000.0, "expiry": now.date(), "qty": 75,
                "entry_premium": 21.15, "entry_cost": 1610.56,
                "entry_spot": 24000.0, "entry_time": now,
                "exit_premium": 22.0, "exit_charges": 25.0, "exit_spot": 24010.0,
                "exit_time": now, "exit_reason": "restore", "gross_pnl": 63.75,
                "charges_total": 49.31, "net_pnl": 14.44, "return_pct": 0.9,
                "holding_minutes": 1.0, "win": True, "held_overnight": False,
                "overnight_pnl": 0.0, "intraday_pnl": 14.44, "reinforcements": 0,
                "mode": "paper", "exit_price_estimated": False, "mfe": 0.0, "mae": 0.0,
            }
            connection.execute(sa.insert(Trade), [
                {**trade_base, "tradingsymbol": "NIFTY-KNOWN",
                 "entry_intent_id": restored_trade_intent,
                 "paper_entry_charge_schedule_id": ZERODHA_CHARGES_V2,
                 "paper_entry_charge_schedule_address": schedule_address,
                 "paper_exit_charge_schedule_id": ZERODHA_CHARGES_V2,
                 "paper_exit_charge_schedule_address": schedule_address},
                {**trade_base, "tradingsymbol": "NIFTY-UNKNOWN",
                 "entry_intent_id": None,
                 "paper_entry_charge_schedule_id": None,
                 "paper_entry_charge_schedule_address": None,
                 "paper_exit_charge_schedule_id": None,
                 "paper_exit_charge_schedule_address": None},
            ])
        execution_sessions = sessionmaker(execution_engine, future=True, expire_on_commit=False)
        with execution_sessions.begin() as session:
            repo = execution_outbox()
            with repo.writer(session):
                repo.append(
                    session, classification="private", owner_id="org-a",
                    broker_account_id="acc-a", aggregate_type="execution_lease",
                    aggregate_id="acc-a", event_type="execution.lease.changed",
                    schema_version=1, payload={"projection": "execution_status"},
                    producer_key="restore-fixture-execution")
                repo.append(
                    session, classification="private", owner_id="org-a",
                    broker_account_id=None, aggregate_type="backtest_run",
                    aggregate_id="owner-run", event_type="execution.backtest.changed",
                    schema_version=1, payload={"projection": "backtest_runs"},
                    producer_key="restore-fixture-execution-owner")
        with execution_sessions.begin() as session:
            repo = execution_outbox()
            claimed = repo.claim_batch(session, consumer_id="restore-consumer",
                                       lease_owner="source", limit=10, lease_seconds=30)
            assert len(claimed.events) == 2
            for event in claimed.events:
                repo.ack(session, claimed.claim_token, event.event_id,
                         effect_key=f"projection:{event.producer_key}")
            repo.release(session, claimed.claim_token)
        lease_repository = LeaseRepository(execution_sessions)
        old_lease_token = lease_repository.claim(
            owner_id="org-a", broker_account_id="acc-a",
            cell_id="source-cell", worker_id="source-boot")
        lease_repository.activate(old_lease_token, reconciliation_evidence="fixture reconciled")
        prepared = lease_repository.prepare_command(
            old_lease_token, kind="place_order", target_id="intent-ambiguous",
            idempotency_key="restore-ambiguous", request_digest="c" * 64,
            broker_tag="pt-bot", requested_qty=1, requested_side="BUY")
        lease_repository.transition_command(
            old_lease_token, prepared.command_id,
            from_state="prepared", to_state="sent_unknown", error_code="ack_lost")

        job_started = dt.datetime(2026, 8, 13, 0, 0, 0)
        backtest_value = {
            "instrument_key": "NIFTY", "name": "NIFTY", "segment": "nse_delivery",
            "strategy_key": "trend_impulse_v3", "strategy_version": "strategy-v1",
            "interval": "day", "bars": 1, "params_hash": "params-v1", "error": "",
        }
        with execution_sessions() as session:
            receipt = admitted_backtest_receipt(session, owner_id="org-a")
            admitted = backtest_repository.load_verified_admission(
                session, owner_id="org-a",
                admission_address=receipt["admission_address"])
        backtest_value.update(
            strategy_key=admitted.strategy_key,
            strategy_version=admitted.strategy_version,
            graph_address=admitted.graph_address,
            attribution_state=admitted.attribution_state)
        with execution_sessions.begin() as session:
            run = backtest_repository.enqueue_run(
                session, owner_id="org-a", scope="liquid", intervals="day",
                capital=1000, total=1, now=job_started, **receipt)
            job_id = run.id
            old_job = backtest_repository.claim_run(
                session, owner_id="org-a", run_id=job_id, claimed_by="source-job",
                now=job_started, lease_seconds=1)
            assert old_job is not None
            old_job_token = old_job.claim_token
        with execution_sessions.begin() as session:
            assert backtest_repository.append_claimed_result_batch(
                session, owner_id="org-a", run_id=job_id,
                claim_token=old_job_token,
                values=[{**backtest_value,
                         "admission_address": receipt["admission_address"]}],
                now=job_started + dt.timedelta(milliseconds=100), lease_seconds=1)

        with research_engine.begin() as connection:
            connection.execute(sa.insert(research_models.ResearchProgram), [
                {"owner_id": "org-a", "name": "A"}, {"owner_id": "org-b", "name": "B"}])
            operation_id = "restore-research-op"
            connection.execute(sa.insert(research_models.ResearchOperation), {
                "owner_id": "org-a", "operation_id": operation_id, "trigger": "manual",
                "plan_json": "{}", "status": "running", "stage": "experiments",
                "build": "test-build", "provider_mode": "fake", "completed_run_ids_json": "[]",
                "created_at": now, "queued_at": now, "started_at": now,
                "heartbeat_at": now, "claim_token": "research-old-token",
                "claimed_by": "research-source-worker",
                "claim_expires_at": now + dt.timedelta(seconds=1), "attempt_count": 1})
        research_sessions = sessionmaker(research_engine, future=True)
        with research_sessions.begin() as session:
            repo = research_outbox()
            with repo.writer(session):
                repo.append(session, classification="private", owner_id="org-a",
                            broker_account_id=None, aggregate_type="research_operation",
                            aggregate_id="op-a", event_type="research.operation.changed",
                            schema_version=1, payload={"projection": "research_operation"},
                            producer_key="restore-fixture-research")
        with ledger_engine.begin() as connection:
            connection.execute(sa.insert(ledger_models.LedgerSnapshot), [
                {"owner_id": "org-a", "broker_account_id": "acc-a", "id": 1,
                 "version": 1, "payload": "{}", "updated_at": now},
                {"owner_id": "org-b", "broker_account_id": "acc-b", "id": 1,
                 "version": 1, "payload": "{}", "updated_at": now},
            ])
            artifact_bytes = b"task7-ledger-artifact"
            artifact_id = hashlib.sha256(artifact_bytes).hexdigest()
            connection.execute(sa.insert(ledger_models.LedgerArtifact), {
                "owner_id": "org-a", "broker_account_id": "acc-a", "id": artifact_id,
                "mime": "application/octet-stream", "bytes": artifact_bytes,
                "created_at": now})
        ledger_sessions = sessionmaker(ledger_engine, future=True)
        with ledger_sessions.begin() as session:
            repo = ledger_outbox()
            with repo.writer(session):
                repo.append(session, classification="private", owner_id="org-a",
                            broker_account_id="acc-a", aggregate_type="ledger_snapshot",
                            aggregate_id="1", event_type="ledger.snapshot.changed",
                            schema_version=1, payload={"projection": "ledger_snapshot"},
                            producer_key="restore-fixture-ledger")

        artifacts = {}
        for plane in source:
            artifact = tmp_path / f"{plane}.dump"
            run_process_spec(postgres_process_spec(
                source[plane], executable=pg_dump, action="dump", artifact=artifact))
            artifacts[plane] = {"identifier": artifact.name, "sha256": sha256_file(artifact)}
        started = dt.datetime.now(dt.timezone.utc)
        signing_key = b"local-restore-fixture-signing-key"
        manifest = capture_manifest(
            configured_restore_planes(execution_url=source["execution"],
                                      research_url=source["research"], ledger_url=source["ledger"]),
            generation_id=f"restore-{nonce}", source_build="test-build", artifacts=artifacts,
            maintenance_evidence={"quiesced": True,
                                  "evidence_address": "sha256:" + "e" * 64},
            backup_started_at=started, backup_completed_at=dt.datetime.now(dt.timezone.utc),
            signing_key=signing_key)
        execution_engine.dispose(); research_engine.dispose(); ledger_engine.dispose()

        for plane in target:
            run_process_spec(postgres_process_spec(
                target[plane], executable=pg_restore, action="restore",
                artifact=tmp_path / f"{plane}.dump"))
        report = verify_restore(
            configured_restore_planes(execution_url=target["execution"],
                                      research_url=target["research"], ledger_url=target["ledger"]),
            manifest, signing_key=signing_key, require_signed=True)
        assert report["cutover_ready"] is True
        assert report["execution_recovery_required"] is True
        target_research = make_research_engine(target["research"])
        with target_research.connect() as connection:
            restored_operation = connection.execute(sa.select(
                research_models.ResearchOperation.status,
                research_models.ResearchOperation.claim_token,
                research_models.ResearchOperation.claimed_by).where(
                    research_models.ResearchOperation.owner_id == "org-a",
                    research_models.ResearchOperation.operation_id == operation_id)).one()
            assert restored_operation.status == "running"
            assert restored_operation.claim_token == "research-old-token"
            assert restored_operation.claimed_by == "research-source-worker"
        target_research.dispose()
        restored_planes = configured_restore_planes(
            execution_url=target["execution"], research_url=target["research"],
            ledger_url=target["ledger"])
        mutation_engine = sa.create_engine(target["execution"], future=True)
        with mutation_engine.begin() as connection:
            connection.execute(sa.text(
                "UPDATE execution_outbox_event "
                "SET broker_account_id='acc-b', scope_key='private:org-a:acc-b' "
                "WHERE producer_key='restore-fixture-execution-owner'"))
        with mutation_engine.connect() as connection:
            with pytest.raises(CopyRefusal, match="broker-account ownership"):
                validate_semantic_ownership(connection, Base.metadata)
        with pytest.raises(RestoreRefusal):
            verify_restore(restored_planes, manifest, signing_key=signing_key,
                           require_signed=True)
        with mutation_engine.begin() as connection:
            connection.execute(sa.text(
                "UPDATE execution_outbox_event "
                "SET broker_account_id=NULL, scope_key='private:org-a:*' "
                "WHERE producer_key='restore-fixture-execution-owner'"))
        with mutation_engine.begin() as connection:
            connection.execute(sa.text("UPDATE alembic_version SET version_num='bad-head'"))
        with pytest.raises(RestoreRefusal):
            verify_restore(restored_planes, manifest, signing_key=signing_key, require_signed=True)
        with mutation_engine.begin() as connection:
            connection.execute(sa.text(
                "UPDATE alembic_version SET version_num=:head"),
                {"head": migrate.head_revision()})
            connection.execute(sa.text(
                "UPDATE capital_state SET cash=cash+1 WHERE broker_account_id='acc-a' AND book='live'"))
        with pytest.raises(RestoreRefusal, match="digest"):
            verify_restore(restored_planes, manifest, signing_key=signing_key, require_signed=True)
        with mutation_engine.begin() as connection:
            connection.execute(sa.text(
                "UPDATE capital_state SET cash=cash-1 WHERE broker_account_id='acc-a' AND book='live'"))
            sequence = connection.scalar(sa.text(
                "SELECT pg_get_serial_sequence('backtest_runs','id')"))
            connection.execute(sa.text(
                "SELECT setval(CAST(:sequence AS regclass), 1, false)"), {"sequence": sequence})
        with pytest.raises(RestoreRefusal):
            verify_restore(restored_planes, manifest, signing_key=signing_key, require_signed=True)
        with mutation_engine.begin() as connection:
            connection.execute(sa.text(
                "SELECT setval(CAST(:sequence AS regclass), 1, true)"), {"sequence": sequence})
        mutation_engine.dispose()
        ledger_mutation = make_engine(target["ledger"])
        with ledger_mutation.begin() as connection:
            connection.execute(sa.text(
                "UPDATE ledger_snapshot SET owner_id='unknown-owner' WHERE owner_id='org-b'"))
        with pytest.raises(RestoreRefusal):
            verify_restore(restored_planes, manifest, signing_key=signing_key, require_signed=True)
        with ledger_mutation.begin() as connection:
            connection.execute(sa.text(
                "UPDATE ledger_snapshot SET owner_id='org-b' WHERE owner_id='unknown-owner'"))
        ledger_mutation.dispose()
        target_engine = sa.create_engine(target["execution"], future=True)
        target_sessions = sessionmaker(target_engine, future=True)
        with target_sessions.begin() as session:
            assert set(session.scalars(sa.select(ExecutionIntent.client_intent_id).where(
                ExecutionIntent.client_intent_id.in_((
                    restored_position_intent, restored_trade_intent))))) == {
                        restored_position_intent, restored_trade_intent}
            assert session.scalar(sa.select(sa.func.count()).select_from(Position).where(
                Position.entry_intent_id.is_(None))) == 1
            assert session.scalar(sa.select(sa.func.count()).select_from(Trade).where(
                Trade.entry_intent_id.is_(None))) == 1
            assert session.scalar(sa.select(sa.func.count()).select_from(
                EXECUTION_OUTBOX_MODELS.Event)) >= 5
            assert session.scalar(sa.select(sa.func.count()).select_from(
                EXECUTION_OUTBOX_MODELS.StreamHead)) >= 2
            assert session.scalar(sa.select(sa.func.count()).select_from(
                EXECUTION_OUTBOX_MODELS.ConsumerCursor)) == 1
            assert session.scalar(sa.select(sa.func.count()).select_from(
                EXECUTION_OUTBOX_MODELS.ConsumerReceipt)) == 2
            assert session.scalar(sa.select(AccountExecutionLease.fence_epoch).where(
                AccountExecutionLease.owner_id == "org-a",
                AccountExecutionLease.broker_account_id == "acc-a")) == old_lease_token.fence_epoch
            assert session.scalar(sa.select(AccountExecutionCommand.state).where(
                AccountExecutionCommand.command_id == prepared.command_id)) == "sent_unknown"
            assert session.scalar(sa.select(sa.func.count()).select_from(BacktestResult).where(
                BacktestResult.owner_id == "org-a", BacktestResult.run_id == job_id)) == 1
            restored_repo = execution_outbox()
            with restored_repo.writer(session):
                restored_repo.append(
                    session, classification="private", owner_id="org-a",
                    broker_account_id="acc-a", aggregate_type="execution_lease",
                    aggregate_id="acc-a", event_type="execution.lease.changed",
                    schema_version=1, payload={"projection": "execution_status"},
                    producer_key="restore-fixture-post-restore")
        with target_sessions.begin() as session:
            batch = execution_outbox().claim_batch(
                session, consumer_id="restore-consumer", lease_owner="target",
                limit=10, lease_seconds=30)
            assert len(batch.events) >= 1
            for event in batch.events:
                execution_outbox().ack(
                    session, batch.claim_token, event.event_id,
                    effect_key=f"projection:post-restore:{event.event_id}")
            execution_outbox().release(session, batch.claim_token)
        restored_leases = LeaseRepository(target_sessions)
        new_lease_token = restored_leases.claim_after_restore(
            owner_id="org-a", broker_account_id="acc-a",
            cell_id="target-cell", worker_id="target-boot",
            restore_evidence=report["content_address"])
        assert new_lease_token.fence_epoch == old_lease_token.fence_epoch + 1
        with pytest.raises(StaleLease):
            restored_leases.heartbeat(old_lease_token)
        with target_sessions() as stale_session:
            restored_leases.bind_money_session(stale_session, old_lease_token)
            stale_session.add(CapitalState(
                broker_account_id="acc-a", book="paper", initial_capital=50,
                cash=50, realized_pnl=0, updated_at=dt.datetime.now()))
            with pytest.raises(StaleLease):
                stale_session.commit()
        with target_sessions.begin() as session:
            restored = session.get(AccountExecutionLease, ("org-a", "acc-a"))
            assert restored.state == "recovering"
            assert restored.desired_state == restored.effective_state == "disabled"
            successor = backtest_repository.claim_run(
                session, owner_id="org-a", run_id=job_id, claimed_by="target-job",
                now=job_started + dt.timedelta(seconds=2), lease_seconds=30)
            assert successor is not None and successor.claim_token != old_job_token
            successor_token = successor.claim_token
        with target_sessions.begin() as session:
            assert backtest_repository.append_claimed_result_batch(
                session, owner_id="org-a", run_id=job_id, claim_token=successor_token,
                values=[{**backtest_value,
                         "admission_address": receipt["admission_address"]}],
                now=job_started + dt.timedelta(seconds=3))
            assert backtest_repository.complete_claim(
                session, owner_id="org-a", run_id=job_id, claim_token=successor_token,
                status="done", now=job_started + dt.timedelta(seconds=3))
        with target_sessions.begin() as session:
            assert session.scalar(sa.select(sa.func.count()).select_from(BacktestResult).where(
                BacktestResult.owner_id == "org-a", BacktestResult.run_id == job_id)) == 1
        target_engine.dispose()
        target_ledger = make_engine(target["ledger"])
        with target_ledger.connect() as connection:
            restored_artifact = connection.execute(sa.select(
                ledger_models.LedgerArtifact.id, ledger_models.LedgerArtifact.bytes).where(
                    ledger_models.LedgerArtifact.owner_id == "org-a",
                    ledger_models.LedgerArtifact.broker_account_id == "acc-a")).one()
            assert restored_artifact.id == artifact_id
            assert hashlib.sha256(restored_artifact.bytes).hexdigest() == artifact_id
        target_ledger.dispose()
    finally:
        # Drop only this test's UUID-bound databases, after terminating their
        # own remaining pooled sessions.
        with admin.connect() as connection:
            for database in (source_database, target_database):
                connection.execute(sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname=:database AND pid <> pg_backend_pid()"), {"database": database})
                connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{database}"'))
        admin.dispose()
