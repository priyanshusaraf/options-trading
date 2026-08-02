"""
RFC 0001 Appendix A — the acceptance set, executed.

"These five artefacts are the acceptance set. A failure to express any one of
them is a defect in this RFC, not in the example."

Appendix A asserts that in prose. Until this file existed, that assertion was
the author's word: the artefacts were written as abbreviated sketches inside a
markdown document and nothing read them. Here they are as real artefacts, run
through the real validator.

A.1–A.4 MUST validate. A.5 MUST be rejected, and rejected for the specific
reason the appendix gives — a domain mismatch on the final edge, not a
structural error that happens to fail.
"""
from __future__ import annotations

import pytest

from app.ir.validate import LIBRARY_DEPENDENT_CLAUSES, clauses_violated, unchecked_clauses, validate

FV = 1


def wire(value="float", structure="series", instrument="NIFTY", timeframe="15m"):
    return {"value": value, "structure": structure,
            "domain": {"instrument": instrument, "timeframe": timeframe}}


def digest(seed: str) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(seed.encode()).hexdigest()


# ── A.1 — the EMA-z strategy, with its fifteen real parameters ────────────

def param(identifier, display_name, kind, default):
    return {"item": "parameter", "identifier": identifier,
            "display_name": display_name, "kind": kind, "default": default}


def out_socket(identifier, display_name):
    return {"item": "socket", "identifier": identifier, "display_name": display_name,
            "direction": "output", "wire_type": wire(value="bool")}


A1_EXPANDING_Z = {
    "format_version": FV,
    "kind": "graph",
    "identifier": "strategy.expanding_z_impulse",
    "version": 4,
    "display_name": "Expanding Z Impulse V4",
    "interface": [
        {"item": "panel", "identifier": "trend", "display_name": "Trend", "items": [
            param("ema_length", "EMA Length", "length", 50),
            param("slope_lookback", "Slope Lookback", "length", 5),
        ]},
        {"item": "panel", "identifier": "zscore", "display_name": "Z-Score", "items": [
            param("z_length", "Z Length", "length", 50),
            param("adapt_length", "Adapt Length", "length", 200),
            param("entry_pct", "Entry Percentile", "pct", 65.0),
            param("exit_pct", "Exit Percentile", "pct", 35.0),
            param("min_abs_z", "Min |z|", "thr", 0.60),
        ]},
        {"item": "panel", "identifier": "volatility", "display_name": "Volatility", "items": [
            param("atr_length", "ATR Length", "length", 14),
            param("min_drift_atr", "Min Drift (ATR)", "mult", 0.08),
            param("max_signal_atr", "Max Signal (ATR)", "mult", 2.75),
        ]},
        {"item": "panel", "identifier": "behaviour", "display_name": "Behaviour", "items": [
            param("require_expansion", "Require Expansion", "bool", True),
            param("allow_reexpansion", "Allow Re-expansion", "bool", True),
            param("use_absz_contraction_exit", "Use |z| Contraction Exit", "bool", False),
            param("exit_on_drift_flip", "Exit on Drift Flip", "bool", True),
            param("exit_on_ema_cross", "Exit on EMA Cross", "bool", True),
        ]},
        out_socket("longEntry", "Long Entry"),
        out_socket("shortEntry", "Short Entry"),
        out_socket("longExit", "Long Exit"),
        out_socket("shortExit", "Short Exit"),
    ],
    "nodes": [
        {"instance_id": "n_ema", "component": {"identifier": "indicator.ema", "version": 1},
         "overrides": {"length": 50}},
        {"instance_id": "n_z", "component": {"identifier": "indicator.zscore", "version": 1},
         "overrides": {"length": 50}},
    ],
    "edges": [
        {"source": {"instance": "n_ema", "socket": "out"},
         "target": {"instance": "n_z", "socket": "reference"}},
    ],
    "groups": [],
}


# ── A.2 — a decomposed ATR indicator (body is a graph, not a kernel) ──────

