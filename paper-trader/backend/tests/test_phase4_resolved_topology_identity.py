"""CUR-H2 regressions for the sole complete resolved-v2 topology identity."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtest.repository import AdmissionRequired, load_verified_admission
from app.core.strategy_admissions import put
from app.db.models import Base, StrategyAdmission
from app.ir.hashing import canonical_json, content_address
from app.ir.registry import PlatformRegistry
from app.ir.resolve import (
    RESOLVED_V2_TOPOLOGY_SCHEMA,
    V2_MAX_AUTHORED_NODES,
    V2_MAX_BOUNDARY_PORTS,
    V2_MAX_COMPOUND_DEPTH,
    ResolutionError,
    resolve_v2,
    resolved_v2_graph_address,
)
from app.market_data.requirements import DataRequirementRefusal, compile_data_requirement_plan

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_ir_v2_admission_receipt import _document as compound_document
from test_ir_v2_admission_receipt import _port as compound_port
from test_ir_v2_admission_receipt import _registry as compound_registry
from test_ir_v2_resolution_bundles import _document as bundle_document
from test_ir_v2_resolution_bundles import _edge as bundle_edge
from test_ir_v2_resolution_bundles import registry as bundle_registry_fixture
from tests.test_phase4_v2_graph_persistence import _phase4_fixture


def _bundle_registry() -> PlatformRegistry:
    return bundle_registry_fixture.__wrapped__()


def _plain(value):
    if isinstance(value, dict) or hasattr(value, "items"):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _connected_compound_document() -> dict[str, object]:
    document = compound_document()
    document["graph_inputs"] = [compound_port("in", "input")]
    document["graph_outputs"] = [compound_port("out", "output")]
    document["edges"] = [
        {
            "edge_id": "outer-input",
            "source": {"scope": "graph_input", "port_id": "in"},
            "target": {"scope": "node", "node_id": "bundle", "port_id": "in"},
            "binding": {"kind": "single"},
        },
        {
            "edge_id": "outer-output",
            "source": {"scope": "node", "node_id": "bundle", "port_id": "out"},
            "target": {"scope": "graph_output", "port_id": "out"},
            "binding": {"kind": "single"},
        },
    ]
    return document


def _persisted_fixture():
    return _phase4_fixture()


def _registry_without_implementation(registry: PlatformRegistry) -> PlatformRegistry:
    return PlatformRegistry(
        components={},
        bodies={},
        registrations={},
        v2_types=registry.v2_types,
        v2_components=registry.v2_components,
        v2_implementations={},
        data_requirement_declarations=registry.data_requirement_declarations,
    )


def _compound_chain(depth: int) -> tuple[dict[str, object], PlatformRegistry]:
    base = compound_registry()
    leaf = _plain(base.v2_components[("leaf.scale", 1)])
    template = _plain(base.v2_components[("compound.bundle", 1)])
    components = {("leaf.scale", 1): leaf}
    for index in range(depth - 1, -1, -1):
        component = deepcopy(template)
        component["component_id"] = f"compound.depth-{index}"
        child_id = "leaf.scale" if index + 1 == depth else f"compound.depth-{index + 1}"
        child = component["compound"]["body"]["nodes"][0]
        old_node_id = child["node_id"]
        child["component"]["component_id"] = child_id
        for edge in component["compound"]["body"]["edges"]:
            for endpoint in (edge["source"], edge["target"]):
                if endpoint.get("scope") == "node" and endpoint.get("node_id") == old_node_id:
                    endpoint["node_id"] = "child"
        child["node_id"] = "child"
        component["compound"]["parameter_bindings"][0]["targets"][0]["node_id"] = "child"
        components[(component["component_id"], 1)] = component
    registry = PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types={key: _plain(value) for key, value in base.v2_types.items()},
        v2_components=components,
    )
    document = compound_document()
    document["nodes"][0]["component"]["component_id"] = "compound.depth-0"
    return document, registry


def _writer_program() -> str:
    return """
import json, sys
sys.path.insert(0, 'tests')
from sqlalchemy.orm import Session
from test_phase4_reclaim_authority_context import _persist_real_phase4_reclaim

class ProcessPatch:
    def setattr(self, target, name, value):
        setattr(target, name, value)

