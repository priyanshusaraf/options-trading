"""Bounded canonical V2 development search using the existing optimizer math.

Axis geometry is shared with sensitivity analysis. Selection never consumes the
sensitivity score or locked-holdout trades, and runtime parameters stay in the IR.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass

from app.ir.hashing import canonical_json, content_address
from research.robustness.parameter_integration import (
    CandidateEvaluationCancelled, MAXIMUM_CANDIDATE_BAR_EVALUATIONS,
    _candidate_surface, _candidate_values, _numeric_decimal, parameter_neighborhood_recipe_binding,
    prepare_parameter_neighborhood,
)

SEARCH_SCHEMA = "canonical-local-development-search/1"
SEARCH_RECIPE_SCHEMA = "canonical-development-search-recipe/1"
SEARCH_EVIDENCE_SCHEMA = "canonical-development-search-evidence/1"


class CanonicalSearchRefusal(ValueError):
    """A saved canonical search cannot be admitted or completed."""


def disabled_search() -> dict:
    return {"schema": SEARCH_SCHEMA, "enabled": False, "axes": []}


def _axis_request(value):
    # Reuse only the existing closed axis validator and local-grid geometry.
    return {"enabled": value["enabled"], "axes": value["axes"],
            "maximum_score_drop_paise": 0, "minimum_stable_fraction_ppm": 0}


def validate_search_settings(value) -> dict:
    if not isinstance(value, dict) or set(value) != {"schema", "enabled", "axes"}:
        raise CanonicalSearchRefusal("Optimization requires its method, enabled choice and axes.")
    if value["schema"] != SEARCH_SCHEMA:
        raise CanonicalSearchRefusal("Choose the supported canonical development search method.")
    parameter_neighborhood_recipe_binding(_axis_request(value))
    return copy.deepcopy(value)


@dataclass(frozen=True)
class PreparedCanonicalSearch:
    binding: dict
    candidates: tuple[dict, ...]


def _authored_candidate_values(document, point, axes):
    parameters = _candidate_values(point, axes)
    nodes = {node["node_id"]: node for node in document["nodes"]}
    for row, axis in zip(parameters, axes):
        if row["normalized_value"] == axis["baseline"]:
            row["value"] = nodes[row["node_id"]]["parameters"][row["parameter_id"]]
    return parameters


def _canonical_candidate(document, point, axes, registry):
    from app.editor.v2_mutations import apply_semantic_commands
    parameters = _authored_candidate_values(document, point, axes)
    commands = [{"command": "set_parameter", "node_id": row["node_id"],
                 "parameter_id": row["parameter_id"], "value": row["value"]}
                for row in parameters]
    mutation = apply_semantic_commands(document, commands, registry=registry)
    return {"coordinates": dict(point), "parameters": list(parameters),
            "canonical_document": mutation.document,
            "content_address": mutation.content_address,
            "graph_address": mutation.graph_address}


def prepare_canonical_search(request, *, document, registry):
    if request is None:
        return None
    request = validate_search_settings(request)
    if not request["enabled"]:
        return None
    before = canonical_json(document)
    geometry = prepare_parameter_neighborhood(
        parameter_neighborhood_recipe_binding(_axis_request(request)),
        baseline_document=document, registry=registry)
    _, points, refusal = _candidate_surface(geometry, 0)
    if refusal or len(points) < 2:
        raise CanonicalSearchRefusal("Optimization needs between two and 81 distinct local points.")
    candidates = tuple(_canonical_candidate(document, point, geometry.axes, registry) for point in points)
    if canonical_json(document) != before:
        raise CanonicalSearchRefusal("Canonical search changed its saved baseline.")
    binding = {"schema": SEARCH_RECIPE_SCHEMA, "request": request,
        "baseline_content_address": candidates[0]["content_address"],
        "selection_data": "development", "validation_use": "locked_holdout",
        "objective": "per-trade-sharpe-times-sqrt-trades/minimum-five/1",
        "tie_break": "baseline-first-then-canonical-grid-order/1",
        "candidate_count": len(candidates), "axes": copy.deepcopy(list(geometry.axes)),
        "candidates": [{key: row[key] for key in ("coordinates", "parameters", "content_address", "graph_address")}
                       for row in candidates]}
    return PreparedCanonicalSearch(binding, candidates)


def search_progress(prepared):
    return {"schema": SEARCH_EVIDENCE_SCHEMA, "state": "pending",
            "recipe_address": content_address(prepared.binding),
            "candidates": [{**copy.deepcopy(row), "state": "pending"}
                           for row in prepared.binding["candidates"]],
            "nested_trials": [], "final_development_trials": [], "selected": None,
            "partition": None, "performance_matrix": [], "n_trials": 0, "var_sr": 0.0}


def _runtime_signals(candidate, row, evaluator, candles, partition):
    from research.evaluation import kernels
    from research.evaluation.walkforward import signal_window
    row["state"] = "running"
    try:
        runtime = evaluator(tuple(candidate["parameters"]))
        if runtime.candidate_graph_address != candidate["graph_address"]:
            raise CanonicalSearchRefusal("Evaluated candidate differs from its frozen canonical graph.")
        signals = signal_window(kernels.compute_signals(candles, runtime.strategy, {}),
            stop_before=partition["_validation_start"], expected_bars=partition["development_bars"])
    except Exception as exc:
        row["state"] = "cancelled" if isinstance(exc, CandidateEvaluationCancelled) else "failed"
        row["reason_code"] = getattr(exc, "code", "CANONICAL_CANDIDATE_EVALUATION_FAILED")
        raise
    row.update(state="evaluated", lineage=copy.deepcopy(dict(runtime.lineage)))
    return runtime, signals


def _optimize_canonical(prepared, evaluator, *, dataset, instrument, partition, settings, progress):
    from research.pipeline.optimize import optimize_signal_frames, _key
    progress["partition"] = {key: value for key, value in partition.items() if not key.startswith("_")}
    work = len(prepared.candidates) * dataset.bar_count * (settings["n_folds"] + 4)
    if work > MAXIMUM_CANDIDATE_BAR_EVALUATIONS:
        progress.update(state="refused", reason_code="CANONICAL_SEARCH_RESOURCE_REFUSED")
        raise CanonicalSearchRefusal("The candidate replay budget exceeds two million bar evaluations. Reduce axes or folds.")
    if partition["development_bars"] < settings["n_folds"] + 1:
        progress.update(state="refused", reason_code="INSUFFICIENT_DEVELOPMENT_HISTORY")
        raise CanonicalSearchRefusal("Use more development history or fewer optimization folds.")
    progress["state"] = "running"
    runtimes, signals, candidates = {}, {}, []
    for candidate, row in zip(prepared.candidates, progress["candidates"]):
        runtime, frame = _runtime_signals(candidate, row, evaluator, dataset.candles, partition)
        parameters = {**candidate["coordinates"], "candidate_graph_address": candidate["graph_address"]}
        key = _key(parameters)
        runtimes[key], signals[key] = runtime, frame
        candidates.append(parameters)
    optimization = optimize_signal_frames(signals, candidates, instrument, next(iter(runtimes.values())).strategy,
        n_folds=settings["n_folds"], capital=settings["capital"], base={}, progress=progress)
    progress.update(performance_matrix=optimization.perf_matrix,
                    n_trials=optimization.n_trials, var_sr=optimization.var_sr)
    _require_eligible_selection(optimization, progress)
    selected_key = _key(optimization.selected_params)
    selected = next(row for row in prepared.candidates
                    if row["graph_address"] == optimization.selected_params["candidate_graph_address"])
    selected_runtime = runtimes[selected_key]
    progress.update(state="selected", selected={**copy.deepcopy(selected),
        "lineage": copy.deepcopy(dict(selected_runtime.lineage))})
    return optimization, selected_runtime


def _require_eligible_selection(optimization, progress):
    if not any(trial.objective is not None for trial in optimization.final_trials):
        progress.update(state="refused", reason_code="NO_ELIGIBLE_DEVELOPMENT_CANDIDATE")
        for row in progress["final_development_trials"]:
            row["selected"] = False
        raise CanonicalSearchRefusal("No development candidate has five trades with usable dispersion. Add history or revise the strategy.")


def optimize_canonical(prepared, evaluator, *, dataset, instrument, partition, settings, progress):
    try:
        return _optimize_canonical(prepared, evaluator, dataset=dataset, instrument=instrument,
                                  partition=partition, settings=settings, progress=progress)
    except Exception as exc:
        if progress["state"] != "refused":
            cancelled = isinstance(exc, CandidateEvaluationCancelled)
            progress.update(state="cancelled" if cancelled else "failed",
                reason_code="CANDIDATE_CANCELLED" if cancelled else getattr(exc, "code", "CANONICAL_SEARCH_FAILED"))
        raise


def _ensure(condition, message):
    if not condition:
        raise CanonicalSearchRefusal(message)


def _same(left, right):
    return canonical_json(left) == canonical_json(right)


def _verify_search_method(binding):
    _ensure(binding["schema"] == SEARCH_RECIPE_SCHEMA and validate_search_settings(binding["request"])["enabled"],
            "Canonical search recipe method is invalid.")
    _ensure(binding["selection_data"] == "development" and binding["validation_use"] == "locked_holdout",
            "Canonical search must select on development and validate on later holdout.")
    _ensure(binding["objective"] == "per-trade-sharpe-times-sqrt-trades/minimum-five/1"
            and binding["tie_break"] == "baseline-first-then-canonical-grid-order/1", "Canonical selection rule differs.")


def _verify_binding(binding):
    from types import SimpleNamespace
    fields = {"schema", "request", "baseline_content_address", "selection_data", "validation_use",
              "objective", "tie_break", "candidate_count", "axes", "candidates"}
    _ensure(isinstance(binding, dict) and set(binding) == fields, "Canonical search recipe is incomplete.")
    _verify_search_method(binding)
    axes = binding["axes"]
    _verify_axes(axes, binding["request"]["axes"])
    geometry = SimpleNamespace(axes=tuple(axes), baseline_values=tuple(axis["baseline"] for axis in axes))
    _, points, refusal = _candidate_surface(geometry, 0)
    _ensure(refusal is None and type(binding["candidate_count"]) is int
            and binding["candidate_count"] == len(points) and len(points) >= 2, "Canonical search budget differs.")
    _verify_bound_population(binding, points, axes)


def _verify_bound_population(binding, points, axes):
    from app.ir.schema import is_content_address
    rows = binding["candidates"]
    _ensure(isinstance(rows, list) and len(rows) == len(points), "Canonical search population is incomplete.")
    for row, point in zip(rows, points):
        _verify_candidate_binding(row, point, axes)
    _ensure(len({row["graph_address"] for row in rows}) == len(rows), "Canonical candidate graph identities repeat.")
    _ensure(is_content_address(binding["baseline_content_address"])
            and rows[0]["content_address"] == binding["baseline_content_address"], "Canonical baseline identity differs.")


def _verify_axes(axes, request_axes):
    _ensure(isinstance(axes, list) and len(axes) == len(request_axes), "Canonical axes differ from reviewed settings.")
    for index, (axis, requested) in enumerate(zip(axes, request_axes)):
        _ensure(isinstance(axis, dict) and set(axis) == {
            "key", "node_id", "parameter_id", "parameter_type", "step", "minimum", "maximum", "baseline"},
            "Canonical axis binding is incomplete.")
        _ensure(axis["key"] == f"axis_{index:03d}" and axis["parameter_type"] in {"int", "float"},
                "Canonical axis type or ordering differs.")
        _ensure(_same({key: axis[key] for key in requested}, requested), "Canonical axis intent differs.")


def _verify_parameter_values(parameters, point, axes):
    expected = _candidate_values(point, tuple(axes))
    _ensure(isinstance(parameters, list) and len(parameters) == len(expected), "Canonical parameter population differs.")
    for actual, wanted, axis in zip(parameters, expected, axes):
        _ensure(isinstance(actual, dict) and set(actual) == set(wanted), "Canonical parameter fields differ.")
        _ensure(_same({key: value for key, value in actual.items() if key != "value"},
                      {key: value for key, value in wanted.items() if key != "value"}), "Canonical parameter identity differs.")
        _ensure(_numeric_decimal(actual["value"], "candidate value")[0] == wanted["normalized_value"],
                "Canonical numeric parameter differs.")
        if axis["parameter_type"] == "int":
            _ensure(type(actual["value"]) is int, "Canonical integer parameter changed its type.")


def _verify_candidate_binding(row, point, axes):
    from app.ir.schema import is_content_address
    _ensure(isinstance(row, dict) and set(row) == {"coordinates", "parameters", "content_address", "graph_address"},
            "Canonical candidate binding is incomplete.")
    _ensure(_same(row["coordinates"], dict(point)), "Canonical candidate coordinates differ.")
    _verify_parameter_values(row["parameters"], point, axes)
    _ensure(is_content_address(row["content_address"]) and is_content_address(row["graph_address"]),
            "Canonical candidate addresses are invalid.")


def _verify_population(progress, binding, graph_provenance):
    rows = progress["candidates"]
    _ensure(isinstance(rows, list) and len(rows) == len(binding["candidates"]), "Recorded search population is incomplete.")
    if progress["state"] == "selected":
        _ensure(all(row.get("state") == "evaluated" for row in rows), "Completed search has unevaluated candidates.")
    for row, expected in zip(rows, binding["candidates"]):
        _ensure(isinstance(row, dict) and set(row) <= set(expected) | {"state", "lineage", "reason_code"},
                "Recorded candidate fields are invalid.")
        _ensure(_same({key: row[key] for key in expected}, expected), "Recorded candidate is outside the frozen grid.")
        _ensure(row["state"] in {"pending", "running", "evaluated", "failed", "cancelled"}, "Candidate state is invalid.")
        if row["state"] == "evaluated":
            _verify_runtime_lineage(row["lineage"], expected, graph_provenance)


def _verify_runtime_lineage(lineage, candidate, provenance):
    _ensure(isinstance(lineage, dict) and lineage.get("content_address") == candidate["content_address"]
            and lineage.get("graph_address") == candidate["graph_address"], "Candidate runtime graph lineage differs.")
    for key in ("dataset_selection_address", "dataset_selection", "primary_input", "input_set_position_map_address"):
        if key in provenance:
            _ensure(_same(lineage.get(key), provenance[key]), "Candidate changed its frozen input selection.")


def _trial_parameters(candidate):
    return {**candidate["coordinates"], "candidate_graph_address": candidate["graph_address"]}


def _verify_trial(row, candidate, fold_index):
    _ensure(isinstance(row, dict) and set(row) == {"params", "fold_index", "objective", "trades", "is_sharpe", "selected"},
            "Recorded development trial is incomplete.")
    _ensure(type(row["fold_index"]) is int and row["fold_index"] == fold_index
            and _same(row["params"], _trial_parameters(candidate)), "Development trial identity differs.")
    _ensure(type(row["trades"]) is int and row["trades"] >= 0 and type(row["selected"]) is bool,
            "Development trial counts or selection flag are invalid.")
    _verify_trial_objective(row)


def _verify_trial_objective(row):
    from types import SimpleNamespace
    from research.pipeline.optimize import _objective, _MIN_IS_TRADES
    sharpe = row["is_sharpe"]
    _ensure(sharpe is None or type(sharpe) in {int, float} and math.isfinite(sharpe), "Development trial dispersion is invalid.")
    _ensure(row["trades"] >= _MIN_IS_TRADES or sharpe is None, "An ineligible trial cannot contribute Sharpe dispersion.")
    objective = _objective(SimpleNamespace(trades=row["trades"], consistency=sharpe))
    _ensure(_same(row["objective"], objective if math.isfinite(objective) else None), "Development objective does not reconstruct.")


def _verify_trials(progress, binding, n_folds):
    candidates = binding["candidates"]
    nested, final = progress["nested_trials"], progress["final_development_trials"]
    _ensure(isinstance(nested, list) and len(nested) <= len(candidates) * n_folds
            and isinstance(final, list) and len(final) <= len(candidates), "Development trial population exceeds its budget.")
    for index, trial in enumerate(nested):
        _verify_trial(trial, candidates[index % len(candidates)], index // len(candidates))
    for trial, candidate in zip(final, candidates):
        _verify_trial(trial, candidate, -1)
    if progress["state"] == "selected":
        _ensure(len(nested) == len(candidates) * n_folds and len(final) == len(candidates), "Completed search dropped trials.")
        for fold in range(n_folds):
            _verify_winner(nested[fold * len(candidates):(fold + 1) * len(candidates)])
        winner = _verify_winner(final)
        _ensure(winner["params"]["candidate_graph_address"] == progress["selected"]["graph_address"],
                "The held-out candidate was not the development winner.")


def _verify_winner(rows):
    winner = max(rows, key=lambda row: float("-inf") if row["objective"] is None else row["objective"])
    _ensure([row["selected"] for row in rows] == [row is winner for row in rows], "Development winner or tie break differs.")
    return winner


def _verify_selected_binding(selected, binding):
    _ensure(isinstance(selected, dict) and set(selected) == {
        "coordinates", "parameters", "canonical_document", "content_address", "graph_address", "lineage"},
        "Frozen selected candidate is incomplete.")
    expected = next((row for row in binding["candidates"] if row["graph_address"] == selected["graph_address"]), None)
    _ensure(expected is not None and _same({key: selected[key] for key in expected}, expected),
            "Selected candidate is outside the reviewed grid.")
    _ensure(content_address(selected["canonical_document"]) == selected["content_address"], "Selected canonical document differs.")


def _verify_selected(progress, binding):
    selected = progress["selected"]
    if progress["state"] != "selected":
        _ensure(selected is None, "An unfinished search cannot claim a selected graph.")
        return
    _verify_selected_binding(selected, binding)
    runtime = next(row for row in progress["candidates"] if row["graph_address"] == selected["graph_address"])
    _ensure(runtime["state"] == "evaluated" and _same(runtime["lineage"], selected["lineage"]), "Selected runtime lineage differs.")


def _verify_search_partition(progress, recipe):
    if progress["partition"] is not None:
        partitions = recipe["research_partition"]["datasets"]
        _ensure(len(partitions) == 1 and _same(progress["partition"], next(iter(partitions.values()))),
                "Search partition differs from the frozen development/holdout split.")


def _verify_pbo_matrix(matrix, count):
    _ensure(isinstance(matrix, list) and len(matrix) in {0, 8}, "PBO matrix block count differs.")
    for block in matrix:
        _ensure(len(block) == count
                and all(type(value) in {int, float} and math.isfinite(value) for value in block), "PBO matrix population differs.")


def _verify_search_statistics(progress, binding, recipe):
    _verify_search_partition(progress, recipe)
    if progress["state"] != "selected":
        return
    _ensure(progress["partition"] is not None, "Selected search is missing its data partition.")
    _ensure(progress["n_trials"] == recipe["gates"]["n_folds"] * binding["candidate_count"], "Search trial count differs.")
    values = [row["is_sharpe"] for row in progress["nested_trials"] if row["is_sharpe"] is not None]
    mean = sum(values) / len(values) if values else 0.0
    variance = sum((value - mean) ** 2 for value in values) / len(values) if len(values) >= 2 else 0.0
    _ensure(_same(progress["var_sr"], variance), "Search Sharpe dispersion differs.")
    _verify_pbo_matrix(progress["performance_matrix"], binding["candidate_count"])


def verify_canonical_search_evidence(recipe, evidence):
    """Reconstruct search identities and selection against the immutable recipe.

    Uses recorded canonical artifact addresses and method geometry; it neither
    resolves current Settings nor evaluates against a changing component registry.
    """
    if "canonical_optimization" not in recipe:
        return
    binding = recipe["canonical_optimization"]
    _ensure(_same(evidence["provenance"], recipe), "Search provenance differs from its immutable experiment recipe.")
    _verify_binding(binding)
    progress = evidence["results"]["canonical_optimization"]
    fields = {"schema", "state", "recipe_address", "candidates", "nested_trials", "final_development_trials",
              "selected", "partition", "performance_matrix", "n_trials", "var_sr"}
    _ensure(isinstance(progress, dict) and set(progress) in (fields, fields | {"reason_code"}), "Search evidence fields differ.")
    _ensure(progress["schema"] == SEARCH_EVIDENCE_SCHEMA and progress["recipe_address"] == content_address(binding),
            "Search evidence method or recipe identity differs.")
    _ensure(progress["state"] in {"pending", "running", "failed", "cancelled", "refused", "not_qualified", "selected"},
            "Search evidence state is invalid.")
    _verify_population(progress, binding, recipe.get("graph_provenance", {}))
    _verify_selected(progress, binding)
    _verify_trials(progress, binding, recipe["gates"]["n_folds"])
    _verify_search_statistics(progress, binding, recipe)
    _verify_terminal_search(progress, evidence)


def _verify_not_qualified(progress):
    _ensure(progress["reason_code"] == "BASELINE_NOT_QUALIFIED", "Skipped search reason differs.")
    _ensure(all(row["state"] == "pending" for row in progress["candidates"]), "An unqualified baseline cannot claim evaluated candidates.")
    _ensure(_same({key: progress[key] for key in ("nested_trials", "final_development_trials", "selected", "partition", "performance_matrix", "n_trials", "var_sr")},
                  {"nested_trials": [], "final_development_trials": [], "selected": None, "partition": None,
                   "performance_matrix": [], "n_trials": 0, "var_sr": 0.0}), "An unqualified baseline cannot claim search results.")


def _verify_terminal_search(progress, evidence):
    status = evidence["run"]["status"]
    _ensure(status in {"completed", "failed"}, "Search evidence is not terminal.")
    if status == "failed":
        _ensure(isinstance(evidence["results"].get("failure"), dict), "Failed search is missing its reason.")
        return
    instruments = evidence["results"]["instruments"]
    _ensure(isinstance(instruments, list) and len(instruments) == 1, "Canonical search requires one primary result.")
    result = instruments[0]
    qualified = result["qualification"]["qualified"]
    _ensure(type(qualified) is bool, "Baseline qualification flag is invalid.")
    _ensure(progress["state"] == ("selected" if qualified else "not_qualified"), "Completed search contradicts baseline qualification.")
    if not qualified:
        _verify_not_qualified(progress)
        return
    _ensure(_same(result["research_partition"], progress["partition"]), "Holdout result partition differs from the search split.")
    _ensure(_same(result["validation"]["params"], _trial_parameters(progress["selected"])), "Holdout result names a different candidate.")
