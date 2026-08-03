"""
RFC 0001 conformance — §3 Format clauses.

The RFC's own status block is blunt about what it is not: "Nothing mechanically
validates an artefact against §3 ... conformance is a claim made by an
implementer, not a fact established by a test." This file, with
`app/ir/validate.py`, is what turns that claim into a fact for §3.

One test per clause F1–F13, each written so it can go red: every clause test
builds a *valid* artefact and then breaks exactly the thing the clause forbids,
so a validator that silently stopped checking would fail here rather than pass
quietly.

F14 (result binding) has no artefact in this grammar and is enforced by
`app/ir/experiment.py` — see `test_f14_is_enforced_by_the_experiment_system_not_by_this_validator`.
"""
from __future__ import annotations

import copy

import pytest

from app.ir.schema import KINDS, STRUCTURE_TYPES, SUPPORTED_FORMAT_VERSION, VALUE_TYPES
from app.ir.validate import clauses_violated, validate


# ── fixtures: the smallest artefacts that pass ────────────────────────────

def wire(value="float", structure="series", instrument="NIFTY", timeframe="15m"):
    return {
        "value": value,
        "structure": structure,
        "domain": {"instrument": instrument, "timeframe": timeframe},
    }


BODY_HASH = "sha256:" + "a" * 64


def a_component():
    """A minimal conforming component-def."""
    return {
        "format_version": SUPPORTED_FORMAT_VERSION,
        "kind": "component",
        "identifier": "indicator.ema",
        "version": 1,
        "display_name": "EMA",
        "interface": [
            {"item": "socket", "identifier": "source", "display_name": "Source",
             "direction": "input", "wire_type": wire()},
            {"item": "parameter", "identifier": "length", "display_name": "Length",
             "kind": "length", "bounds": {"min": 1, "max": 500}, "default": 20},
            {"item": "socket", "identifier": "out", "display_name": "Out",
             "direction": "output", "wire_type": wire()},
        ],
        "body": {"body": "kernel", "ref": BODY_HASH},
    }


def a_graph():
    """A minimal conforming graph-def with two nodes and one edge."""
    return {
        "format_version": SUPPORTED_FORMAT_VERSION,
        "kind": "graph",
        "identifier": "strategy.demo",
        "version": 1,
        "display_name": "Demo",
        "interface": [
            {"item": "socket", "identifier": "longEntry", "display_name": "Long Entry",
             "direction": "output", "wire_type": wire(value="bool")},
        ],
        "nodes": [
            {"instance_id": "n_ema", "component": {"identifier": "indicator.ema", "version": 1},
             "overrides": {"length": 50}},
            {"instance_id": "n_cmp", "component": {"identifier": "compare.gt", "version": 1},
             "overrides": {}},
        ],
        "edges": [
            {"source": {"instance": "n_ema", "socket": "out"},
             "target": {"instance": "n_cmp", "socket": "a"}},
        ],
        "groups": [],
    }


def assert_valid(artefact):
    violations = validate(artefact)
    assert violations == [], f"expected valid, got {violations}"


def assert_violates(artefact, clause):
    violated = clauses_violated(artefact)
    assert clause in violated, f"expected {clause} violated, got {sorted(violated)}"


# ── the fixtures themselves must pass, or every negative test is vacuous ──

def test_the_valid_component_fixture_validates():
    assert_valid(a_component())


def test_the_valid_graph_fixture_validates():
    assert_valid(a_graph())


# ── F1 — artefact envelope ────────────────────────────────────────────────

def test_f1_requires_format_version():
    art = a_component()
    del art["format_version"]
    assert_violates(art, "F1")


def test_f1_requires_kind():
    art = a_component()
    del art["kind"]
    assert_violates(art, "F1")


def test_f1_rejects_an_unknown_kind():
    art = a_component()
    art["kind"] = "experiment"
    assert_violates(art, "F1")


