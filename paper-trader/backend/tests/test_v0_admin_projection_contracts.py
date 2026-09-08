"""Critical tests for pure founder/admin safe aggregate projection contracts."""

from __future__ import annotations

import ast
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta, timezone
from enum import Enum, IntEnum
import inspect
import json
from pathlib import Path
import subprocess
import sys
import time
import tracemalloc

import pytest

from app.admin.projection_contracts import (
    MAX_CANONICAL_BYTES, MAX_COUNT, AdminAggregateProjectionCandidate,
    ContractValidationError, FamilyProjectionPolicy, OperationalBand,
    OperatorProofReferences, ProjectionPolicy,
    SafeAggregateInput, canonical_deserialize,
    create_operator_proof_references, create_projection_policy,
    create_safe_aggregate_input, derive_admin_aggregate_projection,
    validate_admin_aggregate_projection,
)


NOW = datetime(2026, 9, 1, 8, 30, 45, 123456, tzinfo=timezone.utc)
THRESHOLD = 10


def address(seed: str) -> str:
    return "sha256:" + (seed * 64)[:64]


POLICY_PROVENANCE = address("a")
BINDING = address("b")
PERMISSION = address("c")
STEP_UP = address("d")
SOURCE = address("e")

ACCOUNT_FAMILY = 101
ENTITLEMENT_FAMILY = 102
SUPPORT_FAMILY = 103
PRODUCT_USAGE_FAMILY = 104
OPERATIONS_HEALTH_FAMILY = 105
FAMILY_CODES = (
    ACCOUNT_FAMILY, ENTITLEMENT_FAMILY, SUPPORT_FAMILY,
    PRODUCT_USAGE_FAMILY, OPERATIONS_HEALTH_FAMILY,
)
BAND_LOW = 201
BAND_MEDIUM = 202
BAND_HIGH = 203

FAMILY_DIMENSIONS = {
    ACCOUNT_FAMILY: (1, 2),
    ENTITLEMENT_FAMILY: (3, 4),
    SUPPORT_FAMILY: (5, 6),
    PRODUCT_USAGE_FAMILY: (7, 8),
    OPERATIONS_HEALTH_FAMILY: (9, 10),
}


class LegacyStringDimension(str, Enum):
    ACCOUNT_PENDING = "account.state.pending"


class LegacyIntDimension(IntEnum):
    ACCOUNT_PENDING = 2


class LegacyFamilyCode(IntEnum):
    ACCOUNT = 101


class LegacyBandCode(IntEnum):
    LOW = 201


class LegacyProjectionFamily(str, Enum):
    SUPPORT_AGGREGATE = "SUPPORT_AGGREGATE"


class IntSubclass(int):
    pass


def policy(*, threshold: int = THRESHOLD) -> ProjectionPolicy:
    family_policies = tuple(
        FamilyProjectionPolicy(family, FAMILY_DIMENSIONS[family])
        for family in FAMILY_CODES
    )
    return create_projection_policy(
        policy_provenance_address=POLICY_PROVENANCE,
        family_policies=family_policies,
        operational_bands=(
            OperationalBand(BAND_LOW, 0, 99),
            OperationalBand(BAND_MEDIUM, 100, 999),
            OperationalBand(BAND_HIGH, 1000, MAX_COUNT),
        ),
        minimum_cohort_threshold=threshold,
    )


def proofs() -> OperatorProofReferences:
    return create_operator_proof_references(
        binding_address=BINDING,
        permission_policy_address=PERMISSION,
        step_up_proof_address=STEP_UP,
    )


def exact_context(selected_policy: ProjectionPolicy, family: int) -> dict[str, object]:
    return {
        "expected_policy_content_id": selected_policy.content_id,
        "expected_binding_address": BINDING,
        "expected_permission_policy_address": PERMISSION,
        "expected_step_up_proof_address": STEP_UP,
        "expected_source_receipt_address": SOURCE,
        "expected_family": family,
        "expected_evaluated_at": NOW,
        "expected_minimum_cohort_threshold": selected_policy.minimum_cohort_threshold,
    }


def aggregate_input(
    selected_policy: ProjectionPolicy,
    selected_proofs: OperatorProofReferences,
    family: int,
    *, count: int = THRESHOLD,
) -> SafeAggregateInput:
    context = exact_context(selected_policy, family)
    return create_safe_aggregate_input(
        policy=selected_policy, operator_proofs=selected_proofs,
        expected_policy_content_id=context["expected_policy_content_id"],
        expected_binding_address=BINDING,
        expected_permission_policy_address=PERMISSION,
        expected_step_up_proof_address=STEP_UP,
        expected_minimum_cohort_threshold=selected_policy.minimum_cohort_threshold,
        family=family, dimensions=(FAMILY_DIMENSIONS[family][0],), count=count,
        source_receipt_address=SOURCE, expected_source_receipt_address=SOURCE,
        evaluated_at=NOW, expected_evaluated_at=NOW,
    )


def derivation_context(
    selected_policy: ProjectionPolicy,
    family: int,
    selected_input: SafeAggregateInput,
) -> dict[str, object]:
    return exact_context(selected_policy, family) | {
        "expected_aggregate_input_content_id": selected_input.content_id,
    }


