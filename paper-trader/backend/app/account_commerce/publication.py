"""Production composition for the direct-V1 account-commerce router."""
from __future__ import annotations

import datetime as dt
import hashlib
import json

import sqlalchemy as sa

from app.api.account_commerce_routes import (
    ProfileInput,
    TrialEligibility,
    build_account_commerce_router,
)
from app.api.principal import Principal
from app.billing.policy_contracts import (
    CouponEffect,
    CouponPolicy,
    EntitlementPolicy,
    V0_EXAMPLE_BETA_TRIAL_SECONDS,
)
from app.db.models import (
    AccountProfileEvidenceRow,
    AccountTrialUseRow,
    EnrollmentInvite,
    PlatformCouponDefinitionRow,
    User,
)
from app.db.session import SessionLocal
from app.platform_operations.contracts import EntitlementEffectTiming, EntitlementTransition

from .repository import AccountCommerceRefused
from .service import PRODUCT_ACCESS, ServerProfileAttestation


_PROFILE_FIELDS = ("profile.country", "profile.full_name")
_POLICY_ADDRESS = "sha256:" + hashlib.sha256(
    b"strategy-os-v0-invited-beta-entitlement-policy/1"
).hexdigest()
_POLICY = EntitlementPolicy(
    policy_address=_POLICY_ADDRESS,
    entitlement_set_id="set.internal.beta",
    entitlements=("product.access",),
    required_profile_fields=_PROFILE_FIELDS,
    trial_duration_seconds=V0_EXAMPLE_BETA_TRIAL_SECONDS,
)


