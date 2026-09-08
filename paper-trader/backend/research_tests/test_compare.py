import copy

import pytest

from app.ir.hashing import content_address
from research.compare import compare_experiment_evidence


BASE = {
    "spec_id": "spec-a",
    "run": {"id": 1, "status": "completed", "decision": "archive"},
    "provenance": {
        "program": "Published graphs",
        "hypothesis": "Graph has edge",
        "git_commit": "aaaaaaa",
        "strategy": "ir.strategy.example.abc",
        "params": {},
        "seed": 7,
        "versions": ["q1", "none", "v1", "s1"],
        "graph_provenance": {
            "graph": {
                "project_id": "project.alpha",
                "identifier": "strategy.example",
                "version": 1,
                "content_address": "sha256:" + "a" * 64,
            },
            "resolution": {
                "component_versions": [["component.a", 1]],
                "node_identities": {"n_a": "sha256:" + "b" * 64},
            },
            "dataset_bindings": {
                "AAA": {"data_digest": "sha256:" + "c" * 64,
                        "binding": "sha256:" + "d" * 64}
            },
        },
        "datasets": {
            "AAA": {"instrument_key": "AAA", "interval": "day",
                    "requested_days": 30, "bar_count": 300,
                    "start_ts": 1, "end_ts": 300, "content_hash": "data-a"}
        },
        "cost_assumptions": {"capital": 50_000.0, "slippage_bps": 5.0,
                             "slippage_multiplier": 2.0,
                             "charge_model": "zerodha_charges_v1",
                             "sizing_model": "one_lot_or_cash_budget_v1"},
        "gates": {"min_oos_trades": 20, "n_folds": 4,
                  "min_positive_fold_fraction": 0.6,
                  "optimize_search": False, "pbo_threshold": 0.3,
                  "sibling_trials": 1},
    },
    "results": {
        "qualified": [], "validated": [],
        "rejected": [{"instrument": "AAA", "reason": "insufficient trades"}],
        "instruments": [{
            "instrument": "AAA",
            "qualification": {"qualified": False, "trades": 2,
                              "reason": "insufficient trades"},
            "validation": None,
            "scorecard": None,
        }],
        "promotion": None,
        "breadth": None,
        "total_bars": 300,
        "regimes": {},
        "explanation": {"strategy_key": "ir.strategy.example.abc"},
    },
}


def _changed(path, value):
    evidence = copy.deepcopy(BASE)
    target = evidence
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    evidence["spec_id"] = "spec-b"
    evidence["run"]["id"] = 2
    return evidence


def _visualization(run_id: int, spec_id: str, *, seed: int = 7):
    projection = {
        "schema": "strategy-os-backtest-visualization/1",
        "state": "AVAILABLE",
        "identity": {"run_id": run_id, "spec_id": spec_id, "seed": seed},
        "summary": {
            "initial_capital": 50_000.0,
            "final_equity": 50_000.0,
            "net_pnl": 0.0,
            "gross_pnl": 0.0,
        },
        "series": {
            "net_equity": {"points": [{"time": 0, "value": 50_000.0}]},
            "trade_events": [],
        },
        "trades": {"items": [], "original_count": 0, "detail_reason": None},
        "costs": {
            "charges_total": 0.0,
            "slippage": {"state": "STRESS_SCENARIO"},
        },
        "folds": [],
        "provenance": {},
    }
    projection["visualization_address"] = content_address(projection)
    return projection


def test_identical_verified_evidence_is_equivalent():
    result = compare_experiment_evidence(BASE, copy.deepcopy(BASE))
    assert result == {
        "equivalent": True,
        "incomparable": [],
        "differences": [],
    }


@pytest.mark.parametrize(
    "path,value,dimension",
    [
        (("provenance", "graph_provenance", "graph", "version"), 2, "graph"),
        (("provenance", "graph_provenance", "resolution", "component_versions"),
         [["component.a", 2]], "resolution"),
        (("provenance", "params"), {"length": 20}, "parameters"),
        (("provenance", "git_commit"), "bbbbbbb", "build"),
        (("results", "run_marker"), "changed", "results"),
    ],
)
def test_exact_semantic_dimensions_are_reported(path, value, dimension):
    result = compare_experiment_evidence(BASE, _changed(path, value))
    assert result["equivalent"] is False
    assert result["incomparable"] == []
    assert any(item["dimension"] == dimension for item in result["differences"])


