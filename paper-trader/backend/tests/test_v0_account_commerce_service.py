from __future__ import annotations

import datetime as dt
import ast
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.account_commerce import (
    AccountCommerceConflict,
    AccountCommerceRefused,
    AccountCommerceService,
    ServerProfileAttestation,
)
from app.account_commerce.repository import validate_persisted_account_commerce
from app.account_commerce.repository import AccountAuthority, AccountCommerceRepository
import app.account_commerce.repository as account_commerce_repository
from app.api.principal import Principal, SCOPE_ALL
from app.accounts.browser_auth import ABSOLUTE, IDLE
from app.billing.policy_contracts import CouponEffect, CouponPolicy, EntitlementPolicy
from app.db.models import (
    AccountProfileEvidenceRow,
    AccountTrialUseRow,
    Base,
    BrowserSession,
    Membership,
    Organization,
    PlatformCouponDefinitionRow,
    PlatformCouponRedemptionRow,
    PlatformEntitlementEventRow,
    PlatformOperatorBindingRow,
    User,
    UserSession,
)
from app.platform_operations.contracts import (
    BillingInterval,
    CouponState,
    EntitlementEffectTiming,
    EntitlementTransition,
    OperatorAuthority,
    OperatorBindingState,
    PolicyState,
)
from app.platform_operations.repository import (
    PlatformOperationsRepository, validate_persisted_operations,
)


NOW = dt.datetime(2026, 9, 1, 6, 0, tzinfo=dt.timezone.utc)
POLICY = "sha256:" + "a" * 64
COUPON_POLICY = "sha256:" + "b" * 64
EVIDENCE = "sha256:" + "c" * 64
ELIGIBILITY = "sha256:" + "d" * 64
PRIOR = "sha256:" + "e" * 64
REVOCATION = "sha256:" + "f" * 64
PLAN_SET = "sha256:" + "1" * 64
OPERATOR_PROFILE = "sha256:" + "2" * 64
OPERATOR_BOOTSTRAP = "sha256:" + "3" * 64


def _engine(tmp_path, name="commerce.db"):
    engine = sa.create_engine(f"sqlite:///{tmp_path / name}", future=True)

    @sa.event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine


def _policy() -> EntitlementPolicy:
    return EntitlementPolicy(
        policy_address=POLICY,
        entitlement_set_id="set.internal.beta",
        entitlements=("product.access",),
        required_profile_fields=("profile.country", "profile.full_name"),
        trial_duration_seconds=1_296_000,
    )


def _seed(session: Session, *, owner="owner.alpha", user="user.alpha",
          membership="active") -> Principal:
    session.add(Organization(
        organization_id=owner, name="Synthetic", status="active",
        created_at=NOW.replace(tzinfo=None), updated_at=NOW.replace(tzinfo=None),
    ))
    session.add(User(
        user_id=user, email_normalized=f"{user}@example.invalid",
        display_name="Synthetic", status="active",
        created_at=NOW.replace(tzinfo=None), updated_at=NOW.replace(tzinfo=None),
    ))
    session.flush()
    session.add(Membership(
        organization_id=owner, user_id=user, role="member", status=membership,
        created_at=NOW.replace(tzinfo=None), updated_at=NOW.replace(tzinfo=None),
    ))
    session.flush()
    session.add(UserSession(
        session_id=f"session.{user}", token_digest="9" * 64,
        user_id=user, organization_id=owner,
        issued_at=NOW.replace(tzinfo=None),
        expires_at=(NOW + dt.timedelta(days=30)).replace(tzinfo=None),
        revoked_at=None,
    ))
    session.flush()
    session.add(BrowserSession(
        session_id=f"session.{user}", last_seen_at=NOW.replace(tzinfo=None)
    ))
    session.commit()
    return Principal(
        id=user, kind="user", scopes=frozenset({SCOPE_ALL}), user_id=user,
        organization_id=owner, role="member", session_id=f"session.{user}",
    )


