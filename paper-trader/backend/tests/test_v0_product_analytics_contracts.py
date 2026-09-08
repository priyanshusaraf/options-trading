from __future__ import annotations

import ast
import copy
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
from uuid import UUID

import pytest

import app.product_analytics.contracts as contracts_module
from app.product_analytics.contracts import (
    MAX_CANONICAL_BYTES,
    MAX_COLLECTION_ITEMS,
    MAX_IDENTIFIER_LENGTH,
    AggregateDimensionsCandidate,
    AuthoritativeSourceContext,
    AuthoritativeSourceFactAddress,
    BooleanDimension,
    BooleanDimensionDomain,
    CollectionAuthorityProof,
    ContractValidationError,
    EnumDimension,
    EnumDimensionDomain,
    EventCandidate,
    IntegerDimension,
    IntegerDimensionDomain,
    ProductAnalyticsCatalogue,
    canonical_deserialize,
    create_aggregate_dimensions,
    create_event_candidate,
)


NOW = datetime(2026, 9, 1, 6, 30, 0, 123456, tzinfo=timezone.utc)
SUBJECT_A = UUID("10000000-0000-4000-8000-000000000001")
SUBJECT_B = UUID("10000000-0000-4000-8000-000000000002")
TENANT_A = UUID("20000000-0000-4000-8000-000000000001")
TENANT_B = UUID("20000000-0000-4000-8000-000000000002")
SESSION_A = UUID("30000000-0000-4000-8000-000000000001")
SESSION_B = UUID("30000000-0000-4000-8000-000000000002")
FACT_A = UUID("40000000-0000-4000-8000-000000000001")
FACT_B = UUID("40000000-0000-4000-8000-000000000002")
CONTRACTS_PATH = Path(__file__).parents[1] / "app" / "product_analytics" / "contracts.py"


def catalogue(*, provenance: str = "privacy-review.synthetic.20260901") -> ProductAnalyticsCatalogue:
    return ProductAnalyticsCatalogue(
        catalogue_id="product-analytics.synthetic.v1",
        provenance_id=provenance,
        event_type_ids=("product.workflow.completed",),
        purpose_ids=("product-improvement",),
        product_area_ids=("builder",),
        route_template_ids=("desktop.builder",),
        build_ids=("build.synthetic.20260901",),
        outcome_ids=("success",),
        dimension_domains=(
            BooleanDimensionDomain("guided-mode"),
            IntegerDimensionDomain("step-count", 0, 20),
            EnumDimensionDomain("workflow-kind", ("guided", "manual")),
        ),
    )


def source_context(*, context_id: str = "server.workflow-outcome") -> AuthoritativeSourceContext:
    return AuthoritativeSourceContext(
        source_context_id=context_id,
        provenance_id="source-contract.synthetic.20260901",
    )


def authority(
    selected_catalogue: ProductAnalyticsCatalogue | None = None,
    selected_source_context: AuthoritativeSourceContext | None = None,
    *,
    allowed: bool = True,
) -> CollectionAuthorityProof:
    selected_catalogue = selected_catalogue or catalogue()
    selected_source_context = selected_source_context or source_context()
    return CollectionAuthorityProof(
        authority_id="collection-authority.synthetic.v1",
        policy_provenance_id="privacy-policy.synthetic.20260901",
        catalogue_content_id=selected_catalogue.content_id,
        catalogue_provenance_id=selected_catalogue.provenance_id,
        source_context_content_id=selected_source_context.content_id,
        source_context_provenance_id=selected_source_context.provenance_id,
        collection_allowed=allowed,
    )


def source_address(selected_source_context: AuthoritativeSourceContext | None = None):
    selected_source_context = selected_source_context or source_context()
    return AuthoritativeSourceFactAddress(
        source_context_content_id=selected_source_context.content_id,
        source_fact_id=FACT_A,
        source_fact_version=1,
    )


def dimensions():
    return (
        BooleanDimension("guided-mode", True),
        IntegerDimension("step-count", 4),
        EnumDimension("workflow-kind", "guided"),
    )


def event(
    *,
    selected_catalogue: ProductAnalyticsCatalogue | None = None,
    selected_source_context: AuthoritativeSourceContext | None = None,
    selected_authority: CollectionAuthorityProof | None = None,
    subject_id: UUID = SUBJECT_A,
    tenant_id: UUID = TENANT_A,
    session_id: UUID = SESSION_A,
    selected_source_address: AuthoritativeSourceFactAddress | None = None,
) -> EventCandidate:
    selected_catalogue = selected_catalogue or catalogue()
    selected_source_context = selected_source_context or source_context()
    selected_authority = selected_authority or authority(selected_catalogue, selected_source_context)
    selected_source_address = selected_source_address or source_address(selected_source_context)
    return create_event_candidate(
        catalogue=selected_catalogue,
        authority=selected_authority,
        source_context=selected_source_context,
        subject_epoch_id=subject_id,
        tenant_epoch_id=tenant_id,
        session_epoch_id=session_id,
        source_fact_address=selected_source_address,
        event_type_id="product.workflow.completed",
        purpose_id="product-improvement",
        product_area_id="builder",
        route_template_id="desktop.builder",
        build_id="build.synthetic.20260901",
        outcome_id="success",
        dimensions=dimensions(),
        received_at=NOW,
    )


