"""HistoricalDataStore — reproducibility is anchored here. A Dataset is a frozen,
content-hashed view of candles an experiment binds to; the hash changes iff the
underlying candles change (so a Kite backfill can't be silently reused).
"""
import datetime as dt
from decimal import Decimal
import math
from types import SimpleNamespace

import numpy as np
import pytest

from app.market_data.numeric import NumericIngressError
from research.data import store
from research.data.store import StaticDataSource, content_hash, materialize


def test_content_hash_is_stable(candles_factory):
    c = candles_factory(100)
    assert content_hash(c) == content_hash(c)


def test_content_hash_changes_when_candles_change(candles_factory):
    a = candles_factory(100)
    b = candles_factory(100)
    b[-1].close += 1.0
    assert content_hash(a) != content_hash(b)


def test_materialize_builds_frozen_dataset(fake_inst, candles_factory):
    c = candles_factory(120)
    source = StaticDataSource({(fake_inst.key, "day"): c})
    ds = materialize(source, fake_inst, "day")
    assert ds.instrument_key == fake_inst.key
    assert ds.interval == "day"
    assert ds.bar_count == 120
    assert ds.content_hash == content_hash(c)
    assert ds.candles is c


def test_materialize_empty_source_is_safe(fake_inst):
    ds = materialize(StaticDataSource({}), fake_inst, "day")
    assert ds.bar_count == 0
    assert ds.candles == []
    assert ds.content_hash == "e3b0c44298fc1c149afbf4c8996fb924"


_BOOLEAN_SCALARS = (True, False, np.bool_(True), np.bool_(False))
_OHLCV = ("open", "high", "low", "close", "volume")


def _raw_candle(**changes):
    values = dict(
        ts=dt.datetime(2026, 8, 24, 9, 15), open=100.25, high=101.5,
        low=99.75, close=100.0, volume=12_500)
    values.update(changes)
    return SimpleNamespace(**values)


@pytest.mark.parametrize("field", _OHLCV)
@pytest.mark.parametrize("value", _BOOLEAN_SCALARS)
def test_materialize_refuses_boolean_ohlcv_before_hash_or_dataset(
        fake_inst, monkeypatch, field, value):
    candles = [_raw_candle(**{field: value})]
    source = StaticDataSource({(fake_inst.key, "15minute"): candles})
    hash_started = []

    def unexpected_hash():
        hash_started.append(True)
        raise AssertionError("content hashing started before OHLCV refusal")

    monkeypatch.setattr(store.hashlib, "sha256", unexpected_hash)
    with pytest.raises(NumericIngressError, match=field):
        materialize(source, fake_inst, "15minute")
    assert hash_started == []


def test_materialize_preserves_legacy_float_coercible_hash_and_objects(fake_inst):
    candle = _raw_candle(
        open=Decimal("100.25"), high="101.5", low=np.float64(99.75),
        close=100, volume=np.int64(12500))
    candles = [candle]
    source = StaticDataSource({(fake_inst.key, "15minute"): candles})

    dataset = materialize(source, fake_inst, "15minute")

    assert dataset.content_hash == "a3cd0d620593115a8fd827cf1348e44a"
    assert content_hash(candles) == dataset.content_hash
    assert dataset.candles is candles
    assert dataset.candles[0] is candle
    assert isinstance(candle.open, Decimal)
    assert isinstance(candle.high, str)
    assert isinstance(candle.low, np.float64)
    assert type(candle.close) is int
    assert isinstance(candle.volume, np.integer)


def test_current_signed_zero_dataset_identity_converges_without_mutating_source(fake_inst):
    positive_candle = _raw_candle(open=0.0)
    negative_candle = _raw_candle(open=-0.0)
    positive = materialize(
        StaticDataSource({(fake_inst.key, "15minute"): [positive_candle]}),
        fake_inst, "15minute",
    )
    negative = materialize(
        StaticDataSource({(fake_inst.key, "15minute"): [negative_candle]}),
        fake_inst, "15minute",
    )

    assert positive.content_hash == negative.content_hash
    assert math.copysign(1.0, positive.candles[0].open) == 1.0
    assert math.copysign(1.0, negative.candles[0].open) == -1.0
    assert positive.candles[0] is positive_candle
    assert negative.candles[0] is negative_candle


@pytest.mark.parametrize("zero", [
    -0.0,
    Decimal("-0"),
    "-0.0",
    np.float64(-0.0),
    np.int64(0),
])
def test_all_accepted_zero_representations_share_current_research_identity(
        fake_inst, zero):
    canonical = content_hash([_raw_candle(open=0.0)])
    source = _raw_candle(open=zero)

    assert content_hash([source]) == canonical
    assert source.open is zero


def test_research_identity_preserves_nonzero_subnormal_sign(fake_inst):
    positive = content_hash([_raw_candle(open=5e-324)])
    negative = content_hash([_raw_candle(open=-5e-324)])

    assert positive != negative