def _address(kind: str, **facts: object) -> str:
    material = json.dumps(
        {"kind": kind, **facts}, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(material).hexdigest()


def _principal(principal: Principal) -> tuple[str, str]:
    if (
        type(principal) is not Principal
        or principal.kind != "user"
        or not principal.authenticated
        or not principal.organization_id
        or not principal.user_id
        or principal.id != principal.user_id
        or not principal.session_id
    ):
        raise AccountCommerceRefused("current browser account authority required")
    return principal.organization_id, principal.user_id


def _one(rows: list[object], fact: str):
    if len(rows) != 1:
        raise AccountCommerceRefused(f"current {fact} is unavailable")
    return rows[0]


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _db_utc(value: dt.datetime) -> dt.datetime:
    if not isinstance(value, dt.datetime):
        raise AccountCommerceRefused("current server time is unavailable")
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def _profile_attestor(
    principal: Principal, profile: ProfileInput | None,
) -> ServerProfileAttestation:
    owner_ref, user_ref = _principal(principal)
    if profile is not None:
        if type(profile) is not ProfileInput:
            raise AccountCommerceRefused("current profile attestation is unavailable")
        fields = _PROFILE_FIELDS
    else:
        with SessionLocal() as session:
            rows = list(session.scalars(sa.select(AccountProfileEvidenceRow).where(
                AccountProfileEvidenceRow.owner_ref == owner_ref,
                AccountProfileEvidenceRow.user_ref == user_ref,
                AccountProfileEvidenceRow.policy_address == _POLICY_ADDRESS,
            ).limit(2)))
        row = _one(rows, "profile evidence")
        try:
            fields = tuple(json.loads(row.satisfied_fields_json))
        except (TypeError, ValueError):
            raise AccountCommerceRefused("current profile evidence is unavailable") from None
        if fields != _PROFILE_FIELDS:
            raise AccountCommerceRefused("current profile evidence is unavailable")
    return ServerProfileAttestation(
        evidence_address=_address(
            "account-profile-attestation/1",
            owner_ref=owner_ref,
            user_ref=user_ref,
            policy_address=_POLICY_ADDRESS,
            satisfied_field_codes=fields,
        ),
        satisfied_field_codes=fields,
    )


def _eligibility(principal: Principal) -> TrialEligibility:
    owner_ref, user_ref = _principal(principal)
    with SessionLocal() as session:
        user = session.get(User, user_ref)
        if user is None:
            raise AccountCommerceRefused("current invitation eligibility is unavailable")
        invitations = list(session.scalars(sa.select(EnrollmentInvite).where(
            EnrollmentInvite.email_normalized == user.email_normalized,
            EnrollmentInvite.purpose == "enrollment",
            EnrollmentInvite.consumed_at.is_not(None),
        ).limit(2)))
        invitation = _one(invitations, "invitation eligibility")
        prior_rows = list(session.scalars(sa.select(AccountTrialUseRow).where(
            AccountTrialUseRow.owner_ref == owner_ref,
            AccountTrialUseRow.user_ref == user_ref,
            AccountTrialUseRow.policy_address == _POLICY_ADDRESS,
        ).limit(2)))
    prior_identity = None if not prior_rows else _one(prior_rows, "prior-use evidence").trial_use_id
    return TrialEligibility(
        eligible=True,
        eligibility_authority_address=_address(
            "invited-enrollment-eligibility/1",
            owner_ref=owner_ref,
            user_ref=user_ref,
            invitation_digest=invitation.invite_digest,
            consumed_at=_db_utc(invitation.consumed_at).isoformat(),
        ),
        prior_use_authority_address=_address(
            "account-trial-prior-use/1",
            owner_ref=owner_ref,
            user_ref=user_ref,
            policy_address=_POLICY_ADDRESS,
            prior_use_identity=prior_identity,
        ),
        revocation_authority_address=_address(
            "account-trial-revocation-authority/1",
            policy_address=_POLICY_ADDRESS,
        ),
    )


def _coupon_definition(principal: Principal, coupon_plaintext: str) -> tuple[
    PlatformCouponDefinitionRow, str, str, str
]:
    owner_ref, user_ref = _principal(principal)
    if not isinstance(coupon_plaintext, str):
        raise AccountCommerceRefused("current coupon policy is unavailable")
    try:
        encoded = coupon_plaintext.encode("utf-8", errors="strict")
    except UnicodeError:
        raise AccountCommerceRefused("current coupon policy is unavailable") from None
    if not 1 <= len(encoded) <= 256:
        raise AccountCommerceRefused("current coupon policy is unavailable")
    coupon_digest = hashlib.sha256(encoded).hexdigest()
    with SessionLocal() as session:
        rows = list(session.scalars(sa.select(PlatformCouponDefinitionRow).where(
            PlatformCouponDefinitionRow.coupon_digest == coupon_digest,
        ).limit(2)))
        definition = _one(rows, "coupon policy")
        session.expunge(definition)
    now = _utc_now()
    valid_from = _db_utc(definition.valid_from)
    valid_until = None if definition.valid_until is None else _db_utc(definition.valid_until)
    if (
        definition.status != "ACTIVE"
        or now < valid_from
        or (valid_until is not None and now >= valid_until)
        or definition.trial_policy_address != _POLICY_ADDRESS
        or definition.discount_policy_address is not None
        or definition.entitlement_code != PRODUCT_ACCESS
        or definition.entitlement_transition != EntitlementTransition.GRANT.value
        or definition.entitlement_effect_timing
        != EntitlementEffectTiming.DYNAMIC_DURATION.value
        or definition.entitlement_duration_seconds
        != V0_EXAMPLE_BETA_TRIAL_SECONDS
        or definition.entitlement_valid_from is not None
        or definition.entitlement_valid_until is not None
    ):
        raise AccountCommerceRefused("current coupon policy is unavailable")
    return definition, coupon_digest, owner_ref, user_ref


def _coupon_policy(principal: Principal, coupon_plaintext: str) -> CouponPolicy:
    definition, _digest, _owner_ref, _user_ref = _coupon_definition(
        principal, coupon_plaintext
    )
    return CouponPolicy(
        policy_address=definition.policy_address,
        entitlement_policy_address=_POLICY_ADDRESS,
        verifier_address=_address(
            "account-coupon-verifier/1", policy_address=definition.policy_address
        ),
        effect=CouponEffect.TRIAL_ACCESS,
        effect_policy_address=_address(
            "account-coupon-trial-effect/1",
            policy_address=definition.policy_address,
            entitlement_policy_address=_POLICY_ADDRESS,
        ),
    )


def _coupon_proof(principal: Principal, coupon_plaintext: str) -> str:
    definition, coupon_digest, owner_ref, user_ref = _coupon_definition(
        principal, coupon_plaintext
    )
    return _address(
        "account-coupon-proof/1",
        owner_ref=owner_ref,
        user_ref=user_ref,
        policy_address=definition.policy_address,
        coupon_digest=coupon_digest,
    )


def build_published_account_commerce_router():
    """Compose the accepted production router without a mirror or provider seam."""
    return build_account_commerce_router(
        sessionmaker=SessionLocal,
        policy=_POLICY,
        clock=_utc_now,
        profile_attestor=_profile_attestor,
        eligibility_resolver=_eligibility,
        coupon_policy_resolver=_coupon_policy,
        coupon_proof_resolver=_coupon_proof,
    )
