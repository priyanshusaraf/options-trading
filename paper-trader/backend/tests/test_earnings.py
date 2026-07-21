"""Earnings-calendar cache (app/core/earnings.py) — NSE board-meetings fetch +
upsert + the staleness/date window the /api/earnings endpoint relies on. All NSE
HTTP is mocked; no network in tests."""
import datetime as dt

import pytest

from app.core import earnings
from app.db.models import Base, EarningsEvent


@pytest.fixture
def session(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path / 'earnings.db'}", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as s:
        yield s


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeSession:
    """Stands in for requests.Session — no real network, keyed by symbol."""

    def __init__(self, by_symbol):
        self._by_symbol = by_symbol
        self.get_calls = []

    def get(self, url, params=None, timeout=None):
        if params is None:  # the cookie-priming GET to nseindia.com
            return _FakeResponse({})
        symbol = params["symbol"]
        self.get_calls.append(symbol)
        if symbol not in self._by_symbol:
            return _FakeResponse([])
        payload = self._by_symbol[symbol]
        if isinstance(payload, Exception):
            raise payload
        return _FakeResponse(payload)


def test_fetch_board_meeting_picks_nearest_upcoming_results_purpose():
    rows = [
        {"bm_date": "30-Aug-2026", "bm_purpose": "Quarterly Results"},
        {"bm_date": "24-Jul-2026", "bm_purpose": "Quarterly Results"},
        {"bm_date": "10-Jul-2026", "bm_purpose": "Dividend"},  # not a results row
    ]
    sess = _FakeSession({"RELIANCE": rows})
    info = earnings.fetch_board_meeting("RELIANCE", sess, today=dt.date(2026, 7, 1))
    assert info == {"date": "2026-07-24", "purpose": "Quarterly Results"}


def test_fetch_board_meeting_ignores_already_past_meetings():
    # Reproduces the real bug: NSE's feed is mostly historical rows, and
    # string-sorting "DD-Mon-YYYY" dates picks nonsense ("17-Jul-2026" sorts
    # before "24-Apr-2026" alphabetically despite being chronologically later).
    # Every row must be parsed and filtered to >= today before picking nearest.
    rows = [
        {"bm_date": "17-Jul-2026", "bm_purpose": "Financial Results"},   # past
        {"bm_date": "24-Apr-2026", "bm_purpose": "Financial Results"},   # past, earlier
    ]
    sess = _FakeSession({"RELIANCE": rows})
    info = earnings.fetch_board_meeting("RELIANCE", sess, today=dt.date(2026, 7, 21))
    assert info is None  # next quarter's date isn't announced yet — correctly "nothing scheduled"


def test_fetch_board_meeting_returns_none_when_nse_has_nothing():
    sess = _FakeSession({})
    assert earnings.fetch_board_meeting("TCS", sess) is None


def test_fetch_board_meeting_returns_none_when_only_non_results_purposes():
    sess = _FakeSession({"TCS": [{"bm_date": "10-Jul-2026", "bm_purpose": "Buyback"}]})
    assert earnings.fetch_board_meeting("TCS", sess, today=dt.date(2026, 7, 1)) is None


def test_fetch_board_meeting_raises_on_transport_failure():
    sess = _FakeSession({"INFY": RuntimeError("boom")})
    with pytest.raises(earnings.NseFetchError):
        earnings.fetch_board_meeting("INFY", sess)


def test_refresh_all_queries_nse_by_bare_symbol_but_caches_by_instrument_key(session, monkeypatch):
    # The regression this guards: instrument keys carry an exchange prefix
    # ("NSE:ANGELONE") but NSE's API needs the bare tradingsymbol
    # ("ANGELONE") — querying with the prefixed key silently returns nothing.
    fake = _FakeSession({
        "ANGELONE": [{"bm_date": "24-Jul-2026", "bm_purpose": "Quarterly Results"}],
    })
    monkeypatch.setattr(earnings, "_session", lambda: fake)

    result = earnings.refresh_all(session, {"NSE:ANGELONE": "ANGELONE"}, today=dt.date(2026, 7, 1))

    assert result == {"ok": 1, "failed": [], "total": 1}
    assert fake.get_calls == ["ANGELONE"]           # queried NSE with the bare symbol
    row = session.get(EarningsEvent, "NSE:ANGELONE")  # cached under the instrument key
    assert row.event_date == dt.date(2026, 7, 24)


def test_refresh_all_upserts_and_survives_one_symbol_failing(session, monkeypatch):
    fake = _FakeSession({
        "RELIANCE": [{"bm_date": "24-Jul-2026", "bm_purpose": "Quarterly Results"}],
        "TCS": RuntimeError("nse down"),
    })
    monkeypatch.setattr(earnings, "_session", lambda: fake)

    result = earnings.refresh_all(session, {"RELIANCE": "RELIANCE", "TCS": "TCS"}, today=dt.date(2026, 7, 1))

    assert result == {"ok": 1, "failed": ["TCS"], "total": 2}
    row = session.get(EarningsEvent, "RELIANCE")
    assert row.event_date == dt.date(2026, 7, 24)
    assert row.purpose == "Quarterly Results"
    assert session.get(EarningsEvent, "TCS") is None


