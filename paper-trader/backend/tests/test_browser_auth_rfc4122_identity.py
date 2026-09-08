"""Critical proof for canonical browser-principal issuance and propagation."""
from __future__ import annotations

import datetime as dt
import concurrent.futures
import hashlib
import secrets
from contextlib import contextmanager
from uuid import RFC_4122, UUID, uuid4

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.account_commerce import AccountCommerceService
from app.account_commerce.repository import (
    AccountCommerceAuthenticationRefused,
    AccountCommerceRepository,
)
from app.accounts import browser_auth as auth
from app.accounts.lifecycle_contracts import ContractValidationError, CurrentAccountAuthority
from app.api import auth_session_routes, principal as principal_api
from app.api.principal import Principal
from app.billing.policy_contracts import CouponEffect, CouponPolicy
from app.db import migrate
from app.db.engine import create_database_engine
from app.db.models import (
    AccountProfileEvidenceRow,
    AccountTrialUseRow,
    Base,
    BrokerAccount,
    BrokerConnection,
    BrowserCredential,
    BrowserSession,
    EnrollmentInvite,
    LEGACY_OWNER_ID,
    LEGACY_USER_ID,
    Membership,
    OAuthCallbackState,
    Organization,
    User,
    UserSession,
)
from app.platform_operations.contracts import (
    BillingInterval,
    CouponState,
    EntitlementEffectTiming,
    EntitlementTransition,
    PolicyState,
)
from app.platform_operations.repository import PlatformOperationsRepository
from tests.test_v0_account_commerce_service import (
    COUPON_POLICY,
    ELIGIBILITY,
    NOW,
    OPERATOR_BOOTSTRAP,
    OPERATOR_PROFILE,
    PLAN_SET,
    PRIOR,
    REVOCATION,
    _attestation,
    _policy,
)


ORIGIN = "https://testserver"
PASSWORD = "synthetic identity proof passphrase"
NEW_PASSWORD = "replacement synthetic identity passphrase"


def _canonical_v4(value: str) -> UUID:
    parsed = UUID(value)
    assert value == str(parsed)
    assert parsed.variant == RFC_4122
    assert parsed.version == 4
    assert parsed.int != 0
    assert len(value) == 36
    return parsed


@pytest.fixture(params=("sqlite", "postgresql"))
def identity_store(request, tmp_path, monkeypatch):
    if request.param == "sqlite":
        engine = create_database_engine(f"sqlite:///{tmp_path / 'identity.db'}")
    else:
        sandbox = request.getfixturevalue("pg_sandbox")
        engine = sandbox.engine("browser_identity")
        with engine.connect() as connection:
            assert connection.exec_driver_sql("SHOW server_version").scalar().startswith("16.")

    # Identity propagation runs against the current schema; individual migration
    # contracts separately pin their revision and predecessor.
    expected_head = migrate.head_revision()
    assert migrate.init_schema(
        engine,
        create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("fresh database attempted legacy migration"),
        expected_tables=Base.metadata.tables,
    ) == expected_head
    factory = sessionmaker(engine, future=True, expire_on_commit=False)
    monkeypatch.setattr(auth, "SessionLocal", factory)
    monkeypatch.setattr(auth_session_routes, "SessionLocal", factory)
    monkeypatch.setattr(principal_api, "SessionLocal", factory)
    yield request.param, engine, factory
    engine.dispose()


def _enroll(email: str):
    invitation = auth.create_invite(email)
    issued = auth.enroll(email, PASSWORD, "Synthetic account", invitation.token)
    principal = auth.browser_principal(issued.token)
    return invitation, issued, principal


def _account_service(factory, principal: Principal):
    session = factory()
    return AccountCommerceService(session, principal=principal, policy=_policy()), session


def _assert_session_chain(factory, issued, principal: Principal) -> None:
    """The non-secret handle stays exact while the bearer stays digest-only."""
    _canonical_v4(issued.session_id)
    assert principal.session_id == issued.session_id
    with factory() as session:
        durable = session.get(UserSession, issued.session_id)
        browser = session.get(BrowserSession, issued.session_id)
        authority = AccountCommerceRepository(session).resolve_authority(
            principal, server_time=dt.datetime.now(dt.timezone.utc)
        )
        assert durable.session_id == browser.session_id == authority.session_ref
        assert authority.session_ref == issued.session_id
        assert durable.token_digest == hashlib.sha256(issued.token.encode()).hexdigest()
        assert durable.token_digest != issued.session_id


