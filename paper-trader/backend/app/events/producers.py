"""Typed change-fact producers called by the transaction that owns each mutation.

These functions deliberately do not inspect ORM dirty state.  A repository names the
projection and immutable mutation identity at the point where it knows what changed.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.events.outbox import EventIdentity
from app.events.planes import execution_outbox, research_outbox


def _payload(projection: str, facts: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(projection, str) or not projection or len(projection) > 64:
        raise ValueError("projection must be a bounded name")
    values = dict(facts or {})
    if "projection" in values:
        raise ValueError("projection is owned by the typed producer")
    return {"projection": projection, **values}


def append_execution_change(
    session: Session,
    *,
    owner_id: str,
    broker_account_id: str | None,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    projection: str,
    producer_key: str,
    facts: dict[str, Any] | None = None,
) -> EventIdentity:
    """Append one execution-plane change inside the caller's transaction."""
    repo = execution_outbox()
    with repo.writer(session):
        return repo.append(
            session,
            classification="private",
            owner_id=owner_id,
            broker_account_id=broker_account_id,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            event_type=event_type,
            schema_version=1,
            payload=_payload(projection, facts),
            producer_key=producer_key,
        )


def append_research_change(
    session: Session,
    *,
    owner_id: str,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    projection: str,
    producer_key: str,
    facts: dict[str, Any] | None = None,
) -> EventIdentity:
    """Append one research-plane change inside the caller's transaction."""
    repo = research_outbox()
    with repo.writer(session):
        return repo.append(
            session,
            classification="private",
            owner_id=owner_id,
            broker_account_id=None,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            event_type=event_type,
            schema_version=1,
            payload=_payload(projection, facts),
            producer_key=producer_key,
        )
