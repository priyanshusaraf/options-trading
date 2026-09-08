"""Fixed-point sizing, compatibility and pending-aware target-position contracts."""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import pytest

from app.core.instruments import get_instrument
from app.engine.allocator import Candidate, allocate
from app.engine.equity_entry import equity_qty, qty_for_margin
from app.execution import capital_compatibility as compatibility
from app.execution import sizing
from app.execution import target_position as target


NOW = dt.datetime(2026, 8, 25, 12, tzinfo=dt.timezone.utc)
PRODUCT = "sha256:" + "a" * 64


def address(char: str) -> str:
    return "sha256:" + char * 64


def inputs(**changes) -> sizing.SizingInputs:
    values = dict(
        decision_at=NOW, observed_at=NOW - dt.timedelta(seconds=1),
        max_age_seconds=60, quantity_step=1, lot_size=1,
        capital_per_step_minor=2_000, notional_per_step_minor=10_000,
        risk_per_step_minor=1_000, available_capital_minor=1_000_000,
        equity_minor=200_000, observed_volatility_ppm=200_000,
        estimated_fees_minor=100,
        source_addresses=(address("b"), address("c")))
    values.update(changes)
    return sizing.SizingInputs(**values)


@pytest.mark.parametrize("policy,expected", [
    (sizing.SizingPolicy("fixed-units", 1, "FIXED_UNITS", fixed_units=7), 7),
    (sizing.SizingPolicy("fixed-lots", 1, "FIXED_LOTS", fixed_lots=2), 150),
    (sizing.SizingPolicy("fixed-capital", 1, "FIXED_CAPITAL", amount_minor=10_000), 5),
    (sizing.SizingPolicy("capital-pct", 1, "CAPITAL_PCT", rate_ppm=250_000), 125),
    (sizing.SizingPolicy("equity-pct", 1, "EQUITY_PCT", rate_ppm=100_000), 10),
    (sizing.SizingPolicy("risk-stop", 1, "RISK_STOP", risk_budget_minor=5_000), 5),
    (sizing.SizingPolicy("vol-target", 1, "VOLATILITY_TARGET",
                         target_volatility_ppm=100_000), 10),
])
def test_every_sizing_mode_is_deterministic_fixed_point(policy, expected):
    mode_inputs = inputs(
        quantity_step=75, lot_size=75) if policy.mode == "FIXED_LOTS" else inputs()
    decision = sizing.size_position(policy, product_address=PRODUCT, inputs=mode_inputs)
    assert decision.accepted and decision.admitted_quantity == expected
    assert decision.policy_address == policy.address
    assert decision.inputs_address == mode_inputs.address
    assert decision.address == sizing.size_position(
        policy, product_address=PRODUCT, inputs=mode_inputs).address


def test_quantity_step_rounding_is_explicit_not_silent_resize():
    policy = sizing.SizingPolicy("units", 1, "FIXED_UNITS", fixed_units=5)
    decision = sizing.size_position(
        policy, product_address=PRODUCT,
        inputs=inputs(quantity_step=2, lot_size=2))
    assert decision.accepted and decision.requested_quantity == 5
    assert decision.admitted_quantity == 4 and decision.resized is False
    assert (decision.binding_constraint, decision.reason_code) == (
        "quantity_step", "ROUNDED")


def test_cap_or_cash_shortfall_refuses_when_resize_is_not_explicit():
    policy = sizing.SizingPolicy(
        "no-resize", 1, "FIXED_UNITS", fixed_units=10, max_quantity=5)
    decision = sizing.size_position(policy, product_address=PRODUCT, inputs=inputs())
    assert not decision.accepted and decision.admitted_quantity == 0
    assert decision.reason_code == "RESIZE_NOT_ALLOWED"


def test_explicit_resize_records_requested_and_admitted_quantity():
    policy = sizing.SizingPolicy(
        "resize", 1, "FIXED_UNITS", fixed_units=10,
        max_quantity=5, allow_resize=True)
    decision = sizing.size_position(policy, product_address=PRODUCT, inputs=inputs())
    assert decision.accepted and decision.resized
    assert (decision.requested_quantity, decision.admitted_quantity) == (10, 5)
    assert decision.reason_code == "EXPLICIT_RESIZE"


