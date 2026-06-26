"""Charges are real money on a small book, so the structure is pinned down here:
flat brokerage, sell-side-only transaction tax, buy-side-only stamp, and GST
levied on the right base. Exact bps live in the schedule and may be tuned; the
arithmetic and the which-leg-pays rules must not drift."""
import pytest

from app.engine.charges import compute_charges, round_trip_charges


def test_brokerage_is_flat_20_per_order():
    c = compute_charges("NFO", "BUY", premium=172.8, qty=75)
    assert c["brokerage"] == 20.0


def test_buy_leg_has_no_transaction_tax():
    c = compute_charges("NFO", "BUY", premium=172.8, qty=75)
    assert c["stt_ctt"] == 0.0


def test_sell_leg_has_transaction_tax():
    c = compute_charges("NFO", "SELL", premium=172.8, qty=75)
    assert c["stt_ctt"] > 0.0


def test_nfo_sell_stt_is_0p1pct_of_premium_turnover():
    # NSE F&O options STT = 0.1% of premium on the sell side
    c = compute_charges("NFO", "SELL", premium=200.0, qty=75)
    assert c["stt_ctt"] == pytest.approx(0.001 * 200.0 * 75, rel=1e-6)


def test_stamp_duty_only_on_buy_leg():
    buy = compute_charges("NFO", "BUY", premium=172.8, qty=75)
    sell = compute_charges("NFO", "SELL", premium=172.8, qty=75)
    assert buy["stamp"] > 0.0
    assert sell["stamp"] == 0.0


def test_gst_is_18pct_of_brokerage_plus_txn_plus_sebi():
    c = compute_charges("NFO", "SELL", premium=172.8, qty=75)
    expected = 0.18 * (c["brokerage"] + c["exchange_txn"] + c["sebi"])
    assert c["gst"] == pytest.approx(expected, abs=0.01)


def test_total_is_sum_of_all_components():
    c = compute_charges("NFO", "SELL", premium=172.8, qty=75)
    parts = c["brokerage"] + c["stt_ctt"] + c["exchange_txn"] + c["sebi"] + c["stamp"] + c["gst"]
    assert c["total"] == pytest.approx(parts, abs=0.02)


def test_ncdex_agri_has_no_transaction_tax():
    # agri commodities (e.g. DHANIYA on NCDEX) are CTT-exempt
    c = compute_charges("NCDEX", "SELL", premium=100.0, qty=100)
    assert c["stt_ctt"] == 0.0


def test_mcx_sell_has_ctt():
    c = compute_charges("MCX", "SELL", premium=108.0, qty=100)
    assert c["stt_ctt"] > 0.0


def test_round_trip_adds_both_legs():
    rt = round_trip_charges("NFO", entry_premium=172.8, exit_premium=200.0, qty=75)
    buy = compute_charges("NFO", "BUY", 172.8, 75)["total"]
    sell = compute_charges("NFO", "SELL", 200.0, 75)["total"]
    assert rt == pytest.approx(buy + sell, abs=0.02)


def test_known_nfo_buy_total():
    # hand-computed: turnover 12960; brokerage 20; txn 12960*0.0003503=4.5399;
    # sebi 12960e-6=0.013; stamp 12960*3e-5=0.3888; gst 0.18*(20+4.5399+0.013)=4.4195
    # total = 29.36
    c = compute_charges("NFO", "BUY", premium=172.8, qty=75)
    assert c["total"] == pytest.approx(29.36, abs=0.10)


# ── UNDERLYING schedules (used by the backtest) ──────────────────────────────

def test_equity_delivery_taxes_both_legs():
    # equity DELIVERY STT is 0.1% on BOTH buy and sell (unlike F&O, sell-only)
    buy = compute_charges("NSE_EQ", "BUY", premium=2500.0, qty=20)
    sell = compute_charges("NSE_EQ", "SELL", premium=2500.0, qty=20)
    assert buy["stt_ctt"] == pytest.approx(0.001 * 2500 * 20, rel=1e-6)
    assert sell["stt_ctt"] == pytest.approx(0.001 * 2500 * 20, rel=1e-6)


def test_equity_delivery_zero_brokerage():
    c = compute_charges("NSE_EQ", "BUY", premium=2500.0, qty=20)
    assert c["brokerage"] == 0.0


def test_equity_delivery_dp_on_sell_only():
    buy = compute_charges("NSE_EQ", "BUY", premium=2500.0, qty=20)
    sell = compute_charges("NSE_EQ", "SELL", premium=2500.0, qty=20)
    assert buy["dp"] == 0.0
    assert sell["dp"] == 13.5
    # DP must be inside the total
    assert sell["total"] >= sell["dp"]


def test_futures_brokerage_capped_at_20():
    # large turnover -> brokerage caps at ₹20 (min(20, 0.03%·turnover))
    c = compute_charges("NFO_FUT", "BUY", premium=24000.0, qty=75)  # ₹18L turnover
    assert c["brokerage"] == 20.0


