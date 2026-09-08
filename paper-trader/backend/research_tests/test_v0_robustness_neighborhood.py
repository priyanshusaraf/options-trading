from __future__ import annotations

import ast
import dataclasses
import json
import os
from pathlib import Path
import subprocess
import sys
from itertools import product

import pytest

from app.ir.hashing import content_address
from research.robustness import neighborhood as subject


def _address(label: str) -> str:
    return content_address({"candidate": label})


def _candidate(label: str, parameters, score: int = 100, passed: bool = True):
    return subject.NeighborhoodCandidate(
        address=_address(label),
        parameters=tuple(parameters),
        oos_score=score,
        passed=passed,
    )


def _axis(key: str, step: str = "1", lower: str = "0", upper: str = "2"):
    return subject.ParameterAxis(key=key, step=step, lower_bound=lower, upper_bound=upper)


def _complete_input(
    axes=(_axis("a"),),
    *,
    baseline_values=("1",),
    scores=None,
    passes=None,
    max_score_drop=10,
    minimum_stable_fraction_ppm=500_000,
):
    points = subject.expected_local_points(tuple(axes), tuple(baseline_values))
    scores = scores or {}
    passes = passes or {}
    candidates = tuple(
        _candidate(
            "|".join(value for _, value in point),
            point,
            scores.get(tuple(value for _, value in point), 100),
            passes.get(tuple(value for _, value in point), True),
        )
        for point in points
    )
    baseline_point = tuple((axis.key, value) for axis, value in zip(axes, baseline_values))
    baseline = next(candidate for candidate in candidates if candidate.parameters == baseline_point)
    return subject.ParameterNeighborhoodInput(
        baseline=baseline,
        candidates=candidates,
        axes=tuple(axes),
        maximum_score_drop=max_score_drop,
        minimum_stable_fraction_ppm=minimum_stable_fraction_ppm,
    )


def _wide_input():
    axes = tuple(_axis(f"p{index}", lower="0", upper="4") for index in range(4))
    candidates = tuple(
        _candidate(
            "wide:" + "|".join(values),
            tuple((axis.key, value) for axis, value in zip(axes, values)),
            score=100 + sum(int(value) for value in values),
        )
        for values in product(("0", "1", "2", "3", "4"), repeat=4)
    )
    baseline = next(
        candidate for candidate in candidates
        if tuple(value for _, value in candidate.parameters) == ("2", "2", "2", "2")
    )
    return subject.ParameterNeighborhoodInput(
        baseline=baseline,
        candidates=candidates,
        axes=axes,
        maximum_score_drop=10,
        minimum_stable_fraction_ppm=500_000,
    )


def _local_projection(result):
    document = result.to_document()
    keys = (
        "expected_neighbor_count", "stable_neighbor_count", "unstable_neighbor_count",
        "stable_fraction", "stable_fraction_ppm", "score_summary", "sensitivity",
        "local_membership", "stable",
    )
    return subject.canonical_json({key: document[key] for key in keys}).encode("utf-8")


def _refusal(code, factory):
    with pytest.raises(subject.NeighborhoodRefusal) as caught:
        subject.analyze_parameter_neighborhood(factory())
    assert caught.value.code is code


def test_failing_first_contract_import_and_schema_are_frozen():
    request = _complete_input()
    result = subject.analyze_parameter_neighborhood(request)

    assert result.schema == "strategy-os-parameter-neighbourhood/1"
    assert result.method_version == "complete-cartesian-local-grid/1"
    assert result.address == content_address(result.to_document())
    assert result.canonical_bytes == subject.canonical_json(result.to_document()).encode("utf-8")
    assert result.to_document()["limitations"] == list(subject.LIMITATIONS)


def test_public_reconstruction_replays_the_complete_addressed_input():
    result = subject.analyze_parameter_neighborhood(_complete_input())

    reconstructed = subject.reconstruct_parameter_neighborhood(
        result.canonical_bytes, result.address,
    )

    assert reconstructed == result
    assert reconstructed.canonical_bytes == result.canonical_bytes


