"""Bot-vs-manual attribution for orders read off the live Kite account.

Pure by construction: dicts in, a verdict out. No DB, no Kite, no engine import.
That is what makes it exhaustively testable, and it follows this repo's strongest
existing convention (app/engine/reconcile.py).

Two independent sources say "the bot placed this":

  1. tag == "pt-bot" — broker-side truth. Survives a restart and a local DB loss.
     Set at all five placement sites in live_broker.py.
  2. order_id in the local order_journal — local truth. Survives a broker read
     that omits the tag.

Either alone is sufficient. Neither is necessary, which is why an untagged order
is not automatically manual:

  A GTT-triggered stop carries NO tag. Zerodha creates the order server-side and
  the GTT API has no tag field. Worse, Position.gtt_trigger_id is cleared on
  every exit path (live_broker.py:504,614,850,877), so a fired-and-closed GTT
  leaves nothing to attribute against either. Rather than edit the live order
  path to record GTT ids — a real-money change in service of a journalling
  feature — we fail closed on symbol overlap.

The asymmetry driving the whole design: a bot trade mislabelled MANUAL costs a
confusing prompt; a manual trade mislabelled BOT silently corrupts the bot's P&L
attribution and nobody ever sees it. So ambiguity goes to NEEDS_REVIEW.
"""
from __future__ import annotations

BOT = "BOT"
MANUAL = "MANUAL"
NEEDS_REVIEW = "NEEDS_REVIEW"

# Must stay identical to live_broker.TAG. Deliberately NOT imported from there:
# app/ledger/ must never import app/engine/. tests/ledger/test_isolation.py
# asserts the two constants agree.
BOT_TAG = "pt-bot"

# The bot only ever places MIS (equity intraday) or NRML (options). It cannot
# place a delivery order, so CNC is proof of a human regardless of symbol.
_BOT_PRODUCTS = {"MIS", "NRML"}


def classify_order(
    order: dict,
    bot_order_ids: set[str],
    bot_symbols_today: set[str],
) -> str:
    """Return BOT, MANUAL or NEEDS_REVIEW for one Kite order dict.

    `bot_order_ids` — order_id values from the local order_journal, as strings,
      with NULLs already dropped by the caller.
    `bot_symbols_today` — tradingsymbols the bot placed or held today.
    """
    tag = (order.get("tag") or "").strip()
    if tag == BOT_TAG:
        return BOT

    oid = order.get("order_id")
    if oid is not None and str(oid) in bot_order_ids:
        return BOT

    product = (order.get("product") or "").strip().upper()
    if product and product not in _BOT_PRODUCTS:
        return MANUAL

    symbol = (order.get("tradingsymbol") or "").strip().upper()
    if symbol and symbol in {s.strip().upper() for s in bot_symbols_today}:
        # Untagged, unknown locally, on a symbol the bot touched today. That is
        # exactly the shape of a GTT-fired stop. Refuse to guess.
        return NEEDS_REVIEW

    return MANUAL
