"""Critical contracts for complete saved-V2 parameter-neighbourhood evidence."""
from __future__ import annotations

import copy
import datetime as dt
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.ir.hashing import content_address
from research.robustness.parameter_integration import (
    AVAILABLE,
    CandidateEvaluationCancelled,
    CandidateRuntime,
    ParameterNeighborhoodIntegrationRejected,
    evaluate_parameter_neighborhood,
    encode_terminal_evidence_with_parameter_fallback,
    parameter_neighborhood_recipe_binding,
    parent_experiment_identity,
    prepare_parameter_neighborhood,
    reconstruct_parameter_neighborhood_projection,
)


def _settings(**changes):
    value = {
        "enabled": True,
        "axes": [{
            "node_id": "rising", "parameter_id": "window",
            "step": "1", "minimum": "1", "maximum": "3",
        }],
        "maximum_score_drop_paise": 100,
        "minimum_stable_fraction_ppm": 500_000,
    }
    value.update(changes)
    return value


def _document():
    return {"nodes": [{
        "node_id": "rising",
        "component": {"component_id": "analytical.rising", "component_version": 2},
        "parameters": {"window": 2},
    }]}


def _registry():
    return SimpleNamespace(v2_components={
        ("analytical.rising", 2): {"parameters": {"window": {
            "type": "int", "enum": None,
            "domain": {"minimum": 1, "maximum": 20},
        }}},
    })


def _prepared(settings=None):
    return prepare_parameter_neighborhood(
        parameter_neighborhood_recipe_binding(settings or _settings()),
        baseline_document=_document(), registry=_registry(),
    )


def _parent_recipe(**changes):
    recipe = {
        "graph_provenance": {"graph": {"content_address": content_address({"g": 1})}},
        "datasets": {"SAME": {
            "instrument_key": "SAME", "interval": "day", "requested_days": 1,
            "bar_count": 5, "start_ts": 10, "end_ts": 20,
            "content_hash": content_address({"dataset": 1}),
        }},
        "resolved_charge_schedule": {"address": content_address({"charges": 1})},
    }
    recipe.update(changes)
    return recipe


def _parent_identity(recipe=None, spec_id="a" * 32):
    return parent_experiment_identity(spec_id=spec_id, recipe=recipe or _parent_recipe())


def _reconstruct(evidence, recipe_binding=None, recipe=None, spec_id="a" * 32):
    return reconstruct_parameter_neighborhood_projection(
        evidence, recipe_binding=recipe_binding or _prepared().recipe_binding,
        parent_spec_id=spec_id, parent_recipe=recipe or _parent_recipe(),
    )


def _validation(score, *, changed_fold=False):
    trade = SimpleNamespace(net_pnl=score)
    fold = SimpleNamespace(
        fold_index=0, start_ts=10, end_ts=20 if not changed_fold else 21,
        n_bars=5, trades=[trade],
    )
    return SimpleNamespace(
        wf=SimpleNamespace(folds=[fold]),
        gates={"hard": {"passed": score >= 0, "value": score}},
    )


def test_absence_is_byte_compatible_and_present_request_changes_identity():
    assert parameter_neighborhood_recipe_binding(None) is None
    first = parameter_neighborhood_recipe_binding(_settings())
    changed = parameter_neighborhood_recipe_binding(
        _settings(maximum_score_drop_paise=101)
    )
    assert first != changed
    assert content_address(first) != content_address(changed)


@pytest.mark.parametrize("settings", [
    _settings(axes=[]),
    _settings(enabled=False),
    _settings(enabled=False, axes=[], maximum_score_drop_paise=1),
    _settings(axes=[_settings()["axes"][0]] * 2),
    _settings(axes=[{**_settings()["axes"][0], "step": "1.0"}]),
])
def test_request_is_closed_bounded_and_normalized(settings):
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        parameter_neighborhood_recipe_binding(settings)


