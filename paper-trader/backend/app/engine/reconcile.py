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


def account_net_qty(account_positions: list[dict] | None, tradingsymbol: str) -> int:
    """Net signed quantity the ACCOUNT holds for a symbol (long +, short -).
    A None read (API/auth failure) is NOT a flat account — returns 0, but callers
    must fail closed via can_bot_close/find_orphans, not treat 0 as 'flat'."""
    if account_positions is None:
        return 0
    return sum(int(p.get("quantity", 0)) for p in account_positions
               if p.get("tradingsymbol") == tradingsymbol)


def _is_short_equity(pos) -> bool:
    return getattr(pos, "segment", None) == "equity_intraday" and pos.direction == "SHORT"


def can_bot_close(pos, account_positions: list[dict] | None) -> OwnershipCheck:
    """It is safe to send the bot's closing order only if the live account actually
    backs the bot's position of that exact symbol — otherwise the order would eat into
    the owner's own holding or open/deepen a position for them.

      long (bought option, long equity): account must be long  >= +pos.qty -> SELL.
      intraday-equity SHORT: account must be short <= -pos.qty            -> BUY to cover.
    Position-based (not margin) because positions are the reliable signal during the
    owner's intraday exits when margin can lag.

    account_positions is None when the live read failed (network/rate-limit/expired
    token — the routine ~06:00 IST expiry). That is NOT a flat account: fail closed,
    send no order, so a dead-token read can never be mistaken for 'the owner exited'."""
    if account_positions is None:
        return OwnershipCheck(
            False, 0,
            f"account read unavailable (API/auth failure) — cannot verify the account "
            f"backs {pos.tradingsymbol}; sending no order")
    net = account_net_qty(account_positions, pos.tradingsymbol)
    if _is_short_equity(pos):
        if net <= -pos.qty:
            return OwnershipCheck(True, net, "account backs the bot short")
        return OwnershipCheck(
            False, net,
            f"account holds {net} of {pos.tradingsymbol} but the bot expects "
            f"<= -{pos.qty} (short) — NOT sending a cover order (your position, a manual "
            f"exit, or a margin/position glitch). Flagging for you instead.")
    if net >= pos.qty:
        return OwnershipCheck(True, net, "account backs the bot position")
    return OwnershipCheck(
        False, net,
        f"account holds {net} of {pos.tradingsymbol} but the bot expects "
        f">= {pos.qty} long — NOT sending an order (your position, a manual exit, "
        f"or a margin/position glitch). Flagging for you instead.")


def find_orphans(bot_positions, account_positions: list[dict] | None) -> list:
    """Bot-tracked positions the live account no longer fully backs — these need the
    owner's attention (and must never be auto-traded).

    A None read (API/auth failure) returns [] — we cannot confirm anything is orphaned
    without a reliable account read, so nothing is phantom-closed. This is the fix for
    the daily-token-expiry mass-phantom-close bug (audit C4): [] read == flat account,
    but None read == 'unknown', and the two must not be conflated."""
    if account_positions is None:
        return []
    return [p for p in bot_positions if not can_bot_close(p, account_positions).ok]