def flow():
    selected_catalogue = catalogue()
    selected_source_context = source_context()
    selected_authority = authority(selected_catalogue, selected_source_context)
    selected_event = event(
        selected_catalogue=selected_catalogue,
        selected_source_context=selected_source_context,
        selected_authority=selected_authority,
    )
    aggregate = create_aggregate_dimensions(
        catalogue=selected_catalogue,
        authority=selected_authority,
        source_context=selected_source_context,
        event=selected_event,
        expected_subject_epoch_id=SUBJECT_A,
        expected_tenant_epoch_id=TENANT_A,
        expected_session_epoch_id=SESSION_A,
    )
    return selected_catalogue, selected_source_context, selected_authority, selected_event, aggregate


def test_legitimate_server_fact_and_non_publishable_aggregate_pass() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, aggregate = flow()
    assert selected_event.catalogue_content_id == selected_catalogue.content_id
    assert selected_event.authority_content_id == selected_authority.content_id
    assert selected_event.source_context_content_id == selected_source_context.content_id
    assert aggregate.publishable is False
    assert aggregate.canonical_dict() == {
        "contract_type": "AggregateDimensionsCandidate",
        "contract_version": 1,
        "catalogue_content_id": selected_catalogue.content_id,
        "authority_content_id": selected_authority.content_id,
        "event_type_id": "product.workflow.completed",
        "purpose_id": "product-improvement",
        "product_area_id": "builder",
        "route_template_id": "desktop.builder",
        "build_id": "build.synthetic.20260901",
        "outcome_id": "success",
        "dimensions": [item.canonical_dict() for item in dimensions()],
        "publishable": False,
    }
    forbidden = {
        "subject_epoch_id", "tenant_epoch_id", "session_epoch_id",
        "source_context_content_id", "source_fact_address", "received_at",
    }
    assert forbidden.isdisjoint(aggregate.canonical_dict())


def test_all_contracts_are_frozen_and_exact_canonical_roundtrip() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, aggregate = flow()
    values = (
        *selected_catalogue.dimension_domains,
        *dimensions(),
        selected_catalogue,
        selected_source_context,
        selected_authority,
        selected_event.source_fact_address,
        selected_event,
        aggregate,
    )
    for value in values:
        encoded = value.canonical_json()
        kwargs = {}
        if value.contract_type in {"EnumDimension", "BooleanDimension", "IntegerDimension"}:
            kwargs = {"catalogue": selected_catalogue}
        if value.contract_type == "CollectionAuthorityProof":
            kwargs = {"catalogue": selected_catalogue, "source_context": selected_source_context}
        elif value.contract_type == "AuthoritativeSourceFactAddress":
            kwargs = {"source_context": selected_source_context}
        elif value.contract_type == "EventCandidate":
            kwargs = {
                "catalogue": selected_catalogue,
                "authority": selected_authority,
                "source_context": selected_source_context,
            }
        elif value.contract_type == "AggregateDimensionsCandidate":
            kwargs = {
                "catalogue": selected_catalogue,
                "authority": selected_authority,
                "source_context": selected_source_context,
                "event": selected_event,
            }
        restored = canonical_deserialize(encoded, **kwargs)
        assert restored == value
        assert restored.content_id == value.content_id
        assert restored.canonical_json() == encoded
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)


def test_fresh_restart_requires_exact_injected_context() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, aggregate = flow()
    payload = {
        "catalogue": selected_catalogue.canonical_json(),
        "source_context": selected_source_context.canonical_json(),
        "authority": selected_authority.canonical_json(),
        "event": selected_event.canonical_json(),
        "aggregate": aggregate.canonical_json(),
    }
    program = r'''
import json, sys
from app.product_analytics.contracts import canonical_deserialize
p = json.loads(sys.stdin.read())
c = canonical_deserialize(p["catalogue"])
s = canonical_deserialize(p["source_context"])
a = canonical_deserialize(p["authority"], catalogue=c, source_context=s)
e = canonical_deserialize(p["event"], catalogue=c, authority=a, source_context=s)
g = canonical_deserialize(p["aggregate"], catalogue=c, authority=a, source_context=s, event=e)
print(json.dumps([c.content_id, s.content_id, a.content_id, e.content_id, g.content_id]))
'''
    completed = subprocess.run(
        [sys.executable, "-c", program],
        input=json.dumps(payload), text=True, capture_output=True, check=True,
        cwd=Path(__file__).parents[1],
    )
    expected = [item.content_id for item in flow()]
    assert json.loads(completed.stdout) == expected


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        (lambda c, s, a, e: {"catalogue": catalogue(provenance="privacy-review.other")}, "catalogue"),
        (lambda c, s, a, e: {"authority": replace(a, authority_id="collection-authority.other")}, "authority"),
        (lambda c, s, a, e: {"source_context": source_context(context_id="server.other")}, "source"),
        (lambda c, s, a, e: {"subject_epoch_id": SUBJECT_B}, "subject"),
        (lambda c, s, a, e: {"tenant_epoch_id": TENANT_B}, "tenant"),
        (lambda c, s, a, e: {"session_epoch_id": SESSION_B}, "session"),
    ],
)
def test_cross_binding_substitutions_refuse(replacement, message: str) -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, _ = flow()
    kwargs = {
        "catalogue": selected_catalogue,
        "authority": selected_authority,
        "source_context": selected_source_context,
        "subject_epoch_id": SUBJECT_A,
        "tenant_epoch_id": TENANT_A,
        "session_epoch_id": SESSION_A,
        "source_fact_address": selected_event.source_fact_address,
        "event_type_id": selected_event.event_type_id,
        "purpose_id": selected_event.purpose_id,
        "product_area_id": selected_event.product_area_id,
        "route_template_id": selected_event.route_template_id,
        "build_id": selected_event.build_id,
        "outcome_id": selected_event.outcome_id,
        "dimensions": selected_event.dimensions,
        "received_at": selected_event.received_at,
    }
    kwargs.update(replacement(selected_catalogue, selected_source_context, selected_authority, selected_event))
    if message in {"subject", "tenant", "session"}:
        changed = create_event_candidate(**kwargs)
        with pytest.raises(ContractValidationError, match=message):
            create_aggregate_dimensions(
                catalogue=selected_catalogue,
                authority=selected_authority,
                source_context=selected_source_context,
                event=changed,
                expected_subject_epoch_id=SUBJECT_A,
                expected_tenant_epoch_id=TENANT_A,
                expected_session_epoch_id=SESSION_A,
            )
    elif message == "authority":
        with pytest.raises(ContractValidationError, match=message):
            canonical_deserialize(
                selected_event.canonical_json(),
                catalogue=selected_catalogue,
                authority=kwargs["authority"],
                source_context=selected_source_context,
            )
    else:
        with pytest.raises(ContractValidationError, match=message):
            create_event_candidate(**kwargs)


