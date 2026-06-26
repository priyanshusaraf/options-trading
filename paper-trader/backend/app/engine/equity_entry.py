"""
Intraday-equity (MIS) sizing + contention selection — pure, engine-free logic.

The options path sizes at a fixed 1 lot; intraday equity sizes by the MARGIN it
deploys: 7–10k of margin controls ~35–50k of stock at 5x. From a target margin and
a share price we get an integer share quantity. When more signals fire than the
hard cap of 3 concurrent trades allows, the selector enforces the owner's rules:

  * purple (watchlist-priority) names always win a slot, sized at purple_margin;
  * non-purple names compete for the leftover slots by HIGHER QUANTITY — a cheaper
    share buys more units for the same margin, so cheaper wins;
  * the cap of 3 is TOTAL (purple included);
  * selection is cash-greedy and respects a minimum-margin floor.

This module decides WHICH names to enter and HOW MANY shares. It books nothing —
the broker/runner consume the picks. Keeping it pure makes the risk rules trivially
testable (tests/test_equity_entry.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field


def equity_qty(margin: float, leverage: float, price: float) -> int:
    """Share quantity for `margin` of deployed capital at `leverage`: the position
    controls margin×leverage of stock, so qty = floor(margin×leverage / price)."""
    if price <= 0 or margin <= 0 or leverage <= 0:
        return 0
    return int((margin * leverage) // price)


# ── direction-aware exit geometry (equity LONG *and* real intraday SHORT) ────
# Unlike the options path (always long-premium: stop below, target above), an
# equity SHORT profits when price FALLS, so its stop is ABOVE entry and target
# BELOW. These small pure helpers keep that geometry in one tested place.

def equity_stop_target(direction: str, entry: float, sl_pct: float,
                       tp_pct: float) -> tuple[float, float]:
    """(stop_price, target_price) for an equity position. LONG: stop below / target
    above; SHORT: stop above / target below."""
    if direction == "LONG":
        return entry * (1 - sl_pct), entry * (1 + tp_pct)
    return entry * (1 + sl_pct), entry * (1 - tp_pct)


def equity_exit(direction: str, price: float, stop: float, target: float,
                strat_long_exit: bool, strat_short_exit: bool) -> tuple[bool, str]:
    """Decide whether an open equity position should close on this mark. Order of
    precedence: protective stop, then target, then the strategy's own exit flag.
    Returns (exit, reason) with reason in {STOP_LOSS, TARGET, STRATEGY_EXIT, ""}."""
    if direction == "LONG":
        if price <= stop:
            return True, "STOP_LOSS"
        if price >= target:
            return True, "TARGET"
        if strat_long_exit:
            return True, "STRATEGY_EXIT"
    else:  # SHORT
        if price >= stop:
            return True, "STOP_LOSS"
        if price <= target:
            return True, "TARGET"
        if strat_short_exit:
            return True, "STRATEGY_EXIT"
    return False, ""


def equity_unrealized(direction: str, entry: float, price: float, qty: int) -> float:
    """Mark-to-market P&L on the full share notional (LONG profits up, SHORT down)."""
    move = (price - entry) if direction == "LONG" else (entry - price)
    return move * qty


@dataclass
class IntradayCandidate:
    instrument_key: str
    direction: str            # LONG | SHORT
    price: float              # current share price (entry reference)
    is_purple: bool = False   # watchlist priority flag


@dataclass
class IntradayPick:
    instrument_key: str
    direction: str
    price: float
    qty: int
    margin: float             # actual margin deployed = qty × price / leverage
    is_purple: bool


@dataclass
class IntradaySelection:
    selected: list[IntradayPick] = field(default_factory=list)
    skipped: list[tuple[IntradayCandidate, str]] = field(default_factory=list)


def _priority(key: str) -> int:
    # liquidity priority only breaks ties; unknown keys (and any lookup hiccup) sink
    # to the bottom so the selector stays pure/testable without a seeded universe.
    try:
        from app.core.instruments import get_instrument
        return get_instrument(key).priority
    except Exception:
        return 999


def select_intraday_entries(cands: list[IntradayCandidate], *, max_positions: int,
                            min_margin: float, max_margin: float, purple_margin: float,
                            leverage: float, available_cash: float) -> IntradaySelection:
    """Choose up to `max_positions` intraday entries under the owner's rules
    (see module docstring). Returns selected picks (with sized qty/margin) and the
    skipped candidates with a reason each."""
    res = IntradaySelection()
    purple = sorted((c for c in cands if c.is_purple),
                    key=lambda c: _priority(c.instrument_key))
    # non-purple: cheapest share first (highest qty at the target margin), then
    # liquidity priority as a deterministic tie-break.
    normal = sorted((c for c in cands if not c.is_purple),
                    key=lambda c: (-equity_qty(max_margin, leverage, c.price),
                                   _priority(c.instrument_key)))
    cash = available_cash

    def consider(c: IntradayCandidate, target_margin: float) -> None:
        nonlocal cash
        if len(res.selected) >= max_positions:
            res.skipped.append((c, "max concurrent intraday positions reached"))
            return
        qty = equity_qty(target_margin, leverage, c.price)
        if qty < 1:
            res.skipped.append((c, f"share price ₹{c.price:,.0f} too high — target "
                                   f"margin buys <1 share"))
            return
        margin = qty * c.price / leverage
        if margin < min_margin:
            res.skipped.append((c, f"below the ₹{min_margin:,.0f} margin floor "
                                   f"(only ₹{margin:,.0f} fits at ₹{c.price:,.0f}/share)"))
            return
        if margin > cash:
            res.skipped.append((c, f"insufficient cash: need ₹{margin:,.0f}, "
                                   f"have ₹{cash:,.0f}"))
            return
        res.selected.append(IntradayPick(c.instrument_key, c.direction, c.price,
                                         qty, margin, c.is_purple))
        cash -= margin

    for c in purple:
        consider(c, purple_margin)
    for c in normal:
        consider(c, max_margin)
    return res