def _attestation(fields=("profile.country", "profile.full_name")):
    return ServerProfileAttestation(EVIDENCE, fields)


def _beta(service: AccountCommerceService, *, at=NOW, fields=None):
    return service.grant_beta_trial(
        attestation=_attestation() if fields is None else _attestation(fields),
        eligibility_authority_address=ELIGIBILITY,
        prior_use_authority_address=PRIOR,
        revocation_authority_address=REVOCATION,
        eligible=True,
        server_time=at,
    )


def _bind_operator(session: Session) -> OperatorAuthority:
    PlatformOperationsRepository(session).bind_founder(
        binding_id="operator.founder", principal_ref="principal.founder",
        permission_profile_address=OPERATOR_PROFILE,
        bootstrap_evidence_address=OPERATOR_BOOTSTRAP, created_at=NOW,
    )
    session.commit()
    return OperatorAuthority("operator.founder", "principal.founder")


def _fresh_browser_principal(
    session: Session, principal: Principal, *, at: dt.datetime, suffix: str
) -> Principal:
    session_id = f"session.{principal.user_id}.{suffix}"
    session.add(UserSession(
        session_id=session_id, token_digest=(suffix[0] * 64),
        user_id=principal.user_id, organization_id=principal.organization_id,
        issued_at=(at - dt.timedelta(minutes=1)).replace(tzinfo=None),
        expires_at=(at + dt.timedelta(hours=1)).replace(tzinfo=None), revoked_at=None,
    ))
    session.flush()
    session.add(BrowserSession(
        session_id=session_id, last_seen_at=at.replace(tzinfo=None)
    ))
    session.commit()
    return Principal(
        id=principal.user_id, kind="user", scopes=principal.scopes,
        user_id=principal.user_id, organization_id=principal.organization_id,
        role=principal.role, session_id=session_id,
    )


def test_beta_is_exact_single_use_idempotent_rebuildable_and_expires(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        first = _beta(AccountCommerceService(session, principal=principal, policy=_policy()))
        assert first.source_kind == "BETA_TRIAL"
        assert first.valid_until - NOW == dt.timedelta(seconds=1_296_000)
        assert first.access_active is True

    with Session(engine, expire_on_commit=False) as session:
        repeated = _beta(AccountCommerceService(session, principal=principal, policy=_policy()))
        assert repeated == first
        day_one_principal = _fresh_browser_principal(
            session, principal, at=NOW + dt.timedelta(days=1), suffix="d"
        )
        service = AccountCommerceService(
            session, principal=day_one_principal, policy=_policy()
        )
        assert service.rebuild_access(server_time=NOW + dt.timedelta(days=1)).state == "ACTIVE"
        expiry_principal = _fresh_browser_principal(
            session, principal, at=NOW + dt.timedelta(days=15), suffix="e"
        )
        assert AccountCommerceService(
            session, principal=expiry_principal, policy=_policy()
        ).current_access(server_time=NOW + dt.timedelta(days=15)).state == "EXPIRED"
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountTrialUseRow)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(PlatformEntitlementEventRow)) == 1
    with engine.connect() as connection:
        validate_persisted_account_commerce(connection)
        validate_persisted_operations(connection)


