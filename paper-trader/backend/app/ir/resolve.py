"""
RFC 0001 §4 — resolution, by eager lowering.

The single resolution shared by research and live (C12): `resolve()` takes a
specification and a library and nothing else — no plane, mode, or live flag.
Instance ids are the instance path joined by `/` (C7); there is no counter and
no clock in this file, which is what makes re-resolution byte-identical.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from app.ir.hashing import canonical_json, content_address
from app.ir.formats.dispatch import UnsupportedFormatVersion, require_resolved_v1, select_format
from app.ir.kernels import KernelSpec, check_warmup
from app.ir.causal import CausalContract
from app.ir.schema import is_parameter_reference

# A body graph wires its interface through these; resolution removes them, so
# no resolved graph ever contains one.
BOUNDARY_INPUT = "graph.input"
BOUNDARY_OUTPUT = "graph.output"
BOUNDARY_IDENTIFIERS = (BOUNDARY_INPUT, BOUNDARY_OUTPUT)

PATH_SEPARATOR = "/"

DEFAULT_SOURCE_SUFFIX = "@default"

RESOLVED_V2_TOPOLOGY_SCHEMA = "resolved-v2-topology/2"
V2_MAX_AUTHORED_NODES = 10_000
V2_MAX_AUTHORED_EDGES = 50_000
V2_MAX_BOUNDARY_PORTS = 10_000
V2_MAX_COMPOUND_DEPTH = 64
V2_MAX_LOWERED_NODES = 50_000
V2_MAX_LOWERED_EDGES = 200_000


class ResolutionError(Exception):
    """A specification that cannot be resolved, named by the clause it fails.

    `path` is the *authored* graph's path (C4), never the resolved graph's.
    """

    def __init__(self, clause: str, path: str, message: str) -> None:
        super().__init__(f"{clause} at {path}: {message}")
        self.clause = clause
        self.path = path
        self.message = message


@dataclass(frozen=True)
class Library:
    """Everything resolution is allowed to read.

    C2/C6: a resolved graph is a function of `(spec, library)` and nothing else.
    """

    components: Mapping[tuple[str, int], Mapping[str, Any]] = field(default_factory=dict)
    bodies: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    kernels: Mapping[str, KernelSpec] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedNode:
    """One leaf of the resolved graph.

    `path`/`definition` are C4 back-references; `instance_id` is the joined path.
    """

    instance_id: str
    path: tuple[str, ...]
    definition: tuple[str, int]
    body_ref: str
    params: Mapping[str, Any]
    domain: Mapping[str, str] | None
    warmup: int
    purity: str
    cache_id: str
    causal: CausalContract | None = None
    derived_from: str | None = None

    @property
    def authored_root(self) -> str:
        """The authored node this leaf came from — `n_fast`, not `n_fast/n_smooth`."""
        return self.path[0] if self.path else self.instance_id


@dataclass(frozen=True)
class ResolvedEdge:
    source: tuple[str, str]
    target: tuple[str, str]
    declared_in: tuple[str, ...]
    derived: bool = False


@dataclass(frozen=True)
class ResolvedComponent:
    """Every reached authored component, including graph-bodied boundaries."""

    node_path: str
    definition: tuple[str, int]
    body_ref: str
    params: Mapping[str, Any]


@dataclass(frozen=True)
class ResolvedGraph:
    """The output of resolution. Never authored, never edited (C3)."""

    identifier: str
    version: int
    nodes: tuple[ResolvedNode, ...]
    edges: tuple[ResolvedEdge, ...]
    versions: tuple[tuple[str, int], ...]
    inputs: Mapping[str, tuple[tuple[str, str], ...]]
    outputs: Mapping[str, tuple[str, str]]
    components: tuple[ResolvedComponent, ...] = ()
    format_version: int = 1

    @property
    def warmup(self) -> int:
        """C10 — the deepest chain in the graph."""
        return max((n.warmup for n in self.nodes), default=0)

    def node(self, instance_id: str) -> ResolvedNode | None:
        for n in self.nodes:
            if n.instance_id == instance_id:
                return n
        return None


# V2 deliberately has a separate resolved representation.  In particular, an
# input is a bundle, never the historical v1 ``target -> source`` shortcut.
@dataclass(frozen=True)
class ResolvedV2Member:
    edge_id: str
    source: Mapping[str, str]
    binding: Mapping[str, Any]
    type_ref: Mapping[str, Any]
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class ResolvedV2Bundle:
    target: Mapping[str, str]
    assembly: str
    members: tuple[ResolvedV2Member, ...]
    default: Any
    default_provenance: str | None


@dataclass(frozen=True)
class ResolvedV2Node:
    node_id: str
    component: tuple[str, int]
    parameters: Mapping[str, Any]
    parameter_provenance: Mapping[str, Mapping[str, Any]]
    declaration_address: str | None = None
    bound_requirements: tuple[Mapping[str, Any], ...] | None = None
    registry_snapshot_address: str | None = None
    authored_node_id: str | None = None
    lowered_path: tuple[str, ...] | None = None
    binding_implementation_address: str | None = None


@dataclass(frozen=True)
class ResolvedV2Graph:
    nodes: tuple[ResolvedV2Node, ...]
    bundles: Mapping[tuple[str, str], ResolvedV2Bundle]
    outputs: Mapping[str, ResolvedV2Member]
    graph_inputs: Mapping[str, Mapping[str, Any]]
    format_version: int = 2
    registry_snapshot_address: str | None = None
    resolved_graph_address: str | None = None
    implementation_closure_address: str | None = None
    authored_ir_address: str | None = None
    registry_snapshot_payload: Mapping[str, Any] | None = None
    data_requirement_declaration_closure: tuple[Mapping[str, Any], ...] | None = None
    topology_document: Mapping[str, Any] | None = None
    authored_executable_address: str | None = None

    def __post_init__(self) -> None:
        """Keep replacement-based negative fixtures on the closed identity path.

        Runtime-only synthetic graphs may omit Phase 4 authority facts.  Once a
        graph has a topology document, however, every dataclass replacement is
        re-projected into that document and its nodes retain the document for
        the historical five-argument verifier seam.
        """
        if self.topology_document is None:
            return
        topology = _reproject_v2_topology(self, self.topology_document)
        frozen = _freeze_v2(topology)
        object.__setattr__(self, "topology_document", frozen)
        object.__setattr__(self, "nodes", _ResolvedV2Nodes(self.nodes, frozen))


class _ResolvedV2Nodes(tuple):
    """Tuple-compatible nodes carrying the address document for old verifiers."""

    def __new__(cls, values: Sequence[ResolvedV2Node], topology_document: Mapping[str, Any]):
        instance = super().__new__(cls, values)
        instance.topology_document = topology_document
        return instance


def resolve_v2(document: Mapping[str, Any], registry: Any) -> ResolvedV2Graph:
    """Resolve a validated fixed v2 document without consulting ambient state.

    This deliberately accepts only the registry supplied by the caller.  It
    preserves every edge in a deterministic bundle so many-input components
    cannot silently become single-input components at runtime.
    """
    _enforce_v2_resolution_limits(document, registry)
    from app.ir.formats.v2 import canonical_document, graph_address_for, validate_document
    violations = validate_document(document, registry)
    if violations:
        raise ResolutionError("V2", violations[0].path, violations[0].message)
    document = canonical_document(document, registry)
    authored_executable_address = graph_address_for(document, registry)
    components = registry.v2_components
    node_rows = {row["node_id"]: row for row in document["nodes"]}
    nodes: list[ResolvedV2Node] = []
    for node_id in sorted(node_rows):
        row = node_rows[node_id]
        nodes.extend(_expand_v2_node(row, components, (node_id,), None, None, ()))
    nodes = [_bind_v2_data_requirements(node, registry) for node in nodes]
    # Lowering follows every body edge through compound boundaries.  A
    # compound is therefore never an executable node and no public boundary
    # can survive in the resolved graph.
    lowered = _lower_v2_graph(document, components, ())
    by_target: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for edge in lowered.edges:
        target = edge["target"]
        by_target.setdefault((target["node_id"], target["port_id"]), []).append(edge)
    bundles: dict[tuple[str, str], ResolvedV2Bundle] = {}
    for node in nodes:
        component = components[node.component]
        for port in component["ports"]:
            if port["direction"] != "input":
                continue
            key = (node.node_id, port["port_id"])
            edges = by_target.get(key, [])
            assembly = port["connections"]["assembly"]
            ordered = _order_v2_edges(edges, assembly)
            members = tuple(_resolved_lowered_v2_member(edge, document, nodes, registry) for edge in ordered)
            default = port.get("default") if not members and "default" in port else None
            bundles[key] = ResolvedV2Bundle(
                target=_freeze_v2({"scope": "node", "node_id": node.node_id, "port_id": port["port_id"]}),
                assembly=assembly, members=members, default=_freeze_v2(default),
                default_provenance="port_default" if not members and "default" in port else None,
            )
    outputs = {
        name: _resolved_lowered_v2_member(
            {"edge_id": f"graph-output:{name}", "source": {key: value for key, value in endpoint.items() if key != "_provenance"}, "binding": {"kind": "single"},
             "provenance": {**endpoint.get("_provenance", {"kind": "lowered_graph_output", "port_id": name}), "edge_path": endpoint.get("_edge_path", ())}},
            document, nodes, registry,
        )
        for name, endpoint in sorted(lowered.outputs.items())
    }
    graph_inputs = {port["port_id"]: _freeze_v2(port) for port in document["graph_inputs"]}
    snapshot = getattr(registry, "registry_snapshot_address", None)
    implementation_closure = {"implementations": [
        {"component_id": key[0], "component_version": key[1], "implementation_address": value}
        for key, value in sorted(getattr(registry, "v2_implementation_identities", {}).items())
    ]}
    contract_bindings = getattr(registry, "contract_bindings", {})
    if contract_bindings:
        implementation_closure["contract_bindings"] = [
            _plain_v2(contract_bindings[key].document) for key in sorted(contract_bindings)
        ]
    closure = content_address(implementation_closure)
    snapshot_payload = _freeze_v2(getattr(registry, "registry_snapshot_payload", None))
    declaration_closure = tuple(
        _freeze_v2({"component_id": key[0], "component_version": key[1], "declaration": value})
        for key, value in sorted(getattr(registry, "data_requirement_declarations", {}).items())
    )
    topology_document = _resolved_v2_topology_document(
        document=document,
        nodes=nodes,
        bundles=bundles,
        outputs=outputs,
        authored_executable_address=authored_executable_address,
        registry_snapshot_address=snapshot,
        registry_snapshot_payload=snapshot_payload,
        implementation_closure_address=closure,
        implementation_closure=implementation_closure,
        declaration_closure=declaration_closure,
    )
    frozen_topology = _freeze_v2(topology_document)
    resolved_nodes = _ResolvedV2Nodes(nodes, frozen_topology)
    resolved_address = resolved_v2_graph_address(
        resolved_nodes, snapshot, closure, snapshot_payload, declaration_closure,
    )
    return ResolvedV2Graph(
        resolved_nodes, MappingProxyType(bundles), MappingProxyType(outputs), MappingProxyType(graph_inputs),
        registry_snapshot_address=snapshot, resolved_graph_address=resolved_address,
        implementation_closure_address=closure, authored_ir_address=content_address(document),
        registry_snapshot_payload=snapshot_payload, data_requirement_declaration_closure=declaration_closure,
        topology_document=frozen_topology,
        authored_executable_address=authored_executable_address,
    )


def resolved_v2_graph_address(
    nodes: Sequence[ResolvedV2Node], registry_snapshot_address: str | None,
    implementation_closure_address: str | None, registry_snapshot_payload: Any,
    data_requirement_declaration_closure: Any,
) -> str:
    """Address the sole resolved-v2 topology fact.

    ``_ResolvedV2Nodes`` preserves the complete document across the historical
    five-argument verification seam.  Plain sequences have no complete
    topology authority and therefore fail closed.
    """
    topology_document = getattr(nodes, "topology_document", None)
    if topology_document is not None:
        topology = _plain_v2(topology_document)
        registry = topology.get("registry_snapshot")
        implementation = topology.get("implementation_closure")
        if (
            not isinstance(registry, Mapping)
            or set(registry) != {"address", "payload"}
            or registry["address"] != registry_snapshot_address
            or (
                registry_snapshot_address is not None
                and content_address(registry["payload"])
                    != registry_snapshot_address
            )
            or (
                registry_snapshot_address is None
                and registry["payload"] is not None
            )
            or not isinstance(implementation, Mapping)
            or set(implementation) != {"address", "payload"}
            or implementation["address"] != implementation_closure_address
            or content_address(implementation["payload"]) != implementation_closure_address
            or topology.get("declaration_closure")
                != _plain_v2(data_requirement_declaration_closure)
        ):
            raise ResolutionError(
                "V2_TOPOLOGY_STALE", "$.topology_document",
                "resolved v2 topology closure address does not match its payload",
            )
        return content_address({
            "schema": RESOLVED_V2_TOPOLOGY_SCHEMA,
            "fact": topology,
        })
    raise ResolutionError(
        "V2_TOPOLOGY_INCOMPLETE", "$.topology_document",
        "resolved v2 topology identity requires its complete canonical document",
    )


def _resolved_v2_topology_document(
    *, document: Mapping[str, Any], nodes: Sequence[ResolvedV2Node],
    bundles: Mapping[tuple[str, str], ResolvedV2Bundle],
    outputs: Mapping[str, ResolvedV2Member], authored_executable_address: str,
    registry_snapshot_address: str | None, registry_snapshot_payload: Any,
    implementation_closure_address: str,
    implementation_closure: Mapping[str, Any], declaration_closure: Any,
) -> dict[str, Any]:
    node_rows = [_resolved_v2_node_document(node) for node in nodes]
    bundle_rows: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []
    for order, (target_key, bundle) in enumerate(sorted(bundles.items())):
        members = [_resolved_v2_member_document(member) for member in bundle.members]
        bundle_rows.append({
            "target_key": list(target_key),
            "target": _plain_v2(bundle.target),
            "assembly": bundle.assembly,
            "bundle_order": order,
            "member_order": [member["edge_id"] for member in members],
            "members": members,
            "default": _plain_v2(bundle.default),
            "default_provenance": bundle.default_provenance,
        })
        edge_rows.extend({
            "target": _plain_v2(bundle.target),
            "assembly": bundle.assembly,
            "order": member_order,
            **member,
        } for member_order, member in enumerate(members))
    graph_outputs = []
    authored_outputs = {row["port_id"]: row for row in document["graph_outputs"]}
    for output_order, (name, member) in enumerate(sorted(outputs.items())):
        member_document = _resolved_v2_member_document(member)
        graph_outputs.append({
            "port_id": name,
            "output_order": output_order,
            "descriptor": _plain_v2(authored_outputs[name]),
            "member": member_document,
        })
        edge_rows.append({
            "target": {"scope": "graph_output", "port_id": name},
            "assembly": "single",
            "order": output_order,
            **member_document,
        })
    return {
        "format_version": 2,
        "authored_executable_address": authored_executable_address,
        "registry_snapshot": {
            "address": registry_snapshot_address,
            "payload": _plain_v2(registry_snapshot_payload),
        },
        "implementation_closure": {
            "address": implementation_closure_address,
            "payload": _plain_v2(implementation_closure),
        },
        "declaration_closure": _plain_v2(declaration_closure),
        "nodes": node_rows,
        "edges": edge_rows,
        "bundles": bundle_rows,
        "graph_inputs": [{
            "lookup_key": row["port_id"],
            "descriptor": _plain_v2(row),
        } for row in document["graph_inputs"]],
        "graph_outputs": graph_outputs,
        "compound_lowering": [{
            "node_id": node["node_id"],
            "authored_node_id": node["authored_node_id"],
            "lowered_path": node["lowered_path"],
            "parameter_bindings": node["parameter_provenance"],
        } for node in node_rows],
    }


def _resolved_v2_node_document(node: ResolvedV2Node) -> dict[str, Any]:
    document = {
        "node_id": node.node_id,
        "component": {
            "component_id": node.component[0],
            "component_version": node.component[1],
        },
        "parameters": _plain_v2(node.parameters),
        "parameter_provenance": _plain_v2(node.parameter_provenance),
        "declaration_address": node.declaration_address,
        "bound_requirements": _plain_v2(node.bound_requirements),
        "registry_snapshot_address": node.registry_snapshot_address,
        "authored_node_id": node.authored_node_id,
        "lowered_path": _plain_v2(node.lowered_path),
    }
    if node.binding_implementation_address is not None:
        document["binding_implementation_address"] = node.binding_implementation_address
    return document


def _resolved_v2_member_document(member: ResolvedV2Member) -> dict[str, Any]:
    return {
        "edge_id": member.edge_id,
        "source": _plain_v2(member.source),
        "binding": _plain_v2(member.binding),
        "member_type": _plain_v2(member.type_ref),
        "provenance": _plain_v2(member.provenance),
    }


def _reproject_v2_topology(
    graph: ResolvedV2Graph, prior_document: Mapping[str, Any],
) -> dict[str, Any]:
    """Project every execution-bearing graph field into one carried fact."""
    prior = _plain_v2(prior_document)
    nodes = [
        _resolved_v2_node_document(node)
        for node in sorted(graph.nodes, key=lambda value: value.node_id)
    ]
    bundles: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for bundle_order, (target_key, bundle) in enumerate(sorted(graph.bundles.items())):
        members = [_resolved_v2_member_document(member) for member in bundle.members]
        bundles.append({
            "target_key": list(target_key),
            "target": _plain_v2(bundle.target),
            "assembly": bundle.assembly,
            "bundle_order": bundle_order,
            "member_order": [member["edge_id"] for member in members],
            "members": members,
            "default": _plain_v2(bundle.default),
            "default_provenance": bundle.default_provenance,
        })
        edges.extend({
            "target": _plain_v2(bundle.target),
            "assembly": bundle.assembly,
            "order": member_order,
            **member,
        } for member_order, member in enumerate(members))

    prior_outputs = {
        row.get("port_id"): row for row in prior.get("graph_outputs", ())
        if isinstance(row, Mapping) and isinstance(row.get("port_id"), str)
    }
    graph_outputs: list[dict[str, Any]] = []
    for output_order, (name, member) in enumerate(sorted(graph.outputs.items())):
        member_document = _resolved_v2_member_document(member)
        prior_row = prior_outputs.get(name, {})
        descriptor = prior_row.get("descriptor")
        if not isinstance(descriptor, Mapping):
            descriptor = {
                "port_id": name,
                "direction": "output",
                "type_ref": _plain_v2(member.type_ref),
            }
        graph_outputs.append({
            "port_id": name,
            "output_order": output_order,
            "descriptor": _plain_v2(descriptor),
            "member": member_document,
        })
        edges.append({
            "target": {"scope": "graph_output", "port_id": name},
            "assembly": "single",
            "order": output_order,
            **member_document,
        })

    implementation = prior.get("implementation_closure")
    implementation_payload = (
        implementation.get("payload") if isinstance(implementation, Mapping) else None
    )
    return {
        "format_version": graph.format_version,
        "authored_executable_address": graph.authored_executable_address,
        "registry_snapshot": {
            "address": graph.registry_snapshot_address,
            "payload": _plain_v2(graph.registry_snapshot_payload),
        },
        "implementation_closure": {
            "address": graph.implementation_closure_address,
            "payload": _plain_v2(implementation_payload),
        },
        "declaration_closure": _plain_v2(
            graph.data_requirement_declaration_closure),
        "nodes": nodes,
        "edges": edges,
        "bundles": bundles,
        "graph_inputs": [
            {"lookup_key": key, "descriptor": _plain_v2(value)}
            for key, value in sorted(graph.graph_inputs.items())
        ],
        "graph_outputs": graph_outputs,
        "compound_lowering": [{
            "node_id": node["node_id"],
            "authored_node_id": node["authored_node_id"],
            "lowered_path": node["lowered_path"],
            "parameter_bindings": node["parameter_provenance"],
        } for node in nodes],
    }


def _enforce_v2_resolution_limits(document: Any, registry: Any) -> None:
    """Refuse oversized public inputs before validation or lowering allocates."""
    if not isinstance(document, Mapping):
        return
    components = getattr(registry, "v2_components", {})
    stack: list[tuple[Mapping[str, Any], frozenset[tuple[Any, Any]], int, str]] = [
        (document, frozenset(), 0, "$"),
    ]
    lowered_nodes = 0
    lowered_edges = 0
    while stack:
        graph, active, depth, path = stack.pop()
        collections = {
            "nodes": (graph.get("nodes"), V2_MAX_AUTHORED_NODES),
            "edges": (graph.get("edges"), V2_MAX_AUTHORED_EDGES),
            "graph_inputs": (graph.get("graph_inputs"), V2_MAX_BOUNDARY_PORTS),
            "graph_outputs": (graph.get("graph_outputs"), V2_MAX_BOUNDARY_PORTS),
        }
        for name, (rows, limit) in collections.items():
            if isinstance(rows, (list, tuple)) and len(rows) > limit:
                raise ResolutionError(
                    "V2_LIMIT", f"{path}.{name}", f"{name} limit exceeded",
                )
        nodes = graph.get("nodes") if isinstance(graph.get("nodes"), (list, tuple)) else ()
        edges = graph.get("edges") if isinstance(graph.get("edges"), (list, tuple)) else ()
        lowered_edges += len(edges)
        if lowered_edges > V2_MAX_LOWERED_EDGES:
            raise ResolutionError("V2_LIMIT", f"{path}.edges", "lowered edge limit exceeded")
        for row in nodes:
            component = row.get("component", {}) if isinstance(row, Mapping) else {}
            ref = (component.get("component_id"), component.get("component_version"))
            definition = components.get(ref)
            compound = definition.get("compound") if isinstance(definition, Mapping) else None
            body = compound.get("body") if isinstance(compound, Mapping) else None
            if not isinstance(body, Mapping):
                lowered_nodes += 1
                if lowered_nodes > V2_MAX_LOWERED_NODES:
                    raise ResolutionError(
                        "V2_LIMIT", f"{path}.nodes", "lowered node limit exceeded",
                    )
                continue
            if ref in active:
                raise ResolutionError(
                    "V2_LIMIT", f"{path}.nodes", "cyclic compound dependency refused",
                )
            if depth >= V2_MAX_COMPOUND_DEPTH:
                raise ResolutionError(
                    "V2_LIMIT", f"{path}.nodes", "compound dependency depth limit exceeded",
                )
            node_id = row.get("node_id", "?") if isinstance(row, Mapping) else "?"
            stack.append((body, active | {ref}, depth + 1, f"{path}.nodes[{node_id}].compound"))


def _bind_v2_data_requirements(node: ResolvedV2Node, registry: Any) -> ResolvedV2Node:
    declarations = getattr(registry, "data_requirement_declarations", {})
    addresses = getattr(registry, "data_requirement_declaration_addresses", {})
    raw = declarations.get(node.component)
    if raw is None:
        return node
    if raw.get("schema") == "first-party-node-contract/2":
        from app.ir.first_party.analytical_v2.contracts import canonical_binding_parameters
        try:
            registry.validate_contract_bindings()
            registration = registry.contract_bindings[node.component]
            parameters = canonical_binding_parameters(node.parameters, registry.v2_components[node.component]["parameters"])
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ResolutionError("NODE_CONTRACT_BINDING", node.node_id, str(exc)) from exc
        # Resolution contains only an immutable recipe. Data identity is supplied
        # later to the same data-plan compiler; it never enters authored semantics.
        return ResolvedV2Node(
            node.node_id, node.component, parameters, node.parameter_provenance,
            addresses[node.component], None, registry.registry_snapshot_address,
            node.authored_node_id, node.lowered_path, registration.implementation_address,
        )
    from app.ir.registry import _validate_data_direct
    bound: list[Mapping[str, Any]] = []
    for raw_row in raw["requirements"]:
        row: dict[str, Any] = {"requirement_id": raw_row["requirement_id"]}
        for field, expression in raw_row.items():
            if field == "requirement_id":
                continue
            value = expression.get("literal") if "literal" in expression else node.parameters.get(expression["parameter"])
            if value is None and "parameter" in expression:
                raise ResolutionError("PHASE4_DATA", node.node_id, f"data parameter {expression['parameter']!r} is unbound")
            _validate_data_direct(field, value)
            row[field] = value
        bound.append(_freeze_v2(row))
    return ResolvedV2Node(node.node_id, node.component, node.parameters, node.parameter_provenance, addresses[node.component], tuple(bound), getattr(registry, "registry_snapshot_address", None), node.authored_node_id, node.lowered_path)


@dataclass
class _LoweredV2Graph:
    edges: list[dict[str, Any]]
    inputs: dict[str, list[dict[str, Any]]]
    outputs: dict[str, dict[str, Any]]


def _lower_v2_graph(
    graph: Mapping[str, Any], components: Mapping[tuple[str, int], Mapping[str, Any]], path: tuple[str, ...],
) -> _LoweredV2Graph:
    """Substitute compound boundaries with their complete ordinary body graph."""
    children: dict[str, _LoweredV2Graph | None] = {}
    inputs: dict[tuple[str, str], list[dict[str, str]]] = {}
    outputs: dict[tuple[str, str], dict[str, str]] = {}
    for row in graph["nodes"]:
        node_id = row["node_id"]
        ref = (row["component"]["component_id"], row["component"]["component_version"])
        component = components[ref]
        compound = component.get("compound")
        if compound is None:
            children[node_id] = None
            absolute = PATH_SEPARATOR.join(path + (node_id,))
            for port in component["ports"]:
                endpoint = {"scope": "node", "node_id": absolute, "port_id": port["port_id"]}
                if port["direction"] == "input":
                    inputs[(node_id, port["port_id"])] = [endpoint]
                else:
                    outputs[(node_id, port["port_id"])] = endpoint
            continue
        lowered = _lower_v2_graph(compound["body"], components, path + (node_id,))
        children[node_id] = lowered
        for port in component["ports"]:
            key = (node_id, port["port_id"])
            if port["direction"] == "input":
                inputs[key] = lowered.inputs[port["port_id"]]
            else:
                outputs[key] = lowered.outputs[port["port_id"]]

    result = _LoweredV2Graph([], {}, {})
    # Nested edges were already lowered.  Keep them before enclosing edges;
    # edge identifiers remain deterministic and provenance retains every hop.
    for child in children.values():
        if child is not None:
            # A child boundary input is a route, not an executable edge.  The
            # enclosing graph replaces it with the actual edge at its public
            # input boundary.
            result.edges.extend(edge for edge in child.edges if edge["source"]["scope"] != "compound_input")
    for edge in graph["edges"]:
        source = edge["source"]
        target = edge["target"]
        if source["scope"] == "graph_input":
            resolved_source = {"scope": "graph_input" if not path else "compound_input", "port_id": source["port_id"]}
        else:
            resolved_source = {key: value for key, value in outputs[(source["node_id"], source["port_id"])].items() if key not in {"_provenance", "_edge_path"}}
        source_route = tuple(outputs[(source["node_id"], source["port_id"])].get("_edge_path", ())) if source["scope"] == "node" else ()
        hop = {
            "edge_id": edge["edge_id"],
            "path": path,
            "source": source,
            "target": target,
            "binding": edge["binding"],
        }
        if target["scope"] == "graph_output":
            result.outputs[target["port_id"]] = {
                **resolved_source,
                "_edge_path": source_route + (hop,),
                "_provenance": {"edge_id": edge["edge_id"], "path": path, "source": resolved_source, "target": target},
            }
            continue
        for resolved_target in inputs[(target["node_id"], target["port_id"])]:
            target_route = tuple(resolved_target.get("_edge_path", ()))
            result.edges.append({
                "edge_id": PATH_SEPARATOR.join(path + (edge["edge_id"],)),
                "source": resolved_source,
                "target": {key: value for key, value in resolved_target.items() if key != "_edge_path"},
                "binding": edge["binding"],
                "provenance": {"edge_id": edge["edge_id"], "path": path, "source": source, "target": target, "edge_path": source_route + (hop,) + target_route},
            })
    for port in graph["graph_inputs"]:
        # Incoming graph-input edges have been resolved above.  Route the
        # boundary to each leaf target so the enclosing graph can substitute it.
        result.inputs[port["port_id"]] = [
            {**edge["target"], "_edge_path": tuple(edge["provenance"].get("edge_path", ()))} for edge in result.edges
            if edge["source"]["scope"] in {"graph_input", "compound_input"} and edge["source"]["port_id"] == port["port_id"]
        ]
    return result


def _resolved_lowered_v2_member(
    edge: Mapping[str, Any], document: Mapping[str, Any], nodes: Sequence[ResolvedV2Node], registry: Any,
) -> ResolvedV2Member:
    source = edge["source"]
    if source["scope"] == "graph_input":
        port = next(port for port in document["graph_inputs"] if port["port_id"] == source["port_id"])
    else:
        node = next(node for node in nodes if node.node_id == source["node_id"])
        component = registry.v2_components[node.component]
        port = next(port for port in component["ports"] if port["port_id"] == source["port_id"] and port["direction"] == "output")
    provenance = dict(edge.get("provenance", {}))
    provenance["binding"] = edge["binding"]
    provenance.setdefault("edge_path", ({"edge_id": provenance.get("edge_id", edge["edge_id"])},))
    return ResolvedV2Member(edge["edge_id"], _freeze_v2(source), _freeze_v2(edge["binding"]), _freeze_v2(port["type_ref"]), _freeze_v2(provenance))


def _resolve_v2_parameters(values: Mapping[str, Any], component: Mapping[str, Any], path: tuple[str, ...]) -> tuple[dict[str, Any], dict[str, Mapping[str, Any]]]:
    declared = component.get("parameters", {})
    if set(values) - set(declared):
        raise ResolutionError("V2", ".".join(path), "node has undeclared parameters")
    result: dict[str, Any] = {}; provenance: dict[str, Mapping[str, Any]] = {}
    for parameter_id in sorted(declared):
        descriptor = declared[parameter_id]
        if parameter_id in values:
            result[parameter_id] = values[parameter_id]
            provenance[parameter_id] = {"kind": "explicit", "path": path, "parameter_id": parameter_id}
        elif descriptor.get("default") is not None:
            result[parameter_id] = descriptor["default"]
            provenance[parameter_id] = {"kind": "default", "path": path, "parameter_id": parameter_id}
        else:
            result[parameter_id] = None
            provenance[parameter_id] = {"kind": "absence", "path": path, "parameter_id": parameter_id}
    return result, provenance


def _expand_v2_node(
    row: Mapping[str, Any], components: Mapping[tuple[str, int], Mapping[str, Any]], path: tuple[str, ...],
    supplied_values: Mapping[str, Any] | None, supplied_provenance: Mapping[str, Mapping[str, Any]] | None,
    active: tuple[tuple[str, int], ...],
) -> list[ResolvedV2Node]:
    ref = (row["component"]["component_id"], row["component"]["component_version"])
    component = components[ref]
    if ref in active:
        raise ResolutionError("V2", ".".join(path), "compound component cycle")
    params, provenance = _resolve_v2_parameters(row.get("parameters", {}), component, path)
    if supplied_values is not None:
        for parameter_id, value in supplied_values.items():
            params[parameter_id] = value
            provenance[parameter_id] = dict(supplied_provenance or {})[parameter_id]
    compound = component.get("compound")
    if compound is None:
        return [ResolvedV2Node("/".join(path), ref, _freeze_v2(params), _freeze_v2(provenance), authored_node_id=path[0], lowered_path=path)]
    targets_by_node: dict[str, dict[str, tuple[Any, Mapping[str, Any]]]] = {}
    for binding in compound["parameter_bindings"]:
        parameter_id = binding["parameter_id"]
        parent_provenance = dict(provenance[parameter_id])
        for target in binding["targets"]:
            target_paths = tuple(parent_provenance.get("target_paths", ())) + ((target["node_id"], target["parameter_id"]),)
            copied = {**parent_provenance, "path": path + (target["node_id"],), "target_paths": target_paths}
            targets_by_node.setdefault(target["node_id"], {})[target["parameter_id"]] = (params[parameter_id], copied)
    expanded: list[ResolvedV2Node] = []
    for child in sorted(compound["body"].get("nodes", ()), key=lambda value: value["node_id"]):
        supplies = targets_by_node.get(child["node_id"], {})
        expanded.extend(_expand_v2_node(
            child, components, path + (child["node_id"],),
            {key: value for key, (value, _) in supplies.items()},
            {key: value for key, (_, value) in supplies.items()}, active + (ref,),
        ))
    return expanded


def _order_v2_edges(edges: Sequence[Mapping[str, Any]], assembly: str) -> list[Mapping[str, Any]]:
    if assembly == "ordered":
        return sorted(edges, key=lambda edge: edge["binding"]["position"])
    if assembly == "keyed":
        return sorted(edges, key=lambda edge: edge["binding"]["key"])
    return sorted(edges, key=lambda edge: edge["edge_id"])


def _resolved_v2_member(edge: Mapping[str, Any], document: Mapping[str, Any], registry: Any) -> ResolvedV2Member:
    source = edge["source"]
    if source["scope"] == "graph_input":
        port = next(port for port in document["graph_inputs"] if port["port_id"] == source["port_id"])
    else:
        node = next(row for row in document["nodes"] if row["node_id"] == source["node_id"])
        component = registry.v2_components[(node["component"]["component_id"], node["component"]["component_version"])]
        port = next(port for port in component["ports"] if port["port_id"] == source["port_id"] and port["direction"] == "output")
    return ResolvedV2Member(edge["edge_id"], _freeze_v2(source), _freeze_v2(edge["binding"]), _freeze_v2(port["type_ref"]), _freeze_v2({"edge_id": edge["edge_id"], "source": source, "binding": edge["binding"]}))


def _freeze_v2(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_v2(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_v2(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_v2(item) for item in value)
    return value


def _plain_v2(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain_v2(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_v2(item) for item in value]
    return value


def resolve(spec: Mapping[str, Any], library: Library,
            parameters: Mapping[str, Any] | None = None) -> ResolvedGraph:
    """Resolve `spec` against `library` into a fully bound graph.

    `parameters` binds the spec's top-level parameters — one value each; a
    searcher calls this once per candidate (C14).
    """
    try:
        format_version = select_format(spec)
        require_resolved_v1(format_version)
    except UnsupportedFormatVersion as exc:
        raise ResolutionError("F1", "$.format_version", str(exc)) from exc
    ctx = _Context(library)

    root_params = _bind(spec, parameters or {}, {}, "$", ctx)

    kind = spec.get("kind")
    if kind == "graph":
        ports = _expand(spec, (), root_params, None, ctx)
    elif kind == "component":
        ports = _expand_component_body(spec, (), root_params, None, ctx)
    else:
        raise ResolutionError("C3", "$.kind",
                              f"{kind!r} is neither a graph nor a component")

    _apply_default_sources(ctx)
    nodes = _finish(ctx)
    return ResolvedGraph(
        identifier=str(spec.get("identifier")),
        version=int(spec.get("version", 0)),
        nodes=nodes,
        edges=tuple(ctx.edges),
        versions=tuple(sorted(ctx.versions)),
        inputs=MappingProxyType({k: tuple(v) for k, v in ports.inputs.items()}),
        outputs=MappingProxyType(dict(ports.outputs)),
        components=tuple(ctx.components),
        format_version=format_version,
    )


def publish(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Derive a component-def from a graph-def (C15: mechanical, no options).

    `body_for(graph)` gives the entry its body needs in `Library.bodies`.
    """
    if graph.get("kind") != "graph":
        raise ResolutionError("C15", "$.kind", "only a graph can be published as a component")

    component = {
        "format_version": graph["format_version"],
        "kind": "component",
        "identifier": graph["identifier"],
        "version": graph["version"],
        "display_name": graph["display_name"],
        "interface": graph["interface"],
        "body": {"body": "graph", "ref": content_address(graph)},
    }
    if "parent_version" in graph:
        component["parent_version"] = graph["parent_version"]
    return component


