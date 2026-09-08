"""Bounded invited-user lifecycle. UserSession remains the sole authority.

No provider, mail, token-in-JSON or password-recovery boundary lives here.
The fixed limits are also recorded in the Q01 policy/evidence packet.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import ipaddress
import re
import secrets
import threading
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from uuid import uuid4

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from sqlalchemy import delete, func, select, update

from app.api.principal import (_active_membership, _now, _principal_for_active_session,
                               issue_user_session, token_digest)
from app.core.config import effective_auth_enabled, get_settings
from app.core.release_profile import is_v0_profile, parse_release_service_role, ReleaseServiceRole
from app.db.concurrency import begin_reservation
from app.db.models import (LEGACY_USER_ID, BrowserAuthAttempt, BrowserCredential,
                           BrowserSession, EnrollmentInvite, Membership, Organization,
                           PasswordVerifier, User, UserSession)
from app.db.session import SessionLocal

COOKIE = '__Host-strategy-session'
CSRF_HEADER = 'x-strategy-csrf'
MAX_BODY = 8192
ABSOLUTE = dt.timedelta(hours=12)
IDLE = dt.timedelta(minutes=30)
WINDOW_SECONDS = 900
MAX_COUNTERS = 4096
AUTH_SLOTS = threading.BoundedSemaphore(2)
LIFECYCLE_LOCK = 'browser-auth-lifecycle-v1'
COUNTER_LOCK = 'browser-auth-attempts-v1'
VERIFIER_PATTERN = re.compile(r'a2id-v1\$([0-9a-f]{32})\$([0-9a-f]{64})\Z')
TOKEN_PATTERN = re.compile(r'[A-Za-z0-9_-]{43}\Z')
# Small local denylist only; no claim of breach-corpus coverage.
COMMON_PASSWORDS = frozenset({'passwordpassword', 'password123456789',
                             '123456789012345', 'qwertyuiopasdfgh',
                             'letmeinletmeinletmein', 'correct horse battery staple'})


class AuthRefusal(Exception):
    def __init__(self, status: int = 401):
        self.status = status
        super().__init__('authentication unavailable' if status == 503 else 'authentication refused')


class SessionRefusal(AuthRefusal):
    """A well-formed cookie no longer resolves; public bootstraps may clear it."""


class ActionRefusal(AuthRefusal):
    """The session remains valid, but current action credentials/input refuse."""

    def __init__(self):
        super().__init__(422)


@dataclass(frozen=True)
class IssuedInvite:
    token: str = field(repr=False)
    expires_at: dt.datetime


def validate_configuration(settings) -> bool:
    if not settings.browser_auth_enabled:
        return False
    origin = settings.browser_auth_origin
    try:
        parsed = urlsplit(origin)
        port = parsed.port
        hostname = parsed.hostname or ''
        try:
            ipaddress.ip_address(hostname)
            valid_host = True
        except ValueError:
            valid_host = len(hostname) <= 253 and all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', part)
                                                       for part in hostname.split('.'))
        canonical_host = f'[{hostname}]' if ':' in hostname else hostname
        canonical_netloc = canonical_host + (f':{port}' if port is not None and port != 443 else '')
        valid_origin = (parsed.scheme == 'https' and bool(parsed.hostname)
                        and valid_host and parsed.netloc == canonical_netloc
                        and not parsed.username and not parsed.password
                        and not parsed.path and not parsed.query and not parsed.fragment
                        and parsed.netloc == parsed.netloc.lower()
                        and origin == f'https://{parsed.netloc}'
                        and (port is None or 1 <= port <= 65535)
                        and not any(c.isspace() for c in origin))
        role = parse_release_service_role(settings.release_service_role)
    except (ValueError, TypeError):
        return False
    return (valid_origin and is_v0_profile(settings.release_profile)
            and role is ReleaseServiceRole.API and effective_auth_enabled(settings)
            and re.fullmatch(r'[0-9a-f]{64}', settings.browser_auth_counter_secret) is not None)


def normalize_email(value: object) -> str:
    if not isinstance(value, str) or len(value) > 320:
        raise AuthRefusal()
    value = value.strip().lower()
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise AuthRefusal() from None
    if not re.fullmatch(r'[^\s@\x00-\x1f]{1,64}@[^\s@\x00-\x1f]+\.[^\s@\x00-\x1f]+', value):
        raise AuthRefusal()
    return value


def password_bytes(value: object) -> bytes:
    if not isinstance(value, str) or not 15 <= len(value) <= 128:
        raise AuthRefusal()
    try:
        raw = value.encode('utf-8')
    except UnicodeError:
        raise AuthRefusal() from None
    if len(raw) > 512 or value.lower() in COMMON_PASSWORDS:
        raise AuthRefusal()
    return raw


def kdf(salt: bytes) -> Argon2id:
    return Argon2id(salt=salt, length=32, iterations=2, lanes=1, memory_cost=19456)


def hash_password(password: str) -> PasswordVerifier:
    raw = password_bytes(password)
    salt = secrets.token_bytes(16)
    derived = kdf(salt).derive(raw)
    return PasswordVerifier(f'a2id-v1${salt.hex()}${derived.hex()}')


def valid_verifier(value: object) -> bool:
    return isinstance(value, str) and len(value) <= 160 and VERIFIER_PATTERN.fullmatch(value) is not None


def verify_password(password: str, verifier: str | None) -> bool:
    raw = password_bytes(password)
    # Invalid/unknown stored profiles receive the same fixed-cost work, but
    # their attacker-chosen cost/salt/output parameters never reach the KDF.
    matched = VERIFIER_PATTERN.fullmatch(verifier) if valid_verifier(verifier) else None
    salt, expected = (bytes.fromhex(matched[1]), bytes.fromhex(matched[2])) if matched else (b'\0' * 16, b'\0' * 32)
    try:
        kdf(salt).verify(raw, expected)
    except InvalidKey:
        return False
    return matched is not None


def admit_attempt(email: str, client: str) -> None:
    """One shared fixed-window admission; no raw account/address persistence."""
    settings = get_settings()
    key = bytes.fromhex(settings.browser_auth_counter_secret)
    now = _now()
    epoch = int(now.replace(tzinfo=dt.timezone.utc).timestamp())
    expiry = dt.datetime.fromtimestamp((epoch // WINDOW_SECONDS + 1) * WINDOW_SECONDS, dt.timezone.utc).replace(tzinfo=None)
    counters = [(hmac.new(key, (purpose + '\0' + value).encode(), hashlib.sha256).hexdigest(), limit)
                for purpose, value, limit in [('account', email, 10), ('client', client, 60)]]
    denied = False
    with SessionLocal() as session:
        begin_reservation(session, scope=COUNTER_LOCK)
        session.execute(delete(BrowserAuthAttempt).where(BrowserAuthAttempt.expires_at <= now))
        rows = [(digest, limit, session.get(BrowserAuthAttempt, digest)) for digest, limit in counters]
        count = session.scalar(select(func.count()).select_from(BrowserAuthAttempt))
        if any(row is not None and row.attempts >= limit for _, limit, row in rows):
            # An exhausted client/account cannot allocate arbitrary new identity
            # counters and consume the remaining shared retention budget.
            denied = True
        elif count + sum(row is None for _, _, row in rows) > MAX_COUNTERS:
            denied = True
        else:
            for digest, limit, row in rows:
                if row is None:
                    session.add(BrowserAuthAttempt(key_digest=digest, expires_at=expiry, attempts=1))
                else:
                    row.attempts += 1
        session.commit()  # Refused attempts and cleanup must survive the error.
    if denied:
        raise AuthRefusal(429)


def create_invite(email: str, *, minutes: int = 60) -> IssuedInvite:
    email = normalize_email(email)
    if type(minutes) is not int or not 1 <= minutes <= 60:
        raise AuthRefusal()
    now = _now()
    raw = secrets.token_urlsafe(32)
    with SessionLocal() as session:
        begin_reservation(session, scope=LIFECYCLE_LOCK)
        if session.scalar(select(User.user_id).where(User.email_normalized == email)):
            raise AuthRefusal()
        session.add(EnrollmentInvite(invite_digest=token_digest(raw), email_normalized=email,
                                    purpose='enrollment', created_at=now,
                                    expires_at=now + dt.timedelta(minutes=minutes)))
        session.commit()
    return IssuedInvite(raw, now + dt.timedelta(minutes=minutes))


def _revoke(session, user_id: str, *, session_id: str | None = None):
    statement = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if session_id is not None:
        statement = statement.where(UserSession.session_id == session_id)
    session.execute(statement.values(revoked_at=_now()))


def _issue(session, user_id: str, organization_id: str):
    issued = issue_user_session(session, user_id=user_id, organization_id=organization_id,
                                expires_at=_now() + ABSOLUTE)
    session.flush()
    session.add(BrowserSession(session_id=issued.session_id, last_seen_at=_now()))
    session.flush()
    return issued


def _active_browser(session, token: str):
    now = _now()
    row = session.scalar(select(UserSession).join(BrowserSession).where(
        UserSession.token_digest == token_digest(token), UserSession.revoked_at.is_(None),
        UserSession.expires_at > now, UserSession.user_id != LEGACY_USER_ID,
        UserSession.issued_at > now - ABSOLUTE,
        BrowserSession.last_seen_at > now - IDLE))
    if row is None or _principal_for_active_session(session, row) is None:
        raise SessionRefusal()
    return row


def browser_principal(token: str):
    with SessionLocal() as session:
        begin_reservation(session, scope=LIFECYCLE_LOCK)
        row = _active_browser(session, token)
        principal = _principal_for_active_session(session, row)
        session.get(BrowserSession, row.session_id).last_seen_at = _now()
        session.commit()
        return principal


def csrf_value(token: str) -> str:
    return hmac.new(token.encode('ascii'), b'strategy-os/browser-csrf/v1', hashlib.sha256).hexdigest()


def cookie_token(request) -> str | None:
    # Do not use Request.cookies: that parser silently chooses one duplicate.
    values = []
    for header in request.headers.getlist('cookie'):
        for part in header.split(';'):
            name, sep, value = part.strip().partition('=')
            if name == COOKIE:
                if not sep or not TOKEN_PATTERN.fullmatch(value):
                    raise AuthRefusal()
                values.append(value)
    if len(values) > 1:
        raise AuthRefusal()
    if values and (request.headers.getlist('authorization') or request.headers.getlist('x-pt-token')):
        raise AuthRefusal()
    return values[0] if values else None


def check_origin(request, *, mutation: bool):
    origin = request.headers.getlist('origin')
    if request.url.scheme != 'https' or request.url.netloc != urlsplit(get_settings().browser_auth_origin).netloc:
        raise AuthRefusal(403)
    expected = get_settings().browser_auth_origin
    if origin and origin != [expected]:
        raise AuthRefusal(403)
    if mutation and origin != [expected]:
        raise AuthRefusal(403)
    fetch_site = request.headers.getlist('sec-fetch-site')
    if fetch_site and fetch_site not in [['same-origin'], ['none']]:
        raise AuthRefusal(403)


def check_csrf(request, token: str):
    check_origin(request, mutation=True)
    values = request.headers.getlist(CSRF_HEADER)
    if len(values) != 1 or re.fullmatch(r'[0-9a-f]{64}', values[0]) is None or not secrets.compare_digest(values[0], csrf_value(token)):
        raise AuthRefusal(403)


def bootstrap(token: str) -> dict:
    with SessionLocal() as session:
        row = _active_browser(session, token)
        user = session.get(User, row.user_id)
        memberships = session.execute(select(Membership, Organization).join(Organization).where(
            Membership.user_id == row.user_id, Membership.status == 'active',
            Organization.status == 'active').order_by(Membership.organization_id)).all()
        return {'user': {'id': user.user_id, 'display_name': user.display_name},
                'organization_id': row.organization_id,
                'memberships': [{'organization_id': m.organization_id, 'name': o.name, 'role': m.role}
                                for m, o in memberships],
                'expires_at': row.expires_at.isoformat() + 'Z', 'csrf': csrf_value(token)}


def enroll(email: str, password: str, display_name: str, invitation: str, replaced: str | None = None):
    if (not isinstance(display_name, str) or not 1 <= len(display_name.strip()) <= 128
            or not isinstance(invitation, str) or not TOKEN_PATTERN.fullmatch(invitation)):
        raise AuthRefusal()
    try:
        display_name.encode('utf-8')
    except UnicodeError:
        raise AuthRefusal() from None
    verifier = hash_password(password)
    with SessionLocal() as session:
        begin_reservation(session, scope=LIFECYCLE_LOCK)
        now = _now()
        used = session.execute(update(EnrollmentInvite).where(
            EnrollmentInvite.invite_digest == token_digest(invitation),
            EnrollmentInvite.email_normalized == email, EnrollmentInvite.purpose == 'enrollment',
            EnrollmentInvite.consumed_at.is_(None), EnrollmentInvite.expires_at > now).values(consumed_at=now))
        if used.rowcount != 1 or session.scalar(select(User.user_id).where(User.email_normalized == email)):
            raise AuthRefusal()
        user_id, org_id = str(uuid4()), str(uuid4())
        session.add(User(user_id=user_id, email_normalized=email, display_name=display_name.strip()))
        session.add(Organization(organization_id=org_id, name=f'{display_name.strip()} workspace'[:128]))
        session.flush()
        session.add(Membership(user_id=user_id, organization_id=org_id, role='owner', status='active'))
        session.add(BrowserCredential(user_id=user_id, verifier=verifier, updated_at=now))
        session.flush()
        if replaced:
            old = _active_browser(session, replaced)
            _revoke(session, old.user_id, session_id=old.session_id)
        issued = _issue(session, user_id, org_id)
        session.commit()
        return issued


def login(email: str, password: str, replaced: str | None = None):
    with SessionLocal() as session:
        candidate = session.execute(select(User.user_id, BrowserCredential.verifier).join(BrowserCredential).where(
            User.email_normalized == email, User.status == 'active', User.user_id != LEGACY_USER_ID)).first()
    if not verify_password(password, candidate.verifier if candidate else None) or candidate is None:
        raise AuthRefusal()
    with SessionLocal() as session:
        begin_reservation(session, scope=LIFECYCLE_LOCK)
        credential = session.get(BrowserCredential, candidate.user_id)
        if credential is None or credential.verifier != candidate.verifier:
            raise AuthRefusal()
        membership = session.scalar(select(Membership).join(Organization).join(User).where(
            Membership.user_id == candidate.user_id, Membership.status == 'active',
            Organization.status == 'active', User.status == 'active').order_by(Membership.organization_id))
        if membership is None:
            raise AuthRefusal()
        if replaced:
            old = _active_browser(session, replaced)
            _revoke(session, old.user_id, session_id=old.session_id)
        issued = _issue(session, candidate.user_id, membership.organization_id)
        session.commit()
        return issued


def mutate_session(token: str, action: str, *, password: str | None = None,
                   new_password: str | None = None, organization_id: str | None = None):
    old_verifier = None
    new_verifier = None
    if action in {'password', 'logout-all'}:
        with SessionLocal() as session:
            row = _active_browser(session, token)
            credential = session.get(BrowserCredential, row.user_id)
            old_verifier = credential.verifier if credential else None
        if not verify_password(password, old_verifier):
            raise ActionRefusal()
        if action == 'password':
            try:
                new_verifier = hash_password(new_password)
            except AuthRefusal:
                raise ActionRefusal() from None
    with SessionLocal() as session:
        begin_reservation(session, scope=LIFECYCLE_LOCK)
        row = _active_browser(session, token)
        issued = None
        if action in {'password', 'logout-all'}:
            credential = session.get(BrowserCredential, row.user_id)
            if credential is None or credential.verifier != old_verifier:
                raise AuthRefusal()
            _revoke(session, row.user_id)
            if action == 'password':
                credential.verifier = new_verifier
                credential.updated_at = _now()
                issued = _issue(session, row.user_id, row.organization_id)
        elif action == 'organization':
            if _active_membership(session, user_id=row.user_id, organization_id=organization_id) is None:
                raise AuthRefusal(403)
            _revoke(session, row.user_id, session_id=row.session_id)
            issued = _issue(session, row.user_id, organization_id)
        elif action == 'logout':
            _revoke(session, row.user_id, session_id=row.session_id)
        else:
            raise AuthRefusal(404)
        session.commit()
        return issued
