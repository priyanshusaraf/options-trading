"""Real V0 watchlist access, immutable revisions, ownership and capability refusals."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core import release_profile
from app.db.models import Membership, StaticInstrumentScope
from app.db.session import SessionLocal
from app.market_truth.identity import CanonicalPhysicalInstrument, persist_canonical_instrument
from tests.test_cross_tenant_idor import _seed_http_principals, _headers


def test_exact_route_set_and_metadata_are_mirrored_once():
    from app.api.product_object_routes import router
    from app.api.static_scope_routes import require_static_scopes
    from app.api.versioning import build_versioned_router
    from app.api.principal import action_for_request
    originals = [r for r in router.routes if '/static-scopes' in getattr(r, 'path', '')]
    mirrors = [r for r in build_versioned_router(router).routes if '/static-scopes' in r.path]
    assert len(originals) == len(mirrors) == 6
    assert len({(r.path, tuple(r.methods)) for r in originals}) == 6
    for original, mirror in zip(originals, mirrors):
        assert mirror.path == original.path.replace('/api/', '/api/v1/', 1)
        assert mirror.endpoint is original.endpoint
        assert mirror.status_code == original.status_code
        assert mirror.response_model == original.response_model
        assert mirror.dependencies == original.dependencies
        assert any(d.dependency is require_static_scopes for d in mirror.dependencies)
        for fragment in ('review', 'graphs', 'experiments', 'layouts', 'status', 'findings'):
            path = original.path.replace('{project_id}', 'project.test').replace(
                '{scope_id}', 'scope.' + fragment).replace('{revision}', '1')
            for method in original.methods:
                assert action_for_request(method, path) == (
                    'read:project' if method == 'GET' else 'write:project')


@pytest.fixture
def http(monkeypatch):
    from app.main import app
    issued = _seed_http_principals(monkeypatch)
    monkeypatch.setattr(get_settings(), 'release_profile', 'v0_research_signal')
    client = TestClient(app)
    projects = {user: client.post('/api/ir/projects', headers=_headers(issued, user),
                json={'name': 'Research'}).json()['project_id'] for user in ('user.a', 'user.b')}
    instrument = CanonicalPhysicalInstrument('test', 'http', 'NSE', 'EQUITY', 'SPOT', 'INR', None)
    with SessionLocal.begin() as s:
        persist_canonical_instrument(s, instrument)
    return client, issued, projects, instrument.address


@pytest.fixture
def test_only_enabled_capability(monkeypatch):
    # Also prove the fully enabled canonical enum remains supported.
    original = release_profile.manifest
    def enabled(*args, **kwargs):
        manifest = dict(original(*args, **kwargs))
        manifest['capabilities'] = dict(manifest['capabilities'])
        manifest['capabilities']['static_watchlists'] = {
            'state': release_profile.CapabilityState.ENABLED.value,
        }
        return manifest
    monkeypatch.setattr(release_profile, 'manifest', enabled)


@pytest.mark.parametrize('state', [
    release_profile.CapabilityState.BLOCKED.value,
    'enabled',
    'UNKNOWN',
    None,
])
def test_non_enabled_capability_states_refuse_before_writes(http, monkeypatch, state):
    client, issued, projects, member = http
    original = release_profile.manifest

    def manifest(*args, **kwargs):
        value = dict(original(*args, **kwargs))
        value['capabilities'] = dict(value['capabilities'])
        if state is None:
            value['capabilities'].pop('static_watchlists', None)
        else:
            value['capabilities']['static_watchlists'] = {'state': state}
        return value

    monkeypatch.setattr(release_profile, 'manifest', manifest)
    base = f'/api/ir/projects/{projects["user.a"]}/static-scopes'
    response = client.post(base, headers=_headers(issued, 'user.a'),
                           json={'name': 'Research', 'members': [member]})
    assert response.status_code == 403
    assert response.json()['detail'] == {
        'code': 'V0_CAPABILITY_UNAVAILABLE',
        'capability': 'static_watchlists',
        'state': 'blocked',
        'reason': 'Static scope capability has not been accepted',
    }
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(StaticInstrumentScope)) == 0


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
@pytest.mark.parametrize('shape', [
    'null_manifest',
    'string_manifest',
    'missing_capabilities',
    'null_capabilities',
    'string_capabilities',
    'missing_state',
    'null_capability',
    'string_capability',
    'list_capability',
])
def test_malformed_capability_containers_refuse_before_writes(
        http, monkeypatch, prefix, shape):
    client, issued, projects, member = http
    original = release_profile.manifest

    def malformed(*args, **kwargs):
        if shape == 'null_manifest':
            return None
        if shape == 'string_manifest':
            return 'manifest'
        value = dict(original(*args, **kwargs))
        if shape == 'missing_capabilities':
            value.pop('capabilities', None)
            return value
        if shape == 'null_capabilities':
            value['capabilities'] = None
            return value
        if shape == 'string_capabilities':
            value['capabilities'] = 'capabilities'
            return value
        value['capabilities'] = dict(value['capabilities'])
        value['capabilities']['static_watchlists'] = {
            'missing_state': {},
            'null_capability': None,
            'string_capability': 'enabled',
            'list_capability': [release_profile.CapabilityState.ENABLED.value],
        }[shape]
        return value

    monkeypatch.setattr(release_profile, 'manifest', malformed)
    base = f'{prefix}/ir/projects/{projects["user.a"]}/static-scopes'
    response = client.post(base, headers=_headers(issued, 'user.a'),
                           json={'name': 'Research', 'members': [member]})
    assert response.status_code == 403
    assert response.json()['detail'] == {
        'code': 'V0_CAPABILITY_UNAVAILABLE',
        'capability': 'static_watchlists',
        'state': 'blocked',
        'reason': 'Static scope capability has not been accepted',
    }
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(StaticInstrumentScope)) == 0


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_standard_profile_refuses_all_static_scope_endpoints(http, monkeypatch, prefix):
    client, issued, projects, member = http
    monkeypatch.setattr(get_settings(), 'release_profile', 'standard')
    base = f'{prefix}/ir/projects/{projects["user.a"]}/static-scopes'
    for method, suffix, body in [('GET', '', None), ('POST', '', {'name': 'x', 'members': [member]}),
        ('GET', '/scope.main', None), ('GET', '/scope.main/revisions/1', None),
        ('POST', '/scope.main/revisions', {'name': 'x', 'members': [member], 'expected_revision': 1}),
        ('POST', '/scope.main/archive', {'expected_revision': 1})]:
        r = client.request(method, base + suffix, headers=_headers(issued, 'user.a'), json=body)
        assert r.status_code == 403
        assert r.json()['detail']['capability'] == 'static_watchlists'
    assert client.get(base).status_code == 401


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_actual_v0_owner_cas_and_readback(http, prefix):
    client, issued, projects, member = http
    base = f'{prefix}/ir/projects/{projects["user.a"]}/static-scopes'
    headers = _headers(issued, 'user.a')
    body = {'scope_id': 'scope.main', 'name': 'Research', 'members': [member]}
    first = client.post(base, headers=headers, json=body)
    assert first.status_code == 201, first.text
    assert client.post(base, headers=headers, json=body).json() == first.json()
    foreign = client.get(base + '/scope.main', headers=_headers(issued, 'user.b'))
    assert foreign.status_code == 404
    assert foreign.json()['detail']['code'] == 'STATIC_SCOPE_NOT_FOUND'
    assert client.get(base, headers=_headers(issued, 'user.b')).status_code == 404
    absent = client.get(base + '/scope.missing', headers=headers)
    assert absent.status_code == 404 and absent.json() == foreign.json()
    assert client.get(base + '/scope.main', headers=_headers(issued, 'viewer.a')).status_code == 200
    update = {'name': 'Renamed', 'members': [member], 'expected_revision': 1}
    assert client.post(base + '/scope.main/revisions', headers=_headers(issued, 'viewer.a'), json=update).status_code == 403
    with SessionLocal.begin() as s:
        membership = s.scalar(select(Membership).where(Membership.user_id == 'viewer.a'))
        membership.role = 'member'
    second = client.post(base + '/scope.main/revisions', headers=_headers(issued, 'viewer.a'), json=update)
    assert second.status_code == 201, second.text
    assert second.json()['membership_address'] == first.json()['membership_address']
    assert second.json()['address'] != first.json()['address']
    conflict = client.post(base + '/scope.main/revisions', headers=headers, json=update)
    assert conflict.status_code == 409 and conflict.json()['detail']['code'] == 'STATIC_SCOPE_CONFLICT'
    assert client.get(base + '/scope.main/revisions/1', headers=headers).json()['address'] == first.json()['address']
    assert client.post(base + '/scope.main/archive', headers=headers, json={'expected_revision': 1}).status_code == 409
    assert client.post(base + '/scope.main/archive', headers=headers, json={'expected_revision': 2}).status_code == 200
    assert client.get(base, headers=headers).json()['items'] == []
    assert len(client.get(base + '?include_archived=true', headers=headers).json()['items']) == 1


def test_synthetic_enabled_bounds_and_execution_fields(http, test_only_enabled_capability):
    client, issued, projects, member = http
    base = f'/api/ir/projects/{projects["user.a"]}/static-scopes'
    headers = _headers(issued, 'user.a')
    for identifier in ('review', 'graphs', 'status', 'a/b', '..'):
        assert client.post(base, headers=headers, json={'scope_id': identifier,
            'name': 'x', 'members': [member]}).status_code == 422
    for extra in ['owner_id', 'broker_account', 'strategy_key', 'deployment', 'capital', 'ARM', 'provider_symbol']:
        assert client.post(base, headers=headers, json={'name': 'x', 'members': [member], extra: 'x'}).status_code == 422
    for name, members in [('', [member]), ('x'*129, [member]), (' ', [member]), ('x', []),
                          ('x', [member]*33), ('x', ['NSE:INFY']), ('x', [member]*2)]:
        assert client.post(base, headers=headers, json={'name': name, 'members': members}).status_code == 422
    for query in ['limit=-1', 'limit=0', 'limit=51', 'after=', 'after='+'x'*65]:
        assert client.get(base + '?' + query, headers=headers).status_code == 422
    invalid = client.post(base, headers=headers, json={'name': 'Repeated', 'members': [member, member]})
    assert invalid.status_code == 422 and invalid.json()['detail']['code'] == 'STATIC_SCOPE_INVALID'
