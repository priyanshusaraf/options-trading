"""
RFC 0001 §4 — the fourteen contract clauses that constrain resolution.

C13 landed in the previous phase because it is a property of the executor that
already exists. These fourteen are properties of *resolution*, and until
`app/ir/resolve.py` existed a test for any of them would have asserted against
nothing — a conformance suite with no implementation to run against, which is
this codebase's documented unconsumed-mechanism defect wearing a conformance
badge. They land with the resolver, in this file.

Appendix A.4 is the worked case the RFC supplies for C4 and C7 together, so it
is built here as real data and resolved: two instances of one definition that
must stay distinguishable, with `n_fast/n_smooth` and `n_slow/n_smooth` stable
across re-resolution.
"""
from __future__ import annotations

import copy
import pathlib
import re
from dataclasses import FrozenInstanceError

import pytest

from app.ir.hashing import canonical_json, content_address
from app.ir.kernels import KernelDeclarationError, kernel_registry, kernel_spec
from app.ir.resolve import (
    BOUNDARY_INPUT,
    BOUNDARY_OUTPUT,
    Library,
    ResolutionError,
    body_for,
    publish,
    resolve,
)
from app.ir.validate import validate

FV = 1


# ── the fixture library: Appendix A.2's decomposed ATR, made real ─────────
#
# A.2 is the artefact the acceptance set exists for: a component whose body is
# a graph, so "fork ATR, replace the smoothing" is a component-reference change.
# Resolution is what turns that claim into an observable property.

def wire(value="float", structure="series", instrument="NIFTY", timeframe="15m"):
    return {"value": value, "structure": structure,
            "domain": {"instrument": instrument, "timeframe": timeframe}}


def socket(identifier, direction, **extra):
    return {"item": "socket", "identifier": identifier, "display_name": identifier,
            "direction": direction, "wire_type": wire(), **extra}


def param(identifier, kind, default):
    return {"item": "parameter", "identifier": identifier, "display_name": identifier,
            "kind": kind, "default": default}


def kernel_component(identifier, version, interface, seed=None):
    return {
        "format_version": FV, "kind": "component", "identifier": identifier,
        "version": version, "display_name": identifier, "interface": interface,
        "body": {"body": "kernel", "ref": content_address(seed or identifier)},
    }


def boundary(instance, identifier):
    return {"instance_id": instance, "component": {"identifier": identifier, "version": 1},
            "overrides": {}}


TRUE_RANGE = kernel_component("indicator.true_range", 1, [
    socket("high", "input"), socket("low", "input"), socket("close", "input"),
    socket("out", "output"),
])

WILDER = kernel_component("smoothing.wilder", 1, [
    socket("in", "input"), param("length", "length", 14), socket("out", "output"),
])

EMA = kernel_component("smoothing.ema", 1, [
    socket("in", "input"), param("length", "length", 14), socket("out", "output"),
])

COMPARE_GT = kernel_component("compare.gt", 1, [
    socket("a", "input"), socket("b", "input"),
    {"item": "socket", "identifier": "out", "display_name": "out",
     "direction": "output", "wire_type": wire(value="bool")},
])

# A.2's body. `override length ← length` is the parameter reference: the ATR
# component forwards its own `length` into the smoothing node inside it.
ATR_BODY = {
    "format_version": FV, "kind": "graph",
    "identifier": "indicator.atr.wilder.body", "version": 1,
    "display_name": "ATR (Wilder) body",
    "interface": [
        socket("high", "input"), socket("low", "input"), socket("close", "input"),
        param("length", "length", 14), socket("atr", "output"),
    ],
    "nodes": [
        boundary("io_in", BOUNDARY_INPUT),
        {"instance_id": "n_tr", "component": {"identifier": "indicator.true_range",
                                              "version": 1}, "overrides": {}},
        {"instance_id": "n_smooth", "component": {"identifier": "smoothing.wilder",
                                                  "version": 1},
         "overrides": {"length": {"param_ref": "length"}}},
        boundary("io_out", BOUNDARY_OUTPUT),
    ],
    "edges": [
        {"source": {"instance": "io_in", "socket": "high"},
         "target": {"instance": "n_tr", "socket": "high"}},
        {"source": {"instance": "io_in", "socket": "low"},
         "target": {"instance": "n_tr", "socket": "low"}},
        {"source": {"instance": "io_in", "socket": "close"},
         "target": {"instance": "n_tr", "socket": "close"}},
        {"source": {"instance": "n_tr", "socket": "out"},
         "target": {"instance": "n_smooth", "socket": "in"}},
        {"source": {"instance": "n_smooth", "socket": "out"},
         "target": {"instance": "io_out", "socket": "atr"}},
    ],
    "groups": [],
}

