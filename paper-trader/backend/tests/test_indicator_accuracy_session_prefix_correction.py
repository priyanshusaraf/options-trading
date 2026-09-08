"""Correction-owner proof for the bounded F01-FRESH session-prefix repair."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd
import pytest

from app.ir import hashing, node_contracts
from app.ir.first_party.analytical_v2 import session_data as subject
from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract
from app.market_data.requirements import verify_data_requirement_plan
from tests import test_indicator_accuracy_session_data_fresh_assurance as fresh


ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction"
GENERATOR = RUN / "build_product.py"
RECEIPT = RUN / "source-receipt.json"
BASELINES = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/candidate-identities.json"
MATRIX = ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/component-matrix.json"
AUTHORITY = ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/source-authority.json"
SPECIFICATION = ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/specification.py"
PRODUCT = ROOT / "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py"

AFFECTED = frozenset({
    "DISTANCE_FROM_SESSION_HIGH_LOW", "PREVIOUS_SESSION_FIELDS", "PREVIOUS_SESSION_OHLC",
    "SESSION_HIGH", "SESSION_LOW", "SESSION_OPEN", "SESSION_OPEN_HIGH_LOW", "VWAP",
})

SEALED = {
    ".agent/runs/post-phase5-indicator-accuracy-session-data/build_product.py":
        "c865f8d58a9e2e4404d75a8d6bd94e35995e51f170a31378074a2f71f4952321",
    ".agent/runs/post-phase5-indicator-accuracy-session-data/session_data_body.py":
        "8fc337d04e5992b2d080864a153e2c7c5839bf3308d67131be44d47a1d73a56a",
    ".agent/runs/post-phase5-indicator-accuracy-correction-replan/specification.py":
        "09ec1f15fd915a6f6ae14af24b77532224cbf28c15456734a775d95c9637cdcb",
    ".agent/runs/post-phase5-indicator-accuracy-correction-replan/component-matrix.json":
        "95050aec6ab623e9f0fb606a0f5547f90dce93fc20a9d9944c128152c1394959",
}


def plain(value):
    return node_contracts._plain(value)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def original_specs() -> dict:
    specification = load_module(SPECIFICATION, "session_prefix_original_specification")
    rows = {row["name"]: row for row in json.loads(MATRIX.read_text())["records"]}
    authorities = json.loads(AUTHORITY.read_text())["records"]
    result = {}
    for name in subject.ALL_NAMES:
        row = rows[name]
        value = dict(specification.SPECS[name])
        value["decision"] = row["decision"]
        value["threshold_class"] = row["threshold_class"]
        value["source_addresses"] = tuple(
            "sha256:" + authorities[source]["sha256"] for source in row["source_authorities"]
        )
        result[name] = plain(value)
    return result


def identities() -> dict:
    result = {}
    for name in subject.NAMES:
        key = subject.component_key(name)
        result[name] = {
            "component_address": hashing.content_address(plain(subject.V2_COMPONENTS[key])),
            "source_contract_address": hashing.content_address(plain(subject.NODE_CONTRACTS[key])),
            "binding_source_contract_address": subject.CONTRACT_BINDINGS[key].source_contract_address,
            "binding_implementation_address": subject.CONTRACT_BINDINGS[key].implementation_address,
            "implementation_address": subject.V2_IMPLEMENTATIONS[key].implementation_address,
        }
    return result


def first_row(name: str, position: int = 0):
    selected = fresh.fixture_inputs(name)
    declared = subject.fields_by_port(name, fresh.params(name))
    index = next(iter(next(iter(selected.values())).values())).index
    row = {
        port: {field.lower(): selected[port][field.lower()].iloc[position] for field in fields}
        for port, fields in declared.items()
    }
    return selected, index, row


def test_generator_uses_sealed_inputs_and_overlays_only_the_eight_specs():
    assert GENERATOR.is_file()
    generator = load_module(GENERATOR, "session_prefix_correction_generator")
    assert frozenset(generator.AFFECTED) == AFFECTED
    for relative, wanted in SEALED.items():
        assert sha(ROOT / relative) == wanted
    before = original_specs()
    after = {name: plain(subject.SPECS[name]) for name in subject.ALL_NAMES}
    for name in subject.ALL_NAMES:
        if name not in AFFECTED:
            assert after[name] == before[name], name
            continue
        expected = deepcopy(before[name])
        expected["inputs"] = sorted((*expected["inputs"], "session_open_at"))
        assert after[name] == expected, name


def test_historical_regeneration_matches_sealed_receipt_without_mutating_product(tmp_path):
    before = PRODUCT.read_bytes()
    sealed_receipt = json.loads(RECEIPT.read_text())
    generator = load_module(GENERATOR, 'isolated_session_prefix_generator')
    inputs = {ROOT / name for name in SEALED}
    inputs.update((GENERATOR, AUTHORITY, generator.CAPSULE, generator.ORIGINAL_CAPSULE))
    for source in inputs:
        target = tmp_path / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    generated_product = tmp_path / PRODUCT.relative_to(ROOT)
    generated_product.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, str(tmp_path / GENERATOR.relative_to(ROOT))],
        cwd=tmp_path, check=True, text=True, capture_output=True,
    )
    assert sha(generated_product) == sealed_receipt['product_sha256']
    assert PRODUCT.read_bytes() == before
    receipt = json.loads((tmp_path / RECEIPT.relative_to(ROOT)).read_text())
    assert receipt == sealed_receipt
    assert receipt["decision"] == "F01-FRESH"
    assert set(receipt["affected_components"]) == AFFECTED
    assert receipt["product_sha256"] == sha(generated_product)
    assert receipt["original_specification_and_body_edited"] is False
    assert json.loads(completed.stdout)["product_sha256"] == sha(generated_product)


@pytest.mark.parametrize("name", sorted(AFFECTED))
def test_affected_contract_binding_and_plan_require_canonical_session_open(name):
    registry, resolved, context, plan, bound = fresh.compiled(name)
    fields = subject.fields_by_port(name, fresh.params(name))
    assert "SESSION_OPEN_AT" in fields["session"]
    contract = subject.source_contract(name)
    assert "session.session_open_at" in contract["required_market_fields"]
    session_fact = bound.document["input_binding"]["ports"]["session"]["binding"]
    assert session_fact["fields"].count("SESSION_OPEN_AT") == 1
    assert session_fact["instrument"] == {"role": "session", "type": "PHYSICAL"}
    assert session_fact["session"] == "INSTRUMENT_CALENDAR"
    assert session_fact["derived_local"] is True
    assert session_fact["alignment"] == {"kind": "EXACT", "maximum_skew_seconds": 0}
    verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=context)


@pytest.mark.parametrize("name", sorted(AFFECTED))
def test_second_slot_and_missing_session_open_refuse_before_state_mutation(name):
    _, _, _, _, bound = fresh.compiled(name)
    selected, index, row = first_row(name, position=1)
    state = subject.SessionDataState(name, fresh.params(name), bound)
    before = state.snapshot()
    with pytest.raises(node_contracts.NodeContractRefusal, match="INCOMPLETE_SESSION_PREFIX"):
        state.step(row, event_time=index[1])
    assert state.snapshot() == before

    missing = {
        port: {field: series for field, series in values.items() if field != "session_open_at"}
        for port, values in selected.items()
    }
    with pytest.raises(node_contracts.NodeContractRefusal):
        subject.evaluate(name, fresh.params(name), missing, bound_contract=bound)


@pytest.mark.parametrize("name", sorted(AFFECTED))
def test_session_open_identity_and_next_slot_continuity_are_exact(name):
    _, _, _, _, bound = fresh.compiled(name)
    _, index, row0 = first_row(name, position=0)
    _, _, row1 = first_row(name, position=1)
    state = subject.SessionDataState(name, fresh.params(name), bound)
    state.step(row0, event_time=index[0])
    established = state.snapshot()

    changed = deepcopy(row1)
    changed["session"]["session_open_at"] = pd.Timestamp("2026-01-02T21:30:00Z")
    with pytest.raises(node_contracts.NodeContractRefusal, match="SESSION_IDENTITY_CHANGED"):
        state.step(changed, event_time=index[1])
    assert state.snapshot() == established

    skipped = deepcopy(row1)
    with pytest.raises(node_contracts.NodeContractRefusal, match="MISSING_SESSION_SLOT"):
        state.step(skipped, event_time=index[2])
    assert state.snapshot() == established


@pytest.mark.parametrize(
    "name,field,value",
    [
        ("SESSION_HIGH", "instrument", {"role": "primary", "type": "PHYSICAL"}),
        ("SESSION_LOW", "derived_local", False),
        ("SESSION_OPEN", "alignment", {"kind": "AS_OF", "maximum_skew_seconds": 1}),
        ("VWAP", "session", "CONTINUOUS"),
    ],
)
def test_wrong_session_binding_facts_fail_real_plan_verifier(name, field, value):
    registry, resolved, context, plan, _ = fresh.compiled(name)
    document = plain(context.document)
    binding = document["inputs"]["session"]["binding"]
    binding[field] = value
    row = document["inputs"]["session"]
    row["binding_address"] = hashing.content_address(binding)
    row["source_address"] = row["binding_address"]
    with pytest.raises((ValueError, node_contracts.NodeContractRefusal)):
        forged = type(context)(document, hashing.content_address(document))
        verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=forged)


def test_wrong_session_binding_address_and_stale_bound_receipt_refuse():
    name = "PREVIOUS_SESSION_OHLC"
    registry, resolved, context, plan, bound = fresh.compiled(name)
    document = plain(context.document)
    document["inputs"]["session"]["source_address"] = hashing.content_address({"stale": True})
    with pytest.raises((ValueError, node_contracts.NodeContractRefusal)):
        forged = type(context)(document, hashing.content_address(document))
        verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=forged)

    stale = plain(bound.document)
    stale["source_contract_address"] = json.loads(BASELINES.read_text())["records"][name][
        "source_contract_address"
    ]
    stale["bound_contract_address"] = hashing.content_address(
        {key: value for key, value in stale.items() if key != "bound_contract_address"}
    )
    stale_bound = ResolvedNodeContract(stale, stale["bound_contract_address"])
    with pytest.raises(node_contracts.NodeContractRefusal, match="BINDING_REPLAY_MISMATCH"):
        subject.SessionDataState(name, fresh.params(name), stale_bound)


def test_stale_state_snapshot_refuses_after_contract_identity_move():
    name = "SESSION_OPEN_HIGH_LOW"
    _, _, _, _, bound = fresh.compiled(name)
    _, index, row = first_row(name)
    state = subject.SessionDataState(name, {}, bound)
    state.step(row, event_time=index[0])
    stale = plain(state.snapshot())
    stale["bound_contract_address"] = json.loads(BASELINES.read_text())["records"][name][
        "source_contract_address"
    ]
    body = {key: value for key, value in stale.items() if key != "payload_address"}
    stale["payload_address"] = hashing.content_address(body)
    with pytest.raises(node_contracts.NodeContractRefusal, match="STATE_IDENTITY"):
        subject.SessionDataState.restore(name, {}, bound, stale)


def test_invalid_bar_resets_values_without_certifying_incomplete_previous_session():
    name = "PREVIOUS_SESSION_FIELDS"
    _, _, _, _, bound = fresh.compiled(name, field="volume")
    selected = fresh.fixture_inputs(name, field="volume")
    selected["frame"]["volume"] = selected["frame"]["volume"].copy()
    selected["frame"]["volume"].iloc[1] = -1.0
    result = subject.evaluate(
        name, {"field": "volume"}, selected, bound_contract=bound,
    )["value"]
    assert result.iloc[1].state.name == "INVALID"
    # The first session reaches its declared close after the reset, but it has
    # only one post-gap slot. The next session must not receive that suffix as a
    # completed prior-session aggregate.
    assert result.iloc[3].state.name == "INSUFFICIENT_HISTORY"


def test_historical_source_disposition_and_current_registry_identity_are_exact():
    baseline = json.loads(BASELINES.read_text())["records"]
    current = identities()
    assert set(current) == set(baseline) == set(subject.NAMES)
    for name, now in current.items():
        old = baseline[name]
        # All eight already had the typed `session` port. The field-level
        # correction moves its source/bound contract, not the component shape.
        assert now["component_address"] == old["component_address"]
        if name in AFFECTED:
            assert now["source_contract_address"] != old["source_contract_address"]
            assert now["binding_source_contract_address"] != old["binding_source_contract_address"]
        else:
            assert now["source_contract_address"] == old["source_contract_address"]
            assert now["binding_source_contract_address"] == old["binding_source_contract_address"]
        # The F01 repair and later role handling evolve executable closures;
        # historical identities must not silently alias current registrations.
        assert now["binding_implementation_address"] != old["binding_implementation_address"]
        assert now["implementation_address"] != old["implementation_address"]
        fresh.assert_current_registry_identity(subject, subject.component_key(name))


def test_refusals_legacy_and_accepted_source_facts_keep_current_registry_authority():
    before = original_specs()
    for name in subject.REFUSED_NAMES:
        assert plain(subject.SPECS[name]) == before[name]
        expected = {
            "schema": "analytical-unavailable-component/1",
            "component_id": "analytical." + name.lower(),
            "semantic_version": 2,
            "decision": "REFUSE",
            "code": before[name]["refusal"]["code"],
            "release_owner": before[name]["refusal"]["release_owner"],
            "future_requirement": before[name]["refusal"]["future_requirement"],
            "source_addresses": before[name]["source_addresses"],
            "executable": False,
        }
        assert plain(subject.REFUSALS[name]) == plain(expected)
    fresh.test_legacy_125_and_accepted_84_source_facts_and_current_registrations_are_exact()
