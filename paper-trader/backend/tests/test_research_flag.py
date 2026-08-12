"""Research-plane freeze (PT_RESEARCH_ENABLED, default OFF).

The autonomous research plane — the /api/portfolio promotions/deploy surface and
the research UI and operations — is frozen behind one Settings flag so it cannot
interfere with the live engine. Generated execution artifacts always hydrate because
the engine may already be assigned one. Off (the default): the portfolio routes answer
403 and /api/status reports the flag so the cockpit hides the Portfolio tab. On: the
research surfaces work as before. The core
universe endpoints in routes.py (/api/portfolio/add|remove|add-bulk|home) are NOT
part of the plane and must stay open either way.
"""
from fastapi.testclient import TestClient
import pytest

from app.core.config import get_settings
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    app.state.runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    return TestClient(app)


def test_research_disabled_by_default():
    # the frozen state must be the default — no env, no .env entry, no research
    assert get_settings().research_enabled is False


def test_portfolio_routes_403_when_research_disabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "research_enabled", False)
    c = _client()
    for method, path in [
        ("GET", "/api/portfolio/promotions"),
        ("GET", "/api/portfolio/watchlists"),
        ("GET", "/api/portfolio/archive"),
        ("POST", "/api/portfolio/deploy"),
    ]:
        r = c.request(method, path)
        assert r.status_code == 403, f"{method} {path} -> {r.status_code}"
        assert "research" in r.json()["detail"].lower()


def test_portfolio_routes_open_when_research_enabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    c = _client()
    assert c.get("/api/portfolio/watchlists").status_code == 200
    assert c.get("/api/portfolio/archive").status_code == 200


def test_core_portfolio_endpoints_unaffected_by_freeze(monkeypatch):
    # routes.py's universe management shares the /api/portfolio prefix but is CORE
    monkeypatch.setattr(get_settings(), "research_enabled", False)
    c = _client()
    assert c.get("/api/portfolio/home").status_code == 200


def test_status_reports_research_flag(monkeypatch):
    c = _client()
    monkeypatch.setattr(get_settings(), "research_enabled", False)
    assert c.get("/api/status").json()["research_enabled"] is False
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    assert c.get("/api/status").json()["research_enabled"] is True


def _spy_register_all(monkeypatch):
    """Spy on the startup generated-strategy registration (imported lazily in
    lifespan as `from app.core.generated_strategies import register_all`, so
    patching the module attribute intercepts it)."""
    from app.core import generated_strategies
    calls = []
    monkeypatch.setattr(generated_strategies, "register_all",
                        lambda s, *, owner_id: calls.append((s, owner_id)))
    return calls


def test_lifespan_hydrates_legacy_owner_generated_artifacts_when_research_disabled(monkeypatch):
    from app.db.models import LEGACY_OWNER_ID

    monkeypatch.setattr(get_settings(), "research_enabled", False)
    calls = _spy_register_all(monkeypatch)
    with TestClient(app):   # context manager runs the real lifespan (mock provider)
        pass
    assert len(calls) == 1
    assert calls[0][1] == LEGACY_OWNER_ID


def test_lifespan_registers_generated_strategies_when_enabled(monkeypatch):
    from app.db.models import LEGACY_OWNER_ID

    monkeypatch.setattr(get_settings(), "research_enabled", True)
    calls = _spy_register_all(monkeypatch)
    with TestClient(app):
        pass
    assert len(calls) == 1
    assert calls[0][1] == LEGACY_OWNER_ID


def test_lifespan_hydrates_every_execution_owner_before_restart_dispatch(monkeypatch):
    """A non-legacy tenant's generated deployment must resolve after a process restart."""
    from app.db.models import Organization, BacktestRun
    from app.db.session import SessionLocal
    import app.main as main_module

    init_db(reset=True)
    with SessionLocal() as session:
        session.add(Organization(organization_id="tenant", name="Tenant")); session.flush()
        session.add(BacktestRun(owner_id="tenant", status="pending", scope="liquid")); session.commit()
    calls = _spy_register_all(monkeypatch)
    monkeypatch.setattr(main_module, "init_db", lambda *, reset: None)
    with TestClient(app):
        pass
    assert {owner for _, owner in calls} >= {"owner", "tenant"}


def test_disabled_research_startup_evicts_a_corrupt_legacy_generated_artifact(monkeypatch):
    import json

    from app.core import generated_strategies
    from app.db.models import LEGACY_OWNER_ID
    from app.db.session import SessionLocal
    from app.strategy import registry
    from app.strategy.registry import StrategyNotFound
    import app.main as main_module

    composition = {
        "key": "gen_startup_corrupt",
        "longEntry": {"all": ["ema_slope_up(50,5)"]},
        "shortEntry": {"all": ["ema_slope_down(50,5)"]},
        "longExit": {"any": ["ema_slope_down(50,5)"]},
        "shortExit": {"any": ["ema_slope_up(50,5)"]},
    }
    init_db(reset=True)
    try:
        with SessionLocal() as session:
            generated_strategies.save_generated(
                session, composition["key"], json.dumps(composition),
                owner_id=LEGACY_OWNER_ID)
            session.commit()
            assert generated_strategies.register_all(
                session, owner_id=LEGACY_OWNER_ID) == 1
            session.get(
                generated_strategies.GeneratedStrategyRow,
                (LEGACY_OWNER_ID, composition["key"]),
            ).composition_json = "{}"
            session.commit()

        monkeypatch.setattr(get_settings(), "research_enabled", False)
        # Preserve the deliberately corrupt persistent row across the mock-provider boot.
        monkeypatch.setattr(main_module, "init_db", lambda *, reset: None)
        with TestClient(app):
            with pytest.raises(StrategyNotFound):
                registry.resolve_strategy(composition["key"], owner_id=LEGACY_OWNER_ID)
    finally:
        registry._GENERATED_REGISTRY.pop(
            (LEGACY_OWNER_ID, composition["key"]), None)
