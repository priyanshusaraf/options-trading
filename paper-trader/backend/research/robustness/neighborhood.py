"""Deterministic complete local parameter-neighbourhood analysis.

The method consumes an exact, bounded Cartesian ``{-step, 0, +step}`` population
around one baseline.  It refuses incomplete evidence rather than turning a best
candidate or a partial surface into a stability conclusion.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext
from enum import Enum
from fractions import Fraction
from itertools import product
import json
from typing import Any

from app.ir.hashing import canonical_json, content_address
from app.ir.schema import is_content_address


RESULT_SCHEMA = "strategy-os-parameter-neighbourhood/1"
METHOD_VERSION = "complete-cartesian-local-grid/1"
MINIMUM_PARAMETERS = 1
MAXIMUM_PARAMETERS = 4
MAXIMUM_CANDIDATES = 625
MAXIMUM_EXPECTED_LOCAL_NEIGHBORS = 80
MAXIMUM_DECIMAL_CHARACTERS = 128
MINIMUM_SCORE = -(2**63)
MAXIMUM_SCORE = 2**63 - 1
PPM_DENOMINATOR = 1_000_000

LIMITATIONS = (
    "The result is conditional on the complete supplied local OOS candidate population and its bound identities.",
    "The local grid does not establish stability outside the declared per-parameter steps and inclusive bounds.",
    "The maximum score drop and minimum stable-neighbour fraction are experiment inputs, not universal thresholds.",
    "The result does not establish statistical significance, future performance, profitability, or deployment authority.",
)


class RefusalCode(str, Enum):
    INPUT_INVALID = "INPUT_INVALID"
    PARAMETER_COUNT = "PARAMETER_COUNT"
    CANDIDATE_COUNT = "CANDIDATE_COUNT"
    PARAMETER_KEYS_INVALID = "PARAMETER_KEYS_INVALID"
    DECIMAL_INVALID = "DECIMAL_INVALID"
    STEP_INVALID = "STEP_INVALID"
    BOUNDS_INVALID = "BOUNDS_INVALID"
    SCORE_INVALID = "SCORE_INVALID"
    PASS_STATE_INVALID = "PASS_STATE_INVALID"
    ADDRESS_INVALID = "ADDRESS_INVALID"
    DUPLICATE_ADDRESS = "DUPLICATE_ADDRESS"
    DUPLICATE_POINT = "DUPLICATE_POINT"
    BASELINE_INVALID = "BASELINE_INVALID"
    MISSING_EXPECTED_NEIGHBOR = "MISSING_EXPECTED_NEIGHBOR"
    EXTRA_CANDIDATE = "EXTRA_CANDIDATE"
    CANDIDATE_OUT_OF_BOUNDS = "CANDIDATE_OUT_OF_BOUNDS"
    EXPECTED_NEIGHBOR_COUNT = "EXPECTED_NEIGHBOR_COUNT"
    THRESHOLD_INVALID = "THRESHOLD_INVALID"
    ARITHMETIC_OVERFLOW = "ARITHMETIC_OVERFLOW"
    RESULT_REPLAY_INVALID = "RESULT_REPLAY_INVALID"


class NeighborhoodRefusal(ValueError):
    """A stable typed refusal emitted before any result is published."""

    def __init__(self, code: RefusalCode, message: str) -> None:
        self.code = code
        super().__init__(f"{code.value}: {message}")


@dataclass(frozen=True)
class ParameterAxis:
    key: str
    step: str
    lower_bound: str
    upper_bound: str


@dataclass(frozen=True)
class NeighborhoodCandidate:
    address: str
    parameters: tuple[tuple[str, str], ...]
    oos_score: int
    passed: bool


@dataclass(frozen=True)
class ParameterNeighborhoodInput:
    baseline: NeighborhoodCandidate
    candidates: tuple[NeighborhoodCandidate, ...]
    axes: tuple[ParameterAxis, ...]
    maximum_score_drop: int
    minimum_stable_fraction_ppm: int


@dataclass(frozen=True, init=False)
class ParameterNeighborhoodResult:
    schema: str
    method_version: str
    canonical_bytes: bytes
    address: str
    candidate_count: int
    expected_neighbor_count: int
    stable_neighbor_count: int
    stable: bool

    @classmethod
    def _trusted(
        cls, *, canonical_bytes: bytes, address: str, candidate_count: int,
        expected_neighbor_count: int, stable_neighbor_count: int, stable: bool,
    ) -> ParameterNeighborhoodResult:
        result = object.__new__(cls)
        for field, value in (
            ("schema", RESULT_SCHEMA),
            ("method_version", METHOD_VERSION),
            ("canonical_bytes", canonical_bytes),
            ("address", address),
            ("candidate_count", candidate_count),
            ("expected_neighbor_count", expected_neighbor_count),
            ("stable_neighbor_count", stable_neighbor_count),
            ("stable", stable),
        ):
            object.__setattr__(result, field, value)
        return result

    def to_document(self) -> dict[str, Any]:
        """Return a defensive plain-data copy of the addressed document."""
        return json.loads(self.canonical_bytes)


def _refuse(code: RefusalCode, message: str) -> None:
    raise NeighborhoodRefusal(code, message)


def _parameter_key(value: object) -> str:
    if (type(value) is not str or not 1 <= len(value) <= 64
            or not value[0].isalpha()
            or any(not (character.isascii() and (character.isalnum() or character == "_"))
                   for character in value)):
        _refuse(RefusalCode.PARAMETER_KEYS_INVALID, "parameter keys must be bounded identifiers")
    return value


def _decimal(value: object, label: str) -> Decimal:
    if type(value) is not str or not value:
        _refuse(RefusalCode.DECIMAL_INVALID, f"{label} must be normalized decimal text")
    if len(value) > MAXIMUM_DECIMAL_CHARACTERS:
        _refuse(RefusalCode.ARITHMETIC_OVERFLOW, f"{label} exceeds the decimal resource bound")
    try:
        with localcontext() as context:
            context.prec = MAXIMUM_DECIMAL_CHARACTERS * 2
            context.Emax = MAXIMUM_DECIMAL_CHARACTERS * 2
            context.Emin = -MAXIMUM_DECIMAL_CHARACTERS * 2
            number = Decimal(value)
            if not number.is_finite():
                _refuse(RefusalCode.DECIMAL_INVALID, f"{label} must be finite")
            normalized = format(number.normalize(context=context), "f")
    except DecimalException as exc:
        raise NeighborhoodRefusal(RefusalCode.DECIMAL_INVALID,
                                  f"{label} must be normalized decimal text") from exc
    if value != normalized or normalized == "-0":
        _refuse(RefusalCode.DECIMAL_INVALID, f"{label} is not normalized decimal text")
    return number


def _decimal_result(value: Decimal, label: str) -> str:
    if not value.is_finite():
        _refuse(RefusalCode.ARITHMETIC_OVERFLOW, f"{label} is not finite")
    with localcontext() as context:
        context.prec = MAXIMUM_DECIMAL_CHARACTERS * 2
        rendered = format(value.normalize(context=context), "f")
    if rendered == "-0":
        rendered = "0"
    if len(rendered) > MAXIMUM_DECIMAL_CHARACTERS:
        _refuse(RefusalCode.ARITHMETIC_OVERFLOW, f"{label} exceeds the decimal resource bound")
    return rendered


def _decimal_add(left: Decimal, right: Decimal, label: str) -> Decimal:
    try:
        with localcontext() as context:
            context.prec = MAXIMUM_DECIMAL_CHARACTERS * 2
            context.Emax = MAXIMUM_DECIMAL_CHARACTERS * 2
            context.Emin = -MAXIMUM_DECIMAL_CHARACTERS * 2
            value = left + right
    except DecimalException as exc:
        raise NeighborhoodRefusal(RefusalCode.ARITHMETIC_OVERFLOW,
                                  f"{label} exceeds exact decimal arithmetic") from exc
    _decimal_result(value, label)
    return value


def _score(value: object, label: str) -> int:
    if type(value) is not int:
        _refuse(RefusalCode.SCORE_INVALID, f"{label} must be an exact integer")
    if not MINIMUM_SCORE <= value <= MAXIMUM_SCORE:
        _refuse(RefusalCode.ARITHMETIC_OVERFLOW, f"{label} exceeds signed 64-bit bounds")
    return value


def _checked_score_subtract(left: int, right: int, label: str) -> int:
    value = left - right
    if not MINIMUM_SCORE <= value <= MAXIMUM_SCORE:
        _refuse(RefusalCode.ARITHMETIC_OVERFLOW, f"{label} exceeds signed 64-bit bounds")
    return value


def _axes(axes: object) -> tuple[tuple[ParameterAxis, Decimal, Decimal, Decimal], ...]:
    if type(axes) is not tuple:
        _refuse(RefusalCode.INPUT_INVALID, "axes must be an immutable tuple")
    if not MINIMUM_PARAMETERS <= len(axes) <= MAXIMUM_PARAMETERS:
        _refuse(RefusalCode.PARAMETER_COUNT, "one to four parameter axes are required")
    validated = []
    for axis in axes:
        if type(axis) is not ParameterAxis:
            _refuse(RefusalCode.INPUT_INVALID, "every axis must be a ParameterAxis")
        key = _parameter_key(axis.key)
        step = _decimal(axis.step, f"{key} step")
        lower = _decimal(axis.lower_bound, f"{key} lower bound")
        upper = _decimal(axis.upper_bound, f"{key} upper bound")
        if step <= 0:
            _refuse(RefusalCode.STEP_INVALID, f"{key} step must be positive")
        if lower > upper:
            _refuse(RefusalCode.BOUNDS_INVALID, f"{key} lower bound exceeds its upper bound")
        validated.append((axis, step, lower, upper))
    keys = tuple(axis.key for axis, _, _, _ in validated)
    if keys != tuple(sorted(set(keys))):
        _refuse(RefusalCode.PARAMETER_KEYS_INVALID, "axes must use identical sorted unique keys")
    return tuple(validated)


def _candidate(candidate: object, expected_keys: tuple[str, ...]) -> tuple[NeighborhoodCandidate, tuple[Decimal, ...]]:
    if type(candidate) is not NeighborhoodCandidate:
        _refuse(RefusalCode.INPUT_INVALID, "every candidate must be a NeighborhoodCandidate")
    if not is_content_address(candidate.address):
        _refuse(RefusalCode.ADDRESS_INVALID, "candidate address is not a content address")
    if type(candidate.parameters) is not tuple:
        _refuse(RefusalCode.PARAMETER_KEYS_INVALID, "candidate parameters must be an immutable tuple")
    try:
        keys = tuple(pair[0] for pair in candidate.parameters)
    except (TypeError, IndexError):
        _refuse(RefusalCode.PARAMETER_KEYS_INVALID, "candidate parameter entries are malformed")
    if (len(candidate.parameters) != len(expected_keys) or keys != expected_keys
            or any(type(pair) is not tuple or len(pair) != 2 for pair in candidate.parameters)):
        _refuse(RefusalCode.PARAMETER_KEYS_INVALID, "candidate parameter keys do not match the axes")
    values = tuple(_decimal(pair[1], f"candidate {pair[0]}") for pair in candidate.parameters)
    _score(candidate.oos_score, "candidate OOS score")
    if type(candidate.passed) is not bool:
        _refuse(RefusalCode.PASS_STATE_INVALID, "candidate pass state must be boolean")
    return candidate, values


def _expected_points(
    axes: tuple[tuple[ParameterAxis, Decimal, Decimal, Decimal], ...],
    baseline_values: tuple[Decimal, ...],
) -> tuple[tuple[Decimal, ...], ...]:
    choices = []
    for (axis, step, lower, upper), baseline in zip(axes, baseline_values):
        if baseline < lower or baseline > upper:
            _refuse(RefusalCode.BASELINE_INVALID, f"baseline {axis.key} lies outside its bounds")
        values = []
        negative = _decimal_add(baseline, step.copy_negate(), f"expected {axis.key} point")
        positive = _decimal_add(baseline, step, f"expected {axis.key} point")
        for candidate_value in (negative, baseline, positive):
            if lower <= candidate_value <= upper and candidate_value not in values:
                _decimal_result(candidate_value, f"expected {axis.key} point")
                values.append(candidate_value)
        choices.append(tuple(values))
    points = tuple(product(*choices))
    neighbor_count = len(points) - 1
    if neighbor_count < 1 or neighbor_count > MAXIMUM_EXPECTED_LOCAL_NEIGHBORS:
        _refuse(RefusalCode.EXPECTED_NEIGHBOR_COUNT,
                "expected local-neighbour count lies outside one to eighty")
    return points


def expected_local_points(
    axes: tuple[ParameterAxis, ...], baseline_values: tuple[str, ...],
) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Return the frozen in-bounds local grid, including its baseline point."""
    validated_axes = _axes(axes)
    if type(baseline_values) is not tuple or len(baseline_values) != len(validated_axes):
        _refuse(RefusalCode.BASELINE_INVALID, "baseline values do not match the axes")
    values = tuple(_decimal(value, f"baseline {axis.key}")
                   for (axis, _, _, _), value in zip(validated_axes, baseline_values))
    return tuple(
        tuple((axis.key, _decimal_result(value, f"expected {axis.key} point"))
              for (axis, _, _, _), value in zip(validated_axes, point))
        for point in _expected_points(validated_axes, values)
    )


