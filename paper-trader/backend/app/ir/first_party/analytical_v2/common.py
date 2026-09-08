"""Small shared validity/reset helpers. No indicator, runtime or registry instance."""
from __future__ import annotations

import datetime as dt
from typing import Any, Mapping

from app.ir.hashing import content_address
from app.ir.node_contracts import (
    NodeContractRefusal, StateSnapshot, canonical_state_snapshot, _freeze, _plain,
)
from app.ir.schema import is_content_address
from app.ir.validity import NumericValue, ValidityState, invalid, valid
from app.market_data.numeric import NumericIngressError, market_float
from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract, RESET_REASONS_V2


def _canonical_bound_state_snapshot(document: Mapping[str, Any]) -> StateSnapshot:
    """Private /2 reader; the hashed legacy node_contracts.py stays byte-exact."""
    fields = {"schema", "strategy_address", "resolved_graph_address", "node_contract_address",
              "implementation_closure_address", "dataset_context_address", "evaluation_context_address",
              "last_event_address", "last_event_time", "state_bytes_digest", "validity_state",
              "reset_policy_address", "reset_reasons", "creation_evidence_address", "snapshot_address",
              "bound_contract_address"}
    if (not isinstance(document, Mapping) or set(document) != fields
            or document["schema"] != "state-snapshot/2"
            or not isinstance(document["bound_contract_address"], str)
            or not is_content_address(document["bound_contract_address"])):
        raise NodeContractRefusal("bound state snapshot is incomplete or open")
    if not isinstance(document["validity_state"], str) or document["validity_state"] not in {state.value for state in ValidityState}:
        raise NodeContractRefusal("bound state validity is unknown")
    reasons = document["reset_reasons"]
    if (not isinstance(reasons, (tuple, list)) or len(reasons) > 1024
            or any(not isinstance(reason, str) or reason not in RESET_REASONS_V2 for reason in reasons)
            or tuple(reasons) != tuple(sorted(set(reasons)))):
        raise NodeContractRefusal("bound state reset reasons are noncanonical")
    try:
        event_time = dt.datetime.fromisoformat(document["last_event_time"])
        if (event_time.tzinfo is None or event_time.utcoffset() is None
                or event_time.astimezone(dt.timezone.utc).isoformat() != document["last_event_time"]):
            raise ValueError("not canonical UTC")
    except (TypeError, ValueError) as exc:
        raise NodeContractRefusal("bound state event time must be canonical UTC") from exc
    expected = content_address({key: _plain(value) for key, value in document.items() if key != "snapshot_address"})
    if document["snapshot_address"] != expected:
        raise NodeContractRefusal("bound state snapshot address is stale or forged")
    # Validate shared address obligations through the frozen legacy implementation.
    # This projection is never returned or persisted as an actual /1 snapshot.
    projection = {key: _plain(value) for key, value in document.items() if key != "bound_contract_address"}
    projection.update(schema="state-snapshot/1", reset_reasons=[], validity_state="INVALID")
    projection["snapshot_address"] = content_address({key: value for key, value in projection.items() if key != "snapshot_address"})
    canonical_state_snapshot(projection)
    return StateSnapshot(_freeze(document), expected)


def required_numeric_scalar(inputs: Mapping[str, Any], field: str) -> NumericValue:
    """Missing fields refuse; invalid values cannot silently become a price."""
    if not isinstance(inputs, Mapping) or field not in inputs:
        raise NodeContractRefusal(f"required input {field!r} is missing")
    value = inputs[field]
    if isinstance(value, NumericValue):
        if value.state is not ValidityState.VALID:
            return value
        value = value.value
    if value is None:
        return invalid(ValidityState.MISSING)
    try:
        return valid(market_float(value, field=field))
    except NumericIngressError:
        return invalid(ValidityState.INVALID)


