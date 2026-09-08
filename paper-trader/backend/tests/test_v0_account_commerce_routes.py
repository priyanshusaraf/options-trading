from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import re
import sqlite3
import threading
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.account_commerce.service import AccountCommerceService, ServerProfileAttestation
from app.accounts import browser_auth
from app.api.account_commerce_routes import (
    ProfileInput,
    TrialEligibility,
    build_account_commerce_router,
    _public_access_state,
)
from app.api.principal import Principal, SCOPE_ALL
from app.billing.policy_contracts import CouponEffect, CouponPolicy, EntitlementPolicy
from app.db.models import (
    AccountProfileEvidenceRow,
    AccountTrialUseRow,
    Base,
    BrowserSession,
    Membership,
    Organization,
    PlatformEntitlementEventRow,
    PlatformCurrentEntitlementRow,
    PlatformCouponRedemptionRow,
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


NOW = dt.datetime(2026, 9, 1, 6, 0, tzinfo=dt.timezone.utc)
TOKEN = "t" * 43
POLICY_ADDRESS = "sha256:" + "a" * 64
EVIDENCE_ADDRESS = "sha256:" + "b" * 64
ELIGIBILITY_ADDRESS = "sha256:" + "c" * 64
PRIOR_ADDRESS = "sha256:" + "d" * 64
REVOCATION_ADDRESS = "sha256:" + "e" * 64
COUPON_POLICY_ADDRESS = "sha256:" + "f" * 64


class ConsumerContractError(ValueError):
    """The unpublished consumer received a response outside its sealed contract."""


class ConsumerAbortError(TimeoutError):
    """The unpublished consumer aborted a request at its owned time bound."""


_UTC_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{6})?Z$"
)


def _contract(condition: bool, message: str) -> None:
    if not condition:
        raise ConsumerContractError(message)


def _canonical_utc(value, *, nullable: bool) -> dt.datetime | None:
    if value is None:
        _contract(nullable, "timestamp must not be null")
        return None
    _contract(type(value) is str, "timestamp must be an exact string")
    _contract(_UTC_PATTERN.fullmatch(value) is not None, "timestamp is not canonical UTC")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ConsumerContractError("timestamp is not a valid calendar time") from exc
    _contract(parsed.tzinfo is dt.timezone.utc, "timestamp must be UTC")
    _contract(
        parsed.isoformat().replace("+00:00", "Z") == value,
        "timestamp is not canonical UTC",
    )
    return parsed


class FutureWaiter:
    def __call__(self, future: Future, timeout: int):
        return future.result(timeout=timeout)


