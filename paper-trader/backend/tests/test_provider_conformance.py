"""One semantic contract, every adapter run through it, and proof it can fail one.

`test_provider_capabilities.py` checks that declarations are structurally honest. This file
checks that the behaviour behind them is real. The difference is not academic — the three
adapters in `_LIARS` below lie in the three ways that actually cost money, and every one of them
passes the structural check clean.

Kite is exercised through a fake at the **KiteConnect boundary**, not by stubbing the provider's
own methods, so the adapter's real resolution, dump-normalisation, chain-building and refusal
logic all run. That is the level a conformance suite has to sit at: stubbing `_instruments` or
`get_ltp` would test the fake.

What this cannot prove is that Zerodha's live endpoints behave as the fake does. That is
production verification against a real session, and it is not a unit test.
"""
from __future__ import annotations

import datetime as dt
import inspect
import json

import pytest

from app.core.instruments import Instrument, get_instrument
from app.providers import capabilities as caps
from app.providers.base import Candle, MarketDataProvider, OptionChain, OptionQuote
from app.providers.kite import KiteProvider
from app.providers.mock import MockProvider
from app.providers.instrument_resolver import ResolvedInstrument
from app.providers.replay import ReplayProvider
from tests.provider_conformance import (ConformanceCase, check_declaration_matches_implementation,
                                        check_signature_conformance, conform)

TODAY = dt.date.today()
NEAR_EXPIRY = TODAY + dt.timedelta(days=14)
FAR_EXPIRY = TODAY + dt.timedelta(days=45)
ABSENT_EXPIRY = TODAY + dt.timedelta(days=300)      # no contract exists this far out


# ── the fake Kite transport ──────────────────────────────────────────────────

