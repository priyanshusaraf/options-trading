"""Prove causal admission kills stale and freshly registered lookahead kernels."""
from __future__ import annotations

import argparse
import dataclasses
import json
from collections.abc import Callable
from pathlib import Path
import sys
from types import MappingProxyType
from typing import Any

import pandas as pd


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ir.causal import HistoryBound, causal_contract
from app.ir.hashing import content_address
from app.ir.library import REGISTRY
from app.ir.registry import DependencyBoundary, PlatformRegistry, registered_kernel
from app.ir.strategies import expanding_z
from app.ir.strategies.expanding_z import GRAPH
from app.strategy.admission import (
    AdmissionDecision,
    IRGraphAdmissionInput,
    admit_strategy,
)


FRESH_MUTATION_NAMES = (
    "negative_shift",
    "centered_window",
    "bfill",
    "future_join",
    "global_normalize",
)


def _changed_rma(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(alpha=1.0 / length, adjust=False, min_periods=length).mean()


def stale_helper_decision() -> AdmissionDecision:
    """Mutate the actual registered `_rma` helper after registration."""
    registration = expanding_z.REGISTRATIONS[expanding_z.WILDER["body"]["ref"]]
    original = expanding_z._rma
    setattr(expanding_z, "_rma", _changed_rma)
    try:
        changed_boundary = DependencyBoundary(
            registration.dependency_boundary.mode,
            tuple(_changed_rma if value is original else value
                  for value in registration.dependency_boundary.objects),
        )
        stale = dataclasses.replace(
            registration,
            dependency_boundary=changed_boundary,
        )
        object.__setattr__(REGISTRY, "_registrations", MappingProxyType({
            **REGISTRY.registrations,
            registration.body_ref: stale,
        }))
        return admit_strategy(
            owner_id="causal-mutation-owner",
            source_input=IRGraphAdmissionInput(GRAPH, {}, None),
            registry=REGISTRY,
        )
    finally:
        object.__setattr__(REGISTRY, "_registrations", MappingProxyType({
            **REGISTRY.registrations,
            registration.body_ref: registration,
        }))
        setattr(expanding_z, "_rma", original)


def _negative_shift(params, node_inputs, context_inputs):
    close = node_inputs["close"]
    return {"out": close.shift(-1).fillna(close).gt(close)}


def _centered_window(params, node_inputs, context_inputs):
    close = node_inputs["close"]
    return {"out": close.rolling(3, center=True).mean().fillna(close).gt(close)}


def _bfill(params, node_inputs, context_inputs):
    close = node_inputs["close"]
    return {"out": close.bfill().notna()}


def _future_join(params, node_inputs, context_inputs):
    close = node_inputs["close"]
    future = close.shift(-1).rename("future")
    aligned = pd.concat([close.rename("close"), future], axis=1)["future"]
    return {"out": aligned.fillna(close).gt(close)}


def _global_normalize(params, node_inputs, context_inputs):
    close = node_inputs["close"]
    minimum, maximum = close.min(), close.max()
    normalized = (close - minimum) / (maximum - minimum)
    return {"out": normalized.fillna(0.0).gt(0.5)}


_FRESH_IMPLEMENTATIONS: dict[str, Callable[..., dict[str, pd.Series]]] = {
    "negative_shift": _negative_shift,
    "centered_window": _centered_window,
    "bfill": _bfill,
    "future_join": _future_join,
    "global_normalize": _global_normalize,
}


def _fresh_mutation_registry(name: str) -> tuple[dict[str, Any], PlatformRegistry]:
    try:
        implementation = _FRESH_IMPLEMENTATIONS[name]
    except KeyError as exc:
        raise ValueError(f"unknown causal mutation {name!r}") from exc
    body_ref = content_address({"causal-mutation": name})
    component = {
        "format_version": 1,
        "kind": "component",
        "identifier": f"mutation.{name}",
        "version": 1,
        "display_name": name,
        "interface": [
            {
                "item": "socket", "identifier": "close", "display_name": "close",
                "direction": "input",
                "wire_type": {
                    "value": "float", "structure": "series",
                    "domain": {"instrument": "*", "timeframe": "*"},
                },
            },
            {
                "item": "socket", "identifier": "out", "display_name": "out",
                "direction": "output",
                "wire_type": {
                    "value": "bool", "structure": "series",
                    "domain": {"instrument": "*", "timeframe": "*"},
                },
            },
        ],
        "body": {"body": "kernel", "ref": body_ref},
    }
    graph = {
        "format_version": 1,
        "kind": "graph",
        "identifier": f"mutation.{name}",
        "version": 1,
        "display_name": name,
        "interface": [
            component["interface"][0],
            {
                "item": "socket", "identifier": "longEntry", "display_name": "longEntry",
                "direction": "output",
                "wire_type": component["interface"][1]["wire_type"],
            },
        ],
        "nodes": [
            {
                "instance_id": "io_in",
                "component": {"identifier": "graph.input", "version": 1},
                "overrides": {},
            },
            {
                "instance_id": "n",
                "component": {"identifier": component["identifier"], "version": 1},
                "overrides": {},
            },
            {
                "instance_id": "io_out",
                "component": {"identifier": "graph.output", "version": 1},
                "overrides": {},
            },
        ],
        "edges": [
            {
                "source": {"instance": "io_in", "socket": "close"},
                "target": {"instance": "n", "socket": "close"},
            },
            {
                "source": {"instance": "n", "socket": "out"},
                "target": {"instance": "io_out", "socket": "longEntry"},
            },
        ],
        "groups": [],
    }
    registration = registered_kernel(
        body_ref=body_ref,
        implementation=implementation,
        causal=causal_contract(
            node_input_sockets=("close",), history=HistoryBound("bounded")),
        dependency_boundary=DependencyBoundary(
            "declared_objects", (pd,) if name == "future_join" else ()),
    )
    return graph, PlatformRegistry(
        components={(component["identifier"], 1): component},
        bodies={},
        registrations={body_ref: registration},
    )


def fresh_mutation_decision(name: str) -> AdmissionDecision:
    graph, registry = _fresh_mutation_registry(name)
    return admit_strategy(
        owner_id="causal-mutation-owner",
        source_input=IRGraphAdmissionInput(graph, {}, None),
        registry=registry,
    )


def run_mutations() -> dict[str, int]:
    stale = stale_helper_decision()
    fresh = [fresh_mutation_decision(name) for name in FRESH_MUTATION_NAMES]
    identity_killed = int(stale.refusal_code is not None and stale.refusal_code.value == "IMPLEMENTATION_STALE")
    causal_killed = sum(
        decision.refusal_code is not None and decision.refusal_code.value == "STREAMING_DIVERGENCE"
        for decision in fresh
    )
    return {
        "identity_killed": identity_killed,
        "causal_killed": causal_killed,
        "survived": 1 + len(FRESH_MUTATION_NAMES) - identity_killed - causal_killed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit canonical JSON")
    args = parser.parse_args()
    report = run_mutations()
    print(json.dumps(report, sort_keys=True, separators=(",", ":")) if args.json else report)
    return 0 if report["survived"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
