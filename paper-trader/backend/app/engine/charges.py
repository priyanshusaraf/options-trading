"""
Brokerage + statutory charges, modelled on Zerodha's published schedule.

The owner explicitly wanted commissions accounted for, so every paper fill pays
realistic costs. Rates are isolated in CHARGE_SCHEDULE per segment and are easy
to update when the exchanges revise them — the engine never hardcodes a rate.

Two families of segments:
  - OPTIONS (NFO/BFO/MCX/NCDEX) — what the LIVE engine trades. Premium turnover.
  - UNDERLYING (NSE_EQ/BSE_EQ cash + NFO_FUT/MCX_FUT/NCDEX_FUT futures) — what the
    BACKTEST trades, since options history is mostly unavailable. Price turnover.

Rules that are structural (and tested), independent of the exact bps:
  - brokerage: flat per order, OR min(cap, pct·turnover) for futures, OR ₹0
    (equity delivery). Buy and sell each pay it.
  - transaction tax (STT for equity/F&O, CTT for commodities): SELL leg for
    F&O/futures; BOTH legs for equity DELIVERY; agri (NCDEX) exempt.
  - exchange transaction charge + SEBI turnover fee: both legs.
  - GST (18%): on (brokerage + exchange txn + SEBI + DP), both legs.
  - stamp duty: BUY leg only.
  - DP charge: flat per-scrip on the SELL of equity delivery only.

NOTE: rates below are indicative and are the single place to adjust. Verify
against your contract notes and tweak as needed. (STT/CTT reflect the post-Oct-2024
schedule: options sell 0.10%, futures sell 0.02%, MCX CTT 0.01%.)
"""
from __future__ import annotations

import math

CHARGE_SCHEDULE: dict[str, dict] = {
    # ── OPTIONS (live engine) ── premium turnover ───────────────────────────
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

    # ── UNDERLYING (backtest) ── price turnover ─────────────────────────────
    # NSE cash equity, DELIVERY (positional). Zerodha brokerage ₹0; STT 0.1%
    # BOTH legs; DP charge ₹13.5 + GST per scrip on sell.
    "NSE_EQ": {"brokerage_flat": 0.0, "txn_pct": 0.0000297,
               "tax_buy_pct": 0.001, "tax_sell_pct": 0.001,
               "stamp_buy_pct": 0.00015, "sebi_pct": 1e-6, "dp_sell_flat": 13.5,
               "gst_pct": 0.18},
    "BSE_EQ": {"brokerage_flat": 0.0, "txn_pct": 0.0000375,
               "tax_buy_pct": 0.001, "tax_sell_pct": 0.001,
               "stamp_buy_pct": 0.00015, "sebi_pct": 1e-6, "dp_sell_flat": 13.5,
               "gst_pct": 0.18},
    # NSE index/stock FUTURES: brokerage min(₹20, 0.03%); STT 0.02% sell.
    "NFO_FUT": {"brokerage_pct": 0.0003, "brokerage_cap": 20.0, "txn_pct": 0.0000173,
                "tax_sell_pct": 0.0002, "stamp_buy_pct": 0.00002, "sebi_pct": 1e-6,
                "gst_pct": 0.18},
    # MCX commodity FUTURES: brokerage min(₹20, 0.03%); CTT 0.01% sell.
    "MCX_FUT": {"brokerage_pct": 0.0003, "brokerage_cap": 20.0, "txn_pct": 0.000021,
                "tax_sell_pct": 0.0001, "stamp_buy_pct": 0.00002, "sebi_pct": 1e-6,
                "gst_pct": 0.18},
    # NCDEX agri FUTURES: brokerage min(₹20, 0.03%); CTT-exempt.
    "NCDEX_FUT": {"brokerage_pct": 0.0003, "brokerage_cap": 20.0, "txn_pct": 0.00006,
                  "tax_sell_pct": 0.0, "stamp_buy_pct": 0.00002, "sebi_pct": 1e-6,
                  "gst_pct": 0.18},
}


def compute_charges(segment: str, side: str, premium: float, qty: int) -> dict:
    """Charges for a single leg. `side` is 'BUY' or 'SELL'; `qty` is total units
    (lot_size, since we trade 1 lot); `premium` is the per-unit price (option
    premium for the live engine, underlying price for the backtest). Returns a
    per-component breakdown."""
    sch = CHARGE_SCHEDULE.get(segment, CHARGE_SCHEDULE["NFO"])
    turnover = max(0.0, premium * qty)
    side = side.upper()
    is_buy, is_sell = side == "BUY", side == "SELL"

    # brokerage: percentage-with-cap (futures) takes precedence over flat
    if sch.get("brokerage_pct", 0.0) > 0 and turnover > 0:
        brokerage = min(sch.get("brokerage_cap", math.inf), turnover * sch["brokerage_pct"])
    else:
        brokerage = sch.get("brokerage_flat", 0.0) if turnover > 0 else 0.0

    # transaction tax (STT/CTT): per-leg rates; equity delivery taxes both legs
    tax_pct = sch.get("tax_buy_pct", 0.0) if is_buy else sch.get("tax_sell_pct", 0.0)
    tax = turnover * tax_pct

    exchange_txn = turnover * sch.get("txn_pct", 0.0)
    sebi = turnover * sch.get("sebi_pct", 0.0)
    stamp = turnover * sch.get("stamp_buy_pct", 0.0) if is_buy else 0.0
    dp = sch.get("dp_sell_flat", 0.0) if is_sell else 0.0
    gst = sch.get("gst_pct", 0.18) * (brokerage + exchange_txn + sebi + dp)
    total = brokerage + tax + exchange_txn + sebi + stamp + dp + gst

    return {
        "segment": segment,
        "side": side,
        "turnover": round(turnover, 2),
        "brokerage": round(brokerage, 2),
        "stt_ctt": round(tax, 2),
        "exchange_txn": round(exchange_txn, 2),
        "sebi": round(sebi, 2),
        "stamp": round(stamp, 2),
        "dp": round(dp, 2),
        "gst": round(gst, 2),
        "total": round(total, 2),
    }


def round_trip_charges(segment: str, entry_premium: float, exit_premium: float, qty: int) -> float:
    """Total buy+sell charges for a full round trip — used by analytics/expectancy
    and by the backtest to net every trade."""
    buy = compute_charges(segment, "BUY", entry_premium, qty)["total"]
    sell = compute_charges(segment, "SELL", exit_premium, qty)["total"]
    return round(buy + sell, 2)
