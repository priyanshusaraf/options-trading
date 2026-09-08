from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models import (
    AccountProfileEvidenceRow, AccountTrialUseRow, Base, Membership, Organization, User,
)
from app.platform_operations.contracts import (
    BillingEventState, BillingEventType, BillingInterval, BillingMode, BindingState,
    BillingVerifierAuthority,
    CouponState, EntitlementEffectTiming, EntitlementSource, EntitlementState,
    EntitlementTransition,
    GrantAction, MembershipState, OperationsConflict, OperationsNotFound,
    OperationsRefused, OperatorAuthority, PolicyState, SupportCategory, TenantAuthority,
)
from app.platform_operations.repository import (
    PlatformOperationsRepository, validate_persisted_operations,
)


NOW = dt.datetime(2026, 8, 30, 9, 0, tzinfo=dt.timezone.utc)
ADDRESS_A = "sha256:" + "a" * 64
ADDRESS_B = "sha256:" + "b" * 64
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'operations.db'}", future=True)
    @sa.event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    return engine


def _tenant(owner="owner.alpha", state=MembershipState.ACTIVE):
    return TenantAuthority(owner, f"principal.{owner}", state)


def _operator():
    return OperatorAuthority("operator.founder", "principal.founder")


def _verifier():
    return BillingVerifierAuthority(
        "verifier.local", BillingMode.TEST, ADDRESS_A, ADDRESS_B)


def _bind_founder(session):
    PlatformOperationsRepository(session).bind_founder(
        binding_id="operator.founder", principal_ref="principal.founder",
        permission_profile_address=ADDRESS_A,
        bootstrap_evidence_address=ADDRESS_B, created_at=NOW)


