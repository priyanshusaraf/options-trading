"""REST surface for multi-journal workbooks.

Books are created/listed/archived over HTTP, and every dated endpoint takes a
`book_id` so the UI can switch journals. Omitting it keeps the pre-books behaviour
(the default book), so an old client never breaks.
"""
import os
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path):
    """A fresh journal.db per test — the routes module caches its sessionmaker."""
    path = str(tmp_path / f"journal_{next(tempfile._get_candidate_names())}.db")
    monkeypatch.setenv("PT_JOURNAL_DB_PATH", path)
    from app.journal import routes as jr
    monkeypatch.setattr(jr, "_SessionLocal", None)
    monkeypatch.setattr(jr, "_engine", None)
    app = FastAPI()
    app.include_router(jr.router)
    with TestClient(app) as c:
        yield c


def _books(c):
    return c.get("/api/journal/books").json()["books"]


def test_default_book_is_listed_out_of_the_box(client):
    books = _books(client)
    assert len(books) == 1 and books[0]["is_default"] is True


def test_create_and_list_a_book(client):
    r = client.post("/api/journal/books", json={"name": "NIFTY",
                                                "description": "index options"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "NIFTY"
    assert {b["name"] for b in _books(client)} == {"General", "NIFTY"}


def test_duplicate_book_name_is_rejected(client):
    client.post("/api/journal/books", json={"name": "NIFTY"})
    assert client.post("/api/journal/books", json={"name": "NIFTY"}).status_code == 400


def test_archive_hides_the_book(client):
    bid = client.post("/api/journal/books", json={"name": "OLD"}).json()["id"]
    assert client.post(f"/api/journal/books/{bid}/archive").status_code == 200
    assert "OLD" not in {b["name"] for b in _books(client)}
    everything = client.get("/api/journal/books?include_archived=true").json()["books"]
    assert "OLD" in {b["name"] for b in everything}


def test_the_default_book_cannot_be_archived_over_http(client):
    bid = [b for b in _books(client) if b["is_default"]][0]["id"]
    assert client.post(f"/api/journal/books/{bid}/archive").status_code == 400


def test_archiving_an_unknown_book_404s(client):
    assert client.post("/api/journal/books/9999/archive").status_code == 404


# ── entries are scoped to their book ─────────────────────────────────────
def _add_trade(c, book_id=None):
    body = {"symbol": "GOLDM", "direction": "LONG", "lots": 1, "entry_price": 72000.0}
    if book_id is not None:
        body["book_id"] = book_id
    return c.post("/api/journal/trades", json=body)


def test_a_trade_lands_in_the_named_book_only(client):
    nifty = client.post("/api/journal/books", json={"name": "NIFTY"}).json()["id"]
    assert _add_trade(client, book_id=nifty).status_code == 200

    in_nifty = client.get(f"/api/journal/trades?book_id={nifty}").json()["trades"]
    in_default = client.get("/api/journal/trades").json()["trades"]
    assert len(in_nifty) == 1
    assert in_default == [], "the trade leaked into the default journal"


def test_omitting_book_id_uses_the_default_book(client):
    assert _add_trade(client).status_code == 200
    assert len(client.get("/api/journal/trades").json()["trades"]) == 1


def test_an_unknown_book_id_is_rejected_not_silently_defaulted(client):
    """Silently writing to the wrong journal is worse than an error."""
    assert _add_trade(client, book_id=4242).status_code == 400


def test_the_day_feed_is_per_book(client):
    nifty = client.post("/api/journal/books", json={"name": "NIFTY"}).json()["id"]
    client.post("/api/journal/days", json={"entry_date": "2026-07-27",
                                           "market_view": "weak bullish",
                                           "book_id": nifty})
    client.post("/api/journal/days", json={"entry_date": "2026-07-27",
                                           "market_view": "gold consolidating"})

    nifty_feed = client.get(f"/api/journal/feed?book_id={nifty}").json()["days"]
    default_feed = client.get("/api/journal/feed").json()["days"]
    assert [d["market_view"] for d in nifty_feed] == ["weak bullish"]
    assert [d["market_view"] for d in default_feed] == ["gold consolidating"]


def test_the_same_date_can_exist_in_two_books(client):
    """journal_days used to be keyed on the date alone — the second write 500'd."""
    nifty = client.post("/api/journal/books", json={"name": "NIFTY"}).json()["id"]
    a = client.post("/api/journal/days", json={"entry_date": "2026-07-27",
                                               "market_view": "nifty", "book_id": nifty})
    b = client.post("/api/journal/days", json={"entry_date": "2026-07-27",
                                               "market_view": "gold"})
    assert (a.status_code, b.status_code) == (200, 200)


def test_stats_are_per_book(client):
    """`stats` excludes still-open trades, so a missed setup is what actually
    proves the scoping here."""
    nifty = client.post("/api/journal/books", json={"name": "NIFTY"}).json()["id"]
    client.post("/api/journal/missed", json={
        "symbol": "GOLDM", "direction": "SHORT", "skip_reason": "was away",
        "book_id": nifty})

    assert client.get("/api/journal/stats").json()["missed_summary"]["count"] == 0
    scoped = client.get(f"/api/journal/stats?book_id={nifty}").json()
    assert scoped["missed_summary"]["count"] == 1


def test_notes_are_per_book(client):
    nifty = client.post("/api/journal/books", json={"name": "NIFTY"}).json()["id"]
    client.post("/api/journal/notes", json={"body": "index note", "book_id": nifty})
    assert [d["notes"] for d in
            client.get("/api/journal/feed").json()["days"]] == []
    nifty_days = client.get(f"/api/journal/feed?book_id={nifty}").json()["days"]
    assert nifty_days[0]["notes"][0]["body"] == "index note"