def test_fees_and_safety_buffer_are_part_of_required_capital_and_capacity():
    policy = sizing.SizingPolicy(
        "buffered", 1, "FIXED_UNITS", fixed_units=2,
        fee_buffer_minor=30, safety_buffer_minor=20)
    decision = sizing.size_position(
        policy, product_address=PRODUCT,
        inputs=inputs(capital_per_step_minor=100, estimated_fees_minor=10,
                      available_capital_minor=260))
    assert decision.accepted and decision.required_capital_minor == 260


@pytest.mark.parametrize("change,code", [
    ({"observed_at": NOW - dt.timedelta(seconds=61)}, "STALE_INPUT"),
    ({"observed_at": NOW + dt.timedelta(seconds=1)}, "FUTURE_INPUT"),
    ({"risk_per_step_minor": None}, "RISK_INPUT_REQUIRED"),
])
def test_stale_future_and_missing_dynamic_inputs_refuse(change, code):
    policy = sizing.SizingPolicy(
        "risk", 1, "RISK_STOP", risk_budget_minor=10_000)
    with pytest.raises(sizing.SizingRefused, match=code):
        sizing.size_position(policy, product_address=PRODUCT, inputs=inputs(**change))


@pytest.mark.parametrize("field,value", [
    ("available_capital_minor", True),
    ("capital_per_step_minor", 0),
    ("observed_volatility_ppm", True),
    ("estimated_fees_minor", -1),
])
def test_boolean_zero_and_negative_numeric_inputs_refuse(field, value):
    with pytest.raises((sizing.SizingRefused, RuntimeError)):
        inputs(**{field: value})


def target_request(**changes) -> target.TargetPositionRequest:
    values = dict(
        request_id="target-1", owner_id="owner-a",
        broker_account_id="account-a", book="paper", deployment_id=1,
        strategy_key="trend_impulse_v3", strategy_version="v1",
        admission_address=address("d"), graph_address=None,
        attribution_state="NON_GRAPH", canonical_instrument_key="NIFTY",
        product_address=PRODUCT, target_quantity=10,
        purpose="TARGET_ADJUSTMENT", decision_at=NOW)
    values.update(changes)
    return target.TargetPositionRequest(**values)


def pending(evidence_id: str, quantity: int, *, uncertain: bool = False, **changes):
    values = dict(
        evidence_id=evidence_id, owner_id="owner-a",
        broker_account_id="account-a", book="paper",
        canonical_instrument_key="NIFTY", product_address=PRODUCT,
        signed_remaining_quantity=quantity, state="PENDING",
        uncertain=uncertain, source_address=address(evidence_id[-1]))
    values.update(changes)
    return target.PendingQuantityEvidence(**values)


def test_target_delta_subtracts_same_direction_and_adds_opposite_pending():
    decision = target.derive_target_delta(
        target_request(), held_quantity=3,
        pending=(pending("pending-b", 5), pending("pending-e", -2)))
    assert decision.accepted
    assert decision.known_pending_quantity == 3
    assert decision.requested_delta == 4  # 10 - 3 held - (5 - 2 pending)
    assert decision.pending_evidence_addresses == tuple(
        sorted(decision.pending_evidence_addresses))


def test_uncertain_broker_state_blocks_addition_without_inventing_quantity():
    decision = target.derive_target_delta(
        target_request(target_quantity=12), held_quantity=3,
        pending=(pending("pending-f", 5, uncertain=True),))
    assert not decision.accepted and decision.requested_delta == 0
    assert decision.reason_code == "BROKER_UNCERTAINTY_BLOCKS_ENTRY"


def test_risk_reducing_target_bypasses_entry_uncertainty():
    decision = target.derive_target_delta(
        target_request(target_quantity=2, purpose="RISK_REDUCTION"),
        held_quantity=10,
        pending=(pending("pending-f", 5, uncertain=True),))
    assert decision.accepted and decision.risk_reducing
    assert decision.bypass_entry_admission and decision.requested_delta == -8


def test_uncertainty_cannot_use_risk_reduction_to_flip_direction():
    decision = target.derive_target_delta(
        target_request(target_quantity=-2, purpose="RISK_REDUCTION"),
        held_quantity=10,
        pending=(pending("pending-f", 5, uncertain=True),))
    assert not decision.accepted


def test_known_opposite_pending_plus_uncertainty_cannot_authorize_risk_increase():
    decision = target.derive_target_delta(
        target_request(target_quantity=2, purpose="RISK_REDUCTION"),
        held_quantity=10,
        pending=(pending("pending-8", -20),
                 pending("pending-f", 5, uncertain=True)))
    assert decision.known_pending_quantity == -20
    assert not decision.accepted and decision.requested_delta == 0
    assert not decision.risk_reducing and not decision.bypass_entry_admission


