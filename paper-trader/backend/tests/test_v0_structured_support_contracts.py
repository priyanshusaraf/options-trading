from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import time
import tracemalloc
import types
from uuid import UUID

import pytest

from app.support.contracts import (
    MAX_CANONICAL_BYTES,
    MAX_COLLECTION_ITEMS,
    MAX_IDENTIFIER_LENGTH,
    BooleanAnswer,
    BooleanAnswerDomain,
    ContractValidationError,
    EnumAnswer,
    EnumAnswerDomain,
    IntegerAnswer,
    IntegerAnswerDomain,
    Severity,
    StatusTransition,
    SupportPolicy,
    SupportStatus,
    canonical_deserialize,
    create_analytics_dimensions,
    create_in_app_delivery_candidate,
    create_operator_action_candidate,
    create_operator_projection,
    create_submission_candidate,
)


NOW = datetime(2026, 9, 1, 6, 30, tzinfo=timezone.utc)
CASE_A = UUID("10000000-0000-4000-8000-000000000001")
CASE_B = UUID("10000000-0000-4000-8000-000000000002")
ACCOUNT_A = UUID("20000000-0000-4000-8000-000000000001")
ACCOUNT_B = UUID("20000000-0000-4000-8000-000000000002")
TENANT_A = UUID("30000000-0000-4000-8000-000000000001")
TENANT_B = UUID("30000000-0000-4000-8000-000000000002")
CONTRACTS_PATH = Path(__file__).parents[1] / "app" / "support" / "contracts.py"


def policy() -> SupportPolicy:
    transitions = tuple(sorted((
        StatusTransition(SupportStatus.SUBMITTED, SupportStatus.REVIEWING),
        StatusTransition(SupportStatus.REVIEWING, SupportStatus.RESPONDED),
        StatusTransition(SupportStatus.RESPONDED, SupportStatus.CLOSED),
    ), key=lambda item: (item.from_status.value, item.to_status.value)))
    return SupportPolicy(
        policy_id="support.policy.synthetic.v1",
        category_ids=("account-access", "product-use"),
        product_area_ids=("builder", "research"),
        route_template_ids=("desktop.account", "desktop.builder"),
        component_ids=("account.session", "builder.canvas"),
        build_ids=("build.synthetic.20260901",),
        context_ids=("blocked-workflow", "general-guidance"),
        answer_domains=(
            BooleanAnswerDomain("confirmed"),
            IntegerAnswerDomain("frequency", 0, 20),
            EnumAnswerDomain("outcome", ("blocked", "degraded")),
        ),
        response_template_ids=("response.acknowledged", "response.resolved"),
        status_transitions=transitions,
    )


def answers() -> tuple[BooleanAnswer | IntegerAnswer | EnumAnswer, ...]:
    return (
        BooleanAnswer("confirmed", True),
        IntegerAnswer("frequency", 3),
        EnumAnswer("outcome", "blocked"),
    )


def submission(selected_policy: SupportPolicy | None = None):
    return create_submission_candidate(
        policy=selected_policy or policy(), support_case_id=CASE_A,
        account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A,
        category_id="product-use", product_area_id="builder",
        route_template_id="desktop.builder", component_id="builder.canvas",
        build_id="build.synthetic.20260901", context_id="blocked-workflow",
        severity=Severity.BLOCKING, typed_answers=answers(), created_at=NOW,
    )


def flow():
    selected_policy = policy()
    submitted = submission(selected_policy)
    projected = create_operator_projection(
        policy=selected_policy, submission=submitted,
        account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A,
    )
    assert projected is not None
    action = create_operator_action_candidate(
        policy=selected_policy, projection=projected, support_case_id=CASE_A,
        account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A,
        status=SupportStatus.REVIEWING,
        response_template_id="response.acknowledged",
        acted_at=NOW + timedelta(seconds=1),
    )
    assert action is not None
    delivery = create_in_app_delivery_candidate(
        policy=selected_policy, projection=projected, action=action, support_case_id=CASE_A,
        account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A,
    )
    assert delivery is not None
    dimensions = create_analytics_dimensions(
        policy=selected_policy, projection=projected, action=action,
    )
    return selected_policy, submitted, projected, action, delivery, dimensions