class _FakeKite:
    """A KiteConnect-shaped double. Every response is the shape Kite documents."""

    def __init__(self) -> None:
        self.broken = False

    def _guard(self):
        if self.broken:
            raise ConnectionError("Incorrect `api_key` or `access_token`.")

    def profile(self) -> dict:
        self._guard()
        return {"user_id": "AB1234"}

    def instruments(self, exchange: str) -> list[dict]:
        self._guard()
        if exchange == "NSE":
            return [{"instrument_token": 256265, "tradingsymbol": "NIFTY 50",
                     "name": "NIFTY 50", "instrument_type": "EQ", "expiry": "",
                     "strike": 0.0, "lot_size": 0, "tick_size": 0.05}]
        if exchange == "NFO":
            rows = [{"instrument_token": 111, "tradingsymbol": "NIFTY26AUGFUT",
                     "name": "NIFTY", "instrument_type": "FUT", "expiry": NEAR_EXPIRY,
                     "strike": 0.0, "lot_size": 75, "tick_size": 0.05},
                    {"instrument_token": 112, "tradingsymbol": "NIFTY26SEPFUT",
                     "name": "NIFTY", "instrument_type": "FUT", "expiry": FAR_EXPIRY,
                     "strike": 0.0, "lot_size": 75, "tick_size": 0.05}]
            token = 1000
            for strike in range(23800, 24251, 50):
                for kind in ("CE", "PE"):
                    token += 1
                    rows.append({"instrument_token": token,
                                 "tradingsymbol": f"NIFTY26AUG{strike}{kind}",
                                 "name": "NIFTY", "instrument_type": kind,
                                 "expiry": NEAR_EXPIRY, "strike": float(strike),
                                 "lot_size": 75, "tick_size": 0.05})
            return rows
        if exchange == "MCX":
            rows = [{"instrument_token": 211, "tradingsymbol": "GOLDM26AUGFUT",
                     "name": "GOLDM", "instrument_type": "FUT", "expiry": NEAR_EXPIRY,
                     "strike": 0.0, "lot_size": 10, "tick_size": 1.0},
                    {"instrument_token": 212, "tradingsymbol": "GOLDM26SEPFUT",
                     "name": "GOLDM", "instrument_type": "FUT", "expiry": FAR_EXPIRY,
                     "strike": 0.0, "lot_size": 10, "tick_size": 1.0}]
            token = 2000
            for strike in range(71800, 72251, 50):
                for kind in ("CE", "PE"):
                    token += 1
                    rows.append({"instrument_token": token,
                                 "tradingsymbol": f"GOLDM26AUG{strike}{kind}",
                                 "name": "GOLDM", "instrument_type": kind,
                                 "expiry": NEAR_EXPIRY, "strike": float(strike),
                                 # Kite reports lot_size=1 for MCX option rows; the adapter must
                                 # substitute the configured contract unit, and this is the row
                                 # shape that makes it do so.
                                 "lot_size": 1, "tick_size": 1.0})
            return rows
        return []

    def _prices(self) -> dict[str, float]:
        """Exactly the keys Zerodha would recognise, and no others.

        Answering an unknown key is the one thing a quote double must not do. An earlier version
        priced anything ending in `FUT`, which meant `NSE:NIFTY26AUGFUT` — a key Kite does not
        have, built from the wrong exchange — came back with a price, and the wrong-exchange
        defect this file exists to pin could not have reddened a single guard.
        """
        prices = {"NSE:NIFTY 50": 24010.5,
                  # a real basis, deliberately not spot — the whole point of FUTURES_QUOTES
                  "NFO:NIFTY26AUGFUT": 24075.0,
                  "NFO:NIFTY26SEPFUT": 24140.0,
                  "MCX:GOLDM26AUGFUT": 72180.0,
                  "MCX:GOLDM26SEPFUT": 72410.0}
        for segment, premium in (("NFO", 132.25), ("MCX", 940.0)):
            for row in self.instruments(segment):
                if row["instrument_type"] in ("CE", "PE"):
                    prices[f"{segment}:{row['tradingsymbol']}"] = premium
        return prices

    def ltp(self, keys: list[str]) -> dict:
        self._guard()
        prices = self._prices()
        return {k: {"last_price": prices[k]} for k in keys if k in prices}

    def quote(self, keys: list[str]) -> dict:
        self._guard()
        prices = self._prices()
        # Five depth levels, as Kite sends. One level made the crossed-book obligation read
        # only the top of book, which is the level least likely to be wrong.
        return {k: {"last_price": prices[k], "volume": 41200, "oi": 90300,
                    "depth": {"buy": [{"price": prices[k] - 0.25 * (n + 1), "quantity": 75}
                                      for n in range(5)],
                              "sell": [{"price": prices[k] + 0.25 * (n + 1), "quantity": 75}
                                       for n in range(5)]}}
                for k in keys if k in prices}

    def historical_data(self, token, from_date, to_date, interval) -> list[dict]:
        self._guard()
        # Real Kite returns +05:30-AWARE datetimes, and `kite.py` strips the tz to keep the IST
        # wall time. Returning naive stamps here would exercise that `.replace(tzinfo=None)`
        # vacuously — and the contract's naive-IST obligation would never once have observed
        # Kite's actual behaviour, only the double's.
        ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
        start = dt.datetime.combine(to_date.date() - dt.timedelta(days=2),
                                    dt.time(9, 15), tzinfo=ist)
        bars = []
        for i in range(26):                       # 25 completed + the still-forming one
            base = 24000 + i
            bars.append({"date": start + dt.timedelta(minutes=15 * i),
                         "open": float(base), "high": float(base + 6),
                         "low": float(base - 4), "close": float(base + 2),
                         "volume": 15000 + i})
        return bars

    def margins(self) -> dict:
        self._guard()
        return {"equity": {"available": {"live_balance": 250000.0}, "net": 261500.0}}

    def positions(self) -> dict:
        self._guard()
        return {"net": [{"tradingsymbol": "NIFTY26AUG24000CE", "quantity": 75,
                         "exchange": "NFO", "product": "NRML"}]}

    def order_margins(self, orders: list[dict]) -> list[dict]:
        self._guard()
        return [{"total": 48250.0} for _ in orders]


