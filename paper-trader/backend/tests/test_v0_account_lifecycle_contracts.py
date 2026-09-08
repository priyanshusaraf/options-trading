from __future__ import annotations

import ast
import copy
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta, timezone
import inspect
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import tracemalloc
import types

import pytest

from app.accounts.lifecycle_contracts import (
    MAX_CANONICAL_BYTES,
    AccountLifecyclePolicy,
    AuthenticatedAccountContext,
    ContractValidationError,
    CurrentAccountAuthority,
    FounderMatchProofReference,
    LifecycleRequestCandidate,
    OperatorBindingCandidate,
    RetainedExceptionCandidate,
    canonical_deserialize,
    create_authenticated_account_context,
    create_current_account_authority,
    create_founder_match_proof_reference,
    create_lifecycle_request_candidate,
    create_operator_binding_candidate,
    create_retained_exception_candidate,
)


NOW = datetime(2026, 9, 1, 5, 30, tzinfo=timezone.utc)
USER_A = "06f82f16-b66f-4dba-8c86-1f9978968f33"
USER_B = "0e3f4ed5-25a3-41c4-a70b-b1ea076d4c86"
TENANT_A = "b0b60adf-e625-4b76-b4cc-eb9ca27328d9"
TENANT_B = "8dc713a1-f964-4313-89ee-1be890df20a9"


def address(character: str) -> str:
    return "sha256:" + character * 64


def policy(**changes: object) -> AccountLifecyclePolicy:
    values: dict[str, object] = {
        "policy_address": address("1"),
        "issuer_classes": ("LOCAL_SESSION",),
        "account_states": ("ACTIVE", "PENDING"),
        "onboarding_steps": ("COMPLETE", "STARTED"),
        "request_types": ("DELETE", "EXPORT"),
        "retained_exception_codes": ("AUDIT_FACT", "OPEN_DISPUTE"),
    }
    values.update(changes)
    return AccountLifecyclePolicy(**values)


def context(current_policy: AccountLifecyclePolicy | None = None, **changes: object) -> AuthenticatedAccountContext:
    current_policy = current_policy or policy()
    values: dict[str, object] = {
        "policy": current_policy,
        "user_id": USER_A,
        "tenant_id": TENANT_A,
        "session_authority_address": address("2"),
        "session_policy_address": address("3"),
        "issuer_class": "LOCAL_SESSION",
        "account_state": "ACTIVE",
        "onboarding_step": "COMPLETE",
        "authenticated_at": NOW,
    }
    values.update(changes)
    return create_authenticated_account_context(**values)


def authority(current_policy: AccountLifecyclePolicy | None = None, **changes: object) -> CurrentAccountAuthority:
    current_policy = current_policy or policy()
    values: dict[str, object] = {
        "policy": current_policy,
        "user_id": USER_A,
        "tenant_id": TENANT_A,
        "session_authority_address": address("2"),
        "session_policy_address": address("3"),
        "issuer_class": "LOCAL_SESSION",
        "account_state": "ACTIVE",
        "onboarding_step": "COMPLETE",
        "authenticated_at": NOW,
    }
    values.update(changes)
    return create_current_account_authority(**values)


def request(
    current_policy: AccountLifecyclePolicy | None = None,
    current_context: AuthenticatedAccountContext | None = None,
    current_authority: CurrentAccountAuthority | None = None,
    **changes: object,
) -> LifecycleRequestCandidate:
    current_policy = current_policy or policy()
    current_context = current_context or context(current_policy)
    current_authority = current_authority or authority(current_policy)
    values: dict[str, object] = {
        "policy": current_policy,
        "context": current_context,
        "current_account_authority": current_authority,
        "expected_authenticated_context_address": current_context.content_id,
        "request_type": "EXPORT",
        "reauth_proof_address": address("4"),
        "reauth_policy_address": address("5"),
        "requested_at": NOW + timedelta(seconds=1),
    }
    values.update(changes)
    return create_lifecycle_request_candidate(**values)


def founder_reference() -> FounderMatchProofReference:
    return create_founder_match_proof_reference(
        match_proof_address=address("6"), match_policy_address=address("7")
    )


def operator(
    current_policy: AccountLifecyclePolicy | None = None,
    current_context: AuthenticatedAccountContext | None = None,
    current_authority: CurrentAccountAuthority | None = None,
    reference: FounderMatchProofReference | None = None,
    **changes: object,
) -> OperatorBindingCandidate:
    current_policy = current_policy or policy()
    current_context = current_context or context(current_policy)
    current_authority = current_authority or authority(current_policy)
    reference = reference or founder_reference()
    values: dict[str, object] = {
        "policy": current_policy,
        "context": current_context,
        "current_account_authority": current_authority,
        "expected_authenticated_context_address": current_context.content_id,
        "founder_reference": reference,
        "match_proof_address": address("6"),
        "match_policy_address": address("7"),
        "permission_policy_address": address("8"),
        "bootstrap_policy_address": address("9"),
        "complimentary_entitlement_candidate_address": address("a"),
        "created_at": NOW + timedelta(seconds=2),
    }
    values.update(changes)
    return create_operator_binding_candidate(**values)


