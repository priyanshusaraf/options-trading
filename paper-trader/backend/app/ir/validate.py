"""
RFC 0001 §3 — the validator.

Turns fourteen paragraphs of normative prose into a function. `validate()`
returns a list of `Violation`s, each naming the clause it comes from, so a
failure reads as "F7 at nodes[0].wire_type.value" rather than as a schema
error about a key.

**What this module does not do.** Three of F7's guarantees — that an edge's two
endpoints match exactly on value, structure and domain — cannot be checked from
a single artefact, because a node's socket types live in the *component* it
references, not in the graph. Pass a `library` to check them. Without one they
are reported by `unchecked_clauses()` rather than silently passing: an
unchecked clause that looks like a passing clause is how a validator lies.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.ir.schema import (
    ARTEFACT_KINDS,
    BODY_KEYS,
    BODY_KINDS,
    COMPONENT_KEYS,
    COMPONENT_REF_KEYS,
    DOMAIN_AXES,
    EDGE_KEYS,
    GRAPH_KEYS,
    GROUP_KEYS,
    INTERFACE_ITEMS,
    KINDS,
    NODE_KEYS,
    SOCKET_DIRECTIONS,
    SOCKET_REF_KEYS,
    STRUCTURE_TYPES,
    SUPPORTED_FORMAT_VERSION,
    VALUE_TYPES,
    WIRE_TYPE_KEYS,
    is_content_address,
    is_secret_reference,
)

# F1–F13 are checked here. F14 binds experiments and findings to the versions
# that produced them; the IR grammar has no experiment artefact, so there is
# nothing for this module to validate. Recorded, not skipped.
ENFORCED_CLAUSES = frozenset(f"F{n}" for n in range(1, 14))
UNENFORCEABLE_CLAUSES = frozenset({"F14"})

# Checkable only with a component library — see the module docstring.
LIBRARY_DEPENDENT_CLAUSES = frozenset({"F7"})


@dataclass(frozen=True)
class Violation:
    clause: str
    path: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - diagnostics only
        return f"{self.clause} at {self.path}: {self.message}"


class _Report:
    def __init__(self) -> None:
        self.violations: list[Violation] = []

    def add(self, clause: str, path: str, message: str) -> None:
        self.violations.append(Violation(clause, path, message))

    def unknown_keys(self, obj: Mapping[str, Any], allowed: Iterable[str],
                     path: str, clause: str) -> None:
        for key in sorted(set(obj) - set(allowed)):
            self.add(clause, f"{path}.{key}", "not in the grammar")


# ── entry points ──────────────────────────────────────────────────────────

def validate(artefact: Any, library: Mapping[tuple[str, int], Any] | None = None
             ) -> list[Violation]:
    """Return every §3 violation in `artefact`, in document order."""
    r = _Report()

    if not isinstance(artefact, Mapping):
        r.add("F1", "$", "an artefact must be a mapping")
        return r.violations

    # F1 first, and exclusively. "A reader MUST reject an artefact whose
    # format_version it does not understand, and MUST NOT attempt to interpret
    # it partially" — so an unreadable envelope returns here and reports
    # nothing further. Anything else would be partial interpretation.
    if "format_version" not in artefact:
        r.add("F1", "$.format_version", "missing")
    elif artefact["format_version"] != SUPPORTED_FORMAT_VERSION:
        r.add("F1", "$.format_version",
              f"{artefact['format_version']!r} is not understood "
              f"(this reader knows {SUPPORTED_FORMAT_VERSION})")
        return r.violations

    kind = artefact.get("kind")
    if "kind" not in artefact:
        r.add("F1", "$.kind", "missing")
    elif kind not in ARTEFACT_KINDS:
        r.add("F1", "$.kind", f"{kind!r} is not one of {ARTEFACT_KINDS}")

    if r.violations and "kind" != artefact.get("kind", "kind") and kind not in ARTEFACT_KINDS:
        return r.violations

    _identity(r, artefact)

    if kind == "component":
        r.unknown_keys(artefact, COMPONENT_KEYS, "$", "F13")
        _interface(r, artefact, "$")
        _body(r, artefact)
    elif kind == "graph":
        r.unknown_keys(artefact, GRAPH_KEYS, "$", "F13")
        _interface(r, artefact, "$")
        _graph(r, artefact, library)

    return r.violations


def clauses_violated(artefact: Any,
                     library: Mapping[tuple[str, int], Any] | None = None) -> set[str]:
    """The set of clause names `artefact` violates. Convenient for assertions."""
    return {v.clause for v in validate(artefact, library)}


def unchecked_clauses(library: Mapping[tuple[str, int], Any] | None = None) -> set[str]:
    """Clauses this run could not check, and therefore did not pass."""
    unchecked = set(UNENFORCEABLE_CLAUSES)
    if library is None:
        unchecked |= set(LIBRARY_DEPENDENT_CLAUSES)
    return unchecked


# ── F2 / F3 — identity ────────────────────────────────────────────────────

def _identity(r: _Report, art: Mapping[str, Any]) -> None:
    ident = art.get("identifier")
    if not isinstance(ident, str) or not ident:
        r.add("F2", "$.identifier", "must be a non-empty immutable identifier")

    if "version" not in art:
        r.add("F2", "$.version", "missing")
    elif not isinstance(art["version"], int) or isinstance(art["version"], bool) \
            or art["version"] < 1:
        r.add("F2", "$.version", "must be an integer >= 1")

    name = art.get("display_name")
    if not isinstance(name, str) or not name:
        r.add("F2", "$.display_name",
              "must be present and separate from the identifier")

    if "parent_version" in art:
        parent = art["parent_version"]
        if not isinstance(parent, int) or isinstance(parent, bool) or parent < 1:
            r.add("F3", "$.parent_version", "must be an integer >= 1 when present")


# ── F2 — body ─────────────────────────────────────────────────────────────

def _body(r: _Report, art: Mapping[str, Any]) -> None:
    body = art.get("body")
    if not isinstance(body, Mapping):
        r.add("F2", "$.body", "a component must declare a body")
        return
    r.unknown_keys(body, BODY_KEYS, "$.body", "F13")
    if body.get("body") not in BODY_KINDS:
        r.add("F2", "$.body.body", f"must be one of {BODY_KINDS}")
    if not is_content_address(body.get("ref")):
        r.add("F2", "$.body.ref",
              "the body must be content-addressed (sha256:<64 hex>); "
              "a name is not an address")


# ── F4 / F5 / F7 / F8 — the declared interface ────────────────────────────

def _interface(r: _Report, art: Mapping[str, Any], path: str) -> None:
    if "interface" not in art:
        r.add("F4", f"{path}.interface",
              "the interface must be declared, never inferred")
        return
    items = art["interface"]
    if not isinstance(items, list):
        r.add("F4", f"{path}.interface", "must be a list of interface items")
        return
    _interface_items(r, items, f"{path}.interface")


def _interface_items(r: _Report, items: list, path: str) -> None:
    for i, item in enumerate(items):
        here = f"{path}[{i}]"
        if not isinstance(item, Mapping):
            r.add("F4", here, "must be a mapping")
            continue
        kind = item.get("item")
        if kind not in INTERFACE_ITEMS:
            r.add("F4", f"{here}.item",
                  f"{kind!r} is not a panel, socket or parameter")
            continue
        r.unknown_keys(item, INTERFACE_ITEMS[kind], here, "F13")
        if not isinstance(item.get("identifier"), str) or not item.get("identifier"):
            r.add("F2", f"{here}.identifier", "must be a non-empty identifier")
        if not isinstance(item.get("display_name"), str) or not item.get("display_name"):
            r.add("F2", f"{here}.display_name", "must be present")

        if kind == "panel":
            # F4 — the interface is a recursive tree, so checking must recurse.
            nested = item.get("items", [])
            if not isinstance(nested, list):
                r.add("F4", f"{here}.items", "a panel's items must be a list")
            else:
                _interface_items(r, nested, f"{here}.items")
        elif kind == "socket":
            _socket(r, item, here)
        elif kind == "parameter":
            _parameter(r, item, here)


def _socket(r: _Report, item: Mapping[str, Any], path: str) -> None:
    direction = item.get("direction")
    if direction not in SOCKET_DIRECTIONS:
        r.add("F4", f"{path}.direction", f"must be one of {SOCKET_DIRECTIONS}")
    _wire_type(r, item.get("wire_type"), f"{path}.wire_type")

    if "default_source" in item and direction != "input":
        # F8 grants default *sources* to inputs. An output does not have one.
        r.add("F8", f"{path}.default_source",
              "only an input may declare a default source")


def _parameter(r: _Report, item: Mapping[str, Any], path: str) -> None:
    kind = item.get("kind")
    if kind not in KINDS:
        r.add("F5", f"{path}.kind",
              f"{kind!r} is not in the closed vocabulary {KINDS}")
    if "default" not in item:
        r.add("F5", f"{path}.default", "a parameter must carry a default")
        return
    if kind == "secret" and not is_secret_reference(item["default"]):
        # F6 — "A secret value MUST NOT appear in any artefact, under any
        # circumstances." The safe path is the only representable one.
        r.add("F6", f"{path}.default",
              "a secret's value must be a reference ({'secret_ref': ...}), never a literal")


def _wire_type(r: _Report, wt: Any, path: str) -> None:
    if not isinstance(wt, Mapping):
        r.add("F7", path, "a socket must declare a wire type")
        return
    r.unknown_keys(wt, WIRE_TYPE_KEYS, path, "F13")

    if "value" not in wt:
        r.add("F7", f"{path}.value", "missing")
    elif wt["value"] not in VALUE_TYPES:
        # No wildcard, no overlap matching, no comma-separated strings.
        r.add("F7", f"{path}.value",
              f"{wt['value']!r} is not in the closed set {VALUE_TYPES}")

    if "structure" not in wt:
        r.add("F7", f"{path}.structure", "missing")
    elif wt["structure"] not in STRUCTURE_TYPES:
        r.add("F7", f"{path}.structure", f"must be one of {STRUCTURE_TYPES}")

    if "domain" not in wt:
        r.add("F7", f"{path}.domain", "missing")
    elif not isinstance(wt["domain"], Mapping):
        r.add("F7", f"{path}.domain", "must declare an instrument and a timeframe")
    else:
        for axis in DOMAIN_AXES:
            if not wt["domain"].get(axis):
                r.add("F7", f"{path}.domain.{axis}", "missing")
        r.unknown_keys(wt["domain"], DOMAIN_AXES, f"{path}.domain", "F13")


# ── F9 – F12 — the graph ──────────────────────────────────────────────────

def _graph(r: _Report, art: Mapping[str, Any],
           library: Mapping[tuple[str, int], Any] | None) -> None:
    for key in ("nodes", "edges"):
        if key not in art:
            r.add("F9", f"$.{key}", "a graph is nodes and edges")

    nodes = art.get("nodes")
    instances: dict[str, Mapping[str, Any]] = {}
    if isinstance(nodes, list):
        for i, node in enumerate(nodes):
            _node(r, node, f"$.nodes[{i}]", instances)
    elif nodes is not None:
        r.add("F9", "$.nodes", "must be a list")

    edges = art.get("edges")
    if isinstance(edges, list):
        for i, edge in enumerate(edges):
            _edge(r, edge, f"$.edges[{i}]", instances, art, library)
    elif edges is not None:
        r.add("F9", "$.edges", "must be a list")

    groups = art.get("groups", [])
    if isinstance(groups, list):
        for i, group in enumerate(groups):
            _group(r, group, f"$.groups[{i}]", instances)
    else:
        r.add("F12", "$.groups", "must be a list")


def _node(r: _Report, node: Any, path: str, instances: dict) -> None:
    if not isinstance(node, Mapping):
        r.add("F9", path, "a node must be a mapping")
        return
    # F13 — the grammar has nowhere to put a coordinate, which is what keeps
    # dragging a node from changing its hash.
    r.unknown_keys(node, NODE_KEYS, path, "F13")

    iid = node.get("instance_id")
    if not isinstance(iid, str) or not iid:
        r.add("F9", f"{path}.instance_id", "a node must carry an instance identifier")
    elif iid in instances:
        r.add("F9", f"{path}.instance_id", f"{iid!r} is already used in this graph")
    else:
        instances[iid] = node

    ref = node.get("component")
    if not isinstance(ref, Mapping):
        r.add("F9", f"{path}.component", "a node must carry a component reference")
    else:
        _component_ref(r, ref, f"{path}.component")

    _overrides(r, node, path)


def _component_ref(r: _Report, ref: Mapping[str, Any], path: str) -> None:
    if "display_name" in ref:
        # F2 — the display name "MUST NOT be referenced by anything". A
        # reference that carries one is a rename waiting to break every graph.
        r.add("F2", f"{path}.display_name",
              "a reference is by identifier; a display name is never referenced")
    for key in sorted(set(ref) - COMPONENT_REF_KEYS - {"display_name"}):
        # F11 — anything else here is a definition being inlined.
        r.add("F11", f"{path}.{key}",
              "nesting is by reference; a subgraph must not be inlined")
    if not isinstance(ref.get("identifier"), str) or not ref.get("identifier"):
        r.add("F11", f"{path}.identifier", "a reference must name an identifier")
    if not isinstance(ref.get("version"), int) or isinstance(ref.get("version"), bool):
        r.add("F11", f"{path}.version",
              "a reference must be (identifier, version); an unversioned "
              "reference cannot be resolved reproducibly")


def _overrides(r: _Report, node: Mapping[str, Any], path: str) -> None:
    overrides = node.get("overrides", {})
    if not isinstance(overrides, Mapping):
        r.add("F10", f"{path}.overrides", "must be a mapping of identifier to value")
        return
    secret_params = set(node.get("secret_params") or ())
    for name, value in overrides.items():
        here = f"{path}.overrides.{name}"
        if isinstance(value, Mapping) and not is_secret_reference(value):
            # F10 — "An override MUST carry a value only. It MUST NOT carry a
            # kind, bounds, or a display name."
            r.add("F10", here,
                  "an override carries a value only, never a kind, bounds or display name")
        if name in secret_params and not is_secret_reference(value):
            r.add("F6", here, "a secret override must be a reference, never a literal")


def _edge(r: _Report, edge: Any, path: str, instances: dict,
          art: Mapping[str, Any], library: Mapping[tuple[str, int], Any] | None) -> None:
    if not isinstance(edge, Mapping):
        r.add("F9", path, "an edge must be a mapping")
        return
    r.unknown_keys(edge, EDGE_KEYS, path, "F13")

    ends = {}
    for end in ("source", "target"):
        ref = edge.get(end)
        if not isinstance(ref, Mapping):
            r.add("F9", f"{path}.{end}", "an edge end must be a socket reference")
            continue
        r.unknown_keys(ref, SOCKET_REF_KEYS, f"{path}.{end}", "F13")
        instance = ref.get("instance")
        if instance not in instances:
            r.add("F9", f"{path}.{end}.instance",
                  f"{instance!r} is not a node in this graph")
        elif not ref.get("socket"):
            r.add("F9", f"{path}.{end}.socket", "missing")
        else:
            ends[end] = (instances[instance], ref["socket"])

    if library is not None and len(ends) == 2:
        _edge_types(r, ends, path, library)


def _edge_types(r: _Report, ends: dict, path: str,
                library: Mapping[tuple[str, int], Any]) -> None:
    """F7 — exact match on all three axes. No coercion, no overlap."""
    resolved = {}
    for end, (node, socket_name) in ends.items():
        ref = node.get("component", {})
        component = library.get((ref.get("identifier"), ref.get("version")))
        if component is None:
            continue
        wt = _socket_wire_type(component, socket_name)
        if wt is None:
            r.add("F9", f"{path}.{end}.socket",
                  f"{socket_name!r} is not a socket on "
                  f"{ref.get('identifier')!r} v{ref.get('version')}")
            continue
        # A node may pin the domain it runs in; the socket's declared domain is
        # the default. This is what makes A.5's two EMAs different wire types.
        if node.get("domain"):
            wt = {**wt, "domain": {**wt["domain"], **node["domain"]}}
        resolved[end] = wt

    if len(resolved) != 2:
        return
    src, tgt = resolved["source"], resolved["target"]
    for axis in ("value", "structure"):
        if src.get(axis) != tgt.get(axis):
            r.add("F7", f"{path}.{axis}",
                  f"{src.get(axis)!r} does not match {tgt.get(axis)!r}; "
                  "wire types are exact-matched")
    for axis in DOMAIN_AXES:
        if src.get("domain", {}).get(axis) != tgt.get("domain", {}).get(axis):
            r.add("F7", f"{path}.domain.{axis}",
                  f"{src.get('domain', {}).get(axis)!r} does not match "
                  f"{tgt.get('domain', {}).get(axis)!r}; the domain is part of the type")


def _socket_wire_type(component: Mapping[str, Any], name: str) -> Mapping[str, Any] | None:
    def walk(items):
        for item in items or ():
            if not isinstance(item, Mapping):
                continue
            if item.get("item") == "panel":
                found = walk(item.get("items"))
                if found is not None:
                    return found
            elif item.get("item") == "socket" and item.get("identifier") == name:
                return item.get("wire_type")
        return None

    return walk(component.get("interface"))


def _group(r: _Report, group: Any, path: str, instances: dict) -> None:
    if not isinstance(group, Mapping):
        r.add("F12", path, "a group must be a mapping")
        return
    # F12 — "A group MUST NOT be versionable or publishable." If tidying were
    # also the reuse unit, every cosmetic box would fill the version history.
    for key in sorted(set(group) - GROUP_KEYS):
        r.add("F12", f"{path}.{key}",
              "visual grouping is not semantic reuse; a group is neither "
              "versionable nor publishable")
    if not group.get("identifier"):
        r.add("F12", f"{path}.identifier", "missing")
    if not group.get("display_name"):
        r.add("F12", f"{path}.display_name", "missing")
    members = group.get("members")
    if not isinstance(members, list):
        r.add("F12", f"{path}.members", "must be a list of instance identifiers")
        return
    for i, member in enumerate(members):
        if member not in instances:
            r.add("F12", f"{path}.members[{i}]",
                  f"{member!r} is not a node in this graph")