def all_values() -> tuple[object, ...]:
    selected_policy, submitted, projected, action, delivery, dimensions = flow()
    return (
        *selected_policy.answer_domains, *answers(), *selected_policy.status_transitions,
        selected_policy, submitted, projected, action, delivery, dimensions,
    )


def test_legitimate_closed_flow_is_useful_and_non_effecting() -> None:
    selected_policy, submitted, projected, action, delivery, dimensions = flow()
    assert submitted.policy_content_id == selected_policy.content_id
    assert projected.typed_answers == answers()
    assert action.status is SupportStatus.REVIEWING
    assert delivery.delivery_effected is False
    assert dimensions.canonical_dict() == {
        "contract_type": "AnalyticsDimensionsCandidate", "contract_version": 1,
        "category_id": "product-use", "product_area_id": "builder",
        "severity": "BLOCKING", "status": "REVIEWING",
    }


def test_every_contract_is_frozen_and_has_exact_canonical_roundtrip() -> None:
    selected_policy, _, projected, action, _, _ = flow()
    for value in all_values():
        encoded = value.canonical_json()
        kwargs = {"policy": selected_policy} if value.contract_type in {
            "SubmissionCandidate", "OperatorProjection", "OperatorActionCandidate",
            "InAppDeliveryCandidate", "AnalyticsDimensionsCandidate",
        } else {}
        if value.contract_type in {"OperatorActionCandidate", "InAppDeliveryCandidate", "AnalyticsDimensionsCandidate"}:
            kwargs["projection"] = projected
        if value.contract_type in {"InAppDeliveryCandidate", "AnalyticsDimensionsCandidate"}:
            kwargs["action"] = action
        restored = canonical_deserialize(encoded, **kwargs)
        assert restored == value
        assert restored.content_id == value.content_id
        assert restored.canonical_json() == encoded
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)


def test_fresh_interpreter_restart_roundtrip_is_exact() -> None:
    program = """
import json, sys
from app.support.contracts import canonical_deserialize
payload = json.loads(sys.stdin.read())
injected = canonical_deserialize(payload['policy'])
projection = None
action = None
for encoded in payload['values']:
    kind = json.loads(encoded)['contract_type']
    kwargs = {'policy': injected} if kind in payload['bound_types'] else {}
    if kind in {'OperatorActionCandidate', 'InAppDeliveryCandidate', 'AnalyticsDimensionsCandidate'}:
        kwargs['projection'] = projection
    if kind in {'InAppDeliveryCandidate', 'AnalyticsDimensionsCandidate'}:
        kwargs['action'] = action
    value = canonical_deserialize(encoded, **kwargs)
    if kind == 'OperatorProjection':
        projection = value
    elif kind == 'OperatorActionCandidate':
        action = value
    assert value.canonical_json() == encoded
"""
    bound_types = ["SubmissionCandidate", "OperatorProjection", "OperatorActionCandidate", "InAppDeliveryCandidate", "AnalyticsDimensionsCandidate"]
    completed = subprocess.run(
        [sys.executable, "-c", program],
        input=json.dumps({"policy": policy().canonical_json(), "values": [value.canonical_json() for value in all_values()], "bound_types": bound_types}),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("bad_version", [True, False, 1.0, "1", 0, 2, None])
def test_root_and_nested_versions_require_exact_builtin_int_one(bad_version) -> None:
    raw = policy().canonical_dict()
    raw["contract_version"] = bad_version
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(raw, sort_keys=True, separators=(",", ":")))
    raw = policy().canonical_dict()
    raw["answer_domains"][0]["contract_version"] = bad_version
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(raw, sort_keys=True, separators=(",", ":")))
    raw = policy().canonical_dict()
    raw["status_transitions"][0]["contract_version"] = bad_version
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(raw, sort_keys=True, separators=(",", ":")))


def test_noncanonical_duplicate_unknown_and_open_json_are_rejected() -> None:
    encoded = policy().canonical_json()
    with pytest.raises(ContractValidationError):
        canonical_deserialize(" " + encoded)
    raw = policy().canonical_dict()
    raw["free_text"] = "secret"
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(raw, sort_keys=True, separators=(",", ":")))
    for encoded in (
        '{"contract_type":"SupportPolicy","contract_type":"Other"}',
        '{"contract_type":"OpenShape","contract_version":1}',
        '{"contract_type":"SupportPolicy","contract_version":NaN}',
    ):
        with pytest.raises(ContractValidationError):
            canonical_deserialize(encoded)


