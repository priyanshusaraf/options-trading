"""Pure P&L math — no DB, no engine, no provider. GOLDM lot_size=10, multiplier=1.0
throughout (mirrors app/core/instruments.py's GOLDM seed)."""
from app.journal.pnl import gross_pnl, round_trip_charges, net_pnl, unrealized_pnl
from app.engine.charges import compute_charges
from app.journal.pnl import SEGMENT


def test_gross_pnl_long_and_short():
    assert gross_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0) == 5000.0
    assert gross_pnl("SHORT", 72000, 71500, lots=1, lot_size=10, multiplier=1.0) == 5000.0
    assert gross_pnl("LONG", 72000, 71500, lots=2, lot_size=10, multiplier=1.0) == -10000.0


def test_round_trip_charges_uses_mcx_fut_schedule_and_is_positive():
    c = round_trip_charges("LONG", 72000, 72500, lots=1, lot_size=10)
    assert c > 0
    # a bigger round-trip notional charges more
    assert round_trip_charges("LONG", 72000, 72500, lots=2, lot_size=10) > c


def test_net_pnl_computed_when_manual_is_none():
    gross = gross_pnl("LONG", 72000, 72500, lots=1, lot_size=10, multiplier=1.0)
    charges = round_trip_charges("LONG", 72000, 72500, lots=1, lot_size=10)
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
    assert u > gross - round_trip_charges("LONG", 72000, 72500, lots=1, lot_size=10)  # but not a full RT


def test_round_trip_charges_short_swaps_legs_vs_long():
    # LONG: entry=BUY@72000, exit=SELL@72500. SHORT (same prices, "entry" and
    # "exit" price args unchanged): entry=SELL@72000, exit=BUY@72500 — i.e. the
    # BUY/SELL sides are swapped relative to LONG, not the prices.
    qty = 1 * 10
    long_expected = (compute_charges(SEGMENT, "BUY", 72000, qty)["total"]
                      + compute_charges(SEGMENT, "SELL", 72500, qty)["total"])
    short_expected = (compute_charges(SEGMENT, "SELL", 72000, qty)["total"]
                       + compute_charges(SEGMENT, "BUY", 72500, qty)["total"])

    long_actual = round_trip_charges("LONG", 72000, 72500, lots=1, lot_size=10)
    short_actual = round_trip_charges("SHORT", 72000, 72500, lots=1, lot_size=10)

    assert abs(long_actual - long_expected) < 1e-6
    assert abs(short_actual - short_expected) < 1e-6
    # MCX_FUT: CTT (tax_sell_pct) hits the SELL leg and stamp duty (stamp_buy_pct)
    # hits the BUY leg, so swapping which price gets which side changes the total
    # (72000 vs 72500 turnover on each tax) — LONG and SHORT must differ here.
    assert abs(long_actual - short_actual) > 1e-6


def test_net_pnl_passes_direction_through_to_round_trip_charges():
    gross = gross_pnl("SHORT", 72000, 71500, lots=1, lot_size=10, multiplier=1.0)
    charges = round_trip_charges("SHORT", 72000, 71500, lots=1, lot_size=10)
    net = net_pnl("SHORT", 72000, 71500, lots=1, lot_size=10, multiplier=1.0)
    assert abs(net - (gross - charges)) < 1e-6


def test_unrealized_pnl_short_entry_leg_uses_sell_side_charges():
    qty = 1 * 10
    gross = gross_pnl("SHORT", 72000, 71500, lots=1, lot_size=10, multiplier=1.0)
    expected_entry_leg = compute_charges(SEGMENT, "SELL", 72000, qty)["total"]
    expected_u = gross - expected_entry_leg

    u = unrealized_pnl("SHORT", 72000, 71500, lots=1, lot_size=10, multiplier=1.0)
    assert abs(u - expected_u) < 1e-6

    # sanity: it must NOT match the (wrong) BUY-side entry-leg charge that the old
    # code always used, since BUY and SELL rates differ for MCX_FUT (CTT vs stamp).
    wrong_entry_leg = compute_charges(SEGMENT, "BUY", 72000, qty)["total"]
    wrong_u = gross - wrong_entry_leg
    assert abs(u - wrong_u) > 1e-6
