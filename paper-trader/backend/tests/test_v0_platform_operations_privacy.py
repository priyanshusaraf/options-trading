from __future__ import annotations

import ast
import datetime as dt
import inspect
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models import Base, PlatformSupportRequestRow
from app.platform_operations.contracts import (
    AnalyticsEventType, AnalyticsOutcome, AnalyticsSurface, MembershipState,
    OperationsNotFound, OperationsRefused, SupportCategory, TenantAuthority,
    code,
)
from app.platform_operations.repository import OPERATIONS_TABLES, PlatformOperationsRepository


NOW = dt.datetime(2026, 8, 30, 9, 0, tzinfo=dt.timezone.utc)
FORBIDDEN = (
    "strategy_id", "strategy_name", "graph_id", "graph_hash", "graph_body",
    "component_id", "parameters", "annotation", "dataset_id", "research_result",
    "signal_context", "instrument_symbol", "broker_account_id", "provider_account_id",
    "credential", "token", "position", "order", "balance", "capital", "pnl",
    "raw_request", "raw_response", "raw_webhook", "card", "upi", "free_text",
    "attachment",
)


def _engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'privacy.db'}", future=True)
    @sa.event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    return engine


def _tenant(owner):
    return TenantAuthority(owner, f"principal.{owner}", MembershipState.ACTIVE)


def test_schema_and_operations_ast_are_structurally_blind():
    assert {name for name in Base.metadata.tables if name.startswith("platform_")} == OPERATIONS_TABLES
    names = {
        column.name.lower()
        for table_name in OPERATIONS_TABLES
        for column in Base.metadata.tables[table_name].columns
    }
    for sentinel in FORBIDDEN:
        assert sentinel not in names
    for table_name in OPERATIONS_TABLES:
        table = Base.metadata.tables[table_name]
        assert all(fk.column.table.name in OPERATIONS_TABLES for fk in table.foreign_keys)
        assert all(type(column.type).__name__ not in {"JSON", "JSONB", "Text"}
                   for column in table.columns)
    receipt = Base.metadata.tables["platform_billing_event_receipts"]
    receipt_fks = {tuple(fk.constraint.column_keys) for fk in receipt.foreign_keys}
    assert receipt_fks == {(
        "binding_id", "owner_ref", "mode", "merchant_address", "integration_address",
        "provider_customer_ref", "provider_subscription_ref",
    )}
    receipt_uniques = {
        tuple(constraint.columns.keys()) for constraint in receipt.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }
    assert ("mode", "merchant_address", "integration_address", "provider_event_ref") in receipt_uniques

    package = Path(inspect.getfile(PlatformOperationsRepository)).parent
    forbidden_imports = ("app.accounts", "app.ir", "app.backtest", "app.engine",
                         "app.execution", "app.ledger", "app.providers", "research")
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not [name for name in imports if name.startswith(forbidden_imports)]
    assert "role" not in inspect.signature(TenantAuthority).parameters
    assert "admin" not in inspect.signature(TenantAuthority).parameters


@pytest.mark.parametrize("sentinel", FORBIDDEN)
def test_forbidden_sentinel_refuses_before_and_below_repository(tmp_path, sentinel):
    with pytest.raises(OperationsRefused, match="forbidden"):
        code(sentinel.upper(), "detail")
    engine = _engine(tmp_path)
    with Session(engine) as session:
        repository = PlatformOperationsRepository(session, tenant=_tenant("owner.alpha"))
        repository.create_support_request(
            request_id="support.alpha", category=SupportCategory.ACCOUNT_ACCESS,
            detail_code="LOGIN_FAILED", created_at=NOW)
        session.commit()
        with pytest.raises(sa.exc.IntegrityError, match="forbidden content"):
            session.execute(sa.update(PlatformSupportRequestRow).values(
                detail_code=sentinel.upper()))
            session.flush()


