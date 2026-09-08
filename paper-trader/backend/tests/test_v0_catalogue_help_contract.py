"""Fail-closed semantic and source help for every published V0 node."""
from __future__ import annotations

import copy
import json
from collections import Counter
from types import SimpleNamespace

import pytest

from app.editor import v2_catalogue, v2_catalogue_help
from app.ir.formats.v2 import content_address_for, graph_address_for
from app.ir.hashing import content_address
from app.ir.library import ANALYTICAL_V2_DISPOSITIONS, REGISTRY


def _rows(document=v2_catalogue.CATALOGUE_DOCUMENT):
    return [row for group in document["groups"] for row in group["components"]]


def _plain(value):
    if isinstance(value, dict) or hasattr(value, "items"):
        return {key: _plain(child) for key, child in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(child) for child in value]
    return value


def _records():
    return [_plain(row["help"]) for row in _rows()]


def _identity_registry():
    type_record = {
        "type_id": "number", "type_version": 1, "shapes": ["scalar"],
        "runtime_representation": "float",
    }
    input_port = {
        "port_id": "in", "direction": "input", "semantic_flow": "value",
        "semantic_role": "input", "type_ref": {"type_id": "number", "type_version": 1},
        "shape": "scalar", "connections": {
            "cardinality": "optional", "min": 0, "max": 1, "assembly": "single",
        },
    }
    output = {
        "port_id": "out", "direction": "output", "semantic_flow": "value",
        "semantic_role": "result", "type_ref": {"type_id": "number", "type_version": 1},
        "shape": "scalar",
    }
    component = {
        "component_id": "constant", "component_version": 1,
        "domain_family": "transform", "structural_role": "source",
        "ports": [input_port, output], "parameters": {},
    }
    return SimpleNamespace(
        v2_types={("number", 1): type_record},
        v2_components={("constant", 1): component},
    )


def _identity_document():
    return {
        "format_version": 2, "strategy_id": "help-identity-fixture", "strategy_version": 1,
        "metadata": {
            "metadata_version": 1, "name": "Help identity fixture", "description": "",
            "tags": [],
        },
        "graph_inputs": [],
        "graph_outputs": [{
            "port_id": "result", "direction": "output", "semantic_flow": "value",
            "semantic_role": "result", "type_ref": {"type_id": "number", "type_version": 1},
            "shape": "scalar",
        }],
        "nodes": [{
            "node_id": "source", "component": {
                "component_id": "constant", "component_version": 1,
            }, "parameters": {},
        }],
        "edges": [],
    }


def test_exact_help_set_categories_sources_customisation_and_exclusions():
    document = v2_catalogue.CATALOGUE_DOCUMENT
    rows = _rows(document)
    records = [row["help"] for row in rows]
    assert len(rows) == len(records) == 270
    assert {(row["component_id"], row["component_version"]) for row in rows} == {
        (record["component_id"], record["component_version"]) for record in records
    }
    assert Counter(record["semantic_kind"] for record in records) == {
        "MATHEMATICAL_FORMULA": 181, "FIELD_SELECTION": 29, "FIELD_SPLITTER": 1,
        "LOGICAL_OPERATION": 47, "INTENT_BEHAVIOR": 12,
    }
    assert Counter(bool(record["customisation"]["parameters"]) for record in records) == {
        True: 170, False: 100,
    }
    for row, record in zip(rows, records, strict=True):
        assert record["implementation_binding"] == row["implementation_address"]
        assert record["description"].strip() and record["semantic_text"].strip()
        assert record["sources"] and all(source["claim_scope"].strip() for source in record["sources"])
        assert record["customisation"]["built_in_code_immutable"] is True
        assert record["customisation"]["immutable_boundary"] == v2_catalogue_help.IMMUTABLE_BOUNDARY
        assert record["availability"]["status"] == row["availability"]["status"]
        assert "sha256:" not in json.dumps(_plain(record["sources"])).lower()
    assert len(document["exclusions"]) == 78
    assert all("help" not in exclusion and exclusion["reason_code"] for exclusion in document["exclusions"])


def test_all_108_analytical_texts_are_the_exact_existing_v2_formula_fields():
    analytical = [row for row in _rows() if row["component_id"].startswith("analytical.")]
    assert len(analytical) == 108
    for row in analytical:
        assert row["help"]["semantic_text"] == v2_catalogue_help._analytical_spec(
            row["component_id"]
        )["formula"]