def test_axis_and_decimal_boundaries_are_exact():
    one = _settings()
    assert len(parameter_neighborhood_recipe_binding(one)["parameter_neighborhood"]["axes"]) == 1
    four_axes = [{
        "node_id": f"node{index}", "parameter_id": "window",
        "step": "1", "minimum": "1", "maximum": "3",
    } for index in range(4)]
    assert len(parameter_neighborhood_recipe_binding(
        _settings(axes=four_axes)
    )["parameter_neighborhood"]["axes"]) == 4
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        parameter_neighborhood_recipe_binding(_settings(axes=four_axes + [{
            "node_id": "node4", "parameter_id": "window",
            "step": "1", "minimum": "1", "maximum": "3",
        }]))

    decimal_128 = "0." + "0" * 125 + "1"
    decimal_129 = "0." + "0" * 126 + "1"
    assert len(decimal_128) == 128 and len(decimal_129) == 129
    assert parameter_neighborhood_recipe_binding(_settings(axes=[{
        **one["axes"][0], "step": decimal_128,
    }])) is not None
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        parameter_neighborhood_recipe_binding(_settings(axes=[{
            **one["axes"][0], "step": decimal_129,
        }]))


def test_prepare_rejects_non_numeric_enumerated_and_out_of_domain_axes():
    registry = _registry()
    registry.v2_components[("analytical.rising", 2)]["parameters"]["window"]["enum"] = [2]
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        prepare_parameter_neighborhood(
            parameter_neighborhood_recipe_binding(_settings()),
            baseline_document=_document(), registry=registry,
        )


def test_float_axis_accepts_canonical_integer_valued_baseline_and_refuses_lossy_point():
    document = _document()
    document["nodes"][0]["parameters"]["window"] = 2.0
    registry = _registry()
    descriptor = registry.v2_components[("analytical.rising", 2)]["parameters"]["window"]
    descriptor["type"] = "float"
    prepared = prepare_parameter_neighborhood(
        parameter_neighborhood_recipe_binding(_settings(axes=[{
            **_settings()["axes"][0], "step": "0.5", "minimum": "1.5",
            "maximum": "2.5",
        }])), baseline_document=document, registry=registry,
    )
    assert prepared.baseline_values == ("2",)

    lossy = parameter_neighborhood_recipe_binding(_settings(axes=[{
        **_settings()["axes"][0], "step": "0.0000000000000000001",
        "minimum": "1.9999999999999999999", "maximum": "2.0000000000000000001",
    }]))
    prepared_lossy = prepare_parameter_neighborhood(
        lossy, baseline_document=document, registry=registry,
    )
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        from research.robustness.parameter_integration import _typed_value
        _typed_value("2.0000000000000000001", prepared_lossy.axes[0]["parameter_type"])
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        prepare_parameter_neighborhood(
            parameter_neighborhood_recipe_binding(_settings(axes=[{
                **_settings()["axes"][0], "maximum": "21",
            }])), baseline_document=_document(), registry=_registry(),
        )


def test_complete_grid_evaluates_once_scores_signed_paise_and_reconstructs(monkeypatch):
    calls = []
    validation_calls = []

    def evaluator(point):
        value = point[0]["value"]
        calls.append(value)
        return CandidateRuntime(
            strategy=SimpleNamespace(score={1: -1.25, 2: 2.5, 3: 2.0}[value]),
            candidate_graph_address=content_address({"graph": value}),
            lineage={"candidate": value, "authority": content_address({"a": value})},
        )

    def validate_candidate(_candles, _instrument, strategy, _params, **kwargs):
        validation_calls.append(kwargs)
        return _validation(strategy.score)

    monkeypatch.setattr("research.pipeline.validate.validate", validate_candidate)
    evidence = evaluate_parameter_neighborhood(
        _prepared(), candidate_evaluator=evaluator,
        candles=object(), instrument=object(), dataset_bars=5,
        parent_fold_signature=((0, 10, 20, 5),),
        parent_identity=_parent_identity(),
        n_folds=2, capital=50_000.0, min_trades=1,
        min_positive_fold_frac=0.5, slippage_bps=5.0,
        slippage_multiplier=2.0, seed=7,
        evaluation_start="locked-start", evaluation_bars=2,
        evaluation_start_ts=30,
    )
    assert evidence["state"] == AVAILABLE
    assert calls == [2, 1, 3]
    assert all(call["evaluation_start"] == "locked-start"
               and call["evaluation_bars"] == 2 for call in validation_calls)
    assert evidence["evaluation_contract"]["document"]["evaluation_window"] == {
        "use": "locked_validation_challenge", "start_ts": 30, "bars": 2,
    }
    replayed = _reconstruct(copy.deepcopy(evidence))
    scores = sorted(row["oos_score"] for row in replayed["method"]["candidate_population"])
    assert scores == [-125, 200, 250]
    assert len(replayed["population"]) == 3


