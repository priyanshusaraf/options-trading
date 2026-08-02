"""
RFC 0001 §4 — resolution.

    "Resolution — the stage that transforms a specification into a fully bound
    executable graph, resolving component references, versions, kernels and
    dependencies."

This module is that stage. It is the only one: C12 requires research and live to
share **one** resolution, and the way to make that structural rather than tested
is for there to be a single function and no second implementation to drift from
it. `resolve()` takes a specification and a library, and nothing else — in
particular it takes no plane, mode, or live flag, because a resolution that can
be told which plane it is running in is a resolution that can differ between
them.

The RFC prescribes no mechanism (§1.3): "graph rewriting, lazy expansion,
canonicalisation, optimisation passes, or a mechanism not yet invented are all
conforming, provided the observable properties in §4 hold." What is implemented
here is eager lowering — deterministic structural expansion of nested references
— because it is the smallest thing that exhibits those properties, and because
Blender, the most mature node system studied, lowers.

**Two conventions live here rather than in §3, deliberately.**

*Boundary nodes.* A subgraph body needs to say which of its internal nodes an
interface socket connects to. That is expressed with two reserved component
identifiers, `graph.input` and `graph.output`, which resolution elides and
splices through. No grammar construct was added: a reserved identifier is a
value, and §3 stays the size it was. Blender, Node-RED and ComfyUI all reached
the same shape.

*Instance identifiers.* C7 requires them to derive from the instance path. They
are the path, joined by `/` — `n_fast/n_smooth`. There is no counter and no
clock anywhere in this file, which is what makes re-resolution byte-identical.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from app.ir.hashing import content_address
from app.ir.kernels import KernelSpec, check_warmup
from app.ir.schema import is_parameter_reference

# The two reserved identifiers. A body graph wires its interface through these;
# resolution removes them, so no resolved graph ever contains one.
BOUNDARY_INPUT = "graph.input"
BOUNDARY_OUTPUT = "graph.output"
BOUNDARY_IDENTIFIERS = (BOUNDARY_INPUT, BOUNDARY_OUTPUT)

PATH_SEPARATOR = "/"

# C4 — an element resolution inserted, rather than one the author placed, is
# named so it can never be mistaken for authored work in a diagnostic.
DEFAULT_SOURCE_SUFFIX = "@default"


class ResolutionError(Exception):
    """A specification that cannot be resolved, named by the clause it fails.

    The path is the *authored* graph's path (C4): diagnostics speak the
    vocabulary the author wrote, never the resolved graph's.
    """

    def __init__(self, clause: str, path: str, message: str) -> None:
        super().__init__(f"{clause} at {path}: {message}")
        self.clause = clause
        self.path = path
        self.message = message


# ── the library ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Library:
    """Everything resolution is allowed to read.

    C2 (no side effects) and C6 (no hidden state) are structural here: this is
    the whole world. Resolution opens no file, reads no clock, and consults no
    global, so a resolved graph is a function of `(spec, library)` and of
    nothing else.
    """

    components: Mapping[tuple[str, int], Mapping[str, Any]] = field(default_factory=dict)
    bodies: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    kernels: Mapping[str, KernelSpec] = field(default_factory=dict)


# ── the resolved graph ────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResolvedNode:
    """One leaf of the resolved graph.

    `path` and `definition` are C4's back-references: where the author put it,
    and what it was expanded from. `instance_id` is C7's — the path, joined.
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
    derived_from: str | None = None

    @property
    def authored_root(self) -> str:
        """The authored node this leaf came from — `n_fast`, never `n_fast/n_smooth`."""
        return self.path[0] if self.path else self.instance_id


@dataclass(frozen=True)
class ResolvedEdge:
    source: tuple[str, str]
    target: tuple[str, str]
    declared_in: tuple[str, ...]
    derived: bool = False


@dataclass(frozen=True)
class ResolvedGraph:
    """The output of resolution.

    C3: "Never authored, never edited, never a source of truth." Frozen, with
    read-only mappings inside, so that is a property of the object rather than a
    convention someone remembers.
    """

    identifier: str
    version: int
    nodes: tuple[ResolvedNode, ...]
    edges: tuple[ResolvedEdge, ...]
    versions: tuple[tuple[str, int], ...]
    inputs: Mapping[str, tuple[tuple[str, str], ...]]
    outputs: Mapping[str, tuple[str, str]]

    @property
    def warmup(self) -> int:
        """C10 — the graph's warmup is the deepest chain in it."""
        return max((n.warmup for n in self.nodes), default=0)

    def node(self, instance_id: str) -> ResolvedNode | None:
        for n in self.nodes:
            if n.instance_id == instance_id:
                return n
        return None


# ── the single entry point ────────────────────────────────────────────────

def resolve(spec: Mapping[str, Any], library: Library,
            parameters: Mapping[str, Any] | None = None) -> ResolvedGraph:
    """Resolve `spec` against `library` into a fully bound graph.

    `parameters` supplies values for the specification's own top-level
    parameters — one value each. That is a searcher's job (C14): a searcher
    calls this once per candidate, and the component never learns that a search
    is happening.
    """
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
        # C5 — every resolved (identifier, version) pair, recorded. Sorted so
        # the record is a function of what was resolved, not of visit order.
        versions=tuple(sorted(ctx.versions)),
        inputs=MappingProxyType({k: tuple(v) for k, v in ports.inputs.items()}),
        outputs=MappingProxyType(dict(ports.outputs)),
    )


