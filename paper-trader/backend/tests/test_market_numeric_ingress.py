"""A-02 / DP-011 permanent regression: booleans never become executable numbers.

Foundation-audit finding A-02: Python ``bool`` is a subtype of ``int``, so a raw
``True`` crossing a ``float(...)`` boundary becomes the executable price ``1.0``
— corrupting candles, dataset identity, research results, sizing and execution
inputs while every hash stays internally consistent.

Prevention invariant (audit §A-02): reject booleans *before* coercion at every
raw market numeric ingress, under ONE authoritative rule
(``app/market_data/numeric.py::market_float``) applied across the provider,
preparation, storage boundaries exercised here.

Mutation contract: relaxing the rule (accepting bool, or coercing before the
type check) must turn these tests red.  Deleting a call-site guard must turn
that call-site's test red.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

import numpy as np
import pytest

from app.backtest import dataset_store
from app.market_data.numeric import NumericIngressError, market_float
from app.providers import dhan as dhan_mod
from app.providers import kite as kite_mod
from app.providers import replay as replay_mod
from app.providers import upstox as upstox_mod
from app.providers.base import Candle, ProviderReadError

_TS = dt.datetime(2026, 8, 21, 9, 15)
_BOOLS = (True, False, np.bool_(True), np.bool_(False))
# Provider ingresses speak the provider vocabulary (the conformance contract's
# typed refusal); replay and storage keep theirs.
_PROVIDER_ERROR = pytest.raises(ProviderReadError)


# ── the one authoritative rule ───────────────────────────────────────────────

@pytest.mark.parametrize("bad", [True, False, np.bool_(True), np.bool_(False),
                                  None, [1.0], {"v": 1}])
def test_the_rule_refuses_booleans_and_non_numbers_before_any_coercion(bad):
    with pytest.raises(NumericIngressError):
        market_float(bad, field="close")


@pytest.mark.parametrize("good", [2, 2.0, 0, 24_101.45, Decimal("2.125"),
                                   "2.125", np.int64(2), np.float64(2.125)])
def test_the_rule_passes_real_numbers_through_as_plain_floats(good):
    out = market_float(good, field="close")
    assert out == float(good)
    assert type(out) is float


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_the_rule_refuses_non_finite_values(bad):
    with pytest.raises(NumericIngressError):
        market_float(bad, field="open")


# ── provider ingress seams (raw external bytes → Candle) ────────────────────

def _kite_row(field, value):
    row = {"date": _TS, "open": 100.0, "high": 101.0, "low": 99.0,
           "close": 100.5, "volume": 12500}
    row[field] = value
    return row


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "volume"])
@pytest.mark.parametrize("value", _BOOLS)
def test_kite_ingress_refuses_boolean_ohlcv_before_coercion(field, value):
    with _PROVIDER_ERROR:
        kite_mod.candle_from_row(_kite_row(field, value))


def test_kite_ingress_happy_path_is_unchanged():
    candle = kite_mod.candle_from_row(
        {"date": _TS.replace(tzinfo=dt.timezone.utc), "open": 1, "high": 2.5,
         "low": 0.5, "close": 2, "volume": 7})
    assert isinstance(candle, Candle)
    assert (candle.open, candle.high, candle.low, candle.close) == (1.0, 2.5, 0.5, 2.0)
    assert candle.volume == 7.0
    assert candle.ts == (_TS.replace(tzinfo=None))


def _dhan_columns(field, value):
    columns = {"open": [100.0], "high": [101.0], "low": [99.0],
               "close": [100.5], "volume": [12500]}
    columns[field][0] = value
    return columns


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "volume"])
@pytest.mark.parametrize("value", _BOOLS)
def test_dhan_ingress_refuses_boolean_ohlcv_before_coercion(field, value):
    with _PROVIDER_ERROR:
        dhan_mod.candle_from_columns_row(1_768_980_500, _dhan_columns(field, value), 0)


def test_dhan_ingress_happy_path_is_unchanged():
    candle = dhan_mod.candle_from_columns_row(
        1_768_980_500,
        {"open": [1], "high": [2.5], "low": [0.5], "close": [2], "volume": [7]}, 0)
    assert isinstance(candle, Candle)
    assert candle.volume == 7.0
    assert candle.ts.tzinfo is None


def _upstox_row(field, value):
    row = ["2026-08-21T09:15:00+05:30", 100.0, 101.0, 99.0, 100.5, 12500]
    row[["", "open", "high", "low", "close", "volume"].index(field)] = value
    return row


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "volume"])
@pytest.mark.parametrize("value", _BOOLS)
def test_upstox_ingress_refuses_boolean_ohlcv_before_coercion(field, value):
    with _PROVIDER_ERROR:
        upstox_mod._to_candle(_upstox_row(field, value))


def test_upstox_ingress_happy_path_keeps_naive_ist_contract():
    candle = upstox_mod._to_candle(
        ["2026-08-21T09:15:00+05:30", 1, 2.5, 0.5, 2, 7])
    assert isinstance(candle, Candle)
    assert candle.ts == _TS
    assert candle.close == 2.0


def _replay_record(field, value):
    record = {"ts": "2026-08-21T09:15:00", "open": 100.0, "high": 101.0,
              "low": 99.0, "close": 100.5, "volume": 12500}
    record[field] = value
    return record


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "volume"])
@pytest.mark.parametrize("value", _BOOLS)
def test_replay_ingress_refuses_boolean_ohlcv_before_coercion(field, value):
    with pytest.raises(NumericIngressError):
        replay_mod.candle_from_record(_replay_record(field, value))


def test_replay_ingress_happy_path_is_unchanged():
    candle = replay_mod.candle_from_record(
        {"ts": _TS, "open": 1, "high": 2.5, "low": 0.5, "close": 2})
    assert isinstance(candle, Candle)
    assert candle.volume == 0.0
    assert candle.ts == _TS


# ── the storage boundary (dataset encoder) ──────────────────────────────────

def _stored_candle(field, value):
    kwargs = {"ts": _TS, "open": 100.0, "high": 101.0, "low": 99.0,
              "close": 100.5, "volume": 12500}
    kwargs[field] = value
    return Candle(**kwargs)


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "volume"])
@pytest.mark.parametrize("value", _BOOLS)
def test_dataset_encoder_refuses_boolean_ohlcv_before_packing(field, value):
    with pytest.raises(dataset_store.DatasetStoreError):
        dataset_store.encode_candles([_stored_candle(field, value)])


def test_dataset_encoder_happy_path_still_roundtrips():
    blob = dataset_store.encode_candles([_stored_candle("open", 100.0)])
    decoded = dataset_store.decode_candles(blob)
    assert len(decoded) == 1
    assert decoded[0].close == pytest.approx(100.5)
