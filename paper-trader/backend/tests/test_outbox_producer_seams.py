"""Real product mutations append scoped change facts in their own transaction."""
from __future__ import annotations

import json

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.events.planes import execution_outbox, ledger_outbox, research_outbox
from app.db.models import Base, BrokerAccount
from app.execution.leases import LeaseRepository
from app.ledger.db import LedgerBase
from app.ledger.service import delete_artifact, put_artifact, write_snapshot
from research.domain.base import ResearchBase
from research.domain.operations import ResearchOperationRepository
from app.ledger import models as _ledger_models  # noqa: F401
from research.domain import models as _research_models  # noqa: F401


def test_execution_claim_commits_account_scoped_projection_event():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    sm = sessionmaker(engine, expire_on_commit=False, future=True)
    try:
        with sm.begin() as session:
            session.add(BrokerAccount(broker_account_id="account-1", owner_id="org-a",
                                      broker="kite", external_account_id="external",
                                      display_name="Account"))
        token = LeaseRepository(sm).claim(owner_id="org-a", broker_account_id="account-1",
                                          cell_id="cell", worker_id="worker")
        with sm() as session:
            event = session.scalar(select(execution_outbox().models.Event))
            assert (event.owner_id, event.broker_account_id) == ("org-a", "account-1")
            assert event.event_type == "execution.lease.changed"
            assert json.loads(event.payload_json)["fence_epoch"] == token.fence_epoch
    finally:
        engine.dispose()


def test_ledger_snapshot_and_event_commit_together():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    LedgerBase.metadata.create_all(engine)
    sm = sessionmaker(engine, expire_on_commit=False, future=True)
    try:
        assert write_snapshot(sm, '{"journal":[]}', None,
                              owner_id="org-a", broker_account_id="account-1") == 1
        with sm() as session:
            event = session.scalar(select(ledger_outbox().models.Event))
            assert event.event_type == "ledger.snapshot.changed"
            assert json.loads(event.payload_json) == {
                "projection": "ledger_snapshot", "version": 1}
    finally:
        engine.dispose()


def test_research_scheduler_event_references_same_committed_audit_sequence():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    ResearchBase.metadata.create_all(engine)
    sm = sessionmaker(engine, expire_on_commit=False, future=True)
    try:
        with sm() as session:
            repo = ResearchOperationRepository(session)
            view = repo.enqueue(owner_id="org-a", trigger="manual", plan={},
                                build="test", provider_mode="mock")
            repo.request_cancel(view.operation_id, owner_id="org-a")
        with sm() as session:
            events = list(session.scalars(select(research_outbox().models.Event)))
            assert len(events) == 2
            assert [json.loads(event.payload_json)["audit_sequence"] for event in events] == [0, 1]
    finally:
        engine.dispose()


def test_ledger_artifact_delete_and_identical_recreate_emit_distinct_events():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    LedgerBase.metadata.create_all(engine)
    sm = sessionmaker(engine, expire_on_commit=False, future=True)
    try:
        put_artifact(sm, "artifact", "text/plain", b"x",
                     owner_id="org-a", broker_account_id="account-1")
        assert delete_artifact(sm, "artifact", owner_id="org-a",
                               broker_account_id="account-1")
        put_artifact(sm, "artifact", "text/plain", b"x",
                     owner_id="org-a", broker_account_id="account-1")
        put_artifact(sm, "artifact", "text/markdown", b"x",
                     owner_id="org-a", broker_account_id="account-1")
        with sm() as session:
            events = list(session.scalars(select(ledger_outbox().models.Event).order_by(
                ledger_outbox().models.Event.plane_offset)))
            assert len(events) == 4
            assert [event.aggregate_sequence for event in events] == [1, 2, 3, 4]
    finally:
        engine.dispose()