def test_policy_bound_decoders_require_injected_configuration_and_refuse_open_values() -> None:
    selected_policy, submitted, projected, action, _, dimensions = flow()
    for value in (submitted, projected, action, dimensions):
        with pytest.raises(ContractValidationError):
            canonical_deserialize(value.canonical_json())

    vectors = (
        (submitted, "category_id", "arbitrary-category"),
        (action, "response_template_id", "arbitrary-response"),
        (dimensions, "product_area_id", "arbitrary-area"),
    )
    for value, field_name, open_value in vectors:
        raw = value.canonical_dict()
        raw[field_name] = open_value
        encoded = json.dumps(raw, sort_keys=True, separators=(",", ":"))
        kwargs = {"policy": selected_policy}
        if value.contract_type in {"OperatorActionCandidate", "AnalyticsDimensionsCandidate"}:
            kwargs["projection"] = projected
        if value.contract_type == "AnalyticsDimensionsCandidate":
            kwargs["action"] = action
        with pytest.raises(ContractValidationError):
            canonical_deserialize(encoded, **kwargs)


def test_cross_owner_tenant_policy_case_transition_and_delivery_substitutions_refuse() -> None:
    selected_policy = policy()
    submitted = submission(selected_policy)
    assert create_operator_projection(policy=selected_policy, submission=submitted, account_subject_id=ACCOUNT_B, tenant_scope_id=TENANT_A) is None
    assert create_operator_projection(policy=selected_policy, submission=submitted, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_B) is None
    changed_policy = replace(selected_policy, build_ids=("build.synthetic.20260901", "build.synthetic.other"))
    assert create_operator_projection(policy=changed_policy, submission=submitted, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A) is None
    projected = create_operator_projection(policy=selected_policy, submission=submitted, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A)
    assert projected is not None
    base = dict(policy=selected_policy, projection=projected, support_case_id=CASE_A, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A, status=SupportStatus.REVIEWING, response_template_id="response.acknowledged", acted_at=NOW)
    for updates in ({"support_case_id": CASE_B}, {"account_subject_id": ACCOUNT_B}, {"tenant_scope_id": TENANT_B}, {"policy": changed_policy}, {"status": SupportStatus.CLOSED}, {"response_template_id": "response.unknown"}):
        assert create_operator_action_candidate(**(base | updates)) is None
    action = create_operator_action_candidate(**base)
    assert action is not None
    delivery_base = dict(policy=selected_policy, projection=projected, action=action, support_case_id=CASE_A, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A)
    for updates in ({"support_case_id": CASE_B}, {"account_subject_id": ACCOUNT_B}, {"tenant_scope_id": TENANT_B}, {"action": replace(action, policy_content_id=changed_policy.content_id)}):
        assert create_in_app_delivery_candidate(**(delivery_base | updates)) is None


def test_analytics_status_is_derived_only_from_exact_projection_or_action_source() -> None:
    selected_policy, _, projected, action, _, _ = flow()
    submitted_dimensions = create_analytics_dimensions(
        policy=selected_policy, projection=projected,
    )
    assert submitted_dimensions.status is SupportStatus.SUBMITTED
    action_dimensions = create_analytics_dimensions(
        policy=selected_policy, projection=projected, action=action,
    )
    assert action_dimensions.status is SupportStatus.REVIEWING
    with pytest.raises(ContractValidationError):
        create_analytics_dimensions(
            policy=selected_policy,
            projection=projected,
            action=replace(action, status=SupportStatus.CLOSED),
        )