@pytest.mark.parametrize(
    "authority_mutation",
    (
        "wrong_principal_id", "service_principal", "idle_boundary", "absolute_boundary",
        "expired", "revoked", "membership_inactive", "user_inactive",
        "organization_inactive",
    ),
)
def test_exact_current_browser_predicates_refuse_before_any_account_write(
    tmp_path, authority_mutation
):
    engine = _engine(tmp_path, f"browser-{authority_mutation}.db")
    with Session(engine) as session:
        principal = _seed(session)
        user_session = session.get(UserSession, principal.session_id)
        browser_session = session.get(BrowserSession, principal.session_id)
        if authority_mutation == "wrong_principal_id":
            principal = Principal(
                id="user.substituted", kind="user", scopes=principal.scopes,
                user_id=principal.user_id, organization_id=principal.organization_id,
                role=principal.role, session_id=principal.session_id,
            )
        elif authority_mutation == "service_principal":
            principal = Principal(
                id=principal.id, kind="service", scopes=principal.scopes,
                user_id=principal.user_id, organization_id=principal.organization_id,
                role=principal.role, session_id=principal.session_id,
            )
        elif authority_mutation == "idle_boundary":
            browser_session.last_seen_at = (NOW - IDLE).replace(tzinfo=None)
        elif authority_mutation == "absolute_boundary":
            user_session.issued_at = (NOW - ABSOLUTE).replace(tzinfo=None)
        elif authority_mutation == "expired":
            user_session.expires_at = NOW.replace(tzinfo=None)
        elif authority_mutation == "revoked":
            user_session.revoked_at = NOW.replace(tzinfo=None)
        elif authority_mutation == "membership_inactive":
            session.get(Membership, (principal.organization_id, principal.user_id)).status = "revoked"
        elif authority_mutation == "user_inactive":
            session.get(User, principal.user_id).status = "disabled"
        else:
            session.get(Organization, principal.organization_id).status = "disabled"
        session.commit()

        with pytest.raises(AccountCommerceRefused, match="browser principal"):
            _beta(AccountCommerceService(session, principal=principal, policy=_policy()))
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountProfileEvidenceRow)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountTrialUseRow)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(PlatformEntitlementEventRow)) == 0


def test_browser_idle_use_time_guard_is_killed_then_restored(tmp_path, monkeypatch):
    engine = _engine(tmp_path, "browser-idle-use-time-mutation.db")
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        session.get(BrowserSession, principal.session_id).last_seen_at = (
            NOW - IDLE
        ).replace(tzinfo=None)
        session.commit()
        with pytest.raises(AccountCommerceRefused, match="browser principal"):
            _beta(AccountCommerceService(session, principal=principal, policy=_policy()))
        with monkeypatch.context() as mutation:
            mutation.setattr(
                account_commerce_repository, "IDLE", IDLE + dt.timedelta(seconds=1)
            )
            escaped = _beta(AccountCommerceService(
                session, principal=principal, policy=_policy()
            ))
            assert escaped.access_active is True
    with Session(engine) as session:
        with pytest.raises(AccountCommerceRefused, match="browser principal"):
            AccountCommerceService(
                session, principal=principal, policy=_policy()
            ).current_access(server_time=NOW)


def test_concurrent_beta_requests_retry_to_one_source_event_and_projection(tmp_path):
    engine = _engine(tmp_path, "concurrent.db")
    with Session(engine) as session:
        principal = _seed(session)
    barrier = threading.Barrier(2)

    def admit():
        barrier.wait()
        for attempt in range(3):
            try:
                with Session(engine, expire_on_commit=False) as session:
                    return _beta(AccountCommerceService(
                        session, principal=principal, policy=_policy()
                    ))
            except OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == 2:
                    raise
                time.sleep(0.05)
        raise AssertionError("unreachable")

    with ThreadPoolExecutor(max_workers=2) as pool:
        grants = tuple(pool.map(lambda _item: admit(), range(2)))
    assert grants[0].entitlement_event_id == grants[1].entitlement_event_id
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountTrialUseRow)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(PlatformEntitlementEventRow)) == 1


@pytest.mark.parametrize("principal_mutation", ("anonymous", "foreign", "revoked", "no_browser"))
def test_anonymous_foreign_revoked_and_nonbrowser_principals_refuse_before_write(
    tmp_path, principal_mutation
):
    engine = _engine(tmp_path, f"{principal_mutation}.db")
    with Session(engine) as session:
        principal = _seed(session)
        if principal_mutation == "anonymous":
            principal = None
        elif principal_mutation == "foreign":
            principal = Principal(
                id=principal.id, kind="user", scopes=principal.scopes,
                user_id=principal.user_id, organization_id="owner.foreign",
                role="member", session_id=principal.session_id,
            )
        elif principal_mutation == "revoked":
            row = session.get(UserSession, principal.session_id)
            row.revoked_at = NOW.replace(tzinfo=None)
            session.commit()
        else:
            session.delete(session.get(BrowserSession, principal.session_id))
            session.commit()
        with pytest.raises(AccountCommerceRefused, match="browser principal"):
            _beta(AccountCommerceService(session, principal=principal, policy=_policy()))
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountProfileEvidenceRow)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountTrialUseRow)) == 0