def test_authority_is_explicit_non_default_and_denial_refuses() -> None:
    assert inspect.signature(create_event_candidate).parameters["authority"].default is inspect.Parameter.empty
    denied = authority(allowed=False)
    with pytest.raises(ContractValidationError, match="does not allow"):
        event(selected_authority=denied)


def test_catalogue_and_dimensions_are_closed_and_typed() -> None:
    selected_catalogue = catalogue()
    with pytest.raises(ContractValidationError):
        canonical_deserialize(EnumDimension("workflow-kind", "unknown").canonical_json(), catalogue=selected_catalogue)
    with pytest.raises(ContractValidationError, match="catalogue"):
        canonical_deserialize(EnumDimension("workflow-kind", "guided").canonical_json())
    for changed in (
        {"event_type_id": "unknown"}, {"purpose_id": "unknown"},
        {"product_area_id": "unknown"}, {"route_template_id": "unknown"},
        {"build_id": "unknown"}, {"outcome_id": "unknown"},
        {"dimensions": (EnumDimension("workflow-kind", "unknown"),)},
        {"dimensions": (IntegerDimension("step-count", 21),)},
        {"dimensions": (BooleanDimension("guided-mode", True), BooleanDimension("guided-mode", False))},
    ):
        kwargs = {
            "catalogue": selected_catalogue,
            "authority": authority(selected_catalogue, source_context()),
            "source_context": source_context(),
            "subject_epoch_id": SUBJECT_A,
            "tenant_epoch_id": TENANT_A,
            "session_epoch_id": SESSION_A,
            "source_fact_address": source_address(),
            "event_type_id": "product.workflow.completed",
            "purpose_id": "product-improvement",
            "product_area_id": "builder",
            "route_template_id": "desktop.builder",
            "build_id": "build.synthetic.20260901",
            "outcome_id": "success",
            "dimensions": dimensions(),
            "received_at": NOW,
        }
        kwargs.update(changed)
        with pytest.raises(ContractValidationError):
            create_event_candidate(**kwargs)
    with pytest.raises(ContractValidationError):
        IntegerDimension("step-count", True)


def test_strict_decoder_rejects_duplicate_noncanonical_unicode_size_depth_and_version() -> None:
    selected_catalogue = catalogue()
    good = selected_catalogue.canonical_json()
    vectors = [
        good.replace('"contract_version":1', '"contract_version":true'),
        good.replace('"contract_version":1', '"contract_version":1.0'),
        good.replace('"catalogue_id":', '"catalogue_id":"duplicate","catalogue_id":'),
        good.replace(',', ', ', 1),
        good.replace("product-analytics", "product-\\u0061nalytics"),
        " " * MAX_CANONICAL_BYTES + good,
        '{"x":' * 100 + "0" + "}" * 100,
    ]
    for vector in vectors:
        with pytest.raises(ContractValidationError):
            canonical_deserialize(vector)
    raw = selected_catalogue.canonical_dict()
    raw["event_type_ids"] = [f"event-{i}" for i in range(MAX_COLLECTION_ITEMS + 1)]
    with pytest.raises(ContractValidationError):
        canonical_deserialize(json.dumps(raw, sort_keys=True, separators=(",", ":")))


def test_uuid_time_and_source_context_decode_are_strict() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, _ = flow()
    raw = selected_event.canonical_dict()
    for field_name, replacement in (
        ("subject_epoch_id", "abcdefab-cdef-4abc-8def-abcdefabcdef".upper()),
        ("tenant_epoch_id", "00000000-0000-0000-0000-000000000000"),
        ("session_epoch_id", "not-a-uuid"),
        ("received_at", "2026-09-01T06:30:00Z"),
        ("received_at", "2026-09-01T12:00:00.123456+05:30"),
    ):
        changed = dict(raw)
        changed[field_name] = replacement
        encoded = json.dumps(changed, sort_keys=True, separators=(",", ":"))
        with pytest.raises(ContractValidationError):
            canonical_deserialize(
                encoded, catalogue=selected_catalogue,
                authority=selected_authority, source_context=selected_source_context,
            )
    other_context = source_context(context_id="server.other")
    with pytest.raises(ContractValidationError, match="source context"):
        canonical_deserialize(
            selected_event.canonical_json(), catalogue=selected_catalogue,
            authority=selected_authority, source_context=other_context,
        )


