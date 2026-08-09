"""The durable entry lifecycle is persisted and its event history is immutable."""
from __future__ import annotations

import datetime as dt

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Deployment, ExecutionIntent, ExecutionOrderEvent


def _session_factory(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'execution-lifecycle.db'}")

    @sa.event.listens_for(engine, "connect")
    def _enforce_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _intent() -> ExecutionIntent:
    return ExecutionIntent(
        client_intent_id="entry-000000000000000000000001",
        deployment_id=1,
        broker="upstox",
        account_scope="account.default",
        connection_scope="connection.default",
        broker_tag="entry-000000000000001",
        intent="ENTRY",
        instrument_key="NSE_EQ|INE002A01018",
        tradingsymbol="RELIANCE",
        exchange="NSE",
        side="BUY",
        order_type="MARKET",
        requested_qty=1,
        created_at=dt.datetime(2026, 8, 9, 9, 15),
    )


def _event(client_intent_id: str, source_event_id: str = "event-1") -> ExecutionOrderEvent:
    return ExecutionOrderEvent(
        client_intent_id=client_intent_id,
        source="broker",
        source_event_id=source_event_id,
        kind="INTENT_CREATED",
        observed_at=dt.datetime(2026, 8, 9, 9, 15),
    )


def test_execution_intent_and_events_survive_a_fresh_session(tmp_path):
    """Removing either lifecycle table or its foreign key loses durable intent history."""
    Session = _session_factory(tmp_path)
    with Session.begin() as session:
        session.add(Deployment(id=1, name="default"))
        intent = _intent()
        session.add(intent)
        session.add(_event(intent.client_intent_id))

    with Session() as session:
        intent = session.get(ExecutionIntent, "entry-000000000000000000000001")
        event = session.scalar(sa.select(ExecutionOrderEvent))

    assert intent is not None
    assert intent.intent == "ENTRY"
    assert event is not None
    assert event.kind == "INTENT_CREATED"
    assert event.client_intent_id == intent.client_intent_id


def test_execution_event_identity_is_unique_per_intent_and_source(tmp_path):
    """Dropping the event source identity constraint permits duplicate broker facts."""
    Session = _session_factory(tmp_path)
    with Session.begin() as session:
        session.add(Deployment(id=1, name="default"))
        intent = _intent()
        session.add(intent)
        session.add(_event(intent.client_intent_id))

    with pytest.raises(IntegrityError):
        with Session.begin() as session:
            session.add(_event("entry-000000000000000000000001"))


def test_execution_events_are_append_only_in_the_database(tmp_path):
    """Removing either trigger lets an existing broker fact be rewritten or erased."""
    Session = _session_factory(tmp_path)
    with Session.begin() as session:
        session.add(Deployment(id=1, name="default"))
        intent = _intent()
        session.add(intent)
        session.add(_event(intent.client_intent_id))

    for statement in (
        "UPDATE execution_order_events SET kind = 'CHANGED' WHERE id = 1",
        "DELETE FROM execution_order_events WHERE id = 1",
    ):
        # SQLite maps RAISE(ABORT, ...) to its integrity-error class.
        with pytest.raises(IntegrityError, match="execution_order_events are immutable"):
            with Session.begin() as session:
                session.execute(sa.text(statement))