# ── C15 — publishing a subgraph is a mechanical derivation ────────────────

def publish(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Derive a component-def from a graph-def.

    C15: "Publishing a subgraph as a component MUST be a mechanical derivation
    from its declared interface, introducing no information the interface does
    not already carry." So this function asks no questions and takes no options.
    Everything it writes is copied from the graph or computed from it: the
    interface verbatim, the identity verbatim, and a body that is the graph's
    own content address.

    Returns the component; `body_for(graph)` gives the entry its body needs in
    `Library.bodies`.
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


# ── expansion ─────────────────────────────────────────────────────────────

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
        # Sockets fed by a graph's own interface rather than by an edge. They
        # are wired — the value arrives from one level up — but no ResolvedEdge
        # records them, so F8 has to be told about them separately.
        self.interface_bound: set[tuple[str, str]] = set()


def _expand(graph: Mapping[str, Any], path: tuple[str, ...],
            params_env: Mapping[str, Any], domain: Mapping[str, str] | None,
            ctx: _Context) -> _Ports:
    """Expand one graph in place, returning how its interface attaches inside."""
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
            # C5 — a version identity that cannot be resolved cannot be
            # recorded, and an unversioned resolution is not reproducible.
            raise ResolutionError(
                "C5", here,
                f"({identifier!r}, {version!r}) is not in the library")
        ctx.versions.add((identifier, version))

        node_domain = _merge_domain(domain, node.get("domain"))
        node_params = _bind(component, node.get("overrides") or {}, params_env, here, ctx)
        child_path = path + (instance,)

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
    body = ctx.library.bodies.get(ref)
    if body is None:
        raise ResolutionError("C5", here,
                              f"the body {ref} of {component['identifier']!r} "
                              "is not in the library")
    return _expand(body, path, params, domain, ctx)


def _emit_leaf(component: Mapping[str, Any], path: tuple[str, ...],
               params: Mapping[str, Any], domain: Mapping[str, str] | None,
               ctx: _Context, here: str, derived_from: str | None) -> None:
    ref = component["body"]["ref"]
    spec = ctx.library.kernels.get(ref)
    if spec is None:
        # C10 — warmup is derived per component. A kernel with no registry
        # entry has no warmup to derive, so the graph's warmup would be a guess.
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


# ── parameter binding ─────────────────────────────────────────────────────

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
            # C14 — components compute; searchers search.
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
    """F4 — the interface is a recursive tree, so defaults come from all of it."""
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


# ── wiring ────────────────────────────────────────────────────────────────

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
        ports.outputs[consumers[0][1]] = producer
        return

    for consumer in consumers:
        ctx.edges.append(ResolvedEdge(source=producer, target=consumer, declared_in=path))


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
        # C3 — the authored edge said a value comes out here. If nothing
        # inside produces it, resolution would silently drop the connection.
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


# ── F8 — default input sources, inserted with a back-reference ────────────

def _apply_default_sources(ctx: _Context) -> None:
    """Insert the source an unwired input declares.

    F8: "A graph whose unwired inputs all declare sources MUST be valid." The
    inserted node is a derived element, so C4 applies to it — it carries a
    back-reference naming the socket it was inserted for, and an identifier
    derived from that socket's path rather than from a counter (C7).

    This runs once, after the whole specification is expanded, and not at the
    end of each graph. An input of a nested node is wired by an edge in the
    *enclosing* graph, which does not exist yet while that node's own graph is
    being expanded — inserting per graph would fill sockets the author wired a
    level up.
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
            _emit_leaf(source, derived_path, _declared_defaults(source), None, ctx, here,
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


# ── C8 / C10 — cache identity and warmup, in dependency order ─────────────

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

        # C10 — warmup composes: a node needs its own history plus everything
        # its deepest input needed before it could produce a first value. Its
        # own share is derived from *this node's* bound parameters, so a 200-bar
        # EMA warms up in 200 bars even where the component's default is 50.
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
            # C8 — "MAY be declared per component", for components whose
            # identity genuinely is not their inputs.
            identity["declared"] = pending.spec.cache_key
        else:
            # C8 — transitive by default, so correctness under composition is
            # automatic rather than remembered.
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
            derived_from=pending.derived_from,
        )

    # Document order, not topological order: the resolved graph's node list is
    # a function of the specification, and visit order is an implementation
    # detail that must not leak into it (C1).
    return tuple(resolved[n.instance_id] for n in ctx.nodes)


def _topological(ctx: _Context) -> list[str]:
    return topological_order([n.instance_id for n in ctx.nodes], ctx.edges)


def topological_order(ids: Sequence[str],
                      edges: Sequence[ResolvedEdge]) -> list[str]:
    """Dependency order over `ids`, deterministically.

    Public because the runtime needs the same order and deriving it twice is
    how `candles.py` happened. Ties break on the specification's node order, so
    the result is a function of the input rather than of dict iteration.
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
        # C10 — warmup "MUST compose through the graph", and composition over a
        # cycle is not defined. A value that is its own input has no first bar.
        raise ResolutionError("C10", "$", f"the graph has a cycle through {cycle}")
    return order


# ── small helpers ─────────────────────────────────────────────────────────

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
