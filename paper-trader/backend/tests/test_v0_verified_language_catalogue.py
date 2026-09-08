"""V0's authenticated, registry-derived verified-language catalogue."""
from __future__ import annotations

from collections import Counter
import json
from types import SimpleNamespace
import tracemalloc

import pytest
from fastapi.testclient import TestClient

from app.ir.hashing import content_address
from app.ir.first_party import derivatives, execution_intent, logic_state, monitoring_intent_v2, original_strategy_primitives, historical_daily_gaps
from app.ir import original_strategy_presets
from app.ir.library import (
    ANALYTICAL_V2_DISPOSITIONS,
    CONTRIBUTORS,
    REGISTRY,
    V2_CONTRIBUTORS,
    compose,
    compose_v2,
)
from app.ir.registry import PlatformRegistry
from app.ir.schema import is_content_address


GROUPS = (
    ("TYPE_4", "Price, Instrument & Market Data"),
    ("TYPE_2", "Indicators & Derived Features"),
    ("TYPE_3", "Market Structure, Derivatives & Cross-Instrument"),
    ("TYPE_5", "Logic, Math & State"),
    ("TYPE_1", "Execution & Position"),
)
EXPECTED_ANALYTICAL_ACCEPTED = frozenset({
    "ACCUMULATION_DISTRIBUTION", "ADX", "ALPHA", "ANCHORED_VWAP", "ATR",
    "BARS_SINCE_SESSION_OPEN", "BETA", "BETA_ADJUSTED_SPREAD", "BOLLINGER_BANDS",
    "BOLLINGER_BANDWIDTH", "BOLLINGER_PERCENT_B", "CCI", "CHAIKIN_MONEY_FLOW",
    "CHAIKIN_OSCILLATOR", "CLOSE", "CORRELATION", "COVARIANCE", "CROSS_ABOVE",
    "CROSS_BELOW", "CUMULATIVE_RETURN", "DISTANCE_FROM_SESSION_HIGH_LOW",
    "DONCHIAN_CHANNELS", "EMA", "EWMA_VOLATILITY", "FALLING", "GAP", "GAP_DOWN",
    "GAP_UP", "HIGH", "HL2", "HLC3", "INSIDE_BAR", "KAMA", "KELTNER_CHANNELS",
    "LINEAR_REGRESSION_INTERCEPT", "LINEAR_REGRESSION_SLOPE", "LOG_RETURN", "LOW",
    "MACD", "MAD", "MA_SLOPE", "MFI", "MIDPOINT", "MINUS_DI", "MOMENTUM", "NATR",
    "OBV", "OHLC4", "OHLCV", "OPEN", "OPENING_RANGE", "OUTSIDE_BAR", "PARABOLIC_SAR",
    "PARKINSON", "PERCENTILE", "PERCENTILE_RANK", "PERCENT_RETURN", "PLUS_DI",
    "POINT_CHANGE", "PPO", "PREVIOUS_SESSION_FIELDS", "PREVIOUS_SESSION_OHLC",
    "PRICE_MA_DISTANCE", "PRICE_VOLUME_TREND", "RATIO", "REALIZED_VOLATILITY",
    "RELATIVE_VOLUME", "RESIDUAL", "RISING", "RMA_WILDER", "ROC", "ROGERS_SATCHELL",
    "ROLLING_HEDGE_RATIO", "ROLLING_HIGH", "ROLLING_LOW", "ROLLING_MAX", "ROLLING_MEAN",
    "ROLLING_MEDIAN", "ROLLING_MIN", "ROLLING_RANK", "ROLLING_REGRESSION",
    "ROLLING_RETURN", "ROLLING_STDDEV", "ROLLING_VARIANCE", "ROLLING_VOLUME_PERCENTILE",
    "RSI", "R_SQUARED", "SESSION_HIGH", "SESSION_LOW", "SESSION_OPEN",
    "SESSION_OPEN_HIGH_LOW", "SMA", "STOCHASTIC", "STOCH_RSI", "TIME_TO_SESSION_CLOSE",
    "TREND_PERSISTENCE", "TRUE_RANGE", "TYPICAL_PRICE", "VOLATILITY_PERCENTILE",
    "VOLATILITY_RANK", "VOLUME_ZSCORE", "VWAP", "VWMA", "WEIGHTED_CLOSE", "WILLIAMS_R",
    "WMA", "YANG_ZHANG", "ZSCORE",
})
EXPECTED_ANALYTICAL_UNAVAILABLE = {
    "ASK": "QUOTE_BINDING_UNAVAILABLE",
    "BID": "QUOTE_BINDING_UNAVAILABLE",
    "BOOK_DEPTH": "BOOK_BINDING_UNAVAILABLE",
    "DTE": "EXPIRY_BINDING_UNAVAILABLE",
    "EXPIRY_CALENDAR": "EXPIRY_BINDING_UNAVAILABLE",
    "GARMAN_KLASS": "PRIMARY_GK_VARIANT_UNVERIFIED",
    "ICHIMOKU_COMPONENTS": "NUMERICAL_CONVENTION_UNVERIFIED",
    "INSTRUMENT_METADATA": "METADATA_BINDING_UNAVAILABLE",
    "LTP": "TRADE_BINDING_UNAVAILABLE",
    "MARKET_CLOCK": "CLOCK_BINDING_UNAVAILABLE",
    "MID": "QUOTE_BINDING_UNAVAILABLE",
    "OPEN_INTEREST": "OI_BINDING_UNAVAILABLE",
    "RESAMPLING": "RESAMPLING_BINDING_UNAVAILABLE",
    "SESSION_CALENDAR": "CALENDAR_BINDING_UNAVAILABLE",
    "SPREAD": "QUOTE_BINDING_UNAVAILABLE",
    "SUPERTREND": "NUMERICAL_CONVENTION_UNVERIFIED",
    "TIMEFRAME": "TIMEFRAME_BINDING_UNAVAILABLE",
}