def all_values() -> tuple[object, ...]:
    current_policy = policy()
    current_authority = authority(current_policy)
    current_context = context(current_policy)
    current_request = request(current_policy, current_context, current_authority)
    retained = create_retained_exception_candidate(
        policy=current_policy,
        context=current_context,
        current_account_authority=current_authority,
        expected_authenticated_context_address=current_context.content_id,
        request=current_request,
        reauth_proof_address=address("4"),
        reauth_policy_address=address("5"),
        expected_requested_at=NOW + timedelta(seconds=1),
        exception_codes=("AUDIT_FACT",),
        evaluated_at=NOW + timedelta(seconds=2),
    )
    reference = founder_reference()
    return current_policy, current_authority, current_context, current_request, retained, reference, operator(current_policy, current_context, current_authority, reference)


def decode(value: object, **changes: object) -> object:
    current_policy, current_authority, current_context, current_request, _, reference, _ = all_values()
    arguments: dict[str, object] = {
        "current_policy": current_policy,
        "current_account_authority": current_authority,
    }
    if isinstance(value, CurrentAccountAuthority):
        pass
    elif isinstance(value, AuthenticatedAccountContext):
        arguments["expected_context"] = current_context
        arguments["expected_authenticated_context_address"] = current_context.content_id
    elif isinstance(value, LifecycleRequestCandidate):
        arguments.update(expected_context=current_context, expected_authenticated_context_address=current_context.content_id, reauth_proof_address=address("4"), reauth_policy_address=address("5"), expected_requested_at=NOW + timedelta(seconds=1))
    elif isinstance(value, RetainedExceptionCandidate):
        arguments.update(
            expected_context=current_context,
            expected_authenticated_context_address=current_context.content_id,
            expected_request=current_request,
            reauth_proof_address=address("4"),
            reauth_policy_address=address("5"),
            expected_requested_at=NOW + timedelta(seconds=1),
            expected_evaluated_at=NOW + timedelta(seconds=2),
        )
    elif isinstance(value, FounderMatchProofReference):
        arguments.update(match_proof_address=address("6"), match_policy_address=address("7"))
    elif isinstance(value, OperatorBindingCandidate):
        arguments.update(
            expected_context=current_context,
            expected_authenticated_context_address=current_context.content_id,
            expected_founder_reference=reference,
            match_proof_address=address("6"),
            match_policy_address=address("7"),
            permission_policy_address=address("8"),
            bootstrap_policy_address=address("9"),
            complimentary_entitlement_candidate_address=address("a"),
            expected_created_at=NOW + timedelta(seconds=2),
        )
    arguments.update(changes)
    return canonical_deserialize(value.canonical_json(), **arguments)


def test_positive_local_context_export_delete_exception_and_founder_candidates() -> None:
    current_policy, current_authority, current_context, export, retained, reference, binding = all_values()
    deletion = request(current_policy, current_context, current_authority, request_type="DELETE")
    assert export.effected is deletion.effected is retained.effected is False
    assert binding.slot == "FOUNDER" and binding.activated is False
    assert binding.complimentary_entitlement_candidate_address == address("a")
    assert reference.canonical_dict() == {
        "contract_type": "FounderMatchProofReference",
        "contract_version": 1,
        "match_proof_address": address("6"),
        "match_policy_address": address("7"),
    }
    assert all(decode(value) == value for value in all_values())


def test_no_factory_has_policy_time_or_proof_defaults() -> None:
    factories = (
        create_authenticated_account_context,
        create_current_account_authority,
        create_lifecycle_request_candidate,
        create_retained_exception_candidate,
        create_founder_match_proof_reference,
        create_operator_binding_candidate,
    )
    for factory in factories:
        assert all(parameter.default is inspect.Parameter.empty for parameter in inspect.signature(factory).parameters.values())


