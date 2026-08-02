"""
RFC 0001 F14 — result binding, the last clause to stop being a claim.

    "Every experiment and every finding MUST record the exact graph version and
    every resolved component version that produced it."

F14 carries the heaviest evidential weight in the RFC and was recorded as
*unenforceable* through the format and resolver phases, because an experiment is
not a component or a graph and there was nothing to validate. The answer was
never to widen §3 — the RFC's own note says it becomes enforceable when the
**experiment system** defines a record, and `app/ir/experiment.py` is that.

The clause is retrospective, which is what makes it dangerous to defer. Airflow
bound `DagVersion` to task instances only after roughly a decade, by retrofit,
and every run before it stayed unattributable. This platform has already paid
that price once: every research finding before 2026-08 is unusable as a baseline
because the deflation it claimed never engaged. So the tests below care less
about a missing field than about a *stale* one, which is the failure that
actually happened.
"""
from __future__ import annotations

import copy

import pytest

from app.ir.experiment import (
    ExperimentRecord,
    conclude,
    data_digest,
    record,
    validate_experiment,
    validate_finding,
)
from app.ir.resolve import resolve
from app.ir.runtime import evaluate
from app.ir.strategies.expanding_z import GRAPH, IMPLEMENTATIONS, LIBRARY
from tests.test_ir_strategy_parity import candles


@pytest.fixture(scope="module")
def frame():
    return candles(300)


@pytest.fixture(scope="module")
def inputs(frame):
    return {"high": frame["high"], "low": frame["low"], "close": frame["close"]}


@pytest.fixture(scope="module")
def graph():
    return resolve(GRAPH, LIBRARY)


@pytest.fixture(scope="module")
def experiment(graph, inputs):
    out = evaluate(graph, inputs, IMPLEMENTATIONS)
    return record("exp-001", graph, inputs,
                  {"entries": int(out.outputs["longEntry"].sum())})


# ── the binding is derived, which is the whole guarantee ──────────────────

def test_the_versions_cannot_be_supplied_by_the_caller():
    """F14's failure mode is not a missing field — it is a stale one. A record
    that can be *told* its versions is a record that can be told last week's.
    So `record()` has no parameter for them, and this test is what keeps that
    true when someone finds it inconvenient."""
    import inspect

    assert set(inspect.signature(record).parameters) == {
        "experiment_id", "graph", "inputs", "result"}


def test_an_experiment_records_every_resolved_component_version(experiment, graph):
    assert experiment.component_versions == tuple(graph.versions)
    assert ("indicator.atr.wilder", 1) in experiment.component_versions
    # Reached only through the ATR's *body*, so it exists in the record only
    # because the binding comes from resolution rather than from reading the
    # specification's node list.
    assert ("smoothing.wilder", 1) in experiment.component_versions
    assert ("indicator.true_range", 1) in experiment.component_versions


def test_an_experiment_records_the_exact_graph_version(experiment):
    assert experiment.graph == ("strategy.expanding_z_impulse", 4)


def test_an_experiment_records_every_nodes_identity(experiment, graph):
    assert dict(experiment.node_identities) == {
        n.instance_id: n.cache_id for n in graph.nodes}


def test_an_experiment_records_the_data_it_ran_on(experiment, inputs, frame):
    assert experiment.data_digest == data_digest(inputs)
    shifted = {name: series * 1.01 for name, series in inputs.items()}
    assert data_digest(shifted) != experiment.data_digest


def test_the_same_data_through_a_different_route_digests_the_same(inputs):
    """A digest that depended on identity rather than value would make every
    re-load a different experiment."""
    assert data_digest({k: v.copy() for k, v in inputs.items()}) == data_digest(inputs)


# ── the clause, checked ───────────────────────────────────────────────────

def test_a_complete_record_satisfies_f14(experiment, graph):
    assert validate_experiment(experiment, graph) == []


@pytest.mark.parametrize("field, broken", [
    ("experiment_id", ""),
    ("graph", ("", 0)),
    ("component_versions", ()),
    ("node_identities", {}),
    ("data_digest", ""),
])
def test_every_part_of_the_binding_is_required(experiment, field, broken):
    """Each of the five is load-bearing on its own: drop any one and the result
    can no longer be re-derived, which is what F14 is protecting."""
    maimed = ExperimentRecord(**{**experiment.__dict__, field: broken})
    violations = validate_experiment(maimed)
    assert [v.clause for v in violations] == ["F14"]
    assert violations[0].path == f"$.{field}"


def test_a_stale_binding_is_caught_only_because_the_graph_is_available(experiment, graph):
    """Present-but-wrong is the failure that actually happens, and it is
    invisible without something to compare against. A record naming version 3
    of a graph that resolved as version 4 passes every structural check."""
    stale = ExperimentRecord(**{**experiment.__dict__,
                                "graph": ("strategy.expanding_z_impulse", 3)})
    assert validate_experiment(stale) == []
    assert [v.clause for v in validate_experiment(stale, graph)] == ["F14"]


