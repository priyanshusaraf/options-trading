from __future__ import annotations

import datetime as dt
import subprocess
import sys

import pytest
import sqlalchemy as sa
from alembic import command

from app.db import migrate
from app.db.models import Base, Position, Trade
from app.db.schema_semantics import (
    check_sql_matches,
    expected_paper_checks,
    full_sql_matches,
    validate_paper_entry_lifecycle_manifest,
)
from app.engine.broker import PaperBroker
from app.providers.mock import MockProvider
from tests.test_v0_platform_operations_migration import _prepare_0045, _sqlite


def _rewrite_table_sql(connection, table: str, old: str, new: str) -> None:
    raw = connection.connection.driver_connection
    original = raw.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()[0]
    assert old in original
    version = raw.execute("PRAGMA schema_version").fetchone()[0]
    raw.execute("PRAGMA writable_schema=ON")
    raw.execute(
        "UPDATE sqlite_master SET sql=? WHERE type='table' AND name=?",
        (original.replace(old, new), table),
    )
    raw.execute("PRAGMA writable_schema=OFF")
    raw.execute(f"PRAGMA schema_version={version + 1}")


def _regroup_positions_mode(connection) -> None:
    _rewrite_table_sql(
        connection,
        "positions",
        "mode = 'paper' OR (paper_entry_charge_schedule_id IS NULL AND "
        "paper_entry_charge_schedule_address IS NULL)",
        "(mode = 'paper' OR paper_entry_charge_schedule_id IS NULL) AND "
        "paper_entry_charge_schedule_address IS NULL",
    )


def test_monitoring_and_paper_share_one_schema_semantic_authority():
    from app.monitoring import repository
    from app.db import schema_semantics

    assert repository._shared_check_sql_matches is schema_semantics.check_sql_matches
    assert repository._shared_conservative_check_sql is schema_semantics.conservative_check_sql
    assert migrate.validate_paper_entry_lifecycle_manifest is (
        schema_semantics.validate_paper_entry_lifecycle_manifest)


def test_fresh_process_import_preserves_one_paper_manifest_authority():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.db import migrate, schema_semantics; "
            "assert migrate.validate_paper_entry_lifecycle_manifest is "
            "schema_semantics.validate_paper_entry_lifecycle_manifest",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_shared_paper_manifest_authority_accepts_current_0048_head(tmp_path):
    engine = _sqlite(tmp_path, "paper-current-0048.db")
    migrate.init_schema(
        engine,
        create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
        expected_tables=Base.metadata.tables,
    )
    assert migrate.schema_version(engine) == "0048"
    with engine.connect() as connection:
        validate_paper_entry_lifecycle_manifest(connection)
        migrate.validate_paper_entry_lifecycle_manifest(connection)
    engine.dispose()


@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
def test_all_ten_paper_checks_preserve_grouping_literals_operators_casts_and_order(dialect):
    expected = expected_paper_checks(dialect)
    assert sum(map(len, expected.values())) == 10
    for table_name, checks in expected.items():
        table = Base.metadata.tables[table_name]
        for name, sql in checks.items():
            assert check_sql_matches(table, name, dialect, sql, sql, context="paper")
            assert check_sql_matches(
                table, name, dialect, sql, f" /* catalog no-op */ (({sql})) ",
                context="paper")
            assert not check_sql_matches(
                table, name, dialect, sql, sql.replace("'paper'", "'Paper'"),
                context="paper") if "'paper'" in sql else True

    table = Base.metadata.tables["positions"]
    mode = expected["positions"]["ck_positions_paper_charge_mode"]
    regrouped = (
        "(mode = 'paper' or paper_entry_charge_schedule_id is null) and "
        "paper_entry_charge_schedule_address is null")
    assert not check_sql_matches(
        table, "ck_positions_paper_charge_mode", dialect, mode, regrouped,
        context="paper")
    required = expected["positions"]["ck_positions_paper_entry_intent_required"]
    assert not check_sql_matches(
        table, "ck_positions_paper_entry_intent_required", dialect, required,
        required.replace(" is not null", " is null"), context="paper")
    assert not check_sql_matches(
        table, "ck_positions_paper_entry_intent_required", dialect, required,
        required.replace(" or ", " and ", 1), context="paper")
    if dialect == "postgresql":
        native = required.replace("mode", "mode::text", 1).replace(
            "!=", "<>").replace("'paper'", "'paper'::text")
        assert check_sql_matches(
            table, "ck_positions_paper_entry_intent_required", dialect,
            required, native, context="paper")
        assert not check_sql_matches(
            table, "ck_positions_paper_entry_intent_required", dialect,
            required, native.replace("::text", "::varchar", 1), context="paper")