@pytest.mark.parametrize(
    "change",
    [
        {"user_id": USER_B},
        {"tenant_id": TENANT_B},
        {"session_authority_address": address("b")},
        {"session_policy_address": address("c")},
        {"issuer_class": "OTHER"},
        {"account_state": "PENDING"},
        {"onboarding_step": "STARTED"},
        {"authenticated_at": NOW + timedelta(microseconds=1)},
    ],
)
def test_context_answer_fields_change_identity_or_refuse(change: dict[str, object]) -> None:
    original = context()
    if change == {"issuer_class": "OTHER"}:
        with pytest.raises(ContractValidationError):
            context(**change)
    else:
        assert context(**change).content_id != original.content_id


def test_every_policy_catalogue_changes_identity_and_invalidates_old_context() -> None:
    original_policy = policy()
    original_context = context(original_policy)
    for changed in (
        policy(policy_address=address("b")),
        policy(issuer_classes=("LOCAL_SESSION", "OTHER")),
        policy(account_states=("ACTIVE",)),
        policy(onboarding_steps=("COMPLETE",)),
        policy(request_types=("EXPORT",)),
        policy(retained_exception_codes=("AUDIT_FACT",)),
    ):
        assert changed.content_id != original_policy.content_id
        with pytest.raises(ContractValidationError):
            create_lifecycle_request_candidate(
                policy=changed, context=original_context,
                current_account_authority=authority(original_policy),
                expected_authenticated_context_address=original_context.content_id, request_type="EXPORT",
                reauth_proof_address=address("4"), reauth_policy_address=address("5"), requested_at=NOW,
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("authenticated_context_address", address("b")),
        ("lifecycle_policy_id", address("b")),
        ("user_id", USER_B),
        ("tenant_id", TENANT_B),
        ("session_authority_address", address("b")),
        ("request_type", "DELETE"),
        ("reauth_proof_address", address("b")),
        ("reauth_policy_address", address("b")),
        ("requested_at", NOW + timedelta(seconds=9)),
    ],
)
def test_request_answer_fields_change_identity_and_use_time_substitutions_refuse(field: str, value: object) -> None:
    original = request()
    changed = replace(original, **{field: value})
    assert changed.content_id != original.content_id
    if field != "request_type":
        with pytest.raises(ContractValidationError):
            canonical_deserialize(
                changed.canonical_json(), current_policy=policy(), expected_context=context(),
                expected_authenticated_context_address=context().content_id,
                reauth_proof_address=address("4"), reauth_policy_address=address("5"),
                expected_requested_at=NOW + timedelta(seconds=1),
            )


def test_founder_permission_bootstrap_proof_and_complimentary_substitution_refuse() -> None:
    original = operator()
    cases = {
        "founder_match_reference_address": address("b"),
        "permission_policy_address": address("b"),
        "bootstrap_policy_address": address("b"),
        "complimentary_entitlement_candidate_address": address("b"),
        "user_id": USER_B,
        "authenticated_context_address": address("b"),
    }
    for field, value in cases.items():
        changed = replace(original, **{field: value})
        assert changed.content_id != original.content_id
        with pytest.raises(ContractValidationError):
            decode(changed)
    with pytest.raises(ContractValidationError):
        operator(match_proof_address=address("b"))


def test_complimentary_reference_is_optional_separate_and_nonactivating() -> None:
    without = operator(complimentary_entitlement_candidate_address=None)
    assert without.complimentary_entitlement_candidate_address is None
    payload = without.canonical_json().lower()
    for forbidden in ("payment", "coupon", "price", "membership", "access_activated"):
        assert forbidden not in payload
    with pytest.raises(ContractValidationError):
        replace(without, activated=True)


def test_retained_exception_has_no_duration_promise_and_is_request_bound() -> None:
    _, _, _, current_request, retained, _, _ = all_values()
    names = {field.name for field in fields(retained)}
    assert not names & {"duration", "expires_at", "retained_until", "promise", "legal_basis"}
    assert retained.lifecycle_request_address == current_request.content_id
    with pytest.raises(ContractValidationError):
        decode(replace(retained, lifecycle_request_address=address("b")))
    with pytest.raises(ContractValidationError):
        create_retained_exception_candidate(
            policy=policy(), context=context(), current_account_authority=authority(),
            expected_authenticated_context_address=context().content_id,
            request=request(),
            reauth_proof_address=address("4"), reauth_policy_address=address("5"),
            expected_requested_at=NOW + timedelta(seconds=1),
            exception_codes=("UNKNOWN",), evaluated_at=NOW,
        )


def test_frozen_copy_deepcopy_and_replace_are_revalidated_at_use() -> None:
    for value in all_values():
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)
        assert copy.copy(value) == value
        assert copy.deepcopy(value) == value
    copied = copy.deepcopy(request())
    assert decode(copied) == copied
    with pytest.raises(ContractValidationError):
        decode(replace(copied, reauth_proof_address=address("b")))


