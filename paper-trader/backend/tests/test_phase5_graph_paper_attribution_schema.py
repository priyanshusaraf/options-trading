"""Direct P5.1 contract for independent graph/paper attribution facts."""
from __future__ import annotations

import ast
import datetime as dt
import json
from pathlib import Path
import shutil
from copy import deepcopy
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command

from app.db import migrate
from app.db.models import Base
from app.backtest.identity import execution_result_address
from app.ir.strategies.expanding_z import GRAPH, IMPLEMENTATIONS, LIBRARY
from app.strategy.admission import (
    GRAPH_ATTRIBUTION_MISMATCH,
    GRAPH_ATTRIBUTION_UNVERIFIED,
    GraphAttributionRefused,
    require_attribution_tuple,
)
from app.strategy.ir_adapter import IRGraphStrategy


PRODUCTION_PATHS = frozenset({
    "paper-trader/backend/app/strategy/ir_adapter.py",
    "paper-trader/backend/app/strategy/admission.py",
    "paper-trader/backend/app/core/execution_binding.py",
    "paper-trader/backend/app/core/deployments.py",
    "paper-trader/backend/app/core/deploy_bridge.py",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/app/engine/runner.py",
    "paper-trader/backend/app/engine/execution_lifecycle.py",
    "paper-trader/backend/app/engine/broker_protocol.py",
    "paper-trader/backend/app/engine/broker.py",
    "paper-trader/backend/app/engine/live_broker.py",
    "paper-trader/backend/app/engine/cockpit.py",
    "paper-trader/backend/app/api/routes.py",
    "paper-trader/backend/app/backtest/identity.py",
    "paper-trader/backend/app/backtest/cache.py",
    "paper-trader/backend/app/backtest/sweep.py",
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/migrations/versions/20260824_0040_graph_paper_attribution.py",
    "paper-trader/backend/scripts/backfill_strategy_admissions.py",
    "paper-trader/backend/scripts/ir_shadow_mutations.py",
})

DEPLOYMENT_CONSUMER_TESTS = frozenset({
    "tests/test_deployments.py",
    "tests/test_execution_binding.py",
    "tests/test_execution_http_isolation.py",
    "tests/test_money_repository_isolation.py",
    "tests/test_phase1_multi_tenant_gate.py",
    "tests/test_phase2_closure_producers.py",
    "tests/test_phase4_loader_authority_consumers.py",
    "tests/test_scoped_config.py",
    "tests/test_user_plane_tenant_isolation.py",
})

ATTRIBUTION_TABLES = (
    "deployments", "execution_intents", "positions", "trades",
    "backtest_results",
)
LEGACY_IDS = {
    "deployments": 4101,
    "positions": 4201,
    "trades": 4301,
    "backtest_runs": 4401,
    "backtest_results": 4501,
}


def _metadata_without_0040() -> sa.MetaData:
    """Return the checked-in ORM catalogue projected to the exact 0039 columns.

    Tests use these Table objects only for their historical Python defaults and
    typed inserts. Schema construction still runs the repository migration chain.
    """
    metadata = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        copied = table.to_metadata(metadata)
        if copied.name not in ATTRIBUTION_TABLES:
            continue
        for constraint in tuple(copied.constraints):
            if {column.name for column in constraint.columns} & {
                    "graph_address", "attribution_state"}:
                copied.constraints.remove(constraint)
        copied._columns.remove(copied.c.graph_address)
        copied._columns.remove(copied.c.attribution_state)
    return metadata