def _grant_beta(factory, principal: Principal):
    service, session = _account_service(factory, principal)
    try:
        return service.grant_beta_trial(
            attestation=_attestation(),
            eligibility_authority_address=ELIGIBILITY,
            prior_use_authority_address=PRIOR,
            revocation_authority_address=REVOCATION,
            eligible=True,
            server_time=dt.datetime.now(dt.timezone.utc),
        )
    finally:
        session.close()


def _bind_coupon(factory, plaintext: str) -> None:
    from app.platform_operations.contracts import OperatorAuthority

    with factory() as session:
        operations = PlatformOperationsRepository(session)
        operations.bind_founder(
            binding_id="operator.identity",
            principal_ref="principal.identity",
            permission_profile_address=OPERATOR_PROFILE,
            bootstrap_evidence_address=OPERATOR_BOOTSTRAP,
            created_at=NOW,
        )
        operator = OperatorAuthority("operator.identity", "principal.identity")
        operations = PlatformOperationsRepository(session, operator=operator)
        operations.create_plan_version(
            plan_version_id="plan.identity.v1",
            plan_code="IDENTITY",
            version=1,
            amount_minor=0,
            currency_code="INR",
            billing_interval=BillingInterval.UNKNOWN,
            entitlement_set_address=PLAN_SET,
            policy_state=PolicyState.UNKNOWN,
            created_at=NOW,
        )
        operations.define_coupon(
            coupon_id="coupon.identity",
            coupon_digest=hashlib.sha256(plaintext.encode()).hexdigest(),
            plan_version_id="plan.identity.v1",
            policy_address=COUPON_POLICY,
            trial_policy_address=_policy().policy_address,
            discount_policy_address=None,
            valid_from=NOW,
            valid_until=NOW + dt.timedelta(days=3650),
            max_redemptions=1,
            per_owner_limit=1,
            status=CouponState.ACTIVE,
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_valid_from=None,
            entitlement_valid_until=None,
            entitlement_effect_timing=EntitlementEffectTiming.DYNAMIC_DURATION,
            entitlement_duration_seconds=1_296_000,
            created_at=NOW,
        )
        session.commit()