execution, research, _registry, _execution_maker, _research_maker = (
    _persist_real_phase4_reclaim(__import__('pathlib').Path(sys.argv[1]), ProcessPatch()))
with Session(execution) as session:
    from app.db.models import StrategyAdmission
    receipt = session.query(StrategyAdmission).filter_by(owner_id='owner-a').one()
    print(json.dumps({
        'admission_address': receipt.admission_address,
        'execution_url': str(execution.url),
        'research_url': str(research.url),
    }, sort_keys=True))
execution.dispose()
research.dispose()
"""


def _loader_program() -> str:
    return """
import datetime as dt
import json, sys
sys.path.insert(0, 'tests')
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.backtest.reclaim_authority import ReclaimAuthorityContext
from app.backtest.repository import AdmissionRequired, load_verified_admission
from app.db.models import BacktestRun
from app.ir.registry import DependencyBoundary, registered_v2_implementation
from tests.test_phase4_capability_admission import _plan

registry, _document, _plan_value = _plan()
if sys.argv[4] == 'registry':
    registrations = {
        key: registered_v2_implementation(
            component=key, implementation=implementation,
            dependency_boundary=DependencyBoundary('defining_module'))
        for key, implementation in registry.v2_implementations.items()
    }
    registry = type(registry)(components={}, bodies={}, registrations={},
        v2_types=registry.v2_types, v2_components=registry.v2_components,
        v2_implementations=registrations,
        data_requirement_declarations={})
elif sys.argv[4] == 'implementation':
    registry = type(registry)(components={}, bodies={}, registrations={},
        v2_types=registry.v2_types, v2_components=registry.v2_components,
        v2_implementations={},
        data_requirement_declarations=registry.data_requirement_declarations)
execution = sa.create_engine(sys.argv[1], future=True)
research = sa.create_engine(sys.argv[2], future=True)
cutoff = dt.datetime(2026, 8, 1, 3, tzinfo=dt.timezone.utc)
with Session(execution) as execution_session, Session(research) as research_session:
    context = ReclaimAuthorityContext(
        registry=registry, research_sessionmaker=lambda: Session(research))
    run_count_before = execution_session.query(BacktestRun).count()
    try:
        load_verified_admission(
            execution_session, owner_id='owner-a', admission_address=sys.argv[3],
            authority_context=context, research_session=research_session,
            at_time=cutoff)
    except AdmissionRequired as exc:
        assert execution_session.query(BacktestRun).count() == run_count_before
        print(json.dumps({'mutation': sys.argv[4], 'refusal': exc.code,
                          'admission_address': sys.argv[3],
                          'backtest_run_count': run_count_before}, sort_keys=True))
    else:
        raise AssertionError('Phase 4 loader unexpectedly returned runtime authority')
execution.dispose()
research.dispose()
"""


def _stale_mutation_program() -> str:
    return """
import json, sys
import sqlalchemy as sa
execution = sa.create_engine(sys.argv[1], future=True)
research = sa.create_engine(sys.argv[2], future=True)
mutation, admission_address = sys.argv[3], sys.argv[4]
for engine in (execution, research):
    with engine.begin() as connection:
        connection.execute(sa.text('PRAGMA foreign_keys = OFF'))
        for name in connection.execute(sa.text(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )).scalars():
            connection.exec_driver_sql('DROP TRIGGER "' + name.replace('"', '""') + '"')
if mutation == 'topology':
    with execution.begin() as connection:
        connection.execute(sa.text(
            "UPDATE ir_v2_graph_versions SET graph_address=:address"),
            {'address': 'sha256:' + 'f' * 64})
elif mutation in {'dataset', 'truth', 'capability', 'product', 'contract'}:
    targets = {
        'dataset': (research, 'research_dataset_manifests_v2'),
        'truth': (execution, 'authority_market_truth_snapshots'),
        'capability': (execution, 'authority_capability_assessments'),
        'product': (execution, 'authority_provider_products'),
        'contract': (execution, 'authority_provider_contracts'),
    }
    engine, table = targets[mutation]
    with engine.begin() as connection:
        connection.execute(sa.text('DELETE FROM ' + table))
