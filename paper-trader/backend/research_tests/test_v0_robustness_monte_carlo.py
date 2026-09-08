from __future__ import annotations

import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.ir.hashing import canonical_json, content_address
import research.robustness.monte_carlo as monte_carlo
from research.robustness.monte_carlo import (
    BOUNDS,
    MAXIMUM_ABSOLUTE_PATH_PNL_PAISE,
    MAXIMUM_DRAW_OPERATIONS,
    MAXIMUM_EQUITY_PAISE,
    MAXIMUM_ITERATIONS,
    MAXIMUM_STARTING_CAPITAL_PAISE,
    MAXIMUM_TRADE_PNL_PAISE,
    MAXIMUM_TRADES,
    MINIMUM_TRADE_PNL_PAISE,
    MINIMUM_ITERATIONS,
    MINIMUM_TRADES,
    PPM_SCALE,
    SplitMix64,
    StationaryTradeBootstrapRefusal,
    StationaryTradeBootstrapResult,
    _stationary_path_indices,
    reconstruct_stationary_trade_bootstrap,
    stationary_trade_bootstrap,
)


TRADES = tuple((17, -9, 6, -4, 11, -13, 8, 3, -2, 5) * 2)


def _run(**overrides):
    values = {
        "trade_net_pnl_paise": TRADES,
        "starting_capital_paise": 10_000,
        "seed": 7,
        "iterations": 100,
        "restart_probability_ppm": 250_000,
    }
    values.update(overrides)
    return stationary_trade_bootstrap(**values)


def _refusal(code: str, **overrides) -> None:
    with pytest.raises(StationaryTradeBootstrapRefusal) as caught:
        _run(**overrides)
    assert caught.value.code == code
    assert str(caught.value) == f"{code}: {caught.value.detail}"


def test_splitmix64_v1_golden_vector_and_no_shared_state():
    expected = (
        0xE220A8397B1DCDAF,
        0x6E789E6AA1B965F4,
        0x06C45D188009454F,
    )
    assert tuple(SplitMix64(0).next_uint64() for _ in range(1)) == expected[:1]
    left = SplitMix64(0)
    right = SplitMix64(0)
    assert tuple(left.next_uint64() for _ in expected) == expected
    assert tuple(right.next_uint64() for _ in expected) == expected


def test_stationary_blocks_preserve_adjacency_wrap_and_controlled_restart():
    class ScriptedDraws:
        def __init__(self):
            self.draws = iter((1, 999_999, 999_999, 0, 0, 999_999))

        def bounded(self, upper_exclusive: int) -> int:
            value = next(self.draws)
            assert 0 <= value < upper_exclusive
            return value

    # Start at 1, continue twice, restart at 0, then continue. This proves both
    # within-block adjacency and a non-adjacent geometric-block boundary.
    assert _stationary_path_indices(5, 5, 1, ScriptedDraws()) == (1, 2, 3, 0, 1)


def test_baseline_and_simulations_are_integer_exact_and_reproducible():
    trades = (10, -4, -8, 15, -2) * 4
    first = _run(trade_net_pnl_paise=trades)
    second = _run(trade_net_pnl_paise=trades)
    document = first.document

    assert document["baseline"] == {
        "terminal_capital_paise": 10_044,
        "terminal_pnl_paise": 44,
        "maximum_drawdown_paise": 12,
    }
    assert len(document["distributions"]["terminal_pnl_paise"]) == 100
    assert len(document["distributions"]["maximum_drawdown_paise"]) == 100
    assert all(type(value) is int for value in document["distributions"]["terminal_pnl_paise"])
    assert all(type(value) is int for value in document["distributions"]["maximum_drawdown_paise"])
    # Every pseudo-path is a resample of exactly n observations, so its terminal
    # PnL need not equal the observed sum; the zero-vector pins baseline equality.
    zeros = _run(trade_net_pnl_paise=(0,) * MINIMUM_TRADES)
    assert zeros.document["baseline"]["terminal_pnl_paise"] == 0
    assert zeros.document["distributions"]["terminal_pnl_paise"] == (0,) * 100
    assert zeros.document["distributions"]["maximum_drawdown_paise"] == (0,) * 100
    assert first.document == second.document
    assert first.address == second.address
    assert first.canonical_bytes() == second.canonical_bytes()
    assert content_address(json.loads(first.canonical_bytes())) == first.address


