"""
The IR view routes — WS-04's first surface, and the moment `app/ir/` stops being
imported only by its own tests.

The threshold is deliberate, so the tests guard the shape of it: read-only, no
execution surface, and no route that resolves whatever it is handed.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import json
import pathlib
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.ir.hashing import content_address
from app.ir.resolve import ResolutionError, resolve
from app.ir.strategies.expanding_z import GRAPH, LIBRARY
from app.ir.view import ViewEdge, ViewNode, graph_view

IDENTIFIER = GRAPH["identifier"]


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def test_the_repository_owned_reference_artefact_is_registered(client):
    response = client.get(f"/api/ir/graphs/{IDENTIFIER}")
    assert response.status_code == 200
    assert response.json()["version"] == GRAPH["version"]


def test_repository_graph_resolution_checks_library_dependent_wire_types(client, monkeypatch):
    """Removing the library argument from validate() must make this fail.

    The edited edge feeds a series into a scalar socket. F7 can only see that
    mismatch when validation receives the component library.
    """
    from app.api import ir_routes
    from app.ir.strategies.expanding_z import LIBRARY

    ill_typed = copy.deepcopy(GRAPH)
    ill_typed["identifier"] = "strategy.ill_typed"
    ill_typed["edges"][9]["source"] = {"instance": "n_ema", "socket": "out"}
    monkeypatch.setattr(
        ir_routes,
        "catalogue",
        lambda: {ill_typed["identifier"]: (ill_typed, LIBRARY)},
    )

    response = client.get("/api/ir/graphs/strategy.ill_typed")
    assert response.status_code == 500
    assert response.json()["detail"].startswith("F7 at $.edges[9]")


def test_a_graph_renders_as_a_view_model(client):
    body = client.get(f"/api/ir/graphs/{IDENTIFIER}").json()

    assert body["identifier"] == IDENTIFIER
    assert body["warmup"] == 302
    assert len(body["nodes"]) == 18
    assert len(body["edges"]) == 35
    assert set(body["outputs"]) == {"longEntry", "shortEntry", "longExit", "shortExit"}


def test_serialization_is_the_explicit_graph_view_contract(client):
    body = client.get(f"/api/ir/graphs/{IDENTIFIER}").json()
    view = graph_view(resolve(GRAPH, LIBRARY))

    assert set(body) == {
        "identifier", "version", "display_name", "warmup", "layers",
        "inputs", "outputs", "nodes", "edges",
    }
    node_fields = {field.name for field in dataclasses.fields(ViewNode)}
    edge_fields = {field.name for field in dataclasses.fields(ViewEdge)}
    assert {frozenset(node) for node in body["nodes"]} == {frozenset(node_fields)}
    assert {frozenset(edge) for edge in body["edges"]} == {frozenset(edge_fields)}

    assert [node["instance_id"] for node in body["nodes"]] == [
        node.instance_id for node in view.nodes
    ]
    assert [edge for edge in body["edges"]] == [
        {field.name: getattr(edge, field.name) for field in dataclasses.fields(ViewEdge)}
        for edge in view.edges
    ]
    for actual, expected in zip(body["nodes"], view.nodes, strict=True):
        for field in dataclasses.fields(ViewNode):
            value = getattr(expected, field.name)
            if field.name == "params":
                value = dict(value)
            elif field.name == "placed" and value is not None:
                value = list(value)
            assert actual[field.name] == value


def test_the_view_model_carries_what_resolution_computed(client):
    """Warmup, purity and cache identity are the three things a reader of the
    specification cannot work out. Without them this is a picture of the source
    rather than of the resolved graph."""
    nodes = {n["instance_id"]: n for n in
             client.get(f"/api/ir/graphs/{IDENTIFIER}").json()["nodes"]}

    entry = nodes["n_entry_thr"]
    assert entry["warmup"] == 300
    assert entry["purity"] == "pure"
    assert entry["cache_id"].startswith("sha256:")
    assert entry["params"]["pct"] == 65.0


def test_a_nested_node_says_which_authored_node_it_came_from(client):
    """C4 — a diagnostic speaks the authored graph's vocabulary, and a view is a
    diagnostic. `n_atr/n_smooth` must not arrive as an opaque leaf."""
    nodes = {n["instance_id"]: n for n in
             client.get(f"/api/ir/graphs/{IDENTIFIER}").json()["nodes"]}

    assert nodes["n_atr/n_smooth"]["container"] == "n_atr"
    assert nodes["n_atr/n_smooth"]["label"] == "n_smooth"
    assert nodes["n_atr/n_smooth"]["definition"] == "smoothing.wilder v1"
    assert nodes["n_ema"]["container"] == ""


def test_an_unknown_graph_is_404_without_calling_resolve(client, monkeypatch):
    from app.api import ir_routes

    def should_not_resolve(*_args, **_kwargs):
        raise AssertionError("unknown client input reached resolve")

    monkeypatch.setattr(ir_routes, "resolve", should_not_resolve)
    response = client.get("/api/ir/graphs/strategy.does_not_exist")
    assert response.status_code == 404
    assert response.json() == {
        "detail": "no IR graph named 'strategy.does_not_exist'",
    }


def test_resolution_errors_follow_the_fastapi_error_contract(client, monkeypatch):
    from app.api import ir_routes

    def broken_resolution(*_args, **_kwargs):
        raise ResolutionError("C5", "$.nodes[0]", "missing component")

    monkeypatch.setattr(ir_routes, "resolve", broken_resolution)
    for path in (
        f"/api/ir/graphs/{IDENTIFIER}",
        f"/api/v1/ir/graphs/{IDENTIFIER}",
    ):
        response = client.get(path)
        assert response.status_code == 500
        assert response.json() == {
            "detail": "C5 at $.nodes[0]: missing component",
        }


def test_the_route_does_not_resolve_arbitrary_input(client):
    """A viewer, not an evaluator. A route that resolves whatever it is handed
    would be an execution surface reachable over HTTP — so the catalogue is a
    fixed table and there is no POST at all."""
    from app.api import ir_routes
    assert [(route.path, route.methods) for route in ir_routes.router.routes] == [
        ("/api/ir/graphs/{identifier}", {"GET"}),
    ]
    assert {r.methods and tuple(r.methods) for r in ir_routes.router.routes} == {("GET",)}
    for method in ("post", "put", "delete", "patch"):
        response = client.request(
            method.upper(), f"/api/ir/graphs/{IDENTIFIER}", json=GRAPH)
        assert response.status_code == 405


def test_read_routes_do_not_mutate_the_repository_owned_artefact(client):
    before = content_address(GRAPH)

    assert client.get(f"/api/ir/graphs/{IDENTIFIER}").status_code == 200

    assert content_address(GRAPH) == before


def test_openapi_publishes_a_closed_graph_response_contract(client):
    from app.main import app

    schema = app.openapi()
    response_schema = schema["paths"]["/api/ir/graphs/{identifier}"]["get"]["responses"][
        "200"
    ]["content"]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/IrGraphResponse"}
    assert schema["components"]["schemas"]["IrGraphResponse"]["additionalProperties"] is False


def test_the_ir_routes_reach_no_execution_module(client):
    """The threshold this crosses is `app/ir/` entering the application. It must
    not drag execution in with it: this module may import the IR and FastAPI and
    nothing from the engine, the brokers or the providers."""
    path = pathlib.Path(__file__).resolve().parents[1] / "app/api/ir_routes.py"
    tree = ast.parse(path.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0
            if node.module and node.module.startswith("app."):
                imports.add(node.module)
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names if alias.name.startswith("app."))
    assert imports
    assert all(module.startswith("app.ir.") for module in imports), imports

    code = """
import json
import sys
before = set(sys.modules)
import app.api.ir_routes
print(json.dumps(sorted(name for name in set(sys.modules) - before if name.startswith('app.'))))
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=pathlib.Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    loaded = json.loads(result.stdout)
    forbidden = ("app.engine", "app.providers", "app.broker", "app.db", "app.options")
    assert not [name for name in loaded if name.startswith(forbidden)]


def test_health_still_answers_with_the_new_router_mounted(client):
    """The router is mounted before the SPA catch-all and must not shadow
    anything. `/api/health` is what `deploy.sh` polls, and this client does not
    enter the lifespan, so the engine-dependent routes are out of scope here."""
    assert client.get("/api/health").status_code in (200, 503)


def test_the_versioned_mirror_carries_the_new_routes(client):
    """Every other router is mirrored under /api/v1; this one is too, or a
    client pinned to v1 would find the IR missing for no stated reason."""
    assert client.get(f"/api/v1/ir/graphs/{IDENTIFIER}").status_code == 200
