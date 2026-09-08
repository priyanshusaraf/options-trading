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
from app.ir.first_party import (
    analytical,
    derivatives,
    execution_intent,
    historical_daily_gaps,
    logic_state,
    monitoring_intent_v2,
    original_strategy_primitives,
)
from app.ir import original_strategy_presets
from app.ir.first_party.analytical_v2 import (
    core_math,
    multi_output,
    recursive_state,
    remaining_oracles,
    session_data,
)
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
V2_CONTRIBUTORS: tuple[Any, ...] = (
    analytical, execution_intent, derivatives, logic_state,
    core_math, recursive_state, multi_output, session_data, remaining_oracles,
    monitoring_intent_v2,
    original_strategy_primitives, original_strategy_presets, historical_daily_gaps,
)
ANALYTICAL_V2_CONTRIBUTORS: tuple[Any, ...] = (
    core_math, recursive_state, multi_output, session_data, remaining_oracles,
)


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


def _canonical_mapping_bytes(value: Any) -> str:
    def plain(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {key: plain(child) for key, child in item.items()}
        if isinstance(item, (tuple, list)):
            return [plain(child) for child in item]
        return item
    return canonical_json(plain(value))


def _same_analytical_v2_wire_type(key: Any, existing: Any, incoming: Any) -> bool:
    """Reconcile the one sealed annotation delta without weakening type identity."""
    if key != ("analytical.market_frame", 2):
        return False
    base = {
        "type_id": "analytical.market_frame", "type_version": 2,
        "shapes": ["series"], "runtime_representation": "named indexed market fields",
    }
    session = {
        **base,
        "runtime_representation": "named indexed canonical fields and session context",
    }
    actual = {_canonical_mapping_bytes(existing), _canonical_mapping_bytes(incoming)}
    return actual == {_canonical_mapping_bytes(base), _canonical_mapping_bytes(session)}


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
            if existing is not None and _canonical_mapping_bytes(existing) != _canonical_mapping_bytes(component):
                _refuse("components", f"{key[0]!r} v{key[1]}", "their canonical bytes differ")
            components[key] = component

        for ref, body in library.bodies.items():
            existing = bodies.get(ref)
            if existing is not None and _canonical_mapping_bytes(existing) != _canonical_mapping_bytes(body):
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


def compose_v2(base: PlatformRegistry, modules: Sequence[Any]) -> PlatformRegistry:
    """Extend the same PlatformRegistry with frozen v2 contributors."""
    types = dict(base.v2_types)
    components = dict(base.v2_components)
    implementations = dict(base.v2_implementation_registrations)
    declarations = dict(base.data_requirement_declarations)
    contracts = dict(base.node_contracts)
    bindings = dict(base.contract_bindings)
    for module in modules:
        for label, target, incoming in (
            ("v2 types", types, getattr(module, "V2_TYPES", None)),
            ("v2 components", components, getattr(module, "V2_COMPONENTS", None)),
            ("v2 implementations", implementations, getattr(module, "V2_IMPLEMENTATIONS", None)),
            ("data requirements", declarations, getattr(module, "DATA_REQUIREMENTS", None)),
            ("node contracts", contracts, getattr(module, "NODE_CONTRACTS", None)),
            ("contract bindings", bindings, getattr(module, "CONTRACT_BINDINGS", {})),
        ):
            if not isinstance(incoming, Mapping):
                raise LibraryConflict(f"{module!r} exposes no {label} mapping")
            for key, value in incoming.items():
                existing = target.get(key)
                if existing is not None and _canonical_mapping_bytes(existing) != _canonical_mapping_bytes(value):
                    if label == "v2 types" and _same_analytical_v2_wire_type(key, existing, value):
                        continue
                    _refuse(label, repr(key), "canonical bytes differ")
                target[key] = value
    return PlatformRegistry(
        components=base.library.components,
        bodies=base.library.bodies,
        registrations=base.registrations,
        v2_types=types,
        v2_components=components,
        v2_implementations=implementations,
        data_requirement_declarations=declarations,
        node_contracts=contracts,
        contract_bindings=bindings,
    )


def _analytical_v2_dispositions(modules: Sequence[Any]) -> Mapping[str, Mapping[str, str]]:
    """Close the 125-name accuracy universe without publishing refusal stubs."""
    rows: dict[str, Mapping[str, str]] = {}
    accepted_keys: set[tuple[str, int]] = set()
    for module in modules:
        specs = getattr(module, "SPECS", None)
        components = getattr(module, "V2_COMPONENTS", None)
        implementations = getattr(module, "V2_IMPLEMENTATIONS", None)
        contracts = getattr(module, "NODE_CONTRACTS", None)
        bindings = getattr(module, "CONTRACT_BINDINGS", None)
        if any(not isinstance(value, Mapping) for value in (
                specs, components, implementations, contracts, bindings)):
            raise LibraryConflict(f"{module!r} has an incomplete analytical v2 package")
        for name, spec in specs.items():
            if name in rows:
                _refuse("analytical v2 dispositions", name, "the name is duplicated")
            key = (f"analytical.{name.lower()}", 2)
            if spec.get("decision") == "REFUSE":
                refusal = spec.get("refusal")
                code = refusal.get("code") if isinstance(refusal, Mapping) else None
                if (not isinstance(code, str) or not code
                        or any(key in mapping for mapping in (
                            components, implementations, contracts, bindings))):
                    raise LibraryConflict(
                        f"{module!r} publishes an executable or untyped refused analytical v2 row")
                rows[name] = MappingProxyType({"status": "UNAVAILABLE", "reason_code": code})
                continue
            if any(key not in mapping for mapping in (
                    components, implementations, contracts, bindings)):
                raise LibraryConflict(f"{module!r} has an incomplete accepted analytical v2 row")
            accepted_keys.add(key)
            rows[name] = MappingProxyType({
                "status": "ACCEPTED_V2",
                "reason_code": "ACCURACY_ASSURANCE_ACCEPTED",
            })
    expected = set(analytical.CATALOGUE_NAMES)
    if set(rows) != expected or len(rows) != 125 or len(accepted_keys) != 108:
        raise LibraryConflict("analytical v2 dispositions do not close the exact 125-name universe")
    return MappingProxyType({name: rows[name] for name in sorted(rows)})


#: **The** platform component library and its kernel implementations. Everything outside
#: `app/ir/strategies/` that needs a library takes these two, and nothing else.
REGISTRY = compose_v2(compose(CONTRIBUTORS), V2_CONTRIBUTORS)
ANALYTICAL_V2_DISPOSITIONS = _analytical_v2_dispositions(ANALYTICAL_V2_CONTRIBUTORS)
LIBRARY = REGISTRY.library
IMPLEMENTATIONS = REGISTRY.implementations


__all__ = ["ANALYTICAL_V2_CONTRIBUTORS", "ANALYTICAL_V2_DISPOSITIONS",
           "CONTRIBUTORS", "IMPLEMENTATIONS", "LIBRARY", "REGISTRY",
           "V2_CONTRIBUTORS", "LibraryConflict", "compose", "compose_v2"]
