"""Content identity for reusable backtest results.

Each test names a mutation that must make a cached result cold.  The cache wiring
is tested elsewhere; this file owns the pure addresses it will consume.
"""
from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass, replace
from types import ModuleType

import pytest

from app.providers.base import Candle


IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def _candles() -> list[Candle]:
    start = dt.datetime(2026, 8, 3, 9, 15)
    return [
        Candle(start + dt.timedelta(minutes=15 * i),
               100.0 + i, 101.25 + i, 99.5 + i, 100.75 + i, 1_000.0 + i)
        for i in range(4)
    ]


def _dataset(candles=None, **overrides) -> str:
    from app.backtest.identity import ordered_dataset_address

    kwargs = {
        "provider": "kite",
        "instrument": "NIFTY",
        "interval": "15minute",
        "requested_window": {"lookback_days": 30, "start": None, "end": None},
        "effective_window": {"first_ts": 1785738300, "last_ts": 1785741000,
                             "bars": 4, "clamped": False},
    }
    kwargs.update(overrides)
    return ordered_dataset_address(candles or _candles(), **kwargs)


def test_ordered_dataset_address_is_stable_full_sha256():
    address = _dataset()
    assert address == _dataset()
    assert len(address) == 64
    assert set(address) <= set("0123456789abcdef")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda rows: [replace(rows[0], open=rows[0].open + 0.125), *rows[1:]],
        lambda rows: [replace(rows[0], high=rows[0].high + 0.125), *rows[1:]],
        lambda rows: [replace(rows[0], low=rows[0].low - 0.125), *rows[1:]],
        lambda rows: [replace(rows[0], close=rows[0].close + 0.125), *rows[1:]],
        lambda rows: [replace(rows[0], volume=rows[0].volume + 1), *rows[1:]],
        lambda rows: [replace(rows[0], ts=rows[0].ts + dt.timedelta(microseconds=1)),
                      *rows[1:]],
        lambda rows: [rows[1], rows[0], *rows[2:]],
        lambda rows: [rows[0], replace(rows[0], ts=rows[0].ts + dt.timedelta(minutes=1)),
                      *rows[1:]],
        lambda rows: [*rows[:1], *rows[2:]],
    ],
    ids=("open", "high", "low", "close", "volume", "timestamp", "order",
         "insertion", "deletion"),
)
def test_any_ordered_candle_mutation_changes_address_with_same_final_timestamp(mutate):
    original = _candles()
    changed = mutate(original)
    assert changed[-1].ts == original[-1].ts
    assert _dataset(changed) != _dataset(original)


@pytest.mark.parametrize(
    "changed",
    [
        {"provider": "mock"},
        {"instrument": "BANKNIFTY"},
        {"interval": "5minute"},
        {"requested_window": {"lookback_days": 90, "start": None, "end": None}},
        {"effective_window": {"first_ts": 1785738300, "last_ts": 1785741000,
                              "bars": 4, "clamped": True}},
    ],
    ids=("provider", "instrument", "interval", "requested-window", "effective-window"),
)
def test_dataset_provenance_changes_address(changed):
    assert _dataset(**changed) != _dataset()


@pytest.mark.parametrize("field", ("open", "high", "low", "close", "volume"))
def test_dataset_refuses_non_finite_values(field):
    rows = _candles()
    rows[1] = replace(rows[1], **{field: float("nan")})
    with pytest.raises(ValueError, match=field):
        _dataset(rows)


def test_naive_ist_and_aware_ist_name_the_same_market_instant():
    naive = _candles()
    aware = [replace(row, ts=row.ts.replace(tzinfo=IST)) for row in naive]
    assert _dataset(naive) == _dataset(aware)


# ── execution/result identity ────────────────────────────────────────────────

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
    key: str = "expanding_z_v4"
    version: str = "a" * 64
    default_params: dict | None = None
    declared_warmup: int = 302
    risk_model: dict | None = None

    def __post_init__(self):
        if self.default_params is None:
            self.default_params = {"ema_length": 50, "entry_pct": 65.0}
        if self.risk_model is None:
            self.risk_model = {"atr_length": 14, "trail_atr": 3.0}


def _kernel_a(params, inputs, context_inputs):
    return inputs


def _kernel_b(params, inputs, context_inputs):
    return {**inputs, "changed": True}


def _execution(**overrides):
    from app.backtest.identity import execution_result_address

    kwargs = {
        "dataset_address": _dataset(),
        "instrument": _Instrument(),
        "strategy": _Strategy(),
        "parameters": {"ema_length": 50, "entry_pct": 65.0},
        "capital": 50_000.0,
        "window": {"requested": "30d", "clamped": False},
        "slippage_pct": 0.0005,
        "implementation_maps": ({"sha256:kernel": _kernel_a},),
    }
    kwargs.update(overrides)
    return execution_result_address(**kwargs)


def test_execution_result_address_is_stable_full_sha256():
    address = _execution()
    assert address == _execution()
    assert address is not None and len(address) == 64
    assert set(address) <= set("0123456789abcdef")


