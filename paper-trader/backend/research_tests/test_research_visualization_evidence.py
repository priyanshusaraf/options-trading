from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from app.backtest.metrics import BTTrade, compute_metrics
from app.core.research_visualization_read import (
    VisualizationRejected,
    build_visualization_projection,
    page_projection,
)
from app.ir.hashing import content_address


def address(digit):
    return "sha256:" + digit * 64


def recipe():
    return {
        "params": {"length": 20}, "seed": 7, "versions": ["q1", "none", "v1", "s1"],
        "cost_assumptions": {"capital": 100_000.0, "slippage_bps": 5.0,
                             "slippage_multiplier": 2.0,
                             "sizing_model": "one_lot_or_cash_budget_v1"},
        "resolved_charge_schedule": {"id": "corrected", "address": address("a")},
        "graph_provenance": {
            "graph": {"project_id": "project.a", "identifier": "strategy.a", "version": 2,
                      "content_address": address("b")},
            "canonical_dataset_bindings": {"schema": "canonical-dataset-bindings/1",
                                             "bindings": {"one": {"manifest_address": address("c")}}},
        },
    }


def trade(net=90.0, charges=10.0):
    return BTTrade("LONG", 1_700_000_000, 100.0, 1_700_000_900, 101.0, 100,
                   net + charges, charges, net, "STRATEGY_EXIT", 3, mae_pct=1.25,
                   notional=10_000.0)


def test_projection_uses_net_equity_real_charges_and_explicit_slippage_stress():
    trades = [trade()]
    metrics = compute_metrics(trades, 100_000.0)
    fold = SimpleNamespace(fold_index=0, start_ts=1_700_000_000, end_ts=1_700_001_000,
                           n_bars=20, trades=trades, metrics=metrics)
    projection = build_visualization_projection(
        recipe=recipe(), run_id=4, spec_id="d" * 32, metrics=metrics,
        trades=trades, folds=[fold], gate_results={
            "slippage_stress_2x": {"passed": True, "value": 72.5},
        },
    )
    assert projection["state"] == "AVAILABLE"
    assert projection["summary"]["gross_pnl"] == 100.0
    assert projection["summary"]["net_pnl"] == 90.0
    assert projection["summary"]["final_equity"] == 10_090.0
    assert projection["costs"]["charges_total"] == 10.0
    assert projection["costs"]["breakdown"]["state"] == "UNAVAILABLE"
    assert projection["costs"]["slippage"] == {
        "state": "STRESS_SCENARIO", "bps": 5.0, "multiplier": 2.0,
        "mean_stressed_net": 72.5, "passed": True,
    }
    assert projection["folds"][0]["role"] == "OOS"
    assert projection["folds"][0]["selected_parameter_address"] \
        == content_address(recipe()["params"])
    page = page_projection(projection, trade_after=0, trade_limit=100,
                           terminal_evidence_address=address("e"))
    assert page["trade_page"]["items"][0]["charges"] == 10.0
    assert page["identity"]["terminal_evidence_address"] == address("e")


def test_zero_trade_state_is_real_zero_and_tampering_fails_closed():
    projection = build_visualization_projection(
        recipe=recipe(), run_id=5, spec_id="f" * 32,
        metrics=compute_metrics([], 100_000.0), trades=[], folds=[], gate_results={},
    )
    assert projection["summary"]["trades"] == 0
    assert projection["summary"]["profit_factor"] is None
    assert projection["costs"]["charges_total"] == 0.0
    assert projection["series"]["net_equity"]["points"] == [{"time": 0, "value": 100_000.0}]
    corrupted = copy.deepcopy(projection)
    corrupted["summary"]["net_pnl"] = 999.0
    with pytest.raises(VisualizationRejected, match="address"):
        page_projection(corrupted, trade_after=0, trade_limit=10,
                        terminal_evidence_address=address("e"))


@pytest.mark.parametrize("mutation", ["gross_for_net", "omitted_charges", "slippage_label", "event_pair"])
def test_semantic_oracle_kills_readdressed_producer_mutations(mutation):
    trades = [trade()]
    metrics = compute_metrics(trades, 100_000.0)
    fold = SimpleNamespace(fold_index=0, start_ts=1_700_000_000, end_ts=1_700_001_000,
                           n_bars=20, trades=trades, metrics=metrics)
    projection = build_visualization_projection(
        recipe=recipe(), run_id=6, spec_id="6" * 32, metrics=metrics,
        trades=trades, folds=[fold], gate_results={
            "slippage_stress_2x": {"passed": True, "value": 72.5},
        },
    )
    if mutation == "gross_for_net":
        projection["summary"]["net_pnl"] = projection["summary"]["gross_pnl"]
    elif mutation == "omitted_charges":
        projection["costs"]["charges_total"] = 0.0
    elif mutation == "slippage_label":
        projection["costs"]["slippage"]["state"] = "BASE_COST"
    else:
        projection["series"]["trade_events"] = projection["series"]["trade_events"][:1]
    projection.pop("visualization_address")
    projection["visualization_address"] = content_address(projection)
    with pytest.raises(VisualizationRejected):
        page_projection(projection, trade_after=0, trade_limit=10,
                        terminal_evidence_address=address("e"))