def test_constructor_and_ast_surface_have_no_open_or_effecting_escape_hatch() -> None:
    forbidden_names = {
        "properties", "property", "context", "payload", "metadata", "answer",
        "url", "path", "query", "fragment", "referrer", "header", "body",
        "error", "dom", "replay", "screenshot", "strategy", "research",
        "monitoring", "symbol", "instrument", "position", "order", "trade",
        "fill", "balance", "pnl", "capital", "charge", "provider", "broker",
        "payment", "email", "phone", "cookie", "token", "credential",
    }
    classes = (
        ProductAnalyticsCatalogue, AuthoritativeSourceContext, CollectionAuthorityProof,
        AuthoritativeSourceFactAddress, EventCandidate, AggregateDimensionsCandidate,
        EnumDimensionDomain, BooleanDimensionDomain, IntegerDimensionDomain,
        EnumDimension, BooleanDimension, IntegerDimension,
    )
    for cls in classes:
        names = {name.lower() for name in inspect.signature(cls).parameters}
        assert names.isdisjoint(forbidden_names)
        assert not any(param.kind is inspect.Parameter.VAR_KEYWORD for param in inspect.signature(cls).parameters.values())
    tree = ast.parse(CONTRACTS_PATH.read_text())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
    forbidden_prefixes = (
        "app.engine", "app.events", "app.db", "app.api", "app.accounts", "app.admin",
        "app.operator", "app.platform", "app.monitoring", "app.ir", "app.backtest",
        "app.execution", "app.ledger", "app.providers", "research", "os", "pathlib",
        "requests", "httpx", "socket", "sqlalchemy",
    )
    assert not any(name.startswith(forbidden_prefixes) for name in imports)
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert called.isdisjoint({"open", "print", "getenv", "urlopen"})


def test_every_answer_changing_field_changes_identity() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, aggregate = flow()
    changed_catalogue = catalogue(provenance="privacy-review.changed")
    changed_context = source_context(context_id="server.changed")
    assert changed_catalogue.content_id != selected_catalogue.content_id
    assert authority(changed_catalogue, selected_source_context).content_id != selected_authority.content_id
    assert authority(selected_catalogue, changed_context).content_id != selected_authority.content_id
    event_changes = (
        replace(selected_event, subject_epoch_id=SUBJECT_B),
        replace(selected_event, tenant_epoch_id=TENANT_B),
        replace(selected_event, session_epoch_id=SESSION_B),
        replace(selected_event, source_fact_address=replace(selected_event.source_fact_address, source_fact_id=FACT_B)),
        replace(selected_event, received_at=NOW.replace(microsecond=123457)),
    )
    assert all(item.content_id != selected_event.content_id for item in event_changes)
    assert replace(aggregate, outcome_id="other").content_id != aggregate.content_id


def test_100k_pure_decisions_fit_declared_ceiling() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, _ = flow()
    tracemalloc.start()
    started = time.perf_counter()
    for _ in range(100_000):
        candidate = create_aggregate_dimensions(
            catalogue=selected_catalogue, authority=selected_authority, event=selected_event,
            source_context=selected_source_context,
            expected_subject_epoch_id=SUBJECT_A,
            expected_tenant_epoch_id=TENANT_A,
            expected_session_epoch_id=SESSION_A,
        )
        assert candidate.publishable is False
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"100k_metrics elapsed_seconds={elapsed:.6f} peak_bytes={peak}")
    assert elapsed <= 30.0
    assert peak <= 2 * 1024 * 1024


def test_bounds_are_stable_and_machine_identifiers_only() -> None:
    with pytest.raises(ContractValidationError):
        AuthoritativeSourceContext("A" * (MAX_IDENTIFIER_LENGTH + 1), "source.synthetic")
    with pytest.raises(ContractValidationError):
        AuthoritativeSourceContext("server.é", "source.synthetic")


def test_eight_isolated_safety_mutations_are_killed_and_restored(monkeypatch) -> None:
    selected_catalogue, selected_source_context, _, selected_event, _ = flow()
    unsafe_cases = (
        ("_identifier", lambda value, name: value,
         lambda: AuthoritativeSourceContext("SERVER.INVALID", "source.synthetic")),
        ("_strict_bool", lambda value, name: value,
         lambda: BooleanDimension("guided-mode", 1)),
        ("_strict_int", lambda value, name, minimum, maximum: value,
         lambda: IntegerDimension("step-count", True)),
        ("_uuid", lambda value, name: value,
         lambda: AuthoritativeSourceFactAddress(selected_source_context.content_id, UUID(int=0), 1)),
        ("_utc", lambda value, name: value,
         lambda: replace(selected_event, received_at=NOW.replace(tzinfo=None))),
        ("_content_id", lambda value, name: value,
         lambda: AuthoritativeSourceFactAddress("not-a-content-id", FACT_A, 1)),
        ("_dimension_tuple", lambda value: value,
         lambda: replace(selected_event, dimensions=(dimensions()[0], dimensions()[0]))),
        ("_validate_dimensions", lambda selected, values: None,
         lambda: create_event_candidate(
             catalogue=selected_catalogue,
             authority=authority(selected_catalogue, selected_source_context),
             source_context=selected_source_context,
             subject_epoch_id=SUBJECT_A, tenant_epoch_id=TENANT_A, session_epoch_id=SESSION_A,
             source_fact_address=source_address(selected_source_context),
             event_type_id="product.workflow.completed", purpose_id="product-improvement",
             product_area_id="builder", route_template_id="desktop.builder",
             build_id="build.synthetic.20260901", outcome_id="success",
             dimensions=(EnumDimension("workflow-kind", "outside-domain"),), received_at=NOW,
         )),
    )
    for target_name, mutant, unsafe_action in unsafe_cases:
        original = getattr(contracts_module, target_name)
        with pytest.raises(ContractValidationError):
            unsafe_action()
        with monkeypatch.context() as isolated:
            isolated.setattr(contracts_module, target_name, mutant)
            unsafe_action()
        assert getattr(contracts_module, target_name) is original
        with pytest.raises(ContractValidationError):
            unsafe_action()


