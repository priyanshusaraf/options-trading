"""
The tradable universe — the 9-11 instruments the owner can enable from the top
panel of the dashboard.

`priority` encodes the capital-allocation order when several signals fire on the
same tick (lower number wins). This is exactly the order the owner specified:

    NIFTY > GOLD MINI > SILVER MINI > CRUDE OIL > BANKNIFTY > NATURAL GAS >
    SENSEX > COPPER MINI > ZINC > LEAD > DHANIYA

`segment` drives both the option-chain venue and the brokerage/tax schedule
(see engine/charges.py). `lot_size`/`strike_step` are sensible defaults used by
the MockProvider and as fallbacks; against the live Kite API they are re-resolved
from the instruments dump each day (contract specs change periodically).

`mock_*` fields seed the synthetic market so single-lot premiums land in a
realistic, mostly-affordable range for a INR 50,000 book.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    key: str            # internal id, e.g. "NIFTY"
    name: str           # display name, e.g. "NIFTY 50"
    segment: str        # "NFO" | "BFO" | "MCX" | "NCDEX" — venue + charge schedule
    spot_exchange: str  # exchange for the underlying candle feed
    spot_symbol: str    # tradingsymbol/name of the underlying (index spot or near future)
    option_name: str    # `name` used to find option contracts in the instruments dump
    lot_size: int
    strike_step: float
    priority: int       # allocation priority (1 = highest)
    # mock-market seeds
    mock_spot: float
    mock_vol: float     # annualised vol


# Ordered by the owner's liquidity-priority ranking.
INSTRUMENTS: dict[str, Instrument] = {
    "NIFTY": Instrument(
        "NIFTY", "NIFTY 50", "NFO", "NSE", "NIFTY 50", "NIFTY",
        lot_size=75, strike_step=50, priority=1, mock_spot=24000, mock_vol=0.12),
    "GOLDM": Instrument(
        "GOLDM", "GOLD MINI", "MCX", "MCX", "GOLDM", "GOLDM",
        lot_size=10, strike_step=50, priority=2, mock_spot=72000, mock_vol=0.14),
    "SILVERM": Instrument(
        "SILVERM", "SILVER MINI", "MCX", "MCX", "SILVERM", "SILVERM",
        lot_size=5, strike_step=100, priority=3, mock_spot=90000, mock_vol=0.22),
    "CRUDEOIL": Instrument(
        "CRUDEOIL", "CRUDE OIL", "MCX", "MCX", "CRUDEOIL", "CRUDEOIL",
        lot_size=100, strike_step=50, priority=4, mock_spot=6500, mock_vol=0.30),
    "BANKNIFTY": Instrument(
        "BANKNIFTY", "BANKNIFTY", "NFO", "NSE", "NIFTY BANK", "BANKNIFTY",
        lot_size=35, strike_step=100, priority=5, mock_spot=52000, mock_vol=0.14),
    "NATURALGAS": Instrument(
        "NATURALGAS", "NATURAL GAS", "MCX", "MCX", "NATURALGAS", "NATURALGAS",
        lot_size=1250, strike_step=5, priority=6, mock_spot=250, mock_vol=0.40),
    "SENSEX": Instrument(
        "SENSEX", "SENSEX", "BFO", "BSE", "SENSEX", "SENSEX",
        lot_size=20, strike_step=100, priority=7, mock_spot=79000, mock_vol=0.12),
    "COPPERM": Instrument(
        "COPPERM", "COPPER MINI", "MCX", "MCX", "COPPERM", "COPPERM",
        lot_size=250, strike_step=5, priority=8, mock_spot=850, mock_vol=0.20),
    "ZINC": Instrument(
        "ZINC", "ZINC", "MCX", "MCX", "ZINC", "ZINC",
        lot_size=5000, strike_step=1, priority=9, mock_spot=270, mock_vol=0.20),
    "LEAD": Instrument(
        "LEAD", "LEAD", "MCX", "MCX", "LEAD", "LEAD",
        lot_size=5000, strike_step=1, priority=10, mock_spot=180, mock_vol=0.18),
    "DHANIYA": Instrument(
        "DHANIYA", "DHANIYA", "NCDEX", "NCDEX", "DHANIYA", "DHANIYA",
        lot_size=100, strike_step=50, priority=11, mock_spot=7500, mock_vol=0.25),
}


def all_instruments() -> list[Instrument]:
    """All instruments, already in priority order."""
    return sorted(INSTRUMENTS.values(), key=lambda i: i.priority)


def get_instrument(key: str) -> Instrument:
    return INSTRUMENTS[key]


def by_priority(keys: list[str]) -> list[str]:
    """Sort a subset of instrument keys by allocation priority."""
    return sorted(keys, key=lambda k: INSTRUMENTS[k].priority)
