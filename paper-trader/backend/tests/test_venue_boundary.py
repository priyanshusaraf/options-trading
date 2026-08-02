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

    def modify_stop_order(self, oid, trigger, sym=None, exch=None):
        self.calls.append(("modify_stop_order", oid, trigger, sym, exch)); return True

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
    assert c.calls[-1] == ("modify_stop_order", "SLM-1", 3600.0, "LT", "NSE")


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
