"""Server-derived structural editor descriptors for one coherent IR document."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.ir.resolve import Library


@dataclass(frozen=True)
class ParameterDescriptor:
    identifier: str
    display_name: str
    kind: str
    default: Any
    panel_path: tuple[str, ...]


@dataclass(frozen=True)
class SocketDescriptor:
    identifier: str
    display_name: str
    direction: str
    wire_type: dict[str, Any]
    has_default_source: bool


@dataclass(frozen=True)
class ComponentDescriptor:
    identifier: str
    version: int
    display_name: str
    parameters: tuple[ParameterDescriptor, ...]
    sockets: tuple[SocketDescriptor, ...]


@dataclass(frozen=True)
class BoundarySocketDescriptor:
    instance_id: str
    identifier: str
    display_name: str
    direction: str
    wire_type: dict[str, Any]
    has_default_source: bool


def _items(
    interface: Iterable[Mapping[str, Any]], panel_path: tuple[str, ...] = ()
):
    for item in interface:
        if item.get("item") == "panel":
            yield from _items(
                item.get("items", ()), panel_path + (str(item["identifier"]),)
            )
        else:
            yield item, panel_path


def parameters(
    interface: Iterable[Mapping[str, Any]],
) -> tuple[ParameterDescriptor, ...]:
    return tuple(
        ParameterDescriptor(
            identifier=str(item["identifier"]),
            display_name=str(item.get("display_name", item["identifier"])),
            kind=str(item.get("kind", "value")),
            default=copy.deepcopy(item.get("default")),
            panel_path=path,
        )
        for item, path in _items(interface)
        if item.get("item") == "parameter"
    )


def sockets(
    interface: Iterable[Mapping[str, Any]],
) -> tuple[SocketDescriptor, ...]:
    return tuple(
        SocketDescriptor(
            identifier=str(item["identifier"]),
            display_name=str(item.get("display_name", item["identifier"])),
            direction=str(item["direction"]),
            wire_type=copy.deepcopy(dict(item["wire_type"])),
            has_default_source="default_source" in item,
        )
        for item, _path in _items(interface)
        if item.get("item") == "socket"
    )


def component_catalogue(library: Library) -> tuple[ComponentDescriptor, ...]:
    return tuple(
        ComponentDescriptor(
            identifier=identifier,
            version=version,
            display_name=str(component.get("display_name", identifier)),
            parameters=parameters(component.get("interface", ())),
            sockets=sockets(component.get("interface", ())),
        )
        for (identifier, version), component in sorted(library.components.items())
    )


def graph_sockets(
    graph: Mapping[str, Any],
) -> tuple[BoundarySocketDescriptor, ...]:
    result: list[BoundarySocketDescriptor] = []
    for socket in sockets(graph.get("interface", ())):
        graph_direction = socket.direction
        result.append(BoundarySocketDescriptor(
            instance_id="io_in" if graph_direction == "input" else "io_out",
            identifier=socket.identifier,
            display_name=socket.display_name,
            direction="output" if graph_direction == "input" else "input",
            wire_type=socket.wire_type,
            has_default_source=socket.has_default_source,
        ))
    return tuple(result)