ATR = {
    "format_version": FV, "kind": "component",
    "identifier": "indicator.atr.wilder", "version": 1,
    "display_name": "ATR (Wilder)",
    "interface": [
        socket("high", "input"), socket("low", "input"), socket("close", "input"),
        param("length", "length", 14), socket("atr", "output"),
    ],
    "body": {"body": "graph", "ref": content_address(ATR_BODY)},
}

# A.4 — one definition referenced twice, at two lengths.
DUAL_ATR = {
    "format_version": FV, "kind": "graph",
    "identifier": "strategy.dual_atr_filter", "version": 1,
    "display_name": "Dual ATR Filter",
    "interface": [
        socket("high", "input"), socket("low", "input"), socket("close", "input"),
        {"item": "socket", "identifier": "signal", "display_name": "signal",
         "direction": "output", "wire_type": wire(value="bool")},
    ],
    "nodes": [
        boundary("io_in", BOUNDARY_INPUT),
        {"instance_id": "n_fast",
         "component": {"identifier": "indicator.atr.wilder", "version": 1},
         "overrides": {"length": 7}},
        {"instance_id": "n_slow",
         "component": {"identifier": "indicator.atr.wilder", "version": 1},
         "overrides": {"length": 21}},
        {"instance_id": "n_cmp", "component": {"identifier": "compare.gt", "version": 1},
         "overrides": {}},
        boundary("io_out", BOUNDARY_OUTPUT),
    ],
    "edges": [
        {"source": {"instance": "io_in", "socket": "high"},
         "target": {"instance": "n_fast", "socket": "high"}},
        {"source": {"instance": "io_in", "socket": "low"},
         "target": {"instance": "n_fast", "socket": "low"}},
        {"source": {"instance": "io_in", "socket": "close"},
         "target": {"instance": "n_fast", "socket": "close"}},
        {"source": {"instance": "io_in", "socket": "high"},
         "target": {"instance": "n_slow", "socket": "high"}},
        {"source": {"instance": "io_in", "socket": "low"},
         "target": {"instance": "n_slow", "socket": "low"}},
        {"source": {"instance": "io_in", "socket": "close"},
         "target": {"instance": "n_slow", "socket": "close"}},
        {"source": {"instance": "n_fast", "socket": "atr"},
         "target": {"instance": "n_cmp", "socket": "a"}},
        {"source": {"instance": "n_slow", "socket": "atr"},
         "target": {"instance": "n_cmp", "socket": "b"}},
        {"source": {"instance": "n_cmp", "socket": "out"},
         "target": {"instance": "io_out", "socket": "signal"}},
    ],
    "groups": [],
}


KERNELS = kernel_registry({
    TRUE_RANGE["body"]["ref"]: {"warmup": 1},
    WILDER["body"]["ref"]: {"warmup": 14},
    EMA["body"]["ref"]: {"warmup": 14},
    COMPARE_GT["body"]["ref"]: {},
})


def library(**overrides):
    lib = Library(
        components={
            ("indicator.true_range", 1): TRUE_RANGE,
            ("smoothing.wilder", 1): WILDER,
            ("smoothing.ema", 1): EMA,
            ("compare.gt", 1): COMPARE_GT,
            ("indicator.atr.wilder", 1): ATR,
        },
        bodies={ATR["body"]["ref"]: ATR_BODY},
        kernels=KERNELS,
    )
    if not overrides:
        return lib
    return Library(
        components={**lib.components, **overrides.get("components", {})},
        bodies={**lib.bodies, **overrides.get("bodies", {})},
        kernels={**lib.kernels, **overrides.get("kernels", {})},
    )


@pytest.fixture
def resolved():
    return resolve(DUAL_ATR, library())


# ── the fixtures are conforming artefacts, not convenient shapes ──────────

@pytest.mark.parametrize("artefact", [ATR, ATR_BODY, DUAL_ATR, TRUE_RANGE, WILDER,
                                      COMPARE_GT], ids=lambda a: a["identifier"])