class _NoThrottle:
    """Kite's rate limiter sleeps ~1s between quote calls. That is transport plumbing, not
    adapter semantics, and leaving it in would make this suite sleep for a minute."""

    def wait(self, category: str) -> None:
        return None


def _kite_provider() -> tuple[KiteProvider, _FakeKite]:
    from app.core.logging import WarnGate

    p = KiteProvider.__new__(KiteProvider)
    fake = _FakeKite()
    p.kite = fake
    p.s = None
    p.api_key = p.api_secret = "fake"
    p.access_token = "fake"
    p._dumps = {}
    p._fut_cache = {}
    p._tick_cache = {}
    p._throttle = _NoThrottle()
    p._warn = WarnGate()
    return p, fake


# ── the cases: one per adapter, and no adapter may escape ────────────────────

def _replay_session(tmp_path) -> str:
    base = dt.datetime(2026, 8, 3, 9, 15)
    rows = {"NIFTY": [{"ts": (base + dt.timedelta(minutes=15 * i)).isoformat(),
                       "open": 24000.0 + i, "high": 24006.0 + i, "low": 23996.0 + i,
                       "close": 24002.0 + i, "volume": 15000 + i} for i in range(12)]}
    path = tmp_path / "session.json"
    path.write_text(json.dumps(rows))
    return str(path)


@pytest.fixture
def nifty() -> Instrument:
    return get_instrument("NIFTY")


@pytest.fixture
def mock_case(nifty) -> ConformanceCase:
    p = MockProvider()
    # The mock runs its own simulated clock (a 2025 session), so "already expired" has to be
    # measured against THAT clock. Reading it off the wall clock is how the first draft of this
    # fixture passed a contract the provider was in fact still violating.
    return ConformanceCase(provider=p, instrument=nifty, min_bars=50,
                           priceable_expiry=p.now().date() + dt.timedelta(days=14),
                           settled_expiry=p.now().date() - dt.timedelta(days=1),
                           notes={"unlisted": "a synthetic market carries every FUTURE expiry, "
                                              "so it has no unlisted series to refuse; the only "
                                              "refusal it can genuinely make is a settled one"})


@pytest.fixture
def replay_case(tmp_path, nifty) -> ConformanceCase:
    p = ReplayProvider(_replay_session(tmp_path))
    for _ in range(6):
        p.advance()
    return ConformanceCase(provider=p, instrument=nifty, min_bars=5,
                           unlisted_expiry=ABSENT_EXPIRY,
                           notes={"settled": "a recording has no futures feed at all, so both "
                                             "refusals are the same one line"})


@pytest.fixture
def kite_case(nifty) -> ConformanceCase:
    p, fake = _kite_provider()
    return ConformanceCase(provider=p, instrument=nifty, min_bars=20,
                           priceable_expiry=NEAR_EXPIRY,
                           settled_expiry=TODAY - dt.timedelta(days=30),
                           unlisted_expiry=ABSENT_EXPIRY,
                           margin_probe_order={"exchange": "NFO", "tradingsymbol": "NIFTY26AUGFUT",
                                               "transaction_type": "BUY", "variety": "regular",
                                               "product": "NRML", "order_type": "MARKET",
                                               "quantity": 75},
                           break_transport=lambda: setattr(fake, "broken", True))


@pytest.fixture
def kite_mcx_case() -> ConformanceCase:
    """The same adapter against an MCX instrument, and this is not redundancy.

    `segment == spot_exchange` on MCX and differs on NSE. That is exactly why Kite searching the
    cash exchange for futures rows was invisible for a year of commodity tests and wrong for
    every index future. One instrument per adapter would have let the mirror-image defect — an
    adapter correct on NSE and broken on MCX — through just as quietly.
    """
    p, fake = _kite_provider()
    return ConformanceCase(provider=p, instrument=get_instrument("GOLDM"), min_bars=20,
                           priceable_expiry=NEAR_EXPIRY, unlisted_expiry=ABSENT_EXPIRY,
                           expects_basis=False,
                           break_transport=lambda: setattr(fake, "broken", True))