def body_for(graph: Mapping[str, Any]) -> tuple[str, Mapping[str, Any]]:
    """The `(content address, body)` pair `publish(graph)` refers to."""
    return content_address(graph), graph


def validate_graph_component_body(
    component: Mapping[str, Any],
    body: Mapping[str, Any],
    components: Mapping[tuple[str, int], Mapping[str, Any]],
    here: str = "$",
) -> None:
    """Reject a graph component whose body changes its public V1 contract."""
    if _authored_graph_has_cycle(body):
        raise ResolutionError("C10", here, "the graph has a cycle")
    if canonical_json(component.get("interface")) != canonical_json(body.get("interface")):
        raise ResolutionError(
            "C3", f"{here}.interface",
            "graph component public interface differs from its graph body interface")
    _check_graph_boundaries(body, here, components)


def _check_graph_boundaries(
    graph: Mapping[str, Any],
    here: str,
    components: Mapping[tuple[str, int], Mapping[str, Any]],
) -> None:
    if _authored_graph_has_cycle(graph):
        raise ResolutionError("C10", here, "the graph has a cycle")
    sockets = _declared_sockets(graph)
    inputs = {name for name, direction in sockets.items() if direction == "input"}
    outputs = {name for name, direction in sockets.items() if direction == "output"}
    node_refs = {
        node.get("instance_id"): node.get("component") or {}
        for node in graph.get("nodes", ())
        if isinstance(node, Mapping)
    }
    produced_outputs: set[str] = set()
    consumed_targets: set[tuple[Any, Any]] = set()
    for index, edge in enumerate(graph.get("edges", ())):
        if not isinstance(edge, Mapping):
            continue
        source, target = edge.get("source") or {}, edge.get("target") or {}
        source_socket, target_socket = source.get("socket"), target.get("socket")
        edge_here = f"{here}.edges[{index}]"
        source_ref = node_refs.get(source.get("instance"), {})
        target_ref = node_refs.get(target.get("instance"), {})
        source_kind = source_ref.get("identifier")
        target_kind = target_ref.get("identifier")
        if source_kind == BOUNDARY_OUTPUT:
            raise ResolutionError(
                "C3", edge_here + ".source",
                "a graph output boundary cannot be an edge source")
        if target_kind == BOUNDARY_INPUT:
            raise ResolutionError(
                "C3", edge_here + ".target",
                "a graph input boundary cannot be an edge target")
        if source_kind == BOUNDARY_INPUT \
                and source_socket not in inputs:
            raise ResolutionError(
                "C3", edge_here + ".source.socket",
                f"graph input {source_socket!r} is not a declared input boundary name")
        if source_kind not in BOUNDARY_IDENTIFIERS:
            _require_endpoint_direction(
                source_ref, source_socket, "output", edge_here + ".source.socket",
                components)
        if target_kind == BOUNDARY_OUTPUT:
            if target_socket not in outputs:
                raise ResolutionError(
                    "C3", edge_here + ".target.socket",
                    f"graph output {target_socket!r} is not a declared output boundary name")
            if target_socket in produced_outputs:
                raise ResolutionError(
                    "C3", edge_here + ".target",
                    f"graph output {target_socket!r} has more than one producer")
            produced_outputs.add(target_socket)
        else:
            _require_endpoint_direction(
                target_ref, target_socket, "input", edge_here + ".target.socket",
                components)
        target_key = (target.get("instance"), target_socket)
        if target_key in consumed_targets:
            raise ResolutionError(
                "C3", edge_here + ".target",
                f"target {target_key[0]}.{target_key[1]} has more than one incoming edge")
        consumed_targets.add(target_key)
    missing = sorted(outputs - produced_outputs)
    if missing:
        raise ResolutionError(
            "C3", f"{here}.interface",
            f"declared graph output {missing[0]!r} must have exactly one producer")


