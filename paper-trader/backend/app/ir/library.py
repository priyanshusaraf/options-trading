"""The platform's component library — the one `(Library, implementations)` pair.

**Why this module exists.** Until the 2026-08-07 architecture review, five production call
sites imported `app.ir.strategies.expanding_z`'s `LIBRARY`/`IMPLEMENTATIONS` as though they
were the platform's: the editor's component palette (`api/ir_edit_routes.py`), the artefact
store (`editor/graph_artifacts.py`), the shadow lane (`engine/ir_shadow.py`), the research
orchestrator, and — most seriously — `core/paper_authority.adapter_for`, which is on the
paper-**authoritative** path. One strategy was accidentally serving as the platform registry.

That was harmless with one strategy and stops being harmless with two: either the library
forks, which is the second-registry this project has a standing rule against, or
`expanding_z.py` silently becomes the platform library while still being named a strategy.
The second is likelier and worse, because nothing would report it.

**What this is, and is not.** It is a *composition*, not a plugin system. There is no
discovery, no entry points, no dynamic loading and no configuration — `CONTRIBUTORS` is a
literal tuple, and adding a component library is an edit to it, reviewed like any other. The
resolver, the validator, the authoring layer, the runtime and the artefact format are all
untouched and unaware of this module: it hands `resolve()` exactly the `Library` it was
handed before.

**What composition buys that a re-export would not.** A re-export renames the dependency
without removing it. Composing means the platform owns the merge, and therefore owns the one
question a merge raises: what happens when two contributors disagree. Two components sharing
an `(identifier, version)` with different bytes, or a body address with a different kernel,
are refused here rather than resolved by import order. That refusal is the boundary; the rest
is bookkeeping.

**Contributor contract.** A contributor is a module exposing `LIBRARY: Library` and
`IMPLEMENTATIONS: Mapping[str, Kernel]`. Deliberately the shape the existing artefact modules
already have, so contributing costs nothing and no file had to be rewritten to join.

**Identity is unchanged and that is the acceptance criterion.** With one contributor the
composition is the identity function, proven by fingerprint rather than by argument
(`tests/test_ir_platform_library.py`).
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from app.ir.hashing import canonical_json
from app.ir.contributors import generated_blocks
from app.ir.registry import KernelRegistration, PlatformRegistry
from app.ir.resolve import Library
from app.ir.strategies import expanding_z

#: Every module contributing components to the platform library, in precedence-free order —
#: a conflict is refused rather than resolved by position, so the order carries no meaning
#: and reordering this tuple cannot change what resolves.
#:
#: `expanding_z` contributes the generic component set (`indicator.ema`, `math.abs`,
#: `predicate.le`, …) alongside the artefact that motivated it. Relocating those definitions
#: into a component module of their own is a later, separate, purely mechanical step; the
#: point of this boundary is that it is now one line here rather than five imports across the
#: tree.
CONTRIBUTORS: tuple[Any, ...] = (generated_blocks, expanding_z)


class LibraryConflict(Exception):
    """Two contributors disagree about what a name or an address means.

    Its own type because the caller's options are genuinely different from any other import
    error: this is never transient and never a configuration problem. Somebody published two
    different things under one identity, and the platform must not pick one.
    """


def _refuse(what: str, key: str, detail: str) -> None:
    raise LibraryConflict(
        f"two contributors declare different {what} for {key}: {detail}. One identity names "
        f"one thing; the platform library will not choose between them by import order.")


def compose(modules: Sequence[Any]) -> PlatformRegistry:
    """Merge contributors into one immutable registry, refusing disagreement.

    Identical duplicates are fine — that is aliasing, and two modules re-exporting one
    component is not a conflict. Different values under one identity are refused.
    """
    components: dict[tuple[str, int], Mapping[str, Any]] = {}
    bodies: dict[str, Mapping[str, Any]] = {}
    registrations: dict[str, KernelRegistration] = {}

    for module in modules:
        library = getattr(module, "LIBRARY", None)
        if not isinstance(library, Library):
            raise LibraryConflict(
                f"{getattr(module, '__name__', module)!r} is not a component-library "
                f"contributor: it exposes no `LIBRARY` of type `Library`")

        for key, component in library.components.items():
            existing = components.get(key)
            if existing is not None and canonical_json(existing) != canonical_json(component):
                _refuse("components", f"{key[0]!r} v{key[1]}", "their canonical bytes differ")
            components[key] = component

        for ref, body in library.bodies.items():
            existing = bodies.get(ref)
            if existing is not None and canonical_json(existing) != canonical_json(body):
                # Unreachable while a body ref is that body's own content address, which is
                # what `body_for()` guarantees. Checked anyway: the day it is reachable is
                # the day a body ref stopped being an address, and that must not be silent.
                _refuse("bodies", ref, "their canonical bytes differ")
            bodies[ref] = body

        contributed = getattr(module, "REGISTRATIONS", None)
        if not isinstance(contributed, Mapping):
            raise LibraryConflict(
                f"{getattr(module, '__name__', module)!r} exposes no REGISTRATIONS mapping")
        if set(library.kernels) != set(contributed):
            raise LibraryConflict(
                f"{getattr(module, '__name__', module)!r} has split library and registration keys")
        for ref, registration in contributed.items():
            if not isinstance(registration, KernelRegistration):
                raise LibraryConflict(f"{ref} is not an immutable KernelRegistration")
            if registration.spec != library.kernels[ref]:
                _refuse("kernel declarations", ref, "library and registration specs differ")
            existing = registrations.get(ref)
            if existing is not None and existing != registration:
                if existing.spec != registration.spec:
                    _refuse("kernel declarations", ref,
                            "warmup, purity, cache identity, or causal contract differs")
                _refuse("registrations", ref, "one body address names different records")
            registrations[ref] = registration

    return PlatformRegistry(
        components=components,
        bodies=bodies,
        registrations=registrations,
    )


#: **The** platform component library and its kernel implementations. Everything outside
#: `app/ir/strategies/` that needs a library takes these two, and nothing else.
REGISTRY = compose(CONTRIBUTORS)
LIBRARY = REGISTRY.library
IMPLEMENTATIONS = REGISTRY.implementations


__all__ = ["CONTRIBUTORS", "IMPLEMENTATIONS", "LIBRARY", "REGISTRY",
           "LibraryConflict", "compose"]
