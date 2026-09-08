"""Closed integration of saved-V2 parameter candidates with locked-OOS evidence."""
from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext
from numbers import Real
from typing import Any

from app.engine.charges import ChargeScheduleRefusal, monetary_minor
from app.ir.hashing import canonical_json, content_address
from app.ir.schema import is_content_address
from research.evidence import EvidenceRejected, encode_terminal_evidence
from research.robustness.neighborhood import (
    METHOD_VERSION,
    RESULT_SCHEMA,
    NeighborhoodCandidate,
    NeighborhoodRefusal,
    ParameterAxis,
    ParameterNeighborhoodInput,
    analyze_parameter_neighborhood,
    expected_local_points,
    reconstruct_parameter_neighborhood,
)


PROJECTION_SCHEMA = "strategy-os-parameter-neighbourhood-evidence/1"
INTEGRATION_VERSION = "saved-v2-locked-oos/1"
EVALUATION_CONTRACT_SCHEMA = "parameter-neighbourhood-evaluation-contract/2"
MAXIMUM_AXES = 4
MAXIMUM_CANDIDATES = 81
MAXIMUM_CANDIDATE_BAR_EVALUATIONS = 2_000_000
MAXIMUM_DECIMAL_CHARACTERS = 128
AVAILABLE = "AVAILABLE"
DISABLED = "DISABLED"
UNAVAILABLE = "UNAVAILABLE"

_SETTINGS_FIELDS = frozenset({
    "enabled", "axes", "maximum_score_drop_paise",
    "minimum_stable_fraction_ppm",
})
_AXIS_FIELDS = frozenset({"node_id", "parameter_id", "step", "minimum", "maximum"})
_UNAVAILABLE_REASONS = frozenset({
    "LEGACY_V1_GRAPH_UNSUPPORTED",
    "MULTI_INSTRUMENT_AMBIGUITY",
    "OPTIMIZED_PARENT_UNSUPPORTED",
    "PARAMETER_NEIGHBORHOOD_METHOD_REFUSED",
    "PARAMETER_NEIGHBORHOOD_RESOURCE_REFUSED",
    "PARAMETER_NEIGHBORHOOD_CANDIDATE_REFUSED",
    "PARENT_NOT_QUALIFIED",
    "INSUFFICIENT_HOLDOUT",
    "TERMINAL_EVIDENCE_SIZE_REFUSED",
})


class ParameterNeighborhoodIntegrationRejected(ValueError):
    """Requested or stored parameter-neighbourhood evidence is not trustworthy."""


class CandidateEvaluationCancelled(RuntimeError):
    """The durable candidate authority was cancelled or lost its claim."""


@dataclass(frozen=True)
class PreparedParameterNeighborhood:
    recipe_binding: Mapping[str, Any]
    axes: tuple[Mapping[str, Any], ...]
    baseline_values: tuple[str, ...]


@dataclass(frozen=True)
class CandidateRuntime:
    strategy: Any
    candidate_graph_address: str
    lineage: Mapping[str, Any]


@dataclass(frozen=True)
class _EvaluationPolicy:
    n_folds: int
    capital: float
    min_trades: int
    min_positive_fold_frac: float
    slippage_bps: float
    slippage_multiplier: float
    seed: int
    evaluation_start: Any
    evaluation_bars: int | None
    evaluation_start_ts: int | None


@dataclass(frozen=True)
class _CandidateEvaluation:
    point: tuple[tuple[str, str], ...]
    runtime: CandidateRuntime
    validation: Any
    folds: tuple[tuple[int, int, int, int], ...]
    score: int


def _reject(message: str) -> None:
    raise ParameterNeighborhoodIntegrationRejected(message)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _normalized_decimal(value: Any, label: str) -> tuple[str, Decimal]:
    if type(value) is not str or not value or len(value) > MAXIMUM_DECIMAL_CHARACTERS:
        _reject(f"{label} must be bounded normalized decimal text")
    try:
        with localcontext() as context:
            context.prec = MAXIMUM_DECIMAL_CHARACTERS * 2
            number = Decimal(value)
            rendered = format(number.normalize(context=context), "f")
    except DecimalException as exc:
        raise ParameterNeighborhoodIntegrationRejected(
            f"{label} must be normalized decimal text"
        ) from exc
    if not number.is_finite() or rendered == "-0" or rendered != value:
        _reject(f"{label} must be normalized decimal text")
    return rendered, number


