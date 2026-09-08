"""P5 capital-admission schema is additive, guarded and unconsumed."""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path
import shutil
import subprocess

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import Session

from app.db import migrate
from app.db.models import Base, BrokerAccount, Deployment, Organization, SizingPolicyRecord
from tests.test_schema_migrations import (
    _build_from_baseline_at_revision,
    _build_from_models,
)


TABLES = (
    "sizing_policies", "sizing_decisions", "target_position_requests",
    "candidate_intents", "capital_reservation_heads", "decision_batches",
    "portfolio_admission_decisions", "capital_reservations",
    "capital_reservation_events", "position_campaigns", "position_tranches",
    "fill_allocations",
)
IMMUTABLE = {
    "sizing_policies", "sizing_decisions", "target_position_requests",
    "candidate_intents", "decision_batches", "portfolio_admission_decisions",
    "capital_reservation_events", "fill_allocations",
}
NOW = dt.datetime(2026, 8, 25, 12)


def address(char: str) -> str:
    return "sha256:" + char * 64


def _normalize_sql(value: str) -> str:
    result = "".join(value.lower().replace('"', '').split())
    while result.startswith("(") and result.endswith(")"):
        depth = 0
        encloses_all = True
        for index, char in enumerate(result):
            depth += (char == "(") - (char == ")")
            if depth == 0 and index != len(result) - 1:
                encloses_all = False
                break
        if not encloses_all:
            break
        result = result[1:-1]
    return result


def _contract(engine, table: str):
    inspector = sa.inspect(engine)
    columns = [
        (row["name"], str(row["type"]), row["nullable"], str(row["default"]))
        for row in inspector.get_columns(table)
    ]
    foreign = sorted(
        (tuple(row["constrained_columns"]), row["referred_table"],
         tuple(row["referred_columns"]), row["options"].get("ondelete"))
        for row in inspector.get_foreign_keys(table))
    unique = sorted(
        (row["name"], tuple(row["column_names"]))
        for row in inspector.get_unique_constraints(table))
    checks = sorted(
        (row["name"], _normalize_sql(str(row["sqltext"])))
        for row in inspector.get_check_constraints(table))
    primary = tuple(inspector.get_pk_constraint(table)["constrained_columns"])
    with engine.connect() as connection:
        if connection.dialect.name == "sqlite":
            triggers = sorted((row[0], _normalize_sql(row[1] or ""))
                              for row in connection.execute(sa.text(
                "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name=:table"),
                {"table": table}))
        else:
            triggers = sorted((row[0], _normalize_sql(row[1]))
                              for row in connection.execute(sa.text(
                "SELECT tgname,pg_get_triggerdef(t.oid,true) FROM pg_trigger t "
                "JOIN pg_class c ON c.oid=t.tgrelid "
                "WHERE NOT t.tgisinternal AND c.relname=:table"), {"table": table}))
    return dict(columns=columns, foreign=foreign, unique=unique,
                checks=checks, primary=primary, triggers=triggers)


def _seed_scope(engine):
    with Session(engine) as session:
        session.add(Organization(organization_id="owner-a", name="Owner A"))
        session.add(BrokerAccount(
            broker_account_id="account-a", owner_id="owner-a", broker="paper",
            external_account_id="a", display_name="A"))
        session.flush()
        session.add(Deployment(
            id=101, owner_id="owner-a", broker_account_id="account-a", name="D",
            strategy_key=None, strategy_version=None, admission_address=None,
            graph_address=None, attribution_state="NON_GRAPH",
            universe_mode="legacy", params_json="{}", allocation=None,
            status="active", armed=False, notes="", created_at=NOW, updated_at=NOW))
        session.commit()


def _insert_policy_and_decision(connection):
    connection.execute(sa.text(
        "INSERT INTO sizing_policies "
        "(policy_address,policy_id,version,mode,currency,fixed_units,fixed_lots,"
        "amount_minor,rate_ppm,risk_budget_minor,target_volatility_ppm,min_quantity,"
        "max_quantity,max_capital_minor,fee_buffer_minor,safety_buffer_minor,"
        "allow_resize,canonical_json,created_at) VALUES "
        "(:policy,'fixed',1,'FIXED_UNITS','INR',1,NULL,NULL,NULL,NULL,NULL,1,NULL,NULL,"
        "0,0,false,'{}',:now)"), {"policy": address("a"), "now": NOW})
    connection.execute(sa.text(
        "INSERT INTO sizing_decisions "
        "(decision_address,policy_address,product_address,inputs_address,accepted,"
        "requested_quantity,admitted_quantity,required_capital_minor,estimated_fees_minor,"
        "binding_constraint,reason_code,resized,input_addresses_json,decided_at) VALUES "
        "(:decision,:policy,:product,:inputs,true,1,1,100,0,'none','SIZED',false,'[]',:now)"),
        {"decision": address("b"), "policy": address("a"),
         "product": address("c"), "inputs": address("d"), "now": NOW})