def required_condition(inputs: Mapping[str, Any], field: str) -> NumericValue:
    """Unknown and False remain distinct; numeric truthiness is never accepted."""
    if not isinstance(inputs, Mapping) or field not in inputs:
        raise NodeContractRefusal(f"required condition {field!r} is missing")
    value = inputs[field]
    if isinstance(value, NumericValue):
        if value.state is not ValidityState.VALID:
            return value
        value = value.value
    if value is None:
        return invalid(ValidityState.MISSING)
    return valid(value) if type(value) is bool else invalid(ValidityState.INVALID)


def contract_reset_reasons(bound: ResolvedNodeContract, reasons: Any) -> tuple[str, ...]:
    if not isinstance(bound, ResolvedNodeContract):
        raise NodeContractRefusal("reset requires an explicit resolved node contract")
    if (not isinstance(reasons, (tuple, list, set, frozenset)) or len(reasons) > 1024
            or any(not isinstance(reason, str) or reason not in RESET_REASONS_V2 for reason in reasons)):
        raise NodeContractRefusal("contract reset reasons are unknown or unbounded")
    values = tuple(sorted(set(reasons)))
    policy = bound.document["resolved_contract"]["state_reset_policy"]
    if policy["schema"] != "state-reset-policy/2" or not set(values) <= set(policy["reasons"]):
        raise NodeContractRefusal("reset reason is not declared by the bound contract")
    return values


def bound_state_snapshot(bound: ResolvedNodeContract, **facts: Any) -> StateSnapshot:
    """Bind a future state receipt to the verified plan's exact contract/context.

    The caller must obtain `bound` from canonical plan compilation/verification;
    this helper does not certify source authority or execute a state transition.
    """
    if not isinstance(bound, ResolvedNodeContract):
        raise NodeContractRefusal("state requires an explicit resolved node contract")
    owned = {"schema", "bound_contract_address", "node_contract_address", "reset_policy_address",
             "dataset_context_address", "evaluation_context_address", "snapshot_address"}
    if set(facts) & owned:
        raise NodeContractRefusal("state contract/context addresses are derived, not caller overrides")
    if "reset_reasons" not in facts:
        raise NodeContractRefusal("state requires explicit reset reasons, including an empty set")
    supplied = dict(facts)
    supplied["reset_reasons"] = contract_reset_reasons(bound, supplied["reset_reasons"])
    context = bound.document["input_binding"]
    document = {"schema": "state-snapshot/2", "bound_contract_address": bound.bound_contract_address,
                "node_contract_address": bound.document["source_contract_address"],
                "reset_policy_address": content_address(_plain(bound.document["resolved_contract"]["state_reset_policy"])),
                "dataset_context_address": context["dataset_context_address"],
                "evaluation_context_address": context["evaluation_context_address"], **supplied}
    document["snapshot_address"] = content_address(_plain(document))
    return _canonical_bound_state_snapshot(document)


def verify_bound_state_snapshot(document: Mapping[str, Any], bound: ResolvedNodeContract) -> StateSnapshot:
    """A valid content hash is insufficient if the expected bound context changed."""
    snapshot = _canonical_bound_state_snapshot(document)
    if not isinstance(bound, ResolvedNodeContract) or document["schema"] != "state-snapshot/2":
        raise NodeContractRefusal("state restore requires the expected bound /2 contract")
    context = bound.document["input_binding"]
    expected = {
        "bound_contract_address": bound.bound_contract_address,
        "node_contract_address": bound.document["source_contract_address"],
        "dataset_context_address": context["dataset_context_address"],
        "evaluation_context_address": context["evaluation_context_address"],
        "reset_policy_address": content_address(_plain(bound.document["resolved_contract"]["state_reset_policy"])),
    }
    if any(document[key] != value for key, value in expected.items()):
        raise NodeContractRefusal("state restore contract/context is stale or mismatched")
    contract_reset_reasons(bound, document["reset_reasons"])
    return snapshot
