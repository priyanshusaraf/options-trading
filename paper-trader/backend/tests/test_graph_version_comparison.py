import copy

import pytest

from app.editor.comparison import GraphComparisonRejected, compare_graph_versions
from app.ir.hashing import content_address
from app.ir.strategies.expanding_z import GRAPH


def _version(graph):
    return {"graph": graph, "content_address": content_address(graph)}


def _changed(mutator):
    graph = copy.deepcopy(GRAPH)
    mutator(graph)
    return graph


def test_same_immutable_graph_is_exactly_equivalent():
    result = compare_graph_versions(_version(GRAPH), _version(copy.deepcopy(GRAPH)))
    assert result == {"equivalent": True, "incomparable": [], "differences": []}


def test_topology_is_keyed_by_authored_identity_and_canonically_ordered():
    removed_node = GRAPH["nodes"][0]["instance_id"]
    right = _changed(lambda graph: (
        graph["nodes"].pop(0),
        graph["edges"].__setitem__(slice(None), [
            edge for edge in graph["edges"]
            if edge["source"]["instance"] != removed_node
            and edge["target"]["instance"] != removed_node
        ]),
    ))

    result = compare_graph_versions(_version(GRAPH), _version(right))

    structure = [d for d in result["differences"] if d["dimension"] == "structure"]
    assert structure
    assert structure[0]["path"] == ["edges", *sorted(
        [
            edge["source"]["instance"], edge["source"]["socket"],
            edge["target"]["instance"], edge["target"]["socket"],
        ]
        for edge in GRAPH["edges"]
        if edge["source"]["instance"] == removed_node
        or edge["target"]["instance"] == removed_node
    )[0]]
    assert any(d["path"] == ["nodes", removed_node] for d in structure)
    assert result["differences"] == sorted(
        result["differences"], key=lambda d: (d["dimension"], repr(d["path"]))
    )


def test_component_and_parameter_changes_have_distinct_dimensions():
    right = _changed(lambda graph: (
        graph["nodes"][2]["component"].__setitem__("version", 2),
        graph["nodes"][3]["overrides"].__setitem__("length", 99),
    ))

    result = compare_graph_versions(_version(GRAPH), _version(right))

    assert any(d["dimension"] == "components" for d in result["differences"])
    assert any(d["dimension"] == "parameters" for d in result["differences"])


def test_order_only_change_is_identity_not_false_topology():
    right = _changed(lambda graph: (
        graph["nodes"].reverse(), graph["edges"].reverse()
    ))

    result = compare_graph_versions(_version(GRAPH), _version(right))

    assert not any(d["dimension"] == "structure" for d in result["differences"])
    assert {tuple(d["path"]) for d in result["differences"]} >= {
        ("nodes", "order"), ("edges", "order"), ("content_address",),
    }


def test_presentation_contamination_and_false_declared_identity_are_rejected():
    grouped = _changed(lambda graph: graph["groups"].append({
        "identifier": "visual", "display_name": "Visual", "members": []
    }))
    with pytest.raises(GraphComparisonRejected, match="presentation"):
        compare_graph_versions(_version(grouped), _version(GRAPH))

    claimed = _version(GRAPH)
    claimed["content_address"] = "sha256:" + "0" * 64
    with pytest.raises(GraphComparisonRejected, match="content address"):
        compare_graph_versions(claimed, _version(GRAPH))