def test_f1_rejects_a_future_format_version_wholesale():
    """"A reader MUST reject an artefact whose format_version it does not
    understand, and MUST NOT attempt to interpret it partially." So an artefact
    from the future must report F1 and *nothing else* — reporting further
    clause violations would mean we had gone on to interpret it."""
    art = a_component()
    art["format_version"] = SUPPORTED_FORMAT_VERSION + 1
    art["identifier"] = ""            # would be an F2 violation if interpreted
    assert clauses_violated(art) == {"F1"}


# ── F2 — component identity ───────────────────────────────────────────────

def test_f2_requires_a_non_empty_identifier():
    art = a_component()
    art["identifier"] = ""
    assert_violates(art, "F2")


def test_f2_requires_a_version():
    art = a_component()
    del art["version"]
    assert_violates(art, "F2")


def test_f2_requires_a_display_name_separate_from_the_identifier():
    art = a_component()
    del art["display_name"]
    assert_violates(art, "F2")


def test_f2_requires_the_body_to_be_content_addressed():
    """A body stored by name rather than by content address defeats F2's
    'stored once' — and Appendix A.3 records the live case: generated
    strategies use a content hash as their *identity*, which F2 makes the
    body's address instead."""
    art = a_component()
    art["body"] = {"body": "kernel", "ref": "expanding_z_v4.py"}
    assert_violates(art, "F2")


def test_f2_display_name_is_never_referenced():
    """The clause that costs one field and saves every stored graph from the
    first rename. What is mechanically enforceable is that the grammar gives a
    reference nowhere to put a name: a component-ref is (identifier, version),
    so a ref carrying a display name is rejected rather than quietly relied on."""
    art = a_graph()
    art["nodes"][0]["component"] = {
        "identifier": "indicator.ema", "version": 1, "display_name": "EMA",
    }
    assert_violates(art, "F2")


# ── F3 — fork ─────────────────────────────────────────────────────────────

def test_f3_permits_a_parent_version():
    art = a_component()
    art["version"] = 2
    art["parent_version"] = 1
    assert_valid(art)


def test_f3_parent_version_must_be_an_integer():
    art = a_component()
    art["parent_version"] = "v1"
    assert_violates(art, "F3")


# ── F4 — declared, recursive interface ────────────────────────────────────

def test_f4_requires_the_interface_to_be_declared():
    art = a_component()
    del art["interface"]
    assert_violates(art, "F4")


def test_f4_accepts_a_recursive_panel_tree():
    art = a_component()
    art["interface"] = [
        {"item": "panel", "identifier": "trend", "display_name": "Trend", "items": [
            {"item": "parameter", "identifier": "ema_length", "display_name": "EMA Length",
             "kind": "length", "default": 50},
            {"item": "panel", "identifier": "inner", "display_name": "Inner", "items": [
                {"item": "parameter", "identifier": "slope_lookback",
                 "display_name": "Slope Lookback", "kind": "length", "default": 5},
            ]},
        ]},
    ]
    assert_valid(art)


def test_f4_validates_inside_nested_panels():
    """A panel must not be a place where checking stops."""
    art = a_component()
    art["interface"] = [
        {"item": "panel", "identifier": "trend", "display_name": "Trend", "items": [
            {"item": "parameter", "identifier": "ema_length", "display_name": "EMA Length",
             "kind": "not_a_kind", "default": 50},
        ]},
    ]
    assert_violates(art, "F5")


def test_f4_rejects_an_unknown_interface_item():
    art = a_component()
    art["interface"].append({"item": "widget", "identifier": "w", "display_name": "W"})
    assert_violates(art, "F4")


# ── F5 — parameters ───────────────────────────────────────────────────────

def test_f5_requires_a_kind_from_the_closed_vocabulary():
    art = a_component()
    art["interface"][1]["kind"] = "float"
    assert_violates(art, "F5")