def _seed_0039_attribution_corpus(connection) -> dict[str, object]:
    """Seed all five affected tables with scoped, linked, money-bearing history."""
    tables = _metadata_without_0040().tables
    owner = "owner.p5.legacy"
    account = "account.p5.legacy"
    admission = "sha256:" + "9" * 64
    original_version = "legacy-version:版本:" + "f" * 40
    stamp = dt.datetime(2026, 8, 24, 9, 15, 30)
    expiry = dt.date(2026, 9, 24)

    connection.execute(tables["organizations"].insert(), {
        "organization_id": owner, "name": "P5 Legacy Owner", "status": "active",
        "created_at": stamp, "updated_at": stamp,
    })
    connection.execute(tables["broker_accounts"].insert(), {
        "broker_account_id": account, "owner_id": owner, "broker": "mock",
        "external_account_id": "legacy-external", "display_name": "Legacy Account",
        "status": "active", "created_at": stamp, "updated_at": stamp,
    })
    connection.execute(tables["deployments"].insert(), {
        "id": LEGACY_IDS["deployments"], "owner_id": owner, "name": "legacy-graph",
        "strategy_key": "ir.legacy.graph", "strategy_version": original_version,
        "admission_address": admission, "broker_account_id": account,
        "universe_mode": "explicit", "params_json": '{"risk":"legacy"}',
        "allocation": 250000.75, "status": "active", "armed": False,
        "notes": "pre-0040 audit bytes", "created_at": stamp, "updated_at": stamp,
    })
    connection.execute(tables["execution_intents"].insert(), {
        "client_intent_id": "intent-p5-legacy-0001",
        "deployment_id": LEGACY_IDS["deployments"], "owner_id": owner,
        "broker_account_id": account, "broker": "mock", "account_scope": account,
        "connection_scope": "paper", "broker_tag": "p5legacy0001",
        "intent": "ENTRY", "instrument_key": "NIFTY", "tradingsymbol": "NIFTY24SEP",
        "exchange": "NFO", "side": "BUY", "product": "NRML", "order_type": "MARKET",
        "requested_qty": 25, "decision_price": 123.45, "signal_at": stamp,
        "strategy_key": "ir.legacy.graph", "strategy_version": original_version,
        "admission_address": admission, "context_json": '{"legacy":true}',
        "created_at": stamp, "fence_epoch": 7,
    })
    connection.execute(tables["positions"].insert(), {
        "id": LEGACY_IDS["positions"], "owner_id": owner,
        "broker_account_id": account, "deployment_id": LEGACY_IDS["deployments"],
        "entry_intent_id": "intent-p5-legacy-0001", "instrument_key": "NIFTY",
        "direction": "bullish", "option_type": "CE", "tradingsymbol": "NIFTY24SEP",
        "exchange": "NFO", "segment": "options", "strategy_key": "ir.legacy.graph",
        "strategy_version": original_version, "admission_address": admission,
        "strike": 25000.0, "expiry": expiry, "lot_size": 25, "qty": 25,
        "entry_premium": 123.45, "entry_charges": 12.34, "entry_cost": 3086.25,
        "entry_spot": 24980.5, "entry_time": stamp, "entry_reason": "legacy signal",
        "stop_price": 98.75, "target_price": 166.5, "last_premium": 130.0,
        "last_spot": 25010.0, "high_water_premium": 135.0, "mfe": 11.55,
        "mae": -4.25, "held_overnight": True, "overnight_pnl": 37.5,
        "session_close_premium": 128.0, "mode": "paper",
    })
    connection.execute(tables["trades"].insert(), {
        "id": LEGACY_IDS["trades"], "owner_id": owner, "broker_account_id": account,
        "deployment_id": LEGACY_IDS["deployments"],
        "entry_intent_id": "intent-p5-legacy-0001", "instrument_key": "NIFTY",
        "direction": "bullish", "option_type": "CE", "tradingsymbol": "NIFTY24SEP",
        "exchange": "NFO", "segment": "options", "strategy_key": "ir.legacy.graph",
        "strategy_version": original_version, "admission_address": admission,
        "strike": 25000.0, "expiry": expiry, "qty": 25, "entry_premium": 123.45,
        "entry_cost": 3086.25, "entry_spot": 24980.5, "entry_time": stamp,
        "exit_premium": 140.25, "exit_charges": 13.21, "exit_spot": 25030.0,
        "exit_time": stamp + dt.timedelta(minutes=47), "exit_reason": "TARGET",
        "gross_pnl": 420.0, "charges_total": 25.55, "net_pnl": 394.45,
        "return_pct": 12.7801, "holding_minutes": 47.0, "win": True,
        "held_overnight": False, "overnight_pnl": 0.0, "intraday_pnl": 394.45,
        "mode": "paper", "exit_price_estimated": False, "mfe": 16.8, "mae": -4.25,
        "build_sha": None,
    })
    connection.execute(tables["backtest_runs"].insert(), {
        "id": LEGACY_IDS["backtest_runs"], "owner_id": owner, "created_at": stamp,
        "status": "done", "queued_at": stamp, "started_at": stamp,
        "completed_at": stamp + dt.timedelta(minutes=2), "request_json": '{"legacy":true}',
        "scope": "NIFTY", "intervals": "15minute", "capital": 250000.75,
        "total": 1, "done": 1, "window": "legacy", "instruments": "NIFTY",
        "strategies": "ir.legacy.graph", "admission_address": admission,
    })
    connection.execute(tables["backtest_results"].insert(), {
        "id": LEGACY_IDS["backtest_results"], "owner_id": owner,
        "run_id": LEGACY_IDS["backtest_runs"], "cell_key": "legacy-cell-p5",
        "instrument_key": "NIFTY", "name": "NIFTY", "segment": "options",
        "strategy_key": "ir.legacy.graph", "strategy_version": original_version,
        "admission_address": admission, "interval": "15minute", "trades": 3,
        "wins": 2, "win_rate": 66.6667, "profit_factor": 1.75,
        "max_drawdown_pct": 3.125, "return_pct": 8.75, "net_pnl": 21875.65,
        "gross_pnl": 22400.75, "charges": 525.10, "expectancy": 7291.8833,
        "notional": 624512.5, "lots": 1, "affordable": True,
        "option_cost": 3086.25, "first_ts": 1787523300, "last_ts": 1787609700,
        "effective_days": 1, "bars": 75, "curve_json": "[250000.75,271876.4]",
        "bh_curve_json": "[250000.75,251000.0]", "trades_json": '[{"net":394.45}]',
        "params_hash": "a" * 64, "last_candle_ts": 1787609700,
        "schema_version": 7, "from_cache": False, "computed_at": stamp,
    })
    return {"owner_id": owner, "account_id": account,
            "strategy_version": original_version, "admission_address": admission}