def _numeric_decimal(value: Any, label: str) -> tuple[str, Decimal]:
    if isinstance(value, bool) or type(value) not in {int, float}:
        _reject(f"{label} must be a finite numeric value")
    try:
        number = Decimal(str(value))
        rendered = format(number.normalize(), "f")
    except DecimalException as exc:
        raise ParameterNeighborhoodIntegrationRejected(
            f"{label} must be a finite numeric value"
        ) from exc
    if not number.is_finite() or len(rendered) > MAXIMUM_DECIMAL_CHARACTERS:
        _reject(f"{label} must be a bounded finite numeric value")
    return ("0" if rendered == "-0" else rendered), number


def _closed_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(settings, Mapping) or set(settings) != _SETTINGS_FIELDS:
        _reject("parameter-neighbourhood settings are open or incomplete")
    value = _plain(settings)
    if type(value["enabled"]) is not bool:
        _reject("parameter-neighbourhood enabled must be boolean")
    axes = value["axes"]
    if not isinstance(axes, list) or len(axes) > MAXIMUM_AXES:
        _reject("parameter-neighbourhood axes exceed four")
    if not value["enabled"]:
        if axes or value["maximum_score_drop_paise"] != 0 \
                or value["minimum_stable_fraction_ppm"] != 0:
            _reject("disabled parameter-neighbourhood request carries work")
        return value
    if not 1 <= len(axes) <= MAXIMUM_AXES:
        _reject("enabled parameter-neighbourhood requires one to four axes")
    maximum_drop = value["maximum_score_drop_paise"]
    minimum_fraction = value["minimum_stable_fraction_ppm"]
    if type(maximum_drop) is not int or not 0 <= maximum_drop <= 2**63 - 1:
        _reject("maximum score drop must be signed-64-safe nonnegative paise")
    if type(minimum_fraction) is not int or not 0 <= minimum_fraction <= 1_000_000:
        _reject("minimum stable fraction must be integer ppm")
    keys = []
    for axis in axes:
        if not isinstance(axis, Mapping) or set(axis) != _AXIS_FIELDS:
            _reject("parameter-neighbourhood axis is open or incomplete")
        for name in ("node_id", "parameter_id"):
            if not isinstance(axis[name], str) or not axis[name] or len(axis[name]) > 128:
                _reject(f"axis {name} is invalid")
        _normalized_decimal(axis["step"], "axis step")
        _normalized_decimal(axis["minimum"], "axis minimum")
        _normalized_decimal(axis["maximum"], "axis maximum")
        keys.append((axis["node_id"], axis["parameter_id"]))
    if keys != sorted(set(keys)):
        _reject("parameter-neighbourhood axes must be sorted and unique")
    return value


