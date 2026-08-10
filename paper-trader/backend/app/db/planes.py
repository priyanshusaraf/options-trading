"""Which plane each table belongs to — ADR 0015, enforced rather than described.

The three planes are distinguished by **what it costs to lose them**, not by what it costs to
serve them:

  * **MARKET** — re-fetchable. Losing it costs money and rate limit, never correctness.
  * **USER** — irreplaceable creative work. Graphs, research, notes.
  * **MONEY** — legally significant. Ledger, fills, attribution, and broker connections.

Today all three live in one SQLite file, and ADR 0014's topology trigger (multi-host execution
workers) has not fired. So this module is a **logical** boundary, and its whole value is that it
is checkable now, while the schema is still small enough to classify honestly. Two rules:

  1. **Every table is assigned, and a new one with no assignment fails the build.** Classifying
     forty tables under incident pressure is how the money plane ends up holding a cache.
  2. **No foreign key crosses a plane boundary.** This is the constraint that makes the eventual
     physical split an operation rather than a rewrite. Cross-plane references are by value — a
     scope string, a content address — never by FK.

Being wrong about one table's plane is cheap to correct precisely *because* of rule 2: a table
with no incoming cross-plane foreign keys can be moved. That is why accepting this now is not
premature, and why the cost of delay is real: every unassigned table added is one more to
classify later, under worse conditions.
"""
from __future__ import annotations

import enum


class Plane(str, enum.Enum):
    MARKET = "market"
    USER = "user"
    MONEY = "money"


#: Table name → plane. Total over `Base.metadata`; `tests/test_db_planes.py` fails the build on
#: any table missing from here, which is what stops the map decaying into a partial one.
TABLE_PLANES: dict[str, Plane] = {
    # ── money: the ledger and everything that decides or records a real trade ──
    "deployments": Plane.MONEY,
    "execution_intents": Plane.MONEY,
    "execution_order_events": Plane.MONEY,
    "capital_state": Plane.MONEY,
    "instrument_state": Plane.MONEY,
    "positions": Plane.MONEY,
    "trades": Plane.MONEY,
    "equity_snapshots": Plane.MONEY,
    "order_journal": Plane.MONEY,
    "daily_account_snapshot": Plane.MONEY,
    "signal_events": Plane.MONEY,
    # Signals are money-plane because attribution is: "which binding authored this trade" is
    # answered by joining a fill back to the signal that caused it, and that join must not
    # cross a plane.
    "ir_shadow_divergences": Plane.MONEY,
    "ir_shadow_deployments": Plane.MONEY,
    "ir_paper_deployments": Plane.MONEY,
    "broker_connections": Plane.MONEY,
    # ADR 0015 §2: a connection is money-plane on BLAST RADIUS, not on recovery cost. A row
    # here is the authority to place real orders on a real account. The encryption key is not
    # in any plane — it comes from the environment, so a database compromise alone is not a
    # credential compromise.
    #
    # **KNOWN GAP — the owner dimension stops here.** `broker_connections` is the only
    # money-plane table with an `owner_id`. `deployments` and `execution_intents` have none, and
    # `execution_lifecycle.unresolved_entries` recovers live entries on
    # `(deployment_id, account_scope, connection_scope)` with no owner in the predicate.
    #
    # `(owner_id, scope)` being unique rather than `scope` — deliberate, and correct — means two
    # owners may both legitimately hold `kite:legacy`. That is the collision the recovery query
    # cannot currently disambiguate, and `providers/connection.py` calls that outcome "a silent
    # cross-account mix — the worst available failure" while solving it only for the second
    # *connection*, not the second *owner*.
    #
    # Not reachable today: one owner, one deployment, and no route creates a second owner. But
    # the constraint that PERMITS the collision shipped before the query that must handle it,
    # which is the wrong order. Found by an independent security review, 2026-08-10. Fixing it
    # is an owner column across the money plane plus a recovery-predicate change — a reviewed
    # slice of its own, and a prerequisite for onboarding a second owner. Recorded in
    # WS-02 §5 rather than patched here.

    # ── user: irreplaceable creative work ──
    "projects": Plane.USER,
    "graph_artifacts": Plane.USER,
    "graph_versions": Plane.USER,
    "ir_graph_layouts": Plane.USER,
    "ir_graph_layout_positions": Plane.USER,
    "ir_graph_layout_groups": Plane.USER,
    "ir_graph_layout_group_members": Plane.USER,
    "ir_graph_layout_orphan_archive": Plane.USER,
    "ir_graph_layout_position_orphan_archive": Plane.USER,
    "project_review_notes": Plane.USER,
    "project_review_saved_views": Plane.USER,
    "project_review_snapshots": Plane.USER,
    "watchlists": Plane.USER,
    "watchlist_membership": Plane.USER,
    "strategy_lifecycle": Plane.USER,
    "generated_strategies": Plane.USER,
    "runtime_config": Plane.USER,
    # `runtime_config` is a genuinely awkward one and is called out rather than smoothed over:
    # its rows are the owner's hand-set trading decisions, so they *behave* like money, but
    # losing one restores a documented code default rather than corrupting a ledger. It is
    # settings, and settings are user-plane.

    # ── market: re-fetchable, and never on the money plane's failure domain ──
    "universe_instruments": Plane.MARKET,
    "option_data": Plane.MARKET,
    "earnings_events": Plane.MARKET,
    "backtest_runs": Plane.MARKET,
    "backtest_results": Plane.MARKET,
    # Backtests are market-plane because they are *derived* — reproducible from the graph
    # version and the dataset, both of which live elsewhere. They are also by far the largest
    # table set, which is exactly why they must not share a failure domain with the ledger.
}


#: Foreign keys that ALREADY cross a plane boundary, enumerated as of 2026-08-10.
#:
#: ADR 0015 §3 states "no foreign key crosses a plane boundary". Writing the check revealed that
#: the schema already violated it seven times — which is the finding, not a reason to weaken the
#: rule. All seven are the same shape: a money-plane deployment referencing the user-plane
#: artefact it runs. That is the "results bind to the versions that produced them" invariant
#: expressed as a foreign key, so the relationships are correct; only their *enforcement
#: mechanism* is the problem.
#:
#: So this is a **ratchet, not an exemption**: these seven are grandfathered and every new one
#: fails the build. The list is the honest price of the physical split — seven constraints to
#: convert from foreign keys to by-value references — and it is countable here rather than
#: discovered during the migration.
#:
#: Removing an entry when its FK is converted is the intended direction. Adding one requires
#: saying why in the ADR.
GRANDFATHERED_CROSS_PLANE_FKS: frozenset[tuple[str, str]] = frozenset({
    ("deployments", "watchlist_id"),
    ("ir_paper_deployments", "graph_version"),
    ("ir_paper_deployments", "graph_identifier"),
    ("ir_paper_deployments", "project_id"),
    ("ir_shadow_deployments", "graph_identifier"),
    ("ir_shadow_deployments", "graph_version"),
    ("ir_shadow_deployments", "project_id"),
})


def plane_of(table: str) -> Plane:
    try:
        return TABLE_PLANES[table]
    except KeyError:
        raise UnassignedTable(
            f"table {table!r} has no plane. Assign it in app/db/planes.py — a table with no "
            f"plane has no stated durability requirement, which means it silently inherits the "
            f"weakest one available.") from None


class UnassignedTable(LookupError):
    """A table exists with no plane. Deliberately loud: see `plane_of`."""


def tables_in(plane: Plane) -> frozenset[str]:
    return frozenset(t for t, p in TABLE_PLANES.items() if p is plane)
