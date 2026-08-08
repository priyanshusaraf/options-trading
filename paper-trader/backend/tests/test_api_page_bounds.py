"""No list read may be asked for an unbounded page.

Companion to `test_analytics_scan_bounds.py`. That file bounds what the *database* is
asked for; this one bounds what a *caller* may ask for. Both are needed: with only the
first, `?limit=10000000` still serialises every row the table holds, which is the 2026-07-23
outage reached from the outside instead of the inside.

The routes are enumerated rather than discovered, because a new list route that forgets its
bound is exactly the regression worth catching, and a test that discovers routes
automatically would silently start covering it as "already fine".
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.paging import MAX_PAGE
from app.db.session import init_db
from app.main import app

# (path, the query parameter that pages it)
BOUNDED_READS = [
    ("/api/trades", "limit"),
    ("/api/logs", "limit"),
    ("/api/ir-shadow", "limit"),
    ("/api/backtest/runs", "limit"),
    ("/api/backtest/results", "limit"),
]

# `/api/ir-shadow` reads `app.state.runner`, which only exists once the engine lanes are
# running. Serving it here would mean `with TestClient(app)` and a real engine start —
# which these assertions do not need and must not provoke. Its *refusal* assertions are
# unaffected and still run above: FastAPI validates `limit` before the handler is entered,
# so the bound is proven on exactly the path that matters, and the 200-side coverage is
# left to the route's own tests rather than faked with a stub runner here.
NEEDS_ENGINE = {"/api/ir-shadow"}
SERVEABLE_READS = [(p, q) for p, q in BOUNDED_READS if p not in NEEDS_ENGINE]


@pytest.fixture(scope="module")
def client():
    # A bare TestClient, NOT `with TestClient(app)` — the context-manager form runs the
    # real lifespan and starts the engine lanes, which these read-only assertions neither
    # need nor should provoke.
    init_db(reset=True)
    return TestClient(app)


@pytest.mark.parametrize("path,param", BOUNDED_READS)
def test_an_absurd_page_is_refused_not_served(client, path, param):
    r = client.get(path, params={param: 10_000_000})
    assert r.status_code == 422, (
        f"{path}?{param}=10000000 returned {r.status_code}; an unbounded page is a "
        f"memory-exhaustion path into the risk lane"
    )


@pytest.mark.parametrize("path,param", SERVEABLE_READS)
def test_the_ceiling_itself_is_accepted(client, path, param):
    """The bound must be a ceiling, not an off-by-one that refuses its own maximum."""
    r = client.get(path, params={param: MAX_PAGE})
    assert r.status_code == 200, (r.status_code, r.text[:200])


@pytest.mark.parametrize("path,param", BOUNDED_READS)
def test_zero_and_negative_pages_are_refused(client, path, param):
    """`limit=0` and `limit=-1` are not pages. Left unbounded below, a negative limit
    reaches SQLite as `LIMIT -1`, which means *no limit at all* — the bound would be
    trivially bypassable in the direction it exists to prevent."""
    for bad in (0, -1):
        r = client.get(path, params={param: bad})
        assert r.status_code == 422, f"{path}?{param}={bad} returned {r.status_code}"


@pytest.mark.parametrize("path,param", SERVEABLE_READS)
def test_the_shipped_default_still_works(client, path, param):
    """The bound must not have changed any working call."""
    assert client.get(path).status_code == 200