class PrecisionSlateConsumerFixture:
    """Executable future-consumer contract without publishing frontend code."""

    transport = {
        "credentials": "same-origin",
        "cache": "no-store",
        "redirect": "error",
        "abort_after_seconds": 10,
        "csrf_header": "X-Strategy-CSRF",
    }
    success_fields = {
        "access": frozenset({"schema", "state", "expires_at", "evaluated_at"}),
        "status": frozenset({
            "schema", "profile_state", "satisfied_field_codes",
            "profile_attested_at", "trial_state", "trial_source",
            "trial_expires_at", "access_state", "access_expires_at",
            "evaluated_at",
        }),
        "profile": frozenset({
            "schema", "profile_state", "satisfied_field_codes", "attested_at",
            "replayed",
        }),
        "trial": frozenset({
            "schema", "source", "state", "expires_at", "replayed",
        }),
    }
    schemas = {
        "access": "account-commerce-access/1",
        "status": "account-commerce-status/1",
        "profile": "account-commerce-profile-evidence/1",
        "trial": "account-commerce-trial-grant/1",
    }
    approved_profile_fields = frozenset({"profile.country", "profile.full_name"})

    def __init__(self, client=None, *, transport=None, waiter=None):
        self.client = client
        self._transport = transport or self._testclient_transport
        self._waiter = waiter or FutureWaiter()
        self.projections = {}
        self.parse_calls = 0

    def _testclient_transport(self, method, path, *, abort_event, **kwargs):
        if abort_event.is_set():
            raise ConsumerAbortError("request aborted before transport")
        return self.client.request(method, path, **kwargs)

    @staticmethod
    def parse_error(status: int, payload: dict) -> dict:
        exact = {
            400: {"code": "ACCOUNT_COMMERCE_REQUEST_INVALID",
                  "message": "Account request is invalid"},
            409: {"code": "ACCOUNT_COMMERCE_CONFLICT",
                  "message": "Account request conflicts with existing state"},
            401: {"error": "authentication refused"},
            403: {"error": "authentication refused"},
        }
        if status == 503:
            _contract(payload in (
                {"code": "ACCOUNT_COMMERCE_UNAVAILABLE",
                 "message": "Account service is unavailable"},
                {"code": "BILLING_PROVIDER_UNAVAILABLE",
                 "message": "Billing provider is unavailable"},
            ), "unexpected unavailable response")
        else:
            _contract(status in exact and payload == exact[status], "unexpected error response")
        return payload

    @staticmethod
    def _enum(value, allowed: set[str], field: str) -> str:
        _contract(type(value) is str and value in allowed, f"invalid {field}")
        return value

    @classmethod
    def _profile_codes(cls, value) -> list[str]:
        _contract(type(value) is list, "satisfied field codes must be a list")
        _contract(
            all(type(item) is str for item in value),
            "satisfied field codes must contain exact strings",
        )
        _contract(
            all(item in cls.approved_profile_fields for item in value),
            "unknown satisfied field code",
        )
        _contract(len(value) == len(set(value)), "duplicate satisfied field code")
        _contract(value == sorted(value), "satisfied field codes are not canonical")
        return value

    def parse_success(self, kind: str, payload: dict) -> dict:
        self.parse_calls += 1
        _contract(kind in self.success_fields, "unknown response kind")
        _contract(type(payload) is dict, "success payload must be an exact object")
        _contract(frozenset(payload) == self.success_fields[kind], "success keys differ")
        _contract(
            type(payload["schema"]) is str and payload["schema"] == self.schemas[kind],
            "schema differs",
        )
        if kind == "access":
            state = self._enum(payload["state"], {"ACTIVE", "INACTIVE", "EXPIRED"}, "state")
            expires = _canonical_utc(payload["expires_at"], nullable=True)
            evaluated = _canonical_utc(payload["evaluated_at"], nullable=False)
            if state == "ACTIVE":
                _contract(expires is None or expires > evaluated, "active access is expired")
            if state == "EXPIRED":
                _contract(expires is not None and expires <= evaluated, "expired access time differs")
        elif kind == "status":
            profile_state = self._enum(
                payload["profile_state"], {"COMPLETE", "INCOMPLETE"}, "profile state"
            )
            codes = self._profile_codes(payload["satisfied_field_codes"])
            complete = frozenset(codes) == self.approved_profile_fields
            _contract((profile_state == "COMPLETE") == complete, "profile state differs")
            attested = _canonical_utc(payload["profile_attested_at"], nullable=True)
            _contract(not codes or attested is not None, "profile codes lack attestation")
            _contract(attested is not None or not codes, "null attestation has profile codes")
            trial_state = self._enum(
                payload["trial_state"],
                {"AVAILABLE", "USED_ACTIVE", "USED_EXPIRED"},
                "trial state",
            )
            source = payload["trial_source"]
            if source is not None:
                source = self._enum(
                    source, {"BETA_TRIAL", "COUPON_REDEMPTION"}, "trial source"
                )
            trial_expires = _canonical_utc(payload["trial_expires_at"], nullable=True)
            access_state = self._enum(
                payload["access_state"], {"ACTIVE", "INACTIVE", "EXPIRED"}, "access state"
            )
            access_expires = _canonical_utc(payload["access_expires_at"], nullable=True)
            evaluated = _canonical_utc(payload["evaluated_at"], nullable=False)
            if trial_state == "AVAILABLE":
                _contract(source is None and trial_expires is None, "available trial has use facts")
            elif trial_state == "USED_ACTIVE":
                _contract(
                    source is not None and trial_expires is not None and trial_expires > evaluated,
                    "active trial facts differ",
                )
            else:
                _contract(
                    source is not None and trial_expires is not None and trial_expires <= evaluated,
                    "expired trial facts differ",
                )
            if access_state == "ACTIVE":
                _contract(
                    access_expires is None or access_expires > evaluated,
                    "active access is expired",
                )
            if access_state == "EXPIRED":
                _contract(
                    access_expires is not None and access_expires <= evaluated,
                    "expired access time differs",
                )
        elif kind == "profile":
            profile_state = self._enum(
                payload["profile_state"], {"COMPLETE", "INCOMPLETE"}, "profile state"
            )
            codes = self._profile_codes(payload["satisfied_field_codes"])
            _contract(
                (profile_state == "COMPLETE")
                == (frozenset(codes) == self.approved_profile_fields),
                "profile state differs",
            )
            _canonical_utc(payload["attested_at"], nullable=False)
            _contract(type(payload["replayed"]) is bool, "replayed must be an exact bool")
        else:
            self._enum(payload["source"], {"BETA_TRIAL", "COUPON_REDEMPTION"}, "source")
            self._enum(payload["state"], {"ACTIVE", "EXPIRED"}, "state")
            _canonical_utc(payload["expires_at"], nullable=False)
            _contract(type(payload["replayed"]) is bool, "replayed must be an exact bool")
        return payload

    @staticmethod
    def _validate_trial_refresh(trial: dict, status: dict) -> None:
        expected = "USED_ACTIVE" if trial["state"] == "ACTIVE" else "USED_EXPIRED"
        _contract(trial["source"] == status["trial_source"], "trial source refresh differs")
        _contract(trial["expires_at"] == status["trial_expires_at"], "trial expiry refresh differs")
        _contract(expected == status["trial_state"], "trial state refresh differs")

    def request(self, method: str, path: str, *, kind: str, body: dict | None = None):
        mutation = method == "POST"
        headers = {"Origin": "https://testserver"}
        content = None
        if mutation:
            headers.update({
                self.transport["csrf_header"]: browser_auth.csrf_value(TOKEN),
                "Content-Type": "application/json",
            })
            content = json.dumps(body, separators=(",", ":"))
            assert set(headers) == {"Origin", "X-Strategy-CSRF", "Content-Type"}
        abort_event = threading.Event()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                self._transport,
                method,
                path,
                abort_event=abort_event,
                content=content,
                headers=headers,
                follow_redirects=False,
            )
            try:
                response = self._waiter(future, self.transport["abort_after_seconds"])
            except FutureTimeout:
                abort_event.set()
                try:
                    future.result()
                except Exception:
                    pass
                raise ConsumerAbortError("request aborted after 10 seconds") from None
        _contract(not 300 <= response.status_code < 400, "redirect response refused")
        _contract(response.headers["cache-control"] == self.transport["cache"], "cache policy differs")
        payload = response.json()
        if response.status_code >= 400:
            return response, self.parse_error(response.status_code, payload)
        parsed = self.parse_success(kind, payload)
        return response, parsed

    def mutate(self, path: str, *, kind: str, body: dict):
        response, parsed = self.request("POST", path, kind=kind, body=body)
        if response.status_code < 400:
            access = self.request("GET", "/api/v1/account-commerce/access", kind="access")[1]
            status = self.request("GET", "/api/v1/account-commerce/status", kind="status")[1]
            if kind == "trial":
                self._validate_trial_refresh(parsed, status)
            self.projections = {"access": access, "status": status}
        return response, parsed


