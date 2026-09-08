import datetime as dt
from dataclasses import replace

import numpy as np
import pytest
from dataclasses import dataclass
from types import SimpleNamespace

from app.backtest.cache import phase4_cache_identity
from app.backtest.identity import (execution_result_address, ordered_dataset_address,
                                   phase4_binding_payload)
from app.backtest import sweep
from app.providers.base import Candle


def _address(char):
    return "sha256:" + char * 64


def _identity(**changes):
    values = dict(owner_id="owner-a", authored_ir_address=_address("a"), manifest_address=_address("b"), registry_snapshot_address=_address("c"),
                  resolved_graph_address=_address("d"), implementation_closure_address=_address("e"),
                  declaration_addresses=(_address("f"),), plan_address=_address("1"),
                  capability_assessment_address=_address("2"), market_truth_address=_address("3"),
                  evaluation_policy_address=_address("4"), admission_address=_address("5"))
    values.update(changes)
    return phase4_cache_identity(**values)


@dataclass
class _Instrument:
    key: str = "NIFTY"
    name: str = "NIFTY 50"
    segment: str = "NFO"
    lot_size: int = 75
    strike_step: float = 50.0
    has_options: bool = True


@dataclass
class _Strategy:
    key: str = "phase4_identity_test"
    version: str = "a" * 64
    default_params: dict | None = None
    declared_warmup: int = 1
    risk_model: dict | None = None

    def __post_init__(self):
        self.default_params = self.default_params or {}


def _kernel(params, inputs, context_inputs):
    return inputs


def _binding(**changes):
    value = dict(owner_id="owner-a", authored_ir_address=_address("a"),
                 registry_snapshot_address=_address("b"), resolved_graph_address=_address("c"),
                 implementation_closure_address=_address("d"), declaration_addresses=(_address("e"),),
                 plan_address=_address("f"), capability_assessment_address=_address("1"),
                 dataset_manifest_address=_address("2"), market_truth_snapshot_address=_address("3"),
                 evaluation_policy_address=_address("4"))
    value.update(changes)
    return value


def _non_graph_attribution():
    return {
        "strategy_key": _Strategy.key,
        "strategy_version": _Strategy.version,
        "graph_address": None,
        "attribution_state": "NON_GRAPH",
    }


def _result_address(**changes):
    values = dict(dataset_address="a" * 64, instrument=_Instrument(), strategy=_Strategy(),
                  parameters={}, capital=50_000.0, window={"label": "test"}, slippage_pct=0.0,
                  admission_address=_address("5"), phase4_binding=_binding(),
                  implementation_maps=({"sha256:kernel": _kernel},))
    values.update(changes)
    return execution_result_address(**values)


def test_cache_identity_binds_every_answer_changing_phase4_digest():
    base = _identity()
    assert base == _identity()
    mutations = {
        "owner_id": "owner-b", "authored_ir_address": _address("6"),
        "manifest_address": _address("7"), "registry_snapshot_address": _address("8"),
        "resolved_graph_address": _address("9"), "implementation_closure_address": _address("0"),
        "declaration_addresses": (_address("0"),), "plan_address": _address("a"),
        "capability_assessment_address": _address("b"), "market_truth_address": _address("c"),
        "evaluation_policy_address": _address("d"), "admission_address": _address("e"),
    }
    for key, value in mutations.items():
        assert base != _identity(**{key: value}), key


def test_incomplete_legacy_identity_cannot_satisfy_phase4_request():
    with pytest.raises(ValueError):
        _identity(plan_address="")
    with pytest.raises(ValueError):
        _identity(declaration_addresses=())
    with pytest.raises(ValueError):
        _identity(declaration_addresses=(_address("b"), _address("a")))
    with pytest.raises(ValueError):
        _identity(plan_address="sha256:malformed")
    with pytest.raises(ValueError):
        _identity(admission_address="sha256:malformed")


def test_result_binding_validator_matches_cache_identity_contract():
    binding = dict(owner_id="owner-a", authored_ir_address=_address("a"),
                   registry_snapshot_address=_address("b"), resolved_graph_address=_address("c"),
                   implementation_closure_address=_address("d"), declaration_addresses=(_address("e"),),
                   plan_address=_address("f"), capability_assessment_address=_address("1"),
                   dataset_manifest_address=_address("2"), market_truth_snapshot_address=_address("3"),
                   evaluation_policy_address=_address("4"))
    assert phase4_binding_payload(binding)["authored_ir_address"] == _address("a")
    for key in tuple(binding):
        mutant = dict(binding)
        if key == "declaration_addresses":
            mutant[key] = ()
        elif key == "owner_id":
            mutant[key] = ""
        else:
            mutant[key] = "sha256:bad"
        with pytest.raises(ValueError):
            phase4_binding_payload(mutant)
    with pytest.raises(ValueError):
        phase4_binding_payload({**binding, "unexpected": _address("5")})