# One entry per adapter CLASS; extra cases exercise the same class from other angles.
CASE_FIXTURES = {MockProvider: "mock_case", ReplayProvider: "replay_case",
                 KiteProvider: "kite_case"}
EXTRA_CASES = ["kite_mcx_case"]


# ── 1. every adapter satisfies the whole contract ────────────────────────────

@pytest.mark.parametrize("fixture_name", sorted(CASE_FIXTURES.values()) + EXTRA_CASES)
def test_adapter_satisfies_the_semantic_contract(fixture_name, request):
    """The contract, in full, against every adapter that exists.

    A violation here is not a test-maintenance chore. Each obligation names a concrete way a
    connection can look healthy while producing wrong prices, wrong sizes or a wrong view of
    the account.
    """
    case: ConformanceCase = request.getfixturevalue(fixture_name)
    violations = conform(case)
    assert not violations, (
        f"{case.name} violates the provider contract:\n  " + "\n  ".join(violations))


def test_no_adapter_can_exist_without_a_conformance_case():
    """A new adapter with no case would pass this file by being absent from it.

    That is the whole failure mode: Upstox lands, the suite stays green because it never runs,
    and 'both providers pass conformance' becomes a sentence rather than a fact.
    """
    # Imported by enumeration, not by a hand-written list. A hardcoded list passes vacuously on
    # exactly the adapter it was written for: a new `app/providers/upstox.py` that no test
    # imports never becomes a `__subclasses__` entry, so the guard would stay green while the
    # adapter it exists to catch went unchecked.
    import importlib
    import pkgutil

    import app.providers
    for mod in pkgutil.iter_modules(app.providers.__path__):
        importlib.import_module(f"app.providers.{mod.name}")

    subclasses = {c for c in _all_subclasses(MarketDataProvider)
                  if not inspect.isabstract(c) and c.__module__.startswith("app.providers.")}
    missing = sorted(c.__name__ for c in subclasses if c not in CASE_FIXTURES)
    assert not missing, (
        f"these adapters have no conformance case: {missing}. Add one to CASE_FIXTURES — "
        f"an adapter that is not run through the contract has not passed it.")


def _all_subclasses(cls) -> set[type]:
    out = set()
    for sub in cls.__subclasses__():
        out.add(sub)
        out |= _all_subclasses(sub)
    return out


# ── 2. the contract must be able to fail an adapter ──────────────────────────
#
# Without this half, a green conformance suite is indistinguishable from a suite that checks
# nothing. Each liar breaks exactly one obligation and must be caught by exactly that one.

class _ConformantBase(MarketDataProvider):
    """A minimal adapter that satisfies the contract, so each liar below differs in one way."""

    name = "control"
    CAPABILITIES = frozenset({caps.LIVE_QUOTES, caps.HISTORICAL_DATA})

    def is_authenticated(self) -> bool:
        return True

    def get_ltp(self, inst) -> float | None:
        return 24010.5

    def get_candles(self, inst, interval, days) -> list[Candle]:
        base = dt.datetime(2026, 8, 3, 9, 15)
        return [Candle(ts=base + dt.timedelta(minutes=15 * i), open=24000.0 + i,
                       high=24006.0 + i, low=23996.0 + i, close=24002.0 + i, volume=1000)
                for i in range(10)]

    def get_option_chain(self, inst) -> OptionChain | None:
        return None

    def option_ltp(self, inst, tradingsymbol, strike, expiry, option_type) -> float | None:
        return None


class _StubFunds(_ConformantBase):
    """Declares ACCOUNT_FUNDS with a real override that always refuses."""
    name = "liar-stub-funds"
    CAPABILITIES = _ConformantBase.CAPABILITIES | {caps.ACCOUNT_FUNDS}

    def account_funds(self) -> dict | None:
        return None