def test_fresh_and_exact_0040_upgrade_have_identical_capital_relations(tmp_path):
    fresh = _build_from_models(tmp_path)
    upgraded = _build_from_baseline_at_revision(tmp_path, "capital-0041.db", "0040")
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0041")
    assert migrate.schema_version(upgraded) == "0041"
    assert set(TABLES) <= set(sa.inspect(fresh).get_table_names())
    assert set(TABLES) <= set(sa.inspect(upgraded).get_table_names())
    for table in TABLES:
        assert _contract(upgraded, table) == _contract(fresh, table), table


def test_0041_preserves_every_preexisting_table_column_and_row(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "capital-preserve.db", "0040")
    with engine.begin() as connection:
        before_schema = {
            table: tuple((row["name"], str(row["type"]), row["nullable"])
                         for row in sa.inspect(connection).get_columns(table))
            for table in ("organizations", "broker_accounts", "deployments",
                          "execution_intents", "positions", "trades")
        }
        before_rows = {
            table: tuple(connection.execute(sa.text(
                f"SELECT * FROM {table} ORDER BY rowid")))
            for table in before_schema
        }
        command.upgrade(migrate.alembic_config(connection), "0041")
        after_schema = {
            table: tuple((row["name"], str(row["type"]), row["nullable"])
                         for row in sa.inspect(connection).get_columns(table))
            for table in before_schema
        }
        after_rows = {
            table: tuple(connection.execute(sa.text(
                f"SELECT * FROM {table} ORDER BY rowid")))
            for table in before_schema
        }
    assert after_schema == before_schema and after_rows == before_rows


def test_0041_restart_after_interrupted_table_creation_is_idempotent(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "capital-interrupt.db", "0040")
    stopped = False

    def interrupt(_conn, _cursor, statement, _params, _context, _many):
        nonlocal stopped
        if not stopped and "CREATE TABLE CAPITAL_RESERVATION_HEADS" in " ".join(
                statement.upper().split()):
            stopped = True
            raise RuntimeError("0041 interruption")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="interruption"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0041")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0041")
    assert migrate.schema_version(engine) == "0041"
    assert set(TABLES) <= set(sa.inspect(engine).get_table_names())


def test_0041_refuses_a_stale_partial_table_without_mutation(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "capital-stale.db", "0040")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE sizing_policies (attacker TEXT)"))
        before = connection.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE name='sizing_policies'")) .scalar_one()
        with pytest.raises(RuntimeError, match="partial/stale"):
            command.upgrade(migrate.alembic_config(connection), "0041")
        assert connection.execute(sa.text(
            "SELECT sql FROM sqlite_master WHERE name='sizing_policies'")) .scalar_one() == before


def test_immutable_policy_and_graph_attribution_guards_are_real(tmp_path):
    engine = _build_from_models(tmp_path)
    _seed_scope(engine)
    with engine.begin() as connection:
        _insert_policy_and_decision(connection)
    with engine.begin() as connection:
        with pytest.raises(DatabaseError, match="immutable"):
            connection.execute(sa.text(
                "UPDATE sizing_policies SET policy_id='changed'"))
    with engine.begin() as connection:
        with pytest.raises(DatabaseError, match="GRAPH_ATTRIBUTION_UNVERIFIED"):
            connection.execute(sa.text(
                "INSERT INTO target_position_requests "
                "(request_id,request_address,owner_id,broker_account_id,book,deployment_id,"
                "strategy_key,strategy_version,admission_address,graph_address,attribution_state,"
                "canonical_instrument_key,product_address,sizing_decision_address,target_quantity,"
                "purpose,group_id,decision_at) VALUES "
                "('r',:request,'owner-a','account-a','paper',101,'ir.bad','1',:admission,NULL,"
                "'NON_GRAPH','NIFTY',:product,:decision,1,'ENTRY','',:now)"),
                {"request": address("e"), "admission": address("f"),
                 "product": address("c"), "decision": address("b"), "now": NOW})