def test_non_analytical_semantics_are_exhaustive_named_evaluator_records():
    from app.ir.first_party import derivatives, logic_state, monitoring_intent_v2

    assert set(v2_catalogue_help._TYPE_3_SEMANTICS) == set(derivatives.TYPE_3_NAMES)
    assert set(v2_catalogue_help._TYPE_5_SEMANTICS) == set(logic_state.TYPE_5_NAMES)
    assert set(v2_catalogue_help._TYPE_1_SEMANTICS) == set(monitoring_intent_v2.NAMES)
    assert v2_catalogue_help._TYPE_3_SEMANTICS["BASIS"] == "Return future - spot."
    assert v2_catalogue_help._TYPE_5_SEMANTICS["DIVIDE"].endswith(
        "division by zero is mathematically undefined."
    )
    assert "creates no order or execution authority" in v2_catalogue_help._TYPE_1_SEMANTICS["BUY"]


def test_ohlcv_is_exact_completed_candle_five_output_splitter_and_not_indicator():
    row = next(row for row in _rows() if row["component_id"] == "analytical.ohlcv")
    help_record = row["help"]
    assert help_record["semantic_kind"] == "FIELD_SPLITTER"
    assert help_record["description"] == (
        "Splits each fully completed candle into five named outputs: open, high, low, close "
        "and volume. It does not calculate an indicator."
    )
    assert help_record["semantic_text"] == (
        "Return separately named canonical completed-bar open, high, low, close and volume "
        "series. No DataFrame hidden under a scalar value port."
    )


def test_missing_duplicate_version_and_implementation_binding_mutations_fail_closed():
    rows = _rows()
    records = _records()
    with pytest.raises(v2_catalogue_help.CatalogueHelpError, match="identity sets differ"):
        v2_catalogue_help.validate_help_projection(rows, records[:-1])
    with pytest.raises(v2_catalogue_help.CatalogueHelpError, match="duplicated"):
        v2_catalogue_help.validate_help_projection(rows, [*records[:-1], records[0]])

    version = copy.deepcopy(records)
    version[0]["component_version"] += 1
    with pytest.raises(v2_catalogue_help.CatalogueHelpError, match="identity sets differ"):
        v2_catalogue_help.validate_help_projection(rows, version)

    binding = copy.deepcopy(records)
    binding[0]["implementation_binding"] = content_address({"different": "implementation"})
    with pytest.raises(v2_catalogue_help.CatalogueHelpError, match="binding"):
        v2_catalogue_help.validate_help_projection(rows, binding)


@pytest.mark.parametrize("path", ["description", "semantic_text"])
def test_blank_help_text_mutations_fail_closed(path):
    records = _records()
    records[0][path] = "  "
    with pytest.raises(v2_catalogue_help.CatalogueHelpError, match="blank or invalid"):
        v2_catalogue_help.validate_help_projection(_rows(), records)


def test_blank_source_and_raw_hash_source_mutations_fail_closed():
    records = _records()
    records[0]["sources"][0]["claim_scope"] = ""
    with pytest.raises(v2_catalogue_help.CatalogueHelpError, match="blank or invalid"):
        v2_catalogue_help.validate_help_projection(_rows(), records)

    records = _records()
    records[0]["sources"][0]["title"] = "sha256:" + "a" * 64
    with pytest.raises(v2_catalogue_help.CatalogueHelpError, match="raw content address"):
        v2_catalogue_help.validate_help_projection(_rows(), records)


def test_ohlcv_forgery_mutations_fail_closed_and_original_restores_exactly():
    records = _records()
    ohlcv = next(record for record in records if record["component_id"] == "analytical.ohlcv")
    ohlcv["description"] = "Returns one close value from any candle."
    with pytest.raises(v2_catalogue_help.CatalogueHelpError, match="OHLCV help semantics"):
        v2_catalogue_help.validate_help_projection(_rows(), records)
    assert v2_catalogue.catalogue_bytes(REGISTRY, ANALYTICAL_V2_DISPOSITIONS) == v2_catalogue.CATALOGUE_BYTES


def test_help_changes_only_catalogue_identity_and_etag_not_executable_or_research_identity():
    original = json.loads(v2_catalogue.CATALOGUE_BYTES)
    records = _records()
    records[0]["description"] += " Reviewed help copy."
    changed_bytes = v2_catalogue.catalogue_bytes(
        REGISTRY, ANALYTICAL_V2_DISPOSITIONS, help_records=records,
    )
    changed = json.loads(changed_bytes)
    assert changed_bytes != v2_catalogue.CATALOGUE_BYTES
    assert changed["catalogue_identity"] != original["catalogue_identity"]
    assert f'"{changed["catalogue_identity"]}"' != v2_catalogue.CATALOGUE_ETAG
    assert changed["registry_identity"] == original["registry_identity"] == REGISTRY.registry_snapshot_address

    stable_fields = (
        "component_address", "node_contract_address", "implementation_address",
        "contract_binding_address", "data_requirement_address",
    )
    original_rows = _rows(original)
    changed_rows = _rows(changed)
    assert [tuple(row[field] for field in stable_fields) for row in changed_rows] == [
        tuple(row[field] for field in stable_fields) for row in original_rows
    ]

    registry = _identity_registry()
    document = _identity_document()
    graph_identity = graph_address_for(document, registry)
    executable_identity = content_address({"graph_address": graph_identity, "mode": "RESEARCH"})
    research_identity = content_address({
        "graph_address": graph_identity,
        "executable_identity": executable_identity,
        "dataset_manifest_address": content_address({"dataset": "fixture"}),
        "outputs": {"net_return": 0.01},
    })
    assert graph_identity == graph_address_for(document, registry)
    assert content_address_for(document, registry) == content_address_for(document, registry)
    assert executable_identity == content_address({"graph_address": graph_identity, "mode": "RESEARCH"})
    assert research_identity == content_address({
        "graph_address": graph_identity,
        "executable_identity": executable_identity,
        "dataset_manifest_address": content_address({"dataset": "fixture"}),
        "outputs": {"net_return": 0.01},
    })


