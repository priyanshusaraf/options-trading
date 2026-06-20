"""The OrderClient adapter maps our OrderRequest onto Kite place_order / reads the
fill from order_history. Tested with a fake kite — no real exchange."""
from app.engine.kite_order_client import KiteOrderClient
from app.engine.order_executor import OrderRequest


class FakeKite:
    def __init__(self, history=None):
        self.history = history or []
        self.placed = []
        self.gtt_placed = []
        self.gtt_modified = []
        self.gtt_deleted = []

    def place_order(self, **kw):
        self.placed.append(kw)
        return "OID-9"

    def order_history(self, order_id):
        return self.history

    def place_gtt(self, **kw):
        self.gtt_placed.append(kw)
        return {"trigger_id": 555}

    def modify_gtt(self, **kw):
        self.gtt_modified.append(kw)
        return {"trigger_id": kw.get("trigger_id")}

    def delete_gtt(self, trigger_id):
        self.gtt_deleted.append(trigger_id)
        return {"trigger_id": trigger_id}


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


def test_place_stop_gtt_maps_payload_and_returns_id():
    k = FakeKite()
    tid = KiteOrderClient(k).place_stop_gtt("SYM", "NFO", 75,
                                            trigger_price=100.0, last_price=140.0)
    assert tid == "555"
    g = k.gtt_placed[0]
    assert g["tradingsymbol"] == "SYM" and g["trigger_values"] == [100.0]
    assert g["orders"][0]["transaction_type"] == "SELL" and g["orders"][0]["quantity"] == 75


def test_modify_and_delete_gtt():
    k = FakeKite()
    c = KiteOrderClient(k)
    c.modify_stop_gtt("555", "SYM", "NFO", 75, trigger_price=120.0, last_price=160.0)
    assert k.gtt_modified[0]["trigger_id"] == "555"
    assert k.gtt_modified[0]["trigger_values"] == [120.0]
    c.delete_gtt("555")
    assert k.gtt_deleted == ["555"]