class _BackwardsCandles(_ConformantBase):
    """Newest-first bars with an incoherent bar — every indicator on the frame is wrong."""
    name = "liar-candles"

    def get_candles(self, inst, interval, days) -> list[Candle]:
        base = dt.datetime(2026, 8, 3, 9, 15)
        return [Candle(ts=base + dt.timedelta(minutes=15), open=101, high=99, low=105,
                       close=100),
                Candle(ts=base, open=100, high=101, low=99, close=100.5)]


class _SpotFallbackFutures(_ConformantBase):
    """Declares FUTURES_QUOTES and marks every expiry to spot."""
    name = "liar-futures"
    CAPABILITIES = _ConformantBase.CAPABILITIES | {caps.FUTURES_QUOTES}

    def get_futures_ltp(self, inst, expiry) -> float | None:
        return self.get_ltp(inst)


class _NarrowedSignature(_ConformantBase):
    """Overrides `option_ltp` with a signature the base's own `live_snapshot` cannot call."""
    name = "liar-signature"

    def option_ltp(self, tradingsymbol) -> float | None:      # type: ignore[override]
        return None


class _WrongRefusalType(_ConformantBase):
    """Refuses an option chain with `[]`, which survives every `if not chain:` site."""
    name = "liar-refusal"

    def get_option_chain(self, inst):
        return []


class _UnderDeclarer(_ConformantBase):
    """A *correct* futures implementation that is never declared — working behaviour, fenced
    off. It must price the contract it has and refuse the one it does not; a broken
    implementation is a different defect and must not be reported as this one."""
    name = "liar-underdeclare"

    def front_month_expiry(self, inst):
        return NEAR_EXPIRY

    def get_futures_ltp(self, inst, expiry) -> float | None:
        return 24075.0 if expiry == NEAR_EXPIRY else None


class _TzAwareBars(_ConformantBase):
    """Returns tz-aware stamps while every shipping adapter returns naive IST."""
    name = "liar-tz"

    def get_candles(self, inst, interval, days) -> list[Candle]:
        tz = dt.timezone(dt.timedelta(hours=5, minutes=30))
        return [Candle(ts=b.ts.replace(tzinfo=tz), open=b.open, high=b.high, low=b.low,
                       close=b.close, volume=b.volume)
                for b in super().get_candles(inst, interval, days)]


class _WrongInterval(_ConformantBase):
    """Serves DAILY bars for a 15-minute request — every indicator's horizon silently wrong."""
    name = "liar-interval"

    def get_candles(self, inst, interval, days) -> list[Candle]:
        base = dt.datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        return [Candle(ts=base - dt.timedelta(days=6 - i), open=24000.0 + i, high=24006.0 + i,
                       low=23996.0 + i, close=24002.0 + i, volume=1000) for i in range(6)]


class _FormingBar(_ConformantBase):
    """Includes the still-forming candle. Every live signal computed on it repaints."""
    name = "liar-forming"

    def get_candles(self, inst, interval, days) -> list[Candle]:
        now = dt.datetime.now().replace(second=0, microsecond=0)
        return [Candle(ts=now - dt.timedelta(minutes=15 * (9 - i)), open=24000.0 + i,
                       high=24006.0 + i, low=23996.0 + i, close=24002.0 + i, volume=1000)
                for i in range(10)]


class _ThinHistory(_ConformantBase):
    """Answers three bars to a thirty-day request — warmup starves, nothing raises."""
    name = "liar-thin"

    def get_candles(self, inst, interval, days) -> list[Candle]:
        return super().get_candles(inst, interval, days)[:3]


class _StaleUnderFailure(_ConformantBase):
    """Serves its cache when the transport is down, so every read looks healthy forever."""
    name = "liar-stale"

    def __init__(self) -> None:
        self.down = False

    def break_it(self) -> None:
        self.down = True


class _FlatPositionsOnFailure(_ConformantBase):
    """Declares ACCOUNT_POSITIONS — not ACCOUNT_FUNDS — and reports a failed read as flat.

    Audit C4 exactly: `[]` reads as a genuinely flat account, which is how the bot comes to
    trade on top of the owner's own positions. It also pins the account gate itself: while
    `conform` asked only about ACCOUNT_FUNDS, this adapter got no account checking at all.
    """
    name = "liar-flat-positions"
    CAPABILITIES = _ConformantBase.CAPABILITIES | {caps.ACCOUNT_POSITIONS}

    def account_positions(self) -> list[dict] | None:
        return []


