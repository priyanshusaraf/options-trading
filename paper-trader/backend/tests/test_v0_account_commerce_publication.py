from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.account_commerce import publication
from app.account_commerce.repository import AccountCommerceRefused
from app.api.account_commerce_routes import ProfileInput
from app.api.principal import Principal, SCOPE_ALL, action_for_request
from app.billing.policy_contracts import V0_EXAMPLE_BETA_TRIAL_SECONDS
from app.db.models import (
    Base,
    BrowserSession,
    EnrollmentInvite,
    Membership,
    Organization,
    User,
    UserSession,
)
from app.platform_operations.contracts import (
    BillingInterval,
    CouponState,
    EntitlementEffectTiming,
    EntitlementTransition,
    OperatorAuthority,
    PolicyState,
)
from app.platform_operations.repository import PlatformOperationsRepository


NOW = dt.datetime(2026, 9, 2, 8, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def published(tmp_path, monkeypatch):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'publication.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with Session(engine) as session:
        session.add(Organization(
            organization_id="owner.alpha", name="Synthetic", status="active",
            created_at=NOW.replace(tzinfo=None), updated_at=NOW.replace(tzinfo=None),
        ))
        session.add(User(
            user_id="user.alpha", email_normalized="invited@example.invalid",
            display_name="Synthetic", status="active",
            created_at=NOW.replace(tzinfo=None), updated_at=NOW.replace(tzinfo=None),
        ))
        session.flush()
        session.add(Membership(
            organization_id="owner.alpha", user_id="user.alpha", role="member",
            status="active", created_at=NOW.replace(tzinfo=None),
            updated_at=NOW.replace(tzinfo=None),
        ))
        session.flush()
        session.add(UserSession(
            session_id="session.alpha", token_digest="9" * 64,
            user_id="user.alpha", organization_id="owner.alpha",
            issued_at=(NOW - dt.timedelta(minutes=1)).replace(tzinfo=None),
            expires_at=(NOW + dt.timedelta(hours=1)).replace(tzinfo=None), revoked_at=None,
        ))
        session.flush()
        session.add(BrowserSession(
            session_id="session.alpha", last_seen_at=NOW.replace(tzinfo=None),
        ))
        session.add(EnrollmentInvite(
            invite_digest=hashlib.sha256(b"synthetic invitation").hexdigest(),
            email_normalized="invited@example.invalid", purpose="enrollment",
            created_at=(NOW - dt.timedelta(days=2)).replace(tzinfo=None),
            expires_at=(NOW - dt.timedelta(days=1)).replace(tzinfo=None),
            consumed_at=(NOW - dt.timedelta(days=2)).replace(tzinfo=None),
        ))
        session.commit()
    monkeypatch.setattr(publication, "SessionLocal", factory)
    monkeypatch.setattr(publication, "_utc_now", lambda: NOW)
    principal = Principal(
        id="user.alpha", kind="user", scopes=frozenset({SCOPE_ALL}),
        user_id="user.alpha", organization_id="owner.alpha", role="member",
        session_id="session.alpha",
    )
    return engine, principal


def test_published_router_has_exact_direct_v1_inventory():
    router = publication.build_published_account_commerce_router()
    inventory = {
        (method, route.path)
        for route in router.routes
        for method in (route.methods or set())
    }
    assert inventory == {
        ("GET", "/api/v1/account-commerce/access"),
        ("GET", "/api/v1/account-commerce/status"),
        ("POST", "/api/v1/account-commerce/profile-evidence"),
        ("POST", "/api/v1/account-commerce/trials/beta"),
        ("POST", "/api/v1/account-commerce/trials/coupon"),
        ("POST", "/api/v1/account-commerce/billing/checkout"),
        ("POST", "/api/v1/account-commerce/billing/payment"),
        ("GET", "/api/v1/account-commerce/billing/subscription"),
        ("POST", "/api/v1/account-commerce/billing/refund"),
    }
    assert publication._POLICY.trial_duration_seconds == V0_EXAMPLE_BETA_TRIAL_SECONDS
    assert publication._POLICY.required_profile_fields == (
        "profile.country", "profile.full_name",
    )


def test_profile_attestation_is_transient_and_binds_only_accepted_codes(published):
    _engine, principal = published
    canary_name = "Raw Private Profile Canary"
    attestation = publication._profile_attestor(
        principal, ProfileInput(canary_name, "IN")
    )
    assert attestation.satisfied_field_codes == (
        "profile.country", "profile.full_name",
    )
    assert canary_name not in repr(attestation)
    assert "IN" not in attestation.evidence_address
    assert principal.user_id not in attestation.evidence_address
    assert principal.organization_id not in attestation.evidence_address


def test_invitation_and_prior_use_resolver_uses_consumed_server_fact(published):
    _engine, principal = published
    result = publication._eligibility(principal)
    assert result.eligible is True
    assert result.eligibility_authority_address.startswith("sha256:")
    assert result.prior_use_authority_address.startswith("sha256:")
    assert result.revocation_authority_address.startswith("sha256:")


def test_missing_or_ambiguous_invitation_and_missing_coupon_fail_closed(published):
    engine, principal = published
    with Session(engine) as session:
        session.query(EnrollmentInvite).delete()
        session.commit()
    with pytest.raises(AccountCommerceRefused, match="unavailable"):
        publication._eligibility(principal)
    with pytest.raises(AccountCommerceRefused, match="unavailable"):
        publication._coupon_policy(principal, "RAW-COUPON-CANARY")
    with pytest.raises(AccountCommerceRefused, match="unavailable"):
        publication._coupon_proof(principal, "RAW-COUPON-CANARY")


def test_database_coupon_resolvers_accept_only_corrected_dynamic_duration(published):
    engine, principal = published
    secret = "SYNTHETIC-DYNAMIC-COUPON"
    coupon_policy_address = "sha256:" + "7" * 64
    operator = OperatorAuthority("operator.synthetic", "principal.synthetic")
    with Session(engine) as session:
        PlatformOperationsRepository(session).bind_founder(
            binding_id=operator.binding_id,
            principal_ref=operator.principal_ref,
            permission_profile_address="sha256:" + "8" * 64,
            bootstrap_evidence_address="sha256:" + "6" * 64,
            created_at=NOW,
        )
        operations = PlatformOperationsRepository(session, operator=operator)
        operations.create_plan_version(
            plan_version_id="plan.synthetic.dynamic", plan_code="BETA", version=1,
            amount_minor=0, currency_code="INR",
            billing_interval=BillingInterval.UNKNOWN,
            entitlement_set_address="sha256:" + "5" * 64,
            policy_state=PolicyState.UNKNOWN, created_at=NOW,
        )
        operations.define_coupon(
            coupon_id="coupon.synthetic.dynamic",
            coupon_digest=hashlib.sha256(secret.encode()).hexdigest(),
            plan_version_id="plan.synthetic.dynamic",
            policy_address=coupon_policy_address,
            trial_policy_address=publication._POLICY_ADDRESS,
            discount_policy_address=None,
            valid_from=NOW - dt.timedelta(minutes=1),
            valid_until=NOW + dt.timedelta(days=1),
            max_redemptions=1, per_owner_limit=1, status=CouponState.ACTIVE,
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_effect_timing=EntitlementEffectTiming.DYNAMIC_DURATION,
            entitlement_duration_seconds=V0_EXAMPLE_BETA_TRIAL_SECONDS,
            entitlement_valid_from=None, entitlement_valid_until=None,
            created_at=NOW,
        )
        session.commit()
    policy = publication._coupon_policy(principal, secret)
    proof = publication._coupon_proof(principal, secret)
    assert policy.policy_address == coupon_policy_address
    assert policy.effect.value == "TRIAL_ACCESS"
    assert proof.startswith("sha256:")
    assert secret not in repr(policy)
    assert secret not in proof


@pytest.mark.parametrize("method,path,expected", [
    ("GET", "/api/account-commerce/access", "read:account-commerce"),
    ("GET", "/api/account-commerce/status", "read:account-commerce"),
    ("GET", "/api/account-commerce/billing/subscription", "read:account-commerce"),
    ("POST", "/api/account-commerce/profile-evidence", "write:account-commerce"),
    ("POST", "/api/account-commerce/trials/beta", "write:account-commerce"),
    ("POST", "/api/account-commerce/trials/coupon", "write:account-commerce"),
    ("POST", "/api/account-commerce/billing/checkout", "write:account-commerce"),
    ("POST", "/api/account-commerce/billing/payment", "write:account-commerce"),
    ("POST", "/api/account-commerce/billing/refund", "write:account-commerce"),
])
def test_account_commerce_actions_are_closed(method, path, expected):
    assert action_for_request(method, path) == expected
    assert action_for_request("DELETE", path) is None


def test_main_registers_publication_once_and_never_mounts_or_mirrors_it():
    main = Path(__file__).parents[1] / "app" / "main.py"
    source = main.read_text(encoding="utf-8")
    assert source.count("build_published_account_commerce_router()") == 1
    assert source.count("app.include_router(published_account_commerce_router)") == 1
    assert "mount_versioned(app, published_account_commerce_router" not in source
    assert "routes.router.include_router(published_account_commerce_router" not in source