def test_object_level_mutations_are_caught_at_each_use_site_and_restored() -> None:
    current_policy = policy()
    current_context = context(current_policy)
    original = current_context.session_authority_address
    object.__setattr__(current_context, "session_authority_address", address("b"))
    try:
        with pytest.raises(ContractValidationError):
            request(current_policy, current_context, expected_authenticated_context_address=address("0"))
        with pytest.raises(ContractValidationError):
            operator(current_policy, current_context, expected_authenticated_context_address=address("0"))
    finally:
        object.__setattr__(current_context, "session_authority_address", original)
    assert request(current_policy, current_context).session_authority_address == original


@pytest.mark.parametrize("bad_version", [True, False, 1.0, "1", 0, 2])
def test_contract_version_requires_exact_builtin_integer_one(bad_version: object) -> None:
    raw = policy().canonical_dict()
    raw["contract_version"] = bad_version
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(raw, sort_keys=True, separators=(",", ":")))


def test_strict_codec_rejects_duplicate_noncanonical_extra_unicode_size_depth_and_recursion() -> None:
    encoded = policy().canonical_json()
    duplicate = encoded[:-1] + ',"contract_type":"AccountLifecyclePolicy"}'
    hostile = [
        duplicate,
        " " + encoded,
        encoded.replace('"policy_address":', '"extra":false,"policy_address":'),
        encoded.replace("AccountLifecyclePolicy", "AccountLifecyclePol\\u0069cy"),
        "[" * 20 + "0" + "]" * 20,
        "[" * 2000 + "0" + "]" * 2000,
        "x" * (MAX_CANONICAL_BYTES + 1),
    ]
    for item in hostile:
        with pytest.raises(ContractValidationError):
            canonical_deserialize(item)


@pytest.mark.parametrize(
    "bad",
    [
        "06F82F16-B66F-4DBA-8C86-1F9978968F33",
        "06f82f16b66f4dba8c861f9978968f33",
        "00000000-0000-0000-0000-000000000000",
        "not-a-uuid",
    ],
)
def test_user_and_tenant_ids_are_opaque_canonical_rfc4122_values(bad: str) -> None:
    with pytest.raises(ContractValidationError):
        context(user_id=bad)
    with pytest.raises(ContractValidationError):
        context(tenant_id=bad)


def test_times_are_injected_canonical_utc_and_identity_bearing() -> None:
    with pytest.raises(ContractValidationError):
        context(authenticated_at=datetime(2026, 9, 1))
    with pytest.raises(ContractValidationError):
        request(requested_at=datetime(2026, 9, 1, tzinfo=timezone(timedelta(hours=1))))
    assert request(requested_at=NOW).content_id != request(requested_at=NOW + timedelta(microseconds=1)).content_id


def test_restart_round_trip_has_stable_bytes_and_content_ids() -> None:
    value = operator()
    script = """
from app.accounts.lifecycle_contracts import *
from datetime import datetime, timezone
p=AccountLifecyclePolicy(policy_address='sha256:'+'1'*64,issuer_classes=('LOCAL_SESSION',),account_states=('ACTIVE','PENDING'),onboarding_steps=('COMPLETE','STARTED'),request_types=('DELETE','EXPORT'),retained_exception_codes=('AUDIT_FACT','OPEN_DISPUTE'))
c=create_authenticated_account_context(policy=p,user_id='06f82f16-b66f-4dba-8c86-1f9978968f33',tenant_id='b0b60adf-e625-4b76-b4cc-eb9ca27328d9',session_authority_address='sha256:'+'2'*64,session_policy_address='sha256:'+'3'*64,issuer_class='LOCAL_SESSION',account_state='ACTIVE',onboarding_step='COMPLETE',authenticated_at=datetime(2026,9,1,5,30,tzinfo=timezone.utc))
a=create_current_account_authority(policy=p,user_id='06f82f16-b66f-4dba-8c86-1f9978968f33',tenant_id='b0b60adf-e625-4b76-b4cc-eb9ca27328d9',session_authority_address='sha256:'+'2'*64,session_policy_address='sha256:'+'3'*64,issuer_class='LOCAL_SESSION',account_state='ACTIVE',onboarding_step='COMPLETE',authenticated_at=datetime(2026,9,1,5,30,tzinfo=timezone.utc))
f=create_founder_match_proof_reference(match_proof_address='sha256:'+'6'*64,match_policy_address='sha256:'+'7'*64)
o=create_operator_binding_candidate(policy=p,context=c,current_account_authority=a,expected_authenticated_context_address=c.content_id,founder_reference=f,match_proof_address='sha256:'+'6'*64,match_policy_address='sha256:'+'7'*64,permission_policy_address='sha256:'+'8'*64,bootstrap_policy_address='sha256:'+'9'*64,complimentary_entitlement_candidate_address='sha256:'+'a'*64,created_at=datetime(2026,9,1,5,30,2,tzinfo=timezone.utc))
print(o.canonical_json()); print(o.content_id)
"""
    result = subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True)
    assert result.stdout.splitlines() == [value.canonical_json(), value.content_id]


