from __future__ import annotations

import ast
import base64
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.db.models import Base, MonitoringSignalAlertRow, Organization
from app.monitoring import contracts
from app.monitoring.cursor import AlertCursorCodec, MonitoringCursorRefusal
from app.monitoring.evaluation import MonitoringEvaluationTransition
from app.monitoring.query_service import (
    MonitoringQueryRefusal,
    get_alert_inbox_item,
    list_alert_inbox,
    _before_cursor,
)
from app.monitoring.repository import MonitoringNotFound, MonitoringRepository
from app.monitoring.runtime import persist_monitoring_transition
from tests.test_v0_monitoring_persistence import (
    T0,
    _engine,
    _facts,
    _owned_facts,
    _spec,
    _transition,
)


SECRET = b"monitoring-inbox-test-secret-32-bytes"
ROOT = Path(__file__).resolve().parents[3]


def _compiled(snapshot, event, alert):
    return MonitoringEvaluationTransition(
        snapshot, event, contracts.AlertDerived(alert),
    )


def _seed(engine):
    with Session(engine, expire_on_commit=False) as session, session.begin():
        alpha = MonitoringRepository(session, owner_id="tenant.alpha")
        before, after, event, alert = _facts()
        alpha.create_assignment(_spec(), now=T0)
        alpha.append_state_snapshot(before, created_at=T0)
        first = persist_monitoring_transition(
            alpha, _compiled(after, event, alert), created_at=T0,
        )
        second_snapshot, second_event, second_alert = _transition(first.snapshot, 2)
        second = persist_monitoring_transition(
            alpha, _compiled(second_snapshot, second_event, second_alert),
            created_at=second_event.event_at,
        )

        beta = MonitoringRepository(session, owner_id="tenant.beta")
        beta_before, beta_after, beta_event, beta_alert = _owned_facts(
            "tenant.beta", "assignment.beta",
        )
        beta.create_assignment(
            _spec("assignment.beta", "project.beta"), now=T0,
        )
        beta.append_state_snapshot(beta_before, created_at=T0)
        beta_persisted = persist_monitoring_transition(
            beta, _compiled(beta_after, beta_event, beta_alert), created_at=T0,
        )
    return first, second, beta_persisted


def test_newest_first_page_and_stable_cursor_continuation(tmp_path):
    engine = _engine(tmp_path)
    first, second, _beta = _seed(engine)
    codec = AlertCursorCodec(SECRET)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        page1 = list_alert_inbox(repository, codec, limit=1)
        assert [item.alert.address for item in page1.items] == [second.alert.address]
        assert page1.next_cursor is not None
        page2 = list_alert_inbox(
            repository, codec, limit=1, cursor=page1.next_cursor,
        )
        assert [item.alert.address for item in page2.items] == [first.alert.address]
        assert page2.next_cursor is None


def test_postgresql_cursor_boundary_binds_exact_naive_utc_wall_clock(tmp_path):
    engine = _engine(tmp_path)
    _first, second, _beta = _seed(engine)
    codec = AlertCursorCodec(SECRET)
    token = codec.encode(
        owner_id="tenant.alpha", assignment_id=None, unread_only=None,
        event_at=second.alert.event_at, alert_address=second.alert.address,
    )
    position = codec.decode(
        token, owner_id="tenant.alpha", assignment_id=None, unread_only=None,
    )
    statement = sa.select(MonitoringSignalAlertRow).where(_before_cursor(position))
    parameters = statement.compile(dialect=postgresql.dialect()).params
    times = [value for value in parameters.values() if hasattr(value, "tzinfo")]
    assert times
    assert all(value.tzinfo is None for value in times)
    assert all(value == second.alert.event_at.replace(tzinfo=None) for value in times)


def test_cursor_is_owner_and_filter_bound_and_payload_is_privacy_safe(tmp_path):
    engine = _engine(tmp_path)
    _seed(engine)
    codec = AlertCursorCodec(SECRET)
    with Session(engine) as session:
        alpha = MonitoringRepository(session, owner_id="tenant.alpha")
        token = list_alert_inbox(alpha, codec, limit=1).next_cursor
        payload = base64.urlsafe_b64decode(token.split(".")[0] + "===")
        for forbidden in (b"tenant.alpha", b"ABC", b"strategy", b"note", b"credential"):
            assert forbidden not in payload
        beta = MonitoringRepository(session, owner_id="tenant.beta")
        with pytest.raises(MonitoringQueryRefusal, match="cursor"):
            list_alert_inbox(beta, codec, limit=1, cursor=token)
        with pytest.raises(MonitoringQueryRefusal, match="cursor"):
            list_alert_inbox(alpha, codec, limit=1, cursor=token, unread_only=True)
        payload_part, signature_part = token.split(".")
        changed = ("A" if signature_part[0] != "A" else "B") + signature_part[1:]
        with pytest.raises(MonitoringQueryRefusal, match="cursor"):
            list_alert_inbox(alpha, codec, limit=1, cursor=payload_part + "." + changed)


