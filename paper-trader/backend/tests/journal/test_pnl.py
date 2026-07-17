"""Pure P&L math — no DB, no engine, no provider. GOLDM lot_size=10, multiplier=1.0
throughout (mirrors app/core/instruments.py's GOLDM seed)."""
from app.journal.pnl import gross_pnl, round_trip_charges, net_pnl, unrealized_pnl


def test_gross_pnl_long_and_short():
    assert gross_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0) == 5000.0
    assert gross_pnl("SHORT", 72000, 71500, lots=1, lot_size=10, multiplier=1.0) == 5000.0
    assert gross_pnl("LONG", 72000, 71500, lots=2, lot_size=10, multiplier=1.0) == -10000.0


def test_round_trip_charges_uses_mcx_fut_schedule_and_is_positive():
    c = round_trip_charges(72000, 72500, lots=1, lot_size=10)
    assert c > 0
    # a bigger round-trip notional charges more
    assert round_trip_charges(72000, 72500, lots=2, lot_size=10) > c


def test_net_pnl_computed_when_manual_is_none():
    gross = gross_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0)
    charges = round_trip_charges(72000, 72500, lots=1, lot_size=10)
    net = net_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0)
    assert abs(net - (gross - charges)) < 1e-6


def test_net_pnl_manual_overrides_and_never_double_subtracts_charges():
    # owner enters the broker's own net figure directly — must be returned verbatim,
    # NOT further reduced by computed charges.
    assert net_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0,
                    manual_net_pnl=4321.0) == 4321.0


def test_unrealized_pnl_is_gross_only_no_exit_charges_yet():
    # only the entry leg's charges are real so far; unrealized is pre-exit-charge gross
    # minus the entry leg only, not a full round trip.
    u = unrealized_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0)
    gross = gross_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0)
    assert u < gross  # entry-leg charges reduce it
    assert u > gross - round_trip_charges(72000, 72500, lots=1, lot_size=10)  # but not a full RT