def test_ast_signatures_imports_and_fields_preserve_fact_separation() -> None:
    module_path = Path(__file__).parents[1] / "app/accounts/lifecycle_contracts.py"
    tree = ast.parse(module_path.read_text())
    imports = {
        (node.module or "").split(".")[0] if isinstance(node, ast.ImportFrom) else alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imports <= {"__future__", "dataclasses", "datetime", "hashlib", "json", "re", "typing", "uuid"}
    forbidden_fields = {
        "email", "phone", "password", "verifier", "invite", "session_token", "reset_token",
        "recovery_token", "cookie", "profile", "free_text", "operator_flag", "provider",
        "payment", "coupon", "membership", "product_id", "account_number", "balance", "pnl",
    }
    declared = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        for target in (node.target,)
    }
    assert not (declared & forbidden_fields)
    assert not any(isinstance(node, (ast.AsyncFunctionDef, ast.With, ast.AsyncWith)) for node in ast.walk(tree))


def test_self_attested_user_b_context_refuses_against_independent_account_a_authority() -> None:
    selected = policy()
    account_a = authority(selected)
    account_b_context = context(
        selected, user_id=USER_B, tenant_id=TENANT_B,
        session_authority_address=address("b"), session_policy_address=address("c"),
        authenticated_at=NOW + timedelta(seconds=9),
    )
    account_b_authority = authority(
        selected, user_id=USER_B, tenant_id=TENANT_B,
        session_authority_address=address("b"), session_policy_address=address("c"),
        authenticated_at=NOW + timedelta(seconds=9),
    )
    assert account_b_context.content_id != context(selected).content_id
    for copied_context in (
        account_b_context,
        copy.copy(account_b_context),
        copy.deepcopy(account_b_context),
        replace(account_b_context),
    ):
        with pytest.raises(ContractValidationError):
            request(selected, copied_context, account_a)
        with pytest.raises(ContractValidationError):
            operator(selected, copied_context, account_a)
    account_b_request = request(selected, account_b_context, account_b_authority)
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            account_b_request.canonical_json(), current_policy=selected,
            current_account_authority=account_a,
            expected_context=account_b_context,
            expected_authenticated_context_address=account_b_context.content_id,
            reauth_proof_address=address("4"), reauth_policy_address=address("5"),
            expected_requested_at=NOW + timedelta(seconds=1),
        )
    account_b_operator = operator(selected, account_b_context, account_b_authority)
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            account_b_operator.canonical_json(), current_policy=selected,
            current_account_authority=account_a,
            expected_context=account_b_context,
            expected_authenticated_context_address=account_b_context.content_id,
            expected_founder_reference=founder_reference(),
            match_proof_address=address("6"), match_policy_address=address("7"),
            permission_policy_address=address("8"), bootstrap_policy_address=address("9"),
            complimentary_entitlement_candidate_address=address("a"),
            expected_created_at=NOW + timedelta(seconds=2),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", USER_B),
        ("tenant_id", TENANT_B),
        ("session_authority_address", address("b")),
        ("session_policy_address", address("c")),
        ("issuer_class", "OTHER_ISSUER"),
        ("account_state", "PENDING"),
        ("onboarding_step", "STARTED"),
        ("authenticated_at", NOW + timedelta(seconds=1)),
    ],
)
def test_each_independent_current_authority_fact_must_match_context(field: str, value: object) -> None:
    selected = policy(issuer_classes=("LOCAL_SESSION", "OTHER_ISSUER"))
    current_context = context(selected)
    changed_authority = replace(authority(selected), **{field: value})
    with pytest.raises(ContractValidationError):
        request(selected, current_context, changed_authority)
    with pytest.raises(ContractValidationError):
        operator(selected, current_context, changed_authority)


def test_object_mutated_independent_authority_refuses_and_restores() -> None:
    selected = policy()
    current_context = context(selected)
    current_authority = authority(selected)
    original = current_authority.session_authority_address
    object.__setattr__(current_authority, "session_authority_address", address("b"))
    try:
        with pytest.raises(ContractValidationError):
            request(selected, current_context, current_authority)
    finally:
        object.__setattr__(current_authority, "session_authority_address", original)
    assert request(selected, current_context, current_authority).effected is False


