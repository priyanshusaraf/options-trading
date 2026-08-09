"""The benchmark harness has to stay honest, and a script rots faster than a module.

`scripts/sweep_benchmark.py` is where the sweep's published numbers come from. Two ways it
could quietly stop meaning anything:

1. **It stops exercising the real code.** A renamed function or a changed signature turns the
   harness into a broken script nobody runs, and the last recorded numbers silently become the
   permanent answer. So the suite drives it.
2. **Its inputs make a numerical claim vacuous.** `MockProvider` rounds OHLC to two decimals,
   which already hid a worker-side `round(x, 2)` from a bit-identity gate once
   (`tests/test_backtest_parallel.py`). The harness generates its own full-mantissa series
   precisely so it cannot repeat that, and that property is worth pinning rather than trusting.

This is the small in-suite parity test Task 7 asks for. It is deliberately tiny — the real
benchmark takes minutes and does not belong in the suite.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "sweep_benchmark.py"


def _harness():
    spec = importlib.util.spec_from_file_location("sweep_benchmark", _PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_harness_still_imports_and_exposes_its_contract():
    h = _harness()
    for name in ("measure_stages", "measure_sweep", "project", "TIERS"):
        assert hasattr(h, name), f"sweep_benchmark lost {name}; the published numbers came from it"
    assert set(h.TIERS) == {"100x5", "1000x5", "10000x5"}


def test_synthetic_candles_are_not_representable_in_two_decimals():
    """The whole reason the harness does not reuse MockProvider.

    If these round-trip through two decimals unchanged, any numerical comparison built on
    them is blind to exactly the drift it exists to catch.
    """
    h = _harness()
    candles = h._synthetic_candles(200, seed=1)
    assert len(candles) == 200
    offenders = [c for c in candles if round(c.close, 2) == c.close and round(c.open, 2) == c.open]
    assert not offenders, (
        f"{len(offenders)} of 200 synthetic bars are exactly two-decimal; a worker doing "
        f"round(x, 2) would be invisible to anything measured on this series")


def test_synthetic_candles_are_deterministic_and_ordered():
    """The owner's requirement is that an unchanged run reproduces. A benchmark whose own
    input drifts cannot measure that."""
    h = _harness()
    a = h._synthetic_candles(120, seed=7)
    b = h._synthetic_candles(120, seed=7)
    assert [(c.ts, c.open, c.high, c.low, c.close, c.volume) for c in a] == \
           [(c.ts, c.open, c.high, c.low, c.close, c.volume) for c in b]
    assert all(x.ts < y.ts for x, y in zip(a, a[1:])), "timestamps must be strictly increasing"
    assert all(c.high >= c.close and c.low <= c.close for c in a), "OHLC must stay coherent"
    assert h._synthetic_candles(120, seed=8)[0].close != a[0].close, "seeds must differ"


def test_stage_measurement_runs_against_the_real_engine():
    """One repeat, small series — proves the harness reaches the shipped functions."""
    h = _harness()
    stages = h.measure_stages(n_bars=120, repeats=1)
    assert set(stages) >= {"identity", "frame", "signals", "simulate"}
    for name in ("identity", "frame", "signals", "simulate"):
        assert stages[name], f"{name} produced no samples"
        assert stages[name]["p50"] > 0.0


def test_projection_arithmetic_is_what_it_claims():
    h = _harness()
    stages = {"a": {"p50": 10.0}, "b": {"p50": 5.0}}      # 15 ms/cell
    p = h.project(stages, cells=1000, bars=5000)
    assert p["per_cell_ms_p50"] == pytest.approx(15.0)
    assert p["compute_serial_s"] == pytest.approx(15.0)          # 15 ms x 1000
    assert p["provider_io_floor_s"] == pytest.approx(400.0)      # 1000 x 0.40 s
    assert p["cold_serial_s"] == pytest.approx(415.0)
    assert p["total_bars"] == 5_000_000
    assert p["store_bytes_est"] == 5_000_000 * 38


def test_the_io_floor_matches_the_adapter_it_claims_to_model():
    """The 0.40 s constant is Kite's documented historical limit. If the adapter's throttle
    changes, every cold-run projection in the design notes is wrong — so tie them together."""
    from app.providers.kite import _MIN_INTERVAL

    h = _harness()
    p = h.project({"x": {"p50": 0.0}}, cells=100, bars=1)
    assert p["provider_io_floor_s"] == pytest.approx(100 * _MIN_INTERVAL["historical"]), (
        "the benchmark's I/O floor no longer matches KiteProvider's historical throttle; "
        "the projections in the full-universe design note are stale")