@pytest.mark.parametrize(
    "changed",
    [
        {"dataset_address": "b" * 64},
        {"instrument": replace(_Instrument(), segment="BFO")},
        {"instrument": replace(_Instrument(), lot_size=50)},
        {"instrument": replace(_Instrument(), strike_step=100.0)},
        {"instrument": replace(_Instrument(), has_options=False)},
        {"strategy": replace(_Strategy(), version="b" * 64)},
        {"strategy": replace(_Strategy(), declared_warmup=303)},
        {"strategy": replace(_Strategy(), risk_model={"atr_length": 14,
                                                       "trail_atr": 4.0})},
        {"parameters": {"ema_length": 51, "entry_pct": 65.0}},
        {"capital": 60_000.0},
        {"window": {"requested": "90d", "clamped": False}},
        {"slippage_pct": 0.001},
        {"implementation_maps": ({"sha256:kernel": _kernel_b},)},
    ],
    ids=("dataset", "segment", "lot-size", "strike-step", "has-options",
         "strategy-version", "warmup", "risk-model", "bound-parameters",
         "capital", "window", "slippage", "implementation-map"),
)
def test_every_execution_input_mutation_changes_result_address(changed):
    assert _execution(**changed) != _execution()


@pytest.mark.parametrize("version", (None, "", "unknown"))
def test_unidentified_strategy_is_explicitly_non_reusable(version):
    assert _execution(strategy=replace(_Strategy(), version=version)) is None


def test_transitive_source_digest_changes_when_a_helper_module_changes(tmp_path):
    from app.backtest.identity import transitive_module_source_digest

    source = tmp_path / "fixture_strategy.py"
    source.write_text("def helper():\n    return 1\n", encoding="utf-8")
    module = ModuleType("fixture_strategy")
    module.__file__ = str(source)
    sys.modules[module.__name__] = module
    try:
        before = transitive_module_source_digest(modules=(module,))
        source.write_text("def helper():\n    return 2\n", encoding="utf-8")
        after = transitive_module_source_digest(modules=(module,))
    finally:
        sys.modules.pop(module.__name__, None)
    assert before is not None and after is not None and before != after


def test_transitive_source_digest_binds_implementation_map_keys_and_callables():
    from app.backtest.identity import transitive_module_source_digest

    original = transitive_module_source_digest(
        modules=(sys.modules[__name__],),
        implementation_maps=({"sha256:kernel": _kernel_a},))
    changed_callable = transitive_module_source_digest(
        modules=(sys.modules[__name__],),
        implementation_maps=({"sha256:kernel": _kernel_b},))
    changed_address = transitive_module_source_digest(
        modules=(sys.modules[__name__],),
        implementation_maps=({"sha256:other": _kernel_a},))
    assert original is not None
    assert original != changed_callable
    assert original != changed_address


def test_charge_and_event_policy_changes_make_the_result_cold(monkeypatch):
    from app.engine import charges, event_risk

    original = _execution()
    monkeypatch.setitem(charges.CHARGE_SCHEDULE["NFO_FUT"], "gst_pct", 0.19)
    assert _execution() != original
    monkeypatch.undo()

    original = _execution()
    changed_rule = replace(event_risk.DEFAULT_RULES[0], before_minutes=31)
    monkeypatch.setattr(event_risk, "DEFAULT_RULES",
                        (changed_rule, *event_risk.DEFAULT_RULES[1:]))
    assert _execution() != original


@pytest.mark.parametrize(
    "name,new_value",
    [
        ("stop_loss_pct", 0.36),
        ("target_pct", 0.61),
        ("iv_rv_multiplier", 1.16),
        ("premium_spread_pct", 0.021),
        ("entry_dte_days", 15),
        ("trail_enabled", False),
        ("trail_trigger_pct", 0.11),
        ("trail_first_step_lock_pct", 0.026),
        ("trail_step_lock_pct", 0.11),
    ],
)
def test_every_resolved_premium_parameter_changes_result_address(monkeypatch, name, new_value):
    from app.backtest import premium

    original = _execution()
    monkeypatch.setitem(premium.DEFAULT_PREMIUM_PARAMS, name, new_value)
    assert _execution() != original


@pytest.mark.parametrize(
    "name,new_value",
    [
        ("RISK_FREE_RATE", 0.066),
        ("RV_WINDOW_DAYS", 21),
        ("IV_FLOOR", 0.11),
        ("IV_CEIL", 2.1),
        ("EXPIRY_FLOOR_YEARS", 2.0 / 365.0),
        ("MIN_ENTRY_PREMIUM", 0.51),
        ("SECONDS_PER_YEAR", 366 * 86_400),
    ],
)
def test_every_premium_model_constant_changes_result_address(monkeypatch, name, new_value):
    from app.backtest import premium

    original = _execution()
    monkeypatch.setattr(premium, name, new_value)
    assert _execution() != original


def test_backtest_exit_policy_changes_result_address(monkeypatch):
    from app.backtest import engine

    original = _execution()
    monkeypatch.setattr(engine, "BACKTEST_EXIT_POLICY",
                        replace(engine.BACKTEST_EXIT_POLICY, ratchet=False))
    assert _execution() != original
