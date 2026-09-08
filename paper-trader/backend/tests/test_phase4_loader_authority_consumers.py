"""Current-byte consumer coverage for the Phase 4 admission loader.

These tests exercise the real consumer methods.  The only injected object is the
constructor-authorised fixture registry; the production loader itself is never
replaced.  A contextless Phase 4 receipt must refuse before any consumer can
create durable work, resolve execution identity, or mutate the money book.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.backtest import repository
from app.core import deployments, execution_binding
from app.db.models import BacktestRun, BrokerAccount, Deployment, Position, Trade
from app.db.session import SessionLocal, init_db
from app.engine.broker import PaperBroker
from app.engine.runner import EngineRunner


@pytest.fixture(autouse=True)
def _database():
    init_db(reset=True)


@pytest.fixture()
def phase4_receipt(monkeypatch):
    from tests.test_backtest_admission import _persist_phase4_fixture

    registry, wrapper = _persist_phase4_fixture()
    monkeypatch.setattr("app.ir.library.REGISTRY", registry)
    return wrapper


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_enqueue_consumer_refuses_before_durable_job(phase4_receipt):
    with SessionLocal() as session:
        before = _count(session, BacktestRun)
        with pytest.raises(repository.AdmissionRequired) as caught:
            repository.enqueue_run(
                session, owner_id="owner-a", scope="liquid",
                intervals="15minute", capital=50_000.0, total=1,
                admission_address=phase4_receipt.admission_address,
                request_json="{}",
            )
        assert caught.value.args == ("PHASE4_CONTEXT_REQUIRED",)
        assert _count(session, BacktestRun) == before


def test_deployment_create_consumer_refuses_before_row_or_event(phase4_receipt):
    with SessionLocal() as session:
        before = _count(session, Deployment)
        with pytest.raises(ValueError, match="^PHASE4_CONTEXT_REQUIRED$"):
            deployments.create_deployment(
                session, "phase4-refused",
                strategy_key=f"ir.{phase4_receipt.graph_identifier}",
                admission_address=phase4_receipt.admission_address,
                owner_id="owner-a", broker_account_id="account.phase4",
            )
        assert _count(session, Deployment) == before
        assert session.scalar(select(Deployment).where(
            Deployment.name == "phase4-refused")) is None


def test_deployment_resolver_refuses_before_execution_identity(
        phase4_receipt, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.strategy.admission.matches_execution_identity",
        lambda *_args, **_kwargs: calls.append(True) or True,
    )
    with SessionLocal() as session:
        session.add(BrokerAccount(
            broker_account_id="account.phase4", owner_id="owner-a",
            broker="paper", external_account_id="phase4",
            display_name="Phase 4", status="active",
        ))
        row = Deployment(
            owner_id="owner-a", name="phase4-existing",
            strategy_key=f"ir.{phase4_receipt.graph_identifier}",
            strategy_version=str(phase4_receipt.graph_version),
            graph_address=phase4_receipt.graph_address,
            attribution_state="VERIFIED_GRAPH",
            admission_address=phase4_receipt.admission_address,
            broker_account_id="account.phase4", universe_mode="explicit",
            params_json="{}", status=deployments.DRAFT, armed=False,
        )
        session.add(row)
        session.flush()
        with pytest.raises(ValueError, match="^PHASE4_CONTEXT_REQUIRED$"):
            deployments.resolve_deployment_strategy(
                session, row.id, owner_id="owner-a",
                broker_account_id="account.phase4")
        assert calls == []


def test_runner_consumer_refuses_before_execution_identity(
        phase4_receipt, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.strategy.admission.matches_execution_identity",
        lambda *_args, **_kwargs: calls.append(True) or True,
    )
    runner = SimpleNamespace(_session=SessionLocal)
    binding = SimpleNamespace(
        owner_id="owner-a",
        admission_address=phase4_receipt.admission_address,
        strategy_key=f"ir.{phase4_receipt.graph_identifier}",
        strategy_version=phase4_receipt.graph_version,
    )
    with pytest.raises(execution_binding.AuthorityNotGranted) as caught:
        EngineRunner._require_entry_receipt(runner, binding)
    assert caught.value.source == "PHASE4_CONTEXT_REQUIRED"
    assert calls == []


def test_broker_consumer_refuses_before_money_side_effect(
        phase4_receipt, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.strategy.admission.matches_execution_identity",
        lambda *_args, **_kwargs: calls.append(True) or True,
    )
    with SessionLocal() as session:
        before = (_count(session, Position), _count(session, Trade))
        broker = SimpleNamespace(s=session, owner_id="owner-a")
        with pytest.raises(ValueError, match="^PHASE4_CONTEXT_REQUIRED$"):
            PaperBroker._require_current_entry_receipt(
                broker, admission_address=phase4_receipt.admission_address,
                strategy_key=f"ir.{phase4_receipt.graph_identifier}",
                strategy_version=str(phase4_receipt.graph_version),
                graph_address=phase4_receipt.graph_address,
                attribution_state="VERIFIED_GRAPH",
            )
        assert (_count(session, Position), _count(session, Trade)) == before
        assert calls == []


def test_every_production_loader_callsite_has_an_explicit_consumer_mapping():
    """Freeze the complete static source map supporting the dynamic selectors."""
    backend = Path(__file__).resolve().parents[1]
    expected = {
        "app/backtest/repository.py": {"_verify_enqueue_admission": 1},
        "app/backtest/sweep.py": {
            "start_sweep": 2,
            "_verify_worker_admission": 1,
            "_verify_claimed_admission": 1,
            "dispatch_reclaimable": 2,
            "phase4_loader": 2,
        },
        "app/core/deployments.py": {
            "_require_current_deployment_admission": 1,
            "resolve_deployment_strategy": 1,
        },
        "app/engine/runner.py": {"_require_entry_receipt": 1},
        "app/engine/broker.py": {"_require_current_entry_receipt": 1},
    }

    actual = {}
    for relative in expected:
        tree = ast.parse((backend / relative).read_text())
        mapped = {}
        for function in (node for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            count = sum(
                1 for node in ast.walk(function)
                if isinstance(node, ast.Call)
                and ((isinstance(node.func, ast.Name)
                      and node.func.id == "load_verified_admission")
                     or (isinstance(node.func, ast.Attribute)
                         and node.func.attr == "load_verified_admission"))
            )
            if count:
                mapped[function.name] = count
        actual[relative] = mapped

    assert actual == expected


def test_phase4_dependency_verifiers_keep_research_receipt_before_consumers():
    """The loader's research receipt/graph proof cannot be a post-return check."""
    backend = Path(__file__).resolve().parents[1]
    source = (backend / "app/core/strategy_admissions.py").read_text()
    tree = ast.parse(source)
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "require_phase4_current"
    )
    positions = {
        node.func.id: node.lineno
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in {
            "require_current", "require_research_admission",
            "load_verified_dataset_authority", "load_capability_assessment",
        }
    }
    assert positions == {
        "require_current": positions["require_current"],
        "require_research_admission": positions["require_research_admission"],
        "load_verified_dataset_authority": positions["load_verified_dataset_authority"],
        "load_capability_assessment": positions["load_capability_assessment"],
    }
    assert positions["require_current"] < positions["require_research_admission"]
    assert positions["require_research_admission"] < positions[
        "load_verified_dataset_authority"
    ] < positions["load_capability_assessment"]
