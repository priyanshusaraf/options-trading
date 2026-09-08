"""Small dialect port for shared-database reservation and row locking.

SQLite has one writer, so a short ``BEGIN IMMEDIATE`` is the reservation.
PostgreSQL uses transaction-scoped advisory locks for count-and-admit critical
sections and row locks for selecting work or mutable account state.  Callers
keep all business predicates, tokens and fencing updates in their repositories.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager

from sqlalchemy import (Integer, Text, case, cast, event, exists, func, literal,
                        select, text)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

_SQLITE_IMMEDIATE_TRANSACTION = "db_immediate_transaction"
_TRANSACTION_HAS_WRITES = "db_transaction_has_writes"
_CALLER_OWNED_SAVEPOINT_ROOT = "caller_owned_savepoint_root"


class TransactionBoundaryError(RuntimeError):
    """Caller-owned transaction state cannot safely enter a seam boundary."""


@event.listens_for(Session, "do_orm_execute")
def _record_executed_dml(execute_state) -> None:
    """Remember Core/ORM DML that is invisible to Session dirty collections."""
    if bool(getattr(execute_state.statement, "is_dml", False)):
        execute_state.session.info[_TRANSACTION_HAS_WRITES] = True


@event.listens_for(Session, "before_flush")
def _record_flushed_writes(session, _flush_context, _instances) -> None:
    # After a flush, new/dirty/deleted may be empty even though rolling the
    # transaction back would still discard caller writes.
    if session.new or session.dirty or session.deleted:
        session.info[_TRANSACTION_HAS_WRITES] = True


@event.listens_for(Session, "after_transaction_end")
def _clear_write_provenance(session, transaction) -> None:
    # A savepoint ending does not end the enclosing caller transaction.
    if transaction.parent is None:
        session.info.pop(_TRANSACTION_HAS_WRITES, None)
        marker = session.info.get(_CALLER_OWNED_SAVEPOINT_ROOT)
        if marker is not None and marker["root"] is transaction:
            session.info.pop(_CALLER_OWNED_SAVEPOINT_ROOT, None)


def _sqlite_in_transaction(connection) -> bool:
    return bool(connection.connection.driver_connection.in_transaction)


def _postgresql_in_transaction(connection) -> bool:
    """Read psycopg's physical transaction state without changing ownership."""
    raw = connection.connection.driver_connection
    status = getattr(getattr(raw, "info", None), "transaction_status", None)
    return getattr(status, "name", None) == "INTRANS"


def _physical_outer_transaction(connection, dialect: str) -> bool:
    if dialect == "sqlite":
        return _sqlite_in_transaction(connection)
    if dialect == "postgresql":
        return _postgresql_in_transaction(connection)
    raise RuntimeError(f"unsupported database dialect for caller savepoint: {dialect}")


@contextmanager
def caller_owned_savepoint(session: Session, *, scope: str):
    """Create one SAVEPOINT inside a proven caller-owned physical transaction.

    The helper may establish the physical root, but never finishes it.  Its
    marker is tied to the live SQLAlchemy root and exact enlisted connection so
    recursive calls cannot silently borrow a different transaction.
    """
    if not session.is_active:
        raise TransactionBoundaryError(
            "caller savepoint refused on a failed Session; caller rollback or disposal is required")
    connection = session.connection()
    root = session.get_transaction()
    if root is None:  # Defensive: Session.connection() must enlist a root.
        raise RuntimeError("caller savepoint could not enlist a caller transaction")
    dialect = connection.dialect.name
    marker = session.info.get(_CALLER_OWNED_SAVEPOINT_ROOT)
    if (dialect == "sqlite" and session.in_nested_transaction() and (
            marker is None or marker["root"] is not root)):
        raise TransactionBoundaryError(
            "caller savepoint refused inside an unproved external nested transaction")
    # SQLAlchemy flushes pending ORM changes immediately before ``begin_nested``.
    # Letting unrelated caller objects enter that pre-savepoint flush would make a
    # seam-local IntegrityError handler observe a failure outside its boundary.
    if marker is None and (session.new or session.dirty or session.deleted):
        try:
            session.flush()
        except (SQLAlchemyError, ValueError) as exc:
            raise TransactionBoundaryError(
                "caller savepoint refused after a pre-savepoint caller flush failure") from exc
    if marker is not None and (
            marker["root"] is not root
            or marker["connection"] is not connection
            or marker["dialect"] != dialect):
        session.info.pop(_CALLER_OWNED_SAVEPOINT_ROOT, None)
        marker = None

    if marker is None:
        if dialect == "sqlite":
            # SQLAlchemy may own only a logical root after no SQL or a SELECT.
            # A literal BEGIN creates the required physical root before the
            # SAVEPOINT and does not commit or roll back caller work.
            if not _sqlite_in_transaction(connection):
                connection.exec_driver_sql("BEGIN")
        elif dialect == "postgresql":
            # psycopg remains IDLE until a statement reaches the server.
            if not _postgresql_in_transaction(connection):
                connection.exec_driver_sql("SELECT 1")
        else:
            raise TransactionBoundaryError(
                f"unsupported database dialect for caller savepoint: {dialect}")
        if not _physical_outer_transaction(connection, dialect):
            raise TransactionBoundaryError(
                "caller savepoint refused without a physical outer transaction")
        session.info[_CALLER_OWNED_SAVEPOINT_ROOT] = {
            "root": root, "connection": connection, "dialect": dialect,
            "scope": scope,
        }
    elif not _physical_outer_transaction(connection, dialect):
        raise TransactionBoundaryError("caller savepoint root proof became stale")

    with session.begin_nested():
        yield