def test_evaluation_stops_before_work_without_enabled_v2_request_or_parent_identity():
    calls = []
    evaluator = lambda point: calls.append(point)

    def evaluate(prepared, *, candidate_evaluator=evaluator, parent_identity=None):
        return evaluate_parameter_neighborhood(
            prepared, candidate_evaluator=candidate_evaluator,
            candles=object(), instrument=object(), dataset_bars=5,
            parent_fold_signature=((0, 10, 20, 5),),
            parent_identity=_parent_identity() if parent_identity is None
            else parent_identity,
            n_folds=2, capital=1.0, min_trades=1,
            min_positive_fold_frac=0.0, slippage_bps=0.0,
            slippage_multiplier=0.0, seed=0,
        )

    assert evaluate(None) == {
        "schema": "strategy-os-parameter-neighbourhood-evidence/1",
        "state": "NOT_REQUESTED",
    }
    disabled = prepare_parameter_neighborhood(
        parameter_neighborhood_recipe_binding({
            "enabled": False, "axes": [], "maximum_score_drop_paise": 0,
            "minimum_stable_fraction_ppm": 0,
        }), baseline_document=_document(), registry=_registry(),
    )
    assert evaluate(disabled) == {
        "schema": "strategy-os-parameter-neighbourhood-evidence/1",
        "state": "DISABLED",
    }
    assert evaluate(_prepared(), candidate_evaluator=None) == {
        "schema": "strategy-os-parameter-neighbourhood-evidence/1",
        "state": "UNAVAILABLE",
        "reason_code": "LEGACY_V1_GRAPH_UNSUPPORTED",
    }
    with pytest.raises(ParameterNeighborhoodIntegrationRejected, match="parent ExperimentSpec"):
        evaluate(_prepared(), parent_identity={})
    assert calls == []


def test_parent_spec_data_instrument_and_charge_changes_readdress_every_candidate(
    monkeypatch,
):
    monkeypatch.setattr(
        "research.pipeline.validate.validate", lambda *_args, **_kw: _validation(1.0),
    )

    def evaluate(recipe, spec_id="a" * 32):
        return evaluate_parameter_neighborhood(
            _prepared(), candidate_evaluator=lambda point: CandidateRuntime(
                strategy=object(), candidate_graph_address=content_address({
                    "point": [row["normalized_value"] for row in point],
                }), lineage={},
            ), candles=object(), instrument=object(), dataset_bars=5,
            parent_fold_signature=((0, 10, 20, 5),),
            parent_identity=_parent_identity(recipe, spec_id),
            n_folds=2, capital=1.0, min_trades=1,
            min_positive_fold_frac=0.0, slippage_bps=0.0,
            slippage_multiplier=0.0, seed=0,
        )

    baseline_recipe = _parent_recipe()
    variants = []
    changed_data = copy.deepcopy(baseline_recipe)
    changed_data["datasets"]["SAME"]["content_hash"] = content_address({"dataset": 2})
    variants.append((changed_data, "a" * 32))
    changed_instrument = copy.deepcopy(baseline_recipe)
    changed_instrument["datasets"] = {"OTHER": {
        **changed_instrument["datasets"]["SAME"], "instrument_key": "OTHER",
    }}
    variants.append((changed_instrument, "a" * 32))
    changed_charge = copy.deepcopy(baseline_recipe)
    changed_charge["resolved_charge_schedule"]["address"] = content_address({"charges": 2})
    variants.append((changed_charge, "a" * 32))
    variants.append((copy.deepcopy(baseline_recipe), "b" * 32))

    baseline = evaluate(baseline_recipe)
    baseline_candidates = [row["candidate_address"] for row in baseline["population"]]
    for recipe, spec_id in variants:
        changed = evaluate(recipe, spec_id)
        assert changed["evaluation_contract"]["address"] \
            != baseline["evaluation_contract"]["address"]
        assert [row["candidate_address"] for row in changed["population"]] \
            != baseline_candidates