def _require_endpoint_direction(
    ref: Mapping[str, Any],
    socket_name: Any,
    direction: str,
    here: str,
    components: Mapping[tuple[str, int], Mapping[str, Any]],
) -> None:
    identifier, version = ref.get("identifier"), ref.get("version")
    component = components.get((identifier, version))
    if component is None:
        raise ResolutionError(
            "C5", here,
            f"({identifier!r}, {version!r}) is not in the component library")
    socket = _declared_socket(component, socket_name)
    if socket is None or socket.get("direction") != direction:
        raise ResolutionError(
            "C3", here,
            f"{identifier!r} socket {socket_name!r} is not a declared {direction}")


def _declared_socket(
    component: Mapping[str, Any], name: Any,
) -> Mapping[str, Any] | None:
    def walk(items: Sequence[Any]) -> Mapping[str, Any] | None:
        for item in items or ():
            if not isinstance(item, Mapping):
                continue
            if item.get("item") == "panel":
                found = walk(item.get("items", ()))
                if found is not None:
                    return found
            elif item.get("item") == "socket" and item.get("identifier") == name:
                return item
        return None

    return walk(component.get("interface", ()))


def _authored_graph_has_cycle(graph: Mapping[str, Any]) -> bool:
    node_ids = {
        node.get("instance_id")
        for node in graph.get("nodes", ())
        if isinstance(node, Mapping) and node.get("instance_id") is not None
    }
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: set() for node_id in node_ids}
    for edge in graph.get("edges", ()):
        if not isinstance(edge, Mapping):
            continue
        source, target = edge.get("source"), edge.get("target")
        if not isinstance(source, Mapping) or not isinstance(target, Mapping):
            continue
        source_id, target_id = source.get("instance"), target.get("instance")
        if source_id not in node_ids or target_id not in node_ids:
            continue
        if target_id not in outgoing[source_id]:
            outgoing[source_id].add(target_id)
            incoming[target_id] += 1
    ready = [node_id for node_id, count in incoming.items() if count == 0]
    visited = 0
    while ready:
        current = ready.pop()
        visited += 1
        for target in outgoing[current]:
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
    return visited != len(node_ids)


