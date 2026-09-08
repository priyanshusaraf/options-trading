"""Direct V1 local data-provider onboarding routes.

There is intentionally no unversioned router and no connection identifier in a
request.  The active browser principal selects the only owner-local DATA row.
"""
from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status as http_status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.api.principal import Principal, get_principal, require
from app.core.config import get_settings
from app.core.credential_vault import CredentialVaultUnavailable
from app.core.release_profile import is_v0_profile
from app.db.session import SessionLocal
from app.providers import data_connection_service as service
from app.providers.connection_store import (
    ConnectionNotFound,
    DataConnectionConflict,
    DataConnectionUnavailable,
)
from app.providers.zerodha_data_runtime import (
    ZerodhaDataUnavailable, ZerodhaReauthRequired, ZerodhaTransientError,
)


router = APIRouter(prefix="/api/v1/data-connections", tags=["data-connections"])


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EmptyMutation(_ClosedModel):
    pass


class AppKeys(_ClosedModel):
    api_key: SecretStr = Field(min_length=1, max_length=4096)
    api_secret: SecretStr = Field(min_length=1, max_length=4096)


class InstrumentSearch(_ClosedModel):
    query: str = Field(min_length=2, max_length=64)
    exchange: str = "ALL"
    limit: int = 20


class InstrumentSelection(_ClosedModel):
    token: int = Field(strict=True, gt=0, le=4_294_967_295)
    symbol: str = Field(min_length=1, max_length=64)
    exchange: str = Field(min_length=1, max_length=8)


class ProviderSelection(_ClosedModel):
    reference: dict


@router.post("/instrument-selections")
def save_provider_instrument(
        selection: ProviderSelection, response: Response,
        principal: Principal = Depends(get_principal),
) -> dict:
    from app.providers.provider_instrument_reference import ProviderReferenceInvalid
    _v0_only()
    require(principal, "create:connection")
    _no_store(response)
    try:
        return service.select_provider_instrument(SessionLocal, principal, reference=selection.reference)
    except ProviderReferenceInvalid:
        raise HTTPException(status_code=422, detail={
            "code": "INVALID_PROVIDER_REFERENCE",
            "message": "The instrument details are incomplete. Search again and select a result.",
        }) from None
    except service.InstrumentSelectionUnavailable:
        raise HTTPException(status_code=409, detail={
            "code": "INSTRUMENT_SELECTION_UNAVAILABLE",
            "message": "The provider instrument changed or is no longer available. Search again and select the current result.",
        }) from None
    except (ConnectionNotFound, DataConnectionUnavailable,
            CredentialVaultUnavailable, ZerodhaDataUnavailable) as exc:
        _raise_search_error(exc)


@router.post("/instruments/resolve")
def resolve_provider_instrument(
        selection: InstrumentSelection, response: Response,
        principal: Principal = Depends(get_principal),
) -> dict:
    _v0_only()
    require(principal, "create:connection")
    _no_store(response)
    try:
        return service.resolve_instrument(SessionLocal, principal, **selection.model_dump())
    except service.InstrumentSelectionUnavailable:
        raise HTTPException(status_code=409, detail={
            "code": "INSTRUMENT_SELECTION_UNAVAILABLE",
            "message": "This selection could not be verified. Search again and select Nifty 50 or Infosys (INFY) on NSE; other instrument definitions are not supported yet.",
        }) from None
    except (ConnectionNotFound, DataConnectionUnavailable,
            CredentialVaultUnavailable, ZerodhaDataUnavailable) as exc:
        _raise_search_error(exc)


def _raise_search_error(exc: Exception) -> None:
    failures = (
        (service.InvalidInstrumentSearch, 422, "INVALID_INSTRUMENT_SEARCH",
         "Enter 2–64 search characters, choose an available exchange or All, and request 1–50 results."),
        (ZerodhaReauthRequired, 409, "DATA_REAUTH_REQUIRED",
         "Reconnect your data provider, then search again."),
        (ZerodhaTransientError, 503, "DATA_PROVIDER_BUSY",
         "The data provider is temporarily unavailable. Wait a moment and retry."),
        (CredentialVaultUnavailable, 503, "DATA_VAULT_UNAVAILABLE",
         "Data connection credentials are unavailable. Retry when the service recovers."),
        (ZerodhaDataUnavailable, 502, "INSTRUMENT_SEARCH_UNAVAILABLE",
         "The provider returned no usable instrument list. Reconnect or retry the search."),
    )
    for exception_type, status, code, message in failures:
        if isinstance(exc, exception_type):
            raise HTTPException(status_code=status, detail={"code": code, "message": message}) from None
    raise HTTPException(status_code=409, detail={
        "code": "DATA_CONNECTION_UNAVAILABLE",
        "message": "An active owner data connection is required. Check the connection and sign in again.",
    }) from None