def test_profile_field_and_policy_guards_reject_missing_unknown_and_raw_values(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        principal = _seed(session)
        service = AccountCommerceService(session, principal=principal, policy=_policy())
        with pytest.raises(AccountCommerceRefused, match="MISSING_PROFILE_EVIDENCE"):
            _beta(service, fields=("profile.country",))
        with pytest.raises(AccountCommerceRefused, match="unknown profile field"):
            _beta(
                AccountCommerceService(session, principal=principal, policy=_policy()),
                fields=("profile.country", "customer@example.invalid"),
            )
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountTrialUseRow)) == 0
        rows = session.scalars(sa.select(AccountProfileEvidenceRow)).all()
        assert all("Synthetic" not in row.satisfied_fields_json for row in rows)
        assert all("@example" not in row.satisfied_fields_json for row in rows)


def test_prior_use_blocks_coupon_after_beta_and_coupon_plaintext_never_persists(tmp_path):
    engine = _engine(tmp_path)
    secret = "SECRET-TRIAL-COUPON"
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        _beta(AccountCommerceService(session, principal=principal, policy=_policy()))
        with pytest.raises(AccountCommerceConflict, match="another source"):
            AccountCommerceService(session, principal=principal, policy=_policy()).grant_coupon_trial(
                coupon_plaintext=secret,
                coupon_policy=CouponPolicy(
                    policy_address=COUPON_POLICY,
                    entitlement_policy_address=POLICY,
                    verifier_address="coupon.verifier.internal",
                    effect=CouponEffect.TRIAL_ACCESS,
                    effect_policy_address="coupon.effect.trial",
                ),
                coupon_proof_address="coupon.proof.internal",
                attestation=_attestation(),
                eligibility_authority_address=ELIGIBILITY,
                prior_use_authority_address=PRIOR,
                revocation_authority_address=REVOCATION,
                eligible=True,
                server_time=NOW,
            )
    database_bytes = (tmp_path / "commerce.db").read_bytes()
    assert secret.encode() not in database_bytes


