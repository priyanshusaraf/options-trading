"""Research-plane freeze (PT_RESEARCH_ENABLED, default OFF).

The autonomous research plane — the /api/portfolio promotions/deploy surface and
the startup registration of generated strategies — is frozen behind one Settings
flag so it cannot interfere with the live engine. Off (the default): the portfolio
routes answer 403, startup registers nothing, and /api/status reports the flag so
the cockpit hides the Portfolio tab. On: everything works as before. The core
universe endpoints in routes.py (/api/portfolio/add|remove|add-bulk|home) are NOT
part of the plane and must stay open either way.
"""
from fastapi.testclient import TestClient

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
    app.state.runner = EngineRunner()
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
                        lambda s: calls.append(s))
    return calls


def test_lifespan_skips_generated_registration_when_disabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "research_enabled", False)
    calls = _spy_register_all(monkeypatch)
    with TestClient(app):   # context manager runs the real lifespan (mock provider)
        pass
    assert calls == []


def test_lifespan_registers_generated_strategies_when_enabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "research_enabled", True)
    calls = _spy_register_all(monkeypatch)
    with TestClient(app):
        pass
    assert len(calls) == 1
