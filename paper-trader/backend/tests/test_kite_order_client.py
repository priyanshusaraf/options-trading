"""The OrderClient adapter maps our OrderRequest onto Kite place_order / reads the
fill from order_history. Tested with a fake kite — no real exchange."""
from app.engine.kite_order_client import KiteOrderClient
from app.engine.order_executor import OrderRequest


class FakeKite:
    def __init__(self, history=None):
        self.history = history or []
        self.placed = []

    def place_order(self, **kw):
        self.placed.append(kw)
        return "OID-9"

    def order_history(self, order_id):
        return self.history


def test_place_maps_limit_order_fields():
    k = FakeKite()
    oid = KiteOrderClient(k).place(
        OrderRequest("SYM", "NFO", "BUY", 75, "LIMIT", limit_price=101.0, tag="pt-bot"))
    assert oid == "OID-9"
    p = k.placed[0]
    assert p["tradingsymbol"] == "SYM" and p["exchange"] == "NFO"
    assert p["transaction_type"] == "BUY" and p["quantity"] == 75
    assert p["order_type"] == "LIMIT" and p["price"] == 101.0
    assert p["variety"] == "regular" and p["product"] == "NRML"


def test_market_order_carries_no_price():
    k = FakeKite()
    KiteOrderClient(k).place(OrderRequest("SYM", "NFO", "SELL", 75, "MARKET"))
    assert k.placed[0]["order_type"] == "MARKET" and "price" not in k.placed[0]


def test_status_reads_last_history_row():
    k = FakeKite([{"status": "OPEN", "filled_quantity": 0, "average_price": 0.0},
                  {"status": "COMPLETE", "filled_quantity": 75, "average_price": 100.5,
                   "status_message": ""}])
    st = KiteOrderClient(k).status("OID-9")
    assert st["status"] == "COMPLETE" and st["filled_qty"] == 75 and st["avg_price"] == 100.5
