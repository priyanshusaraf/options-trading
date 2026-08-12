"""Pure bounded search over verified project review text."""
from __future__ import annotations

import base64
import datetime as dt
import json
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

from app.core.research_review import ReviewQueryRejected, make_review_event
from app.ir.hashing import canonical_json, content_address


MAX_SEARCH_EVENTS = 2_000
MAX_SEARCH_NOTES = 2_000
MAX_SEARCH_CURSOR_BYTES = 2_048
_EVENT_FIELDS = {
    "event_id", "type", "occurred_at", "status", "summary", "references",
}
_NOTE_FIELDS = {
    "note_id", "event_id", "event_type", "body", "created_by", "anchor_state",
    "updated_at",
}
_REFERENCE_KEYS = ("run_id", "finding_id", "candidate_id")


class ReviewSearchRejected(Exception):
    pass


def normalize_search_query(value: str) -> str:
    if not isinstance(value, str):
        raise ReviewSearchRejected("review search query must be text")
    if any(unicodedata.category(character).startswith("C") for character in value):
        raise ReviewSearchRejected("review search query contains a control character")
    normalized = " ".join(
        unicodedata.normalize("NFKC", value).casefold().split()
    )
    if not 2 <= len(normalized) <= 120:
        raise ReviewSearchRejected(
            "review search query must contain 2 to 120 normalized characters"
        )
    return normalized


def _timestamp(value: str) -> tuple[str, int]:
    if not isinstance(value, str):
        raise ReviewSearchRejected("review search document timestamp is invalid")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewSearchRejected("review search document timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ReviewSearchRejected("review search document timestamp is invalid")
    parsed = parsed.astimezone(dt.UTC)
    canonical = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if value != canonical:
        raise ReviewSearchRejected("review search document timestamp is not canonical")
    epoch = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)
    elapsed = parsed - epoch
    micros = elapsed.days * 86_400_000_000 + elapsed.seconds * 1_000_000 + elapsed.microseconds
    return canonical, micros