def test_coupon_trial_uses_digest_capacity_policy_and_exact_source(tmp_path):
    engine = _engine(tmp_path)
    secret = "BETA-ACCESS-ONLY"
    redeemed_at = NOW + dt.timedelta(microseconds=68_105)
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        operator = _bind_operator(session)
        operations = PlatformOperationsRepository(session, operator=operator)
        operations.create_plan_version(
            plan_version_id="plan.beta.v1", plan_code="BETA", version=1,
            amount_minor=0, currency_code="INR",
            billing_interval=BillingInterval.UNKNOWN,
            entitlement_set_address=PLAN_SET, policy_state=PolicyState.UNKNOWN,
            created_at=NOW,
        )
        operations.define_coupon(
            coupon_id="coupon.beta", coupon_digest=__import__("hashlib").sha256(
                secret.encode()
            ).hexdigest(),
            plan_version_id="plan.beta.v1", policy_address=COUPON_POLICY,
            trial_policy_address=POLICY, discount_policy_address=None,
            valid_from=NOW, valid_until=NOW + dt.timedelta(days=1),
            max_redemptions=1, per_owner_limit=1, status=CouponState.ACTIVE,
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_valid_from=None,
            entitlement_valid_until=None,
            entitlement_effect_timing=EntitlementEffectTiming.DYNAMIC_DURATION,
            entitlement_duration_seconds=1_296_000,
            created_at=NOW,
        )
        session.commit()
        grant = AccountCommerceService(session, principal=principal, policy=_policy()).grant_coupon_trial(
            coupon_plaintext=secret,
            coupon_policy=CouponPolicy(
                policy_address=COUPON_POLICY,
                entitlement_policy_address=POLICY,
                verifier_address="coupon.verifier.internal",
                effect=CouponEffect.TRIAL_ACCESS,
                effect_policy_address="coupon.effect.trial",
            ),
            coupon_proof_address="coupon.proof.internal",
            attestation=_attestation(),
            eligibility_authority_address=ELIGIBILITY,
            prior_use_authority_address=PRIOR,
            revocation_authority_address=REVOCATION,
            eligible=True,
            server_time=redeemed_at,
        )
        assert grant.source_kind == "COUPON_REDEMPTION"
        redemption = session.get(PlatformCouponRedemptionRow, grant.source_ref)
        trial = session.scalar(sa.select(AccountTrialUseRow).where(
            AccountTrialUseRow.source_ref == grant.source_ref
        ))
        event = session.get(PlatformEntitlementEventRow, grant.entitlement_event_id)
        assert event.source_ref == grant.source_ref
        expected_start = redeemed_at.replace(tzinfo=None)
        expected_end = (redeemed_at + dt.timedelta(seconds=1_296_000)).replace(tzinfo=None)
        assert (redemption.entitlement_valid_from, redemption.entitlement_valid_until) == (
            expected_start, expected_end)
        assert (trial.valid_from, trial.valid_until) == (expected_start, expected_end)
        assert (event.valid_from, event.valid_until) == (expected_start, expected_end)
        definition = session.get(PlatformCouponDefinitionRow, "coupon.beta")
        assert (definition.entitlement_valid_from, definition.entitlement_valid_until) == (
            None, None)
        assert secret not in repr(grant)

        at_expiry = redeemed_at + dt.timedelta(seconds=1_296_000)
        expiry_principal = _fresh_browser_principal(
            session, principal, at=at_expiry, suffix="a"
        )
        repeated = AccountCommerceService(
            session, principal=expiry_principal, policy=_policy()
        ).grant_coupon_trial(
            coupon_plaintext=secret,
            coupon_policy=CouponPolicy(
                policy_address=COUPON_POLICY,
                entitlement_policy_address=POLICY,
                verifier_address="coupon.verifier.internal",
                effect=CouponEffect.TRIAL_ACCESS,
                effect_policy_address="coupon.effect.trial",
            ),
            coupon_proof_address="coupon.proof.internal",
            attestation=_attestation(),
            eligibility_authority_address=ELIGIBILITY,
            prior_use_authority_address=PRIOR,
            revocation_authority_address=REVOCATION,
            eligible=True,
            server_time=at_expiry,
        )
        assert repeated.entitlement_event_id == grant.entitlement_event_id
        assert repeated.access_active is False
        assert AccountCommerceService(
            session, principal=expiry_principal, policy=_policy()
        ).current_access(server_time=at_expiry).state == "EXPIRED"


