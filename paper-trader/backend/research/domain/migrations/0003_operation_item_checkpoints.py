"""Create the final, owner-local durable operation receipt table.

0003 has never shipped, so it creates the final contract directly instead of
introducing an intermediate nullable receipt schema.  The table is empty when
added after 0002; a pre-existing table must exactly match the final DDL before
it can be stamped.
"""
import re
import datetime as dt
import json

from sqlalchemy.schema import CreateIndex, CreateTable

VERSION = "0003"


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace('"', '').strip()).upper()


def _expected_sql(connection, table) -> str:
    return _normalise(str(CreateTable(table).compile(dialect=connection.dialect)))


def _ensure_table(connection, table, *, error: str, refuse_existing_rows: bool = False) -> None:
    names = {row[0] for row in connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    if table.name not in names:
        connection.exec_driver_sql(str(CreateTable(table).compile(dialect=connection.dialect)))
    else:
        actual = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table.name,)
        ).scalar_one()
        if _normalise(actual) != _expected_sql(connection, table):
            raise RuntimeError(error)
        # 0002 had no operation event contract. A nonempty exact-shaped table
        # is therefore forged/stale evidence, not a restart artifact; accepting
        # it would let someone manufacture takeover/latency history before the
        # first event-capable revision stamps the database.
        if refuse_existing_rows and connection.exec_driver_sql(
                f"SELECT 1 FROM {table.name} LIMIT 1").first() is not None:
            raise RuntimeError("research_operation_event preexists during 0003 upgrade")
    present = {row[1] for row in connection.exec_driver_sql(f"PRAGMA index_list({table.name!r})")}
    for index in table.indexes:
        if index.name not in present:
            connection.exec_driver_sql(str(CreateIndex(index).compile(dialect=connection.dialect)))


def upgrade(connection, table, event_table=None) -> None:
    _ensure_table(connection, table,
                  error="research_operation_item schema contract is malformed")
    if event_table is not None:
        _ensure_table(connection, event_table,
                      error="research_operation_event schema contract is malformed",
                      refuse_existing_rows=True)
    # 0002 could contain queued work but had no durable item boundary.  Pending
    # rows are safely reconstructible from their frozen plan; a running row is
    # inherently ambiguous (it may have crossed a provider boundary) and is
    # therefore terminalized rather than silently stamped as replayable.
    rows = connection.exec_driver_sql(
        "SELECT owner_id, operation_id, status, plan_json FROM research_operation "
        "WHERE status IN ('pending', 'running')"
    ).all()
    for owner_id, operation_id, status, raw_plan in rows:
        if status == "running":
            connection.exec_driver_sql(
                "UPDATE research_operation SET status='failed', completed_at=?, "
                "error_json=?, claim_token=NULL, claimed_by=NULL, claim_expires_at=NULL "
                "WHERE owner_id=? AND operation_id=? AND status='running'",
                (dt.datetime.now(dt.UTC).replace(tzinfo=None),
                 json.dumps({"code": "RESEARCH_OPERATION_MIGRATION_REPLAY_REFUSED",
                             "message": "pre-checkpoint running operation cannot be replayed"},
                            sort_keys=True, separators=(",", ":")),
                 owner_id, operation_id),
            )
            continue
        try:
            from research.domain.operations import operation_item_keys
            plan = json.loads(raw_plan)
            keys = operation_item_keys(plan, trigger=connection.exec_driver_sql(
                "SELECT trigger FROM research_operation WHERE owner_id=? AND operation_id=?",
                (owner_id, operation_id)).scalar_one())
        except Exception:
            connection.exec_driver_sql(
                "UPDATE research_operation SET status='failed', completed_at=?, error_json=? "
                "WHERE owner_id=? AND operation_id=? AND status='pending'",
                (dt.datetime.now(dt.UTC).replace(tzinfo=None),
                 json.dumps({"code": "RESEARCH_OPERATION_MIGRATION_PLAN_REFUSED",
                             "message": "pre-checkpoint operation plan cannot be replayed"},
                            sort_keys=True, separators=(",", ":")), owner_id, operation_id),
            )
            continue
        for ordinal, item_key in enumerate(keys):
            existing = connection.exec_driver_sql(
                "SELECT ordinal, status, run_id, completed_at FROM research_operation_item "
                "WHERE owner_id=? AND operation_id=? AND item_key=?",
                (owner_id, operation_id, item_key),
            ).first()
            if existing is not None:
                # A 0002 source has no legitimate item receipt.  Even a valid
                # looking row is forged/stale when this migration first runs;
                # refusing it is safer than allowing OR IGNORE to shadow the
                # deterministic descriptor-derived key or ordinal.
                raise RuntimeError("research_operation_item preexists during 0003 backfill")
            connection.exec_driver_sql(
                "INSERT INTO research_operation_item "
                "(owner_id, operation_id, item_key, ordinal, status, run_id, completed_at) "
                "VALUES (?, ?, ?, ?, 'pending', NULL, NULL)",
                (owner_id, operation_id, item_key, ordinal),
            )


def downgrade(_connection, _table) -> None:
    raise RuntimeError("0003 refuses destructive removal of operation checkpoints")
