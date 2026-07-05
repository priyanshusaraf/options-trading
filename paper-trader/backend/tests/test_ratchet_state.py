"""Pine-parity ratchet math (expanding-z-impulse-v4.pine lines 253-315):
initial ATR stop -> Chandelier after trail_start_r -> MFE floor after
capture_start_r; the stop only ever ratchets in the trade's favour and stop
hits are CLOSE-confirmed (a wick through the stop does not exit)."""
import pandas as pd
import pytest

from app.backtest.ratchet import RatchetState, wilder_atr

RM = {"atr_length": 3, "initial_risk_atr": 1.0, "trail_start_r": 2.0,
      "trail_atr": 1.0, "use_mfe_capture_floor": True,
      "capture_start_r": 1.0, "capture_pct": 0.5}


def test_initial_stop_and_inactive_layers_below_thresholds():
    s = RatchetState("LONG", 100.0, 2.0, RM)          # risk_pts = 1.0*2 = 2
    assert s.stop == pytest.approx(98.0)               # fill - risk_pts
    s.update(high=101.0, low=99.0, close=100.5, current_atr=2.0)  # MFE 1pt = 0.5R
    assert s.stop == pytest.approx(98.0)               # nothing active yet
    assert not s.stop_hit(98.01) and s.stop_hit(98.0)


def test_capture_floor_then_chandelier_activate_and_ratchet():
    s = RatchetState("LONG", 100.0, 2.0, RM)
    s.update(102.5, 100.0, 102.0, 2.0)   # MFE 2.5 = 1.25R >= capture_start_r
    # floor = fill + 0.5*2.5 = 101.25 > initial 98
    assert s.stop == pytest.approx(101.25)
    s.update(104.0, 101.5, 103.5, 2.0)   # MFE 4 = 2R >= trail_start_r
    # chandelier = 104 - 1.0*2 = 102 ; floor = 100 + 0.5*4 = 102
    assert s.stop == pytest.approx(102.0)


def test_stop_never_loosens():
    # capture floor OFF so the chandelier alone drives the stop — a later ATR
    # spike then forces the candidate BELOW the locked stop, which only the
    # never-loosen clamp survives (a mutant `stop = best` would drop to 98).
    rm = dict(RM, use_mfe_capture_floor=False)
    s = RatchetState("LONG", 100.0, 2.0, rm)
    s.update(104.0, 101.5, 103.5, 2.0)   # MFE 4 = 2R -> chandelier 104-2 = 102
    assert s.stop == pytest.approx(102.0)
    s.update(103.0, 101.0, 101.5, 8.0)   # ATR spike: chandelier 104-8 = 96 < 102
    assert s.stop == pytest.approx(102.0)   # clamp holds; initial-stop cand is 98
    assert s.stop_hit(101.9)


def test_close_confirmed_wick_through_stop_survives():
    s = RatchetState("LONG", 100.0, 2.0, RM)
    s.update(104.0, 101.5, 103.5, 2.0)          # stop ratchets to 102
    s.update(103.0, 95.0, 102.5, 2.0)           # LOW pierces 102, close doesn't
    assert not s.stop_hit(102.5)
    assert s.stop_hit(101.9)


def test_short_mirror():
    s = RatchetState("SHORT", 100.0, 2.0, RM)   # risk_pts 2, stop 102
    assert s.stop == pytest.approx(102.0)
    s.update(98.5, 96.0, 96.5, 2.0)             # MFE 4pts = 2R (low-water 96)
    # chandelier = 96 + 2 = 98 ; floor = 100 - 0.5*4 = 98
    assert s.stop == pytest.approx(98.0)
    assert not s.stop_hit(97.9) and s.stop_hit(98.0)


def test_capture_floor_can_be_disabled():
    rm = dict(RM, use_mfe_capture_floor=False)
    s = RatchetState("LONG", 100.0, 2.0, rm)
    s.update(102.5, 100.0, 102.0, 2.0)          # 1.25R: floor would fire, trail not yet
    assert s.stop == pytest.approx(98.0)


def test_nonfinite_current_atr_skips_chandelier_candidate():
    s = RatchetState("LONG", 100.0, 2.0, RM)
    s.update(104.0, 101.5, 103.5, float("nan"))  # trail active but ATR NaN
    # floor = 100 + 0.5*4 = 102 still applies; no NaN poisoning
    assert s.stop == pytest.approx(102.0)


def test_wilder_atr_matches_v4_port_atr():
    df = pd.DataFrame({"high": [10, 11, 12, 11, 13, 12, 14],
                       "low": [9, 10, 10, 10, 11, 11, 12],
                       "close": [9.5, 10.5, 11, 10.5, 12.5, 11.5, 13.0]})
    from app.strategy.registry.expanding_z_v4 import _atr
    expected = _atr(df["high"], df["low"], df["close"], 3)
    got = wilder_atr(df, 3)
    pd.testing.assert_series_equal(got, expected, check_names=False)
