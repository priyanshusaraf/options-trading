"""
Phase F guard tests — audit C2 (no broker abstraction) and H7 (venue semantics
inherited rather than declared).

The one that earns its keep is `test_no_venue_facing_method_is_silently_inherited`.
`LiveBroker` subclasses `PaperBroker`, so every method it does not override runs
the *simulator's* arithmetic on real money. For ledger bookkeeping that is the
intended sharing. For anything that must reach the exchange it is a silent
simulation — and "looks wired, isn't" is the defect class this codebase has
already shipped three times.

Nothing here asserts a docstring. Each test compares the real class dictionaries.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

from app.engine.broker import PaperBroker
from app.engine.broker_protocol import (
    BOOKKEEPING_METHODS,
    KNOWN_UNIMPLEMENTED_VENUE_METHODS,
    VENUE_FACING_METHODS,
    Broker,
    ProtectiveStopKind,
    Tenor,
    clear_protective_order_id,
    protective_order_id,
    set_protective_order_id,
)
from app.engine.live_broker import LiveBroker
from app.engine.venue import (
    protective_kind_for_book_segment,
    tenor_for_charge_segment,
)


# ── the H7 guard ──────────────────────────────────────────────────────────

def test_venue_and_bookkeeping_sets_are_disjoint_and_real():
    """Both sets must name methods that actually exist, and no method may be
    classified as both — otherwise the guard below is checking nothing."""
    assert not (VENUE_FACING_METHODS & BOOKKEEPING_METHODS), (
        "a method cannot be both shared bookkeeping and venue-facing")
    for name in VENUE_FACING_METHODS | BOOKKEEPING_METHODS:
        assert callable(getattr(PaperBroker, name, None)), (
            f"{name} is classified in broker_protocol but does not exist on PaperBroker "
            f"— the classification has drifted from the code")
    assert KNOWN_UNIMPLEMENTED_VENUE_METHODS <= VENUE_FACING_METHODS


def test_no_venue_facing_method_is_silently_inherited():
    """A real-money broker must DEFINE every venue-facing verb, never inherit the
    simulator's version of it."""
    must_define = VENUE_FACING_METHODS - KNOWN_UNIMPLEMENTED_VENUE_METHODS
    inherited = sorted(n for n in must_define if n not in LiveBroker.__dict__)
    assert not inherited, (
        f"LiveBroker INHERITS venue-facing method(s) {inherited} from PaperBroker. "
        f"Those would run simulator arithmetic on the real-money path: a position "
        f"booked with no order behind it, or a stop that exists only in the DB. "
        f"Either implement them on LiveBroker, or — if the gap is deliberate and "
        f"unreachable — add them to KNOWN_UNIMPLEMENTED_VENUE_METHODS with the "
        f"reason, so the hole is declared rather than discovered.")


def test_known_venue_gaps_are_exactly_the_declared_ones():
    """The gap list is a pin, not an escape hatch: it must match reality in BOTH
    directions, so closing a gap without deleting its entry fails too."""
    actual = {n for n in VENUE_FACING_METHODS if n not in LiveBroker.__dict__}
    assert actual == set(KNOWN_UNIMPLEMENTED_VENUE_METHODS), (
        f"declared venue gaps {sorted(KNOWN_UNIMPLEMENTED_VENUE_METHODS)} != actual "
        f"{sorted(actual)}. If you implemented one on LiveBroker, remove it from "
        f"KNOWN_UNIMPLEMENTED_VENUE_METHODS.")


def test_the_futures_gap_is_currently_unreachable_in_live():
    """The declared gap is only tolerable while the segment is switched off.

    `open_futures_position` is wired into the runner but not overridden by
    LiveBroker, so a live futures entry today would book a simulated position with
    no real order behind it. That is survivable ONLY because the segment defaults
    inert. If this assertion ever fails, the gap must be closed before the flag
    flips — not after.
    """
    from app.core.config import get_settings
    assert get_settings().index_futures_enabled is False, (
        "index futures are enabled but LiveBroker still inherits "
        "open_futures_position/close_futures_position from the paper simulator — "
        "a live futures entry would book a phantom position with no order.")


