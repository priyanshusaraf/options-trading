"""
Authoring a component in Python: interface, version, body address and kernel
declaration from one decorator.

The interface is declared and the function checked against it, never inferred
(F4); the body address is the source's content address (F2); nothing records
provenance (C13). This does not sandbox — that belongs to the kernel registry.
"""
from __future__ import annotations

import inspect
import textwrap
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from app.ir.hashing import content_address
from app.ir.kernels import KernelSpec, kernel_spec
from app.ir.resolve import Library
from app.ir.validate import Violation, validate

FORMAT_VERSION = 1

# A kernel is handed its bound parameters, exact node inputs, and declared
# context. The context channel is explicit even when empty.
KERNEL_SIGNATURE = ("params", "node_inputs", "context_inputs")


class AuthoringError(Exception):
    """A component declaration that would not produce a conforming artefact."""

    def __init__(self, identifier: str, message: str,
                 violations: Sequence[Violation] = ()) -> None:
        detail = "; ".join(str(v) for v in violations)
        super().__init__(f"{identifier}: {message}" + (f" — {detail}" if detail else ""))
        self.identifier = identifier
        self.violations = tuple(violations)


@dataclass(frozen=True)
class AuthoredComponent:
    """A component-def, its kernel declaration, and the function behind it."""

    definition: Mapping[str, Any]
    spec: KernelSpec
    kernel: Callable[..., Mapping[str, Any]]
    # Which of ("inputs", "params") the interface check could not verify because
    # the kernel reaches them dynamically.
    unchecked: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, int]:
        return (self.definition["identifier"], self.definition["version"])

    @property
    def body_ref(self) -> str:
        return self.definition["body"]["ref"]


# ── interface items ───────────────────────────────────────────────────────

def wire(value: str = "float", structure: str = "series", *,
         instrument: str, timeframe: str) -> dict[str, Any]:
    return {"value": value, "structure": structure,
            "domain": {"instrument": instrument, "timeframe": timeframe}}


