"""Opening index-futures entries — and every reason not to.

The default state is OFF, and the first test asserts that the flag alone is
enough: with `index_futures_enabled=False` no amount of signal produces a
position. That is what makes "built but not live" a real guarantee rather than a
hopeful one.

Everything else here is a refusal. A new leveraged segment is mostly a
collection of reasons not to trade, and each one below has a specific failure it
prevents.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner
from app.core import paper_authority
from app.db.models import LEGACY_DEPLOYMENT_ID
from tests.admitted_entry import persist_admitted_entry

NOW = dt.datetime(2026, 8, 3, 11, 0)


@pytest.fixture
def runner(monkeypatch, give_futures_price_feed):
    init_db(reset=True)
    r = EngineRunner(owner_id="owner", broker_account_id="account.default")
    r.armed = True
    # Fund the ledger. ONE NIFTY lot is ~₹18 lakh of notional and blocks ~₹2.1
    # lakh of margin at the 12% estimate, so the default ₹50,000 paper ledger
    # cannot open a single contract. That is correct behaviour, not a test
    # problem — see test_a_small_account_cannot_trade_index_futures — but it
    # makes every OTHER assertion here vacuous unless the account is funded.
    cap = r.broker.capital()
    cap.initial_capital = 1_000_000.0
    cap.cash = 1_000_000.0
    r.broker.s.commit()
    admission = persist_admitted_entry(r.broker.s)
    with r._session() as s:
        row = paper_authority.stage(s, project_id="test.admission.4c1029697ee358715d3a14a2",
            graph_identifier="test.strategy.expanding_z_impulse", graph_version=1,
            deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY", interval="30minute",
            owner_id=r.owner_id, broker_account_id=r.broker_account_id); s.commit()
    with r._session() as s:
        from unittest.mock import patch
        d={"project_id":"test.admission.4c1029697ee358715d3a14a2","graph_identifier":"test.strategy.expanding_z_impulse","graph_version":1,"content_address":admission["graph_address"],"admission_address":admission["admission_address"],"decision":"approved"}
        with patch.object(paper_authority, "verified_decision", return_value=d):
            paper_authority.activate(s, row.id, revision=row.revision, owner_id=r.owner_id, broker_account_id=r.broker_account_id)
        s.commit()
    r.refresh_paper_authority()
    r.publish_signal(
        "NIFTY", r._binding_for("NIFTY"), {"long_entry": True, "short_entry": False, "close": 24_000.0})
    give_futures_price_feed(r.provider,
                           lambda inst, expiry: 24_000.0)
    yield r
    try:
        r.broker.s.close()
    except Exception:
        pass


def _enable(r, **over):
    r.params = {**r.params, "index_futures_enabled": True,
                "index_futures_max_positions": 1,
                "index_futures_max_margin": 250_000.0,
                "index_futures_min_margin": 50_000.0, **over}


def _futs(r):
    return [p for p in r.broker.open_positions() if p.segment == "index_futures"]


# ── the flag is the guarantee ───────────────────────────────────────────────

def test_disabled_means_no_position_no_matter_the_signal(runner):
    runner._process_futures_entries(NOW)
    assert _futs(runner) == [], "the segment traded while disabled"


def test_enabled_with_a_signal_opens_one(runner):
    _enable(runner)
    runner._process_futures_entries(NOW)
    assert len(_futs(runner)) == 1


# ── the refusals ────────────────────────────────────────────────────────────

def test_disarmed_never_opens(runner):
    _enable(runner)
    runner.armed = False
    runner._process_futures_entries(NOW)
    assert _futs(runner) == []


def test_the_concurrency_cap_is_respected(runner):
    _enable(runner)
    runner._process_futures_entries(NOW)
    runner._process_futures_entries(NOW)
    assert len(_futs(runner)) == 1, "cap of 1 was exceeded"


def test_no_futures_price_means_no_trade(runner, monkeypatch, give_futures_price_feed):
    """Opening at spot when the contract cannot be priced would enter at a price
    the future never traded at."""
    _enable(runner)
    give_futures_price_feed(runner.provider,
                           lambda inst, expiry: None)
    runner._process_futures_entries(NOW)
    assert _futs(runner) == []


def test_no_real_margin_quote_means_no_trade(runner, monkeypatch):
    """The sizer returning None must be a refusal, not a fallback — a guessed
    SPAN figure would go straight into the ledger."""
    _enable(runner)
    monkeypatch.setattr(runner, "_futures_margin_sizer",
                        lambda: (lambda *a, **k: None))
    runner._process_futures_entries(NOW)
    assert _futs(runner) == []


def test_it_never_opens_inside_the_force_flat_window(runner, monkeypatch):
    """A position opened minutes before the square-off is closed immediately,
    paying both legs' charges for nothing."""
    from app.core import market_hours
    _enable(runner)
    monkeypatch.setattr(market_hours, "minutes_to_close", lambda seg, now: 3)
    runner._process_futures_entries(NOW)
    assert _futs(runner) == []


def test_it_never_opens_into_a_delivery_window(runner, monkeypatch):
    """Refuse to OPEN into a window we would immediately have to force-close out
    of — the guard runs on entry, not only on exit."""
    import app.engine.delivery_calendar as dc
    _enable(runner)
    # A window that actually contains `NOW`. It used to be written as `ends=e`, which only
    # described a real window because the entry expiry was silently *today* — the runner had no
    # way to name a contract and invented one. Now that the expiry is the connection's front
    # month, `ends=e` would describe a window ending before it starts, and the guard would
    # correctly let the entry through, testing nothing.
    monkeypatch.setattr(dc.CashSettledCalendar, "window_for",
                        lambda self, k, e: dc.DeliveryWindow(
                            starts=NOW.date(), ends=NOW.date() + dt.timedelta(days=7)))
    runner._process_futures_entries(NOW)
    assert _futs(runner) == []


def test_a_margin_below_the_dust_floor_is_skipped(runner):
    _enable(runner, index_futures_min_margin=10_000_000.0)
    runner._process_futures_entries(NOW)
    assert _futs(runner) == []


def test_no_signal_no_position(runner):
    _enable(runner)
    runner.publish_signal(
        "NIFTY", runner._binding_for("NIFTY"), {"long_entry": False, "short_entry": False})
    runner._process_futures_entries(NOW)
    assert _futs(runner) == []


def test_a_short_signal_opens_short(runner):
    _enable(runner)
    runner.publish_signal(
        "NIFTY", runner._binding_for("NIFTY"), {"long_entry": False, "short_entry": True, "close": 24_000.0})
    runner._process_futures_entries(NOW)
    assert _futs(runner)[0].direction == "SHORT"


def test_the_ledger_still_reconciles_after_a_futures_entry(runner):
    _enable(runner)
    runner._process_futures_entries(NOW)
    cap = runner.broker.capital()
    open_cost = sum(p.entry_cost for p in runner.broker.open_positions())
    drift = cap.cash - (cap.initial_capital + cap.realized_pnl - open_cost)
    assert drift == pytest.approx(0.0, abs=1e-6)


def test_a_small_account_cannot_trade_index_futures(runner):
    """Not a bug — the reason futures were scoped as a bigger-capital feature.

    One NIFTY lot blocks roughly ₹2.1 lakh of margin. A ₹50,000 account is
    refused on affordability, silently and correctly, rather than opening some
    fractional position that does not exist."""
    _enable(runner)
    cap = runner.broker.capital()
    cap.initial_capital = 50_000.0
    cap.cash = 50_000.0
    runner.broker.s.commit()
    runner._process_futures_entries(NOW)
    assert _futs(runner) == []