def test_nearest_rank_summaries_are_derived_from_retained_distributions():
    result = _run()
    for name in ("terminal_pnl_paise", "maximum_drawdown_paise"):
        ordered = sorted(result.document["distributions"][name])
        assert result.document["summaries"][name] == {
            "minimum": ordered[0],
            "p05_nearest_rank": ordered[4],
            "p50_nearest_rank": ordered[49],
            "p95_nearest_rank": ordered[94],
            "maximum": ordered[-1],
        }


def test_document_is_closed_frozen_content_addressed_and_states_method_limits():
    result = _run()
    assert set(result.document) == {
        "schema",
        "algorithm_version",
        "prng_version",
        "bounds",
        "input",
        "ordered_trade_digest",
        "baseline",
        "distributions",
        "summaries",
        "source",
        "preserved_dependencies",
        "lost_dependencies",
        "limitations",
    }
    assert result.document["schema"] == "strategy-os-stationary-trade-bootstrap/1"
    assert result.document["prng_version"] == "splitmix64/1"
    assert "weakly dependent stationary observations" in result.document["source"]["claim"]
    assert result.document["source"]["doi"] == "10.1080/01621459.1994.10476870"
    assert "not proved stationary" in result.document["limitations"][0]
    assert "future-market or profitability guarantee" in result.document["limitations"][-1]
    assert "within_block_local_trade_order" in result.document["preserved_dependencies"]
    assert "calendar_timing" in result.document["lost_dependencies"]
    with pytest.raises(TypeError):
        result.document["seed"] = 9
    with pytest.raises(TypeError):
        result.document["bounds"]["maximum_iterations"] = 9

    mutable = json.loads(result.canonical_bytes())
    copied = reconstruct_stationary_trade_bootstrap(result.canonical_bytes(), result.address)
    mutable["input"]["seed"] = 999
    assert copied.document["input"]["seed"] == 7

    malformed = json.loads(result.canonical_bytes())
    malformed["summaries"]["terminal_pnl_paise"]["maximum"] += 1
    with pytest.raises(StationaryTradeBootstrapRefusal) as caught:
        reconstruct_stationary_trade_bootstrap(
            canonical_json(malformed).encode(), content_address(malformed)
        )
    assert caught.value.code == "RESULT_SUMMARY_INVALID"

    with pytest.raises(TypeError):
        StationaryTradeBootstrapResult(mutable, result.address)


def test_public_reconstruction_replays_and_refuses_self_consistent_forged_distribution():
    result = _run()
    forged = json.loads(result.canonical_bytes())
    values = forged["distributions"]["terminal_pnl_paise"]
    values[0] += 1
    ordered = sorted(values)
    forged["summaries"]["terminal_pnl_paise"] = {
        "minimum": ordered[0],
        "p05_nearest_rank": ordered[4],
        "p50_nearest_rank": ordered[49],
        "p95_nearest_rank": ordered[94],
        "maximum": ordered[-1],
    }
    payload = canonical_json(forged).encode()
    with pytest.raises(StationaryTradeBootstrapRefusal) as caught:
        reconstruct_stationary_trade_bootstrap(payload, content_address(forged))
    assert caught.value.code == "RESULT_SEMANTIC_REPLAY_MISMATCH"


@pytest.mark.parametrize(
    ("field", "replacement", "code"),
    (
        ("algorithm_version", "stationary-circular-geometric-blocks/2", "RESULT_METHOD_INVALID"),
        ("source", {"forged": "source"}, "RESULT_LIMITATIONS_INVALID"),
        ("limitations", ["forged limitation"], "RESULT_LIMITATIONS_INVALID"),
        ("bounds", {"forged": 1}, "RESULT_BOUNDS_INVALID"),
    ),
)
def test_public_reconstruction_refuses_readdressed_method_source_limit_tampering(
    field, replacement, code
):
    forged = json.loads(_run().canonical_bytes())
    forged[field] = replacement
    with pytest.raises(StationaryTradeBootstrapRefusal) as caught:
        reconstruct_stationary_trade_bootstrap(
            canonical_json(forged).encode(), content_address(forged)
        )
    assert caught.value.code == code


