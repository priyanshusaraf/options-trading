"""
How much capital the bot may deploy right now — designed so the owner's own
trades always take priority on a shared real account.

Two bounds, whichever is tighter:
  * bot capital cap headroom: (cap or ledger_base) - what the bot already deployed
  * (live only) real account headroom: live available margin - a reserve kept free
    for the owner

Using the LIVE available margin means the owner's own positions (which consume that
margin) automatically reduce what the bot can touch. The hard cap is a second,
independent ceiling so a brief margin-feed glitch during the owner's intraday exits
can never let the bot overspend.
"""
from __future__ import annotations


def deployable_capital(*, ledger_base: float, bot_deployed: float,
                       account_available: float | None, reserve: float,
                       cap: float, is_live: bool) -> float:
    base = cap if cap and cap > 0 else ledger_base
    cap_headroom = base - bot_deployed
    if is_live and account_available is None:
        # H12: live but the real account headroom is unknown (margins()/token failure).
        # Fail CLOSED — never size a new entry off the bot's ledger cap while blind to
        # the real account; deploy nothing until the funds read recovers.
        return 0.0
    headroom = cap_headroom
    if is_live and account_available is not None:
        headroom = min(cap_headroom, account_available - reserve)
    return max(0.0, headroom)