A2_ATR_WILDER = {
    "format_version": FV,
    "kind": "component",
    "identifier": "indicator.atr.wilder",
    "version": 1,
    "display_name": "ATR (Wilder)",
    "interface": [
        {"item": "socket", "identifier": "high", "display_name": "High",
         "direction": "input", "wire_type": wire()},
        {"item": "socket", "identifier": "low", "display_name": "Low",
         "direction": "input", "wire_type": wire()},
        {"item": "socket", "identifier": "close", "display_name": "Close",
         "direction": "input", "wire_type": wire()},
        param("length", "Length", "length", 14),
        {"item": "socket", "identifier": "atr", "display_name": "ATR",
         "direction": "output", "wire_type": wire()},
    ],
    "body": {"body": "graph", "ref": digest("atr.wilder.body")},
}


# ── A.3 — a generated strategy from the block grammar ─────────────────────

A3_GENERATED = {
    "format_version": FV,
    "kind": "graph",
    # Under F2 the content hash is the identifier's *suffix*; the body's own
    # content address is a separate thing, and the version starts at 1.
    "identifier": "generated.9f2c1ab4",
    "version": 1,
    "display_name": "Generated 9f2c1ab4",
    "interface": [out_socket("longEntry", "Long Entry")],
    "nodes": [
        {"instance_id": "n_1", "component": {"identifier": "block.atr_pct_lt", "version": 1},
         "overrides": {"length": 14, "max_pct": 3.0}},
        {"instance_id": "n_2", "component": {"identifier": "block.range_atr_lt", "version": 1},
         "overrides": {"length": 14, "mult": 0.8}},
        {"instance_id": "n_3", "component": {"identifier": "logic.and", "version": 1},
         "overrides": {}},
    ],
    "edges": [
        {"source": {"instance": "n_1", "socket": "out"},
         "target": {"instance": "n_3", "socket": "a"}},
        {"source": {"instance": "n_2", "socket": "out"},
         "target": {"instance": "n_3", "socket": "b"}},
    ],
    "groups": [],
}


# ── A.4 — a nested subgraph, referencing A.2 twice at two lengths ─────────

A4_DUAL_ATR = {
    "format_version": FV,
    "kind": "graph",
    "identifier": "strategy.dual_atr_filter",
    "version": 1,
    "display_name": "Dual ATR Filter",
    "interface": [out_socket("longEntry", "Long Entry")],
    "nodes": [
        {"instance_id": "n_fast",
         "component": {"identifier": "indicator.atr.wilder", "version": 1},
         "overrides": {"length": 7}},
        {"instance_id": "n_slow",
         "component": {"identifier": "indicator.atr.wilder", "version": 1},
         "overrides": {"length": 21}},
        {"instance_id": "n_cmp", "component": {"identifier": "compare.gt", "version": 1},
         "overrides": {}},
    ],
    "edges": [
        {"source": {"instance": "n_fast", "socket": "atr"},
         "target": {"instance": "n_cmp", "socket": "a"}},
        {"source": {"instance": "n_slow", "socket": "atr"},
         "target": {"instance": "n_cmp", "socket": "b"}},
    ],
    "groups": [],
}


# ── A.5 — the multi-timeframe case, whose final edge is ill-typed ─────────

A5_MULTI_TIMEFRAME = {
    "format_version": FV,
    "kind": "graph",
    "identifier": "strategy.mtf_ema_cross",
    "version": 1,
    "display_name": "MTF EMA Cross",
    "interface": [out_socket("longEntry", "Long Entry")],
    "nodes": [
        {"instance_id": "n_5m", "component": {"identifier": "indicator.ema", "version": 1},
         "overrides": {"length": 20}, "domain": {"instrument": "NIFTY", "timeframe": "5m"}},
        {"instance_id": "n_15m", "component": {"identifier": "indicator.ema", "version": 1},
         "overrides": {"length": 20}, "domain": {"instrument": "NIFTY", "timeframe": "15m"}},
        {"instance_id": "n_cmp", "component": {"identifier": "compare.gt", "version": 1},
         "overrides": {}, "domain": {"instrument": "NIFTY", "timeframe": "5m"}},
    ],
    "edges": [
        {"source": {"instance": "n_5m", "socket": "out"},
         "target": {"instance": "n_cmp", "socket": "a"}},
        {"source": {"instance": "n_15m", "socket": "out"},
         "target": {"instance": "n_cmp", "socket": "b"}},   # ✗ 15m into a 5m node
    ],
    "groups": [],
}


