"""The picker must: trade the right side (CE long / PE short), reject illiquid or
wide-spread contracts, then among what's left choose the delta closest to ~0.50
within the 0.35-0.65 band — or pick nothing if nothing qualifies."""
from datetime import datetime, time, timedelta

import pytest

from app.core.config import get_settings
from app.options.picker import pick_option
from app.options.pricing import bs_price
from app.providers.base import OptionChain, OptionQuote

NOW = datetime(2025, 1, 1, 10, 0)
EXPIRY = (NOW + timedelta(days=7)).date()
R = 0.065
SIGMA = 0.15
SPOT = 24000.0


def _T() -> float:
    return (datetime.combine(EXPIRY, time(15, 30)) - NOW).total_seconds() / (365 * 86400)


def make_quote(strike, otype, oi=5000, spread_pct=0.01):
    flag = "c" if otype == "CE" else "p"
    px = max(bs_price(SPOT, strike, _T(), R, SIGMA, flag), 0.05)
    half = px * spread_pct / 2
    return OptionQuote(
        instrument_key="NIFTY", tradingsymbol=f"NIFTY{int(strike)}{otype}",
        exchange="NFO", strike=float(strike), expiry=EXPIRY, option_type=otype,
        lot_size=75, ltp=round(px, 2), bid=round(px - half, 2), ask=round(px + half, 2),
        volume=int(oi * 0.3), oi=oi)


def chain(quotes):
    return OptionChain(instrument_key="NIFTY", spot=SPOT, expiry=EXPIRY, quotes=quotes)


def test_long_signal_picks_a_call():
    quotes = [make_quote(s, "CE") for s in (23800, 24000, 24200)]
    quotes += [make_quote(s, "PE") for s in (23800, 24000, 24200)]
    res = pick_option(chain(quotes), "LONG", get_settings(), NOW)
    assert res.chosen is not None
    assert res.chosen.option_type == "CE"


def test_short_signal_picks_a_put():
    quotes = [make_quote(s, "CE") for s in (23800, 24000, 24200)]
    quotes += [make_quote(s, "PE") for s in (23800, 24000, 24200)]
    res = pick_option(chain(quotes), "SHORT", get_settings(), NOW)
    assert res.chosen is not None
    assert res.chosen.option_type == "PE"


def test_picks_delta_closest_to_target():
    # ATM (24000) has delta nearest 0.50; it should win over ITM/OTM
    quotes = [make_quote(s, "CE") for s in (23600, 23800, 24000, 24200, 24400)]
    res = pick_option(chain(quotes), "LONG", get_settings(), NOW)
    assert res.chosen.strike == 24000


def test_rejects_low_oi_contract():
    # ATM is illiquid (oi below the 500 floor) -> must not be chosen
    quotes = [
        make_quote(24000, "CE", oi=100),   # illiquid ATM
        make_quote(24200, "CE", oi=5000),  # liquid, delta still in band
    ]
    res = pick_option(chain(quotes), "LONG", get_settings(), NOW)
    assert res.chosen is not None
    assert res.chosen.strike == 24200
    atm_row = next(c for c in res.candidates if c["strike"] == 24000)
    assert atm_row["passed_liquidity"] is False


def test_rejects_wide_spread_contract():
    quotes = [
        make_quote(24000, "CE", spread_pct=0.05),  # 5% spread > 3% cap
        make_quote(24200, "CE", spread_pct=0.01),
    ]
    res = pick_option(chain(quotes), "LONG", get_settings(), NOW)
    assert res.chosen.strike == 24200


def test_none_when_nothing_liquid_in_band():
    # only a deep-OTM call (delta far below 0.35) that is also illiquid
    quotes = [make_quote(26000, "CE", oi=50)]
    res = pick_option(chain(quotes), "LONG", get_settings(), NOW)
    assert res.chosen is None
    assert res.reason


def test_candidates_table_has_greeks_for_every_row_of_side():
    quotes = [make_quote(s, "CE") for s in (23800, 24000, 24200)]
    quotes += [make_quote(s, "PE") for s in (23800, 24000, 24200)]
    res = pick_option(chain(quotes), "LONG", get_settings(), NOW)
    assert len(res.candidates) == 3  # only the CE side is evaluated for a long
    for c in res.candidates:
        assert "delta" in c and "iv" in c and "passed_liquidity" in c