def _grant_coupon(factory, principal: Principal, plaintext: str):
    service, session = _account_service(factory, principal)
    try:
        return service.grant_coupon_trial(
            coupon_plaintext=plaintext,
            coupon_policy=CouponPolicy(
                policy_address=COUPON_POLICY,
                entitlement_policy_address=_policy().policy_address,
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
            server_time=dt.datetime.now(dt.timezone.utc),
        )
    finally:
        session.close()


def _assert_forbidden_absent(engine, forbidden: tuple[str, ...]) -> None:
    """Scan text columns without returning any forbidden value to evidence."""
    with engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            for column in table.columns:
                if isinstance(column.type, sa.String):
                    count = connection.scalar(
                        sa.select(sa.func.count()).select_from(table).where(column.in_(forbidden))
                    )
                    assert count == 0, f"forbidden plaintext persisted in {table.name}.{column.name}"


def _lifecycle_authority(user_id: str, organization_id: str) -> CurrentAccountAuthority:
    return CurrentAccountAuthority(
        user_id=user_id,
        tenant_id=organization_id,
        session_authority_address="sha256:" + "1" * 64,
        session_policy_address="sha256:" + "2" * 64,
        lifecycle_policy_id="sha256:" + "3" * 64,
        issuer_class="PASSWORD",
        account_state="ACTIVE",
        onboarding_step="COMPLETE",
        authenticated_at=dt.datetime.now(dt.timezone.utc),
    )


def test_generated_ids_survive_session_tenant_restart_and_commerce(identity_store, monkeypatch):
    dialect, engine, factory = identity_store
    alice_invite, alice_issued, alice = _enroll(f"alice-{dialect}@example.test")
    bob_invite, bob_issued, bob = _enroll(f"bob-{dialect}@example.test")

    for value in (alice.user_id, alice.organization_id, bob.user_id, bob.organization_id):
        _canonical_v4(value)
    assert len({alice.user_id, alice.organization_id, bob.user_id, bob.organization_id}) == 4
    _assert_session_chain(factory, alice_issued, alice)
    _assert_session_chain(factory, bob_issued, bob)
    assert auth.bootstrap(alice_issued.token)["user"]["id"] == alice.user_id
    assert auth.bootstrap(alice_issued.token)["organization_id"] == alice.organization_id
    lifecycle = _lifecycle_authority(alice.user_id, alice.organization_id)
    assert (lifecycle.user_id, lifecycle.tenant_id) == (alice.user_id, alice.organization_id)

    login = auth.login(f"alice-{dialect}@example.test", PASSWORD, alice_issued.token)
    with pytest.raises(auth.AuthRefusal):
        auth.browser_principal(alice_issued.token)
    logged_in = auth.browser_principal(login.token)
    _assert_session_chain(factory, login, logged_in)
    assert (logged_in.user_id, logged_in.organization_id) == (
        alice.user_id,
        alice.organization_id,
    )

    password_session = auth.mutate_session(
        login.token, "password", password=PASSWORD, new_password=NEW_PASSWORD
    )
    with pytest.raises(auth.AuthRefusal):
        auth.browser_principal(login.token)
    password_principal = auth.browser_principal(password_session.token)
    _assert_session_chain(factory, password_session, password_principal)
    assert (password_principal.user_id, password_principal.organization_id) == (
        alice.user_id,
        alice.organization_id,
    )
    with pytest.raises(auth.AuthRefusal):
        auth.login(f"alice-{dialect}@example.test", PASSWORD)
    replacement_login = auth.login(
        f"alice-{dialect}@example.test", NEW_PASSWORD, password_session.token
    )
    password_principal = auth.browser_principal(replacement_login.token)
    _assert_session_chain(factory, replacement_login, password_principal)

    beta = _grant_beta(factory, password_principal)
    assert beta.owner_ref == alice.organization_id

    coupon_plaintext = secrets.token_urlsafe(24)
    _bind_coupon(factory, coupon_plaintext)
    coupon = _grant_coupon(factory, bob, coupon_plaintext)
    assert coupon.owner_ref == bob.organization_id
    assert coupon_plaintext not in repr(coupon)

    forged = Principal(
        id=alice.user_id,
        kind="user",
        scopes=alice.scopes,
        user_id=alice.user_id,
        organization_id=bob.organization_id,
        role="owner",
        session_id=password_principal.session_id,
    )
    service, session = _account_service(factory, forged)
    try:
        with pytest.raises(AccountCommerceAuthenticationRefused):
            service.current_status(server_time=dt.datetime.now(dt.timezone.utc))
    finally:
        session.close()

    with factory() as session:
        session.add(Membership(
            user_id=alice.user_id,
            organization_id=bob.organization_id,
            role="viewer",
            status="active",
        ))
        session.commit()
    switched = auth.mutate_session(
        replacement_login.token, "organization", organization_id=bob.organization_id
    )
    with pytest.raises(auth.AuthRefusal):
        auth.browser_principal(replacement_login.token)
    switched_principal = auth.browser_principal(switched.token)
    _assert_session_chain(factory, switched, switched_principal)
    assert switched_principal.user_id == alice.user_id
    assert switched_principal.organization_id == bob.organization_id
    service, session = _account_service(factory, switched_principal)
    try:
        status = service.current_status(server_time=dt.datetime.now(dt.timezone.utc))
        assert status.trial_source is None
    finally:
        session.close()

    with factory() as session:
        membership = session.get(Membership, (bob.organization_id, alice.user_id))
        membership.status = "revoked"
        session.commit()
    with pytest.raises(auth.AuthRefusal):
        auth.browser_principal(switched.token)
    with factory() as session:
        membership = session.get(Membership, (bob.organization_id, alice.user_id))
        membership.status = "active"
        session.commit()

    engine.dispose()
    restarted = create_database_engine(str(engine.url))
    assert migrate.init_schema(
        restarted,
        create_all=lambda: pytest.fail("restart unexpectedly created schema"),
        legacy_migrate=lambda: pytest.fail("restart unexpectedly migrated legacy schema"),
        expected_tables=Base.metadata.tables,
    ) == migrate.head_revision()
    restarted_factory = sessionmaker(restarted, future=True, expire_on_commit=False)
    monkeypatch.setattr(auth, "SessionLocal", restarted_factory)
    restarted_principal = auth.browser_principal(switched.token)
    _assert_session_chain(restarted_factory, switched, restarted_principal)
    assert (restarted_principal.user_id, restarted_principal.organization_id) == (
        alice.user_id,
        bob.organization_id,
    )

    with restarted_factory() as session:
        profiles = session.scalars(sa.select(AccountProfileEvidenceRow)).all()
        trials = session.scalars(sa.select(AccountTrialUseRow)).all()
        assert {(row.owner_ref, row.user_ref) for row in profiles} == {
            (alice.organization_id, alice.user_id),
            (bob.organization_id, bob.user_id),
        }
        assert {(row.owner_ref, row.user_ref) for row in trials} == {
            (alice.organization_id, alice.user_id),
            (bob.organization_id, bob.user_id),
        }
    _assert_forbidden_absent(
        restarted,
        (
            PASSWORD,
            NEW_PASSWORD,
            alice_invite.token,
            bob_invite.token,
            alice_issued.token,
            bob_issued.token,
            coupon_plaintext,
        ),
    )
    restarted.dispose()


@pytest.mark.parametrize("collision", ("handle", "digest"))
def test_session_identity_collision_is_generic_atomic_and_invitation_reusable(
    identity_store, monkeypatch, collision
):
    dialect, _engine, factory = identity_store
    existing_user = str(uuid4())
    existing_organization = str(uuid4())
    existing_handle = str(uuid4())
    colliding_bearer = "B" * 43
    existing_digest = (
        hashlib.sha256(colliding_bearer.encode()).hexdigest()
        if collision == "digest"
        else "c" * 64
    )
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    email = f"session-{collision}-{dialect}@example.test"
    with factory() as session:
        session.add(Organization(organization_id=existing_organization, name="Existing"))
        session.add(User(
            user_id=existing_user,
            email_normalized=f"existing-session-{collision}-{dialect}@example.test",
            display_name="Existing",
        ))
        session.flush()
        session.add(Membership(
            organization_id=existing_organization,
            user_id=existing_user,
            role="owner",
            status="active",
        ))
        session.flush()
        session.add(UserSession(
            session_id=existing_handle,
            token_digest=existing_digest,
            user_id=existing_user,
            organization_id=existing_organization,
            issued_at=now,
            expires_at=now + dt.timedelta(hours=1),
        ))
        session.commit()

    invitation = auth.create_invite(email)
    original_token_urlsafe = principal_api.secrets.token_urlsafe
    with monkeypatch.context() as collision_patch:
        if collision == "handle":
            collision_patch.setattr(principal_api, "uuid4", lambda: UUID(existing_handle))
        else:
            collision_patch.setattr(
                principal_api.secrets,
                "token_urlsafe",
                lambda size: colliding_bearer if size == 32 else original_token_urlsafe(size),
            )
        app = FastAPI()
        app.include_router(auth_session_routes.router, prefix="/api/v1")
        settings = auth.get_settings()
        for name, value in {
            "browser_auth_enabled": True,
            "browser_auth_origin": ORIGIN,
            "browser_auth_counter_secret": "a1" * 32,
            "auth_disabled": False,
            "api_token": "",
            "release_profile": "v0_research_signal",
            "release_service_role": "api",
        }.items():
            collision_patch.setattr(settings, name, value)
        with TestClient(app, base_url=ORIGIN) as client:
            response = client.post(
                "/api/v1/api/auth/enroll",
                json={
                    "email": email,
                    "password": PASSWORD,
                    "display_name": "Session collision",
                    "invitation": invitation.token,
                },
                headers={"Origin": ORIGIN},
            )

    assert response.status_code == 503
    assert response.json() == {"error": "authentication unavailable"}
    assert auth.COOKIE not in response.headers.get("set-cookie", "")
    assert existing_handle not in response.text
    with factory() as session:
        existing = session.get(UserSession, existing_handle)
        assert existing.session_id == existing_handle
        assert (existing.user_id, existing.organization_id, existing.token_digest) == (
            existing_user,
            existing_organization,
            existing_digest,
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(UserSession)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(BrowserSession)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(OAuthCallbackState)) == 0
        assert session.scalar(
            sa.select(sa.func.count()).select_from(User).where(User.email_normalized == email)
        ) == 0
        assert session.get(EnrollmentInvite, auth.token_digest(invitation.token)).consumed_at is None

    recovered = auth.enroll(email, PASSWORD, "Session collision", invitation.token)
    recovered_principal = auth.browser_principal(recovered.token)
    _assert_session_chain(factory, recovered, recovered_principal)


def test_generated_session_handle_round_trips_oauth_state_and_restart(
    identity_store, monkeypatch
):
    """The corrected producer reaches the protected OAuth persistence boundary exactly."""
    _dialect, engine, factory = identity_store
    _invite, issued, principal = _enroll("oauth-generated@example.test")
    _assert_session_chain(factory, issued, principal)
    state_plaintext = "synthetic-oauth-state-never-persisted"
    state_digest = hashlib.sha256(state_plaintext.encode()).hexdigest()
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    with factory() as session:
        session.add(BrokerAccount(
            broker_account_id="account.oauth.generated",
            owner_id=principal.organization_id,
            broker="kite",
            external_account_id="synthetic-oauth-account",
            display_name="Synthetic OAuth",
        ))
        session.flush()
        session.add(BrokerConnection(
            id=901,
            owner_id=principal.organization_id,
            broker_account_id="account.oauth.generated",
            broker="kite",
            scope="kite:oauth-generated",
            label="Synthetic OAuth",
        ))
        session.flush()
        session.add(OAuthCallbackState(
            state_digest=state_digest,
            connection_id=901,
            session_id=principal.session_id,
            user_id=principal.user_id,
            organization_id=principal.organization_id,
            created_at=now,
            expires_at=now + dt.timedelta(minutes=10),
        ))
        session.commit()
        persisted = session.get(OAuthCallbackState, state_digest)
        assert (persisted.session_id, persisted.user_id, persisted.organization_id) == (
            issued.session_id,
            principal.user_id,
            principal.organization_id,
        )
        assert session.get(UserSession, persisted.session_id).token_digest == hashlib.sha256(
            issued.token.encode()
        ).hexdigest()

    _assert_forbidden_absent(engine, (state_plaintext, issued.token))
    engine.dispose()
    restarted = create_database_engine(str(engine.url))
    restarted_factory = sessionmaker(restarted, future=True, expire_on_commit=False)
    with restarted_factory() as session:
        persisted = session.get(OAuthCallbackState, state_digest)
        assert (persisted.session_id, persisted.user_id, persisted.organization_id) == (
            issued.session_id,
            principal.user_id,
            principal.organization_id,
        )
        assert persisted.connection_id == 901
        assert session.get(BrowserSession, persisted.session_id).session_id == issued.session_id
    _assert_forbidden_absent(restarted, (state_plaintext, issued.token))
    restarted.dispose()


def test_postgresql16_concurrent_issue_revoke_expiry_and_logout(
    identity_store, monkeypatch
):
    """PostgreSQL executes the session lifecycle rather than inheriting SQLite proof."""
    dialect, _engine, factory = identity_store
    if dialect != "postgresql":
        pytest.skip("PostgreSQL-specific concurrent lifecycle proof")
    monkeypatch.setattr(auth.get_settings(), "auth_disabled", False)
    monkeypatch.setattr(auth.get_settings(), "api_token", "")
    _invite, browser_issued, browser_principal = _enroll("pg-lifecycle@example.test")
    user_id = browser_principal.user_id
    organization_id = browser_principal.organization_id

    def issue_one(_number):
        with factory() as session:
            issued = principal_api.issue_user_session(
                session,
                user_id=user_id,
                organization_id=organization_id,
                expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
            )
            session.commit()
            return issued

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        issued = list(pool.map(issue_one, range(8)))
    assert len({item.session_id for item in issued}) == 8
    assert all(_canonical_v4(item.session_id) for item in issued)
    assert all(
        (principal_api.resolve_principal(item.token).user_id,
         principal_api.resolve_principal(item.token).organization_id)
        == (user_id, organization_id)
        for item in issued
    )

    revoked = issued[0]

    def revoke_one(_number):
        with factory() as session:
            changed = principal_api.revoke_user_session(session, revoked.session_id)
            session.commit()
            return changed

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(revoke_one, range(8)))
    assert outcomes.count(True) == 1
    assert principal_api.resolve_principal(revoked.token) is None
    assert all(principal_api.resolve_principal(item.token) is not None for item in issued[1:])

    with factory() as session:
        expired = principal_api.issue_user_session(
            session,
            user_id=user_id,
            organization_id=organization_id,
            expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1),
        )
        session.commit()
    assert principal_api.resolve_principal(expired.token) is None

    assert auth.mutate_session(browser_issued.token, "logout") is None
    with pytest.raises(auth.AuthRefusal):
        auth.browser_principal(browser_issued.token)
    with factory() as session:
        logged_out = session.get(UserSession, browser_issued.session_id)
        assert logged_out.revoked_at is not None
        assert (logged_out.user_id, logged_out.organization_id) == (
            user_id, organization_id)