def has_pending_writes(session) -> bool:
    """Whether rollback would discard ORM state or already-executed DML."""
    return bool(session.new or session.dirty or session.deleted
                or session.info.get(_TRANSACTION_HAS_WRITES))


def dialect_name(session) -> str:
    return session.get_bind().dialect.name


def _sqlite_transaction_has_sql(transaction, connection, *, already_enlisted: bool) -> bool:
    """Whether a logical transaction has already enlisted SQLite SQL.

    Pysqlite reports ``in_transaction=False`` after a SELECT even though
    SQLAlchemy has already enlisted the connection.  The enlisted mapping is
    therefore the necessary fallback for refusing SELECT-then-upgrade races.
    Kept here so no caller depends on SQLAlchemy transaction internals.
    """
    return connection.connection.driver_connection.in_transaction or already_enlisted


def begin_reservation(session, *, scope: str) -> None:
    """Serialize a bounded count-and-write decision for this transaction."""
    existing = session.get_transaction()
    marked = session.info.get(_SQLITE_IMMEDIATE_TRANSACTION)
    if marked is not None and marked is not existing:
        session.info.pop(_SQLITE_IMMEDIATE_TRANSACTION, None)
    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        already_enlisted = bool(getattr(existing, "_connections", ()))
        connection = session.connection()
        if existing is not None:
            if marked is existing:
                return
            # ``session.begin()`` is logical until the driver executes SQL. It
            # may still become immediate; an active DB transaction may not be
            # upgraded after the fact without losing the serialization proof.
            if _sqlite_transaction_has_sql(
                    existing, connection, already_enlisted=already_enlisted):
                raise RuntimeError(
                    "SQLite reservation refused inside a pre-existing deferred transaction")
        transaction = session.get_transaction()
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        session.info[_SQLITE_IMMEDIATE_TRANSACTION] = transaction
        return
    if dialect == "postgresql":
        connection = session.connection()
        digest = hashlib.sha256(scope.encode("utf-8")).digest()
        key = int.from_bytes(digest[:8], "big", signed=True)
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        return
    raise RuntimeError(f"unsupported database dialect for reservation: {dialect}")


def locked_rows(statement, session, *, skip_locked: bool = False):
    """Apply the PostgreSQL row-lock policy while leaving SQLite unchanged."""
    dialect = dialect_name(session)
    if dialect == "postgresql":
        return statement.with_for_update(skip_locked=skip_locked)
    if dialect == "sqlite":
        return statement
    raise RuntimeError(f"unsupported database dialect for row locking: {dialect}")


def begin_after_clean_reads(session, *, scope: str) -> None:
    """End a clean SQLite snapshot, then begin a reservation.

    Long-lived repositories may perform owner-scoped reads between their own
    committed operations. They may discard only that clean read transaction;
    pending caller writes always fail closed.
    """
    if dialect_name(session) == "sqlite" and session.get_transaction() is not None:
        marked = session.info.get(_SQLITE_IMMEDIATE_TRANSACTION)
        if marked is not session.get_transaction():
            if has_pending_writes(session):
                raise RuntimeError(
                    "SQLite reservation refused because the caller session has pending writes")
            session.rollback()
    begin_reservation(session, scope=scope)


def locked_mutation(statement, session, *, scope: str):
    """Lock one mutable row on PostgreSQL or the short SQLite writer lane."""
    dialect = dialect_name(session)
    if dialect == "sqlite":
        transaction = session.get_transaction()
        marked = session.info.get(_SQLITE_IMMEDIATE_TRANSACTION)
        if transaction is not None and marked is not transaction:
            already_enlisted = bool(getattr(transaction, "_connections", ()))
            connection = session.connection()
            if _sqlite_transaction_has_sql(
                    transaction, connection, already_enlisted=already_enlisted):
                if has_pending_writes(session):
                    raise RuntimeError(
                        "SQLite mutation lock refused because the caller session has pending writes")
                session.rollback()
            else:
                # The explicit logical transaction had no SQL before this
                # helper enlisted the connection. Start and mark it directly;
                # calling begin_reservation again would mistake our own
                # enlistment for a caller's deferred SQL.
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                session.info[_SQLITE_IMMEDIATE_TRANSACTION] = transaction
                return statement
        begin_reservation(session, scope=scope)
        return statement
    if dialect == "postgresql":
        return statement.with_for_update()
    raise RuntimeError(f"unsupported database dialect for mutation lock: {dialect}")


def append_unique_json_integer(column, value: int, session):
    """Return an atomic, idempotent JSON-array append for a text column."""
    dialect = dialect_name(session)
    item = literal(value, type_=Integer)
    if dialect == "sqlite":
        members = func.json_each(column).table_valued("key", "value")
        present = exists(select(1).select_from(members).where(members.c.value == item))
        return case((present, column), else_=func.json_insert(column, "$[#]", item))
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        current = cast(column, JSONB)
        array = func.jsonb_build_array(item)
        return case((current.op("@>")(array), column),
                    else_=cast(current.op("||")(array), Text))
    raise RuntimeError(f"unsupported database dialect for JSON array append: {dialect}")
