"""The second `ExecutionVenue` — and the first evidence that the seam is a boundary rather than
Kite with neutral names on it.

`tests/test_venue_boundary.py` proved `KiteVenue` implements the protocol. That is one adapter,
and one adapter cannot distinguish "a neutral contract" from "Kite's shape, renamed". These tests
hold a second, genuinely different broker to the same protocol and check the places where it
does NOT match — because those are where a boundary either earns its cost or quietly leaks.

Written against https://dhanhq.co/docs/v2/ read on 2026-08-10. Each test names the documented
fact it enforces.
"""
from __future__ import annotations

import pytest

from app.engine.broker_protocol import ProtectiveStopKind, Tenor
from app.engine.dhan_order_client import DhanOrderClient, DhanOrderRejected, normalise_order
from app.engine.dhan_venue import (
    DhanVenue,
    UnsupportedProtection,
    UnsupportedSegment,
    dhan_exchange,
    dhan_product,
)
from app.engine.order_executor import OrderRequest
from app.engine.venue import ExecutionVenue


class _Resp:
    def __init__(self, data):
        self.data = data


class FakeDhanTransport:
    """Records what a real Dhan API would have been asked to do."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.order_row = {"orderId": "DH-1", "orderStatus": "PENDING"}
        self.book: list[dict] = []

    def post(self, path, body, *, allow_list: bool = False):
        # `allow_list` mirrors the real transport: the order endpoints opt in because Dhan
        # answers some of them with a single-element array. Accepted here so the fake cannot
        # pass while the real signature has drifted.
        self.calls.append(("POST", path, body))
        if path == "/margincalculator":
            return _Resp({"totalMargin": 1234.5})
        return _Resp(dict(self.order_row))

    def get(self, path):
        self.calls.append(("GET", path))
        if path == "/fundlimit":
            return _Resp({"availabelBalance": 50000.0})
        if path == "/orders":
            return _Resp(list(self.book))
        return _Resp(dict(self.order_row))

    def put(self, path, body):
        self.calls.append(("PUT", path, body)); return _Resp({"orderId": "DH-1"})

    def delete(self, path):
        self.calls.append(("DELETE", path)); return _Resp({"orderId": "DH-1"})


def _venue(tick_source=None):
    t = FakeDhanTransport()
    c = DhanOrderClient(t, lambda: "1000000001", tick_source=tick_source)
    return DhanVenue(c), c, t


# ── the protocol is satisfied by a genuinely different broker ─────────────

def test_dhan_implements_every_verb_the_protocol_declares():
    """If a second adapter cannot implement the protocol, the protocol was Kite's shape with
    neutral names on it. This is the test that distinguishes those two."""
    verbs = [n for n, v in vars(ExecutionVenue).items()
             if callable(v) and not n.startswith("_")]
    assert len(verbs) >= 13, "the ExecutionVenue protocol lost its verbs"
    missing = [n for n in verbs if not callable(getattr(DhanVenue, n, None))]
    assert not missing, f"DhanVenue does not implement {missing}"


def test_dhan_leaks_no_kite_vocabulary_back_through_the_seam():
    """Implementations "MUST NOT leak their own wire vocabulary back" (venue.py). The mirror
    risk for a second adapter is leaking the FIRST adapter's vocabulary — copying MIS/NRML out
    of `kite_venue.py` would pass every test that only checks a string came back."""
    v, _, _ = _venue()
    assert v.product_for(Tenor.INTRADAY) == "INTRADAY"   # not MIS
    assert v.product_for(Tenor.CARRY) == "MARGIN"        # not NRML
    assert v.exchange_for("NSE_INTRADAY") == "NSE_EQ"    # not bare "NSE"
    assert v.exchange_for("NFO") == "NSE_FNO"            # not "NFO"


def test_an_unmapped_segment_is_refused_not_passed_through():
    """Dhan's segment vocabulary is its own. Passing an unmapped value through is rejected at
    the API with an error that does not name the field — so the refusal happens here."""
    with pytest.raises(UnsupportedSegment):
        dhan_exchange("NCDEX")


# ── the capability Dhan genuinely lacks ───────────────────────────────────

@pytest.mark.parametrize("verb,args", [
    ("place_protective_stop", {}),
    ("modify_protective_stop", {"protective_id": "X"}),
    ("cancel_protective_stop", {"protective_id": "X"}),
    ("protective_stop_state", {"protective_id": "X"}),
    ("protective_inventory", {}),
])
def test_a_server_trigger_is_refused_on_every_verb_not_just_placement(verb, args):
    """The most valuable test in this file.

    Dhan has no GTT equivalent — `STOP_LOSS_MARKET` is a RESTING_STOP, and super orders bundle
    entry+stop+target and cannot attach to an already-open position. Substituting a RESTING_STOP
    would look like it worked: it protects the position. But the ids differ (an order id vs a
    trigger id), the margin differs, and `_protection_inventory` matches one and not the other —
    so `protective_stop_state` would report a fill that never happened, and the check that
    decides whether the bot may re-enter a contract reads exactly that.

    Refusing on placement alone is not enough: a position protected under a different venue, or
    a stale id from a previous session, reaches the modify/cancel/read paths directly.
    """
    v, _, _ = _venue()
    kwargs = dict(args)
    if verb in ("place_protective_stop", "modify_protective_stop"):
        kwargs |= {"tradingsymbol": "DLF", "exchange": "NSE_EQ", "qty": 10,
                   "trigger_price": 99.0}
    with pytest.raises(UnsupportedProtection):
        getattr(v, verb)(ProtectiveStopKind.SERVER_TRIGGER, **kwargs)


def test_the_refusal_names_what_the_venue_can_do():
    v, _, _ = _venue()
    assert v.PROTECTIVE_KINDS == frozenset({ProtectiveStopKind.RESTING_STOP})
    with pytest.raises(UnsupportedProtection) as e:
        v.protective_inventory(ProtectiveStopKind.SERVER_TRIGGER)
    assert "STOP_LOSS_MARKET" in str(e.value) and "super order" in str(e.value).lower()


def test_a_resting_stop_is_placed_as_stop_loss_market():
    v, _, t = _venue()
    assert v.place_protective_stop(
        ProtectiveStopKind.RESTING_STOP, tradingsymbol="DLF", exchange="NSE_EQ",
        qty=10, trigger_price=99.0, tag="pt-bot") == "DH-1"
    _, path, body = t.calls[-1]
    assert path == "/orders"
    assert body["orderType"] == "STOP_LOSS_MARKET"
    assert body["triggerPrice"] == 99.0
    assert body["correlationId"] == "pt-bot"


# ── the status vocabulary, which is the likeliest thing to get wrong ──────

def test_traded_is_the_fill_not_complete():
    """Dhan's terminal fill is `TRADED`; Kite's is `COMPLETE`. A status map copied from Kite
    reads every filled Dhan order as still working, and `execute_order` polls to TIMEOUT on an
    order that filled instantly — which the caller must then treat as possibly-working and
    refuse to replace."""
    assert normalise_order({"orderStatus": "TRADED", "filledQty": 10,
                            "averageTradedPrice": 101.5})["status"] == "COMPLETE"
    assert normalise_order({"orderStatus": "PART_TRADED", "filledQty": 4})["status"] == "PARTIAL"
    assert normalise_order({"orderStatus": "REJECTED"})["status"] == "REJECTED"
    assert normalise_order({"orderStatus": "EXPIRED"})["status"] == "CANCELLED"


def test_complete_is_not_a_dhan_status_at_all():
    """Guard the guard. If someone 'fixes' the map by adding COMPLETE, that is the Kite word
    leaking back in — Dhan never sends it, so the branch would be dead and the real one wrong."""
    from app.engine.dhan_order_client import DEAD_STATUSES, FILLED_STATUS
    assert FILLED_STATUS == "TRADED"
    assert "COMPLETE" not in DEAD_STATUSES


def test_a_rejected_order_returned_with_http_200_is_raised_not_returned():
    """Dhan can answer 200 with a REJECTED order. Returning its id as a successful placement
    leaves the caller polling an order that will never work — and, for a protective stop,
    believing the position is backstopped when nothing is resting."""
    v, _, t = _venue()
    t.order_row = {"orderId": "DH-9", "orderStatus": "REJECTED",
                   "omsErrorCode": "RMS-1", "omsErrorDescription": "insufficient margin"}
    with pytest.raises(DhanOrderRejected) as e:
        v.place(OrderRequest("DLF", "NSE_EQ", "BUY", 10, "MARKET"))
    assert "insufficient margin" in str(e.value)


def test_a_response_with_no_order_id_is_raised():
    v, _, t = _venue()
    t.order_row = {"omsErrorCode": "X", "omsErrorDescription": "bad payload"}
    with pytest.raises(DhanOrderRejected):
        v.place(OrderRequest("DLF", "NSE_EQ", "BUY", 10, "MARKET"))


# ── the tick grid — the 2026-07-15 incident, at a second broker ───────────

def test_a_stop_trigger_is_snapped_to_the_instruments_real_tick():
    """2,437 SL-M placements were rejected outright in July for assuming the 0.05 grid. Dhan
    publishes the real value as `SEM_TICK_SIZE` in its scrip master; an unsnapped trigger is
    rejected, and a rejected protective stop is an open position with no backstop."""
    v, _, t = _venue(tick_source=lambda sym, exch: 0.10 if sym == "LT" else 0.05)
    v.place_protective_stop(ProtectiveStopKind.RESTING_STOP, tradingsymbol="LT",
                            exchange="NSE_EQ", qty=1, trigger_price=3456.07)
    assert t.calls[-1][2]["triggerPrice"] == 3456.10, "trigger not snapped to LT's 0.10 grid"


def test_a_missing_tick_source_falls_back_to_the_standard_grid_and_says_so():
    """The fallback is a known compromise, not a good answer — correct for most NSE equity and
    wrong for LT and MARUTI. It is pinned here so that a venue declaring execution without a
    tick source is a visible decision rather than an accident."""
    v, c, _ = _venue()
    assert c.tick_size("LT", "NSE_EQ") == 0.05


# ── attribution must survive the second broker ────────────────────────────

def test_the_intent_tag_travels_as_correlation_id():
    """Execution attribution is carried scan-to-fill by the broker tag. Dhan's `correlationId`
    is 30 chars and our durable intent tag is 20, so it fits — which is what keeps attribution
    working across brokers rather than degrading to "Kite only"."""
    v, _, t = _venue()
    v.place(OrderRequest("DLF", "NSE_EQ", "BUY", 10, "MARKET", tag="pt-a1b2c3d4e5f6a7b8"))
    assert t.calls[-1][2]["correlationId"] == "pt-a1b2c3d4e5f6a7b8"


def test_an_over_long_tag_is_refused_rather_than_truncated():
    """A truncated tag is an order nobody can attribute, and the truncation is silent."""
    v, _, _ = _venue()
    with pytest.raises(DhanOrderRejected):
        v.place(OrderRequest("DLF", "NSE_EQ", "BUY", 10, "MARKET", tag="x" * 31))


# ── inventory and reads ───────────────────────────────────────────────────

def test_the_inventory_is_normalised_and_a_filled_stop_is_dead():
    v, _, t = _venue()
    t.book = [
        {"orderId": "DH-9", "tradingSymbol": "DLF", "exchangeSegment": "NSE_EQ",
         "transactionType": "SELL", "quantity": 10, "triggerPrice": 99.0,
         "orderStatus": "PENDING", "correlationId": "pt-bot"},
        {"orderId": "DH-8", "tradingSymbol": "DLF", "exchangeSegment": "NSE_EQ",
         "transactionType": "SELL", "quantity": 10, "triggerPrice": 99.0,
         "orderStatus": "TRADED", "correlationId": "pt-bot"},
    ]
    rows = v.protective_inventory(ProtectiveStopKind.RESTING_STOP)
    assert {r["id"]: r["status"] for r in rows} == {"DH-9": "live", "DH-8": "dead"}
    assert rows[0]["side"] == "SELL" and rows[0]["qty"] == 10


def test_an_unreadable_inventory_raises_rather_than_reporting_empty():
    """`[]` is read by callers as "no exchange-side stop exists" and licenses placing one.
    Doing that when the truth is "we could not look" doubles the protective order."""
    class Blind:
        product = "MARGIN"
        orders = None

    with pytest.raises(NotImplementedError):
        DhanVenue(Blind()).protective_inventory(ProtectiveStopKind.RESTING_STOP)


def test_find_fill_reads_the_order_book_because_dhan_documents_no_trade_book():
    v, _, t = _venue()
    t.book = [{"orderId": "DH-3", "tradingSymbol": "DLF", "transactionType": "SELL",
               "orderStatus": "TRADED", "filledQty": 10, "averageTradedPrice": 101.5}]
    assert v.find_fill("DLF", side="SELL") == {"avg_price": 101.5, "filled_qty": 10}
    assert v.find_fill("DLF", side="BUY") is None


def test_margin_fails_closed_to_zero():
    """Sizing must fail CLOSED — an unanswerable probe means no deployable cash, never a
    fallback to an assumed leverage figure."""
    class NoAnswer(FakeDhanTransport):
        def post(self, path, body):
            raise RuntimeError("margin service down")

    c = DhanOrderClient(NoAnswer(), lambda: "1")
    assert DhanVenue(c).margin_probe(OrderRequest("DLF", "NSE_EQ", "BUY", 10, "MARKET")) == 0.0


def test_funds_preserves_dhans_own_spelling():
    """Dhan's field is `availabelBalance`. Correcting the typo reads nothing and returns zero
    deployable cash — sizing then fails closed for entirely the wrong reason, which is the
    hardest kind of bug to find because the safe outcome hides the cause."""
    v, _, _ = _venue()
    assert "availabelBalance" in v.funds()


# ── modify and cancel use the documented verbs ────────────────────────────

def test_modify_is_a_put_and_cancel_is_a_delete():
    """Documented: `PUT /orders/{id}` and `DELETE /orders/{id}`. Kite uses POSTs to action
    paths; assuming the same shape here returns 404 or 405, and a failed protective-stop cancel
    means the caller must NOT send a closing order."""
    v, _, t = _venue()
    v.modify_protective_stop(ProtectiveStopKind.RESTING_STOP, "DH-1", tradingsymbol="DLF",
                             exchange="NSE_EQ", qty=10, trigger_price=98.0)
    assert t.calls[-1][0] == "PUT" and t.calls[-1][1] == "/orders/DH-1"
    v.cancel_protective_stop(ProtectiveStopKind.RESTING_STOP, "DH-1")
    assert t.calls[-1][0] == "DELETE" and t.calls[-1][1] == "/orders/DH-1"


# ── the registry can now BUILD a Dhan live path ───────────────────────────

def test_the_registry_builds_a_dhan_venue_from_a_connection():
    """`make_broker` no longer names a broker. It asks the registry to build the live path, so
    adding a broker is a registry row plus a builder rather than an edit to the one function
    that decides whether real orders go out."""
    from app.core.config import get_settings
    from app.providers.brokers import build_live_venue
    from app.providers.connection import Connection

    conn = Connection(broker="dhan", scope="dhan:main",
                      capabilities=frozenset({"live_execution", "market_orders"}),
                      token_source=lambda: "TOK",
                      secrets_source=lambda: {"access_token": "TOK", "client_id": "1000000001"})
    client, venue = build_live_venue(conn, get_settings())
    assert isinstance(venue, DhanVenue)
    assert client is venue.client


def test_the_dhan_builder_reads_the_client_id_from_the_bundle_not_the_token():
    """Dhan needs `client-id` on every request AND `dhanClientId` in every order body. A token
    without it authenticates nothing, so it comes from the credential bundle rather than being
    assumed — and its absence is refused at the transport, naming the field."""
    from app.core.config import get_settings
    from app.providers.base import ProviderReadError
    from app.providers.brokers import build_live_venue
    from app.providers.connection import Connection

    conn = Connection(broker="dhan", scope="dhan:main",
                      capabilities=frozenset({"live_execution"}),
                      token_source=lambda: "TOK",
                      secrets_source=lambda: {"access_token": "TOK"})   # no client_id
    client, _ = build_live_venue(conn, get_settings())
    with pytest.raises(ProviderReadError) as e:
        client.transport.post("/orders", {}, allow_list=True)
    assert "client id" in str(e.value)


def test_a_broker_with_no_builder_is_refused_by_the_registry():
    """The refusal that replaced `conn.broker != "kite"`. Same guarantee, now a lookup."""
    from app.core.config import get_settings
    from app.providers.brokers import BrokerNotSupported, build_live_venue
    from app.providers.connection import Connection

    conn = Connection(broker="upstox", scope="upstox:x",
                      capabilities=frozenset({"live_execution"}),
                      token_source=lambda: "TOK")
    with pytest.raises(BrokerNotSupported) as e:
        build_live_venue(conn, get_settings())
    assert "no order client" in str(e.value)
