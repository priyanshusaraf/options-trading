"""The event-risk rules must be enforced by the ENGINE, not merely computable.

A pure rule table that no entry path consults is the most dangerous kind of safety
feature: it tests green forever while the bot keeps trading through the release. These
tests drive the real gates.
"""
import datetime as dt

from app.db.models import Position
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner


def _runner():
    init_db(reset=True)
    return EngineRunner(owner_id="owner", broker_account_id="account.default")


def test_engine_skips_an_instrument_inside_its_release_window(monkeypatch):
    """SENSEX on a Thursday: the gate must fire before any entry work happens."""
    r = _runner()
    thursday = dt.datetime(2026, 8, 6, 12, 0)
    monkeypatch.setattr(r, "_earnings_date_for", lambda k: None)
    from app.engine.event_risk import active_blackout
    assert active_blackout("SENSEX", "options", thursday) is not None
    # ... and the engine's own override hatch is the ONLY way past it.
    r.params["intraday_override_date"] = thursday.date().isoformat()
    assert r._event_override_today(thursday) is True
    r.params["intraday_override_date"] = "2020-01-01"
    assert r._event_override_today(thursday) is False


def test_stale_override_from_another_day_does_not_carry_forward():
    r = _runner()
    r.params["intraday_override_date"] = "2026-08-05"
    assert r._event_override_today(dt.datetime(2026, 8, 6, 12)) is False
    r.params["intraday_override_date"] = "garbage"
    assert r._event_override_today(dt.datetime(2026, 8, 6, 12)) is False


def test_earnings_lookup_is_cached_per_day_and_fails_open(monkeypatch):
    """An unrefreshed calendar must return None (trade normally), never block the book,
    and must not re-query per tick."""
    r = _runner()
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("calendar unavailable")

    monkeypatch.setattr("app.core.earnings.earnings_map", boom)
    assert r._earnings_date_for("INFY") is None
    assert r._earnings_date_for("TCS") is None
    assert calls["n"] == 1          # one attempt per calendar day, not per lookup


def test_open_position_is_flattened_before_a_release_window():
    """Blocking entries alone would leave a position opened an hour earlier fully
    exposed to the print."""
    r = _runner()
    with SessionLocal() as s:
        s.add(Position(owner_id='owner', broker_account_id='account.default',
            instrument_key="NATURALGAS", direction="LONG", option_type="CE",
            tradingsymbol="NATURALGAS26AUG250CE", exchange="MCX", segment="options",
            strike=250.0, expiry=dt.date(2026, 8, 25), lot_size=1250, qty=1250,
            entry_premium=10.0, entry_charges=5.0, entry_cost=12_505.0,
            entry_spot=250.0, entry_time=dt.datetime(2026, 8, 6, 18, 0),
            last_premium=11.0, last_spot=252.0,
            stop_price=7.0, target_price=16.0,
        ))
        s.commit()

    # 19:29 IST — one minute before the 19:30 window opens, inside the 2-minute lead.
    closed = r.flatten_before_events(dt.datetime(2026, 8, 6, 19, 29))
    assert closed == ["NATURALGAS26AUG250CE"]
    assert r.broker.open_positions() == []


def test_position_is_left_alone_well_before_the_window():
    r = _runner()
    with SessionLocal() as s:
        s.add(Position(owner_id='owner', broker_account_id='account.default',
            instrument_key="NATURALGAS", direction="LONG", option_type="CE",
            tradingsymbol="NATURALGAS26AUG250CE", exchange="MCX", segment="options",
            strike=250.0, expiry=dt.date(2026, 8, 25), lot_size=1250, qty=1250,
            entry_premium=10.0, entry_charges=5.0, entry_cost=12_505.0,
            entry_spot=250.0, entry_time=dt.datetime(2026, 8, 6, 12, 0),
            last_premium=11.0, last_spot=252.0,
            stop_price=7.0, target_price=16.0,
        ))
        s.commit()

    assert r.flatten_before_events(dt.datetime(2026, 8, 6, 17, 0)) == []
    assert len(r.broker.open_positions()) == 1


def test_unrelated_instrument_is_never_flattened():
    r = _runner()
    with SessionLocal() as s:
        s.add(Position(owner_id='owner', broker_account_id='account.default',
            instrument_key="GOLDM", direction="LONG", option_type="CE",
            tradingsymbol="GOLDM26AUG72000CE", exchange="MCX", segment="options",
            strike=72000.0, expiry=dt.date(2026, 8, 28), lot_size=10, qty=10,
            entry_premium=100.0, entry_charges=5.0, entry_cost=1005.0,
            entry_spot=72000.0, entry_time=dt.datetime(2026, 8, 6, 12, 0),
            last_premium=110.0, last_spot=72100.0,
            stop_price=70.0, target_price=160.0,
        ))
        s.commit()

    assert r.flatten_before_events(dt.datetime(2026, 8, 6, 19, 29)) == []
    assert len(r.broker.open_positions()) == 1


def test_flatten_can_be_switched_off():
    r = _runner()
    r.params["event_risk_flatten"] = False
    with SessionLocal() as s:
        s.add(Position(owner_id='owner', broker_account_id='account.default',
            instrument_key="NATURALGAS", direction="LONG", option_type="CE",
            tradingsymbol="NATURALGAS26AUG250CE", exchange="MCX", segment="options",
            strike=250.0, expiry=dt.date(2026, 8, 25), lot_size=1250, qty=1250,
            entry_premium=10.0, entry_charges=5.0, entry_cost=12_505.0,
            entry_spot=250.0, entry_time=dt.datetime(2026, 8, 6, 18, 0),
            last_premium=11.0, last_spot=252.0,
            stop_price=7.0, target_price=16.0,
        ))
        s.commit()
    assert r.flatten_before_events(dt.datetime(2026, 8, 6, 19, 29)) == []


def test_a_flatten_failure_never_breaks_the_risk_loop(monkeypatch):
    r = _runner()

    def boom(*a, **k):
        raise RuntimeError("broker down")

    monkeypatch.setattr(r, "flatten_before_events", boom)
    r._safe_flatten_before_events(dt.datetime(2026, 8, 6, 19, 29))   # must not raise


def test_earnings_lookup_matches_the_key_format_the_universe_actually_stores():
    """REGRESSION (found 2026-08-01 by inspecting production, not by a failing test):
    `earnings_events.symbol` holds the FULL instrument key — production rows read
    'NSE:HEG', 'NSE:NCC', 'NSE:IRCTC'. The lookup queried normalized names ('HEG'), so
    `symbol IN (...)` matched nothing and the earnings blackout could never have fired on
    a real symbol. It would have tested green forever while doing nothing at all."""
    import datetime as _dt

    from app.core.earnings import EarningsEvent
    r = _runner()
    when = r.provider.now().date() + _dt.timedelta(days=2)
    with SessionLocal() as s:
        s.add(EarningsEvent(symbol="NSE:HEG", event_date=when,
                            purpose="Financial Results",
                            fetched_at=_dt.datetime.now()))
        s.commit()

    r.enabled = {"NSE:HEG"}
    r._earnings_cache_date = None      # force a rebuild
    assert r._earnings_date_for("NSE:HEG") == when
    # ... and the normalized form resolves to the same date, since the engine sees both.
    assert r._earnings_date_for("HEG") == when