def test_direct_result_construction_is_unavailable():
    with pytest.raises(TypeError):
        subject.ParameterNeighborhoodResult(
            schema=subject.RESULT_SCHEMA,
            method_version=subject.METHOD_VERSION,
            canonical_bytes=b"{}",
            address=content_address({}),
            candidate_count=0,
            expected_neighbor_count=0,
            stable_neighbor_count=0,
            stable=False,
        )


def test_public_reconstruction_refuses_coherently_readdressed_forged_outputs():
    result = subject.analyze_parameter_neighborhood(_complete_input())
    document = result.to_document()
    document["local_membership"][0]["stable"] = False
    document["stable_neighbor_count"] = 1
    document["unstable_neighbor_count"] = 1
    document["stable_fraction"] = {"numerator": 1, "denominator": 2}
    document["stable_fraction_ppm"] = {"numerator": 500_000, "denominator": 1}
    document["score_summary"]["minimum"] = 99
    document["stable"] = True
    encoded = subject.canonical_json(document).encode("utf-8")

    with pytest.raises(subject.NeighborhoodRefusal) as caught:
        subject.reconstruct_parameter_neighborhood(encoded, content_address(document))

    assert caught.value.code is subject.RefusalCode.RESULT_REPLAY_INVALID


@pytest.mark.parametrize(
    "field",
    ["population", "digest", "membership", "summary", "sensitivity", "decision"],
)
def test_public_reconstruction_refuses_every_readdressed_result_forgery(field):
    result = subject.analyze_parameter_neighborhood(_wide_input())
    document = result.to_document()
    if field == "population":
        document["candidate_population"][0]["oos_score"] += 1
    elif field == "digest":
        document["candidate_population_digest"] = _address("forged-population-digest")
    elif field == "membership":
        document["local_membership"][0]["stable"] = not document["local_membership"][0]["stable"]
    elif field == "summary":
        document["score_summary"]["maximum"] += 1
    elif field == "sensitivity":
        document["sensitivity"][0]["negative"]["score_delta"] += 1
    else:
        document["stable"] = not document["stable"]
    encoded = subject.canonical_json(document).encode("utf-8")

    with pytest.raises(subject.NeighborhoodRefusal) as caught:
        subject.reconstruct_parameter_neighborhood(encoded, content_address(document))

    assert caught.value.code is subject.RefusalCode.RESULT_REPLAY_INVALID


@pytest.mark.parametrize("field", ["method_version", "limitations"])
def test_public_reconstruction_refuses_readdressed_method_or_limitation_tampering(field):
    result = subject.analyze_parameter_neighborhood(_complete_input())
    document = result.to_document()
    if field == "method_version":
        document[field] = "complete-cartesian-local-grid/forged"
    else:
        document[field].append("forged conclusion")
    encoded = subject.canonical_json(document).encode("utf-8")

    with pytest.raises(subject.NeighborhoodRefusal) as caught:
        subject.reconstruct_parameter_neighborhood(encoded, content_address(document))

    assert caught.value.code is subject.RefusalCode.RESULT_REPLAY_INVALID


@pytest.mark.parametrize("dimensions", [1, 2, 3, 4])
def test_complete_grid_accepts_one_through_four_dimensions(dimensions):
    axes = tuple(_axis(chr(ord("a") + index)) for index in range(dimensions))
    request = _complete_input(axes, baseline_values=("1",) * dimensions)

    result = subject.analyze_parameter_neighborhood(request)

    assert result.expected_neighbor_count == 3**dimensions - 1
    assert result.candidate_count == 3**dimensions
    assert result.stable_neighbor_count == result.expected_neighbor_count
    assert result.stable is True
    assert len(result.to_document()["candidate_population"]) == 3**dimensions
    assert len(result.to_document()["local_membership"]) == 3**dimensions - 1


