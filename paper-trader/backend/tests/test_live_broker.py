"""LiveBroker: real-order fills booked at the ACTUAL price, and the ownership
boundary — it will not close a position the live account doesn't back (your
position, a manual exit, a margin glitch). No real exchange: a fake order client
and a fake account-positions feed."""
from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.execution_policy import OrderPlan
from app.engine.live_broker import LiveBroker
from app.providers.mock import MockProvider

MKT = OrderPlan("MARKET", None, "tight", 0.005)


class FakeClient:
    def __init__(self, fill_price=100.0, status="COMPLETE"):
        self.fill_price = fill_price
        self._status = status
        self.placed = []
        self._req = None

    def place(self, req):
        self.placed.append(req)
        self._req = req
        return "OID-1"

    def status(self, order_id):
        return {"status": self._status, "filled_qty": self._req.qty,
                "avg_price": self.fill_price, "reason": "x"}


def _broker(client, account=None):
    init_db(reset=True)
    prov = MockProvider()
    prov.account_positions = lambda: (account or [])
    return LiveBroker(prov, client, poll_seconds=0.0, timeout_seconds=0.0)


def _open(b, client):
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    return b.open_position(inst, "LONG", q, "t", b.provider.now(), chain.spot,
                           params={}, plan=MKT), q, chain


def test_open_books_the_actual_fill_price():
    c = FakeClient(fill_price=123.45)
    b = _broker(c)
    pos, q, _ = _open(b, c)
    assert pos is not None
    assert pos.entry_premium == 123.45            # real fill, not the snapshot ltp
    assert c.placed[0].side == "BUY" and c.placed[0].order_type == "MARKET"


def test_open_returns_none_and_records_nothing_when_not_filled():
    c = FakeClient(status="REJECTED")
    b = _broker(c)
    pos, _, _ = _open(b, c)
    assert pos is None
    assert len(b.open_positions()) == 0


def test_close_blocked_when_account_does_not_back_the_position():
    c = FakeClient(fill_price=100.0)
    b = _broker(c, account=[])                     # the account holds nothing
    pos, q, chain = _open(b, c)
    assert pos is not None
    res = b.close_position(pos, 90.0, "STOP_LOSS", b.provider.now(), chain.spot)
    assert res is None                             # NO sell order sent
    assert b.position_for("NIFTY") is not None     # position protected, still held


def test_close_sells_when_account_backs_the_position():
    c = FakeClient(fill_price=100.0)
    b = _broker(c)
    pos, q, chain = _open(b, c)
    b.provider.account_positions = lambda: [{"tradingsymbol": pos.tradingsymbol,
                                             "quantity": pos.qty}]
    c.fill_price = 140.0
    tr = b.close_position(pos, 140.0, "TARGET", b.provider.now(), chain.spot)
    assert tr is not None
    assert b.position_for("NIFTY") is None
    assert c.placed[-1].side == "SELL" and tr.exit_premium == 140.0