def _declared_sockets(component: Mapping[str, Any]) -> dict[str, str]:
    sockets: dict[str, str] = {}

    def walk(items: Sequence[Any]) -> None:
        for item in items or ():
            if not isinstance(item, Mapping):
                continue
            if item.get("item") == "panel":
                walk(item.get("items", ()))
            elif item.get("item") == "socket":
                sockets[item.get("identifier")] = item.get("direction")

    walk(component.get("interface", ()))
    return sockets


@dataclass
class _Ports:
    """How a graph's interface sockets attach to the nodes inside it."""

    inputs: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    outputs: dict[str, tuple[str, str]] = field(default_factory=dict)


@dataclass
class _Pending:
    """A node before its cache identity and warmup are known."""

    instance_id: str
    path: tuple[str, ...]
    definition: tuple[str, int]
    body_ref: str
    params: dict[str, Any]
    domain: dict[str, str] | None
    spec: KernelSpec
    derived_from: str | None
    component: Mapping[str, Any]


class _Context:
    def __init__(self, library: Library) -> None:
        self.library = library
        self.nodes: list[_Pending] = []
        self.edges: list[ResolvedEdge] = []
        self.versions: set[tuple[str, int]] = set()
        self.components: list[ResolvedComponent] = []
        self.active_graph_bodies: set[str] = set()
        # Wired from one level up, so no ResolvedEdge records them; F8 has to
        # be told about them separately.
        self.interface_bound: set[tuple[str, str]] = set()
        self.claimed_targets: set[tuple[str, str]] = set()


