"""What a provider connection must actually *do*, as opposed to what it says it can do.

`capabilities.py` fixed the vocabulary. `test_provider_capabilities.py` then checked that a
declared capability has a method behind it which is not the base class's default. That check is
structural, and structural is not enough: three adapters written to lie in the three ways that
matter all pass it clean.

  * declare `ACCOUNT_FUNDS`, override `account_funds` with `return None` — a real override, a
    permanent refusal, and every caller stops fail-closing because the connection said it could;
  * declare `HISTORICAL_DATA` and return newest-first bars with `low > high` — every indicator
    computed on that frame is wrong, and nothing raises;
  * declare `FUTURES_QUOTES` and return spot for every expiry — the mis-pricing wearing a
    working provider's clothes, which is the exact failure `get_futures_ltp` was written to
    prevent.

So this module holds the *semantic* contract, and it is one contract that every adapter is run
through. The obligations are in two tiers.

**Tier 1 — the base contract.** Applies to every adapter whatever it declares. An override must
accept the call the base class makes, and must refuse in the contract's vocabulary (`None`, not
`[]`). And a capability must be declared if and only if it is implemented: over-declaring makes
callers trust a connection that cannot deliver, and **under-declaring silently fences off working
behaviour**, which is how the mock came to price futures perfectly while the futures segment
refused to open a single position on it.

**Tier 2 — capability semantics.** Runs only the obligations for the capabilities an adapter
declares, because a declaration is the promise being held to.

Checks are plain functions returning a list of violation strings rather than assertions, so the
same code proves both directions: real adapters produce no violations, and a deliberately
dishonest adapter produces the specific violation naming the obligation it broke. A conformance
suite that has never been observed failing an adapter is not evidence.

The checks need a live-ish connection, so `ConformanceCase` carries the adapter together with
the canonical instrument to exercise it on and the expiries it should and should not be able to
price. Adding an adapter means adding a case; `test_provider_conformance.py` refuses to let a
`MarketDataProvider` subclass exist without one.

**Why this lives under `tests/` and not `app/providers/`.** Its only consumer is CI. Putting it
in the runtime package would ship a mechanism wired to nothing, which is the failure shape this
codebase has repeatedly paid for. A deployment-time capability precondition is a plausible second
consumer; when something actually needs it, it moves, with the caller in the same change.
"""
from __future__ import annotations

import datetime as dt
import inspect
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from app.core.instruments import Instrument
from app.providers import capabilities as caps
from app.providers.base import (Candle, MarketDataProvider, OptionChain,
                                ProviderReadError)
from app.providers.instrument_resolver import ResolvedInstrument


@dataclass
class ConformanceCase:
    """One adapter, ready to be exercised, plus what it should be able to answer."""

    provider: MarketDataProvider
    instrument: Instrument
    interval: str = "15minute"
    days: int = 30
    # How many bars this connection should serve for (interval, days). Explicit per adapter,
    # because "enough" is a property of the connection's history depth, not of the contract.
    # A provider that answers three daily bars to a thirty-day fifteen-minute request has
    # under-served every warmup downstream, and no generic rule catches that.
    min_bars: int = 0
    # An expiry this connection can price, and the two distinct ways it can be unable to.
    # They are different code paths and are deliberately not one field: "that contract has
    # settled" and "I do not carry that series" are answered by different logic, and merging
    # them means whichever an adapter happens to hit is the only one ever tested.
    priceable_expiry: dt.date | None = None
    settled_expiry: dt.date | None = None
    unlisted_expiry: dt.date | None = None
    # A margin-quote payload in THIS provider's vocabulary. On the case rather than in the
    # contract: a Kite order dict hard-coded into the canonical checker is the same
    # provider-symbology-in-canonical-object defect `instrument_resolver.py` exists to unwind.
    margin_probe_order: dict | None = None
    # Does this connection quote an underlying that is economically DISTINCT from the front
    # future? True for an index (NIFTY cash vs NIFTY futures, tens of points apart). False on
    # MCX, where Kite has no cash quote at all and `resolve_underlying` returns the near-future
    # symbol — so "spot" and "the front month" are legitimately the same number, and requiring
    # a basis there would fail a correct adapter.
    expects_basis: bool = True
    # (tradingsymbol, exchange, tick) for an instrument this connection serves whose tick is
    # NOT the 0.05 default. Only such a symbol can distinguish "reads the venue's tick" from
    # "returns the constant" — checking a 0.05 instrument passes either way, which is the
    # right-clause-wrong-cause shape. Required of every executing connection; `None` on a
    # data-only one, where the field is meaningless.
    non_default_tick: tuple[str, str, float] | None = None
    # Puts the connection's transport into a failure state (expired token, network error).
    # Every declared read must degrade to its documented refusal rather than propagate or,
    # worse, serve a stale cache as though it were data.
    break_transport: Callable[[], None] | None = None
    notes: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return getattr(self.provider, "name", type(self.provider).__name__)

    @property
    def unpriceable_expiries(self) -> list[dt.date]:
        return [d for d in (self.settled_expiry, self.unlisted_expiry) if d is not None]


