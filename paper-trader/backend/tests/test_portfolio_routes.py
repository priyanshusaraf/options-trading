"""Portfolio API: deploy (preview + commit), watchlists/archive reads, and lifecycle
status control. Deploy is staged config only — the endpoint never arms or trades."""
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.main import app
from fastapi.testclient import TestClient


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


def test_deploy_dry_run_previews_without_writing():
    c = _client()
    body = {"watchlist_name": "Bullion", "strategy_key": "trend_impulse_v3",
            "proposals": [{"instrument_key": "GOLDM", "score": 0.8}], "dry_run": True}
    res = c.post("/api/portfolio/deploy", json=body).json()
    assert res["dry_run"] is True and res["accepted"] == ["GOLDM"]
    assert c.get("/api/portfolio/watchlists").json()["watchlists"] == []   # nothing written


def test_deploy_commits_and_shows_in_watchlists_and_archive():
    c = _client()
    body = {"watchlist_name": "Bullion", "strategy_key": "trend_impulse_v3",
            "proposals": [{"instrument_key": "GOLDM", "score": 0.8},
                          {"instrument_key": "SILVERM", "score": 0.7}], "source": "builtin"}
    res = c.post("/api/portfolio/deploy", json=body).json()
    assert set(res["assigned"]) == {"GOLDM", "SILVERM"}
    assert "staged" in res["note"]
    wls = c.get("/api/portfolio/watchlists").json()["watchlists"]
    assert wls[0]["name"] == "Bullion"
    assert set(wls[0]["instruments"]) == {"GOLDM", "SILVERM"}
    arch = c.get("/api/portfolio/archive").json()["strategies"]
    assert any(a["strategy_key"] == "trend_impulse_v3" and a["status"] == "running" for a in arch)


def test_deploy_blocks_an_incumbent():
    c = _client()
    c.post("/api/portfolio/deploy", json={
        "watchlist_name": "A", "strategy_key": "expanding_z_v4",
        "proposals": [{"instrument_key": "SILVERM", "score": 0.9}]})
    res = c.post("/api/portfolio/deploy", json={
        "watchlist_name": "B", "strategy_key": "trend_impulse_v3",
        "proposals": [{"instrument_key": "SILVERM", "score": 0.99},
                      {"instrument_key": "GOLDM", "score": 0.5}]}).json()
    assert res["assigned"] == ["GOLDM"]
    assert any(r["instrument"] == "SILVERM" and r["reason"] == "incumbent"
               for r in res["rejected"])


def test_watchlist_status_can_be_paused():
    c = _client()
    c.post("/api/portfolio/deploy", json={
        "watchlist_name": "Bullion", "strategy_key": "trend_impulse_v3",
        "proposals": [{"instrument_key": "GOLDM", "score": 0.8}]})
    res = c.post("/api/portfolio/watchlists/Bullion/status", json={"status": "paused"}).json()
    assert res["status"] == "paused"


def test_archive_lifecycle_transitions_and_rejects_illegal():
    c = _client()
    c.post("/api/portfolio/deploy", json={
        "watchlist_name": "Bullion", "strategy_key": "trend_impulse_v3",
        "proposals": [{"instrument_key": "GOLDM", "score": 0.8}]})           # -> running
    ok = c.post("/api/portfolio/archive/trend_impulse_v3/status",
                json={"status": "probation"}).json()
    assert ok["status"] == "probation"
    bad = c.post("/api/portfolio/archive/trend_impulse_v3/status",
                 json={"status": "candidate"}).json()                        # probation->candidate illegal
    assert "error" in bad
