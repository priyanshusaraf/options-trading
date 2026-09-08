"""Task 5A behavioural contract for durable user-plane sessions.

These tests exercise the resolver at its public boundary.  The raw bearer value
is deliberately only present at issuance and request time; persistence and SQL
assertions deal in its SHA-256 digest.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import inspect
import logging
import secrets
import base64
from uuid import RFC_4122, UUID, uuid4

import pytest
from fastapi import Request
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from app.api import principal as principal_api
from app.core.config import BootConfigError, Settings, assert_boot_config, get_settings
from app.db import models
from app.db.session import SessionLocal, engine, init_db
from app.platform_operations.contracts import OperationsRefused, _FORBIDDEN, reference


UTC = dt.timezone.utc


def _canonical_session_handle(value: str) -> UUID:
    parsed = UUID(value)
    assert value == str(parsed)
    assert parsed.variant == RFC_4122
    assert parsed.version == 4
    assert parsed.int != 0
    assert len(value) == 36
    return parsed


class _FakeWs:
    def __init__(self, token: str | None):
        self.query_params = {}
        self.headers = {}
        self.cookies = {} if token is None else {"pt_session": token}


def _request(token: str | None) -> Request:
    headers = [] if token is None else [(b"authorization", f"Bearer {token}".encode())]
    return Request({"type": "http", "method": "GET", "path": "/api/status",
                    "query_string": b"", "headers": headers})


def _session_model():
    value = getattr(models, "UserSession", None)
    assert value is not None, "Task 5A must persist a UserSession record"
    return value


def _service(name: str):
    value = getattr(principal_api, name, None)
    assert callable(value), f"Task 5A must provide {name}"
    return value


def _seed(*, memberships: tuple[tuple[str, str, str, str], ...] = (
        ("org.a", "user.a", "owner", "active"),
        ("org.b", "user.b", "member", "active"),
)):
    """Return active roots with deliberately independent user and org identities."""
    _session_model()
    init_db(reset=True)
    with SessionLocal() as session:
        for organization_id in sorted({org for org, *_ in memberships}):
            session.add(models.Organization(organization_id=organization_id,
                                            name=organization_id))
        for user_id in sorted({user for _, user, *_ in memberships}):
            session.add(models.User(user_id=user_id,
                                    email_normalized=f"{user_id}@example.test",
                                    display_name=user_id))
        session.flush()
        for organization_id, user_id, role, status in memberships:
            session.add(models.Membership(organization_id=organization_id, user_id=user_id,
                                          role=role, status=status))
        session.commit()


def _issue(*, user_id: str, organization_id: str,
           expires_at: dt.datetime | None = None):
    issue = _service("issue_user_session")
    with SessionLocal() as session:
        issued = issue(session, user_id=user_id, organization_id=organization_id,
                       expires_at=expires_at or (dt.datetime.now(UTC) + dt.timedelta(hours=1)))
        session.commit()
        return issued


def test_two_users_resolve_only_their_own_active_membership(monkeypatch):
    """Removing the digest predicate or returning the legacy owner must break this."""
    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", "configured-legacy-token")
    a = _issue(user_id="user.a", organization_id="org.a")
    b = _issue(user_id="user.b", organization_id="org.b")

    a_principal = principal_api.resolve_principal(a.token)
    b_principal = principal_api.resolve_principal(b.token)

    assert (a_principal.user_id, a_principal.organization_id, a_principal.role) == (
        "user.a", "org.a", "owner")
    assert (b_principal.user_id, b_principal.organization_id, b_principal.role) == (
        "user.b", "org.b", "member")


def test_issued_bearer_contains_at_least_256_random_bits(monkeypatch):
    """Shortening the issued random byte source must fail this independent check."""
    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    issued = _issue(user_id="user.a", organization_id="org.a")
    padding = "=" * (-len(issued.token) % 4)
    assert len(base64.urlsafe_b64decode(issued.token + padding)) >= 32


def test_generated_record_handle_is_canonical_uuid4_and_caller_override_is_retired(monkeypatch):
    """The handle is one server authority, while the bearer retains 256 random bits."""
    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    issued = _issue(user_id="user.a", organization_id="org.a")

    _canonical_session_handle(issued.session_id)
    assert reference(issued.session_id, "browser session", maximum=64) == issued.session_id
    assert "session_id" not in inspect.signature(principal_api.issue_user_session).parameters
    with SessionLocal() as session:
        row = session.get(models.UserSession, issued.session_id)
        assert row.session_id == issued.session_id
        assert row.token_digest == hashlib.sha256(issued.token.encode()).hexdigest()
        assert row.token_digest != issued.session_id


@pytest.mark.parametrize("invalid", ("-" + "A" * 23, "_" + "A" * 23, "s.token" + "A" * 19))
def test_old_and_prefixed_base64url_handle_mutations_are_refused(monkeypatch, invalid):
    """Restoring either rejected generator must reproduce the closed-consumer RED."""
    _seed()
    monkeypatch.setattr(principal_api, "uuid4", lambda: invalid)
    issued = _issue(user_id="user.a", organization_id="org.a")
    assert issued.session_id == invalid
    with pytest.raises(OperationsRefused):
        reference(issued.session_id, "browser session", maximum=64)


def test_uuid4_alphabet_cannot_form_an_operations_privacy_sentinel():
    """Broadening the downstream privacy contract is unnecessary and forbidden."""
    alphabet = set("0123456789abcdef-")
    assert all(not set(sentinel).issubset(alphabet) for sentinel in _FORBIDDEN)
    for _ in range(256):
        handle = str(uuid4())
        _canonical_session_handle(handle)
        assert reference(handle, "browser session", maximum=64) == handle


@pytest.mark.parametrize("collision", ("handle", "digest"))
def test_session_handle_and_digest_collisions_roll_back_without_rebinding(
    monkeypatch, collision
):
    """Both database identities fail closed and a fresh whole-operation retry works."""
    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", "")
    existing_handle = str(uuid4())
    colliding_bearer = "B" * 43
    existing_digest = (
        hashlib.sha256(colliding_bearer.encode()).hexdigest()
        if collision == "digest"
        else "a" * 64
    )
    with SessionLocal() as session:
        session.add(models.UserSession(
            session_id=existing_handle,
            token_digest=existing_digest,
            user_id="user.b",
            organization_id="org.b",
            issued_at=dt.datetime.now(UTC),
            expires_at=dt.datetime.now(UTC) + dt.timedelta(hours=1),
        ))
        session.commit()

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
        with SessionLocal() as session:
            issued = principal_api.issue_user_session(
                session,
                user_id="user.a",
                organization_id="org.a",
                expires_at=dt.datetime.now(UTC) + dt.timedelta(hours=1),
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
        collision_resolution = principal_api.resolve_principal(issued.token)
        if collision == "handle":
            assert collision_resolution is None
        else:
            assert (collision_resolution.user_id, collision_resolution.organization_id) == (
                "user.b", "org.b")
            assert collision_resolution.session_id == existing_handle

    with SessionLocal() as session:
        existing = session.get(models.UserSession, existing_handle)
        assert (existing.user_id, existing.organization_id, existing.token_digest) == (
            "user.b", "org.b", existing_digest)
        assert session.scalars(select(models.UserSession).where(
            models.UserSession.user_id == "user.a"
        )).all() == []

    recovered = _issue(user_id="user.a", organization_id="org.a")
    _canonical_session_handle(recovered.session_id)
    resolved = principal_api.resolve_principal(recovered.token)
    assert (resolved.user_id, resolved.organization_id) == ("user.a", "org.a")


def test_one_user_can_hold_distinct_active_organization_sessions(monkeypatch):
    """Ignoring the session's active organization would make these principals equal."""
    _seed(memberships=(("org.a", "user.a", "owner", "active"),
                       ("org.b", "user.a", "admin", "active")))
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", "configured-legacy-token")
    first = _issue(user_id="user.a", organization_id="org.a")
    second = _issue(user_id="user.a", organization_id="org.b")

    assert principal_api.resolve_principal(first.token).organization_id == "org.a"
    assert principal_api.resolve_principal(second.token).organization_id == "org.b"


