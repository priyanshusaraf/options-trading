"""Fail-closed capital guardrails — the most important tests in the research plane.

These pin the structural boundary that makes "research is autonomous, capital
allocation is not" a property of the code rather than a convention: the research
process must be unable to (a) open the execution database, (b) import the
broker/runner/live-execution modules, or (c) run with live execution enabled in
its environment. If any of these tests weakens, capital safety is at risk.
"""
import pytest

from research.guards import (
    ResearchIsolationError,
    assert_capital_safe,
    assert_distinct_databases,
    assert_no_execution_engine_imported,
    enforce,
)


def test_distinct_databases_rejects_identical_paths(tmp_path):
    db = str(tmp_path / "same.db")
    with pytest.raises(ResearchIsolationError):
        assert_distinct_databases(db, db)


def test_distinct_databases_rejects_paths_resolving_to_same_file(tmp_path):
    real = tmp_path / "paper_trader.db"
    real.write_text("")
    a = str(real)
    b = str(tmp_path / "." / "paper_trader.db")  # same file, different spelling
    with pytest.raises(ResearchIsolationError):
        assert_distinct_databases(a, b)


def test_distinct_databases_allows_different_paths(tmp_path):
    # no raise
    assert_distinct_databases(str(tmp_path / "research.db"),
                              str(tmp_path / "paper_trader.db"))


def test_rejects_when_runner_imported():
    with pytest.raises(ResearchIsolationError):
        assert_no_execution_engine_imported({"app.engine.runner": object()})


def test_rejects_when_live_broker_imported():
    with pytest.raises(ResearchIsolationError):
        assert_no_execution_engine_imported({"app.engine.live_broker": object()})


def test_rejects_when_broker_factory_imported():
    with pytest.raises(ResearchIsolationError):
        assert_no_execution_engine_imported({"app.engine.broker_factory": object()})


def test_allows_when_no_execution_engine_modules():
    # pure kernels are allowed; only capital-moving modules are forbidden
    assert_no_execution_engine_imported({"app.backtest.engine": object(),
                                         "app.strategy.registry": object(),
                                         "research.guards": object()})


def test_capital_safe_rejects_live_execution_env():
    with pytest.raises(ResearchIsolationError):
        assert_capital_safe({"PT_EXECUTION": "live"})


def test_capital_safe_rejects_live_execution_env_case_insensitive():
    with pytest.raises(ResearchIsolationError):
        assert_capital_safe({"PT_EXECUTION": "LIVE"})


def test_capital_safe_allows_paper_and_unset():
    assert_capital_safe({"PT_EXECUTION": "paper"})
    assert_capital_safe({})


def test_enforce_raises_on_identical_db(tmp_path):
    db = str(tmp_path / "x.db")
    with pytest.raises(ResearchIsolationError):
        enforce(research_db=db, exec_db=db, loaded_modules={}, env={})


def test_enforce_raises_on_forbidden_import(tmp_path):
    with pytest.raises(ResearchIsolationError):
        enforce(research_db=str(tmp_path / "r.db"), exec_db=str(tmp_path / "e.db"),
                loaded_modules={"app.engine.runner": object()}, env={})


def test_enforce_passes_when_isolated(tmp_path):
    # no raise: distinct DBs, no forbidden imports, paper env
    enforce(research_db=str(tmp_path / "research.db"),
            exec_db=str(tmp_path / "paper_trader.db"),
            loaded_modules={"app.backtest.engine": object()},
            env={"PT_EXECUTION": "paper"})