def test_public_reconstruction_requires_exact_canonical_bytes_and_address():
    result = _run()
    with pytest.raises(StationaryTradeBootstrapRefusal) as caught:
        reconstruct_stationary_trade_bootstrap(result.canonical_bytes(), "sha256:" + "0" * 64)
    assert caught.value.code == "RESULT_ADDRESS_INVALID"
    with pytest.raises(StationaryTradeBootstrapRefusal) as caught:
        reconstruct_stationary_trade_bootstrap(
            json.dumps(json.loads(result.canonical_bytes()), indent=2).encode(), result.address
        )
    assert caught.value.code == "RESULT_PAYLOAD_NOT_CANONICAL"
    with pytest.raises(StationaryTradeBootstrapRefusal) as caught:
        reconstruct_stationary_trade_bootstrap(b"\xff", result.address)
    assert caught.value.code == "RESULT_PAYLOAD_INVALID_UTF8"


def test_seed_order_value_and_all_identity_contributors_change_address():
    base = _run()
    assert _run(seed=8).address != base.address
    assert _run(trade_net_pnl_paise=tuple(reversed(TRADES))).address != base.address
    changed = list(TRADES)
    changed[0] += 1
    assert _run(trade_net_pnl_paise=tuple(changed)).address != base.address

    for field, replacement in (
        ("algorithm_version", "stationary-circular-geometric-blocks/2"),
        ("prng_version", "splitmix64/2"),
        ("bounds", {**dict(base.document["bounds"]), "maximum_iterations": 5_001}),
        ("limitations", (*base.document["limitations"], "additional explicit limitation")),
    ):
        altered = copy.deepcopy(json.loads(base.canonical_bytes()))
        altered[field] = replacement
        assert content_address(altered) != base.address


def test_separate_processes_emit_byte_identical_document_and_address():
    backend = Path(__file__).resolve().parents[1]
    program = """
from research.robustness.monte_carlo import stationary_trade_bootstrap
result = stationary_trade_bootstrap(
    tuple((17, -9, 6, -4, 11, -13, 8, 3, -2, 5) * 2),
    starting_capital_paise=10000, seed=7, iterations=100,
    restart_probability_ppm=250000,
)
print(result.address)
print(result.canonical_bytes().decode('utf-8'))
"""
    env = {**os.environ, "PYTHONPATH": str(backend), "PYTHONHASHSEED": "random"}
    one = subprocess.run(
        [sys.executable, "-c", program], cwd=backend, env=env,
        check=True, capture_output=True,
    ).stdout
    two = subprocess.run(
        [sys.executable, "-c", program], cwd=backend, env=env,
        check=True, capture_output=True,
    ).stdout
    assert one == two


@pytest.mark.parametrize(
    ("overrides", "code"),
    (
        ({"trade_net_pnl_paise": [*TRADES]}, "TRADE_SEQUENCE_NOT_IMMUTABLE"),
        ({"trade_net_pnl_paise": TRADES[:-1]}, "TRADE_COUNT_OUT_OF_RANGE"),
        ({"trade_net_pnl_paise": (*TRADES[:-1], True)}, "TRADE_VALUE_NOT_INTEGER"),
        ({"trade_net_pnl_paise": (*TRADES[:-1], 1.0)}, "TRADE_VALUE_NOT_INTEGER"),
        ({"trade_net_pnl_paise": (*TRADES[:-1], float("inf"))}, "TRADE_VALUE_NOT_INTEGER"),
        ({"starting_capital_paise": True}, "STARTING_CAPITAL_NOT_POSITIVE_INTEGER"),
        ({"starting_capital_paise": 0}, "STARTING_CAPITAL_NOT_POSITIVE_INTEGER"),
        ({"starting_capital_paise": -1}, "STARTING_CAPITAL_NOT_POSITIVE_INTEGER"),
        ({"starting_capital_paise": -0.0}, "STARTING_CAPITAL_NOT_POSITIVE_INTEGER"),
        ({"seed": True}, "SEED_NOT_UINT64"),
        ({"seed": -1}, "SEED_NOT_UINT64"),
        ({"seed": 1 << 64}, "SEED_NOT_UINT64"),
        ({"iterations": True}, "ITERATIONS_OUT_OF_RANGE"),
        ({"iterations": MINIMUM_ITERATIONS - 1}, "ITERATIONS_OUT_OF_RANGE"),
        ({"iterations": MAXIMUM_ITERATIONS + 1}, "ITERATIONS_OUT_OF_RANGE"),
        ({"restart_probability_ppm": True}, "RESTART_PROBABILITY_OUT_OF_RANGE"),
        ({"restart_probability_ppm": 1.0}, "RESTART_PROBABILITY_OUT_OF_RANGE"),
        ({"restart_probability_ppm": 0}, "RESTART_PROBABILITY_OUT_OF_RANGE"),
        ({"restart_probability_ppm": PPM_SCALE + 1}, "RESTART_PROBABILITY_OUT_OF_RANGE"),
    ),
)
def test_invalid_numeric_and_structural_inputs_refuse_stably(overrides, code):
    _refusal(code, **overrides)