def test_every_fixture_passes_the_section_3_validator(artefact):
    """A resolver proved correct against artefacts the format rejects would
    prove nothing. `{"param_ref": ...}` in particular must be a legal override."""
    assert validate(artefact) == []


# ── C1 — resolution is deterministic ──────────────────────────────────────

def test_c1_the_same_specification_resolves_to_the_same_graph():
    a = resolve(DUAL_ATR, library())
    b = resolve(DUAL_ATR, library())
    assert a == b


def test_c1_node_order_is_the_specifications_order_not_the_visit_order():
    """Topological order is how cache identity is computed; it must not leak
    into the output, or a semantically irrelevant reordering of the input would
    change the resolved graph."""
    ids = [n.instance_id for n in resolve(DUAL_ATR, library()).nodes]
    assert ids == [
        "n_fast/n_tr", "n_fast/n_smooth",
        "n_slow/n_tr", "n_slow/n_smooth",
        "n_cmp",
    ]


# ── C2 / C6 — no side effects, no hidden state ────────────────────────────

def test_c2_resolution_does_not_mutate_the_specification():
    """Two checks, because one of them is not enough and the suppression sweep
    proved it. Deep-copying the shared fixture and comparing before to after
    sees nothing once an earlier test has already resolved it: a resolver that
    eats its input does so on the first call and is idempotent thereafter. So
    the second check resolves the *shared* specification and asserts it is
    still intact — which is the property, stated directly."""
    spec = copy.deepcopy(DUAL_ATR)
    before = copy.deepcopy(spec)
    body = copy.deepcopy(ATR_BODY)
    body_before = copy.deepcopy(body)

    resolve(spec, library(bodies={ATR["body"]["ref"]: body}))

    assert spec == before
    assert body == body_before

    resolve(DUAL_ATR, library())
    assert DUAL_ATR["nodes"][1]["overrides"] == {"length": 7}
    assert ATR_BODY["nodes"][2]["overrides"] == {"length": {"param_ref": "length"}}


SOURCE = pathlib.Path(__file__).resolve().parents[1] / "app" / "ir" / "resolve.py"

# Every way a resolution could stop being a function of its inputs. C7 names
# three of them explicitly: "MUST NOT derive from clocks, counters, or
# randomness".
IMPURE_NAMES = ("random", "datetime", "time.time", "uuid", "os.environ",
                "open(", "requests", "itertools.count", "id(")


def test_c6_the_resolver_reads_nothing_but_its_arguments():
    """The enforcement is an absence, as C13's is. If this goes red the fix is
    not to widen the list — it is to ask what the resolver needed to look up."""
    text = SOURCE.read_text()
    hits = [name for name in IMPURE_NAMES if name in text]
    assert hits == [], f"C6: resolution must introduce no hidden state — {hits}"


def test_c6_a_parameter_reference_to_nothing_is_refused():
    """Falling back to a default here would invent a value the specification
    does not carry, which is exactly the hidden state C6 forbids."""
    body = copy.deepcopy(ATR_BODY)
    body["nodes"][2]["overrides"]["length"] = {"param_ref": "not_a_parameter"}
    with pytest.raises(ResolutionError) as exc:
        resolve(DUAL_ATR, library(bodies={ATR["body"]["ref"]: body}))
    assert exc.value.clause == "C6"


# ── C3 — resolution preserves semantics ───────────────────────────────────

def test_c3_the_resolved_graph_is_not_editable(resolved):
    """"Never authored, never edited, never a source of truth." A frozen
    dataclass with read-only mappings makes that a property of the object."""
    with pytest.raises(FrozenInstanceError):
        resolved.nodes[0].instance_id = "anything"
    with pytest.raises(TypeError):
        resolved.nodes[0].params["length"] = 99


def test_c3_authored_connectivity_survives_expansion(resolved):
    """The authored edge `n_fast.atr → n_cmp.a` names a socket on a component
    whose body is a graph. After lowering it must connect the node that really
    produces the value to the node that really consumes it — with no boundary
    node left behind."""
    edges = {(e.source, e.target) for e in resolved.edges}
    assert (("n_fast/n_smooth", "out"), ("n_cmp", "a")) in edges
    assert (("n_slow/n_smooth", "out"), ("n_cmp", "b")) in edges
    assert not any(BOUNDARY_INPUT in n.instance_id or BOUNDARY_OUTPUT in n.instance_id
                   for n in resolved.nodes)