def test_f5_requires_a_default():
    art = a_component()
    del art["interface"][1]["default"]
    assert_violates(art, "F5")


def test_f5_bool_is_in_the_vocabulary():
    """Appendix A.1's recorded red state: five of expanding_z_v4's fifteen real
    parameters are booleans, and the first grammar omitted the kind."""
    assert "bool" in KINDS


def test_f5_accepts_every_kind_in_the_vocabulary():
    for kind in KINDS:
        art = a_component()
        art["interface"][1]["kind"] = kind
        art["interface"][1]["default"] = {"secret_ref": "kite.api_key"} if kind == "secret" else 1
        art["interface"][1].pop("bounds", None)
        assert_valid(art)


# ── F6 — secrets ──────────────────────────────────────────────────────────

def test_f6_a_secret_default_must_be_a_reference():
    art = a_component()
    art["interface"][1].update({"kind": "secret", "default": "sk_live_abcdef123456"})
    art["interface"][1].pop("bounds", None)
    assert_violates(art, "F6")


def test_f6_a_secret_override_must_be_a_reference():
    """The safe path must be the only representable one — including on the
    override, which is where a value actually gets typed in."""
    art = a_graph()
    art["nodes"][0]["overrides"] = {"api_key": {"secret_ref": "kite.api_key"}}
    assert_valid(art)
    art["nodes"][0]["overrides"] = {"api_key": "sk_live_abcdef123456"}
    art["nodes"][0]["secret_params"] = ["api_key"]
    assert_violates(art, "F6")


# ── F7 — wire types ───────────────────────────────────────────────────────

def test_f7_requires_all_three_axes():
    for axis in ("value", "structure", "domain"):
        art = a_component()
        del art["interface"][0]["wire_type"][axis]
        assert_violates(art, "F7")


def test_f7_requires_both_domain_components():
    for part in ("instrument", "timeframe"):
        art = a_component()
        del art["interface"][0]["wire_type"]["domain"][part]
        assert_violates(art, "F7")


def test_f7_value_types_are_closed():
    art = a_component()
    art["interface"][0]["wire_type"]["value"] = "DataFrame"
    assert_violates(art, "F7")


def test_f7_rejects_a_wildcard_value_type():
    """ComfyUI's ecosystem froze around `*`-as-Any and three compatibility
    shims. There is no wildcard here, and this test is why."""
    for wildcard in ("*", "any", "ANY", "FLOAT,INT"):
        art = a_component()
        art["interface"][0]["wire_type"]["value"] = wildcard
        assert_violates(art, "F7")
        assert wildcard not in VALUE_TYPES


def test_f7_structure_axis_carries_scalar_series_and_auto():
    assert {"scalar", "series", "auto"} <= set(STRUCTURE_TYPES)


# ── F8 — default input sources ────────────────────────────────────────────

A_DEFAULT_SOURCE = {
    "component": {"identifier": "market.close", "version": 1},
    "socket": "out",
}


def test_f8_an_input_may_declare_a_default_source():
    art = a_component()
    art["interface"][0]["default_source"] = dict(A_DEFAULT_SOURCE)
    assert_valid(art)


def test_f8_an_output_may_not_declare_a_default_source():
    art = a_component()
    art["interface"][2]["default_source"] = dict(A_DEFAULT_SOURCE)
    assert_violates(art, "F8")


def test_f8_a_default_source_names_a_component_and_a_socket():
    """A *source*, not a value. Resolution has to insert something and take the
    value from somewhere; a declaration that says neither cannot be honoured,
    and F8's promise — "a graph whose unwired inputs all declare sources MUST
    be valid" — would be unkeepable."""
    art = a_component()
    art["interface"][0]["default_source"] = {"component": "market.close"}
    assert_violates(art, "F8")


