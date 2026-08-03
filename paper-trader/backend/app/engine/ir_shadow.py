"""L1 Stage 1 — the Component IR shadow lane. An observer, and only an observer.

The live hand-written strategy is the **sole execution authority**. This module evaluates
the IR mirror of that strategy on the *identical* candle frame the authoritative lane just
consumed, compares the two verdicts on the newest bar, and classifies any disagreement.
Its return value is a record. Nothing reads it back into the engine's state.

**What this module may not do, and how that is enforced.**

- It reaches no broker, order, position, ledger, sizing, routing, reconciliation or
  square-off seam. It imports none of them, transitively, and `test_ir_shadow_isolation.py`
  proves that by parsing imports *and* by patching every seam and running the lane.
- It mutates nothing it is given. Both frames are treated as read-only; the adapter copies
  before writing columns, and the comparison reads single cells.
- It cannot raise into the caller. Every failure is caught here and turned into a
  classified observation, because a shadow that can break the authoritative lane is worse
  than no shadow at all.
- It holds **no cross-frame evaluation cache**. `Cache` is keyed on `node.cache_id`, fixed
  at resolution and carrying nothing about the input data, so one reused across frames
  returns the previous frame's series with every node reporting a hit — fast, healthy
  looking, and entirely wrong (ADR 0011 §4a). The resolved *graph* is cached, which is
  topology, not data.

**Pairing is by authoritative strategy key.** The only graph that exists mirrors
`expanding_z_v4`. Evaluating it against an instrument running a different strategy would
compare two different strategies and call the difference a divergence, so an instrument
whose strategy has no mirror is skipped — and the skip is counted, not silent.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.strategy.ir_adapter import (
    InsufficientHistory,
    IRAdapterError,
    IRGraphStrategy,
    MissingGraphInput,
)
from app.strategy.registry.base import CANONICAL_COLUMNS

# ── classification: what a recorded disagreement is ───────────────────────────────
#: The two lanes produced the same four flags on the newest bar. Counted, never persisted.
AGREEMENT = "AGREEMENT"
#: Both lanes produced flags and at least one of the four canonical columns differs.
FLAG_DIVERGENCE = "FLAG_DIVERGENCE"
#: The graph's resolved warmup exceeds the frame the live admission guard admitted.
#: ADR 0011 conflict #2; zero of these in market hours is a Stage 1 close criterion.
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
#: The frame does not carry an input the graph declares.
MISSING_GRAPH_INPUT = "MISSING_GRAPH_INPUT"
#: Any other typed refusal from the adapter (unmappable outputs, invalid risk model).
ADAPTER_REFUSAL = "ADAPTER_REFUSAL"
#: The IR runtime refused, named by the RFC clause it failed.
EVALUATION_ERROR = "EVALUATION_ERROR"
#: Anything else. Always a defect; never a routine outcome.
UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
#: The authoritative lane did not present the four canonical columns to compare against.
AUTHORITATIVE_UNAVAILABLE = "AUTHORITATIVE_UNAVAILABLE"

#: Every class a persisted row may carry. Kept as a tuple so the store, the metrics and
#: the report cannot drift apart from the classifier.
DISAGREEMENT_REASONS = (
    FLAG_DIVERGENCE, INSUFFICIENT_HISTORY, MISSING_GRAPH_INPUT, ADAPTER_REFUSAL,
    EVALUATION_ERROR, UNEXPECTED_ERROR, AUTHORITATIVE_UNAVAILABLE,
)

_DETAIL_LIMIT = 400


#: Candle minutes per live-interval string. An interval absent here is refused rather than
#: guessed: an admission decision made on a guessed bar length is not a decision.
INTERVAL_MINUTES = {"5minute": 5, "15minute": 15, "30minute": 30, "60minute": 60}

#: Sessions per calendar week, used to turn `history_days` into a session count. Floored,
#: and holidays are not modelled, so the estimate is deliberately on the low side: an
#: optimistic count admits a graph that then refuses in the middle of a session, which is
#: the failure this validator exists to prevent.
SESSIONS_PER_WEEK = 5

#: Consecutive post-admission `INSUFFICIENT_HISTORY` refusals tolerated before the pairing
#: is demoted to rejected. Admission reasons from *configuration*; a feed can still disagree
#: with it (the mock provider returns 161 bars whatever it is asked for). Predicting
#: correctly is not the contract — the contract is that a pairing cannot produce repeated
#: in-hours refusals, so observation gets the last word. Small, because there is nothing to
#: learn from the fourth identical refusal that the third did not already say.
REFUSALS_BEFORE_DEMOTION = 3


@dataclass(frozen=True)
class Admission:
    """Whether a graph's declared warmup can be satisfied by the configured history.

    Decided from **configuration**, before any evaluation, because the alternative is to
    learn it from a refusal — and a refusal repeated every 2.5 s for a whole session is
    both useless and not free.
    """

    ok: bool
    instrument_key: str
    interval: str
    warmup: int
    expected_bars: int
    sessions: int
    bars_per_session: int
    reason: str


def bars_per_session(segment: str, interval: str) -> int:
    """Completed bars one session of `segment` can print at `interval`.

    Rounds **up**: the part-bar at the close is a bar the feed returns. An unknown segment
    falls back to the *shortest* session (the equity window), never the longest — guessing
    MCX's 14½ hours for something unrecognised would admit a configuration that cannot
    settle.
    """
    from app.core.market_hours import _DEFAULT, SESSIONS

    minutes = INTERVAL_MINUTES.get(interval)
    if not minutes:
        return 0
    opens, closes = SESSIONS.get(segment, _DEFAULT)
    span = (closes.hour * 60 + closes.minute) - (opens.hour * 60 + opens.minute)
    return -(-span // minutes)


def trading_sessions(history_days: int) -> int:
    return max(0, int(history_days)) * SESSIONS_PER_WEEK // 7


def admit(*, instrument_key: str, segment: str, interval: str, history_days: int,
          warmup: int) -> Admission:
    """Decide whether `instrument_key` may be shadowed at all under this configuration."""
    per_session = bars_per_session(segment, interval)
    sessions = trading_sessions(history_days)
    expected = per_session * sessions

    def verdict(ok: bool, reason: str) -> Admission:
        return Admission(ok=ok, instrument_key=instrument_key, interval=interval,
                         warmup=warmup, expected_bars=expected, sessions=sessions,
                         bars_per_session=per_session, reason=reason)

    if not per_session:
        return verdict(False, f"{instrument_key}: live interval {interval!r} is not one this "
                              f"validator knows how to size; refusing rather than guessing")
    if expected <= warmup:
        return verdict(False, (
            f"{instrument_key}: {interval} on {segment} yields about {expected} bars in "
            f"{history_days} days ({sessions} sessions x {per_session}), which cannot settle "
            f"a graph whose declared warmup is {warmup}; at least {warmup + 1} are needed. "
            f"Shadow evaluation is disabled for this instrument until the configuration "
            f"changes."))
    return verdict(True, (
        f"{instrument_key}: {interval} on {segment} yields about {expected} bars, clearing "
        f"a declared warmup of {warmup}"))


def demote(admission: Admission, *, observed_bars: int, refusals: int) -> Admission:
    """Turn an admitted pairing into a rejected one after the feed contradicts admission.

    The reason names **both** numbers — what the configuration predicted and what the feed
    actually returned — because the gap between them is the thing someone has to fix, and a
    demotion that only said "not enough bars" would hide which of the two is wrong.
    """
    return Admission(
        ok=False, instrument_key=admission.instrument_key, interval=admission.interval,
        warmup=admission.warmup, expected_bars=admission.expected_bars,
        sessions=admission.sessions, bars_per_session=admission.bars_per_session,
        reason=(
            f"{admission.instrument_key}: demoted after {refusals} consecutive refusals — "
            f"admission expected about {admission.expected_bars} bars at "
            f"{admission.interval} but the feed returned {observed_bars}, against a "
            f"declared warmup of {admission.warmup}. Shadow evaluation is disabled for "
            f"this instrument until the configuration or the feed changes."))


@dataclass
class ShadowPairing:
    """One hand-written strategy and the graph that mirrors it.

    The adapter is built on first use and kept: resolution is not free and the signal lane
    runs every 2.5 s. This is a cache of *topology*, which is fixed at resolution — not the
    forbidden evaluation cache, which would carry one frame's data into the next.
    """

    authoritative_key: str
    graph: dict[str, Any]
    library: tuple[Any, Any]
    strategy: Any = None

    def adapter(self) -> Any:
        if self.strategy is None:
            self.strategy = IRGraphStrategy(self.graph, self.library)
        return self.strategy


@dataclass(frozen=True)
class ShadowObservation:
    """One bar, both verdicts, and everything needed to attribute a disagreement later.

    Every field the owner asked a disagreement to carry is here: when it was seen, on what
    instrument, which graph (content address) under which stable execution key, what the
    authoritative lane said, what the IR said, the warmup state, the exact identity of the
    input frame, and the classified reason.
    """

    instrument_key: str
    bar_time: dt.datetime | None
    observed_at: dt.datetime
    authoritative_strategy_key: str
    shadow_strategy_key: str
    graph_address: str
    authoritative: dict[str, bool] | None
    ir: dict[str, bool] | None
    warmup_state: str
    declared_warmup: int
    frame_bars: int
    frame_id: str
    frame_first_ts: dt.datetime | None
    frame_last_ts: dt.datetime | None
    reason: str
    detail: str
    eval_seconds: float

    @property
    def agreed(self) -> bool:
        return self.reason == AGREEMENT


# ── the pairing registry ──────────────────────────────────────────────────────────

def _expanding_z_pairing() -> ShadowPairing:
    from app.ir.strategies.expanding_z import GRAPH, IMPLEMENTATIONS, LIBRARY
    return ShadowPairing(authoritative_key="expanding_z_v4", graph=GRAPH,
                         library=(LIBRARY, IMPLEMENTATIONS))


#: authoritative strategy key -> how to build its mirror. Lazy, because importing the
#: graph module resolves nothing but does import the IR language, and the engine must not
#: pay for it when the lane is switched off.
PAIRING_BUILDERS: dict[str, Any] = {"expanding_z_v4": _expanding_z_pairing}

_PAIRINGS: dict[str, ShadowPairing] = {}


def pairing_for(authoritative_key: str | None) -> ShadowPairing | None:
    """The shadow pairing for an authoritative strategy key, or None if it has no mirror."""
    if not authoritative_key or authoritative_key not in PAIRING_BUILDERS:
        return None
    if authoritative_key not in _PAIRINGS:
        _PAIRINGS[authoritative_key] = PAIRING_BUILDERS[authoritative_key]()
    return _PAIRINGS[authoritative_key]


# ── frame identity ────────────────────────────────────────────────────────────────

def frame_identity(frame: pd.DataFrame, inputs: tuple[str, ...]) -> str:
    """A content address for the exact bars the graph was given.

    Digested from the declared input columns' float64 bytes and the bars' own timestamps,
    so two observations carry the same identity if and only if the graph saw the same data.
    Nothing about the wall clock enters, or a re-scan of an unchanged frame would look like
    a different input.
    """
    digest = hashlib.sha256()
    if "date" in frame.columns:
        stamps = pd.to_datetime(frame["date"], utc=True, errors="coerce")
        digest.update(stamps.to_numpy(dtype="datetime64[ns]").tobytes())
    for name in inputs:
        digest.update(name.encode())
        if name in frame.columns:
            digest.update(frame[name].to_numpy(dtype="float64").tobytes())
    return f"sha256:{digest.hexdigest()}"


def _stamp(frame: pd.DataFrame, position: int) -> dt.datetime | None:
    if "date" not in frame.columns or frame.empty:
        return None
    value = pd.Timestamp(frame["date"].iloc[position])
    return None if pd.isna(value) else value.to_pydatetime()


def _flags_of(frame: pd.DataFrame) -> dict[str, bool] | None:
    if frame is None or len(frame) == 0:
        return None
    if not all(column in frame.columns for column in CANONICAL_COLUMNS):
        return None
    last = frame.iloc[-1]
    return {column: bool(last[column]) for column in CANONICAL_COLUMNS}


def compare(authoritative: dict[str, bool], ir: dict[str, bool]) -> tuple[str, str]:
    """Classify one bar's two verdicts: `(reason, detail)`."""
    differing = [column for column in CANONICAL_COLUMNS
                 if authoritative[column] != ir[column]]
    if not differing:
        return AGREEMENT, ""
    detail = "; ".join(
        f"{column}: authoritative={authoritative[column]} ir={ir[column]}"
        for column in differing)
    return FLAG_DIVERGENCE, detail


