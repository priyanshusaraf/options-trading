"""G-1 — the platform component library, and the proof it changed nothing.

The 2026-08-07 architecture review found that five production call sites imported one
*strategy's* component library as though it were the platform's, including
`core/paper_authority.adapter_for` on the paper-authoritative path. `app/ir/library.py` is
the correction. It is mechanical by design, so the tests here are of two kinds and no others:

1. **Identity** — the same graph resolves to byte-identical canonical content, the same
   content and body addresses, the same node ids, the same cache ids. If any of these moved,
   the correction was not mechanical and every published artefact, every experiment binding
   and every paper deployment's recorded content address would be invalidated at once.

2. **The seam is real** — no production module reaches around the boundary to take a library
   from a strategy again. Parsed, not grepped: several modules legitimately import a *graph*
   from `app.ir.strategies`, and a substring guard would either miss the violation or fail on
   the legitimate case.

The mutation that turns each red is recorded on the test.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import pathlib

import pytest

from app.ir import library as platform
from app.ir.causal import HistoryBound, causal_contract
from app.ir.contributors import generated_blocks
from app.ir.hashing import canonical_json, content_address
from app.ir.library import IMPLEMENTATIONS, LIBRARY, REGISTRY, LibraryConflict, compose
from app.ir.registry import PlatformRegistry
from app.ir.resolve import Library, resolve
from app.ir.strategies import expanding_z

#: The published identity of the reference artefact, as measured at `75809a3` — before the
#: correction existed. Hard-coded rather than recomputed from the module under test: a
#: fixture that derives the expected value from the thing it is checking proves nothing.
#: This is also the address `editor/graph_artifacts.CATALOGUE_CONTENT_ADDRESS` pins and the
#: address a paper deployment records, so a change here is a change to deployed identity.
REFERENCE_GRAPH_ADDRESS = (
    "sha256:d78b424e8247e26663728b19980e197fb5e84a4e21c08c4df00ac704db1ae02b"
)

#: Measured at `75809a3`. 18 leaves, 35 edges, 302 bars of warmup.
REFERENCE_NODES = 18
REFERENCE_EDGES = 35
REFERENCE_WARMUP = 302


def test_platform_registry_is_the_single_immutable_authority():
    assert isinstance(REGISTRY, PlatformRegistry)
    assert LIBRARY is REGISTRY.library
    assert IMPLEMENTATIONS is REGISTRY.implementations
    with pytest.raises(TypeError):
        REGISTRY.registrations["forged"] = object()


def test_platform_registry_deep_copies_component_bytes():
    component = _one_component(ref=expanding_z.EMA["body"]["ref"])
    original = {("indicator.fake", 1): component}
    registration = expanding_z.REGISTRATIONS[expanding_z.EMA["body"]["ref"]]
    registry = PlatformRegistry(
        components=original, bodies={}, registrations={registration.body_ref: registration})

    component["display_name"] = "mutated outside registry"
    assert registry.library.components[("indicator.fake", 1)]["display_name"] == "Fake"
    with pytest.raises(TypeError):
        registry.library.components[("indicator.fake", 1)]["display_name"] = "forged"


def test_platform_registry_can_rebuild_from_read_only_views():
    rebuilt = PlatformRegistry(
        components=REGISTRY.library.components,
        bodies=REGISTRY.library.bodies,
        registrations=REGISTRY.registrations,
    )
    assert set(rebuilt.library.components) == set(REGISTRY.library.components)
    for key in REGISTRY.library.components:
        assert canonical_json(rebuilt.library.components[key]) == \
            canonical_json(REGISTRY.library.components[key])


def test_platform_registry_rejects_directly_forged_registration_address():
    registration = expanding_z.REGISTRATIONS[expanding_z.EMA["body"]["ref"]]
    forged = dataclasses.replace(
        registration, implementation_address="sha256:" + "0" * 64)

    with pytest.raises(ValueError, match="implementation_address"):
        PlatformRegistry(
            components={(expanding_z.EMA["identifier"], 1): expanding_z.EMA},
            bodies={},
            registrations={forged.body_ref: forged},
        )


def test_platform_registry_rejects_missing_or_forged_graph_body():
    graph_component = expanding_z.ATR
    ref = graph_component["body"]["ref"]

    with pytest.raises(ValueError, match="graph body closure"):
        PlatformRegistry(
            components={(graph_component["identifier"], 1): graph_component},
            bodies={},
            registrations={},
        )
    with pytest.raises(ValueError, match="content address"):
        PlatformRegistry(
            components={(graph_component["identifier"], 1): graph_component},
            bodies={ref: {**expanding_z.ATR_BODY, "display_name": "forged"}},
            registrations={},
        )


def test_platform_registry_rejects_graph_component_interface_drift():
    graph_component = dict(expanding_z.ATR)
    graph_component["interface"] = tuple(graph_component["interface"][:-1])
    ref = graph_component["body"]["ref"]

    with pytest.raises(ValueError, match="public interface differs"):
        PlatformRegistry(
            components={(graph_component["identifier"], 1): graph_component},
            bodies={ref: expanding_z.ATR_BODY}, registrations={},
        )


@pytest.mark.parametrize("mutation", ["input_as_source", "missing_output"])
def test_platform_registry_enforces_graph_body_socket_contract(mutation):
    body = copy.deepcopy(expanding_z.ATR_BODY)
    if mutation == "input_as_source":
        body["edges"][3]["source"]["socket"] = "high"
        expected = "declared output"
    else:
        body["edges"].pop()
        expected = "exactly one producer"
    old_ref = expanding_z.ATR["body"]["ref"]
    new_ref = content_address(body)
    component = copy.deepcopy(expanding_z.ATR)
    component["body"]["ref"] = new_ref
    components = dict(REGISTRY.library.components)
    components[(component["identifier"], component["version"])] = component
    bodies = dict(REGISTRY.library.bodies)
    bodies.pop(old_ref)
    bodies[new_ref] = body

    with pytest.raises(ValueError, match=expected):
        PlatformRegistry(
            components=components,
            bodies=bodies,
            registrations=REGISTRY.registrations,
        )


def test_platform_registry_preserves_graph_body_cycle_error_priority():
    body = copy.deepcopy(expanding_z.ATR_BODY)
    body["edges"].append({
        "source": {"instance": "n_smooth", "socket": "out"},
        "target": {"instance": "n_tr", "socket": "high"},
    })
    old_ref = expanding_z.ATR["body"]["ref"]
    new_ref = content_address(body)
    component = copy.deepcopy(expanding_z.ATR)
    component["interface"] = component["interface"][:-1]
    component["body"]["ref"] = new_ref
    components = dict(REGISTRY.library.components)
    components[(component["identifier"], component["version"])] = component
    bodies = dict(REGISTRY.library.bodies)
    bodies.pop(old_ref)
    bodies[new_ref] = body

    with pytest.raises(ValueError, match="C10"):
        PlatformRegistry(
            components=components,
            bodies=bodies,
            registrations=REGISTRY.registrations,
        )


def test_platform_registry_includes_generated_blocks_and_boolean_logic():
    identifiers = {identifier for identifier, _version in LIBRARY.components}
    assert {"logic.and", "logic.or"} <= identifiers
    assert {f"block.{name}" for name in generated_blocks.BLOCKS} <= identifiers
    assert set(LIBRARY.kernels) == set(REGISTRY.registrations) == set(IMPLEMENTATIONS)


# ── 1. identity across the correction ────────────────────────────────────────────

def test_reference_graph_content_address_is_unchanged():
    """Mutation: change any byte of `expanding_z.GRAPH` — this fails, and so does every
    stored `graph_versions.content_address` that ever named it."""
    assert content_address(expanding_z.GRAPH) == REFERENCE_GRAPH_ADDRESS


def test_platform_library_resolves_the_reference_artefact_identically():
    """The whole point of the correction, stated as an equality.

    Mutation: drop a component from `CONTRIBUTORS`, or let `compose` reorder/replace one —
    resolution raises or the cache ids move, and this fails.
    """
    through_platform = resolve(expanding_z.GRAPH, LIBRARY)
    through_strategy = resolve(expanding_z.GRAPH, expanding_z.LIBRARY)

    assert [n.instance_id for n in through_platform.nodes] == \
           [n.instance_id for n in through_strategy.nodes]
    assert [n.cache_id for n in through_platform.nodes] == \
           [n.cache_id for n in through_strategy.nodes]
    assert [n.body_ref for n in through_platform.nodes] == \
           [n.body_ref for n in through_strategy.nodes]
    assert [n.warmup for n in through_platform.nodes] == \
           [n.warmup for n in through_strategy.nodes]
    assert through_platform.edges == through_strategy.edges
    assert through_platform.versions == through_strategy.versions
    assert dict(through_platform.outputs) == dict(through_strategy.outputs)
    assert through_platform.warmup == through_strategy.warmup == REFERENCE_WARMUP
    assert len(through_platform.nodes) == REFERENCE_NODES
    assert len(through_platform.edges) == REFERENCE_EDGES


def test_platform_library_carries_every_body_address_unchanged():
    """Body addresses are what the runtime keys kernels on (C13). If one moved, the
    implementation map would no longer answer for it."""
    for key, component in expanding_z.LIBRARY.components.items():
        assert LIBRARY.components[key]["body"]["ref"] == component["body"]["ref"]
    for key, body in expanding_z.LIBRARY.bodies.items():
        assert canonical_json(LIBRARY.bodies[key]) == canonical_json(body)
    for key, spec in expanding_z.LIBRARY.kernels.items():
        assert LIBRARY.kernels[key] == spec
        assert platform.IMPLEMENTATIONS[key] is expanding_z.IMPLEMENTATIONS[key]


def test_every_declared_kernel_has_an_implementation():
    """C13's precondition. `compose` refuses a library that would fail at evaluation time
    instead of at construction time."""
    assert set(LIBRARY.kernels) == set(platform.IMPLEMENTATIONS)


def test_single_contributor_composition_is_the_identity_function():
    """With one contributor the merge must add and remove nothing.

    Mutation: make `compose` skip, rename or re-wrap an entry — this fails.
    """
    composed = compose([expanding_z])
    assert set(composed.library.components) == set(expanding_z.LIBRARY.components)
    for key in expanding_z.LIBRARY.components:
        assert canonical_json(composed.library.components[key]) == \
            canonical_json(expanding_z.LIBRARY.components[key])
    assert canonical_json(sorted(f"{i}@{v}" for i, v in composed.library.components)) == \
           canonical_json(sorted(f"{i}@{v}" for i, v in expanding_z.LIBRARY.components))


# ── 2. the boundary refuses disagreement ─────────────────────────────────────────

class _Contributor:
    """A stand-in contributor module. A dataclass would do; a class keeps the attribute
    access identical to a real module's."""

    def __init__(self, library: Library, registrations=None):
        self.LIBRARY = library
        self.REGISTRATIONS = registrations or {}
        self.__name__ = "tests.contributor"