def _expand(graph: Mapping[str, Any], path: tuple[str, ...],
            params_env: Mapping[str, Any], domain: Mapping[str, str] | None,
            ctx: _Context) -> _Ports:
    """Expand one graph in place, returning how its interface attaches inside."""
    _check_graph_boundaries(graph, _authored_graph(path), ctx.library.components)
    ports = _Ports()
    local: dict[str, Any] = {}

    for node in graph.get("nodes", ()):
        instance = node.get("instance_id")
        ref = node.get("component") or {}
        identifier, version = ref.get("identifier"), ref.get("version")
        here = _authored(path, instance)

        if identifier in BOUNDARY_IDENTIFIERS:
            local[instance] = (identifier, None)
            continue

        component = ctx.library.components.get((identifier, version))
        if component is None:
            raise ResolutionError(
                "C5", here,
                f"({identifier!r}, {version!r}) is not in the library")
        ctx.versions.add((identifier, version))

        node_domain = _merge_domain(domain, node.get("domain"))
        node_params = _bind(component, node.get("overrides") or {}, params_env, here, ctx)
        child_path = path + (instance,)
        ctx.components.append(ResolvedComponent(
            node_path=_join(child_path),
            definition=(component["identifier"], component["version"]),
            body_ref=component["body"]["ref"],
            params=MappingProxyType(dict(node_params)),
        ))

        if _body_kind(component, here) == "graph":
            local[instance] = ("sub", _expand_component_body(
                component, child_path, node_params, node_domain, ctx))
        else:
            _emit_leaf(component, child_path, node_params, node_domain, ctx, here, None)
            local[instance] = ("leaf", _join(child_path))

    for i, edge in enumerate(graph.get("edges", ())):
        _wire(edge, f"{_authored_graph(path)}.edges[{i}]", local, path, ports, ctx)

    return ports


