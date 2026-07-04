"""Kite product routing: intraday equity must go out as MIS (leveraged, same-day,
broker auto-square-off) while options/futures stay NRML (overnight-capable). The
options path must be byte-unchanged — req.product=None keeps the client default."""
from app.engine.kite_order_client import KiteOrderClient, product_for_segment
from app.engine.order_executor import OrderRequest


def test_product_for_segment_maps_intraday_to_mis():
    assert product_for_segment("NSE_INTRADAY") == "MIS"
    assert product_for_segment("BSE_INTRADAY") == "MIS"
    assert product_for_segment("NFO") == "NRML"        # options keep NRML
    assert product_for_segment("NFO_FUT") == "NRML"
    assert product_for_segment("NSE_EQ") == "NRML"     # delivery is not MIS


class _FakeKite:
    def __init__(self):
        self.kw = None
    def place_order(self, **kw):
        self.kw = kw
        return "OID1"


def test_client_uses_req_product_when_set():
    k = _FakeKite()
    client = KiteOrderClient(k, product="NRML")
    client.place(OrderRequest(tradingsymbol="SBIN", exchange="NSE", side="BUY",
                              qty=10, order_type="MARKET", product="MIS"))
    assert k.kw["product"] == "MIS"


def test_client_defaults_to_nrml_for_options_path_unchanged():
    k = _FakeKite()
    client = KiteOrderClient(k, product="NRML")
    client.place(OrderRequest(tradingsymbol="NIFTY24000CE", exchange="NFO", side="BUY",
                              qty=75, order_type="MARKET"))   # product=None
    assert k.kw["product"] == "NRML"