def test_policy_address_primary_mode_json_and_money_constraints_are_real(tmp_path):
    engine = _build_from_models(tmp_path)
    invalid_rows = (
        ("bad-address", 1, None, "{}"),
        (address("a"), 1, 1, "{}"),
        (address("a"), 1, None, "not-json"),
    )
    for policy_address, fixed_units, fixed_lots, canonical_json in invalid_rows:
        with pytest.raises((DatabaseError, IntegrityError)):
            with engine.begin() as connection:
                connection.execute(sa.text(
                    "INSERT INTO sizing_policies "
                    "(policy_address,policy_id,version,mode,currency,fixed_units,fixed_lots,"
                    "amount_minor,rate_ppm,risk_budget_minor,target_volatility_ppm,min_quantity,"
                    "max_quantity,max_capital_minor,fee_buffer_minor,safety_buffer_minor,"
                    "allow_resize,canonical_json,created_at) VALUES "
                    "(:address,'fixed',1,'FIXED_UNITS','INR',:units,:lots,NULL,NULL,NULL,NULL,"
                    "1,NULL,NULL,0,0,false,:document,:now)"),
                    {"address": policy_address, "units": fixed_units, "lots": fixed_lots,
                     "document": canonical_json, "now": NOW})


def test_money_columns_are_bigint_or_integer_never_float(tmp_path):
    engine = _build_from_models(tmp_path)
    inspector = sa.inspect(engine)
    for table in TABLES:
        for column in inspector.get_columns(table):
            if column["name"].endswith(("_minor", "_quantity", "_ppm", "_scaled")):
                assert "FLOAT" not in str(column["type"]).upper(), (table, column)


def _insert_lineage_rows(connection):
    connection.execute(sa.text(
            "INSERT INTO position_campaigns "
            "(campaign_id,campaign_address,owner_id,broker_account_id,book,deployment_id,"
            "strategy_key,strategy_version,admission_address,graph_address,attribution_state,"
            "canonical_instrument_key,execution_instrument_key,product_address,direction,"
            "target_policy_address,position_id,status,opened_at,closed_at,revision) VALUES "
            "('campaign',:campaign,'owner-a','account-a','paper',101,NULL,NULL,NULL,NULL,"
            "'NON_GRAPH','NIFTY','NIFTY-FUT',:product,'LONG',:policy,NULL,'open',:now,NULL,0)"),
            {"campaign": address("1"), "product": address("2"),
             "policy": address("3"), "now": NOW})
    connection.execute(sa.text(
            "INSERT INTO position_tranches "
            "(tranche_id,tranche_address,campaign_id,target_position_request_id,"
            "candidate_intent_id,batch_id,decision_id,reservation_id,execution_intent_id,"
            "purpose,requested_quantity,admitted_quantity,state,created_at,terminal_at,revision) "
            "VALUES ('tranche',:tranche,'campaign',NULL,NULL,NULL,NULL,NULL,NULL,"
            "'REDUCTION',-1,-1,'planned',:now,NULL,0)"),
            {"tranche": address("4"), "now": NOW})


def _insert_lineage_identity_rows(engine):
    _seed_scope(engine)
    with engine.begin() as connection:
        _insert_lineage_rows(connection)


def test_lineage_address_identity_and_delete_guards_match_fresh_and_upgraded(tmp_path):
    fresh = _build_from_models(tmp_path)
    upgraded = _build_from_baseline_at_revision(tmp_path, "lineage-guards.db", "0040")
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0041")
    for engine in (fresh, upgraded):
        _insert_lineage_identity_rows(engine)
        for statement in (
                "UPDATE position_campaigns SET opened_at=:changed WHERE campaign_id='campaign'",
                "UPDATE position_campaigns SET position_id=999 WHERE campaign_id='campaign'",
                "UPDATE position_tranches SET execution_intent_id='other' "
                "WHERE tranche_id='tranche'"):
            with pytest.raises(DatabaseError, match="identity is immutable"):
                with engine.begin() as connection:
                    connection.execute(sa.text(statement), {
                        "changed": NOW + dt.timedelta(seconds=1)})
        for table, identity in (
                ("position_tranches", "tranche_id='tranche'"),
                ("position_campaigns", "campaign_id='campaign'")):
            with pytest.raises(DatabaseError, match="is durable"):
                with engine.begin() as connection:
                    connection.execute(sa.text(
                        f"DELETE FROM {table} WHERE {identity}"))