def _catalogue_module():
    from app.editor import v2_catalogue

    return v2_catalogue


def test_condition_projection_is_not_monitoring_type1_authority():
    from app.ir.first_party import monitoring_intent_v2
    catalogue = _catalogue_module()
    key = monitoring_intent_v2.FINAL_PREFIX_CONDITION
    assert key in REGISTRY.v2_components
    assert REGISTRY.node_contracts[key]["visible_family"] == "TYPE_2"
    assert key not in catalogue._MONITORING_TYPE_1_ALLOWLIST
    assert set(catalogue._MONITORING_TYPE_1_ALLOWLIST) == {
        monitoring_intent_v2.component_key(name) for name in monitoring_intent_v2.NAMES}
    assert len(catalogue._MONITORING_TYPE_1_ALLOWLIST) == 12


def _rows(document):
    return tuple(component for group in document["groups"] for component in group["components"])


def _plain(value):
    if hasattr(value, "items"):
        return {key: _plain(child) for key, child in value.items()}
    if isinstance(value, (tuple, list, frozenset)):
        return [_plain(child) for child in value]
    return value


def _matrix_fixture():
    accepted = {
        (f"analytical.{name.lower()}", 2)
        for name in EXPECTED_ANALYTICAL_ACCEPTED
    }
    refused = {
        (f"analytical.{name.lower()}", 2)
        for name in EXPECTED_ANALYTICAL_UNAVAILABLE
    }
    return accepted, refused


def _registry_with(**updates):
    fields = {
        "v2_components": REGISTRY.v2_components,
        "v2_implementation_identities": REGISTRY.v2_implementation_identities,
        "data_requirement_declarations": REGISTRY.data_requirement_declarations,
        "data_requirement_declaration_addresses": REGISTRY.data_requirement_declaration_addresses,
        "node_contracts": REGISTRY.node_contracts,
        "node_contract_addresses": REGISTRY.node_contract_addresses,
        "contract_bindings": REGISTRY.contract_bindings,
        "registry_snapshot_address": REGISTRY.registry_snapshot_address,
        "registry_snapshot_payload": REGISTRY.registry_snapshot_payload,
    }
    fields.update(updates)
    return SimpleNamespace(**fields)


def _real_registry_with(**updates):
    fields = {
        "components": REGISTRY.library.components,
        "bodies": REGISTRY.library.bodies,
        "registrations": REGISTRY.registrations,
        "v2_types": REGISTRY.v2_types,
        "v2_components": REGISTRY.v2_components,
        "v2_implementations": REGISTRY.v2_implementation_registrations,
        "data_requirement_declarations": REGISTRY.data_requirement_declarations,
        "node_contracts": REGISTRY.node_contracts,
        "contract_bindings": REGISTRY.contract_bindings,
    }
    fields.update(updates)
    return PlatformRegistry(**fields)