def test_c3_the_graphs_own_interface_is_reported_not_dropped(resolved):
    """A graph's inputs are consumed by real nodes after lowering, and its
    outputs are produced by them. Losing that mapping would make the resolved
    graph unusable as the thing an executor runs."""
    assert set(resolved.inputs) == {"high", "low", "close"}
    assert ("n_fast/n_tr", "high") in resolved.inputs["high"]
    assert ("n_slow/n_tr", "high") in resolved.inputs["high"]
    assert resolved.outputs == {"signal": ("n_cmp", "out")}


def test_c3_resolution_refuses_duplicate_targets_when_validation_is_bypassed():
    """Resolution cannot let document order select one of two v1 producers."""
    spec = copy.deepcopy(DUAL_ATR)
    spec["edges"].append({
        "source": {"instance": "n_slow", "socket": "atr"},
        "target": {"instance": "n_cmp", "socket": "a"},
    })

    with pytest.raises(ResolutionError, match="more than one incoming edge"):
        resolve(spec, library())


@pytest.mark.parametrize("mutation", ["undeclared_input", "duplicate_output"])
def test_c3_graph_boundaries_are_declared_and_outputs_are_unique(mutation):
    """Boundary socket spelling and single-output cardinality survive validator bypass."""
    spec = copy.deepcopy(ATR_BODY)
    if mutation == "undeclared_input":
        spec["edges"][0]["source"]["socket"] = "ghost"
    else:
        spec["edges"].append({
            "source": {"instance": "n_tr", "socket": "out"},
            "target": {"instance": "io_out", "socket": "atr"},
        })

    with pytest.raises(ResolutionError, match="declared|more than one producer"):
        resolve(spec, library())


def test_c3_graph_component_public_interface_must_equal_its_body_at_resolution():
    component = copy.deepcopy(ATR)
    component["interface"] = component["interface"][:-1]

    with pytest.raises(ResolutionError, match="public interface differs"):
        resolve(component, library())


def test_c3_resolution_rejects_leaf_socket_direction_when_validation_is_bypassed():
    spec = copy.deepcopy(ATR_BODY)
    spec["edges"][3]["source"]["socket"] = "high"

    with pytest.raises(ResolutionError, match="declared output"):
        resolve(spec, library())


def test_c3_resolution_rejects_declared_output_without_a_producer():
    spec = copy.deepcopy(ATR_BODY)
    spec["edges"].pop()

    with pytest.raises(ResolutionError, match="exactly one producer"):
        resolve(spec, library())


def test_c3_an_override_that_binds_to_nothing_is_refused():
    spec = copy.deepcopy(DUAL_ATR)
    spec["nodes"][1]["overrides"]["lenght"] = 7   # a typo, not a parameter
    with pytest.raises(ResolutionError) as exc:
        resolve(spec, library())
    assert exc.value.clause == "C3"
    assert "lenght" in exc.value.path


# ── C4 — derived elements carry back-references ───────────────────────────

def test_c4_two_instances_of_one_definition_stay_distinguishable(resolved):
    """Appendix A.4's first requirement, verbatim: `n_fast` and `n_slow` expand
    from the same definition and MUST remain distinguishable."""
    smoothers = [n for n in resolved.nodes if n.definition == ("smoothing.wilder", 1)]
    assert len(smoothers) == 2
    assert {n.authored_root for n in smoothers} == {"n_fast", "n_slow"}
    assert smoothers[0].params["length"] == 7
    assert smoothers[1].params["length"] == 21


def test_c4_every_expanded_node_traces_to_the_definition_it_came_from(resolved):
    assert {n.definition for n in resolved.nodes} <= set(resolved.versions)
    assert all(n.path[0] in {"n_fast", "n_slow", "n_cmp"} for n in resolved.nodes)


def test_c4_a_failure_inside_a_body_is_reported_against_the_authored_node():
    """Appendix A.4's third requirement: "an error inside the smoothing node
    reported against the authored graph's vocabulary, naming `n_fast`, not
    against a generated node the author never placed"."""
    lib = library()
    broken = {k: v for k, v in lib.kernels.items() if k != WILDER["body"]["ref"]}
    with pytest.raises(ResolutionError) as exc:
        resolve(DUAL_ATR, Library(lib.components, lib.bodies, broken))
    assert exc.value.path.startswith("n_fast")
    assert "n_smooth" in exc.value.path