def flow(
    family: int = ACCOUNT_FAMILY,
    *, count: int = THRESHOLD,
) -> tuple[ProjectionPolicy, OperatorProofReferences, SafeAggregateInput, AdminAggregateProjectionCandidate]:
    selected_policy = policy()
    selected_proofs = proofs()
    selected_input = aggregate_input(selected_policy, selected_proofs, family, count=count)
    projection = derive_admin_aggregate_projection(
        policy=selected_policy, operator_proofs=selected_proofs,
        aggregate_input=selected_input,
        **derivation_context(selected_policy, family, selected_input),
    )
    return selected_policy, selected_proofs, selected_input, projection


@pytest.mark.parametrize("family", FAMILY_CODES)
def test_five_legitimate_families_pass_at_threshold(family: int) -> None:
    selected_policy, selected_proofs, selected_input, projection = flow(family)
    assert projection.family == family
    assert projection.count == THRESHOLD
    assert projection.dimensions == (FAMILY_DIMENSIONS[family][0],)
    assert projection.policy_content_id == selected_policy.content_id
    assert projection.operator_proofs_content_id == selected_proofs.content_id
    assert projection.aggregate_input_content_id == selected_input.content_id
    assert projection.publishable is False
    assert projection.access_activated is False


@pytest.mark.parametrize("count", [0, -1, True, MAX_COUNT + 1])
def test_zero_negative_bool_and_oversize_counts_refuse(count: object) -> None:
    selected_policy = policy()
    selected_proofs = proofs()
    with pytest.raises(ContractValidationError):
        aggregate_input(selected_policy, selected_proofs, ACCOUNT_FAMILY, count=count)


def test_positive_below_threshold_refuses_only_at_derivation() -> None:
    selected_policy = policy()
    selected_proofs = proofs()
    selected_input = aggregate_input(
        selected_policy, selected_proofs,
        ACCOUNT_FAMILY, count=THRESHOLD - 1,
    )
    with pytest.raises(ContractValidationError, match="below"):
        derive_admin_aggregate_projection(
            policy=selected_policy, operator_proofs=selected_proofs,
            aggregate_input=selected_input,
            **derivation_context(
                selected_policy, ACCOUNT_FAMILY, selected_input,
            ),
        )


def test_no_threshold_or_catalogue_default_exists() -> None:
    signature = inspect.signature(create_projection_policy)
    assert signature.parameters["minimum_cohort_threshold"].default is inspect.Parameter.empty
    assert signature.parameters["family_policies"].default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        create_projection_policy(policy_provenance_address=POLICY_PROVENANCE)


def test_policy_requires_exactly_five_sorted_finite_family_catalogues() -> None:
    selected = policy()
    with pytest.raises(ContractValidationError):
        replace(selected, family_policies=selected.family_policies[:-1])
    with pytest.raises(ContractValidationError):
        replace(selected, family_policies=tuple(reversed(selected.family_policies)))
    with pytest.raises(ContractValidationError):
        replace(selected.family_policies[0], allowed_dimension_codes=())
    with pytest.raises(ContractValidationError):
        replace(selected.family_policies[0], allowed_dimension_codes=(2, 1))


def test_operational_bands_are_closed_contiguous_and_cover_bound() -> None:
    selected = policy()
    with pytest.raises(ContractValidationError):
        replace(selected, operational_bands=(OperationalBand(BAND_LOW, 1, MAX_COUNT),))
    with pytest.raises(ContractValidationError):
        replace(selected, operational_bands=(
            OperationalBand(BAND_LOW, 0, 5), OperationalBand(BAND_MEDIUM, 7, MAX_COUNT),
        ))
    with pytest.raises(ContractValidationError):
        replace(selected, operational_bands=(OperationalBand(BAND_LOW, 0, MAX_COUNT - 1),))


def test_cross_policy_authority_source_family_dimension_threshold_and_time_refuse() -> None:
    selected_policy, selected_proofs, selected_input, _ = flow()
    base = derivation_context(
        selected_policy, ACCOUNT_FAMILY, selected_input,
    )
    cases = [
        {"expected_policy_content_id": address("1")},
        {"expected_binding_address": address("2")},
        {"expected_permission_policy_address": address("3")},
        {"expected_step_up_proof_address": address("4")},
        {"expected_source_receipt_address": address("5")},
        {"expected_family": SUPPORT_FAMILY},
        {"expected_evaluated_at": NOW + timedelta(microseconds=1)},
        {"expected_minimum_cohort_threshold": THRESHOLD + 1},
    ]
    for changed in cases:
        with pytest.raises(ContractValidationError):
            derive_admin_aggregate_projection(
                policy=selected_policy, operator_proofs=selected_proofs,
                aggregate_input=selected_input, **(base | changed),
            )
    with pytest.raises(ContractValidationError):
        create_safe_aggregate_input(
            policy=selected_policy, operator_proofs=selected_proofs,
            expected_policy_content_id=selected_policy.content_id,
            expected_binding_address=BINDING,
            expected_permission_policy_address=PERMISSION,
            expected_step_up_proof_address=STEP_UP,
            expected_minimum_cohort_threshold=selected_policy.minimum_cohort_threshold,
            family=ACCOUNT_FAMILY,
            dimensions=(5,), count=THRESHOLD,
            source_receipt_address=SOURCE, expected_source_receipt_address=SOURCE,
            evaluated_at=NOW, expected_evaluated_at=NOW,
        )