def test_red_fixture_closes_the_exact_accepted_and_refused_analytical_universe():
    accepted, refused = _matrix_fixture()
    assert len(accepted) == 108
    assert len(refused) == 17
    assert accepted.isdisjoint(refused)
    assert Counter(row["status"] for row in ANALYTICAL_V2_DISPOSITIONS.values()) == {
        "ACCEPTED_V2": 108,
        "UNAVAILABLE": 17,
    }
    assert {
        name for name, row in ANALYTICAL_V2_DISPOSITIONS.items()
        if row["status"] == "ACCEPTED_V2"
    } == EXPECTED_ANALYTICAL_ACCEPTED
    assert {
        name: row["reason_code"] for name, row in ANALYTICAL_V2_DISPOSITIONS.items()
        if row["status"] == "UNAVAILABLE"
    } == EXPECTED_ANALYTICAL_UNAVAILABLE


def test_projection_has_one_frozen_five_family_order_and_exact_membership():
    subject = _catalogue_module()
    document = subject.CATALOGUE_DOCUMENT
    assert tuple((group["visible_family"], group["display_name"]) for group in document["groups"]) == GROUPS
    assert tuple(group["order"] for group in document["groups"]) == (1, 2, 3, 4, 5)
    assert document["counts"] == {
        "groups": 5,
        "components": 270,
        "original_primitives": 24, "original_compounds": 2,
        "analytical_v2": 108,
        "type_3": 64,
        "type_5": 60,
        "monitoring_type_1_v2": 12,
        "analytical_unavailable": 17,
        "legacy_type_1_excluded": 61,
    }
    rows = _rows(document)
    accepted, _ = _matrix_fixture()
    assert {(row["component_id"], row["component_version"]) for row in rows if row["component_id"].startswith("analytical.")} == accepted
    assert {(row["component_id"], row["component_version"]) for row in rows if row["visible_family"] == "TYPE_3"} == set(derivatives.V2_COMPONENTS) | set(historical_daily_gaps.V2_COMPONENTS)
    assert {(row["component_id"], row["component_version"]) for row in rows if row["visible_family"] == "TYPE_5"} == set(logic_state.V2_COMPONENTS)
    assert {(row["component_id"], row["component_version"]) for row in rows if row["visible_family"] == "TYPE_1"} == set(monitoring_intent_v2.V2_COMPONENTS)


def test_every_admitted_row_is_exactly_registry_derived_and_content_addressed():
    subject = _catalogue_module()
    for row in _rows(subject.CATALOGUE_DOCUMENT):
        key = (row["component_id"], row["component_version"])
        descriptor = REGISTRY.v2_components[key]
        if row["component_kind"] == "COMPOUND":
            continue  # Compound identity and absence of leaf facts are checked below.
        contract = REGISTRY.node_contracts[key]
        assert row["descriptor"] == descriptor
        assert row["component_address"] == content_address(descriptor)
        assert row["node_contract_address"] == REGISTRY.node_contract_addresses[key]
        assert row["implementation_address"] == REGISTRY.v2_implementation_identities[key]
        assert row["data_requirement"] == REGISTRY.data_requirement_declarations[key]
        assert row["data_requirement_address"] == REGISTRY.data_requirement_declaration_addresses[key]
        assert row["visible_family"] == contract["visible_family"]
        assert row["mode_eligibility"] == contract["mode_eligibility"]
        assert row["provider_requirements"] == contract["provider_requirements"]
        assert row["resource_profile"] == contract["resource_profile"]
        for address_name in (
            "component_address", "node_contract_address", "implementation_address",
            "data_requirement_address",
        ):
            assert is_content_address(row[address_name])