# ── C5 — version identity is preserved and recorded ───────────────────────

def test_c5_every_resolved_identifier_version_pair_is_recorded(resolved):
    assert resolved.versions == (
        ("compare.gt", 1),
        ("indicator.atr.wilder", 1),
        ("indicator.true_range", 1),
        ("smoothing.wilder", 1),
    )


def test_c5_an_unresolvable_reference_is_refused_not_guessed():
    """"A version distinguishing bodies under that identifier" is only useful
    if a missing one stops the resolution. Falling back to the newest available
    would make every recorded result unattributable — F14's failure mode."""
    lib = library()
    thinned = {k: v for k, v in lib.components.items() if k != ("compare.gt", 1)}
    with pytest.raises(ResolutionError) as exc:
        resolve(DUAL_ATR, Library(thinned, lib.bodies, lib.kernels))
    assert exc.value.clause == "C5"


def test_c5_a_fork_resolves_to_a_different_recorded_version():
    """A.2's whole point: fork ATR, replace the smoothing. The fork is a new
    version whose body references `smoothing.ema`, and the record says so."""
    forked_body = copy.deepcopy(ATR_BODY)
    forked_body["nodes"][2]["component"] = {"identifier": "smoothing.ema", "version": 1}
    forked = copy.deepcopy(ATR)
    forked.update(version=2, parent_version=1,
                  body={"body": "graph", "ref": content_address(forked_body)})

    spec = copy.deepcopy(DUAL_ATR)
    spec["nodes"][1]["component"] = {"identifier": "indicator.atr.wilder", "version": 2}

    out = resolve(spec, library(components={("indicator.atr.wilder", 2): forked},
                                bodies={forked["body"]["ref"]: forked_body}))
    assert ("indicator.atr.wilder", 2) in out.versions
    assert ("smoothing.ema", 1) in out.versions
    assert out.node("n_fast/n_smooth").definition == ("smoothing.ema", 1)


# ── C7 — reproducibility; ids derive from the instance path ───────────────

def test_c7_instance_identifiers_are_the_instance_path(resolved):
    """Appendix A.4's second requirement, verbatim: `n_fast/n_smooth`,
    `n_slow/n_smooth` — "rather than from a counter"."""
    assert {n.instance_id for n in resolved.nodes} == {
        "n_fast/n_tr", "n_fast/n_smooth",
        "n_slow/n_tr", "n_slow/n_smooth",
        "n_cmp",
    }


def test_c7_re_resolution_is_identical_even_after_an_unrelated_resolution():
    """A counter would survive this only if it were reset between calls, and a
    counter that must be reset between calls is the bug, not the fix."""
    first = resolve(DUAL_ATR, library())
    resolve(ATR, library())          # something else, in between
    assert [n.instance_id for n in resolve(DUAL_ATR, library()).nodes] == \
           [n.instance_id for n in first.nodes]


def test_c7_reordering_the_nodes_does_not_rename_anything():
    """Position in a list is a counter in disguise. If it fed the identifier,
    dragging a node in an editor would rename it."""
    spec = copy.deepcopy(DUAL_ATR)
    spec["nodes"][1], spec["nodes"][2] = spec["nodes"][2], spec["nodes"][1]
    assert {n.instance_id for n in resolve(spec, library()).nodes} == \
           {n.instance_id for n in resolve(DUAL_ATR, library()).nodes}


# ── C8 — cache identity: transitive by default, declarable ────────────────

def test_c8_identity_is_transitive_over_the_upstream_subgraph(resolved):
    """Prefect's `TaskSource` excludes nested tasks, so a change deep in a
    subgraph leaves the cache key of everything downstream unchanged. Change
    `n_fast`'s length and `n_cmp`, three hops downstream, must move."""
    spec = copy.deepcopy(DUAL_ATR)
    spec["nodes"][1]["overrides"]["length"] = 8
    after = resolve(spec, library())

    assert resolved.node("n_cmp").cache_id != after.node("n_cmp").cache_id
    assert resolved.node("n_slow/n_smooth").cache_id == after.node("n_slow/n_smooth").cache_id