def test_node_identities_that_are_present_but_wrong_are_caught(experiment, graph):
    """The suppression sweep found this missing. Every other test of
    `node_identities` emptied it, which trips the *presence* check — so
    deleting the comparison against the resolved graph left the suite green.
    A wrong identity is the interesting case: it is what a hand-maintained
    record looks like one refactor later."""
    corrupted = dict(experiment.node_identities)
    corrupted["n_ema"] = "sha256:" + "0" * 64
    wrong = ExperimentRecord(**{**experiment.__dict__, "node_identities": corrupted})

    assert validate_experiment(wrong) == []          # structurally complete…
    violations = validate_experiment(wrong, graph)   # …and still not the truth
    assert [v.clause for v in violations] == ["F14"]
    assert violations[0].path == "$.node_identities"


def test_a_record_missing_a_component_version_is_caught(experiment, graph):
    """The Airflow shape: the definition is versioned, the *run* is not fully
    bound, and a component reached through a subgraph body goes unrecorded."""
    thinned = ExperimentRecord(**{
        **experiment.__dict__,
        "component_versions": tuple(v for v in experiment.component_versions
                                    if v != ("smoothing.wilder", 1))})
    violations = validate_experiment(thinned, graph)
    assert [v.clause for v in violations] == ["F14"]
    assert "smoothing.wilder" in violations[0].message


def test_a_reparameterised_graph_produces_a_different_binding(graph, inputs):
    """Re-running with a moved parameter must not look like the same
    experiment. The node identities are transitive over their upstream (C8), so
    this holds without anyone remembering to record the parameters separately."""
    moved = copy.deepcopy(GRAPH)
    for item in moved["interface"]:
        if item.get("identifier") == "zscore":
            for p in item["items"]:
                if p["identifier"] == "entry_pct":
                    p["default"] = 80.0

    other = resolve(moved, LIBRARY)
    first = record("exp-001", graph, inputs, {"entries": 1})
    second = record("exp-002", other, inputs, {"entries": 1})

    assert first.component_versions == second.component_versions   # same components…
    assert first.binding != second.binding                          # …different run


def test_the_same_experiment_re_recorded_binds_identically(graph, inputs):
    """C1 and C7 reaching the record: replay must be recognisable as replay."""
    assert record("exp-001", graph, inputs, {"entries": 1}).binding == \
           record("exp-001", resolve(GRAPH, LIBRARY), inputs, {"entries": 1}).binding


def test_the_same_graph_on_different_data_is_a_different_experiment(graph, inputs):
    other = {name: series * 1.01 for name, series in inputs.items()}
    assert record("a", graph, inputs, {}).binding != record("b", graph, other, {}).binding


# ── "and every finding" ───────────────────────────────────────────────────

def test_a_finding_carries_the_binding_of_the_experiment_it_came_from(experiment):
    finding = conclude("find-001", experiment, {"claim": "entries are rare"})
    assert validate_finding(finding, experiment) == []
    assert finding.binding == experiment.binding


def test_a_finding_left_behind_by_a_re_run_is_caught(experiment, graph, inputs):
    """The state this repository is actually in for everything before 2026-08:
    a claim that outlived the run it came from. The finding still names a real
    experiment id — what has moved is what that experiment now is."""
    finding = conclude("find-001", experiment, {"claim": "entries are rare"})

    moved = copy.deepcopy(GRAPH)
    for item in moved["interface"]:
        if item.get("identifier") == "zscore":
            for p in item["items"]:
                if p["identifier"] == "entry_pct":
                    p["default"] = 80.0
    rerun = record("exp-001", resolve(moved, LIBRARY), inputs, {"entries": 9})

    violations = validate_finding(finding, rerun)
    assert [v.clause for v in violations] == ["F14"]
    assert violations[0].path == "$.binding"


def test_a_finding_must_name_an_experiment(experiment):
    from app.ir.experiment import Finding
    orphan = Finding(finding_id="find-002", experiment_id="", binding="x", claim={})
    assert [v.path for v in validate_finding(orphan)] == ["$.experiment_id"]


def test_a_finding_that_names_a_different_experiment_is_caught(experiment, graph, inputs):
    other = record("exp-002", graph, inputs, {"entries": 1})
    finding = conclude("find-003", other, {})
    assert [v.path for v in validate_finding(finding, experiment)] == ["$.experiment_id"]


# ── the record is not editable after the fact ─────────────────────────────

def test_a_record_cannot_be_edited_into_agreement(experiment):
    """A binding that can be adjusted to match is not a binding."""
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        experiment.graph = ("x", 1)
    with pytest.raises(TypeError):
        experiment.node_identities["n_ema"] = "anything"
    with pytest.raises(TypeError):
        experiment.result["entries"] = 999
