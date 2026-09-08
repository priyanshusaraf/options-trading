"""NMT-003: signed zero has one market-numeric identity after raw ingress."""
from __future__ import annotations

import datetime as dt
import json
import math
import subprocess
import sys

import pytest

from app.backtest import dataset_store, identity
from app.backtest.cache import phase4_cache_identity
from app.ir.hashing import canonical_json
from app.ir.validity import valid
from app.market_data.numeric import NumericIngressError, market_float
from app.market_data.observations import (
    NormalizedMarketObservation,
    RawObservationSegment,
    StaleNumericIdentityError,
)


_ADDRESS = "sha256:" + "1" * 64
_AT = dt.datetime(2026, 8, 29, tzinfo=dt.UTC)
_PROVIDER = {"key": "provider-a", "name": "Provider A", "provider": "provider-a"}
_INSTRUMENT = {"key": "NIFTY", "spot_exchange": "XNSE", "spot_symbol": "NIFTY"}
_REQUESTED = {"start": None, "end": None, "lookback_days": 1}
_EFFECTIVE = {"first_ts": 1, "last_ts": 1, "bars": 1, "clamped": False}


def _normalized(value: object) -> NormalizedMarketObservation:
    return NormalizedMarketObservation(
        canonical_instrument_address=_ADDRESS,
        provider_observation_addresses=(_ADDRESS,),
        transform_address=_ADDRESS,
        transform_version="1",
        policy_address=_ADDRESS,
        algorithm_address=_ADDRESS,
        algorithm_version="1",
        market_truth_address=_ADDRESS,
        normalized_schema="strategy-bar/1",
        field="close",
        resolution_seconds=60,
        event_time=_AT,
        completed_at=_AT,
        available_at=_AT,
        recorded_at=_AT,
        numeric=valid(value),
    )


def _candle(value: float) -> dataset_store.StoredCandle:
    return dataset_store.StoredCandle(_AT.replace(tzinfo=None), value, value, value, value, value)


def _put(store: dataset_store.DatasetStore, value: float) -> str:
    return store.put(
        [_candle(value)],
        provider=_PROVIDER,
        instrument=_INSTRUMENT,
        interval="1minute",
        requested_window=_REQUESTED,
        effective_window=_EFFECTIVE,
    )


def _cache_key(dataset_address: str) -> str:
    address = f"sha256:{dataset_address}"
    return phase4_cache_identity(
        owner_id="owner-a",
        authored_ir_address=_ADDRESS,
        manifest_address=address,
        registry_snapshot_address=_ADDRESS,
        resolved_graph_address=_ADDRESS,
        implementation_closure_address=_ADDRESS,
        declaration_addresses=(_ADDRESS,),
        plan_address=_ADDRESS,
        capability_assessment_address=_ADDRESS,
        market_truth_address=_ADDRESS,
        evaluation_policy_address=_ADDRESS,
        admission_address=_ADDRESS,
    )


def test_signed_zero_normalizes_at_the_one_market_float_ingress():
    positive = market_float(0.0, field="close")
    negative = market_float(-0.0, field="close")

    assert positive == negative == 0.0
    assert math.copysign(1.0, positive) == 1.0
    assert math.copysign(1.0, negative) == 1.0
    assert market_float(5e-324, field="close") == 5e-324
    assert market_float(-5e-324, field="close") == -5e-324
    assert math.copysign(1.0, market_float(-5e-324, field="close")) == -1.0

    for refused in (True, False, float("nan"), float("inf"), float("-inf")):
        with pytest.raises(NumericIngressError):
            market_float(refused, field="close")


def test_raw_bytes_remain_distinct_but_normalized_zero_identity_converges():
    positive_raw = RawObservationSegment(
        "owner-a", _ADDRESS, _ADDRESS, "application/json", "vendor-bar/1",
        b'{"close":0.0}', _AT,
    )
    negative_raw = RawObservationSegment(
        "owner-a", _ADDRESS, _ADDRESS, "application/json", "vendor-bar/1",
        b'{"close":-0.0}', _AT,
    )

    assert positive_raw.address != negative_raw.address
    assert positive_raw.byte_digest != negative_raw.byte_digest
    assert _normalized(0.0).numeric.value == 0.0
    assert math.copysign(1.0, _normalized(-0.0).numeric.value) == 1.0
    assert _normalized(0.0).canonical_bytes == _normalized(-0.0).canonical_bytes
    assert _normalized(0.0).address == _normalized(-0.0).address