def test_c8_a_declared_identity_is_not_its_inputs():
    """"MAY be declared per component", for components whose identity genuinely
    is not their inputs. A declared node's key must therefore *not* move when
    its upstream does."""
    declared = kernel_registry({
        **{k: v for k, v in KERNELS.items()},
        COMPARE_GT["body"]["ref"]: {"cache_identity": "declared",
                                    "cache_key": "compare.gt@1"},
    })
    lib = library()
    base = resolve(DUAL_ATR, Library(lib.components, lib.bodies, declared))

    spec = copy.deepcopy(DUAL_ATR)
    spec["nodes"][1]["overrides"]["length"] = 8
    after = resolve(spec, Library(lib.components, lib.bodies, declared))
    assert base.node("n_cmp").cache_id == after.node("n_cmp").cache_id


def test_c8_which_socket_an_input_arrives_on_is_part_of_the_identity(resolved):
    """`gt(fast, slow)` and `gt(slow, fast)` are different computations. An
    identity over an unordered set of upstream keys would collide them."""
    spec = copy.deepcopy(DUAL_ATR)
    a, b = spec["edges"][6], spec["edges"][7]
    a["target"]["socket"], b["target"]["socket"] = "b", "a"
    assert resolve(spec, library()).node("n_cmp").cache_id != resolved.node("n_cmp").cache_id


def test_c8_a_declared_identity_must_say_what_it_is():
    with pytest.raises(KernelDeclarationError) as exc:
        kernel_spec(cache_identity="declared")
    assert exc.value.clause == "C8"


# ── C9 — purity; impurity only as a declared policy ───────────────────────

def test_c9_a_kernel_cannot_declare_an_escape_hatch():
    """ComfyUI's `IS_CHANGED` by name. C9 forbids the hatch existing, not its
    use, so the rejection is at declaration time."""
    with pytest.raises(KernelDeclarationError) as exc:
        kernel_spec(is_changed="lambda: True")
    assert exc.value.clause == "C9"


def test_c9_impurity_must_name_a_policy_from_the_closed_set():
    assert kernel_spec(purity="broker_state").purity == "broker_state"
    with pytest.raises(KernelDeclarationError) as exc:
        kernel_spec(purity="impure")
    assert exc.value.clause == "C9"


def test_c9_a_declared_policy_reaches_the_resolved_node():
    """A policy nothing can read is not a policy. This is the wiring check the
    unconsumed-mechanism defect exists to catch."""
    impure = kernel_registry({
        **KERNELS,
        COMPARE_GT["body"]["ref"]: {"purity": "account_state"},
    })
    lib = library()
    out = resolve(DUAL_ATR, Library(lib.components, lib.bodies, impure))
    assert out.node("n_cmp").purity == "account_state"
    assert out.node("n_fast/n_tr").purity == "pure"


# ── C10 — warmup is derived per component and composes ────────────────────

def test_c10_warmup_composes_through_the_graph(resolved):
    """True range needs 1 bar; Wilder smoothing needs 14 more; the comparison
    needs none of its own but cannot produce a value before its inputs can."""
    assert resolved.node("n_fast/n_tr").warmup == 1
    assert resolved.node("n_fast/n_smooth").warmup == 15
    assert resolved.node("n_cmp").warmup == 15
    assert resolved.warmup == 15


def test_c10_warmup_follows_the_deepest_chain_not_the_last_one():
    """max, not the most recently visited. A graph that warms up for its
    shallowest input produces its first bars from an unwarmed indicator, which
    is a silently wrong backtest rather than an error."""
    deep = kernel_registry({**KERNELS, WILDER["body"]["ref"]: {"warmup": 200}})
    lib = library()
    out = resolve(DUAL_ATR, Library(lib.components, lib.bodies, deep))
    assert out.node("n_cmp").warmup == 201


def test_c10_a_cycle_is_refused_because_composition_is_undefined_on_one():
    spec = copy.deepcopy(DUAL_ATR)
    spec["edges"].append({"source": {"instance": "n_cmp", "socket": "out"},
                          "target": {"instance": "n_fast", "socket": "high"}})
    with pytest.raises(ResolutionError) as exc:
        resolve(spec, library())
    assert exc.value.clause == "C10"


