import datetime as dt

import pytest

from app.core.research_review import (
    ReviewQueryRejected,
    decode_review_cursor,
    encode_review_cursor,
    make_review_event,
    paginate_review_events,
)


def _event(index: int, *, kind="experiment_run", status="completed"):
    return make_review_event(
        event_id=f"run:{index}",
        event_type=kind,
        occurred_at=dt.datetime(2026, 8, 3, 10, index, tzinfo=dt.UTC),
        status=status,
        summary=f"Run {index}",
        references={
            "graph": {
                "identifier": "strategy.alpha", "version": index,
                "content_address": f"sha256:{index:064x}",
            },
            "run_id": index,
            "finding_id": None,
            "candidate_id": None,
        },
    )


def test_event_shape_and_cursor_are_closed_canonical_and_tamper_evident():
    event = _event(1)
    assert set(event) == {
        "event_id", "type", "occurred_at", "status", "summary", "references"
    }
    assert event["occurred_at"] == "2026-08-03T10:01:00.000000Z"

    token = encode_review_cursor(event["occurred_at"], event["event_id"])
    assert decode_review_cursor(token) == {
        "occurred_at": event["occurred_at"], "event_id": "run:1"
    }
    with pytest.raises(ReviewQueryRejected, match="cursor"):
        decode_review_cursor(token[:-1] + ("A" if token[-1] != "A" else "B"))
    with pytest.raises(ReviewQueryRejected, match="cursor"):
        decode_review_cursor("x" * 2000)


def test_pagination_is_deterministic_and_stable_when_newer_event_arrives():
    events = [_event(1), _event(3), _event(2)]

    first = paginate_review_events(events, limit=2)

    assert [event["event_id"] for event in first["events"]] == ["run:3", "run:2"]
    assert first["next_cursor"] is not None
    newer = make_review_event(
        **{
            **{k: v for k, v in _event(4).items() if k not in {"type", "occurred_at"}},
            "event_type": "experiment_run",
            "occurred_at": "2026-08-03T11:00:00Z",
        }
    )
    second = paginate_review_events(
        [newer, *events], limit=2, cursor=first["next_cursor"]
    )
    assert [event["event_id"] for event in second["events"]] == ["run:1"]
    assert second["next_cursor"] is None


def test_filters_are_bounded_closed_and_applied_before_cursor():
    events = [
        _event(1, kind="experiment_run", status="failed"),
        _event(2, kind="finding_created", status="active"),
        _event(3, kind="experiment_run", status="completed"),
    ]
    page = paginate_review_events(
        events,
        limit=10,
        event_types={"experiment_run"},
        statuses={"failed"},
        after="2026-08-03T10:00:00Z",
        before="2026-08-03T10:02:00Z",
    )
    assert [event["event_id"] for event in page["events"]] == ["run:1"]

    for kwargs in (
        {"limit": 0},
        {"limit": 101},
        {"limit": 10, "event_types": {"raw_provider_event"}},
        {"limit": 10, "statuses": {"whatever"}},
        {"limit": 10, "after": "not-a-time"},
    ):
        with pytest.raises(ReviewQueryRejected):
            paginate_review_events(events, **kwargs)


def test_event_rejects_unknown_fields_unbounded_summary_and_non_utc_timestamp():
    with pytest.raises(ReviewQueryRejected):
        make_review_event(
            event_id="x", event_type="unknown", occurred_at="2026-08-03T10:00:00Z",
            status="active", summary="x", references={},
        )
    with pytest.raises(ReviewQueryRejected):
        make_review_event(
            event_id="x", event_type="finding_created",
            occurred_at="2026-08-03T10:00:00Z", status="active",
            summary="x" * 401,
            references={"graph": None, "run_id": None, "finding_id": 1,
                        "candidate_id": None},
        )
