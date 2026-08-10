"""ADR 0015's plane rules, enforced rather than described.

A plane map in a document is a decision. A plane map nothing checks is a decision that decays,
and it decays silently — the way you find out is during the migration you wrote it to make
possible.

Two rules, and the second is the one that carries the cost:

  1. Every table is assigned. A new one with no plane has no stated durability requirement, so
     it inherits the weakest available.
  2. No foreign key crosses a plane boundary. This is what makes the eventual physical split an
     operation rather than a rewrite — and it is the reason being wrong about one table's plane
     is cheap to correct, which is in turn why accepting ADR 0015 now is not premature.
"""
from __future__ import annotations

import pytest

from app.db.models import Base
from app.db.planes import (
    GRANDFATHERED_CROSS_PLANE_FKS as GRANDFATHERED,
    TABLE_PLANES,
    Plane,
    UnassignedTable,
    plane_of,
    tables_in,
)


def test_every_table_has_a_plane():
    """Enumerated from the metadata, not from a hand-written list. A hardcoded list passes
    vacuously on exactly the tables it was written for."""
    missing = sorted(set(Base.metadata.tables) - set(TABLE_PLANES))
    assert not missing, (
        f"these tables have no plane: {missing}. Assign them in app/db/planes.py. Classifying "
        f"forty tables under incident pressure is how the money plane ends up holding a cache.")


def test_the_map_has_no_tables_that_do_not_exist():
    """A stale entry is not harmless: it makes `tables_in(MONEY)` name something the physical
    split would then look for and not find."""
    stale = sorted(set(TABLE_PLANES) - set(Base.metadata.tables))
    assert not stale, f"planes.py names tables that do not exist: {stale}"


def test_no_foreign_key_crosses_a_plane_boundary():
    """The constraint that makes the split an operation rather than a rewrite.

    Cross-plane references are by VALUE — a scope string, a content address — never by FK.
    `execution_intents.connection_scope` is the worked example: it points at a broker connection
    without a foreign key, deliberately, because an intent must survive the deletion of the
    connection that authored it. A live order whose connection row is gone is still a live
    order.

    A **ratchet**: seven pre-existing crossings are grandfathered in `GRANDFATHERED_CROSS_PLANE_FKS`
    and every new one fails here. Writing this check is what found them — the schema violated the
    rule before the rule was written down, which is the ordinary case and not a reason to soften it.
    """
    crossings = []
    for table in Base.metadata.tables.values():
        here = plane_of(table.name)
        for fk in table.foreign_keys:
            target = fk.column.table.name
            there = plane_of(target)
            if there is not here and (table.name, fk.parent.name) not in GRANDFATHERED:
                crossings.append(
                    f"{table.name}({here.value}) -> {target}({there.value}) "
                    f"via {fk.parent.name}")
    assert not crossings, (
        "foreign keys cross a plane boundary:\n  " + "\n  ".join(crossings) +
        "\nEither the plane assignment is wrong, or the reference must be by value.")


def test_the_money_plane_holds_the_ledger_and_the_credentials():
    """The specific claims ADR 0015 makes, pinned. If someone later moves `broker_connections`
    to the user plane on recovery-cost grounds, this fails and they have to say so in the ADR
    rather than in a commit."""
    money = tables_in(Plane.MONEY)
    for table in ("positions", "trades", "capital_state", "execution_intents",
                  "execution_order_events", "broker_connections"):
        assert table in money, f"{table} must be money-plane (ADR 0015 §1, §2)"


def test_the_market_plane_holds_nothing_whose_loss_is_permanent():
    """Market-plane data is defined by being re-fetchable. A table here whose loss is permanent
    is a mis-assignment, and the consequence is that it gets the cheapest durability in the
    system."""
    market = tables_in(Plane.MARKET)
    for table in ("positions", "trades", "graph_versions", "projects", "broker_connections"):
        assert table not in market, f"{table} is not re-fetchable and cannot be market-plane"


def test_an_unassigned_table_is_a_loud_lookup_failure():
    with pytest.raises(UnassignedTable) as e:
        plane_of("a_table_nobody_classified")
    assert "planes.py" in str(e.value)


def test_the_three_planes_are_all_populated():
    """A plane with no tables means the split is notional. All three carrying real tables is
    what makes rule 2 a constraint rather than a tautology."""
    for plane in Plane:
        assert tables_in(plane), f"the {plane.value} plane is empty"


def test_the_grandfathered_crossings_are_all_real():
    """Guard the ratchet. A stale entry silently widens the exemption: it would permit a NEW
    crossing that happened to reuse the same (table, column) pair, and nothing would say so."""
    actual = set()
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            if plane_of(fk.column.table.name) is not plane_of(table.name):
                actual.add((table.name, fk.parent.name))
    stale = sorted(GRANDFATHERED - actual)
    assert not stale, (
        f"these crossings no longer exist and must be removed from "
        f"GRANDFATHERED_CROSS_PLANE_FKS: {stale}. Shrinking that set is the intended "
        f"direction; leaving dead entries in it re-opens the gate.")


def test_every_grandfathered_crossing_points_from_money_to_user():
    """All seven are the same shape — a money-plane deployment referencing the user-plane
    artefact it runs. If a NEW shape ever appears here (say, money -> market), that is a
    different and more serious problem than the debt this set records."""
    for table, column in GRANDFATHERED:
        assert plane_of(table) is Plane.MONEY, (table, column)
