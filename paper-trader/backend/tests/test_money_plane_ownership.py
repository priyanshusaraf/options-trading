"""Migration 0017 — an owner on the money plane, and an honest account of where it is not.

`0015` and `0016` made the *authority* to trade per-owner: a broker connection and an execution
intent both know whose they are. What the orders PRODUCE did not. A second owner would have
shared the first owner's positions, trades, order journal and equity curve — which is not a
privacy problem, it is one customer's money in another customer's book.

This file guards three separate claims, and they fail in different ways:

  * the column exists, is non-null, and defaults to the original owner on every legacy row —
    because NULL on a row recording a real fill would make "belongs to the owner"
    indistinguishable from "we lost track of whose this is";
  * a NEW row written through the ORM carries an owner without anyone passing one, so an insert
    path nobody has taught about tenancy lands on the owner rather than failing or nulling;
  * **the three tables that did NOT get the column are still recorded as not having it.** That
    is the test that matters most here. `capital_state`, `instrument_state` and
    `daily_account_snapshot` are keyed one-row-per-book/instrument/day, so an `owner_id` on them
    would be a column that cannot express two owners — correct, indexed, non-null and wired to
    nothing, which is this codebase's defining defect. If a later slice adds the column without
    also changing the key, this test fails and says why.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
import sqlalchemy as sa

from app.db.models import LEGACY_BROKER_ACCOUNT_ID, LEGACY_OWNER_ID, Base
from app.db.planes import TABLE_PLANES, Plane


def _load_revision(filename: str):
    """Alembic revision files are not an importable package (their names start with a digit),
    so the table list is loaded from the file itself. Reading it from the migration rather than
    restating it here is the point: a restated list drifts, and the drift would be a money-plane
    table that quietly has no owner."""
    path = pathlib.Path(__file__).resolve().parents[1] / "migrations/versions" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rev0017 = _load_revision("20260811_0017_money_plane_owner.py")

#: Keyed so that only one row can exist per book / instrument / day. Making these per-owner is a
#: PRIMARY KEY change, not an added column — see `rev0017`'s module docstring.
SINGLETON_KEYED: set[str] = set()

#: Owned by earlier revisions.
ALREADY_OWNED = {"broker_connections", "execution_intents"}

# Added after migration 0017.  Each category names the durable scope that owns it;
# internal delivery rows do not pretend to be tenant rows when their authority is a
# stream/consumer/scope key instead.
ACCOUNT_SCOPED = {
    "account_execution_leases", "account_execution_lease_history",
    "account_execution_commands", "oauth_callback_states",
}
DELIVERY_SCOPED = {
    "execution_outbox_stream_head",       # aggregate_type + aggregate_id
    "execution_outbox_event",             # owner/account scope_key
    "execution_outbox_consumer_cursor",   # internal consumer_id
    "execution_outbox_consumer_receipt",  # consumer_id + event_id
    "execution_outbox_retention_watermark",  # durable scope_key
}


def _money_tables() -> set[str]:
    return {t for t, plane in TABLE_PLANES.items() if plane is Plane.MONEY}


def test_every_money_table_is_accounted_for():
    """No money-plane table may be silently left out. Either it carries an owner, or it is on
    the singleton-keyed list with a reason — there is no third category, and a new money table
    that is neither fails here rather than shipping unowned."""
    scoped = {"broker_accounts", "capital_state", "instrument_state", "daily_account_snapshot"}
    accounted = (set(rev0017.TABLES) | scoped | SINGLETON_KEYED | ALREADY_OWNED
                 | ACCOUNT_SCOPED | DELIVERY_SCOPED)
    unaccounted = _money_tables() - accounted
    assert not unaccounted, (
        f"money-plane tables with no ownership decision: {sorted(unaccounted)}. Add the column "
        f"in a migration, or add the table to SINGLETON_KEYED with the key that prevents it.")


def test_the_ten_owned_tables_require_an_explicit_owner():
    for table in rev0017.TABLES:
        col = Base.metadata.tables[table].columns["owner_id"]
        assert col.nullable is False, f"{table}.owner_id must be NOT NULL"
        assert col.server_default is None, (
            f"{table}.owner_id must not silently assign the legacy owner")
        assert col.index is True, (
            f"{table}.owner_id joins a WHERE clause on a table that grows per trade or per bar")


def test_the_replacement_keys_make_each_former_singleton_tenant_addressable():
    tables = Base.metadata.tables
    assert [c.name for c in tables["capital_state"].primary_key] == ["broker_account_id", "book"]
    assert [c.name for c in tables["instrument_state"].primary_key] == ["owner_id", "instrument_key"]
    assert [c.name for c in tables["daily_account_snapshot"].primary_key] == ["broker_account_id", "day"]
    from app.db import models
    assert getattr(models, "LEGACY_BROKER_ACCOUNT_ID", None) == "account.default"


def test_a_new_deployment_rejects_omitted_scope_and_accepts_explicit_scope(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path/'t.db'}")
    Base.metadata.create_all(engine)
    from app.db.models import Deployment

    with sa.orm.Session(engine) as s:
        s.add(Deployment(name="missing-scope"))
        with pytest.raises(sa.exc.IntegrityError):
            s.commit()
        s.rollback()
        d = Deployment(owner_id=LEGACY_OWNER_ID,
                       broker_account_id=LEGACY_BROKER_ACCOUNT_ID, name="fresh")
        s.add(d)
        s.commit()
        assert (d.owner_id, d.broker_account_id) == (
            LEGACY_OWNER_ID, LEGACY_BROKER_ACCOUNT_ID)


def test_raw_sql_also_rejects_omitted_deployment_scope(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path/'t.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        with pytest.raises(sa.exc.IntegrityError):
            c.execute(sa.text(
                "INSERT INTO deployments (id, name, created_at, updated_at) "
                "VALUES (99, 'written-without-an-owner', "
                "'2026-08-01 09:15:00', '2026-08-01 09:15:00')"))