def test_c10_graph_body_cycle_precedes_component_interface_drift():
    body = copy.deepcopy(ATR_BODY)
    body["edges"].append({
        "source": {"instance": "n_smooth", "socket": "out"},
        "target": {"instance": "n_tr", "socket": "high"},
    })
    component = copy.deepcopy(ATR)
    component["interface"] = component["interface"][:-1]
    component["body"]["ref"] = content_address(body)
    lib = library(
        components={(component["identifier"], component["version"]): component},
        bodies={component["body"]["ref"]: body},
    )

    with pytest.raises(ResolutionError) as exc:
        resolve(component, lib)
    assert exc.value.clause == "C10"


# ── C11 — lookahead is prevented structurally ─────────────────────────────

def test_c11_a_negative_warmup_is_unrepresentable():
    """"A component MUST NOT be able to violate it by convention." Warmup is
    the only temporal declaration a kernel has and it counts backwards, so
    refusing a negative one refuses every way of asking for a future bar."""
    with pytest.raises(KernelDeclarationError) as exc:
        kernel_spec(warmup=-1)
    assert exc.value.clause == "C11"


def test_c11_there_is_no_forward_offset_to_declare():
    """The structural half of the clause: the vocabulary a kernel may use has
    no field that could name a future bar. If one is added, this goes red."""
    from app.ir import kernels
    assert set(kernels.KernelSpec.__dataclass_fields__) == {
        "warmup", "purity", "cache_identity", "cache_key", "causal"}


# ── C12 — research and live share one resolution ──────────────────────────

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def test_c12_there_is_exactly_one_resolver():
    """The `candles.py` defect was two hand-written implementations of one
    idea, and this clause exists because of it. Parity is structural only while
    there is nothing to drift from.

    The signal is *building* a resolved graph, not the word "resolve" — config
    scoping legitimately has a `resolve()` and a guard that fired on it would
    be turned off. A second resolution has to construct the output type."""
    pattern = re.compile(r"\bResolvedGraph\(|^def lower\(", re.M)
    hits = sorted(
        str(p.relative_to(BACKEND))
        for p in list((BACKEND / "app").rglob("*.py")) + list(
            (BACKEND.parent / "research").rglob("*.py"))
        if pattern.search(p.read_text())
    )
    assert hits == ["app/ir/resolve.py"], f"C12: more than one resolution — {hits}"


def test_c12_resolution_cannot_be_told_which_plane_it_is_running_in():
    """A resolution that takes a mode can differ by mode. The absence of the
    parameter is what makes one resolution structural rather than tested."""
    import inspect
    names = set(inspect.signature(resolve).parameters)
    assert names == {"spec", "library", "parameters"}


# ── C14 — components compute; searchers search ────────────────────────────

def test_c14_an_override_may_not_be_a_grid():
    """vectorbt builds parameter grids into the indicator contract itself,
    which silently defines search = parameter sweeping for everything
    downstream. A list here is that decision, made by accident."""
    spec = copy.deepcopy(DUAL_ATR)
    spec["nodes"][1]["overrides"]["length"] = [7, 14, 21]
    with pytest.raises(ResolutionError) as exc:
        resolve(spec, library())
    assert exc.value.clause == "C14"
    assert validate(spec) and validate(spec)[0].clause == "C14"


def test_c14_a_searcher_supplies_one_value_per_candidate():
    """The conforming shape: the searcher calls resolution once per candidate,
    and the component never learns a search is happening."""
    lengths = [7, 14, 21]
    spec = copy.deepcopy(ATR)
    keys = {
        n: resolve(spec, library(), parameters={"length": n}).node(
            "n_smooth").params["length"]
        for n in lengths
    }
    assert keys == {7: 7, 14: 14, 21: 21}


# ── C15 — publishing a subgraph is a mechanical derivation ────────────────

def test_c15_publishing_introduces_nothing_the_interface_did_not_carry():
    component = publish(DUAL_ATR)
    assert component["interface"] is DUAL_ATR["interface"]
    assert set(component) - set(DUAL_ATR) == {"body"}
    assert set(DUAL_ATR) - set(component) == {"nodes", "edges", "groups"}
    assert validate(component) == []


def test_c15_a_published_subgraph_resolves_identically_to_the_subgraph():
    """The equivalence evidence. "A subgraph and a component are the same kind
    of thing" is a claim until the two resolve to the same nodes and edges."""
    component = publish(DUAL_ATR)
    ref, body = body_for(DUAL_ATR)

    direct = resolve(DUAL_ATR, library())
    published = resolve(component, library(bodies={ref: body}))

    assert published.nodes == direct.nodes
    assert published.edges == direct.edges
    assert published.outputs == direct.outputs


