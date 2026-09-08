"""Owner proof for the unpublished V0 signal-alert attention contract."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from time import perf_counter
import tracemalloc

import pytest

from app.monitoring import contracts as subject


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(os.environ.get(
    "V0_ALERT_CONTRACT_SOURCE",
    ROOT / "paper-trader/backend/app/monitoring/contracts.py",
))
UTC = timezone.utc
T0 = datetime(2026, 8, 29, 9, 15, tzinfo=UTC)
GOLDEN_EVENT_ADDRESS = "sha256:baae3d754b5438c38fb5e44ff5c7aafccd349bc64f82d516a0563cb39607a801"
GOLDEN_ALERT_ADDRESS = "sha256:6b92d11a51ef94ce179dc443e947f1f5256bcd5b539ae1d0f0a063a63e1978d1"


def address(letter: str) -> str:
    return "sha256:" + letter * 64


def reference_address(payload: dict) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return "sha256:" + sha256(encoded).hexdigest()


def entry(*, validity=subject.FactValidity.VALID, value="100"):
    return subject.EntryReference(
        kind=subject.EntryReferenceKind.COMPLETED_EVENT_CLOSE,
        canonical_instrument_address=address("7"),
        value=value if validity is subject.FactValidity.VALID else None,
        currency="INR",
        observed_at=T0,
        source_truth_address=address("8"),
        validity=validity,
    )


def protection(kind, resolved, *, validity=subject.FactValidity.VALID):
    basis = (
        subject.ProtectionBasis.PERCENT_FROM_ENTRY_REFERENCE
        if kind is subject.ProtectionKind.STOP_LOSS
        else subject.ProtectionBasis.DISTANCE_FROM_ENTRY_REFERENCE
    )
    return subject.ProtectionEvidence(
        kind=kind,
        basis=basis,
        authored_component_id=(
            "intent.fixed_stop_percent"
            if kind is subject.ProtectionKind.STOP_LOSS
            else "intent.risk_reward_target"
        ),
        authored_component_version=2,
        authored_component_address=address("9" if kind is subject.ProtectionKind.STOP_LOSS else "a"),
        authored_contract_address=address("b" if kind is subject.ProtectionKind.STOP_LOSS else "c"),
        authored_parameters_address=address("d" if kind is subject.ProtectionKind.STOP_LOSS else "e"),
        authored_value="0.1" if kind is subject.ProtectionKind.STOP_LOSS else "2",
        units=subject.ProtectionUnits.RATE if kind is subject.ProtectionKind.STOP_LOSS else subject.ProtectionUnits.PRICE_POINTS,
        resolved_value=resolved if validity is subject.FactValidity.VALID else None,
        resolution_address=address("f" if kind is subject.ProtectionKind.STOP_LOSS else "1"),
        validity=validity,
    )


def event(
    action=subject.SignalAction.BUY,
    *,
    previous=subject.StrategyState.FLAT,
    target=subject.StrategyState.LONG,
    evaluation_validity=subject.FactValidity.VALID,
    freshness=subject.Freshness.FRESH,
    repeated=False,
    entry_reference=None,
    stop_loss=None,
    take_profit=None,
    owner_id="tenant.alpha",
    assignment_id="assignment.alpha",
):
    return subject.MonitoringSignalEvent(
        owner_id=owner_id,
        assignment_id=assignment_id,
        strategy_id="strategy.alpha",
        graph_version_address=address("2"),
        resolved_graph_address=address("3"),
        implementation_closure_address=address("4"),
        admission_address=address("5"),
        canonical_instrument_address=address("7"),
        display_symbol="NIFTY 50",
        previous_state=previous,
        target_state=target,
        action=action,
        evaluation_event_address=address("6"),
        event_at=T0 + timedelta(minutes=1),
        latest_data_at=T0,
        knowledge_cutoff_at=T0 + timedelta(minutes=2),
        valid_until=T0 + timedelta(minutes=7),
        evaluation_validity=evaluation_validity,
        freshness=freshness,
        repeated_target_state=repeated,
        entry_reference=entry() if entry_reference is None else entry_reference,
        stop_loss=protection(subject.ProtectionKind.STOP_LOSS, "90") if stop_loss is None else stop_loss,
        take_profit=protection(subject.ProtectionKind.TAKE_PROFIT, "120") if take_profit is None else take_profit,
        state_before_address=address("0"),
        state_after_address=address("1"),
        provider_evidence_address=address("a"),
        dataset_address=address("b"),
        reason_code="TARGET_STATE_CHANGED",
        reason_evidence_address=address("c"),
    )


def derived_alert(**changes):
    result = subject.derive_signal_alert(event(**changes))
    assert isinstance(result, subject.AlertDerived)
    return result.alert


def test_five_distinct_immutable_schema_identities_and_no_legacy_alias():
    alert = derived_alert()
    attempt = subject.AlertDeliveryAttempt.create(
        alert=alert, sequence=1, outcome=subject.DeliveryOutcome.FAILED,
        occurred_at=T0 + timedelta(minutes=3), failure_code="IN_APP_UNAVAILABLE",
    )
    attention = subject.AlertAttentionEvent.create(
        alert=alert, sequence=1, action=subject.AttentionAction.READ,
        occurred_at=T0 + timedelta(minutes=4),
    )
    projection = subject.rebuild_attention_projection(alert, [attention])
    facts = (event(), alert, attempt, attention, projection)
    assert [fact.schema for fact in facts] == [
        "monitoring-signal-event/1", "signal-alert/1", "alert-delivery-attempt/1",
        "alert-attention-event/1", "alert-attention-projection/1",
    ]
    assert len({type(fact) for fact in facts}) == 5
    for fact in facts:
        with pytest.raises((FrozenInstanceError, AttributeError)):
            fact.owner_id = "tenant.other"
    from app.db.models import SignalEvent
    assert subject.MonitoringSignalEvent is not SignalEvent


def test_source_import_boundary_and_forbidden_fields_are_closed():
    tree = ast.parse(SOURCE.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    assert not any(name.startswith((
        "app.db", "app.api", "app.engine", "app.execution", "app.providers",
        "app.main", "app.core.deployments",
    )) for name in imports)
    forbidden = {
        "account", "allocation", "armed", "broker", "capital", "deployment",
        "execution", "fill", "lease", "live", "money", "order", "position",
        "quantity", "reservation", "route", "tradingsymbol",
    }
    for cls in (
        subject.MonitoringSignalEvent, subject.SignalAlert,
        subject.AlertDeliveryAttempt, subject.AlertAttentionEvent,
        subject.AlertAttentionProjection,
    ):
        fields = set(cls.__dataclass_fields__)
        assert not forbidden & fields
        assert not any(token in field.lower().split("_") for field in fields for token in forbidden)


@pytest.mark.parametrize(
    "action,previous,target,stop,target_price",
    [
        (subject.SignalAction.BUY, subject.StrategyState.FLAT, subject.StrategyState.LONG, "90", "120"),
        (subject.SignalAction.BUY, subject.StrategyState.SHORT, subject.StrategyState.LONG, "90", "120"),
        (subject.SignalAction.SELL, subject.StrategyState.FLAT, subject.StrategyState.SHORT, "110", "80"),
        (subject.SignalAction.SELL, subject.StrategyState.LONG, subject.StrategyState.SHORT, "110", "80"),
        (subject.SignalAction.EXIT, subject.StrategyState.LONG, subject.StrategyState.FLAT, "90", "120"),
    ],
)
def test_golden_buy_sell_exit_preserve_attribution_and_protection(action, previous, target, stop, target_price):
    source = event(
        action, previous=previous, target=target,
        stop_loss=protection(subject.ProtectionKind.STOP_LOSS, stop),
        take_profit=protection(subject.ProtectionKind.TAKE_PROFIT, target_price),
    )
    first = subject.derive_signal_alert(source)
    second = subject.derive_signal_alert(source)
    assert isinstance(first, subject.AlertDerived)
    alert = first.alert
    assert alert == second.alert
    assert alert.canonical_bytes == second.alert.canonical_bytes
    assert alert.monitoring_event_address == source.address
    assert (alert.owner_id, alert.assignment_id, alert.strategy_id) == (
        source.owner_id, source.assignment_id, source.strategy_id,
    )
    assert alert.entry_reference == source.entry_reference
    assert alert.stop_loss == source.stop_loss and alert.take_profit == source.take_profit
    assert alert.freshness is source.freshness is subject.Freshness.FRESH
    assert alert.reason_evidence_address == source.reason_evidence_address
    assert alert.address == reference_address(alert.canonical_payload())


def test_owner_authored_golden_buy_payload_and_identity():
    source = event()
    alert = derived_alert()
    expected_entry = {
        "schema": "monitoring-entry-reference/1", "kind": "COMPLETED_EVENT_CLOSE",
        "canonical_instrument_address": address("7"), "value": "100", "currency": "INR",
        "observed_at": "2026-08-29T09:15:00.000000Z",
        "source_truth_address": address("8"), "validity": "VALID",
    }
    expected_stop = {
        "schema": "monitoring-protection-evidence/1", "kind": "STOP_LOSS",
        "basis": "PERCENT_FROM_ENTRY_REFERENCE",
        "authored_component_id": "intent.fixed_stop_percent",
        "authored_component_version": 2, "authored_component_address": address("9"),
        "authored_contract_address": address("b"), "authored_parameters_address": address("d"),
        "authored_value": "0.1", "units": "RATE", "resolved_value": "90",
        "resolution_address": address("f"), "validity": "VALID",
    }
    expected_target = {
        "schema": "monitoring-protection-evidence/1", "kind": "TAKE_PROFIT",
        "basis": "DISTANCE_FROM_ENTRY_REFERENCE",
        "authored_component_id": "intent.risk_reward_target",
        "authored_component_version": 2, "authored_component_address": address("a"),
        "authored_contract_address": address("c"), "authored_parameters_address": address("e"),
        "authored_value": "2", "units": "PRICE_POINTS", "resolved_value": "120",
        "resolution_address": address("1"), "validity": "VALID",
    }
    expected = {
        "schema": "signal-alert/1",
        "owner_id": "tenant.alpha",
        "assignment_id": "assignment.alpha",
        "monitoring_event_address": GOLDEN_EVENT_ADDRESS,
        "strategy_id": "strategy.alpha",
        "graph_version_address": address("2"),
        "resolved_graph_address": address("3"),
        "implementation_closure_address": address("4"),
        "admission_address": address("5"),
        "canonical_instrument_address": address("7"),
        "display_symbol": "NIFTY 50",
        "previous_state": "FLAT",
        "target_state": "LONG",
        "action": "BUY",
        "evaluation_event_address": address("6"),
        "event_at": "2026-08-29T09:16:00.000000Z",
        "latest_data_at": "2026-08-29T09:15:00.000000Z",
        "knowledge_cutoff_at": "2026-08-29T09:17:00.000000Z",
        "valid_until": "2026-08-29T09:22:00.000000Z",
        "freshness": "FRESH",
        "entry_reference": expected_entry,
        "stop_loss": expected_stop,
        "take_profit": expected_target,
        "state_before_address": address("0"),
        "state_after_address": address("1"),
        "provider_evidence_address": address("a"),
        "dataset_address": address("b"),
        "reason_code": "TARGET_STATE_CHANGED",
        "reason_evidence_address": address("c"),
    }
    assert source.address == GOLDEN_EVENT_ADDRESS
    assert alert.canonical_payload() == expected
    assert reference_address(expected) == GOLDEN_ALERT_ADDRESS
    assert alert.address == GOLDEN_ALERT_ADDRESS


@pytest.mark.parametrize(
    "evaluation_validity,freshness,code",
    [
        (validity, freshness, code)
        for validity, code in (
            (subject.FactValidity.VALID, subject.NoAlertCode.HOLD),
            (subject.FactValidity.MISSING, subject.NoAlertCode.MISSING_DATA),
            (subject.FactValidity.INVALID, subject.NoAlertCode.INVALID_DATA),
            (subject.FactValidity.REFUSED, subject.NoAlertCode.EVALUATION_REFUSED),
        )
        for freshness in (subject.Freshness.FRESH, subject.Freshness.STALE)
        if not (validity is subject.FactValidity.VALID and freshness is subject.Freshness.STALE)
    ] + [
        (subject.FactValidity.VALID, subject.Freshness.STALE, subject.NoAlertCode.STALE_DATA),
    ],
)
def test_hold_validity_and_freshness_truth_table(evaluation_validity, freshness, code):
    source = event(
        subject.SignalAction.HOLD,
        previous=subject.StrategyState.LONG,
        target=subject.StrategyState.LONG,
        evaluation_validity=evaluation_validity,
        freshness=freshness,
    )
    assert subject.derive_signal_alert(source) == subject.NoAlert(source.address, code)


def test_signal_alert_freshness_is_closed_serialized_and_addressed():
    alert = derived_alert()
    payload = alert.canonical_payload()
    assert payload["freshness"] == "FRESH"
    assert subject.SignalAlert.from_dict(alert.to_dict()) == alert
    without_freshness = {key: value for key, value in payload.items() if key != "freshness"}
    assert reference_address(without_freshness) != alert.address
    with pytest.raises(subject.MonitoringContractError, match="FRESHNESS"):
        replace(alert, freshness=subject.Freshness.STALE)


def test_unsupported_reverse_operation_remains_closed_and_refused():
    assert "REVERSE" not in {action.value for action in subject.SignalAction}
    with pytest.raises(subject.MonitoringContractError, match="SIGNAL_ACTION_CLOSED_VALUE_REQUIRED"):
        replace(event(), action="REVERSE")


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"action": subject.SignalAction.HOLD, "previous": subject.StrategyState.LONG, "target": subject.StrategyState.LONG}, subject.NoAlertCode.HOLD),
        ({"evaluation_validity": subject.FactValidity.REFUSED}, subject.NoAlertCode.EVALUATION_REFUSED),
        ({"evaluation_validity": subject.FactValidity.MISSING}, subject.NoAlertCode.MISSING_DATA),
        ({"evaluation_validity": subject.FactValidity.INVALID}, subject.NoAlertCode.INVALID_DATA),
        ({"freshness": subject.Freshness.STALE}, subject.NoAlertCode.STALE_DATA),
        ({"repeated": True, "previous": subject.StrategyState.LONG, "target": subject.StrategyState.LONG}, subject.NoAlertCode.REPEATED_TARGET_STATE),
        ({"entry_reference": entry(validity=subject.FactValidity.MISSING)}, subject.NoAlertCode.INVALID_ENTRY_REFERENCE),
        ({"stop_loss": protection(subject.ProtectionKind.STOP_LOSS, "90", validity=subject.FactValidity.INVALID)}, subject.NoAlertCode.INVALID_PROTECTION),
        ({"take_profit": protection(subject.ProtectionKind.TAKE_PROFIT, "120", validity=subject.FactValidity.MISSING)}, subject.NoAlertCode.INVALID_PROTECTION),
        ({"stop_loss": protection(subject.ProtectionKind.STOP_LOSS, "110")}, subject.NoAlertCode.INVALID_PROTECTION_GEOMETRY),
        ({"action": subject.SignalAction.BUY, "target": subject.StrategyState.SHORT}, subject.NoAlertCode.ACTION_STATE_MISMATCH),
    ],
)
def test_every_ineligible_condition_returns_typed_no_alert(changes, code):
    result = subject.derive_signal_alert(event(**changes))
    assert result == subject.NoAlert(
        monitoring_event_address=event(**changes).address,
        code=code,
    )


def test_material_immutable_change_changes_event_and_alert_addresses():
    original_event = event()
    changed_event = replace(original_event, reason_code="TARGET_STATE_CHANGED_BY_RULE")
    original = subject.derive_signal_alert(original_event).alert
    changed = subject.derive_signal_alert(changed_event).alert
    assert original_event.address != changed_event.address
    assert original.address != changed.address


def test_signal_alert_cannot_be_constructed_with_invalid_display_evidence():
    alert = derived_alert()
    with pytest.raises(subject.MonitoringContractError, match="VALID_EVIDENCE"):
        replace(alert, entry_reference=entry(validity=subject.FactValidity.MISSING))
    with pytest.raises(subject.MonitoringContractError, match="GEOMETRY"):
        replace(alert, stop_loss=protection(subject.ProtectionKind.STOP_LOSS, "110"))


@pytest.mark.parametrize("value", ["01", "+1", "1.0", "1.00", "1e2", "NaN", "Infinity", 100, True])
def test_noncanonical_decimals_refuse(value):
    with pytest.raises(subject.MonitoringContractError, match="CANONICAL_DECIMAL"):
        entry(value=value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("event_at", T0.replace(tzinfo=None)),
        ("latest_data_at", T0 + timedelta(minutes=3)),
        ("knowledge_cutoff_at", T0),
        ("valid_until", T0),
    ],
)
def test_non_utc_and_non_monotonic_event_time_refuse(field, value):
    with pytest.raises(subject.MonitoringContractError):
        replace(event(), **{field: value})


@pytest.mark.parametrize("field", [
    "graph_version_address", "resolved_graph_address", "implementation_closure_address",
    "admission_address", "canonical_instrument_address", "evaluation_event_address",
    "state_before_address", "state_after_address", "provider_evidence_address",
    "dataset_address", "reason_evidence_address",
])
def test_every_noncanonical_event_address_refuses(field):
    with pytest.raises(subject.MonitoringContractError, match="CONTENT_ADDRESS"):
        replace(event(), **{field: "sha256:BAD"})


def test_closed_actions_states_validities_channels_outcomes_and_attention():
    mutations = [
        (event(), "action", "BUY"),
        (event(), "previous_state", "FLAT"),
        (event(), "evaluation_validity", "VALID"),
    ]
    for fact, field, value in mutations:
        with pytest.raises(subject.MonitoringContractError):
            replace(fact, **{field: value})
    alert = derived_alert()
    with pytest.raises(subject.MonitoringContractError):
        subject.AlertDeliveryAttempt(
            owner_id=alert.owner_id, assignment_id=alert.assignment_id,
            alert_address=alert.address, sequence=1, channel="IN_APP",
            outcome=subject.DeliveryOutcome.DELIVERED,
            occurred_at=T0 + timedelta(minutes=3), failure_code=None,
        )
    with pytest.raises(subject.MonitoringContractError):
        subject.AlertAttentionEvent(
            owner_id=alert.owner_id, assignment_id=alert.assignment_id,
            alert_address=alert.address, sequence=1, action="READ",
            occurred_at=T0 + timedelta(minutes=3),
        )


def test_delivery_failure_never_mutates_alert_and_attempt_replay_is_idempotent():
    alert = derived_alert()
    before = alert.canonical_bytes
    failed = subject.AlertDeliveryAttempt.create(
        alert=alert, sequence=1, outcome=subject.DeliveryOutcome.FAILED,
        occurred_at=T0 + timedelta(minutes=3), failure_code="IN_APP_UNAVAILABLE",
    )
    delivered = subject.AlertDeliveryAttempt.create(
        alert=alert, sequence=2, outcome=subject.DeliveryOutcome.DELIVERED,
        occurred_at=T0 + timedelta(minutes=4),
    )
    assert subject.validate_delivery_attempts(alert, [failed, failed, delivered]) == (failed, delivered)
    assert alert.canonical_bytes == before
    assert failed.alert_address == alert.address
    assert failed.attempt_id == reference_address({
        "schema": "alert-delivery-request/1", "owner_id": alert.owner_id,
        "assignment_id": alert.assignment_id, "alert_address": alert.address,
        "sequence": 1, "channel": "IN_APP",
    })


def test_duplicate_delivery_attempt_identity_with_different_content_refuses():
    alert = derived_alert()
    failed = subject.AlertDeliveryAttempt.create(
        alert=alert, sequence=1, outcome=subject.DeliveryOutcome.FAILED,
        occurred_at=T0 + timedelta(minutes=3), failure_code="IN_APP_UNAVAILABLE",
    )
    conflict = replace(failed, failure_code="RENDER_FAILED")
    with pytest.raises(subject.MonitoringContractError, match="DUPLICATE_ATTEMPT_CONFLICT"):
        subject.validate_delivery_attempts(alert, [failed, conflict])


def test_delivery_owner_alert_assignment_sequence_and_time_adversaries_refuse():
    alert = derived_alert()
    first = subject.AlertDeliveryAttempt.create(
        alert=alert, sequence=1, outcome=subject.DeliveryOutcome.DELIVERED,
        occurred_at=T0 + timedelta(minutes=3),
    )
    for changed in (
        replace(first, owner_id="tenant.other"),
        replace(first, assignment_id="assignment.other"),
        replace(first, alert_address=address("f")),
        replace(first, sequence=2),
        replace(first, occurred_at=T0),
    ):
        with pytest.raises(subject.MonitoringContractError):
            subject.validate_delivery_attempts(alert, [changed])


def attention(alert, sequence, action, minutes):
    return subject.AlertAttentionEvent.create(
        alert=alert, sequence=sequence, action=action,
        occurred_at=T0 + timedelta(minutes=minutes),
    )


def test_attention_rebuild_is_restart_and_shuffle_deterministic_and_preserves_validity():
    alert = derived_alert()
    read = attention(alert, 1, subject.AttentionAction.READ, 3)
    acknowledge = attention(alert, 2, subject.AttentionAction.ACKNOWLEDGE, 4)
    dismiss = attention(alert, 3, subject.AttentionAction.DISMISS, 5)
    ordered = subject.rebuild_attention_projection(alert, [read, acknowledge, dismiss])
    replayed = subject.rebuild_attention_projection(alert, [dismiss, read, acknowledge, read])
    assert ordered == replayed
    assert ordered.canonical_bytes == replayed.canonical_bytes
    assert ordered.is_unread is False
    assert ordered.read_at == read.occurred_at
    assert ordered.acknowledged_at == acknowledge.occurred_at
    assert ordered.dismissed_at == dismiss.occurred_at
    assert ordered.alert_event_at == alert.event_at
    assert ordered.alert_valid_until == alert.valid_until
    encoded = ordered.to_dict()
    assert subject.AlertAttentionProjection.from_dict(encoded) == ordered


def test_initial_attention_projection_is_unread_and_does_not_change_alert():
    alert = derived_alert()
    before = alert.canonical_bytes
    projection = subject.rebuild_attention_projection(alert, [])
    assert projection.is_unread is True
    assert projection.last_sequence == 0
    assert projection.read_at is projection.acknowledged_at is projection.dismissed_at is None
    assert alert.canonical_bytes == before
    assert projection.alert_event_at == alert.event_at
    assert projection.alert_valid_until == alert.valid_until


def test_attention_owner_alert_assignment_gap_conflict_and_time_adversaries_refuse():
    alert = derived_alert()
    first = attention(alert, 1, subject.AttentionAction.READ, 3)
    conflict = replace(first, occurred_at=first.occurred_at + timedelta(seconds=1))
    adversaries = (
        [replace(first, owner_id="tenant.other")],
        [replace(first, assignment_id="assignment.other")],
        [replace(first, alert_address=address("f"))],
        [replace(first, sequence=2)],
        [first, conflict],
        [replace(first, occurred_at=T0)],
        [first, attention(alert, 2, subject.AttentionAction.DISMISS, 2)],
    )
    for events in adversaries:
        with pytest.raises(subject.MonitoringContractError):
            subject.rebuild_attention_projection(alert, events)


def test_attention_request_identity_is_deterministic_and_material_action_changes_it():
    alert = derived_alert()
    read = attention(alert, 1, subject.AttentionAction.READ, 3)
    read_again = attention(alert, 1, subject.AttentionAction.READ, 3)
    dismiss = attention(alert, 1, subject.AttentionAction.DISMISS, 3)
    assert read == read_again
    assert read.request_id == reference_address({
        "schema": "alert-attention-request/1", "owner_id": alert.owner_id,
        "assignment_id": alert.assignment_id, "alert_address": alert.address,
        "sequence": 1, "action": "READ",
    })
    assert read.request_id != dismiss.request_id


@pytest.mark.parametrize("factory", [
    lambda: event(),
    lambda: derived_alert(),
    lambda: subject.AlertDeliveryAttempt.create(
        alert=derived_alert(), sequence=1, outcome=subject.DeliveryOutcome.DELIVERED,
        occurred_at=T0 + timedelta(minutes=3),
    ),
    lambda: attention(derived_alert(), 1, subject.AttentionAction.READ, 3),
])
def test_serialization_restart_round_trip(factory):
    fact = factory()
    rebuilt = type(fact).from_dict(json.loads(json.dumps(fact.to_dict())))
    assert rebuilt == fact
    assert rebuilt.canonical_bytes == fact.canonical_bytes
    assert rebuilt.address == fact.address


def test_serialized_facts_reject_unknown_fields_and_forged_addresses():
    facts = [
        event(), derived_alert(),
        subject.AlertDeliveryAttempt.create(
            alert=derived_alert(), sequence=1, outcome=subject.DeliveryOutcome.DELIVERED,
            occurred_at=T0 + timedelta(minutes=3),
        ),
        attention(derived_alert(), 1, subject.AttentionAction.READ, 3),
        subject.rebuild_attention_projection(derived_alert(), []),
    ]
    for fact in facts:
        with pytest.raises(subject.MonitoringContractError):
            type(fact).from_dict({**fact.to_dict(), "unexpected": "field"})
        with pytest.raises(subject.MonitoringContractError, match="ADDRESS_MISMATCH"):
            type(fact).from_dict({**fact.to_dict(), "address": address("f")})


def test_resource_ceiling_for_100000_pure_facts():
    source = event()
    tracemalloc.start()
    started = perf_counter()
    for _ in range(100_000):
        result = subject.derive_signal_alert(source)
    elapsed = perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert isinstance(result, subject.AlertDerived)
    assert elapsed / 100_000 < 0.0006
    assert peak < 2_000_000
    print(f"facts=100000 elapsed_seconds={elapsed:.6f} peak_bytes={peak}")