def test_approved_contributors_preserve_all_prior_identities():
    prior_keys = set()
    for contributor in V2_CONTRIBUTORS:
        if contributor in (monitoring_intent_v2, original_strategy_primitives, original_strategy_presets, historical_daily_gaps):
            continue
        prior_keys.update(contributor.V2_COMPONENTS)
        for key, descriptor in contributor.V2_COMPONENTS.items():
            assert content_address(_plain(REGISTRY.v2_components[key])) == content_address(
                _plain(descriptor)
            )
        for key, implementation in contributor.V2_IMPLEMENTATIONS.items():
            assert (
                REGISTRY.v2_implementation_identities[key]
                == implementation.implementation_address
            )
        for key, declaration in contributor.DATA_REQUIREMENTS.items():
            assert content_address(_plain(REGISTRY.data_requirement_declarations[key])) == content_address(
                _plain(declaration)
            )
        for key, contract in contributor.NODE_CONTRACTS.items():
            assert content_address(_plain(REGISTRY.node_contracts[key])) == content_address(
                _plain(contract)
            )
    assert len(prior_keys) == 417
    additions = set(monitoring_intent_v2.V2_COMPONENTS) | set(original_strategy_primitives.V2_COMPONENTS) | set(original_strategy_presets.V2_COMPONENTS) | set(historical_daily_gaps.V2_COMPONENTS)
    assert set(REGISTRY.v2_components) - prior_keys == additions
    assert len(REGISTRY.v2_components) == 456


def test_exclusions_are_typed_identity_only_and_never_executable_descriptors():
    document = _catalogue_module().CATALOGUE_DOCUMENT
    exclusions = document["exclusions"]
    analytical = tuple(row for row in exclusions if row["kind"] == "ANALYTICAL_V2_UNAVAILABLE")
    legacy_type_1 = tuple(row for row in exclusions if row["kind"] == "LEGACY_TYPE_1_EXCLUDED")
    _, refused = _matrix_fixture()
    assert {(row["component_id"], row["component_version"]) for row in analytical} == refused
    assert {
        row["component_id"].removeprefix("analytical.").upper(): row["reason_code"]
        for row in analytical
    } == EXPECTED_ANALYTICAL_UNAVAILABLE
    assert {(row["component_id"], row["component_version"]) for row in legacy_type_1} == set(execution_intent.V2_COMPONENTS)
    assert len(analytical) == 17 and len(legacy_type_1) == 61
    assert all(row["executable"] is False and "descriptor" not in row for row in exclusions)
    assert all(row["reason_code"] for row in exclusions)


def test_type_1_publication_is_monitoring_only_and_has_no_authority_surface():
    document = _catalogue_module().CATALOGUE_DOCUMENT
    rows = tuple(row for row in _rows(document) if row["visible_family"] == "TYPE_1")
    forbidden = {
        "account", "broker", "capital", "deployment", "execution", "fill", "live",
        "money", "order", "position", "quantity", "reservation", "route",
    }
    assert len(rows) == 12
    for row in rows:
        assert row["component_version"] == 2
        assert row["mode_eligibility"] == {"research": True, "paper": False, "live": False}
        assert row["availability"]["authority"] == "MONITORING_ONLY"
        assert not forbidden.intersection(row["descriptor"])
    assert document["nonauthority"]["execution_authority"] is False
    assert document["nonauthority"]["provider_conformance"] is False
    assert document["nonauthority"]["backtest_eligibility"] is False


def test_capability_and_data_nodes_are_conditionally_described_without_support_claims():
    rows = _rows(_catalogue_module().CATALOGUE_DOCUMENT)
    conditional = tuple(row for row in rows if row["availability"]["status"] == "CONDITIONAL")
    assert conditional
    assert any(row["visible_family"] == "TYPE_3" for row in conditional)
    for row in conditional:
        assert row["availability"]["provider_support_verified"] is False
        assert row["availability"]["data_rights_verified"] is False
        assert row["availability"]["backtest_eligible"] is False


def test_projection_is_deeply_immutable_and_canonical_bytes_match_identity():
    subject = _catalogue_module()
    with pytest.raises(TypeError):
        subject.CATALOGUE_DOCUMENT["schema"] = "mutated"
    with pytest.raises(TypeError):
        subject.CATALOGUE_DOCUMENT["groups"][0]["components"][0]["descriptor"]["component_id"] = "mutated"
    parsed = json.loads(subject.CATALOGUE_BYTES)
    identity = parsed.pop("catalogue_identity")
    assert identity == content_address(parsed)
    assert identity == subject.CATALOGUE_IDENTITY
    assert parsed["registry_identity"] == REGISTRY.registry_snapshot_address
    assert len(subject.CATALOGUE_BYTES) <= subject.MAX_CATALOGUE_BYTES