def _sqlite_corpus_snapshot(connection) -> dict[str, object]:
    owner = "owner.p5.legacy"
    rows = {}
    for table in ATTRIBUTION_TABLES:
        columns = [item[1] for item in connection.exec_driver_sql(
            f"PRAGMA table_info({table})").all()]
        selected = connection.execute(sa.text(
            f"SELECT * FROM {table} WHERE owner_id=:owner ORDER BY "
            + ("client_intent_id" if table == "execution_intents" else "id")),
            {"owner": owner}).all()
        rows[table] = {"columns": columns, "rows": [tuple(row) for row in selected]}
    sequences = {
        table: connection.execute(sa.text(f"SELECT COALESCE(MAX(id), 0) FROM {table}"))
        .scalar_one()
        for table in ("deployments", "positions", "trades", "backtest_results")
    }
    return {"rows": rows, "sequences": sequences}


def test_owned_production_universe_is_closed_against_the_capsule():
    root = Path(__file__).resolve().parents[3]
    capsule = root / "paper-trader/docs/agent/tasks/phase5-graph-paper-attribution-schema.md"
    document = json.loads(capsule.read_text().split("---", 2)[1])
    assignment = next(item for item in document["assignments"]
                      if item["id"] == "phase5_graph_paper_attribution_implementation")
    declared = frozenset(assignment["write_paths"])
    actual_production = frozenset(
        path for path in declared
        if path.startswith("paper-trader/backend/app/")
        or path.startswith("paper-trader/backend/migrations/")
        or path.startswith("paper-trader/backend/scripts/"))
    assert actual_production == PRODUCTION_PATHS
    assert all((root / path).is_file() for path in PRODUCTION_PATHS)


def test_every_current_create_deployment_consumer_is_in_the_affected_inventory():
    """Repository discovery prevents selective deployment-writer regression runs."""
    backend = Path(__file__).resolve().parents[1]
    def consumes_writer(path: Path) -> bool:
        tree = ast.parse(path.read_text(), filename=str(path))
        return any(
            isinstance(node, ast.Call)
            and ((isinstance(node.func, ast.Name)
                  and node.func.id == "create_deployment")
                 or (isinstance(node.func, ast.Attribute)
                     and node.func.attr == "create_deployment"))
            for node in ast.walk(tree)
        )
    discovered = frozenset(
        path.relative_to(backend).as_posix()
        for path in (backend / "tests").glob("test_*.py")
        if consumes_writer(path)
    )
    assert discovered == DEPLOYMENT_CONSUMER_TESTS
    assert "tests/test_phase2_closure_producers.py" in discovered


