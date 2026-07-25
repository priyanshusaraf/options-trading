"""E9 — the entry LIMIT price must snap to the instrument's REAL tick grid.

The surviving cousin of the 2026-07-08 LODHA / 2026-07-15 tick-size class. Every
TRIGGER path (place_stop_order, modify_stop_order, the GTTs) resolves the real
per-instrument tick and snaps to it, but `place()` forwarded `req.limit_price`
untouched — and `execution_policy` computes it on a hardcoded 0.05 grid. A contract on
a coarser grid, quoted inside the LIMIT-routing spread band, gets the entry order
REJECTED outright ("Tick size for this script is …") → a silently missed entry.
"""
from app.engine.kite_order_client import KiteOrderClient
from app.engine.order_executor import OrderRequest
from tests.test_kite_order_client import FakeKite


def _tick_source():
    grid = {"LT": 0.10, "MARUTI": 1.00}
    return lambda sym, exch: grid.get(sym)


def _limit(sym, price, tick_source=None):
    k = FakeKite()
    KiteOrderClient(k, tick_source=tick_source).place(
        OrderRequest(sym, "NSE", "BUY", 1, "LIMIT", price, tag="t"))
    return k.placed[0]["price"]


def test_limit_price_snaps_to_the_standard_grid():
    assert _limit("LODHA", 1125.13) == 1125.15


def test_limit_price_uses_the_real_tenth_rupee_grid():
    """LT-like: a 0.05 rounding gives 3837.45, which the exchange rejects."""
    assert _limit("LT", 3837.4499, _tick_source()) == 3837.4


def test_limit_price_uses_the_real_whole_rupee_grid():
    price = _limit("MARUTI", 12786.3, _tick_source())
    assert price == 12786.0
    assert price * 100 == int(price * 100)        # paise-exact, no float residue


def test_an_already_aligned_limit_price_is_untouched():
    assert _limit("LODHA", 1125.15) == 1125.15


def test_market_orders_still_carry_no_price():
    k = FakeKite()
    KiteOrderClient(k).place(OrderRequest("LODHA", "NSE", "BUY", 1, "MARKET", None, tag="t"))
    assert "price" not in k.placed[0]