@pytest.mark.parametrize("state", ("unknown", "malformed", "expired", "revoked"))
def test_unknown_malformed_expired_and_revoked_credentials_are_indistinguishable(monkeypatch, state):
    """Dropping any fail-closed predicate must make one case resolve."""
    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", "configured-legacy-token")
    token = None
    if state == "expired":
        token = _issue(user_id="user.a", organization_id="org.a",
                       expires_at=dt.datetime.now(UTC) - dt.timedelta(seconds=1)).token
    elif state == "revoked":
        issued = _issue(user_id="user.a", organization_id="org.a")
        revoke = _service("revoke_user_session")
        with SessionLocal() as session:
            revoke(session, issued.session_id)
            session.commit()
        token = issued.token
    elif state == "malformed":
        token = "not a bearer credential"
    else:
        token = secrets.token_urlsafe(32)

    assert principal_api.resolve_principal(token) is None


@pytest.mark.parametrize("change", ("user", "organization", "membership"))
def test_disabled_identity_or_membership_cannot_resolve(monkeypatch, change):
    """The resolver must reject status changes made after the session was issued."""
    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", "configured-legacy-token")
    issued = _issue(user_id="user.a", organization_id="org.a")
    with SessionLocal() as session:
        if change == "user":
            session.get(models.User, "user.a").status = "disabled"
        elif change == "organization":
            session.get(models.Organization, "org.a").status = "disabled"
        else:
            session.get(models.Membership, ("org.a", "user.a")).status = "revoked"
        session.commit()
    assert principal_api.resolve_principal(issued.token) is None


