import pytest
from fastapi.testclient import TestClient

from app.ledger import db as ledger_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PT_LEDGER_DB_PATH", str(tmp_path / "ledger.db"))
    ledger_db._sessionmaker = None
    from app.main import app
    with TestClient(app) as c:
        yield c
    ledger_db._sessionmaker = None


def test_get_snapshot_404_when_empty(client):
    assert client.get("/api/ledger/snapshot").status_code == 404


def test_first_put_with_null_base_version_creates_v1(client):
    r = client.put("/api/ledger/snapshot",
                   json={"base_version": None, "payload": {"trades": []}})
    assert r.status_code == 200
    assert r.json()["version"] == 1


def test_round_trip(client):
    client.put("/api/ledger/snapshot",
               json={"base_version": None, "payload": {"trades": [{"id": "t1"}]}})
    r = client.get("/api/ledger/snapshot")
    assert r.status_code == 200
    assert r.json() == {"version": 1, "payload": {"trades": [{"id": "t1"}]}}


def test_stale_base_version_is_409_and_reports_current(client):
    client.put("/api/ledger/snapshot", json={"base_version": None, "payload": {}})
    client.put("/api/ledger/snapshot", json={"base_version": 1, "payload": {"a": 1}})
    r = client.put("/api/ledger/snapshot",
                   json={"base_version": 1, "payload": {"b": 2}})
    assert r.status_code == 409
    assert r.json()["current"] == 2


def test_second_null_base_version_is_409(client):
    client.put("/api/ledger/snapshot", json={"base_version": None, "payload": {}})
    r = client.put("/api/ledger/snapshot", json={"base_version": None, "payload": {}})
    assert r.status_code == 409


def test_conflict_does_not_write(client):
    client.put("/api/ledger/snapshot", json={"base_version": None, "payload": {"keep": 1}})
    client.put("/api/ledger/snapshot", json={"base_version": 1, "payload": {"keep": 2}})
    client.put("/api/ledger/snapshot", json={"base_version": 1, "payload": {"clobber": 1}})
    assert client.get("/api/ledger/snapshot").json()["payload"] == {"keep": 2}


def test_artifact_round_trip(client):
    r = client.post("/api/ledger/artifacts",
                    files={"file": ("a.png", b"\x89PNG-bytes", "image/png")},
                    data={"artifact_id": "art_1"})
    assert r.status_code == 200 and r.json()["id"] == "art_1"

    g = client.get("/api/ledger/artifacts/art_1")
    assert g.status_code == 200
    assert g.content == b"\x89PNG-bytes"
    assert g.headers["content-type"].startswith("image/png")

    assert client.delete("/api/ledger/artifacts/art_1").status_code == 200
    assert client.get("/api/ledger/artifacts/art_1").status_code == 404


def test_artifact_upload_is_idempotent_on_id(client):
    for body in (b"one", b"two"):
        client.post("/api/ledger/artifacts",
                    files={"file": ("a.png", body, "image/png")},
                    data={"artifact_id": "art_dup"})
    assert client.get("/api/ledger/artifacts/art_dup").content == b"two"


# ── Manual fills ──────────────────────────────────────────────────────────

def _seed_fill(order_id="o1", verdict="MANUAL"):
    from datetime import datetime
    from app.ledger.db import get_sessionmaker
    from app.ledger.models import LedgerManualFill
    with get_sessionmaker()() as s, s.begin():
        s.add(LedgerManualFill(
            order_id=order_id, tradingsymbol="NIFTY25000CE", exchange="NFO",
            product="NRML", side="BUY", qty=65, avg_price=120.5,
            order_ts=datetime(2026, 7, 31, 9, 30), fill_ts=None,
            verdict=verdict, raw="{}", seen_at=datetime(2026, 7, 31, 9, 31)))


def test_lists_unclaimed_fills(client):
    _seed_fill()
    r = client.get("/api/ledger/manual-fills?unclaimed=true")
    assert r.status_code == 200
    assert [f["order_id"] for f in r.json()["fills"]] == ["o1"]


def test_the_broker_price_is_returned_so_the_owner_never_types_it(client):
    _seed_fill()
    f = client.get("/api/ledger/manual-fills").json()["fills"][0]
    assert f["avg_price"] == 120.5 and f["qty"] == 65 and f["side"] == "BUY"


def test_claiming_removes_it_from_the_queue(client):
    _seed_fill()
    assert client.post("/api/ledger/manual-fills/o1/claim",
                       json={"trade_id": "tr_1"}).status_code == 200
    assert client.get("/api/ledger/manual-fills?unclaimed=true").json()["fills"] == []


def test_claiming_twice_is_a_conflict_not_a_silent_overwrite(client):
    _seed_fill()
    client.post("/api/ledger/manual-fills/o1/claim", json={"trade_id": "tr_1"})
    r = client.post("/api/ledger/manual-fills/o1/claim", json={"trade_id": "tr_2"})
    assert r.status_code == 409
    assert r.json()["trade_id"] == "tr_1"


def test_claiming_an_unknown_order_is_404(client):
    r = client.post("/api/ledger/manual-fills/nope/claim", json={"trade_id": "t"})
    assert r.status_code == 404


def test_needs_review_rows_are_listed_and_flagged(client):
    _seed_fill(verdict="NEEDS_REVIEW")
    f = client.get("/api/ledger/manual-fills").json()["fills"][0]
    assert f["verdict"] == "NEEDS_REVIEW"
