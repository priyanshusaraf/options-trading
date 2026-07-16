"""GTT safety-net stop payload. A SINGLE Good-Till-Triggered order that SELLs the
bot's long option when the premium falls to the stop — it lives on Zerodha's
servers, so it protects the position even if the bot/laptop/internet dies."""
from app.engine.gtt import round_to_tick, stop_gtt_params


def test_single_sell_stop_payload():
    p = stop_gtt_params("NIFTY25CE", "NFO", 75, trigger_price=110.004,
                        last_price=150.0, product="NRML")
    assert p["trigger_type"] == "single"
    assert p["tradingsymbol"] == "NIFTY25CE" and p["exchange"] == "NFO"
    assert p["trigger_values"] == [110.0]            # rounded to tick precision
    assert p["last_price"] == 150.0
    o = p["orders"][0]
    assert o["transaction_type"] == "SELL"
    assert o["quantity"] == 75
    assert o["order_type"] == "LIMIT" and o["price"] == 110.0
    assert o["product"] == "NRML"


# ── tick-size snapping (2026-07-08: LODHA's SL-M was rejected outright by Zerodha —
# "Tick size for this script is 0.05..." — because round(x, 2) makes a price clean to
# the paisa but does NOT guarantee it lands on the exchange's actual tick grid) ──────
def test_round_to_tick_snaps_to_the_nearest_multiple():
    assert round_to_tick(1125.13) == 1125.15    # nearest 0.05 multiple, rounding up
    assert round_to_tick(1125.11) == 1125.10    # nearest 0.05 multiple, rounding down
    assert round_to_tick(110.0) == 110.0        # already aligned -> unchanged
    assert round_to_tick(1400.75) == 1400.75    # already aligned -> unchanged (BDL's stop)


def test_stop_gtt_params_snaps_trigger_and_limit_to_the_tick_grid():
    p = stop_gtt_params("NIFTY25CE", "NFO", 75, trigger_price=110.12, last_price=140.0)
    assert p["trigger_values"] == [110.10]      # NOT 110.12 — 110.12 isn't a 0.05 multiple
    assert p["orders"][0]["price"] == 110.10


# ── 2026-07-15: per-instrument tick size, not a hardcoded 0.05 grid ────────────────
# `stop_gtt_params` must accept the instrument's REAL tick size so a GTT stop on a
# wider-tick contract snaps to ITS grid, not the NFO-options default.
def test_stop_gtt_params_honours_an_explicit_tick_size():
    p = stop_gtt_params("SOMEFUT", "MCX", 10, trigger_price=12786.3, last_price=13000.0,
                        tick_size=1.0)
    assert p["trigger_values"] == [12786.0]     # snapped to the 1.00 grid, not 0.05
    assert p["orders"][0]["price"] == 12786.0


def test_round_to_tick_handles_a_tenth_rupee_grid():
    """LT trades in 0.10 steps. A 0.05-only rounding would produce 3837.45, which
    Zerodha rejects outright for a 0.10-tick script."""
    assert round_to_tick(3837.4499, tick_size=0.10) == 3837.4


def test_round_to_tick_handles_a_whole_rupee_grid():
    """MARUTI trades in whole-rupee steps; the trigger must be an exact rupee amount
    with no fractional paisa left over."""
    trig = round_to_tick(12786.3, tick_size=1.0)
    assert trig == 12786.0
    assert trig * 100 == int(trig * 100)          # paise-exact, no float residue