class _WrongProvenance(_ConformantBase):
    """Stamps another connection's name on its mapping."""
    name = "liar-provenance"

    def resolve_underlying(self, inst):
        return ResolvedInstrument(canonical_key=inst.key, provider="kite",
                                  symbol="NIFTY 50", exchange="NSE", token=256265)


_LIARS = [
    (_StubFunds, caps.ACCOUNT_FUNDS, "never answers", {}),
    (_BackwardsCandles, caps.HISTORICAL_DATA, "oldest-first", {}),
    (_SpotFallbackFutures, caps.FUTURES_QUOTES, "exactly spot", {}),
    (_NarrowedSignature, "base contract", "cannot accept the base contract's call", {}),
    (_WrongRefusalType, "base contract", "vocabulary is", {}),
    (_UnderDeclarer, "declaration", "does not declare it", {}),
    (_TzAwareBars, caps.HISTORICAL_DATA, "carry tzinfo", {}),
    (_WrongInterval, caps.HISTORICAL_DATA, "spaced", {}),
    (_FormingBar, caps.HISTORICAL_DATA, "has not closed", {}),
    (_ThinHistory, caps.HISTORICAL_DATA, "should serve at least", {"min_bars": 8}),
    (_FlatPositionsOnFailure, "account", "never as an answer", {"break": True}),
    (_WrongProvenance, "identity", "stamped provider", {}),
]


@pytest.mark.parametrize("cls,tier,expected,extra", _LIARS, ids=[c.name for c, _, _, _ in _LIARS])
def test_a_dishonest_adapter_is_caught_by_the_obligation_it_broke(cls, tier, expected, extra,
                                                                  nifty):
    """Right clause AND right cause. Matching only 'some violation' would let a liar be caught
    for an unrelated reason and still read as proof the obligation works."""
    provider = cls()
    kwargs = {k: v for k, v in extra.items() if k != "break"}
    if extra.get("break"):
        kwargs["break_transport"] = lambda: None      # nothing to break; the lie is unconditional
    case = ConformanceCase(provider=provider, instrument=nifty,
                           priceable_expiry=NEAR_EXPIRY, unlisted_expiry=ABSENT_EXPIRY, **kwargs)
    violations = conform(case)
    assert any(expected in v for v in violations), (
        f"{cls.name} broke {tier} but the contract reported: {violations or 'nothing at all'}")


def test_a_stale_cache_served_through_a_dead_transport_is_caught(nifty):
    """The obligation that had no caller at all in the first draft.

    `break_transport` was set on the Kite case and reachable only through the account checks, so
    a data-only connection — which declares no account capability — never had its failure
    behaviour exercised once. A mechanism wired to nothing, inside the guard written to catch
    mechanisms wired to nothing.
    """
    p = _StaleUnderFailure()
    case = ConformanceCase(provider=p, instrument=nifty, break_transport=p.break_it)
    violations = conform(case)
    assert any("with the transport down" in v for v in violations), violations


def test_a_connection_with_account_capabilities_must_expose_a_way_to_break_it(request):
    """Otherwise the C4 obligation is skipped silently, which looks exactly like passing."""
    for fixture_name in sorted(CASE_FIXTURES.values()) + EXTRA_CASES:
        case: ConformanceCase = request.getfixturevalue(fixture_name)
        declared = type(case.provider).CAPABILITIES
        if declared & {caps.ACCOUNT_FUNDS, caps.ACCOUNT_POSITIONS, caps.ACCOUNT_EQUITY,
                       caps.ORDER_MARGIN}:
            assert case.break_transport is not None, (
                f"{fixture_name} declares account capabilities but supplies no break_transport, "
                f"so its failed-read behaviour is never exercised")