def test_action_delivery_and_analytics_decode_require_exact_source_context() -> None:
    selected_policy, _, projected, action, delivery, dimensions = flow()
    submitted_dimensions = create_analytics_dimensions(
        policy=selected_policy, projection=projected,
    )
    with pytest.raises(ContractValidationError):
        canonical_deserialize(action.canonical_json(), policy=selected_policy)
    with pytest.raises(ContractValidationError):
        canonical_deserialize(delivery.canonical_json(), policy=selected_policy)
    with pytest.raises(ContractValidationError):
        canonical_deserialize(dimensions.canonical_json(), policy=selected_policy)

    assert canonical_deserialize(
        action.canonical_json(), policy=selected_policy, projection=projected,
    ) == action
    assert canonical_deserialize(
        delivery.canonical_json(), policy=selected_policy,
        projection=projected, action=action,
    ) == delivery
    assert canonical_deserialize(
        dimensions.canonical_json(), policy=selected_policy,
        projection=projected, action=action,
    ) == dimensions
    assert canonical_deserialize(
        submitted_dimensions.canonical_json(), policy=selected_policy,
        projection=projected,
    ) == submitted_dimensions

    forged_projections = (
        replace(projected, support_case_id=CASE_B),
        replace(projected, account_subject_id=ACCOUNT_B),
        replace(projected, tenant_scope_id=TENANT_B),
        replace(projected, policy_content_id="sha256:" + "1" * 64),
    )
    for forged in forged_projections:
        with pytest.raises(ContractValidationError):
            canonical_deserialize(
                action.canonical_json(), policy=selected_policy, projection=forged,
            )
        with pytest.raises(ContractValidationError):
            canonical_deserialize(
                delivery.canonical_json(), policy=selected_policy,
                projection=forged, action=action,
            )
    forged_actions = (
        replace(action, support_case_id=CASE_B),
        replace(action, account_subject_id=ACCOUNT_B),
        replace(action, tenant_scope_id=TENANT_B),
        replace(action, policy_id="support.policy.synthetic.v2"),
        replace(action, policy_content_id="sha256:" + "1" * 64),
        replace(action, status=SupportStatus.CLOSED),
    )
    for forged in forged_actions:
        with pytest.raises(ContractValidationError):
            canonical_deserialize(
                forged.canonical_json(), policy=selected_policy,
                projection=projected,
            )
        with pytest.raises(ContractValidationError):
            canonical_deserialize(
                delivery.canonical_json(), policy=selected_policy,
                projection=projected, action=forged,
            )
    forged_deliveries = (
        replace(delivery, support_case_id=CASE_B),
        replace(delivery, account_subject_id=ACCOUNT_B),
        replace(delivery, tenant_scope_id=TENANT_B),
        replace(delivery, policy_content_id="sha256:" + "1" * 64),
        replace(delivery, status=SupportStatus.CLOSED),
    )
    for forged in forged_deliveries:
        with pytest.raises(ContractValidationError):
            canonical_deserialize(
                forged.canonical_json(), policy=selected_policy,
                projection=projected, action=action,
            )
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            replace(action, status=SupportStatus.CLOSED).canonical_json(),
            policy=selected_policy, projection=projected,
        )


def test_answer_domains_and_builtin_types_are_strict() -> None:
    base = dict(policy=policy(), support_case_id=CASE_A, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A, category_id="product-use", product_area_id="builder", route_template_id="desktop.builder", component_id="builder.canvas", build_id="build.synthetic.20260901", context_id="blocked-workflow", severity=Severity.BLOCKING, typed_answers=answers(), created_at=NOW)
    invalid = (
        answers()[:-1],
        (BooleanAnswer("confirmed", True), IntegerAnswer("frequency", 21), EnumAnswer("outcome", "blocked")),
        (BooleanAnswer("confirmed", True), IntegerAnswer("frequency", 3), EnumAnswer("outcome", "unknown")),
    )
    for invalid_answers in invalid:
        with pytest.raises(ContractValidationError):
            create_submission_candidate(**(base | {"typed_answers": invalid_answers}))
    with pytest.raises(ContractValidationError):
        BooleanAnswer("confirmed", 1)  # type: ignore[arg-type]
    with pytest.raises(ContractValidationError):
        IntegerAnswer("frequency", True)  # type: ignore[arg-type]