def test_retained_factory_rejects_copy_replace_and_object_mutated_request_time() -> None:
    selected = policy()
    current_authority = authority(selected)
    current_context = context(selected)
    valid_request = request(selected, current_context, current_authority)

    def retain(candidate: LifecycleRequestCandidate) -> RetainedExceptionCandidate:
        return create_retained_exception_candidate(
            policy=selected, context=current_context,
            current_account_authority=current_authority,
            expected_authenticated_context_address=current_context.content_id,
            request=candidate, reauth_proof_address=address("4"),
            reauth_policy_address=address("5"),
            expected_requested_at=NOW + timedelta(seconds=1),
            exception_codes=("AUDIT_FACT",), evaluated_at=NOW + timedelta(seconds=2),
        )

    assert retain(copy.copy(valid_request)).effected is False
    assert retain(copy.deepcopy(valid_request)).effected is False
    changed = replace(valid_request, requested_at=NOW + timedelta(seconds=99))
    with pytest.raises(ContractValidationError):
        retain(changed)
    original = valid_request.requested_at
    object.__setattr__(valid_request, "requested_at", NOW + timedelta(seconds=99))
    try:
        with pytest.raises(ContractValidationError):
            retain(valid_request)
    finally:
        object.__setattr__(valid_request, "requested_at", original)
    assert retain(valid_request).lifecycle_request_address == valid_request.content_id


def test_retained_decode_fully_revalidates_direct_copy_replace_and_mutated_request_sources() -> None:
    _, _, _, valid_request, retained, _, _ = all_values()
    direct_open = LifecycleRequestCandidate(
        authenticated_context_address=valid_request.authenticated_context_address,
        lifecycle_policy_id=valid_request.lifecycle_policy_id,
        user_id=valid_request.user_id, tenant_id=valid_request.tenant_id,
        session_authority_address=valid_request.session_authority_address,
        request_type="OTHER", reauth_proof_address=valid_request.reauth_proof_address,
        reauth_policy_address=valid_request.reauth_policy_address,
        requested_at=valid_request.requested_at, effected=False,
    )
    for invalid in (direct_open, copy.copy(direct_open), copy.deepcopy(direct_open), replace(direct_open)):
        invalid_retained = replace(retained, lifecycle_request_address=invalid.content_id)
        with pytest.raises(ContractValidationError):
            decode(invalid_retained, expected_request=invalid)
    original = valid_request.effected
    object.__setattr__(valid_request, "effected", True)
    try:
        invalid_retained = replace(retained, lifecycle_request_address=valid_request.content_id)
        with pytest.raises(ContractValidationError):
            decode(invalid_retained, expected_request=valid_request)
    finally:
        object.__setattr__(valid_request, "effected", original)
    assert decode(retained) == retained


def _expect_mutant_refusal(call: object) -> None:
    try:
        call()
    except ValueError:
        return
    raise AssertionError("permissive mutant accepted an invalid lifecycle fact")