def test_known_pending_is_applied_before_uncertain_exit_delta_is_bounded():
    decision = target.derive_target_delta(
        target_request(target_quantity=2, purpose="RISK_REDUCTION"),
        held_quantity=10,
        pending=(pending("pending-3", -3),
                 pending("pending-f", 5, uncertain=True)))
    assert decision.accepted and decision.risk_reducing
    assert decision.known_pending_quantity == -3
    assert decision.requested_delta == -5  # target 2 - known effective 7


def test_uncertain_exit_delta_never_exceeds_current_held_inventory():
    decision = target.derive_target_delta(
        target_request(target_quantity=5, purpose="RISK_REDUCTION"),
        held_quantity=2,
        pending=(pending("pending-8", 8),
                 pending("pending-f", 1, uncertain=True)))
    assert decision.accepted and decision.requested_delta == -2
    assert decision.bypass_entry_admission


def test_known_opposite_pending_quantity_changes_effective_reduction_classification():
    decision = target.derive_target_delta(
        target_request(target_quantity=2, purpose="RISK_REDUCTION"),
        held_quantity=10, pending=(pending("pending-8", -8),))
    assert decision.accepted and decision.requested_delta == 0
    assert not decision.risk_reducing and not decision.bypass_entry_admission


def test_pending_evidence_is_owner_account_book_instrument_and_product_scoped():
    with pytest.raises(target.TargetPositionRefused, match="PENDING_IDENTITY_MISMATCH"):
        target.derive_target_delta(
            target_request(), held_quantity=0,
            pending=(pending("pending-f", 1, owner_id="owner-b"),))


def test_duplicate_pending_identity_refuses_before_delta():
    item = pending("pending-f", 1)
    with pytest.raises(target.TargetPositionRefused, match="DUPLICATE"):
        target.derive_target_delta(
            target_request(), held_quantity=0, pending=(item, item))


@pytest.mark.parametrize("margin,leverage,price", [
    (10_000, 5, 500), (7_500, 4, 321.5), (3_000, 3, 1_200),
])
def test_legacy_equity_quantity_matches_current_pure_helper(margin, leverage, price):
    assert compatibility.legacy_equity_quantity(
        margin=margin, leverage=leverage, price=price) == equity_qty(
            margin, leverage, price)


@pytest.mark.parametrize("per_share,target_margin", [
    (120, 10_000), (333.3, 7_500), (2_000, 1_999),
])
def test_broker_margin_equity_quantity_matches_current_helper(per_share, target_margin):
    assert compatibility.broker_margin_equity_quantity(
        per_share_margin=per_share, target_margin=target_margin) == qty_for_margin(
            per_share, target_margin)


def test_options_remain_one_exact_lot_and_futures_remain_whole_lots():
    assert compatibility.fixed_option_quantity(75) == 75
    assert compatibility.futures_quantity_from_margin(
        margin_per_lot=120_000, target_margin=260_000, lot_size=75) == (
            150, 240_000)
    assert compatibility.paper_futures_quantity(
        price=24_000, lot_size=75, margin_pct=0.1,
        target_margin=400_000) == (150, 360_000)


def test_priority_greedy_compatibility_matches_current_allocator():
    current = [
        Candidate("SILVERM", "LONG", 300.0),
        Candidate("NIFTY", "LONG", 400.0),
        Candidate("GOLDM", "SHORT", 150.0),
    ]
    expected = allocate(current, 500.0)
    projected = tuple(
        compatibility.CompatibilityCandidate(
            item.instrument_key, item.direction, int(item.cost * 100),
            get_instrument(item.instrument_key).priority)
        for item in current)
    actual = compatibility.allocate_compatibility(
        projected, available_cash_minor=50_000)
    assert [item.instrument_key for item in actual.funded] == [
        item.instrument_key for item in expected.funded]
    assert [item.instrument_key for item, _ in actual.skipped] == [
        item.instrument_key for item, _ in expected.skipped]


def test_new_contract_modules_have_no_database_provider_broker_or_runner_imports():
    from app.execution import product_policy
    modules = (sizing, target, compatibility, product_policy)
    for module in modules:
        parsed = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imports = {
            alias.name for node in ast.walk(parsed) if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module for node in ast.walk(parsed)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert not any(name.startswith((
            "app.db", "app.providers", "app.engine", "app.execution.leases"))
            for name in imports)
