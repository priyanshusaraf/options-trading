"""Startup repair for positions opened before contract-unit normalization."""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, CapitalState, Position, UniverseInstrument
from app.db.session import _repair_open_position_lot_sizes
from app.engine.charges import compute_charges


def _session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)()


def test_repair_open_position_reprices_entry_cost_to_universe_lot_size():
    s = _session()
    now = dt.datetime(2026, 6, 19, 9, 30)
    s.add(CapitalState(id=1, initial_capital=50_000, cash=49_611.07, realized_pnl=0))
    s.add(UniverseInstrument(
        key="CRUDEOIL", name="CRUDE OIL", segment="MCX", spot_exchange="MCX",
        spot_symbol="CRUDEOIL", option_name="CRUDEOIL", lot_size=100,
        strike_step=50, priority=4, has_options=True, source="seed",
        on_home=True, active=True, mock_spot=6500, mock_vol=0.30,
    ))
    s.add(Position(
        instrument_key="CRUDEOIL", direction="LONG", option_type="CE",
        tradingsymbol="CRUDEOIL26JUL7200CE", exchange="MCX", strike=7200,
        expiry=dt.date(2026, 7, 16), lot_size=1, qty=1, entry_premium=365.10,
        entry_charges=23.83, entry_cost=388.93, entry_spot=7119,
        entry_time=now, entry_reason="old bad fill", stop_price=237.315,
        target_price=584.16, last_premium=370.0, last_spot=7119,
    ))
    s.commit()

    fixed = _repair_open_position_lot_sizes(s)

    pos = s.query(Position).one()
    expected_charges = compute_charges("MCX", "BUY", 365.10, 100)["total"]
    expected_cost = 365.10 * 100 + expected_charges
    assert fixed == 1
    assert pos.qty == 100
    assert pos.lot_size == 100
    assert pos.entry_charges == pytest.approx(expected_charges, abs=0.01)
    assert pos.entry_cost == pytest.approx(expected_cost, abs=0.01)
    assert s.get(CapitalState, 1).cash == pytest.approx(49_611.07 - (expected_cost - 388.93), abs=0.01)