elif mutation in {'policy', 'owner'}:
    with execution.begin() as connection:
        row = connection.execute(sa.text(
            'SELECT artifact_json FROM strategy_admissions WHERE owner_id=:owner AND admission_address=:address'
        ), {'owner': 'owner-a', 'address': admission_address}).mappings().one()
        document = json.loads(row['artifact_json'])
        if mutation == 'policy':
            document['phase4_data_binding']['evaluation_policy_address'] = 'sha256:' + 'f' * 64
        else:
            document['owner_id'] = 'owner-b'
        connection.execute(sa.text(
            'UPDATE strategy_admissions SET owner_id=:replacement_owner, artifact_json=:artifact_json WHERE owner_id=:owner AND admission_address=:address'
        ), {'replacement_owner': 'owner-b' if mutation == 'owner' else 'owner-a',
            'artifact_json': json.dumps(document, sort_keys=True, separators=(',', ':')),
            'owner': 'owner-a', 'address': admission_address})
else:
    raise AssertionError(mutation)
print(json.dumps({'mutation': mutation, 'admission_address': admission_address}, sort_keys=True))
execution.dispose()
research.dispose()
"""


def test_canonical_document_is_complete_domain_separated_and_deterministic():
    registry = compound_registry()
    document = _connected_compound_document()
    first = resolve_v2(document, registry)
    shuffled = deepcopy(document)
    shuffled["nodes"].reverse()
    shuffled["edges"].reverse()
    second = resolve_v2(shuffled, registry)

    assert first.resolved_graph_address == second.resolved_graph_address
    topology = _plain(first.topology_document)
    assert set(topology) == {
        "format_version", "authored_executable_address", "registry_snapshot", "implementation_closure",
        "declaration_closure", "nodes", "edges", "bundles", "graph_inputs",
        "graph_outputs", "compound_lowering",
    }
    assert topology["graph_inputs"] and topology["graph_outputs"]
    assert topology["edges"] and topology["bundles"]
    assert topology["compound_lowering"][0]["lowered_path"] == ["bundle", "leaf"]
    assert first.resolved_graph_address == content_address({
        "schema": RESOLVED_V2_TOPOLOGY_SCHEMA,
        "fact": topology,
    })


@pytest.mark.parametrize(
    "label,mutation",
    [
        ("graph-input-boundary", lambda doc, reg: doc["graph_inputs"][0].__setitem__("semantic_role", "alternate")),
        ("edge-provenance", lambda doc, reg: doc["edges"][0].__setitem__("edge_id", "outer-input-renamed")),
        ("compound-parameter", lambda doc, reg: doc["nodes"][0]["parameters"].__setitem__("gain", 4.5)),
    ],
)
def test_semantic_topology_mutations_change_identity(label, mutation):
    del label
    registry = compound_registry()
    document = _connected_compound_document()
    baseline = resolve_v2(document, registry).resolved_graph_address
    changed = deepcopy(document)
    mutation(changed, registry)
    assert resolve_v2(changed, registry).resolved_graph_address != baseline


def test_bundle_order_member_type_default_and_registry_payload_enter_identity():
    registry = _bundle_registry()
    ordered = bundle_document("ordered", [
        bundle_edge("a", "source-a", binding={"kind": "ordered", "position": 0}),
        bundle_edge("b", "source-b", binding={"kind": "ordered", "position": 1}),
    ])
    swapped = deepcopy(ordered)
    swapped["edges"][0]["binding"]["position"] = 1
    swapped["edges"][1]["binding"]["position"] = 0
    assert resolve_v2(ordered, registry).resolved_graph_address != resolve_v2(swapped, registry).resolved_graph_address

    default_document = bundle_document("optional", [])
    default_registry = _bundle_registry()
    changed_components = {key: _plain(value) for key, value in default_registry.v2_components.items()}
    changed_components[("optional", 1)]["ports"][0]["default"] = 1.0
    changed_registry = PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types=default_registry.v2_types,
        v2_components=changed_components,
    )
    original = resolve_v2(default_document, default_registry)
    changed = resolve_v2(default_document, changed_registry)
    assert original.bundles[("target", "value")].default == 0.0
    assert changed.bundles[("target", "value")].default == 1.0
    assert original.resolved_graph_address != changed.resolved_graph_address
    member = resolve_v2(ordered, registry).topology_document["edges"][0]
    assert member["member_type"] == {"type_id": "test.float", "type_version": 1}


def test_presentation_and_lineage_are_excluded_while_executable_changes_are_bound():
    from app.ir.formats.v2 import graph_address_for

    document = _connected_compound_document()
    registry = compound_registry()
    baseline_content = content_address(document)
    baseline_graph = graph_address_for(document, registry)
    baseline_resolved = resolve_v2(document, registry).resolved_graph_address
    variants = []
    for mutate in (
        lambda value: value["metadata"].__setitem__("name", "Presentation name"),
        lambda value: value["metadata"].__setitem__("description", "Presentation description"),
        lambda value: value["metadata"].__setitem__("tags", ["presentation"]),
        lambda value: value.__setitem__("strategy_id", "lineage-only"),
        lambda value: value.__setitem__("strategy_version", 2),
    ):
        variant = deepcopy(document)
        mutate(variant)
        variants.append(variant)
    for variant in variants:
        assert content_address(variant) != baseline_content
        assert graph_address_for(variant, registry) == baseline_graph
        assert resolve_v2(variant, registry).resolved_graph_address == baseline_resolved

    executable = deepcopy(document)
    executable["nodes"][0]["parameters"]["gain"] = 8.5
    assert content_address(executable) != baseline_content
    assert graph_address_for(executable, registry) != baseline_graph
    assert resolve_v2(executable, registry).resolved_graph_address != baseline_resolved
    assert "metadata" not in resolve_v2(document, registry).topology_document


def test_plain_nodes_cannot_create_an_incomplete_authority_address_or_compile():
    resolved = resolve_v2(compound_document(), compound_registry())
    plain_nodes = tuple(resolved.nodes)
    with pytest.raises(ResolutionError, match="complete canonical document"):
        resolved_v2_graph_address(
            plain_nodes, resolved.registry_snapshot_address,
            resolved.implementation_closure_address, resolved.registry_snapshot_payload,
            resolved.data_requirement_declaration_closure,
        )
    incomplete = replace(resolved, topology_document=None, nodes=plain_nodes)
    with pytest.raises((ResolutionError, DataRequirementRefusal)):
        compile_data_requirement_plan(incomplete)


def test_replaced_bundle_output_graph_input_and_implementation_closure_refuse_stale_address():
    resolved = resolve_v2(_connected_compound_document(), compound_registry())
    key, bundle = next(iter(resolved.bundles.items()))
    forged_bundle = replace(bundle, default=99.0, default_provenance="forged")
    with pytest.raises(DataRequirementRefusal, match="identity"):
        compile_data_requirement_plan(replace(resolved, bundles={key: forged_bundle}))

    name, output = next(iter(resolved.outputs.items()))
    forged_output = replace(output, edge_id="forged-output")
    with pytest.raises(DataRequirementRefusal, match="identity"):
        compile_data_requirement_plan(replace(resolved, outputs={name: forged_output}))

    graph_inputs = {key: _plain(value) for key, value in resolved.graph_inputs.items()}
    graph_inputs["in"]["semantic_role"] = "forged-input"
    with pytest.raises(DataRequirementRefusal, match="identity"):
        compile_data_requirement_plan(replace(resolved, graph_inputs=graph_inputs))

    with pytest.raises(DataRequirementRefusal, match="identity"):
        compile_data_requirement_plan(replace(
            resolved, graph_inputs={"forged-key": resolved.graph_inputs["in"]},
        ))

    with pytest.raises(DataRequirementRefusal, match="identity"):
        compile_data_requirement_plan(replace(resolved, format_version=3))

    with pytest.raises(ResolutionError, match="closure address"):
        compile_data_requirement_plan(replace(
            resolved, implementation_closure_address="sha256:" + "d" * 64,
        ))


def test_adv_001_identical_inputs_converge_and_changed_semantics_diverge():
    registry = compound_registry()
    document = _connected_compound_document()
    first = resolve_v2(document, registry)
    assert resolve_v2(deepcopy(document), registry).resolved_graph_address == first.resolved_graph_address
    changed = deepcopy(document)
    changed["nodes"][0]["parameters"]["gain"] = 9.0
    changed_address = resolve_v2(changed, registry).resolved_graph_address
    assert changed_address != first.resolved_graph_address
    print(json.dumps({"baseline": first.resolved_graph_address, "changed": changed_address}))


def test_adv_017_canonical_bytes_converge_and_distinct_topology_bytes_diverge():
    registry = compound_registry()
    first = resolve_v2(_connected_compound_document(), registry)
    second = resolve_v2(_connected_compound_document(), registry)
    assert canonical_json(_plain(first.topology_document)) == canonical_json(_plain(second.topology_document))
    changed = resolve_v2(compound_document(gain=7.0), registry)
    assert canonical_json(_plain(first.topology_document)) != canonical_json(_plain(changed.topology_document))
    assert first.resolved_graph_address != changed.resolved_graph_address
    print(json.dumps({
        "canonical_baseline": content_address(_plain(first.topology_document)),
        "canonical_changed": content_address(_plain(changed.topology_document)),
        "resolved_baseline": first.resolved_graph_address,
        "resolved_changed": changed.resolved_graph_address,
    }))


def test_adv_018_forged_topology_document_and_outer_address_refuse():
    resolved = resolve_v2(compound_document(), compound_registry())
    forged = replace(resolved, resolved_graph_address="sha256:" + "f" * 64)
    with pytest.raises(DataRequirementRefusal, match="identity"):
        compile_data_requirement_plan(forged)
    name, output = next(iter(resolved.outputs.items()), (None, None))
    if output is None:
        stale = replace(resolved, authored_executable_address="sha256:" + "e" * 64)
    else:
        stale = replace(resolved, outputs={name: replace(output, edge_id="forged")})
    with pytest.raises(DataRequirementRefusal, match="identity"):
        compile_data_requirement_plan(stale)
    print(json.dumps({
        "valid": resolved.resolved_graph_address,
        "forged_outer": forged.resolved_graph_address,
        "stale_authored_executable": stale.authored_executable_address,
    }))


def test_adv_019_real_writer_exit_fresh_loader_stale_refusal_then_runtime_boundary(tmp_path: Path):
    """ADV-019 crosses a complete persisted two-plane chain at the real loader."""
    mutations = (
        "topology", "registry", "implementation", "dataset", "truth",
        "capability", "policy", "owner", "product", "contract",
    )

    def write(case: Path) -> dict[str, str]:
        completed = subprocess.run(
            [sys.executable, "-c", _writer_program(), str(case)],
            text=True, capture_output=True, check=True,
        )
        return json.loads(completed.stdout.strip())

    def load(fact: dict[str, str], mutation: str) -> dict[str, str]:
        completed = subprocess.run(
            [sys.executable, "-c", _loader_program(), fact["execution_url"],
             fact["research_url"], fact["admission_address"], mutation],
            text=True, capture_output=True,
        )
        assert completed.returncode == 0, completed.stderr
        return json.loads(completed.stdout.strip())

    observations = {}
    for mutation in mutations:
        case = tmp_path / mutation
        case.mkdir()
        fact = write(case)
        if mutation not in {"registry", "implementation"}:
            changed = subprocess.run(
                [sys.executable, "-c", _stale_mutation_program(),
                 fact["execution_url"], fact["research_url"], mutation,
                 fact["admission_address"]],
                text=True, capture_output=True,
            )
            assert changed.returncode == 0, changed.stderr
            assert json.loads(changed.stdout.strip())["mutation"] == mutation
        observed = load(fact, mutation)
        assert observed["mutation"] == mutation
        assert observed["refusal"] == "RECEIPT_STALE"
        observations[mutation] = observed["refusal"]

    current_case = tmp_path / "current"
    current_case.mkdir()
    current_fact = write(current_case)
    current = load(current_fact, "current")
    assert current == {
        "admission_address": current_fact["admission_address"],
        "backtest_run_count": 1,
        "mutation": "current",
        "refusal": "V2_RUNTIME_UNAVAILABLE",
    }
    assert set(observations) == set(mutations)
    print(json.dumps({"stale_refusals": observations, "current": current}, sort_keys=True))


def test_adv_020_missing_current_implementation_refuses_before_runtime(tmp_path: Path):
    database = tmp_path / "phase4-missing-implementation"
    database.mkdir()
    writer = subprocess.run(
        [sys.executable, "-c", _writer_program(), str(database)],
        text=True, capture_output=True, check=True,
    )
    fact = json.loads(writer.stdout.strip())
    stale = subprocess.run(
        [sys.executable, "-c", _loader_program(), fact["execution_url"],
         fact["research_url"], fact["admission_address"], "implementation"],
        text=True, capture_output=True, check=True,
    )
    stale_fact = json.loads(stale.stdout.strip())
    assert stale_fact["refusal"] == "RECEIPT_STALE"
    print(json.dumps(stale_fact, sort_keys=True))


def test_adv_024_empty_graph_has_typed_complete_identity():
    document = {
        "format_version": 2, "strategy_id": "empty", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Empty", "description": None, "tags": []},
        "graph_inputs": [], "graph_outputs": [], "nodes": [], "edges": [],
    }
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={}, v2_components={})
    resolved = resolve_v2(document, registry)
    assert resolved.topology_document["nodes"] == ()
    assert resolved.topology_document["edges"] == ()
    assert resolved.resolved_graph_address.startswith("sha256:")
    print(json.dumps({"empty_resolved_graph_address": resolved.resolved_graph_address}))


def test_adv_025_huge_graph_refuses_at_preflight_limit():
    document = {
        "format_version": 2, "strategy_id": "huge", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Huge", "description": None, "tags": []},
        "graph_inputs": [], "graph_outputs": [],
        "nodes": [{"node_id": "n", "component": {"component_id": "missing", "component_version": 1}, "parameters": {}}] * (V2_MAX_AUTHORED_NODES + 1),
        "edges": [],
    }
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={}, v2_components={})
    with pytest.raises(ResolutionError) as exc:
        resolve_v2(document, registry)
    assert exc.value.clause == "V2_LIMIT"
    print(json.dumps({"huge_input_address": content_address(document),
                      "refusal": exc.value.clause}))


def test_adv_025_huge_boundary_refuses_at_preflight_limit():
    document = {
        "format_version": 2, "strategy_id": "huge-boundary", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Huge boundary", "description": None, "tags": []},
        "graph_inputs": [{"port_id": "in", "direction": "input"}] * (V2_MAX_BOUNDARY_PORTS + 1),
        "graph_outputs": [], "nodes": [], "edges": [],
    }
    registry = SimpleNamespace(v2_components={})
    with pytest.raises(ResolutionError) as exc:
        resolve_v2(document, registry)
    assert exc.value.clause == "V2_LIMIT"
    print(json.dumps({"huge_boundary_address": content_address(document),
                      "refusal": exc.value.clause}))


def test_adv_025_deep_compound_chain_refuses_without_recursion_error():
    depth = 1_200
    components = {}
    for index in range(depth):
        child = index + 1
        body_nodes = [] if child == depth else [{
            "node_id": f"n{child}",
            "component": {"component_id": f"c{child}", "component_version": 1},
            "parameters": {},
        }]
        components[(f"c{index}", 1)] = {
            "compound": {"body": {
                "graph_inputs": [], "graph_outputs": [],
                "nodes": body_nodes, "edges": [],
            }},
        }
    document = {
        "format_version": 2, "strategy_id": "deep", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Deep", "description": None, "tags": []},
        "graph_inputs": [], "graph_outputs": [],
        "nodes": [{"node_id": "n0", "component": {
            "component_id": "c0", "component_version": 1}, "parameters": {}}],
        "edges": [],
    }
    with pytest.raises(ResolutionError) as exc:
        resolve_v2(document, SimpleNamespace(v2_components=components))
    assert exc.value.clause == "V2_LIMIT"
    assert "depth" in str(exc.value)
    print(json.dumps({"deep_chain_address": content_address(document),
                      "depth": depth, "refusal": exc.value.clause}))


def test_adv_025_compound_depth_acceptance_boundary_is_safe_and_next_refuses():
    accepted_document, accepted_registry = _compound_chain(V2_MAX_COMPOUND_DEPTH)
    accepted = resolve_v2(accepted_document, accepted_registry)
    assert len(accepted.nodes) == 1
    refused_document, refused_registry = _compound_chain(V2_MAX_COMPOUND_DEPTH + 1)
    with pytest.raises(ResolutionError) as exc:
        resolve_v2(refused_document, refused_registry)
    assert exc.value.clause == "V2_LIMIT"
    assert "depth" in str(exc.value)
    print(json.dumps({
        "accepted_depth": V2_MAX_COMPOUND_DEPTH,
        "accepted_address": accepted.resolved_graph_address,
        "first_refused_depth": V2_MAX_COMPOUND_DEPTH + 1,
        "refusal": exc.value.clause,
    }))