def test_canonical_identity_covers_every_answer_changing_field() -> None:
    _, _, selected_input, projection = flow(count=100)
    changed_inputs = (
        replace(selected_input, count=101),
        replace(selected_input, dimensions=(2,)),
        replace(selected_input, source_receipt_address=address("f")),
        replace(selected_input, evaluated_at=NOW + timedelta(microseconds=1)),
    )
    assert all(item.content_id != selected_input.content_id for item in changed_inputs)
    changed_projections = (
        replace(projection, count=101),
        replace(projection, dimensions=(2,)),
        replace(projection, operational_band_code=BAND_LOW),
        replace(projection, source_receipt_address=address("f")),
    )
    assert all(item.content_id != projection.content_id for item in changed_projections)


def test_projection_surface_excludes_private_individual_money_raw_and_effect_fields() -> None:
    forbidden = {
        "user_id", "tenant_id", "session_id", "account_id", "support_case_id",
        "subject_id", "source_event_id", "email", "phone", "ip", "user_agent",
        "strategy_id", "graph_id", "research_id", "monitoring_id", "symbol",
        "instrument_id", "signal_id", "position_id", "order_id", "trade_id",
        "fill_id", "balance", "pnl", "capital", "charge", "payment_id",
        "provider_id", "customer_id", "credential", "token", "secret",
        "free_text", "properties", "url", "query", "header", "body", "log",
        "error", "stack", "screenshot", "replay", "mutation", "audit",
        "session", "impersonation",
    }
    contract_types = (
        FamilyProjectionPolicy, OperationalBand, ProjectionPolicy,
        OperatorProofReferences, SafeAggregateInput, AdminAggregateProjectionCandidate,
    )
    for contract_type in contract_types:
        names = {field.name for field in fields(contract_type)}
        assert forbidden.isdisjoint(names)


def test_fixed_numeric_dimension_table_is_exact_and_fully_allocated() -> None:
    selected_policy = policy()
    selected = {
        code for family_policy in selected_policy.family_policies
        for code in family_policy.allowed_dimension_codes
    }
    assert selected == set(range(1, 11))
    assert all(type(code) is int for code in selected)
    with pytest.raises(ContractValidationError):
        FamilyProjectionPolicy(
            ACCOUNT_FAMILY,
            (5,),
        )


def test_numeric_canonical_values_are_exact_builtin_integers() -> None:
    _, _, selected_input, projection = flow()
    assert all(type(code) is int for code in selected_input.dimensions)
    assert all(type(code) is int for code in projection.dimensions)


def test_mutated_legacy_enum_name_and_value_cannot_enter_policy() -> None:
    string_code = LegacyStringDimension.ACCOUNT_PENDING
    int_code = LegacyIntDimension.ACCOUNT_PENDING
    original_value = string_code._value_
    original_name = int_code._name_
    object.__setattr__(string_code, "_value_", "tenant:tenant-a")
    object.__setattr__(int_code, "_name_", "TENANT_PRIVATE")
    try:
        with pytest.raises(ContractValidationError):
            FamilyProjectionPolicy(ACCOUNT_FAMILY, (string_code,))
        with pytest.raises(ContractValidationError):
            FamilyProjectionPolicy(ACCOUNT_FAMILY, (int_code,))
    finally:
        object.__setattr__(string_code, "_value_", original_value)
        object.__setattr__(int_code, "_name_", original_name)


def test_removed_projection_family_enum_mutation_cannot_change_cached_output() -> None:
    selected_policy, _, selected_input, projection = flow()
    before = (
        selected_policy.content_id,
        selected_policy.canonical_json(),
        selected_input.content_id,
        selected_input.canonical_json(),
        projection.content_id,
        projection.canonical_json(),
    )
    family = LegacyProjectionFamily.SUPPORT_AGGREGATE
    original_value = family._value_
    original_name = family._name_
    object.__setattr__(family, "_value_", "tenant:tenant-private")
    object.__setattr__(family, "_name_", "TENANT_PRIVATE")
    try:
        after = (
            selected_policy.content_id,
            selected_policy.canonical_json(),
            selected_input.content_id,
            selected_input.canonical_json(),
            projection.content_id,
            projection.canonical_json(),
        )
        assert after == before
        with pytest.raises(ContractValidationError):
            FamilyProjectionPolicy(family, (5,))
        with pytest.raises(ContractValidationError):
            SafeAggregateInput(
                address("1"), address("2"), family, (5,), THRESHOLD, SOURCE, NOW,
            )
    finally:
        object.__setattr__(family, "_value_", original_value)
        object.__setattr__(family, "_name_", original_name)