def _run_mutation_vector(module: types.ModuleType) -> None:
    selected = module.AccountLifecyclePolicy(
        policy_address=address("1"), issuer_classes=("LOCAL_SESSION",),
        account_states=("ACTIVE", "PENDING"), onboarding_steps=("COMPLETE", "STARTED"),
        request_types=("DELETE", "EXPORT"), retained_exception_codes=("AUDIT_FACT", "OPEN_DISPUTE"),
    )
    authenticated = module.create_authenticated_account_context(
        policy=selected, user_id=USER_A, tenant_id=TENANT_A,
        session_authority_address=address("2"), session_policy_address=address("3"),
        issuer_class="LOCAL_SESSION", account_state="ACTIVE", onboarding_step="COMPLETE",
        authenticated_at=NOW,
    )
    current_authority = module.create_current_account_authority(
        policy=selected, user_id=USER_A, tenant_id=TENANT_A,
        session_authority_address=address("2"), session_policy_address=address("3"),
        issuer_class="LOCAL_SESSION", account_state="ACTIVE", onboarding_step="COMPLETE",
        authenticated_at=NOW,
    )
    authenticated_address = authenticated.content_id
    _expect_mutant_refusal(lambda: module.create_lifecycle_request_candidate(
        policy=selected, context=authenticated, current_account_authority=current_authority,
        expected_authenticated_context_address=address("b"), request_type="EXPORT",
        reauth_proof_address=address("4"), reauth_policy_address=address("5"), requested_at=NOW,
    ))
    altered_context = replace(authenticated, session_authority_address=address("b"))
    _expect_mutant_refusal(lambda: module.create_lifecycle_request_candidate(
        policy=selected, context=altered_context, current_account_authority=current_authority,
        expected_authenticated_context_address=authenticated_address, request_type="EXPORT",
        reauth_proof_address=address("4"), reauth_policy_address=address("5"), requested_at=NOW,
    ))
    altered_policy = replace(selected, policy_address=address("b"))
    _expect_mutant_refusal(lambda: module.create_lifecycle_request_candidate(
        policy=altered_policy, context=authenticated, current_account_authority=current_authority,
        expected_authenticated_context_address=authenticated_address, request_type="EXPORT",
        reauth_proof_address=address("4"), reauth_policy_address=address("5"), requested_at=NOW,
    ))
    valid_request = module.create_lifecycle_request_candidate(
        policy=selected, context=authenticated, current_account_authority=current_authority,
        expected_authenticated_context_address=authenticated_address, request_type="EXPORT",
        reauth_proof_address=address("4"), reauth_policy_address=address("5"), requested_at=NOW,
    )
    forged_request = replace(valid_request, authenticated_context_address=address("b"))
    _expect_mutant_refusal(lambda: module.canonical_deserialize(
        forged_request.canonical_json(), current_policy=selected,
        current_account_authority=current_authority,
        expected_context=authenticated, expected_authenticated_context_address=authenticated_address,
        reauth_proof_address=address("4"), reauth_policy_address=address("5"), expected_requested_at=NOW,
    ))
    open_request = replace(valid_request, request_type="OTHER")
    _expect_mutant_refusal(lambda: module.canonical_deserialize(
        open_request.canonical_json(), current_policy=selected,
        current_account_authority=current_authority,
        expected_context=authenticated, expected_authenticated_context_address=authenticated_address,
        reauth_proof_address=address("4"), reauth_policy_address=address("5"), expected_requested_at=NOW,
    ))
    reference = module.create_founder_match_proof_reference(
        match_proof_address=address("6"), match_policy_address=address("7")
    )
    base_operator = dict(
        policy=selected, context=authenticated, current_account_authority=current_authority,
        expected_authenticated_context_address=authenticated_address,
        founder_reference=reference, match_proof_address=address("6"), match_policy_address=address("7"),
        permission_policy_address=address("8"), bootstrap_policy_address=address("9"),
        complimentary_entitlement_candidate_address=address("a"), created_at=NOW,
    )
    _expect_mutant_refusal(lambda: module.create_operator_binding_candidate(
        **{**base_operator, "match_proof_address": address("b")}
    ))
    _expect_mutant_refusal(lambda: module.create_operator_binding_candidate(
        **{**base_operator, "match_policy_address": address("b")}
    ))
    valid_operator = module.create_operator_binding_candidate(**base_operator)
    forged_operator = replace(valid_operator, permission_policy_address=address("b"))
    _expect_mutant_refusal(lambda: module.canonical_deserialize(
        forged_operator.canonical_json(), current_policy=selected,
        current_account_authority=current_authority,
        expected_context=authenticated, expected_authenticated_context_address=authenticated_address,
        expected_founder_reference=reference, match_proof_address=address("6"), match_policy_address=address("7"),
        permission_policy_address=address("8"), bootstrap_policy_address=address("9"),
        complimentary_entitlement_candidate_address=address("a"), expected_created_at=NOW,
    ))
    _expect_mutant_refusal(lambda: module.LifecycleRequestCandidate(
        authenticated_context_address=authenticated_address, lifecycle_policy_id=selected.content_id,
        user_id=USER_A, tenant_id=TENANT_A, session_authority_address=address("2"),
        request_type="EXPORT", reauth_proof_address=address("4"), reauth_policy_address=address("5"),
        requested_at=NOW, effected=True,
    ))
    _expect_mutant_refusal(lambda: module.canonical_deserialize(" " + selected.canonical_json()))
    forged_authority = replace(current_authority, lifecycle_policy_id=address("b"))
    _expect_mutant_refusal(lambda: module.canonical_deserialize(
        forged_authority.canonical_json(), current_policy=selected,
        current_account_authority=forged_authority,
    ))

    substituted_context = module.create_authenticated_account_context(
        policy=selected, user_id=USER_B, tenant_id=TENANT_B,
        session_authority_address=address("b"), session_policy_address=address("c"),
        issuer_class="LOCAL_SESSION", account_state="ACTIVE", onboarding_step="COMPLETE",
        authenticated_at=NOW,
    )
    _expect_mutant_refusal(lambda: module.create_lifecycle_request_candidate(
        policy=selected, context=substituted_context,
        current_account_authority=current_authority,
        expected_authenticated_context_address=substituted_context.content_id,
        request_type="EXPORT", reauth_proof_address=address("4"),
        reauth_policy_address=address("5"), requested_at=NOW,
    ))
    time_changed_request = replace(valid_request, requested_at=NOW + timedelta(seconds=99))
    _expect_mutant_refusal(lambda: module.create_retained_exception_candidate(
        policy=selected, context=authenticated,
        current_account_authority=current_authority,
        expected_authenticated_context_address=authenticated_address,
        request=time_changed_request, reauth_proof_address=address("4"),
        reauth_policy_address=address("5"), expected_requested_at=NOW,
        exception_codes=("AUDIT_FACT",), evaluated_at=NOW,
    ))
    invalid_retained = module.RetainedExceptionCandidate(
        lifecycle_request_address=open_request.content_id,
        lifecycle_policy_id=selected.content_id,
        exception_codes=("AUDIT_FACT",), evaluated_at=NOW, effected=False,
    )
    _expect_mutant_refusal(lambda: module.canonical_deserialize(
        invalid_retained.canonical_json(), current_policy=selected,
        current_account_authority=current_authority,
        expected_context=authenticated,
        expected_authenticated_context_address=authenticated_address,
        expected_request=open_request, reauth_proof_address=address("4"),
        reauth_policy_address=address("5"), expected_requested_at=NOW,
        expected_evaluated_at=NOW,
    ))


