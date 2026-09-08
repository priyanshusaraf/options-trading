"""Invited-user authentication guards with synthetic secrets and isolated databases."""
import importlib
import importlib.util
import datetime as dt
import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update, func

ORIGIN = 'https://testserver'
PASSWORD = 'a synthetic sufficiently long password'


@pytest.fixture
def browser(monkeypatch):
    from app.core.config import get_settings
    from app.db.session import init_db
    settings = get_settings()
    for name, value in {'browser_auth_enabled': True, 'browser_auth_origin': ORIGIN,
                        'browser_auth_counter_secret': 'a1' * 32, 'auth_disabled': False,
                        'api_token': '', 'release_profile': 'v0_research_signal',
                        'release_service_role': 'api'}.items():
        monkeypatch.setattr(settings, name, value)
    init_db(reset=True)
    from app.main import app
    with _no_lifespan(app) as client:
        yield client


from contextlib import contextmanager


@contextmanager
def _no_lifespan(app):
    client = TestClient(app, base_url=ORIGIN)
    try:
        yield client
    finally:
        client.close()


def post(client, action, data, csrf=None, **kwargs):
    headers = {'Origin': ORIGIN}
    if csrf:
        headers['x-strategy-csrf'] = csrf
    headers.update(kwargs.pop('headers', {}))
    return client.post('/api/v1/auth/' + action, json=data, headers=headers, **kwargs)


def enroll_client(client, email='alice@example.test'):
    auth = auth_module()
    invite = auth.create_invite(email)
    response = post(client, 'enroll', {'email': email, 'password': PASSWORD,
                                     'display_name': 'Synthetic Alice', 'invitation': invite.token})
    assert response.status_code == 200, response.text
    assert response.json() == {'ok': True}
    state = client.get('/api/v1/auth/session')
    assert state.status_code == 200, state.text
    return state.json(), response


def auth_module():
    assert importlib.util.find_spec('app.accounts') is not None, 'Q01 browser auth missing'
    assert importlib.util.find_spec('app.accounts.browser_auth') is not None, 'Q01 browser auth missing'
    return importlib.import_module('app.accounts.browser_auth')


@pytest.mark.parametrize('key,value', [
    ('max_daily_loss', 6000), ('max_open_drawdown', 3000), ('max_daily_profit', 1000),
])
def test_v0_owner_saves_account_limits_without_an_execution_cell(browser, monkeypatch, key, value):
    from app.api import routes
    from app.core import runtime_config
    state, _ = enroll_client(browser)
    monkeypatch.setattr(routes, '_runner', lambda *_: pytest.fail('account settings requested an execution cell'))
    response = browser.post('/api/v1/account-risk-settings', json={'key': key, 'value': value},
        headers={'Origin': ORIGIN, 'X-Strategy-CSRF': state['csrf']})
    assert response.status_code == 200, response.text
    assert 'error' not in response.json()
    owner = state['organization_id']
    assert float(runtime_config.get_overrides(owner_id=owner)[key]) == value
    assert runtime_config.get_overrides(owner_id='unrelated-owner') == {}
    rows = browser.get('/api/v1/account-risk-settings').json()['params']
    assert {row['key'] for row in rows} == {'max_daily_loss', 'max_open_drawdown', 'max_daily_profit'}
    saved = next(row for row in rows if row['key'] == key)
    assert saved['value'] == value and saved['overridden'] is True


def test_v0_account_limit_write_keeps_role_and_execution_gates(browser):
    from app.core import runtime_config
    from app.db.models import Membership
    from app.db.session import SessionLocal
    state, _ = enroll_client(browser)
    headers = {'Origin': ORIGIN, 'X-Strategy-CSRF': state['csrf']}
    refused = browser.post('/api/v1/settings', json={'key': 'intraday_max_positions', 'value': 4}, headers=headers)
    assert refused.status_code == 409
    assert refused.json()['code'] == 'V0_CAPABILITY_UNAVAILABLE'
    unsupported = browser.post('/api/v1/account-risk-settings', json={'key': 'intraday_max_positions', 'value': 4}, headers=headers)
    assert unsupported.status_code == 422
    assert runtime_config.get_overrides(owner_id=state['organization_id']) == {}
    with SessionLocal() as session:
        session.execute(update(Membership).where(Membership.user_id == state['user']['id']).values(role='viewer'))
        session.commit()
    forbidden = browser.post('/api/v1/account-risk-settings', json={'key': 'max_daily_loss', 'value': 6000}, headers=headers)
    assert forbidden.status_code == 403
    assert runtime_config.get_overrides(owner_id=state['organization_id']) == {}


