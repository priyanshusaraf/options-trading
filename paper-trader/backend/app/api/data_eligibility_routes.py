"""Unregistered V0 graph-data eligibility HTTP seam.

The active capsule deliberately does not install this router into ``app.main`` or
the release profile. A later owner-gated integration must supply the server-side,
owner-scoped authority resolver dependency before including it.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.principal import Principal, get_principal, owner_id_for
from app.market_data.eligibility import (
    EligibilityResult,
    PrivateEligibilityUnavailable,
    compile_graph_data_eligibility,
)


router = APIRouter(prefix="/api/ir")


class EligibilityQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    graph_content_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    plan_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    input_binding_context_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    dataset_manifest_addresses: tuple[str, ...] = Field(min_length=1, max_length=32)
    capability_profile_address: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    requested_start: str
    requested_end: str
    as_of: str


AuthorityResolver = Callable[[str, str, int, EligibilityQuery], Mapping[str, Any]]


def private_eligibility_response(_cause: object = None) -> JSONResponse:
    """Use one body/status for missing, foreign, revoked, and malformed lookups."""
    return JSONResponse(status_code=404, content={
        "detail": {"code": "DATA_ELIGIBILITY_UNAVAILABLE",
                   "message": "Graph or data eligibility authority is unavailable"}
    })


def get_authority_resolver() -> AuthorityResolver:
    """Fail closed until a later capsule wires the accepted authority loader."""
    raise HTTPException(status_code=503, detail={
        "code": "DATA_ELIGIBILITY_NOT_REGISTERED",
        "message": "Graph data eligibility has not been activated",
    })


@router.post("/graphs/{graph_identifier}/versions/{graph_version}/data-eligibility",
             name="v0_graph_data_eligibility")
def get_eligibility(graph_identifier: str, graph_version: int, body: EligibilityQuery,
                    principal: Principal = Depends(get_principal),
                    resolver: AuthorityResolver = Depends(get_authority_resolver)):
    owner_id = owner_id_for(principal)
    try:
        facts = resolver(owner_id, graph_identifier, graph_version, body)
        if not isinstance(facts, Mapping):
            raise PrivateEligibilityUnavailable
        result = compile_graph_data_eligibility(**facts)
        if not _query_matches_result(body, graph_identifier, graph_version, result):
            raise PrivateEligibilityUnavailable
    except PrivateEligibilityUnavailable as exc:
        raise HTTPException(status_code=404, detail={
            "code": "DATA_ELIGIBILITY_UNAVAILABLE",
            "message": "Graph or data eligibility authority is unavailable",
        }) from exc
    return eligibility_document(result)


def _query_matches_result(body: EligibilityQuery, graph_identifier: str, graph_version: int,
                          result: EligibilityResult) -> bool:
    try:
        times = tuple(dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.UTC)
                      for value in (body.requested_start, body.requested_end, body.as_of))
    except (TypeError, ValueError):
        return False
    return (
        graph_identifier == result.graph_identifier
        and graph_version == result.graph_version
        and body.graph_content_address == result.graph_content_address
        and body.plan_address == result.plan_address
        and body.input_binding_context_address == result.input_binding_context_address
        and body.dataset_manifest_addresses == result.dataset_manifest_addresses
        and body.capability_profile_address == result.capability_profile_address
        and times == (result.requested_start, result.requested_end, result.as_of)
    )


def eligibility_document(result: EligibilityResult) -> dict[str, Any]:
    return {
        "schema": "graph-data-eligibility-response/1",
        "eligibility_address": result.eligibility_address,
        "graph_identifier": result.graph_identifier, "graph_version": result.graph_version,
        "graph_content_address": result.graph_content_address,
        "plan_address": result.plan_address, "status": result.status,
        "requested_start": result.requested_start.isoformat(),
        "requested_end": result.requested_end.isoformat(), "as_of": result.as_of.isoformat(),
        "refusals": [{"code": item.code.value, "selector": item.selector,
                      "detail": item.detail} for item in result.refusals],
    }


__all__ = ["EligibilityQuery", "eligibility_document", "get_authority_resolver",
           "get_eligibility", "private_eligibility_response", "router"]