def test_complete_trigger_sql_accepts_only_declared_noops():
    identifiers = frozenset({
        "positions", "positions_refuse_entry_intent_id_rebind",
        "positions_refuse_entry_intent_id_rebind_fn", "new", "old",
        "entry_intent_id"})
    expected = (
        "create trigger positions_refuse_entry_intent_id_rebind before update on positions "
        "when new.entry_intent_id is not old.entry_intent_id begin "
        "select raise(abort, 'positions entry_intent_id is immutable'); end")
    assert full_sql_matches(
        expected, "/* harmless */ " + expected.upper().replace(
            "'POSITIONS ENTRY_INTENT_ID IS IMMUTABLE'",
            "'positions entry_intent_id is immutable'"), identifiers=identifiers)
    for altered in (
        expected.replace("before update", "after update"),
        expected.replace("before update", "before insert"),
        expected.replace("on positions", "on trades"),
        expected.replace("entry_intent_id is immutable", "entry_intent_id may change"),
        expected.replace("select raise", "select 1; select raise"),
    ):
        assert not full_sql_matches(expected, altered, identifiers=identifiers)


def test_postgresql_every_trigger_and_function_catalog_field_is_load_bearing():
    from app.db.schema_semantics import _postgresql_trigger_function_matches

    trigger = "positions_refuse_entry_intent_id_rebind"
    function = f"{trigger}_fn"
    identifiers = frozenset({
        "positions", trigger, function, "new", "old", "entry_intent_id"})
    expected_trigger = (
        f"create trigger {trigger} before update on positions for each row "
        f"execute function {function}()")
    expected_body = (
        "begin if new.entry_intent_id is distinct from old.entry_intent_id then "
        "raise exception 'positions entry_intent_id is immutable'; "
        "end if; return new; end;")
    metadata = {
        "schema_name": "public", "table_name": "positions", "tgname": trigger,
        "tgenabled": "O", "tgtype": 19, "tgisinternal": False,
        "tgdeferrable": False, "tginitdeferred": False, "tgnargs": 0,
        "trigger_arguments": "", "update_columns": "", "when_clause": None,
        "tgoldtable": None, "tgnewtable": None, "function_schema": "public",
        "function_name": function, "prokind": "f", "pronargs": 0,
        "arguments": "", "result": "trigger", "language": "plpgsql",
        "provolatile": "v", "proisstrict": False, "prosecdef": False,
        "proleakproof": False, "proparallel": "u", "proconfig": None,
    }
    actual = {
        **metadata, "trigger_definition": expected_trigger, "prosrc": expected_body}
    matches = lambda candidate: _postgresql_trigger_function_matches(
        candidate, expected_metadata=metadata, expected_trigger=expected_trigger,
        expected_body=expected_body, identifiers=identifiers)
    assert matches(actual)
    assert matches({
        **actual,
        "trigger_definition": "/* catalog no-op */ " + expected_trigger,
        "prosrc": "/* catalog no-op */ " + expected_body,
    })
    for key, value in metadata.items():
        if value is None:
            changed = "unexpected"
        elif isinstance(value, bool):
            changed = not value
        elif isinstance(value, int):
            changed = value + 1
        else:
            changed = value + "_changed"
        assert not matches({**actual, key: changed}), key
    assert not matches({
        **actual, "trigger_definition": expected_trigger.replace("before", "after")})
    assert not matches({**actual, "prosrc": "begin return new; end;"})


