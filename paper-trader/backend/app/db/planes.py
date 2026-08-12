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
    "oauth_callback_states": Plane.MONEY,
    "broker_accounts": Plane.MONEY,
    "account_execution_leases": Plane.MONEY,
    "account_execution_lease_history": Plane.MONEY,
    "account_execution_commands": Plane.MONEY,
    # ADR 0015 §2: a connection is money-plane on BLAST RADIUS, not on recovery cost. A row
    # here is the authority to place real orders on a real account. The encryption key is not
    # in any plane — it comes from the environment, so a database compromise alone is not a
    # credential compromise.
    #
    # Every account-specific table in this plane carries both the organization owner and the
    # durable Strategy OS broker-account identity.  Broker/external labels remain observations;
    # they are never repository boundaries.  This is what lets two owners use identical broker,
    # connection-scope and external-account strings without lifecycle recovery crossing tenants.

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
    "organizations": Plane.USER,
    "users": Plane.USER,
    "memberships": Plane.USER,
    "user_sessions": Plane.USER,
    # `runtime_config` is a genuinely awkward one and is called out rather than smoothed over:
    # its rows are the owner's hand-set trading decisions, so they *behave* like money, but
    # losing one restores a documented code default rather than corrupting a ledger. It is
    # settings, and settings are user-plane.

    # ── market: re-fetchable, and never on the money plane's failure domain ──
    "universe_instruments": Plane.MARKET,
    "universe_preferences": Plane.USER,
    "option_data": Plane.MARKET,
    "earnings_events": Plane.MARKET,
    # Raw candles are MARKET. A durable run/result records private strategy work and is USER.
    "backtest_runs": Plane.USER,
    "backtest_results": Plane.USER,
    "backtest_computations": Plane.MARKET,
}


#: Foreign keys that ALREADY cross a plane boundary, enumerated as of 2026-08-10.
#:
#: ADR 0015 §3 states "no foreign key crosses a plane boundary". Writing the check revealed
#: existing crossings — which is the finding, not a reason to weaken the rule. They include the
#: money-plane deployment provenance links, the short-lived OAuth capability's membership/session
#: links, and an owner preference's reference to canonical market data. The relationships are
#: correct; only their *enforcement mechanism* blocks a physical split.
#:
#: So this is a **ratchet, not an exemption**: these six are grandfathered and every new one
#: fails the build. The list is the honest price of the physical split — six constraints to
#: convert from foreign keys to by-value references — and it is countable here rather than
#: discovered during the migration.
#:
#: Removing an entry when its FK is converted is the intended direction. Adding one requires
#: saying why in the ADR.
GRANDFATHERED_CROSS_PLANE_FKS: frozenset[tuple[str, str]] = frozenset({
    ("ir_paper_deployments", "project_id"),
    ("ir_shadow_deployments", "project_id"),
    ("oauth_callback_states", "organization_id"),
    ("oauth_callback_states", "user_id"),
    ("oauth_callback_states", "session_id"),
    ("universe_preferences", "instrument_key"),
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