def test_trade_iteration_probability_seed_and_combined_operation_boundaries():
    _run(trade_net_pnl_paise=(0,) * MINIMUM_TRADES)
    _run(trade_net_pnl_paise=(0,) * MAXIMUM_TRADES, iterations=MINIMUM_ITERATIONS)
    _run(iterations=MINIMUM_ITERATIONS)
    _run(iterations=MAXIMUM_ITERATIONS, trade_net_pnl_paise=(0,) * 400)
    _run(restart_probability_ppm=1)
    _run(restart_probability_ppm=PPM_SCALE)
    _run(seed=0)
    _run(seed=(1 << 64) - 1)
    _run(trade_net_pnl_paise=(0,) * 10_000, iterations=200)
    assert MAXIMUM_DRAW_OPERATIONS == 2_000_000
    _refusal(
        "DRAW_OPERATION_LIMIT_EXCEEDED",
        trade_net_pnl_paise=(0,) * 10_000,
        iterations=201,
    )
    _refusal("TRADE_COUNT_OUT_OF_RANGE", trade_net_pnl_paise=(0,) * (MAXIMUM_TRADES + 1))


def test_all_monetary_bounds_are_addressed_and_starting_capital_is_bounded():
    result = _run(starting_capital_paise=MAXIMUM_STARTING_CAPITAL_PAISE)
    assert dict(BOUNDS) == result.document["bounds"]
    assert result.document["bounds"] | {
        "maximum_starting_capital_paise": MAXIMUM_STARTING_CAPITAL_PAISE,
        "minimum_trade_pnl_paise": MINIMUM_TRADE_PNL_PAISE,
        "maximum_trade_pnl_paise": MAXIMUM_TRADE_PNL_PAISE,
        "maximum_absolute_path_pnl_paise": MAXIMUM_ABSOLUTE_PATH_PNL_PAISE,
        "maximum_equity_paise": MAXIMUM_EQUITY_PAISE,
    } == result.document["bounds"]
    _run(starting_capital_paise=1, trade_net_pnl_paise=(0,) * MINIMUM_TRADES)
    _refusal("STARTING_CAPITAL_NOT_POSITIVE_INTEGER", starting_capital_paise=0)
    _refusal(
        "STARTING_CAPITAL_OUT_OF_RANGE",
        starting_capital_paise=MAXIMUM_STARTING_CAPITAL_PAISE + 1,
    )
    _refusal("STARTING_CAPITAL_OUT_OF_RANGE", starting_capital_paise=10**5000)