def test_f8_a_default_source_reference_carries_no_display_name():
    """F2 again: a reference is by identifier. A default source is a component
    reference like any other and gets no exemption."""
    art = a_component()
    art["interface"][0]["default_source"] = {
        "component": {"identifier": "market.close", "version": 1,
                      "display_name": "Close"},
        "socket": "out",
    }
    assert_violates(art, "F2")


# ── F9 — graph ────────────────────────────────────────────────────────────

def test_f9_a_graph_requires_nodes_and_edges():
    for key in ("nodes", "edges"):
        art = a_graph()
        del art[key]
        assert_violates(art, "F9")


def test_f9_a_node_requires_an_instance_id_and_a_component_ref():
    for key in ("instance_id", "component"):
        art = a_graph()
        del art["nodes"][0][key]
        assert_violates(art, "F9")


def test_f9_instance_ids_must_be_unique_within_a_graph():
    """Asserted by path, not merely by clause. Renaming a node also orphans the
    edge that pointed at it, and a dangling edge is an F9 violation too — so a
    bare `F9 in violated` here passes whether or not uniqueness is checked at
    all. It did, until a mutation run caught it."""
    art = a_graph()
    art["nodes"][1]["instance_id"] = "n_ema"
    art["edges"][0]["target"]["instance"] = "n_ema"     # keep every edge resolvable
    paths = [v.path for v in validate(art) if v.clause == "F9"]
    assert paths == ["$.nodes[1].instance_id"], f"got {paths}"


def test_f9_an_edge_must_reference_a_declared_instance():
    art = a_graph()
    art["edges"][0]["target"]["instance"] = "n_missing"
    assert_violates(art, "F9")


# ── F10 — overrides carry values only ─────────────────────────────────────

def test_f10_an_override_may_not_redefine_a_parameter():
    """The author's constraints are the only thing protecting a user of a
    component they did not write."""
    for smuggled in ("kind", "bounds", "display_name"):
        art = a_graph()
        art["nodes"][0]["overrides"] = {"length": {"value": 50, smuggled: "x"}}
        assert_violates(art, "F10")


def test_f10_a_plain_value_override_is_fine():
    art = a_graph()
    art["nodes"][0]["overrides"] = {"length": 50, "enabled": True, "pct": 0.65}
    assert_valid(art)


def test_f10_an_override_may_be_a_parameter_reference():
    """Erratum, 2026-08-02. Appendix A.2 writes `override length ← length` —
    the ATR component forwarding its own parameter into the smoothing node
    inside its body — and the validator rejected it, because it forbade every
    mapping rather than the three things F10 names. A reference carries no
    kind, no bounds and no display name, and F6 already puts one in the format.
    Without this, A.2 is inexpressible and no component can forward a
    parameter into its own body."""
    art = a_graph()
    art["nodes"][0]["overrides"] = {"length": {"param_ref": "length"}}
    assert_valid(art)


def test_f10_a_mapping_that_is_no_known_reference_is_still_refused():
    """The erratum widened the rule to a closed set of reference forms, not to
    "any mapping". An unknown one is a definition being smuggled in."""
    art = a_graph()
    art["nodes"][0]["overrides"] = {"length": {"ref": "length"}}
    assert_violates(art, "F10")


# ── C14 — sweeping is the searcher's job, checked at the artefact too ─────

def test_c14_an_override_may_not_carry_a_grid_of_candidates():
    """C14 is a contract clause, so it is enforced by the resolver
    (`test_ir_resolution.py`). It is *also* visible in the artefact, and an
    artefact that stores a sweep has already made search part of the
    component's contract — vectorbt's shape — whether or not it is resolved."""
    art = a_graph()
    art["nodes"][0]["overrides"] = {"length": [7, 14, 21]}
    assert_violates(art, "C14")


# ── F11 — nesting by reference ────────────────────────────────────────────

def test_f11_a_node_may_not_inline_a_definition():
    """Langflow inlines full source per node, with the result that every graph
    is already a fork and the concept loses meaning."""
    for inlined in ("interface", "body", "nodes"):
        art = a_graph()
        art["nodes"][0]["component"][inlined] = []
        assert_violates(art, "F11")