def _event_document(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != _EVENT_FIELDS:
        raise ReviewSearchRejected("review search event source is invalid")
    try:
        event = make_review_event(
            event_id=raw["event_id"],
            event_type=raw["type"],
            occurred_at=raw["occurred_at"],
            status=raw["status"],
            summary=raw["summary"],
            references=raw["references"],
        )
    except ReviewQueryRejected as exc:
        raise ReviewSearchRejected("review search event source is invalid") from exc
    timestamp, micros = _timestamp(event["occurred_at"])
    return {
        "result_id": f"event:{event['event_id']}",
        "kind": "event",
        "event_id": event["event_id"],
        "event_type": event["type"],
        "text": event["summary"],
        "timestamp": timestamp,
        "timestamp_micros": micros,
        "anchor_state": "available",
        "reference": {key: event["references"][key] for key in _REFERENCE_KEYS},
    }


def _note_document(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != _NOTE_FIELDS:
        raise ReviewSearchRejected("review search note source is invalid")
    if (
        not isinstance(raw["note_id"], str) or not raw["note_id"]
        or not isinstance(raw["event_id"], str) or not raw["event_id"]
        or not isinstance(raw["event_type"], str) or not raw["event_type"]
        or not isinstance(raw["body"], str) or not raw["body"].strip()
        or len(raw["body"]) > 4_000
        or not isinstance(raw["created_by"], str) or not raw["created_by"]
        or len(raw["created_by"]) > 64
        or raw["anchor_state"] not in {"available", "missing"}
    ):
        raise ReviewSearchRejected("review search note source is invalid")
    timestamp, micros = _timestamp(raw["updated_at"])
    return {
        "result_id": f"note:{raw['note_id']}",
        "kind": "note",
        "event_id": raw["event_id"],
        "event_type": raw["event_type"],
        "text": raw["body"],
        "timestamp": timestamp,
        "timestamp_micros": micros,
        "anchor_state": raw["anchor_state"],
        "reference": {key: None for key in _REFERENCE_KEYS},
    }


def _rank(document: Mapping[str, Any], offset: int) -> tuple[int, int, int, str]:
    return (
        offset,
        -document["timestamp_micros"],
        0 if document["kind"] == "event" else 1,
        document["result_id"],
    )


def _encode_cursor(query: str, document: Mapping[str, Any], offset: int) -> str:
    position = {
        "kind": document["kind"],
        "match_offset": offset,
        "result_id": document["result_id"],
        "timestamp": document["timestamp"],
    }
    payload = {
        "position": position,
        "query_address": content_address({"query": query}),
    }
    envelope = {"content_address": content_address(payload), **payload}
    return base64.urlsafe_b64encode(canonical_json(envelope).encode()).decode().rstrip("=")


def _decode_cursor(token: str, query: str) -> tuple[int, int, int, str]:
    if not isinstance(token, str) or not token or len(token) > MAX_SEARCH_CURSOR_BYTES:
        raise ReviewSearchRejected("review search cursor is missing or exceeds the size limit")
    try:
        padding = "=" * (-len(token) % 4)
        raw = base64.b64decode(token + padding, altchars=b"-_", validate=True).decode()
        envelope = json.loads(raw)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ReviewSearchRejected("review search cursor is invalid") from exc
    if not isinstance(envelope, dict) or set(envelope) != {
        "content_address", "position", "query_address",
    }:
        raise ReviewSearchRejected("review search cursor envelope is invalid")
    canonical_token = base64.urlsafe_b64encode(canonical_json(envelope).encode()).decode().rstrip("=")
    if raw != canonical_json(envelope) or token != canonical_token:
        raise ReviewSearchRejected("review search cursor is not canonical")
    payload = {key: envelope[key] for key in ("position", "query_address")}
    if envelope["content_address"] != content_address(payload):
        raise ReviewSearchRejected("review search cursor integrity verification failed")
    if envelope["query_address"] != content_address({"query": query}):
        raise ReviewSearchRejected("review search cursor belongs to another query")
    position = envelope["position"]
    if not isinstance(position, dict) or set(position) != {
        "kind", "match_offset", "result_id", "timestamp",
    } or position["kind"] not in {"event", "note"} or not isinstance(
        position["match_offset"], int
    ) or isinstance(position["match_offset"], bool) or position["match_offset"] < 0 or not isinstance(
        position["result_id"], str
    ) or not position["result_id"]:
        raise ReviewSearchRejected("review search cursor position is invalid")
    timestamp, micros = _timestamp(position["timestamp"])
    if timestamp != position["timestamp"]:
        raise ReviewSearchRejected("review search cursor position is invalid")
    return (
        position["match_offset"], -micros,
        0 if position["kind"] == "event" else 1, position["result_id"],
    )


def search_review_documents(
    events: Iterable[Mapping[str, Any]],
    notes: Iterable[Mapping[str, Any]],
    *,
    query: str,
    limit: int,
    cursor: str | None = None,
) -> dict[str, Any]:
    normalized_query = normalize_search_query(query)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        raise ReviewSearchRejected("review search limit must be between 1 and 50")
    event_values = list(events)
    note_values = list(notes)
    if len(event_values) > MAX_SEARCH_EVENTS:
        raise ReviewSearchRejected("review search event source exceeds the 2000-document limit")
    if len(note_values) > MAX_SEARCH_NOTES:
        raise ReviewSearchRejected("review search note source exceeds the 2000-document limit")

    cursor_rank = _decode_cursor(cursor, normalized_query) if cursor is not None else None
    ranked: list[tuple[tuple[int, int, int, str], dict[str, Any]]] = []
    for raw in event_values:
        document = _event_document(raw)
        offset = normalize_search_query_for_document(document["text"]).find(normalized_query)
        if offset >= 0:
            ranked.append((_rank(document, offset), document))
    for raw in note_values:
        document = _note_document(raw)
        offset = normalize_search_query_for_document(document["text"]).find(normalized_query)
        if offset >= 0:
            ranked.append((_rank(document, offset), document))
    ranked.sort(key=lambda item: item[0])
    if cursor_rank is not None:
        ranked = [item for item in ranked if item[0] > cursor_rank]
    selected = ranked[:limit]
    results = []
    for _, document in selected:
        results.append({
            key: value for key, value in document.items() if key != "timestamp_micros"
        })
    next_cursor = None
    if len(ranked) > limit and selected:
        rank, document = selected[-1]
        next_cursor = _encode_cursor(normalized_query, document, rank[0])
    return {"query": normalized_query, "results": results, "next_cursor": next_cursor}


def normalize_search_query_for_document(value: str) -> str:
    """Normalize trusted bounded corpus text without applying query length rules."""
    if not isinstance(value, str):
        raise ReviewSearchRejected("review search document text is invalid")
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


__all__ = [
    "MAX_SEARCH_EVENTS", "MAX_SEARCH_NOTES", "ReviewSearchRejected",
    "normalize_search_query", "search_review_documents",
]
