"""Focused IR-v2 admission receipt and persistence contract cases."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.strategy_admissions import (
    AdmissionPersistenceError,
    get,
    put,
    require_current,
)
from app.db.models import Base, Organization, StrategyAdmission
from app.ir.hashing import content_address
from app.ir.registry import (
    DependencyBoundary,
    PlatformRegistry,
    registered_v2_implementation,
)
from app.strategy.admission import (
    V2AdmissionEvidence,
    admit_v2_strategy,
)


ADDRESS = "sha256:" + "a" * 64


def _scale_implementation(parameters, inputs):
    return {"out": inputs["in"] * parameters["gain"]}


def _type() -> dict[str, object]:
    return {
        "type_id": "test.float",
        "type_version": 1,
        "shapes": ["scalar"],
        "runtime_representation": "float",
    }


def _port(port_id: str, direction: str, *, default: object = ...):
    port: dict[str, object] = {
        "port_id": port_id,
        "direction": direction,
        "semantic_flow": "value",
        "semantic_role": "value",
        "type_ref": {"type_id": "test.float", "type_version": 1},
        "shape": "scalar",
    }
    if direction == "input":
        port["connections"] = {
            "cardinality": "optional" if default is not ... else "single",
            "min": 0 if default is not ... else 1,
            "max": 1,
            "assembly": "single",
        }
        if default is not ...:
            port["default"] = default
    return port


def _registry() -> PlatformRegistry:
    parameter = {
        "type": "float", "required": True, "default": None, "enum": None,
        "domain": None, "units": "value", "serialization": "canonical-float",
    }
    leaf = {
        "component_id": "leaf.scale", "component_version": 1,
        "domain_family": "utility", "structural_role": "transform",
        "ports": [_port("in", "input"), _port("out", "output")],
        "parameters": {"gain": parameter},
    }
    compound = {
        "component_id": "compound.bundle", "component_version": 1,
        "domain_family": "utility", "structural_role": "transform",
        "ports": [_port("in", "input", default=0.0), _port("out", "output")],
        "parameters": {"gain": parameter},
        "compound": {
            "body": {
                "graph_inputs": [_port("in", "input", default=0.0)],
                "graph_outputs": [_port("out", "output")],
                "nodes": [{
                    "node_id": "leaf", "component": {
                        "component_id": "leaf.scale", "component_version": 1,
                    }, "parameters": {},
                }],
                "edges": [
                    {"edge_id": "input", "source": {"scope": "graph_input", "port_id": "in"},
                     "target": {"scope": "node", "node_id": "leaf", "port_id": "in"},
                     "binding": {"kind": "single"}},
                    {"edge_id": "output", "source": {"scope": "node", "node_id": "leaf", "port_id": "out"},
                     "target": {"scope": "graph_output", "port_id": "out"},
                     "binding": {"kind": "single"}},
                ],
            },
            "parameter_bindings": [{"parameter_id": "gain", "targets": [{
                "node_id": "leaf", "parameter_id": "gain",
            }]}],
        },
    }
    registration = registered_v2_implementation(
        component=("leaf.scale", 1),
        implementation=_scale_implementation,
        dependency_boundary=DependencyBoundary("defining_module"),
    )
    return PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types={("test.float", 1): _type()},
        v2_components={("leaf.scale", 1): leaf, ("compound.bundle", 1): compound},
        v2_implementations={("leaf.scale", 1): registration},
    )


def _document(*, gain: float = 3.5) -> dict[str, object]:
    return {
        "format_version": 2,
        "strategy_id": "receipt-fixture",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Receipt", "description": None, "tags": []},
        "graph_inputs": [], "graph_outputs": [],
        "nodes": [{
            "node_id": "bundle",
            "component": {"component_id": "compound.bundle", "component_version": 1},
            "parameters": {"gain": gain},
        }],
        "edges": [],
    }


def _evidence() -> V2AdmissionEvidence:
    return V2AdmissionEvidence(*(ADDRESS[:7] + c + ADDRESS[8:] for c in "1234567"))


def _artifact(*, owner_id: str = "owner-a", gain: float = 3.5):
    return admit_v2_strategy(
        owner_id=owner_id, document=_document(gain=gain), registry=_registry(), evidence=_evidence()
    )


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            Organization(organization_id="owner-a", name="Owner A"),
            Organization(organization_id="owner-b", name="Owner B"),
        ])
        session.commit()
        yield session
    engine.dispose()


def test_v2_receipt_binds_canonical_content_graph_and_compound_provenance():
    artifact = _artifact()
    receipt = artifact.to_dict()
    assert receipt["content_address"] == artifact.content_address
    assert receipt["graph_address"] == artifact.graph_address
    assert artifact.admission_address != artifact.content_address
    node = next(item for item in artifact.resolved_topology["nodes"] if item["node_id"] == "bundle/leaf")
    assert node["parameters"]["gain"] == 3.5
    assert node["parameter_provenance"]["gain"]["path"] == ("bundle", "leaf")
    assert node["parameter_provenance"]["gain"]["target_paths"] == (("leaf", "gain"),)


def test_v2_receipt_pins_registry_owned_transitive_implementation_identity():
    artifact = _artifact()
    snapshot = artifact.registry_snapshot["snapshot"]
    identities = snapshot["implementation_identities"]
    assert [dict(identity) for identity in identities] == [{
        "component_id": "leaf.scale",
        "component_version": 1,
        "implementation_address": _registry().v2_implementation_identities[("leaf.scale", 1)],
    }]
    assert artifact.admission_address == content_address(artifact.to_dict())
    with pytest.raises(TypeError):
        identities[0]["component_id"] = "forged"


def test_v2_registry_refuses_stale_or_forged_leaf_identity():
    registry = _registry()
    registration = registry.v2_implementation_identities
    forged = registered_v2_implementation(
        component=("leaf.scale", 1),
        implementation=_scale_implementation,
        dependency_boundary=DependencyBoundary("defining_module"),
    )
    forged = replace(forged, implementation_address=ADDRESS)
    with pytest.raises(ValueError, match="stale or forged"):
        PlatformRegistry(
            components={}, bodies={}, registrations={},
            v2_types=registry.v2_types,
            v2_components=registry.v2_components,
            v2_implementations={("leaf.scale", 1): forged},
        )


def test_v2_persistence_is_deterministic_idempotent_and_owner_scoped(db):
    artifact = _artifact()
    first = put(db, artifact)
    second = put(db, artifact)
    db.commit()
    assert first is second
    assert db.scalar(select(StrategyAdmission).where(StrategyAdmission.owner_id == "owner-a")).artifact_json == first.artifact_json
    assert get(db, owner_id="owner-b", admission_address=artifact.admission_address) is None
    with pytest.raises(AdmissionPersistenceError, match="absent"):
        require_current(db, replace(artifact, owner_id="owner-b"))


def test_v2_partial_or_mismatched_evidence_fails_closed():
    with pytest.raises(ValueError, match="canonical content address"):
        V2AdmissionEvidence(
            "missing", ADDRESS, ADDRESS, ADDRESS, ADDRESS, ADDRESS, ADDRESS
        )
    artifact = _artifact()
    forged = deepcopy(artifact.to_dict())
    forged["content_address"] = ADDRESS
    forged_artifact = _ForgedReceipt(artifact, forged)
    with pytest.raises(AdmissionPersistenceError, match="address does not match"):
        put(_new_session(), forged_artifact)


class _ForgedReceipt:
    def __init__(self, artifact, document):
        self._artifact = artifact
        self._document = document

    def __getattr__(self, name):
        return getattr(self._artifact, name)

    def to_dict(self):
        return self._document


def _new_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Organization(organization_id="owner-a", name="Owner A"))
    session.commit()
    return session


def test_v2_receipt_content_and_provenance_mutations_are_killed(db):
    artifact = _artifact()
    put(db, artifact)
    db.commit()
    with pytest.raises(TypeError):
        artifact.document["metadata"] = {}
    with pytest.raises(TypeError):
        artifact.resolved_topology["nodes"][0]["parameter_provenance"]["gain"]["path"] = ("forged",)
    row = db.get(StrategyAdmission, (artifact.owner_id, artifact.admission_address))
    row.artifact_json = row.artifact_json.replace("receipt-fixture", "forged-fixture")
    with pytest.raises(ValueError, match="immutable"):
        db.commit()
    db.rollback()