def test_f11_a_component_ref_requires_a_version():
    art = a_graph()
    del art["nodes"][0]["component"]["version"]
    assert_violates(art, "F11")


# ── F12 — visual grouping is not semantic reuse ───────────────────────────

def test_f12_a_group_may_not_be_versioned_or_published():
    for publishable in ("version", "body", "interface"):
        art = a_graph()
        art["groups"] = [{"identifier": "g1", "display_name": "Filters",
                          "members": ["n_ema"], publishable: 1}]
        assert_violates(art, "F12")


def test_f12_visual_groups_are_not_executable_graph_content():
    art = a_graph()
    art["groups"] = [{"identifier": "g1", "display_name": "Filters", "members": ["n_ema"]}]
    violations = validate(art)
    assert [(violation.clause, violation.path) for violation in violations] == [
        ("F12", "$.groups")
    ]


def test_f12_a_group_member_must_be_a_declared_instance():
    art = a_graph()
    art["groups"] = [{"identifier": "g1", "display_name": "Filters", "members": ["n_ghost"]}]
    assert_violates(art, "F12")


# ── F13 — presentation state is not in the artefact ───────────────────────

def test_f13_rejects_presentation_state_on_a_node():
    """Dragging a node must not change its hash. The grammar has no place to
    put a coordinate, so an artefact carrying one is not conforming."""
    for key in ("position", "x", "collapsed", "colour"):
        art = a_graph()
        art["nodes"][0][key] = 1
        assert_violates(art, "F13")


def test_f13_rejects_presentation_state_at_the_top_level():
    art = a_graph()
    art["viewport"] = {"zoom": 1.5}
    assert_violates(art, "F13")


def test_f13_unknown_keys_are_rejected_everywhere_not_just_at_the_top():
    art = a_component()
    art["interface"][1]["ui_widget"] = "slider"
    assert_violates(art, "F13")


# ── F14 — enforced elsewhere, and the bookkeeping that proves it ─────────

def test_f14_is_enforced_by_the_experiment_system_not_by_this_validator():
    """F14 binds every experiment and finding to the versions that produced it,
    and it is the clause carrying the heaviest evidential weight in the RFC.

    It was recorded here as *unenforceable* until 2026-08-02, because there was
    no experiment artefact to validate. An experiment is not a component or a
    graph, so the answer was never to widen §3 — it was for the experiment
    system to define the record, which `app/ir/experiment.py` now does. This
    test is the pointer, so the clause cannot go missing between two files."""
    from app.ir.experiment import validate_experiment
    from app.ir.validate import ELSEWHERE_ENFORCED_CLAUSES, UNENFORCEABLE_CLAUSES

    assert ELSEWHERE_ENFORCED_CLAUSES == {"F14"}
    assert UNENFORCEABLE_CLAUSES == frozenset()
    assert [v.clause for v in validate_experiment(None)] == ["F14"]


def test_every_format_clause_is_enforced_somewhere():
    """The guard against this suite quietly falling behind the RFC: F1–F14 must
    each be exercised by a test above, enforced elsewhere and named, or
    declared unenforceable and named. Nothing may be simply absent."""
    from app.ir.validate import (
        ELSEWHERE_ENFORCED_CLAUSES,
        ENFORCED_CLAUSES,
        UNENFORCEABLE_CLAUSES,
    )

    all_clauses = {f"F{n}" for n in range(1, 15)}
    accounted = ENFORCED_CLAUSES | ELSEWHERE_ENFORCED_CLAUSES | UNENFORCEABLE_CLAUSES
    assert accounted == all_clauses
    assert ENFORCED_CLAUSES & ELSEWHERE_ENFORCED_CLAUSES == set()
    assert accounted & UNENFORCEABLE_CLAUSES == UNENFORCEABLE_CLAUSES