def test_session_active_organization_must_be_a_real_membership():
    """A database constraint, not resolver convention, protects this invariant."""
    UserSession = _session_model()
    _seed()
    with SessionLocal() as session:
        session.add(UserSession(session_id="mismatch", token_digest="a" * 64,
                                user_id="user.a", organization_id="org.b",
                                issued_at=dt.datetime.now(UTC),
                                expires_at=dt.datetime.now(UTC) + dt.timedelta(hours=1)))
        with pytest.raises(Exception):
            session.commit()
        session.rollback()


def test_persistence_sql_logs_and_principal_dto_never_expose_plaintext_token(monkeypatch, caplog):
    """Changing the digest write or serialisation path to use the bearer must fail this."""
    UserSession = _session_model()
    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", "configured-legacy-token")
    captured: list[tuple[str, object]] = []

    def capture(_conn, _cursor, statement, parameters, _context, _many):
        captured.append((statement, parameters))

    event.listen(engine, "before_cursor_execute", capture)
    try:
        with caplog.at_level(logging.DEBUG):
            issued = _issue(user_id="user.a", organization_id="org.a")
            principal = principal_api.resolve_principal(issued.token)
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    with SessionLocal() as session:
        row = session.get(UserSession, issued.session_id)
        assert row.token_digest == hashlib.sha256(issued.token.encode()).hexdigest()
        assert issued.token not in repr(row)
    assert issued.token not in principal.to_dict().values()
    assert all(issued.token not in statement and issued.token not in repr(parameters)
               for statement, parameters in captured)
    assert issued.token not in caplog.text


@pytest.mark.parametrize("representation", ("repr", "str", "list", "log_s", "log_r"))
def test_issued_bearer_routine_representations_omit_token(monkeypatch, caplog, representation):
    """Removing token repr suppression must fail every routine representation."""
    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", "configured-legacy-token")
    issued = _issue(user_id="user.a", organization_id="org.a")

    # Explicit one-time delivery remains usable; this is not serialization redaction.
    principal = principal_api.resolve_principal(issued.token)
    assert (principal.user_id, principal.organization_id) == ("user.a", "org.a")
    if representation.startswith("log_"):
        with caplog.at_level(logging.INFO, logger=__name__):
            logging.getLogger(__name__).info(
                "issued %s" if representation == "log_s" else "issued %r", issued)
        rendered = caplog.text
    else:
        rendered = {"repr": repr(issued), "str": str(issued), "list": repr([issued])}[representation]
    assert "IssuedBearerCredential" in rendered
    assert issued.session_id in rendered
    assert issued.token not in rendered


