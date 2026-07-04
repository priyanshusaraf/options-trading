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
        self.cancelled = []
        self.modified = []

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

    def cancel_order(self, **kw):
        self.cancelled.append(kw)
        return kw.get("order_id")

    def modify_order(self, **kw):
        self.modified.append(kw)
        return kw.get("order_id")


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


def test_market_order_carries_automatic_market_protection_by_default():
    """Since SEBI's 1-Apr-2026 rule, a MARKET order via API WITHOUT non-zero market
    protection is rejected (all segments, MCX included). The client must attach
    market_protection=-1 (automatic exchange guideline) by default so the bot can
    place a market order at all."""
    k = FakeKite()
    KiteOrderClient(k).place(OrderRequest("SYM", "NFO", "BUY", 75, "MARKET"))
    assert k.placed[0]["market_protection"] == -1


def test_market_order_passes_configured_protection_pct():
    k = FakeKite()
    KiteOrderClient(k, market_protection=3.0).place(
        OrderRequest("SYM", "NFO", "BUY", 75, "MARKET"))
    assert k.placed[0]["market_protection"] == 3.0


def test_configured_zero_protection_is_coerced_to_automatic():
    """A 0 (or unset) market protection is REJECTED by the exchange — we must never
    send an unprotected market order, so a configured 0 falls back to -1 (auto)."""
    k = FakeKite()
    KiteOrderClient(k, market_protection=0).place(
        OrderRequest("SYM", "NFO", "BUY", 75, "MARKET"))
    assert k.placed[0]["market_protection"] == -1


def test_market_sell_exit_on_commodity_also_carries_protection():
    """The protective SELL exit is a MARKET order too — and on MCX an unprotected
    market order bounces just like a buy. Both directions, all segments, get it."""
    k = FakeKite()
    KiteOrderClient(k).place(OrderRequest("GOLDM25JULFUT", "MCX", "SELL", 10, "MARKET"))
    assert k.placed[0]["market_protection"] == -1


def test_limit_order_carries_no_market_protection():
    """market_protection only applies to MARKET/SL-M; a LIMIT order is already
    price-bounded and must not carry it."""
    k = FakeKite()
    KiteOrderClient(k, market_protection=3.0).place(
        OrderRequest("SYM", "NFO", "BUY", 75, "LIMIT", limit_price=101.0))
    assert "market_protection" not in k.placed[0]


def test_cancel_calls_kite_cancel_order_with_the_variety():
    """Cancelling a stuck/in-flight order needs the same variety it was placed with."""
    k = FakeKite()
    KiteOrderClient(k).cancel("OID-9")
    assert k.cancelled == [{"variety": "regular", "order_id": "OID-9"}]


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


# ── #18 SL-M protective stop for intraday (MIS), where GTT is not allowed ──────
def test_place_stop_order_maps_sl_m_fields():
    # GTT can't back a MIS position (Zerodha: GTT only on CNC/NRML), so the intraday
    # backstop is a real SL-M order resting at the exchange.
    k = FakeKite()
    oid = KiteOrderClient(k).place_stop_order("SYM", "NSE", 13, trigger_price=100.0,
                                              side="SELL", tag="pt-bot")
    assert oid == "OID-9"
    p = k.placed[0]
    assert p["order_type"] == "SL-M" and p["trigger_price"] == 100.0
    assert p["transaction_type"] == "SELL" and p["quantity"] == 13
    assert p["product"] == "MIS" and p["variety"] == "regular"
    assert "price" not in p                        # market-on-trigger — no limit price
    assert p["market_protection"] == -1            # SL-M IS a market order → SEBI protection
    assert p["tag"] == "pt-bot"


def test_place_stop_order_buy_side_covers_a_short():
    k = FakeKite()
    KiteOrderClient(k).place_stop_order("SYM", "NSE", 13, trigger_price=110.0, side="BUY")
    assert k.placed[0]["transaction_type"] == "BUY" and k.placed[0]["order_type"] == "SL-M"


def test_modify_stop_order_changes_the_trigger():
    k = FakeKite()
    KiteOrderClient(k).modify_stop_order("OID-9", trigger_price=95.0)
    m = k.modified[0]
    assert m["order_id"] == "OID-9" and m["trigger_price"] == 95.0 and m["variety"] == "regular"


class FakeKiteWithToken(FakeKite):
    def __init__(self, history=None):
        super().__init__(history)
        self.tokens = []

    def set_access_token(self, tok):
        self.tokens.append(tok)


def test_token_source_syncs_current_token_before_orders():
    """The order client must adopt the data provider's CURRENT access token before
    every Kite call, so a daily re-login flows through without rebuilding the broker —
    and only re-applies it when it actually changes (no redundant set per call)."""
    k = FakeKiteWithToken()
    token = {"v": "tok-day1"}
    c = KiteOrderClient(k, token_source=lambda: token["v"])

    c.place(OrderRequest("SYM", "NFO", "BUY", 75, "MARKET"))
    assert k.tokens == ["tok-day1"]            # applied on first use

    c.place(OrderRequest("SYM", "NFO", "SELL", 75, "MARKET"))
    assert k.tokens == ["tok-day1"]            # unchanged token -> not re-applied

    token["v"] = "tok-day2"                     # simulate a morning re-login
    c.place_stop_gtt("SYM", "NFO", 75, trigger_price=100.0, last_price=140.0)
    assert k.tokens == ["tok-day1", "tok-day2"]  # picked up the fresh token, no restart


# ── GTT is CNC/NRML-only at Zerodha: an equity-exchange (MIS) GTT must fail LOUDLY ──
# The 2026-07-03 class of failure: place_stop_gtt built product=MIS GTTs for NSE/BSE
# which the broker silently rejected server-side — options backstops worked, intraday
# ones never existed. The client must refuse locally (the caller then falls back to
# the SL-M path / alerts) instead of shipping a payload Zerodha will never accept.
def test_stop_gtt_refuses_equity_exchange():
    import pytest
    k = FakeKite()
    c = KiteOrderClient(k)
    with pytest.raises(ValueError):
        c.place_stop_gtt("LODHA", "NSE", 10, 940.0, 990.0)
    with pytest.raises(ValueError):
        c.place_stop_gtt("SENSEXBEES", "BSE", 10, 940.0, 990.0)
    assert k.gtt_placed == []          # nothing reached the broker


def test_modify_stop_gtt_refuses_equity_exchange():
    import pytest
    k = FakeKite()
    c = KiteOrderClient(k)
    with pytest.raises(ValueError):
        c.modify_stop_gtt("555", "LODHA", "NSE", 10, 945.0, 990.0)
    assert k.gtt_modified == []


def test_stop_gtt_still_places_for_fo_exchanges():
    k = FakeKite()
    tid = KiteOrderClient(k).place_stop_gtt("NIFTY26JUL24000CE", "NFO", 75, 55.0, 80.0)
    assert tid == "555"
    assert k.gtt_placed[0]["orders"][0]["product"] == "NRML"