@router.get("/instruments")
def search_provider_instruments(
        search: Annotated[InstrumentSearch, Query()], response: Response,
        principal: Principal = Depends(get_principal),
) -> dict:
    _v0_only()
    require(principal, "read:connections")
    _no_store(response)
    try:
        return service.search_instruments(SessionLocal, principal, **search.model_dump())
    except (service.InvalidInstrumentSearch, ConnectionNotFound, DataConnectionUnavailable,
            CredentialVaultUnavailable, ZerodhaDataUnavailable) as exc:
        _raise_search_error(exc)


def _v0_only() -> None:
    if not is_v0_profile(get_settings().release_profile):
        raise HTTPException(status_code=409, detail="data onboarding is unavailable")


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _raise_closed(exc: Exception) -> None:
    if isinstance(exc, CredentialVaultUnavailable):
        raise HTTPException(status_code=503, detail="credential vault unavailable") from exc
    if isinstance(exc, ConnectionNotFound):
        raise HTTPException(status_code=404, detail="data connection unavailable") from exc
    if isinstance(exc, DataConnectionConflict):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=409, detail="data connection unavailable") from exc


@router.get("/status")
def data_connection_status(
        response: Response, principal: Principal = Depends(get_principal),
) -> dict:
    _v0_only()
    require(principal, "read:connections")
    _no_store(response)
    with SessionLocal() as session:
        return service.status(session, principal)


@router.post("", status_code=http_status.HTTP_201_CREATED)
def create_data_connection(
        _body: EmptyMutation, response: Response,
        principal: Principal = Depends(get_principal),
) -> dict:
    _v0_only()
    require(principal, "create:connection")
    _no_store(response)
    with SessionLocal() as session:
        try:
            service.create(session, principal)
            session.commit()
            return service.status(session, principal)
        except (ConnectionNotFound, DataConnectionConflict,
                DataConnectionUnavailable, CredentialVaultUnavailable) as exc:
            session.rollback()
            _raise_closed(exc)


def _write_keys(
        body: AppKeys, response: Response, principal: Principal, *, rotate: bool,
) -> dict:
    _v0_only()
    require(principal, "write:credential")
    _no_store(response)
    keys = {
        "api_key": body.api_key.get_secret_value(),
        "api_secret": body.api_secret.get_secret_value(),
    }
    with SessionLocal() as session:
        try:
            service.write_app_keys(session, principal, keys, rotate=rotate)
            session.commit()
            return service.status(session, principal)
        except (ConnectionNotFound, DataConnectionConflict,
                DataConnectionUnavailable, CredentialVaultUnavailable) as exc:
            session.rollback()
            _raise_closed(exc)


@router.post("/app-keys")
def store_initial_app_keys(
        body: AppKeys, response: Response,
        principal: Principal = Depends(get_principal),
) -> dict:
    return _write_keys(body, response, principal, rotate=False)


@router.post("/app-keys/rotate")
def rotate_app_keys(
        body: AppKeys, response: Response,
        principal: Principal = Depends(get_principal),
) -> dict:
    return _write_keys(body, response, principal, rotate=True)


@router.post("/oauth/initiate")
def initiate_oauth(
        _body: EmptyMutation, response: Response,
        principal: Principal = Depends(get_principal),
        authenticator=Depends(service.production_data_authenticator),
) -> dict:
    _v0_only()
    require(principal, "write:credential")
    _no_store(response)
    with SessionLocal() as session:
        try:
            login_url = service.initiate(session, principal, authenticator)
            session.commit()
            return {"login_url": login_url}
        except (ConnectionNotFound, DataConnectionConflict,
                DataConnectionUnavailable, CredentialVaultUnavailable) as exc:
            session.rollback()
            _raise_closed(exc)


@router.get("/oauth/callback")
def oauth_callback(
        state: str | None = None, request_token: str | None = None,
        authenticator=Depends(service.production_data_authenticator),
):
    _v0_only()
    if not service.complete(
            SessionLocal, raw_state=state, request_token=request_token,
            authenticator=authenticator):
        raise HTTPException(status_code=400, detail="invalid data login callback")
    response = RedirectResponse(url="/account/provider", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.delete("")
def revoke_data_connection(
        response: Response, principal: Principal = Depends(get_principal),
) -> dict:
    _v0_only()
    require(principal, "revoke:connection")
    _no_store(response)
    with SessionLocal() as session:
        try:
            service.revoke(session, principal)
            session.commit()
            return service.status(session, principal)
        except (ConnectionNotFound, DataConnectionConflict,
                DataConnectionUnavailable, CredentialVaultUnavailable) as exc:
            session.rollback()
            _raise_closed(exc)


__all__ = ["router"]