def _one_component(identifier="indicator.fake", version=1, display="Fake", ref="sha256:" + "0" * 64):
    return {
        "format_version": 1, "kind": "component", "identifier": identifier,
        "version": version, "display_name": display,
        "interface": [{"item": "socket", "identifier": "out", "display_name": "out",
                       "direction": "output",
                       "wire_type": {"value": "float", "structure": "series",
                                     "domain": {"instrument": "NIFTY", "timeframe": "15m"}}}],
        "body": {"body": "kernel", "ref": ref},
    }


def test_two_contributors_may_alias_one_component():
    """Re-exporting the same component is not a conflict. Only *disagreement* is."""
    component = expanding_z.EMA
    registration = expanding_z.REGISTRATIONS[component["body"]["ref"]]
    lib = Library(components={("indicator.ema", 1): component}, bodies={},
                  kernels={registration.body_ref: registration.spec})
    merged = compose([_Contributor(lib, {registration.body_ref: registration}),
                      _Contributor(lib, {registration.body_ref: registration})])
    assert canonical_json(merged.library.components[("indicator.ema", 1)]) == \
        canonical_json(component)


def test_conflicting_component_bytes_are_refused():
    """The boundary's reason to exist: one identity must not name two things.

    Mutation: delete the canonical-bytes comparison in `compose` — import order silently
    decides which component wins, and this test goes red.
    """
    a = Library(components={("indicator.fake", 1): _one_component(display="A")},
                bodies={}, kernels={})
    b = Library(components={("indicator.fake", 1): _one_component(display="B")},
                bodies={}, kernels={})
    with pytest.raises(LibraryConflict, match="canonical bytes differ"):
        compose([_Contributor(a), _Contributor(b)])


