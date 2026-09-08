"""Expiry-day guard SCOPE — block only the expiring index, not the whole book.

#9 sat out the weekly-expiry weekday (Tuesday) for EVERY entry. The owner's call
(2026-07-28): on expiry day only NIFTY needs to sit out; the intraday-equity names are
unaffected by a NIFTY expiry and should keep trading.

`expiry_day_block_keys` decides the scope on the blocked weekday:
  "*"              -> block ALL entries (the pre-2026-07-28 behaviour)
  "NIFTY"          -> block only NIFTY (the new default)
  "NIFTY,SENSEX"   -> block a set
  ""               -> fail SAFE, same as "*" (a cleared field must not silently
                      remove the guard)

The weekday selector (`intraday_block_weekday`) and the per-day opt-in
(`intraday_override_date`) keep their existing meaning and still win outright.
"""
import datetime as dt

import pytest

from app.core.logging import log
from app.core.market_hours import ist_epoch
from app.db.session import init_db
from app.db.models import LEGACY_DEPLOYMENT_ID
from app.core import paper_authority
from app.engine.risk_controls import intraday_blocked_for_expiry_day
from app.engine.runner import EngineRunner
from app.providers.factory import get_provider
from tests.admitted_entry import persist_admitted_entry


@pytest.fixture(autouse=True)
def _restore_mock_clock():
    """The provider is a PROCESS-WIDE singleton, so `provider.now = lambda: ...` leaks
    into every later test in the run. Parking it on a Tuesday left NIFTY permanently
    expiry-blocked and broke test_notify_engine. Restore the real method after each test."""
    provider = get_provider()
    had_stub = "now" in provider.__dict__
    original = provider.__dict__.get("now")
    yield
    if had_stub:
        provider.now = original
    else:
        provider.__dict__.pop("now", None)

TUE = dt.date(2026, 6, 30)      # NIFTY weekly expiry
WED = dt.date(2026, 7, 1)


def _blocked(key, block_keys, today=TUE, override=""):
    return intraday_blocked_for_expiry_day(today, override, 1, key, block_keys)


# ── scope: only the listed keys sit out ──────────────────────────────────
def test_nifty_is_blocked_on_expiry_day():
    assert _blocked("NIFTY", "NIFTY") is True


def test_an_equity_name_still_trades_on_expiry_day():
    """The whole point: a NIFTY expiry says nothing about SUZLON."""
    assert _blocked("SUZLON", "NIFTY") is False


def test_star_blocks_every_key():
    """Back-compat: "*" restores the old block-the-whole-book behaviour."""
    assert _blocked("SUZLON", "*") is True
    assert _blocked("NIFTY", "*") is True


def test_blank_scope_fails_safe_and_blocks_everything():
    """A cleared field must not silently disable a safety guard."""
    assert _blocked("SUZLON", "") is True


def test_a_list_blocks_each_member():
    assert _blocked("NIFTY", "NIFTY,SENSEX") is True
    assert _blocked("SENSEX", "NIFTY,SENSEX") is True
    assert _blocked("BANKNIFTY", "NIFTY,SENSEX") is False


def test_list_tolerates_spacing_and_case():
    assert _blocked("SENSEX", " nifty , sensex ") is True


def test_no_key_supplied_falls_back_to_blocking():
    """Defensive: an unresolved key must not sneak past a scoped guard."""
    assert _blocked(None, "NIFTY") is True


# ── the existing switches still win ──────────────────────────────────────
def test_non_expiry_weekday_blocks_nothing():
    assert _blocked("NIFTY", "NIFTY", today=WED) is False


def test_per_day_override_lifts_the_block_even_for_nifty():
    assert _blocked("NIFTY", "NIFTY", override="2026-06-30") is False


def test_weekday_guard_off_blocks_nothing():
    assert intraday_blocked_for_expiry_day(TUE, "", -1, "NIFTY", "NIFTY") is False


# ── WIRING on the live entry path (the #15 lesson: pure tests can pass while
# the live wiring stays broken) ──────────────────────────────────────────
def _runner(key, product, bar, block_keys):
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.enabled = {key}
    r.products[key] = product
    r.params = {**r.params, "intraday_enabled": True,
                "intraday_block_weekday": 1, "expiry_day_block_keys": block_keys}
    r.armed = True
    admission = persist_admitted_entry(r.broker.s)
    with r._session() as session:
        row = paper_authority.stage(
            session, project_id="test.admission.4c1029697ee358715d3a14a2",
            graph_identifier="test.strategy.expanding_z_impulse", graph_version=1,
            deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key=key, interval="30minute",
            owner_id=r.owner_id, broker_account_id=r.broker_account_id)
        session.commit()
    from unittest.mock import patch
    with r._session() as session:
        decision = {"project_id": "test.admission.4c1029697ee358715d3a14a2",
                    "graph_identifier": "test.strategy.expanding_z_impulse", "graph_version": 1,
                    "content_address": admission["graph_address"],
                    "admission_address": admission["admission_address"], "decision": "approved"}
        with patch.object(paper_authority, "verified_decision", return_value=decision):
            paper_authority.activate(session, row.id, revision=row.revision,
                                     owner_id=r.owner_id, broker_account_id=r.broker_account_id)
        session.commit()
    r.refresh_paper_authority()
    r.publish_signal(
        key, r._binding_for(key), {"signal": "LONG_ENTRY", "z": 2.5, "slope": 1.0, "close": 100.0,
                                   "time": ist_epoch(bar)})
    return r


def _events(after=0):
    return [e.get("event") for e in log.recent(80) if e.get("seq", 0) > after]


def test_wiring_equity_name_opens_on_expiry_day_when_scoped_to_nifty():
    before = log.recent(1)[-1]["seq"] if log.recent(1) else 0
    # NATURALGAS is affordable enough for the real-margin sizer to buy >=1 unit.
    r = _runner("NATURALGAS", "equity_intraday", dt.datetime(2026, 6, 30, 10, 30), "NIFTY")
    r.provider.now = lambda: dt.datetime(2026, 6, 30, 10, 46)    # Tuesday, mid-session
    r.process_entries()
    assert [p for p in r.broker.open_positions() if p.segment == "equity_intraday"] != []
    assert "EXPIRY_DAY_SKIP" not in _events(before)


def test_wiring_nifty_still_blocked_on_expiry_day():
    r = _runner("NIFTY", "options", dt.datetime(2026, 6, 30, 10, 30), "NIFTY")
    r.provider.now = lambda: dt.datetime(2026, 6, 30, 10, 46)
    r.process_entries()
    assert r.broker.open_positions() == []
    assert "EXPIRY_DAY_SKIP" in _events()


def test_wiring_star_still_blocks_the_equity_name():
    r = _runner("NATURALGAS", "equity_intraday", dt.datetime(2026, 6, 30, 10, 30), "*")
    r.provider.now = lambda: dt.datetime(2026, 6, 30, 10, 46)
    r.process_entries()
    assert [p for p in r.broker.open_positions() if p.segment == "equity_intraday"] == []
    assert "EXPIRY_DAY_SKIP" in _events()