def test_boundary_clipping_enumerates_only_complete_in_bounds_cartesian_grid():
    axes = (_axis("a", lower="1", upper="2"), _axis("b", lower="0", upper="1"))
    request = _complete_input(axes, baseline_values=("1", "1"))

    result = subject.analyze_parameter_neighborhood(request)

    assert result.candidate_count == 4
    assert result.expected_neighbor_count == 3
    points = {tuple(value for _, value in row["parameters"])
              for row in result.to_document()["local_membership"]}
    assert points == {("1", "0"), ("2", "0"), ("2", "1")}


def test_exact_classification_counts_fraction_summaries_variance_and_sensitivity():
    request = _complete_input(
        scores={("0",): 91, ("1",): 100, ("2",): 80},
        passes={("2",): False},
        max_score_drop=9,
        minimum_stable_fraction_ppm=500_000,
    )

    result = subject.analyze_parameter_neighborhood(request)
    document = result.to_document()

    assert result.stable_neighbor_count == 1
    assert result.stable is True
    assert document["stable_fraction"] == {"numerator": 1, "denominator": 2}
    assert document["stable_fraction_ppm"] == {"numerator": 500_000, "denominator": 1}
    assert document["score_summary"] == {
        "minimum": 80,
        "maximum": 91,
        "median": {"numerator": 171, "denominator": 2},
        "variance": {"numerator": 121, "denominator": 4},
    }
    assert document["sensitivity"] == [
        {
            "parameter": "a",
            "negative": {
                "candidate_address": _address("0"),
                "parameter_value": "0",
                "score_delta": -9,
                "passed": True,
                "stable": True,
            },
            "positive": {
                "candidate_address": _address("2"),
                "parameter_value": "2",
                "score_delta": -20,
                "passed": False,
                "stable": False,
            },
        }
    ]


def test_exact_threshold_comparison_does_not_floor_the_observed_fraction():
    axes = (_axis("a"), _axis("b"))
    scores = {(a, b): (100 if (a, b) in {("0", "0"), ("0", "1"), ("0", "2")} else 0)
              for a in ("0", "1", "2") for b in ("0", "1", "2")}
    scores[("1", "1")] = 100
    request = _complete_input(
        axes,
        baseline_values=("1", "1"),
        scores=scores,
        max_score_drop=0,
        minimum_stable_fraction_ppm=375_001,
    )

    result = subject.analyze_parameter_neighborhood(request)

    assert result.stable_neighbor_count == 3
    assert result.expected_neighbor_count == 8
    assert result.stable is False
    assert result.to_document()["stable_fraction_ppm"] == {
        "numerator": 375_000,
        "denominator": 1,
    }


def test_pass_state_and_score_drop_are_both_required_for_stability():
    for score, passed in ((89, True), (100, False)):
        request = _complete_input(
            scores={("0",): score, ("1",): 100, ("2",): 100},
            passes={("0",): passed},
            max_score_drop=10,
            minimum_stable_fraction_ppm=1_000_000,
        )
        result = subject.analyze_parameter_neighborhood(request)
        assert result.stable is False
        assert result.stable_neighbor_count == 1


def test_population_order_is_semantically_unordered_and_identity_invariant():
    request = _complete_input()
    reordered = dataclasses.replace(request, candidates=tuple(reversed(request.candidates)))

    left = subject.analyze_parameter_neighborhood(request)
    right = subject.analyze_parameter_neighborhood(reordered)

    assert left.canonical_bytes == right.canonical_bytes
    assert left.address == right.address


def test_duplicate_address_refuses_before_publication():
    request = _complete_input()
    candidates = list(request.candidates)
    candidates[1] = dataclasses.replace(candidates[1], address=candidates[0].address)
    _refusal(subject.RefusalCode.DUPLICATE_ADDRESS,
             lambda: dataclasses.replace(request, candidates=tuple(candidates)))