_INTERVAL_MINUTES: dict[str, int] = {"minute": 1, "hour": 60, "day": 1440, "week": 10080}


def interval_delta(interval: str) -> dt.timedelta | None:
    """`"15minute"` -> 15 minutes. None when the vocabulary is not one we can decode.

    Deliberately decoded here rather than trusted: a provider whose historical vocabulary is not
    Kite's — Upstox's is not — can map a request wrongly and return one-minute bars for a
    fifteen-minute request. Nothing downstream raises; `z_length` and `ema_length` simply
    compute over a fifteen-times shorter horizon.
    """
    text = (interval or "").strip().lower()
    for unit, minutes in _INTERVAL_MINUTES.items():
        if text == unit:
            return dt.timedelta(minutes=minutes)
        if text.endswith(unit):
            head = text[: -len(unit)]
            if head.isdigit():
                return dt.timedelta(minutes=int(head) * minutes)
    return None


# ── tier 1: the base contract ────────────────────────────────────────────────

# Methods whose refusal value is documented on the base class. An override that refuses with a
# different falsy type still reads as "no data" at an `if not x:` call site and then explodes at
# the first site that does anything else with it.
_REFUSAL_VOCABULARY: dict[str, tuple[type, ...]] = {
    "get_option_chain": (OptionChain, type(None)),
    "option_ltp": (float, int, type(None)),
    "get_ltp": (float, int, type(None)),
    "get_futures_ltp": (float, int, type(None)),
    "account_funds": (dict, type(None)),
    "account_positions": (list, type(None)),
    "account_equity": (float, int, type(None)),
    "order_margin": (float, int, type(None)),
}