def component(identifier, version, sockets):
    return {
        "format_version": FV, "kind": "component", "identifier": identifier,
        "version": version, "display_name": identifier, "interface": [
            {"item": "socket", "identifier": name, "display_name": name,
             "direction": direction, "wire_type": wire(value=value)}
            for name, direction, value in sockets
        ],
        "body": {"body": "kernel", "ref": digest(identifier)},
    }


LIBRARY = {
    ("indicator.ema", 1): component("indicator.ema", 1,
                                    [("source", "input", "float"), ("out", "output", "float")]),
    ("compare.gt", 1): component("compare.gt", 1,
                                 [("a", "input", "float"), ("b", "input", "float"),
                                  ("out", "output", "bool")]),
    ("indicator.atr.wilder", 1): A2_ATR_WILDER,
}


# ── the acceptance set ────────────────────────────────────────────────────

ACCEPTED = [
    pytest.param(A1_EXPANDING_Z, id="A.1 expanding_z_v4"),
    pytest.param(A2_ATR_WILDER, id="A.2 decomposed ATR"),
    pytest.param(A3_GENERATED, id="A.3 generated strategy"),
    pytest.param(A4_DUAL_ATR, id="A.4 nested subgraph"),
]


@pytest.mark.parametrize("artefact", ACCEPTED)
def test_the_acceptance_set_is_expressible(artefact):
    assert validate(artefact) == []


def test_a1_declares_all_fifteen_real_parameters():
    """Not plausible parameters — the real ones. Five are booleans, which is
    the red state Appendix A.1 records against the first draft of the grammar."""
    params = [item for panel in A1_EXPANDING_Z["interface"]
              if panel["item"] == "panel" for item in panel["items"]]
    assert len(params) == 15
    assert sum(1 for p in params if p["kind"] == "bool") == 5


def test_a2_body_is_a_graph_which_is_what_makes_a_component_decomposable():
    """C15: a subgraph and a component are the same kind of thing, so an
    indicator is itself a graph. This is the Generation-2 property the current
    block library fails — `_atr` is a private helper and every public block
    returns Series[bool]."""
    assert A2_ATR_WILDER["body"]["body"] == "graph"


def test_a4_references_one_definition_twice_and_keeps_the_instances_distinct():
    """F11 nesting by reference, and the precondition for C4: n_fast and n_slow
    expand from the same definition and MUST remain distinguishable."""
    refs = [n["component"] for n in A4_DUAL_ATR["nodes"][:2]]
    assert refs[0] == refs[1]
    assert A4_DUAL_ATR["nodes"][0]["instance_id"] != A4_DUAL_ATR["nodes"][1]["instance_id"]


# ── A.5 — the rejection, for the right reason ─────────────────────────────

def test_a5_is_structurally_valid_so_the_rejection_is_about_types_only():
    """Without a library the domain mismatch is invisible — and that is the
    point of the next test. A.5 must be well-formed, or its rejection would
    prove nothing about F7."""
    assert validate(A5_MULTI_TIMEFRAME) == []


def test_a5_final_edge_is_ill_typed_on_the_domain_axis():
    violations = validate(A5_MULTI_TIMEFRAME, library=LIBRARY)
    assert [v.clause for v in violations] == ["F7"]
    only = violations[0]
    assert only.path == "$.edges[1].domain.timeframe"
    assert "'15m'" in only.message and "'5m'" in only.message


def test_a5_would_connect_under_a_one_axis_type_system():
    """Both wires carry float values with series structure. A validator that
    checked only value and structure would pass this graph — which is how a
    plausible backtest becomes an unreproducible live result."""
    src = LIBRARY[("indicator.ema", 1)]["interface"][1]["wire_type"]
    assert src["value"] == "float" and src["structure"] == "series"


def test_a4_type_checks_clean_against_the_same_library():
    """The control: same validator, same library, a graph whose domains agree."""
    assert validate(A4_DUAL_ATR, library=LIBRARY) == []


# ── the honesty guard ─────────────────────────────────────────────────────

def test_without_a_library_f7_is_reported_unchecked_not_passed():
    """An unchecked clause that looks like a passing clause is how a validator
    lies. This codebase's documented failure mode is mechanisms that exist and
    are wired to nothing; a silent skip is the same defect in a validator."""
    assert "F7" in unchecked_clauses(library=None)
    assert "F7" not in unchecked_clauses(library=LIBRARY)
    assert LIBRARY_DEPENDENT_CLAUSES == {"F7"}