def _expand_component_body(component: Mapping[str, Any], path: tuple[str, ...],
                           params: Mapping[str, Any], domain: Mapping[str, str] | None,
                           ctx: _Context) -> _Ports:
    """Expand a component whose body is a graph, or emit it if it is a kernel."""
    here = _authored_graph(path)
    if _body_kind(component, here) == "kernel":
        _emit_leaf(component, path or (component["identifier"],), params, domain,
                   ctx, here, None)
        return _Ports()

    ref = component["body"]["ref"]
    if ref in ctx.active_graph_bodies:
        raise ResolutionError(
            "C10", here,
            f"graph component recursion repeats body {ref}")
    body = ctx.library.bodies.get(ref)
    if body is None:
        raise ResolutionError("C5", here,
                              f"the body {ref} of {component['identifier']!r} "
                              "is not in the library")
    validate_graph_component_body(component, body, ctx.library.components, here)
    ctx.active_graph_bodies.add(ref)
    try:
        return _expand(body, path, params, domain, ctx)
    finally:
        ctx.active_graph_bodies.remove(ref)


def _emit_leaf(component: Mapping[str, Any], path: tuple[str, ...],
               params: Mapping[str, Any], domain: Mapping[str, str] | None,
               ctx: _Context, here: str, derived_from: str | None) -> None:
    ref = component["body"]["ref"]
    spec = ctx.library.kernels.get(ref)
    if spec is None:
        raise ResolutionError(
            "C10", here,
            f"no kernel is registered at {ref} for {component['identifier']!r}; "
            "warmup, purity and cache identity are all unknown")
    ctx.nodes.append(_Pending(
        instance_id=_join(path),
        path=path,
        definition=(component["identifier"], component["version"]),
        body_ref=ref,
        params=dict(params),
        domain=dict(domain) if domain else None,
        spec=spec,
        derived_from=derived_from,
        component=component,
    ))