def test_c15_the_published_body_address_is_the_graphs_content():
    """Content-addressed, per F2 — so republishing an unchanged graph is a
    no-op and reformatting it is not a new body."""
    ref, _ = body_for(DUAL_ATR)
    assert publish(DUAL_ATR)["body"]["ref"] == ref
    reordered = {k: DUAL_ATR[k] for k in reversed(list(DUAL_ATR))}
    assert content_address(reordered) == ref


def test_c15_only_a_graph_can_be_published():
    with pytest.raises(ResolutionError) as exc:
        publish(ATR)
    assert exc.value.clause == "C15"


# ── F8 — a default source is inserted, and it is a derived element ────────

WARMUP_ZERO_CLOSE = kernel_component("market.close", 1, [socket("out", "output")])


def test_f8_an_unwired_input_with_a_declared_source_resolves():
    """"A graph whose unwired inputs all declare sources MUST be valid." This
    is what makes graph mutation a local edit rather than a constraint problem."""
    tr = copy.deepcopy(TRUE_RANGE)
    tr["interface"][2]["default_source"] = {
        "component": {"identifier": "market.close", "version": 1}, "socket": "out"}
    assert validate(tr) == []

    spec = copy.deepcopy(ATR_BODY)
    spec["edges"] = [e for e in spec["edges"]
                     if e["target"].get("socket") != "close"]

    out = resolve(spec, library(
        components={("indicator.true_range", 1): tr,
                    ("market.close", 1): WARMUP_ZERO_CLOSE},
        kernels=kernel_registry({WARMUP_ZERO_CLOSE["body"]["ref"]: {}})))

    inserted = out.node("n_tr/close@default")
    assert inserted is not None
    # C4 — an inserted element carries a back-reference to what it came from,
    # and C7 — its identifier is its path, not a counter.
    assert inserted.derived_from == "n_tr.close"
    assert inserted.definition == ("market.close", 1)
    assert any(e.derived and e.target == ("n_tr", "close") for e in out.edges)


def test_f8_a_wired_input_gets_no_default_even_when_it_declares_one(resolved):
    """The wire wins. Inserting anyway would silently double-feed a socket —
    and inside a subgraph the wire arrives from the graph one level up, which
    is why insertion runs after the whole specification is expanded."""
    tr = copy.deepcopy(TRUE_RANGE)
    tr["interface"][2]["default_source"] = {
        "component": {"identifier": "market.close", "version": 1}, "socket": "out"}
    out = resolve(DUAL_ATR, library(
        components={("indicator.true_range", 1): tr,
                    ("market.close", 1): WARMUP_ZERO_CLOSE},
        kernels=kernel_registry({WARMUP_ZERO_CLOSE["body"]["ref"]: {}})))
    assert [n.instance_id for n in out.nodes] == \
           [n.instance_id for n in resolved.nodes]


# ── the domain axis survives lowering ─────────────────────────────────────

def test_a_pinned_domain_is_inherited_by_everything_inside_the_body():
    """A.5's domain axis is a type-level concern, but it has to reach the
    resolved leaves or an executor cannot know which series to feed them."""
    spec = copy.deepcopy(DUAL_ATR)
    spec["nodes"][1]["domain"] = {"instrument": "NIFTY", "timeframe": "5m"}
    out = resolve(spec, library())
    assert dict(out.node("n_fast/n_smooth").domain) == {"instrument": "NIFTY",
                                                        "timeframe": "5m"}
    assert out.node("n_slow/n_smooth").domain is None


def test_the_domain_is_part_of_cache_identity(resolved):
    spec = copy.deepcopy(DUAL_ATR)
    spec["nodes"][1]["domain"] = {"instrument": "NIFTY", "timeframe": "5m"}
    assert resolve(spec, library()).node("n_fast/n_smooth").cache_id != \
        resolved.node("n_fast/n_smooth").cache_id


# ── canonical addressing ──────────────────────────────────────────────────

def test_key_order_does_not_change_a_content_address():
    assert content_address({"a": 1, "b": 2}) == content_address({"b": 2, "a": 1})


def test_a_content_address_refuses_values_json_cannot_round_trip():
    with pytest.raises(ValueError):
        canonical_json({"x": float("nan")})
