"""SPA serving is env-gated and must never shadow /api or /ws (PT_SERVE_FRONTEND)."""
import importlib

from fastapi.testclient import TestClient


def _build_app(tmp_path, monkeypatch, *, serve: bool):
    # a fake built frontend
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>PT</title>")
    (dist / "assets" / "app.js").write_text("console.log('pt')")

    monkeypatch.setenv("PT_PROVIDER", "mock")
    monkeypatch.setenv("PT_SERVE_FRONTEND", "1" if serve else "0")
    monkeypatch.setenv("PT_FRONTEND_DIST", str(dist))

    # get_settings() is lru_cache'd and main.py builds routes at import time,
    # so reload both to pick up the env for this test.
    from app.core import config
    config.get_settings.cache_clear()
    import app.main as main
    importlib.reload(main)
    return main.app


# NOTE: build the client WITHOUT the `with` context manager, matching the
# codebase convention — that skips the engine lifespan (which deadlocked the
# full suite in other tests) and these SPA routes don't need app.state.runner.

def test_spa_served_at_root(tmp_path, monkeypatch):
    c = TestClient(_build_app(tmp_path, monkeypatch, serve=True))
    r = c.get("/")
    assert r.status_code == 200
    assert "<!doctype html>" in r.text.lower()


def test_spa_fallback_for_client_route(tmp_path, monkeypatch):
    c = TestClient(_build_app(tmp_path, monkeypatch, serve=True))
    r = c.get("/some/deep/client-route")
    assert r.status_code == 200
    assert "<title>PT</title>" in r.text


def test_static_asset_served(tmp_path, monkeypatch):
    c = TestClient(_build_app(tmp_path, monkeypatch, serve=True))
    r = c.get("/assets/app.js")
    assert r.status_code == 200
    assert "console.log" in r.text


def test_api_not_shadowed(tmp_path, monkeypatch):
    c = TestClient(_build_app(tmp_path, monkeypatch, serve=True))
    assert c.get("/api/health").json() == {"ok": True}
    # unknown /api path must 404 as JSON, NOT the SPA index
    r = c.get("/api/does-not-exist")
    assert r.status_code == 404
    assert "<!doctype html>" not in r.text.lower()


def test_serving_off_by_default(tmp_path, monkeypatch):
    c = TestClient(_build_app(tmp_path, monkeypatch, serve=False))
    # health still works; root is NOT the SPA (404 with no catch-all)
    assert c.get("/api/health").json() == {"ok": True}
    assert c.get("/").status_code == 404
