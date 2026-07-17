"""Autopsy rank 5: ~3,800 unbacked-off 'Incorrect api_key or access_token'
lines/morning. A known-bad token should short-circuit the per-instrument sweep
to one probe/loop instead of hammering every instrument every cycle."""
import datetime as dt

from app.db.session import init_db
from app.engine.runner import EngineRunner


def _runner():
    init_db(reset=True)
    return EngineRunner()


def test_token_latch_starts_clear():
    r = _runner()
    assert r._is_token_probably_bad(dt.datetime.now()) is False


def test_token_latch_engages_and_expires():
    r = _runner()
    now = dt.datetime.now()
    r._mark_token_bad(now)
    assert r._is_token_probably_bad(now) is True
    # a fresh success clears the latch immediately (mirrors the proven
    # margins()-suppression pattern's "recovered" behavior)
    r._mark_token_ok()
    assert r._is_token_probably_bad(now) is False


def test_token_latch_expires_after_cooldown():
    r = _runner()
    now = dt.datetime.now()
    r._mark_token_bad(now, cooldown_seconds=20.0)
    assert r._is_token_probably_bad(now + dt.timedelta(seconds=19)) is True
    assert r._is_token_probably_bad(now + dt.timedelta(seconds=21)) is False


def test_auth_error_engages_latch_and_sweep_stops_hammering_every_instrument():
    """The whole point: with a dead token, one loop must make ~1 provider call,
    not one per enabled instrument."""
    r = _runner()
    calls = []

    class _DeadTokenProvider:
        def now(self):
            return dt.datetime(2026, 7, 17, 10, 0)

        def is_tradable_now(self, inst):
            return True

        def get_candles(self, inst, interval, days):
            calls.append(("candles", inst.key))
            raise Exception("Incorrect `api_key` or `access_token`.")

        def get_ltp(self, inst):
            calls.append(("ltp", inst.key))
            raise Exception("Incorrect `api_key` or `access_token`.")

    r.provider = _DeadTokenProvider()
    r.enabled = {"NIFTY", "GOLDM", "SILVERM", "CRUDEOIL"}

    r.scan_signals()          # first sweep: discovers the bad token, latches
    first_sweep = len(calls)
    calls.clear()
    r.scan_signals()          # second sweep: must be suppressed to a single probe
    assert len(calls) <= 1, f"latched sweep still made {len(calls)} provider calls"
    assert first_sweep >= 1


def test_recovered_token_clears_latch_and_resumes_full_sweep():
    r = _runner()
    state = {"bad": True}
    calls = []

    class _FlakyProvider:
        def now(self):
            return dt.datetime(2026, 7, 17, 10, 0)

        def is_tradable_now(self, inst):
            return True

        def get_candles(self, inst, interval, days):
            calls.append(("candles", inst.key))
            if state["bad"]:
                raise Exception("Incorrect `api_key` or `access_token`.")
            return []

        def get_ltp(self, inst):
            if state["bad"]:
                raise Exception("Incorrect `api_key` or `access_token`.")
            return 100.0

    r.provider = _FlakyProvider()
    r.enabled = {"NIFTY", "GOLDM"}
    r.scan_signals()
    assert r._is_token_probably_bad(r.provider.now()) is True

    state["bad"] = False      # owner re-authed via Connect Kite
    calls.clear()
    r.scan_signals()          # the probe succeeds -> latch clears, sweep resumes
    assert r._is_token_probably_bad(r.provider.now()) is False
    assert len(calls) >= 1, "sweep should resume fetching candles once recovered"
