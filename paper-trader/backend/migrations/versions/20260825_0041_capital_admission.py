"""Add sizing, target, capital admission and position-lineage facts.

Revision ID: 0041
Revises: 0040
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def _address(column: str, dialect: str, *, nullable: bool = False) -> str:
    prefix = f"{column} IS NULL OR " if nullable else ""
    if dialect == "postgresql":
        return prefix + f"{column} ~ '^sha256:[0-9a-f]{{64}}$'"
    return prefix + (
        f"(length({column}) = 71 AND substr({column},1,7) = 'sha256:' AND "
        f"substr({column},8) = lower(substr({column},8)) AND "
        f"substr({column},8) NOT GLOB '*[^0-9a-f]*')")


def _digest(column: str, dialect: str) -> str:
    if dialect == "postgresql":
        return f"char_length({column}) = 64 AND {column} ~ '^[0-9a-f]{{64}}$'"
    return (f"length({column}) = 64 AND {column} = lower({column}) AND "
            f"{column} NOT GLOB '*[^0-9a-f]*'")


def _json(column: str, dialect: str) -> str:
    return (f"CAST({column} AS JSONB) IS NOT NULL" if dialect == "postgresql"
            else f"json_valid({column})")


def _create(name: str, columns: list, constraints: list) -> None:
    bind = op.get_bind()
    existing = sa.inspect(bind).has_table(name)
    expected = {item.name for item in columns}
    if existing:
        actual = {item["name"] for item in sa.inspect(bind).get_columns(name)}
        if actual != expected:
            raise RuntimeError(
                f"0041 refuses partial/stale table {name}: actual={sorted(actual)} "
                f"expected={sorted(expected)}")
        return
    op.create_table(name, *columns, *constraints)


def _account_fk(name: str, *, fields=("owner_id", "broker_account_id")):
    return sa.ForeignKeyConstraint(
        fields, ("broker_accounts.owner_id", "broker_accounts.broker_account_id"),
        name=name, ondelete="RESTRICT")


def _attribution_columns() -> list[sa.Column]:
    return [
        sa.Column("strategy_key", sa.String(64), nullable=True),
        sa.Column("strategy_version", sa.String(128), nullable=True),
        sa.Column("admission_address", sa.String(71), nullable=True),
        sa.Column("graph_address", sa.String(71), nullable=True),
        sa.Column("attribution_state", sa.String(24), nullable=False),
    ]


def _create_tables(dialect: str) -> None:
    _create("sizing_policies", [
        sa.Column("policy_address", sa.String(71), primary_key=True),
        sa.Column("policy_id", sa.String(96), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("fixed_units", sa.Integer(), nullable=True),
        sa.Column("fixed_lots", sa.Integer(), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("rate_ppm", sa.Integer(), nullable=True),
        sa.Column("risk_budget_minor", sa.BigInteger(), nullable=True),
        sa.Column("target_volatility_ppm", sa.Integer(), nullable=True),
        sa.Column("min_quantity", sa.Integer(), nullable=False),
        sa.Column("max_quantity", sa.Integer(), nullable=True),
        sa.Column("max_capital_minor", sa.BigInteger(), nullable=True),
        sa.Column("fee_buffer_minor", sa.BigInteger(), nullable=False),
        sa.Column("safety_buffer_minor", sa.BigInteger(), nullable=False),
        sa.Column("allow_resize", sa.Boolean(), nullable=False),
        sa.Column("canonical_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    ], [
        sa.CheckConstraint(_address("policy_address", dialect),
                           name="ck_sizing_policies_address"),
        sa.CheckConstraint(
            "mode IN ('FIXED_UNITS','FIXED_LOTS','FIXED_CAPITAL','CAPITAL_PCT',"
            "'EQUITY_PCT','RISK_STOP','VOLATILITY_TARGET')",
            name="ck_sizing_policies_mode"),
        sa.CheckConstraint("currency = upper(currency) AND length(currency) = 3",
                           name="ck_sizing_policies_currency"),
        sa.CheckConstraint("version > 0 AND min_quantity > 0",
                           name="ck_sizing_policies_positive"),
        sa.CheckConstraint(_json("canonical_json", dialect),
                           name="ck_sizing_policies_canonical_json"),
        sa.CheckConstraint(
            "fee_buffer_minor >= 0 AND safety_buffer_minor >= 0 AND "
            "(max_quantity IS NULL OR max_quantity >= min_quantity) AND "
            "(max_capital_minor IS NULL OR max_capital_minor > 0)",
            name="ck_sizing_policies_caps"),
        sa.CheckConstraint(
            "(mode = 'FIXED_UNITS' AND fixed_units > 0 AND fixed_lots IS NULL AND "
            "amount_minor IS NULL AND rate_ppm IS NULL AND risk_budget_minor IS NULL AND "
            "target_volatility_ppm IS NULL) OR "
            "(mode = 'FIXED_LOTS' AND fixed_lots > 0 AND fixed_units IS NULL AND "
            "amount_minor IS NULL AND rate_ppm IS NULL AND risk_budget_minor IS NULL AND "
            "target_volatility_ppm IS NULL) OR "
            "(mode = 'FIXED_CAPITAL' AND amount_minor > 0 AND fixed_units IS NULL AND "
            "fixed_lots IS NULL AND rate_ppm IS NULL AND risk_budget_minor IS NULL AND "
            "target_volatility_ppm IS NULL) OR "
            "(mode IN ('CAPITAL_PCT','EQUITY_PCT') AND rate_ppm > 0 AND rate_ppm <= 1000000 "
            "AND fixed_units IS NULL AND fixed_lots IS NULL AND amount_minor IS NULL AND "
            "risk_budget_minor IS NULL AND target_volatility_ppm IS NULL) OR "
            "(mode = 'RISK_STOP' AND risk_budget_minor > 0 AND fixed_units IS NULL AND "
            "fixed_lots IS NULL AND amount_minor IS NULL AND rate_ppm IS NULL AND "
            "target_volatility_ppm IS NULL) OR "
            "(mode = 'VOLATILITY_TARGET' AND target_volatility_ppm > 0 AND "
            "target_volatility_ppm <= 1000000 AND fixed_units IS NULL AND fixed_lots IS NULL "
            "AND amount_minor IS NULL AND rate_ppm IS NULL AND risk_budget_minor IS NULL)",
            name="ck_sizing_policies_primary_mode"),
    ])

    _create("sizing_decisions", [
        sa.Column("decision_address", sa.String(71), primary_key=True),
        sa.Column("policy_address", sa.String(71), nullable=False),
        sa.Column("product_address", sa.String(71), nullable=False),
        sa.Column("inputs_address", sa.String(71), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("admitted_quantity", sa.Integer(), nullable=False),
        sa.Column("required_capital_minor", sa.BigInteger(), nullable=False),
        sa.Column("estimated_fees_minor", sa.BigInteger(), nullable=False),
        sa.Column("binding_constraint", sa.String(64), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("resized", sa.Boolean(), nullable=False),
        sa.Column("input_addresses_json", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
    ], [
        sa.ForeignKeyConstraint(("policy_address",), ("sizing_policies.policy_address",),
                                name="fk_sizing_decisions_policy", ondelete="RESTRICT"),
        sa.CheckConstraint(_address("decision_address", dialect),
                           name="ck_sizing_decisions_address"),
        sa.CheckConstraint(_address("product_address", dialect),
                           name="ck_sizing_decisions_product"),
        sa.CheckConstraint(_address("inputs_address", dialect),
                           name="ck_sizing_decisions_inputs"),
        sa.CheckConstraint("requested_quantity >= 0 AND admitted_quantity >= 0",
                           name="ck_sizing_decisions_quantity"),
        sa.CheckConstraint("required_capital_minor >= 0 AND estimated_fees_minor >= 0",
                           name="ck_sizing_decisions_money"),
        sa.CheckConstraint("(accepted AND admitted_quantity > 0) OR "
                           "(NOT accepted AND admitted_quantity = 0)",
                           name="ck_sizing_decisions_outcome"),
        sa.CheckConstraint(_json("input_addresses_json", dialect),
                           name="ck_sizing_decisions_inputs_json"),
    ])

    _create("target_position_requests", [
        sa.Column("request_id", sa.String(64), primary_key=True),
        sa.Column("request_address", sa.String(71), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("book", sa.String(8), nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        *_attribution_columns(),
        sa.Column("canonical_instrument_key", sa.String(64), nullable=False),
        sa.Column("product_address", sa.String(71), nullable=False),
        sa.Column("sizing_decision_address", sa.String(71), nullable=False),
        sa.Column("target_quantity", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("group_id", sa.String(64), nullable=False),
        sa.Column("decision_at", sa.DateTime(), nullable=False),
    ], [
        _account_fk("fk_target_requests_account"),
        sa.ForeignKeyConstraint(("deployment_id",), ("deployments.id",),
                                name="fk_target_requests_deployment", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("sizing_decision_address",),
                                ("sizing_decisions.decision_address",),
                                name="fk_target_requests_sizing", ondelete="RESTRICT"),
        sa.UniqueConstraint("request_address", name="uq_target_requests_address"),
        sa.CheckConstraint(_address("request_address", dialect),
                           name="ck_target_requests_address"),
        sa.CheckConstraint(_address("product_address", dialect),
                           name="ck_target_requests_product"),
        sa.CheckConstraint(_address("admission_address", dialect, nullable=True),
                           name="ck_target_position_requests_admission_address"),
        sa.CheckConstraint("book IN ('paper','live')", name="ck_target_requests_book"),
        sa.CheckConstraint("purpose IN ('ENTRY','TARGET_ADJUSTMENT','RISK_REDUCTION')",
                           name="ck_target_requests_purpose"),
    ])

    _create("candidate_intents", [
        sa.Column("candidate_intent_id", sa.String(64), primary_key=True),
        sa.Column("candidate_address", sa.String(71), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("book", sa.String(8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("fence_epoch", sa.Integer(), nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        *_attribution_columns(),
        sa.Column("signal_instrument_key", sa.String(64), nullable=False),
        sa.Column("execution_instrument_key", sa.String(96), nullable=False),
        sa.Column("product_address", sa.String(71), nullable=False),
        sa.Column("sizing_decision_address", sa.String(71), nullable=False),
        sa.Column("target_position_request_id", sa.String(64), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("required_capital_minor", sa.BigInteger(), nullable=False),
        sa.Column("group_id", sa.String(64), nullable=False),
        sa.Column("group_semantics", sa.String(16), nullable=False),
        sa.Column("freshness_deadline", sa.DateTime(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("score_scaled", sa.BigInteger(), nullable=False),
        sa.Column("rank_json", sa.Text(), nullable=False),
        sa.Column("held_pending_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    ], [
        _account_fk("fk_candidate_intents_account"),
        sa.ForeignKeyConstraint(("deployment_id",), ("deployments.id",),
                                name="fk_candidate_intents_deployment", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("sizing_decision_address",),
                                ("sizing_decisions.decision_address",),
                                name="fk_candidate_intents_sizing", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("target_position_request_id",),
                                ("target_position_requests.request_id",),
                                name="fk_candidate_intents_target", ondelete="RESTRICT"),
        sa.UniqueConstraint("candidate_address", name="uq_candidate_intents_address"),
        sa.CheckConstraint(_address("candidate_address", dialect),
                           name="ck_candidate_address"),
        sa.CheckConstraint(_address("product_address", dialect),
                           name="ck_candidate_product"),
        sa.CheckConstraint(_address("admission_address", dialect, nullable=True),
                           name="ck_candidate_intents_admission_address"),
        sa.CheckConstraint(_digest("held_pending_digest", dialect),
                           name="ck_candidate_pending_digest"),
        sa.CheckConstraint(_json("rank_json", dialect), name="ck_candidate_rank_json"),
        sa.CheckConstraint("book IN ('paper','live') AND currency = upper(currency) "
                           "AND length(currency) = 3", name="ck_candidate_book_currency"),
        sa.CheckConstraint("fence_epoch > 0 AND requested_quantity <> 0 "
                           "AND required_capital_minor >= 0", name="ck_candidate_numeric"),
        sa.CheckConstraint("direction IN ('LONG','SHORT')", name="ck_candidate_direction"),
        sa.CheckConstraint("purpose IN ('ENTRY','TARGET_ADJUSTMENT','RISK_REDUCTION')",
                           name="ck_candidate_purpose"),
        sa.CheckConstraint("group_semantics IN ('INDEPENDENT','ATOMIC','RESIZABLE')",
                           name="ck_candidate_group"),
    ])

    _create("capital_reservation_heads", [
        sa.Column("owner_id", sa.String(64), primary_key=True),
        sa.Column("broker_account_id", sa.String(64), primary_key=True),
        sa.Column("book", sa.String(8), primary_key=True),
        sa.Column("currency", sa.String(3), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ], [
        _account_fk("fk_capital_reservation_heads_account"),
        sa.CheckConstraint("book IN ('paper','live') AND currency = upper(currency) "
                           "AND length(currency) = 3", name="ck_reservation_heads_scope"),
        sa.CheckConstraint("revision >= 0", name="ck_reservation_heads_revision"),
    ])

    _create("decision_batches", [
        sa.Column("decision_batch_id", sa.String(64), primary_key=True),
        sa.Column("batch_address", sa.String(71), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("book", sa.String(8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("fence_epoch", sa.Integer(), nullable=False),
        sa.Column("decision_at", sa.DateTime(), nullable=False),
        sa.Column("effective_at", sa.DateTime(), nullable=False),
        sa.Column("capital_snapshot_address", sa.String(71), nullable=False),
        sa.Column("margin_available_minor", sa.BigInteger(), nullable=False),
        sa.Column("margin_source", sa.String(64), nullable=False),
        sa.Column("margin_observed_at", sa.DateTime(), nullable=False),
        sa.Column("margin_snapshot_address", sa.String(71), nullable=False),
        sa.Column("active_reservation_minor", sa.BigInteger(), nullable=False),
        sa.Column("safety_buffer_minor", sa.BigInteger(), nullable=False),
        sa.Column("reservation_head_revision", sa.Integer(), nullable=False),
        sa.Column("product_policy_address", sa.String(71), nullable=False),
        sa.Column("sizing_policy_address", sa.String(71), nullable=False),
        sa.Column("portfolio_policy_address", sa.String(71), nullable=False),
        sa.Column("candidate_set_digest", sa.String(64), nullable=False),
        sa.Column("contention_policy", sa.String(64), nullable=False),
        sa.Column("tie_break_policy", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("refusal_reason", sa.String(200), nullable=False),
    ], [
        sa.ForeignKeyConstraint(
            ("owner_id", "broker_account_id", "book", "currency"),
            ("capital_reservation_heads.owner_id", "capital_reservation_heads.broker_account_id",
             "capital_reservation_heads.book", "capital_reservation_heads.currency"),
            name="fk_decision_batches_head", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("sizing_policy_address",),
                                ("sizing_policies.policy_address",),
                                name="fk_decision_batches_sizing", ondelete="RESTRICT"),
        sa.UniqueConstraint("batch_address", name="uq_decision_batches_address"),
        sa.CheckConstraint(_address("batch_address", dialect),
                           name="ck_decision_batch_address"),
        sa.CheckConstraint(_address("capital_snapshot_address", dialect),
                           name="ck_decision_batch_capital_snapshot"),
        sa.CheckConstraint(_address("margin_snapshot_address", dialect),
                           name="ck_decision_batch_margin_snapshot"),
        sa.CheckConstraint(_address("product_policy_address", dialect),
                           name="ck_decision_batch_product_policy"),
        sa.CheckConstraint(_address("portfolio_policy_address", dialect),
                           name="ck_decision_batch_portfolio_policy"),
        sa.CheckConstraint(_digest("candidate_set_digest", dialect),
                           name="ck_decision_batch_candidates"),
        sa.CheckConstraint("book IN ('paper','live') AND currency = upper(currency) "
                           "AND length(currency) = 3", name="ck_decision_batch_scope"),
        sa.CheckConstraint("fence_epoch > 0 AND reservation_head_revision >= 0 AND "
                           "margin_available_minor >= 0 AND active_reservation_minor >= 0 AND "
                           "safety_buffer_minor >= 0", name="ck_decision_batch_numeric"),
        sa.CheckConstraint("status IN ('decided','refused')",
                           name="ck_decision_batch_status"),
    ])

    _create("portfolio_admission_decisions", [
        sa.Column("decision_id", sa.String(64), primary_key=True),
        sa.Column("decision_address", sa.String(71), nullable=False),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("candidate_intent_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("admitted_quantity", sa.Integer(), nullable=False),
        sa.Column("required_capital_minor", sa.BigInteger(), nullable=False),
        sa.Column("held_capital_minor", sa.BigInteger(), nullable=False),
        sa.Column("score_scaled", sa.BigInteger(), nullable=False),
        sa.Column("rank_json", sa.Text(), nullable=False),
        sa.Column("constraints_json", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("explanation", sa.String(400), nullable=False),
        sa.Column("reservation_id", sa.String(64), nullable=True),
    ], [
        sa.ForeignKeyConstraint(("batch_id",), ("decision_batches.decision_batch_id",),
                                name="fk_portfolio_decisions_batch", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("candidate_intent_id",),
                                ("candidate_intents.candidate_intent_id",),
                                name="fk_portfolio_decisions_candidate", ondelete="RESTRICT"),
        sa.UniqueConstraint("batch_id", "candidate_intent_id",
                            name="uq_portfolio_decisions_batch_candidate"),
        sa.UniqueConstraint("decision_address", name="uq_portfolio_decisions_address"),
        sa.CheckConstraint(_address("decision_address", dialect),
                           name="ck_portfolio_decision_address"),
        sa.CheckConstraint(_json("rank_json", dialect),
                           name="ck_portfolio_decision_rank_json"),
        sa.CheckConstraint(_json("constraints_json", dialect),
                           name="ck_portfolio_decision_constraints_json"),
        sa.CheckConstraint("status IN ('admitted','rejected','resized')",
                           name="ck_portfolio_decision_status"),
        sa.CheckConstraint("requested_quantity <> 0 AND required_capital_minor >= 0 AND "
                           "held_capital_minor >= 0", name="ck_portfolio_decision_numeric"),
        sa.CheckConstraint("(status = 'rejected' AND admitted_quantity = 0 AND "
                           "reservation_id IS NULL) OR (status IN ('admitted','resized') "
                           "AND admitted_quantity <> 0)",
                           name="ck_portfolio_decision_outcome"),
    ])

    _create("capital_reservations", [
        sa.Column("reservation_id", sa.String(64), primary_key=True),
        sa.Column("reservation_address", sa.String(71), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("book", sa.String(8), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("candidate_intent_id", sa.String(64), nullable=False),
        sa.Column("decision_id", sa.String(64), nullable=False),
        sa.Column("estimated_minor", sa.BigInteger(), nullable=False),
        sa.Column("consumed_minor", sa.BigInteger(), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("admitted_quantity", sa.Integer(), nullable=False),
        sa.Column("consumed_quantity", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("fence_epoch", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("command_id", sa.String(64), nullable=True),
        sa.Column("last_reconciled_at", sa.DateTime(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
    ], [
        sa.ForeignKeyConstraint(
            ("owner_id", "broker_account_id", "book", "currency"),
            ("capital_reservation_heads.owner_id", "capital_reservation_heads.broker_account_id",
             "capital_reservation_heads.book", "capital_reservation_heads.currency"),
            name="fk_capital_reservations_head", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("batch_id",), ("decision_batches.decision_batch_id",),
                                name="fk_capital_reservations_batch", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("candidate_intent_id",),
                                ("candidate_intents.candidate_intent_id",),
                                name="fk_capital_reservations_candidate", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("decision_id",),
                                ("portfolio_admission_decisions.decision_id",),
                                name="fk_capital_reservations_decision", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("command_id",), ("account_execution_commands.command_id",),
                                name="fk_capital_reservations_command", ondelete="RESTRICT"),
        sa.UniqueConstraint("reservation_address", name="uq_capital_reservations_address"),
        sa.UniqueConstraint("decision_id", name="uq_capital_reservations_decision"),
        sa.CheckConstraint(_address("reservation_address", dialect),
                           name="ck_capital_reservation_address"),
        sa.CheckConstraint("state IN ('held','submission_pending','partially_consumed',"
                           "'consumed','released','reconciliation_required')",
                           name="ck_capital_reservation_state"),
        sa.CheckConstraint("estimated_minor >= 0 AND consumed_minor >= 0 AND "
                           "consumed_minor <= estimated_minor", name="ck_reservation_money"),
        sa.CheckConstraint("requested_quantity <> 0 AND admitted_quantity <> 0 AND "
                           "consumed_quantity >= 0 AND revision >= 0 AND fence_epoch > 0",
                           name="ck_reservation_quantity_revision"),
    ])

    _create("capital_reservation_events", [
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("event_address", sa.String(71), nullable=False),
        sa.Column("reservation_id", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=True),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("consumed_minor", sa.BigInteger(), nullable=False),
        sa.Column("consumed_quantity", sa.Integer(), nullable=False),
        sa.Column("fence_epoch", sa.Integer(), nullable=False),
        sa.Column("evidence_address", sa.String(71), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    ], [
        sa.ForeignKeyConstraint(("reservation_id",),
                                ("capital_reservations.reservation_id",),
                                name="fk_capital_reservation_events_reservation",
                                ondelete="RESTRICT"),
        sa.UniqueConstraint("reservation_id", "revision",
                            name="uq_capital_reservation_events_revision"),
        sa.UniqueConstraint("event_address", name="uq_capital_reservation_events_address"),
        sa.CheckConstraint(_address("event_address", dialect),
                           name="ck_capital_reservation_event_address"),
        sa.CheckConstraint(_address("evidence_address", dialect),
                           name="ck_capital_reservation_event_evidence"),
        sa.CheckConstraint("revision >= 0 AND fence_epoch > 0 AND consumed_minor >= 0 AND "
                           "consumed_quantity >= 0", name="ck_reservation_event_numeric"),
        sa.CheckConstraint("to_state IN ('held','submission_pending','partially_consumed',"
                           "'consumed','released','reconciliation_required')",
                           name="ck_reservation_event_state"),
    ])

    _create("position_campaigns", [
        sa.Column("campaign_id", sa.String(64), primary_key=True),
        sa.Column("campaign_address", sa.String(71), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("broker_account_id", sa.String(64), nullable=False),
        sa.Column("book", sa.String(8), nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        *_attribution_columns(),
        sa.Column("canonical_instrument_key", sa.String(64), nullable=False),
        sa.Column("execution_instrument_key", sa.String(96), nullable=False),
        sa.Column("product_address", sa.String(71), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("target_policy_address", sa.String(71), nullable=False),
        sa.Column("position_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
    ], [
        _account_fk("fk_position_campaigns_account"),
        sa.ForeignKeyConstraint(("deployment_id",), ("deployments.id",),
                                name="fk_position_campaigns_deployment", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("position_id",), ("positions.id",),
                                name="fk_position_campaigns_position", ondelete="RESTRICT"),
        sa.UniqueConstraint("campaign_address", name="uq_position_campaigns_address"),
        sa.CheckConstraint(_address("campaign_address", dialect),
                           name="ck_position_campaign_address"),
        sa.CheckConstraint(_address("product_address", dialect),
                           name="ck_position_campaign_product"),
        sa.CheckConstraint(_address("target_policy_address", dialect),
                           name="ck_position_campaign_target_policy"),
        sa.CheckConstraint(_address("admission_address", dialect, nullable=True),
                           name="ck_position_campaigns_admission_address"),
        sa.CheckConstraint("book IN ('paper','live') AND direction IN ('LONG','SHORT')",
                           name="ck_position_campaign_scope"),
        sa.CheckConstraint("status IN ('open','closed','legacy_unattributed') AND revision >= 0",
                           name="ck_position_campaign_state"),
    ])

    _create("position_tranches", [
        sa.Column("tranche_id", sa.String(64), primary_key=True),
        sa.Column("tranche_address", sa.String(71), nullable=False),
        sa.Column("campaign_id", sa.String(64), nullable=False),
        sa.Column("target_position_request_id", sa.String(64), nullable=True),
        sa.Column("candidate_intent_id", sa.String(64), nullable=True),
        sa.Column("batch_id", sa.String(64), nullable=True),
        sa.Column("decision_id", sa.String(64), nullable=True),
        sa.Column("reservation_id", sa.String(64), nullable=True),
        sa.Column("execution_intent_id", sa.String(32), nullable=True),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("admitted_quantity", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("terminal_at", sa.DateTime(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
    ], [
        sa.ForeignKeyConstraint(("campaign_id",), ("position_campaigns.campaign_id",),
                                name="fk_position_tranches_campaign", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("target_position_request_id",),
                                ("target_position_requests.request_id",),
                                name="fk_position_tranches_target", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("candidate_intent_id",),
                                ("candidate_intents.candidate_intent_id",),
                                name="fk_position_tranches_candidate", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("batch_id",), ("decision_batches.decision_batch_id",),
                                name="fk_position_tranches_batch", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("decision_id",),
                                ("portfolio_admission_decisions.decision_id",),
                                name="fk_position_tranches_decision", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("reservation_id",),
                                ("capital_reservations.reservation_id",),
                                name="fk_position_tranches_reservation", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("execution_intent_id",),
                                ("execution_intents.client_intent_id",),
                                name="fk_position_tranches_intent", ondelete="RESTRICT"),
        sa.UniqueConstraint("tranche_address", name="uq_position_tranches_address"),
        sa.CheckConstraint(_address("tranche_address", dialect),
                           name="ck_position_tranche_address"),
        sa.CheckConstraint("purpose IN ('ENTRY','ADDITION','REDUCTION') AND "
                           "requested_quantity <> 0 AND admitted_quantity <> 0 AND revision >= 0",
                           name="ck_position_tranche_numeric"),
        sa.CheckConstraint("state IN ('planned','submitted','partially_filled','filled',"
                           "'cancelled','reconciliation_required')",
                           name="ck_position_tranche_state"),
    ])

    _create("fill_allocations", [
        sa.Column("allocation_id", sa.String(64), primary_key=True),
        sa.Column("allocation_address", sa.String(71), nullable=False),
        sa.Column("tranche_id", sa.String(64), nullable=False),
        sa.Column("execution_order_event_id", sa.Integer(), nullable=False),
        sa.Column("trade_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("allocated_at", sa.DateTime(), nullable=False),
    ], [
        sa.ForeignKeyConstraint(("tranche_id",), ("position_tranches.tranche_id",),
                                name="fk_fill_allocations_tranche", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("execution_order_event_id",),
                                ("execution_order_events.id",),
                                name="fk_fill_allocations_event", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("trade_id",), ("trades.id",),
                                name="fk_fill_allocations_trade", ondelete="RESTRICT"),
        sa.UniqueConstraint("allocation_address", name="uq_fill_allocations_address"),
        sa.UniqueConstraint("execution_order_event_id", "tranche_id",
                            name="uq_fill_allocations_event_tranche"),
        sa.CheckConstraint(_address("allocation_address", dialect),
                           name="ck_fill_allocation_address"),
        sa.CheckConstraint("quantity > 0", name="ck_fill_allocation_quantity"),
    ])


def _immutable(table: str, dialect: str) -> None:
    bind = op.get_bind()
    if dialect == "postgresql":
        function = f"{table}_refuse_mutation"
        bind.execute(sa.text(
            f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ "
            f"BEGIN RAISE EXCEPTION '{table} is immutable'; END; $$ LANGUAGE plpgsql"))
        bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {function} ON {table}"))
        bind.execute(sa.text(
            f"CREATE TRIGGER {function} BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"))
        return
    for operation in ("update", "delete"):
        name = f"{table}_refuse_{operation}"
        bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
        bind.execute(sa.text(
            f"CREATE TRIGGER {name} BEFORE {operation.upper()} ON {table} BEGIN "
            f"SELECT RAISE(ABORT, '{table} is immutable'); END"))


def _identity_guard(table: str, columns: tuple[str, ...], dialect: str) -> None:
    bind = op.get_bind()
    trigger = f"{table}_refuse_identity_change"
    if dialect == "postgresql":
        function = f"{trigger}_fn"
        changed = " OR ".join(
            f"NEW.{column} IS DISTINCT FROM OLD.{column}" for column in columns)
        bind.execute(sa.text(
            f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
            f"IF {changed} THEN RAISE EXCEPTION '{table} identity is immutable'; "
            "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql"))
        bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger} ON {table}"))
        bind.execute(sa.text(
            f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"))
        return
    changed = " OR ".join(f"NEW.{column} IS NOT OLD.{column}" for column in columns)
    bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger}"))
    bind.execute(sa.text(
        f"CREATE TRIGGER {trigger} BEFORE UPDATE ON {table} WHEN {changed} BEGIN "
        f"SELECT RAISE(ABORT, '{table} identity is immutable'); END"))


def _delete_guard(table: str, dialect: str) -> None:
    bind = op.get_bind()
    trigger = f"{table}_refuse_delete"
    if dialect == "postgresql":
        function = f"{trigger}_fn"
        bind.execute(sa.text(
            f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
            f"RAISE EXCEPTION '{table} is durable'; END; $$ LANGUAGE plpgsql"))
        bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger} ON {table}"))
        bind.execute(sa.text(
            f"CREATE TRIGGER {trigger} BEFORE DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"))
        return
    bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger}"))
    bind.execute(sa.text(
        f"CREATE TRIGGER {trigger} BEFORE DELETE ON {table} BEGIN "
        f"SELECT RAISE(ABORT, '{table} is durable'); END"))


def _graph_guard(table: str, dialect: str) -> None:
    bind = op.get_bind()
    trigger = f"{table}_validate_graph_attribution"
    if dialect == "postgresql":
        function = f"{trigger}_fn"
        bind.execute(sa.text(
            f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
            "IF NOT (((NEW.attribution_state = 'VERIFIED_GRAPH' AND "
            "NEW.strategy_key LIKE 'ir.%%' AND NEW.strategy_version ~ '^[0-9]+$' AND "
            "NEW.graph_address ~ '^sha256:[0-9a-f]{64}$' AND NEW.admission_address IS NOT NULL) "
            "OR (NEW.attribution_state = 'NON_GRAPH' AND NEW.graph_address IS NULL AND "
            "(NEW.strategy_key IS NULL OR NEW.strategy_key NOT LIKE 'ir.%%')) OR "
            "(NEW.attribution_state = 'LEGACY_UNVERIFIED' AND NEW.graph_address IS NULL))) "
            "THEN RAISE EXCEPTION 'GRAPH_ATTRIBUTION_MISMATCH'; END IF; RETURN NEW; "
            "END; $$ LANGUAGE plpgsql"))
        bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger} ON {table}"))
        bind.execute(sa.text(
            f"CREATE TRIGGER {trigger} BEFORE INSERT OR UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"))
        insert = f"{table}_refuse_legacy_attribution_insert"
        insert_fn = f"{insert}_fn"
        bind.execute(sa.text(
            f"CREATE OR REPLACE FUNCTION {insert_fn}() RETURNS trigger AS $$ BEGIN "
            "IF NEW.attribution_state = 'LEGACY_UNVERIFIED' OR "
            "(NEW.strategy_key LIKE 'ir.%%' AND NEW.attribution_state <> 'VERIFIED_GRAPH') "
            "THEN RAISE EXCEPTION 'GRAPH_ATTRIBUTION_UNVERIFIED'; END IF; RETURN NEW; "
            "END; $$ LANGUAGE plpgsql"))
        bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {insert} ON {table}"))
        bind.execute(sa.text(
            f"CREATE TRIGGER {insert} BEFORE INSERT ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {insert_fn}()"))
        return
    valid = (
        "((NEW.attribution_state = 'VERIFIED_GRAPH' AND NEW.strategy_key LIKE 'ir.%' "
        "AND NEW.strategy_version IS NOT NULL AND length(NEW.strategy_version) > 0 "
        "AND NEW.strategy_version NOT GLOB '*[^0-9]*' "
        "AND NEW.graph_address IS NOT NULL AND length(NEW.graph_address) = 71 "
        "AND substr(NEW.graph_address,1,7) = 'sha256:' "
        "AND substr(NEW.graph_address,8) = lower(substr(NEW.graph_address,8)) "
        "AND substr(NEW.graph_address,8) NOT GLOB '*[^0-9a-f]*' "
        "AND NEW.admission_address IS NOT NULL) OR "
        "(NEW.attribution_state = 'NON_GRAPH' AND NEW.graph_address IS NULL "
        "AND (NEW.strategy_key IS NULL OR NEW.strategy_key NOT LIKE 'ir.%')) OR "
        "(NEW.attribution_state = 'LEGACY_UNVERIFIED' AND NEW.graph_address IS NULL))")
    for operation in ("insert", "update"):
        name = f"{trigger}_{operation}"
        bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
        bind.execute(sa.text(
            f"CREATE TRIGGER {name} BEFORE {operation.upper()} ON {table} WHEN NOT {valid} "
            "BEGIN SELECT RAISE(ABORT, 'GRAPH_ATTRIBUTION_MISMATCH'); END"))
    insert = f"{table}_refuse_legacy_attribution_insert"
    bind.execute(sa.text(f"DROP TRIGGER IF EXISTS {insert}"))
    bind.execute(sa.text(
        f"CREATE TRIGGER {insert} BEFORE INSERT ON {table} "
        "WHEN NEW.attribution_state = 'LEGACY_UNVERIFIED' OR "
        "(NEW.strategy_key LIKE 'ir.%' AND NEW.attribution_state <> 'VERIFIED_GRAPH') "
        "BEGIN SELECT RAISE(ABORT, 'GRAPH_ATTRIBUTION_UNVERIFIED'); END"))


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError(f"0041 does not support {dialect!r}")
    _create_tables(dialect)
    for table in (
        "sizing_policies", "sizing_decisions", "target_position_requests",
        "candidate_intents", "decision_batches", "portfolio_admission_decisions",
        "capital_reservation_events", "fill_allocations",
    ):
        _immutable(table, dialect)
    _identity_guard("capital_reservations", (
        "reservation_address", "owner_id", "broker_account_id", "book", "currency",
        "batch_id", "candidate_intent_id", "decision_id", "estimated_minor",
        "requested_quantity", "admitted_quantity", "fence_epoch", "created_at",
    ), dialect)
    _identity_guard("position_campaigns", (
        "campaign_address", "owner_id", "broker_account_id", "book", "deployment_id",
        "strategy_key", "strategy_version", "admission_address", "graph_address",
        "attribution_state", "canonical_instrument_key", "execution_instrument_key",
        "product_address", "direction", "target_policy_address", "position_id",
        "opened_at",
    ), dialect)
    _identity_guard("position_tranches", (
        "tranche_address", "campaign_id", "target_position_request_id",
        "candidate_intent_id", "batch_id", "decision_id", "reservation_id",
        "execution_intent_id", "purpose", "requested_quantity",
        "admitted_quantity", "created_at",
    ), dialect)
    for table in ("position_campaigns", "position_tranches"):
        _delete_guard(table, dialect)
    for table in ("target_position_requests", "candidate_intents", "position_campaigns"):
        _graph_guard(table, dialect)


def downgrade() -> None:
    raise RuntimeError(
        "0041 refuses destructive capital-admission downgrade; disable new writers, "
        "retain immutable decisions/reservations and restore a verified 0040 backup "
        "or forward-reconcile the current schema"
    )