def test_sqlite_regrouping_refuses_before_0046_ddl_and_exact_controls_restart(tmp_path):
    exact = _sqlite(tmp_path, "paper-exact.db")
    _prepare_0045(exact)
    with exact.connect() as connection:
        validate_paper_entry_lifecycle_manifest(
            connection, compatible_heads=frozenset({"0045"}))
    with exact.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0046")
    assert migrate.schema_version(exact) == "0046"
    with exact.connect() as connection:
        validate_paper_entry_lifecycle_manifest(
            connection, compatible_heads=frozenset({"0046"}))
        migrate.validate_paper_entry_lifecycle_manifest(
            connection, compatible_heads=frozenset({"0046"}))

    drifted = _sqlite(tmp_path, "paper-regrouped.db")
    _prepare_0045(drifted)
    with drifted.connect() as connection:
        _regroup_positions_mode(connection)
        connection.connection.driver_connection.commit()
    before = set(sa.inspect(drifted).get_table_names())
    with pytest.raises(RuntimeError, match="positions CHECK"):
        with drifted.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0046")
    assert migrate.schema_version(drifted) == "0045"
    assert set(sa.inspect(drifted).get_table_names()) == before
    assert not {name for name in before if name.startswith("platform_")}


def test_copy_source_preflight_uses_same_regrouping_guard(tmp_path):
    from app.db.copy_contract import CopyPlane, CopyRefusal, _source_engine, _validate_source_schema

    path = tmp_path / "paper-copy-source.db"
    engine = _sqlite(tmp_path, path.name)
    _prepare_0045(engine)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0046")
    with engine.connect() as connection:
        _regroup_positions_mode(connection)
        connection.connection.driver_connection.commit()
    engine.dispose()
    plane = CopyPlane(
        name="execution", source_path=path,
        destination_url="postgresql://unused/unused", metadata=Base.metadata,
        marker_table="alembic_version", source_head="0046",
        initialize_destination=lambda _engine: None,
        validate_destination=lambda _engine: None,
    )
    source = _source_engine(path)
    try:
        with pytest.raises(CopyRefusal, match="Paper lifecycle manifest"):
            _validate_source_schema(plane, source)
    finally:
        source.dispose()


@pytest.mark.parametrize("family", ["options", "equity", "futures"])
def test_regrouping_refuses_every_paper_entry_before_money(
        admitted_entry_identity, family):
    from app.core.instruments import get_instrument
    from app.db.session import init_db

    init_db(reset=True)
    broker = PaperBroker(MockProvider(), owner_id="owner", broker_account_id="account.default")
    admission = admitted_entry_identity(broker.s)
    instrument = get_instrument("NIFTY")
    now = dt.datetime(2026, 8, 30, 10, 0)
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    before_cash = broker.cash()
    before_positions = broker.s.scalar(sa.select(sa.func.count()).select_from(Position))
    _regroup_positions_mode(broker.s.connection())
    with pytest.raises(RuntimeError, match="PAPER_ENTRY_LIFECYCLE_SCHEMA_STALE"):
        if family == "options":
            broker.open_position(
                instrument, "LONG", quote, "DRIFT", now, chain.spot, **admission)
        elif family == "equity":
            broker.open_equity_position(
                instrument, "LONG", 100.0, 101, "NSE_INTRADAY", "DRIFT", now,
                margin=4_001.0, params={}, **admission)
        else:
            broker.open_futures_position(
                instrument, "LONG", 24_000.0, 50, "NFO_FUT", "DRIFT", now,
                dt.date(2026, 9, 24), margin=25_000.0, **admission)
    assert broker.cash() == before_cash
    assert broker.s.scalar(sa.select(sa.func.count()).select_from(Position)) == before_positions
    broker.s.rollback()
    broker.s.close()


@pytest.mark.parametrize("family", ["options", "equity", "futures"])
def test_manifest_drift_never_blocks_risk_reducing_exits(
        admitted_entry_identity, family):
    from app.core.instruments import get_instrument
    from app.db.session import init_db

    init_db(reset=True)
    broker = PaperBroker(MockProvider(), owner_id="owner", broker_account_id="account.default")
    admission = admitted_entry_identity(broker.s)
    instrument = get_instrument("NIFTY")
    now = dt.datetime(2026, 8, 30, 10, 0)
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    if family == "options":
        position = broker.open_position(
            instrument, "LONG", quote, "EXIT", now, chain.spot, **admission)
    elif family == "equity":
        position = broker.open_equity_position(
            instrument, "LONG", 100.0, 101, "NSE_INTRADAY", "EXIT", now,
            margin=4_001.0, params={}, **admission)
    else:
        position = broker.open_futures_position(
            instrument, "LONG", 24_000.0, 50, "NFO_FUT", "EXIT", now,
            dt.date(2026, 9, 24), margin=25_000.0, **admission)
    _regroup_positions_mode(broker.s.connection())
    if family == "options":
        trade = broker.close_position(position, quote.ltp, "RISK", now, chain.spot)
    elif family == "equity":
        trade = broker.close_equity_position(position, 101.0, "RISK", now)
    else:
        trade = broker.close_futures_position(position, 24_050.0, "RISK", now)
    assert trade.id is not None
    assert broker.s.scalar(sa.select(sa.func.count()).select_from(Position)) == 0
    assert broker.s.scalar(sa.select(sa.func.count()).select_from(Trade)) == 1
    broker.s.rollback()
    broker.s.close()