def test_forbidden_content_and_io_are_absent_from_signatures_fields_and_imports() -> None:
    source = CONTRACTS_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"free_text", "title", "description", "note", "attachment", "screenshot", "diagnostic", "log", "url", "query", "header", "body", "properties", "email", "strategy", "graph", "symbol", "signal", "position", "order", "trade", "fill", "balance", "pnl", "capital", "credential", "token", "secret", "payment", "provider"}
    contract_classes = tuple(value.__class__ for value in all_values())
    for contract_class in contract_classes:
        assert forbidden.isdisjoint(item.name.lower() for item in fields(contract_class))
        assert forbidden.isdisjoint(inspect.signature(contract_class).parameters)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    banned = {"sqlalchemy", "fastapi", "requests", "httpx", "socket", "urllib", "os", "pathlib", "smtplib", "email", "app.db", "app.api", "app.admin", "app.operator_auth", "app.analytics", "app.monitoring", "app.ir", "app.backtest", "app.engine", "app.execution", "app.ledger", "app.providers", "research"}
    assert not any(name == item or name.startswith(item + ".") for name in imports for item in banned)
    calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert calls.isdisjoint({"open", "exec", "eval", "compile", "__import__"})


@pytest.mark.parametrize("change", [
    lambda value: replace(value, policy_id="support.policy.synthetic.v2"),
    lambda value: replace(value, category_ids=("account-access", "other", "product-use")),
    lambda value: replace(value, product_area_ids=("builder", "other", "research")),
    lambda value: replace(value, route_template_ids=("desktop.account", "desktop.builder", "desktop.other")),
    lambda value: replace(value, component_ids=("account.session", "builder.canvas", "builder.other")),
    lambda value: replace(value, build_ids=("build.synthetic.20260901", "build.synthetic.20260902")),
    lambda value: replace(value, context_ids=("blocked-workflow", "general-guidance", "other-context")),
    lambda value: replace(value, answer_domains=(BooleanAnswerDomain("confirmed"), IntegerAnswerDomain("frequency", 0, 21), EnumAnswerDomain("outcome", ("blocked", "degraded")))),
    lambda value: replace(value, response_template_ids=("response.acknowledged", "response.other", "response.resolved")),
    lambda value: replace(value, status_transitions=tuple(sorted((*value.status_transitions, StatusTransition(SupportStatus.SUBMITTED, SupportStatus.CLOSED)), key=lambda item: (item.from_status.value, item.to_status.value)))),
])
def test_policy_identity_changes_for_every_answer_changing_fact(change) -> None:
    original = policy()
    assert change(original).content_id != original.content_id


@pytest.mark.parametrize("change", [
    lambda value: replace(value, support_case_id=CASE_B),
    lambda value: replace(value, account_subject_id=ACCOUNT_B),
    lambda value: replace(value, tenant_scope_id=TENANT_B),
    lambda value: replace(value, policy_id="support.policy.synthetic.v2"),
    lambda value: replace(value, policy_content_id="sha256:" + "1" * 64),
    lambda value: replace(value, category_id="account-access"),
    lambda value: replace(value, product_area_id="research"),
    lambda value: replace(value, route_template_id="desktop.account"),
    lambda value: replace(value, component_id="account.session"),
    lambda value: replace(value, build_id="build.synthetic.other"),
    lambda value: replace(value, context_id="general-guidance"),
    lambda value: replace(value, severity=Severity.HIGH),
    lambda value: replace(value, typed_answers=(BooleanAnswer("confirmed", False), IntegerAnswer("frequency", 3), EnumAnswer("outcome", "blocked"))),
    lambda value: replace(value, created_at=NOW + timedelta(microseconds=1)),
])
def test_submission_identity_changes_for_owner_policy_context_answer_and_time(change) -> None:
    original = submission()
    assert change(original).content_id != original.content_id


def test_action_and_delivery_identity_cover_status_template_and_time() -> None:
    _, _, _, action, delivery, _ = flow()
    for changed in (
        replace(action, status=SupportStatus.RESPONDED),
        replace(action, response_template_id="response.resolved"),
        replace(action, acted_at=action.acted_at + timedelta(microseconds=1)),
    ):
        assert changed.content_id != action.content_id
    for changed in (
        replace(delivery, status=SupportStatus.RESPONDED),
        replace(delivery, response_template_id="response.resolved"),
        replace(delivery, created_at=delivery.created_at + timedelta(microseconds=1)),
    ):
        assert changed.content_id != delivery.content_id


