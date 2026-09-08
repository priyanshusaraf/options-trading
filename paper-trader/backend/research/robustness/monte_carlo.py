"""Bounded deterministic stationary bootstrap for ordered net trade PnL.

This pure method resamples observed, cost-inclusive integer trade outcomes. It
does not create prices, market events, orders, fills, or execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import Any, Mapping

from app.ir.hashing import canonical_json, content_address


SCHEMA = "strategy-os-stationary-trade-bootstrap/1"
ALGORITHM_VERSION = "stationary-circular-geometric-blocks/1"
PRNG_VERSION = "splitmix64/1"
MINIMUM_TRADES = 20
MAXIMUM_TRADES = 10_000
MINIMUM_ITERATIONS = 100
MAXIMUM_ITERATIONS = 5_000
MAXIMUM_DRAW_OPERATIONS = 2_000_000
PPM_SCALE = 1_000_000
UINT64_SIZE = 1 << 64
UINT64_MASK = UINT64_SIZE - 1
MINIMUM_TRADE_PNL_PAISE = -(1 << 63)
MAXIMUM_TRADE_PNL_PAISE = (1 << 63) - 1
MAXIMUM_STARTING_CAPITAL_PAISE = MAXIMUM_TRADE_PNL_PAISE
MAXIMUM_ABSOLUTE_PATH_PNL_PAISE = MAXIMUM_TRADE_PNL_PAISE
MAXIMUM_EQUITY_PAISE = (1 << 64) - 2

BOUNDS = MappingProxyType({
    "minimum_trades": MINIMUM_TRADES,
    "maximum_trades": MAXIMUM_TRADES,
    "minimum_iterations": MINIMUM_ITERATIONS,
    "maximum_iterations": MAXIMUM_ITERATIONS,
    "maximum_draw_operations": MAXIMUM_DRAW_OPERATIONS,
    "minimum_restart_probability_ppm": 1,
    "maximum_restart_probability_ppm": PPM_SCALE,
    "maximum_starting_capital_paise": MAXIMUM_STARTING_CAPITAL_PAISE,
    "minimum_trade_pnl_paise": MINIMUM_TRADE_PNL_PAISE,
    "maximum_trade_pnl_paise": MAXIMUM_TRADE_PNL_PAISE,
    "maximum_absolute_path_pnl_paise": MAXIMUM_ABSOLUTE_PATH_PNL_PAISE,
    "maximum_equity_paise": MAXIMUM_EQUITY_PAISE,
})
SOURCE = MappingProxyType({
    "title": "The Stationary Bootstrap",
    "authors": "D. N. Politis and J. P. Romano",
    "publication": "Journal of the American Statistical Association 89(428), 1994",
    "doi": "10.1080/01621459.1994.10476870",
    "url": "https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870",
    "claim": (
        "A stationary bootstrap forms pseudo-series from randomly sized circular "
        "blocks to support inference for weakly dependent stationary observations."
    ),
})
PRESERVED_DEPENDENCIES = (
    "cost_inclusive_integer_net_trade_pnl",
    "observed_trade_count_per_pseudo_path",
    "observed_trade_outcome_support",
    "within_block_local_trade_order",
)
LOST_DEPENDENCIES = (
    "calendar_timing",
    "market_regime_and_nonstationarity",
    "cross_asset_dependence",
    "market_impact",
    "unobserved_execution_dependence",
)
LIMITATIONS = (
    "Observed strategy trades are not proved stationary.",
    "Circular geometric blocks preserve only some local ordering in the supplied trade sequence.",
    "Calendar, regime, cross-asset, market-impact and unobserved execution dependencies are lost.",
    "The output is a conditional stress distribution, never a future-market or profitability guarantee.",
)
DOCUMENT_FIELDS = frozenset({
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
})


class StationaryTradeBootstrapRefusal(ValueError):
    """Stable closed refusal raised before a result can be published."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True, init=False)