@pytest.mark.parametrize("sentinel", [
    "tenant:tenant-a",
    "account:account-a",
    "credential:secret-value",
    "token:opaque-token-value",
    "secret:private-secret",
    "pii:person-profile",
    "email:founder@example.com",
    "strategy:alpha",
    "research:run-a",
    "monitoring:alert-a",
    "symbol:nifty",
    "signal:entry",
    "pnl:1000",
    "money:1000",
    "provider:zerodha",
    "broker:kite",
    "payment:customer-a",
    "raw:url",
    "raw:body",
    "raw:log",
    "account.state.active",
    "token:" + "a" * 256,
])
def test_hostile_dimension_value_matrix_refuses_direct_policy_codec_and_self_attestation(
    sentinel: str,
) -> None:
    family = ACCOUNT_FAMILY
    with pytest.raises(ContractValidationError):
        FamilyProjectionPolicy(family, (sentinel,))
    with pytest.raises(ContractValidationError):
        SafeAggregateInput(
            address("1"), address("2"), family, (sentinel,), THRESHOLD,
            SOURCE, NOW,
        )
    with pytest.raises(ContractValidationError):
        OperationalBand(sentinel, 0, MAX_COUNT)
    with pytest.raises(ContractValidationError):
        AdminAggregateProjectionCandidate(
            address("1"), address("2"), address("3"), family, (1,), THRESHOLD,
            sentinel, SOURCE, NOW, False, False,
        )

    selected_policy = policy()
    self_attested = deepcopy(selected_policy)
    object.__setattr__(
        self_attested.family_policies[0], "allowed_dimension_codes", (sentinel,),
    )
    with pytest.raises(ContractValidationError):
        self_attested.__post_init__()

    raw_policy = selected_policy.canonical_dict()
    raw_policy["family_policies"][0]["allowed_dimension_codes"] = [sentinel]
    encoded = json.dumps(raw_policy, sort_keys=True, separators=(",", ":"))
    with pytest.raises(ContractValidationError):
        canonical_deserialize(encoded, expected_policy_content_id=selected_policy.content_id)

    self_attested_band_policy = deepcopy(selected_policy)
    object.__setattr__(self_attested_band_policy.operational_bands[0], "code", sentinel)
    with pytest.raises(ContractValidationError):
        self_attested_band_policy.canonical_json()
    raw_band = OperationalBand(BAND_LOW, 0, MAX_COUNT).canonical_dict() | {"code": sentinel}
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(raw_band, sort_keys=True, separators=(",", ":")))

    with pytest.raises(ContractValidationError):
        create_safe_aggregate_input(
            policy=selected_policy,
            operator_proofs=proofs(),
            expected_policy_content_id=selected_policy.content_id,
            expected_binding_address=BINDING,
            expected_permission_policy_address=PERMISSION,
            expected_step_up_proof_address=STEP_UP,
            expected_minimum_cohort_threshold=THRESHOLD,
            family=family,
            dimensions=(sentinel,),
            count=THRESHOLD,
            source_receipt_address=SOURCE,
            expected_source_receipt_address=SOURCE,
            evaluated_at=NOW,
            expected_evaluated_at=NOW,
        )


@pytest.mark.parametrize("invalid_code", [
    True,
    1.0,
    "1",
    LegacyIntDimension.ACCOUNT_PENDING,
    IntSubclass(1),
    0,
    -1,
    11,
    10**100,
    3,
], ids=[
    "bool", "float", "string", "int-enum", "int-subclass", "zero",
    "negative", "eleven", "huge", "cross-family",
])
def test_numeric_type_range_and_family_matrix_refuses_every_contract_boundary(
    invalid_code: object,
) -> None:
    family = ACCOUNT_FAMILY
    with pytest.raises(ContractValidationError):
        FamilyProjectionPolicy(family, (invalid_code,))
    with pytest.raises(ContractValidationError):
        SafeAggregateInput(
            address("1"), address("2"), family, (invalid_code,), THRESHOLD,
            SOURCE, NOW,
        )
    with pytest.raises(ContractValidationError):
        AdminAggregateProjectionCandidate(
            address("1"), address("2"), address("3"), family,
            (invalid_code,), THRESHOLD, BAND_LOW, SOURCE, NOW, False, False,
        )

    selected_policy = policy()
    selected_proofs = proofs()
    with pytest.raises(ContractValidationError):
        create_safe_aggregate_input(
            policy=selected_policy,
            operator_proofs=selected_proofs,
            expected_policy_content_id=selected_policy.content_id,
            expected_binding_address=BINDING,
            expected_permission_policy_address=PERMISSION,
            expected_step_up_proof_address=STEP_UP,
            expected_minimum_cohort_threshold=THRESHOLD,
            family=family,
            dimensions=(invalid_code,),
            count=THRESHOLD,
            source_receipt_address=SOURCE,
            expected_source_receipt_address=SOURCE,
            evaluated_at=NOW,
            expected_evaluated_at=NOW,
        )

    if type(invalid_code) not in {LegacyIntDimension, IntSubclass}:
        raw_policy = selected_policy.canonical_dict()
        raw_policy["family_policies"][0]["allowed_dimension_codes"] = [invalid_code]
        encoded = json.dumps(raw_policy, sort_keys=True, separators=(",", ":"))
        with pytest.raises(ContractValidationError):
            canonical_deserialize(
                encoded, expected_policy_content_id=selected_policy.content_id,
            )


@pytest.mark.parametrize("invalid_family", [
    True, 101.0, "101", LegacyFamilyCode.ACCOUNT, IntSubclass(101),
    0, 100, 106, 10**100,
], ids=[
    "bool", "float", "string", "int-enum", "int-subclass",
    "zero", "below-table", "above-table", "huge",
])
def test_family_code_exact_type_and_fixed_table_refuse(invalid_family: object) -> None:
    with pytest.raises(ContractValidationError):
        FamilyProjectionPolicy(invalid_family, (1,))
    with pytest.raises(ContractValidationError):
        SafeAggregateInput(
            address("1"), address("2"), invalid_family, (1,), THRESHOLD, SOURCE, NOW,
        )
    with pytest.raises(ContractValidationError):
        AdminAggregateProjectionCandidate(
            address("1"), address("2"), address("3"), invalid_family, (1,),
            THRESHOLD, BAND_LOW, SOURCE, NOW, False, False,
        )
    if type(invalid_family) not in {LegacyFamilyCode, IntSubclass}:
        raw = FamilyProjectionPolicy(ACCOUNT_FAMILY, (1,)).canonical_dict()
        raw["family"] = invalid_family
        with pytest.raises(ContractValidationError):
            canonical_deserialize(json.dumps(raw, sort_keys=True, separators=(",", ":")))