def test_twelve_isolated_permissive_mutations_are_killed_and_source_is_restored() -> None:
    source_path = Path(__file__).parents[1] / "app/accounts/lifecycle_contracts.py"
    source = source_path.read_text(encoding="utf-8")
    before = hashlib.sha256(source.encode()).hexdigest()
    mutations = (
        ('if context.content_id != _content_address(', 'if False and context.content_id != _content_address('),
        ('if authority.lifecycle_policy_id != policy.content_id:', 'if False:'),
        ('if actual != expected:\n        raise ContractValidationError("request does not match current context, policy, or reauth proof")', 'if False:\n        raise ContractValidationError("request does not match current context, policy, or reauth proof")'),
        ('_member(request.request_type, policy.request_types, "request_type")', '_strict_code(request.request_type, "request_type")'),
        ('if reference.match_proof_address != _content_address(match_proof_address, "match_proof_address"):', 'if False:'),
        ('if reference.match_policy_address != _content_address(match_policy_address, "match_policy_address"):', 'if False:'),
        ('if actual != expected:\n        raise ContractValidationError("operator candidate does not match current context or proof policies")', 'if False:\n        raise ContractValidationError("operator candidate does not match current context or proof policies")'),
        ('if type(value) is not bool or value is not False:', 'if False:'),
        ('if _canonical_json(raw) != encoded:', 'if False:'),
        ('if actual_context != expected_authority:', 'if False:'),
        ('if request.requested_at != _utc(expected_requested_at, "expected_requested_at"):', 'if False:'),
        ('''        _validate_request(
            expected_request, current_policy, expected_context,
            current_account_authority, expected_authenticated_context_address,
            reauth_proof_address, reauth_policy_address,
            expected_requested_at,
        )
''', ''),
    )
    for index, (needle, replacement) in enumerate(mutations):
        assert source.count(needle) == 1
        mutated = source.replace(needle, replacement, 1)
        name = f"isolated_account_lifecycle_mutant_{index}"
        module = types.ModuleType(name)
        module.__file__ = str(source_path)
        sys.modules[name] = module
        try:
            exec(compile(mutated, str(source_path), "exec"), module.__dict__)
            try:
                _run_mutation_vector(module)
            except AssertionError:
                pass
            else:
                pytest.fail(f"mutation {index} was not killed")
        finally:
            sys.modules.pop(name, None)
    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before


def test_one_hundred_thousand_pure_decisions_fit_time_and_memory_bounds() -> None:
    current_policy = policy()
    current_authority = authority(current_policy)
    current_context = context(current_policy)
    started = time.perf_counter()
    for _ in range(100_000):
        candidate = create_lifecycle_request_candidate(
            policy=current_policy, context=current_context,
            current_account_authority=current_authority,
            expected_authenticated_context_address=current_context.content_id, request_type="EXPORT",
            reauth_proof_address=address("4"), reauth_policy_address=address("5"), requested_at=NOW,
        )
        assert candidate.effected is False
    elapsed = time.perf_counter() - started
    tracemalloc.start()
    for _ in range(1_000):
        create_lifecycle_request_candidate(
            policy=current_policy, context=current_context,
            current_account_authority=current_authority,
            expected_authenticated_context_address=current_context.content_id, request_type="EXPORT",
            reauth_proof_address=address("4"), reauth_policy_address=address("5"), requested_at=NOW,
        )
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert elapsed < 30
    assert peak < 2 * 1024 * 1024