def test_strategy_content_version_and_graph_label_are_independent():
    strategy = IRGraphStrategy(GRAPH, (LIBRARY, IMPLEMENTATIONS))
    assert strategy.version == strategy.address
    assert strategy.version.startswith("sha256:") and len(strategy.version) == 71
    assert strategy.graph_version_label == str(GRAPH["version"])
    assert strategy.graph_version_label != strategy.version


def test_source_state_tuple_refuses_missing_mismatched_and_legacy_graph_entries():
    address = "sha256:" + "a" * 64
    require_attribution_tuple(
        strategy_key="ir.graph", strategy_version="12",
        graph_address=address, admission_address="sha256:" + "b" * 64,
        attribution_state="VERIFIED_GRAPH")
    require_attribution_tuple(
        strategy_key="handwritten", strategy_version="content-v1",
        graph_address=None, admission_address=address,
        attribution_state="NON_GRAPH")
    with pytest.raises(GraphAttributionRefused, match=GRAPH_ATTRIBUTION_UNVERIFIED):
        require_attribution_tuple(
            strategy_key="ir.graph", strategy_version="12", graph_address=None,
            admission_address=address, attribution_state="VERIFIED_GRAPH")
    with pytest.raises(GraphAttributionRefused, match=GRAPH_ATTRIBUTION_MISMATCH):
        require_attribution_tuple(
            strategy_key="ir.graph", strategy_version="12", graph_address=None,
            admission_address=address, attribution_state="NON_GRAPH")
    with pytest.raises(GraphAttributionRefused, match=GRAPH_ATTRIBUTION_UNVERIFIED):
        require_attribution_tuple(
            strategy_key="ir.graph", strategy_version=address, graph_address=None,
            admission_address=address, attribution_state="LEGACY_UNVERIFIED")


def test_result_identity_distinguishes_same_label_different_graph_addresses(monkeypatch):
    from app.backtest import identity as identity_module

    manifests = []
    original_canonical = identity_module._canonical_json
    def capture(value):
        if isinstance(value, dict) and value.get("scheme") == "backtest-execution/1":
            manifests.append(value)
        return original_canonical(value)
    monkeypatch.setattr(identity_module, "_canonical_json", capture)
    other = deepcopy(GRAPH)
    other["display_name"] = str(other.get("display_name", "")) + " edited"
    strategies = (
        IRGraphStrategy(GRAPH, (LIBRARY, IMPLEMENTATIONS)),
        IRGraphStrategy(other, (LIBRARY, IMPLEMENTATIONS)),
    )
    addresses = [execution_result_address(
        dataset_address="f" * 64,
        instrument=SimpleNamespace(
            key="NIFTY", name="NIFTY", segment="NFO", lot_size=25,
            strike_step=50, has_options=True),
        strategy=strategy, parameters={}, capital=50_000.0, window={},
        slippage_pct=0.0005, admission_address="sha256:" + "a" * 64,
        strategy_key=strategy.key,
        strategy_version=strategy.graph_version_label,
        graph_address=strategy.version,
        attribution_state="VERIFIED_GRAPH") for strategy in strategies]
    assert all(addresses) and addresses[0] != addresses[1]
    assert [manifest["strategy"]["graph_address"] for manifest in manifests] == [
        strategy.version for strategy in strategies]