def _fraction(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _summary(scores: tuple[int, ...]) -> dict[str, Any]:
    ordered = sorted(scores)
    count = len(ordered)
    median = (Fraction(ordered[count // 2], 1) if count % 2
              else Fraction(ordered[count // 2 - 1] + ordered[count // 2], 2))
    total = sum(ordered)
    mean = Fraction(total, count)
    variance = sum((Fraction(score, 1) - mean) ** 2 for score in ordered) / count
    return {
        "minimum": ordered[0],
        "maximum": ordered[-1],
        "median": _fraction(median),
        "variance": _fraction(variance),
    }


def _candidate_document(candidate: NeighborhoodCandidate) -> dict[str, Any]:
    return {
        "address": candidate.address,
        "parameters": [list(pair) for pair in candidate.parameters],
        "oos_score": candidate.oos_score,
        "passed": candidate.passed,
    }


def _candidate_from_document(value: object, label: str) -> NeighborhoodCandidate:
    if type(value) is not dict or set(value) != {"address", "parameters", "oos_score", "passed"}:
        _refuse(RefusalCode.RESULT_REPLAY_INVALID, f"{label} candidate document is malformed")
    parameters = value["parameters"]
    if type(parameters) is not list or any(type(pair) is not list or len(pair) != 2
                                           for pair in parameters):
        _refuse(RefusalCode.RESULT_REPLAY_INVALID, f"{label} parameters are malformed")
    return NeighborhoodCandidate(
        address=value["address"],
        parameters=tuple((pair[0], pair[1]) for pair in parameters),
        oos_score=value["oos_score"],
        passed=value["passed"],
    )


def _request_from_result_document(document: object) -> ParameterNeighborhoodInput:
    if type(document) is not dict:
        _refuse(RefusalCode.RESULT_REPLAY_INVALID, "result document must be an object")
    try:
        axes_document = document["axes"]
        population_document = document["candidate_population"]
        thresholds = document["thresholds"]
        baseline_document = document["baseline"]
    except KeyError as exc:
        raise NeighborhoodRefusal(RefusalCode.RESULT_REPLAY_INVALID,
                                  "result lacks a replay input") from exc
    if type(axes_document) is not list or any(
        type(axis) is not dict
        or set(axis) != {"key", "step", "lower_bound", "upper_bound"}
        for axis in axes_document
    ):
        _refuse(RefusalCode.RESULT_REPLAY_INVALID, "result axes are malformed")
    if type(population_document) is not list:
        _refuse(RefusalCode.RESULT_REPLAY_INVALID, "result candidate population is malformed")
    if type(thresholds) is not dict or set(thresholds) != {
        "maximum_score_drop", "minimum_stable_fraction_ppm",
    }:
        _refuse(RefusalCode.RESULT_REPLAY_INVALID, "result thresholds are malformed")
    axes = tuple(ParameterAxis(
        key=axis["key"], step=axis["step"],
        lower_bound=axis["lower_bound"], upper_bound=axis["upper_bound"],
    ) for axis in axes_document)
    candidates = tuple(_candidate_from_document(value, "population")
                       for value in population_document)
    baseline = _candidate_from_document(baseline_document, "baseline")
    return ParameterNeighborhoodInput(
        baseline=baseline,
        candidates=candidates,
        axes=axes,
        maximum_score_drop=thresholds["maximum_score_drop"],
        minimum_stable_fraction_ppm=thresholds["minimum_stable_fraction_ppm"],
    )


def reconstruct_parameter_neighborhood(
    canonical_bytes: bytes, address: str,
) -> ParameterNeighborhoodResult:
    """Reconstruct only a result whose entire addressed semantics replay exactly."""
    if type(canonical_bytes) is not bytes or not is_content_address(address):
        _refuse(RefusalCode.RESULT_REPLAY_INVALID,
                "result reconstruction requires canonical bytes and a content address")
    try:
        document = json.loads(canonical_bytes)
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise NeighborhoodRefusal(RefusalCode.RESULT_REPLAY_INVALID,
                                  "result bytes are not canonical JSON") from exc
    if canonical_json(document).encode("utf-8") != canonical_bytes:
        _refuse(RefusalCode.RESULT_REPLAY_INVALID, "result bytes are not canonical")
    if content_address(document) != address:
        _refuse(RefusalCode.RESULT_REPLAY_INVALID, "result address does not match its bytes")
    try:
        replayed = analyze_parameter_neighborhood(_request_from_result_document(document))
    except NeighborhoodRefusal as exc:
        if exc.code is RefusalCode.RESULT_REPLAY_INVALID:
            raise
        raise NeighborhoodRefusal(RefusalCode.RESULT_REPLAY_INVALID,
                                  "addressed result inputs do not replay") from exc
    if replayed.canonical_bytes != canonical_bytes or replayed.address != address:
        _refuse(RefusalCode.RESULT_REPLAY_INVALID,
                "addressed result semantics differ from deterministic replay")
    return replayed


def analyze_parameter_neighborhood(request: ParameterNeighborhoodInput) -> ParameterNeighborhoodResult:
    """Analyze exactly one complete, bounded local parameter population."""
    if type(request) is not ParameterNeighborhoodInput:
        _refuse(RefusalCode.INPUT_INVALID, "input must be ParameterNeighborhoodInput")
    axes = _axes(request.axes)
    if type(request.candidates) is not tuple:
        _refuse(RefusalCode.INPUT_INVALID, "candidate population must be an immutable tuple")
    if not 1 <= len(request.candidates) <= MAXIMUM_CANDIDATES:
        _refuse(RefusalCode.CANDIDATE_COUNT, "candidate population lies outside one to 625")
    if type(request.maximum_score_drop) is not int:
        _refuse(RefusalCode.THRESHOLD_INVALID, "maximum score drop must be an exact integer")
    maximum_drop = _score(request.maximum_score_drop, "maximum score drop")
    if maximum_drop < 0:
        _refuse(RefusalCode.THRESHOLD_INVALID, "maximum score drop must be nonnegative")
    minimum_fraction = request.minimum_stable_fraction_ppm
    if type(minimum_fraction) is not int or not 0 <= minimum_fraction <= PPM_DENOMINATOR:
        _refuse(RefusalCode.THRESHOLD_INVALID,
                "minimum stable-neighbour fraction must be integer ppm in [0, 1000000]")
    if type(request.baseline) is not NeighborhoodCandidate:
        _refuse(RefusalCode.BASELINE_INVALID, "baseline must be a NeighborhoodCandidate")

    expected_keys = tuple(axis.key for axis, _, _, _ in axes)
    validated = tuple(_candidate(candidate, expected_keys) for candidate in request.candidates)
    baseline, baseline_values = _candidate(request.baseline, expected_keys)
    for candidate, values in validated:
        for value, (axis, _step, lower, upper) in zip(values, axes):
            if value < lower or value > upper:
                _refuse(RefusalCode.CANDIDATE_OUT_OF_BOUNDS,
                        f"candidate {axis.key} lies outside its inclusive bounds")
    addresses = tuple(candidate.address for candidate, _ in validated)
    if len(set(addresses)) != len(addresses):
        _refuse(RefusalCode.DUPLICATE_ADDRESS, "candidate addresses must be unique")
    numeric_points = tuple(values for _, values in validated)
    if len(set(numeric_points)) != len(numeric_points):
        _refuse(RefusalCode.DUPLICATE_POINT, "candidate parameter points must be unique")
    baseline_records = tuple(candidate for candidate, _ in validated if candidate.address == baseline.address)
    if len(baseline_records) != 1 or baseline_records[0] != baseline:
        _refuse(RefusalCode.BASELINE_INVALID,
                "the exact baseline candidate must occur once in the population")

    expected_points = _expected_points(axes, baseline_values)
    expected_set = set(expected_points)
    actual_set = set(numeric_points)
    missing = expected_set - actual_set
    if missing:
        _refuse(RefusalCode.MISSING_EXPECTED_NEIGHBOR,
                "the complete in-bounds local grid is missing a point")

    stable_floor = _checked_score_subtract(baseline.oos_score, maximum_drop,
                                           "baseline score-drop threshold")
    by_point = {values: candidate for candidate, values in validated}
    neighbor_points = tuple(point for point in expected_points if point != baseline_values)
    stable_by_point = {
        point: by_point[point].passed and by_point[point].oos_score >= stable_floor
        for point in neighbor_points
    }
    stable_count = sum(stable_by_point.values())
    neighbor_count = len(neighbor_points)
    decision = stable_count * PPM_DENOMINATOR >= minimum_fraction * neighbor_count

    population = sorted((_candidate_document(candidate) for candidate, _ in validated),
                        key=lambda row: row["address"])
    membership = []
    for point in neighbor_points:
        candidate = by_point[point]
        membership.append({
            **_candidate_document(candidate),
            "stable": stable_by_point[point],
            "score_drop_from_baseline": _checked_score_subtract(
                baseline.oos_score, candidate.oos_score, "candidate score drop"),
        })
    membership.sort(key=lambda row: tuple(Decimal(value) for _, value in row["parameters"]))

    sensitivity = []
    for index, (axis, step, lower, upper) in enumerate(axes):
        row: dict[str, Any] = {"parameter": axis.key}
        for label, offset in (("negative", step.copy_negate()), ("positive", step)):
            target_value = _decimal_add(baseline_values[index], offset,
                                        f"sensitivity {axis.key}")
            if not lower <= target_value <= upper:
                row[label] = None
                continue
            target = list(baseline_values)
            target[index] = target_value
            point = tuple(target)
            candidate = by_point[point]
            row[label] = {
                "candidate_address": candidate.address,
                "parameter_value": _decimal_result(target_value, f"sensitivity {axis.key}"),
                "score_delta": _checked_score_subtract(candidate.oos_score,
                                                        baseline.oos_score,
                                                        "sensitivity score delta"),
                "passed": candidate.passed,
                "stable": stable_by_point[point],
            }
        sensitivity.append(row)

    bounds_document = {
        "minimum_parameters": MINIMUM_PARAMETERS,
        "maximum_parameters": MAXIMUM_PARAMETERS,
        "maximum_candidates": MAXIMUM_CANDIDATES,
        "maximum_expected_local_neighbours": MAXIMUM_EXPECTED_LOCAL_NEIGHBORS,
        "maximum_decimal_characters": MAXIMUM_DECIMAL_CHARACTERS,
        "score_minimum": MINIMUM_SCORE,
        "score_maximum": MAXIMUM_SCORE,
    }
    population_digest = content_address({
        "schema": "strategy-os-parameter-neighbourhood-population/1",
        "candidates": population,
    })
    document = {
        "schema": RESULT_SCHEMA,
        "method_version": METHOD_VERSION,
        "bounds": bounds_document,
        "limitations": list(LIMITATIONS),
        "baseline": _candidate_document(baseline),
        "candidate_population_digest": population_digest,
        "candidate_population": population,
        "axes": [
            {
                "key": axis.key,
                "step": axis.step,
                "lower_bound": axis.lower_bound,
                "upper_bound": axis.upper_bound,
            }
            for axis, _, _, _ in axes
        ],
        "thresholds": {
            "maximum_score_drop": maximum_drop,
            "minimum_stable_fraction_ppm": minimum_fraction,
        },
        "candidate_count": len(validated),
        "expected_neighbor_count": neighbor_count,
        "stable_neighbor_count": stable_count,
        "unstable_neighbor_count": neighbor_count - stable_count,
        "stable_fraction": _fraction(Fraction(stable_count, neighbor_count)),
        "stable_fraction_ppm": _fraction(Fraction(stable_count * PPM_DENOMINATOR,
                                                   neighbor_count)),
        "score_summary": _summary(tuple(by_point[point].oos_score
                                        for point in neighbor_points)),
        "sensitivity": sensitivity,
        "local_membership": membership,
        "stable": decision,
    }
    encoded = canonical_json(document).encode("utf-8")
    return ParameterNeighborhoodResult._trusted(
        canonical_bytes=encoded,
        address=content_address(document),
        candidate_count=len(validated),
        expected_neighbor_count=neighbor_count,
        stable_neighbor_count=stable_count,
        stable=decision,
    )