def socket(identifier: str, direction: str, wire_type: Mapping[str, Any],
           display_name: str | None = None,
           default_source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    item = {"item": "socket", "identifier": identifier,
            "display_name": display_name or identifier,
            "direction": direction, "wire_type": dict(wire_type)}
    if default_source is not None:
        item["default_source"] = dict(default_source)
    return item


def parameter(identifier: str, kind: str, default: Any,
              display_name: str | None = None,
              bounds: Mapping[str, Any] | None = None) -> dict[str, Any]:
    item = {"item": "parameter", "identifier": identifier,
            "display_name": display_name or identifier,
            "kind": kind, "default": default}
    if bounds is not None:
        item["bounds"] = dict(bounds)
    return item


def panel(identifier: str, items: Sequence[Mapping[str, Any]],
          display_name: str | None = None) -> dict[str, Any]:
    return {"item": "panel", "identifier": identifier,
            "display_name": display_name or identifier, "items": list(items)}


# ── the decorator ─────────────────────────────────────────────────────────

def component(identifier: str, *, interface: Sequence[Mapping[str, Any]],
              version: int = 1, display_name: str | None = None,
              parent_version: int | None = None,
              warmup: Any = 0, purity: str = "pure",
              cache_identity: str = "transitive",
              cache_key: str | None = None,
              causal: Any = None,
              closes_over: Any = None) -> Callable[[Callable], AuthoredComponent]:
    """Declare a component whose body is this function.

    Returns an `AuthoredComponent`, not the function. `closes_over` is part of
    the body's content address: a factory-built kernel must supply it, or every
    sibling it produces shares one address.
    """

    def decorate(fn: Callable) -> AuthoredComponent:
        _check_signature(identifier, fn)
        input_name = tuple(inspect.signature(fn).parameters)[1]

        definition: dict[str, Any] = {
            "format_version": FORMAT_VERSION,
            "kind": "component",
            "identifier": identifier,
            "version": version,
            "display_name": display_name or identifier,
            "interface": [dict(item) for item in interface],
            "body": {"body": "kernel",
                     "ref": _body_address(identifier, fn, closes_over)},
        }
        if parent_version is not None:
            definition["parent_version"] = parent_version

        violations = validate(definition)
        if violations:
            raise AuthoringError(identifier, "is not a conforming component", violations)

        unchecked = _check_satisfies_interface(
            identifier, fn, definition["interface"], input_name)

        return AuthoredComponent(
            definition=definition,
            spec=kernel_spec(warmup=warmup, purity=purity,
                             cache_identity=cache_identity, cache_key=cache_key,
                             causal=causal),
            kernel=fn,
            unchecked=unchecked,
        )

    return decorate


def _check_signature(identifier: str, fn: Callable) -> None:
    names = tuple(inspect.signature(fn).parameters)
    valid = len(names) == 3 and names[0] == "params" \
        and names[1] in {"node_inputs", "inputs"} \
        and names[2] == "context_inputs"
    if not valid:
        raise AuthoringError(
            identifier,
            f"a kernel takes exactly {KERNEL_SIGNATURE}, not {names}; it is handed "
            "its bound parameters and its inputs, and nothing that would let it "
            "behave differently depending on where it was used")


def _body_address(identifier: str, fn: Callable, closes_over: Any = None) -> str:
    """F2 — the body, content-addressed.

    Dedented before hashing, so moving a function into or out of a class does
    not by itself mint a new body.
    """
    try:
        source = textwrap.dedent(inspect.getsource(fn))
    except OSError as exc:                                  # pragma: no cover
        raise AuthoringError(
            identifier,
            "has no readable source, so its body cannot be content-addressed") from exc
    return content_address({"kernel": source, "closes_over": closes_over})


def _check_satisfies_interface(identifier: str, fn: Callable,
                               interface: Sequence[Mapping[str, Any]],
                               input_name: str) -> tuple[str, ...]:
    """F4 — the declaration is authoritative; the kernel must satisfy it.

    Statically checkable: the function reads every input and parameter it
    declared, and reads nothing it did not.
    """
    declared_inputs, declared_params, declared_outputs = _declared(interface)
    if not declared_outputs:
        raise AuthoringError(identifier, "declares no output socket")

    try:
        source = textwrap.dedent(inspect.getsource(fn))
    except OSError:                                          # pragma: no cover
        return ("inputs", "params")

    read, dynamic = _subscripts(source, input_name)
    unchecked: list[str] = []
    for kind, logical_kind, declared in (
            (input_name, "inputs", declared_inputs), ("params", "params", declared_params)):
        if kind in dynamic:
            # A syntactic check can conclude nothing here, so say so rather
            # than guess in either direction.
            unchecked.append(logical_kind)
            continue
        used = read.get(kind, set())
        missing = sorted(declared - used)
        extra = sorted(used - declared)
        if missing:
            raise AuthoringError(
                identifier,
                f"declares {kind} {missing} that its kernel never reads; a declared "
                "socket the implementation ignores is a lie in the interface")
        if extra:
            raise AuthoringError(
                identifier,
                f"reads {kind} {extra} it does not declare; an undeclared dependency "
                "is one no graph can wire and no warmup can account for")

    return tuple(unchecked)


def _declared(interface: Sequence[Mapping[str, Any]]
              ) -> tuple[set[str], set[str], set[str]]:
    inputs: set[str] = set()
    params: set[str] = set()
    outputs: set[str] = set()

    def walk(items: Sequence[Mapping[str, Any]]) -> None:
        for item in items:
            if item.get("item") == "panel":
                walk(item.get("items", ()))
            elif item.get("item") == "parameter":
                params.add(item["identifier"])
            elif item.get("item") == "socket":
                (inputs if item.get("direction") == "input" else outputs).add(
                    item["identifier"])

    walk(interface)
    return inputs, params, outputs


def _subscripts(source: str, input_name: str = "node_inputs"
                ) -> tuple[dict[str, set[str]], set[str]]:
    """Which literal keys the source reads out of `inputs` and `params`, and
    which of the two it also reaches *dynamically*.

    A mapping counts as dynamic if it is subscripted with anything but a string
    literal, or used bare — iterated, unpacked, passed on, `.get()`.
    """
    import ast

    tree = ast.parse(source)
    names = {input_name, "params"}
    found: dict[str, set[str]] = {name: set() for name in names}
    dynamic: set[str] = set()

    subscript_bases = {id(node.value) for node in ast.walk(tree)
                       if isinstance(node, ast.Subscript)}

    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
                and node.value.id in names:
            key = node.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                found[node.value.id].add(key.value)
            else:
                dynamic.add(node.value.id)
        elif isinstance(node, ast.Name) and node.id in names \
                and id(node) not in subscript_bases \
                and isinstance(node.ctx, ast.Load):
            dynamic.add(node.id)

    return found, dynamic


# ── a library from authored components ────────────────────────────────────

def library(components: Sequence[AuthoredComponent],
            extra: Library | None = None) -> tuple[Library, dict[str, Callable]]:
    """Build the `(Library, implementations)` pair the resolver and runtime want.

    C13: keyed by body address only, so an authored component is indistinguishable
    from a built-in by the time anything executes.
    """
    seen: dict[tuple[str, int], AuthoredComponent] = {}
    bodies: dict[str, AuthoredComponent] = {}
    for authored in components:
        if authored.key in seen:
            raise AuthoringError(
                authored.key[0],
                f"version {authored.key[1]} is declared twice; an identifier and "
                "version name one body")
        seen[authored.key] = authored

        # Sharing a body is fine (an alias); sharing one while declaring a
        # different kernel is not — the registry is keyed by address, so one
        # would silently win.
        other = bodies.get(authored.body_ref)
        if other is not None and other.spec != authored.spec:
            raise AuthoringError(
                authored.key[0],
                f"shares a body address with {other.key[0]!r} but declares a "
                "different kernel; a kernel built by a factory must pass "
                "`closes_over` so its address reflects what it actually computes")
        bodies.setdefault(authored.body_ref, authored)

    return (
        Library(
            components={**(extra.components if extra else {}),
                        **{c.key: c.definition for c in components}},
            bodies=dict(extra.bodies) if extra else {},
            kernels={**(extra.kernels if extra else {}),
                     **{c.body_ref: c.spec for c in components}},
        ),
        {c.body_ref: c.kernel for c in components},
    )
