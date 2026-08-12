import datetime as dt

import pytest

from app.core.review_search import (
    ReviewSearchRejected,
    normalize_search_query,
    search_review_documents,
)
from app.core.research_review import make_review_event


def _event(
    event_id: str,
    summary: str,
    *,
    minute: int = 0,
    run_id: int | None = None,
):
    return make_review_event(
        event_id=event_id,
        event_type="experiment_run",
        occurred_at=dt.datetime(2026, 8, 3, 10, minute, tzinfo=dt.UTC),
        status="completed",
        summary=summary,
        references={
            "graph": None,
            "run_id": run_id,
            "finding_id": None,
            "candidate_id": None,
        },
    )


def _note(
    note_id: str,
    body: str,
    *,
    minute: int = 0,
    event_id: str = "run:1",
    anchor_state: str = "available",
):
    return {
        "note_id": note_id,
        "event_id": event_id,
        "event_type": "experiment_run",
        "body": body,
        "created_by": "owner",
        "anchor_state": anchor_state,
        "updated_at": f"2026-08-03T10:{minute:02d}:00.000000Z",
    }


def test_query_normalization_is_unicode_case_and_whitespace_stable():
    assert normalize_search_query("  ＡLPHA\u00a0 Straße  ") == "alpha strasse"
    assert normalize_search_query("alpha strasse") == "alpha strasse"
    for value, message in (
        (" ", "2 to 120"),
        ("x", "2 to 120"),
        ("x" * 121, "2 to 120"),
        ("safe\nunsafe", "control"),
    ):
        with pytest.raises(ReviewSearchRejected, match=message):
            normalize_search_query(value)


def test_search_is_literal_and_orders_by_offset_newest_kind_and_id():
    events = [
        _event("run:1", "alpha [risk]", minute=1, run_id=1),
        _event("run:2", "later alpha [risk]", minute=4, run_id=2),
        _event("run:3", "alpha [risk]", minute=3, run_id=3),
    ]
    notes = [
        _note("note.b", "alpha [risk]", minute=5),
        _note("note.a", "alpha [risk]", minute=5),
    ]

    page = search_review_documents(events, notes, query="[RISK]", limit=10)

    assert [item["result_id"] for item in page["results"]] == [
        "note:note.a", "note:note.b", "event:run:3", "event:run:1",
        "event:run:2",
    ]
    assert page["query"] == "[risk]"
    assert page["results"][2]["reference"] == {
        "run_id": 3, "finding_id": None, "candidate_id": None,
    }


def test_keyset_cursor_is_query_bound_tamper_evident_and_complete():
    events = [_event(f"run:{index}", "shared text", minute=index, run_id=index)
              for index in range(1, 6)]
    first = search_review_documents(events, [], query="SHARED", limit=2)
    second = search_review_documents(
        events, [], query="shared", limit=2, cursor=first["next_cursor"]
    )
    third = search_review_documents(
        events, [], query="shared", limit=2, cursor=second["next_cursor"]
    )
    assert [item["result_id"] for page in (first, second, third)
            for item in page["results"]] == [
        "event:run:5", "event:run:4", "event:run:3", "event:run:2", "event:run:1",
    ]
    assert third["next_cursor"] is None
    with pytest.raises(ReviewSearchRejected, match="query"):
        search_review_documents(
            events, [], query="different", limit=2, cursor=first["next_cursor"]
        )
    token = first["next_cursor"]
    with pytest.raises(ReviewSearchRejected, match="cursor"):
        search_review_documents(
            events, [], query="shared", limit=2,
            cursor=token[:-1] + ("A" if token[-1] != "A" else "B"),
        )


def test_missing_anchor_note_is_searchable_without_an_invented_summary():
    page = search_review_documents(
        [], [_note("note.missing", "human-only context", anchor_state="missing")],
        query="HUMAN", limit=10,
    )
    assert page["results"] == [{
        "result_id": "note:note.missing",
        "kind": "note",
        "event_id": "run:1",
        "event_type": "experiment_run",
        "text": "human-only context",
        "timestamp": "2026-08-03T10:00:00.000000Z",
        "anchor_state": "missing",
        "reference": {"run_id": None, "finding_id": None, "candidate_id": None},
    }]
    assert "summary" not in page["results"][0]


def test_event_metadata_and_references_are_not_search_corpus_or_result_content():
    event = _event("run:9", "Safe published summary", run_id=9)
    event["references"]["graph"] = {
        "identifier": "raw-secret-marker",
        "version": 9,
        "content_address": f"sha256:{9:064x}",
    }

    assert search_review_documents(
        [event], [], query="raw-secret", limit=10,
    )["results"] == []
    result = search_review_documents(
        [event], [], query="published", limit=10,
    )["results"][0]
    assert set(result["reference"]) == {"run_id", "finding_id", "candidate_id"}
    assert "graph" not in result["reference"]


def test_search_bounds_and_closed_document_shapes_fail_closed():
    with pytest.raises(ReviewSearchRejected, match="limit"):
        search_review_documents([], [], query="valid", limit=51)
    with pytest.raises(ReviewSearchRejected, match="event source exceeds"):
        search_review_documents(
            [_event(f"run:{index}", "bounded") for index in range(2001)],
            [], query="bounded", limit=1,
        )
    with pytest.raises(ReviewSearchRejected, match="note source"):
        search_review_documents(
            [], [_note("note.bad", "text") | {"created_by": ""}],
            query="text", limit=1,
        )