def test_original_help_covers_exact_identities_and_parameter_descriptors():
    from app.ir import original_strategy_presets
    from app.ir.first_party import original_strategy_primitives
    expected = set(original_strategy_presets.V2_COMPONENTS) | set(original_strategy_primitives.V2_COMPONENTS)
    rows = [row for row in _rows() if (row['component_id'], row['component_version']) in expected]
    assert len(rows) == 26
    for row in rows:
        parameters = row['help']['customisation']['parameters']
        assert {record['name']: {key: _plain(value) for key, value in record.items() if key != 'name'}
                for record in parameters} == _plain(row['descriptor']['parameters'])
        assert row['help']['sources'][0]['authors_or_organization'] == 'Strategy OS'
    v4 = next(row for row in rows if row['component_id'] == 'strategy.expanding_z_v4_pine')
    assert 'consumer behavior' in v4['help']['semantic_text']


@pytest.mark.parametrize('mutation', ('implementation', 'component', 'registry', 'missing'))
def test_compound_help_binding_forgery_refuses(mutation):
    row = next(row for row in _rows() if row['component_kind'] == 'COMPOUND')
    help_record = _plain(row['help'])
    if mutation == 'implementation':
        help_record['implementation_binding'] = row['component_address']
    elif mutation == 'component':
        help_record['composition_binding']['component_address'] = content_address({'wrong': 'component'})
    elif mutation == 'registry':
        help_record['composition_binding']['registry_identity'] = content_address({'wrong': 'registry'})
    else:
        del help_record['composition_binding']
    with pytest.raises(v2_catalogue_help.CatalogueHelpError):
        v2_catalogue_help.validate_help_record(row, help_record)


@pytest.mark.parametrize("mutation", ("implementation", "missing", "extra", "component", "address"))
def test_compound_row_binding_refuses_invalid_identity(mutation):
    row = _plain(next(row for row in _rows() if row["component_kind"] == "COMPOUND"))
    if mutation == "implementation":
        row["implementation_address"] = row["component_address"]
    elif mutation == "missing":
        row["composition_binding"] = None
    elif mutation == "extra":
        row["composition_binding"]["extra"] = True
    elif mutation == "component":
        row["composition_binding"]["component_address"] = content_address({"wrong": "component"})
    else:
        row["composition_binding"]["registry_identity"] = "not-an-address"
    with pytest.raises(v2_catalogue_help.CatalogueHelpError, match="composition binding"):
        v2_catalogue_help.validate_help_record(row, row["help"])


@pytest.mark.parametrize("mutation", ("shape", "mutable", "boundary", "parameters", "availability"))
def test_compound_help_refuses_changed_customisation_contract(mutation):
    row = next(row for row in _rows() if row["component_kind"] == "COMPOUND")
    record = _plain(row["help"])
    if mutation == "shape":
        record["customisation"] = None
    elif mutation == "mutable":
        record["customisation"]["built_in_code_immutable"] = False
    elif mutation == "boundary":
        record["customisation"]["immutable_boundary"] = "Editable built-in code"
    elif mutation == "parameters":
        record["customisation"]["parameters"] = []
    else:
        record["availability"] = {}
    with pytest.raises(v2_catalogue_help.CatalogueHelpError):
        v2_catalogue_help.validate_help_record(row, record)


def test_full_session_gap_help_preserves_explicit_input_and_execution_limits():
    row = next(row for row in _rows() if row["component_id"] == "structure.historical_daily_gaps")
    assert row["component_version"] == 2 and row["visible_family"] == "TYPE_3"
    assert row["node_contract"]["required_resolution"]["alignment"] == "SESSION"
    assert row["availability"]["backtest_eligible"] is False
    text = row["help"]["semantic_text"]
    assert "Exact canonical session-close inputs are required" in text
    assert "4096-zone bound" in text
    assert "do not prove order fills" in text
    assert "UTC epoch seconds" in text