def test_trade_int64_and_worst_case_path_magnitude_below_at_above_boundaries():
    # 2^63-1 is divisible by 49, so this vector hits the worst-case path bound
    # exactly while every possible pseudo-path remains inside [0, 2^64-2].
    count = 49
    magnitude = MAXIMUM_ABSOLUTE_PATH_PNL_PAISE // count
    assert magnitude * count == MAXIMUM_ABSOLUTE_PATH_PNL_PAISE
    below = (magnitude - 1,) * count
    boundary = (magnitude,) * count
    drawdown_boundary = (-magnitude,) * count
    _run(
        trade_net_pnl_paise=below,
        starting_capital_paise=MAXIMUM_STARTING_CAPITAL_PAISE,
    )
    result = _run(
        trade_net_pnl_paise=boundary,
        starting_capital_paise=MAXIMUM_STARTING_CAPITAL_PAISE,
    )
    reconstructed = reconstruct_stationary_trade_bootstrap(
        result.canonical_bytes(), result.address
    )
    assert reconstructed.canonical_bytes() == result.canonical_bytes()
    assert reconstructed.address == result.address
    assert result.document["baseline"] == {
        "terminal_capital_paise": MAXIMUM_EQUITY_PAISE,
        "terminal_pnl_paise": MAXIMUM_ABSOLUTE_PATH_PNL_PAISE,
        "maximum_drawdown_paise": 0,
    }
    assert all(
        abs(value) <= MAXIMUM_ABSOLUTE_PATH_PNL_PAISE
        for value in result.document["distributions"]["terminal_pnl_paise"]
    )
    assert all(
        0 <= value <= MAXIMUM_ABSOLUTE_PATH_PNL_PAISE
        for value in result.document["distributions"]["maximum_drawdown_paise"]
    )
    drawdown_result = _run(
        trade_net_pnl_paise=drawdown_boundary,
        starting_capital_paise=MAXIMUM_STARTING_CAPITAL_PAISE,
    )
    assert drawdown_result.document["baseline"] == {
        "terminal_capital_paise": 0,
        "terminal_pnl_paise": -MAXIMUM_ABSOLUTE_PATH_PNL_PAISE,
        "maximum_drawdown_paise": MAXIMUM_ABSOLUTE_PATH_PNL_PAISE,
    }
    _refusal(
        "ABSOLUTE_PATH_PNL_LIMIT_EXCEEDED",
        trade_net_pnl_paise=(magnitude + 1,) * count,
        starting_capital_paise=MAXIMUM_STARTING_CAPITAL_PAISE,
    )

    _refusal(
        "ABSOLUTE_PATH_PNL_LIMIT_EXCEEDED",
        trade_net_pnl_paise=(MAXIMUM_TRADE_PNL_PAISE,) + (0,) * 19,
    )
    _refusal(
        "ABSOLUTE_PATH_PNL_LIMIT_EXCEEDED",
        trade_net_pnl_paise=(MINIMUM_TRADE_PNL_PAISE,) + (0,) * 19,
    )
    _refusal(
        "TRADE_VALUE_OUT_OF_RANGE",
        trade_net_pnl_paise=(MAXIMUM_TRADE_PNL_PAISE + 1,) + (0,) * 19,
    )
    _refusal(
        "TRADE_VALUE_OUT_OF_RANGE",
        trade_net_pnl_paise=(MINIMUM_TRADE_PNL_PAISE - 1,) + (0,) * 19,
    )
    _refusal(
        "TRADE_VALUE_OUT_OF_RANGE",
        trade_net_pnl_paise=(10**5000,) + (0,) * 19,
    )


def test_maximum_count_accepts_its_maximum_safe_magnitude_without_derived_overflow():
    magnitude = MAXIMUM_ABSOLUTE_PATH_PNL_PAISE // MAXIMUM_TRADES
    trades = (magnitude,) * MAXIMUM_TRADES
    result = _run(
        trade_net_pnl_paise=trades,
        starting_capital_paise=MAXIMUM_STARTING_CAPITAL_PAISE,
        iterations=MINIMUM_ITERATIONS,
    )
    assert result.document["baseline"]["terminal_capital_paise"] \
        == MAXIMUM_STARTING_CAPITAL_PAISE + magnitude * MAXIMUM_TRADES
    assert all(
        0 <= result.document["input"]["starting_capital_paise"] + terminal
        <= MAXIMUM_EQUITY_PAISE
        for terminal in result.document["distributions"]["terminal_pnl_paise"]
    )


@pytest.mark.parametrize(
    ("field", "replacement", "code"),
    (
        ("starting_capital_paise", MAXIMUM_STARTING_CAPITAL_PAISE + 1,
         "STARTING_CAPITAL_OUT_OF_RANGE"),
        ("starting_capital_paise", True, "STARTING_CAPITAL_NOT_POSITIVE_INTEGER"),
        ("starting_capital_paise", 1.0, "STARTING_CAPITAL_NOT_POSITIVE_INTEGER"),
    ),
)
def test_reconstruction_translates_over_bound_boolean_and_float_capital(field, replacement, code):
    forged = json.loads(_run().canonical_bytes())
    forged["input"][field] = replacement
    payload = canonical_json(forged).encode()
    with pytest.raises(StationaryTradeBootstrapRefusal) as caught:
        reconstruct_stationary_trade_bootstrap(payload, content_address(forged))
    assert caught.value.code == code