def test_reviewer_foreign_six_identifier_direct_event_is_refused() -> None:
    selected_catalogue, _, selected_authority, selected_event, _ = flow()
    foreign = replace(
        selected_event,
        event_type_id="foreign.event",
        purpose_id="foreign-purpose",
        product_area_id="foreign-area",
        route_template_id="foreign.route",
        build_id="foreign.build",
        outcome_id="foreign-outcome",
    )
    with pytest.raises(ContractValidationError):
        create_aggregate_dimensions(
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=source_context(),
            event=foreign,
            expected_subject_epoch_id=SUBJECT_A,
            expected_tenant_epoch_id=TENANT_A,
            expected_session_epoch_id=SESSION_A,
        )


def test_reviewer_forged_authority_and_foreign_source_are_refused() -> None:
    _, _, _, selected_event, _ = flow()
    foreign_catalogue = catalogue(provenance="privacy-review.foreign")
    foreign_context = source_context(context_id="server.foreign")
    forged_authority = replace(
        authority(),
        catalogue_content_id=foreign_catalogue.content_id,
        source_context_content_id=foreign_context.content_id,
    )
    forged_event = replace(
        selected_event,
        catalogue_content_id=foreign_catalogue.content_id,
        authority_content_id=forged_authority.content_id,
        source_context_content_id=foreign_context.content_id,
        source_fact_address=source_address(foreign_context),
    )
    with pytest.raises(ContractValidationError):
        create_aggregate_dimensions(
            catalogue=foreign_catalogue,
            authority=forged_authority,
            source_context=foreign_context,
            event=forged_event,
            expected_subject_epoch_id=SUBJECT_A,
            expected_tenant_epoch_id=TENANT_A,
            expected_session_epoch_id=SESSION_A,
        )


@pytest.mark.parametrize(
    "forged_authority",
    (
        replace(authority(), catalogue_content_id=catalogue(provenance="foreign").content_id),
        replace(authority(), catalogue_provenance_id="privacy-review.foreign"),
        replace(authority(), source_context_content_id=source_context(context_id="server.foreign").content_id),
        replace(authority(), source_context_provenance_id="source-contract.foreign"),
    ),
)
def test_reviewer_authority_catalogue_provenance_and_source_bindings_refuse(
    forged_authority: CollectionAuthorityProof,
) -> None:
    with pytest.raises(ContractValidationError):
        event(selected_authority=forged_authority)


def test_direct_aggregate_requires_exact_event_rederivation() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, selected_aggregate = flow()
    direct_aggregate = replace(selected_aggregate)
    with pytest.raises(ContractValidationError, match="event"):
        canonical_deserialize(
            direct_aggregate.canonical_json(),
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=selected_source_context,
        )
    restored = canonical_deserialize(
        direct_aggregate.canonical_json(),
        catalogue=selected_catalogue,
        authority=selected_authority,
        source_context=selected_source_context,
        event=selected_event,
    )
    assert restored == selected_aggregate

    foreign_event = replace(selected_event, event_type_id="foreign.event")
    foreign_aggregate = replace(selected_aggregate, event_type_id="foreign.event")
    with pytest.raises(ContractValidationError):
        canonical_deserialize(
            foreign_aggregate.canonical_json(),
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=selected_source_context,
            event=foreign_event,
        )


def test_use_site_validation_mutations_are_attributable_and_restored(monkeypatch) -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, _ = flow()
    foreign_event = replace(selected_event, event_type_id="foreign.event")

    def derive(candidate: EventCandidate = foreign_event) -> AggregateDimensionsCandidate:
        return create_aggregate_dimensions(
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=selected_source_context,
            event=candidate,
            expected_subject_epoch_id=SUBJECT_A,
            expected_tenant_epoch_id=TENANT_A,
            expected_session_epoch_id=SESSION_A,
        )

    def factory() -> EventCandidate:
        return create_event_candidate(
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=selected_source_context,
            subject_epoch_id=SUBJECT_A,
            tenant_epoch_id=TENANT_A,
            session_epoch_id=SESSION_A,
            source_fact_address=source_address(selected_source_context),
            event_type_id="foreign.event",
            purpose_id="product-improvement",
            product_area_id="builder",
            route_template_id="desktop.builder",
            build_id="build.synthetic.20260901",
            outcome_id="success",
            dimensions=dimensions(),
            received_at=NOW,
        )

    def decode() -> EventCandidate:
        return canonical_deserialize(
            foreign_event.canonical_json(),
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=selected_source_context,
        )

    actions = (
        ("factory_complete_validation", factory),
        ("derivation_complete_validation", derive),
        ("decode_complete_validation", decode),
    )
    for label, unsafe_action in actions:
        original = contracts_module._validate_event_in_context
        with pytest.raises(ContractValidationError):
            unsafe_action()
        with monkeypatch.context() as isolated:
            isolated.setattr(
                contracts_module,
                "_validate_event_in_context",
                lambda **kwargs: (
                    kwargs["catalogue"].content_id,
                    kwargs["authority"].content_id,
                    kwargs["source_context"].content_id,
                ),
            )
            unsafe_action()
            print(f"mutation_exposed={label}")
        assert contracts_module._validate_event_in_context is original
        with pytest.raises(ContractValidationError):
            unsafe_action()
        print(f"mutation_restored={label}")