def test_live_broker_does_not_reimplement_ledger_bookkeeping():
    """The other half of the split. Ledger arithmetic is shared ON PURPOSE — a
    live broker with its own copy of `mark`/`snapshot`/`book_partial_close` is how
    the money path diverges between simulator and production, which hard invariant
    4 (live/backtest parity) exists to prevent."""
    overridden = sorted(n for n in BOOKKEEPING_METHODS if n in LiveBroker.__dict__)
    assert not overridden, (
        f"LiveBroker re-implements shared bookkeeping {overridden}. If it genuinely "
        f"needs to, move the name from BOOKKEEPING_METHODS to VENUE_FACING_METHODS "
        f"so every future broker is held to the same requirement.")


# ── the Broker contract ───────────────────────────────────────────────────

def test_both_brokers_satisfy_the_broker_protocol():
    """Structural conformance, checked on the classes so no LiveBroker is ever
    instantiated in a test process (see broker_factory's pytest refusal)."""
    verbs = [n for n, v in vars(Broker).items()
             if not n.startswith("_") and callable(v)]
    assert len(verbs) >= 15, "the Broker protocol lost its verbs"
    for cls in (PaperBroker, LiveBroker):
        missing = [n for n in verbs if not callable(getattr(cls, n, None))]
        assert not missing, f"{cls.__name__} does not satisfy Broker: missing {missing}"
        assert isinstance(getattr(cls, "MODE", None), str)


#: Every method the runner calls positionally or by keyword on whichever broker it built.
_CONTRACT = ("open_position", "open_equity_position", "close_position",
             "close_equity_position", "ensure_stop_protection",
             "update_stop_protection", "reconcile_orphans")
_PAPER_RUNTIME_ONLY_PARAMETERS = frozenset({"runtime_context_json"})


def _paper_shared_parameters(method) -> list[str]:
    return [
        name for name in inspect.signature(method).parameters
        if name not in _PAPER_RUNTIME_ONLY_PARAMETERS
    ]


def test_broker_protocol_signatures_match_the_paper_implementation():
    """A Protocol whose parameter names have drifted from the implementation is a
    lie that type checkers believe. Compare the actual signatures."""
    for name in _CONTRACT:
        proto = list(inspect.signature(getattr(Broker, name)).parameters)
        impl = _paper_shared_parameters(getattr(PaperBroker, name))
        assert proto == impl, (
            f"Broker.{name}{tuple(proto)} does not match "
            f"PaperBroker.{name}{tuple(impl)}")


def test_the_live_broker_accepts_everything_the_paper_broker_does():
    """The gap this closes, found by L1.3C: adding `strategy_key`/`strategy_version` to
    the entry paths updated `PaperBroker` and the Protocol, both of which this file
    checked — and left `LiveBroker` unable to accept the arguments the runner had started
    passing. Every real order would have raised `TypeError` at the fill.

    Checking only the paper implementation is what made that invisible. `LiveBroker`
    overrides these methods to place a real order and then delegates, so its signature is
    a real interface, and it is the one nothing in the suite can exercise end to end.
    """
    from app.engine.live_broker import LiveBroker

    for name in _CONTRACT:
        paper = _paper_shared_parameters(getattr(PaperBroker, name))
        live = list(inspect.signature(getattr(LiveBroker, name)).parameters)
        if getattr(LiveBroker, name) is getattr(PaperBroker, name):
            continue   # inherited unchanged — nothing to drift
        assert live == paper, (
            f"LiveBroker.{name}{tuple(live)} does not exactly match the shared "
            f"PaperBroker parameters {tuple(paper)}")


