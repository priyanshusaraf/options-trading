"""audit C8: a quote with no genuine two-sided market (a missing bid or ask depth
side) must read as maximally illiquid, not collapse spread_pct to ~0 and sail
through the liquidity filter into a real, unfillable order."""
from app.providers.base import OptionQuote


def _q(bid, ask, ltp=50.0):
    return OptionQuote(
        instrument_key="X", tradingsymbol="X24CE", exchange="NFO",
        strike=100.0, expiry="2026-07-31", option_type="CE", lot_size=75,
        ltp=ltp, bid=bid, ask=ask, volume=0, oi=1000)


def test_spread_pct_normal_two_sided():
    assert _q(49.5, 50.5, ltp=50.0).spread_pct == 0.02


def test_spread_pct_illiquid_when_no_bid():
    # no resting buyer — cannot actually sell here; must fail the liquidity filter
    assert _q(0.0, 50.5).spread_pct == 1.0


def test_spread_pct_illiquid_when_no_ask():
    assert _q(49.5, 0.0).spread_pct == 1.0


def test_spread_pct_illiquid_when_no_two_sided_market():
    assert _q(0.0, 0.0).spread_pct == 1.0