class StationaryTradeBootstrapResult:
    """An immutable canonical method document and its canonical address."""

    document: Mapping[str, Any]
    address: str

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError(
            "StationaryTradeBootstrapResult cannot be constructed directly; "
            "use stationary_trade_bootstrap or reconstruct_stationary_trade_bootstrap"
        )

    @classmethod
    def _from_generated(
        cls, document: Mapping[str, Any], address: str
    ) -> StationaryTradeBootstrapResult:
        """Private single-pass construction for a document generated in this module."""
        plain = _plain(document)
        _validate_result_document(plain)
        if content_address(plain) != address:
            raise StationaryTradeBootstrapRefusal(
                "RESULT_ADDRESS_INVALID", "stationary bootstrap result address is stale or forged"
            )
        instance = object.__new__(cls)
        object.__setattr__(instance, "document", _freeze(plain))
        object.__setattr__(instance, "address", address)
        return instance

    def canonical_bytes(self) -> bytes:
        return canonical_json(_plain(self.document)).encode("utf-8")


class SplitMix64:
    """Local SplitMix64/1 state; instances share no process-global RNG state."""

    __slots__ = ("_state",)

    def __init__(self, seed: int) -> None:
        if type(seed) is not int or not 0 <= seed < UINT64_SIZE:
            _refuse("SEED_NOT_UINT64", "seed must be an integer in uint64 range")
        self._state = seed

    def next_uint64(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & UINT64_MASK
        value = self._state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & UINT64_MASK
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & UINT64_MASK
        return (value ^ (value >> 31)) & UINT64_MASK

    def bounded(self, upper_exclusive: int) -> int:
        if type(upper_exclusive) is not int or upper_exclusive <= 0 \
                or upper_exclusive > UINT64_SIZE:
            _refuse("PRNG_BOUND_INVALID", "SplitMix64 bound must be in 1..2^64")
        cutoff = UINT64_SIZE - (UINT64_SIZE % upper_exclusive)
        while True:
            value = self.next_uint64()
            if value < cutoff:
                return value % upper_exclusive


def stationary_trade_bootstrap(
    trade_net_pnl_paise: tuple[int, ...],
    *,
    starting_capital_paise: int,
    seed: int,
    iterations: int,
    restart_probability_ppm: int,
) -> StationaryTradeBootstrapResult:
    """Return a deterministic bounded stationary-bootstrap stress distribution."""
    trades = _validate_inputs(
        trade_net_pnl_paise,
        starting_capital_paise=starting_capital_paise,
        seed=seed,
        iterations=iterations,
        restart_probability_ppm=restart_probability_ppm,
    )
    baseline = _path_metrics(
        trades,
        starting_capital_paise,
        insolvency_code="BASELINE_CAPITAL_BELOW_ZERO",
    )
    rng = SplitMix64(seed)
    terminal_distribution: list[int] = []
    drawdown_distribution: list[int] = []
    trade_count = len(trades)
    for _ in range(iterations):
        indices = _stationary_path_indices(
            trade_count, trade_count, restart_probability_ppm, rng
        )
        path = tuple(trades[index] for index in indices)
        metrics = _path_metrics(
            path,
            starting_capital_paise,
            insolvency_code="SIMULATED_CAPITAL_BELOW_ZERO",
        )
        terminal_distribution.append(metrics["terminal_pnl_paise"])
        drawdown_distribution.append(metrics["maximum_drawdown_paise"])

    trade_document = {"ordered_trade_net_pnl_paise": list(trades)}
    document = {
        "schema": SCHEMA,
        "algorithm_version": ALGORITHM_VERSION,
        "prng_version": PRNG_VERSION,
        "bounds": dict(BOUNDS),
        "input": {
            "trade_net_pnl_paise": list(trades),
            "starting_capital_paise": starting_capital_paise,
            "seed": seed,
            "iterations": iterations,
            "restart_probability_ppm": restart_probability_ppm,
        },
        "ordered_trade_digest": content_address(trade_document),
        "baseline": baseline,
        "distributions": {
            "terminal_pnl_paise": terminal_distribution,
            "maximum_drawdown_paise": drawdown_distribution,
        },
        "summaries": {
            "terminal_pnl_paise": _summary(terminal_distribution),
            "maximum_drawdown_paise": _summary(drawdown_distribution),
        },
        "source": dict(SOURCE),
        "preserved_dependencies": list(PRESERVED_DEPENDENCIES),
        "lost_dependencies": list(LOST_DEPENDENCIES),
        "limitations": list(LIMITATIONS),
    }
    address = content_address(document)
    return StationaryTradeBootstrapResult._from_generated(document, address)


def reconstruct_stationary_trade_bootstrap(
    canonical_payload: bytes, expected_address: str
) -> StationaryTradeBootstrapResult:
    """Decode and semantically replay an addressed canonical result document."""
    if type(canonical_payload) is not bytes:
        _refuse("RESULT_PAYLOAD_NOT_BYTES", "canonical result payload must be bytes")
    if not isinstance(expected_address, str):
        _refuse("RESULT_ADDRESS_INVALID", "expected result address must be a string")
    try:
        text = canonical_payload.decode("utf-8")
    except UnicodeDecodeError:
        _refuse("RESULT_PAYLOAD_INVALID_UTF8", "canonical result payload is not UTF-8")
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        _refuse("RESULT_PAYLOAD_INVALID_JSON", "canonical result payload is not valid JSON")
    except ValueError:
        _refuse(
            "RESULT_PAYLOAD_INTEGER_OUT_OF_RANGE",
            "canonical result payload contains an oversized integer",
        )
    except RecursionError:
        _refuse("RESULT_PAYLOAD_INVALID_JSON", "canonical result payload is too deeply nested")
    if not isinstance(document, dict):
        _refuse("RESULT_SCHEMA_INVALID", "stationary bootstrap result must be a JSON object")
    try:
        rendered = canonical_json(document).encode("utf-8")
    except (TypeError, ValueError):
        _refuse("RESULT_PAYLOAD_INVALID_JSON", "canonical result contains invalid JSON values")
    if rendered != canonical_payload:
        _refuse("RESULT_PAYLOAD_NOT_CANONICAL", "result payload bytes are not canonical")
    if content_address(document) != expected_address:
        _refuse("RESULT_ADDRESS_INVALID", "result payload does not match its expected address")

    _validate_result_document(document)
    inputs = document["input"]
    replayed = stationary_trade_bootstrap(
        tuple(inputs["trade_net_pnl_paise"]),
        starting_capital_paise=inputs["starting_capital_paise"],
        seed=inputs["seed"],
        iterations=inputs["iterations"],
        restart_probability_ppm=inputs["restart_probability_ppm"],
    )
    if replayed.address != expected_address or replayed.canonical_bytes() != canonical_payload:
        _refuse(
            "RESULT_SEMANTIC_REPLAY_MISMATCH",
            "addressed result does not match deterministic method replay",
        )
    return replayed


def _validate_inputs(
    trades: tuple[int, ...],
    *,
    starting_capital_paise: int,
    seed: int,
    iterations: int,
    restart_probability_ppm: int,
) -> tuple[int, ...]:
    if type(trades) is not tuple:
        _refuse("TRADE_SEQUENCE_NOT_IMMUTABLE", "trade net PnL must be supplied as a tuple")
    trade_count = len(trades)
    if not MINIMUM_TRADES <= trade_count <= MAXIMUM_TRADES:
        _refuse(
            "TRADE_COUNT_OUT_OF_RANGE",
            f"trade count must be in {MINIMUM_TRADES}..{MAXIMUM_TRADES}",
        )
    if any(type(value) is not int for value in trades):
        _refuse("TRADE_VALUE_NOT_INTEGER", "every net trade PnL value must be an integer")
    if any(
        value < MINIMUM_TRADE_PNL_PAISE or value > MAXIMUM_TRADE_PNL_PAISE
        for value in trades
    ):
        _refuse(
            "TRADE_VALUE_OUT_OF_RANGE",
            "every net trade PnL value must fit signed int64 paise",
        )
    if type(starting_capital_paise) is not int or starting_capital_paise <= 0:
        _refuse(
            "STARTING_CAPITAL_NOT_POSITIVE_INTEGER",
            "starting capital must be a positive integer number of paise",
        )
    if starting_capital_paise > MAXIMUM_STARTING_CAPITAL_PAISE:
        _refuse(
            "STARTING_CAPITAL_OUT_OF_RANGE",
            "starting capital must not exceed signed int64 maximum paise",
        )
    maximum_magnitude = max(abs(value) for value in trades)
    if maximum_magnitude * trade_count > MAXIMUM_ABSOLUTE_PATH_PNL_PAISE:
        _refuse(
            "ABSOLUTE_PATH_PNL_LIMIT_EXCEEDED",
            "worst-case absolute path PnL exceeds the signed path bound",
        )
    if type(seed) is not int or not 0 <= seed < UINT64_SIZE:
        _refuse("SEED_NOT_UINT64", "seed must be an integer in uint64 range")
    if type(iterations) is not int \
            or not MINIMUM_ITERATIONS <= iterations <= MAXIMUM_ITERATIONS:
        _refuse(
            "ITERATIONS_OUT_OF_RANGE",
            f"iterations must be in {MINIMUM_ITERATIONS}..{MAXIMUM_ITERATIONS}",
        )
    if type(restart_probability_ppm) is not int \
            or not 1 <= restart_probability_ppm <= PPM_SCALE:
        _refuse(
            "RESTART_PROBABILITY_OUT_OF_RANGE",
            f"restart probability must be an integer in 1..{PPM_SCALE} ppm",
        )
    draw_operations = trade_count * iterations
    if draw_operations > MAXIMUM_DRAW_OPERATIONS:
        _refuse(
            "DRAW_OPERATION_LIMIT_EXCEEDED",
            f"requested {draw_operations} draws exceeds {MAXIMUM_DRAW_OPERATIONS}",
        )
    return trades


def _validate_result_document(document: dict[str, Any]) -> None:
    if set(document) != DOCUMENT_FIELDS or document.get("schema") != SCHEMA:
        _refuse("RESULT_SCHEMA_INVALID", "stationary bootstrap result is open or incomplete")
    if document["algorithm_version"] != ALGORITHM_VERSION \
            or document["prng_version"] != PRNG_VERSION:
        _refuse("RESULT_METHOD_INVALID", "stationary bootstrap method identity is invalid")
    if document["bounds"] != dict(BOUNDS):
        _refuse("RESULT_BOUNDS_INVALID", "stationary bootstrap bounds identity is invalid")
    if document["source"] != dict(SOURCE) \
            or document["preserved_dependencies"] != list(PRESERVED_DEPENDENCIES) \
            or document["lost_dependencies"] != list(LOST_DEPENDENCIES) \
            or document["limitations"] != list(LIMITATIONS):
        _refuse("RESULT_LIMITATIONS_INVALID", "source or dependency limitations are invalid")
    inputs = document["input"]
    if not isinstance(inputs, dict) or set(inputs) != {
        "trade_net_pnl_paise",
        "starting_capital_paise",
        "seed",
        "iterations",
        "restart_probability_ppm",
    } or not isinstance(inputs["trade_net_pnl_paise"], list):
        _refuse("RESULT_INPUT_INVALID", "stationary bootstrap input record is malformed")
    trades = tuple(inputs["trade_net_pnl_paise"])
    _validate_inputs(
        trades,
        starting_capital_paise=inputs["starting_capital_paise"],
        seed=inputs["seed"],
        iterations=inputs["iterations"],
        restart_probability_ppm=inputs["restart_probability_ppm"],
    )
    if document["ordered_trade_digest"] != content_address({
        "ordered_trade_net_pnl_paise": list(trades)
    }):
        _refuse("RESULT_TRADE_DIGEST_INVALID", "ordered trade digest is stale or forged")
    expected_baseline = _path_metrics(
        trades,
        inputs["starting_capital_paise"],
        insolvency_code="BASELINE_CAPITAL_BELOW_ZERO",
    )
    if document["baseline"] != expected_baseline:
        _refuse("RESULT_BASELINE_INVALID", "baseline metrics do not match the ordered trades")
    distributions = document["distributions"]
    summaries = document["summaries"]
    names = {"terminal_pnl_paise", "maximum_drawdown_paise"}
    if not isinstance(distributions, dict) or set(distributions) != names \
            or not isinstance(summaries, dict) or set(summaries) != names:
        _refuse("RESULT_DISTRIBUTION_INVALID", "result distributions are open or incomplete")
    for name in names:
        values = distributions[name]
        if not isinstance(values, list) or len(values) != inputs["iterations"] \
                or any(type(value) is not int for value in values):
            _refuse("RESULT_DISTRIBUTION_INVALID", f"{name} distribution is malformed")
        if name == "terminal_pnl_paise" and any(
            abs(value) > MAXIMUM_ABSOLUTE_PATH_PNL_PAISE for value in values
        ):
            _refuse(
                "RESULT_DERIVED_VALUE_OUT_OF_RANGE",
                "terminal PnL distribution exceeds the signed path bound",
            )
        if name == "maximum_drawdown_paise" and any(
            value < 0 or value > MAXIMUM_ABSOLUTE_PATH_PNL_PAISE for value in values
        ):
            _refuse(
                "RESULT_DERIVED_VALUE_OUT_OF_RANGE",
                "drawdown distribution exceeds the declared path bound",
            )
        if summaries[name] != _summary(values):
            _refuse("RESULT_SUMMARY_INVALID", f"{name} summary is stale or forged")


def _stationary_path_indices(
    population_size: int,
    path_size: int,
    restart_probability_ppm: int,
    rng: Any,
) -> tuple[int, ...]:
    """Draw one circular geometric-block path using an injected local RNG."""
    index = rng.bounded(population_size)
    indices = [index]
    for _ in range(1, path_size):
        if rng.bounded(PPM_SCALE) < restart_probability_ppm:
            index = rng.bounded(population_size)
        else:
            index = (index + 1) % population_size
        indices.append(index)
    return tuple(indices)


def _path_metrics(
    path: tuple[int, ...], starting_capital_paise: int, *, insolvency_code: str
) -> dict[str, int]:
    equity = starting_capital_paise
    cumulative_pnl = 0
    peak = equity
    maximum_drawdown = 0
    for pnl in path:
        cumulative_pnl += pnl
        if abs(cumulative_pnl) > MAXIMUM_ABSOLUTE_PATH_PNL_PAISE:
            _refuse(
                "DERIVED_PATH_PNL_LIMIT_EXCEEDED",
                "cumulative path PnL exceeds the signed path bound",
            )
        equity = starting_capital_paise + cumulative_pnl
        if equity < 0:
            _refuse(insolvency_code, "a capital path fell below zero")
        if equity > MAXIMUM_EQUITY_PAISE:
            _refuse(
                "DERIVED_EQUITY_LIMIT_EXCEEDED",
                "path equity exceeds the declared maximum equity",
            )
        if equity > peak:
            peak = equity
        else:
            maximum_drawdown = max(maximum_drawdown, peak - equity)
            if maximum_drawdown > MAXIMUM_ABSOLUTE_PATH_PNL_PAISE:
                _refuse(
                    "DERIVED_DRAWDOWN_LIMIT_EXCEEDED",
                    "path drawdown exceeds the declared path bound",
                )
    return {
        "terminal_capital_paise": equity,
        "terminal_pnl_paise": cumulative_pnl,
        "maximum_drawdown_paise": maximum_drawdown,
    }


def _summary(values: list[int]) -> dict[str, int]:
    ordered = sorted(values)
    return {
        "minimum": ordered[0],
        "p05_nearest_rank": ordered[_nearest_rank_index(len(ordered), 5, 100)],
        "p50_nearest_rank": ordered[_nearest_rank_index(len(ordered), 50, 100)],
        "p95_nearest_rank": ordered[_nearest_rank_index(len(ordered), 95, 100)],
        "maximum": ordered[-1],
    }


def _nearest_rank_index(length: int, numerator: int, denominator: int) -> int:
    return ((length * numerator + denominator - 1) // denominator) - 1


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _refuse(code: str, detail: str) -> None:
    raise StationaryTradeBootstrapRefusal(code, detail)
