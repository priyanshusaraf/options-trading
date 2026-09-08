import datetime as dt
from decimal import Decimal

import numpy as np
import pytest

from app.backtest import engine
from app.core.instruments import get_instrument
from app.core.market_hours import ist_epoch
from app.ir.validity import NumericValue, ValidityState
from app.market_data.observations import (AlignmentPolicy, DataObservation,
                                          align_observation,
                                          align_required_series)
from app.market_data.candles import candles_to_df, observations_to_frame
from app.providers.base import Candle


def _row(event, available, completed, value=10.0):
    address = "sha256:" + "a" * 64
    return DataObservation("NSE:ABC", "CLOSE", 60, event, available, completed,
                           address, address,
                           NumericValue(ValidityState.VALID, value))


def test_alignment_refuses_forming_future_stale_and_skewed_observations():
    now = dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.timezone.utc)
    policy = AlignmentPolicy(maximum_age_seconds=60, maximum_skew_seconds=20)
    completed = _row(now - dt.timedelta(seconds=20), now - dt.timedelta(seconds=10),
                     now - dt.timedelta(seconds=10))
    forming = _row(now - dt.timedelta(seconds=5), now + dt.timedelta(seconds=1),
                   now + dt.timedelta(seconds=1), 20.0)
    assert align_observation([completed, forming], at=now, policy=policy) == completed
    unavailable = _row(now - dt.timedelta(seconds=5), now + dt.timedelta(seconds=1),
                       now - dt.timedelta(seconds=1), 30.0)
    assert align_observation([unavailable], at=now, policy=policy) is None
    assert align_observation([_row(now - dt.timedelta(seconds=61), now, now)],
                             at=now, policy=policy) is None
    assert align_required_series({"one": [completed], "two": [_row(
        now - dt.timedelta(seconds=50), now - dt.timedelta(seconds=10), now - dt.timedelta(seconds=10))]},
        at=now, policy=policy) is None


def test_future_append_does_not_change_prior_alignment():
    at = dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.timezone.utc)
    policy = AlignmentPolicy(maximum_age_seconds=120, maximum_skew_seconds=120)
    prefix = [_row(at - dt.timedelta(seconds=10), at - dt.timedelta(seconds=10),
                   at - dt.timedelta(seconds=10), 1.0)]
    baseline = align_observation(prefix, at=at, policy=policy)
    future = _row(at + dt.timedelta(seconds=10), at + dt.timedelta(seconds=10),
                  at + dt.timedelta(seconds=10), 2.0)
    assert align_observation(prefix + [future], at=at, policy=policy) == baseline


def test_same_event_correction_is_causal_and_does_not_rewrite_prior_answer():
    at = dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.timezone.utc)
    policy = AlignmentPolicy(maximum_age_seconds=120, maximum_skew_seconds=120)
    original = _row(at - dt.timedelta(seconds=10), at - dt.timedelta(seconds=10),
                    at - dt.timedelta(seconds=10), 1.0)
    correction = _row(at - dt.timedelta(seconds=10), at + dt.timedelta(seconds=5),
                      at + dt.timedelta(seconds=5), 2.0)
    assert align_observation([original, correction], at=at, policy=policy) == original
    assert align_observation([original, correction], at=at + dt.timedelta(seconds=4),
                             policy=policy) == original
    assert align_observation([original, correction], at=at + dt.timedelta(seconds=5),
                             policy=policy) == correction


def test_aligned_observations_use_the_canonical_candle_frame_converter():
    at = dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.timezone.utc)
    policy = AlignmentPolicy(maximum_age_seconds=60, maximum_skew_seconds=0)
    series = {name: [DataObservation("NSE:ABC", name, 60, at, at, at,
                                     "sha256:" + "a" * 64, "sha256:" + "b" * 64,
                                     NumericValue(ValidityState.VALID, value))] for name, value in
              {"OPEN": 1.0, "HIGH": 3.0, "LOW": 0.5, "CLOSE": 2.0, "VOLUME": 5.0}.items()}
    frame = observations_to_frame(series, at=at, policy=policy)
    assert frame.to_dict("records") == [{"date": at, "open": 1.0, "high": 3.0,
                                          "low": 0.5, "close": 2.0, "volume": 5.0}]


def test_observation_reuses_closed_numeric_validity_contract():
    at = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
    for state in (ValidityState.INSUFFICIENT_HISTORY, ValidityState.PROVIDER_UNAVAILABLE,
                  ValidityState.NOT_LISTED, ValidityState.NO_TRADE):
        observation = DataObservation("NSE:ABC", "CLOSE", 60, at, at, at,
                                      "sha256:" + "a" * 64, "sha256:" + "b" * 64,
                                      NumericValue(state))
        assert observation.value is None and observation.validity is state
    with pytest.raises(ValueError):
        NumericValue(ValidityState.VALID, float("nan"))
    with pytest.raises(ValueError):
        NumericValue(ValidityState.VALID, float("inf"))