def test_beta_trial_is_a_distinct_exact_source_and_rebuilds(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session:
        stamp = NOW.replace(tzinfo=None)
        session.add(Organization(
            organization_id="owner.alpha", name="Synthetic", status="active",
            created_at=stamp, updated_at=stamp,
        ))
        session.add(User(
            user_id="user.alpha", email_normalized="synthetic@example.invalid",
            display_name="Synthetic", status="active", created_at=stamp, updated_at=stamp,
        ))
        session.flush()
        session.add(Membership(
            organization_id="owner.alpha", user_id="user.alpha", role="member",
            status="active", created_at=stamp, updated_at=stamp,
        ))
        session.flush()
        session.add(AccountProfileEvidenceRow(
            profile_evidence_id="profile.alpha", owner_ref="owner.alpha",
            user_ref="user.alpha", policy_address=ADDRESS_A,
            evidence_address=ADDRESS_B,
            satisfied_fields_json='["profile.country","profile.full_name"]',
            attested_at=stamp,
        ))
        session.flush()
        session.add(AccountTrialUseRow(
            trial_use_id="trial.alpha", owner_ref="owner.alpha", user_ref="user.alpha",
            policy_address=ADDRESS_A, profile_evidence_id="profile.alpha",
            source_kind="BETA_TRIAL", source_ref="trial.alpha",
            eligibility_authority_address=ADDRESS_A,
            prior_use_authority_address=ADDRESS_B,
            decision_basis_address="sha256:" + "c" * 64,
            entitlement_code="PRODUCT_ACCESS", entitlement_transition="GRANT",
            entitlement_event_id="entitlement.beta.alpha",
            valid_from=stamp, valid_until=(NOW + dt.timedelta(days=15)).replace(tzinfo=None),
            used_at=stamp,
        ))
        tenant = PlatformOperationsRepository(session, tenant=_tenant())
        current = tenant.append_entitlement_event(
            event_id="entitlement.beta.alpha", entitlement_code="PRODUCT_ACCESS",
            mode=BillingMode.INTERNAL, source_kind=EntitlementSource.BETA_TRIAL,
            source_ref="trial.alpha", transition=EntitlementTransition.GRANT,
            policy_address=ADDRESS_A, valid_from=NOW,
            valid_until=NOW + dt.timedelta(days=15), effective_at=NOW, recorded_at=NOW,
        )
        assert current.state is EntitlementState.ACTIVE
        assert tenant.rebuild_entitlements(rebuilt_at=NOW + dt.timedelta(minutes=1)) == (current,)
        with pytest.raises(OperationsRefused, match="beta trial source"):
            PlatformOperationsRepository(
                session, tenant=_tenant("owner.beta")
            ).append_entitlement_event(
                event_id="entitlement.beta.foreign", entitlement_code="PRODUCT_ACCESS",
                mode=BillingMode.INTERNAL, source_kind=EntitlementSource.BETA_TRIAL,
                source_ref="trial.alpha", transition=EntitlementTransition.GRANT,
                policy_address=ADDRESS_A, valid_from=NOW,
                valid_until=NOW + dt.timedelta(days=15), effective_at=NOW, recorded_at=NOW,
            )


def test_paid_coupon_and_complimentary_facts_are_separate_and_rebuildable(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session:
        _bind_founder(session)
        operator = PlatformOperationsRepository(session, operator=_operator())
        operator.create_plan_version(
            plan_version_id="plan.beta.v1", plan_code="BETA", version=1,
            amount_minor=10000, currency_code="INR",
            billing_interval=BillingInterval.MONTH,
            entitlement_set_address=ADDRESS_A, policy_state=PolicyState.UNKNOWN,
            created_at=NOW)
        operator.define_coupon(
            coupon_id="coupon.beta", coupon_digest=DIGEST_A,
            plan_version_id="plan.beta.v1", policy_address=ADDRESS_A,
            valid_from=NOW, valid_until=NOW + dt.timedelta(days=15),
            max_redemptions=5, per_owner_limit=1, status=CouponState.ACTIVE,
            created_at=NOW, trial_policy_address=ADDRESS_B,
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_valid_from=NOW,
            entitlement_valid_until=NOW + dt.timedelta(days=15))
        operator.add_complimentary_grant(
            grant_id="grant.alpha", owner_ref="owner.alpha",
            entitlement_code="FOUNDER_ACCESS", action=GrantAction.GRANT,
            policy_address=ADDRESS_B, valid_from=NOW, valid_until=None,
            created_at=NOW)
        tenant = PlatformOperationsRepository(session, tenant=_tenant())
        assert tenant.current_entitlement("PRODUCT_ACCESS", BillingMode.INTERNAL).state is EntitlementState.UNKNOWN
        redemption = tenant.redeem_coupon(
            coupon_digest=DIGEST_A, redemption_id="redemption.alpha",
            policy_address=ADDRESS_A, redeemed_at=NOW + dt.timedelta(minutes=1))
        tenant.create_billing_binding(
            binding_id="billing.alpha", mode=BillingMode.TEST,
            merchant_address=ADDRESS_A, integration_address=ADDRESS_B,
            status=BindingState.PENDING, created_at=NOW,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha")
        receipt = PlatformOperationsRepository(session, verifier=_verifier()).receive_billing_event(
            receipt_id="receipt.alpha", binding_id="billing.alpha",
            provider_event_ref="event.alpha", event_type=BillingEventType.PAYMENT_CAPTURED,
            event_state=BillingEventState.VERIFIED, raw_body_digest=DIGEST_B,
            occurred_at=NOW + dt.timedelta(minutes=2),
            received_at=NOW + dt.timedelta(minutes=3), amount_minor=10000,
            currency_code="EUR", provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha",
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_policy_address=ADDRESS_A,
            entitlement_valid_from=NOW,
            entitlement_valid_until=NOW + dt.timedelta(days=30))
        tenant.append_entitlement_event(
            event_id="entitlement.paid", entitlement_code="PRODUCT_ACCESS",
            mode=BillingMode.TEST, source_kind=EntitlementSource.BILLING_RECEIPT,
            source_ref=receipt.receipt_id, transition=EntitlementTransition.GRANT,
            policy_address=ADDRESS_A, valid_from=NOW,
            valid_until=NOW + dt.timedelta(days=30),
            effective_at=NOW + dt.timedelta(minutes=3), recorded_at=NOW + dt.timedelta(minutes=3))
        # An older coupon event is durable but cannot regress the newer projection.
        tenant.append_entitlement_event(
            event_id="entitlement.coupon", entitlement_code="PRODUCT_ACCESS",
            mode=BillingMode.INTERNAL, source_kind=EntitlementSource.COUPON_REDEMPTION,
            source_ref=redemption.redemption_id, transition=EntitlementTransition.GRANT,
            policy_address=ADDRESS_A, valid_from=NOW,
            valid_until=NOW + dt.timedelta(days=15),
            effective_at=NOW + dt.timedelta(minutes=1), recorded_at=NOW + dt.timedelta(minutes=4))
        tenant.append_entitlement_event(
            event_id="entitlement.complimentary", entitlement_code="FOUNDER_ACCESS",
            mode=BillingMode.INTERNAL, source_kind=EntitlementSource.COMPLIMENTARY_GRANT,
            source_ref="grant.alpha", transition=EntitlementTransition.GRANT,
            policy_address=ADDRESS_B, valid_from=NOW, valid_until=None,
            effective_at=NOW + dt.timedelta(minutes=2), recorded_at=NOW + dt.timedelta(minutes=4))
        before = tenant.current_entitlement("PRODUCT_ACCESS", BillingMode.TEST)
        rebuilt = tenant.rebuild_entitlements(rebuilt_at=NOW + dt.timedelta(minutes=5))
        after = tenant.current_entitlement("PRODUCT_ACCESS", BillingMode.TEST)
        assert before == after
        assert {(item.entitlement_code, item.mode, item.state) for item in rebuilt} == {
            ("FOUNDER_ACCESS", BillingMode.INTERNAL, EntitlementState.ACTIVE),
            ("PRODUCT_ACCESS", BillingMode.INTERNAL, EntitlementState.ACTIVE),
            ("PRODUCT_ACCESS", BillingMode.TEST, EntitlementState.ACTIVE),
        }
        session.commit()


def test_dynamic_coupon_resolves_once_from_locked_server_redemption_time(tmp_path):
    engine = _engine(tmp_path)
    redeemed_at = NOW + dt.timedelta(seconds=17, microseconds=901)
    with Session(engine, expire_on_commit=False) as session:
        _bind_founder(session)
        operator = PlatformOperationsRepository(session, operator=_operator())
        operator.create_plan_version(
            plan_version_id="plan.dynamic.v1", plan_code="DYNAMIC", version=1,
            amount_minor=0, currency_code="INR",
            billing_interval=BillingInterval.UNKNOWN,
            entitlement_set_address=ADDRESS_A, policy_state=PolicyState.APPROVED,
            created_at=NOW)
        operator.define_coupon(
            coupon_id="coupon.dynamic", coupon_digest=DIGEST_B,
            plan_version_id="plan.dynamic.v1", policy_address=ADDRESS_A,
            trial_policy_address=ADDRESS_B, discount_policy_address=None,
            valid_from=NOW, valid_until=NOW + dt.timedelta(days=1),
            max_redemptions=1, per_owner_limit=1, status=CouponState.ACTIVE,
            created_at=NOW, entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_valid_from=None, entitlement_valid_until=None,
            entitlement_effect_timing=EntitlementEffectTiming.DYNAMIC_DURATION,
            entitlement_duration_seconds=1_296_000)
        redemption = PlatformOperationsRepository(
            session, tenant=_tenant()
        ).redeem_coupon(
            coupon_digest=DIGEST_B, redemption_id="redemption.dynamic",
            policy_address=ADDRESS_A, redeemed_at=redeemed_at)
        assert redemption.redeemed_at == redeemed_at
        assert redemption.entitlement_valid_from == redeemed_at
        assert redemption.entitlement_valid_until == redeemed_at + dt.timedelta(
            seconds=1_296_000)
        definition = session.execute(sa.text(
            "SELECT entitlement_valid_from,entitlement_valid_until,"
            "entitlement_effect_timing,entitlement_duration_seconds "
            "FROM platform_coupon_definitions WHERE coupon_id='coupon.dynamic'"
        )).one()
        assert definition == (None, None, "DYNAMIC_DURATION", 1_296_000)
        stored = session.execute(sa.text(
            "SELECT entitlement_valid_from,entitlement_valid_until FROM "
            "platform_coupon_redemptions WHERE redemption_id='redemption.dynamic'"
        )).one()
        assert stored == (
            str(redeemed_at.replace(tzinfo=None)),
            str((redeemed_at + dt.timedelta(seconds=1_296_000)).replace(tzinfo=None)),
        )


@pytest.mark.parametrize("redeemed_at", (
    NOW - dt.timedelta(microseconds=1),
    NOW + dt.timedelta(seconds=1),
))
def test_dynamic_coupon_definition_window_is_half_open_and_rolls_back(tmp_path, redeemed_at):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        _bind_founder(session)
        operator = PlatformOperationsRepository(session, operator=_operator())
        operator.create_plan_version(
            plan_version_id="plan.boundary", plan_code="BOUNDARY", version=1,
            amount_minor=0, currency_code="INR",
            billing_interval=BillingInterval.UNKNOWN,
            entitlement_set_address=ADDRESS_A, policy_state=PolicyState.APPROVED,
            created_at=NOW)
        operator.define_coupon(
            coupon_id="coupon.boundary", coupon_digest=DIGEST_B,
            plan_version_id="plan.boundary", policy_address=ADDRESS_A,
            trial_policy_address=ADDRESS_B, valid_from=NOW,
            valid_until=NOW + dt.timedelta(seconds=1), max_redemptions=1,
            per_owner_limit=1, status=CouponState.ACTIVE, created_at=NOW,
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_valid_from=None, entitlement_valid_until=None,
            entitlement_effect_timing=EntitlementEffectTiming.DYNAMIC_DURATION,
            entitlement_duration_seconds=1_296_000)
        session.commit()
        with pytest.raises(OperationsRefused, match="currently admissible"):
            PlatformOperationsRepository(session, tenant=_tenant()).redeem_coupon(
                coupon_digest=DIGEST_B, redemption_id="redemption.boundary",
                policy_address=ADDRESS_A, redeemed_at=redeemed_at)
        session.rollback()
        assert session.scalar(sa.select(sa.func.count()).select_from(
            Base.metadata.tables["platform_coupon_redemptions"])) == 0


@pytest.mark.parametrize("mutation", (
    "dynamic_duration", "dynamic_start", "dynamic_discount", "fixed_duration",
    "unknown_timing",
))
def test_coupon_definition_database_exclusive_shape_refuses_mutation(tmp_path, mutation):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        _bind_founder(session)
        operator = PlatformOperationsRepository(session, operator=_operator())
        operator.create_plan_version(
            plan_version_id="plan.shape.v1", plan_code="SHAPE", version=1,
            amount_minor=0, currency_code="INR",
            billing_interval=BillingInterval.UNKNOWN,
            entitlement_set_address=ADDRESS_A, policy_state=PolicyState.APPROVED,
            created_at=NOW)
        operator.define_coupon(
            coupon_id="coupon.shape", coupon_digest=DIGEST_B,
            plan_version_id="plan.shape.v1", policy_address=ADDRESS_A,
            trial_policy_address=ADDRESS_B, discount_policy_address=None,
            valid_from=NOW, valid_until=None, max_redemptions=1,
            per_owner_limit=1, status=CouponState.ACTIVE, created_at=NOW,
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_valid_from=None, entitlement_valid_until=None,
            entitlement_effect_timing=EntitlementEffectTiming.DYNAMIC_DURATION,
            entitlement_duration_seconds=1_296_000)
        session.commit()
    statements = {
        "dynamic_duration": "entitlement_duration_seconds=1",
        "dynamic_start": "entitlement_valid_from='2026-08-30 09:00:00'",
        "dynamic_discount": f"discount_policy_address='{ADDRESS_A}'",
        "fixed_duration": (
            "entitlement_effect_timing='FIXED_ABSOLUTE',"
            "entitlement_valid_from='2026-08-30 09:00:00',"
            "entitlement_duration_seconds=1296000"
        ),
        "unknown_timing": "entitlement_effect_timing='REQUEST_TIME'",
    }
    with pytest.raises(sa.exc.IntegrityError, match="CHECK constraint failed"):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE platform_coupon_definitions SET " + statements[mutation]
                + " WHERE coupon_id='coupon.shape'")


def test_coupon_definition_shape_guard_is_killed_then_restored(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        _bind_founder(session)
        operator = PlatformOperationsRepository(session, operator=_operator())
        operator.create_plan_version(
            plan_version_id="plan.guard", plan_code="GUARD", version=1,
            amount_minor=0, currency_code="INR",
            billing_interval=BillingInterval.UNKNOWN,
            entitlement_set_address=ADDRESS_A, policy_state=PolicyState.APPROVED,
            created_at=NOW)
        operator.define_coupon(
            coupon_id="coupon.guard", coupon_digest=DIGEST_B,
            plan_version_id="plan.guard", policy_address=ADDRESS_A,
            trial_policy_address=ADDRESS_B, valid_from=NOW, valid_until=None,
            max_redemptions=1, per_owner_limit=1, status=CouponState.ACTIVE,
            created_at=NOW, entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_valid_from=None, entitlement_valid_until=None,
            entitlement_effect_timing=EntitlementEffectTiming.DYNAMIC_DURATION,
            entitlement_duration_seconds=1_296_000)
        session.commit()
    connection = engine.connect()
    transaction = connection.begin()
    original = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' "
        "AND name='platform_coupon_definitions'"
    ).scalar_one()
    check = next(
        item["sqltext"] for item in sa.inspect(connection).get_check_constraints(
            "platform_coupon_definitions")
        if item["name"] == "ck_platform_coupon_entitlement_shape"
    )
    needle = f"CONSTRAINT ck_platform_coupon_entitlement_shape CHECK ({check})"
    assert needle in original
    version = connection.exec_driver_sql("PRAGMA schema_version").scalar_one()
    connection.exec_driver_sql("PRAGMA writable_schema=ON")
    connection.exec_driver_sql(
        "UPDATE sqlite_master SET sql=? WHERE type='table' "
        "AND name='platform_coupon_definitions'",
        (original.replace(needle, "CONSTRAINT ck_platform_coupon_entitlement_shape CHECK (1=1)"),),
    )
    connection.exec_driver_sql("PRAGMA writable_schema=OFF")
    connection.exec_driver_sql(f"PRAGMA schema_version={version + 1}")
    connection.exec_driver_sql(
        "UPDATE platform_coupon_definitions SET entitlement_duration_seconds=1 "
        "WHERE coupon_id='coupon.guard'"
    )
    with pytest.raises(OperationsRefused, match="definition entitlement shape"):
        validate_persisted_operations(connection)
    transaction.rollback()
    connection.close()
    with pytest.raises(sa.exc.IntegrityError, match="CHECK constraint failed"):
        with engine.begin() as restored:
            restored.exec_driver_sql(
                "UPDATE platform_coupon_definitions SET entitlement_duration_seconds=1 "
                "WHERE coupon_id='coupon.guard'"
            )


def test_receipt_dedupe_owner_scope_revocation_and_coupon_limit(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session:
        _bind_founder(session)
        operator = PlatformOperationsRepository(session, operator=_operator())
        operator.create_plan_version(
            plan_version_id="plan.one", plan_code="ONE", version=1, amount_minor=1,
            currency_code="INR", billing_interval=BillingInterval.UNKNOWN,
            entitlement_set_address=ADDRESS_A, policy_state=PolicyState.UNKNOWN,
            created_at=NOW)
        operator.define_coupon(
            coupon_id="coupon.one", coupon_digest=DIGEST_A, plan_version_id="plan.one",
            policy_address=ADDRESS_A, valid_from=NOW, valid_until=None,
            max_redemptions=1, per_owner_limit=1, status=CouponState.ACTIVE,
            created_at=NOW, entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_valid_from=NOW, entitlement_valid_until=None)
        alpha = PlatformOperationsRepository(session, tenant=_tenant())
        alpha.redeem_coupon(coupon_digest=DIGEST_A, redemption_id="redeem.alpha",
                            policy_address=ADDRESS_A, redeemed_at=NOW)
        with pytest.raises(OperationsRefused, match="capacity"):
            PlatformOperationsRepository(session, tenant=_tenant("owner.beta")).redeem_coupon(
                coupon_digest=DIGEST_A, redemption_id="redeem.beta",
                policy_address=ADDRESS_A, redeemed_at=NOW)
        alpha.create_billing_binding(
            binding_id="billing.alpha", mode=BillingMode.TEST,
            merchant_address=ADDRESS_A, integration_address=ADDRESS_B,
            status=BindingState.PENDING, created_at=NOW,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha")
        verifier = PlatformOperationsRepository(session, verifier=_verifier())
        with pytest.raises(OperationsRefused, match="verifier"):
            alpha.receive_billing_event(
                receipt_id="receipt.tenant", binding_id="billing.alpha",
                provider_event_ref="event.tenant", event_type=BillingEventType.PAYMENT_CAPTURED,
                event_state=BillingEventState.VERIFIED, raw_body_digest=DIGEST_A,
                occurred_at=NOW, received_at=NOW,
                provider_customer_ref="customer.alpha",
                provider_subscription_ref="subscription.alpha")
        first = verifier.receive_billing_event(
            receipt_id="receipt.alpha", binding_id="billing.alpha",
            provider_event_ref="event.alpha", event_type=BillingEventType.PAYMENT_CAPTURED,
            event_state=BillingEventState.VERIFIED, raw_body_digest=DIGEST_A,
            occurred_at=NOW, received_at=NOW,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha")
        same = verifier.receive_billing_event(
            receipt_id="receipt.alpha", binding_id="billing.alpha",
            provider_event_ref="event.alpha", event_type=BillingEventType.PAYMENT_CAPTURED,
            event_state=BillingEventState.VERIFIED, raw_body_digest=DIGEST_A,
            occurred_at=NOW, received_at=NOW,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha")
        assert first == same
        with pytest.raises(OperationsConflict):
            verifier.receive_billing_event(
                receipt_id="receipt.other", binding_id="billing.alpha",
                provider_event_ref="event.alpha", event_type=BillingEventType.PAYMENT_CAPTURED,
                event_state=BillingEventState.VERIFIED, raw_body_digest=DIGEST_B,
                occurred_at=NOW, received_at=NOW,
                provider_customer_ref="customer.alpha",
                provider_subscription_ref="subscription.alpha")
        with pytest.raises(OperationsNotFound):
            PlatformOperationsRepository(session, tenant=_tenant("owner.beta")).receive_billing_event(
                receipt_id="receipt.beta", binding_id="billing.alpha",
                provider_event_ref="event.beta", event_type=BillingEventType.PAYMENT_CAPTURED,
                event_state=BillingEventState.REJECTED, raw_body_digest=DIGEST_A,
                occurred_at=NOW, received_at=NOW,
                provider_customer_ref="customer.alpha",
                provider_subscription_ref="subscription.alpha")
        with pytest.raises(OperationsRefused, match="active"):
            PlatformOperationsRepository(
                session, tenant=_tenant(state=MembershipState.REVOKED)).list_support_requests()


def test_receipt_before_effect_survives_restart(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        tenant = PlatformOperationsRepository(session, tenant=_tenant())
        tenant.create_billing_binding(
            binding_id="billing.alpha", mode=BillingMode.TEST,
            merchant_address=ADDRESS_A, integration_address=ADDRESS_B,
            status=BindingState.PENDING, created_at=NOW,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha")
        PlatformOperationsRepository(session, verifier=_verifier()).receive_billing_event(
            receipt_id="receipt.alpha", binding_id="billing.alpha",
            provider_event_ref="event.alpha", event_type=BillingEventType.PAYMENT_CAPTURED,
            event_state=BillingEventState.VERIFIED, raw_body_digest=DIGEST_A,
            occurred_at=NOW, received_at=NOW,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha",
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_policy_address=ADDRESS_A,
            entitlement_valid_from=NOW, entitlement_valid_until=None)
        session.commit()
    with Session(engine) as session:
        tenant = PlatformOperationsRepository(session, tenant=_tenant())
        assert tenant.current_entitlement("PRODUCT_ACCESS", BillingMode.TEST).state is EntitlementState.UNKNOWN
        entitlement = tenant.append_entitlement_event(
            event_id="entitlement.alpha", entitlement_code="PRODUCT_ACCESS",
            mode=BillingMode.TEST, source_kind=EntitlementSource.BILLING_RECEIPT,
            source_ref="receipt.alpha", transition=EntitlementTransition.GRANT,
            policy_address=ADDRESS_A, valid_from=NOW, valid_until=None,
            effective_at=NOW, recorded_at=NOW + dt.timedelta(seconds=1))
        assert entitlement.state is EntitlementState.ACTIVE


def test_concurrent_coupon_capacity_admits_exactly_one_owner(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        _bind_founder(session)
        operator = PlatformOperationsRepository(session, operator=_operator())
        operator.create_plan_version(
            plan_version_id="plan.concurrent", plan_code="CONCURRENT", version=1,
            amount_minor=1, currency_code="INR",
            billing_interval=BillingInterval.UNKNOWN,
            entitlement_set_address=ADDRESS_A, policy_state=PolicyState.UNKNOWN,
            created_at=NOW)
        operator.define_coupon(
            coupon_id="coupon.concurrent", coupon_digest=DIGEST_A,
            plan_version_id="plan.concurrent", policy_address=ADDRESS_A,
            trial_policy_address=ADDRESS_B, discount_policy_address=None,
            valid_from=NOW, valid_until=None, max_redemptions=1,
            per_owner_limit=1, status=CouponState.ACTIVE, created_at=NOW,
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_valid_from=None, entitlement_valid_until=None,
            entitlement_effect_timing=EntitlementEffectTiming.DYNAMIC_DURATION,
            entitlement_duration_seconds=1_296_000)
        session.commit()
    barrier = threading.Barrier(2)
    def redeem(owner):
        with Session(engine) as session:
            barrier.wait()
            try:
                PlatformOperationsRepository(session, tenant=_tenant(owner)).redeem_coupon(
                    coupon_digest=DIGEST_A, redemption_id=f"redeem.{owner}",
                    policy_address=ADDRESS_A, redeemed_at=NOW)
                session.commit()
                return "ACCEPTED"
            except (OperationsConflict, OperationsRefused):
                session.rollback()
                return "REFUSED"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(redeem, ("owner.alpha", "owner.beta")))
    assert sorted(results) == ["ACCEPTED", "REFUSED"]
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT count(*) FROM platform_coupon_redemptions WHERE status='ACCEPTED'")) == 1


def test_entitlement_source_content_inversion_refuses_repository_and_database(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        _bind_founder(session)
        operator = PlatformOperationsRepository(session, operator=_operator())
        operator.add_complimentary_grant(
            grant_id="grant.revoke", owner_ref="owner.alpha",
            entitlement_code="PRODUCT_ACCESS", action=GrantAction.REVOKE,
            policy_address=ADDRESS_A, valid_from=NOW, valid_until=None,
            created_at=NOW)
        tenant = PlatformOperationsRepository(session, tenant=_tenant())
        with pytest.raises(OperationsRefused, match="exactly match"):
            tenant.append_entitlement_event(
                event_id="entitlement.inverted", entitlement_code="FOUNDER_ACCESS",
                mode=BillingMode.INTERNAL,
                source_kind=EntitlementSource.COMPLIMENTARY_GRANT,
                source_ref="grant.revoke", transition=EntitlementTransition.GRANT,
                policy_address=ADDRESS_B, valid_from=NOW, valid_until=None,
                effective_at=NOW, recorded_at=NOW)
        session.commit()
    with engine.begin() as connection, pytest.raises(
            sa.exc.IntegrityError, match="source mismatch"):
        connection.execute(sa.text(
            "INSERT INTO platform_entitlement_events(event_id,owner_ref,entitlement_code,mode,"
            "source_kind,source_ref,transition,policy_address,valid_from,valid_until,effective_at,"
            "recorded_at) VALUES('entitlement.direct','owner.alpha','FOUNDER_ACCESS','INTERNAL',"
            "'COMPLIMENTARY_GRANT','grant.revoke','GRANT',:policy,:at,NULL,:at,:at)"),
            {"policy": ADDRESS_B, "at": NOW.replace(tzinfo=None)})


def test_provider_event_boundary_and_binding_attribution_refuse_replay(tmp_path):
    with pytest.raises(OperationsRefused, match="verifier mode"):
        BillingVerifierAuthority("verifier.invalid", "TEST", ADDRESS_A, ADDRESS_B)
    engine = _engine(tmp_path)
    with Session(engine) as session:
        alpha = PlatformOperationsRepository(session, tenant=_tenant("owner.alpha"))
        beta = PlatformOperationsRepository(session, tenant=_tenant("owner.beta"))
        alpha.create_billing_binding(
            binding_id="billing.alpha", mode=BillingMode.TEST,
            merchant_address=ADDRESS_A, integration_address=ADDRESS_B,
            status=BindingState.PENDING, created_at=NOW,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha")
        beta.create_billing_binding(
            binding_id="billing.beta", mode=BillingMode.TEST,
            merchant_address=ADDRESS_A, integration_address=ADDRESS_B,
            status=BindingState.PENDING, created_at=NOW,
            provider_customer_ref="customer.beta",
            provider_subscription_ref="subscription.beta")
        verifier = PlatformOperationsRepository(session, verifier=_verifier())
        verifier.receive_billing_event(
            receipt_id="receipt.alpha", binding_id="billing.alpha",
            provider_event_ref="provider.event", event_type=BillingEventType.PAYMENT_CAPTURED,
            event_state=BillingEventState.VERIFIED, raw_body_digest=DIGEST_A,
            occurred_at=NOW, received_at=NOW,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha")
        with pytest.raises(OperationsRefused, match="attribution mismatch"):
            verifier.receive_billing_event(
                receipt_id="receipt.substituted", binding_id="billing.beta",
                provider_event_ref="provider.other", event_type=BillingEventType.PAYMENT_CAPTURED,
                event_state=BillingEventState.VERIFIED, raw_body_digest=DIGEST_A,
                occurred_at=NOW, received_at=NOW,
                provider_customer_ref="customer.alpha",
                provider_subscription_ref="subscription.alpha")
        with pytest.raises(OperationsConflict, match="provider event"):
            verifier.receive_billing_event(
                receipt_id="receipt.beta", binding_id="billing.beta",
                provider_event_ref="provider.event", event_type=BillingEventType.PAYMENT_CAPTURED,
                event_state=BillingEventState.VERIFIED, raw_body_digest=DIGEST_A,
                occurred_at=NOW, received_at=NOW,
                provider_customer_ref="customer.beta",
                provider_subscription_ref="subscription.beta")


def test_founder_bootstrap_and_identity_are_immutable(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        _bind_founder(session)
        session.commit()
    for column, value in (
        ("principal_ref", "principal.replacement"),
        ("binding_id", "operator.replacement"),
        ("bootstrap_evidence_address", ADDRESS_A),
    ):
        with engine.begin() as connection, pytest.raises(
                sa.exc.IntegrityError, match="immutable"):
            connection.execute(sa.text(
                f"UPDATE platform_operator_bindings SET {column}=:value WHERE operator_slot='FOUNDER'"),
                {"value": value})


def test_grant_and_reply_require_local_operator_and_request_owner(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        _bind_founder(session)
        PlatformOperationsRepository(session, tenant=_tenant("owner.alpha")).create_support_request(
            request_id="support.alpha", category=SupportCategory.ACCOUNT_ACCESS,
            detail_code="LOGIN_FAILED", created_at=NOW)
        session.commit()
    with engine.begin() as connection, pytest.raises(sa.exc.IntegrityError):
        connection.execute(sa.text(
            "INSERT INTO platform_complimentary_entitlement_grants(grant_id,owner_ref,"
            "entitlement_code,action,policy_address,valid_from,valid_until,operator_binding_id,"
            "created_at) VALUES('grant.forged','owner.alpha','PRODUCT_ACCESS','GRANT',:policy,"
            ":at,NULL,'operator.missing',:at)"),
            {"policy": ADDRESS_A, "at": NOW.replace(tzinfo=None)})
    with engine.begin() as connection, pytest.raises(sa.exc.IntegrityError):
        connection.execute(sa.text(
            "INSERT INTO platform_support_replies(reply_id,request_id,owner_ref,schema_version,"
            "operator_binding_id,response_code,created_at) VALUES('reply.cross','support.alpha',"
            "'owner.beta',1,'operator.founder','ACKNOWLEDGED',:at)"),
            {"at": NOW.replace(tzinfo=None)})