def test_absent_digest_legacy_bootstrap_collision_rolls_back_and_retries_after_restart(
    identity_store, monkeypatch
):
    """The real bootstrap caller transaction rolls back roots and retries cleanly."""
    _dialect, engine, factory = identity_store
    _invite, issued, principal = _enroll("legacy-collision@example.test")
    collision_handle = issued.session_id
    legacy_token = "L" * 43
    legacy_digest = principal_api.token_digest(legacy_token)

    with monkeypatch.context() as collision_patch:
        collision_patch.setattr(principal_api, "uuid4", lambda: UUID(collision_handle))
        with factory() as session:
            session.add(Organization(organization_id=LEGACY_OWNER_ID, name="Legacy"))
            session.add(User(
                user_id=LEGACY_USER_ID,
                email_normalized="legacy-owner@example.test",
                display_name="Legacy",
            ))
            session.flush()
            session.add(Membership(
                organization_id=LEGACY_OWNER_ID,
                user_id=LEGACY_USER_ID,
                role="owner",
                status="active",
            ))
            session.flush()
            attempted = principal_api.bootstrap_legacy_session(session, legacy_token)
            assert attempted.session_id == collision_handle
            with pytest.raises(sa.exc.IntegrityError):
                session.commit()
            session.rollback()

    with factory() as session:
        existing = session.get(UserSession, collision_handle)
        assert (existing.user_id, existing.organization_id, existing.token_digest) == (
            principal.user_id,
            principal.organization_id,
            hashlib.sha256(issued.token.encode()).hexdigest(),
        )
        assert session.scalar(sa.select(UserSession).where(
            UserSession.token_digest == legacy_digest
        )) is None
        assert session.get(User, LEGACY_USER_ID) is None
        assert session.get(Organization, LEGACY_OWNER_ID) is None

    engine.dispose()
    restarted = create_database_engine(str(engine.url))
    restarted_factory = sessionmaker(restarted, future=True, expire_on_commit=False)
    with restarted_factory() as session:
        session.add(Organization(organization_id=LEGACY_OWNER_ID, name="Legacy"))
        session.add(User(
            user_id=LEGACY_USER_ID,
            email_normalized="legacy-owner@example.test",
            display_name="Legacy",
        ))
        session.flush()
        session.add(Membership(
            organization_id=LEGACY_OWNER_ID,
            user_id=LEGACY_USER_ID,
            role="owner",
            status="active",
        ))
        session.flush()
        recovered = principal_api.bootstrap_legacy_session(session, legacy_token)
        session.commit()
        _canonical_v4(recovered.session_id)
        assert recovered.session_id != collision_handle
    restarted.dispose()

    final = create_database_engine(str(engine.url))
    with sessionmaker(final, future=True, expire_on_commit=False)() as session:
        durable = session.scalar(sa.select(UserSession).where(
            UserSession.token_digest == legacy_digest
        ))
        assert (durable.session_id, durable.user_id, durable.organization_id) == (
            recovered.session_id,
            LEGACY_USER_ID,
            LEGACY_OWNER_ID,
        )
    final.dispose()


