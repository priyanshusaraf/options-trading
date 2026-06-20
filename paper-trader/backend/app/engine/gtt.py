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


def stop_gtt_params(tradingsymbol: str, exchange: str, qty: int,
                    trigger_price: float, last_price: float,
                    product: str = "NRML") -> dict:
    trig = round(trigger_price, 2)
    return {
        "trigger_type": "single",
        "tradingsymbol": tradingsymbol,
        "exchange": exchange,
        "trigger_values": [trig],
        "last_price": round(last_price, 2),
        "orders": [{
            "transaction_type": "SELL",
            "quantity": int(qty),
            "order_type": "LIMIT",
            "product": product,
            "price": trig,
        }],
    }
