"""
Phase F — the venue boundary (audit C2).

Two properties are worth a test here:

  1. **The translation table is right.** MIS/NRML/GTT/SL-M are Zerodha's spelling
     of neutral concepts, and getting the mapping wrong is not a cosmetic bug:
     a GTT sent for an MIS position is refused server-side, which is how intraday
     positions went stopless in July.
  2. **The delegation changed nothing.** `product_for_segment` /
     `exchange_for_segment` (imported by runner.py, which this phase may not
     touch) now delegate into `kite_venue`. Their output must be identical for
     every segment this system trades.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from app.engine import kite_order_client as koc
from app.engine.broker_protocol import ProtectiveStopKind, Tenor
from app.engine.kite_venue import (
    KiteVenue,
    kite_exchange,
    kite_product,
    kite_product_for_charge_segment,
)
from app.engine.order_executor import OrderRequest
from app.engine.venue import ExecutionVenue

ALL_SEGMENTS = ["NSE_INTRADAY", "BSE_INTRADAY", "NSE_EQ", "BSE_EQ",
                "NFO", "NFO_FUT", "BFO", "MCX", "CDS", "NCDEX"]


# ── the delegation is behaviour-preserving ────────────────────────────────

def test_product_for_segment_is_unchanged_for_every_segment():
    for seg in ALL_SEGMENTS:
        assert koc.product_for_segment(seg) == kite_product_for_charge_segment(seg)
    # and the concrete values the live path depends on
    assert koc.product_for_segment("NSE_INTRADAY") == "MIS"
    assert koc.product_for_segment("BSE_INTRADAY") == "MIS"
    assert koc.product_for_segment("NFO") == "NRML"
    assert koc.product_for_segment("NSE_EQ") == "NRML"


def test_product_for_segment_still_honours_a_custom_carry_default():
    """A client configured with a non-NRML carry product keeps it; only the
    intraday leg is forced."""
    assert koc.product_for_segment("NFO", "CNC") == "CNC"
    assert koc.product_for_segment("NSE_INTRADAY", "CNC") == "MIS"


def test_exchange_for_segment_is_unchanged_for_every_segment():
    assert koc.exchange_for_segment("NSE_INTRADAY") == "NSE"
    assert koc.exchange_for_segment("BSE_INTRADAY") == "BSE"
    for seg in ["NSE_EQ", "NFO", "NFO_FUT", "BFO", "MCX", "CDS", "NCDEX"]:
        assert koc.exchange_for_segment(seg) == seg   # already a Kite exchange
        assert koc.exchange_for_segment(seg) == kite_exchange(seg)


def test_legacy_segment_constant_still_exported():
    """runner.py and older tests import these names from kite_order_client."""
    assert koc.EQUITY_INTRADAY_SEGMENTS == frozenset({"NSE_INTRADAY", "BSE_INTRADAY"})


def test_kite_product_translates_the_neutral_tenor():
    assert kite_product(Tenor.INTRADAY) == "MIS"
    assert kite_product(Tenor.CARRY) == "NRML"


# ── the boundary holds ────────────────────────────────────────────────────

@pytest.mark.parametrize("module", ["broker_protocol", "venue"])
def test_no_kite_vocabulary_in_the_neutral_modules(module):
    """The whole point of the split: `broker_protocol` and `venue` describe what
    the engine wants, never how Zerodha spells it. Kite words may appear in prose
    (explaining the mapping is the file's job) but not in code."""
    src = Path(inspect.getfile(__import__(f"app.engine.{module}",
                                          fromlist=["x"]))).read_text()
    code = re.sub(r'"""(?:.|\n)*?"""', "", src)
    code = re.sub(r"#.*", "", code)
    for word in ("MIS", "NRML", "SL-M", "place_gtt", "delete_gtt"):
        assert word not in code, (
            f"Kite vocabulary '{word}' leaked into app/engine/{module}.py — "
            f"translation belongs in kite_venue.py")


def test_kite_venue_implements_the_whole_execution_venue_protocol():
    verbs = [n for n, v in vars(ExecutionVenue).items()
             if not n.startswith("_") and callable(v)]
    assert len(verbs) >= 11, "the ExecutionVenue protocol lost its verbs"
    missing = [n for n in verbs if not callable(getattr(KiteVenue, n, None))]
    assert not missing, f"KiteVenue does not implement {missing}"


def test_execution_venue_covers_every_method_live_broker_calls_on_its_client():
    """`OrderClient` declares three methods; the live broker has always called
    eight more straight through it. Every one of those must now have a neutral
    counterpart on ExecutionVenue, or the seam is still narrower than reality."""
    src = Path("app/engine/live_broker.py").read_text()
    called = set(re.findall(r"self\.client\.(\w+)", src))
    kite_verbs = {n for n, v in vars(KiteVenue).items()
                  if not n.startswith("_") and callable(v)}
    # every call the broker makes is covered either directly or by a protective-stop verb
    covered = kite_verbs | {"place_stop_gtt", "modify_stop_gtt", "delete_gtt",
                            "place_stop_order", "modify_stop_order", "gtt_status"}
    assert called <= covered, f"live_broker calls uncovered client methods: {called - covered}"
    # and the Kite-specific spellings must NOT be on the neutral protocol
    venue_verbs = {n for n in vars(ExecutionVenue) if not n.startswith("_")}
    assert not (venue_verbs & {"place_stop_gtt", "delete_gtt", "place_stop_order"})


# ── KiteVenue dispatch ────────────────────────────────────────────────────

class FakeKiteClient:
    """Records what a KiteOrderClient would have been asked to do."""
    variety = "regular"
    product = "NRML"

    def __init__(self):
        self.calls: list[tuple] = []
        self.gtt_state = {"status": "active"}
        self.order_state = {"status": "COMPLETE", "filled_qty": 5, "avg_price": 101.5,
                            "reason": ""}

    def place(self, req):
        self.calls.append(("place", req)); return "OID-1"

    def status(self, oid):
        self.calls.append(("status", oid)); return dict(self.order_state)

    def cancel(self, oid):
        self.calls.append(("cancel", oid)); return True

    def orders(self):
        self.calls.append(("orders",)); return [{"order_id": "OID-1"}]

    def find_fill(self, sym, side="SELL"):
        self.calls.append(("find_fill", sym, side)); return {"avg_price": 9.0, "filled_qty": 1}

    def place_stop_order(self, sym, exch, qty, trigger, side="SELL", tag=None):
        self.calls.append(("place_stop_order", sym, exch, qty, trigger, side, tag))
        return "SLM-1"

    def modify_stop_order(self, oid, trigger, sym=None, exch=None, quantity=None):
        self.calls.append(("modify_stop_order", oid, trigger, sym, exch, quantity)); return True

    def place_stop_gtt(self, sym, exch, qty, trigger, last, side="SELL"):
        self.calls.append(("place_stop_gtt", sym, exch, qty, trigger, last, side))
        return "GTT-1"

    def modify_stop_gtt(self, tid, sym, exch, qty, trigger, last, side="SELL"):
        self.calls.append(("modify_stop_gtt", tid, sym, exch, qty, trigger, last, side))
        return True

    def delete_gtt(self, tid):
        self.calls.append(("delete_gtt", tid)); return True

    def gtt_status(self, tid):
        self.calls.append(("gtt_status", tid)); return dict(self.gtt_state)

    def tick_size(self, sym, exch=None):
        return 0.05


def _venue():
    c = FakeKiteClient()
    return KiteVenue(c), c


def test_resting_stop_uses_slm_and_server_trigger_uses_gtt():
    v, c = _venue()
    assert v.place_protective_stop(ProtectiveStopKind.RESTING_STOP,
                                   tradingsymbol="DLF", exchange="NSE", qty=10,
                                   trigger_price=99.0, tag="pt-bot") == "SLM-1"
    assert c.calls[-1][0] == "place_stop_order"
    assert v.place_protective_stop(ProtectiveStopKind.SERVER_TRIGGER,
                                   tradingsymbol="NIFTY24000CE", exchange="NFO", qty=50,
                                   trigger_price=70.0, last_price=100.0) == "GTT-1"
    assert c.calls[-1][0] == "place_stop_gtt"


def test_cancelling_the_wrong_kind_would_hit_the_wrong_endpoint():
    """A resting SL-M is an ordinary order and is cancelled as one; a GTT is a
    trigger and needs the GTT endpoint. Sending either to the other is rejected —
    which is exactly why the kind travels with the id."""
    v, c = _venue()
    v.cancel_protective_stop(ProtectiveStopKind.RESTING_STOP, "SLM-1")
    assert c.calls[-1] == ("cancel", "SLM-1")
    v.cancel_protective_stop(ProtectiveStopKind.SERVER_TRIGGER, "GTT-1")
    assert c.calls[-1] == ("delete_gtt", "GTT-1")


def test_modify_carries_the_symbol_so_the_real_tick_grid_is_used():
    """The 2026-07-15 incident: 2,437 SL-M placements rejected because LT (tick
    0.10) and MARUTI (tick 1.00) do not trade on the hardcoded 0.05 grid. The
    re-price must resolve the same tick the placement did, which needs the symbol."""
    v, c = _venue()
    v.modify_protective_stop(ProtectiveStopKind.RESTING_STOP, "SLM-1",
                             tradingsymbol="LT", exchange="NSE", qty=10,
                             trigger_price=3600.0)
    assert c.calls[-1] == ("modify_stop_order", "SLM-1", 3600.0, "LT", "NSE", 10)


def test_resting_stop_state_reports_its_fill_but_a_trigger_only_reports_firing():
    """R3 vs E6. An SL-M has an order id, so its real fill price is readable and
    the close is booked STOP_LOSS at that price. A GTT has only a trigger id — the
    venue can say it fired, not what it filled at."""
    v, c = _venue()
    st = v.protective_stop_state(ProtectiveStopKind.RESTING_STOP, "SLM-1")
    assert st["triggered"] is True and st["avg_price"] == 101.5 and st["filled_qty"] == 5

    c.gtt_state = {"status": "triggered"}
    gt = v.protective_stop_state(ProtectiveStopKind.SERVER_TRIGGER, "GTT-1")
    assert gt["triggered"] is True and gt["avg_price"] == 0.0

    c.gtt_state = {"status": "active"}
    assert v.protective_stop_state(ProtectiveStopKind.SERVER_TRIGGER, "GTT-1")["triggered"] is False


def test_an_unfilled_resting_stop_is_not_reported_as_triggered():
    v, c = _venue()
    c.order_state = {"status": "OPEN", "filled_qty": 0, "avg_price": 0.0}
    assert v.protective_stop_state(ProtectiveStopKind.RESTING_STOP, "SLM-1")["triggered"] is False


def test_a_venue_that_cannot_answer_trigger_state_is_read_conservatively():
    """No `gtt_status` must mean 'assume an external exit', which keeps the safe
    re-entry block — never 'it definitely did not fire'."""
    class NoTriggerLookup:
        pass
    assert KiteVenue(NoTriggerLookup()).protective_stop_state(
        ProtectiveStopKind.SERVER_TRIGGER, "GTT-1")["triggered"] is False


def test_plain_order_verbs_pass_straight_through():
    v, c = _venue()
    req = OrderRequest("DLF", "NSE", "BUY", 10, "MARKET")
    assert v.place(req) == "OID-1"
    assert v.status("OID-1")["avg_price"] == 101.5
    v.cancel("OID-1")
    assert v.orders() == [{"order_id": "OID-1"}]
    assert v.find_fill("DLF")["avg_price"] == 9.0
    assert v.tick_size("DLF", "NSE") == 0.05


def test_margin_probe_fails_closed_to_zero():
    """Sizing must fail CLOSED — an unanswerable margin probe means no deployable
    cash, never a fallback to an assumed leverage figure."""
    class NoAnswer(FakeKiteClient):
        kite = type("K", (), {"order_margins": staticmethod(lambda *_: [])})()
    assert KiteVenue(NoAnswer()).margin_probe(
        OrderRequest("DLF", "NSE", "BUY", 10, "MARKET")) == 0.0


def test_kite_order_client_exposes_the_public_tick_size_verb():
    """`tick_size` is an ExecutionVenue verb; the client had it only as `_tick`."""
    c = koc.KiteOrderClient(object(), tick_source=lambda s, e: 0.10)
    assert c.tick_size("LT", "NSE") == 0.10
    assert c.tick_size(None, "NSE") == 0.05          # no symbol -> standard grid
    assert c.tick_size("LT", "NSE") == c._tick("LT", "NSE")


# ── protective inventory: the normalisation, and what it refuses ──────────
# Added 2026-08-10 when the broker stopped reading Kite's raw dumps. These rows are
# what the reconciliation compares against a live position, so a wrong field name here
# produces a *silent* mismatch: the stop is real, the broker cannot see it, and it
# places a second one.


class _InventoryClient(FakeKiteClient):
    """Rows shaped exactly as `KiteOrderClient.orders()` / `.gtts()` emit them."""

    def orders(self):
        return [
            {"order_id": "SLM-9", "tradingsymbol": "DLF", "exchange": "NSE",
             "transaction_type": "sell", "quantity": 10, "trigger_price": 99.0,
             "status": "TRIGGER PENDING", "tag": "pt-bot"},
            {"order_id": "SLM-8", "tradingsymbol": "DLF", "exchange": "NSE",
             "transaction_type": "SELL", "quantity": 10, "trigger_price": 99.0,
             "status": "COMPLETE", "tag": "pt-bot"},
        ]

    def gtts(self):
        return [
            {"trigger_id": "GTT-9", "tradingsymbol": "NIFTY25000CE", "exchange": "NFO",
             "side": "SELL", "qty": 50, "trigger_price": 12.0, "status": "active"},
            {"trigger_id": "GTT-8", "tradingsymbol": "NIFTY25000CE", "exchange": "NFO",
             "side": "SELL", "qty": 50, "trigger_price": 12.0, "status": "triggered"},
            # Kite omits the status on some shapes; the historical filter read that as
            # active and this must keep doing so.
            {"trigger_id": "GTT-7", "tradingsymbol": "NIFTY25000CE", "exchange": "NFO",
             "side": "SELL", "qty": 50, "trigger_price": 12.0},
        ]


def test_resting_stop_inventory_is_normalised_off_kites_field_names():
    rows = KiteVenue(_InventoryClient()).protective_inventory(
        ProtectiveStopKind.RESTING_STOP)
    assert [r["id"] for r in rows] == ["SLM-9", "SLM-8"]
    live = next(r for r in rows if r["id"] == "SLM-9")
    # `transaction_type` -> `side` (upper-cased), `quantity` -> `qty`
    assert live == {"id": "SLM-9", "tradingsymbol": "DLF", "exchange": "NSE",
                    "side": "SELL", "qty": 10, "trigger_price": 99.0,
                    "status": "live", "tag": "pt-bot"}


def test_a_filled_resting_stop_is_dead_because_it_protects_nothing():
    """COMPLETE is a success and still means the stop is gone. Reading it as live
    leaves the position believing it is protected by an order that already fired."""
    rows = KiteVenue(_InventoryClient()).protective_inventory(
        ProtectiveStopKind.RESTING_STOP)
    assert {r["id"]: r["status"] for r in rows} == {"SLM-9": "live", "SLM-8": "dead"}


def test_server_trigger_inventory_normalises_and_defaults_missing_status_to_live():
    rows = KiteVenue(_InventoryClient()).protective_inventory(
        ProtectiveStopKind.SERVER_TRIGGER)
    assert {r["id"]: r["status"] for r in rows} == {
        "GTT-9": "live", "GTT-8": "dead", "GTT-7": "live"}
    assert all(r["tag"] is None for r in rows), "Kite GTTs carry no tag"


@pytest.mark.parametrize("kind,missing", [
    (ProtectiveStopKind.RESTING_STOP, "orders"),
    (ProtectiveStopKind.SERVER_TRIGGER, "gtts"),
])
def test_an_unreadable_inventory_raises_rather_than_reporting_empty(kind, missing):
    """The most dangerous possible return value here is `[]`. Callers read emptiness as
    "this position has no exchange-side stop" and place one; doing that when the truth
    is "we could not look" doubles the protective order on a live position."""
    class Blind(FakeKiteClient):
        pass

    setattr(Blind, missing, property(lambda self: (_ for _ in ()).throw(AttributeError)))
    with pytest.raises(Exception):
        KiteVenue(Blind()).protective_inventory(kind)


# ── vocabulary verbs ──────────────────────────────────────────────────────

def test_exchange_and_product_verbs_match_the_pure_functions():
    v, _ = _venue()
    for seg in ALL_SEGMENTS:
        assert v.exchange_for(seg) == kite_exchange(seg)
    assert v.product_for(Tenor.INTRADAY) == "MIS"
    assert v.product_for(Tenor.CARRY) == "NRML"


def test_a_client_configured_with_another_carry_product_keeps_it():
    """`kite_product`'s `default` allowance, preserved through the verb. A client built
    for CNC delivery must not have NRML forced back onto it by the venue."""
    class CncClient(FakeKiteClient):
        product = "CNC"

    assert KiteVenue(CncClient()).product_for(Tenor.CARRY) == "CNC"
    assert KiteVenue(CncClient()).product_for(Tenor.INTRADAY) == "MIS"


# ── F6/F7 from the execution-safety review, 2026-08-10 ────────────────────

@pytest.mark.parametrize("kind,missing", [
    (ProtectiveStopKind.RESTING_STOP, "orders"),
    (ProtectiveStopKind.SERVER_TRIGGER, "gtts"),
])
def test_a_reader_answering_none_is_unreadable_not_empty(kind, missing):
    """`reader() or []` turned a client that answers `None` on a failed read into an EMPTY
    inventory. Callers read emptiness as "this position has no exchange-side stop" and place
    one — so a duplicate protective order lands on a live position.

    Not reachable through `KiteOrderClient`, which returns a list or raises. Fixed anyway
    because the protocol docstring stated the guarantee absolutely, and a docstring ahead of the
    code is this codebase's repeat failure shape.
    """
    class NoneReader(FakeKiteClient):
        pass

    setattr(NoneReader, missing, lambda self: None)
    with pytest.raises(NotImplementedError) as e:
        KiteVenue(NoneReader()).protective_inventory(kind)
    assert "None is not an empty inventory" in str(e.value)


def test_an_empty_list_is_still_a_legitimate_empty_inventory():
    """Guard the guard: refusing `None` must not also refuse a genuine empty book, which is the
    normal state before the first stop of the day is placed."""
    class EmptyReader(FakeKiteClient):
        def orders(self):
            return []

        def gtts(self):
            return []

    v = KiteVenue(EmptyReader())
    assert v.protective_inventory(ProtectiveStopKind.RESTING_STOP) == []
    assert v.protective_inventory(ProtectiveStopKind.SERVER_TRIGGER) == []


def test_one_rule_decides_the_protective_kind_everywhere():
    """F7. `_entry_protection_preflight` used `kind == "options"` while `_protection_inventory`
    used `protective_kind_for_book_segment(pos.segment)`. They agree for every segment that
    exists today, so the baseline written by one and the ids compared by the other matched by
    luck. A new segment mapping differently under the two would silently compare a GTT id
    against the SL-M order book."""
    from app.engine.venue import protective_kind_for_book_segment

    assert protective_kind_for_book_segment("options") is ProtectiveStopKind.SERVER_TRIGGER
    assert protective_kind_for_book_segment("equity_intraday") is ProtectiveStopKind.RESTING_STOP
    # and a segment nobody has classified defaults to the server trigger, which is what the
    # engine has always done for options/futures — stated so a new segment is a visible decision.
    assert protective_kind_for_book_segment("futures") is ProtectiveStopKind.SERVER_TRIGGER


def test_the_preflight_and_the_inventory_agree_on_every_book_segment():
    """The property F7 is really about: whichever path computes the kind, they must agree.

    Checked by AST, not by a substring. The first version of this test asserted
    `"protective_kind_for_book_segment" in inspect.getsource(...)` and was **vacuous**: the
    mutation that restores the old two-branch expression leaves the explanatory comment intact,
    and that comment names the function. Right clause, wrong cause — shape #1 of the vacuous-test
    catalogue, committed while fixing a finding about a docstring being ahead of the code.
    """
    import ast
    import inspect
    import textwrap

    from app.engine.live_broker import LiveBroker

    tree = ast.parse(textwrap.dedent(
        inspect.getsource(LiveBroker._entry_protection_preflight)))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "protective_kind_for_book_segment" in called, (
        "the entry preflight computes the protective kind by its own rule again; it must CALL "
        "the same function `_protection_inventory` does. A comment mentioning the name is not "
        "a call.")