def test_observation_and_alignment_reject_malformed_time_inputs():
    aware = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
    with pytest.raises(ValueError):
        _row(aware, aware, aware - dt.timedelta(seconds=1))
    with pytest.raises(ValueError):
        align_observation([_row(aware, aware, aware)], at=aware.replace(tzinfo=None),
                          policy=AlignmentPolicy(1, 1))
    with pytest.raises(ValueError):
        align_observation([object()], at=aware, policy=AlignmentPolicy(1, 1))
    with pytest.raises(ValueError):
        DataObservation("NSE:ABC", "CLOSE", True, aware, aware, aware,
                        "sha256:" + "a" * 64, "sha256:" + "b" * 64,
                        NumericValue(ValidityState.VALID, 1.0))
    with pytest.raises(ValueError):
        AlignmentPolicy("1", 1)
    with pytest.raises(ValueError):
        AlignmentPolicy(1, 1, timezone="Asia/Kolkata")
    with pytest.raises(ValueError):
        AlignmentPolicy(1, 1, completed_bar_rule="FORMING_OK")


def test_available_forming_observation_waits_for_completion():
    at = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
    forming = _row(at, at, at + dt.timedelta(seconds=1))
    policy = AlignmentPolicy(2, 2)
    assert align_observation([forming], at=at, policy=policy) is None
    assert align_observation([forming], at=at + dt.timedelta(seconds=1), policy=policy) == forming


def test_alignment_refuses_ambiguous_equally_ranked_observations():
    at = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
    left = _row(at, at, at, 1.0)
    right = _row(at, at, at, 2.0)
    assert align_observation([left, right], at=at, policy=AlignmentPolicy(1, 1)) is None


def test_candle_adapter_refuses_mixed_observation_identity():
    at = dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.timezone.utc)
    policy = AlignmentPolicy(maximum_age_seconds=60, maximum_skew_seconds=0)
    series = {name: [DataObservation("NSE:ABC", name, 60, at, at, at,
                                     "sha256:" + "a" * 64, "sha256:" + "b" * 64,
                                     NumericValue(ValidityState.VALID, value))] for name, value in
              {"OPEN": 1.0, "HIGH": 3.0, "LOW": 0.5, "CLOSE": 2.0, "VOLUME": 5.0}.items()}
    series["VOLUME"] = [DataObservation("NSE:OTHER", "VOLUME", 60, at, at, at,
                                          "sha256:" + "a" * 64, "sha256:" + "b" * 64,
                                          NumericValue(ValidityState.VALID, 5.0))]
    assert observations_to_frame(series, at=at, policy=policy).empty


@pytest.mark.parametrize("field", ("OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"))
@pytest.mark.parametrize("value", (True, False, np.bool_(True), np.bool_(False)))
def test_observation_adapter_refuses_boolean_before_a_causal_signal(field, value):
    at = dt.datetime(2026, 1, 2, 10, 0, tzinfo=dt.timezone.utc)
    policy = AlignmentPolicy(maximum_age_seconds=60, maximum_skew_seconds=0)
    values = {"OPEN": 1.0, "HIGH": 3.0, "LOW": 0.5,
              "CLOSE": 2.0, "VOLUME": 5.0}
    values[field] = value
    series = {
        name: [DataObservation(
            "NSE:ABC", name, 60, at, at, at,
            "sha256:" + "a" * 64, "sha256:" + "b" * 64,
            NumericValue(ValidityState.VALID, raw))]
        for name, raw in values.items()}

    assert observations_to_frame(series, at=at, policy=policy).empty


def test_compatible_numeric_inputs_keep_exact_next_bar_result():
    first = dt.datetime(2025, 1, 2, 9, 15)
    candles = [
        Candle(first, Decimal("100"), "101", np.float64(99), 100.5, np.int64(7)),
        Candle(first + dt.timedelta(minutes=5), "101", Decimal("102"),
               np.float64(100), 101.5, np.int64(8)),
    ]
    frame = candles_to_df(candles)
    frame["longEntry"] = [True, False]
    frame["shortEntry"] = [False, False]
    frame["longExit"] = [False, False]
    frame["shortExit"] = [False, False]

    trades = engine.run_trades(
        frame, get_instrument("NIFTY"), "NFO", 50_000.0, rm=None,
        event_risk=False, slippage_pct=0.0)

    assert len(trades) == 1
    assert trades[0].entry_time == ist_epoch(candles[1].ts)
    assert trades[0].entry_price == 101.0