def test_duplicate_point_refuses_before_publication():
    request = _complete_input()
    candidates = request.candidates + (
        dataclasses.replace(request.candidates[-1], address=_address("distinct-address")),
    )
    _refusal(subject.RefusalCode.DUPLICATE_POINT,
             lambda: dataclasses.replace(request, candidates=candidates))


def test_missing_expected_neighbor_refuses_before_publication():
    request = _complete_input()
    _refusal(subject.RefusalCode.MISSING_EXPECTED_NEIGHBOR,
             lambda: dataclasses.replace(request, candidates=request.candidates[:-1]))


def test_valid_distant_in_bounds_candidate_is_retained_outside_local_metrics():
    request = _complete_input()
    extra = _candidate("3", (("a", "3"),))
    widened = dataclasses.replace(
        request,
        axes=(_axis("a", lower="0", upper="3"),),
        candidates=request.candidates + (extra,),
    )

    result = subject.analyze_parameter_neighborhood(widened)

    assert result.candidate_count == 4
    assert result.expected_neighbor_count == 2
    assert len(result.to_document()["local_membership"]) == 2


def test_valid_625_candidate_population_retains_all_trials_and_80_local_neighbours():
    result = subject.analyze_parameter_neighborhood(_wide_input())

    assert result.candidate_count == subject.MAXIMUM_CANDIDATES == 625
    assert result.expected_neighbor_count == subject.MAXIMUM_EXPECTED_LOCAL_NEIGHBORS == 80
    assert len(result.to_document()["candidate_population"]) == 625
    assert len(result.to_document()["local_membership"]) == 80
    assert subject.reconstruct_parameter_neighborhood(result.canonical_bytes, result.address) == result


def test_wide_population_missing_local_point_still_refuses():
    request = _wide_input()
    candidates = tuple(
        candidate for candidate in request.candidates
        if tuple(value for _, value in candidate.parameters) != ("1", "1", "1", "1")
    )
    _refusal(subject.RefusalCode.MISSING_EXPECTED_NEIGHBOR,
             lambda: dataclasses.replace(request, candidates=candidates))


def test_wide_population_duplicate_address_and_point_still_refuse():
    request = _wide_input()
    duplicate_address = list(request.candidates)
    duplicate_address[-1] = dataclasses.replace(
        duplicate_address[-1], address=duplicate_address[0].address,
    )
    _refusal(subject.RefusalCode.DUPLICATE_ADDRESS,
             lambda: dataclasses.replace(request, candidates=tuple(duplicate_address)))

    duplicate_point = list(request.candidates)
    duplicate_point[-1] = dataclasses.replace(
        duplicate_point[-1], parameters=duplicate_point[0].parameters,
    )
    _refusal(subject.RefusalCode.DUPLICATE_POINT,
             lambda: dataclasses.replace(request, candidates=tuple(duplicate_point)))


def test_wide_population_out_of_bounds_distant_candidate_refuses():
    request = _wide_input()
    candidates = list(request.candidates)
    parameters = list(candidates[-1].parameters)
    parameters[0] = ("p0", "5")
    candidates[-1] = dataclasses.replace(candidates[-1], parameters=tuple(parameters))
    _refusal(subject.RefusalCode.CANDIDATE_OUT_OF_BOUNDS,
             lambda: dataclasses.replace(request, candidates=tuple(candidates)))


def test_full_population_reorder_is_identity_invariant():
    request = _wide_input()
    reordered = dataclasses.replace(request, candidates=tuple(reversed(request.candidates)))
    assert subject.analyze_parameter_neighborhood(reordered).address == \
        subject.analyze_parameter_neighborhood(request).address