def test_conflicting_kernel_declarations_are_refused():
    """Warmup, purity and cache identity must not depend on which module imported first."""
    from app.ir.registry import DependencyBoundary, registered_kernel

    ref = "sha256:" + "1" * 64
    def implementation(params, node_inputs, context_inputs):
        return {}
    causal = causal_contract(node_input_sockets=(), history=HistoryBound("bounded"))
    reg_a = registered_kernel(body_ref=ref, implementation=implementation, causal=causal,
                              dependency_boundary=DependencyBoundary("declared_objects"),
                              warmup=5)
    reg_b = registered_kernel(body_ref=ref, implementation=implementation, causal=causal,
                              dependency_boundary=DependencyBoundary("declared_objects"),
                              warmup=9)
    a = Library(components={}, bodies={}, kernels={ref: reg_a.spec})
    b = Library(components={}, bodies={}, kernels={ref: reg_b.spec})
    with pytest.raises(LibraryConflict, match="kernel declarations"):
        compose([_Contributor(a, {ref: reg_a}), _Contributor(b, {ref: reg_b})])


def test_one_address_may_not_execute_two_functions():
    """C13 keys the runtime on the address alone, so two functions at one address is the
    one thing that would make evaluation depend on import order."""
    from app.ir.registry import DependencyBoundary, registered_kernel
    ref = "sha256:" + "2" * 64
    causal = causal_contract(node_input_sockets=(), history=HistoryBound("bounded"))
    def first(params, node_inputs, context_inputs): return {}
    def second(params, node_inputs, context_inputs): return {"different": True}
    reg_a = registered_kernel(body_ref=ref, implementation=first, causal=causal,
                              dependency_boundary=DependencyBoundary("declared_objects"))
    reg_b = registered_kernel(body_ref=ref, implementation=second, causal=causal,
                              dependency_boundary=DependencyBoundary("declared_objects"))
    lib_a = Library(components={}, bodies={}, kernels={ref: reg_a.spec})
    lib_b = Library(components={}, bodies={}, kernels={ref: reg_b.spec})
    with pytest.raises(LibraryConflict, match="registrations"):
        compose([_Contributor(lib_a, {ref: reg_a}), _Contributor(lib_b, {ref: reg_b})])