def test_100000_projected_resource_reads_are_bounded_and_complete():
    rows = [row for row in _rows(_catalogue_module().CATALOGUE_DOCUMENT) if row["component_kind"] == "LEAF"]
    required = {
        "compute_microseconds_per_event", "memory_bytes_upper_bound",
        "history_bytes_upper_bound", "state_bytes_upper_bound",
        "storage_bytes_per_day_upper_bound", "subscription_count_upper_bound",
        "fanout_upper_bound",
    }
    checksum = 0
    tracemalloc.start()
    for index in range(100_000):
        profile = rows[index % len(rows)]["resource_profile"]
        assert set(profile) == required
        assert all(type(profile[field]) is int and profile[field] >= 0 for field in required)
        checksum += profile["compute_microseconds_per_event"]
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert checksum > 0
    assert peak <= 1_048_576


def test_reordered_contributors_and_registry_mappings_do_not_change_response_bytes():
    subject = _catalogue_module()
    reordered = compose_v2(compose(tuple(reversed(CONTRIBUTORS))), tuple(reversed(V2_CONTRIBUTORS)))
    assert reordered.registry_snapshot_address == REGISTRY.registry_snapshot_address
    assert subject.catalogue_bytes(reordered, ANALYTICAL_V2_DISPOSITIONS) == subject.CATALOGUE_BYTES


def test_projection_refuses_omission_refusal_and_authority_mutations():
    subject = _catalogue_module()
    accepted_key = next(
        key for key in REGISTRY.v2_components
        if key[1] == 2 and key[0].startswith("analytical.")
    )
    missing_components = dict(REGISTRY.v2_components)
    missing_components.pop(accepted_key)
    with pytest.raises(subject.CatalogueProjectionError):
        subject.catalogue_bytes(_registry_with(v2_components=missing_components), ANALYTICAL_V2_DISPOSITIONS)

    refused_name = next(name for name, row in ANALYTICAL_V2_DISPOSITIONS.items() if row["status"] == "UNAVAILABLE")
    dispositions = {name: dict(row) for name, row in ANALYTICAL_V2_DISPOSITIONS.items()}
    dispositions[refused_name]["status"] = "ACCEPTED_V2"
    with pytest.raises(subject.CatalogueProjectionError):
        subject.catalogue_bytes(REGISTRY, dispositions)

    monitoring_key = next(iter(monitoring_intent_v2.V2_COMPONENTS))
    contracts = dict(REGISTRY.node_contracts)
    mutated = _plain(contracts[monitoring_key])
    mutated["mode_eligibility"] = {"research": True, "paper": True, "live": True}
    contracts[monitoring_key] = mutated
    with pytest.raises(subject.CatalogueProjectionError):
        subject.catalogue_bytes(_registry_with(node_contracts=contracts), ANALYTICAL_V2_DISPOSITIONS)


def test_real_registry_nested_authority_and_private_sentinels_fail_closed():
    subject = _catalogue_module()
    monitoring_key = ("intent.atr_stop", 2)
    components = dict(REGISTRY.v2_components)
    descriptor = _plain(components[monitoring_key])
    descriptor["ports"][0]["semantic_role"] = (
        "broker_account_order_route tenant_id strategy_id pnl_value"
    )
    components[monitoring_key] = descriptor
    mutated = _real_registry_with(v2_components=components)
    with pytest.raises(
        subject.CatalogueProjectionError,
        match="accepted monitoring component",
    ):
        subject.catalogue_bytes(mutated, ANALYTICAL_V2_DISPOSITIONS)

    type_3_key = next(
        key for key, contract in REGISTRY.node_contracts.items()
        if contract["visible_family"] == "TYPE_3"
    )
    components = dict(REGISTRY.v2_components)
    descriptor = _plain(components[type_3_key])
    descriptor["ports"][0]["semantic_role"] = (
        "tenant_id strategy_id pnl_value research_result graph_id"
    )
    components[type_3_key] = descriptor
    mutated = _real_registry_with(v2_components=components)
    with pytest.raises(subject.CatalogueProjectionError, match="private metadata value"):
        subject.catalogue_bytes(mutated, ANALYTICAL_V2_DISPOSITIONS)

    with pytest.raises(subject.CatalogueProjectionError, match="authority metadata value"):
        subject._validate_public_surface(
            {"nested": [{"semantic_role": "broker_account_order_route"}]},
            visible_family="TYPE_1",
        )