def _policy() -> EntitlementPolicy:
    return EntitlementPolicy(
        policy_address=POLICY_ADDRESS,
        entitlement_set_id="set.internal.beta",
        entitlements=("product.access",),
        required_profile_fields=("profile.country", "profile.full_name"),
        trial_duration_seconds=1_296_000,
    )


def _principal() -> Principal:
    return Principal(
        id="user.alpha", kind="user", scopes=frozenset({SCOPE_ALL}),
        user_id="user.alpha", organization_id="owner.alpha", role="member",
        session_id="session.alpha",
    )


def _seed(engine) -> None:
    with Session(engine) as session:
        session.add(Organization(
            organization_id="owner.alpha", name="Synthetic", status="active",
            created_at=NOW.replace(tzinfo=None), updated_at=NOW.replace(tzinfo=None),
        ))
        session.add(User(
            user_id="user.alpha", email_normalized="private@example.invalid",
            display_name="Private", status="active",
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
            expires_at=(NOW + dt.timedelta(hours=1)).replace(tzinfo=None),
            revoked_at=None,
        ))
        session.flush()
        session.add(BrowserSession(
            session_id="session.alpha", last_seen_at=NOW.replace(tzinfo=None)
        ))
        session.commit()


@pytest.fixture
def api(tmp_path, monkeypatch):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'commerce-api.db'}")
    Base.metadata.create_all(engine)
    _seed(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    calls = {name: 0 for name in (
        "session", "attestor", "eligibility", "coupon_policy", "coupon_proof"
    )}

    def counted_sessionmaker():
        calls["session"] += 1
        return factory()

    def attest(_principal, profile):
        calls["attestor"] += 1
        assert profile is None or type(profile) is ProfileInput
        return ServerProfileAttestation(
            EVIDENCE_ADDRESS, ("profile.country", "profile.full_name")
        )

    def eligibility(_principal):
        calls["eligibility"] += 1
        return TrialEligibility(
            True, ELIGIBILITY_ADDRESS, PRIOR_ADDRESS, REVOCATION_ADDRESS
        )

    def coupon_policy(_principal, _secret):
        calls["coupon_policy"] += 1
        return CouponPolicy(
            policy_address=COUPON_POLICY_ADDRESS,
            entitlement_policy_address=POLICY_ADDRESS,
            verifier_address="coupon.verifier.internal",
            effect=CouponEffect.TRIAL_ACCESS,
            effect_policy_address="coupon.effect.trial",
        )

    def coupon_proof(_principal, _secret):
        calls["coupon_proof"] += 1
        return "coupon.proof.internal"

    router = build_account_commerce_router(
        sessionmaker=counted_sessionmaker, policy=_policy(), clock=lambda: NOW,
        profile_attestor=attest, eligibility_resolver=eligibility,
        coupon_policy_resolver=coupon_policy,
        coupon_proof_resolver=coupon_proof,
    )
    app = FastAPI()
    state = SimpleNamespace(principal=_principal())

    @app.middleware("http")
    async def principal_state(request: Request, call_next):
        request.state.principal = state.principal
        return await call_next(request)

    app.include_router(router)
    monkeypatch.setattr(
        browser_auth, "get_settings",
        lambda: SimpleNamespace(browser_auth_origin="https://testserver"),
    )
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(browser_auth.COOKIE, TOKEN, path="/")
    return SimpleNamespace(
        app=app, router=router, client=client, calls=calls, state=state, engine=engine
    )


@pytest.fixture
def precision_slate_consumer(api):
    return PrecisionSlateConsumerFixture(api.client)


def _post_headers(token=TOKEN):
    return {
        "Origin": "https://testserver",
        "X-Strategy-CSRF": browser_auth.csrf_value(token),
        "Content-Type": "application/json",
    }


def _seed_coupon(engine, secret: str) -> None:
    operator = OperatorAuthority("operator.founder", "principal.founder")
    with Session(engine) as session:
        PlatformOperationsRepository(session).bind_founder(
            binding_id=operator.binding_id,
            principal_ref=operator.principal_ref,
            permission_profile_address="sha256:" + "1" * 64,
            bootstrap_evidence_address="sha256:" + "2" * 64,
            created_at=NOW,
        )
        operations = PlatformOperationsRepository(session, operator=operator)
        operations.create_plan_version(
            plan_version_id="plan.beta.v1",
            plan_code="BETA",
            version=1,
            amount_minor=0,
            currency_code="INR",
            billing_interval=BillingInterval.UNKNOWN,
            entitlement_set_address="sha256:" + "3" * 64,
            policy_state=PolicyState.UNKNOWN,
            created_at=NOW,
        )
        operations.define_coupon(
            coupon_id="coupon.beta",
            coupon_digest=hashlib.sha256(secret.encode()).hexdigest(),
            plan_version_id="plan.beta.v1",
            policy_address=COUPON_POLICY_ADDRESS,
            trial_policy_address=POLICY_ADDRESS,
            discount_policy_address=None,
            valid_from=NOW,
            valid_until=NOW + dt.timedelta(days=1),
            max_redemptions=1,
            per_owner_limit=1,
            status=CouponState.ACTIVE,
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_effect_timing=EntitlementEffectTiming.DYNAMIC_DURATION,
            entitlement_duration_seconds=1_296_000,
            entitlement_valid_from=None,
            entitlement_valid_until=None,
            created_at=NOW,
        )
        session.commit()


def _valid_consumer_payloads() -> dict[str, dict]:
    return {
        "access": {
            "schema": "account-commerce-access/1",
            "state": "ACTIVE",
            "expires_at": "2026-09-16T06:00:00Z",
            "evaluated_at": "2026-09-01T06:00:00Z",
        },
        "status": {
            "schema": "account-commerce-status/1",
            "profile_state": "COMPLETE",
            "satisfied_field_codes": ["profile.country", "profile.full_name"],
            "profile_attested_at": "2026-09-01T06:00:00Z",
            "trial_state": "USED_ACTIVE",
            "trial_source": "BETA_TRIAL",
            "trial_expires_at": "2026-09-16T06:00:00Z",
            "access_state": "ACTIVE",
            "access_expires_at": "2026-09-16T06:00:00Z",
            "evaluated_at": "2026-09-01T06:00:00Z",
        },
        "profile": {
            "schema": "account-commerce-profile-evidence/1",
            "profile_state": "COMPLETE",
            "satisfied_field_codes": ["profile.country", "profile.full_name"],
            "attested_at": "2026-09-01T06:00:00Z",
            "replayed": False,
        },
        "trial": {
            "schema": "account-commerce-trial-grant/1",
            "source": "BETA_TRIAL",
            "state": "ACTIVE",
            "expires_at": "2026-09-16T06:00:00Z",
            "replayed": False,
        },
    }


_MALFORMED_TIMESTAMPS = (
    {"coupon": "SECRET-TRIAL-COUPON"},
    {"full_name": "Private Consumer Profile"},
    [], False, 7, 7.5, float("nan"), float("inf"), float("-inf"),
    "2026-09-01T11:30:00+05:30", "2026-09-01T06:00:00z",
    "2026-09-01 06:00:00Z", "2026-9-1T6:0:0Z", "2026-02-30T06:00:00Z",
    "2026-09-01T06:00:60Z", "2026-09-01T06:00:00.1Z",
    " 2026-09-01T06:00:00Z",
)


def _consumer_malformed_corpus() -> list[tuple[str, str, dict]]:
    valid = _valid_consumer_payloads()
    cases: list[tuple[str, str, dict]] = []

    for kind, payload in valid.items():
        extra = copy.deepcopy(payload)
        extra["owner_id"] = "owner.alpha"
        cases.append((kind, "extra-key", extra))
        for field in payload:
            missing = copy.deepcopy(payload)
            del missing[field]
            cases.append((kind, f"missing-{field}", missing))
        for case_id, value in (
            ("schema-null", None), ("schema-number", 1), ("schema-bool", True),
            ("schema-array", []),
            ("schema-object-secret", {"coupon": "SECRET-COUPON", "full_name": "Private Name"}),
            ("schema-wrong-version", "account-commerce-unknown/1"),
        ):
            mutation = copy.deepcopy(payload)
            mutation["schema"] = value
            cases.append((kind, case_id, mutation))

    timestamp_fields = {
        "access": ("expires_at", "evaluated_at"),
        "status": (
            "profile_attested_at", "trial_expires_at", "access_expires_at", "evaluated_at",
        ),
        "profile": ("attested_at",),
        "trial": ("expires_at",),
    }
    for kind, fields in timestamp_fields.items():
        for field in fields:
            for index, value in enumerate(_MALFORMED_TIMESTAMPS):
                mutation = copy.deepcopy(valid[kind])
                mutation[field] = copy.deepcopy(value)
                cases.append((kind, f"{field}-malformed-{index}", mutation))

    def add(kind: str, case_id: str, **changes) -> None:
        mutation = copy.deepcopy(valid[kind])
        mutation.update(changes)
        cases.append((kind, case_id, mutation))

    for case_id, state in (("state-null", None), ("state-bool", True),
                           ("state-object-secret", {"coupon": "SECRET"}),
                           ("state-unknown-internal", "UNKNOWN")):
        add("access", case_id, state=state)
    add("access", "active-expired-time", expires_at="2026-09-01T06:00:00Z")
    add("access", "expired-null-time", state="EXPIRED", expires_at=None)
    add("access", "expired-future-time", state="EXPIRED")
    add("access", "evaluated-null", evaluated_at=None)

    for index, value in enumerate((None, True, 1, "profile.country", {"full_name": "Private Name"})):
        add("status", f"field-codes-not-list-{index}", satisfied_field_codes=value)
    add("status", "field-code-not-string", satisfied_field_codes=["profile.country", {"coupon": "SECRET"}])
    add("status", "field-code-unknown", satisfied_field_codes=["profile.country", "profile.raw_name"])
    add("status", "field-code-duplicate", satisfied_field_codes=["profile.country", "profile.country"])
    add("status", "field-code-noncanonical-order", satisfied_field_codes=["profile.full_name", "profile.country"])
    add("status", "complete-missing-code", satisfied_field_codes=["profile.country"])
    add("status", "incomplete-all-codes", profile_state="INCOMPLETE")
    add("status", "attestation-null-with-codes", profile_attested_at=None)
    add("status", "available-with-source", trial_state="AVAILABLE", trial_expires_at=None)
    add("status", "available-with-expiry", trial_state="AVAILABLE", trial_source=None)
    add("status", "used-with-null-source", trial_source=None)
    add("status", "used-with-null-expiry", trial_expires_at=None)
    add("status", "used-active-expired-time", trial_expires_at="2026-09-01T06:00:00Z")
    add("status", "used-expired-future-time", trial_state="USED_EXPIRED")
    add("status", "access-state-unknown-internal", access_state="UNKNOWN")
    add("status", "access-active-expired-time", access_expires_at="2026-09-01T06:00:00Z")
    add("status", "access-expired-null-time", access_state="EXPIRED", access_expires_at=None)
    add("status", "privacy-bearing-trial-source", trial_source="SECRET-COUPON")
    for field, value in (
        ("profile_state", None), ("profile_state", True), ("trial_state", None),
        ("trial_source", True), ("access_state", None), ("evaluated_at", None),
    ):
        add("status", f"exact-type-{field}-{type(value).__name__}", **{field: value})

    for case_id, changes in (
        ("replayed-null", {"replayed": None}), ("replayed-string", {"replayed": "false"}),
        ("replayed-integer", {"replayed": 0}), ("replayed-array", {"replayed": []}),
        ("profile-state-secret", {"profile_state": "Private Consumer Profile"}),
        ("complete-missing-code", {"satisfied_field_codes": ["profile.country"]}),
        ("incomplete-all-codes", {"profile_state": "INCOMPLETE"}),
        ("duplicate-code", {"satisfied_field_codes": ["profile.full_name", "profile.full_name"]}),
    ):
        add("profile", case_id, **changes)

    for case_id, changes in (
        ("source-null", {"source": None}), ("source-bool", {"source": True}),
        ("source-founder", {"source": "FOUNDER_GRANT"}),
        ("source-secret", {"source": "SECRET-TRIAL-COUPON"}),
        ("state-null", {"state": None}), ("state-pending", {"state": "PENDING"}),
        ("replayed-string", {"replayed": "false"}), ("replayed-number", {"replayed": 1}),
        ("expires-null", {"expires_at": None}),
    ):
        add("trial", case_id, **changes)
    return cases


def test_exact_direct_v1_inventory_and_absent_families(api):
    inventory = {
        (method, route.path)
        for route in api.router.routes
        for method in getattr(route, "methods", set())
        if route.path.startswith("/api/v1/account-commerce")
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
    source = __import__("pathlib").Path(
        "app/api/account_commerce_routes.py"
    ).read_text()
    assert "mount_versioned" not in source
    for shared in ("app/main.py", "app/api/routes.py"):
        assert "account_commerce_routes" not in __import__("pathlib").Path(shared).read_text()
        assert "build_account_commerce_router" not in __import__("pathlib").Path(shared).read_text()
    for path in ("/admin/", "/operator/", "/founder/", "/support/", "/auth/google/"):
        assert path not in source


def test_precision_slate_consumer_transport_strict_parsers_and_privacy(
    api, precision_slate_consumer
):
    consumer = precision_slate_consumer
    assert consumer.transport == {
        "credentials": "same-origin",
        "cache": "no-store",
        "redirect": "error",
        "abort_after_seconds": 10,
        "csrf_header": "X-Strategy-CSRF",
    }
    raw_name = "Private Consumer Profile"
    _, profile = consumer.request(
        "POST",
        "/api/v1/account-commerce/profile-evidence",
        kind="profile",
        body={"full_name": raw_name, "country": "IN"},
    )
    _, trial = consumer.mutate(
        "/api/v1/account-commerce/trials/beta", kind="trial", body={}
    )
    assert consumer.projections["access"]["state"] == "ACTIVE"
    assert consumer.projections["status"]["trial_source"] == "BETA_TRIAL"

    invalid = api.client.post(
        "/api/v1/account-commerce/trials/beta",
        content='{"eligible":true}',
        headers=_post_headers(),
    )
    assert invalid.headers["cache-control"] == "no-store"
    consumer.parse_error(invalid.status_code, invalid.json())
    csrf = api.client.post(
        "/api/v1/account-commerce/trials/beta",
        content="{}",
        headers={"Origin": "https://testserver", "Content-Type": "application/json"},
    )
    assert csrf.headers["cache-control"] == "no-store"
    consumer.parse_error(csrf.status_code, csrf.json())

    negative_mutations = []
    for kind, accepted in (
        ("profile", profile),
        ("trial", trial),
        ("access", consumer.projections["access"]),
        ("status", consumer.projections["status"]),
    ):
        extra = {**accepted, "owner_id": "owner.alpha"}
        missing = dict(accepted)
        missing.pop(next(iter(consumer.success_fields[kind])))
        wrong_schema = {**accepted, "schema": "account-commerce-unknown/1"}
        negative_mutations.extend((
            (kind, extra), (kind, missing), (kind, wrong_schema),
        ))
    negative_mutations.extend((
        ("profile", {**profile, "replayed": "false"}),
        ("trial", {**trial, "source": "FOUNDER_GRANT"}),
        ("access", {**consumer.projections["access"], "state": "UNKNOWN"}),
        ("status", {**consumer.projections["status"], "trial_state": "PENDING"}),
    ))
    for kind, mutation in negative_mutations:
        with pytest.raises(ConsumerContractError):
            consumer.parse_success(kind, mutation)

    retained = json.dumps(consumer.projections, sort_keys=True)
    database_bytes = __import__("pathlib").Path(api.engine.url.database).read_bytes()
    assert raw_name not in retained
    assert raw_name.encode() not in database_bytes


def test_pretrial_access_and_status_present_inactive_without_changing_authority(api):
    headers = {"Origin": "https://testserver"}
    access = api.client.get("/api/v1/account-commerce/access", headers=headers)
    status = api.client.get("/api/v1/account-commerce/status", headers=headers)
    assert access.status_code == 200
    assert access.json() == {
        "schema": "account-commerce-access/1",
        "state": "INACTIVE",
        "expires_at": None,
        "evaluated_at": "2026-09-01T06:00:00Z",
    }
    assert status.status_code == 200
    assert status.json() == {
        "schema": "account-commerce-status/1",
        "profile_state": "INCOMPLETE",
        "satisfied_field_codes": [],
        "profile_attested_at": None,
        "trial_state": "AVAILABLE",
        "trial_source": None,
        "trial_expires_at": None,
        "access_state": "INACTIVE",
        "access_expires_at": None,
        "evaluated_at": "2026-09-01T06:00:00Z",
    }
    with Session(api.engine) as session:
        service = AccountCommerceService(
            session, principal=_principal(), policy=_policy()
        )
        assert service.current_access(server_time=NOW).state == "UNKNOWN"
        assert service.current_status(server_time=NOW).access.state == "UNKNOWN"


def test_public_access_state_mapping_is_exhaustive_and_fail_closed():
    assert {
        state: _public_access_state(state)
        for state in ("ACTIVE", "INACTIVE", "EXPIRED", "UNKNOWN")
    } == {
        "ACTIVE": "ACTIVE",
        "INACTIVE": "INACTIVE",
        "EXPIRED": "EXPIRED",
        "UNKNOWN": "INACTIVE",
    }
    for invalid in (None, True, 1, "PENDING", {}, []):
        with pytest.raises(ValueError, match="invalid internal access state"):
            _public_access_state(invalid)


@pytest.mark.parametrize(
    "kind,case_id,malformed",
    _consumer_malformed_corpus(),
    ids=lambda value: value if type(value) is str else None,
)
def test_precision_slate_consumer_rejects_sealed_malformed_corpus_without_retention(
    kind, case_id, malformed
):
    del case_id
    consumer = PrecisionSlateConsumerFixture()
    valid = _valid_consumer_payloads()
    consumer.projections = copy.deepcopy({
        "access": valid["access"], "status": valid["status"]
    })
    retained = json.dumps(consumer.projections, sort_keys=True, separators=(",", ":"))
    with pytest.raises(ConsumerContractError):
        consumer.parse_success(kind, malformed)
    assert json.dumps(consumer.projections, sort_keys=True, separators=(",", ":")) == retained
    assert consumer.parse_success(kind, copy.deepcopy(valid[kind])) == valid[kind]
    assert json.dumps(consumer.projections, sort_keys=True, separators=(",", ":")) == retained


def test_precision_slate_consumer_accepts_nullable_and_expired_contract_edges():
    consumer = PrecisionSlateConsumerFixture()
    payloads = _valid_consumer_payloads()
    access = {**payloads["access"], "state": "INACTIVE", "expires_at": None}
    status = {
        **payloads["status"],
        "profile_state": "INCOMPLETE",
        "satisfied_field_codes": [],
        "profile_attested_at": "2026-09-01T06:00:00Z",
        "trial_state": "AVAILABLE",
        "trial_source": None,
        "trial_expires_at": None,
        "access_state": "INACTIVE",
        "access_expires_at": None,
    }
    expired_access = {
        **payloads["access"], "state": "EXPIRED",
        "expires_at": "2026-09-01T06:00:00Z",
    }
    expired_status = {
        **payloads["status"],
        "trial_state": "USED_EXPIRED",
        "trial_expires_at": "2026-09-01T06:00:00Z",
        "access_state": "EXPIRED",
        "access_expires_at": "2026-09-01T05:59:59Z",
    }
    for kind, payload in (
        ("access", access), ("status", status),
        ("access", expired_access), ("status", expired_status),
    ):
        assert consumer.parse_success(kind, payload) == payload


@pytest.mark.parametrize("case_id,trial_changes,status_changes", (
    ("trial-source-mismatch", {"source": "COUPON_REDEMPTION"}, {}),
    ("trial-expiry-mismatch", {"expires_at": "2026-09-17T06:00:00Z"}, {}),
    ("trial-state-mismatch", {"state": "EXPIRED"}, {}),
))
def test_precision_slate_consumer_rejects_cross_response_drift(
    case_id, trial_changes, status_changes
):
    del case_id
    payloads = _valid_consumer_payloads()
    trial = {**payloads["trial"], **trial_changes}
    status = {**payloads["status"], **status_changes}
    with pytest.raises(ConsumerContractError):
        PrecisionSlateConsumerFixture._validate_trial_refresh(trial, status)


def test_precision_slate_consumer_aborts_exact_bound_before_parse_or_projection(api):
    entered = threading.Event()
    abort_observed = threading.Event()
    unwound = threading.Event()
    observed_bounds = []

    def cooperative_slow_transport(_method, _path, *, abort_event, **_kwargs):
        entered.set()
        abort_event.wait()
        abort_observed.set()
        unwound.set()
        raise ConsumerAbortError("cooperative transport observed abort")

    def deterministic_waiter(_future, timeout):
        entered.wait()
        observed_bounds.append(timeout)
        raise FutureTimeout()

    consumer = PrecisionSlateConsumerFixture(
        transport=cooperative_slow_transport, waiter=deterministic_waiter
    )
    consumer.projections = {"sentinel": {"state": "unchanged"}}
    retained = json.dumps(consumer.projections, sort_keys=True)
    with pytest.raises(ConsumerAbortError, match="after 10 seconds"):
        consumer.request("GET", "/api/v1/account-commerce/access", kind="access")
    assert observed_bounds == [10]
    assert abort_observed.is_set()
    assert unwound.is_set()
    assert consumer.parse_calls == 0
    assert json.dumps(consumer.projections, sort_keys=True) == retained

    consumer.client = api.client
    consumer._transport = consumer._testclient_transport
    consumer._waiter = FutureWaiter()
    response, parsed = consumer.request(
        "GET", "/api/v1/account-commerce/access", kind="access"
    )
    assert response.status_code == 200
    assert parsed["state"] == "INACTIVE"
    assert consumer.parse_calls == 1
    assert json.dumps(consumer.projections, sort_keys=True) == retained


@pytest.mark.parametrize("path", (
    "/billing/checkout", "/billing/payment", "/billing/subscription", "/billing/refund",
))
def test_billing_stubs_are_constant_before_poison_body_or_dependency_calls(api, path):
    before = dict(api.calls)
    method = "get" if path.endswith("subscription") else "post"
    response = api.client.request(
        method.upper(),
        "/api/v1/account-commerce" + path,
        content=b"not-json\x00" * 10000,
        headers={"Content-Type": "provider/poison"},
    )
    assert response.status_code == 503
    assert response.json() == {
        "code": "BILLING_PROVIDER_UNAVAILABLE",
        "message": "Billing provider is unavailable",
    }
    assert response.headers["cache-control"] == "no-store"
    assert api.calls == before


@pytest.mark.parametrize("mutation", ("anonymous", "service", "mismatched"))
def test_non_browser_principals_fail_closed_before_effects(api, mutation):
    principal = _principal()
    if mutation == "anonymous":
        api.state.principal = None
    elif mutation == "service":
        api.state.principal = Principal(
            id=principal.id, kind="service", scopes=principal.scopes,
            user_id=principal.user_id, organization_id=principal.organization_id,
            session_id=principal.session_id,
        )
    else:
        api.state.principal = Principal(
            id="substituted", kind="user", scopes=principal.scopes,
            user_id=principal.user_id, organization_id=principal.organization_id,
            session_id=principal.session_id,
        )
    response = api.client.post(
        "/api/v1/account-commerce/trials/beta", content="{}", headers=_post_headers()
    )
    assert response.status_code == 401
    assert response.json() == {"error": "authentication refused"}
    assert response.headers["cache-control"] == "no-store"
    assert api.calls["session"] == 0


@pytest.mark.parametrize("headers", (
    {"Content-Type": "application/json"},
    {"Origin": "https://foreign.invalid", "Content-Type": "application/json"},
    {"Origin": "https://testserver", "X-Strategy-CSRF": "0" * 64,
     "Content-Type": "application/json"},
))
def test_mutations_use_current_origin_and_csrf_before_body_or_service(api, headers):
    response = api.client.post(
        "/api/v1/account-commerce/trials/beta", content=b"poison", headers=headers
    )
    assert response.status_code == 403
    assert response.json() == {"error": "authentication refused"}
    assert api.calls["session"] == 0
    assert api.calls["attestor"] == 0


@pytest.mark.parametrize("raw,content_type", (
    (b"", "application/json"),
    (b"[]", "application/json"),
    (b'{"eligible":true}', "application/json"),
    (b'{"coupon":"a","coupon":"b"}', "application/json"),
    (b'{"coupon":{"value":"secret"}}', "application/json"),
    (b"{\xff}", "application/json"),
    (b"{}", "application/json; charset=utf-8"),
    (b"{" + b" " * 4096 + b"}", "application/json"),
))
def test_strict_parser_refuses_shape_duplicate_utf8_media_and_size_before_resolvers(
    api, raw, content_type
):
    response = api.client.post(
        "/api/v1/account-commerce/trials/coupon", content=raw,
        headers={**_post_headers(), "Content-Type": content_type},
    )
    assert response.status_code == 400
    assert response.json() == {
        "code": "ACCOUNT_COMMERCE_REQUEST_INVALID",
        "message": "Account request is invalid",
    }
    assert response.headers["cache-control"] == "no-store"
    assert api.calls["attestor"] == 0
    assert api.calls["coupon_policy"] == 0


@pytest.mark.parametrize("payload", (
    {"full_name": "", "country": "IN"},
    {"full_name": "A\u0000B", "country": "IN"},
    {"full_name": "A" * 129, "country": "IN"},
    {"full_name": "Valid", "country": "in"},
    {"full_name": "Valid", "country": "ZZ"},
    {"full_name": "Valid", "country": ["IN"]},
    {"full_name": "Valid", "country": "IN", "owner_id": "owner.alpha"},
))
def test_profile_normalization_country_and_authority_fields_are_closed(api, payload):
    response = api.client.post(
        "/api/v1/account-commerce/profile-evidence",
        content=json.dumps(payload), headers=_post_headers(),
    )
    assert response.status_code == 400
    assert api.calls["attestor"] == 0


def test_profile_status_access_and_beta_use_closed_no_store_schemas(api, tmp_path):
    raw_name = "  Jose\u0301 Private  "
    profile = api.client.post(
        "/api/v1/account-commerce/profile-evidence",
        content=json.dumps({"full_name": raw_name, "country": "IN"}),
        headers=_post_headers(),
    )
    assert profile.status_code == 200
    assert profile.json() == {
        "schema": "account-commerce-profile-evidence/1",
        "profile_state": "COMPLETE",
        "satisfied_field_codes": ["profile.country", "profile.full_name"],
        "attested_at": "2026-09-01T06:00:00Z",
        "replayed": False,
    }
    replay = api.client.post(
        "/api/v1/account-commerce/profile-evidence",
        json={"full_name": "Jos\u00e9 Private", "country": "IN"},
        headers=_post_headers(),
    )
    assert replay.json()["replayed"] is True

    beta = api.client.post(
        "/api/v1/account-commerce/trials/beta", content="{}", headers=_post_headers()
    )
    assert beta.status_code == 200
    assert beta.json() == {
        "schema": "account-commerce-trial-grant/1",
        "source": "BETA_TRIAL", "state": "ACTIVE",
        "expires_at": "2026-09-16T06:00:00Z", "replayed": False,
    }
    retry = api.client.post(
        "/api/v1/account-commerce/trials/beta", content="{}", headers=_post_headers()
    )
    assert retry.json() == {**beta.json(), "replayed": True}

    status = api.client.get(
        "/api/v1/account-commerce/status", headers={"Origin": "https://testserver"}
    )
    assert status.status_code == 200
    assert status.json()["schema"] == "account-commerce-status/1"
    assert status.json()["trial_state"] == "USED_ACTIVE"
    access = api.client.get(
        "/api/v1/account-commerce/access", headers={"Origin": "https://testserver"}
    )
    assert access.status_code == 200
    assert access.json() == {
        "schema": "account-commerce-access/1", "state": "ACTIVE",
        "expires_at": "2026-09-16T06:00:00Z",
        "evaluated_at": "2026-09-01T06:00:00Z",
    }
    combined = " ".join(
        json.dumps(response.json()) for response in (profile, replay, beta, retry, status, access)
    )
    assert "Private" not in combined
    assert "owner.alpha" not in combined
    assert "user.alpha" not in combined
    assert "session.alpha" not in combined
    assert "sha256:" not in combined
    with Session(api.engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountProfileEvidenceRow)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountTrialUseRow)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(PlatformEntitlementEventRow)) == 1