def test_identifier_collection_time_size_and_depth_bounds() -> None:
    with pytest.raises(ContractValidationError):
        BooleanAnswer("X", True)
    with pytest.raises(ContractValidationError):
        BooleanAnswer("x" * (MAX_IDENTIFIER_LENGTH + 1), True)
    with pytest.raises(ContractValidationError):
        EnumAnswerDomain("outcome", tuple(f"value.{index:03d}" for index in range(MAX_COLLECTION_ITEMS + 1)))
    with pytest.raises(ContractValidationError):
        replace(submission(), created_at=NOW.replace(tzinfo=None))
    with pytest.raises(ContractValidationError):
        replace(submission(), created_at=NOW.astimezone(timezone(timedelta(hours=5, minutes=30))))
    with pytest.raises(ContractValidationError):
        replace(submission(), created_at=NOW.replace(year=1999))
    with pytest.raises(ContractValidationError):
        replace(submission(), support_case_id=UUID(int=0))
    with pytest.raises(ContractValidationError):
        replace(submission(), support_case_id="10000000-0000-4000-8000-000000000001")
    with pytest.raises(ContractValidationError):
        canonical_deserialize("x" * (MAX_CANONICAL_BYTES + 1))
    deep: object = 0
    for _ in range(20):
        deep = {"x": deep}
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(deep, separators=(",", ":")))
    hostile_but_under_size = "[" * 1_200 + "0" + "]" * 1_200
    assert len(hostile_but_under_size.encode()) < MAX_CANONICAL_BYTES
    with pytest.raises(ContractValidationError):
        canonical_deserialize(hostile_but_under_size)


def test_projection_and_analytics_have_exact_safe_allowlists() -> None:
    _, _, projected, _, _, dimensions = flow()
    assert {item.name for item in fields(projected)} == {
        "support_case_id", "account_subject_id", "tenant_scope_id", "policy_id",
        "policy_content_id", "category_id", "product_area_id", "route_template_id",
        "component_id", "build_id", "context_id", "severity", "typed_answers",
        "status", "created_at",
    }
    assert {item.name for item in fields(dimensions)} == {
        "category_id", "product_area_id", "severity", "status"
    }
    dimension_keys = set(dimensions.canonical_dict())
    for forbidden in ("case", "account", "tenant", "answer", "timestamp", "route", "component", "build"):
        assert all(forbidden not in key.lower() for key in dimension_keys)


def test_one_hundred_thousand_pure_evaluations_are_deterministic_and_bounded() -> None:
    selected_policy, _, projected, action, _, expected = flow()
    expected_id = expected.content_id
    tracemalloc.start()
    started = time.perf_counter()
    for _ in range(100_000):
        actual = create_analytics_dimensions(
            policy=selected_policy, projection=projected, action=action,
        )
        assert actual.content_id == expected_id
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert elapsed < 30.0
    assert peak < 2_000_000