def test_candidate_cancellation_propagates_before_later_points(monkeypatch):
    calls = []

    def cancelled(point):
        calls.append(point)
        from research.orchestrator.v2_operation import V2OperationRefusal
        raise V2OperationRefusal("V2_OPERATION_CANCELLED")

    with pytest.raises(CandidateEvaluationCancelled, match="V2_OPERATION_CANCELLED"):
        evaluate_parameter_neighborhood(
            _prepared(), candidate_evaluator=cancelled,
            candles=object(), instrument=object(), dataset_bars=5,
            parent_fold_signature=((0, 10, 20, 5),),
            parent_identity=_parent_identity(), n_folds=2, capital=1.0,
            min_trades=1, min_positive_fold_frac=0.0, slippage_bps=0.0,
            slippage_multiplier=0.0, seed=0,
        )
    assert len(calls) == 1


def test_candidate_cancellation_stops_parent_work_and_persists_no_completed_fact(monkeypatch):
    import research.orchestrator.run as run_module
    from research.domain.base import init_research_db, make_engine, make_sessionmaker
    from research.domain.models import ExperimentRun
    from research.evidence import decode_terminal_evidence

    engine = make_engine(":memory:")
    init_research_db(engine)
    Session = make_sessionmaker(engine)
    dataset = SimpleNamespace(
        instrument_key="SAME", interval="day", requested_days=1,
        bar_count=5,
        start_ts=int(dt.datetime(2026, 1, 1, 9, 15).timestamp()),
        end_ts=int(dt.datetime(2026, 1, 5, 9, 15).timestamp()),
        content_hash=content_address({"dataset": "cancel"}),
        candles=[SimpleNamespace(
            ts=dt.datetime(2026, 1, day, 9, 15),
            open=100.0, high=101.0, low=99.0, close=100.0,
        )
                 for day in range(1, 6)],
    )
    strategy = SimpleNamespace(key="probe", default_params={})
    parent_validation = _validation(1.0)
    monkeypatch.setattr(
        run_module, "_evaluate_datasets",
        lambda *_args, **_kwargs: run_module._EvaluationState(
            qualified=["SAME"], total_bars=5,
            locked_validation=parent_validation,
        ),
    )
    try:
        with Session() as session:
            with pytest.raises(CandidateEvaluationCancelled):
                run_module.run_experiment(
                    session, owner_id="owner", program_name="cancel",
                    hypothesis_statement="cancel", strategy=strategy,
                    datasets=[(SimpleNamespace(key="SAME"), dataset)], params={},
                    graph_provenance={"graph": {
                        "content_address": content_address({"graph": "cancel"}),
                    }}, parameter_neighborhood=_prepared(),
                    parameter_neighborhood_evaluator=lambda _point: (
                        _ for _ in ()
                    ).throw(CandidateEvaluationCancelled("claim lost")),
                    n_folds=2, min_trades=1, min_positive_fold_frac=0.0,
                )
            runs = session.query(ExperimentRun).all()
            assert len(runs) == 1 and runs[0].status == "failed"
            terminal = decode_terminal_evidence(runs[0].checkpoint_json)
            assert terminal["run"]["status"] == "failed"
            assert terminal["results"]["failure"]["stage"] == "parameter_neighborhood"
            assert terminal["results"]["failure"]["code"] \
                == "RESEARCH_PARAMETER_NEIGHBORHOOD_FAILED"
            assert "parameter_neighborhood" not in terminal["results"]
    finally:
        engine.dispose()


def test_rejected_parent_does_not_open_parameter_holdout(
        research_session, inst_factory, candles_factory):
    from research.data.store import StaticDataSource, materialize
    from research.domain.models import ExperimentRun
    from research.evaluation import kernels
    from research.evidence import decode_terminal_evidence
    from research.orchestrator.run import run_experiment

    instrument = inst_factory("REJECTED")
    dataset = materialize(
        StaticDataSource({("REJECTED", "day"): candles_factory(20)}),
        instrument, "day",
    )
    calls = []
    report = run_experiment(
        research_session, owner_id="rejected-parent", program_name="Rejected",
        hypothesis_statement="Development gate fails",
        strategy=kernels.get_strategy("trend_impulse_v3"),
        datasets=[(instrument, dataset)], min_trades=10_000, n_folds=2,
        parameter_neighborhood=_prepared(),
        parameter_neighborhood_evaluator=lambda point: calls.append(point),
    )
    run = research_session.get(ExperimentRun, report["run_id"])
    evidence = decode_terminal_evidence(run.checkpoint_json)
    assert calls == []
    assert evidence["results"]["parameter_neighborhood"] == {
        "schema": "strategy-os-parameter-neighbourhood-evidence/1",
        "state": "UNAVAILABLE", "reason_code": "PARENT_NOT_QUALIFIED",
    }