def test_routes_are_authenticated_scope_classified_mirrors_with_immutable_etag(monkeypatch):
    from app.api.principal import action_for_request
    from app.core.config import get_settings
    from app.db.session import init_db
    from app.main import app

    settings = get_settings()
    monkeypatch.setattr(settings, "browser_auth_enabled", False)
    monkeypatch.setattr(settings, "api_token", "catalogue-secret")
    init_db(reset=True)
    client = TestClient(app)
    assert action_for_request("GET", "/api/ir/catalogue") == "read:project"
    assert client.get("/api/ir/catalogue").status_code == 401
    assert client.get("/api/v1/ir/catalogue").status_code == 401
    headers = {"Authorization": "Bearer catalogue-secret"}
    first = client.get("/api/ir/catalogue", headers=headers)
    mirror = client.get("/api/v1/ir/catalogue", headers=headers)
    assert first.status_code == mirror.status_code == 200
    assert first.content == mirror.content == _catalogue_module().CATALOGUE_BYTES
    assert first.headers["etag"] == mirror.headers["etag"] == _catalogue_module().CATALOGUE_ETAG
    assert first.headers["cache-control"] == "private, max-age=0, must-revalidate"
    assert client.get("/api/ir/catalogue?family=TYPE_1", headers=headers).status_code == 400
    cached = client.get("/api/ir/catalogue", headers={**headers, "If-None-Match": first.headers["etag"]})
    assert cached.status_code == 304 and cached.content == b""


def test_catalogue_contains_no_tenant_private_fact_names():
    document = json.loads(_catalogue_module().CATALOGUE_BYTES)

    def keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)

    assert not {
        "organization_id", "owner_id", "tenant_id", "strategy_id", "graph_id",
        "research_result", "pnl_value", "profit_value",
    }.intersection(keys(document))


def test_original_compounds_have_real_descriptor_and_registry_binding_without_leaf_facts():
    subject = _catalogue_module()
    rows = _rows(subject.CATALOGUE_DOCUMENT)
    original = { (row['component_id'], row['component_version']): row for row in rows
                 if row['component_id'].startswith(('strategy_math.', 'strategy.')) }
    assert set(original) == set(original_strategy_primitives.V2_COMPONENTS) | set(original_strategy_presets.V2_COMPONENTS)
    for key in original_strategy_presets.V2_COMPONENTS:
        row = original[key]
        assert row['component_kind'] == 'COMPOUND'
        assert row['descriptor'] == REGISTRY.v2_components[key]
        assert row['component_address'] == content_address(_plain(row['descriptor']))
        assert row['composition_binding'] == {
            'component_address': row['component_address'],
            'registry_identity': REGISTRY.registry_snapshot_address,
        }
        for field in ('implementation_address', 'node_contract', 'node_contract_address',
                      'data_requirement', 'data_requirement_address', 'resource_profile',
                      'mode_eligibility', 'provider_requirements', 'contract_binding', 'contract_binding_address'):
            assert row[field] is None
        assert row['help']['implementation_binding'] is None
        assert row['help']['composition_binding'] == row['composition_binding']
        assert row['availability']['authority'] == 'NONE'
        assert row['availability']['status'] == 'CONDITIONAL'
        assert row['help']['customisation']['parameters']
    leaf = original[('strategy_math.ema_first_close', 1)]
    assert leaf['component_kind'] == 'LEAF'
    assert leaf['implementation_address'] == REGISTRY.v2_implementation_identities[('strategy_math.ema_first_close', 1)]
    assert leaf['composition_binding'] is None


@pytest.mark.parametrize('mutation', ('implementation', 'contract', 'descriptor', 'snapshot'))
def test_compound_projection_refuses_fabricated_leaf_or_stale_snapshot(mutation):
    subject = _catalogue_module()
    key = ('strategy.trend_impulse_v3', 1)
    updates = {}
    if mutation == 'implementation':
        updates['v2_implementation_identities'] = {**REGISTRY.v2_implementation_identities, key: content_address({'fake': 'implementation'})}
    elif mutation == 'contract':
        updates['node_contracts'] = {**REGISTRY.node_contracts, key: {}}
    elif mutation == 'descriptor':
        descriptor = _plain(REGISTRY.v2_components[key])
        descriptor['compound']['body']['nodes'][0]['node_id'] = 'different'
        updates['v2_components'] = {**REGISTRY.v2_components, key: descriptor}
    else:
        updates['registry_snapshot_address'] = content_address({'different': 'registry'})
    with pytest.raises(subject.CatalogueProjectionError):
        subject.catalogue_bytes(_registry_with(**updates), ANALYTICAL_V2_DISPOSITIONS)