@pytest.mark.parametrize(
    "path,value,reason,dimension",
    [
        (("provenance", "datasets", "AAA", "content_hash"), "data-b",
         "DATASET_IDENTITY_CHANGED", "datasets"),
        (("provenance", "cost_assumptions", "slippage_bps"), 8.0,
         "COST_ASSUMPTIONS_CHANGED", "costs"),
        (("provenance", "gates", "n_folds"), 6,
         "GATE_CONTRACT_CHANGED", "gates"),
    ],
)
def test_data_cost_or_gate_changes_are_explicitly_incomparable(
        path, value, reason, dimension):
    result = compare_experiment_evidence(BASE, _changed(path, value))
    assert reason in result["incomparable"]
    assert any(item["dimension"] == dimension for item in result["differences"])


def test_run_and_spec_ids_are_context_not_false_semantic_differences():
    right = copy.deepcopy(BASE)
    right["spec_id"] = "same-recipe-other-id"
    right["run"]["id"] = 99
    assert compare_experiment_evidence(BASE, right)["equivalent"] is True


def test_nested_visualization_run_identity_is_context_but_results_remain_semantic():
    left = copy.deepcopy(BASE)
    right = copy.deepcopy(BASE)
    left["results"]["visualization"] = _visualization(1, "spec-a")
    right["results"]["visualization"] = _visualization(2, "spec-b")
    right["run"]["id"] = 2

    assert compare_experiment_evidence(left, right) == {
        "equivalent": True,
        "incomparable": [],
        "differences": [],
    }

    right["results"]["visualization"] = _visualization(2, "spec-b", seed=8)
    changed = compare_experiment_evidence(left, right)
    assert changed["equivalent"] is False
    assert changed["differences"] == [{
        "dimension": "results",
        "path": ["evidence", "visualization", "identity", "seed"],
        "left": 7,
        "right": 8,
    }]


def test_visualization_address_and_semantics_are_verified_before_normalization():
    left = copy.deepcopy(BASE)
    right = copy.deepcopy(BASE)
    left["results"]["visualization"] = _visualization(1, "spec-a")
    right["results"]["visualization"] = _visualization(2, "spec-b")

    right["results"]["visualization"]["visualization_address"] = (
        "sha256:" + "f" * 64
    )
    with pytest.raises(ValueError, match="verified terminal evidence"):
        compare_experiment_evidence(left, right)

    right["results"]["visualization"] = _visualization(2, "spec-b")
    right["results"]["visualization"]["summary"]["final_equity"] = 49_999.0
    body = copy.deepcopy(right["results"]["visualization"])
    del body["visualization_address"]
    right["results"]["visualization"]["visualization_address"] = content_address(body)
    with pytest.raises(ValueError, match="verified terminal evidence"):
        compare_experiment_evidence(left, right)


def test_unavailable_visualization_is_closed_and_never_context_normalized():
    left = copy.deepcopy(BASE)
    right = copy.deepcopy(BASE)
    right["results"]["visualization"] = None
    with pytest.raises(ValueError, match="verified terminal evidence"):
        compare_experiment_evidence(left, right)

    left["results"]["visualization"] = {
        "schema": "strategy-os-backtest-visualization/1",
        "state": "UNAVAILABLE",
        "reason_code": "TERMINAL_VISUALIZATION_NOT_PRODUCED",
    }
    right["results"]["visualization"] = copy.deepcopy(
        left["results"]["visualization"]
    )
    assert compare_experiment_evidence(left, right)["equivalent"] is True

    right["results"]["visualization"].update({
        "identity": {"run_id": 2, "spec_id": "spec-b"},
        "visualization_address": "sha256:" + "f" * 64,
    })
    with pytest.raises(ValueError, match="verified terminal evidence"):
        compare_experiment_evidence(left, right)

    right["results"]["visualization"] = {
        "schema": "strategy-os-backtest-visualization/1",
        "state": "UNAVAILABLE",
        "reason_code": "MULTI_INSTRUMENT_VISUALIZATION_UNAVAILABLE",
    }
    changed = compare_experiment_evidence(left, right)
    assert changed["equivalent"] is False
    assert changed["differences"] == [{
        "dimension": "results",
        "path": ["evidence", "visualization", "reason_code"],
        "left": "TERMINAL_VISUALIZATION_NOT_PRODUCED",
        "right": "MULTI_INSTRUMENT_VISUALIZATION_UNAVAILABLE",
    }]


def test_missing_value_is_not_conflated_with_explicit_null():
    right = copy.deepcopy(BASE)
    right["results"]["new_metric"] = None

    result = compare_experiment_evidence(BASE, right)

    assert result["differences"][-1] == {
        "dimension": "results",
        "path": ["evidence", "new_metric"],
        "left": {"state": "missing"},
        "right": None,
    }


@pytest.mark.parametrize("bad", [None, {}, {"provenance": {}}, {"results": {}}])
def test_incomplete_evidence_is_rejected_instead_of_compared(bad):
    with pytest.raises(ValueError, match="verified terminal evidence"):
        compare_experiment_evidence(BASE, bad)