def test_fresh_lineage_has_no_stored_derivation_marker_or_identity_trust() -> None:
    forbidden = {
        "_TRUSTED_DERIVATION_SEAL",
        "_TrustedDerivationSeal",
        "_seal_derivation",
        "_require_trusted_derivation",
    }
    assert forbidden.isdisjoint(vars(contracts_module))
    assert "_derivation_seal" not in {item.name for item in fields(EventCandidate)}
    assert "_derivation_seal" not in {item.name for item in fields(AggregateDimensionsCandidate)}


def test_shallow_copy_with_object_mutated_naive_time_refuses_at_use() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, _ = flow()
    copied = copy.copy(selected_event)
    object.__setattr__(copied, "received_at", NOW.replace(tzinfo=None))
    with pytest.raises(ContractValidationError, match="UTC"):
        create_aggregate_dimensions(
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=selected_source_context,
            event=copied,
            expected_subject_epoch_id=SUBJECT_A,
            expected_tenant_epoch_id=TENANT_A,
            expected_session_epoch_id=SESSION_A,
        )


def test_unchanged_event_and_aggregate_copies_validate_from_current_facts() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, selected_aggregate = flow()
    for copier in (copy.copy, copy.deepcopy):
        copied_event = copier(selected_event)
        derived = create_aggregate_dimensions(
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=selected_source_context,
            event=copied_event,
            expected_subject_epoch_id=SUBJECT_A,
            expected_tenant_epoch_id=TENANT_A,
            expected_session_epoch_id=SESSION_A,
        )
        assert derived == selected_aggregate
        copied_aggregate = copier(selected_aggregate)
        assert canonical_deserialize(
            copied_aggregate.canonical_json(),
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=selected_source_context,
            event=copied_event,
        ) == selected_aggregate


def test_copy_and_deepcopy_object_mutation_matrix_refuses_current_event_fields() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, _ = flow()
    foreign_content_id = "sha256:" + "0" * 64

    def set_field(candidate, copier, name, value):
        object.__setattr__(candidate, name, value)

    def set_source(candidate, copier, name, value):
        address = copier(candidate.source_fact_address)
        object.__setattr__(address, name, value)
        object.__setattr__(candidate, "source_fact_address", address)

    def set_dimension(candidate, copier, index, value):
        current = list(candidate.dimensions)
        changed = copier(current[index])
        object.__setattr__(changed, "value", value)
        current[index] = changed
        object.__setattr__(candidate, "dimensions", tuple(current))

    mutations = (
        ("naive_time", lambda c, cp: set_field(c, cp, "received_at", NOW.replace(tzinfo=None))),
        ("non_utc_time", lambda c, cp: set_field(c, cp, "received_at", NOW.astimezone(timezone(timedelta(hours=5, minutes=30))))),
        ("time_type", lambda c, cp: set_field(c, cp, "received_at", "2026-09-01")),
        ("subject_zero", lambda c, cp: set_field(c, cp, "subject_epoch_id", UUID(int=0))),
        ("subject_type", lambda c, cp: set_field(c, cp, "subject_epoch_id", str(SUBJECT_A))),
        ("tenant_zero", lambda c, cp: set_field(c, cp, "tenant_epoch_id", UUID(int=0))),
        ("session_zero", lambda c, cp: set_field(c, cp, "session_epoch_id", UUID(int=0))),
        ("catalogue_content", lambda c, cp: set_field(c, cp, "catalogue_content_id", foreign_content_id)),
        ("authority_content", lambda c, cp: set_field(c, cp, "authority_content_id", foreign_content_id)),
        ("source_context_content", lambda c, cp: set_field(c, cp, "source_context_content_id", foreign_content_id)),
        ("source_uuid", lambda c, cp: set_source(c, cp, "source_fact_id", UUID(int=0))),
        ("source_version", lambda c, cp: set_source(c, cp, "source_fact_version", 0)),
        ("source_version_bool", lambda c, cp: set_source(c, cp, "source_fact_version", True)),
        ("source_context", lambda c, cp: set_source(c, cp, "source_context_content_id", foreign_content_id)),
        ("event_type", lambda c, cp: set_field(c, cp, "event_type_id", "foreign.event")),
        ("event_type_type", lambda c, cp: set_field(c, cp, "event_type_id", True)),
        ("purpose", lambda c, cp: set_field(c, cp, "purpose_id", "foreign-purpose")),
        ("product_area", lambda c, cp: set_field(c, cp, "product_area_id", "foreign-area")),
        ("route", lambda c, cp: set_field(c, cp, "route_template_id", "foreign.route")),
        ("build", lambda c, cp: set_field(c, cp, "build_id", "foreign.build")),
        ("outcome", lambda c, cp: set_field(c, cp, "outcome_id", "foreign-outcome")),
        ("boolean_dimension", lambda c, cp: set_dimension(c, cp, 0, 1)),
        ("integer_dimension", lambda c, cp: set_dimension(c, cp, 1, 21)),
        ("enum_dimension", lambda c, cp: set_dimension(c, cp, 2, "foreign")),
    )
    for copier in (copy.copy, copy.deepcopy):
        for label, mutate in mutations:
            candidate = copier(selected_event)
            candidate.content_id
            mutate(candidate, copier)
            with pytest.raises(ContractValidationError):
                create_aggregate_dimensions(
                    catalogue=selected_catalogue,
                    authority=selected_authority,
                    source_context=selected_source_context,
                    event=candidate,
                    expected_subject_epoch_id=SUBJECT_A,
                    expected_tenant_epoch_id=TENANT_A,
                    expected_session_epoch_id=SESSION_A,
                )