@pytest.mark.parametrize("invalid_band", [
    True, 201.0, "201", LegacyBandCode.LOW, IntSubclass(201),
    0, 200, 204, 10**100,
], ids=[
    "bool", "float", "string", "int-enum", "int-subclass",
    "zero", "below-table", "above-table", "huge",
])
def test_band_code_exact_type_and_fixed_table_refuse(invalid_band: object) -> None:
    with pytest.raises(ContractValidationError):
        OperationalBand(invalid_band, 0, MAX_COUNT)
    with pytest.raises(ContractValidationError):
        AdminAggregateProjectionCandidate(
            address("1"), address("2"), address("3"), ACCOUNT_FAMILY, (1,),
            THRESHOLD, invalid_band, SOURCE, NOW, False, False,
        )
    if type(invalid_band) not in {LegacyBandCode, IntSubclass}:
        raw = OperationalBand(BAND_LOW, 0, MAX_COUNT).canonical_dict()
        raw["code"] = invalid_band
        with pytest.raises(ContractValidationError):
            canonical_deserialize(json.dumps(raw, sort_keys=True, separators=(",", ":")))


CROSS_FAMILY_CASES = tuple(
    (family, foreign_family, code)
    for family in FAMILY_CODES
    for foreign_family in FAMILY_CODES
    if foreign_family != family
    for code in FAMILY_DIMENSIONS[foreign_family]
)


@pytest.mark.parametrize(
    ("family", "foreign_family", "foreign_code"),
    CROSS_FAMILY_CASES,
    ids=[f"family-{family}-from-{foreign_family}-code-{code}"
         for family, foreign_family, code in CROSS_FAMILY_CASES],
)
def test_exhaustive_json_numeric_cross_family_matrix_refuses(
    family: int, foreign_family: int, foreign_code: int,
) -> None:
    selected_policy = policy()
    selected_proofs = proofs()
    selected_input = aggregate_input(selected_policy, selected_proofs, family)
    projection = derive_admin_aggregate_projection(
        policy=selected_policy, operator_proofs=selected_proofs,
        aggregate_input=selected_input,
        **derivation_context(selected_policy, family, selected_input),
    )
    with pytest.raises(ContractValidationError):
        FamilyProjectionPolicy(family, (foreign_code,))
    with pytest.raises(ContractValidationError):
        SafeAggregateInput(
            address("1"), address("2"), family, (foreign_code,), THRESHOLD,
            SOURCE, NOW,
        )

    raw_policy = selected_policy.canonical_dict()
    family_index = FAMILY_CODES.index(family)
    raw_policy["family_policies"][family_index]["allowed_dimension_codes"] = [foreign_code]
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            json.dumps(raw_policy, sort_keys=True, separators=(",", ":")),
            expected_policy_content_id=selected_policy.content_id,
        )
    context = {
        "policy": selected_policy, "operator_proofs": selected_proofs,
        **derivation_context(selected_policy, family, selected_input),
    }
    raw_input = selected_input.canonical_dict() | {"dimensions": [foreign_code]}
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            json.dumps(raw_input, sort_keys=True, separators=(",", ":")), **context,
        )
    raw_projection = projection.canonical_dict() | {"dimensions": [foreign_code]}
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            json.dumps(raw_projection, sort_keys=True, separators=(",", ":")),
            aggregate_input=selected_input, **context,
        )


def test_json_numeric_text_has_no_python_subclass_provenance() -> None:
    assert type(LegacyFamilyCode.ACCOUNT) is LegacyFamilyCode
    assert type(IntSubclass(101)) is IntSubclass
    decoded_enum = json.loads(json.dumps(LegacyFamilyCode.ACCOUNT))
    decoded_subclass = json.loads(json.dumps(IntSubclass(101)))
    assert type(decoded_enum) is int
    assert type(decoded_subclass) is int
    assert decoded_enum == decoded_subclass == ACCOUNT_FAMILY
    with pytest.raises(ContractValidationError):
        FamilyProjectionPolicy(LegacyFamilyCode.ACCOUNT, (1,))
    with pytest.raises(ContractValidationError):
        FamilyProjectionPolicy(IntSubclass(101), (1,))
    assert canonical_deserialize(
        FamilyProjectionPolicy(ACCOUNT_FAMILY, (1,)).canonical_json()
    ) == FamilyProjectionPolicy(ACCOUNT_FAMILY, (1,))


def test_canonical_dimension_payloads_are_json_integers_without_labels() -> None:
    selected_policy, _, selected_input, projection = flow()
    payloads = (
        selected_policy.canonical_dict(), selected_input.canonical_dict(),
        projection.canonical_dict(),
    )
    policy_codes = [
        code for item in payloads[0]["family_policies"]
        for code in item["allowed_dimension_codes"]
    ]
    assert all(type(code) is int for code in policy_codes)
    assert all(type(code) is int for code in payloads[1]["dimensions"])
    assert all(type(code) is int for code in payloads[2]["dimensions"])
    assert all(
        type(item["code"]) is int for item in payloads[0]["operational_bands"]
    )
    assert type(payloads[1]["family"]) is int
    assert type(payloads[2]["family"]) is int
    assert type(payloads[2]["operational_band_code"]) is int
    encoded = "".join(json.dumps(item, sort_keys=True) for item in payloads)
    assert "AdminDimensionCode" not in encoded
    assert "account.state" not in encoded
    assert "support.status" not in encoded
    assert "band." not in encoded
    assert "ACCOUNT_STATE_AGGREGATE" not in encoded


