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
import pathlib

import pytest

from app.ir import library as platform
from app.ir.hashing import canonical_json, content_address
from app.ir.library import LIBRARY, LibraryConflict, compose
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
    assert {k: c["body"]["ref"] for k, c in LIBRARY.components.items()} == \
           {k: c["body"]["ref"] for k, c in expanding_z.LIBRARY.components.items()}
    assert dict(LIBRARY.bodies) == dict(expanding_z.LIBRARY.bodies)
    assert dict(LIBRARY.kernels) == dict(expanding_z.LIBRARY.kernels)
    assert platform.IMPLEMENTATIONS == expanding_z.IMPLEMENTATIONS


def test_every_declared_kernel_has_an_implementation():
    """C13's precondition. `compose` refuses a library that would fail at evaluation time
    instead of at construction time."""
    assert set(LIBRARY.kernels) == set(platform.IMPLEMENTATIONS)


def test_single_contributor_composition_is_the_identity_function():
    """With one contributor the merge must add and remove nothing.

    Mutation: make `compose` skip, rename or re-wrap an entry — this fails.
    """
    assert dict(LIBRARY.components) == dict(expanding_z.LIBRARY.components)
    assert canonical_json(sorted(f"{i}@{v}" for i, v in LIBRARY.components)) == \
           canonical_json(sorted(f"{i}@{v}" for i, v in expanding_z.LIBRARY.components))


# ── 2. the boundary refuses disagreement ─────────────────────────────────────────

class _Contributor:
    """A stand-in contributor module. A dataclass would do; a class keeps the attribute
    access identical to a real module's."""

    def __init__(self, library: Library, implementations=None):
        self.LIBRARY = library
        self.IMPLEMENTATIONS = implementations or {}
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
    component = _one_component()
    lib = Library(components={("indicator.fake", 1): component}, bodies={}, kernels={})
    merged, _ = compose([_Contributor(lib), _Contributor(lib)])
    assert dict(merged.components) == {("indicator.fake", 1): component}


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
    from app.ir.kernels import kernel_spec

    ref = "sha256:" + "1" * 64
    a = Library(components={}, bodies={}, kernels={ref: kernel_spec(warmup=5)})
    b = Library(components={}, bodies={}, kernels={ref: kernel_spec(warmup=9)})
    with pytest.raises(LibraryConflict, match="kernel declarations"):
        compose([_Contributor(a, {ref: lambda p, i, c: {}}),
                 _Contributor(b, {ref: lambda p, i, c: {}})])


def test_one_address_may_not_execute_two_functions():
    """C13 keys the runtime on the address alone, so two functions at one address is the
    one thing that would make evaluation depend on import order."""
    ref = "sha256:" + "2" * 64
    lib = Library(components={}, bodies={}, kernels={})
    with pytest.raises(LibraryConflict, match="two different functions"):
        compose([_Contributor(lib, {ref: lambda p, i, c: {}}),
                 _Contributor(lib, {ref: lambda p, i, c: {}})])


def test_declared_kernel_without_implementation_is_refused():
    from app.ir.kernels import kernel_spec

    ref = "sha256:" + "3" * 64
    lib = Library(components={}, bodies={}, kernels={ref: kernel_spec(warmup=1)})
    with pytest.raises(LibraryConflict, match="no implementation"):
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