def test_replace_matrix_refuses_changed_event_fields_at_construction_or_use() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, _ = flow()
    use_time_changes = (
        {"subject_epoch_id": SUBJECT_B},
        {"event_type_id": "foreign.event"},
        {"purpose_id": "foreign-purpose"},
        {"product_area_id": "foreign-area"},
        {"route_template_id": "foreign.route"},
        {"build_id": "foreign.build"},
        {"outcome_id": "foreign-outcome"},
    )
    for changed in use_time_changes:
        candidate = replace(selected_event, **changed)
        with pytest.raises(ContractValidationError):
            create_aggregate_dimensions(
                catalogue=selected_catalogue,
                authority=selected_authority,
                source_context=selected_source_context,
                event=candidate,
                expected_subject_epoch_id=SUBJECT_A,
                expected_tenant_epoch_id=TENANT_A,
                expected_session_epoch_id=SESSION_A,
            )
    invalid_boolean = copy.copy(selected_event.dimensions[0])
    object.__setattr__(invalid_boolean, "value", 1)
    invalid_dimension_event = replace(
        selected_event,
        dimensions=(invalid_boolean, *selected_event.dimensions[1:]),
    )
    with pytest.raises(ContractValidationError):
        create_aggregate_dimensions(
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=selected_source_context,
            event=invalid_dimension_event,
            expected_subject_epoch_id=SUBJECT_A,
            expected_tenant_epoch_id=TENANT_A,
            expected_session_epoch_id=SESSION_A,
        )
    constructor_actions = (
        lambda: replace(selected_event, received_at=NOW.replace(tzinfo=None)),
        lambda: replace(selected_event, tenant_epoch_id=UUID(int=0)),
        lambda: replace(selected_event, session_epoch_id=UUID(int=0)),
        lambda: replace(
            selected_event,
            source_fact_address=replace(
                selected_event.source_fact_address, source_fact_version=0
            ),
        ),
    )
    for action in constructor_actions:
        with pytest.raises(ContractValidationError):
            action()


def test_copied_context_and_authority_mutations_refuse_after_cached_identity() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, _ = flow()

    def derive(catalogue_value, authority_value, context_value):
        return create_aggregate_dimensions(
            catalogue=catalogue_value,
            authority=authority_value,
            source_context=context_value,
            event=selected_event,
            expected_subject_epoch_id=SUBJECT_A,
            expected_tenant_epoch_id=TENANT_A,
            expected_session_epoch_id=SESSION_A,
        )

    for copier in (copy.copy, copy.deepcopy):
        catalogue_copy = copier(selected_catalogue)
        catalogue_copy.content_id
        object.__setattr__(catalogue_copy, "provenance_id", "privacy-review.mutated")
        with pytest.raises(ContractValidationError):
            derive(catalogue_copy, selected_authority, selected_source_context)

        catalogue_type_copy = copier(selected_catalogue)
        object.__setattr__(catalogue_type_copy, "event_type_ids", ["product.workflow.completed"])
        with pytest.raises(ContractValidationError):
            derive(catalogue_type_copy, selected_authority, selected_source_context)

        context_copy = copier(selected_source_context)
        context_copy.content_id
        object.__setattr__(context_copy, "provenance_id", "source-contract.mutated")
        with pytest.raises(ContractValidationError):
            derive(selected_catalogue, selected_authority, context_copy)

        for field_name, value in (
            ("catalogue_content_id", "sha256:" + "0" * 64),
            ("catalogue_provenance_id", "privacy-review.mutated"),
            ("source_context_content_id", "sha256:" + "0" * 64),
            ("source_context_provenance_id", "source-contract.mutated"),
            ("collection_allowed", False),
            ("collection_allowed", 1),
        ):
            authority_copy = copier(selected_authority)
            authority_copy.content_id
            object.__setattr__(authority_copy, field_name, value)
            with pytest.raises(ContractValidationError):
                derive(selected_catalogue, authority_copy, selected_source_context)


def test_copied_aggregate_mutation_matrix_refuses_exact_rederivation() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, selected_aggregate = flow()
    mutations = (
        ("catalogue_content_id", "sha256:" + "0" * 64),
        ("authority_content_id", "sha256:" + "0" * 64),
        ("event_type_id", "foreign.event"),
        ("purpose_id", "foreign-purpose"),
        ("product_area_id", "foreign-area"),
        ("route_template_id", "foreign.route"),
        ("build_id", "foreign.build"),
        ("outcome_id", "foreign-outcome"),
        ("dimensions", (BooleanDimension("guided-mode", False), *selected_aggregate.dimensions[1:])),
        ("publishable", True),
    )
    for copier in (copy.copy, copy.deepcopy):
        for field_name, value in mutations:
            candidate = copier(selected_aggregate)
            candidate.content_id
            object.__setattr__(candidate, field_name, value)
            with pytest.raises(ContractValidationError):
                canonical_deserialize(
                    candidate.canonical_json(),
                    catalogue=selected_catalogue,
                    authority=selected_authority,
                    source_context=selected_source_context,
                    event=selected_event,
                )


