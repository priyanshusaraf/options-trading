"""Journal REST surface. Uses a TestClient with PT_JOURNAL_DB_PATH pointed at a
temp file (isolation — never touches the owner's real journal.db)."""
import os
import tempfile

os.environ["PT_JOURNAL_DB_PATH"] = os.path.join(tempfile.gettempdir(), "journal_pytest.db")

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _client():
    # fresh DB per test run — also reset routes.py's module-level DB singleton,
    # otherwise the already-open engine keeps serving the previous file's rows.
    path = os.environ["PT_JOURNAL_DB_PATH"]
    from app.journal import routes as journal_routes
    if journal_routes._engine is not None:
        journal_routes._engine.dispose()
    journal_routes._engine = None
    journal_routes._SessionLocal = None
    # remove the WAL sidecars too — a fresh main .db beside stale -wal/-shm
    # files makes SQLite raise "disk I/O error" on the next open.
    for suffix in ("", "-wal", "-shm"):
        p = path + suffix
        if os.path.exists(p):
            os.remove(p)
    return TestClient(app)


@pytest.fixture
def client():
    return _client()


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


def test_feed_endpoint_empty_ok(client):
    r = client.get("/api/journal/feed")
    assert r.status_code == 200
    body = r.json()
    assert {b["horizon"] for b in body["bias"]} == {"6M", "1M"}
    assert body["days"] == []


def test_day_and_note_and_bias_flow(client):
    assert client.post("/api/journal/days", json={
        "entry_date": "2026-07-17", "market_view": "broke 24200"}).status_code == 200
    note = client.post("/api/journal/notes", json={
        "body": "exited early", "noted_at": "2026-07-17T10:00:00"})
    assert note.status_code == 200
    nid = note.json()["id"]
    assert client.put("/api/journal/bias/6M",
                      json={"stance": "bullish", "note": "uptrend"}).status_code == 200

    feed = client.get("/api/journal/feed").json()
    day = next(d for d in feed["days"] if d["date"] == "2026-07-17")
    assert day["market_view"] == "broke 24200"
    assert any(n["body"] == "exited early" for n in day["notes"])
    assert next(b for b in feed["bias"] if b["horizon"] == "6M")["stance"] == "bullish"

    assert client.delete(f"/api/journal/notes/{nid}").status_code == 200
    assert client.delete(f"/api/journal/notes/{nid}").status_code == 404


def test_note_unknown_instrument_400(client):
    r = client.post("/api/journal/notes", json={"body": "x", "instrument_symbol": "NOPE"})
    assert r.status_code == 400


def test_bias_unknown_horizon_400(client):
    r = client.put("/api/journal/bias/3Y", json={"stance": "x"})
    assert r.status_code == 400