def test_founder_access_requires_current_operator_binding_and_is_ordinary_access(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        operator = OperatorAuthority("operator.founder", "principal.founder")
        with pytest.raises(ValueError, match="operator binding"):
            AccountCommerceService(session, principal=principal, policy=_policy()).grant_founder_access(
                operator=operator, revocation_authority_address=REVOCATION,
                server_time=NOW,
            )
        operator = _bind_operator(session)
        grant = AccountCommerceService(
            session, principal=principal, policy=_policy()
        ).grant_founder_access(
            operator=operator, revocation_authority_address=REVOCATION,
            server_time=NOW,
        )
        assert grant.source_kind == "COMPLIMENTARY_GRANT"
        assert grant.access_active is True
        assert session.get(PlatformOperatorBindingRow, "FOUNDER").principal_ref == "principal.founder"
        session.rollback()  # close the read-only inspection transaction
        repeated = AccountCommerceService(
            session, principal=principal, policy=_policy()
        ).grant_founder_access(
            operator=operator, revocation_authority_address=REVOCATION,
            server_time=NOW + dt.timedelta(minutes=1),
        )
        assert repeated.entitlement_event_id == grant.entitlement_event_id
        revoked = AccountCommerceService(
            session, principal=principal, policy=_policy()
        ).revoke_founder_access(
            operator=operator, revocation_authority_address=REVOCATION,
            server_time=NOW + dt.timedelta(minutes=2),
        )
        assert revoked.access_active is False
        assert AccountCommerceService(
            session, principal=principal, policy=_policy()
        ).rebuild_access(server_time=NOW + dt.timedelta(minutes=3)).state == "INACTIVE"


def test_founder_existing_grant_and_revoke_revalidate_exact_operator_principal(tmp_path):
    engine = _engine(tmp_path, "founder-reuse-principal.db")
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        operator = _bind_operator(session)
        service = AccountCommerceService(session, principal=principal, policy=_policy())
        service.grant_founder_access(
            operator=operator, revocation_authority_address=REVOCATION, server_time=NOW
        )
        wrong = OperatorAuthority(operator.binding_id, "principal.foreign")
        with pytest.raises(ValueError, match="operator binding"):
            AccountCommerceService(
                session, principal=principal, policy=_policy()
            ).grant_founder_access(
                operator=wrong, revocation_authority_address=REVOCATION,
                server_time=NOW + dt.timedelta(minutes=1),
            )
        with pytest.raises(ValueError, match="operator binding"):
            AccountCommerceService(
                session, principal=principal, policy=_policy()
            ).revoke_founder_access(
                operator=wrong, revocation_authority_address=REVOCATION,
                server_time=NOW + dt.timedelta(minutes=2),
            )


def test_founder_existing_source_refuses_noncurrent_operator_binding(tmp_path):
    engine = _engine(tmp_path, "founder-noncurrent.db")
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        operator = _bind_operator(session)
        AccountCommerceService(
            session, principal=principal, policy=_policy()
        ).grant_founder_access(
            operator=operator, revocation_authority_address=REVOCATION, server_time=NOW
        )
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER platform_operator_bindings_refuse_update")
        connection.exec_driver_sql(
            "UPDATE platform_operator_bindings SET status=?, revoked_at=? "
            "WHERE operator_slot='FOUNDER'",
            (OperatorBindingState.REVOKED.value, NOW.replace(tzinfo=None)),
        )
    with Session(engine) as session:
        with pytest.raises(ValueError, match="operator binding"):
            AccountCommerceService(
                session, principal=principal, policy=_policy()
            ).grant_founder_access(
                operator=operator, revocation_authority_address=REVOCATION,
                server_time=NOW + dt.timedelta(minutes=1),
            )


def test_operator_use_time_guard_is_killed_then_restored(tmp_path, monkeypatch):
    engine = _engine(tmp_path, "operator-use-time-mutation.db")
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        operator = _bind_operator(session)
        AccountCommerceService(
            session, principal=principal, policy=_policy()
        ).grant_founder_access(
            operator=operator, revocation_authority_address=REVOCATION, server_time=NOW
        )
        wrong = OperatorAuthority(operator.binding_id, "principal.foreign")
        with monkeypatch.context() as mutation:
            mutation.setattr(
                PlatformOperationsRepository, "_operator_row",
                lambda repository: repository.session.get(
                    PlatformOperatorBindingRow, "FOUNDER"
                ),
            )
            escaped = AccountCommerceService(
                session, principal=principal, policy=_policy()
            ).grant_founder_access(
                operator=wrong, revocation_authority_address=REVOCATION,
                server_time=NOW + dt.timedelta(minutes=1),
            )
            assert escaped.access_active is True
        with pytest.raises(ValueError, match="operator binding"):
            AccountCommerceService(
                session, principal=principal, policy=_policy()
            ).grant_founder_access(
                operator=wrong, revocation_authority_address=REVOCATION,
                server_time=NOW + dt.timedelta(minutes=2),
            )


def test_duplicate_beta_is_inactive_at_and_after_supplied_expiry_time(tmp_path):
    engine = _engine(tmp_path, "beta-expiry-retry.db")
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        first = _beta(AccountCommerceService(
            session, principal=principal, policy=_policy()
        ))
        for index, delta in enumerate((dt.timedelta(days=15), dt.timedelta(days=16))):
            at = NOW + delta
            current_principal = _fresh_browser_principal(
                session, principal, at=at, suffix=chr(ord("b") + index)
            )
            repeated = _beta(AccountCommerceService(
                session, principal=current_principal, policy=_policy()
            ), at=at)
            assert repeated.entitlement_event_id == first.entitlement_event_id
            assert repeated.access_active is False
            assert AccountCommerceService(
                session, principal=current_principal, policy=_policy()
            ).current_access(server_time=at).state == "EXPIRED"


def test_duplicate_trial_expiry_use_time_guard_is_killed_then_restored(
    tmp_path, monkeypatch
):
    engine = _engine(tmp_path, "trial-expiry-use-time-mutation.db")
    at_expiry = NOW + dt.timedelta(days=15)
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        _beta(AccountCommerceService(session, principal=principal, policy=_policy()))
        expiry_principal = _fresh_browser_principal(
            session, principal, at=at_expiry, suffix="f"
        )
        with monkeypatch.context() as mutation:
            mutation.setattr(
                AccountCommerceService, "_access_active_at",
                staticmethod(lambda _current, _server_time: True),
            )
            escaped = _beta(AccountCommerceService(
                session, principal=expiry_principal, policy=_policy()
            ), at=at_expiry)
            assert escaped.access_active is True
        restored = _beta(AccountCommerceService(
            session, principal=expiry_principal, policy=_policy()
        ), at=at_expiry)
        assert restored.access_active is False


def test_transaction_failure_leaves_no_profile_trial_event_or_projection(tmp_path, monkeypatch):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        principal = _seed(session)

        def die(*_args, **_kwargs):
            raise RuntimeError("injected death")

        monkeypatch.setattr(PlatformOperationsRepository, "append_entitlement_event", die)
        with pytest.raises(RuntimeError, match="injected death"):
            _beta(AccountCommerceService(session, principal=principal, policy=_policy()))
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountProfileEvidenceRow)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountTrialUseRow)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(PlatformEntitlementEventRow)) == 0