def test_futures_brokerage_pct_when_small():
    # tiny turnover -> brokerage is 0.03% of turnover, below the ₹20 cap
    c = compute_charges("NFO_FUT", "BUY", premium=100.0, qty=10)  # ₹1000 turnover
    assert c["brokerage"] == pytest.approx(0.0003 * 1000, rel=1e-6)


def test_futures_stt_sell_only():
    buy = compute_charges("NFO_FUT", "BUY", premium=24000.0, qty=75)
    sell = compute_charges("NFO_FUT", "SELL", premium=24000.0, qty=75)
    assert buy["stt_ctt"] == 0.0
    assert sell["stt_ctt"] == pytest.approx(0.0002 * 24000 * 75, rel=1e-6)


def test_ncdex_futures_ctt_exempt():
    c = compute_charges("NCDEX_FUT", "SELL", premium=7500.0, qty=100)
    assert c["stt_ctt"] == 0.0


def test_underlying_total_includes_all_components():
    c = compute_charges("NSE_EQ", "SELL", premium=2500.0, qty=20)
    parts = (c["brokerage"] + c["stt_ctt"] + c["exchange_txn"] + c["sebi"]
             + c["stamp"] + c["dp"] + c["gst"])
    assert c["total"] == pytest.approx(parts, abs=0.02)


# ── EQUITY INTRADAY / MIS schedules (used by the intraday-equity segment) ─────
# Zerodha MIS equity: brokerage min(₹20, 0.03%) per leg; STT 0.025% SELL only
# (half the delivery rate); stamp 0.003% BUY only (NOT the 0.015% delivery rate);
# NO DP charge (nothing is debited from demat intraday).

def test_intraday_stt_is_0p025pct_sell_only():
    buy = compute_charges("NSE_INTRADAY", "BUY", premium=1000.0, qty=10)
    sell = compute_charges("NSE_INTRADAY", "SELL", premium=1000.0, qty=10)
    assert buy["stt_ctt"] == 0.0
    assert sell["stt_ctt"] == pytest.approx(0.00025 * 1000.0 * 10, rel=1e-6)


def test_intraday_brokerage_capped_at_20():
    # ₹6L turnover -> 0.03% = ₹180, capped to ₹20
    c = compute_charges("NSE_INTRADAY", "BUY", premium=6000.0, qty=100)
    assert c["brokerage"] == 20.0


def test_intraday_brokerage_pct_when_small():
    # ₹10k turnover -> 0.03% = ₹3, below the ₹20 cap
    c = compute_charges("NSE_INTRADAY", "BUY", premium=1000.0, qty=10)
    assert c["brokerage"] == pytest.approx(0.0003 * 10_000, rel=1e-6)


def test_intraday_has_no_dp_charge():
    buy = compute_charges("NSE_INTRADAY", "BUY", premium=1000.0, qty=10)
    sell = compute_charges("NSE_INTRADAY", "SELL", premium=1000.0, qty=10)
    assert buy["dp"] == 0.0
    assert sell["dp"] == 0.0


def test_intraday_stamp_buy_only_at_0p003pct():
    buy = compute_charges("NSE_INTRADAY", "BUY", premium=1000.0, qty=10)
    sell = compute_charges("NSE_INTRADAY", "SELL", premium=1000.0, qty=10)
    assert buy["stamp"] == pytest.approx(0.00003 * 10_000, rel=1e-6)
    assert sell["stamp"] == 0.0


def test_intraday_gst_base_excludes_dp():
    c = compute_charges("NSE_INTRADAY", "SELL", premium=1000.0, qty=10)
    expected = 0.18 * (c["brokerage"] + c["exchange_txn"] + c["sebi"])
    assert c["gst"] == pytest.approx(expected, abs=0.01)


def test_intraday_known_totals():
    # BUY: turnover 10000; brokerage 3.0; txn 0.297; sebi 0.01; stamp 0.3;
    #   gst 0.18*(3.0+0.297+0.01)=0.59526; total = 4.2023
    buy = compute_charges("NSE_INTRADAY", "BUY", premium=1000.0, qty=10)
    assert buy["total"] == pytest.approx(4.20, abs=0.02)
    # SELL: + STT 2.5, no stamp; total = 3.0+2.5+0.297+0.01+0.59526 = 6.4023
    sell = compute_charges("NSE_INTRADAY", "SELL", premium=1000.0, qty=10)
    assert sell["total"] == pytest.approx(6.40, abs=0.02)


def test_bse_intraday_also_defined():
    c = compute_charges("BSE_INTRADAY", "SELL", premium=1000.0, qty=10)
    assert c["stt_ctt"] == pytest.approx(0.00025 * 1000.0 * 10, rel=1e-6)
    assert c["dp"] == 0.0
