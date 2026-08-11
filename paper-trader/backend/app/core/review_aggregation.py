"""Application/research source aggregation shared by review reads and note anchors."""
from __future__ import annotations

from app.core import research_read
from app.core.research_review import make_review_event
from app.editor import graph_artifacts as store


def project_review_source(project_id: str, *, owner_id: str) -> dict:
    source_errors: list[dict] = []
    events: list[dict] = []
    try:
        versions = store.list_project_version_events(project_id, owner_id=owner_id)
    except store.GraphVersionCorrupt as exc:
        source_errors.append({
            "source": "graph_version",
            "source_id": str(exc.args[0]),
            "code": "GRAPH_VERSION_CORRUPT",
        })
        versions = ()
    for version in versions:
        events.append(make_review_event(
            event_id=f"graph:{version.identifier}:{version.version}",
            event_type="graph_version_published",
            occurred_at=version.created_at,
            status="published",
            summary=f"Published {version.identifier} version {version.version}",
            references={
                "graph": {
                    "identifier": version.identifier,
                    "version": version.version,
                    "content_address": version.content_address,
                },
                "run_id": None,
                "finding_id": None,
                "candidate_id": None,
            },
        ))
    research = research_read.project_review_source(project_id)
    events.extend(research["events"])
    source_errors.extend(research["source_errors"])
    return {
        "events": events,
        "queues": research["queues"],
        "source_errors": source_errors,
    }
