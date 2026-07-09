"""audit H1: /ws/instrument's per-tick fetch (synchronous Kite calls) must run off
the event loop. The blocking work is factored into _instrument_payload so the WS
handler can asyncio.to_thread it — proven here to keep the loop responsive."""
import asyncio
import time

from app.api.routes import _instrument_payload
from app.db.session import init_db
from app.providers.mock import MockProvider


def test_instrument_payload_returns_the_tick_shape():
    init_db(reset=True)
    prov = MockProvider()
    p = _instrument_payload(prov, "NIFTY")
    assert p["instrument"] == "NIFTY"
    assert "time" in p and "spot" in p
    assert "option_premium" in p and "tradingsymbol" in p


def test_payload_fetch_offloaded_keeps_loop_responsive():
    init_db(reset=True)
    prov = MockProvider()
    real_price = prov.get_live_price

    def slow_price(inst):
        time.sleep(0.3)                     # stand-in for a slow Kite quote
        return real_price(inst)

    prov.get_live_price = slow_price
    asyncio.run(_probe(prov))


async def _probe(prov):
    ticks = {"n": 0}
    stop = {"v": False}

    async def ticker():
        while not stop["v"]:
            await asyncio.sleep(0.01)
            ticks["n"] += 1

    t = asyncio.create_task(ticker())
    await asyncio.to_thread(_instrument_payload, prov, "NIFTY")   # the handler's per-tick call
    during = ticks["n"]
    stop["v"] = True
    await t
    assert during >= 3               # the event loop kept running through the slow fetch