def test_unknown_token_is_a_digest_first_lookup_without_membership_materialization(monkeypatch):
    """Removing the digest lookup first must make this issue membership/user SQL."""
    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", "configured-legacy-token")
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(" ".join(statement.lower().split()))

    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert principal_api.resolve_principal(secrets.token_urlsafe(32)) is None
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    reads = [statement for statement in statements if "select" in statement]
    assert len(reads) == 1
    assert "user_sessions" in reads[0]
    assert "memberships" not in reads[0] and "users" not in reads[0]


def test_http_and_websocket_credentials_share_the_same_resolver(monkeypatch):
    """A second WebSocket token authority would make this deliberate mutation fail."""
    calls = []
    sentinel = principal_api.Principal("sentinel", "user", frozenset({"*"}))

    def shared(token):
        calls.append(token)
        return sentinel

    monkeypatch.setattr(principal_api, "resolve_principal", shared)
    assert principal_api.resolve_http_principal(_request("http-bearer")) is sentinel
    assert principal_api.resolve_ws_proof(None, "", "ws-bearer") is sentinel
    assert calls == ["http-bearer", "ws-bearer"]


def test_websocket_rejects_handshake_credentials(monkeypatch):
    """Changing WS auth back to ?token= would leak bearer material in server logs."""
    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    issued = _issue(user_id="user.a", organization_id="org.a")
    url_token = _FakeWs(None)
    url_token.query_params = {"token": issued.token}
    assert principal_api.resolve_ws_principal(url_token) is None
    assert principal_api.resolve_ws_principal(_FakeWs(issued.token)) is None


def test_websocket_protocol_filter_redacts_installed_websockets_frame_records():
    """Protocol DEBUG must retain frame metadata but never the bearer payload."""
    from websockets.frames import Frame, Opcode

    secret = "bearer-that-must-never-reach-a-log-handler"
    record = logging.LogRecord(
        "uvicorn.error", logging.DEBUG, __file__, 1, "< %s",
        (Frame(Opcode.TEXT, (f'{{"type":"authenticate","bearer":"{secret}"}}').encode()),),
        None,
    )
    redactor = principal_api._WebSocketPayloadRedactionFilter()
    assert redactor.filter(record) is True
    assert secret not in record.getMessage()
    assert "inbound text" in record.getMessage()
    assert "bytes" in record.getMessage()

    preformatted = logging.LogRecord(
        "websockets.protocol", logging.DEBUG, __file__, 1,
        f"< TEXT '{{\"bearer\":\"{secret}\"}}' [12 bytes]", (), None,
    )
    redactor.filter(preformatted)
    assert secret not in preformatted.getMessage()
    assert "redacted" in preformatted.getMessage()

    ordinary = logging.LogRecord("uvicorn.error", logging.DEBUG, __file__, 1,
                                 "connection diagnostic %s", ("kept",), None)
    redactor.filter(ordinary)
    assert ordinary.getMessage() == "connection diagnostic kept"


def test_disabled_auth_refuses_production_boot_and_yields_explicit_development_principal(monkeypatch):
    """Changing either service-role branch must fail one half of this boundary test."""
    with pytest.raises(BootConfigError, match="authentication is disabled"):
        assert_boot_config(Settings(service_role="production", api_token="", auth_disabled=True),
                           env_file=".env", under_test=False, warn=lambda _message: None)
    monkeypatch.setattr(get_settings(), "service_role", "development", raising=False)
    monkeypatch.setattr(get_settings(), "auth_disabled", True)
    monkeypatch.setattr(get_settings(), "api_token", "")
    principal = principal_api.resolve_principal(None)
    assert principal is principal_api.DEVELOPMENT_ANONYMOUS
    assert principal.kind == "anonymous_owner"
    assert principal.authenticated is False