def check_signature_conformance(provider: MarketDataProvider) -> list[str]:
    """Every override must accept the call the base class already makes.

    This is not style. `MarketDataProvider.live_snapshot` calls
    `self.option_ltp(inst, tradingsymbol, strike, expiry, option_type)` on any non-equity
    position. An adapter that narrowed `option_ltp` to one argument satisfies every structural
    check and every capability gate, and then raises `TypeError` from inherited code the moment
    an option position is open.
    """
    violations = []
    for name, base_method in vars(MarketDataProvider).items():
        if name.startswith("_") or not callable(base_method):
            continue
        override = getattr(type(provider), name, None)
        if override is None or override is base_method:
            continue
        base_params = [p for p in inspect.signature(base_method).parameters.values()
                       if p.name != "self"]
        required = [p for p in base_params
                    if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        try:
            inspect.signature(override).bind(provider, *[None] * len(required))
        except TypeError as e:
            violations.append(
                f"{name}() cannot accept the base contract's call "
                f"({len(required)} positional args): {e}")
    return violations


def check_refusal_vocabulary(case: ConformanceCase) -> list[str]:
    """A refusal must be spelled the way the contract spells it.

    `get_option_chain` returning `[]` instead of `None` is falsy, so it survives every
    `if not chain:` site and looks harmless — until one site iterates it, or a type-driven
    caller treats an empty chain as a chain that exists with no strikes.
    """
    violations = []
    p, inst = case.provider, case.instrument
    probes: list[tuple[str, Callable[[], object]]] = [
        ("get_ltp", lambda: p.get_ltp(inst)),
        ("get_option_chain", lambda: p.get_option_chain(inst)),
        ("get_futures_ltp", lambda: p.get_futures_ltp(
            inst, (case.unpriceable_expiries or [dt.date(1990, 1, 1)])[0])),
        ("account_funds", p.account_funds),
        ("account_positions", p.account_positions),
        ("account_equity", p.account_equity),
        ("option_ltp", lambda: p.option_ltp(inst, "PROBE", 100.0, dt.date(1990, 1, 1), "CE")),
    ]
    for name, call in probes:
        if getattr(type(p), name, None) is getattr(MarketDataProvider, name, None):
            continue                       # inherited default — the base's own vocabulary
        try:
            value = call()
        except Exception as e:             # noqa: BLE001 — raising is itself the violation
            violations.append(f"{name}() raised {type(e).__name__}: {e} instead of refusing")
            continue
        allowed = _REFUSAL_VOCABULARY.get(name)
        if allowed and not isinstance(value, allowed):
            violations.append(
                f"{name}() returned {type(value).__name__} {value!r}; the contract's "
                f"vocabulary is {'/'.join(t.__name__ for t in allowed)}")
    return violations


def check_declaration_matches_implementation(provider: MarketDataProvider) -> list[str]:
    """A declared capability must not be backed by the base class's default.

    Structural and cheap, so it stays: a connection that claims `ACCOUNT_FUNDS` and inherits
    `return None` is worse than one that claims nothing, because callers stop fail-closing.
    Abstract methods are skipped — an abstract method must be overridden even in order to
    refuse, so the presence of an override says nothing either way.
    """
    violations = []
    cls = type(provider)
    for cap, method in caps.BACKING_METHOD.items():
        if method is None:
            continue                       # declaration-only, no consumer yet
        base = getattr(MarketDataProvider, method, None)
        if getattr(base, "__isabstractmethod__", False):
            continue
        own = getattr(cls, method, None)
        if cap in cls.CAPABILITIES and (own is None or own is base):
            violations.append(
                f"declares {cap!r} but {method}() is the base default — callers will stop "
                f"fail-closing on a connection that always refuses")
    return violations


def check_undeclared_options_are_refused(case: ConformanceCase) -> list[str]:
    """A connection that does not declare OPTION_CHAIN must return `None`, not a number.

    `get_option_chain` and `option_ltp` were `@abstractmethod` until 2026-08-10, which made a
    data-only adapter impossible to construct — the parked Upstox adapter failed at
    instantiation. Making them concrete with a `None` default fixed that and opened a hole in
    the same movement: `check_no_undeclared_working_capability` deliberately skips a method the
    adapter inherits unchanged, so a wrong *base* default would be invisible to every adapter at
    once. A suppression sweep found it — the base returning `1.0` reddened nothing.

    The consequence is specific. `None` means "I cannot price this" and callers refuse; any
    number is taken as a real premium, and an option position gets marked, stopped and booked
    against a price no market ever quoted.
    """
    p = case.provider
    if caps.OPTION_CHAIN in type(p).CAPABILITIES:
        return []
    violations = []
    try:
        chain = p.get_option_chain(case.instrument)
    except Exception as e:            # noqa: BLE001
        violations.append(f"get_option_chain raised {type(e).__name__} on an adapter that does "
                          f"not declare {caps.OPTION_CHAIN!r}; it must simply answer None")
    else:
        if chain is not None:
            violations.append(
                f"get_option_chain served {type(chain).__name__} without declaring "
                f"{caps.OPTION_CHAIN!r} — every gate in the system reads this connection as "
                f"unable to price options while it hands out chains")
    try:
        px = p.option_ltp(case.instrument, "SYNTHETIC", 0.0, dt.date(2026, 1, 1), "CE")
    except Exception as e:            # noqa: BLE001
        violations.append(f"option_ltp raised {type(e).__name__} for a contract this connection "
                          f"cannot price; the contract's refusal is None")
    else:
        if px is not None:
            violations.append(
                f"option_ltp answered {px!r} for a contract on a connection that declares no "
                f"option capability — a fabricated premium marks and stops a real position")
    return violations


def check_no_undeclared_working_capability(case: ConformanceCase) -> list[str]:
    """The quieter half: behaviour that works and is never declared.

    This one cannot be decided structurally, and trying to was wrong. `ReplayProvider` overrides
    `get_futures_ltp` *in order to refuse* — a recording has no futures feed — which is correct
    and must not be reported. The only honest test is behavioural: run the capability's own
    obligations against an adapter that did not declare it, and if it satisfies all of them, it
    is serving the capability while every gate in the system reads it as incapable.

    That is exactly what `MockProvider` did: it priced futures with a basis decaying to zero at
    settlement, declared nothing, and so `_process_futures_entries` refused to open a position on
    the one connection where the index-futures segment could be exercised before going live.

    "Satisfies the obligations" alone is not enough to conclude this, and the first draft that
    used it was wrong: a connection that refuses everything also breaks no obligation. So the
    capability must additionally have *answered* — `_ANSWERED` below. That is what separates
    the mock (priced a real contract, declared nothing) from replay (overrides `get_futures_ltp`
    precisely in order to refuse, and is right to).
    """
    violations = []
    cls = type(case.provider)
    for cap, check in CAPABILITY_OBLIGATIONS.items():
        method = caps.BACKING_METHOD.get(cap)
        if cap in cls.CAPABILITIES or method is None:
            continue
        base = getattr(MarketDataProvider, method, None)
        own = getattr(cls, method, None)
        if own is None or own is base:
            continue
        # Abstract methods are NOT skipped here, though an earlier draft skipped them. That skip
        # left the check able to fire only for FUTURES_QUOTES and ACCOUNT_FUNDS — every abstract
        # one (get_candles, get_ltp, get_option_chain, option_ltp) was exempt, which is to say
        # the three capabilities a data-only adapter will actually declare were invisible to it.
        # `_ANSWERED` is what makes them decidable: an override written purely to refuse does not
        # answer, so it is not reported, and the abstractness never needed to be consulted.
        answered = _ANSWERED.get(cap)
        if answered is None or not answered(case) or check(case):
            # `_ANSWERED` is the limit of this check's reach, deliberately and not silently:
            # a capability with no way to ask "did it answer" cannot be judged behaviourally,
            # and guessing from the presence of an override is what made the first draft report
            # replay's deliberate refusal as a defect. `test_provider_conformance.py` pins which
            # capabilities are covered, so the gap is a listed fact rather than an assumption.
            continue
        violations.append(
            f"satisfies every obligation of {cap!r} and answers, but does not declare it — "
            f"capability gates fence off working behaviour and nothing reports it")
    return violations


def _answered_futures(case: ConformanceCase) -> bool:
    return (case.priceable_expiry is not None
            and case.provider.get_futures_ltp(case.instrument, case.priceable_expiry) is not None)


# "Did this connection produce a usable answer?", per capability. Distinct from "did it break
# an obligation?" — a connection that refuses everything breaks none.
_ANSWERED: dict[str, Callable[[ConformanceCase], bool]] = {
    caps.HISTORICAL_DATA: lambda c: bool(
        c.provider.get_candles(c.instrument, c.interval, c.days)),
    caps.LIVE_QUOTES: lambda c: c.provider.get_ltp(c.instrument) is not None,
    caps.OPTION_CHAIN: lambda c: c.provider.get_option_chain(c.instrument) is not None,
    caps.FUTURES_QUOTES: _answered_futures,
    caps.ACCOUNT_FUNDS: lambda c: isinstance(c.provider.account_funds(), dict),
}


# ── tier 2: capability semantics ─────────────────────────────────────────────

def _finite_positive(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x) and x > 0


def check_historical_data(case: ConformanceCase) -> list[str]:
    """Bars must be ordered, coherent, correctly spaced, complete, and stamped the one way.

    Order and OHLC coherence are what every indicator silently assumes. The rest are the
    cross-provider hazards, and a first draft of this contract asserted none of them — a
    deliberately wrong adapter that served three tz-aware daily bars for a thirty-day
    fifteen-minute request, including the still-forming one, passed it clean.
    """
    violations = []
    p = case.provider
    bars = p.get_candles(case.instrument, case.interval, case.days)
    if not isinstance(bars, list):
        return [f"get_candles returned {type(bars).__name__}, not a list"]
    if not bars:
        return ["get_candles returned no bars for an instrument this connection resolves"]
    if any(not isinstance(b, Candle) for b in bars):
        violations.append("get_candles returned rows that are not Candle")
        return violations
    for i in range(1, len(bars)):
        if bars[i].ts <= bars[i - 1].ts:
            violations.append(
                f"bars are not strictly oldest-first at index {i}: "
                f"{bars[i - 1].ts} then {bars[i].ts}")
            break

    # Timestamps are naive IST throughout this codebase — `kite.py` strips the tz off every raw
    # bar deliberately, and the frontend re-anchors offset-less times to +05:30. An adapter that
    # returns aware stamps is internally consistent and mutually incompatible with every other
    # one, and the comparison that raises happens deep inside a warmup window, not here.
    aware = [b for b in bars if b.ts.tzinfo is not None]
    if aware:
        violations.append(
            f"{len(aware)}/{len(bars)} bars carry tzinfo; this codebase's candle epoch is naive "
            f"IST, and a second convention only surfaces at a comparison far from the adapter")

    step = interval_delta(case.interval)
    if step is not None and len(bars) > 2:
        deltas = [bars[i].ts - bars[i - 1].ts for i in range(1, len(bars))]
        modal = Counter(deltas).most_common(1)[0][0]      # modal, so session gaps do not count
        if modal != step:
            violations.append(
                f"bars are spaced {modal} apart for a {case.interval!r} request — an interval "
                f"mapped wrongly changes every indicator's horizon and raises nothing")

    now = p.now()
    if aware or now.tzinfo is not None:
        # The clock and the bars are on different conventions, which is the violation already
        # recorded above. Comparing them raises TypeError, so the remaining temporal obligations
        # cannot be evaluated — say so rather than crash the contract on a defective adapter.
        return violations + ["temporal obligations were not evaluated: bar and clock tz "
                             "conventions disagree, so no comparison between them is meaningful"]
    if bars[-1].ts > now:
        violations.append(f"newest bar {bars[-1].ts} is stamped after now() {now} — look-ahead")
    elif step is not None and caps.SIMULATED_CLOCK not in type(p).CAPABILITIES:
        # Only for a real clock. A simulated clock's `now()` IS the current bar's stamp by
        # construction (replay pins `bars[-1].ts == now()`), so the completed-bar test would be
        # asserting a convention that does not apply rather than a defect.
        if bars[-1].ts + step > now:
            violations.append(
                f"newest bar {bars[-1].ts} has not closed at now() {now} — this codebase fires "
                f"signals only on completed candles, and a forming bar repaints every one")

    if bars[0].ts < now - dt.timedelta(days=case.days + 1):
        violations.append(
            f"oldest bar {bars[0].ts} predates the {case.days}-day window that was requested")
    if case.min_bars and len(bars) < case.min_bars:
        violations.append(
            f"served {len(bars)} bars for {case.days} days at {case.interval!r}; this "
            f"connection should serve at least {case.min_bars}, and under-serving history "
            f"starves warmup silently")

    for i, b in enumerate(bars):
        prices = (b.open, b.high, b.low, b.close)
        if not all(_finite_positive(x) for x in prices):
            violations.append(f"bar {i} has a non-finite or non-positive price: {prices}")
            break
        if b.low > min(b.open, b.close) or b.high < max(b.open, b.close) or b.low > b.high:
            violations.append(
                f"bar {i} is not OHLC-coherent: o={b.open} h={b.high} l={b.low} c={b.close}")
            break
        if not (isinstance(b.volume, (int, float)) and math.isfinite(b.volume)
                and b.volume >= 0):
            violations.append(f"bar {i} has an impossible volume: {b.volume}")
            break
    return violations


def check_live_quotes(case: ConformanceCase) -> list[str]:
    violations = []
    for label, value in (("get_ltp", case.provider.get_ltp(case.instrument)),
                         ("get_live_price", case.provider.get_live_price(case.instrument))):
        if value is None:
            violations.append(f"{label} refused for an instrument this connection resolves")
        elif not _finite_positive(value):
            violations.append(f"{label} returned {value!r}, which is not a tradable price")
    return violations


def check_option_chain(case: ConformanceCase) -> list[str]:
    """A chain must be one expiry's worth of contracts that can then be priced.

    The `option_ltp` round-trip is deliberate: `OPTION_CHAIN` is one capability covering both,
    and an adapter that lists strikes it cannot subsequently price leaves every open position
    unmarkable.
    """
    violations = []
    chain = case.provider.get_option_chain(case.instrument)
    if chain is None:
        return ["get_option_chain refused for an instrument this connection resolves"]
    if not isinstance(chain, OptionChain):
        return [f"get_option_chain returned {type(chain).__name__}, not OptionChain"]
    if not _finite_positive(chain.spot):
        violations.append(f"chain spot {chain.spot!r} is not a price")
    if not chain.quotes:
        return violations + ["chain has no quotes"]
    for q in chain.quotes:
        if q.expiry != chain.expiry:
            violations.append(
                f"quote {q.tradingsymbol} has expiry {q.expiry}, chain says {chain.expiry} — "
                f"a chain that mixes expiries prices two different contracts as one")
            break
    for q in chain.quotes:
        if q.option_type not in ("CE", "PE"):
            violations.append(f"quote {q.tradingsymbol} has option_type {q.option_type!r}")
            break
        if not _finite_positive(q.strike):
            violations.append(f"quote {q.tradingsymbol} has strike {q.strike!r}")
            break
        if not (isinstance(q.lot_size, int) and q.lot_size > 0):
            violations.append(
                f"quote {q.tradingsymbol} has lot_size {q.lot_size!r} — sizing and every "
                f"charge computed from it would be wrong")
            break
        if q.bid > 0 and q.ask > 0 and q.bid > q.ask:
            violations.append(f"quote {q.tradingsymbol} is crossed: bid {q.bid} > ask {q.ask}")
            break
    first = chain.quotes[0]
    premium = case.provider.option_ltp(
        case.instrument, first.tradingsymbol, first.strike, first.expiry, first.option_type)
    if premium is None:
        violations.append(
            f"option_ltp cannot price {first.tradingsymbol}, which this connection itself "
            f"listed in the chain")
    elif not (isinstance(premium, (int, float)) and math.isfinite(premium) and premium >= 0):
        violations.append(f"option_ltp returned {premium!r} for {first.tradingsymbol}")
    return violations


def check_futures_quotes(case: ConformanceCase) -> list[str]:
    """Price the contract, or refuse. Never substitute the underlying.

    Falling back to spot is the failure this capability exists to prevent: an index future sits
    tens of points from its cash index and converges only at settlement, so marking to spot
    corrupts entry, every risk tick and the exit, and looks entirely healthy while doing it.
    """
    violations = []
    p, inst = case.provider, case.instrument

    # The expiry the ONLY caller actually uses. An earlier draft asserted this capability at
    # `today + 14d` and `today + 300d` — dates nothing in the system ever passes — while
    # `_process_futures_entries` asked at an expiry of *today*, where Kite matched no contract
    # and the mock's basis had converged to exactly spot. The obligation was clean at every
    # expiry except the one that mattered. So ask the connection which contract it would trade,
    # and then require that it can price that one.
    front = p.front_month_expiry(inst)
    if front is None:
        violations.append(
            "declares it can price futures but cannot name a front-month contract; the caller "
            "then has no series to trade and must refuse")
    else:
        px = p.get_futures_ltp(inst, front)
        if px is None:
            violations.append(
                f"named {front} as its front month and then could not price it — the caller "
                f"asks those two questions in sequence and both must answer")
        elif not _finite_positive(px):
            violations.append(f"priced its own front month {front} at {px!r}")
        else:
            spot = p.get_ltp(inst)
            if (case.expects_basis and spot is not None and px == spot
                    and front > p.now().date()):
                violations.append(
                    f"priced its front month {front} at exactly spot ({spot}) with days still "
                    f"to run; a future at spot models no basis, which is the substitution this "
                    f"capability exists to forbid")

    if case.priceable_expiry is not None:
        px = p.get_futures_ltp(inst, case.priceable_expiry)
        if px is None:
            violations.append(
                f"refused to price {case.priceable_expiry}, a contract this connection has")
        elif not _finite_positive(px):
            violations.append(f"priced {case.priceable_expiry} at {px!r}")
    for label, expiry in (("settled", case.settled_expiry), ("unlisted", case.unlisted_expiry)):
        if expiry is None:
            continue
        px = p.get_futures_ltp(inst, expiry)
        if px is not None:
            spot = p.get_ltp(inst)
            detail = " — and it is exactly spot" if spot is not None and px == spot else ""
            violations.append(
                f"priced {expiry}, a {label} contract, at {px!r}{detail}; the contract is to "
                f"refuse")
    return violations


def check_instrument_identity(case: ConformanceCase) -> list[str]:
    """A provider's mapping must carry its own provenance and the canonical key, and nothing else.

    `ResolvedInstrument.provider` is what stops one connection's mapping being applied against
    another — which resolves to a wrong contract while looking entirely valid. This obligation
    exists now, before the second adapter, because the next slice relocates `spot_symbol` and
    `option_name` off the canonical `Instrument`, and the failure it guards against is an Upstox
    resolver quietly returning a Kite string.
    """
    p = case.provider
    if getattr(type(p), "resolve_underlying", None) is None:
        return []
    violations = []
    resolved = p.resolve_underlying(case.instrument)
    if resolved is None:
        return ["resolve_underlying refused an instrument this connection serves data for"]
    if not isinstance(resolved, ResolvedInstrument):
        return [f"resolve_underlying returned {type(resolved).__name__}, not ResolvedInstrument"]
    if resolved.canonical_key != case.instrument.key:
        violations.append(
            f"mapping claims canonical key {resolved.canonical_key!r} for "
            f"{case.instrument.key!r} — the canonical key is the ONE identifier that crosses "
            f"connections and it must be carried unchanged")
    if resolved.provider != case.name:
        violations.append(
            f"mapping is stamped provider {resolved.provider!r} but was produced by "
            f"{case.name!r}; an unprovenanced mapping can be applied against the wrong broker")
    if not resolved.symbol or not resolved.exchange:
        violations.append(
            f"mapping has no usable symbology (symbol={resolved.symbol!r}, "
            f"exchange={resolved.exchange!r})")
    return violations


def check_market_data_under_failure(case: ConformanceCase) -> list[str]:
    """A dead transport must produce a refusal, not yesterday's answer.

    This is the half the first draft never ran. `break_transport` was set on the Kite case,
    documented, and reachable only through `check_account_reads` — so for a data-only connection,
    which declares no account capability, it was never invoked at all: a mechanism wired to
    nothing, inside the guard built to catch mechanisms wired to nothing.

    What it catches is the plausible adapter that serves a cached frame when the API is down.
    Every read then looks healthy, the engine marks positions and fires signals on data that
    stopped updating, and no health counter moves.
    """
    if case.break_transport is None:
        return []
    violations = []
    p, inst = case.provider, case.instrument
    declared = type(p).CAPABILITIES
    case.break_transport()
    if caps.HISTORICAL_DATA in declared:
        # `get_candles` returns a list, so `[]` is the only thing it could once say about a
        # failure — which made "the token expired" indistinguishable from "no history" and left
        # the engine's own health and token-latch handling unreachable. The refusal here is
        # therefore a TYPED one: `ProviderReadError`, carrying the transport's message.
        try:
            bars = p.get_candles(inst, case.interval, case.days)
        except ProviderReadError:
            pass                       # the contract's failure channel, used correctly
        except Exception as e:         # noqa: BLE001
            violations.append(
                f"get_candles raised {type(e).__name__} on a dead transport; a read failure "
                f"must arrive as ProviderReadError so callers can tell it from empty history")
        else:
            if bars:
                violations.append(
                    f"get_candles served {len(bars)} bars with the transport down, newest "
                    f"{bars[-1].ts} — stale data presented as data is worse than no data")
            else:
                violations.append(
                    "get_candles reported no bars with the transport down; `[]` means 'this "
                    "instrument has no history' and a failed read must not borrow it")
    # `None` and `ProviderReadError` are BOTH acceptable refusals for a quote. They say
    # different things — "no price" versus "the read failed" — and the second is strictly more
    # informative, so an adapter that raises the typed error is not penalised for it. What is
    # never acceptable is an answer, or an untyped exception the caller cannot classify.
    if caps.LIVE_QUOTES in declared:
        try:
            px = p.get_ltp(inst)
        except ProviderReadError:
            pass
        except Exception as e:         # noqa: BLE001
            violations.append(
                f"get_ltp raised {type(e).__name__} on a dead transport; a read failure must "
                f"arrive as ProviderReadError or as None")
        else:
            if px is not None:
                violations.append(f"get_ltp answered {px!r} with the transport down")
    if caps.OPTION_CHAIN in declared:
        try:
            chain = p.get_option_chain(inst)
        except ProviderReadError:
            pass
        except Exception as e:         # noqa: BLE001
            violations.append(
                f"get_option_chain raised {type(e).__name__} on a dead transport; a read "
                f"failure must arrive as ProviderReadError or as None")
        else:
            if chain is not None:
                violations.append("get_option_chain served a chain with the transport down")
    return violations


_ACCOUNT_PROBE = [
    (caps.ACCOUNT_FUNDS, "account_funds", dict),
    (caps.ACCOUNT_POSITIONS, "account_positions", list),
    (caps.ACCOUNT_EQUITY, "account_equity", (float, int)),
    (caps.ORDER_MARGIN, "order_margin", (float, int)),
]


def _account_call(case: ConformanceCase, name: str):
    if name == "order_margin":
        return case.provider.order_margin(
            [case.margin_probe_order] if case.margin_probe_order else [])
    return getattr(case.provider, name)()


def check_account_reads(case: ConformanceCase) -> list[str]:
    """Answer when the connection is healthy; report a failure when it is not.

    Both halves are load-bearing and they fail in opposite directions.

    Healthy: a declared account capability that returns `None` unconditionally is a stub wearing
    a real override. It passes every structural check and every caller quietly treats the
    account as unreadable forever.

    Broken: `account_positions` returning `[]` on a transport error reads as a genuinely flat
    account, which is how the bot would trade on top of the owner's own positions (audit C4).
    The documented refusal is `None`, and it must survive an expired token rather than
    propagate out of the adapter.
    """
    violations = []
    cls, p = type(case.provider), case.provider
    declared = [(cap, name, ok) for cap, name, ok in _ACCOUNT_PROBE if cap in cls.CAPABILITIES]

    for cap, name, ok_type in declared:
        try:
            value = _account_call(case, name)
        except Exception as e:             # noqa: BLE001
            violations.append(f"{name}() raised {type(e).__name__} on a healthy connection: {e}")
            continue
        if not isinstance(value, ok_type):
            violations.append(
                f"{name}() returned {value!r} on a healthy connection; it declares {cap!r}, so "
                f"callers have stopped fail-closing on a connection that never answers")

    if case.break_transport is None:
        return violations
    case.break_transport()
    # `None` for every one of them. An earlier draft allowed each probe's *success* type here
    # too, which made the clause unfailable for three of the four: an adapter fabricating
    # `{"available": 0.0, "net": 0.0}` on a dead transport produced no violation at all, under a
    # message that reads "a failed read must be reported as a failure, never as an answer".
    for cap, name, _ in declared:
        allowed = (type(None),)
        try:
            value = _account_call(case, name)
        except Exception as e:             # noqa: BLE001
            violations.append(
                f"{name}() propagated {type(e).__name__} on a broken transport instead of "
                f"returning its documented refusal")
            continue
        if not isinstance(value, allowed):
            violations.append(
                f"{name}() answered {value!r} on a broken transport; a failed read must be "
                f"reported as a failure, never as an answer")
    return violations


_ORDER_TYPE_CAPS = (caps.MARKET_ORDERS, caps.LIMIT_ORDERS, caps.STOP_ORDERS)


def check_execution_declaration_coherence(provider: MarketDataProvider) -> list[str]:
    """Tier 1. The execution capabilities are the only ones with **no required method**
    (`capabilities._METHOD_FOR[LIVE_EXECUTION] is None`), because declaring `LIVE_EXECUTION`
    says "a live order client can be built from this connection", not "I place orders myself" —
    the orders go through `app/engine/broker_protocol.py`. That makes the declaration
    unfalsifiable by the structural check, so its *internal* coherence is checked here instead.

    Both directions are real defects, not tidiness:

      * **execution without an order type.** `plan_order` chooses between market, limit and
        SL-M per signal. A connection that can execute but names no order kind leaves every
        caller to assume; the assumption in this codebase is Kite's, and it would be applied to
        a venue that never agreed to it.
      * **an order type without execution.** `make_broker` gates on `LIVE_EXECUTION` alone. A
        connection declaring `MARKET_ORDERS` and not `LIVE_EXECUTION` reads as capable
        everywhere a human looks and is refused at the one place that decides — which surfaces
        as "the bot silently stopped trading" rather than as a configuration error.
    """
    declared = type(provider).CAPABILITIES
    executes = caps.LIVE_EXECUTION in declared
    order_types = [c for c in _ORDER_TYPE_CAPS if c in declared]
    if executes and not order_types:
        return [f"declares {caps.LIVE_EXECUTION!r} but no order type; callers must not have to "
                f"guess which of {list(_ORDER_TYPE_CAPS)} this venue accepts"]
    if order_types and not executes:
        return [f"declares {order_types} but not {caps.LIVE_EXECUTION!r}; make_broker gates on "
                f"the latter alone, so this connection reads as tradable and is refused"]
    return []


def check_execution_role(case: ConformanceCase) -> list[str]:
    """Tier 2. What an executing connection must be able to answer *before* an order exists.

    No order is placed here and none should be — a conformance run that trades is a conformance
    run nobody dares execute. These are the two reads the order path makes on the connection
    itself, and each has a live incident behind it.

    **A credential.** `connection_for(provider).token_source()` is what seeds the order client.
    A provider declaring `LIVE_EXECUTION` without an `access_token` attribute yields a source
    that returns `None` forever: `make_broker` builds the client, logs 🔴 LIVE EXECUTION
    ENABLED, and every order is rejected unauthenticated. Nothing in the current suite would
    notice.

    **A real tick.** 2026-07-15: SL-M triggers were rounded to a hardcoded 0.05 grid while LT
    trades in 0.10 steps and MARUTI in whole rupees, and 2,437 stop placements were rejected —
    stops that the operator believed were in place. An executing connection must resolve the
    venue's actual tick, and `case.non_default_tick` is how an adapter proves it reads the
    instrument rather than returning the default. A case that omits it leaves that hole open on
    purpose rather than by accident: the check below says so in its violation text only when the
    connection also has no way to be asked.
    """
    from app.providers.connection import connection_for

    violations = []
    provider = case.provider

    if not hasattr(provider, "access_token"):
        violations.append(
            f"declares {caps.LIVE_EXECUTION!r} but exposes no `access_token`; the order client "
            f"would be seeded with None and every order rejected unauthenticated")
    else:
        token = connection_for(provider).token_source()
        if provider.is_authenticated() and not token:
            violations.append(
                "reports authenticated but the derived connection produces no credential; "
                "the order client cannot authenticate what the data feed already has")

    tick_of = getattr(provider, "tick_size", None)
    if not callable(tick_of):
        violations.append(
            "declares execution but cannot resolve a tick size; SL-M triggers would be rounded "
            "to a hardcoded grid, which is the 2026-07-15 naked-stop incident")
        return violations

    if case.non_default_tick is None:
        violations.append(
            "declares execution but its conformance case names no non-default-tick instrument, "
            "so `tick_size` is never distinguished from returning the 0.05 constant")
    else:
        symbol, exchange, expected = case.non_default_tick
        try:
            actual = tick_of(symbol, exchange)
        except Exception as e:                        # noqa: BLE001
            violations.append(f"tick_size({symbol!r}, {exchange!r}) raised {type(e).__name__}: {e}")
            return violations
        if actual != expected:
            violations.append(
                f"tick_size({symbol!r}, {exchange!r}) answered {actual!r}, expected {expected!r} "
                f"— the instrument's real tick is being replaced by a default, so stop triggers "
                f"round onto a grid this venue does not trade on")
    return violations


def check_simulated_clock(case: ConformanceCase) -> list[str]:
    """An advanceable clock must actually advance, or a replay/backtest never moves."""
    p = case.provider
    before = p.now()
    moved = p.advance()
    after = p.now()
    if moved and after <= before:
        return [f"advance() reported progress but now() went {before} -> {after}"]
    if not moved and after != before:
        return [f"advance() reported exhaustion but now() still moved {before} -> {after}"]
    if not moved:
        # A clock that refuses to advance is legitimate only at the end of the series. An
        # adapter whose `advance()` always returns False satisfied the first clause vacuously,
        # so ask it to prove it is exhausted rather than stuck: a fresh connection must move.
        return ["advance() reported no progress on a connection that has not been driven to "
                "the end of its series — a permanently stuck clock never replays anything"]
    return []


CAPABILITY_OBLIGATIONS: dict[str, Callable[[ConformanceCase], list[str]]] = {
    caps.HISTORICAL_DATA: check_historical_data,
    caps.LIVE_QUOTES: check_live_quotes,
    caps.OPTION_CHAIN: check_option_chain,
    caps.FUTURES_QUOTES: check_futures_quotes,
    caps.ACCOUNT_FUNDS: check_account_reads,
    caps.LIVE_EXECUTION: check_execution_role,
    caps.SIMULATED_CLOCK: check_simulated_clock,
}


def conform(case: ConformanceCase) -> list[str]:
    """Every violation this connection commits, tier 1 then tier 2.

    Returns rather than asserts so the suite can prove both directions with one body of code.
    Account reads run last: `break_transport` is deliberately destructive to the connection.
    """
    violations = [f"base contract: {v}"
                  for v in check_signature_conformance(case.provider)]
    violations += [f"base contract: {v}" for v in check_refusal_vocabulary(case)]
    violations += [f"identity: {v}" for v in check_instrument_identity(case)]
    violations += [f"declaration: {v}"
                   for v in check_declaration_matches_implementation(case.provider)]
    violations += [f"declaration: {v}" for v in check_no_undeclared_working_capability(case)]
    violations += [f"declaration: {v}" for v in check_undeclared_options_are_refused(case)]
    violations += [f"declaration: {v}"
                   for v in check_execution_declaration_coherence(case.provider)]
    declared = type(case.provider).CAPABILITIES
    for cap, check in CAPABILITY_OBLIGATIONS.items():
        if cap in declared and check is not check_account_reads:
            violations += [f"{cap}: {v}" for v in check(case)]

    # Everything below breaks the transport, so it runs last and never before a healthy read.
    # The account gate asks whether ANY account capability is declared: gating it on
    # ACCOUNT_FUNDS alone meant a connection declaring only ACCOUNT_POSITIONS got no account
    # checking at all — and `account_positions` returning `[]` on a failed read is audit C4,
    # the bot trading on top of the owner's own book.
    if any(cap in declared for cap, _, _ in _ACCOUNT_PROBE):
        violations += [f"account: {v}" for v in check_account_reads(case)]
    violations += [f"transport: {v}" for v in check_market_data_under_failure(case)]
    return violations
