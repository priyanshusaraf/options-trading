from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from app.ir.first_party import analytical
from app.ir.first_party.conformance import (
    CatalogueConformanceError,
    assert_catalogue_complete,
    assert_deterministic,
    assert_prefix_causal,
    reference_frame,
)
from app.ir.library import REGISTRY
from app.ir.registry import PlatformRegistry


CATALOGUE = Path(__file__).resolve().parents[2] / "docs/reports/phase5-v1-catalogue.json"


def _expected_names() -> set[str]:
    document = json.loads(CATALOGUE.read_text())
    result: set[str] = set()
    for group in document["groups"]:
        if group["owner_capsule"] != "phase5-first-party-analytical-catalogue":
            continue
        result.update(group["v1_required"])
        result.update(group["v1_capability_gated"])
    return result


def test_production_registry_equals_frozen_type2_type4_inventory():
    expected = _expected_names()
    assert set(analytical.CATALOGUE_NAMES) == expected
    expected_components = {(analytical.component_id(name), 1) for name in expected}
    assert_catalogue_complete(analytical.REGISTRY, expected_components)
    assert expected_components <= set(REGISTRY.v2_components)
    for key in expected_components:
        assert REGISTRY.node_contract_addresses[key] \
            == analytical.REGISTRY.node_contract_addresses[key]
    assert len(expected_components) == 125


@pytest.mark.parametrize("name", analytical.CATALOGUE_NAMES)
def test_every_entry_is_deterministic_prefix_causal_and_closed(name):
    registration = REGISTRY.v2_implementation_registrations[(analytical.component_id(name), 1)]
    parameters = {"window": 14, "capability_verified": name in analytical.CAPABILITY_GATED_NAMES}
    frame = reference_frame()
    assert_deterministic(registration.implementation, frame, parameters)
    assert_prefix_causal(registration.implementation, frame, parameters)
    contract = REGISTRY.node_contracts[(analytical.component_id(name), 1)]
    assert len(contract) == 22
    assert contract["visible_family"] in {"TYPE_2", "TYPE_4"}
    assert REGISTRY.data_requirement_declarations[(analytical.component_id(name), 1)][
        "classification"
    ] == "REQUIRES_DATA"


@pytest.mark.parametrize("name", analytical.CAPABILITY_GATED_NAMES)
def test_capability_gated_entries_refuse_without_accepted_fact(name):
    implementation = REGISTRY.v2_implementation_registrations[
        (analytical.component_id(name), 1)
    ].implementation
    with pytest.raises(analytical.AnalyticalRefusal, match="CAPABILITY_REQUIRED"):
        implementation({"window": 14, "capability_verified": False}, {"frame": reference_frame()})


def test_representative_independent_mathematical_vectors():
    frame = reference_frame(40)
    sma = analytical.evaluate_analytical("SMA", frame, {"window": 5})
    pd.testing.assert_series_equal(sma, frame["close"].rolling(5).mean())
    point = analytical.evaluate_analytical("POINT_CHANGE", frame, {"window": 3})
    pd.testing.assert_series_equal(point, frame["close"].diff(3))
    hl2 = analytical.evaluate_analytical("HL2", frame, {"window": 5})
    pd.testing.assert_series_equal(hl2, (frame["high"] + frame["low"]) / 2)
    cross = analytical.evaluate_analytical("CROSS_ABOVE", frame, {"window": 5})
    expected = (frame["close"] > frame["peer"]) & (
        frame["close"].shift() <= frame["peer"].shift()
    )
    pd.testing.assert_series_equal(cross, expected)


@pytest.mark.parametrize("missing", ["component", "implementation", "contract", "declaration"])
def test_complete_universe_gate_rejects_each_missing_surface(missing):
    types = dict(analytical.V2_TYPES)
    components = dict(analytical.V2_COMPONENTS)
    implementations = dict(analytical.V2_IMPLEMENTATIONS)
    contracts = dict(analytical.NODE_CONTRACTS)
    declarations = dict(analytical.DATA_REQUIREMENTS)
    key = sorted(components)[0]
    if missing == "component":
        components.pop(key); implementations.pop(key); contracts.pop(key); declarations.pop(key)
    elif missing == "implementation":
        implementations.pop(key)
    elif missing == "contract":
        contracts.pop(key)
    else:
        declarations.pop(key)
    if missing == "implementation":
        with pytest.raises(ValueError, match="implementation closure"):
            PlatformRegistry(
                components={}, bodies={}, registrations={}, v2_types=types,
                v2_components=components, v2_implementations=implementations,
                node_contracts=contracts, data_requirement_declarations=declarations,
            )
        return
    candidate = PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types=types,
        v2_components=components, v2_implementations=implementations,
        node_contracts=contracts, data_requirement_declarations=declarations,
    )
    with pytest.raises(CatalogueConformanceError):
        assert_catalogue_complete(
            candidate,
            {(analytical.component_id(name), 1) for name in analytical.CATALOGUE_NAMES},
        )


def test_registry_rebuild_and_mapping_order_are_identity_stable():
    reverse = PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types=dict(reversed(list(analytical.V2_TYPES.items()))),
        v2_components=dict(reversed(list(analytical.V2_COMPONENTS.items()))),
        v2_implementations=dict(reversed(list(analytical.V2_IMPLEMENTATIONS.items()))),
        node_contracts=dict(reversed(list(analytical.NODE_CONTRACTS.items()))),
        data_requirement_declarations=dict(reversed(list(analytical.DATA_REQUIREMENTS.items()))),
    )
    assert reverse.registry_snapshot_address == analytical.REGISTRY.registry_snapshot_address