def _bind(component: Mapping[str, Any], overrides: Mapping[str, Any],
          params_env: Mapping[str, Any], here: str, ctx: _Context) -> dict[str, Any]:
    """Declared defaults, then overrides. F10: overrides carry values only."""
    params = _declared_defaults(component)

    for name, value in overrides.items():
        if name not in params:
            raise ResolutionError(
                "C3", f"{here}.overrides.{name}",
                f"{component.get('identifier')!r} declares no parameter {name!r}; "
                "an override that binds to nothing changes the specification's meaning")
        if isinstance(value, list):
            raise ResolutionError(
                "C14", f"{here}.overrides.{name}",
                "an override is one value, not a set of candidates; sweeping is "
                "the searcher's job and never part of a component's contract")
        if is_parameter_reference(value):
            source = value["param_ref"]
            if source not in params_env:
                raise ResolutionError(
                    "C6", f"{here}.overrides.{name}",
                    f"{source!r} is not a parameter of the enclosing component; "
                    "resolution introduces no state the specification does not carry")
            params[name] = params_env[source]
        else:
            params[name] = value

    return params


def _declared_defaults(component: Mapping[str, Any]) -> dict[str, Any]:
    """F4 — the interface is a recursive tree; defaults come from all of it."""
    out: dict[str, Any] = {}

    def walk(items: Sequence[Any]) -> None:
        for item in items or ():
            if not isinstance(item, Mapping):
                continue
            if item.get("item") == "panel":
                walk(item.get("items", ()))
            elif item.get("item") == "parameter":
                out[item["identifier"]] = item.get("default")

    walk(component.get("interface", ()))
    return out


def _wire(edge: Mapping[str, Any], here: str, local: dict, path: tuple[str, ...],
          ports: _Ports, ctx: _Context) -> None:
    source = edge.get("source") or {}
    target = edge.get("target") or {}
    producer = _producer(source, here + ".source", local)
    consumers = _consumers(target, here + ".target", local)

    from_interface = producer[0] is _INTERFACE
    to_interface = any(c[0] is _INTERFACE for c in consumers)

    if from_interface and to_interface:
        raise ResolutionError(
            "C3", here,
            "an edge straight from this graph's input to its output has no "
            "component to resolve; express the pass-through as a component")

    if from_interface:
        ports.inputs.setdefault(producer[1], []).extend(consumers)
        ctx.interface_bound.update(consumers)
        return
    if to_interface:
        output = consumers[0][1]
        if output in ports.outputs:
            raise ResolutionError(
                "C3", here,
                f"graph output {output!r} has more than one producer")
        ports.outputs[output] = producer
        return

    for consumer in consumers:
        _claim_target(consumer, here, ctx)
        ctx.edges.append(ResolvedEdge(source=producer, target=consumer, declared_in=path))


def _claim_target(target: tuple[Any, str], here: str, ctx: _Context) -> None:
    if target in ctx.claimed_targets:
        raise ResolutionError(
            "C3", here,
            f"target {target[0]}.{target[1]} has more than one incoming edge")
    ctx.claimed_targets.add(target)


_INTERFACE = object()


def _producer(ref: Mapping[str, Any], here: str, local: dict) -> tuple[Any, str]:
    instance, socket = ref.get("instance"), ref.get("socket")
    entry = _lookup(instance, here, local)
    if entry[0] == BOUNDARY_INPUT:
        return (_INTERFACE, socket)
    if entry[0] == BOUNDARY_OUTPUT:
        raise ResolutionError("C3", here, "a graph's output boundary produces nothing")
    if entry[0] == "leaf":
        return (entry[1], socket)
    produced = entry[1].outputs.get(socket)
    if produced is None:
        raise ResolutionError(
            "C3", here,
            f"nothing inside {instance!r} produces the interface output {socket!r}")
    return produced