def parameter_neighborhood_recipe_binding(
    settings: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Bind a present closed request without changing absence identities."""
    if settings is None:
        return None
    request = _closed_settings(settings)
    return {
        "parameter_neighborhood": {
            **request,
            "method": {
                "result_schema": RESULT_SCHEMA,
                "method_version": METHOD_VERSION,
                "integration_version": INTEGRATION_VERSION,
            },
        }
    }


def validate_parameter_neighborhood_recipe_binding(
    recipe_binding: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(recipe_binding, Mapping) or set(recipe_binding) != {
        "parameter_neighborhood"
    }:
        _reject("parameter-neighbourhood recipe is open or incomplete")
    request = recipe_binding["parameter_neighborhood"]
    if not isinstance(request, Mapping) or set(request) != {*_SETTINGS_FIELDS, "method"}:
        _reject("parameter-neighbourhood recipe is open or incomplete")
    expected = parameter_neighborhood_recipe_binding({
        key: request[key] for key in _SETTINGS_FIELDS
    })
    if expected != _plain(recipe_binding):
        _reject("parameter-neighbourhood method identity is stale")
    return expected


def parameter_neighborhood_binding_from_provenance(
    robustness: Any,
) -> dict[str, Any] | None:
    """Parse the closed parameter request from a combined robustness recipe."""
    if robustness is None:
        return None
    if not isinstance(robustness, Mapping) or not set(robustness) <= {
        "stationary_bootstrap", "parameter_neighborhood"
    } or not robustness:
        _reject("persisted robustness recipe is open or malformed")
    if "parameter_neighborhood" not in robustness:
        return None
    return validate_parameter_neighborhood_recipe_binding({
        "parameter_neighborhood": robustness["parameter_neighborhood"],
    })


def parent_experiment_identity(
    *, spec_id: Any, recipe: Any,
) -> dict[str, Any]:
    """Address the exact parent recipe and its critical data/economics facts."""
    if not isinstance(spec_id, str) or re.fullmatch(r"[0-9a-f]{32}", spec_id) is None \
            or not isinstance(recipe, Mapping):
        _reject("parent ExperimentSpec identity is invalid")
    graph = recipe.get("graph_provenance")
    datasets = recipe.get("datasets")
    schedule = recipe.get("resolved_charge_schedule")
    if not isinstance(graph, Mapping) or not isinstance(datasets, Mapping) \
            or len(datasets) != 1 or not isinstance(schedule, Mapping) \
            or not is_content_address(schedule.get("address")):
        _reject("parent ExperimentSpec lacks exact graph, dataset or charge identity")
    instrument_key, dataset = next(iter(sorted(datasets.items())))
    if not isinstance(instrument_key, str) or not isinstance(dataset, Mapping) \
            or dataset.get("instrument_key") != instrument_key \
            or not is_content_address(dataset.get("content_hash")):
        _reject("parent ExperimentSpec dataset/instrument identity is invalid")
    return {
        "schema": "parameter-neighbourhood-parent-experiment/1",
        "experiment_spec_id": spec_id,
        "recipe_address": content_address(_plain(recipe)),
        "graph_provenance_address": content_address(_plain(graph)),
        "datasets_address": content_address(_plain(datasets)),
        "dataset_identity_address": content_address(_plain(dataset)),
        "instrument_key": instrument_key,
        "resolved_charge_schedule_address": schedule["address"],
    }


def _component_parameter(
    document: Mapping[str, Any], registry: Any, *, node_id: str, parameter_id: str,
) -> tuple[Any, Mapping[str, Any]]:
    nodes = [node for node in document.get("nodes", ())
             if isinstance(node, Mapping) and node.get("node_id") == node_id]
    if len(nodes) != 1:
        _reject("parameter-neighbourhood node does not exist uniquely")
    node = nodes[0]
    component = node.get("component", {})
    contract = registry.v2_components.get((
        component.get("component_id"), component.get("component_version"),
    ))
    descriptor = contract.get("parameters", {}).get(parameter_id) \
        if isinstance(contract, Mapping) else None
    if not isinstance(descriptor, Mapping) or descriptor.get("type") not in {"int", "float"} \
            or descriptor.get("enum") is not None:
        _reject("axis parameter is not a non-enumerated numeric registry parameter")
    parameters = node.get("parameters")
    if not isinstance(parameters, Mapping) or parameter_id not in parameters:
        _reject("axis parameter has no authored baseline value")
    return parameters[parameter_id], descriptor


def prepare_parameter_neighborhood(
    recipe_binding: Mapping[str, Any] | None, *,
    baseline_document: Mapping[str, Any], registry: Any,
) -> PreparedParameterNeighborhood | None:
    if recipe_binding is None:
        return None
    expected = validate_parameter_neighborhood_recipe_binding(recipe_binding)
    request = expected["parameter_neighborhood"]
    if not request["enabled"]:
        return PreparedParameterNeighborhood(expected, (), ())
    prepared_axes = []
    baseline_values = []
    for index, axis in enumerate(request["axes"]):
        baseline, descriptor = _component_parameter(
            baseline_document, registry, node_id=axis["node_id"],
            parameter_id=axis["parameter_id"],
        )
        kind = descriptor["type"]
        baseline_text, baseline_decimal = _numeric_decimal(baseline, "authored baseline")
        step_text, step = _normalized_decimal(axis["step"], "axis step")
        minimum_text, minimum = _normalized_decimal(axis["minimum"], "axis minimum")
        maximum_text, maximum = _normalized_decimal(axis["maximum"], "axis maximum")
        domain = descriptor["domain"]
        if step <= 0 or minimum > maximum or not minimum <= baseline_decimal <= maximum \
                or minimum < Decimal(str(domain["minimum"])) \
                or maximum > Decimal(str(domain["maximum"])):
            _reject("axis bounds, step, baseline or registry domain differ")
        if kind == "int" and any(number != number.to_integral_value()
                                 for number in (baseline_decimal, step, minimum, maximum)):
            _reject("integer axis requires integral baseline, step and bounds")
        prepared_axes.append({
            "key": f"axis_{index:03d}", "node_id": axis["node_id"],
            "parameter_id": axis["parameter_id"], "parameter_type": kind,
            "step": step_text, "minimum": minimum_text, "maximum": maximum_text,
            "baseline": baseline_text,
        })
        baseline_values.append(baseline_text)
    return PreparedParameterNeighborhood(
        recipe_binding=expected, axes=tuple(prepared_axes),
        baseline_values=tuple(baseline_values),
    )


def _typed_value(text: str, kind: str) -> int | float:
    number = Decimal(text)
    if kind == "int":
        return int(number)
    value = float(number)
    if not isinstance(json.loads(canonical_json(value)), float) \
            or Decimal(str(value)) != number:
        _reject("float candidate cannot round-trip through canonical JSON")
    return value


def _signed_minor(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, Real):
        _reject("candidate net PnL is not accepted monetary input")
    try:
        negative = value < 0
        amount = monetary_minor(abs(value))
    except (ChargeScheduleRefusal, TypeError, ValueError) as exc:
        raise ParameterNeighborhoodIntegrationRejected(
            "candidate net PnL is not accepted monetary input"
        ) from exc
    return -amount if negative else amount


def _fold_signature(validation: Any) -> tuple[tuple[int, int, int, int], ...]:
    return tuple((fold.fold_index, fold.start_ts, fold.end_ts, fold.n_bars)
                 for fold in validation.wf.folds)


def unavailable(reason_code: str) -> dict[str, str]:
    if reason_code not in _UNAVAILABLE_REASONS:
        _reject("unknown parameter-neighbourhood unavailable reason")
    return {"schema": PROJECTION_SCHEMA, "state": UNAVAILABLE, "reason_code": reason_code}


def _evaluation_window(dataset_bars: int, evaluation_bars: int | None,
                       evaluation_start_ts: int | None) -> dict[str, Any]:
    return {
        "use": "locked_validation_challenge",
        "start_ts": evaluation_start_ts,
        "bars": dataset_bars if evaluation_bars is None else evaluation_bars,
    }


def _valid_evaluation_window(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == {"use", "start_ts", "bars"}
        and value["use"] == "locked_validation_challenge"
        and (value["start_ts"] is None or type(value["start_ts"]) is int)
        and type(value["bars"]) is int
    )


def _valid_parent_identity(value: Any) -> bool:
    address_fields = (
        "recipe_address", "graph_provenance_address", "datasets_address",
        "dataset_identity_address", "resolved_charge_schedule_address",
    )
    return (
        isinstance(value, Mapping)
        and set(value) == {
            "schema", "experiment_spec_id", *address_fields, "instrument_key",
        }
        and value.get("schema") == "parameter-neighbourhood-parent-experiment/1"
        and all(is_content_address(value[name]) for name in address_fields)
    )


def _candidate_work_exceeds_limit(point_count: int, dataset_bars: Any) -> bool:
    return (
        point_count > MAXIMUM_CANDIDATES
        or type(dataset_bars) is not int
        or dataset_bars < 0
        or point_count * dataset_bars > MAXIMUM_CANDIDATE_BAR_EVALUATIONS
    )


def _candidate_surface(
    prepared: PreparedParameterNeighborhood, dataset_bars: int,
) -> tuple[tuple[ParameterAxis, ...], tuple[tuple[tuple[str, str], ...], ...], str | None]:
    axes = tuple(ParameterAxis(
        key=axis["key"], step=axis["step"], lower_bound=axis["minimum"],
        upper_bound=axis["maximum"],
    ) for axis in prepared.axes)
    try:
        points = expected_local_points(axes, prepared.baseline_values)
    except NeighborhoodRefusal:
        return axes, (), "PARAMETER_NEIGHBORHOOD_METHOD_REFUSED"
    if _candidate_work_exceeds_limit(len(points), dataset_bars):
        return axes, (), "PARAMETER_NEIGHBORHOOD_RESOURCE_REFUSED"
    baseline = tuple((axis["key"], value)
                     for axis, value in zip(prepared.axes, prepared.baseline_values))
    return axes, (baseline,) + tuple(point for point in points if point != baseline), None


def _candidate_values(
    point: tuple[tuple[str, str], ...], axes: tuple[Mapping[str, Any], ...],
) -> tuple[Mapping[str, Any], ...]:
    by_key = dict(point)
    return tuple({
        "node_id": axis["node_id"], "parameter_id": axis["parameter_id"],
        "value": _typed_value(by_key[axis["key"]], axis["parameter_type"]),
        "normalized_value": by_key[axis["key"]],
    } for axis in axes)


def _evaluate_candidate(
    point: tuple[tuple[str, str], ...], prepared_axes: tuple[Mapping[str, Any], ...],
    candidate_evaluator: Callable[[tuple[Mapping[str, Any], ...]], CandidateRuntime],
    validate: Callable[..., Any], candles: Any, instrument: Any,
    policy: _EvaluationPolicy,
    locked_folds: tuple[tuple[int, int, int, int], ...],
) -> tuple[_CandidateEvaluation, tuple[tuple[int, int, int, int], ...]]:
    runtime = candidate_evaluator(_candidate_values(point, prepared_axes))
    validation = validate(
        candles, instrument, runtime.strategy, {}, n_folds=policy.n_folds,
        capital=policy.capital, min_oos_trades=policy.min_trades,
        min_positive_fold_frac=policy.min_positive_fold_frac,
        slippage_bps=policy.slippage_bps,
        slippage_mult=policy.slippage_multiplier, seed=policy.seed,
        evaluation_start=policy.evaluation_start,
        evaluation_bars=policy.evaluation_bars,
    )
    folds = _fold_signature(validation)
    if not locked_folds:
        locked_folds = folds
    if folds != locked_folds:
        _reject("candidate changed the locked chronological OOS fold boundaries")
    score = sum(_signed_minor(trade.net_pnl)
                for fold in validation.wf.folds for trade in fold.trades)
    return _CandidateEvaluation(point, runtime, validation, folds, score), locked_folds


def _evaluate_surface(
    points: tuple[tuple[tuple[str, str], ...], ...],
    prepared_axes: tuple[Mapping[str, Any], ...],
    candidate_evaluator: Callable[[tuple[Mapping[str, Any], ...]], CandidateRuntime],
    validate: Callable[..., Any], candles: Any, instrument: Any,
    policy: _EvaluationPolicy,
    locked_folds: tuple[tuple[int, int, int, int], ...],
) -> tuple[list[_CandidateEvaluation], tuple[tuple[int, int, int, int], ...]]:
    evaluated = []
    for point in points:
        item, locked_folds = _evaluate_candidate(
            point, prepared_axes, candidate_evaluator, validate,
            candles, instrument, policy, locked_folds,
        )
        evaluated.append(item)
    return evaluated, locked_folds


def _evaluation_document(
    prepared: PreparedParameterNeighborhood, parent_identity: Mapping[str, Any],
    locked_folds: tuple[tuple[int, int, int, int], ...], dataset_bars: int,
    policy: _EvaluationPolicy,
) -> dict[str, Any]:
    return {
        "schema": EVALUATION_CONTRACT_SCHEMA,
        "request_address": content_address(_plain(prepared.recipe_binding)),
        "parent_experiment": _plain(parent_identity),
        "folds": [list(row) for row in locked_folds],
        "dataset_bars": dataset_bars, "n_folds": policy.n_folds,
        "capital": policy.capital, "min_trades": policy.min_trades,
        "min_positive_fold_frac": policy.min_positive_fold_frac,
        "slippage_bps": policy.slippage_bps,
        "slippage_multiplier": policy.slippage_multiplier, "seed": policy.seed,
        "evaluation_window": _evaluation_window(
            dataset_bars, policy.evaluation_bars, policy.evaluation_start_ts,
        ),
    }


def _candidate_evidence(
    item: _CandidateEvaluation, evaluation_contract: str,
    gates_passed: Callable[[Mapping[str, Any]], bool],
) -> tuple[NeighborhoodCandidate, dict[str, Any]]:
    parameters = [list(pair) for pair in item.point]
    candidate_address = content_address({
        "schema": "saved-v2-parameter-candidate/1",
        "candidate_graph_address": item.runtime.candidate_graph_address,
        "point": parameters,
        "evaluation_contract_address": evaluation_contract,
    })
    candidate = NeighborhoodCandidate(
        address=candidate_address, parameters=item.point,
        oos_score=item.score, passed=gates_passed(item.validation.gates),
    )
    population = {
        "candidate_address": candidate_address,
        "candidate_graph_address": item.runtime.candidate_graph_address,
        "parameters": parameters,
        "folds": [list(row) for row in item.folds],
        "lineage": _plain(item.runtime.lineage),
    }
    return candidate, population


def _analyze_surface(
    evaluated: list[_CandidateEvaluation], evaluation_contract: str,
    prepared: PreparedParameterNeighborhood, axes: tuple[ParameterAxis, ...],
    gates_passed: Callable[[Mapping[str, Any]], bool],
) -> tuple[Any, list[dict[str, Any]]]:
    pairs = [_candidate_evidence(item, evaluation_contract, gates_passed)
             for item in evaluated]
    candidates = tuple(pair[0] for pair in pairs)
    baseline = candidates[0]
    request = prepared.recipe_binding["parameter_neighborhood"]
    result = analyze_parameter_neighborhood(ParameterNeighborhoodInput(
        baseline=baseline, candidates=candidates, axes=axes,
        maximum_score_drop=request["maximum_score_drop_paise"],
        minimum_stable_fraction_ppm=request["minimum_stable_fraction_ppm"],
    ))
    return result, [pair[1] for pair in pairs]


def _available_projection(
    evaluation_document: Mapping[str, Any], population: list[dict[str, Any]], result: Any,
) -> dict[str, Any]:
    return {
        "schema": PROJECTION_SCHEMA, "state": AVAILABLE,
        "evaluation_contract": {
            "address": content_address(evaluation_document),
            "document": evaluation_document,
        },
        "population": population,
        "method": {
            "address": result.address,
            "canonical_payload": result.canonical_bytes.decode("utf-8"),
        },
    }


def _insufficient_holdout(parent_fold_signature, evaluation_bars) -> bool:
    return not parent_fold_signature or evaluation_bars == 0


def evaluate_parameter_neighborhood(
    prepared: PreparedParameterNeighborhood | None, *,
    candidate_evaluator: Callable[[tuple[Mapping[str, Any], ...]], CandidateRuntime] | None,
    candles: Any, instrument: Any, dataset_bars: int,
    parent_fold_signature: tuple[tuple[int, int, int, int], ...],
    parent_identity: Mapping[str, Any],
    n_folds: int, capital: float, min_trades: int,
    min_positive_fold_frac: float, slippage_bps: float,
    slippage_multiplier: float, seed: int, evaluation_start=None,
    evaluation_bars: int | None = None, evaluation_start_ts: int | None = None,
) -> dict[str, Any]:
    """Evaluate the complete local surface once under the parent's locked fold contract."""
    if prepared is None:
        return {"schema": PROJECTION_SCHEMA, "state": "NOT_REQUESTED"}
    if not prepared.recipe_binding["parameter_neighborhood"]["enabled"]:
        return {"schema": PROJECTION_SCHEMA, "state": DISABLED}
    if candidate_evaluator is None:
        return unavailable("LEGACY_V1_GRAPH_UNSUPPORTED")
    if _insufficient_holdout(parent_fold_signature, evaluation_bars):
        return unavailable("INSUFFICIENT_HOLDOUT")
    if not _valid_parent_identity(parent_identity):
        _reject("parent ExperimentSpec identity is absent or malformed")
    axes, points, refusal = _candidate_surface(prepared, dataset_bars)
    if refusal is not None:
        return unavailable(refusal)

    from research.pipeline.validate import gates_passed, validate

    policy = _EvaluationPolicy(
        n_folds, capital, min_trades, min_positive_fold_frac, slippage_bps,
        slippage_multiplier, seed, evaluation_start, evaluation_bars,
        evaluation_start_ts,
    )
    try:
        evaluated, locked_folds = _evaluate_surface(
            points, prepared.axes, candidate_evaluator, validate,
            candles, instrument, policy, parent_fold_signature,
        )
        document = _evaluation_document(
            prepared, parent_identity, locked_folds, dataset_bars, policy,
        )
        result, population = _analyze_surface(
            evaluated, content_address(document), prepared, axes, gates_passed,
        )
        return _available_projection(document, population, result)
    except (NeighborhoodRefusal, ParameterNeighborhoodIntegrationRejected,
            AttributeError, TypeError, ValueError) as exc:
        if getattr(exc, "code", None) == "V2_OPERATION_CANCELLED":
            raise CandidateEvaluationCancelled("V2_OPERATION_CANCELLED") from exc
        return unavailable("PARAMETER_NEIGHBORHOOD_CANDIDATE_REFUSED")


def _expected_projection_states(parsed_recipe: Mapping[str, Any] | None) -> set[str]:
    if parsed_recipe is None:
        return {"NOT_REQUESTED"}
    if not parsed_recipe["parameter_neighborhood"]["enabled"]:
        return {DISABLED}
    return {UNAVAILABLE, AVAILABLE}


def _terminal_projection(stored: Mapping[str, Any], state: str) -> dict[str, Any]:
    if state in {"NOT_REQUESTED", DISABLED}:
        if set(stored) != {"schema", "state"}:
            _reject("parameter-neighbourhood terminal state is open")
        return dict(stored)
    if set(stored) != {"schema", "state", "reason_code"} \
            or stored.get("reason_code") not in _UNAVAILABLE_REASONS:
        _reject("parameter-neighbourhood unavailable state is invalid")
    return dict(stored)


def _reconstruct_method(method: Any) -> Any:
    if not isinstance(method, Mapping) \
            or set(method) != {"address", "canonical_payload"} \
            or not isinstance(method["canonical_payload"], str):
        _reject("parameter-neighbourhood method evidence is incomplete")
    try:
        return reconstruct_parameter_neighborhood(
            method["canonical_payload"].encode("utf-8"), method["address"],
        )
    except (NeighborhoodRefusal, UnicodeEncodeError) as exc:
        raise ParameterNeighborhoodIntegrationRejected(
            "stored parameter-neighbourhood method failed semantic reconstruction"
        ) from exc


def _valid_evaluation_envelope(evaluation: Any) -> bool:
    return (
        isinstance(evaluation, Mapping)
        and set(evaluation) == {"address", "document"}
        and is_content_address(evaluation["address"])
        and isinstance(evaluation["document"], Mapping)
        and content_address(_plain(evaluation["document"])) == evaluation["address"]
    )


def _valid_evaluation_identity(
    document: Mapping[str, Any], parsed_recipe: Mapping[str, Any],
    expected_parent: Mapping[str, Any],
) -> bool:
    return (
        document["schema"] == EVALUATION_CONTRACT_SCHEMA
        and document["request_address"] == content_address(_plain(parsed_recipe))
        and document["parent_experiment"] == expected_parent
        and _valid_evaluation_window(document["evaluation_window"])
    )


def _validated_evaluation_contract(
    evaluation: Any, parsed_recipe: Mapping[str, Any],
    parent_spec_id: Any, parent_recipe: Any,
) -> dict[str, Any]:
    if not _valid_evaluation_envelope(evaluation):
        _reject("stored parameter-neighbourhood evaluation contract is invalid")
    document = _plain(evaluation["document"])
    if set(document) != {
        "schema", "request_address", "parent_experiment", "folds", "dataset_bars",
        "n_folds", "capital", "min_trades", "min_positive_fold_frac",
        "slippage_bps", "slippage_multiplier", "seed", "evaluation_window",
    }:
        _reject("stored parameter-neighbourhood evaluation identity is stale")
    expected_parent = parent_experiment_identity(
        spec_id=parent_spec_id, recipe=parent_recipe,
    )
    if not _valid_evaluation_identity(document, parsed_recipe, expected_parent):
        _reject("stored parameter-neighbourhood evaluation identity is stale")
    return document


def _validate_method_request(result: Any, request: Mapping[str, Any]) -> None:
    document = result.to_document()
    thresholds = {
        "maximum_score_drop": request["maximum_score_drop_paise"],
        "minimum_stable_fraction_ppm": request["minimum_stable_fraction_ppm"],
    }
    method_axes = [(axis.get("step"), axis.get("lower_bound"), axis.get("upper_bound"))
                   for axis in document.get("axes", [])]
    request_axes = [(axis["step"], axis["minimum"], axis["maximum"])
                    for axis in request["axes"]]
    if document.get("thresholds") != thresholds or method_axes != request_axes:
        _reject("stored parameter-neighbourhood method and request differ")


def _valid_parameters(value: Any) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(pair, list) and len(pair) == 2
                and all(isinstance(item, str) for item in pair)
                for pair in value)
    )