@pytest.mark.parametrize('value', [True, -1, 100_000_001, '6000', 'Infinity'])
def test_account_entry_limit_rejects_invalid_numeric_input(browser, value):
    from app.core import runtime_config
    state, _ = enroll_client(browser)
    response = browser.post('/api/v1/account-risk-settings', json={'key': 'max_daily_loss', 'value': value},
        headers={'Origin': ORIGIN, 'X-Strategy-CSRF': state['csrf']})
    assert response.status_code == 422
    assert runtime_config.get_overrides(owner_id=state['organization_id']) == {}


def test_password_profile_and_random_salts():
    auth = auth_module()
    password = 'a synthetic sufficiently long password'
    first, second = auth.hash_password(password), auth.hash_password(password)
    assert first != second
    assert auth.verify_password(password, first)
    assert not auth.verify_password('another sufficiently long password', first)
    assert password not in repr(first)


def test_password_policy_preserves_unicode_and_whitespace():
    auth = auth_module()
    password = '  a unicode passphrase \u00e9  '
    encoded = auth.hash_password(password)
    assert auth.verify_password(password, encoded)
    assert not auth.verify_password(password.strip(), encoded)


def test_rfc9106_vector_and_fixed_profile_preallocation(monkeypatch):
    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
    auth = auth_module()
    assert Argon2id(salt=b'\2'*16, length=32, iterations=3, lanes=4, memory_cost=32,
                    secret=b'\3'*8, ad=b'\4'*12).derive(b'\1'*32).hex() == (
        '0d640df58d78766c08c037a34a8b53c9d01ef0452d75b65eb52520e96b01e659')
    salts = []
    original = auth.kdf
    def spy(salt):
        salts.append(salt)
        return original(salt)
    monkeypatch.setattr(auth, 'kdf', spy)
    auth.hash_password(PASSWORD)
    auth.hash_password(PASSWORD)
    assert len(salts[0]) == len(salts[1]) == 16 and salts[0] != salts[1]
    assert not auth.verify_password(PASSWORD, '$argon2id$v=19$m=999999999,t=999999,p=99$bad')
    assert salts[-1] == b'\0' * 16


@pytest.mark.parametrize('password', ['short', 'x'*129, '123456789012345', '\ud800'*15])
def test_invalid_password_refused(password):
    with pytest.raises(auth_module().AuthRefusal):
        auth_module().hash_password(password)


def test_malformed_unicode_and_csrf_refuse_without_exceptions(monkeypatch):
    from fastapi import Request
    from app.core.config import get_settings
    auth = auth_module()
    monkeypatch.setattr(get_settings(), 'browser_auth_origin', ORIGIN)
    request = Request({'type': 'http', 'scheme': 'https', 'method': 'POST', 'path': '/',
                       'server': ('testserver', 443), 'headers': [(b'origin', ORIGIN.encode()),
                       (b'x-strategy-csrf', b'\xe9'*64)]})
    with pytest.raises(auth.AuthRefusal) as refused:
        auth.check_csrf(request, secrets.token_urlsafe(32))
    assert refused.value.status == 403
    with pytest.raises(auth.AuthRefusal):
        auth.normalize_email('\ud800@example.test')


def test_enroll_bootstrap_cookie_and_own_project(browser):
    auth = auth_module()
    state, response = enroll_client(browser)
    cookie = response.headers['set-cookie']
    for attribute in ['Secure', 'HttpOnly', 'Path=/', 'SameSite=lax', 'Max-Age=43200']:
        assert attribute in cookie
    assert 'Domain=' not in cookie
    assert response.headers['cache-control'] == 'no-store'
    token = browser.cookies.get(auth.COOKIE)
    assert token not in response.text and token not in str(state)
    assert state['memberships'][0]['role'] == 'owner'
    response = browser.get('/api/v1/ir/projects')
    assert response.status_code == 200, response.text
    assert browser.get('/api/auth/session?normal=query').status_code == 200
    assert browser.get('/api/v1/auth/session%3Fnot-query').status_code == 403