def _classify_failure(error: BaseException) -> tuple[str, str]:
    from app.ir.runtime import EvaluationError

    if isinstance(error, InsufficientHistory):
        return INSUFFICIENT_HISTORY, str(error)
    if isinstance(error, MissingGraphInput):
        return MISSING_GRAPH_INPUT, str(error)
    if isinstance(error, IRAdapterError):
        return ADAPTER_REFUSAL, f"{type(error).__name__}: {error}"
    if isinstance(error, EvaluationError):
        return EVALUATION_ERROR, f"{type(error).__name__}: {error}"
    return UNEXPECTED_ERROR, f"{type(error).__name__}: {error}"


def observe(*, instrument_key: str, authoritative_key: str,
            authoritative_frame: pd.DataFrame, frame: pd.DataFrame,
            now: dt.datetime, pairing: ShadowPairing | None = None,
            ) -> ShadowObservation | None:
    """Evaluate the mirror of `authoritative_key` on `frame` and compare the newest bar.

    Returns `None` when the authoritative strategy has no mirror — the ordinary case for
    an instrument the shadow lane is not configured for. Never raises: a shadow that can
    interrupt the authoritative lane would defeat its own purpose.
    """
    pairing = pairing or pairing_for(authoritative_key)
    if pairing is None:
        return None

    started = time.perf_counter()
    address, shadow_key, warmup, inputs = "", "", 0, ()
    ir_flags: dict[str, bool] | None = None
    reason = detail = ""
    try:
        adapter = pairing.adapter()
        address = str(getattr(adapter, "address", ""))
        shadow_key = str(getattr(adapter, "key", ""))
        warmup = int(getattr(adapter, "declared_warmup", 0) or 0)
        inputs = tuple(getattr(adapter, "required_inputs", ()) or ())
        ir_flags = _flags_of(adapter.compute(frame))
        if ir_flags is None:
            reason, detail = UNEXPECTED_ERROR, "the graph produced no canonical columns"
    except BaseException as error:                        # noqa: BLE001 — see docstring
        reason, detail = _classify_failure(error)
    elapsed = time.perf_counter() - started

    authoritative_flags = _flags_of(authoritative_frame)
    if authoritative_flags is None and not reason:
        reason, detail = AUTHORITATIVE_UNAVAILABLE, (
            "the authoritative frame carries no canonical columns to compare against")
    if not reason:
        reason, detail = compare(authoritative_flags, ir_flags)

    return ShadowObservation(
        instrument_key=instrument_key,
        bar_time=_stamp(frame, -1),
        observed_at=now,
        authoritative_strategy_key=authoritative_key,
        shadow_strategy_key=shadow_key,
        graph_address=address,
        authoritative=authoritative_flags,
        ir=ir_flags,
        warmup_state="insufficient" if reason == INSUFFICIENT_HISTORY else "settled",
        declared_warmup=warmup,
        frame_bars=int(len(frame)),
        frame_id=frame_identity(frame, inputs),
        frame_first_ts=_stamp(frame, 0),
        frame_last_ts=_stamp(frame, -1),
        reason=reason,
        detail=detail[:_DETAIL_LIMIT],
        eval_seconds=elapsed,
    )


__all__ = [
    "INTERVAL_MINUTES", "SESSIONS_PER_WEEK", "Admission", "admit", "bars_per_session",
    "trading_sessions",
    "ADAPTER_REFUSAL", "AGREEMENT", "AUTHORITATIVE_UNAVAILABLE", "DISAGREEMENT_REASONS",
    "EVALUATION_ERROR", "FLAG_DIVERGENCE", "INSUFFICIENT_HISTORY", "MISSING_GRAPH_INPUT",
    "PAIRING_BUILDERS", "ShadowObservation", "ShadowPairing", "UNEXPECTED_ERROR",
    "compare", "frame_identity", "observe", "pairing_for",
]