def _run_mutation_vector(module: types.ModuleType) -> None:
    selected_policy = module.SupportPolicy(
        policy_id="support.policy.synthetic.v1", category_ids=("product-use",),
        product_area_ids=("builder",), route_template_ids=("desktop.builder",),
        component_ids=("builder.canvas",), build_ids=("build.synthetic",),
        context_ids=("blocked",),
        answer_domains=(module.BooleanAnswerDomain("confirmed"),),
        response_template_ids=("response.ack",),
        status_transitions=(module.StatusTransition(module.SupportStatus.SUBMITTED, module.SupportStatus.REVIEWING),),
    )
    submitted = module.create_submission_candidate(
        policy=selected_policy, support_case_id=CASE_A, account_subject_id=ACCOUNT_A,
        tenant_scope_id=TENANT_A, category_id="product-use", product_area_id="builder",
        route_template_id="desktop.builder", component_id="builder.canvas",
        build_id="build.synthetic", context_id="blocked", severity=module.Severity.HIGH,
        typed_answers=(module.BooleanAnswer("confirmed", True),), created_at=NOW,
    )
    assert module.create_operator_projection(policy=selected_policy, submission=submitted, account_subject_id=ACCOUNT_B, tenant_scope_id=TENANT_A) is None
    assert module.create_operator_projection(policy=selected_policy, submission=submitted, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_B) is None
    changed_policy = replace(selected_policy, build_ids=("build.other", "build.synthetic"))
    assert module.create_operator_projection(policy=changed_policy, submission=submitted, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A) is None
    projected = module.create_operator_projection(policy=selected_policy, submission=submitted, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A)
    assert projected is not None
    forged_projection = replace(projected, policy_content_id="sha256:" + "1" * 64)
    try:
        module.create_analytics_dimensions(
            policy=selected_policy, projection=forged_projection,
        )
    except module.ContractValidationError:
        pass
    else:
        raise AssertionError("policy-proof substitution was accepted")
    assert module.create_operator_action_candidate(policy=selected_policy, projection=projected, support_case_id=CASE_B, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A, status=module.SupportStatus.REVIEWING, response_template_id="response.ack", acted_at=NOW) is None
    assert module.create_operator_action_candidate(policy=selected_policy, projection=projected, support_case_id=CASE_A, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A, status=module.SupportStatus.CLOSED, response_template_id="response.ack", acted_at=NOW) is None
    action = module.create_operator_action_candidate(policy=selected_policy, projection=projected, support_case_id=CASE_A, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A, status=module.SupportStatus.REVIEWING, response_template_id="response.ack", acted_at=NOW)
    assert action is not None
    try:
        module.create_analytics_dimensions(
            policy=selected_policy, projection=projected,
            action=replace(action, status=module.SupportStatus.CLOSED),
        )
    except module.ContractValidationError:
        pass
    else:
        raise AssertionError("analytics accepted an action without an exact transition")
    try:
        module.canonical_deserialize(
            action.canonical_json(), policy=selected_policy,
            projection=replace(projected, support_case_id=CASE_B),
        )
    except module.ContractValidationError:
        pass
    else:
        raise AssertionError("action decoder accepted a foreign source case")
    assert module.create_in_app_delivery_candidate(policy=selected_policy, projection=projected, action=action, support_case_id=CASE_A, account_subject_id=ACCOUNT_B, tenant_scope_id=TENANT_A) is None
    forged_action = replace(action, account_subject_id=ACCOUNT_B)
    assert module.create_in_app_delivery_candidate(policy=selected_policy, projection=projected, action=forged_action, support_case_id=CASE_A, account_subject_id=ACCOUNT_A, tenant_scope_id=TENANT_A) is None
    dimensions = module.create_analytics_dimensions(
        policy=selected_policy, projection=projected, action=action,
    )
    assert set(dimensions.canonical_dict()) == {
        "contract_type", "contract_version", "category_id", "product_area_id",
        "severity", "status",
    }


def test_nine_isolated_permissive_mutations_are_killed_and_source_is_restored() -> None:
    source = CONTRACTS_PATH.read_text(encoding="utf-8")
    before = hashlib.sha256(source.encode()).hexdigest()
    analytics_block = '''        return {
            "category_id": self.category_id,
            "product_area_id": self.product_area_id,
            "severity": self.severity.value,
            "status": self.status.value,
        }
'''
    mutations = (
        ("or submission.account_subject_id != account_subject_id", "or False"),
        ("or submission.tenant_scope_id != tenant_scope_id", "or False"),
        ("or submission.policy_content_id != expected_content_id", "or False"),
        ("and action.support_case_id == projection.support_case_id", "and True"),
        ('''and any(
            item.from_status is projection.status and item.to_status is action.status
            for item in policy.status_transitions
        )''', "and True"),
        ("and delivery.account_subject_id == projection.account_subject_id == action.account_subject_id", "and True"),
        ('''or (
            action is not None
            and not _action_matches_sources(policy, projection, action)
        )''', "or False"),
        ('''if isinstance(result, OperatorActionCandidate) and not _action_matches_sources(
        policy, projection, result,
    ):''', "if False:"),
        (analytics_block, analytics_block.replace(
            '"status": self.status.value,',
            '"status": self.status.value,\n            "account_subject_id": "mutated",',
        )),
    )
    for index, (needle, replacement) in enumerate(mutations):
        assert source.count(needle) >= 1
        mutated = source.replace(needle, replacement, 1)
        name = f"isolated_support_mutant_{index}"
        module = types.ModuleType(name)
        module.__file__ = str(CONTRACTS_PATH)
        sys.modules[name] = module
        try:
            exec(compile(mutated, str(CONTRACTS_PATH), "exec"), module.__dict__)
            with pytest.raises(AssertionError):
                _run_mutation_vector(module)
        finally:
            sys.modules.pop(name, None)
    assert hashlib.sha256(CONTRACTS_PATH.read_bytes()).hexdigest() == before