def test_two_owner_support_and_analytics_markers_do_not_cross(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session:
        alpha = PlatformOperationsRepository(session, tenant=_tenant("owner.alpha"))
        beta = PlatformOperationsRepository(session, tenant=_tenant("owner.beta"))
        alpha.create_support_request(
            request_id="support.alpha", category=SupportCategory.ACCOUNT_ACCESS,
            detail_code="LOGIN_FAILED", created_at=NOW)
        beta.create_support_request(
            request_id="support.beta", category=SupportCategory.BILLING,
            detail_code="PAYMENT_FAILED", created_at=NOW)
        assert [item.request_id for item in alpha.list_support_requests().items] == ["support.alpha"]
        assert [item.request_id for item in beta.list_support_requests().items] == ["support.beta"]
        subject = alpha.create_analytics_subject(created_at=NOW)
        alpha.record_analytics_event(
            event_id="event.alpha", subject_id=subject.subject_id,
            event_type=AnalyticsEventType.WORKSPACE_OPENED,
            surface=AnalyticsSurface.WORKSPACE, outcome=AnalyticsOutcome.SUCCEEDED,
            occurred_at=NOW, dimension_a="DESKTOP")
        alpha.mark_analytics_exported(subject_id=subject.subject_id, at=NOW)
        alpha.mark_analytics_deleted(subject_id=subject.subject_id, at=NOW)
        with pytest.raises(OperationsNotFound):
            beta.mark_analytics_exported(subject_id=subject.subject_id, at=NOW)
        with pytest.raises(OperationsNotFound):
            beta.record_analytics_event(
                event_id="event.beta", subject_id=subject.subject_id,
                event_type=AnalyticsEventType.WORKSPACE_OPENED,
                surface=AnalyticsSurface.WORKSPACE,
                outcome=AnalyticsOutcome.SUCCEEDED, occurred_at=NOW)


def test_page_bounds_refuse_zero_negative_and_unbounded(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        repository = PlatformOperationsRepository(session, tenant=_tenant("owner.alpha"))
        for limit in (0, -1, 101):
            with pytest.raises(OperationsRefused, match="page limit"):
                repository.list_support_requests(limit=limit)


def test_versioned_vocabularies_reject_open_support_and_analytics_codes(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        repository = PlatformOperationsRepository(session, tenant=_tenant("owner.alpha"))
        with pytest.raises(OperationsRefused, match="support detail"):
            repository.create_support_request(
                request_id="support.sensitive", category=SupportCategory.ACCOUNT_ACCESS,
                detail_code="MONITORING_NIFTY_PROFIT_SECRET", created_at=NOW)
        subject = repository.create_analytics_subject(created_at=NOW)
        with pytest.raises(OperationsRefused, match="analytics dimension"):
            repository.record_analytics_event(
                event_id="event.open", subject_id=subject.subject_id,
                event_type=AnalyticsEventType.WORKSPACE_OPENED,
                surface=AnalyticsSurface.WORKSPACE,
                outcome=AnalyticsOutcome.SUCCEEDED, occurred_at=NOW,
                dimension_a="UNVERSIONED_DIMENSION")


def test_copy_restore_rescans_every_text_field_without_trigger_trust(tmp_path):
    from app.db.copy_contract import CopyRefusal, validate_content_addresses

    engine = _engine(tmp_path)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER platform_support_requests_privacy_insert")
        connection.execute(sa.text(
            "INSERT INTO platform_support_requests(request_id,owner_ref,schema_version,category,"
            "detail_code,status,created_at,updated_at,deleted_at,exported_at) "
            "VALUES('private_strategy_name','owner.alpha',1,'ACCOUNT_ACCESS','LOGIN_FAILED',"
            "'OPEN',:at,:at,NULL,NULL)"), {"at": NOW.replace(tzinfo=None)})
    with engine.connect() as connection, pytest.raises(
            CopyRefusal, match="platform operations source or projection"):
        validate_content_addresses(connection, Base.metadata)


def test_copy_restore_validator_recomputes_entitlement_projection(tmp_path):
    from app.db.copy_contract import CopyRefusal, validate_content_addresses
    from app.platform_operations.contracts import (
        BillingEventState, BillingEventType, BillingMode, BindingState,
        BillingVerifierAuthority, EntitlementSource, EntitlementTransition,
    )
    engine = _engine(tmp_path)
    address = "sha256:" + "a" * 64
    with Session(engine) as session:
        repository = PlatformOperationsRepository(session, tenant=_tenant("owner.alpha"))
        repository.create_billing_binding(
            binding_id="billing.alpha", mode=BillingMode.TEST,
            merchant_address=address, integration_address=address,
            status=BindingState.PENDING, created_at=NOW,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha")
        PlatformOperationsRepository(session, verifier=BillingVerifierAuthority(
            "verifier.local", BillingMode.TEST, address, address)).receive_billing_event(
            receipt_id="receipt.alpha", binding_id="billing.alpha",
            provider_event_ref="event.alpha", event_type=BillingEventType.PAYMENT_CAPTURED,
            event_state=BillingEventState.VERIFIED, raw_body_digest="a" * 64,
            occurred_at=NOW, received_at=NOW,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha",
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_policy_address=address,
            entitlement_valid_from=NOW, entitlement_valid_until=None)
        repository.append_entitlement_event(
            event_id="entitlement.alpha", entitlement_code="PRODUCT_ACCESS",
            mode=BillingMode.TEST, source_kind=EntitlementSource.BILLING_RECEIPT,
            source_ref="receipt.alpha", transition=EntitlementTransition.GRANT,
            policy_address=address, valid_from=NOW, valid_until=None,
            effective_at=NOW, recorded_at=NOW)
        session.commit()
    with engine.connect() as connection:
        validate_content_addresses(connection, Base.metadata)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "UPDATE platform_current_entitlements SET state='INACTIVE'"))
    with engine.connect() as connection, pytest.raises(
            CopyRefusal, match="platform operations source or projection"):
        validate_content_addresses(connection, Base.metadata)