def _valid_folds(value: Any) -> bool:
    return (
        isinstance(value, list) and bool(value)
        and all(isinstance(fold, list) and len(fold) == 4
                and all(type(item) is int for item in fold)
                for fold in value)
    )


def _valid_population_envelope(row: Any) -> bool:
    return (
        isinstance(row, Mapping)
        and set(row) == {
            "candidate_address", "candidate_graph_address", "parameters",
            "folds", "lineage",
        }
        and is_content_address(row["candidate_address"])
        and is_content_address(row["candidate_graph_address"])
        and isinstance(row["lineage"], Mapping)
    )


def _validate_population_row(
    row: Any, evaluation_address: str, method_population: Mapping[str, Any],
) -> None:
    if not _valid_population_envelope(row) \
            or not _valid_parameters(row["parameters"]) \
            or not _valid_folds(row["folds"]):
        _reject("stored parameter-neighbourhood candidate lineage is malformed")
    expected_address = content_address({
        "schema": "saved-v2-parameter-candidate/1",
        "candidate_graph_address": row["candidate_graph_address"],
        "point": row["parameters"],
        "evaluation_contract_address": evaluation_address,
    })
    if row["candidate_address"] != expected_address \
            or method_population.get(row["candidate_address"]) != row["parameters"]:
        _reject("stored parameter-neighbourhood candidate identity differs")


