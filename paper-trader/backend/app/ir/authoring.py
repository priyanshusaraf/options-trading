"""
Authoring a component in Python.

Until now a kernel was a bare function that someone remembered to put in a dict
under the right content address, with its interface written out by hand
somewhere else and nothing checking the two agreed. This is the path from "here
is my indicator" to a conforming component: interface, version, body address,
kernel declaration, all from one place.

**The interface is declared, not inferred (F4).** The author writes it out, and
the decorator checks the *function* satisfies it rather than the other way
round. Inferring an interface from a signature is tempting and wrong for exactly
the reason F4 gives: "an inferred interface changes whenever internals change,
which is catastrophic for a published component". Renaming a local parameter
would silently republish a different contract. Here, a function that does not
match its declared interface is refused at import.

**The body address is the source's content address (F2).** "The body MUST be
stored once and content-addressed." Two authors who write the same function get
the same address; an author who reformats one gets a different one, which is
the honest answer — the registry cannot know that a whitespace change is
semantically empty, and claiming otherwise is how a cache lies.

**Nothing records where a component came from (C13).** An authored component is
a component. It carries no `source`, no `author`, no `is_python` — the executor
must not be able to branch on provenance, and the way to guarantee that is for
there to be nothing to branch on. `tests/test_ir_contract_c13.py` greps for
exactly those names, and this is the first time that guard is load-bearing
rather than precautionary: before today there was only one way to make a
component.

**What this deliberately does not do.** It does not sandbox. RFC 0001 Appendix
C(f) puts sandboxing on the *kernel registry* — "sandboxing constrains what a
component kernel may do, which is a property of the kernel registry rather than
of the graph language" — and the platform already has an AST allow-list stronger
than anything in the nine systems studied. Wiring that in is the marketplace's
phase, triggered by third-party distribution. Locally-authored components are
code the owner already runs.
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

# The signature every kernel has. It is deliberately not the author's parameter
# names: a kernel is handed its bound parameters and its inputs, and nothing
# else — not the graph, not its instance id, not where it came from.
KERNEL_SIGNATURE = ("params", "inputs")


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
    """A component-def, its kernel declaration, and the function behind it.

    The three travel together because they are three views of one thing, and
    keeping them apart is what let the interface and the implementation drift.
    """

    definition: Mapping[str, Any]
    spec: KernelSpec
    kernel: Callable[..., Mapping[str, Any]]

    @property
    def key(self) -> tuple[str, int]:
        return (self.definition["identifier"], self.definition["version"])

    @property
    def body_ref(self) -> str:
        return self.definition["body"]["ref"]


# ── interface items, so an author does not hand-write dictionaries ────────

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
              cache_key: str | None = None) -> Callable[[Callable], AuthoredComponent]:
    """Declare a component whose body is this function.

    Returns an `AuthoredComponent`, not the function — the function alone was
    never the thing, and returning it would let a caller register the kernel
    without its interface, which is the drift this exists to stop.
    """

    def decorate(fn: Callable) -> AuthoredComponent:
        _check_signature(identifier, fn)

        definition: dict[str, Any] = {
            "format_version": FORMAT_VERSION,
            "kind": "component",
            "identifier": identifier,
            "version": version,
            "display_name": display_name or identifier,
            "interface": [dict(item) for item in interface],
            "body": {"body": "kernel", "ref": _body_address(identifier, fn)},
        }
        if parent_version is not None:
            definition["parent_version"] = parent_version

        violations = validate(definition)
        if violations:
            raise AuthoringError(identifier, "is not a conforming component", violations)

        _check_satisfies_interface(identifier, fn, definition["interface"])

        return AuthoredComponent(
            definition=definition,
            spec=kernel_spec(warmup=warmup, purity=purity,
                             cache_identity=cache_identity, cache_key=cache_key),
            kernel=fn,
        )

    return decorate


def _check_signature(identifier: str, fn: Callable) -> None:
    names = tuple(inspect.signature(fn).parameters)
    if names != KERNEL_SIGNATURE:
        raise AuthoringError(
            identifier,
            f"a kernel takes exactly {KERNEL_SIGNATURE}, not {names}; it is handed "
            "its bound parameters and its inputs, and nothing that would let it "
            "behave differently depending on where it was used")


def _body_address(identifier: str, fn: Callable) -> str:
    """F2 — the body, content-addressed.

    The source is dedented before hashing so that moving a function into or out
    of a class does not, by itself, mint a new body.
    """
    try:
        source = textwrap.dedent(inspect.getsource(fn))
    except OSError as exc:                                  # pragma: no cover
        raise AuthoringError(
            identifier,
            "has no readable source, so its body cannot be content-addressed") from exc
    return content_address({"kernel": source})


def _check_satisfies_interface(identifier: str, fn: Callable,
                               interface: Sequence[Mapping[str, Any]]) -> None:
    """F4 — the interface is the contract; the internals must satisfy it.

    Checked in the direction F4 requires. The declaration is authoritative, and
    the function is what has to keep up — not the reverse, which would make a
    rename inside the body a silent republication of a different contract.

    What is checkable statically is that the function *reads* every input and
    parameter it declared, and reads nothing it did not. A declared input the
    kernel ignores is a lie in the interface; an undeclared one it reads is a
    dependency no resolver can see, so no graph can wire it and no warmup can
    account for it.
    """
    declared_inputs, declared_params, declared_outputs = _declared(interface)
    if not declared_outputs:
        raise AuthoringError(identifier, "declares no output socket")

    try:
        source = textwrap.dedent(inspect.getsource(fn))
    except OSError:                                          # pragma: no cover
        return

    read = _subscripts(source)
    for kind, declared in (("inputs", declared_inputs), ("params", declared_params)):
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


def _subscripts(source: str) -> dict[str, set[str]]:
    """Which string keys the source reads out of `inputs` and `params`.

    Deliberately syntactic rather than dynamic: an authoring check that had to
    *run* the kernel to learn its interface would be inferring the interface,
    which is what F4 forbids.
    """
    import ast

    found: dict[str, set[str]] = {"inputs": set(), "params": set()}
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Subscript):
            continue
        base, key = node.value, node.slice
        if isinstance(base, ast.Name) and base.id in found and \
                isinstance(key, ast.Constant) and isinstance(key.value, str):
            found[base.id].add(key.value)
    return found


# ── a library from authored components ────────────────────────────────────

def library(components: Sequence[AuthoredComponent],
            extra: Library | None = None) -> tuple[Library, dict[str, Callable]]:
    """Build the `(Library, implementations)` pair the resolver and runtime want.

    C13, structurally: the key is the body's content address and there is no
    other. An authored component lands in the same two dicts a built-in lands
    in, so by the time anything executes, there is no way to tell them apart —
    which is the property, not a side effect of it.
    """
    seen: dict[tuple[str, int], AuthoredComponent] = {}
    for authored in components:
        if authored.key in seen:
            raise AuthoringError(
                authored.key[0],
                f"version {authored.key[1]} is declared twice; an identifier and "
                "version name one body")
        seen[authored.key] = authored

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