def test_postgresql16_complete_paper_trigger_and_function_metadata(pg_sandbox):
    engine = pg_sandbox.engine("paper_semantic_manifest")
    _prepare_0045(engine)
    with engine.connect() as connection:
        validate_paper_entry_lifecycle_manifest(
            connection, compatible_heads=frozenset({"0045"}))
        assert sum(len(sa.inspect(connection).get_check_constraints(name))
                   for name in ("positions", "trades")) >= 10

    mutations = (
        "ALTER TABLE positions DISABLE TRIGGER positions_refuse_entry_intent_id_rebind",
        "ALTER FUNCTION positions_refuse_entry_intent_id_rebind_fn() STABLE",
        "ALTER FUNCTION positions_refuse_entry_intent_id_rebind_fn() STRICT",
        "ALTER FUNCTION positions_refuse_entry_intent_id_rebind_fn() SECURITY DEFINER",
        "ALTER FUNCTION positions_refuse_entry_intent_id_rebind_fn() PARALLEL SAFE",
        "ALTER FUNCTION positions_refuse_entry_intent_id_rebind_fn() SET work_mem='64kB'",
        "CREATE OR REPLACE FUNCTION positions_refuse_entry_intent_id_rebind_fn() "
        "RETURNS trigger AS $$ BEGIN RETURN NEW; "
        "IF NEW.entry_intent_id IS DISTINCT FROM OLD.entry_intent_id THEN "
        "RAISE EXCEPTION 'positions entry_intent_id is immutable'; END IF; "
        "RETURN NEW; END; $$ LANGUAGE plpgsql",
    )
    for statement in mutations:
        connection = engine.connect()
        transaction = connection.begin()
        try:
            connection.exec_driver_sql(statement)
            with pytest.raises(RuntimeError, match="positions trigger"):
                validate_paper_entry_lifecycle_manifest(
                    connection, compatible_heads=frozenset({"0045"}))
        finally:
            transaction.rollback()
            connection.close()
    trigger_mutations = (
        "CREATE TRIGGER positions_refuse_entry_intent_id_rebind AFTER UPDATE ON positions "
        "FOR EACH ROW EXECUTE FUNCTION positions_refuse_entry_intent_id_rebind_fn()",
        "CREATE TRIGGER positions_refuse_entry_intent_id_rebind BEFORE INSERT ON positions "
        "FOR EACH ROW EXECUTE FUNCTION positions_refuse_entry_intent_id_rebind_fn()",
        "CREATE TRIGGER positions_refuse_entry_intent_id_rebind BEFORE UPDATE ON trades "
        "FOR EACH ROW EXECUTE FUNCTION positions_refuse_entry_intent_id_rebind_fn()",
        "CREATE TRIGGER positions_refuse_entry_intent_id_rebind BEFORE UPDATE ON positions "
        "FOR EACH ROW EXECUTE FUNCTION trades_refuse_entry_intent_id_rebind_fn()",
    )
    for create_statement in trigger_mutations:
        connection = engine.connect()
        transaction = connection.begin()
        try:
            connection.exec_driver_sql(
                "DROP TRIGGER positions_refuse_entry_intent_id_rebind ON positions")
            connection.exec_driver_sql(create_statement)
            with pytest.raises(RuntimeError, match="positions trigger"):
                validate_paper_entry_lifecycle_manifest(
                    connection, compatible_heads=frozenset({"0045"}))
        finally:
            transaction.rollback()
            connection.close()
    from app.db.copy_contract import CopyRefusal, validate_content_addresses
    connection = engine.connect()
    transaction = connection.begin()
    try:
        connection.exec_driver_sql(
            "ALTER FUNCTION positions_refuse_entry_intent_id_rebind_fn() STABLE")
        with pytest.raises(CopyRefusal, match="immutability triggers"):
            validate_content_addresses(connection, Base.metadata)
    finally:
        transaction.rollback()
        connection.close()
    engine.dispose()