def test_distant_candidate_identity_and_record_bind_full_identity_not_local_metrics():
    request = _wide_input()
    baseline = subject.analyze_parameter_neighborhood(request)
    distant = request.candidates[0]

    changed_identity = dataclasses.replace(distant, address=_address("changed-distant-identity"))
    identity_request = dataclasses.replace(
        request,
        candidates=(changed_identity,) + request.candidates[1:],
    )
    changed_record = dataclasses.replace(distant, oos_score=distant.oos_score + 1)
    record_request = dataclasses.replace(
        request,
        candidates=(changed_record,) + request.candidates[1:],
    )
    identity_result = subject.analyze_parameter_neighborhood(identity_request)
    record_result = subject.analyze_parameter_neighborhood(record_request)

    assert len({
        baseline.to_document()["candidate_population_digest"],
        identity_result.to_document()["candidate_population_digest"],
        record_result.to_document()["candidate_population_digest"],
    }) == 3
    assert len({baseline.address, identity_result.address, record_result.address}) == 3
    assert _local_projection(identity_result) == _local_projection(baseline)
    assert _local_projection(record_result) == _local_projection(baseline)


def test_baseline_must_occur_exactly_once_and_match_the_population_record():
    request = _complete_input()
    absent = dataclasses.replace(request, baseline=dataclasses.replace(request.baseline,
                                                                        address=_address("absent")))
    _refusal(subject.RefusalCode.BASELINE_INVALID, lambda: absent)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("address", "candidate-1", subject.RefusalCode.ADDRESS_INVALID),
        ("passed", 1, subject.RefusalCode.PASS_STATE_INVALID),
        ("passed", "true", subject.RefusalCode.PASS_STATE_INVALID),
    ],
)
def test_unknown_candidate_identity_or_pass_state_refuses(field, value, code):
    request = _complete_input()
    candidates = list(request.candidates)
    candidates[0] = dataclasses.replace(candidates[0], **{field: value})
    _refusal(code, lambda: dataclasses.replace(request, candidates=tuple(candidates)))


@pytest.mark.parametrize(
    "parameters",
    [
        (("wrong", "1"),),
        (("a", "1"), ("extra", "2")),
        tuple(),
        (("a", "1"), ("a", "1")),
    ],
)
def test_wrong_extra_missing_or_duplicate_parameter_keys_refuse(parameters):
    request = _complete_input()
    candidates = list(request.candidates)
    candidates[0] = dataclasses.replace(candidates[0], parameters=parameters)
    _refusal(subject.RefusalCode.PARAMETER_KEYS_INVALID,
             lambda: dataclasses.replace(request, candidates=tuple(candidates)))


@pytest.mark.parametrize(
    "value",
    ["-0", "-0.0", "1.0", "01", "+1", "1e0", ".5", "0.50", "NaN", "Infinity", "", 1, 1.0, True],
)
def test_non_normal_negative_zero_boolean_float_and_non_string_parameter_values_refuse(value):
    request = _complete_input()
    candidates = list(request.candidates)
    candidates[1] = dataclasses.replace(candidates[1], parameters=(("a", value),))
    _refusal(subject.RefusalCode.DECIMAL_INVALID,
             lambda: dataclasses.replace(request, candidates=tuple(candidates)))


@pytest.mark.parametrize(
    "axis",
    [
        _axis("a", step="0"),
        _axis("a", step="-1"),
        _axis("a", step="1.0"),
        _axis("a", lower="2", upper="1"),
        _axis("a", lower="-0", upper="2"),
    ],
)
def test_invalid_step_bounds_and_non_normal_axis_decimals_refuse(axis):
    request = _complete_input()
    expected = (subject.RefusalCode.STEP_INVALID if axis.step in {"0", "-1"}
                else subject.RefusalCode.DECIMAL_INVALID
                if axis.step == "1.0" or axis.lower_bound == "-0"
                else subject.RefusalCode.BOUNDS_INVALID)
    _refusal(expected, lambda: dataclasses.replace(request, axes=(axis,)))