def test_zero_bar_holdout_refuses_before_candidate_evaluation():
    calls = []
    evidence = evaluate_parameter_neighborhood(
        _prepared(), candidate_evaluator=lambda point: calls.append(point),
        candles=object(), instrument=object(), dataset_bars=1,
        parent_fold_signature=((0, 10, 20, 1),),
        parent_identity=_parent_identity(), n_folds=2, capital=1.0,
        min_trades=1, min_positive_fold_frac=0.0, slippage_bps=0.0,
        slippage_multiplier=0.0, seed=0, evaluation_bars=0,
    )
    assert calls == []
    assert evidence["state"] == "UNAVAILABLE"
    assert evidence["reason_code"] == "INSUFFICIENT_HOLDOUT"


def test_combined_work_refuses_before_any_candidate_evaluation():
    calls = []
    evidence = evaluate_parameter_neighborhood(
        _prepared(), candidate_evaluator=lambda point: calls.append(point),
        candles=object(), instrument=object(), dataset_bars=666_667,
        parent_fold_signature=((0, 10, 20, 5),), n_folds=2,
        parent_identity=_parent_identity(),
        capital=1.0, min_trades=1, min_positive_fold_frac=0.0,
        slippage_bps=0.0, slippage_multiplier=0.0, seed=0,
    )
    assert evidence == {
        "schema": "strategy-os-parameter-neighbourhood-evidence/1",
        "state": "UNAVAILABLE",
        "reason_code": "PARAMETER_NEIGHBORHOOD_RESOURCE_REFUSED",
    }
    assert calls == []


@pytest.mark.parametrize(("bars", "available"), [
    (999_999, True), (1_000_000, True), (1_000_001, False),
])
def test_two_candidate_work_boundary_below_at_and_above(monkeypatch, bars, available):
    prepared = _prepared(_settings(axes=[{
        **_settings()["axes"][0], "minimum": "2", "maximum": "3",
    }]))
    calls = []
    monkeypatch.setattr(
        "research.pipeline.validate.validate", lambda *_args, **_kw: _validation(1.0),
    )
    evidence = evaluate_parameter_neighborhood(
        prepared, candidate_evaluator=lambda point: calls.append(point) or CandidateRuntime(
            strategy=object(), candidate_graph_address=content_address({"p": str(point)}),
            lineage={},
        ), candles=object(), instrument=object(), dataset_bars=bars,
        parent_fold_signature=((0, 10, 20, 5),),
        parent_identity=_parent_identity(), n_folds=2, capital=1.0,
        min_trades=1, min_positive_fold_frac=0.0, slippage_bps=0.0,
        slippage_multiplier=0.0, seed=0,
    )
    assert (evidence["state"] == AVAILABLE) is available
    assert len(calls) == (2 if available else 0)


def test_changed_fold_refuses_the_whole_surface(monkeypatch):
    monkeypatch.setattr(
        "research.pipeline.validate.validate",
        lambda *_args, **_kw: _validation(1.0, changed_fold=True),
    )
    evidence = evaluate_parameter_neighborhood(
        _prepared(), candidate_evaluator=lambda point: CandidateRuntime(
            strategy=object(), candidate_graph_address=content_address({"p": str(point)}),
            lineage={},
        ), candles=object(), instrument=object(), dataset_bars=5,
        parent_fold_signature=((0, 10, 20, 5),), n_folds=2,
        parent_identity=_parent_identity(),
        capital=1.0, min_trades=1, min_positive_fold_frac=0.0,
        slippage_bps=0.0, slippage_multiplier=0.0, seed=0,
    )
    assert evidence["state"] == "UNAVAILABLE"
    assert evidence["reason_code"] == "PARAMETER_NEIGHBORHOOD_CANDIDATE_REFUSED"