def test_postgresql16_full_partial_and_remaining_exits_ignore_manifest_drift(
        pg_sandbox, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    from app.core.instruments import get_instrument
    from app.db.models import BrokerAccount, CapitalState, Deployment, Organization
    from app.engine import broker as broker_module
    from tests.admitted_entry import persist_admitted_entry

    engine = pg_sandbox.engine("paper_manifest_exit_safety")
    migrate.init_schema(
        engine, create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("unexpected legacy migration"),
        expected_tables=Base.metadata.tables)
    factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    monkeypatch.setattr(broker_module, "SessionLocal", factory)
    now = dt.datetime(2026, 8, 30, 10, 0)
    with factory() as session:
        session.add(Organization(
            organization_id="owner", name="Owner", status="active",
            created_at=now, updated_at=now))
        session.add(BrokerAccount(
            broker_account_id="account.default", owner_id="owner", broker="mock",
            external_account_id="default", display_name="Default", status="active",
            created_at=now, updated_at=now))
        session.add(Deployment(
            id=1, owner_id="owner", name="paper",
            broker_account_id="account.default", universe_mode="legacy",
            params_json="{}", status="active", armed=False, notes="",
            created_at=now, updated_at=now))
        session.add(CapitalState(
            broker_account_id="account.default", book="paper",
            initial_capital=1_000_000.0, cash=1_000_000.0, realized_pnl=0.0,
            updated_at=now))
        session.commit()
        admission = persist_admitted_entry(session)

    broker = PaperBroker(
        MockProvider(), owner_id="owner", broker_account_id="account.default")
    instrument = get_instrument("NIFTY")
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    positions = {
        "options": [broker.open_position(
            instrument, "LONG", quote, "PG EXIT", now, chain.spot,
            params={}, **admission)
            for _ in range(2)],
        "equity": [broker.open_equity_position(
            instrument, "LONG", 100.0, 101, "NSE_INTRADAY", "PG EXIT", now,
            margin=4_001.0, params={}, **admission) for _ in range(2)],
        "futures": [broker.open_futures_position(
            instrument, "LONG", 24_000.0, 50, "NFO_FUT", "PG EXIT", now,
            dt.date(2026, 9, 24), margin=25_000.0, params={}, **admission)
            for _ in range(2)],
    }
    broker.s.commit()
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER FUNCTION positions_refuse_entry_intent_id_rebind_fn() STABLE")
        with pytest.raises(RuntimeError, match="positions trigger"):
            validate_paper_entry_lifecycle_manifest(connection)

    broker.close_position(positions["options"][0], quote.ltp, "FULL", now, chain.spot)
    broker.close_equity_position(positions["equity"][0], 101.0, "FULL", now)
    broker.close_futures_position(positions["futures"][0], 24_050.0, "FULL", now)
    broker.book_partial_close(
        positions["options"][1], 1, quote.ltp, "PARTIAL", now, chain.spot)
    broker.book_partial_close_equity(
        positions["equity"][1], 37, 101.0, "PARTIAL", now)
    broker.book_partial_close_futures(
        positions["futures"][1], 17, 24_050.0, "PARTIAL", now)
    broker.close_position(
        positions["options"][1], quote.ltp, "REMAINING", now, chain.spot)
    broker.close_equity_position(
        positions["equity"][1], 101.0, "REMAINING", now)
    broker.close_futures_position(
        positions["futures"][1], 24_050.0, "REMAINING", now)
    assert broker.s.scalar(sa.select(sa.func.count()).select_from(Position)) == 0
    assert broker.s.scalar(sa.select(sa.func.count()).select_from(Trade)) == 9
    assert broker.reconcile()["diff"] == pytest.approx(0.0, abs=0.01)
    broker.s.rollback()
    broker.s.close()
    engine.dispose()