@pytest.mark.parametrize("count", [0, 5])
def test_parameter_count_outside_one_to_four_refuses(count):
    request = _complete_input()
    axes = tuple(_axis(f"p{index}") for index in range(count))
    _refusal(subject.RefusalCode.PARAMETER_COUNT,
             lambda: dataclasses.replace(request, axes=axes))


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, -(2**63) - 1, 2**63])
def test_non_integer_boolean_float_and_overflow_scores_refuse(value):
    request = _complete_input()
    candidates = list(request.candidates)
    candidates[0] = dataclasses.replace(candidates[0], oos_score=value)
    code = subject.RefusalCode.ARITHMETIC_OVERFLOW if type(value) is int else subject.RefusalCode.SCORE_INVALID
    _refusal(code, lambda: dataclasses.replace(request, candidates=tuple(candidates)))


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("maximum_score_drop", True, subject.RefusalCode.THRESHOLD_INVALID),
        ("maximum_score_drop", 1.0, subject.RefusalCode.THRESHOLD_INVALID),
        ("maximum_score_drop", -1, subject.RefusalCode.THRESHOLD_INVALID),
        ("maximum_score_drop", 2**63, subject.RefusalCode.ARITHMETIC_OVERFLOW),
        ("minimum_stable_fraction_ppm", False, subject.RefusalCode.THRESHOLD_INVALID),
        ("minimum_stable_fraction_ppm", 1.0, subject.RefusalCode.THRESHOLD_INVALID),
        ("minimum_stable_fraction_ppm", -1, subject.RefusalCode.THRESHOLD_INVALID),
        ("minimum_stable_fraction_ppm", 1_000_001, subject.RefusalCode.THRESHOLD_INVALID),
    ],
)
def test_invalid_thresholds_refuse(field, value, code):
    request = _complete_input()
    _refusal(code, lambda: dataclasses.replace(request, **{field: value}))


def test_candidate_resource_bound_refuses_before_point_processing():
    request = _complete_input()
    malformed = dataclasses.replace(request.baseline, parameters=(("wrong", object()),))
    candidates = (malformed,) * (subject.MAXIMUM_CANDIDATES + 1)
    _refusal(subject.RefusalCode.CANDIDATE_COUNT,
             lambda: dataclasses.replace(request, candidates=candidates))


def test_maximum_expected_neighbor_bound_is_exact_for_four_dimensions():
    axes = tuple(_axis(f"p{index}") for index in range(4))
    request = _complete_input(axes, baseline_values=("1",) * 4)
    result = subject.analyze_parameter_neighborhood(request)
    assert result.expected_neighbor_count == subject.MAXIMUM_EXPECTED_LOCAL_NEIGHBORS == 80


def test_decimal_size_and_operation_overflow_refuse_without_partial_result():
    request = _complete_input()
    huge = "9" * (subject.MAXIMUM_DECIMAL_CHARACTERS + 1)
    axis = _axis("a", step="1", lower="0", upper=huge)
    _refusal(subject.RefusalCode.ARITHMETIC_OVERFLOW,
             lambda: dataclasses.replace(request, axes=(axis,)))


def test_decimal_character_bound_accepts_an_exact_128_character_local_grid():
    baseline_value = "1" + "0" * (subject.MAXIMUM_DECIMAL_CHARACTERS - 1)
    lower = "9" * (subject.MAXIMUM_DECIMAL_CHARACTERS - 1)
    upper = "1" + "0" * (subject.MAXIMUM_DECIMAL_CHARACTERS - 2) + "1"
    axis = _axis("a", step="1", lower=lower, upper=upper)
    request = _complete_input((axis,), baseline_values=(baseline_value,))
    result = subject.analyze_parameter_neighborhood(request)
    assert result.expected_neighbor_count == 2


@pytest.mark.parametrize("minimum_ppm", [0, 1_000_000])
def test_threshold_ppm_inclusive_bounds_are_accepted(minimum_ppm):
    result = subject.analyze_parameter_neighborhood(
        _complete_input(minimum_stable_fraction_ppm=minimum_ppm)
    )
    assert result.stable is True


