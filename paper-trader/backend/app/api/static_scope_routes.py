"""Static research scope API; disabled until the server capability is accepted."""
from collections.abc import Mapping
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.principal import Principal, get_principal, owner_id_for
from app.core import release_profile, static_scopes as store
from app.core.config import get_settings
from app.db.session import SessionLocal


def require_static_scopes():
    settings = get_settings()
    manifest = release_profile.manifest(
        settings.release_profile,
        research_enabled=settings.research_enabled,
    )
    capabilities = manifest.get('capabilities') if isinstance(manifest, Mapping) else None
    capability = (
        capabilities.get('static_watchlists')
        if isinstance(capabilities, Mapping)
        else None
    )
    if not isinstance(capability, Mapping) or (
            capability.get('state') not in {release_profile.CapabilityState.ENABLED.value,
                                           release_profile.CapabilityState.ENABLED_WITH_LIMIT.value}):
        reason = capability.get('reason') if isinstance(capability, Mapping) else None
        if not isinstance(reason, str) or not reason:
            reason = 'Static scope capability has not been accepted'
        raise HTTPException(403, detail={'code': 'V0_CAPABILITY_UNAVAILABLE',
            'capability': 'static_watchlists', 'state': 'blocked',
            'reason': reason})


Identifier = Annotated[str, Path(min_length=1, max_length=64)]


class CanonicalMember(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    kind: Literal['CANONICAL']
    instrument_address: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')


class ProviderMember(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    kind: Literal['PROVIDER_REFERENCE']
    selection_address: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')


TypedMember = Annotated[CanonicalMember | ProviderMember, Field(discriminator='kind')]


class ScopeWrite(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name: str = Field(min_length=1, max_length=128)
    members: list[str] | list[TypedMember] = Field(min_length=1, max_length=32)


class ScopeCreate(ScopeWrite):
    scope_id: str | None = Field(default=None, min_length=1, max_length=64)


class ScopeRevision(ScopeWrite):
    expected_revision: int = Field(ge=1)


class ScopeArchive(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    expected_revision: int = Field(ge=1)


def _call(operation, principal, project_id, **kwargs):
    try:
        with SessionLocal.begin() as session:
            return operation(session, owner_id=owner_id_for(principal), project_id=project_id, **kwargs)
    except store.ScopeNotFound as exc:
        raise HTTPException(404, detail={'code': 'STATIC_SCOPE_NOT_FOUND',
                                        'message': 'Watchlist or project not found.'}) from exc
    except store.ScopeConflict as exc:
        raise HTTPException(409, detail={'code': 'STATIC_SCOPE_CONFLICT',
                                        'message': 'This watchlist changed, was archived, or its name is already in use. Reload it before saving.'}) from exc
    except store.ScopeInvalid as exc:
        raise HTTPException(422, detail={'code': 'STATIC_SCOPE_INVALID',
                                        'message': str(exc)}) from exc


def create_scope(project_id: Identifier, body: ScopeCreate, principal: Principal = Depends(get_principal)):
    return _call(store.create_scope, principal, project_id, **body.model_dump())


def list_scopes(project_id: Identifier, principal: Principal = Depends(get_principal),
                limit: int = Query(50, ge=1, le=50), after: str | None = Query(None, min_length=1, max_length=64),
                include_archived: bool = False):
    return _call(store.list_scopes, principal, project_id, limit=limit, after=after,
                 include_archived=include_archived)


def get_scope(project_id: Identifier, scope_id: Identifier, principal: Principal = Depends(get_principal)):
    return _call(store.get_scope, principal, project_id, scope_id=scope_id)


def get_revision(project_id: Identifier, scope_id: Identifier, revision: int = Path(ge=1),
                 principal: Principal = Depends(get_principal)):
    return _call(store.get_scope, principal, project_id, scope_id=scope_id, revision=revision)


def revise_scope(project_id: Identifier, scope_id: Identifier, body: ScopeRevision,
                 principal: Principal = Depends(get_principal)):
    return _call(store.revise_scope, principal, project_id, scope_id=scope_id, **body.model_dump())


def archive_scope(project_id: Identifier, scope_id: Identifier, body: ScopeArchive,
                  principal: Principal = Depends(get_principal)):
    return _call(store.archive_scope, principal, project_id, scope_id=scope_id, **body.model_dump())


def install_routes(target: APIRouter) -> None:
    """Materialize only these six routes for the existing direct-route v1 mirror.

    FastAPI's lazy include wrapper is not consumed by the existing versioning
    adapter. Keep one endpoint set and use its public registration seam instead.
    """
    base = '/projects/{project_id}/static-scopes'
    for suffix, endpoint, method, code in (
        ('', create_scope, 'POST', 201),
        ('', list_scopes, 'GET', 200),
        ('/{scope_id}', get_scope, 'GET', 200),
        ('/{scope_id}/revisions/{revision}', get_revision, 'GET', 200),
        ('/{scope_id}/revisions', revise_scope, 'POST', 201),
        ('/{scope_id}/archive', archive_scope, 'POST', 200),
    ):
        target.add_api_route(base + suffix, endpoint, methods=[method], status_code=code,
                             dependencies=[Depends(require_static_scopes)],
                             name='static_scope_' + endpoint.__name__)