def test_production_accepts_legacy_bootstrap_or_explicit_durable_auth_mode():
    """Legacy upgrade and tokenless durable production are both valid enabled postures."""
    assert_boot_config(Settings(service_role="production", api_token="legacy-token",
                                event_cursor_secret="s" * 32),
                       env_file=".env", under_test=False, warn=lambda _message: None)
    assert_boot_config(Settings(service_role="production", api_token="", auth_disabled=False,
                                event_cursor_secret="s" * 32),
                       env_file=".env", under_test=False, warn=lambda _message: None)


def test_explicit_development_disabled_auth_overrides_a_stale_legacy_bootstrap_token(monkeypatch):
    """A development disable switch must not leave a copied legacy secret authoritative."""
    monkeypatch.setattr(get_settings(), "service_role", "development")
    monkeypatch.setattr(get_settings(), "api_token", "stale-legacy-token")
    monkeypatch.setattr(get_settings(), "auth_disabled", True)
    assert principal_api.resolve_principal("stale-legacy-token") is principal_api.DEVELOPMENT_ANONYMOUS


def test_concurrent_issuance_and_revocation_leave_only_active_sessions_resolvable(monkeypatch):
    """Concurrent issuers remain distinct and a competing revoke wins exactly once."""
    _seed()
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", "configured-legacy-token")

    def issue_one(_number):
        return _issue(user_id="user.a", organization_id="org.a")

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        issued = list(pool.map(issue_one, range(8)))
    assert len({item.session_id for item in issued}) == len(issued)
    assert all(_canonical_session_handle(item.session_id) for item in issued)
    assert len({hashlib.sha256(item.token.encode()).hexdigest() for item in issued}) == len(issued)
    assert all(principal_api.resolve_principal(item.token) is not None for item in issued)

    revoked = issued[0]
    revoke = _service("revoke_user_session")

    def revoke_one(_number):
        with SessionLocal() as session:
            changed = revoke(session, revoked.session_id)
            session.commit()
            return changed

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(revoke_one, range(8)))
    assert outcomes.count(True) == 1
    assert principal_api.resolve_principal(revoked.token) is None
    assert all(principal_api.resolve_principal(item.token) is not None for item in issued[1:])


def test_legacy_token_bootstrap_binds_only_the_seeded_legacy_identity(monkeypatch):
    """Overwriting a foreign digest binding would make the second assertion fail."""
    UserSession = _session_model()
    token = secrets.token_urlsafe(32)
    monkeypatch.setattr(get_settings(), "auth_disabled", False)
    monkeypatch.setattr(get_settings(), "api_token", token)
    init_db(reset=True)
    digest = hashlib.sha256(token.encode()).hexdigest()
    with SessionLocal() as session:
        legacy = session.scalar(select(UserSession).where(UserSession.token_digest == digest))
        assert legacy.user_id == models.LEGACY_USER_ID
        assert legacy.organization_id == models.LEGACY_OWNER_ID
        _canonical_session_handle(legacy.session_id)
        bootstrap = _service("bootstrap_legacy_session")
        assert bootstrap(session, token).session_id == legacy.session_id
        session.add(models.Organization(organization_id="org.a", name="A"))
        session.add(models.User(user_id="user.a", email_normalized="a@example.test",
                                display_name="A"))
        session.flush()
        session.add(models.Membership(organization_id="org.a", user_id="user.a"))
        session.delete(legacy)
        session.flush()
        session.add(UserSession(session_id="foreign-binding", token_digest=digest,
                                user_id="user.a", organization_id="org.a",
                                issued_at=dt.datetime.now(UTC),
                                expires_at=dt.datetime.now(UTC) + dt.timedelta(hours=1)))
        session.commit()
        with pytest.raises(RuntimeError, match="foreign"):
            bootstrap(session, token)
        foreign = session.get(UserSession, "foreign-binding")
        assert (foreign.user_id, foreign.organization_id) == ("user.a", "org.a")