def test_semantic_reconstruction_refuses_method_or_population_tamper(monkeypatch):
    monkeypatch.setattr(
        "research.pipeline.validate.validate",
        lambda *_args, **_kw: _validation(1.0),
    )
    evidence = evaluate_parameter_neighborhood(
        _prepared(), candidate_evaluator=lambda point: CandidateRuntime(
            strategy=object(), candidate_graph_address=content_address({"p": str(point)}),
            lineage={},
        ), candles=object(), instrument=object(), dataset_bars=5,
        parent_fold_signature=((0, 10, 20, 5),), n_folds=2,
        parent_identity=_parent_identity(),
        capital=1.0, min_trades=1, min_positive_fold_frac=0.0,
        slippage_bps=0.0, slippage_multiplier=0.0, seed=0,
    )
    forged = copy.deepcopy(evidence)
    forged["method"]["address"] = content_address({"forged": True})
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        _reconstruct(forged)
    missing = copy.deepcopy(evidence)
    missing["population"].pop()
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        _reconstruct(missing)


def test_request_and_terminal_state_matrix_is_closed():
    disabled = parameter_neighborhood_recipe_binding({
        "enabled": False, "axes": [], "maximum_score_drop_paise": 0,
        "minimum_stable_fraction_ppm": 0,
    })
    enabled = _prepared().recipe_binding
    states = {
        "NOT_REQUESTED": {"schema": "strategy-os-parameter-neighbourhood-evidence/1",
                          "state": "NOT_REQUESTED"},
        "DISABLED": {"schema": "strategy-os-parameter-neighbourhood-evidence/1",
                     "state": "DISABLED"},
        "UNAVAILABLE": {"schema": "strategy-os-parameter-neighbourhood-evidence/1",
                        "state": "UNAVAILABLE",
                        "reason_code": "PARAMETER_NEIGHBORHOOD_METHOD_REFUSED"},
    }
    valid = {(None, "NOT_REQUESTED"), ("disabled", "DISABLED"),
             ("enabled", "UNAVAILABLE")}
    bindings = {None: None, "disabled": disabled, "enabled": enabled}
    for request, binding in bindings.items():
        for state, stored in states.items():
            call = lambda: reconstruct_parameter_neighborhood_projection(
                stored, recipe_binding=binding, parent_spec_id=None,
                parent_recipe=None,
            )
            if (request, state) in valid:
                assert call()["state"] == state
            else:
                with pytest.raises(ParameterNeighborhoodIntegrationRejected):
                    call()


def test_available_replay_binds_request_parent_and_evaluation_document(monkeypatch):
    monkeypatch.setattr(
        "research.pipeline.validate.validate", lambda *_args, **_kw: _validation(1.0),
    )
    evidence = evaluate_parameter_neighborhood(
        _prepared(), candidate_evaluator=lambda point: CandidateRuntime(
            strategy=object(), candidate_graph_address=content_address({"p": str(point)}),
            lineage={},
        ), candles=object(), instrument=object(), dataset_bars=5,
        parent_fold_signature=((0, 10, 20, 5),),
        parent_identity=_parent_identity(), n_folds=2, capital=1.0,
        min_trades=1, min_positive_fold_frac=0.0, slippage_bps=0.0,
        slippage_multiplier=0.0, seed=0,
    )
    stale_request = parameter_neighborhood_recipe_binding(
        _settings(maximum_score_drop_paise=101)
    )
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        _reconstruct(copy.deepcopy(evidence), recipe_binding=stale_request)
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        _reconstruct(copy.deepcopy(evidence), spec_id="b" * 32)
    changed_recipe = _parent_recipe()
    changed_recipe["datasets"]["SAME"]["content_hash"] = content_address({"changed": True})
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        _reconstruct(copy.deepcopy(evidence), recipe=changed_recipe)
    readdressed = copy.deepcopy(evidence)
    readdressed["evaluation_contract"]["document"]["seed"] = 1
    readdressed["evaluation_contract"]["address"] = content_address(
        readdressed["evaluation_contract"]["document"]
    )
    with pytest.raises(ParameterNeighborhoodIntegrationRejected):
        _reconstruct(readdressed)


