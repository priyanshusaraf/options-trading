"""Shell graph index: real principals, bounded canonical metadata, no side effects."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.release_profile import manifest
from app.db.models import GraphArtifact, Membership, Project
from app.db.session import SessionLocal
from tests.test_cross_tenant_idor import _seed_http_principals, _headers
from tests.test_product_object_routes import _graph


@pytest.fixture
def setup(monkeypatch):
    from app.main import app
    issued = _seed_http_principals(monkeypatch)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    client = TestClient(app)  # No runner lifespan needed for the read contract.
    projects = {}
    for user in ("user.a", "user.b"):
        response = client.post('/api/v1/ir/projects', headers=_headers(issued, user),
                               json={"name": "Same name", "description": "Owner-scoped"})
        assert response.status_code == 201
        projects[user] = response.json()['project_id']
    return client, issued, projects


def seed_graphs(project_id, owner_id, identifiers):
    with SessionLocal.begin() as session:
        session.add_all(GraphArtifact(owner_id=owner_id, project_id=project_id,
            identifier=identifier, display_name=f"Graph {identifier}", draft_revision=0,
            draft_json='{"private":"must not leave the index"}') for identifier in identifiers)


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
@pytest.mark.parametrize('profile', ['v0_research_signal', 'standard'])
def test_index_is_owner_scoped_in_both_profiles_and_mounts(setup, monkeypatch, prefix, profile):
    client, issued, projects = setup
    monkeypatch.setattr(get_settings(), 'release_profile', profile)
    seed_graphs(projects['user.a'], 'org.a', ['same.graph'])
    seed_graphs(projects['user.b'], 'org.b', ['same.graph', 'private.b'])
    for user, other in [('user.a', 'user.b'), ('user.b', 'user.a')]:
        headers = _headers(issued, user)
        visible = client.get(f'{prefix}/ir/projects', headers=headers).json()
        assert [p['project_id'] for p in visible] == [projects[user]]
        path = f'{prefix}/ir/projects/{projects[user]}/graphs'
        result = client.get(path, headers=headers)
        assert result.status_code == 200
        assert result.json() == {
            'schema': 'strategy-os-graph-index/1', 'project_id': projects[user],
            'items': [{'identifier': key, 'display_name': f'Graph {key}',
                       'draft_revision': 0, 'current_version': None}
                      for key in (['same.graph'] if user == 'user.a' else ['private.b', 'same.graph'])],
            'next_cursor': None,
        }
        for target in [projects[other], 'missing']:
            denied = client.get(f'{prefix}/ir/projects/{target}/graphs?owner_id=org.b&limit=1', headers=headers)
            assert denied.status_code == 404
            assert denied.json() == {'detail': 'project not found'}
        assert client.get(path).status_code == 401
    viewer = client.get(f'{prefix}/ir/projects/{projects["user.a"]}/graphs', headers=_headers(issued, 'viewer.a'))
    assert viewer.status_code == 200


def test_bounded_keyset_index_does_not_duplicate_or_disclose_other_projects(setup):
    client, issued, projects = setup
    keys = [f'strategy.{i:03}' for i in range(105)]
    seed_graphs(projects['user.a'], 'org.a', reversed(keys))
    seed_graphs(projects['user.b'], 'org.b', ['strategy.050-other-owner'])
    headers = _headers(issued, 'user.a')
    extra = client.post('/api/ir/projects', headers=headers, json={'name': 'Other project'}).json()['project_id']
    seed_graphs(extra, 'org.a', ['strategy.050-other-project'])
    base = f'/api/v1/ir/projects/{projects["user.a"]}/graphs'
    first = client.get(base, headers=headers).json()
    assert len(first['items']) == 50 and first['next_cursor'] == keys[49]
    page = client.get(base, params={'limit': 100}, headers=headers).json()
    tail = client.get(base, params={'limit': 100, 'after': page['next_cursor']}, headers=headers).json()
    assert [row['identifier'] for row in page['items'] + tail['items']] == keys
    assert tail['next_cursor'] is None
    assert client.get(base, params={'after': keys[-1]}, headers=headers).json()['items'] == []
    for params in [{'limit': 0}, {'limit': -1}, {'limit': 101}, {'limit': 'bad'}, {'after': ''}, {'after': 'x' * 129}]:
        assert client.get(base, params=params, headers=headers).status_code == 422


def test_empty_archived_revoked_and_downgraded_access(setup):
    client, issued, projects = setup
    path = f'/api/v1/ir/projects/{projects["user.a"]}/graphs'
    headers = _headers(issued, 'user.a')
    assert client.get(path, headers=headers).json()['items'] == []
    with SessionLocal.begin() as session:
        membership = session.scalar(select(Membership).where(Membership.user_id == 'user.a'))
        membership.role = 'viewer'
    assert client.get(path, headers=headers).status_code == 200
    with SessionLocal.begin() as session:
        membership = session.scalar(select(Membership).where(Membership.user_id == 'user.a'))
        membership.status = 'revoked'
    assert client.get(path, headers=headers).status_code == 401
    viewer_headers = _headers(issued, 'viewer.a')
    with SessionLocal.begin() as session:
        session.get(Project, projects['user.a']).status = 'archived'
    assert client.get(path, headers=viewer_headers).status_code == 404
    assert client.get('/api/v1/ir/projects', headers=viewer_headers).json() == []


def test_index_projects_real_draft_and_published_metadata_without_writing(setup):
    client, issued, projects = setup
    headers = _headers(issued, 'user.a')
    base = f'/api/v1/ir/projects/{projects["user.a"]}/graphs'
    assert client.post(base, headers=headers, json={'identifier': 'strategy.desk', 'graph': _graph()}).status_code == 201
    draft = client.get(base, headers=headers).json()['items'][0]
    assert draft == {'identifier': 'strategy.desk', 'display_name': 'Desk graph', 'draft_revision': 0, 'current_version': None}
    assert client.post(f'{base}/strategy.desk/versions', headers=headers, json={'base_revision': 0}).status_code == 201
    def snapshot():
        with SessionLocal() as session:
            return [dict(row) for row in session.execute(select(GraphArtifact.__table__)).mappings()]
    before = snapshot()
    assert client.get(base, headers=headers).json()['items'][0]['current_version'] == 1
    assert snapshot() == before


def test_frontend_manifest_contract_fixture_is_current_server_truth():
    # Cross-repository consumer fixture. Never part of the production import graph.
    path = Path('/Users/priyanshusaraf/dev/strategy-os-frontend/src/test/releaseManifest.json')
    assert json.loads(path.read_text()) == jsonable_encoder(manifest('v0_research_signal', research_enabled=True))
