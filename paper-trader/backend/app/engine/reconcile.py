"""
Position ownership & reconciliation — keep the bot strictly to ITS OWN positions.

This is the single most important safety boundary now that the platform trades on
the owner's REAL Kite account, which also holds the owner's own discretionary
stock/option trades. The rules the live broker enforces:

  * The bot only ever acts on contracts IT opened and recorded in its ledger.
  * Before it closes one of its long option positions with a real SELL, it checks
    the live account actually holds AT LEAST the bot's quantity, LONG, of that exact
    contract. If not — the owner traded the same symbol, exited manually, or Kite's
    position/margin feed is briefly wrong — it sends NO order and flags it instead.
  * It never enumerates the account's positions to act on them, never 'exit all',
    never convert. Only ever a specific order for a specific contract+qty it owns.

Pure functions over plain data (Kite position dicts), so fully unit-tested with no
live broker. Position-based checks are used (not margin) because positions are the
reliable signal during the owner's intraday exits when margin can lag.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OwnershipCheck:
    ok: bool
    available_same_side: int   # net account qty for the symbol (long +, short -)
    reason: str


def account_net_qty(account_positions: list[dict], tradingsymbol: str) -> int:
    """Net signed quantity the ACCOUNT holds for a symbol (long +, short -)."""
    return sum(int(p.get("quantity", 0)) for p in account_positions
               if p.get("tradingsymbol") == tradingsymbol)


def can_bot_close(pos, account_positions: list[dict]) -> OwnershipCheck:
    """The bot holds `pos` (always a bought option, long, qty > 0). It is safe to
    send a closing SELL only if the account is long at least `pos.qty` of that exact
    contract — otherwise selling would eat into the owner's holding or open/deepen a
    short for them."""
    net = account_net_qty(account_positions, pos.tradingsymbol)
    if net >= pos.qty:
        return OwnershipCheck(True, net, "account backs the bot position")
    return OwnershipCheck(
        False, net,
        f"account holds {net} of {pos.tradingsymbol} but the bot expects "
        f">= {pos.qty} long — NOT sending an order (your position, a manual exit, "
        f"or a margin/position glitch). Flagging for you instead.")


def find_orphans(bot_positions, account_positions: list[dict]) -> list:
    """Bot-tracked positions the live account no longer fully backs — these need the
    owner's attention (and must never be auto-traded)."""
    return [p for p in bot_positions if not can_bot_close(p, account_positions).ok]