@pytest.mark.parametrize(
    ("replacement", "code"),
    (
        (MAXIMUM_TRADE_PNL_PAISE + 1, "TRADE_VALUE_OUT_OF_RANGE"),
        (True, "TRADE_VALUE_NOT_INTEGER"),
        (1.0, "TRADE_VALUE_NOT_INTEGER"),
    ),
)
def test_reconstruction_translates_over_bound_boolean_and_float_trade(replacement, code):
    forged = json.loads(_run().canonical_bytes())
    forged["input"]["trade_net_pnl_paise"][0] = replacement
    payload = canonical_json(forged).encode()
    with pytest.raises(StationaryTradeBootstrapRefusal) as caught:
        reconstruct_stationary_trade_bootstrap(payload, content_address(forged))
    assert caught.value.code == code


def test_reconstruction_translates_python_integer_digit_limit_to_typed_refusal():
    payload = _run().canonical_bytes()
    huge = b"1" + (b"0" * 5000)
    payload = payload.replace(b'"starting_capital_paise":10000',
                              b'"starting_capital_paise":' + huge)
    with pytest.raises(StationaryTradeBootstrapRefusal) as caught:
        reconstruct_stationary_trade_bootstrap(payload, "sha256:" + "0" * 64)
    assert caught.value.code == "RESULT_PAYLOAD_INTEGER_OUT_OF_RANGE"


@pytest.mark.parametrize(
    ("distribution", "replacement"),
    (
        ("terminal_pnl_paise", MAXIMUM_ABSOLUTE_PATH_PNL_PAISE + 1),
        ("maximum_drawdown_paise", MAXIMUM_ABSOLUTE_PATH_PNL_PAISE + 1),
    ),
)
def test_reconstruction_refuses_readdressed_derived_values_above_path_bound(
    distribution, replacement
):
    forged = json.loads(_run().canonical_bytes())
    values = forged["distributions"][distribution]
    values[0] = replacement
    ordered = sorted(values)
    forged["summaries"][distribution] = {
        "minimum": ordered[0],
        "p05_nearest_rank": ordered[4],
        "p50_nearest_rank": ordered[49],
        "p95_nearest_rank": ordered[94],
        "maximum": ordered[-1],
    }
    payload = canonical_json(forged).encode()
    with pytest.raises(StationaryTradeBootstrapRefusal) as caught:
        reconstruct_stationary_trade_bootstrap(payload, content_address(forged))
    assert caught.value.code == "RESULT_DERIVED_VALUE_OUT_OF_RANGE"


def test_magnitude_preflight_runs_before_rng_loops_or_canonical_serialization(monkeypatch):
    touched = []

    def forbidden(*_args, **_kwargs):
        touched.append(True)
        raise AssertionError("expensive work ran before magnitude refusal")

    monkeypatch.setattr(monte_carlo, "SplitMix64", forbidden)
    monkeypatch.setattr(monte_carlo, "content_address", forbidden)
    _refusal("STARTING_CAPITAL_OUT_OF_RANGE", starting_capital_paise=10**5000)
    _refusal(
        "TRADE_VALUE_OUT_OF_RANGE",
        trade_net_pnl_paise=(10**5000,) + (0,) * 19,
    )
    assert touched == []


def test_baseline_and_simulated_insolvency_refuse_without_partial_result():
    _refusal(
        "BASELINE_CAPITAL_BELOW_ZERO",
        trade_net_pnl_paise=(-101, *((0,) * 19)),
        starting_capital_paise=100,
    )
    _refusal(
        "SIMULATED_CAPITAL_BELOW_ZERO",
        trade_net_pnl_paise=(70, -60, *((0,) * 18)),
        starting_capital_paise=50,
        seed=0,
        iterations=100,
        restart_probability_ppm=1,
    )


def test_module_static_boundary_has_only_stdlib_and_canonical_hash_authority():
    module_path = Path(__file__).parents[1] / "research" / "robustness" / "monte_carlo.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    assert imports <= {
        "__future__",
        "dataclasses",
        "json",
        "types",
        "typing",
        "app.ir.hashing",
    }
    source = module_path.read_text(encoding="utf-8")
    for forbidden in ("random.", "numpy.", "pandas.", "os.environ", "open("):
        assert forbidden not in source.lower()
    assert "from app.ir.hashing import canonical_json, content_address" in source
    assert canonical_json(json.loads(_run().canonical_bytes())) == _run().canonical_bytes().decode()
