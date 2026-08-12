"""The research-run driver's plan must sweep BOTH 15m and 30m so each strategy is
evaluated on both of its native timeframes (the strategy is invalid on anything
slower or faster). The dev-blacklist filtering must still apply on every interval."""
import importlib
import contextlib
from types import SimpleNamespace

from research.operations import OperationAlreadyRunning


def _load():
    import scripts.research_run as rr
    return importlib.reload(rr)


def test_plan_sweeps_both_15m_and_30m(monkeypatch):
    monkeypatch.delenv("PT_WATCHLIST_SNAPSHOT", raising=False)
    rr = _load()
    plan = rr._plan(lambda k: k)          # identity instrument factory
    assert {item["interval"] for item in plan} == {"15minute", "30minute"}


def test_plan_runs_every_strategy_on_every_interval(monkeypatch):
    monkeypatch.delenv("PT_WATCHLIST_SNAPSHOT", raising=False)
    rr = _load()
    plan = rr._plan(lambda k: k)
    pairs = {(item["strategy_key"], item["interval"]) for item in plan}
    assert len(pairs) == len(plan)        # no duplicate (strategy, interval) cell
    for sk in ("trend_impulse_v3", "expanding_z_v4"):
        for iv in ("15minute", "30minute"):
            assert (sk, iv) in pairs


def test_plan_respects_dev_blacklist_on_every_interval(monkeypatch, tmp_path):
    import json
    snap = tmp_path / "wl.json"
    snap.write_text(json.dumps({"in_watchlists": ["NIFTY", "BANKNIFTY"]}))
    monkeypatch.setenv("PT_WATCHLIST_SNAPSHOT", str(snap))
    rr = _load()
    plan = rr._plan(lambda k: k)
    # NIFTY/BANKNIFTY are committed (and not in the always-allowed sandbox) -> excluded
    for item in plan:
        assert "NIFTY" not in item["instruments"]
        assert "BANKNIFTY" not in item["instruments"]
    # every interval is still represented after filtering
    assert {item["interval"] for item in plan} == {"15minute", "30minute"}


def test_manual_entry_point_reports_shared_lock_conflict(monkeypatch):
    rr = _load()
    monkeypatch.setattr(rr, "_enforce_isolation", lambda: "research.db")
    monkeypatch.setattr(rr, "_research_enabled", lambda: True)
    monkeypatch.setattr(
        rr,
        "_run_enabled_operation",
        lambda _research_db: (_ for _ in ()).throw(OperationAlreadyRunning()),
    )

    assert rr.main() == 2


def test_manual_entry_point_enforces_isolation_before_operation(monkeypatch):
    import pytest

    rr = _load()
    calls = []
    monkeypatch.setattr(
        rr, "_enforce_isolation",
        lambda: (_ for _ in ()).throw(RuntimeError("isolation failed")),
    )
    monkeypatch.setattr(rr, "_run_enabled_operation", lambda _db: calls.append(_db))

    with pytest.raises(RuntimeError, match="isolation failed"):
        rr.main()
    assert calls == []


def test_manual_entry_point_freeze_precedes_operation_receipt(monkeypatch):
    rr = _load()
    calls = []
    monkeypatch.setattr(rr, "_enforce_isolation", lambda: "research.db")
    monkeypatch.setattr(rr, "_research_enabled", lambda: False)
    monkeypatch.setattr(rr, "_run_enabled_operation", lambda _db: calls.append(_db))

    assert rr.main() == 0
    assert calls == []


def test_manual_operation_forwards_the_required_owner_to_every_research_call(monkeypatch):
    """The CLI has no compatibility owner: both manual paths receive the env owner."""
    rr = _load()
    monkeypatch.setenv("PT_RESEARCH_OWNER_ID", "manual-owner")
    monkeypatch.setattr(rr, "_plan", lambda _instrument: [])
    monkeypatch.setattr(rr, "_dump_db", lambda _session: None)
    monkeypatch.setattr(rr, "UNIVERSE", ("NIFTY",))
    monkeypatch.setattr(rr, "INTERVALS", ("day",))
    seen = []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class Engine:
        def dispose(self):
            pass

    class Recorder:
        @staticmethod
        def start(*_args, **_kwargs):
            return Recorder()

        def transition(self, *_args):
            pass

        def start_watchdog(self, *_args, **_kwargs):
            pass

        def set_plan(self, *_args):
            pass

        def add_completed_run(self, *_args):
            pass

        def complete(self, **_kwargs):
            pass

        def fail(self, **_kwargs):
            pass

    import app.core.config as config
    import app.core.instruments as instruments
    import app.providers.factory as providers
    import research.data.store as data_store
    import research.domain.base as domain_base
    import research.domain.operations as domain_operations
    import research.operations as operations
    import research.orchestrator.generate as generate
    import research.orchestrator.run as run
    import research.universe as universe

    monkeypatch.setattr(config, "get_settings", lambda: SimpleNamespace(provider="mock"))
    monkeypatch.setattr(instruments, "get_instrument", lambda key: SimpleNamespace(key=key))
    monkeypatch.setattr(providers, "get_provider", lambda: SimpleNamespace(name="mock"))
    monkeypatch.setattr(data_store, "KiteDataSource", lambda provider: provider)
    monkeypatch.setattr(domain_base, "make_engine", lambda _path: Engine())
    monkeypatch.setattr(domain_base, "init_research_db", lambda _engine: None)
    monkeypatch.setattr(domain_base, "make_sessionmaker", lambda _engine: Session)
    monkeypatch.setattr(domain_operations, "DurableOperationRecorder", Recorder)
    monkeypatch.setattr(domain_operations, "ResearchOperationRepository", lambda session: session)
    monkeypatch.setattr(operations, "safe_plan_summary", lambda plan: plan)
    monkeypatch.setattr(universe, "ALWAYS_ALLOWED", frozenset({"NIFTY"}))
    monkeypatch.setattr(run, "run_nightly", lambda *_args, **kwargs: seen.append(("nightly", kwargs["owner_id"])) or [])
    monkeypatch.setattr(generate, "run_generated", lambda *_args, **kwargs: seen.append(("generated", kwargs["owner_id"])) or [])

    reports, provider = rr._run_enabled_operation("research.db")

    assert reports == []
    assert provider == "mock"
    assert seen == [("nightly", "manual-owner"), ("generated", "manual-owner")]