@pytest.mark.parametrize("score", [-(2**63), 2**63 - 1])
def test_signed_64_bit_score_bounds_are_inclusive(score):
    result = subject.analyze_parameter_neighborhood(
        _complete_input(scores={("0",): score, ("1",): score, ("2",): score},
                        max_score_drop=0)
    )
    assert result.to_document()["score_summary"]["minimum"] == score


def test_input_and_result_are_frozen_and_documents_are_defensive_copies():
    request = _complete_input()
    result = subject.analyze_parameter_neighborhood(request)
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.maximum_score_drop = 99
    document = result.to_document()
    document["candidate_population"].clear()
    assert len(result.to_document()["candidate_population"]) == 3


def test_any_baseline_candidate_bound_step_threshold_method_or_limitation_change_changes_identity(monkeypatch):
    request = _complete_input()
    original = subject.analyze_parameter_neighborhood(request).address
    mutations = [
        dataclasses.replace(request, maximum_score_drop=11),
        dataclasses.replace(request, minimum_stable_fraction_ppm=500_001),
        _complete_input((_axis("a", step="2", lower="-1", upper="3"),), baseline_values=("1",)),
        _complete_input((_axis("a", lower="-1", upper="2"),), baseline_values=("1",)),
    ]
    candidate_request = _complete_input(scores={("0",): 99})
    mutations.append(candidate_request)
    changed_baseline = dataclasses.replace(request.baseline, address=_address("new-baseline-identity"))
    changed_population = tuple(changed_baseline if candidate == request.baseline else candidate
                               for candidate in request.candidates)
    mutations.append(dataclasses.replace(request, baseline=changed_baseline,
                                         candidates=changed_population))
    changed_candidate = dataclasses.replace(request.candidates[0], address=_address("new-candidate-identity"))
    mutations.append(dataclasses.replace(
        request,
        candidates=tuple(changed_candidate if candidate == request.candidates[0] else candidate
                         for candidate in request.candidates),
    ))
    assert all(subject.analyze_parameter_neighborhood(item).address != original for item in mutations)

    monkeypatch.setattr(subject, "METHOD_VERSION", "complete-cartesian-local-grid/ablation")
    assert subject.analyze_parameter_neighborhood(request).address != original
    monkeypatch.setattr(subject, "METHOD_VERSION", "complete-cartesian-local-grid/1")
    monkeypatch.setattr(subject, "LIMITATIONS", subject.LIMITATIONS + ("identity sensitivity probe",))
    assert subject.analyze_parameter_neighborhood(request).address != original


def test_separate_process_document_bytes_and_address_are_identical():
    script = """
import json
from app.ir.hashing import content_address
from research.robustness.neighborhood import ParameterAxis, NeighborhoodCandidate, ParameterNeighborhoodInput, analyze_parameter_neighborhood
def c(label, value):
    return NeighborhoodCandidate(content_address({'candidate': label}), (('a', value),), 100, True)
candidates = (c('2', '2'), c('0', '0'), c('1', '1'))
request = ParameterNeighborhoodInput(candidates[2], candidates, (ParameterAxis('a', '1', '0', '2'),), 10, 500000)
result = analyze_parameter_neighborhood(request)
print(json.dumps({'bytes': result.canonical_bytes.decode(), 'address': result.address}, sort_keys=True))
"""
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[1])}
    outputs = [subprocess.check_output([sys.executable, "-c", script], env=env, text=True)
               for _ in range(2)]
    assert outputs[0] == outputs[1]
    payload = json.loads(outputs[0])
    assert payload["address"] == content_address(json.loads(payload["bytes"]))


def test_module_has_only_allowed_pure_imports_and_uses_canonical_hash_authority():
    source_path = Path(subject.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imports <= {"__future__", "dataclasses", "decimal", "enum", "fractions", "itertools", "json", "typing", "app"}
    assert "from app.ir.hashing import canonical_json, content_address" in source_path.read_text(encoding="utf-8")
