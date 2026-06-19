"""
The tradable universe — now DB-backed and dynamic.

The curated SEED below is the starting portfolio (LEAD/ZINC/DHANIYA were dropped
as the least liquid). At runtime the universe lives in the `universe_instruments`
table: the owner can add instruments from the homepage / backtest winners, and
those join the live portfolio. `has_options` decides whether the live engine
options-trades an instrument or merely tracks + backtests it (most cash equities
have no listed options).

`priority` encodes the capital-allocation order when several signals fire on the
same tick (lower number wins).

`segment` drives both the option-chain venue and the brokerage/tax schedule
(see engine/charges.py). `lot_size`/`strike_step` are sensible defaults used by
the MockProvider and as fallbacks; against the live Kite API they are re-resolved
from the instruments dump each day.

The registry always includes the SEED as a base (so tests and the mock work with
no DB), overlaid with rows from the database at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Instrument:
    key: str            # internal id, e.g. "NIFTY"
    name: str           # display name, e.g. "NIFTY 50"
    segment: str        # "NFO" | "BFO" | "MCX" | "NCDEX" | "NSE" | "BSE"
    spot_exchange: str  # exchange for the underlying candle feed
    spot_symbol: str    # tradingsymbol/name of the underlying (index spot or near future)
    option_name: str    # `name` used to find option contracts in the instruments dump
    lot_size: int
    strike_step: float
    priority: int       # allocation priority (1 = highest)
    # mock-market seeds
    mock_spot: float
    mock_vol: float     # annualised vol
    # dynamic-universe fields
    has_options: bool = True   # False -> tracking/backtest only (no live option trades)
    on_home: bool = False      # shown on the customizable homepage grid
    source: str = "seed"       # "seed" | "user"


# Curated seed — the owner's liquidity-priority ranking, minus LEAD/ZINC/DHANIYA.
SEED_INSTRUMENTS: dict[str, Instrument] = {
    "NIFTY": Instrument(
        "NIFTY", "NIFTY 50", "NFO", "NSE", "NIFTY 50", "NIFTY",
        lot_size=75, strike_step=50, priority=1, mock_spot=24000, mock_vol=0.12,
        on_home=True),
    "GOLDM": Instrument(
        "GOLDM", "GOLD MINI", "MCX", "MCX", "GOLDM", "GOLDM",
        lot_size=10, strike_step=50, priority=2, mock_spot=72000, mock_vol=0.14,
        on_home=True),
    "SILVERM": Instrument(
        "SILVERM", "SILVER MINI", "MCX", "MCX", "SILVERM", "SILVERM",
        lot_size=5, strike_step=100, priority=3, mock_spot=90000, mock_vol=0.22),
    "CRUDEOIL": Instrument(
        "CRUDEOIL", "CRUDE OIL", "MCX", "MCX", "CRUDEOIL", "CRUDEOIL",
        lot_size=100, strike_step=50, priority=4, mock_spot=6500, mock_vol=0.30,
        on_home=True),
    "BANKNIFTY": Instrument(
        "BANKNIFTY", "BANKNIFTY", "NFO", "NSE", "NIFTY BANK", "BANKNIFTY",
        lot_size=35, strike_step=100, priority=5, mock_spot=52000, mock_vol=0.14,
        on_home=True),
    "NATURALGAS": Instrument(
        "NATURALGAS", "NATURAL GAS", "MCX", "MCX", "NATURALGAS", "NATURALGAS",
        lot_size=1250, strike_step=5, priority=6, mock_spot=250, mock_vol=0.40),
    "SENSEX": Instrument(
        "SENSEX", "SENSEX", "BFO", "BSE", "SENSEX", "SENSEX",
        lot_size=20, strike_step=100, priority=7, mock_spot=79000, mock_vol=0.12),
    "COPPERM": Instrument(
        "COPPERM", "COPPER MINI", "MCX", "MCX", "COPPER", "COPPER",
        lot_size=250, strike_step=5, priority=8, mock_spot=850, mock_vol=0.20),
}

# ── registry (SEED base, overlaid with DB rows) ──────────────────────────────
_registry: dict[str, Instrument] = dict(SEED_INSTRUMENTS)


def seed_instruments() -> list[Instrument]:
    return list(SEED_INSTRUMENTS.values())


def _row_to_instrument(row) -> Instrument:
    return Instrument(
        key=row.key, name=row.name, segment=row.segment,
        spot_exchange=row.spot_exchange, spot_symbol=row.spot_symbol,
        option_name=row.option_name or row.key, lot_size=row.lot_size,
        strike_step=row.strike_step, priority=row.priority,
        mock_spot=row.mock_spot, mock_vol=row.mock_vol,
        has_options=row.has_options, on_home=row.on_home, source=row.source)


def load_universe() -> None:
    """Rebuild the in-memory registry from the DB (SEED is the always-present
    base). Safe to call when the DB isn't ready — falls back to SEED only."""
    global _registry
    reg = dict(SEED_INSTRUMENTS)
    try:
        from sqlalchemy import select

        from app.db.models import UniverseInstrument
        from app.db.session import SessionLocal
        with SessionLocal() as s:
            for row in s.scalars(select(UniverseInstrument)):
                if row.active:
                    reg[row.key] = _row_to_instrument(row)
                else:
                    reg.pop(row.key, None)
    except Exception:
        pass  # DB not initialised yet (e.g. unit tests) — SEED is enough
    _registry = reg


def all_instruments() -> list[Instrument]:
    """Active universe, in priority order."""
    return sorted(_registry.values(), key=lambda i: (i.priority, i.key))


def get_instrument(key: str) -> Instrument:
    inst = _registry.get(key)
    if inst is None:
        load_universe()             # maybe a freshly-added instrument
        inst = _registry.get(key)
    if inst is None:
        raise KeyError(f"unknown instrument: {key}")
    return inst


def by_priority(keys: list[str]) -> list[str]:
    """Sort a subset of instrument keys by allocation priority."""
    return sorted(keys, key=lambda k: _registry[k].priority if k in _registry else 999)


def home_instruments() -> list[Instrument]:
    """Instruments pinned to the customizable homepage."""
    return [i for i in all_instruments() if i.on_home]