def test_the_control_adapter_itself_is_clean(nifty):
    """The liars differ from this by exactly one thing. If the control were already dirty, each
    'the contract caught it' result above would be someone else's violation."""
    case = ConformanceCase(provider=_ConformantBase(), instrument=nifty)
    assert not conform(case), conform(case)


def test_the_structural_check_alone_would_have_passed_every_liar():
    """Why this file exists. The pre-existing honesty check is satisfied by all three of the
    capability liars, because each one *does* override the backing method — it just does not
    honour it. Recorded as an executable statement so the gap cannot silently reappear.
    """
    for cls in (_StubFunds, _BackwardsCandles, _SpotFallbackFutures):
        offenders = []
        for cap in sorted(cls.CAPABILITIES):
            method = caps.BACKING_METHOD.get(cap)
            if method is None:
                continue
            own = getattr(cls, method, None)
            base = getattr(MarketDataProvider, method, None)
            if own is None or (base is not None and own is base):
                offenders.append(cap)
        assert not offenders, (
            f"{cls.name} is now caught structurally; this file's premise has changed")


# ── 3. the two defects the contract found, pinned ────────────────────────────

def test_replay_can_be_asked_for_an_option_price_by_inherited_code(tmp_path, nifty):
    """`MarketDataProvider.live_snapshot` calls `option_ltp` with five arguments on any
    non-equity position. Replay had narrowed it to one, so marking an open option position in a
    replayed session raised TypeError inside the provider — swallowed by the runner into a
    'quote' health failure, leaving the position permanently unmarked. A replay whose whole
    purpose is fidelity to a real day silently stopped reproducing it.
    """
    p = ReplayProvider(_replay_session(tmp_path))
    p.advance()

    class _Pos:
        instrument_key = "NIFTY"
        tradingsymbol = "NIFTY26AUG24000CE"
        strike = 24000.0
        expiry = NEAR_EXPIRY
        option_type = "CE"

    snap = p.live_snapshot([nifty], [_Pos()])
    assert snap["NIFTY"]["option_premium"] is None, "replay has no option feed; it must refuse"
    assert snap["NIFTY"]["spot"] is not None, "the underlying is recorded and must still mark"


def test_replay_refuses_an_option_chain_in_the_contracts_vocabulary(tmp_path, nifty):
    """`[]` is falsy, so it survived every `if not chain:` call site while being the wrong
    type at any site that did anything else with it."""
    p = ReplayProvider(_replay_session(tmp_path))
    assert p.get_option_chain(nifty) is None


def test_the_mock_declares_the_futures_pricing_it_actually_implements():
    """The mock computes a synthetic futures price with a basis that decays to zero at
    settlement — and did not declare FUTURES_QUOTES, so `_process_futures_entries` refused to open
    a position on it. The index-futures segment was fenced off from the only connection on
    which it could be exercised before being switched on for real.
    """
    assert caps.FUTURES_QUOTES in MockProvider.CAPABILITIES
    assert not check_declaration_matches_implementation(MockProvider())


def test_the_mock_refuses_an_expiry_that_has_already_passed(nifty):
    """A contract that has settled cannot be priced. Returning spot for it is the same
    substitution the capability exists to prevent, in a different disguise.

    Measured against the mock's own simulated clock, not the wall clock — they are more than a
    year apart, and using the wrong one silently makes the case untestable.
    """
    p = MockProvider()
    today = p.now().date()
    assert p.get_futures_ltp(nifty, today - dt.timedelta(days=1)) is None
    assert p.get_futures_ltp(nifty, today) is not None, "settlement day still prices, at spot"
    assert p.get_futures_ltp(nifty, today + dt.timedelta(days=14)) is not None


