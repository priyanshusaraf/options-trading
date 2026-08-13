"""Mechanical lowering of generated ``Composition`` values into Component IR v1.

Generated Python may explain or compare a composition, but it has no new-exposure
authority.  The returned graph resolves exclusively through the platform registry.
"""
from __future__ import annotations

import json
from typing import Any

from app.ir.contributors.generated_blocks import BAR_INPUTS, BLOCKS
from app.ir.hashing import canonical_json
from app.ir.library import REGISTRY
from app.ir.resolve import BOUNDARY_INPUT, BOUNDARY_OUTPUT
from app.ir.validate import validate
from research.strategy.builder.grammar import Clause, Composition


CANONICAL_CLAUSES = (
    ("long_entry", "longEntry"),
    ("short_entry", "shortEntry"),
    ("long_exit", "longExit"),
    ("short_exit", "shortExit"),
)


class CompositionLoweringError(ValueError):
    """A Composition that cannot become a closed, registered Component IR graph."""


def _wire(value: str, *, instrument: str, timeframe: str) -> dict[str, Any]:
    return {
        "value": value,
        "structure": "series",
        "domain": {"instrument": instrument, "timeframe": timeframe},
    }


def _socket(name: str, direction: str, value: str, *, instrument: str, timeframe: str) -> dict[str, Any]:
    return {
        "item": "socket",
        "identifier": name,
        "display_name": name,
        "direction": direction,
        "wire_type": _wire(value, instrument=instrument, timeframe=timeframe),
    }


def _node(instance_id: str, identifier: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "component": {"identifier": identifier, "version": 1},
        "overrides": overrides or {},
    }


def _edge(source_instance: str, source_socket: str, target_instance: str, target_socket: str) -> dict[str, Any]:
    return {
        "source": {"instance": source_instance, "socket": source_socket},
        "target": {"instance": target_instance, "socket": target_socket},
    }


def _component(identifier: str) -> dict[str, Any]:
    component = REGISTRY.library.components.get((identifier, 1))
    if component is None:
        raise CompositionLoweringError(
            f"registered component {identifier!r} v1 is unavailable")
    if component["body"]["ref"] not in REGISTRY.registrations:
        raise CompositionLoweringError(
            f"registered component {identifier!r} has no executable registration")
    return component


def _require_logic(identifier: str) -> None:
    component = _component(identifier)
    body_ref = component["body"]["ref"]
    if body_ref not in REGISTRY.registrations:
        raise CompositionLoweringError(
            f"registered logic component {identifier!r} has no executable registration")


def _validate_clause(clause: Clause, *, name: str) -> None:
    if clause.op not in {"all", "any"}:
        raise CompositionLoweringError(f"{name} has unsupported operation {clause.op!r}")
    if not clause.refs:
        raise CompositionLoweringError(f"{name} is an empty clause")
    for ref in clause.refs:
        if ref.name not in BLOCKS:
            raise CompositionLoweringError(f"{name} references unknown block {ref.name!r}")
        expected = len(BLOCKS[ref.name].params)
        if len(ref.args) != expected:
            raise CompositionLoweringError(
                f"{name}.{ref.name} expects {expected} arguments, got {len(ref.args)}")


def composition_to_ir(
    comp: Composition,
    *,
    identifier: str,
    version: int = 1,
    instrument: str = "SELF",
    timeframe: str = "*",
) -> dict[str, Any]:
    """Return the deterministic IR v1 graph represented by ``comp``.

    ``instrument`` is a logical role.  It is intentionally not resolved into a
    provider symbol or deployment binding here.
    """
    if not isinstance(comp, Composition):
        raise CompositionLoweringError("composition must be a Composition")
    raw_clauses = tuple((getattr(comp, attribute), output) for attribute, output in CANONICAL_CLAUSES)
    for (attribute, _), (clause, _) in zip(CANONICAL_CLAUSES, raw_clauses):
        _validate_clause(clause, name=attribute)
    try:
        comp = Composition.from_dict(comp.to_dict())
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise CompositionLoweringError("composition cannot canonical-round-trip") from exc
    if not isinstance(identifier, str) or not identifier:
        raise CompositionLoweringError("identifier must be a non-empty string")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise CompositionLoweringError("version must be an integer >= 1")
    if instrument != "SELF":
        raise CompositionLoweringError("Composition lowering accepts only the SELF logical role")
    if not isinstance(timeframe, str) or not timeframe:
        raise CompositionLoweringError("timeframe must be a non-empty logical timeframe")

    _require_logic("logic.and")
    _require_logic("logic.or")
    clauses = tuple((getattr(comp, attribute), output) for attribute, output in CANONICAL_CLAUSES)

    required_inputs = {
        field for clause, _ in clauses for ref in clause.refs for field in BLOCKS[ref.name].inputs
    }
    input_names = tuple(field for field in BAR_INPUTS if field in required_inputs)
    nodes = [_node("io_in", BOUNDARY_INPUT), _node("io_out", BOUNDARY_OUTPUT)]
    edges: list[dict[str, Any]] = []

    for clause_index, (clause, output) in enumerate(clauses):
        block_ids: list[str] = []
        for block_index, ref in enumerate(clause.refs):
            component_id = f"block.{ref.name}"
            _component(component_id)
            spec = BLOCKS[ref.name]
            instance_id = f"c{clause_index}_b{block_index}"
            overrides = {
                param_name: value
                for (param_name, _kind), value in zip(spec.params, ref.args)
            }
            nodes.append(_node(instance_id, component_id, overrides))
            block_ids.append(instance_id)
            for field in spec.inputs:
                edges.append(_edge("io_in", field, instance_id, field))

        current = block_ids[0]
        logic_identifier = "logic.and" if clause.op == "all" else "logic.or"
        logic_prefix = "and" if clause.op == "all" else "or"
        for block_index, block_id in enumerate(block_ids[1:], start=1):
            logic_id = f"c{clause_index}_{logic_prefix}{block_index}"
            nodes.append(_node(logic_id, logic_identifier))
            edges.append(_edge(current, "out", logic_id, "left"))
            edges.append(_edge(block_id, "out", logic_id, "right"))
            current = logic_id
        edges.append(_edge(current, "out", "io_out", output))

    graph = {
        "format_version": 1,
        "kind": "graph",
        "identifier": identifier,
        "version": version,
        "display_name": comp.key,
        "interface": [
            *(_socket(name, "input", "float", instrument=instrument, timeframe=timeframe)
              for name in input_names),
            *(_socket(output, "output", "bool", instrument=instrument, timeframe=timeframe)
              for _, output in clauses),
        ],
        "nodes": nodes,
        "edges": edges,
        "groups": [],
    }
    violations = validate(graph, REGISTRY.library.components)
    if violations:
        raise CompositionLoweringError(
            "lowered graph is invalid: " + "; ".join(str(item) for item in violations))
    return json.loads(canonical_json(graph))


__all__ = ["CompositionLoweringError", "composition_to_ir"]