def test_runtime_context_is_concrete_paper_runtime_authority_not_shared_broker_api():
    root = Path(__file__).resolve().parents[1]
    runner_source = (root / "app/engine/runner.py").read_text()
    live_source = (root / "app/engine/live_broker.py").read_text()
    protocol_source = (root / "app/engine/broker_protocol.py").read_text()
    paper_service_source = (root / "app/paper_runtime/service.py").read_text()
    assert "runtime_context_json" not in runner_source
    assert "runtime_context_json" not in live_source
    assert "runtime_context_json" not in protocol_source
    assert paper_service_source.count("runtime_context_json=context_json") == 1
    for cls in (Broker, LiveBroker):
        for name, value in vars(cls).items():
            if callable(value):
                assert "runtime_context_json" not in inspect.signature(value).parameters, (
                    f"{cls.__name__}.{name} exposes paper-only runtime context")
    paper_methods = {
        name for name, value in vars(PaperBroker).items()
        if callable(value)
        and "runtime_context_json" in inspect.signature(value).parameters
    }
    assert paper_methods == {
        "_prepare_paper_entry_intent", "open_position", "open_equity_position",
        "open_futures_position",
    }
    external_keyword_call_sites = set()
    for path in (root / "app").rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        if relative == "app/engine/broker.py":
            continue
        tree = ast.parse(path.read_text())
        if any(
                isinstance(node, ast.Call)
                and any(keyword.arg == "runtime_context_json" for keyword in node.keywords)
                for node in ast.walk(tree)):
            external_keyword_call_sites.add(relative)
    assert external_keyword_call_sites == {"app/paper_runtime/service.py"}


# ── neutral vocabulary ────────────────────────────────────────────────────

def test_tenor_classification_matches_the_charge_segments():
    assert tenor_for_charge_segment("NSE_INTRADAY") is Tenor.INTRADAY
    assert tenor_for_charge_segment("BSE_INTRADAY") is Tenor.INTRADAY
    assert tenor_for_charge_segment("NFO") is Tenor.CARRY
    assert tenor_for_charge_segment("NFO_FUT") is Tenor.CARRY
    assert tenor_for_charge_segment("NSE_EQ") is Tenor.CARRY   # delivery is not MIS
    assert tenor_for_charge_segment("MCX") is Tenor.CARRY


def test_protective_kind_matches_what_zerodha_actually_accepts():
    """Zerodha refuses a GTT on an MIS position — the 2026-07-03 failure class,
    where option GTTs worked and intraday stops were never created at all."""
    assert (protective_kind_for_book_segment("equity_intraday")
            is ProtectiveStopKind.RESTING_STOP)
    assert (protective_kind_for_book_segment("options")
            is ProtectiveStopKind.SERVER_TRIGGER)
    assert (protective_kind_for_book_segment("futures")
            is ProtectiveStopKind.SERVER_TRIGGER)


# ── the neutral protective-order accessor (C2: gtt_trigger_id in the ORM) ──

class _Row:
    def __init__(self, gtt_trigger_id=None):
        self.gtt_trigger_id = gtt_trigger_id


def test_protective_order_accessors_round_trip_the_column():
    r = _Row()
    assert protective_order_id(r) is None
    set_protective_order_id(r, "SLM-1")
    assert protective_order_id(r) == "SLM-1"
    assert r.gtt_trigger_id == "SLM-1"        # still the same column underneath
    clear_protective_order_id(r)
    assert protective_order_id(r) is None and r.gtt_trigger_id is None


def test_missing_protection_column_reads_as_unprotected_not_an_error():
    """Several call sites pass recovery contexts and doubles that are not full ORM
    rows. 'No such attribute' must mean 'no stop resting', never an exception in
    the risk loop."""
    class Bare:
        pass
    assert protective_order_id(Bare()) is None


def test_live_broker_reaches_the_column_only_through_the_neutral_accessor():
    """C2 asks for a neutral name in engine code. Enforce it where it was actually
    changed: no direct `pos.gtt_trigger_id` access is left in live_broker's CODE
    (prose and comments are exempt — the column still has that name)."""
    import re
    from pathlib import Path
    src = Path(inspect.getfile(LiveBroker)).read_text()
    # strip docstrings and comments, then look for real attribute access
    stripped = re.sub(r'"""(?:.|\n)*?"""', "", src)
    stripped = re.sub(r"#.*", "", stripped)
    hits = [ln.strip() for ln in stripped.splitlines() if ".gtt_trigger_id" in ln]
    assert not hits, (
        f"live_broker still touches the Kite-named column directly: {hits}. "
        f"Use protective_order_id()/set_protective_order_id()/"
        f"clear_protective_order_id() so the eventual column rename is one line.")
