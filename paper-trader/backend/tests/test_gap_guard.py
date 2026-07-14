"""Fix D (2026-07-14): Nifty-50 opening-gap guard. When the index opens ≥ gap_pct
away from the prior close, the first hour is erratic — block ALL new entries until a
resume time (default 11:00 IST). Exits/management are unaffected; this gates entries
only. Pure helper here; the runner supplies the index open + prior close."""
import datetime as dt

from app.engine.risk_controls import gap_halt_active


def _now(hh, mm):
    return dt.datetime(2026, 7, 14, hh, mm)


def test_big_gap_before_resume_blocks():
    # 0.8% gap up, 09:45 (< 11:00) → blocked
    assert gap_halt_active(_now(9, 45), 24_192.0, 24_000.0, gap_pct=0.6, resume_hhmm="11:00")


def test_big_gap_down_also_blocks():
    assert gap_halt_active(_now(10, 30), 23_760.0, 24_000.0, gap_pct=0.6, resume_hhmm="11:00")


def test_small_gap_does_not_block():
    # 0.3% gap < 0.6% threshold → trade normally
    assert not gap_halt_active(_now(9, 20), 24_072.0, 24_000.0, gap_pct=0.6, resume_hhmm="11:00")


def test_big_gap_after_resume_does_not_block():
    # gap was big but it's 11:05 — the erratic window has passed
    assert not gap_halt_active(_now(11, 5), 24_300.0, 24_000.0, gap_pct=0.6, resume_hhmm="11:00")


def test_disabled_when_pct_zero():
    assert not gap_halt_active(_now(9, 30), 25_000.0, 24_000.0, gap_pct=0.0, resume_hhmm="11:00")


def test_missing_data_fails_open():
    # no index read → don't block (a data hiccup must not halt the whole book)
    assert not gap_halt_active(_now(9, 30), None, 24_000.0, gap_pct=0.6, resume_hhmm="11:00")
    assert not gap_halt_active(_now(9, 30), 24_200.0, 0.0, gap_pct=0.6, resume_hhmm="11:00")


def test_exact_threshold_blocks():
    # exactly 0.6% counts as a gap (>=)
    assert gap_halt_active(_now(9, 30), 24_144.0, 24_000.0, gap_pct=0.6, resume_hhmm="11:00")


# ── runner glue ───────────────────────────────────────────────────────────────

def _runner():
    from app.db.session import init_db
    from app.engine.runner import EngineRunner
    init_db(reset=True)
    r = EngineRunner()
    r.params["gap_guard_enabled"] = True
    r.params["gap_guard_pct"] = 0.6
    r.params["gap_guard_resume"] = "11:00"
    return r


def test_runner_gap_guard_active_before_resume_only():
    r = _runner()
    r._index_open_prevclose = lambda now: (24_192.0, 24_000.0)   # 0.8% gap up
    assert r._gap_guard_active(_now(9, 45)) is True
    assert r._gap_guard_active(_now(11, 5)) is False             # window passed


def test_runner_gap_guard_respects_enabled_flag():
    r = _runner()
    r.params["gap_guard_enabled"] = False
    r._index_open_prevclose = lambda now: (24_192.0, 24_000.0)
    assert r._gap_guard_active(_now(9, 45)) is False


class _CandleStub:
    def __init__(self, ts, open_, close):
        self.ts, self.open, self.close = ts, open_, close


class _KiteCandleProvider:
    """Non-mock provider stub that serves 3 daily candles and counts get_candles hits."""
    name = "kite"

    def __init__(self):
        self.calls = 0

    def get_candles(self, inst, interval, days):
        self.calls += 1
        d = _now(9, 30).date()
        return [_CandleStub(dt.datetime(2026, 7, 12), 23_900.0, 23_950.0),
                _CandleStub(dt.datetime(2026, 7, 13), 23_950.0, 24_000.0),   # prior close 24000
                _CandleStub(dt.datetime(d.year, d.month, d.day), 24_192.0, 24_100.0)]  # today open 24192


def test_runner_index_readout_is_cached_per_day():
    r = _runner()
    r.provider = _KiteCandleProvider()          # swap the runner's ref (not the singleton)
    assert r._index_open_prevclose(_now(9, 30)) == (24_192.0, 24_000.0)
    assert r._index_open_prevclose(_now(10, 0)) == (24_192.0, 24_000.0)
    assert r.provider.calls == 1                 # second call served from the per-day cache
