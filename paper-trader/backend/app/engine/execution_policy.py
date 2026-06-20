"""
Adaptive order routing — decide HOW to send an order based on the live book.

A MARKET order on a wide bid-ask spread (illiquid contracts — the COPPER options
the owner flagged) fills deep in the spread and bleeds money instantly. So for an
ENTRY (BUY) we look at the order-time spread and top-of-book depth:

  - tight spread + adequate depth -> MARKET   (fill fast, don't miss a NIFTY move)
  - moderate spread / thin depth  -> LIMIT     (marketable-limit capped at a max
                                                slippage off the mid — caps the
                                                worst price we'll pay)
  - too wide (COPPER-like)         -> SKIP      (don't get caught)

A protective EXIT (SELL on a stop/target) always goes MARKET: not getting out is
worse than the slippage, and it mirrors the GTT safety-net stop.

Pure + side-effect free so it is fully unit-tested without any live broker.
"""
from __future__ import annotations

from dataclasses import dataclass

TICK = 0.05  # option premiums tick in ₹0.05


@dataclass
class OrderPlan:
    action: str               # "MARKET" | "LIMIT" | "SKIP"
    limit_price: float | None  # set only for LIMIT
    reason: str
    spread_pct: float


def _round_tick(price: float) -> float:
    return round(round(price / TICK) * TICK, 2)


def _spread_pct(bid: float, ask: float, ltp: float) -> tuple[float, float]:
    """Return (mid, spread_pct). Unknown/crossed/zero quotes are treated as wide."""
    if bid and ask and ask >= bid > 0:
        mid = (bid + ask) / 2.0
        return mid, (ask - bid) / mid if mid > 0 else 1.0
    # missing or crossed book -> use ltp as the reference but flag the spread as wide
    return (ltp if ltp > 0 else 0.0), 1.0


def plan_order(side: str, bid: float, ask: float, ltp: float,
               top_qty: float | None, lot_qty: int, params: dict) -> OrderPlan:
    mid, spread = _spread_pct(bid, ask, ltp)
    market_max = params["exec_market_max_spread_pct"]
    limit_max = params["exec_limit_max_spread_pct"]
    slip = params["exec_max_slippage_pct"]

    # Protective exit: always market — guarantee the fill.
    if side == "SELL":
        return OrderPlan("MARKET", None,
                         "protective exit — market to guarantee the fill", spread)

    # Entry (BUY).
    if mid <= 0:
        return OrderPlan("SKIP", None, "no usable quote to price the order", spread)
    if spread > limit_max:
        return OrderPlan("SKIP", None,
                         f"spread {spread:.1%} > {limit_max:.0%} max — too illiquid "
                         f"to enter safely", spread)
    thin = top_qty is not None and top_qty < params["exec_min_top_qty_lots"] * lot_qty
    if spread <= market_max and not thin:
        return OrderPlan("MARKET", None,
                         f"tight book (spread {spread:.1%}) — market", spread)
    # moderate spread or thin top-of-book -> capped marketable limit
    limit_price = _round_tick(mid * (1 + slip))
    why = "thin top-of-book" if thin else f"spread {spread:.1%}"
    return OrderPlan("LIMIT", limit_price,
                     f"{why} — capped limit @ {limit_price:.2f} (≤ +{slip:.0%})", spread)
