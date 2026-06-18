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