def test_normalized_decoder_verifies_current_bytes_and_refuses_stale_signed_zero():
    nonzero = _normalized(-5e-324)
    assert NormalizedMarketObservation.from_bytes(nonzero.canonical_bytes) == nonzero
    zero = _normalized(-0.0)
    assert NormalizedMarketObservation.from_bytes(zero.canonical_bytes) == zero

    stale = json.loads(_normalized(0.0).canonical_bytes)
    stale["fact"]["numeric"]["value"] = -0.0
    stale_bytes = canonical_json(stale).encode("utf-8")

    with pytest.raises(StaleNumericIdentityError, match="stale signed-zero numeric identity"):
        NormalizedMarketObservation.from_bytes(stale_bytes)


def test_dataset_and_cache_inputs_converge_for_signed_zero(tmp_path):
    store = dataset_store.DatasetStore(tmp_path / "datasets")
    try:
        positive_address = _put(store, 0.0)
        negative_address = _put(store, -0.0)

        assert positive_address == negative_address
        assert store.get(positive_address) is not None
        assert math.copysign(1.0, store.get(positive_address).candles[0].close) == 1.0
        assert _cache_key(positive_address) == _cache_key(negative_address)
    finally:
        store.close()


def test_stored_legacy_signed_zero_refuses_after_restart_without_aliasing(
        tmp_path, monkeypatch):
    root = tmp_path / "datasets"

    def legacy_market_float(value, *, field: str) -> float:
        if isinstance(value, bool):
            raise NumericIngressError(f"{field}: boolean is not a market number")
        out = float(value)
        if not math.isfinite(out):
            raise NumericIngressError(f"{field}: non-finite value")
        return out

    with monkeypatch.context() as legacy:
        legacy.setattr(identity, "market_float", legacy_market_float)
        legacy.setattr(dataset_store, "market_float", legacy_market_float)
        old_store = dataset_store.DatasetStore(root)
        try:
            legacy_address = _put(old_store, -0.0)
            assert old_store.get(legacy_address) is not None
        finally:
            old_store.close()

    probe = """
import datetime as dt
import json
import sys
from app.backtest import dataset_store

root, legacy_address = sys.argv[1:]
store = dataset_store.DatasetStore(root)
try:
    refused_before_put = store.get(legacy_address) is None
    candle = dataset_store.StoredCandle(
        dt.datetime(2026, 8, 29), 0.0, 0.0, 0.0, 0.0, 0.0)
    current_address = store.put(
        [candle],
        provider={"key": "provider-a", "name": "Provider A", "provider": "provider-a"},
        instrument={"key": "NIFTY", "spot_exchange": "XNSE", "spot_symbol": "NIFTY"},
        interval="1minute",
        requested_window={"start": None, "end": None, "lookback_days": 1},
        effective_window={"first_ts": 1, "last_ts": 1, "bars": 1, "clamped": False},
    )
    print(json.dumps({
        "current_address": current_address,
        "current_reads": store.get(current_address) is not None,
        "fresh_process": True,
        "legacy_address": legacy_address,
        "legacy_refused_before_put": refused_before_put,
        "legacy_refused_after_put": store.get(legacy_address) is None,
        "stored_addresses": store.stored_addresses(),
    }, sort_keys=True))
finally:
    store.close()
"""
    completed = subprocess.run(
        [sys.executable, "-c", probe, str(root), legacy_address],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["fresh_process"] is True
    assert receipt["legacy_refused_before_put"] is True
    assert receipt["legacy_refused_after_put"] is True
    assert receipt["current_reads"] is True
    assert receipt["current_address"] != legacy_address
    assert receipt["stored_addresses"] == sorted(
        [legacy_address, receipt["current_address"]]
    )
    print(json.dumps({"legacy_restart_receipt": receipt}, sort_keys=True))