def test_csrf_origin_and_duplicate_credentials_fail_closed(browser):
    auth = auth_module()
    state, _ = enroll_client(browser)
    token = browser.cookies.get(auth.COOKIE)
    assert post(browser, 'logout', {}).status_code == 403
    assert post(browser, 'logout', {}, 'bad').status_code == 403
    assert post(browser, 'logout', {}, state['csrf'], headers={'Origin': 'https://evil.test'}).status_code == 403
    assert browser.get('/api/v1/auth/session', headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    assert browser.get('/api/v1/auth/session', headers={'Cookie': f'{auth.COOKIE}={token}; {auth.COOKIE}={token}'}).status_code == 401
    browser.cookies.set(auth.COOKIE, token, domain='testserver.local', path='/')
    assert browser.get('/api/v1/ir/projects', headers={'X-PT-Token': token}).status_code == 401
    browser.cookies.clear()
    assert browser.get('/api/v1/ir/projects', headers={'Authorization': f'Bearer {token}'}).status_code == 401


def test_login_password_rotation_logout_all_and_replay(browser):
    auth = auth_module()
    state, _ = enroll_client(browser)
    first = browser.cookies.get(auth.COOKIE)
    assert post(browser, 'logout', {}, state['csrf']).status_code == 200
    assert browser.get('/api/v1/auth/session').status_code == 401
    assert post(browser, 'login', {'email': 'alice@example.test', 'password': PASSWORD}).status_code == 200
    second = browser.cookies.get(auth.COOKIE)
    assert second != first
    state = browser.get('/api/v1/auth/session').json()
    new_password = 'another synthetic sufficiently long password'
    assert post(browser, 'password', {'password': PASSWORD, 'new_password': new_password}, state['csrf']).status_code == 200
    third = browser.cookies.get(auth.COOKIE)
    assert third not in {first, second}
    with pytest.raises(auth.AuthRefusal):
        auth.browser_principal(second)
    assert post(browser, 'logout-all', {'password': new_password}, browser.get('/api/v1/auth/session').json()['csrf']).status_code == 200
    for old in [first, second, third]:
        with pytest.raises(auth.AuthRefusal):
            auth.browser_principal(old)
    assert post(browser, 'login', {'email': 'alice@example.test', 'password': PASSWORD}).status_code == 401
    assert post(browser, 'login', {'email': 'alice@example.test', 'password': new_password}).status_code == 200


def test_membership_revocation_and_idle_expiry(browser):
    from app.db.session import SessionLocal
    from app.db.models import Membership, BrowserSession
    auth = auth_module()
    state, _ = enroll_client(browser)
    token = browser.cookies.get(auth.COOKIE)
    with SessionLocal() as s:
        s.execute(update(Membership).where(Membership.user_id == state['user']['id']).values(status='revoked'))
        s.commit()
    assert browser.get('/api/v1/ir/projects').status_code == 401
    response = browser.get('/api/v1/release-profile', headers={'Cookie': f'{auth.COOKIE}={token}'})
    assert response.status_code == 200
    assert 'Max-Age=0' in response.headers['set-cookie']
    with SessionLocal() as s:
        s.execute(update(Membership).where(Membership.user_id == state['user']['id']).values(status='active'))
        s.execute(update(BrowserSession).values(last_seen_at=auth._now()-dt.timedelta(minutes=31)))
        s.commit()
    with pytest.raises(auth.AuthRefusal):
        auth.browser_principal(token)


def test_invite_replay_concurrent_consume_and_existing_account(browser):
    from app.db.session import SessionLocal
    from app.db.models import User, Organization, EnrollmentInvite
    auth = auth_module()
    invite = auth.create_invite('race@example.test')
    def attempt(_):
        try:
            auth.enroll('race@example.test', PASSWORD, 'Race', invite.token)
            return True
        except auth.AuthRefusal:
            return False
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [False, True]
    with pytest.raises(auth.AuthRefusal):
        auth.create_invite('race@example.test')
    with SessionLocal() as s:
        assert s.scalar(select(func.count()).select_from(User).where(User.email_normalized == 'race@example.test')) == 1
        assert s.get(EnrollmentInvite, auth.token_digest(invite.token)).consumed_at is not None


def test_bounds_admission_and_unknown_user_profile(browser, monkeypatch):
    auth = auth_module()
    calls = []
    real = auth.kdf
    def spy(salt):
        calls.append(salt)
        return real(salt)
    monkeypatch.setattr(auth, 'kdf', spy)
    assert post(browser, 'login', {'email': 'nobody@example.test', 'password': PASSWORD}).status_code == 401
    assert len(calls) == 1
    assert post(browser, 'login', {'email': 'nobody@example.test', 'password': 'x'*9000}).status_code == 413
    assert len(calls) == 1
    auth.AUTH_SLOTS.acquire(); auth.AUTH_SLOTS.acquire()
    try:
        assert post(browser, 'login', {'email': 'nobody@example.test', 'password': PASSWORD}).status_code == 503
    finally:
        auth.AUTH_SLOTS.release(); auth.AUTH_SLOTS.release()
    for _ in range(9):
        auth.admit_attempt('nobody@example.test', 'testclient')
    with pytest.raises(auth.AuthRefusal) as refusal:
        auth.admit_attempt('nobody@example.test', 'testclient')
    assert refusal.value.status == 429


def test_two_tenants_and_active_membership_switch(browser):
    from app.main import app
    from app.db.session import SessionLocal
    from app.db.models import Membership
    from app.editor import graph_artifacts
    auth = auth_module()
    alice, _ = enroll_client(browser)
    with _no_lifespan(app) as bob:
        bob_state, _ = enroll_client(bob, 'bob@example.test')
        project = graph_artifacts.create_project('Alice only', '', owner_id=alice['organization_id'])
        assert browser.get(f'/api/v1/ir/projects/{project.project_id}/graphs').status_code == 200
        assert bob.get(f'/api/v1/ir/projects/{project.project_id}/graphs').status_code == 404
        assert post(bob, 'organization', {'organization_id': alice['organization_id']}, bob_state['csrf']).status_code == 403
        with SessionLocal() as s:
            s.add(Membership(user_id=alice['user']['id'], organization_id=bob_state['organization_id'], role='viewer', status='active'))
            s.commit()
        old = browser.cookies.get(auth.COOKIE)
        response = post(browser, 'organization', {'organization_id': bob_state['organization_id']}, alice['csrf'])
        assert response.status_code == 200, response.text
        changed = browser.get('/api/v1/auth/session').json()
        assert changed['organization_id'] == bob_state['organization_id']
        assert browser.get(f'/api/v1/ir/projects/{project.project_id}/graphs').status_code == 404
        with pytest.raises(auth.AuthRefusal):
            auth.browser_principal(old)


def test_cookie_expiry_account_state_and_legacy_refusal(browser, monkeypatch):
    from app.db.session import SessionLocal
    from app.db.models import User, Organization, UserSession
    from app.api.principal import bootstrap_legacy_session
    auth = auth_module()
    state, _ = enroll_client(browser)
    token = browser.cookies.get(auth.COOKIE)
    for model, predicate in [(User, User.user_id == state['user']['id']),
                             (Organization, Organization.organization_id == state['organization_id'])]:
        with SessionLocal() as s:
            s.execute(update(model).where(predicate).values(status='disabled')); s.commit()
        with pytest.raises(auth.AuthRefusal):
            auth.browser_principal(token)
        with SessionLocal() as s:
            s.execute(update(model).where(predicate).values(status='active')); s.commit()
    with SessionLocal() as s:
        s.execute(update(UserSession).values(expires_at=auth._now()-dt.timedelta(seconds=1)))
        s.commit()
    with pytest.raises(auth.AuthRefusal):
        auth.browser_principal(token)
    browser.cookies.clear()
    legacy = secrets.token_urlsafe(32)
    with SessionLocal() as s:
        bootstrap_legacy_session(s, legacy); s.commit()
    response = browser.get('/api/v1/ir/projects', headers={'Cookie': f'{auth.COOKIE}={legacy}'})
    assert response.status_code == 401


def test_enrollment_refusals_never_create_identity(browser):
    from app.db.session import SessionLocal
    from app.db.models import EnrollmentInvite, User
    auth = auth_module()
    invite = auth.create_invite('expired@example.test')
    with SessionLocal() as s:
        s.execute(update(EnrollmentInvite).values(created_at=auth._now()-dt.timedelta(hours=2), expires_at=auth._now()-dt.timedelta(hours=1)))
        s.commit()
    payload = {'email': 'expired@example.test', 'password': PASSWORD, 'display_name': 'Expired', 'invitation': invite.token}
    assert post(browser, 'enroll', payload).status_code == 401
    assert post(browser, 'enroll', {**payload, 'owner_id': 'owner'}).status_code == 400
    with SessionLocal() as s:
        assert s.scalar(select(User).where(User.email_normalized == payload['email'])) is None


def test_configuration_and_method_exemptions_fail_closed(browser, monkeypatch):
    from app.core.config import get_settings
    for field, bad in [('auth_disabled', True), ('browser_auth_origin', 'http://testserver'),
                       ('browser_auth_origin', 'https://testserver/path'), ('release_profile', 'standard'),
                       ('release_service_role', 'research_worker'), ('browser_auth_counter_secret', '')]:
        with monkeypatch.context() as patch:
            patch.setattr(get_settings(), field, bad)
            assert post(browser, 'login', {'email': 'nobody@example.test', 'password': PASSWORD}).status_code == 503
    assert browser.get('/api/v1/auth/login').status_code == 401
    assert browser.post('/api/v1/auth/login%3Ffake', json={}).status_code == 401
    assert post(browser, 'login', {'email': 'nobody@example.test', 'password': PASSWORD}, headers={'Origin': 'https://evil.test'}).status_code == 403


def test_root_path_and_redaction(browser, caplog):
    from app.main import app
    auth = auth_module()
    state, _ = enroll_client(browser)
    token = browser.cookies.get(auth.COOKIE)
    client = TestClient(app, base_url=ORIGIN, root_path='/mount')
    try:
        response = client.get('/mount/api/v1/auth/session?normal=query', headers={'Cookie': f'{auth.COOKIE}={token}'})
        assert response.status_code == 200, response.text
        assert response.json()['user'] == state['user']
        bad = post(browser, 'login', {'email': 'alice@example.test', 'password': PASSWORD, 'secret-marker': token})
        assert bad.status_code == 403  # cookie mutations require CSRF before JSON handling
        assert token not in bad.text and PASSWORD not in caplog.text and token not in caplog.text
    finally:
        client.close()


def test_unresolved_cookie_does_not_auth_gate_public_non_api_paths(browser):
    auth = auth_module()
    # A missing public path must reach the router's 404, not an auth challenge.
    response = browser.get('/public-file-not-present.js', headers={
        'Cookie': f'{auth.COOKIE}={secrets.token_urlsafe(32)}'})
    assert response.status_code == 404
    assert 'Max-Age=0' in response.headers['set-cookie']


def test_action_refusals_retain_valid_cookie_and_session(browser):
    auth = auth_module()
    state, _ = enroll_client(browser)
    cookie = browser.cookies.get(auth.COOKIE)
    wrong = 'wrong synthetic password phrase'
    response = post(browser, 'logout-all', {'password': wrong}, state['csrf'])
    assert response.status_code == 422
    assert 'set-cookie' not in response.headers
    assert browser.cookies.get(auth.COOKIE) == cookie
    state = browser.get('/api/v1/auth/session').json()
    response = post(browser, 'password', {'password': wrong, 'new_password': 'a valid replacement password phrase'}, state['csrf'])
    assert response.status_code == 422 and 'set-cookie' not in response.headers
    assert browser.cookies.get(auth.COOKIE) == cookie
    assert browser.get('/api/v1/auth/session').status_code == 200


def test_persisted_verifier_repr_and_logs_remain_redacted(browser, caplog):
    from app.db.session import SessionLocal
    from app.db.models import BrowserCredential
    import logging
    enroll_client(browser)
    with SessionLocal() as session:
        loaded = session.scalar(select(BrowserCredential.verifier))
        row = session.execute(select(BrowserCredential.verifier)).first()
        model = session.scalar(select(BrowserCredential))
        assert type(loaded).__name__ == 'PasswordVerifier'
        assert repr(loaded) == '<PasswordVerifier redacted>'
        bound = BrowserCredential.__table__.c.verifier.type.process_bind_param(loaded, None)
        assert repr(bound) == '<PasswordVerifier redacted>'
        assert '<PasswordVerifier redacted>' in repr(row)
        assert 'a2id-v1$' not in repr(row)
        with caplog.at_level(logging.WARNING):
            logging.getLogger('q01.verifier.probe').warning('loaded=%r row=%r model=%r', loaded, row, model)
        assert 'a2id-v1$' not in caplog.text
        assert caplog.text.count('<PasswordVerifier redacted>') >= 2


@pytest.mark.parametrize('method,path,root_path,callback', [
    ('GET', '/api/v1/data-connections/oauth/callback', '', True),
    ('GET', '/api/data-connections/oauth/callback', '', True),
    ('GET', '/mount/api/v1/data-connections/oauth/callback', '/mount', True),
    ('POST', '/api/v1/data-connections/oauth/callback', '', False),
    ('HEAD', '/api/v1/data-connections/oauth/callback', '', False),
    ('GET', '/api/v1/data-connections/oauth/callback/extra', '', False),
    ('GET', '/api/v1/data-connections/status', '', False),
    ('GET', '/api/v1/auth/session', '', False),
    ('GET', '/mountain/api/v1/data-connections/oauth/callback', '/mount', False),
])
def test_cross_site_data_oauth_return_uses_only_state_authority(monkeypatch, method, path, root_path, callback):
    from types import SimpleNamespace
    from starlette.requests import Request
    from app.api import principal
    auth = auth_module()
    settings = SimpleNamespace(browser_auth_enabled=True, browser_auth_origin=ORIGIN)
    monkeypatch.setattr(principal, 'get_settings', lambda: settings)
    monkeypatch.setattr(auth, 'get_settings', lambda: settings)
    monkeypatch.setattr(auth, 'validate_configuration', lambda _settings: True)
    def cookie(_request):
        if callback: pytest.fail('OAuth callback must not derive authority from a browser cookie')
        return 'synthetic-cookie'
    monkeypatch.setattr(auth, 'cookie_token', cookie)
    request = Request({'type': 'http', 'method': method, 'scheme': 'https',
        'path': path, 'root_path': root_path, 'query_string': b'',
        'server': ('testserver', 443), 'headers': [(b'host', b'testserver'), (b'sec-fetch-site', b'cross-site')]})
    if callback:
        assert principal.resolve_http_principal(request) is None
    else:
        with pytest.raises(auth.AuthRefusal) as failure:
            principal.resolve_http_principal(request)
        assert failure.value.status == 403


def test_cross_site_oauth_callback_keeps_one_use_state_and_session_authority(browser, monkeypatch):
    import base64
    from urllib.parse import parse_qs, urlsplit
    from app.main import app
    from app.providers import data_connection_service as service

    monkeypatch.setenv('PT_CREDENTIAL_KEY', base64.b64encode(b's' * 32).decode())
    class OfflineAuth:
        callback_passthrough = 'ZERODHA_REDIRECT_PARAMS'
        calls = 0
        def login_url(self, keys):
            return 'https://kite.zerodha.com/connect/login?api_key=synthetic'
        def exchange(self, keys, request_token):
            assert request_token == 'synthetic-request'
            self.calls += 1
            return {'access_token': 'synthetic-data-token'}
    fake = OfflineAuth()
    app.dependency_overrides[service.production_data_authenticator] = lambda: fake
    try:
        identity, _ = enroll_client(browser, 'oauth-return@example.test')
        headers = {'Origin': ORIGIN, 'x-strategy-csrf': identity['csrf']}
        assert browser.post('/api/v1/data-connections', json={}, headers=headers).status_code == 201
        assert browser.post('/api/v1/data-connections/app-keys', json={
            'api_key': 'synthetic-key', 'api_secret': 'synthetic-secret'}, headers=headers).status_code == 200
        def initiate():
            response = browser.post('/api/v1/data-connections/oauth/initiate', json={}, headers=headers)
            assert response.status_code == 200
            query = parse_qs(urlsplit(response.json()['login_url']).query)
            return parse_qs(query['redirect_params'][0])['state'][0]
        state = initiate()
        path = '/api/v1/data-connections/oauth/callback'
        cross_site = {'Sec-Fetch-Site': 'cross-site'}
        assert browser.get(path, params={'state': 'invalid', 'request_token': 'synthetic-request'},
                           headers=cross_site, follow_redirects=False).status_code == 400
        assert fake.calls == 0
        response = browser.get(path, params={'state': state, 'request_token': 'synthetic-request'},
                               headers=cross_site, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers['location'] == '/account/provider'
        assert fake.calls == 1
        assert browser.get(path, params={'state': state, 'request_token': 'synthetic-request'},
                           headers=cross_site, follow_redirects=False).status_code == 400
        state = initiate()
        assert post(browser, 'logout', {}, csrf=identity['csrf']).status_code == 200
        assert browser.get(path, params={'state': state, 'request_token': 'synthetic-request'},
                           headers=cross_site, follow_redirects=False).status_code == 400
        assert fake.calls == 1
    finally:
        app.dependency_overrides.pop(service.production_data_authenticator, None)
