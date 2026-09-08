"""Add the closed platform OPERATIONS plane over exact accepted 0045.

The revision is additive and forward-only. Old binaries ignore these tables;
operations writers require exact 0046. Recovery uses a verified pre-write
backup or an owner-directed forward repair, never destructive downgrade.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.db.migrate import validate_paper_entry_lifecycle_manifest


revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


TABLES = (
    "platform_plan_versions", "platform_coupon_definitions",
    "platform_coupon_redemptions", "platform_billing_bindings",
    "platform_billing_event_receipts", "platform_entitlement_events",
    "platform_current_entitlements", "platform_complimentary_entitlement_grants",
    "platform_analytics_subjects", "platform_analytics_events",
    "platform_support_requests", "platform_support_replies",
    "platform_operator_bindings", "platform_operator_audit_events",
)


def _address(column: str, dialect: str, *, nullable: bool = False) -> str:
    if dialect == "postgresql":
        body = f"{column} ~ '^sha256:[0-9a-f]{{64}}$'"
    else:
        body = (f"length({column}) = 71 AND substr({column}, 1, 7) = 'sha256:' AND "
                f"substr({column}, 8) = lower(substr({column}, 8)) AND "
                f"substr({column}, 8) NOT GLOB '*[^0-9a-f]*'")
    return f"{column} IS NULL OR ({body})" if nullable else body


def _digest(column: str, dialect: str) -> str:
    if dialect == "postgresql":
        return f"char_length({column}) = 64 AND {column} ~ '^[0-9a-f]{{64}}$'"
    return (f"length({column}) = 64 AND {column} = lower({column}) AND "
            f"{column} NOT GLOB '*[^0-9a-f]*'")


def _code(column: str, dialect: str, *, nullable: bool = False) -> str:
    if dialect == "postgresql":
        body = f"{column} ~ '^[A-Z][A-Z0-9_]{{0,63}}$'"
    else:
        body = (f"length({column}) BETWEEN 1 AND 64 AND substr({column}, 1, 1) GLOB '[A-Z]' "
                f"AND {column} NOT GLOB '*[^A-Z0-9_]*'")
    return f"{column} IS NULL OR ({body})" if nullable else body


def _currency(column: str, dialect: str, *, nullable: bool = False) -> str:
    body = (f"{column} ~ '^[A-Z]{{3}}$'" if dialect == "postgresql"
            else f"length({column}) = 3 AND {column} NOT GLOB '*[^A-Z]*'")
    return f"{column} IS NULL OR ({body})" if nullable else body


def _revision_metadata(dialect: str) -> sa.MetaData:
    """Frozen revision-owned 0046 catalog; current ORM changes cannot alter replay."""
    metadata = sa.MetaData()
    plan = sa.Table(
        "platform_plan_versions", metadata,
        sa.Column("plan_version_id", sa.String(128), primary_key=True),
        sa.Column("plan_code", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("billing_interval", sa.String(16), nullable=False),
        sa.Column("entitlement_set_address", sa.String(71), nullable=False),
        sa.Column("policy_state", sa.String(16), nullable=False),
        sa.Column("test_provider_plan_address", sa.String(71)),
        sa.Column("live_provider_plan_address", sa.String(71)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("plan_code", "version", name="uq_platform_plan_code_version"),
        sa.CheckConstraint(_code("plan_code", dialect), name="ck_platform_plan_code"),
        sa.CheckConstraint("version >= 1 AND amount_minor >= 0", name="ck_platform_plan_numbers"),
        sa.CheckConstraint(_currency("currency", dialect), name="ck_platform_plan_currency"),
        sa.CheckConstraint("billing_interval IN ('UNKNOWN','MONTH','YEAR')", name="ck_platform_plan_interval"),
        sa.CheckConstraint("policy_state IN ('UNKNOWN','APPROVED','RETIRED')", name="ck_platform_plan_policy"),
        sa.CheckConstraint(_address("entitlement_set_address", dialect), name="ck_platform_plan_entitlement"),
        sa.CheckConstraint(_address("test_provider_plan_address", dialect, nullable=True), name="ck_platform_plan_test_provider"),
        sa.CheckConstraint(_address("live_provider_plan_address", dialect, nullable=True), name="ck_platform_plan_live_provider"),
    )
    coupon = sa.Table(
        "platform_coupon_definitions", metadata,
        sa.Column("coupon_id", sa.String(128), primary_key=True),
        sa.Column("coupon_digest", sa.String(64), nullable=False),
        sa.Column("plan_version_id", sa.String(128), nullable=False),
        sa.Column("policy_address", sa.String(71), nullable=False),
        sa.Column("trial_policy_address", sa.String(71)),
        sa.Column("discount_policy_address", sa.String(71)),
        sa.Column("entitlement_code", sa.String(64), nullable=False),
        sa.Column("entitlement_transition", sa.String(16), nullable=False),
        sa.Column("entitlement_valid_from", sa.DateTime(), nullable=False),
        sa.Column("entitlement_valid_until", sa.DateTime()),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime()),
        sa.Column("max_redemptions", sa.Integer()),
        sa.Column("per_owner_limit", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(("plan_version_id",), (plan.c.plan_version_id,),
                                name="fk_platform_coupon_plan", ondelete="RESTRICT"),
        sa.UniqueConstraint("coupon_digest", name="uq_platform_coupon_digest"),
        sa.CheckConstraint(_digest("coupon_digest", dialect), name="ck_platform_coupon_digest"),
        sa.CheckConstraint(_address("policy_address", dialect), name="ck_platform_coupon_policy"),
        sa.CheckConstraint(_address("trial_policy_address", dialect, nullable=True), name="ck_platform_coupon_trial"),
        sa.CheckConstraint(_address("discount_policy_address", dialect, nullable=True), name="ck_platform_coupon_discount"),
        sa.CheckConstraint(_code("entitlement_code", dialect), name="ck_platform_coupon_entitlement_code"),
        sa.CheckConstraint("entitlement_transition IN ('GRANT','RENEW','EXPIRE','REVOKE')", name="ck_platform_coupon_entitlement_transition"),
        sa.CheckConstraint("entitlement_valid_until IS NULL OR entitlement_valid_until > entitlement_valid_from", name="ck_platform_coupon_entitlement_validity"),
        sa.CheckConstraint("status IN ('UNKNOWN','ACTIVE','SUSPENDED','EXPIRED')", name="ck_platform_coupon_status"),
        sa.CheckConstraint("max_redemptions IS NULL OR max_redemptions >= 1", name="ck_platform_coupon_max"),
        sa.CheckConstraint("per_owner_limit >= 1 AND per_owner_limit <= 100", name="ck_platform_coupon_owner_limit"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_platform_coupon_validity"),
    )
    sa.Index("ix_platform_coupon_status_validity", coupon.c.status, coupon.c.valid_from,
             coupon.c.valid_until)
    redemption = sa.Table(
        "platform_coupon_redemptions", metadata,
        sa.Column("redemption_id", sa.String(128), primary_key=True),
        sa.Column("coupon_id", sa.String(128), nullable=False),
        sa.Column("owner_ref", sa.String(128), nullable=False),
        sa.Column("policy_address", sa.String(71), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("entitlement_code", sa.String(64), nullable=False),
        sa.Column("entitlement_transition", sa.String(16), nullable=False),
        sa.Column("entitlement_valid_from", sa.DateTime(), nullable=False),
        sa.Column("entitlement_valid_until", sa.DateTime()),
        sa.Column("redeemed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(("coupon_id",), (coupon.c.coupon_id,),
                                name="fk_platform_redemption_coupon", ondelete="RESTRICT"),
        sa.UniqueConstraint("coupon_id", "owner_ref", "policy_address",
                            name="uq_platform_redemption_owner_policy"),
        sa.CheckConstraint(_address("policy_address", dialect), name="ck_platform_redemption_policy"),
        sa.CheckConstraint("status IN ('ACCEPTED','REVOKED')", name="ck_platform_redemption_status"),
        sa.CheckConstraint(_code("entitlement_code", dialect), name="ck_platform_redemption_entitlement_code"),
        sa.CheckConstraint("entitlement_transition IN ('GRANT','RENEW','EXPIRE','REVOKE')", name="ck_platform_redemption_entitlement_transition"),
        sa.CheckConstraint("entitlement_valid_until IS NULL OR entitlement_valid_until > entitlement_valid_from", name="ck_platform_redemption_entitlement_validity"),
    )
    sa.Index("ix_platform_redemptions_owner_time", redemption.c.owner_ref,
             redemption.c.redeemed_at, redemption.c.redemption_id)
    binding = sa.Table(
        "platform_billing_bindings", metadata,
        sa.Column("binding_id", sa.String(128), primary_key=True),
        sa.Column("owner_ref", sa.String(128), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("merchant_address", sa.String(71), nullable=False),
        sa.Column("integration_address", sa.String(71), nullable=False),
        sa.Column("provider_customer_ref", sa.String(128), nullable=False),
        sa.Column("provider_subscription_ref", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("owner_ref", "mode", "merchant_address", "integration_address",
                            name="uq_platform_billing_owner_integration"),
        sa.UniqueConstraint("binding_id", "owner_ref", "mode", "merchant_address",
                            "integration_address", "provider_customer_ref",
                            "provider_subscription_ref", name="uq_platform_billing_attribution"),
        sa.UniqueConstraint("mode", "merchant_address", "integration_address",
                            "provider_customer_ref", "provider_subscription_ref",
                            name="uq_platform_billing_provider_binding"),
        sa.CheckConstraint("mode IN ('TEST','LIVE')", name="ck_platform_billing_mode"),
        sa.CheckConstraint("status IN ('UNKNOWN','PENDING','ACTIVE','PAUSED','CANCELLED')", name="ck_platform_billing_status"),
        sa.CheckConstraint(_address("merchant_address", dialect), name="ck_platform_billing_merchant"),
        sa.CheckConstraint(_address("integration_address", dialect), name="ck_platform_billing_integration"),
    )
    sa.Index("ix_platform_billing_owner_status", binding.c.owner_ref, binding.c.mode,
             binding.c.status, binding.c.binding_id)
    receipt = sa.Table(
        "platform_billing_event_receipts", metadata,
        sa.Column("receipt_id", sa.String(128), primary_key=True),
        sa.Column("binding_id", sa.String(128), nullable=False),
        sa.Column("owner_ref", sa.String(128), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("merchant_address", sa.String(71), nullable=False),
        sa.Column("integration_address", sa.String(71), nullable=False),
        sa.Column("provider_customer_ref", sa.String(128), nullable=False),
        sa.Column("provider_event_ref", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("event_state", sa.String(16), nullable=False),
        sa.Column("raw_body_digest", sa.String(64), nullable=False),
        sa.Column("facts_schema_version", sa.Integer(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger()),
        sa.Column("currency", sa.String(3)),
        sa.Column("provider_payment_ref", sa.String(128)),
        sa.Column("provider_subscription_ref", sa.String(128), nullable=False),
        sa.Column("provider_invoice_ref", sa.String(128)),
        sa.Column("entitlement_code", sa.String(64)),
        sa.Column("entitlement_transition", sa.String(16)),
        sa.Column("entitlement_policy_address", sa.String(71)),
        sa.Column("entitlement_valid_from", sa.DateTime()),
        sa.Column("entitlement_valid_until", sa.DateTime()),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ("binding_id", "owner_ref", "mode", "merchant_address", "integration_address",
             "provider_customer_ref", "provider_subscription_ref"),
            (binding.c.binding_id, binding.c.owner_ref, binding.c.mode,
             binding.c.merchant_address, binding.c.integration_address,
             binding.c.provider_customer_ref, binding.c.provider_subscription_ref),
            name="fk_platform_receipt_binding_attribution", ondelete="RESTRICT"),
        sa.UniqueConstraint("mode", "merchant_address", "integration_address",
                            "provider_event_ref", name="uq_platform_receipt_provider_event_boundary"),
        sa.CheckConstraint("mode IN ('TEST','LIVE')", name="ck_platform_receipt_mode"),
        sa.CheckConstraint("event_type IN ('SUBSCRIPTION_AUTHENTICATED','SUBSCRIPTION_ACTIVATED','SUBSCRIPTION_CHARGED','SUBSCRIPTION_PAUSED','SUBSCRIPTION_CANCELLED','PAYMENT_CAPTURED','PAYMENT_FAILED')", name="ck_platform_receipt_type"),
        sa.CheckConstraint("event_state IN ('VERIFIED','REJECTED','UNKNOWN')", name="ck_platform_receipt_state"),
        sa.CheckConstraint(_digest("raw_body_digest", dialect), name="ck_platform_receipt_digest"),
        sa.CheckConstraint("facts_schema_version = 1", name="ck_platform_receipt_facts_version"),
        sa.CheckConstraint("amount_minor IS NULL OR amount_minor >= 0", name="ck_platform_receipt_amount"),
        sa.CheckConstraint(_currency("currency", dialect, nullable=True), name="ck_platform_receipt_currency"),
        sa.CheckConstraint(_code("entitlement_code", dialect, nullable=True), name="ck_platform_receipt_entitlement_code"),
        sa.CheckConstraint("entitlement_transition IS NULL OR entitlement_transition IN ('GRANT','RENEW','EXPIRE','REVOKE')", name="ck_platform_receipt_entitlement_transition"),
        sa.CheckConstraint(_address("entitlement_policy_address", dialect, nullable=True), name="ck_platform_receipt_entitlement_policy"),
        sa.CheckConstraint("entitlement_valid_until IS NULL OR (entitlement_valid_from IS NOT NULL AND entitlement_valid_until > entitlement_valid_from)", name="ck_platform_receipt_entitlement_validity"),
        sa.CheckConstraint("(entitlement_code IS NULL AND entitlement_transition IS NULL AND entitlement_policy_address IS NULL AND entitlement_valid_from IS NULL AND entitlement_valid_until IS NULL) OR (entitlement_code IS NOT NULL AND entitlement_transition IS NOT NULL AND entitlement_policy_address IS NOT NULL AND entitlement_valid_from IS NOT NULL)", name="ck_platform_receipt_entitlement_envelope"),
    )
    sa.Index("ix_platform_receipts_owner_time", receipt.c.owner_ref, receipt.c.received_at,
             receipt.c.receipt_id)
    entitlement = sa.Table(
        "platform_entitlement_events", metadata,
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("owner_ref", sa.String(128), nullable=False),
        sa.Column("entitlement_code", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(128), nullable=False),
        sa.Column("transition", sa.String(16), nullable=False),
        sa.Column("policy_address", sa.String(71), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime()),
        sa.Column("effective_at", sa.DateTime(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_kind", "source_ref", name="uq_platform_entitlement_source"),
        sa.CheckConstraint(_code("entitlement_code", dialect), name="ck_platform_entitlement_code"),
        sa.CheckConstraint("mode IN ('TEST','LIVE','INTERNAL')", name="ck_platform_entitlement_mode"),
        sa.CheckConstraint("source_kind IN ('BILLING_RECEIPT','COUPON_REDEMPTION','COMPLIMENTARY_GRANT')", name="ck_platform_entitlement_source"),
        sa.CheckConstraint("transition IN ('GRANT','RENEW','EXPIRE','REVOKE')", name="ck_platform_entitlement_transition"),
        sa.CheckConstraint(_address("policy_address", dialect), name="ck_platform_entitlement_policy"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_platform_entitlement_validity"),
    )
    sa.Index("ix_platform_entitlement_reduce", entitlement.c.owner_ref,
             entitlement.c.entitlement_code, entitlement.c.mode, entitlement.c.effective_at,
             entitlement.c.event_id)
    current = sa.Table(
        "platform_current_entitlements", metadata,
        sa.Column("owner_ref", sa.String(128), primary_key=True),
        sa.Column("entitlement_code", sa.String(64), primary_key=True),
        sa.Column("mode", sa.String(8), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("source_event_id", sa.String(128), nullable=False),
        sa.Column("effective_at", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime()),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("rebuilt_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(("source_event_id",), (entitlement.c.event_id,),
                                name="fk_platform_current_event", ondelete="RESTRICT"),
        sa.CheckConstraint(_code("entitlement_code", dialect), name="ck_platform_current_code"),
        sa.CheckConstraint("mode IN ('TEST','LIVE','INTERNAL')", name="ck_platform_current_mode"),
        sa.CheckConstraint("state IN ('UNKNOWN','ACTIVE','INACTIVE')", name="ck_platform_current_state"),
        sa.CheckConstraint("projection_version >= 1", name="ck_platform_current_version"),
    )
    sa.Index("ix_platform_current_owner_state", current.c.owner_ref, current.c.state,
             current.c.entitlement_code)
    operator = sa.Table(
        "platform_operator_bindings", metadata,
        sa.Column("operator_slot", sa.String(16), primary_key=True),
        sa.Column("binding_id", sa.String(128), nullable=False),
        sa.Column("principal_ref", sa.String(128), nullable=False),
        sa.Column("permission_profile_address", sa.String(71), nullable=False),
        sa.Column("bootstrap_evidence_address", sa.String(71), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.UniqueConstraint("binding_id", name="uq_platform_operator_binding"),
        sa.CheckConstraint("operator_slot = 'FOUNDER'", name="ck_platform_operator_founder_slot"),
        sa.CheckConstraint("status IN ('UNKNOWN','ACTIVE','REVOKED')", name="ck_platform_operator_status"),
        sa.CheckConstraint(_address("permission_profile_address", dialect), name="ck_platform_operator_permissions"),
        sa.CheckConstraint(_address("bootstrap_evidence_address", dialect), name="ck_platform_operator_bootstrap"),
        sa.CheckConstraint("(status = 'REVOKED' AND revoked_at IS NOT NULL) OR (status <> 'REVOKED' AND revoked_at IS NULL)", name="ck_platform_operator_revocation"),
    )
    grant = sa.Table(
        "platform_complimentary_entitlement_grants", metadata,
        sa.Column("grant_id", sa.String(128), primary_key=True),
        sa.Column("owner_ref", sa.String(128), nullable=False),
        sa.Column("entitlement_code", sa.String(64), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("policy_address", sa.String(71), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime()),
        sa.Column("operator_binding_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(("operator_binding_id",), (operator.c.binding_id,),
                                name="fk_platform_grant_operator", ondelete="RESTRICT"),
        sa.CheckConstraint(_code("entitlement_code", dialect), name="ck_platform_grant_code"),
        sa.CheckConstraint("action IN ('GRANT','REVOKE')", name="ck_platform_grant_action"),
        sa.CheckConstraint(_address("policy_address", dialect), name="ck_platform_grant_policy"),
        sa.CheckConstraint("valid_until IS NULL OR valid_until > valid_from", name="ck_platform_grant_validity"),
    )
    sa.Index("ix_platform_grants_owner_time", grant.c.owner_ref, grant.c.created_at,
             grant.c.grant_id)
    subject = sa.Table(
        "platform_analytics_subjects", metadata,
        sa.Column("owner_ref", sa.String(128), primary_key=True),
        sa.Column("subject_id", sa.String(128), primary_key=True),
        sa.Column("pseudonym_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("exported_at", sa.DateTime()),
        sa.UniqueConstraint("subject_id", name="uq_platform_analytics_subject"),
        sa.CheckConstraint(_digest("pseudonym_digest", dialect), name="ck_platform_analytics_pseudonym"),
    )
    sa.Index("ix_platform_analytics_owner", subject.c.owner_ref, subject.c.subject_id)
    analytics = sa.Table(
        "platform_analytics_events", metadata,
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("owner_ref", sa.String(128), nullable=False),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("surface", sa.String(24), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("dimension_a", sa.String(64)),
        sa.Column("dimension_b", sa.String(64)),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(("owner_ref", "subject_id"),
                                (subject.c.owner_ref, subject.c.subject_id),
                                name="fk_platform_analytics_subject", ondelete="RESTRICT"),
        sa.CheckConstraint("schema_version = 1", name="ck_platform_analytics_schema"),
        sa.CheckConstraint("event_type IN ('SESSION_STARTED','WORKSPACE_OPENED','RESEARCH_STARTED','RESEARCH_COMPLETED','DEPLOYMENT_FLOW_OPENED','ERROR_SHOWN')", name="ck_platform_analytics_type"),
        sa.CheckConstraint("surface IN ('SHELL','WORKSPACE','RESEARCH','DEPLOYMENT')", name="ck_platform_analytics_surface"),
        sa.CheckConstraint("outcome IN ('SUCCEEDED','FAILED','ABANDONED','UNKNOWN')", name="ck_platform_analytics_outcome"),
        sa.CheckConstraint("dimension_a IS NULL OR dimension_a IN ('DESKTOP','WEB','EMPTY','RETRY','MANUAL')", name="ck_platform_analytics_dimension_a"),
        sa.CheckConstraint("dimension_b IS NULL OR dimension_b IN ('DESKTOP','WEB','EMPTY','RETRY','MANUAL')", name="ck_platform_analytics_dimension_b"),
    )
    sa.Index("ix_platform_analytics_event_rollup", analytics.c.event_type,
             analytics.c.occurred_at, analytics.c.event_id)
    sa.Index("ix_platform_analytics_owner_time", analytics.c.owner_ref,
             analytics.c.occurred_at, analytics.c.event_id)
    support = sa.Table(
        "platform_support_requests", metadata,
        sa.Column("request_id", sa.String(128), primary_key=True),
        sa.Column("owner_ref", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("detail_code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("exported_at", sa.DateTime()),
        sa.UniqueConstraint("request_id", "owner_ref", name="uq_platform_support_request_owner"),
        sa.CheckConstraint("schema_version = 1", name="ck_platform_support_schema"),
        sa.CheckConstraint("category IN ('ACCOUNT_ACCESS','BILLING','PRODUCT_USAGE','DATA_QUALITY','OTHER_STRUCTURED')", name="ck_platform_support_category"),
        sa.CheckConstraint("detail_code IN ('LOGIN_FAILED','PAYMENT_FAILED','PRODUCT_GUIDANCE','DATA_MISMATCH','OTHER_DECLARED')", name="ck_platform_support_detail"),
        sa.CheckConstraint("status IN ('OPEN','IN_REVIEW','WAITING_CUSTOMER','RESOLVED','CLOSED')", name="ck_platform_support_status"),
    )
    sa.Index("ix_platform_support_owner_status", support.c.owner_ref, support.c.status,
             support.c.updated_at, support.c.request_id)
    reply = sa.Table(
        "platform_support_replies", metadata,
        sa.Column("reply_id", sa.String(128), primary_key=True),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("owner_ref", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("operator_binding_id", sa.String(128), nullable=False),
        sa.Column("response_code", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(("request_id", "owner_ref"),
                                (support.c.request_id, support.c.owner_ref),
                                name="fk_platform_support_reply_request_owner",
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(("operator_binding_id",), (operator.c.binding_id,),
                                name="fk_platform_support_reply_operator", ondelete="RESTRICT"),
        sa.CheckConstraint("schema_version = 1", name="ck_platform_support_reply_schema"),
        sa.CheckConstraint("response_code IN ('ACKNOWLEDGED','NEEDS_ACCOUNT_ACTION','BILLING_REVIEWED','RESOLVED_WITH_GUIDANCE','CANNOT_ASSIST')", name="ck_platform_support_response"),
    )
    sa.Index("ix_platform_support_replies_request", reply.c.request_id, reply.c.created_at,
             reply.c.reply_id)
    audit = sa.Table(
        "platform_operator_audit_events", metadata,
        sa.Column("audit_event_id", sa.String(128), primary_key=True),
        sa.Column("operator_binding_id", sa.String(128), nullable=False),
        sa.Column("permission_class", sa.String(24), nullable=False),
        sa.Column("action_class", sa.String(32), nullable=False),
        sa.Column("target_class", sa.String(24), nullable=False),
        sa.Column("target_redacted_id", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(("operator_binding_id",), (operator.c.binding_id,),
                                name="fk_platform_audit_operator", ondelete="RESTRICT"),
        sa.CheckConstraint("permission_class IN ('BILLING_READ','SUPPORT_WRITE','ENTITLEMENT_WRITE','AUDIT_WRITE')", name="ck_platform_audit_permission"),
        sa.CheckConstraint("action_class IN ('VIEW_AGGREGATE','REPLY_SUPPORT','ISSUE_COMPLIMENTARY','REVOKE_COMPLIMENTARY','CHANGE_BINDING')", name="ck_platform_audit_action"),
        sa.CheckConstraint("target_class IN ('SUBSCRIPTION','SUPPORT_REQUEST','ENTITLEMENT','OPERATOR_BINDING')", name="ck_platform_audit_target"),
        sa.CheckConstraint("outcome IN ('SUCCEEDED','REFUSED','FAILED')", name="ck_platform_audit_outcome"),
        sa.CheckConstraint("length(target_redacted_id) BETWEEN 16 AND 64", name="ck_platform_audit_redacted_length"),
        sa.CheckConstraint(_digest("target_redacted_id", dialect), name="ck_platform_audit_redacted_digest"),
    )
    sa.Index("ix_platform_audit_time", audit.c.occurred_at, audit.c.audit_event_id)
    return metadata


_PRIVACY_TERMS = (
    "strategy", "graph", "component", "parameter", "annotation", "dataset",
    "research", "monitoring", "alert", "signal", "instrument", "nifty",
    "banknifty", "broker", "provider_account", "credential", "secret", "token", "position", "order",
    "trade", "balance", "capital", "pnl", "profit", "loss", "raw_request",
    "raw_response", "raw_webhook", "card", "upi", "free_text", "attachment",
    "diagnostic",
)
_IMMUTABLE_TABLES = (
    "platform_plan_versions", "platform_coupon_redemptions",
    "platform_billing_event_receipts", "platform_entitlement_events",
    "platform_complimentary_entitlement_grants", "platform_analytics_events",
    "platform_support_replies", "platform_operator_bindings",
    "platform_operator_audit_events",
)


def _create_revision_triggers(connection, dialect: str, metadata: sa.MetaData) -> None:
    for table_name in TABLES:
        table = metadata.tables[table_name]
        textual = tuple(
            column.name for column in table.columns
            if isinstance(column.type, sa.String)
            and column.name not in {"event_type", "surface"}
        )
        if dialect == "sqlite":
            terms = " OR ".join(
                f"instr(lower(COALESCE(NEW.{column},'')), '{term}') > 0"
                for column in textual for term in _PRIVACY_TERMS)
            for operation in ("INSERT", "UPDATE"):
                connection.exec_driver_sql(
                    f"CREATE TRIGGER {table_name}_privacy_{operation.lower()} BEFORE {operation} "
                    f"ON {table_name} WHEN {terms} BEGIN "
                    "SELECT RAISE(ABORT, 'platform operations forbidden content'); END")
        else:
            terms = " OR ".join(
                f"position('{term}' in lower(COALESCE(NEW.{column},''))) > 0"
                for column in textual for term in _PRIVACY_TERMS)
            function = f"{table_name}_privacy_guard_fn"
            connection.exec_driver_sql(
                f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
                f"IF {terms} THEN RAISE EXCEPTION 'platform operations forbidden content'; "
                "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql")
            connection.exec_driver_sql(
                f"CREATE TRIGGER {table_name}_privacy_guard BEFORE INSERT OR UPDATE ON "
                f"{table_name} FOR EACH ROW EXECUTE FUNCTION {function}()")
    for table_name in _IMMUTABLE_TABLES:
        if dialect == "sqlite":
            for operation in ("UPDATE", "DELETE"):
                connection.exec_driver_sql(
                    f"CREATE TRIGGER {table_name}_refuse_{operation.lower()} BEFORE {operation} "
                    f"ON {table_name} BEGIN SELECT RAISE(ABORT, '{table_name} is immutable'); END")
        else:
            function = f"{table_name}_refuse_mutation"
            connection.exec_driver_sql(
                f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$ BEGIN "
                f"RAISE EXCEPTION '{table_name} is immutable'; END; $$ LANGUAGE plpgsql")
            connection.exec_driver_sql(
                f"CREATE TRIGGER {function} BEFORE UPDATE OR DELETE ON {table_name} "
                f"FOR EACH ROW EXECUTE FUNCTION {function}()")
    if dialect == "sqlite":
        connection.exec_driver_sql(
            "CREATE TRIGGER platform_coupon_redemptions_capacity BEFORE INSERT ON "
            "platform_coupon_redemptions WHEN NEW.status='ACCEPTED' AND ("
            "((SELECT max_redemptions FROM platform_coupon_definitions WHERE coupon_id=NEW.coupon_id) "
            "IS NOT NULL AND (SELECT count(*) FROM platform_coupon_redemptions WHERE "
            "coupon_id=NEW.coupon_id AND status='ACCEPTED') >= (SELECT max_redemptions FROM "
            "platform_coupon_definitions WHERE coupon_id=NEW.coupon_id)) OR "
            "((SELECT count(*) FROM platform_coupon_redemptions WHERE coupon_id=NEW.coupon_id "
            "AND owner_ref=NEW.owner_ref AND status='ACCEPTED') >= (SELECT per_owner_limit FROM "
            "platform_coupon_definitions WHERE coupon_id=NEW.coupon_id))) BEGIN "
            "SELECT RAISE(ABORT, 'coupon redemption capacity exhausted'); END")
        connection.exec_driver_sql(
            "CREATE TRIGGER platform_entitlement_events_source_exact BEFORE INSERT ON "
            "platform_entitlement_events WHEN NOT ("
            "(NEW.source_kind='BILLING_RECEIPT' AND NEW.mode IN ('TEST','LIVE') AND EXISTS "
            "(SELECT 1 FROM platform_billing_event_receipts s WHERE s.receipt_id=NEW.source_ref "
            "AND s.owner_ref=NEW.owner_ref AND s.mode=NEW.mode AND s.event_state='VERIFIED' "
            "AND s.entitlement_code IS NEW.entitlement_code AND s.entitlement_transition IS NEW.transition "
            "AND s.entitlement_policy_address IS NEW.policy_address AND s.entitlement_valid_from IS NEW.valid_from "
            "AND s.entitlement_valid_until IS NEW.valid_until)) OR "
            "(NEW.source_kind='COUPON_REDEMPTION' AND NEW.mode='INTERNAL' AND EXISTS "
            "(SELECT 1 FROM platform_coupon_redemptions s WHERE s.redemption_id=NEW.source_ref "
            "AND s.owner_ref=NEW.owner_ref AND s.status='ACCEPTED' AND s.entitlement_code IS NEW.entitlement_code "
            "AND s.entitlement_transition IS NEW.transition AND s.policy_address IS NEW.policy_address "
            "AND s.entitlement_valid_from IS NEW.valid_from AND s.entitlement_valid_until IS NEW.valid_until)) OR "
            "(NEW.source_kind='COMPLIMENTARY_GRANT' AND NEW.mode='INTERNAL' AND EXISTS "
            "(SELECT 1 FROM platform_complimentary_entitlement_grants s WHERE s.grant_id=NEW.source_ref "
            "AND s.owner_ref=NEW.owner_ref AND s.entitlement_code IS NEW.entitlement_code "
            "AND s.action IS NEW.transition AND s.policy_address IS NEW.policy_address "
            "AND s.valid_from IS NEW.valid_from AND s.valid_until IS NEW.valid_until))) BEGIN "
            "SELECT RAISE(ABORT, 'entitlement event source mismatch'); END")
    else:
        connection.exec_driver_sql(
            "CREATE OR REPLACE FUNCTION platform_coupon_redemptions_capacity_fn() RETURNS trigger "
            "AS $$ DECLARE maximum integer; owner_maximum integer; BEGIN "
            "SELECT max_redemptions,per_owner_limit INTO maximum,owner_maximum FROM "
            "platform_coupon_definitions WHERE coupon_id=NEW.coupon_id FOR UPDATE; "
            "IF NEW.status='ACCEPTED' AND ((maximum IS NOT NULL AND (SELECT count(*) FROM "
            "platform_coupon_redemptions WHERE coupon_id=NEW.coupon_id AND status='ACCEPTED') >= maximum) "
            "OR ((SELECT count(*) FROM platform_coupon_redemptions WHERE coupon_id=NEW.coupon_id "
            "AND owner_ref=NEW.owner_ref AND status='ACCEPTED') >= owner_maximum)) THEN "
            "RAISE EXCEPTION 'coupon redemption capacity exhausted'; END IF; RETURN NEW; END; "
            "$$ LANGUAGE plpgsql")
        connection.exec_driver_sql(
            "CREATE TRIGGER platform_coupon_redemptions_capacity BEFORE INSERT ON "
            "platform_coupon_redemptions FOR EACH ROW EXECUTE FUNCTION "
            "platform_coupon_redemptions_capacity_fn()")
        connection.exec_driver_sql(
            "CREATE OR REPLACE FUNCTION platform_entitlement_events_source_exact_fn() RETURNS trigger "
            "AS $$ BEGIN IF NOT ((NEW.source_kind='BILLING_RECEIPT' AND NEW.mode IN ('TEST','LIVE') "
            "AND EXISTS (SELECT 1 FROM platform_billing_event_receipts s WHERE s.receipt_id=NEW.source_ref "
            "AND s.owner_ref=NEW.owner_ref AND s.mode=NEW.mode AND s.event_state='VERIFIED' "
            "AND s.entitlement_code IS NOT DISTINCT FROM NEW.entitlement_code "
            "AND s.entitlement_transition IS NOT DISTINCT FROM NEW.transition "
            "AND s.entitlement_policy_address IS NOT DISTINCT FROM NEW.policy_address "
            "AND s.entitlement_valid_from IS NOT DISTINCT FROM NEW.valid_from "
            "AND s.entitlement_valid_until IS NOT DISTINCT FROM NEW.valid_until)) OR "
            "(NEW.source_kind='COUPON_REDEMPTION' AND NEW.mode='INTERNAL' AND EXISTS "
            "(SELECT 1 FROM platform_coupon_redemptions s WHERE s.redemption_id=NEW.source_ref "
            "AND s.owner_ref=NEW.owner_ref AND s.status='ACCEPTED' "
            "AND s.entitlement_code IS NOT DISTINCT FROM NEW.entitlement_code "
            "AND s.entitlement_transition IS NOT DISTINCT FROM NEW.transition "
            "AND s.policy_address IS NOT DISTINCT FROM NEW.policy_address "
            "AND s.entitlement_valid_from IS NOT DISTINCT FROM NEW.valid_from "
            "AND s.entitlement_valid_until IS NOT DISTINCT FROM NEW.valid_until)) OR "
            "(NEW.source_kind='COMPLIMENTARY_GRANT' AND NEW.mode='INTERNAL' AND EXISTS "
            "(SELECT 1 FROM platform_complimentary_entitlement_grants s WHERE s.grant_id=NEW.source_ref "
            "AND s.owner_ref=NEW.owner_ref AND s.entitlement_code IS NOT DISTINCT FROM NEW.entitlement_code "
            "AND s.action IS NOT DISTINCT FROM NEW.transition AND s.policy_address IS NOT DISTINCT FROM NEW.policy_address "
            "AND s.valid_from IS NOT DISTINCT FROM NEW.valid_from AND s.valid_until IS NOT DISTINCT FROM NEW.valid_until))) "
            "THEN RAISE EXCEPTION 'entitlement event source mismatch'; END IF; RETURN NEW; END; "
            "$$ LANGUAGE plpgsql")
        connection.exec_driver_sql(
            "CREATE TRIGGER platform_entitlement_events_source_exact BEFORE INSERT ON "
            "platform_entitlement_events FOR EACH ROW EXECUTE FUNCTION "
            "platform_entitlement_events_source_exact_fn()")


def _refuse_partial_catalog(connection) -> None:
    present = set(sa.inspect(connection).get_table_names()) & set(TABLES)
    if present:
        raise RuntimeError(
            "0046 refuses partial or unversioned platform operations schema; "
            "use a clean restore or owner-directed forward repair"
        )


def bootstrap_postgresql_roles(connection) -> None:
    """Create only cluster-global NOLOGIN roles before a clean-cluster restore."""
    for role in (
        "operations_billing", "operations_analytics",
        "operations_support", "operations_operator",
    ):
        connection.exec_driver_sql(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
            f"'{role}') THEN CREATE ROLE {role} NOLOGIN; END IF; END $$")
        connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {role}")


def _create_postgresql_roles(connection) -> None:
    bootstrap_postgresql_roles(connection)

    joined = ",".join(TABLES)
    connection.exec_driver_sql(f"REVOKE ALL ON {joined} FROM PUBLIC")
    connection.exec_driver_sql(
        "GRANT SELECT ON platform_plan_versions,platform_coupon_definitions,"
        "platform_billing_bindings,platform_billing_event_receipts,"
        "platform_entitlement_events,platform_complimentary_entitlement_grants "
        "TO operations_billing")
    connection.exec_driver_sql(
        "GRANT SELECT,INSERT ON platform_coupon_redemptions TO operations_billing")
    connection.exec_driver_sql(
        "GRANT SELECT,INSERT,UPDATE,DELETE ON platform_current_entitlements "
        "TO operations_billing")
    connection.exec_driver_sql(
        "GRANT INSERT ON platform_analytics_events TO operations_analytics")
    connection.exec_driver_sql(
        "GRANT SELECT,INSERT,UPDATE ON platform_support_requests TO operations_support")
    connection.exec_driver_sql(
        "GRANT SELECT ON platform_support_replies TO operations_support")

    connection.exec_driver_sql(
        "CREATE OR REPLACE VIEW platform_analytics_event_counts AS "
        "SELECT schema_version,event_type,surface,outcome,count(*) AS event_count "
        "FROM platform_analytics_events GROUP BY schema_version,event_type,surface,outcome")
    connection.exec_driver_sql(
        "CREATE OR REPLACE VIEW platform_operator_entitlement_counts AS "
        "SELECT entitlement_code,mode,state,count(*) AS entitlement_count "
        "FROM platform_current_entitlements GROUP BY entitlement_code,mode,state")
    connection.exec_driver_sql(
        "CREATE OR REPLACE VIEW platform_operator_support_counts AS "
        "SELECT category,detail_code,status,count(*) AS request_count "
        "FROM platform_support_requests GROUP BY category,detail_code,status")
    connection.exec_driver_sql(
        "REVOKE ALL ON platform_analytics_event_counts,"
        "platform_operator_entitlement_counts,platform_operator_support_counts FROM PUBLIC")
    connection.exec_driver_sql(
        "GRANT SELECT ON platform_analytics_event_counts TO operations_analytics")
    connection.exec_driver_sql(
        "GRANT SELECT ON platform_operator_entitlement_counts,"
        "platform_operator_support_counts TO operations_operator")

    connection.exec_driver_sql(
        "CREATE OR REPLACE FUNCTION platform_append_operator_audit("
        "p_audit_event_id varchar,p_operator_binding_id varchar,p_permission_class varchar,"
        "p_action_class varchar,p_target_class varchar,p_target_redacted_id varchar,"
        "p_outcome varchar,p_occurred_at timestamp) RETURNS void "
        "LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$ "
        "BEGIN IF NOT EXISTS (SELECT 1 FROM platform_operator_bindings "
        "WHERE binding_id=p_operator_binding_id AND operator_slot='FOUNDER' AND status='ACTIVE') "
        "THEN RAISE EXCEPTION 'active founder operator binding required'; END IF; "
        "INSERT INTO platform_operator_audit_events(audit_event_id,operator_binding_id,"
        "permission_class,action_class,target_class,target_redacted_id,outcome,occurred_at) "
        "VALUES(p_audit_event_id,p_operator_binding_id,p_permission_class,p_action_class,"
        "p_target_class,p_target_redacted_id,p_outcome,p_occurred_at); END $$")
    connection.exec_driver_sql(
        "REVOKE ALL ON FUNCTION platform_append_operator_audit(varchar,varchar,varchar,"
        "varchar,varchar,varchar,varchar,timestamp) FROM PUBLIC")
    connection.exec_driver_sql(
        "GRANT EXECUTE ON FUNCTION platform_append_operator_audit(varchar,varchar,varchar,"
        "varchar,varchar,varchar,varchar,timestamp) TO operations_operator")


def upgrade() -> None:
    connection = op.get_bind()
    dialect = connection.dialect.name
    if dialect not in {"sqlite", "postgresql"}:
        raise RuntimeError("0046 unsupported database dialect")
    if dialect == "sqlite":
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(4200046)")
    validate_paper_entry_lifecycle_manifest(
        connection, compatible_heads=frozenset({"0045"}))
    _refuse_partial_catalog(connection)
    metadata = _revision_metadata(dialect)
    for table in metadata.sorted_tables:
        table.create(connection, checkfirst=False)
    _create_revision_triggers(connection, dialect, metadata)
    if dialect == "postgresql":
        _create_postgresql_roles(connection)


def downgrade() -> None:
    raise RuntimeError(
        "0046 refuses destructive downgrade; quiesce operations writers and "
        "use a verified pre-write restore or owner-directed forward repair"
    )
