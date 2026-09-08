"""Retain the exact canonical output needed to finish a cross-plane publication.

The execution commit contains these bytes and all referenced source facts. A
later request can restore the same research rows without calling the provider
again or pretending that a later response is the original acquisition.
"""
from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import Text, case, cast, func, select

from app.backtest.dataset_store import DatasetManifest, DatasetSegment, verify_dataset_manifest
from app.db.models import AuthorityRawSegment
from app.ir.hashing import canonical_json
from app.market_data.kite_historical_attribution import _instant
from app.market_data.observations import RawObservationSegment, load_raw_segment, persist_raw_segment
from research.data.canonical_dataset import decode_observation_index
from research.data.historical_capture import PURPOSE, _require

SCHEMA = "strategy-os-history-publication/1"
_FIELDS = {"schema", "owner_id", "project_id", "request", "manifest", "segments"}


def _request_time(value):
    _require(type(value) is dt.datetime and value.tzinfo is not None and value.utcoffset() is not None)
    return _instant(value.astimezone(dt.timezone.utc), whole=True)


def _request(selection_address, start, end):
    start, end = map(_request_time, (start, end))
    _require(start <= end)
    return {"selection_address": selection_address, "start": start.isoformat(), "end": end.isoformat()}


def _artifact(manifest, schema, payload):
    _require(len(manifest.provider_product_addresses) == len(manifest.provider_contract_addresses) == 1)
    return RawObservationSegment(manifest.owner_id, manifest.provider_product_addresses[0],
        manifest.provider_contract_addresses[0], "application/json", schema, payload,
        dt.datetime.fromisoformat(manifest.recorded_at))


def retain_history_publication(session, result, *, project_id, selection_address, start, end):
    """Store exact manifest, segment metadata and index bytes before the authority commit."""
    manifest = result.manifest
    _require(manifest.purpose == PURPOSE + project_id)
    request = _request(selection_address, start, end)
    _publication_request(session, manifest, request)
    segments = []
    for segment, payload in zip(result.segments, result.object_bytes, strict=True):
        index = _artifact(manifest, decode_observation_index(payload)["schema"], payload)
        persist_raw_segment(session, index)
        segments.append({"segment": segment.fact(), "index_address": index.address})
    document = {"schema": SCHEMA, "owner_id": manifest.owner_id, "project_id": project_id,
        "request": request, "manifest": manifest.fact(), "segments": segments}
    saved = _artifact(manifest, SCHEMA, canonical_json(document).encode())
    persist_raw_segment(session, saved)
    return saved.address


def _json_fragment(key, value):
    return canonical_json({key: value})[1:-1]


def _payload_text(session, is_publication):
    # SQLite casts BLOB bytes to text; PostgreSQL's bytea text cast instead
    # produces hex. Decode UTF-8 explicitly there before the bounded lookup.
    payload = case((is_publication, AuthorityRawSegment.raw_bytes), else_=b"")
    if session.get_bind().dialect.name == "postgresql":
        return func.convert_from(payload, "UTF8")
    return cast(payload, Text)


def _candidate_addresses(session, owner_id, request):
    is_publication = (AuthorityRawSegment.schema == RawObservationSegment.SCHEMA) & \
        AuthorityRawSegment.canonical_json.contains(_json_fragment("raw_schema", SCHEMA), autoescape=True)
    payload = _payload_text(session, is_publication)
    statement = select(AuthorityRawSegment.address).where(
        AuthorityRawSegment.owner_id == owner_id,
        is_publication,
        *(payload.contains(_json_fragment(key, value), autoescape=True) for key, value in request.items()),
    ).order_by(AuthorityRawSegment.address).limit(2)
    return session.scalars(statement).all()


def _publication_document(raw, owner_id, request):
    _require((raw.owner_id, raw.raw_schema, raw.media_type) == (owner_id, SCHEMA, "application/json"))
    document = json.loads(raw.payload)
    _require(type(document) is dict and set(document) == _FIELDS
        and canonical_json(document).encode() == raw.payload)
    _require(document["schema"] == SCHEMA and document["owner_id"] == owner_id
        and document["request"] == request)
    manifest = DatasetManifest(**document["manifest"])
    _require(manifest.owner_id == owner_id and manifest.purpose == PURPOSE + document["project_id"]
        and manifest.provider_product_addresses == (raw.product_address,)
        and manifest.provider_contract_addresses == (raw.contract_address,)
        and manifest.recorded_at == raw.recorded_at.isoformat())
    return document, manifest


def _publication_request(session, manifest, request):
    from app.market_data.dataset_authority import load_normalization_transform
    from research.data.provider_history_bundle import PRODUCER
    _require(len(manifest.normalization_transform_addresses) == 1)
    transform = load_normalization_transform(session, manifest.normalization_transform_addresses[0])
    parameters = dict(transform.parameters)
    _require(transform.owner_id == manifest.owner_id and parameters.get("kind") == PRODUCER)
    _require((parameters["selection_address"], parameters["requested_start"], parameters["requested_end"])
        == (request["selection_address"], request["start"], request["end"]))


def _publication_segments(session, document, manifest):
    rows = document["segments"]
    _require(type(rows) is list and 0 < len(rows) <= 8)
    segments = {}
    for row in rows:
        _require(type(row) is dict and set(row) == {"segment", "index_address"})
        segment = DatasetSegment(**row["segment"])
        raw = load_raw_segment(session, row["index_address"])
        _require((raw.owner_id, raw.product_address, raw.contract_address, raw.media_type)
            == (manifest.owner_id, manifest.provider_product_addresses[0],
                manifest.provider_contract_addresses[0], "application/json"))
        _require(raw.raw_schema == decode_observation_index(raw.payload)["schema"]
            and raw.recorded_at.isoformat() == manifest.recorded_at
            and segment.segment_address not in segments)
        segments[segment.segment_address] = (segment, raw.payload)
    verify_dataset_manifest(manifest, segments)
    return segments


def find_history_publication(session, *, owner_id, selection_address, start, end):
    """Find one exact owned acquisition; ambiguous vintages are never selected silently.

    The returned bytes still undergo the canonical authority and row checks
    when they are published or reused in the research plane.
    """
    request = _request(selection_address, start, end)
    addresses = _candidate_addresses(session, owner_id, request)
    _require(len(addresses) <= 1, "HISTORICAL_PUBLICATION_AMBIGUOUS",
        "Several saved captures match this range. Choose the intended saved dataset before continuing.")
    if not addresses:
        return None
    document, manifest = _publication_document(load_raw_segment(session, addresses[0]), owner_id, request)
    _publication_request(session, manifest, request)
    return manifest, _publication_segments(session, document, manifest)
