"""Every money-plane table has one explicit, content-addressed, or parent scope.

`0015` and `0016` made the *authority* to trade per-owner: a broker connection and an execution
intent both know whose they are. What the orders PRODUCE did not. A second owner would have
shared the first owner's positions, trades, order journal and equity curve — which is not a
privacy problem, it is one customer's money in another customer's book.

This file guards four separate claims, and they fail in different ways:

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
    also changing the key, this test fails and says why;
  * Phase 5's capital facts form three deliberate ownership categories: global immutable
    content addresses, explicit owner/account rows, and facts scoped through a money parent.
    A table omitted from or duplicated across those categories fails the totality ratchet.
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

#: Owner columns added by the migration whose list is loaded above.
MIGRATION_0017_OWNED = frozenset(rev0017.TABLES)

#: Durable identity or replacement-key scoped rows.
KEY_SCOPED = frozenset({
    "broker_accounts", "capital_state", "instrument_state", "daily_account_snapshot",
})

#: Owned by earlier revisions.
ALREADY_OWNED = frozenset({"broker_connections", "execution_intents"})

# Added after migration 0017.  Each category names the durable scope that owns it;
# internal delivery rows do not pretend to be tenant rows when their authority is a
# stream/consumer/scope key instead.
ACCOUNT_SCOPED = frozenset({
    "account_execution_leases", "account_execution_lease_history",
    "account_execution_commands", "oauth_callback_states",
})
DELIVERY_SCOPED = frozenset({
    "execution_outbox_stream_head",       # aggregate_type + aggregate_id
    "execution_outbox_event",             # owner/account scope_key
    "execution_outbox_consumer_cursor",   # internal consumer_id
    "execution_outbox_consumer_receipt",  # consumer_id + event_id
    "execution_outbox_retention_watermark",  # durable scope_key
})

# Phase 5 capital ownership. These three categories are the accepted architecture
# decision recorded by phase5-integration-evidence-recovery-replan.
GLOBAL_CONTENT_ADDRESSED = frozenset({"sizing_policies", "sizing_decisions"})
EXPLICIT_ACCOUNT_SCOPED = frozenset({
    "target_position_requests",
    "candidate_intents",
    "capital_reservation_heads",
    "decision_batches",
    "capital_reservations",
    "position_campaigns",
})
PARENT_SCOPED = frozenset({
    "portfolio_admission_decisions",
    "capital_reservation_events",
    "position_tranches",
    "fill_allocations",
})

OWNERSHIP_CATEGORIES = {
    "migration_0017": MIGRATION_0017_OWNED,
    "key_scoped": KEY_SCOPED,
    "already_owned": ALREADY_OWNED,
    "account_scoped": ACCOUNT_SCOPED,
    "delivery_scoped": DELIVERY_SCOPED,
    "global_content_addressed": GLOBAL_CONTENT_ADDRESSED,
    "explicit_account_scoped": EXPLICIT_ACCOUNT_SCOPED,
    "parent_scoped": PARENT_SCOPED,
}


def _money_tables() -> set[str]:
    return {t for t, plane in TABLE_PLANES.items() if plane is Plane.MONEY}


def test_every_money_table_has_exactly_one_ownership_decision():
    """The category partition is total, disjoint, and contains no stale non-money table."""
    money_tables = _money_tables()
    accounted = set().union(*OWNERSHIP_CATEGORIES.values())
    memberships = {
        table: sorted(name for name, tables in OWNERSHIP_CATEGORIES.items() if table in tables)
        for table in accounted | money_tables
    }
    invalid = {table: categories for table, categories in memberships.items()
               if table not in money_tables or len(categories) != 1}
    assert accounted == money_tables and not invalid, (
        f"money ownership accounting is not a partition; "
        f"missing={sorted(money_tables - accounted)}, "
        f"stale={sorted(accounted - money_tables)}, invalid={invalid}"
    )


def test_global_capital_facts_are_content_addressed_primary_keys():
    expected_keys = {
        "sizing_policies": ["policy_address"],
        "sizing_decisions": ["decision_address"],
    }
    for table_name, expected_key in expected_keys.items():
        table = Base.metadata.tables[table_name]
        assert [column.name for column in table.primary_key] == expected_key
        assert "owner_id" not in table.c and "broker_account_id" not in table.c


def test_explicit_capital_facts_require_their_complete_account_scope():
    expected_scope = {
        "target_position_requests": ("owner_id", "broker_account_id", "book"),
        "candidate_intents": ("owner_id", "broker_account_id", "book", "currency"),
        "capital_reservation_heads": ("owner_id", "broker_account_id", "book", "currency"),
        "decision_batches": ("owner_id", "broker_account_id", "book", "currency"),
        "capital_reservations": ("owner_id", "broker_account_id", "book", "currency"),
        "position_campaigns": ("owner_id", "broker_account_id", "book"),
    }
    assert set(expected_scope) == set(EXPLICIT_ACCOUNT_SCOPED)
    for table_name, columns in expected_scope.items():
        table = Base.metadata.tables[table_name]
        assert all(column in table.c and not table.c[column].nullable for column in columns)


def test_parent_scoped_capital_facts_have_money_plane_ownership_paths():
    expected_parents = {
        "portfolio_admission_decisions": {"decision_batches", "candidate_intents"},
        "capital_reservation_events": {"capital_reservations"},
        "position_tranches": {"position_campaigns"},
        "fill_allocations": {"position_tranches", "execution_order_events"},
    }
    assert set(expected_parents) == set(PARENT_SCOPED)
    for table_name, required_parents in expected_parents.items():
        table = Base.metadata.tables[table_name]
        actual_parents = {fk.column.table.name for fk in table.foreign_keys}
        assert required_parents <= actual_parents
        assert all(TABLE_PLANES[parent] is Plane.MONEY for parent in actual_parents)
        assert "owner_id" not in table.c and "broker_account_id" not in table.c


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