def _consumers(ref: Mapping[str, Any], here: str, local: dict) -> list[tuple[Any, str]]:
    instance, socket = ref.get("instance"), ref.get("socket")
    entry = _lookup(instance, here, local)
    if entry[0] == BOUNDARY_OUTPUT:
        return [(_INTERFACE, socket)]
    if entry[0] == BOUNDARY_INPUT:
        raise ResolutionError("C3", here, "a graph's input boundary consumes nothing")
    if entry[0] == "leaf":
        return [(entry[1], socket)]
    consumed = entry[1].inputs.get(socket)
    if not consumed:
        raise ResolutionError(
            "C3", here,
            f"nothing inside {instance!r} consumes the interface input {socket!r}")
    return list(consumed)


def _lookup(instance: Any, here: str, local: dict):
    entry = local.get(instance)
    if entry is None:
        raise ResolutionError("C3", here, f"{instance!r} is not a node in this graph")
    return entry


def _apply_default_sources(ctx: _Context) -> None:
    """Insert the source an unwired input declares (F8).

    Runs once, after the whole specification is expanded: a nested node's input
    is wired by an edge in the enclosing graph, so a per-graph pass would fill
    sockets the author wired a level up.
    """
    wired = {(e.target[0], e.target[1]) for e in ctx.edges} | ctx.interface_bound

    for pending in list(ctx.nodes):
        for socket in _input_sockets(pending.component):
            default = socket.get("default_source")
            if not default or (pending.instance_id, socket["identifier"]) in wired:
                continue
            here = f"{pending.instance_id}.{socket['identifier']}"
            src_ref = default.get("component") or {}
            source = ctx.library.components.get(
                (src_ref.get("identifier"), src_ref.get("version")))
            if source is None:
                raise ResolutionError(
                    "C5", here,
                    f"the default source ({src_ref.get('identifier')!r}, "
                    f"{src_ref.get('version')!r}) is not in the library")
            if _body_kind(source, here) != "kernel":
                raise ResolutionError(
                    "C3", here,
                    "a default source must be a leaf component; a subgraph "
                    "default would expand into nodes the author never placed")
            ctx.versions.add((src_ref["identifier"], src_ref["version"]))

            derived_path = pending.path + (socket["identifier"] + DEFAULT_SOURCE_SUFFIX,)
            source_params = _declared_defaults(source)
            ctx.components.append(ResolvedComponent(
                node_path=_join(derived_path),
                definition=(source["identifier"], source["version"]),
                body_ref=source["body"]["ref"],
                params=MappingProxyType(dict(source_params)),
            ))
            _emit_leaf(source, derived_path, source_params, None, ctx, here,
                       derived_from=here)
            ctx.edges.append(ResolvedEdge(
                source=(_join(derived_path), default["socket"]),
                target=(pending.instance_id, socket["identifier"]),
                declared_in=pending.path,
                derived=True,
            ))


def _input_sockets(component: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []

    def walk(items):
        for item in items or ():
            if not isinstance(item, Mapping):
                continue
            if item.get("item") == "panel":
                walk(item.get("items", ()))
            elif item.get("item") == "socket" and item.get("direction") == "input":
                out.append(item)

    walk(component.get("interface", ()))
    return out


def _finish(ctx: _Context) -> tuple[ResolvedNode, ...]:
    order = _topological(ctx)
    upstream: dict[str, list[tuple[str, str]]] = {}
    for edge in ctx.edges:
        upstream.setdefault(edge.target[0], []).append((edge.target[1], edge.source[0]))

    by_id = {n.instance_id: n for n in ctx.nodes}
    resolved: dict[str, ResolvedNode] = {}

    for instance_id in order:
        pending = by_id[instance_id]
        feeds = sorted(upstream.get(instance_id, ()))

        # C10: a node's own share is derived from *this node's* bound params,
        # not the component's defaults.
        own = check_warmup(pending.spec.warmup_for(pending.params),
                           f"{pending.definition[0]} at {pending.instance_id}")
        warmup = own + max(
            (resolved[src].warmup for _, src in feeds if src in resolved), default=0)

        identity: dict[str, Any] = {
            "definition": list(pending.definition),
            "params": pending.params,
            "domain": pending.domain,
        }
        if pending.spec.cache_identity == "declared":
            identity["declared"] = pending.spec.cache_key
        else:
            identity["upstream"] = [
                [socket, resolved[src].cache_id] for socket, src in feeds
                if src in resolved
            ]

        resolved[instance_id] = ResolvedNode(
            instance_id=pending.instance_id,
            path=pending.path,
            definition=pending.definition,
            body_ref=pending.body_ref,
            params=MappingProxyType(dict(pending.params)),
            domain=MappingProxyType(dict(pending.domain)) if pending.domain else None,
            warmup=warmup,
            purity=pending.spec.purity,
            cache_id=content_address(identity),
            causal=pending.spec.causal,
            derived_from=pending.derived_from,
        )

    # Document order, not topological: visit order must not leak into the
    # resolved node list (C1).
    return tuple(resolved[n.instance_id] for n in ctx.nodes)


def _topological(ctx: _Context) -> list[str]:
    return topological_order([n.instance_id for n in ctx.nodes], ctx.edges)


def topological_order(ids: Sequence[str],
                      edges: Sequence[ResolvedEdge]) -> list[str]:
    """Dependency order over `ids`, deterministically.

    Public because the runtime needs the same order — a second implementation
    would drift. Ties break on the specification's node order.
    """
    incoming: dict[str, set[str]] = {i: set() for i in ids}
    outgoing: dict[str, list[str]] = {i: [] for i in ids}
    for edge in edges:
        src, tgt = edge.source[0], edge.target[0]
        if src in incoming and tgt in incoming and src != tgt:
            if tgt not in outgoing[src]:
                outgoing[src].append(tgt)
                incoming[tgt].add(src)

    ready = [i for i in ids if not incoming[i]]
    order: list[str] = []
    while ready:
        ready.sort(key=list(ids).index)
        current = ready.pop(0)
        order.append(current)
        for nxt in outgoing[current]:
            incoming[nxt].discard(current)
            if not incoming[nxt]:
                ready.append(nxt)

    if len(order) != len(ids):
        cycle = sorted(set(ids) - set(order))
        raise ResolutionError("C10", "$", f"the graph has a cycle through {cycle}")
    return order


def _body_kind(component: Mapping[str, Any], here: str) -> str:
    body = component.get("body")
    if not isinstance(body, Mapping) or body.get("body") not in ("kernel", "graph"):
        raise ResolutionError("C3", here,
                              f"{component.get('identifier')!r} declares no usable body")
    return body["body"]


def _merge_domain(inherited: Mapping[str, str] | None,
                  pinned: Mapping[str, str] | None) -> dict[str, str] | None:
    if not inherited and not pinned:
        return None
    return {**(inherited or {}), **(pinned or {})}


def _join(path: tuple[str, ...]) -> str:
    return PATH_SEPARATOR.join(path)


def _authored(path: tuple[str, ...], instance: Any) -> str:
    """C4 — diagnostics speak the authored graph's vocabulary."""
    return _join(path + (str(instance),)) or str(instance)


def _authored_graph(path: tuple[str, ...]) -> str:
    return _join(path) or "$"
