"""Journal REST surface. Uses a TestClient with PT_JOURNAL_DB_PATH pointed at a
temp file (isolation — never touches the owner's real journal.db)."""
import os
import tempfile

os.environ["PT_JOURNAL_DB_PATH"] = os.path.join(tempfile.gettempdir(), "journal_pytest.db")

from fastapi.testclient import TestClient

from app.main import app


def _client():
    # fresh DB per test run
    path = os.environ["PT_JOURNAL_DB_PATH"]
    if os.path.exists(path):
        os.remove(path)
    return TestClient(app)


def test_instruments_seeded_on_first_call():
    c = _client()
    res = c.get("/api/journal/instruments").json()
    symbols = {r["symbol"] for r in res["instruments"]}
    assert {"GOLDM", "SILVERM", "CRUDEOILM", "NATGASM"} <= symbols


def test_add_and_list_trade_roundtrip():
    c = _client()
    r = c.post("/api/journal/trades", json={
        "symbol": "GOLDM", "direction": "LONG", "lots": 1,
        "entry_price": 72000.0, "setup_tag": "breakout",
    })
    assert r.status_code == 200
    trade_id = r.json()["id"]
    rows = c.get("/api/journal/trades").json()["trades"]
    assert any(t["id"] == trade_id for t in rows)


def test_close_trade_route():
    c = _client()
    trade_id = c.post("/api/journal/trades", json={
        "symbol": "GOLDM", "direction": "LONG", "lots": 1, "entry_price": 72000.0,
    }).json()["id"]
    r = c.post(f"/api/journal/trades/{trade_id}/close", json={"exit_price": 72500.0})
    assert r.status_code == 200
    assert r.json()["exit_price"] == 72500.0


def test_add_missed_route():
    c = _client()
    r = c.post("/api/journal/missed", json={
        "symbol": "SILVERM", "direction": "SHORT", "skip_reason": "away from desk",
    })
    assert r.status_code == 200
    assert r.json()["id"] is not None


def test_stats_route():
    c = _client()
    trade_id = c.post("/api/journal/trades", json={
        "symbol": "GOLDM", "direction": "LONG", "lots": 1, "entry_price": 72000.0,
        "setup_tag": "breakout",
    }).json()["id"]
    c.post(f"/api/journal/trades/{trade_id}/close", json={"exit_price": 72500.0})
    r = c.get("/api/journal/stats")
    assert r.status_code == 200
    assert "breakout" in r.json()["by_tag"]


def test_views_route_create_and_list():
    c = _client()
    r = c.post("/api/journal/views", json={"name": "swing-2026", "thesis": "test"})
    assert r.status_code == 200
    rows = c.get("/api/journal/views").json()["views"]
    assert any(v["name"] == "swing-2026" for v in rows)
