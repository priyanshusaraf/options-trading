import datetime as dt
import sqlite3

import pytest

from research.domain.base import init_research_db, make_engine


def test_only_one_worker_can_claim_the_same_owner_operation(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    init_research_db(engine)
    try:
        now = dt.datetime(2026, 8, 12, tzinfo=dt.UTC)
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO research_operation (owner_id, operation_id, trigger, plan_json, status, stage, build, provider_mode, completed_run_ids_json, created_at, queued_at, attempt_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("owner-a", "operation-a", "manual", "{}", "pending", "startup", "test", "mock", "[]", now, now, 0),
            )
            first = connection.exec_driver_sql(
                "UPDATE research_operation SET status='running', claim_token='worker-one' WHERE owner_id=? AND operation_id=? AND status='pending'",
                ("owner-a", "operation-a"),
            )
            second = connection.exec_driver_sql(
                "UPDATE research_operation SET status='running', claim_token='worker-two' WHERE owner_id=? AND operation_id=? AND status='pending'",
                ("owner-a", "operation-a"),
            )
        assert first.rowcount == 1
        assert second.rowcount == 0
    finally:
        engine.dispose()


def test_same_operation_id_can_exist_per_owner_without_cross_owner_read(tmp_path):
    engine = make_engine(str(tmp_path / "research.db"))
    init_research_db(engine)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO research_operation (owner_id, operation_id, trigger, plan_json, status, stage, build, provider_mode, completed_run_ids_json, created_at, queued_at, attempt_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)",
                ("owner-a", "same", "manual", '{"private":"a"}', "pending", "startup", "test", "mock", "[]", 0),
            )
            connection.exec_driver_sql(
                "INSERT INTO research_operation (owner_id, operation_id, trigger, plan_json, status, stage, build, provider_mode, completed_run_ids_json, created_at, queued_at, attempt_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)",
                ("owner-b", "same", "manual", '{"private":"b"}', "pending", "startup", "test", "mock", "[]", 0),
            )
            foreign = connection.exec_driver_sql(
                "SELECT plan_json FROM research_operation WHERE owner_id=? AND operation_id=?", ("owner-c", "same")
            ).first()
        assert foreign is None
    finally:
        engine.dispose()