def _validate_population(
    population: Any, result: Any, evaluation_address: str,
) -> None:
    method_population = {
        row["address"]: row["parameters"]
        for row in result.to_document()["candidate_population"]
    }
    if not isinstance(population, list) or len(population) != result.candidate_count:
        _reject("stored parameter-neighbourhood population differs from method evidence")
    fold_contract = None
    observed_addresses = set()
    for row in population:
        _validate_population_row(row, evaluation_address, method_population)
        if fold_contract is None:
            fold_contract = row["folds"]
        elif row["folds"] != fold_contract:
            _reject("stored parameter-neighbourhood fold contract differs")
        observed_addresses.add(row["candidate_address"])
    if observed_addresses != set(method_population):
        _reject("stored parameter-neighbourhood population differs from method evidence")


def _reconstruct_available_projection(
    stored: Mapping[str, Any], parsed_recipe: Mapping[str, Any],
    parent_spec_id: Any, parent_recipe: Any,
) -> dict[str, Any]:
    if set(stored) != {
        "schema", "state", "evaluation_contract", "population", "method",
    }:
        _reject("parameter-neighbourhood available state is open or incomplete")
    result = _reconstruct_method(stored["method"])
    evaluation = stored["evaluation_contract"]
    _validated_evaluation_contract(
        evaluation, parsed_recipe, parent_spec_id, parent_recipe,
    )
    _validate_method_request(result, parsed_recipe["parameter_neighborhood"])
    _validate_population(stored["population"], result, evaluation["address"])
    return {
        "schema": PROJECTION_SCHEMA, "state": AVAILABLE,
        "evaluation_contract": copy.deepcopy(evaluation),
        "method_address": result.address, "method": result.to_document(),
        "population": copy.deepcopy(stored["population"]),
    }


