"""
Brokerage + statutory charges, modelled on Zerodha's published schedule.

The owner explicitly wanted commissions accounted for, so every paper fill pays
realistic costs. Rates are isolated in CHARGE_SCHEDULE per segment and are easy
to update when the exchanges revise them — the engine never hardcodes a rate.

Rules that are structural (and tested), independent of the exact bps:
  - brokerage: flat per executed order (buy and sell each pay it)
  - transaction tax (STT for equity F&O / CTT for commodities): SELL leg only;
    agri commodities (NCDEX) are exempt
  - exchange transaction charge + SEBI turnover fee: both legs
  - GST (18%): charged on (brokerage + exchange txn + SEBI), both legs
  - stamp duty: BUY leg only

NOTE: rates below are indicative as of the time of writing and are the single
place to adjust. Verify against your contract notes and tweak as needed.
"""
from __future__ import annotations

CHARGE_SCHEDULE: dict[str, dict] = {
    # NSE equity/index F&O options
    "NFO": {"brokerage_flat": 20.0, "txn_pct": 0.0003503, "tax_sell_pct": 0.001,
            "stamp_buy_pct": 0.00003, "sebi_pct": 1e-6, "gst_pct": 0.18},
    # BSE F&O options (SENSEX / BANKEX)
    "BFO": {"brokerage_flat": 20.0, "txn_pct": 0.000325, "tax_sell_pct": 0.001,
            "stamp_buy_pct": 0.00003, "sebi_pct": 1e-6, "gst_pct": 0.18},
    # MCX commodity options (CTT 0.05% on sell)
    "MCX": {"brokerage_flat": 20.0, "txn_pct": 0.0005, "tax_sell_pct": 0.0005,
            "stamp_buy_pct": 0.00003, "sebi_pct": 1e-6, "gst_pct": 0.18},
    # NCDEX agri options (CTT-exempt)
    "NCDEX": {"brokerage_flat": 20.0, "txn_pct": 0.00006, "tax_sell_pct": 0.0,
              "stamp_buy_pct": 0.00002, "sebi_pct": 1e-6, "gst_pct": 0.18},
}


def compute_charges(segment: str, side: str, premium: float, qty: int) -> dict:
    """Charges for a single leg. `side` is 'BUY' or 'SELL'; `qty` is total units
    (lot_size, since we trade 1 lot). Returns a per-component breakdown."""
    sch = CHARGE_SCHEDULE.get(segment, CHARGE_SCHEDULE["NFO"])
    turnover = max(0.0, premium * qty)
    side = side.upper()

    brokerage = sch["brokerage_flat"] if turnover > 0 else 0.0
    tax = turnover * sch["tax_sell_pct"] if side == "SELL" else 0.0   # STT / CTT
    exchange_txn = turnover * sch["txn_pct"]
    sebi = turnover * sch["sebi_pct"]
    stamp = turnover * sch["stamp_buy_pct"] if side == "BUY" else 0.0
    gst = sch["gst_pct"] * (brokerage + exchange_txn + sebi)
    total = brokerage + tax + exchange_txn + sebi + stamp + gst

    return {
        "segment": segment,
        "side": side,
        "turnover": round(turnover, 2),
        "brokerage": round(brokerage, 2),
        "stt_ctt": round(tax, 2),
        "exchange_txn": round(exchange_txn, 2),
        "sebi": round(sebi, 2),
        "stamp": round(stamp, 2),
        "gst": round(gst, 2),
        "total": round(total, 2),
    }


def round_trip_charges(segment: str, entry_premium: float, exit_premium: float, qty: int) -> float:
    """Total buy+sell charges for a full round trip — used by analytics/expectancy."""
    buy = compute_charges(segment, "BUY", entry_premium, qty)["total"]
    sell = compute_charges(segment, "SELL", exit_premium, qty)["total"]
    return round(buy + sell, 2)
