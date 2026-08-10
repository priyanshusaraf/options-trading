"""
`LiveBroker` must not speak Kite's protective-stop dialect.

The seam (`app/engine/venue.py`) and its Kite translation (`app/engine/kite_venue.py`)
existed for weeks with **no caller** — the unconsumed-mechanism shape this codebase has
shipped three times. Wiring it is only half the fix: without a guard, the next protective
stop added to the broker is written the old way, the boundary silently regrows, and a
second venue is once again unreachable.

So this file asserts two things a reading of the code cannot:

  1. the six Kite verbs are absent from `live_broker.py`'s executable lines, and
  2. the broker actually dispatches to the venue — a broker that imported nothing but
     also called nothing would pass (1) trivially.

Scope, stated so a green run here is not misread as "the boundary is finished": the
*plain-order* verbs (`place` / `status` / `cancel` / `orders` / `find_fill`) are already
neutral by name and still go direct to the client, the entry pre-flight still reads raw
`orders()` / `gtts()` dumps, and `exchange_for_segment` / `product_for_segment` still put
Kite exchange and product strings into `OrderRequest`. Those are named in
`kite_venue.py`'s docstring as the next slice and are deliberately NOT guarded here.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from app.engine.broker_protocol import ProtectiveStopKind

LIVE_BROKER = pathlib.Path(__file__).resolve().parents[1] / "app" / "engine" / "live_broker.py"

#: Kite's spellings. Each is a method on `KiteOrderClient` and on nothing else; a second
#: broker's client answers to none of them.
KITE_VERBS = frozenset({
    "place_stop_gtt", "place_stop_order",
    "modify_stop_gtt", "modify_stop_order",
    "delete_gtt", "gtt_status",
})


def _attribute_names(source: str) -> set[str]:
    """Every attribute accessed anywhere in the module — parsed, not grepped.

    A regex over the text would also match the docstrings and log strings that
    legitimately still say "GTT" and "SL-M" (the operator reads those messages on their
    phone; renaming them would cost more than it buys). The AST sees only real accesses,
    which is exactly the distinction the guard is about.
    """
    tree = ast.parse(source)
    return {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}


def test_the_live_broker_does_not_call_kite_protective_stop_verbs():
    leaked = sorted(KITE_VERBS & _attribute_names(LIVE_BROKER.read_text()))
    assert not leaked, (
        f"live_broker.py calls Kite-only verb(s) {leaked}. Protective stops go through "
        f"`self.venue.place/modify/cancel_protective_stop` with a ProtectiveStopKind; "
        f"the venue owns the spelling. A second broker's client has no {leaked[0]!r}."
    )


def test_the_names_this_guard_watches_are_real_kite_verbs():
    """Guard the guard. If `KiteOrderClient` renames a verb, the set above silently
    stops watching anything and this file passes forever while the leak is wide open —
    the vacuous shape where the assertion is right and the cause has evaporated."""
    from app.engine.kite_order_client import KiteOrderClient
    missing = sorted(v for v in KITE_VERBS if not callable(getattr(KiteOrderClient, v, None)))
    assert not missing, (
        f"{missing} are no longer methods of KiteOrderClient, so watching for them "
        f"proves nothing. Update KITE_VERBS to the current spellings."
    )


# ── the broker really dispatches to the venue ─────────────────────────────


class _RecordingVenue:
    """Records the neutral calls and fails loudly on anything Kite-shaped."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def place_protective_stop(self, kind, **kw) -> str:
        self.calls.append(("place", kind, kw))
        return "PROT-1"

    def modify_protective_stop(self, kind, protective_id, **kw):
        self.calls.append(("modify", kind, protective_id, kw))

    def cancel_protective_stop(self, kind, protective_id):
        self.calls.append(("cancel", kind, protective_id))

    def protective_stop_state(self, kind, protective_id) -> dict:
        self.calls.append(("state", kind, protective_id))
        return {"triggered": True}

    def protective_inventory(self, kind) -> list[dict]:
        self.calls.append(("inventory", kind))
        return []

    # Deliberately NOT Kite's answers — a venue is free to name its own exchanges and
    # products, and a broker that hardcoded Kite's would show up here as a mismatch.
    def exchange_for(self, charge_segment: str) -> str:
        return f"X:{charge_segment}"

    def product_for(self, tenor) -> str:
        return f"P:{tenor.value}"

    def tick_size(self, tradingsymbol: str, exchange: str | None = None) -> float:
        return 0.05


class _ExplodingClient:
    """Any Kite verb reaching the client is a routing failure, so it raises rather
    than returning something plausible — a silent fallback is what we are testing for."""

    def __getattr__(self, name):
        if name in KITE_VERBS:
            def boom(*a, **k):
                raise AssertionError(f"LiveBroker reached the Kite client for {name!r}")
            return boom
        raise AttributeError(name)


@pytest.fixture()
def broker_and_venue():
    from app.db.session import init_db
    from app.engine.live_broker import LiveBroker
    from app.providers.mock import MockProvider
    init_db(reset=True)
    venue = _RecordingVenue()
    return LiveBroker(MockProvider(), _ExplodingClient(), venue=venue), venue


