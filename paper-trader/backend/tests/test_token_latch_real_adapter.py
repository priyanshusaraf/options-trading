"""F-02: the token latch must not declare recovery on a `None` quote.

`_token_sweep_suspended()` probes one instrument with `get_ltp()` while latched. The
existing suppression tests (`test_token_storm_suppression.py`) drive it with a fake whose
`get_ltp()` RAISES on a dead token — so the `except` arm keeps the latch and the test
passes. The real adapter does not behave that way: `KiteProvider.get_ltp()` catches the
expired-token exception, logs it and returns `None`. Nothing is raised, so the latch was
cleared and the whole book resumed hammering `historical_data` with a dead token — the
exact storm the latch exists to stop.

These tests go through the concrete `KiteProvider.get_ltp()` failure semantics rather than
a fake that raises differently. `None` is absence of evidence, not evidence of recovery:
only a positive quote clears the latch.
"""
from __future__ import annotations

import datetime as dt

from app.core.instruments import get_instrument
from app.providers.kite import KiteProvider

AUTH_FAILURE = "Incorrect `api_key` or `access_token`."
NIFTY_DUMP = [{"instrument_token": 256265, "tradingsymbol": "NIFTY 50",
               "name": "NIFTY 50", "instrument_type": "EQ", "expiry": "",
               "strike": 0.0, "lot_size": 0, "tick_size": 0.05}]


class _Kite:
    """A KiteConnect double whose quote endpoint can be failed on its own."""

    def __init__(self, *, ltp_fails: bool = False, last_price: float | None = 24000.0,
                 dump: list | None = None) -> None:
        self.ltp_fails = ltp_fails
        self.last_price = last_price
        self.dump = NIFTY_DUMP if dump is None else dump
        self.ltp_calls = 0

    def instruments(self, exchange):
        return self.dump if exchange == "NSE" else []

    def ltp(self, keys):
        self.ltp_calls += 1
        if self.ltp_fails:
            raise Exception(AUTH_FAILURE)
        if self.last_price is None:
            return {}
        return {k: {"last_price": self.last_price} for k in keys}


class _NoThrottle:
    def wait(self, category):
        return None


def _provider(**kw) -> KiteProvider:
    from app.core.logging import WarnGate

    p = KiteProvider.__new__(KiteProvider)
    p.kite = _Kite(**kw)
    p.s = None
    p.api_key = p.api_secret = p.access_token = "fake"
    p._dumps, p._fut_cache, p._tick_cache = {}, {}, {}
    p._throttle = _NoThrottle()
    p._warn = WarnGate()
    p.now = lambda: dt.datetime(2026, 8, 9, 11, 0)
    p.is_tradable_now = lambda inst: True
    return p


def _runner():
    from app.db.session import init_db
    from app.engine.runner import EngineRunner

    init_db(reset=True)
    return EngineRunner(owner_id="owner", broker_account_id="account.default")


NIFTY = get_instrument("NIFTY")


# ── the adapter's actual failure semantics (the premise of the bug) ──────────

def test_the_real_adapter_returns_none_on_an_expired_token_rather_than_raising():
    """If this ever starts raising, the latch's `except` arm becomes reachable and the
    fake-based suppression tests stop lying. Until then, `None` is what the latch sees."""
    assert _provider(ltp_fails=True).get_ltp(NIFTY) is None


# ── the latch ────────────────────────────────────────────────────────────────

def test_a_none_probe_does_not_clear_the_latch():
    r = _runner()
    try:
        prov = _provider(ltp_fails=True)
        r.provider = prov
        r.enabled = {"NIFTY"}
        r._mark_token_bad(prov.now())

        assert r._token_sweep_suspended() is True, (
            "a probe that returned no quote is not proof of re-auth")
        assert r._is_token_probably_bad(prov.now()) is True, (
            "the latch must survive a None probe or the whole book resumes hammering")
        assert prov.kite.ltp_calls == 1, "the probe must still cost exactly one call"
    finally:
        _close(r)


def test_an_unresolvable_probe_instrument_does_not_clear_the_latch_either():
    """`get_ltp` returns `None` before any transport call when no quote key resolves —
    a commodity whose near future cannot be found in an unreadable dump. Same absence of
    evidence, and the latch must not read it as recovery."""
    r = _runner()
    try:
        prov = _provider()
        prov.resolve_underlying = lambda inst: None   # no near future in the dump
        r.provider = prov
        r.enabled = {"NIFTY"}
        r._mark_token_bad(prov.now())

        assert r._token_sweep_suspended() is True
        assert r._is_token_probably_bad(prov.now()) is True
    finally:
        _close(r)


def test_an_empty_quote_payload_does_not_clear_the_latch():
    """Kite answers a live-but-unauthorised session with a payload missing the key."""
    r = _runner()
    try:
        prov = _provider(last_price=None)
        r.provider = prov
        r.enabled = {"NIFTY"}
        r._mark_token_bad(prov.now())

        assert r._token_sweep_suspended() is True
        assert r._is_token_probably_bad(prov.now()) is True
    finally:
        _close(r)


def test_a_positive_quote_still_clears_the_latch_and_resumes_the_sweep():
    """The fix must not strand the engine: a real re-auth still recovers on the next probe."""
    r = _runner()
    try:
        prov = _provider(last_price=24187.5)
        r.provider = prov
        r.enabled = {"NIFTY"}
        r._mark_token_bad(prov.now())

        assert r._token_sweep_suspended() is False
        assert r._is_token_probably_bad(prov.now()) is False
    finally:
        _close(r)


def _close(r) -> None:
    try:
        r.broker.s.close()
    except Exception:
        pass