def test_refresh_all_leaves_prior_cache_untouched_on_repeat_failure(session, monkeypatch):
    session.add(EarningsEvent(symbol="TCS", event_date=dt.date(2026, 7, 20),
                               purpose="Quarterly Results",
                               fetched_at=dt.datetime(2026, 7, 15)))
    session.commit()
    fake = _FakeSession({"TCS": RuntimeError("nse down again")})
    monkeypatch.setattr(earnings, "_session", lambda: fake)

    earnings.refresh_all(session, {"TCS": "TCS"}, today=dt.date(2026, 7, 1))

    row = session.get(EarningsEvent, "TCS")
    assert row.event_date == dt.date(2026, 7, 20)  # untouched, not wiped
    assert row.fetched_at == dt.datetime(2026, 7, 15)


def test_refresh_all_updates_existing_row_in_place(session, monkeypatch):
    session.add(EarningsEvent(symbol="RELIANCE", event_date=dt.date(2026, 4, 20),
                               purpose="Quarterly Results",
                               fetched_at=dt.datetime(2026, 4, 15)))
    session.commit()
    fake = _FakeSession({"RELIANCE": [{"bm_date": "24-Jul-2026", "bm_purpose": "Quarterly Results"}]})
    monkeypatch.setattr(earnings, "_session", lambda: fake)

    earnings.refresh_all(session, {"RELIANCE": "RELIANCE"}, today=dt.date(2026, 7, 1))

    rows = session.query(EarningsEvent).filter_by(symbol="RELIANCE").all()
    assert len(rows) == 1
    assert rows[0].event_date == dt.date(2026, 7, 24)


def test_earnings_map_excludes_stale_cache_entries(session):
    session.add(EarningsEvent(symbol="RELIANCE", event_date=dt.date(2026, 7, 24),
                               purpose="Quarterly Results",
                               fetched_at=dt.datetime.now() - dt.timedelta(days=30)))
    session.commit()
    out = earnings.earnings_map(session, ["RELIANCE"], now=dt.date(2026, 7, 20))
    assert out == {}


def test_earnings_map_excludes_past_dates(session):
    session.add(EarningsEvent(symbol="RELIANCE", event_date=dt.date(2026, 7, 1),
                               purpose="Quarterly Results", fetched_at=dt.datetime.now()))
    session.commit()
    out = earnings.earnings_map(session, ["RELIANCE"], now=dt.date(2026, 7, 20))
    assert out == {}


def test_earnings_map_returns_fresh_upcoming_entries(session):
    session.add(EarningsEvent(symbol="RELIANCE", event_date=dt.date(2026, 7, 24),
                               purpose="Quarterly Results", fetched_at=dt.datetime.now()))
    session.commit()
    out = earnings.earnings_map(session, ["RELIANCE", "TCS"], now=dt.date(2026, 7, 20))
    assert out == {"RELIANCE": {"date": "2026-07-24", "purpose": "Quarterly Results"}}


# ── /api/earnings route ───────────────────────────────────────────────────────

def test_earnings_route_only_returns_nse_bse_stocks_with_fresh_cache():
    from fastapi.testclient import TestClient

    from app.core import instruments as inst_registry
    from app.db.models import UniverseInstrument
    from app.db.session import init_db, SessionLocal as _SessionLocal
    from app.engine.runner import EngineRunner
    from app.main import app

    init_db(reset=True)
    with _SessionLocal() as s:
        s.add(UniverseInstrument(
            key="RELIANCE", name="Reliance Industries", segment="NSE", spot_exchange="NSE",
            spot_symbol="RELIANCE", option_name="RELIANCE", lot_size=1, strike_step=1.0,
            priority=999, has_options=False, source="user", on_home=True,
            active=True, mock_spot=2900.0, mock_vol=0.2))
        s.commit()
        # RELIANCE (NSE stock) has a fresh cache entry and must show up; NIFTY
        # (segment NFO, an index) has one too but must be excluded regardless.
        s.add(EarningsEvent(symbol="RELIANCE", event_date=dt.date.today() + dt.timedelta(days=2),
                             purpose="Quarterly Results", fetched_at=dt.datetime.now()))
        s.add(EarningsEvent(symbol="NIFTY", event_date=dt.date.today() + dt.timedelta(days=2),
                             purpose="Quarterly Results", fetched_at=dt.datetime.now()))
        s.commit()
    inst_registry.load_universe()
    app.state.runner = EngineRunner()
    client = TestClient(app)

    res = client.get("/api/earnings").json()
    assert "RELIANCE" in res["earnings"]
    assert res["earnings"]["RELIANCE"]["purpose"] == "Quarterly Results"
    assert "NIFTY" not in res["earnings"]  # index — excluded by segment regardless of cache
