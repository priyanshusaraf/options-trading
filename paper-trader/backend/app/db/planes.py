"""Which plane each table belongs to — ADR 0015, enforced rather than described.

The logical planes are distinguished by authority and recovery boundaries, not by what it costs to
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
    OPERATIONS = "operations"


#: Table name → plane. Total over `Base.metadata`; `tests/test_db_planes.py` fails the build on
#: any table missing from here, which is what stops the map decaying into a partial one.
TABLE_PLANES: dict[str, Plane] = {
    # Platform commerce, access, analytics, structured support and founder
    # operations are physically colocated but structurally blind to product
    # content and money/execution state. All relationships stay inside this set.
    "platform_plan_versions": Plane.OPERATIONS,
    "platform_coupon_definitions": Plane.OPERATIONS,
    "platform_coupon_redemptions": Plane.OPERATIONS,
    "platform_billing_bindings": Plane.OPERATIONS,
    "platform_billing_event_receipts": Plane.OPERATIONS,
    "platform_entitlement_events": Plane.OPERATIONS,
    "platform_current_entitlements": Plane.OPERATIONS,
    "platform_complimentary_entitlement_grants": Plane.OPERATIONS,
    "platform_analytics_subjects": Plane.OPERATIONS,
    "platform_analytics_events": Plane.OPERATIONS,
    "platform_support_requests": Plane.OPERATIONS,
    "platform_support_replies": Plane.OPERATIONS,
    "platform_operator_bindings": Plane.OPERATIONS,
    "platform_operator_audit_events": Plane.OPERATIONS,
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
    "execution_outbox_stream_head": Plane.MONEY,
    "execution_outbox_event": Plane.MONEY,
    "execution_outbox_consumer_cursor": Plane.MONEY,
    "execution_outbox_consumer_receipt": Plane.MONEY,
    "execution_outbox_retention_watermark": Plane.MONEY,
    # Phase 5 capital admission remains one money authority.  The first two rows are
    # immutable, content-addressed capital decisions; the remaining rows either carry
    # an explicit owner/account scope or inherit it through a money-plane parent.  Keeping
    # the complete chain together creates no new cross-plane foreign key and makes a future
    # physical money-plane copy/restore preserve the decisions with the facts they authorize.
    "sizing_policies": Plane.MONEY,
    "sizing_decisions": Plane.MONEY,
    "target_position_requests": Plane.MONEY,
    "candidate_intents": Plane.MONEY,
    "capital_reservation_heads": Plane.MONEY,
    "decision_batches": Plane.MONEY,
    "portfolio_admission_decisions": Plane.MONEY,
    "capital_reservations": Plane.MONEY,
    "capital_reservation_events": Plane.MONEY,
    "position_campaigns": Plane.MONEY,
    "position_tranches": Plane.MONEY,
    "fill_allocations": Plane.MONEY,
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
    "owner_provider_instrument_selections": Plane.USER,
    "static_instrument_scopes": Plane.USER,
    "static_instrument_scope_revisions": Plane.USER,
    "watchlist_monitoring_revisions": Plane.USER,
    "graph_artifacts": Plane.USER,
    "graph_versions": Plane.USER,
    "ir_v2_editor_presentations": Plane.USER,
    "chart_context_annotations": Plane.USER,
    "workspace_research_settings_revisions": Plane.USER,
    "strategy_research_settings_revisions": Plane.USER,
    "strategy_admissions": Plane.USER,
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
    "browser_credentials": Plane.USER,
    "enrollment_invites": Plane.USER,
    "browser_sessions": Plane.USER,
    "browser_auth_attempts": Plane.USER,
    # Privacy-minimised account attestations and prior-use facts are durable
    # owner-authored USER facts. Their only FKs remain within this plane.
    "account_profile_evidence": Plane.USER,
    "account_trial_uses": Plane.USER,
    # V0 monitoring is owner-authored evidence only. These tables intentionally
    # have no deployment, broker-account, execution, position or money link.
    "monitoring_assignments": Plane.USER,
    "monitoring_state_snapshots": Plane.USER,
    "monitoring_signal_events": Plane.USER,
    "monitoring_signal_alerts": Plane.USER,
    "monitoring_alert_delivery_attempts": Plane.USER,
    "monitoring_alert_attention_events": Plane.USER,
    "monitoring_latest_state": Plane.USER,
    "monitoring_alert_attention_state": Plane.USER,
    "monitoring_signal_reviews": Plane.USER,
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
    # ── Phase 4 authority chain: canonical, non-tenant, re-derivable ──
    # These are GLOBAL canonical facts, not tenant rows (no owner column by
    # design), so money-plane ownership accounting does not apply. The
    # execution-side copies are re-derivable from the research plane's
    # content-addressed admissions (FND-11's two-plane verification is exactly
    # that reconstruction), which makes them MARKET under this module's own
    # definition: losing them costs re-derivation and rate limit, never the
    # correctness of an already-admitted artifact. The one authored artifact —
    # ir_v2_graph_versions — is USER.
    "ir_v2_graph_versions": Plane.USER,   # irreplaceable authored graph versions
    "authority_canonical_instruments": Plane.MARKET,
    "authority_market_truth_snapshots": Plane.MARKET,
    "market_truth_snapshots": Plane.MARKET,
    "authority_missing_data_policies": Plane.MARKET,
    "authority_adjustment_policies": Plane.MARKET,
    "authority_alignment_policies": Plane.MARKET,
    "authority_roll_policies": Plane.MARKET,
    "authority_normalization_transforms": Plane.MARKET,
    "authority_raw_schemas": Plane.MARKET,
    "authority_normalized_observation_inputs": Plane.MARKET,
    "authority_normalized_observations": Plane.MARKET,
    "authority_raw_segments": Plane.MARKET,
    "authority_deterministic_algorithms": Plane.MARKET,
    "authority_dataset_creation_evidence": Plane.MARKET,
    "authority_dataset_corrections": Plane.MARKET,
    "authority_capability_profiles": Plane.MARKET,
    "market_data_capability_profiles": Plane.MARKET,
    "authority_capability_assessments": Plane.MARKET,
    "authority_provider_contracts": Plane.MARKET,
    "authority_provider_conformance": Plane.MARKET,
    # REVERTED 2026-08-22: a loss-review reclassification to MONEY was tried
    # inside the PostgreSQL-isolation correction and reverted on review — it
    # expanded ADR 0015's grandfather list, which requires its own architecture
    # capsule. The loss concern is real (owner-scoped accepted evidence:
    # creation evidence, corrections, capability assessments, provider
    # contracts/conformance) and is recorded as a pending architecture
    # decision; until that capsule lands, these keep their pre-correction
    # MARKET assignments.
    # Provider catalog: contracts/observations/aliases all resolve THROUGH
    # products/entities/canonical-instruments, so any catalog split would
    # manufacture cross-plane crossings inside one authority domain.
    "authority_provider_entities": Plane.MARKET,
    "authority_provider_products": Plane.MARKET,
    "authority_provider_aliases": Plane.MARKET,
    "authority_provider_observations": Plane.MARKET,
    # Isolated pair: today's instrument master + its provider mapping. Nothing
    # on the money plane references them; they are re-fetchable dumps.
    "market_truth_instruments": Plane.MARKET,
    "market_truth_provider_mappings": Plane.MARKET,
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