def test_only_the_unwired_shadow_recovery_modules_consume_capital_admission_models():
    names = {
        "SizingPolicyRecord", "SizingDecisionRecord", "TargetPositionRequestRecord",
        "CandidateIntentRecord", "CapitalReservationHead", "DecisionBatchRecord",
        "PortfolioAdmissionDecisionRecord", "CapitalReservationRecord",
        "CapitalReservationEventRecord", "PositionCampaignRecord",
        "PositionTrancheRecord", "FillAllocationRecord",
    }
    consumers = {}
    root = Path(__file__).resolve().parents[1] / "app"
    for path in root.rglob("*.py"):
        if path.name == "models.py":
            continue
        parsed = ast.parse(path.read_text(encoding="utf-8"))
        used = sorted({node.id for node in ast.walk(parsed)
                       if isinstance(node, ast.Name) and node.id in names})
        if used:
            consumers[path.relative_to(root).as_posix()] = used
    assert consumers == {
        "execution/capital_admission.py": [
            "CandidateIntentRecord", "CapitalReservationEventRecord",
            "CapitalReservationHead", "CapitalReservationRecord",
            "DecisionBatchRecord", "PortfolioAdmissionDecisionRecord",
            "SizingDecisionRecord", "TargetPositionRequestRecord",
        ],
        "execution/capital_recovery.py": [
            "CapitalReservationEventRecord", "CapitalReservationHead",
            "CapitalReservationRecord",
        ],
        "execution/capital_shadow.py": [
            "CandidateIntentRecord", "CapitalReservationRecord",
            "DecisionBatchRecord", "PortfolioAdmissionDecisionRecord",
        ],
        "execution/leases.py": [
            "CandidateIntentRecord", "CapitalReservationEventRecord",
            "CapitalReservationRecord",
        ],
        "execution/position_lineage.py": [
            "CandidateIntentRecord", "CapitalReservationRecord",
            "FillAllocationRecord", "PortfolioAdmissionDecisionRecord",
            "PositionCampaignRecord", "PositionTrancheRecord",
            "TargetPositionRequestRecord",
        ],
    }


def test_0041_downgrade_refuses_without_dropping_facts(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, "capital-down.db", "0040")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0041")
        connection.execute(sa.text(
            "INSERT INTO sizing_policies "
            "(policy_address,policy_id,version,mode,currency,fixed_units,fixed_lots,"
            "amount_minor,rate_ppm,risk_budget_minor,target_volatility_ppm,min_quantity,"
            "max_quantity,max_capital_minor,fee_buffer_minor,safety_buffer_minor,allow_resize,"
            "canonical_json,created_at) VALUES (:a,'fixed',1,'FIXED_UNITS','INR',1,NULL,NULL,"
            "NULL,NULL,NULL,1,NULL,NULL,0,0,false,'{}',:now)"), {"a": address("a"), "now": NOW})
        with pytest.raises(RuntimeError, match="refuses destructive"):
            command.downgrade(migrate.alembic_config(connection), "0040")
        assert connection.execute(sa.text(
            "SELECT policy_id FROM sizing_policies")).scalar_one() == "fixed"
    assert migrate.schema_version(engine) == "0041"


def _capital_snapshot(connection):
    rows = {
        table: [tuple(row) for row in connection.execute(sa.text(
            f"SELECT * FROM {table} ORDER BY 1"))]
        for table in TABLES
    }
    return {
        "head": connection.execute(sa.text(
            "SELECT version_num FROM alembic_version")).scalar_one(),
        "rows": rows,
        "contracts": {table: _contract(connection.engine, table) for table in TABLES},
    }


