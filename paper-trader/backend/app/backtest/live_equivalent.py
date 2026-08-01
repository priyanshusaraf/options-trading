"""Translating a backtest result into what the LIVE sizing model would have done.

The 2026-08-01 backtester audit called this the biggest interpretive trap in the
system, and it is not a bug — it is two deliberately different models being read
as one:

  - the backtest holds ONE unleveraged position sized `floor(capital / price)`,
    chosen to isolate the strategy's raw edge per unit of price movement;
  - production sizes against REAL MIS margin with no leverage cap, targeting
    ~₹10,000 of margin per name across up to 4 concurrent positions.

So a backtest `return_pct` is not a prediction of live account return, and its
`net_pnl` is not a prediction of live rupees. Both are statements about edge.

This module makes the conversion explicit instead of leaving it as a caveat
nobody applies. It takes the margin model as an INPUT and refuses to guess:
per-share MIS margin depends on the instrument and the broker's live quote, and
inventing a leverage number here would manufacture exactly the false precision
the audit was written to remove. Give it a real `order_margins()` reading, or
get `None` back.
"""
from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True)
class LiveEquivalent:
    per_share_pnl: float        # the backtest's edge, per share, net of charges
    live_qty: int               # shares the live margin model would have bought
    live_notional: float
    projected_pnl: float        # per-position, before concurrency
    concurrency: int
    projected_pnl_all_slots: float
    scale_vs_backtest: float    # live qty / backtest qty
    assumption: str             # stated in the result, so it travels with the number


def project(*, backtest_net_pnl: float, backtest_qty: int, entry_price: float,
            per_share_margin: float | None, target_margin: float,
            concurrency: int = 1) -> LiveEquivalent | None:
    """What this backtest's edge would have produced under the live sizing model.

    `per_share_margin` must come from a real broker margin quote
    (`kite.order_margins()` on a MARKET/MIS probe, the same call the live sizer
    uses). `None` returns `None` — the honest answer when the margin is unknown
    is no number, not a number with a guessed leverage buried in it.

    Deliberately linear in quantity: it scales the per-share edge, and makes no
    claim that a larger position would have filled at the same price. At
    ₹10k-of-margin sizes on liquid names that is close enough to be useful and
    far enough from true to be worth saying out loud — which is why `assumption`
    is a field on the result rather than a docstring.
    """
    if not backtest_qty or backtest_qty <= 0 or entry_price <= 0:
        return None
    if per_share_margin is None or per_share_margin <= 0:
        return None
    if target_margin <= 0:
        return None

    per_share = backtest_net_pnl / backtest_qty
    live_qty = int(target_margin // per_share_margin)
    if live_qty <= 0:
        return None
    slots = max(1, int(concurrency))
    projected = per_share * live_qty
    return LiveEquivalent(
        per_share_pnl=round(per_share, 4),
        live_qty=live_qty,
        live_notional=round(live_qty * entry_price, 2),
        projected_pnl=round(projected, 2),
        concurrency=slots,
        projected_pnl_all_slots=round(projected * slots, 2),
        scale_vs_backtest=round(live_qty / backtest_qty, 3),
        assumption=(
            f"linear scaling of a per-share edge to {live_qty} shares "
            f"(₹{target_margin:,.0f} target margin ÷ ₹{per_share_margin:,.2f} per-share "
            f"margin), × {slots} concurrent slot(s). Assumes the larger position fills "
            f"at the same price; no market impact is modelled."
        ),
    )
