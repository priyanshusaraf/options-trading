"""Pure Execution Product Policy contract and compatibility boundaries."""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import pytest

from app.execution import product_policy as product


NOW = dt.datetime(2026, 8, 25, 12, tzinfo=dt.timezone.utc)


def address(char: str) -> str:
    return "sha256:" + char * 64


def policy(family: str = "options") -> product.ExecutionProductPolicy:
    return product.ExecutionProductPolicy(
        policy_id=f"compat.{family}", version=1, product_family=family,
        execution_modes=("live", "paper"), selector_version="compatibility/1",
        allowed_order_types=("LIMIT", "MARKET"), max_fact_age_seconds=60)


def request(**changes) -> product.ProductResolutionRequest:
    values = dict(
        owner_id="owner-a", broker_account_id="account-a", book="paper",
        deployment_id=1, binding_instrument_key="NIFTY",
        strategy_key="trend_impulse_v3", strategy_version="v1",
        admission_address=address("a"), graph_address=None,
        attribution_state="NON_GRAPH", binding_authority="authoritative",
        execution_mode="paper", signal_instrument_key="NIFTY",
        direction="LONG", purpose="ENTRY", decision_at=NOW,
        market_snapshot_address=address("b"), capability_address=address("c"))
    values.update(changes)
    return product.ProductResolutionRequest(**values)


def candidate(family: str = "options", **changes) -> product.ProductCandidateFacts:
    defaults = {
        "options": dict(execution_instrument_key="NIFTY:2026-09-24:24000:CE",
                        tradingsymbol="NIFTY24SEP24000CE", exchange="NFO",
                        product_code="NRML", lot_size=75, quantity_step=75),
        "equity": dict(execution_instrument_key="NIFTY-EQ",
                       tradingsymbol="NIFTYBEES", exchange="NSE",
                       product_code="MIS", lot_size=1, quantity_step=1),
        "futures": dict(execution_instrument_key="NIFTY:2026-09-24:FUT",
                        tradingsymbol="NIFTY24SEPFUT", exchange="NFO",
                        product_code="NRML", lot_size=75, quantity_step=75),
    }[family]
    values = dict(
        signal_instrument_key="NIFTY", product_family=family,
        order_types=("LIMIT", "MARKET"), tick_size_minor=5,
        observed_at=NOW - dt.timedelta(seconds=10),
        source_address=address("d"), selection_evidence_address=address("e"),
        **defaults)
    values.update(changes)
    return product.ProductCandidateFacts(**values)


@pytest.mark.parametrize("family", ["options", "equity", "futures"])
def test_exact_compatibility_facts_resolve_without_lookup(family):
    resolved = product.resolve_product(policy(family), request(), candidate(family))
    assert resolved.product_family == family
    assert resolved.policy_address == policy(family).address
    assert resolved.request_address == request().address
    assert resolved.candidate_address == candidate(family).address
    assert resolved.address.startswith("sha256:") and len(resolved.address) == 71


def test_resolution_is_content_deterministic_and_separates_policy_request_candidate():
    first = product.resolve_product(policy(), request(), candidate())
    second = product.resolve_product(policy(), request(), candidate())
    assert first == second and first.address == second.address
    assert len({first.policy_address, first.request_address,
                first.candidate_address, first.address}) == 4


@pytest.mark.parametrize("change,code", [
    ({"binding_authority": "shadow"}, "AUTHORITY_NOT_GRANTED"),
    ({"execution_mode": "live"}, "BOOK_MODE_MISMATCH"),
    ({"binding_instrument_key": "BANKNIFTY"}, "BINDING_INSTRUMENT_MISMATCH"),
])
def test_request_refusals_are_typed(change, code):
    with pytest.raises(product.ProductPolicyRefused, match=code):
        product.resolve_product(policy(), request(**change), candidate())


def test_graph_attribution_cannot_be_self_asserted_by_a_non_graph_key():
    with pytest.raises(product.ProductPolicyRefused, match="GRAPH_ATTRIBUTION"):
        request(graph_address=address("f"), attribution_state="VERIFIED_GRAPH")


@pytest.mark.parametrize("candidate_change,code", [
    ({"signal_instrument_key": "BANKNIFTY"}, "SIGNAL_INSTRUMENT_MISMATCH"),
    ({"observed_at": NOW - dt.timedelta(seconds=61)}, "STALE_PRODUCT_FACT"),
    ({"observed_at": NOW + dt.timedelta(seconds=1)}, "FUTURE_PRODUCT_FACT"),
    ({"order_types": ("SL",)}, "ORDER_TYPE_NOT_ALLOWED"),
])
def test_candidate_mismatch_staleness_and_order_capability_refuse(candidate_change, code):
    with pytest.raises(product.ProductPolicyRefused, match=code):
        product.resolve_product(policy(), request(), candidate(**candidate_change))


def test_product_family_cannot_fall_back_to_policy_default():
    with pytest.raises(product.ProductPolicyRefused, match="PRODUCT_FAMILY_MISMATCH"):
        product.resolve_product(policy("options"), request(), candidate("equity"))


@pytest.mark.parametrize("value", [True, 0, -1])
def test_lot_and_step_reject_boolean_zero_or_negative(value):
    with pytest.raises(product.ProductPolicyRefused):
        candidate(lot_size=value)


def test_product_policy_module_has_no_provider_broker_order_or_database_import():
    parsed = ast.parse(Path(product.__file__).read_text(encoding="utf-8"))
    imports = {
        alias.name for node in ast.walk(parsed) if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module for node in ast.walk(parsed)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(name.startswith((
        "app.providers", "app.engine", "app.db", "app.execution.leases"))
        for name in imports)