def test_price_adjustment_coupon_stays_unavailable_before_any_write(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        principal = _seed(session)
        with pytest.raises(AccountCommerceRefused, match="PRICE_ADJUSTMENT_UNAVAILABLE"):
            AccountCommerceService(session, principal=principal, policy=_policy()).grant_coupon_trial(
                coupon_plaintext="not-stored",
                coupon_policy=CouponPolicy(
                    policy_address=COUPON_POLICY,
                    entitlement_policy_address=POLICY,
                    verifier_address="coupon.verifier.internal",
                    effect=CouponEffect.PRICE_ADJUSTMENT,
                    effect_policy_address="coupon.effect.price.closed",
                ),
                coupon_proof_address="coupon.proof.internal",
                attestation=_attestation(), eligibility_authority_address=ELIGIBILITY,
                prior_use_authority_address=PRIOR,
                revocation_authority_address=REVOCATION, eligible=True,
                server_time=NOW,
            )
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountTrialUseRow)) == 0


def test_service_return_types_have_no_private_trading_or_payment_fields():
    annotations = " ".join(
        field for cls in (__import__("app.account_commerce.service", fromlist=["AccessGrant"]).AccessGrant,
                          __import__("app.account_commerce.service", fromlist=["AccessStatus"]).AccessStatus)
        for field in cls.__dataclass_fields__
    ).lower()
    for forbidden in ("strategy", "pnl", "position", "broker", "credential", "payment", "coupon_plaintext"):
        assert forbidden not in annotations