def test_complete_four_axis_surface_has_all_81_points_once(monkeypatch):
    axes = [{
        "node_id": f"node{index}", "parameter_id": "window",
        "step": "1", "minimum": "1", "maximum": "3",
    } for index in range(4)]
    settings = _settings(axes=axes)
    document = {"nodes": [{
        "node_id": f"node{index}",
        "component": {"component_id": f"analytical.probe{index}",
                      "component_version": 2},
        "parameters": {"window": 2},
    } for index in range(4)]}
    registry = SimpleNamespace(v2_components={
        (f"analytical.probe{index}", 2): {"parameters": {"window": {
            "type": "int", "enum": None,
            "domain": {"minimum": 1, "maximum": 3},
        }}} for index in range(4)
    })
    prepared = prepare_parameter_neighborhood(
        parameter_neighborhood_recipe_binding(settings),
        baseline_document=document, registry=registry,
    )
    calls = []
    monkeypatch.setattr(
        "research.pipeline.validate.validate", lambda *_args, **_kw: _validation(1.0),
    )

    def evaluator(point):
        calls.append(tuple(row["value"] for row in point))
        return CandidateRuntime(
            strategy=object(), candidate_graph_address=content_address({"point": calls[-1]}),
            lineage={},
        )

    evidence = evaluate_parameter_neighborhood(
        prepared, candidate_evaluator=evaluator, candles=object(), instrument=object(),
        dataset_bars=24_691, parent_fold_signature=((0, 10, 20, 5),),
        parent_identity=_parent_identity(),
        n_folds=2, capital=1.0, min_trades=1,
        min_positive_fold_frac=0.0, slippage_bps=0.0,
        slippage_multiplier=0.0, seed=0,
    )
    assert evidence["state"] == AVAILABLE
    assert len(calls) == len(set(calls)) == 81
    assert 81 * 24_691 == 1_999_971


def test_available_evidence_semantically_reconstructs_in_fresh_process(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(
        "research.pipeline.validate.validate", lambda *_args, **_kw: _validation(1.0),
    )
    evidence = evaluate_parameter_neighborhood(
        _prepared(), candidate_evaluator=lambda point: CandidateRuntime(
            strategy=object(), candidate_graph_address=content_address({"p": str(point)}),
            lineage={},
        ), candles=object(), instrument=object(), dataset_bars=5,
        parent_fold_signature=((0, 10, 20, 5),), n_folds=2,
        parent_identity=_parent_identity(),
        capital=1.0, min_trades=1, min_positive_fold_frac=0.0,
        slippage_bps=0.0, slippage_multiplier=0.0, seed=0,
    )
    payload = tmp_path / "parameter-evidence.json"
    payload.write_text(json.dumps({
        "evidence": evidence, "recipe_binding": _prepared().recipe_binding,
        "parent_spec_id": "a" * 32, "parent_recipe": _parent_recipe(),
    }), encoding="utf-8")
    completed = subprocess.run([
        sys.executable, "-c",
        "import json,sys; from research.robustness.parameter_integration import "
        "reconstruct_parameter_neighborhood_projection as r; "
        "p=json.load(open(sys.argv[1], encoding='utf-8')); "
        "assert r(p['evidence'], recipe_binding=p['recipe_binding'], "
        "parent_spec_id=p['parent_spec_id'], parent_recipe=p['parent_recipe'])['state']=='AVAILABLE'",
        str(payload),
    ], check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_terminal_overflow_replaces_only_parameter_distribution(monkeypatch):
    from research.evidence import EvidenceRejected
    import research.robustness.parameter_integration as integration
    import research.robustness.integration as stationary

    calls = []

    def encode(value):
        calls.append(copy.deepcopy(value))
        if len(calls) == 1:
            raise EvidenceRejected("terminal evidence exceeds the persisted size limit")
        return "encoded"

    monkeypatch.setattr(integration, "encode_terminal_evidence", encode)
    monkeypatch.setattr(stationary, "encode_terminal_evidence", encode)
    evidence = {"results": {
        "base": {"decision": "archive"},
        "robustness": {"state": "UNAVAILABLE"},
        "parameter_neighborhood": {
            "schema": "strategy-os-parameter-neighbourhood-evidence/1",
            "state": "AVAILABLE", "distribution": "large",
        },
    }}
    assert encode_terminal_evidence_with_parameter_fallback(evidence) == "encoded"
    assert calls[-1]["results"]["base"] == evidence["results"]["base"]
    assert calls[-1]["results"]["robustness"] == evidence["results"]["robustness"]
    assert calls[-1]["results"]["parameter_neighborhood"]["reason_code"] \
        == "TERMINAL_EVIDENCE_SIZE_REFUSED"