@pytest.mark.parametrize("kind", ("beta", "coupon"))
def test_simultaneous_identical_trial_routes_converge_to_original_and_replay(
    api, monkeypatch, kind
):
    secret = "BETA-ACCESS-ONLY"
    if kind == "coupon":
        _seed_coupon(api.engine, secret)
    original_status = AccountCommerceService.current_status
    barrier = threading.Barrier(2)
    counter_lock = threading.Lock()
    calls = 0

    def synchronized_status(self, *, server_time):
        nonlocal calls
        result = original_status(self, server_time=server_time)
        with counter_lock:
            calls += 1
            synchronize = calls <= 2
        if synchronize:
            barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(AccountCommerceService, "current_status", synchronized_status)
    path = f"/api/v1/account-commerce/trials/{kind}"
    content = "{}" if kind == "beta" else json.dumps({"coupon": secret})

    def request():
        return api.client.post(path, content=content, headers=_post_headers())

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _index: request(), range(2)))

    assert [response.status_code for response in responses] == [200, 200]
    bodies = [response.json() for response in responses]
    assert sorted(body["replayed"] for body in bodies) == [False, True]
    assert {body["source"] for body in bodies} == {
        "BETA_TRIAL" if kind == "beta" else "COUPON_REDEMPTION"
    }
    assert len({body["expires_at"] for body in bodies}) == 1
    with Session(api.engine) as session:
        for model in (
            AccountProfileEvidenceRow,
            AccountTrialUseRow,
            PlatformEntitlementEventRow,
            PlatformCurrentEntitlementRow,
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(model)) == 1
        expected_redemptions = 1 if kind == "coupon" else 0
        assert session.scalar(
            sa.select(sa.func.count()).select_from(PlatformCouponRedemptionRow)
        ) == expected_redemptions
    conflict_path = (
        "/api/v1/account-commerce/trials/coupon"
        if kind == "beta"
        else "/api/v1/account-commerce/trials/beta"
    )
    conflict_content = json.dumps({"coupon": "DIFFERENT-SOURCE"}) if kind == "beta" else "{}"
    conflict = api.client.post(
        conflict_path, content=conflict_content, headers=_post_headers()
    )
    assert conflict.status_code == 409
    assert conflict.json() == {
        "code": "ACCOUNT_COMMERCE_CONFLICT",
        "message": "Account request conflicts with existing state",
    }
    database_bytes = __import__("pathlib").Path(api.engine.url.database).read_bytes()
    assert secret.encode() not in database_bytes
    assert b"DIFFERENT-SOURCE" not in database_bytes