def test_account_commerce_has_no_public_or_private_trading_import_surface():
    package = Path(__file__).parents[1] / "app" / "account_commerce"
    imported = set()
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
    forbidden_prefixes = (
        "app.execution", "app.engine", "app.providers", "app.strategy",
        "app.backtest", "research", "app.api.routes", "app.main",
    )
    assert not {
        name for name in imported if name.startswith(forbidden_prefixes)
    }
    for table in (AccountProfileEvidenceRow.__table__, AccountTrialUseRow.__table__):
        columns = {column.name.lower() for column in table.columns}
        assert not columns.intersection({
            "email", "display_name", "phone", "coupon_plaintext", "strategy",
            "pnl", "position", "credential", "payment_payload",
        })


def test_membership_and_profile_field_guard_mutations_are_killed_then_restored(
    tmp_path, monkeypatch
):
    engine = _engine(tmp_path, "mutations.db")
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        anonymous = AccountCommerceService(session, principal=None, policy=_policy())
        with pytest.raises(AccountCommerceRefused, match="browser principal"):
            _beta(anonymous)
        authority = AccountAuthority(
            principal.organization_id, principal.user_id, principal.user_id,
            principal.session_id,
        )
        with monkeypatch.context() as mutation:
            mutation.setattr(
                AccountCommerceRepository, "resolve_authority",
                lambda _self, _principal, server_time: authority,
            )
            escaped = _beta(AccountCommerceService(session, principal=None, policy=_policy()))
            assert escaped.access_active is True
    with Session(engine) as session:
        with pytest.raises(AccountCommerceRefused, match="browser principal"):
            AccountCommerceService(
                session, principal=None, policy=_policy()
            ).current_access(server_time=NOW)

    profile_engine = _engine(tmp_path, "profile-mutation.db")
    unknown = ("profile.country", "profile.full_name", "profile.nickname")
    with Session(profile_engine, expire_on_commit=False) as session:
        principal = _seed(session)
        with pytest.raises(AccountCommerceRefused, match="unknown profile field"):
            _beta(AccountCommerceService(session, principal=principal, policy=_policy()),
                  fields=unknown)
        original = AccountCommerceRepository.canonical_fields
        with monkeypatch.context() as mutation:
            mutation.setattr(
                AccountCommerceRepository, "canonical_fields",
                staticmethod(lambda fields, required_fields: (
                    tuple(sorted(fields)),
                    __import__("json").dumps(tuple(sorted(fields)), separators=(",", ":")),
                )),
            )
            escaped = _beta(
                AccountCommerceService(session, principal=principal, policy=_policy()),
                fields=unknown,
            )
            assert escaped.access_active is True
        assert AccountCommerceRepository.canonical_fields is original
    restored_engine = _engine(tmp_path, "profile-restored.db")
    with Session(restored_engine) as session:
        restored_principal = _seed(session)
        with pytest.raises(AccountCommerceRefused, match="unknown profile field"):
            _beta(AccountCommerceService(
                session, principal=restored_principal, policy=_policy()
            ), fields=unknown)


def test_projection_guard_mutation_is_detected_then_rebuild_restores_access(
    tmp_path, monkeypatch
):
    engine = _engine(tmp_path, "projection-mutation.db")
    with Session(engine, expire_on_commit=False) as session:
        principal = _seed(session)
        with monkeypatch.context() as mutation:
            mutation.setattr(
                PlatformOperationsRepository, "_project",
                lambda _self, _event, _rebuilt_at: None,
            )
            escaped = _beta(AccountCommerceService(
                session, principal=principal, policy=_policy()
            ))
            assert escaped.access_active is False
    with Session(engine, expire_on_commit=False) as session:
        restored = AccountCommerceService(
            session, principal=principal, policy=_policy()
        ).rebuild_access(server_time=NOW + dt.timedelta(minutes=1))
        assert restored.state == "ACTIVE"
