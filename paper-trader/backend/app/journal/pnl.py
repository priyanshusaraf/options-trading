"""Pure P&L math for manual/physical journal trades. Reuses the engine's real
charge schedule (app.engine.charges) so journal figures are net-of-cost on the
same basis as the live/backtest ledgers — no separate cost model to drift.
"""
from __future__ import annotations

from app.engine.charges import compute_charges

SEGMENT = "MCX_FUT"


def gross_pnl(direction: str, entry_price: float, exit_price: float, *,
              lots: int, lot_size: int, multiplier: float = 1.0) -> float:
    qty = lots * lot_size
    move = (exit_price - entry_price) if direction == "LONG" else (entry_price - exit_price)
    return move * qty * multiplier


def round_trip_charges(entry_price: float, exit_price: float, *,
                        lots: int, lot_size: int) -> float:
    qty = lots * lot_size
    entry_leg = compute_charges(SEGMENT, "BUY", entry_price, qty)["total"]
    exit_leg = compute_charges(SEGMENT, "SELL", exit_price, qty)["total"]
    return entry_leg + exit_leg


def net_pnl(direction: str, entry_price: float, exit_price: float, *,
            lots: int, lot_size: int, multiplier: float = 1.0,
            manual_net_pnl: float | None = None) -> float:
    if manual_net_pnl is not None:
        return manual_net_pnl
    gross = gross_pnl(direction, entry_price, exit_price,
                       lots=lots, lot_size=lot_size, multiplier=multiplier)
    charges = round_trip_charges(entry_price, exit_price, lots=lots, lot_size=lot_size)
    return gross - charges


def unrealized_pnl(direction: str, entry_price: float, last_price: float, *,
                    lots: int, lot_size: int, multiplier: float = 1.0) -> float:
    """Mark-to-market on an OPEN trade: gross minus the entry leg's charges only
    (the exit leg hasn't happened yet, so it isn't deducted)."""
    qty = lots * lot_size
    gross = gross_pnl(direction, entry_price, last_price,
                       lots=lots, lot_size=lot_size, multiplier=multiplier)
    entry_leg = compute_charges(SEGMENT, "BUY", entry_price, qty)["total"]
    return gross - entry_leg