def test_execution_result_address_binds_phase4_facts_and_refuses_bad_bindings():
    base = _result_address()
    assert base is not None
    for key in _binding():
        mutant = _binding()
        mutant[key] = ((_address("9"),) if key == "declaration_addresses" else "owner-b"
                       if key == "owner_id" else _address("9"))
        assert _result_address(phase4_binding=mutant) != base, key
    assert _result_address(phase4_binding={"owner_id": "owner-a"}) is None
    assert _result_address(phase4_binding={**_binding(), "extra": _address("9")}) is None
    assert _result_address(phase4_binding=None) is not None


def test_sweep_execution_address_binds_every_phase4_fact():
    """The real sweep caller must carry the verified binding into identity."""
    prepared = SimpleNamespace(dataset_address="a" * 64)
    base = sweep._execution_address(
        prepared, _Instrument(), "15minute", 50_000.0,
        {"label": "test"}, _Strategy(), 0.0, _address("5"), _binding(),
        attribution=_non_graph_attribution())
    assert base
    for key in _binding():
        mutant = _binding()
        mutant[key] = (() if key == "declaration_addresses" else "owner-b"
                       if key == "owner_id" else _address("9"))
        changed = sweep._execution_address(
            prepared, _Instrument(), "15minute", 50_000.0,
            {"label": "test"}, _Strategy(), 0.0, _address("5"), mutant,
            attribution=_non_graph_attribution())
        assert changed != base, key


_BOOLEAN_SCALARS = (True, False, np.bool_(True), np.bool_(False))
_OHLCV = ("open", "high", "low", "close", "volume")


def _market_candles(count=60):
    start = dt.datetime(2026, 8, 21, 9, 15)
    return [Candle(start + dt.timedelta(minutes=15 * index),
                   100.0 + index, 101.0 + index, 99.0 + index,
                   100.5 + index, 1_000.0 + index)
            for index in range(count)]


@pytest.mark.parametrize("field", _OHLCV)
@pytest.mark.parametrize("value", _BOOLEAN_SCALARS)
def test_dataset_identity_refuses_boolean_before_minting_an_address(field, value):
    candles = _market_candles(1)
    candles[0] = replace(candles[0], **{field: value})
    with pytest.raises(ValueError, match=field):
        ordered_dataset_address(
            candles, provider="kite", instrument="NIFTY", interval="15minute",
            requested_window={"lookback_days": 30, "start": None, "end": None},
            effective_window={"first_ts": 1, "last_ts": 2, "bars": 1})


@pytest.mark.parametrize("field", _OHLCV)
@pytest.mark.parametrize("value", _BOOLEAN_SCALARS)
def test_sweep_refuses_boolean_before_dataset_or_cache_authority(
        monkeypatch, field, value):
    candles = _market_candles()
    candles[3] = replace(candles[3], **{field: value})
    provider = SimpleNamespace(get_candles=lambda *_args, **_kwargs: candles)
    address_calls = []
    monkeypatch.setattr(sweep, "ordered_dataset_address",
                        lambda *_args, **_kwargs: address_calls.append(True))

    prepared = sweep._prepare_dataset(
        provider, _Instrument(), "15minute",
        {"lookback_days": 30, "start": None, "end": None})

    assert "boolean scalar" in prepared.error
    assert prepared.dataset_address == ""
    assert prepared.candles == ()
    assert address_calls == []
    assert sweep._execution_address(
        prepared, _Instrument(), "15minute", 50_000.0, {"label": "test"},
        _Strategy(), 0.0, _address("5"), _binding()) == ""


@pytest.mark.parametrize("field", _OHLCV)
@pytest.mark.parametrize("value", _BOOLEAN_SCALARS)
def test_pinned_reload_refuses_boolean_before_verified_dataset_authority(field, value):
    candles = _market_candles()
    candles[3] = replace(candles[3], **{field: value})
    requested = {"lookback_days": 30, "start": None, "end": None}
    stored = SimpleNamespace(
        address="a" * 64, candles=tuple(candles), provider="provider-id",
        instrument="instrument-id", interval="15minute",
        requested_window=requested,
        effective_window={"clamped": False}, classification="MARKET_PUBLIC")

    prepared = sweep._pinned_dataset_from_store(
        lambda _address: stored, address=stored.address, key="NIFTY|15minute",
        provider_identity="provider-id", instrument_identity="instrument-id",
        interval="15minute", requested_window=requested, clamped=False)

    assert "contains invalid candles" in prepared.error
    assert prepared.dataset_verified is False
    assert prepared.dataset_address == ""