def test_assignment_and_unread_filters_are_owner_scoped(tmp_path):
    engine = _engine(tmp_path)
    first, second, _beta = _seed(engine)
    codec = AlertCursorCodec(SECRET)
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        read = contracts.AlertAttentionEvent.create(
            alert=first.alert, sequence=1, action=contracts.AttentionAction.READ,
            occurred_at=first.alert.event_at,
        )
        repository.append_attention_event(read, created_at=T0)
        unread = list_alert_inbox(
            repository, codec, assignment_id="assignment.alpha", unread_only=True,
        )
        assert [item.alert.address for item in unread.items] == [second.alert.address]
        assert unread.items[0].attention.is_unread is True
        read_page = list_alert_inbox(repository, codec, unread_only=False)
        assert [item.alert.address for item in read_page.items] == [first.alert.address]


def test_detail_and_lists_never_cross_owner_or_mutate_session(tmp_path):
    engine = _engine(tmp_path)
    first, _second, beta = _seed(engine)
    codec = AlertCursorCodec(SECRET)
    with Session(engine) as session:
        alpha = MonitoringRepository(session, owner_id="tenant.alpha")
        before = (tuple(session.new), tuple(session.dirty), tuple(session.deleted))
        detail = get_alert_inbox_item(
            alpha, assignment_id=first.alert.assignment_id,
            alert_address=first.alert.address,
        )
        assert detail.alert == first.alert
        listed = list_alert_inbox(alpha, codec).items
        assert len(listed) == 2
        assert all(item.alert.owner_id == "tenant.alpha" for item in listed)
        after = (tuple(session.new), tuple(session.dirty), tuple(session.deleted))
        assert after == before == ((), (), ())
        with pytest.raises(MonitoringNotFound):
            get_alert_inbox_item(
                alpha, assignment_id=beta.alert.assignment_id,
                alert_address=beta.alert.address,
            )


def test_pending_caller_writes_refuse_before_query(tmp_path):
    engine = _engine(tmp_path)
    _seed(engine)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        session.add(Organization(organization_id="pending.owner", name="pending"))
        with pytest.raises(MonitoringQueryRefusal, match="pending writes"):
            list_alert_inbox(repository, AlertCursorCodec(SECRET))
        session.rollback()


def test_repeated_reads_leave_all_nine_monitoring_table_counts_unchanged(tmp_path):
    engine = _engine(tmp_path)
    _seed(engine)
    monitoring_tables = tuple(
        table for name, table in Base.metadata.tables.items()
        if name.startswith("monitoring_")
    )
    assert len(monitoring_tables) == 9
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        before = {
            table.name: session.scalar(sa.select(sa.func.count()).select_from(table))
            for table in monitoring_tables
        }
        for _ in range(5):
            assert list_alert_inbox(repository, AlertCursorCodec(SECRET)).items
        after = {
            table.name: session.scalar(sa.select(sa.func.count()).select_from(table))
            for table in monitoring_tables
        }
        assert after == before


@pytest.mark.parametrize("limit", [0, 101, True])
def test_page_bounds_refuse(limit, tmp_path):
    engine = _engine(tmp_path)
    _seed(engine)
    with Session(engine) as session:
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        with pytest.raises(MonitoringQueryRefusal, match="limit"):
            list_alert_inbox(repository, AlertCursorCodec(SECRET), limit=limit)


@pytest.mark.parametrize("token", ["", "x", "x.y.z", "!bad.y", "x." + "a" * 4096])
def test_malformed_tampered_and_oversized_cursors_refuse(token):
    codec = AlertCursorCodec(SECRET)
    with pytest.raises(MonitoringCursorRefusal):
        codec.decode(
            token, owner_id="tenant.alpha", assignment_id=None, unread_only=None,
        )


def test_source_has_no_route_auth_provider_execution_or_frontend_import():
    imports = set()
    for relative in (
        "paper-trader/backend/app/monitoring/cursor.py",
        "paper-trader/backend/app/monitoring/query_service.py",
    ):
        tree = ast.parse((ROOT / relative).read_text())
        imports |= {
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        } | {
            alias.name for node in ast.walk(tree)
            if isinstance(node, ast.Import) for alias in node.names
        }
    forbidden = (
        "app.api", "app.core.release_profile", "app.main", "app.providers",
        "app.engine", "app.execution", "app.ledger", "paper-trader.frontend",
    )
    assert not any(name == prefix or name.startswith(prefix + ".") for name in imports for prefix in forbidden)