def test_aggregate_replace_and_object_mutation_matrix_is_complete() -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, selected_aggregate = flow()

    def changed_dimensions(index: int, value: object):
        result = list(selected_aggregate.dimensions)
        changed = copy.copy(result[index])
        object.__setattr__(changed, "value", value)
        result[index] = changed
        return tuple(result)

    vectors = (
        ("catalogue_content_id", "sha256:" + "0" * 64),
        ("authority_content_id", "sha256:" + "0" * 64),
        ("event_type_id", "foreign.event"),
        ("purpose_id", "foreign-purpose"),
        ("product_area_id", "foreign-area"),
        ("route_template_id", "foreign.route"),
        ("build_id", "foreign.build"),
        ("outcome_id", "foreign-outcome"),
        ("dimensions", changed_dimensions(0, 1)),
        ("dimensions", changed_dimensions(1, 21)),
        ("dimensions", changed_dimensions(1, True)),
        ("dimensions", changed_dimensions(2, "outside-domain")),
        ("dimensions", changed_dimensions(2, True)),
    )

    def decode(candidate: AggregateDimensionsCandidate):
        return canonical_deserialize(
            candidate.canonical_json(),
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=selected_source_context,
            event=selected_event,
        )

    assert decode(selected_aggregate) == selected_aggregate
    for field_name, value in vectors:
        replaced = replace(selected_aggregate, **{field_name: value})
        try:
            decode(replaced)
        except ContractValidationError:
            pass
        else:
            pytest.fail(f"aggregate replace mutation escaped: {field_name}={value!r}")
        object_mutated = copy.copy(selected_aggregate)
        object.__setattr__(object_mutated, field_name, value)
        try:
            decode(object_mutated)
        except ContractValidationError:
            pass
        else:
            pytest.fail(f"aggregate object mutation escaped: {field_name}={value!r}")

    with pytest.raises(ContractValidationError):
        replace(selected_aggregate, publishable=True)
    publishable = copy.copy(selected_aggregate)
    object.__setattr__(publishable, "publishable", True)
    with pytest.raises(ContractValidationError):
        decode(publishable)


def test_aggregate_decode_rederivation_mutation_is_exposed_and_restored(monkeypatch) -> None:
    selected_catalogue, selected_source_context, selected_authority, selected_event, selected_aggregate = flow()
    foreign = replace(selected_aggregate, outcome_id="foreign-outcome")

    def decode():
        return canonical_deserialize(
            foreign.canonical_json(),
            catalogue=selected_catalogue,
            authority=selected_authority,
            source_context=selected_source_context,
            event=selected_event,
        )

    original = contracts_module._rederive_aggregate_for_decode
    with pytest.raises(ContractValidationError):
        decode()
    with monkeypatch.context() as isolated:
        isolated.setattr(
            contracts_module,
            "_rederive_aggregate_for_decode",
            lambda **kwargs: foreign,
        )
        assert decode() == foreign
        print("mutation_exposed=aggregate_decode_rederive_compare")
    assert contracts_module._rederive_aggregate_for_decode is original
    with pytest.raises(ContractValidationError):
        decode()
    assert canonical_deserialize(
        selected_aggregate.canonical_json(),
        catalogue=selected_catalogue,
        authority=selected_authority,
        source_context=selected_source_context,
        event=selected_event,
    ) == selected_aggregate
    print("mutation_restored=aggregate_decode_rederive_compare")


def test_identity_only_cache_tracks_field_and_nested_mutation_without_alias() -> None:
    contracts_module._cached_content_id.cache_clear()
    catalogue_value = copy.deepcopy(catalogue())
    before = catalogue_value.content_id
    object.__setattr__(catalogue_value, "provenance_id", "privacy-review.changed")
    assert catalogue_value.content_id != before

    contracts_module._cached_content_id.cache_clear()
    nested_catalogue = copy.deepcopy(catalogue())
    before_nested = nested_catalogue.content_id
    changed_domain = copy.copy(nested_catalogue.dimension_domains[2])
    object.__setattr__(changed_domain, "allowed_values", ("guided", "manual", "other"))
    object.__setattr__(
        nested_catalogue,
        "dimension_domains",
        (*nested_catalogue.dimension_domains[:2], changed_domain),
    )
    assert nested_catalogue.content_id != before_nested

    contracts_module._cached_content_id.cache_clear()
    _, _, _, event_value, aggregate_value = flow()
    before_event = event_value.content_id
    changed_dimension = copy.copy(event_value.dimensions[1])
    object.__setattr__(changed_dimension, "value", 5)
    object.__setattr__(
        event_value,
        "dimensions",
        (event_value.dimensions[0], changed_dimension, event_value.dimensions[2]),
    )
    assert event_value.content_id != before_event
    assert aggregate_value.content_id == "sha256:32f3e01fb9ba01d7247fa48c08810352b1d20d284cc0d8fb42b0fe46c3ce0a7a"

    first = catalogue(provenance="privacy-review.first")
    second = catalogue(provenance="privacy-review.second")
    assert first is not second
    assert first.content_id != second.content_id


def test_identity_cache_is_bounded_and_complete_validation_runs_every_use(monkeypatch) -> None:
    contracts_module._cached_content_id.cache_clear()
    for index in range(402):
        AuthoritativeSourceContext(
            source_context_id=f"server.context-{index}",
            provenance_id="source-contract.synthetic",
        ).content_id
    info = contracts_module._cached_content_id.cache_info()
    assert info.maxsize == 256
    assert info.currsize == 256

    selected_catalogue, selected_source_context, selected_authority, selected_event, _ = flow()
    calls = 0
    original = contracts_module._validate_catalogue_current

    def counted(value):
        nonlocal calls
        calls += 1
        return original(value)

    with monkeypatch.context() as isolated:
        isolated.setattr(contracts_module, "_validate_catalogue_current", counted)
        for _ in range(2):
            create_aggregate_dimensions(
                catalogue=selected_catalogue,
                authority=selected_authority,
                source_context=selected_source_context,
                event=selected_event,
                expected_subject_epoch_id=SUBJECT_A,
                expected_tenant_epoch_id=TENANT_A,
                expected_session_epoch_id=SESSION_A,
            )
    assert calls == 2
    assert contracts_module._validate_catalogue_current is original