@pytest.mark.parametrize("collision", ("user", "organization"))
def test_collision_is_generic_atomic_and_invitation_reusable(
    identity_store, monkeypatch, collision
):
    dialect, _engine, factory = identity_store
    existing_user = str(uuid4())
    existing_organization = str(uuid4())
    fresh_user = str(uuid4())
    fresh_organization = str(uuid4())
    email = f"collision-{collision}-{dialect}@example.test"

    with factory() as session:
        session.add(Organization(organization_id=existing_organization, name="Existing"))
        session.add(User(
            user_id=existing_user,
            email_normalized=f"existing-{collision}-{dialect}@example.test",
            display_name="Existing",
        ))
        session.flush()
        session.add(Membership(
            organization_id=existing_organization,
            user_id=existing_user,
            role="owner",
            status="active",
        ))
        session.commit()

    invitation = auth.create_invite(email)
    generated = (
        (UUID(existing_user), UUID(fresh_organization))
        if collision == "user"
        else (UUID(fresh_user), UUID(existing_organization))
    )
    iterator = iter(generated)
    with monkeypatch.context() as collision_patch:
        collision_patch.setattr(auth, "uuid4", lambda: next(iterator))
        app = FastAPI()
        app.include_router(auth_session_routes.router, prefix="/api/v1")
        settings = auth.get_settings()
        for name, value in {
            "browser_auth_enabled": True,
            "browser_auth_origin": ORIGIN,
            "browser_auth_counter_secret": "a1" * 32,
            "auth_disabled": False,
            "api_token": "",
            "release_profile": "v0_research_signal",
            "release_service_role": "api",
        }.items():
            collision_patch.setattr(settings, name, value)
        with TestClient(app, base_url=ORIGIN) as client:
            response = client.post(
                "/api/v1/api/auth/enroll",
                json={
                    "email": email,
                    "password": PASSWORD,
                    "display_name": "Collision",
                    "invitation": invitation.token,
                },
                headers={"Origin": ORIGIN},
            )
    assert response.status_code == 503
    assert response.json() == {"error": "authentication unavailable"}
    assert auth.COOKIE not in response.headers.get("set-cookie", "")
    assert existing_user not in response.text
    assert existing_organization not in response.text

    with factory() as session:
        assert session.get(User, existing_user).email_normalized.startswith("existing-")
        assert session.get(Organization, existing_organization).name == "Existing"
        assert session.get(Membership, (existing_organization, existing_user)) is not None
        assert session.scalar(
            sa.select(sa.func.count()).select_from(User).where(User.email_normalized == email)
        ) == 0
        assert session.get(User, fresh_user) is None
        assert session.get(Organization, fresh_organization) is None
        assert session.get(EnrollmentInvite, auth.token_digest(invitation.token)).consumed_at is None
        assert session.scalar(
            sa.select(sa.func.count()).select_from(BrowserCredential).where(
                BrowserCredential.user_id.in_((existing_user, fresh_user))
            )
        ) == 0
        assert session.scalar(
            sa.select(sa.func.count()).select_from(UserSession).where(
                UserSession.user_id.in_((existing_user, fresh_user))
            )
        ) == 0
        assert session.scalar(
            sa.select(sa.func.count()).select_from(BrowserSession).join(
                UserSession, UserSession.session_id == BrowserSession.session_id
            ).where(UserSession.user_id.in_((existing_user, fresh_user)))
        ) == 0

    recovered = auth.enroll(email, PASSWORD, "Collision", invitation.token)
    recovered_principal = auth.browser_principal(recovered.token)
    _canonical_v4(recovered_principal.user_id)
    _canonical_v4(recovered_principal.organization_id)


@pytest.mark.parametrize(
    "invalid",
    (
        "00000000-0000-0000-0000-000000000000",
        "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA",
        "token_safe_identity",
    ),
)
def test_lifecycle_contract_refuses_noncanonical_principal_samples(invalid):
    valid = str(uuid4())
    with pytest.raises(ContractValidationError):
        _lifecycle_authority(invalid, valid)
    with pytest.raises(ContractValidationError):
        _lifecycle_authority(valid, invalid)