def _position(segment: str, *, direction: str = "LONG", protective_id=None):
    class P:
        id = 1
        tradingsymbol = "TESTSYM"
        instrument_key = "NSE:TESTSYM"
        exchange = "NSE_INTRADAY" if segment == "equity_intraday" else "NFO"
        qty = 10
        stop_price = 100.0
        entry_premium = 110.0
        last_premium = 110.0
        gtt_trigger_id = protective_id
    P.segment = segment
    P.direction = direction
    return P()


def test_a_server_trigger_stop_is_placed_through_the_venue(broker_and_venue, monkeypatch):
    b, venue = broker_and_venue
    monkeypatch.setattr(b, "_gtt_enabled", lambda: True)
    monkeypatch.setattr(b.s, "commit", lambda: None)
    b._place_gtt(_position("options"), 110.0)
    kinds = [(c[0], c[1]) for c in venue.calls]
    assert ("place", ProtectiveStopKind.SERVER_TRIGGER) in kinds, venue.calls


def test_a_resting_stop_is_placed_through_the_venue(broker_and_venue, monkeypatch):
    b, venue = broker_and_venue
    monkeypatch.setattr(b, "_gtt_enabled", lambda: True)
    monkeypatch.setattr(b.s, "commit", lambda: None)
    monkeypatch.setattr(b, "_journal_stop", lambda *a, **k: None)
    b._place_equity_stop(_position("equity_intraday"), 110.0)
    kinds = [(c[0], c[1]) for c in venue.calls]
    assert ("place", ProtectiveStopKind.RESTING_STOP) in kinds, venue.calls


def test_each_cancel_carries_the_kind_that_picks_the_endpoint(broker_and_venue):
    """A resting SL-M is cancelled as an order, a GTT through the GTT endpoint. Sending
    either to the other's endpoint is rejected by Kite — which is the whole reason the
    kind is carried rather than inferred at the wire."""
    b, venue = broker_and_venue
    assert b._cancel_equity_stop("OID-9", "TESTSYM") is True
    assert b._cancel_gtt("TID-9", "TESTSYM") is True
    assert venue.calls == [
        ("cancel", ProtectiveStopKind.RESTING_STOP, "OID-9"),
        ("cancel", ProtectiveStopKind.SERVER_TRIGGER, "TID-9"),
    ]


def test_the_exchange_on_the_wire_is_the_venues_not_the_brokers(broker_and_venue, monkeypatch):
    """The broker classifies by charge-segment; only the venue turns that into an
    exchange code. The recording venue answers `X:NFO`, which no Kite mapping produces —
    so a broker that still computed `NSE`/`NFO` itself fails here rather than passing by
    coincidence, which is what a Kite-shaped fake would have allowed."""
    b, venue = broker_and_venue
    monkeypatch.setattr(b, "_gtt_enabled", lambda: True)
    monkeypatch.setattr(b.s, "commit", lambda: None)
    b._place_gtt(_position("options"), 110.0)
    place = next(c for c in venue.calls if c[0] == "place")
    assert place[2]["exchange"] == "X:NFO", place


def test_the_protection_inventory_is_read_through_the_venue(broker_and_venue):
    """`_protection_inventory` used to read the raw `gtts()` / `orders()` dumps and
    filter them on Kite's own field names. The exploding client has neither method, so
    reaching past the venue raises rather than quietly returning nothing."""
    b, venue = broker_and_venue
    state, all_ids, exact = b._protection_inventory(_position("options"))
    assert (state, all_ids, exact) == ("ok", set(), set())
    assert ("inventory", ProtectiveStopKind.SERVER_TRIGGER) in venue.calls


def test_an_unreadable_inventory_is_ambiguous_not_empty(broker_and_venue, monkeypatch):
    """The distinction the whole reconciliation rests on. Empty means "this position has
    no exchange-side stop" and licenses placing one; ambiguous means "we could not look"
    and must not. A venue that cannot answer must produce the second."""
    b, venue = broker_and_venue

    def blow_up(kind):
        raise RuntimeError("inventory unreachable")

    monkeypatch.setattr(venue, "protective_inventory", blow_up)
    assert b._protection_inventory(_position("options"))[0] == "ambiguous"


def test_the_fired_check_reads_venue_state_not_a_kite_probe(broker_and_venue):
    b, venue = broker_and_venue
    assert b._gtt_fired("TID-1", "TESTSYM") is True
    assert venue.calls == [("state", ProtectiveStopKind.SERVER_TRIGGER, "TID-1")]


def test_an_unreadable_venue_still_answers_not_fired(broker_and_venue, monkeypatch):
    """The conservative fallback survives the re-route. False means "assume the close was
    external", which keeps the safe re-entry block; a True guessed from a failed read
    would let the bot re-enter a contract whose stop may still be resting."""
    b, venue = broker_and_venue

    def blow_up(kind, protective_id):
        raise RuntimeError("venue unreachable")

    monkeypatch.setattr(venue, "protective_stop_state", blow_up)
    assert b._gtt_fired("TID-1", "TESTSYM") is False