def test_kite_still_prices_the_exact_series_and_refuses_the_others(kite_case):
    """The behaviour the contract must not have disturbed: a dated future prices on its own
    contract at its own basis, not on spot and not on the front month."""
    p, inst = kite_case.provider, kite_case.instrument
    spot = p.get_ltp(inst)
    aug = p.get_futures_ltp(inst, NEAR_EXPIRY)
    sep = p.get_futures_ltp(inst, FAR_EXPIRY)
    assert aug is not None and sep is not None and aug != sep
    assert aug != spot and sep != spot, "a future marked at spot is the failure, not the feature"
    assert p.get_futures_ltp(inst, ABSENT_EXPIRY) is None


def test_the_signature_check_reads_every_adapter_not_just_the_liars(mock_case, kite_case):
    """A guard that only ever runs against purpose-built doubles proves nothing about the
    adapters that ship."""
    assert check_signature_conformance(mock_case.provider) == []
    assert check_signature_conformance(kite_case.provider) == []


def test_the_refusal_vocabulary_does_not_drift_from_the_provider_surface():
    """A third hand-maintained table of the provider surface is a drift hazard.

    `_REFUSAL_VOCABULARY`, `capabilities.BACKING_METHOD` and the base class's own signatures all
    describe the same methods. The failure mode is a new method added to `base.py` with no
    vocabulary row — silently unchecked, and indistinguishable from a checked one.
    """
    from tests.provider_conformance import _REFUSAL_VOCABULARY

    unknown = [m for m in _REFUSAL_VOCABULARY if not hasattr(MarketDataProvider, m)]
    assert not unknown, f"_REFUSAL_VOCABULARY names methods that do not exist: {unknown}"

    backed = {m for m in caps.BACKING_METHOD.values() if m}
    # `get_candles` and `advance` return a list and a bool; they have no refusal *value*, and
    # their obligations are behavioural rather than type-shaped.
    missing = sorted(backed - set(_REFUSAL_VOCABULARY) - {"get_candles", "advance"})
    assert not missing, (
        f"these capability-backing methods have no refusal vocabulary: {missing} — add a row, "
        f"or this contract stops describing the whole provider surface")


def test_the_futures_entry_path_refuses_when_no_contract_can_be_named(monkeypatch):
    """The blocker an independent review found, pinned end to end.

    `_process_futures_entries` read `getattr(inst, "expiry", None) or now.date()`. `Instrument`
    is a frozen dataclass describing the economic underlying and has no `expiry`, so that was
    always *today*. With the mock declaring FUTURES_QUOTES, the gate opened and a NIFTY futures
    position was booked at 24101.45 — **exactly spot**, because at zero days to run the mock's
    basis has converged. Kite, matching expiries exactly, would instead have found no contract
    on all but one day a month.

    The connection is now asked, and its refusal is honoured.
    """
    from app.db.session import init_db
    from app.engine.runner import EngineRunner

    init_db(reset=True)
    r = EngineRunner()
    r.armed = True
    cap = r.broker.capital()
    cap.initial_capital = cap.cash = 1_000_000.0
    r.broker.s.commit()
    try:
        r.publish_signal("NIFTY", r._binding_for("NIFTY"),
                         {"long_entry": True, "short_entry": False, "close": 24_000.0})
        r.params = {**r.params, "index_futures_enabled": True,
                    "index_futures_max_positions": 1,
                    "index_futures_max_margin": 250_000.0,
                    "index_futures_min_margin": 50_000.0}

        monkeypatch.setattr(type(r.provider), "front_month_expiry", lambda self, inst: None)
        r._process_futures_entries(r.provider.now())
        assert [p for p in r.broker.open_positions() if p.segment == "index_futures"] == [], (
            "a connection that cannot name a contract must not open a futures position")
    finally:
        try:
            r.broker.s.close()
        except Exception:
            pass


def test_the_mock_never_prices_its_own_front_month_at_spot():
    """The exact number the review booked a position at. A future with days to run and no basis
    is the underlying substituted for the contract, which is the failure the whole capability
    exists to forbid."""
    p = MockProvider()
    inst = get_instrument("NIFTY")
    front = p.front_month_expiry(inst)
    assert front is not None and front > p.now().date()
    assert p.get_futures_ltp(inst, front) != p.get_ltp(inst)