def test_exact_0039_sqlite_upgrade_preserves_version_bytes_and_full_addresses(tmp_path):
    from tests.test_schema_migrations import _apply_baseline_ddl

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'p5-attribution.db'}")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0039")
        historical = "sha256:" + "c" * 64
        connection.execute(sa.text(
            "UPDATE deployments SET strategy_version=:version WHERE id=1"),
            {"version": historical})
        command.upgrade(migrate.alembic_config(connection), "0040")
        row = connection.execute(sa.text(
            "SELECT strategy_version,graph_address,attribution_state "
            "FROM deployments WHERE id=1")).one()
        assert row == (historical, None, "LEGACY_UNVERIFIED")

        prefix = "d" * 63
        first = "sha256:" + prefix + "0"
        second = "sha256:" + prefix + "1"
        for index, address in enumerate((first, second), 1):
            connection.execute(sa.text(
                "INSERT INTO deployments "
                "(owner_id,name,strategy_key,strategy_version,graph_address,"
                "admission_address,attribution_state,broker_account_id,universe_mode,"
                "params_json,status,armed,notes,created_at,updated_at) VALUES "
                "('owner',:name,'ir.graph',:label,:graph,:admission,'VERIFIED_GRAPH',"
                "'account.default','explicit','{}','draft',0,'',CURRENT_TIMESTAMP,"
                "CURRENT_TIMESTAMP)"),
                {"name": f"graph-{index}", "label": str(index), "graph": address,
                 "admission": "sha256:" + str(index) * 64})
        rows = connection.execute(sa.text(
            "SELECT graph_address FROM deployments WHERE name LIKE 'graph-%' "
            "ORDER BY name")).scalars().all()
        assert rows == [first, second]
        with pytest.raises(sa.exc.IntegrityError, match=GRAPH_ATTRIBUTION_UNVERIFIED):
            connection.execute(sa.text(
                "INSERT INTO deployments "
                "(owner_id,name,strategy_key,strategy_version,broker_account_id,"
                "universe_mode,params_json,status,armed,notes,created_at,updated_at) VALUES "
                "('owner','stale','ir.graph','1','account.default','explicit','{}',"
                "'draft',0,'',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    assert migrate.schema_version(engine) == "0040"


def test_0040_fresh_model_has_exact_columns_constraints_guards_and_refuses_downgrade(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0040")
    inspector = sa.inspect(engine)
    for table in ("deployments", "execution_intents", "positions", "trades",
                  "backtest_results"):
        columns = {column["name"]: column for column in inspector.get_columns(table)}
        assert columns["graph_address"]["type"].length == 71
        assert columns["attribution_state"]["nullable"] is False
    with engine.begin() as connection:
        trigger_rows = connection.execute(sa.text(
            "SELECT name,sql FROM sqlite_master WHERE type='trigger'")).mappings().all()
        triggers = {row["name"] for row in trigger_rows}
        trigger_sql = {row["name"]: row["sql"] for row in trigger_rows}
    for table in ("deployments", "execution_intents", "positions", "trades",
                  "backtest_results"):
        for operation in ("insert", "update"):
            name = f"{table}_validate_graph_attribution_{operation}"
            assert name in triggers
            assert "length(NEW.graph_address) = 71" in trigger_sql[name]
    assert {f"{table}_refuse_legacy_attribution_insert" for table in
            ("deployments", "execution_intents", "positions", "backtest_results")} <= triggers
    with pytest.raises(RuntimeError, match="refuses destructive"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0039")


def test_sqlite_restore_based_rollback_recovers_exact_0039_bytes(tmp_path):
    from tests.test_schema_migrations import _apply_baseline_ddl

    database = tmp_path / "upgrade.db"
    backup = tmp_path / "pre-0040.db"
    restored = tmp_path / "restored.db"
    engine = sa.create_engine(f"sqlite:///{database}")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0039")
        corpus = _seed_0039_attribution_corpus(connection)
        before = _sqlite_corpus_snapshot(connection)
    engine.dispose()
    shutil.copy2(database, backup)
    engine = sa.create_engine(f"sqlite:///{database}")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0040")
    engine.dispose()
    shutil.copy2(backup, restored)
    restored_engine = sa.create_engine(f"sqlite:///{restored}")
    assert migrate.schema_version(restored_engine) == "0039"
    with restored_engine.connect() as connection:
        after = _sqlite_corpus_snapshot(connection)
        assert after == before
        for table in ATTRIBUTION_TABLES:
            columns = {item["name"] for item in sa.inspect(connection).get_columns(table)}
            assert "graph_address" not in columns and "attribution_state" not in columns
        assert all(
            row["rows"][0][row["columns"].index("strategy_version")]
            == corpus["strategy_version"]
            for row in after["rows"].values()
        )
