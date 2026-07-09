"""
GTT (Good-Till-Triggered) safety-net stop payloads.

A GTT lives on Zerodha's servers: it does nothing until the LTP crosses the
trigger, then Zerodha places the order — so it protects an open position even when
the bot, the laptop, or the internet is down. We use a SINGLE GTT per long option
position that SELLs the bot's quantity when the premium falls to the stop.

Pure payload builder (no Kite call), so it is unit-tested without a broker. The
order placed at trigger time is a LIMIT at the trigger price (Kite GTTs are limit
orders); on a hard gap below the trigger it may not fill — a documented GTT
limitation. This is a *backstop* for downtime; the bot's own faster stop/target/
trail handles normal exits.
"""
from __future__ import annotations

# Zerodha's standard NSE/BSE equity + most F&O tick size. A trigger/limit price that
# isn't an exact multiple of this is rejected outright ("Tick size for this script is
# 0.05...") — plain round(x, 2) makes a price clean to the paisa but does not
# guarantee it lands on the tick grid (the 2026-07-08 LODHA stop-loss failure).
TICK_SIZE = 0.05


def round_to_tick(price: float, tick_size: float = TICK_SIZE) -> float:
    """Snap a price to the exchange's tick grid (nearest multiple of `tick_size`)."""
    return round(round(price / tick_size) * tick_size, 2)


def stop_gtt_params(tradingsymbol: str, exchange: str, qty: int,
                    trigger_price: float, last_price: float,
                    product: str = "NRML", side: str = "SELL") -> dict:
    """`side` is the protective order's transaction type: SELL for a long position
    (long option, long equity) whose stop is below; BUY to cover for an intraday
    equity SHORT whose stop is above."""
    trig = round_to_tick(trigger_price)
    return {
        "trigger_type": "single",
        "tradingsymbol": tradingsymbol,
        "exchange": exchange,
        "trigger_values": [trig],
        "last_price": round(last_price, 2),
        "orders": [{
            "transaction_type": side,
            "quantity": int(qty),
            "order_type": "LIMIT",
            "product": product,
            "price": trig,
        }],
    }