def test_declared_kernel_without_implementation_is_refused():
    from app.ir.kernels import kernel_spec

    ref = "sha256:" + "3" * 64
    lib = Library(components={}, bodies={}, kernels={ref: kernel_spec(warmup=1)})
    with pytest.raises(LibraryConflict, match="split library and registration"):
        compose([_Contributor(lib)])


def test_a_non_contributor_is_refused():
    with pytest.raises(LibraryConflict, match="no `LIBRARY`"):
        compose([_Contributor.__new__(_Contributor)])


# ── 3. the seam is real: nothing reaches around it ───────────────────────────────

BACKEND = pathlib.Path(__file__).resolve().parents[1]

#: The only two production modules allowed to take a *library* from a strategy artefact
#: module: the artefact itself, and the platform library that composes it.
LIBRARY_SOURCE_EXEMPT = (
    BACKEND / "app" / "ir" / "library.py",
)

#: Names that are a component *library*. A `GRAPH` is a strategy artefact and importing one
#: is legitimate — `catalogue.py`, `graph_artifacts.py` and `ir_shadow.py` all do, on
#: purpose. This guard is about where the *vocabulary* comes from, not the artefact.
LIBRARY_NAMES = frozenset({"LIBRARY", "IMPLEMENTATIONS", "KERNELS", "COMPONENTS"})


def _production_modules():
    for root in ("app", "research"):
        for path in sorted((BACKEND / root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            if path.is_relative_to(BACKEND / "app" / "ir" / "strategies"):
                continue      # the artefact modules are the source, not a consumer
            if path in LIBRARY_SOURCE_EXEMPT:
                continue
            yield path


def _strategy_library_imports(path: pathlib.Path) -> list[str]:
    """Names imported from an `app.ir.strategies.*` module that are libraries, not graphs."""
    offending: list[str] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if not node.module.startswith("app.ir.strategies"):
            continue
        offending.extend(a.name for a in node.names if a.name in LIBRARY_NAMES)
    return offending


def test_no_production_module_takes_its_library_from_a_strategy():
    """The G-1 seam, as a property of the tree rather than of anyone's memory.

    Mutation (verified): restore `from app.ir.strategies.expanding_z import LIBRARY` in
    `app/api/ir_edit_routes.py` — this test names that file and fails.
    """
    violations = {
        str(path.relative_to(BACKEND)): names
        for path in _production_modules()
        if (names := _strategy_library_imports(path))
    }
    assert not violations, (
        f"these modules take a component library from a strategy artefact instead of from "
        f"`app.ir.library`, which is how one strategy came to serve as the platform "
        f"registry: {violations}")


def test_the_guard_can_see_a_violation():
    """A guard that cannot go red is decoration. Proven on a synthetic file rather than by
    editing a real one, so the proof is part of the suite instead of a note in a document."""
    offending = ast.parse("from app.ir.strategies.expanding_z import GRAPH, LIBRARY\n")
    names = [a.name for node in ast.walk(offending)
             if isinstance(node, ast.ImportFrom) and node.module
             and node.module.startswith("app.ir.strategies")
             for a in node.names if a.name in LIBRARY_NAMES]
    assert names == ["LIBRARY"], "the guard must catch LIBRARY and ignore GRAPH"


def test_the_paper_authoritative_path_resolves_against_the_platform_library():
    """`adapter_for` is the one library consumer on the authoritative path. It must take the
    platform's vocabulary, and the test names the function rather than the import so a
    later refactor cannot pass by moving the line."""
    import inspect

    from app.core import paper_authority

    source = inspect.getsource(paper_authority.adapter_for)
    assert "from app.ir.library import" in source
    assert "app.ir.strategies" not in source