def test_fresh_numeric_policy_input_projection_and_decode_mutations_refuse() -> None:
    selected_policy, selected_proofs, selected_input, projection = flow()
    context = derivation_context(
        selected_policy, ACCOUNT_FAMILY, selected_input,
    )

    hostile_policy = deepcopy(selected_policy)
    object.__setattr__(hostile_policy.family_policies[0], "allowed_dimension_codes", (3,))
    with pytest.raises(ContractValidationError):
        hostile_policy.canonical_json()
    with pytest.raises(ContractValidationError):
        derive_admin_aggregate_projection(
            policy=hostile_policy, operator_proofs=selected_proofs,
            aggregate_input=selected_input, **context,
        )

    hostile_input = replace(selected_input)
    object.__setattr__(hostile_input, "dimensions", (11,))
    with pytest.raises(ContractValidationError):
        hostile_input.canonical_json()
    with pytest.raises(ContractValidationError):
        derive_admin_aggregate_projection(
            policy=selected_policy, operator_proofs=selected_proofs,
            aggregate_input=hostile_input, **context,
        )

    hostile_projection = copy(projection)
    object.__setattr__(hostile_projection, "dimensions", (3,))
    with pytest.raises(ContractValidationError):
        hostile_projection.canonical_json()
    with pytest.raises(ContractValidationError):
        validate_admin_aggregate_projection(
            hostile_projection, policy=selected_policy,
            operator_proofs=selected_proofs, aggregate_input=selected_input,
            **context,
        )

    codec_context = {
        "policy": selected_policy, "operator_proofs": selected_proofs, **context,
    }
    hostile_policy_raw = selected_policy.canonical_dict()
    hostile_policy_raw["family_policies"][0]["allowed_dimension_codes"] = [3]
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            json.dumps(hostile_policy_raw, sort_keys=True, separators=(",", ":")),
            expected_policy_content_id=selected_policy.content_id,
        )
    hostile_input_raw = selected_input.canonical_dict() | {"dimensions": [11]}
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            json.dumps(hostile_input_raw, sort_keys=True, separators=(",", ":")),
            **codec_context,
        )
    hostile_projection_raw = projection.canonical_dict() | {"dimensions": [3]}
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            json.dumps(hostile_projection_raw, sort_keys=True, separators=(",", ":")),
            aggregate_input=selected_input, **codec_context,
        )


def test_fresh_family_and_band_policy_input_projection_decode_mutations_refuse() -> None:
    selected_policy, selected_proofs, selected_input, projection = flow()
    context = derivation_context(selected_policy, ACCOUNT_FAMILY, selected_input)

    family_policy = deepcopy(selected_policy)
    object.__setattr__(family_policy.family_policies[0], "family", 106)
    with pytest.raises(ContractValidationError):
        family_policy.canonical_json()
    with pytest.raises(ContractValidationError):
        derive_admin_aggregate_projection(
            policy=family_policy, operator_proofs=selected_proofs,
            aggregate_input=selected_input, **context,
        )

    band_policy = deepcopy(selected_policy)
    object.__setattr__(band_policy.operational_bands[0], "code", 204)
    with pytest.raises(ContractValidationError):
        band_policy.canonical_json()

    family_input = replace(selected_input)
    object.__setattr__(family_input, "family", ENTITLEMENT_FAMILY)
    with pytest.raises(ContractValidationError):
        derive_admin_aggregate_projection(
            policy=selected_policy, operator_proofs=selected_proofs,
            aggregate_input=family_input, **context,
        )

    family_projection = copy(projection)
    object.__setattr__(family_projection, "family", ENTITLEMENT_FAMILY)
    with pytest.raises(ContractValidationError):
        validate_admin_aggregate_projection(
            family_projection, policy=selected_policy,
            operator_proofs=selected_proofs, aggregate_input=selected_input, **context,
        )
    band_projection = deepcopy(projection)
    object.__setattr__(band_projection, "operational_band_code", 204)
    with pytest.raises(ContractValidationError):
        validate_admin_aggregate_projection(
            band_projection, policy=selected_policy,
            operator_proofs=selected_proofs, aggregate_input=selected_input, **context,
        )

    raw_family_policy = selected_policy.family_policies[0].canonical_dict() | {"family": 106}
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            json.dumps(raw_family_policy, sort_keys=True, separators=(",", ":"))
        )
    raw_band = selected_policy.operational_bands[0].canonical_dict() | {"code": 204}
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(raw_band, sort_keys=True, separators=(",", ":")))

    codec_context = {
        "policy": selected_policy, "operator_proofs": selected_proofs, **context,
    }
    raw_input = selected_input.canonical_dict() | {"family": ENTITLEMENT_FAMILY}
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            json.dumps(raw_input, sort_keys=True, separators=(",", ":")), **codec_context,
        )
    raw_projection = projection.canonical_dict() | {"operational_band_code": 204}
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            json.dumps(raw_projection, sort_keys=True, separators=(",", ":")),
            aggregate_input=selected_input, **codec_context,
        )


