"""Pure event normalization, filtering and cursor pagination for daily review."""
from __future__ import annotations

import base64
import datetime as dt
import json
from collections.abc import Iterable, Mapping
from typing import Any

from app.ir.hashing import canonical_json, content_address


EVENT_TYPES = frozenset({
    "graph_version_published",
    "experiment_run",
    "finding_created",
    "candidate_created",
    "candidate_decided",
})
EVENT_STATUSES = frozenset({
    "published", "pending", "running", "failed", "completed", "needs_review",
    "active", "superseded", "created", "shadow", "approved", "rejected",
})
MAX_CURSOR_BYTES = 1024
MAX_SUMMARY = 400
_EVENT_FIELDS = {
    "event_id", "type", "occurred_at", "status", "summary", "references"
}
_REFERENCE_FIELDS = {"graph", "run_id", "finding_id", "candidate_id"}
_GRAPH_FIELDS = {"identifier", "version", "content_address"}


class ReviewQueryRejected(Exception):
    pass


def _timestamp(value: dt.datetime | str) -> str:
    try:
        parsed = value if isinstance(value, dt.datetime) else dt.datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ReviewQueryRejected("review timestamp is invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    parsed = parsed.astimezone(dt.UTC)
    return parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _references(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _REFERENCE_FIELDS:
        raise ReviewQueryRejected("review event references are invalid")
    result = dict(value)
    graph = result["graph"]
    if graph is not None:
        if not isinstance(graph, Mapping) or set(graph) != _GRAPH_FIELDS:
            raise ReviewQueryRejected("review graph reference is invalid")
        if (
            not isinstance(graph["identifier"], str) or not graph["identifier"]
            or len(graph["identifier"]) > 128
            or not isinstance(graph["version"], int)
            or isinstance(graph["version"], bool) or graph["version"] < 1
            or not isinstance(graph["content_address"], str)
            or not graph["content_address"].startswith("sha256:")
            or len(graph["content_address"]) != 71
        ):
            raise ReviewQueryRejected("review graph reference is invalid")
        result["graph"] = dict(graph)
    for key in ("run_id", "finding_id", "candidate_id"):
        item = result[key]
        if item is not None and (
            not isinstance(item, int) or isinstance(item, bool) or item < 1
        ):
            raise ReviewQueryRejected(f"review {key} reference is invalid")
    return result


def make_review_event(
    *,
    event_id: str,
    event_type: str,
    occurred_at: dt.datetime | str,
    status: str,
    summary: str,
    references: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        not isinstance(event_id, str) or not event_id or len(event_id) > 200
        or event_type not in EVENT_TYPES
        or status not in EVENT_STATUSES
        or not isinstance(summary, str) or not summary or len(summary) > MAX_SUMMARY
    ):
        raise ReviewQueryRejected("review event fields are invalid")
    return {
        "event_id": event_id,
        "type": event_type,
        "occurred_at": _timestamp(occurred_at),
        "status": status,
        "summary": summary,
        "references": _references(references),
    }


def encode_review_cursor(occurred_at: dt.datetime | str, event_id: str) -> str:
    if not isinstance(event_id, str) or not event_id or len(event_id) > 200:
        raise ReviewQueryRejected("review cursor event id is invalid")
    position = {"occurred_at": _timestamp(occurred_at), "event_id": event_id}
    raw = canonical_json({
        "content_address": content_address(position),
        "position": position,
    }).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_review_cursor(token: str) -> dict[str, str]:
    if not isinstance(token, str) or not token or len(token) > MAX_CURSOR_BYTES:
        raise ReviewQueryRejected("review cursor is missing or exceeds the size limit")
    try:
        padding = "=" * (-len(token) % 4)
        raw = base64.b64decode(
            token + padding, altchars=b"-_", validate=True
        ).decode("utf-8")
        envelope = json.loads(raw)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ReviewQueryRejected("review cursor is invalid") from exc
    if not isinstance(envelope, dict) or set(envelope) != {"content_address", "position"}:
        raise ReviewQueryRejected("review cursor envelope is invalid")
    position = envelope["position"]
    if (
        not isinstance(position, dict)
        or set(position) != {"occurred_at", "event_id"}
        or not isinstance(position["event_id"], str)
        or not position["event_id"]
        or len(position["event_id"]) > 200
    ):
        raise ReviewQueryRejected("review cursor position is invalid")
    normalized = {
        "occurred_at": _timestamp(position["occurred_at"]),
        "event_id": position["event_id"],
    }
    if (
        position != normalized
        or envelope["content_address"] != content_address(position)
        or encode_review_cursor(**normalized) != token
    ):
        raise ReviewQueryRejected("review cursor integrity verification failed")
    return normalized


def _validated_event(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _EVENT_FIELDS:
        raise ReviewQueryRejected("review event shape is invalid")
    return make_review_event(
        event_id=value["event_id"],
        event_type=value["type"],
        occurred_at=value["occurred_at"],
        status=value["status"],
        summary=value["summary"],
        references=value["references"],
    )


def paginate_review_events(
    events: Iterable[Mapping[str, Any]],
    *,
    limit: int,
    cursor: str | None = None,
    event_types: set[str] | frozenset[str] | None = None,
    statuses: set[str] | frozenset[str] | None = None,
    after: dt.datetime | str | None = None,
    before: dt.datetime | str | None = None,
) -> dict[str, Any]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ReviewQueryRejected("review page limit must be between 1 and 100")
    selected_types = EVENT_TYPES if event_types is None else frozenset(event_types)
    selected_statuses = EVENT_STATUSES if statuses is None else frozenset(statuses)
    if not selected_types <= EVENT_TYPES or not selected_statuses <= EVENT_STATUSES:
        raise ReviewQueryRejected("review filter contains an unsupported value")
    after_value = _timestamp(after) if after is not None else None
    before_value = _timestamp(before) if before is not None else None
    if after_value and before_value and after_value >= before_value:
        raise ReviewQueryRejected("review date range is invalid")
    cursor_position = decode_review_cursor(cursor) if cursor is not None else None
    cursor_key = (
        (cursor_position["occurred_at"], cursor_position["event_id"])
        if cursor_position else None
    )

    filtered = []
    for raw_event in events:
        event = _validated_event(raw_event)
        key = (event["occurred_at"], event["event_id"])
        if event["type"] not in selected_types or event["status"] not in selected_statuses:
            continue
        if after_value is not None and event["occurred_at"] <= after_value:
            continue
        if before_value is not None and event["occurred_at"] >= before_value:
            continue
        if cursor_key is not None and key >= cursor_key:
            continue
        filtered.append(event)
    filtered.sort(key=lambda event: (event["occurred_at"], event["event_id"]), reverse=True)
    page = filtered[:limit]
    next_cursor = None
    if len(filtered) > limit and page:
        last = page[-1]
        next_cursor = encode_review_cursor(last["occurred_at"], last["event_id"])
    return {"events": page, "next_cursor": next_cursor}


def normalize_review_filters(value: Mapping[str, Any]) -> dict[str, Any]:
    """Canonical persisted subset of the transient review query contract."""
    fields = {"event_type", "status", "after", "before", "limit"}
    if not isinstance(value, Mapping) or not set(value) <= fields:
        raise ReviewQueryRejected("saved review filters contain unsupported fields")
    event_type = value.get("event_type")
    status = value.get("status")
    limit = value.get("limit", 25)
    if event_type is not None and event_type not in EVENT_TYPES:
        raise ReviewQueryRejected("saved review event type is unsupported")
    if status is not None and status not in EVENT_STATUSES:
        raise ReviewQueryRejected("saved review status is unsupported")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ReviewQueryRejected("saved review limit must be between 1 and 100")
    after = _timestamp(value["after"]) if value.get("after") is not None else None
    before = _timestamp(value["before"]) if value.get("before") is not None else None
    if after is not None and before is not None and after >= before:
        raise ReviewQueryRejected("saved review date range is invalid")
    return {
        "after": after,
        "before": before,
        "event_type": event_type,
        "limit": limit,
        "status": status,
    }


__all__ = [
    "EVENT_STATUSES", "EVENT_TYPES", "ReviewQueryRejected", "decode_review_cursor",
    "encode_review_cursor", "make_review_event", "normalize_review_filters",
    "paginate_review_events",
]