def reconstruct_parameter_neighborhood_projection(
    stored: Mapping[str, Any], *, recipe_binding: Mapping[str, Any] | None,
    parent_spec_id: Any, parent_recipe: Any,
) -> dict[str, Any]:
    parsed_recipe = (
        validate_parameter_neighborhood_recipe_binding(recipe_binding)
        if recipe_binding is not None else None
    )
    if not isinstance(stored, Mapping) or stored.get("schema") != PROJECTION_SCHEMA:
        _reject("parameter-neighbourhood projection schema is invalid")
    state = stored.get("state")
    if state not in _expected_projection_states(parsed_recipe):
        _reject("parameter-neighbourhood request and terminal state disagree")
    if state != AVAILABLE:
        return _terminal_projection(stored, state)
    return _reconstruct_available_projection(
        stored, parsed_recipe, parent_spec_id, parent_recipe,
    )


def encode_terminal_evidence_with_parameter_fallback(evidence: Mapping[str, Any]) -> str:
    try:
        return encode_terminal_evidence(evidence)
    except EvidenceRejected as exc:
        if "exceeds the persisted size limit" not in str(exc):
            raise
        results = evidence.get("results") if isinstance(evidence, Mapping) else None
        stored = results.get("parameter_neighborhood") if isinstance(results, Mapping) else None
        if not isinstance(stored, Mapping) or stored.get("state") != AVAILABLE:
            raise
        fallback = copy.deepcopy(dict(evidence))
        fallback["results"]["parameter_neighborhood"] = unavailable(
            "TERMINAL_EVIDENCE_SIZE_REFUSED"
        )
        from research.robustness.integration import (
            encode_terminal_evidence_with_robustness_fallback,
        )
        return encode_terminal_evidence_with_robustness_fallback(fallback)


__all__ = [
    "AVAILABLE", "CandidateEvaluationCancelled", "CandidateRuntime", "DISABLED",
    "EVALUATION_CONTRACT_SCHEMA", "MAXIMUM_CANDIDATES",
    "MAXIMUM_CANDIDATE_BAR_EVALUATIONS", "PROJECTION_SCHEMA",
    "ParameterNeighborhoodIntegrationRejected", "PreparedParameterNeighborhood",
    "UNAVAILABLE", "encode_terminal_evidence_with_parameter_fallback",
    "evaluate_parameter_neighborhood", "parameter_neighborhood_recipe_binding",
    "parameter_neighborhood_binding_from_provenance", "parent_experiment_identity",
    "prepare_parameter_neighborhood", "reconstruct_parameter_neighborhood_projection",
    "unavailable", "validate_parameter_neighborhood_recipe_binding",
]