def test_operator_references_are_only_three_opaque_addresses_and_authenticate_nobody() -> None:
    selected = proofs()
    assert {field.name for field in fields(selected)} == {
        "binding_address", "permission_policy_address", "step_up_proof_address",
    }
    assert set(selected.canonical_dict()) == {
        "contract_type", "contract_version", "binding_address",
        "permission_policy_address", "step_up_proof_address",
    }


def test_all_values_are_frozen_and_copy_roundtrip_is_stable() -> None:
    selected_policy, selected_proofs, selected_input, projection = flow()
    values = (
        *selected_policy.family_policies, *selected_policy.operational_bands,
        selected_policy, selected_proofs, selected_input, projection,
    )
    for value in values:
        assert copy(value) == value
        assert deepcopy(value) == value
        assert replace(value) == value
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)


def test_strict_canonical_codecs_and_exact_context_roundtrip() -> None:
    selected_policy, selected_proofs, selected_input, projection = flow()
    restored_policy = canonical_deserialize(
        selected_policy.canonical_json(), expected_policy_content_id=selected_policy.content_id,
    )
    restored_proofs = canonical_deserialize(
        selected_proofs.canonical_json(),
        expected_binding_address=BINDING,
        expected_permission_policy_address=PERMISSION,
        expected_step_up_proof_address=STEP_UP,
    )
    context = {
        "policy": restored_policy, "operator_proofs": restored_proofs,
        **derivation_context(restored_policy, selected_input.family, selected_input),
    }
    restored_input = canonical_deserialize(selected_input.canonical_json(), **context)
    restored_projection = canonical_deserialize(
        projection.canonical_json(), aggregate_input=restored_input, **context,
    )
    assert [item.content_id for item in (
        restored_policy, restored_proofs, restored_input, restored_projection,
    )] == [item.content_id for item in (
        selected_policy, selected_proofs, selected_input, projection,
    )]


def test_policy_decode_requires_exact_external_identity_and_threshold_context() -> None:
    selected_policy, selected_proofs, selected_input, _ = flow()
    with pytest.raises(ContractValidationError):
        canonical_deserialize(selected_policy.canonical_json())
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            selected_policy.canonical_json(), expected_policy_content_id=address("1"),
        )
    context = {
        "policy": selected_policy, "operator_proofs": selected_proofs,
        **derivation_context(selected_policy, selected_input.family, selected_input),
        "expected_minimum_cohort_threshold": THRESHOLD + 1,
    }
    with pytest.raises(ContractValidationError):
        canonical_deserialize(selected_input.canonical_json(), **context)


@pytest.mark.parametrize("encoded", [
    '{"contract_type":"OperatorProofReferences","contract_type":"OperatorProofReferences"}',
    '{ "contract_type":"ProjectionPolicy"}',
    '{"contract_type":"Unknown","contract_version":1}',
    '{"contract_type":"\\u0050rojectionPolicy","contract_version":1}',
    "[]", "null", "",
])
def test_strict_codec_rejects_duplicates_noncanonical_unicode_shape_and_unknown(encoded: str) -> None:
    with pytest.raises(ContractValidationError):
        canonical_deserialize(encoded)


def test_codec_rejects_size_depth_recursion_version_count_and_time() -> None:
    with pytest.raises(ContractValidationError):
        canonical_deserialize(" " * (MAX_CANONICAL_BYTES + 1))
    deep: object = {"contract_type": "Unknown", "contract_version": 1}
    for _ in range(20):
        deep = {"x": deep}
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(deep, sort_keys=True, separators=(",", ":")))
    selected_policy, selected_proofs, selected_input, _ = flow()
    context = {
        "policy": selected_policy, "operator_proofs": selected_proofs,
        **derivation_context(selected_policy, selected_input.family, selected_input),
    }
    raw = selected_input.canonical_dict()
    for key, value in (
        ("contract_version", 2), ("contract_version", True),
        ("count", True), ("count", -1),
        ("evaluated_at", "2026-09-01T08:30:45.123456+00:00"),
        ("evaluated_at", "2026-09-01T08:30:45Z"),
    ):
        hostile = raw | {key: value}
        encoded = json.dumps(hostile, sort_keys=True, separators=(",", ":"))
        with pytest.raises(ContractValidationError):
            canonical_deserialize(encoded, **context)