def test_trial_route_retries_one_explicit_sqlite_lock_in_a_fresh_session(
    api, monkeypatch
):
    original = AccountCommerceService.grant_beta_trial
    attempts = 0

    def transient_lock(self, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OperationalError(
                "INSERT", {}, sqlite3.OperationalError("database is locked")
            )
        return original(self, **kwargs)

    monkeypatch.setattr(AccountCommerceService, "grant_beta_trial", transient_lock)
    response = api.client.post(
        "/api/v1/account-commerce/trials/beta", content="{}", headers=_post_headers()
    )
    assert response.status_code == 200
    assert response.json()["replayed"] is False
    assert attempts == 2
    assert api.calls["session"] == 3


def test_trial_route_does_not_retry_other_database_failures(api, monkeypatch):
    attempts = 0

    def database_failure(_self, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise OperationalError(
            "INSERT", {}, sqlite3.OperationalError("disk I/O error")
        )

    monkeypatch.setattr(AccountCommerceService, "grant_beta_trial", database_failure)
    response = api.client.post(
        "/api/v1/account-commerce/trials/beta", content="{}", headers=_post_headers()
    )
    assert response.status_code == 503
    assert response.json() == {
        "code": "ACCOUNT_COMMERCE_UNAVAILABLE",
        "message": "Account service is unavailable",
    }
    assert attempts == 1


def test_get_body_and_bearer_cookie_mix_are_refused(api):
    body = api.client.request(
        "GET", "/api/v1/account-commerce/access", content="{}",
        headers={"Origin": "https://testserver"},
    )
    assert body.status_code == 400
    mixed = api.client.get(
        "/api/v1/account-commerce/access",
        headers={"Origin": "https://testserver", "Authorization": "Bearer poison"},
    )
    assert mixed.status_code == 401
    assert mixed.json() == {"error": "authentication refused"}


def test_coupon_byte_boundary_uses_server_resolvers_without_echoing_plaintext(api):
    secret = "S" * 256
    response = api.client.post(
        "/api/v1/account-commerce/trials/coupon",
        content=json.dumps({"coupon": secret}), headers=_post_headers(),
    )
    assert response.status_code == 409
    assert response.json() == {
        "code": "ACCOUNT_COMMERCE_CONFLICT",
        "message": "Account request conflicts with existing state",
    }
    assert secret not in response.text
    assert api.calls["attestor"] == 1
    assert api.calls["eligibility"] == 1
    assert api.calls["coupon_policy"] == 1
    assert api.calls["coupon_proof"] == 1

    before = dict(api.calls)
    oversized = api.client.post(
        "/api/v1/account-commerce/trials/coupon",
        content=json.dumps({"coupon": "S" * 257}), headers=_post_headers(),
    )
    assert oversized.status_code == 400
    assert api.calls == before


def test_stale_browser_session_returns_fixed_auth_error_without_write(api):
    with Session(api.engine) as session:
        session.get(UserSession, "session.alpha").revoked_at = NOW.replace(tzinfo=None)
        session.commit()
    response = api.client.post(
        "/api/v1/account-commerce/profile-evidence",
        json={"full_name": "Private Person", "country": "IN"},
        headers=_post_headers(),
    )
    assert response.status_code == 401
    assert response.json() == {"error": "authentication refused"}
    assert api.calls["attestor"] == 0
    with Session(api.engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(AccountProfileEvidenceRow)) == 0
