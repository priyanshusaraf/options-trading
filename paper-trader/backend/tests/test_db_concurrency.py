"""Behavioral contracts for the centralized SQLite reservation primitive."""
from __future__ import annotations

import pytest
from sqlalchemy import (Column, Integer, MetaData, Table, create_engine,
                        select, text, update)
from sqlalchemy.orm import Session

from app.db.concurrency import (begin_after_clean_reads, begin_reservation,
                                locked_mutation)


def _one_row_table(engine):
    metadata = MetaData()
    rows = Table(
        "provenance_rows", metadata,
        Column("id", Integer, primary_key=True),
        Column("value", Integer, nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(rows.insert().values(id=1, value=0))
    return rows


def test_sqlite_reservation_refuses_a_preexisting_deferred_transaction():
    engine = create_engine("sqlite://", future=True)
    with Session(engine) as session:
        session.execute(text("SELECT 1"))

        with pytest.raises(RuntimeError, match="deferred transaction"):
            begin_reservation(session, scope="test")


def test_sqlite_reservation_is_repeatable_only_inside_its_own_transaction():
    engine = create_engine("sqlite://", future=True)
    with Session(engine) as session:
        begin_reservation(session, scope="first")
        begin_reservation(session, scope="second")
        assert session.connection().connection.driver_connection.in_transaction
        session.commit()


def test_sqlite_reservation_upgrades_an_explicit_transaction_before_first_sql():
    engine = create_engine("sqlite://", future=True)
    with Session(engine) as session, session.begin():
        begin_reservation(session, scope="test")
        assert session.connection().connection.driver_connection.in_transaction


def test_clean_read_restart_refuses_and_preserves_an_executed_core_update():
    engine = create_engine("sqlite://", future=True)
    rows = _one_row_table(engine)
    with Session(engine) as session:
        session.execute(update(rows).where(rows.c.id == 1).values(value=7))

        with pytest.raises(RuntimeError, match="pending writes"):
            begin_after_clean_reads(session, scope="test")

        session.commit()
    with engine.connect() as connection:
        assert connection.scalar(select(rows.c.value)) == 7


def test_sqlite_mutation_lock_refuses_and_preserves_an_executed_core_update():
    engine = create_engine("sqlite://", future=True)
    rows = _one_row_table(engine)
    with Session(engine) as session:
        session.execute(update(rows).where(rows.c.id == 1).values(value=9))

        with pytest.raises(RuntimeError, match="pending writes"):
            locked_mutation(select(rows), session, scope="test")

        session.commit()
    with engine.connect() as connection:
        assert connection.scalar(select(rows.c.value)) == 9