def test_fresh_process_restart_preserves_exact_identity() -> None:
    selected_policy, selected_proofs, selected_input, projection = flow()
    payload = json.dumps({
        "policy": selected_policy.canonical_json(),
        "proofs": selected_proofs.canonical_json(),
        "input": selected_input.canonical_json(),
        "projection": projection.canonical_json(),
        "ids": [selected_policy.content_id, selected_proofs.content_id,
                selected_input.content_id, projection.content_id],
    })
    program = r'''
import json, sys
from datetime import datetime
from app.admin.projection_contracts import canonical_deserialize
p=json.loads(sys.stdin.read())
policy=canonical_deserialize(p["policy"], expected_policy_content_id=p["ids"][0])
proofs=canonical_deserialize(p["proofs"], expected_binding_address="sha256:"+"b"*64, expected_permission_policy_address="sha256:"+"c"*64, expected_step_up_proof_address="sha256:"+"d"*64)
context=dict(policy=policy, operator_proofs=proofs, expected_policy_content_id=policy.content_id, expected_binding_address="sha256:"+"b"*64, expected_permission_policy_address="sha256:"+"c"*64, expected_step_up_proof_address="sha256:"+"d"*64, expected_source_receipt_address="sha256:"+"e"*64, expected_family=101, expected_evaluated_at=datetime.fromisoformat("2026-09-01T08:30:45.123456+00:00"), expected_minimum_cohort_threshold=10, expected_aggregate_input_content_id=p["ids"][2])
i=canonical_deserialize(p["input"], **context)
g=canonical_deserialize(p["projection"], aggregate_input=i, **context)
print(json.dumps([policy.content_id, proofs.content_id, i.content_id, g.content_id]))
'''
    completed = subprocess.run(
        [sys.executable, "-c", program], input=payload, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == json.loads(payload)["ids"]


def test_direct_copy_deepcopy_replace_and_object_mutations_fail_at_use_time() -> None:
    for mutation in range(12):
        selected_policy, selected_proofs, selected_input, projection = flow(count=100)
        target: object
        if mutation == 0:
            target = copy(selected_policy)
            object.__setattr__(target, "minimum_cohort_threshold", 101)
        elif mutation == 1:
            target = deepcopy(selected_policy)
            object.__setattr__(
                target.family_policies[0], "allowed_dimension_codes", ("private",),
            )
        elif mutation == 2:
            target = replace(selected_policy)
            object.__setattr__(target.operational_bands[0], "maximum_count", 98)
        elif mutation == 3:
            target = selected_policy
            object.__setattr__(target, "policy_provenance_address", address("9"))
        elif mutation == 4:
            target = copy(selected_proofs)
            object.__setattr__(target, "binding_address", address("8"))
        elif mutation == 5:
            target = deepcopy(selected_proofs)
            object.__setattr__(target, "step_up_proof_address", address("7"))
        elif mutation == 6:
            target = copy(selected_input)
            object.__setattr__(target, "source_receipt_address", address("6"))
        elif mutation == 7:
            target = deepcopy(selected_input)
            object.__setattr__(target, "dimensions", ("support.closed",))
        elif mutation == 8:
            target = replace(selected_input)
            object.__setattr__(target, "count", 101)
        elif mutation == 9:
            target = copy(projection)
            object.__setattr__(target, "publishable", True)
        elif mutation == 10:
            target = deepcopy(projection)
            object.__setattr__(target, "access_activated", True)
        else:
            target = replace(projection)
            object.__setattr__(target, "operational_band_code", "band.9")
        with pytest.raises(ContractValidationError):
            if mutation <= 3:
                clean_policy = policy()
                derive_admin_aggregate_projection(
                    policy=target, operator_proofs=selected_proofs,
                    aggregate_input=selected_input,
                    **derivation_context(
                        clean_policy, ACCOUNT_FAMILY, selected_input,
                    ),
                )
            elif mutation <= 5:
                derive_admin_aggregate_projection(
                    policy=selected_policy, operator_proofs=target,
                    aggregate_input=selected_input,
                    **derivation_context(
                        selected_policy, ACCOUNT_FAMILY, selected_input,
                    ),
                )
            elif mutation <= 8:
                derive_admin_aggregate_projection(
                    policy=selected_policy, operator_proofs=selected_proofs,
                    aggregate_input=target,
                    **derivation_context(
                        selected_policy, ACCOUNT_FAMILY, selected_input,
                    ),
                )
            else:
                validate_admin_aggregate_projection(
                    target, policy=selected_policy, operator_proofs=selected_proofs,
                    aggregate_input=selected_input,
                    **derivation_context(
                        selected_policy, ACCOUNT_FAMILY, selected_input,
                    ),
                )


def test_projection_exact_derivation_rejects_direct_and_replaced_forgery() -> None:
    selected_policy, selected_proofs, selected_input, projection = flow(count=100)
    for hostile in (
        replace(projection, count=101),
        replace(projection, aggregate_input_content_id=address("1")),
        replace(projection, operational_band_code=BAND_LOW),
    ):
        with pytest.raises(ContractValidationError):
            validate_admin_aggregate_projection(
                hostile, policy=selected_policy, operator_proofs=selected_proofs,
                aggregate_input=selected_input,
                **derivation_context(
                    selected_policy, ACCOUNT_FAMILY, selected_input,
                ),
            )


def test_ast_and_import_surface_has_no_protected_dependencies_or_effects() -> None:
    module_path = Path(inspect.getfile(ProjectionPolicy))
    source = module_path.read_text(encoding="utf-8")
    assert "AdminDimensionCode" not in source
    assert "ProjectionFamily" not in source
    tree = ast.parse(source)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert imports <= {
        "__future__", "dataclasses", "datetime", "enum", "functools", "hashlib", "json", "re", "typing",
    }
    calls = {
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert calls.isdisjoint({"open", "print", "exec", "eval", "compile", "input", "__import__"})
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert attributes.isdisjoint({
        "execute", "commit", "publish", "request", "post", "getenv",
        "environ", "now", "utcnow",
    })


def test_100000_decisions_under_30_seconds_and_2_mib_peak() -> None:
    selected_policy, selected_proofs, selected_input, _ = flow(count=100)
    context = derivation_context(
        selected_policy, ACCOUNT_FAMILY, selected_input,
    )
    tracemalloc.start()
    started = time.perf_counter()
    for _ in range(100_000):
        projection = derive_admin_aggregate_projection(
            policy=selected_policy, operator_proofs=selected_proofs,
            aggregate_input=selected_input, **context,
        )
        assert projection.publishable is False
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert elapsed < 30.0
    assert peak <= 2 * 1024 * 1024
