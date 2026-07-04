"""Schema additions + live-interval config helpers."""
from app.db.models import InstrumentState, Position, BacktestResult
from app.core import config


def test_instrument_state_has_interval_defaults():
    cols = InstrumentState.__table__.columns
    assert "live_interval" in cols
    assert "entries_blocked" in cols


def test_position_has_trailing_and_freshness_columns():
    cols = Position.__table__.columns
    assert "last_mark_time" in cols
    assert "high_water_premium" in cols


def test_backtest_result_has_cache_columns():
    cols = BacktestResult.__table__.columns
    for c in ("params_hash", "last_candle_ts", "schema_version", "from_cache", "computed_at"):
        assert c in cols


def test_live_intervals_and_normalize():
    assert config.LIVE_INTERVALS == ("5minute", "15minute", "30minute", "60minute")
    assert config.DEFAULT_LIVE_INTERVAL == "15minute"
    assert config.normalize_live_interval("60minute") == "60minute"
    assert config.normalize_live_interval("1minute") == "15minute"   # unsupported -> default
    assert config.normalize_live_interval("") == "15minute"


def test_cadence_and_trail_settings_present():
    s = config.get_settings()
    assert s.position_loop_seconds > 0 and s.signal_loop_seconds > 0
    assert s.max_stale_seconds >= 1
    # trailing-stop knobs (aggressive schedule: entry 400 -> SL 410/440/480…, no cap)
    assert s.trail_enabled in (True, False)
    assert s.trail_trigger_pct > 0 and s.trail_first_step_lock_pct > 0 and s.trail_step_lock_pct > 0