def test_postgresql16_exact_0040_interruption_restart_and_clean_restore(
        pg_sandbox, tmp_path):
    from tests.test_postgres_execution_schema import _install_repository_0037_catalog

    fresh = pg_sandbox.engine("capital_0041_fresh")
    upgraded = pg_sandbox.engine("capital_0041_upgrade")
    restored = pg_sandbox.engine("capital_0041_restore")
    assert migrate.init_schema(
        fresh, create_all=lambda: Base.metadata.create_all(fresh),
        legacy_migrate=lambda: pytest.fail("legacy migration ran"),
        expected_tables=Base.metadata.tables) == "0041"

    with upgraded.begin() as connection:
        _install_repository_0037_catalog(connection)
        command.stamp(migrate.alembic_config(connection), "0037")
        command.upgrade(migrate.alembic_config(connection), "0040")
    assert migrate.schema_version(upgraded) == "0040"
    assert set(TABLES).isdisjoint(sa.inspect(upgraded).get_table_names())

    interrupted = False

    def interrupt(_conn, _cursor, statement, _parameters, _context, _many):
        nonlocal interrupted
        if (not interrupted and "CREATE TABLE DECISION_BATCHES" in
                " ".join(statement.upper().split())):
            interrupted = True
            raise RuntimeError("0041 PostgreSQL interruption")

    sa.event.listen(upgraded, "after_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="0041 PostgreSQL interruption"):
            with upgraded.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0041")
    finally:
        sa.event.remove(upgraded, "after_cursor_execute", interrupt)
    assert interrupted and migrate.schema_version(upgraded) == "0040"
    assert set(TABLES).isdisjoint(sa.inspect(upgraded).get_table_names())

    upgraded.dispose()
    upgraded = sa.create_engine(pg_sandbox.url("capital_0041_upgrade"), future=True)
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0041")
    assert migrate.schema_version(upgraded) == "0041"
    for table in TABLES:
        assert _contract(upgraded, table) == _contract(fresh, table), table

    _seed_scope(upgraded)
    with upgraded.begin() as connection:
        _insert_policy_and_decision(connection)
        connection.execute(sa.text(
            "INSERT INTO capital_reservation_heads "
            "(owner_id,broker_account_id,book,currency,revision,updated_at) "
            "VALUES ('owner-a','account-a','paper','INR',0,:now)"), {"now": NOW})
        _insert_lineage_rows(connection)
    with upgraded.connect() as connection:
        source = _capital_snapshot(connection)

    tool_directories = (
        Path("/opt/homebrew/opt/postgresql@16/bin"),
        Path("/usr/local/opt/postgresql@16/bin"),
        Path("/opt/local/lib/postgresql16/bin"),
    )
    pg_dump = shutil.which("pg_dump") or next(
        (str(path / "pg_dump") for path in tool_directories
         if (path / "pg_dump").is_file()), None)
    pg_restore = shutil.which("pg_restore") or next(
        (str(path / "pg_restore") for path in tool_directories
         if (path / "pg_restore").is_file()), None)
    assert pg_dump and pg_restore
    assert "16.14" in subprocess.run(
        [pg_dump, "--version"], check=True, capture_output=True, text=True).stdout
    backup = tmp_path / "capital-0041.dump"
    source_url = str(sa.engine.make_url(pg_sandbox.url(
        "capital_0041_upgrade")).set(drivername="postgresql"))
    restore_url = str(sa.engine.make_url(pg_sandbox.url(
        "capital_0041_restore")).set(drivername="postgresql"))
    subprocess.run([
        pg_dump, "--format=custom", "--no-owner", "--no-acl",
        f"--file={backup}", source_url,
    ], check=True, capture_output=True, text=True)
    subprocess.run([
        pg_restore, "--no-owner", "--no-acl", "--exit-on-error",
        f"--dbname={restore_url}", str(backup),
    ], check=True, capture_output=True, text=True)
    with restored.connect() as connection:
        recovered = _capital_snapshot(connection)
    assert recovered["head"] == source["head"]
    assert recovered["rows"] == source["rows"]
    for table in TABLES:
        recovered_contract = recovered["contracts"][table]
        source_contract = source["contracts"][table]
        for field in ("columns", "foreign", "unique", "primary", "triggers"):
            assert recovered_contract[field] == source_contract[field], (table, field)
        # pg_dump/pg_restore may deparse equivalent ARRAY/enum casts differently;
        # names plus direct behavior are the stable restore contract.
        assert [name for name, _sql in recovered_contract["checks"]] == [
            name for name, _sql in source_contract["checks"]]
    with pytest.raises(sa.exc.DBAPIError):
        with restored.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO sizing_policies "
                "(policy_address,policy_id,version,mode,currency,fixed_units,fixed_lots,"
                "amount_minor,rate_ppm,risk_budget_minor,target_volatility_ppm,min_quantity,"
                "max_quantity,max_capital_minor,fee_buffer_minor,safety_buffer_minor,"
                "allow_resize,canonical_json,created_at) VALUES "
                "('bad','bad',1,'FIXED_UNITS','INR',1,NULL,NULL,NULL,NULL,NULL,1,NULL,NULL,"
                "0,0,false,'{}',:now)"), {"now": NOW})
    for statement in (
            "UPDATE position_campaigns SET opened_at=:changed WHERE campaign_id='campaign'",
            "UPDATE position_campaigns SET position_id=999 WHERE campaign_id='campaign'",
            "UPDATE position_tranches SET execution_intent_id='other' "
            "WHERE tranche_id='tranche'",
            "DELETE FROM position_tranches WHERE tranche_id='tranche'",
            "DELETE FROM position_campaigns WHERE campaign_id='campaign'"):
        with pytest.raises(sa.exc.DBAPIError):
            with restored.begin() as connection:
                connection.execute(sa.text(statement), {
                    "changed": NOW + dt.timedelta(seconds=1)})
