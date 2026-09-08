"""Bounded immutable visualization projection for verified terminal research evidence.

This module is a projection/read seam only.  It never runs a strategy, loads market
data, or changes research identity.  The orchestrator passes the exact metrics,
trades, folds, recipe, and gate results that produced its terminal decision.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.ir.hashing import content_address


SCHEMA = "strategy-os-backtest-visualization/1"
CALCULATION_SCHEMA = "strategy-os-net-equity-close-drawdown/1"
MAX_SERIES_POINTS = 2_000
MAX_TRADE_EVENTS = 10_000
# Preserve space for the rest of the terminal envelope under its 2 MB hard gate.
MAX_EMBEDDED_TRADE_BYTES = 1_100_000


class VisualizationRejected(Exception):
    """Persisted visualization bytes cannot be trusted."""


def _finite(value: Any, *, label: str) -> float:
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise VisualizationRejected(f"{label} must be finite")
    return number


def _round(value: Any, digits: int = 2) -> float:
    return round(_finite(value, label="numeric projection"), digits)


def _downsample(points: Sequence[dict[str, Any]], limit: int = MAX_SERIES_POINTS) -> list[dict[str, Any]]:
    """Stable first/last plus min/max buckets; never interpolates market facts."""
    rows = [dict(point) for point in points]
    if len(rows) <= limit:
        return rows
    interior = rows[1:-1]
    bucket_count = max(1, (limit - 2) // 2)
    selected: list[dict[str, Any]] = [rows[0]]
    for bucket in range(bucket_count):
        start = bucket * len(interior) // bucket_count
        end = (bucket + 1) * len(interior) // bucket_count
        segment = interior[start:end]
        if not segment:
            continue
        extrema = sorted(
            {min(range(len(segment)), key=lambda i: segment[i]["value"]),
             max(range(len(segment)), key=lambda i: segment[i]["value"])},
        )
        selected.extend(segment[index] for index in extrema)
    selected.append(rows[-1])
    return selected[:limit]


def _drawdown(points: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    peak: float | None = None
    out = []
    for point in points:
        value = _finite(point["value"], label="equity point")
        peak = value if peak is None else max(peak, value)
        absolute = max(0.0, peak - value)
        out.append({
            "time": int(point["time"]),
            "value": _round((absolute / peak * 100.0) if peak and peak > 0 else 0.0, 4),
            "absolute": _round(absolute),
        })
    return out


def _trade_item(trade: Any, cursor: int) -> dict[str, Any]:
    quantity = int(getattr(trade, "qty"))
    entry_price = _round(getattr(trade, "entry_price"))
    notional = entry_price * quantity
    net_pnl = _round(getattr(trade, "net_pnl"))
    return {
        "cursor": cursor,
        "direction": str(getattr(trade, "direction")),
        "entry_time": int(getattr(trade, "entry_time")),
        "entry_price": entry_price,
        "exit_time": int(getattr(trade, "exit_time")),
        "exit_price": _round(getattr(trade, "exit_price")),
        "quantity": quantity,
        "gross_pnl": _round(getattr(trade, "gross_pnl")),
        "charges": _round(getattr(trade, "charges")),
        "net_pnl": net_pnl,
        "return_pct": _round((net_pnl / notional * 100.0) if notional else 0.0, 4),
        "mae_pct": _round(getattr(trade, "mae_pct", 0.0), 4),
        "bars_held": int(getattr(trade, "bars_held")),
        "exit_reason": str(getattr(trade, "reason")),
        "open_at_end": str(getattr(trade, "reason")) == "OPEN_AT_END",
    }


def _metric(metric: Any, name: str, default: Any = None) -> Any:
    return getattr(metric, name, default)


def _summary(metrics: Any, initial_capital: float) -> dict[str, Any]:
    curve = list(_metric(metrics, "equity_curve", ()))
    base = _finite(curve[0]["value"], label="initial equity") if curve else initial_capital
    net_pnl = _finite(_metric(metrics, "net_pnl", 0.0), label="net pnl")
    gross_pnl = _finite(_metric(metrics, "gross_pnl", 0.0), label="gross pnl")
    trades = int(_metric(metrics, "trades", 0))
    losses = int(_metric(metrics, "losses", 0))
    return {
        "initial_capital": _round(base),
        "final_equity": _round(base + net_pnl),
        "gross_pnl": _round(gross_pnl),
        "net_pnl": _round(net_pnl),
        "gross_return_pct": _round((gross_pnl / base * 100.0) if base else 0.0, 4),
        "net_return_pct": _round((net_pnl / base * 100.0) if base else 0.0, 4),
        "max_close_to_close_drawdown_abs": _round(_metric(metrics, "max_drawdown_abs", 0.0)),
        "max_close_to_close_drawdown_pct": _round(_metric(metrics, "max_drawdown_pct", 0.0), 4),
        "worst_mae_pct": _round(_metric(metrics, "worst_mae_pct", 0.0), 4),
        "trades": trades,
        "wins": int(_metric(metrics, "wins", 0)),
        "losses": losses,
        "win_rate": _round(_metric(metrics, "win_rate", 0.0), 4),
        "profit_factor": (None if _metric(metrics, "profit_factor") is None
                          else _round(_metric(metrics, "profit_factor"), 4)),
        "expectancy": _round(_metric(metrics, "expectancy", 0.0)),
        "avg_win": _round(_metric(metrics, "avg_win", 0.0)),
        "avg_loss": _round(_metric(metrics, "avg_loss", 0.0)),
        "cagr": None if _metric(metrics, "cagr") is None else _round(_metric(metrics, "cagr"), 4),
        "calmar": None if _metric(metrics, "calmar") is None else _round(_metric(metrics, "calmar"), 4),
        "sharpe": None if _metric(metrics, "sharpe") is None else _round(_metric(metrics, "sharpe"), 4),
        "max_consecutive_losses": int(_metric(metrics, "max_consec_losses", 0)),
        "time_underwater_pct": _round(_metric(metrics, "time_underwater_pct", 0.0), 4),
        "open_at_end": bool(_metric(metrics, "open_at_end", False)),
    }


def _fold_item(fold: Any, params_address: str, gate_results: Mapping[str, Any]) -> dict[str, Any]:
    metrics = getattr(fold, "metrics")
    return {
        "fold_index": int(getattr(fold, "fold_index")),
        "role": "OOS",
        "start_time": int(getattr(fold, "start_ts")),
        "end_time": int(getattr(fold, "end_ts")),
        "bars": int(getattr(fold, "n_bars")),
        "oos_trades": int(_metric(metrics, "trades", 0)),
        "oos_net_pnl": _round(_metric(metrics, "net_pnl", 0.0)),
        "oos_return_pct": _round(_metric(metrics, "return_pct", 0.0), 4),
        "oos_expectancy": _round(_metric(metrics, "expectancy", 0.0)),
        "oos_max_drawdown_pct": _round(_metric(metrics, "max_drawdown_pct", 0.0), 4),
        "selected_parameter_address": params_address,
        "gate_results": dict(gate_results),
    }


def unavailable(reason_code: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "state": "UNAVAILABLE", "reason_code": reason_code}


def verify_visualization_semantics(projection: Mapping[str, Any]) -> None:
    """Independent arithmetic/shape oracle, including after address recomputation."""
    if projection.get("state") != "AVAILABLE":
        return
    try:
        summary = projection["summary"]
        series = projection["series"]
        trades = projection["trades"]
        costs = projection["costs"]
        initial = _finite(summary["initial_capital"], label="initial capital")
        final = _finite(summary["final_equity"], label="final equity")
        net = _finite(summary["net_pnl"], label="summary net pnl")
        gross = _finite(summary["gross_pnl"], label="summary gross pnl")
        charges = _finite(costs["charges_total"], label="charges total")
        if abs((final - initial) - net) > 0.011:
            raise VisualizationRejected("final equity is not net pnl over initial capital")
        equity = series["net_equity"]["points"]
        if not isinstance(equity, list) or not equity or abs(_finite(equity[-1]["value"], label="last equity") - final) > 0.011:
            raise VisualizationRejected("net equity endpoint does not match summary")
        if costs["slippage"].get("state") != "STRESS_SCENARIO":
            raise VisualizationRejected("slippage must remain an explicit stress scenario")
        items = trades["items"]
        detail_reason = trades.get("detail_reason")
        if detail_reason is None:
            if int(trades["original_count"]) != len(items):
                raise VisualizationRejected("complete trade detail count does not match")
            trade_gross = sum(_finite(item["gross_pnl"], label="trade gross") for item in items)
            trade_charges = sum(_finite(item["charges"], label="trade charges") for item in items)
            trade_net = sum(_finite(item["net_pnl"], label="trade net") for item in items)
            rounding_tolerance = max(0.02, len(items) * 0.011)
            if any(abs(left - right) > rounding_tolerance for left, right in (
                (trade_gross, gross), (trade_charges, charges), (trade_net, net),
                (trade_gross - trade_charges, trade_net),
            )):
                raise VisualizationRejected("trade arithmetic does not reconstruct summary")
            events = series["trade_events"]
            if len(events) != len(items) * 2:
                raise VisualizationRejected("each trade must have one entry and one exit event")
            for item, entry, exit_event in zip(items, events[::2], events[1::2], strict=True):
                if (entry.get("event_kind"), exit_event.get("event_kind")) != ("ENTRY", "EXIT") \
                        or entry.get("cursor") != item["cursor"] or exit_event.get("cursor") != item["cursor"] \
                        or entry.get("time") != item["entry_time"] or exit_event.get("time") != item["exit_time"]:
                    raise VisualizationRejected("trade event pair does not reconstruct trade")
        elif detail_reason != "TRADE_DETAIL_UNAVAILABLE_OVER_LIMIT" or items:
            raise VisualizationRejected("trade detail refusal is inconsistent")
        for fold in projection["folds"]:
            if fold.get("role") != "OOS" or not isinstance(fold.get("selected_parameter_address"), str) \
                    or not isinstance(fold.get("gate_results"), dict):
                raise VisualizationRejected("fold evidence is incomplete")
    except VisualizationRejected:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise VisualizationRejected("visualization semantic fields are malformed") from exc


def build_visualization_projection(
    *, recipe: Mapping[str, Any], run_id: int, spec_id: str, metrics: Any,
    trades: Sequence[Any], folds: Sequence[Any], gate_results: Mapping[str, Any],
) -> dict[str, Any]:
    """Build from already-evaluated objects; callers must not rerun research."""
    graph = recipe.get("graph_provenance", {}).get("graph")
    canonical = recipe.get("graph_provenance", {}).get("canonical_dataset_bindings")
    if not isinstance(graph, dict) or not isinstance(canonical, dict):
        return unavailable("CANONICAL_GRAPH_OR_DATASET_BINDING_UNAVAILABLE")
    from app.ir.library import REGISTRY

    equity = list(_metric(metrics, "equity_curve", ()))
    initial = _finite(recipe["cost_assumptions"]["capital"], label="initial capital")
    if not equity:
        equity = [{"time": 0, "value": _round(initial)}]
    full_equity = [{"time": int(point["time"]), "value": _round(point["value"])} for point in equity]
    sampled_equity = _downsample(full_equity)
    sampled_drawdown = _downsample(_drawdown(full_equity))
    trade_rows = [_trade_item(trade, index + 1) for index, trade in enumerate(trades)]
    from app.ir.hashing import canonical_json
    detail_reason = None
    if len(trade_rows) > MAX_TRADE_EVENTS or len(canonical_json(trade_rows).encode()) > MAX_EMBEDDED_TRADE_BYTES:
        detail_reason = "TRADE_DETAIL_UNAVAILABLE_OVER_LIMIT"
        trade_rows = []
    params_address = content_address(recipe.get("params", {}))
    slippage = gate_results.get("slippage_stress_2x") or {}
    projection = {
        "schema": SCHEMA,
        "state": "AVAILABLE",
        "identity": {
            "run_id": run_id,
            "spec_id": spec_id,
            "graph_identifier": graph["identifier"],
            "graph_version": graph["version"],
            "graph_content_address": graph["content_address"],
            "component_registry_address": REGISTRY.registry_snapshot_address,
            "dataset_bindings": canonical,
            "charge_model": recipe["resolved_charge_schedule"],
            "sizing_model": recipe["cost_assumptions"]["sizing_model"],
            "seed": recipe["seed"],
            "calculation_schema": CALCULATION_SCHEMA,
        },
        "summary": _summary(metrics, initial),
        "series": {
            "net_equity": {"points": sampled_equity, "original_count": len(full_equity)},
            "drawdown": {"points": sampled_drawdown, "original_count": len(full_equity)},
            "benchmark": {"state": "UNAVAILABLE", "reason_code": "CANONICAL_BENCHMARK_NOT_COMPUTED"},
            "trade_events": [event for row in trade_rows for event in ({
                "cursor": row["cursor"], "event_kind": "ENTRY", "time": row["entry_time"],
                "price": row["entry_price"], "direction": row["direction"], "shape": "TRIANGLE",
            }, {
                "cursor": row["cursor"], "event_kind": "EXIT", "time": row["exit_time"],
                "price": row["exit_price"], "direction": row["direction"], "shape": "SQUARE",
            })],
        },
        "trades": {"items": trade_rows, "original_count": len(trades),
                   "detail_reason": detail_reason},
        "costs": {
            "charges_total": _round(_metric(metrics, "charges", 0.0)),
            "breakdown": {"state": "UNAVAILABLE", "reason_code": "ITEMIZED_CHARGE_LEGS_NOT_PERSISTED"},
            "slippage": {
                "state": "STRESS_SCENARIO",
                "bps": _round(recipe["cost_assumptions"]["slippage_bps"], 4),
                "multiplier": _round(recipe["cost_assumptions"]["slippage_multiplier"], 4),
                "mean_stressed_net": _round(slippage.get("value", 0.0)),
                "passed": bool(slippage.get("passed", False)),
            },
        },
        "folds": [_fold_item(fold, params_address, gate_results) for fold in folds],
        "provenance": {
            "graph": graph,
            "dataset_bindings": canonical,
            "resolved_charge_schedule": recipe["resolved_charge_schedule"],
            "versions": list(recipe["versions"]),
        },
    }
    verify_visualization_semantics(projection)
    projection["visualization_address"] = content_address(projection)
    return projection


def page_projection(projection: Mapping[str, Any], *, trade_after: int, trade_limit: int,
                    terminal_evidence_address: str) -> dict[str, Any]:
    """Strict enough read gate for the closed producer; corrupt shapes fail closed."""
    if not isinstance(projection, Mapping) or projection.get("schema") != SCHEMA:
        raise VisualizationRejected("visualization schema is absent")
    if projection.get("state") == "UNAVAILABLE":
        reason = projection.get("reason_code")
        if not isinstance(reason, str) or not reason:
            raise VisualizationRejected("unavailable visualization has no reason")
        return dict(projection)
    if projection.get("state") != "AVAILABLE":
        raise VisualizationRejected("visualization state is invalid")
    required = {"schema", "state", "identity", "summary", "series", "trades", "costs",
                "folds", "provenance", "visualization_address"}
    if set(projection) != required:
        raise VisualizationRejected("visualization fields are not closed")
    expected = dict(projection)
    declared_address = expected.pop("visualization_address")
    if declared_address != content_address(expected):
        raise VisualizationRejected("visualization address does not match")
    verify_visualization_semantics(expected)
    trades = projection["trades"]
    if not isinstance(trades, Mapping) or not isinstance(trades.get("items"), list):
        raise VisualizationRejected("trade detail is malformed")
    items = trades["items"]
    if any(not isinstance(item, dict) or item.get("cursor") != index + 1
           for index, item in enumerate(items)):
        raise VisualizationRejected("trade cursors are not canonical")
    start = next((index for index, item in enumerate(items)
                  if int(item["cursor"]) > trade_after), len(items))
    page = items[start:start + trade_limit]
    result = dict(projection)
    identity = dict(result["identity"])
    identity["terminal_evidence_address"] = terminal_evidence_address
    result["identity"] = identity
    result["trade_page"] = {
        "items": page,
        "next_cursor": (page[-1]["cursor"] if start + len(page) < len(items) else None),
        "total": int(trades["original_count"]),
        "detail_reason": trades.get("detail_reason"),
    }
    del result["trades"]
    return result


__all__ = ["SCHEMA", "VisualizationRejected", "build_visualization_projection",
           "page_projection", "unavailable", "verify_visualization_semantics"]
