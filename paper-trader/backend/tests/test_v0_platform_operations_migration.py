from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
import threading
import os
import sys

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.orm import Session

from app.db import migrate
from app.db.models import Base
from app.platform_operations.repository import OPERATIONS_TABLES


def _sqlite(tmp_path, name):
    engine = sa.create_engine(f"sqlite:///{tmp_path / name}", future=True)
    @sa.event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
    return engine


def _prepare_0045(engine):
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.exec_driver_sql("DROP VIEW IF EXISTS platform_analytics_event_counts")
            connection.exec_driver_sql("DROP VIEW IF EXISTS platform_operator_entitlement_counts")
            connection.exec_driver_sql("DROP VIEW IF EXISTS platform_operator_support_counts")
            connection.exec_driver_sql(
                "DROP FUNCTION IF EXISTS platform_append_operator_audit(varchar,varchar,varchar,"
                "varchar,varchar,varchar,varchar,timestamp)")
        for table in [table for table in Base.metadata.sorted_tables
                      if table.name in OPERATIONS_TABLES][::-1]:
            table.drop(connection)
        command.stamp(migrate.alembic_config(connection), "0045")


def _rewrite_sqlite_table(engine, table, old, new):
    with engine.connect() as connection:
        raw = connection.connection.driver_connection
        original = raw.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        assert old in original
        version = raw.execute("PRAGMA schema_version").fetchone()[0]
        raw.execute("PRAGMA writable_schema=ON")
        raw.execute("UPDATE sqlite_master SET sql=? WHERE type='table' AND name=?",
                    (original.replace(old, new), table))
        raw.execute("PRAGMA writable_schema=OFF")
        raw.execute(f"PRAGMA schema_version={version + 1}")
        raw.commit()


def test_sqlite_exact_0045_upgrade_is_additive_restart_safe_and_partial_closed(tmp_path):
    engine = _sqlite(tmp_path, "upgrade.db")
    _prepare_0045(engine)
    before = set(sa.inspect(engine).get_table_names())
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0046")
    assert migrate.schema_version(engine) == "0046"
    assert set(sa.inspect(engine).get_table_names()) - before == OPERATIONS_TABLES
    # 0046 remains historical, but 0049 accepts only the exact 0048 source at
    # managed startup; intermediate revisions require their own sealed rollout.
    with pytest.raises(RuntimeError, match="exact accepted 0048"):
        migrate.init_schema(
            engine, create_all=lambda: Base.metadata.create_all(engine),
            legacy_migrate=lambda: pytest.fail("legacy migration must not run"),
            expected_tables=Base.metadata.tables)

    partial = _sqlite(tmp_path, "partial.db")
    _prepare_0045(partial)
    with partial.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE platform_plan_versions(plan_version_id VARCHAR(128) PRIMARY KEY)")
    with pytest.raises(RuntimeError, match="partial or unversioned"):
        with partial.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0046")
    assert migrate.schema_version(partial) == "0045"
    assert ({name for name in sa.inspect(partial).get_table_names()
             if name.startswith("platform_")} == {"platform_plan_versions"})


def test_sqlite_interrupted_0046_rolls_back_and_retry_converges(tmp_path):
    engine = _sqlite(tmp_path, "interrupted.db")
    _prepare_0045(engine)
    interrupted = False

    def interrupt(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal interrupted
        if not interrupted and "CREATE TABLE platform_billing_bindings" in statement:
            interrupted = True
            raise RuntimeError("injected 0046 interruption")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected 0046 interruption"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0046")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    assert interrupted
    assert migrate.schema_version(engine) == "0045"
    assert not ({name for name in sa.inspect(engine).get_table_names()
                 if name.startswith("platform_")})
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0046")
    assert migrate.schema_version(engine) == "0046"


@pytest.mark.parametrize("mutation", ("same_name_noop_trigger", "same_name_altered_check"))
def test_sqlite_0045_semantic_manifest_refuses_before_0046_writes(tmp_path, mutation):
    engine = _sqlite(tmp_path, f"0045-manifest-{mutation}.db")
    _prepare_0045(engine)
    if mutation == "same_name_noop_trigger":
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TRIGGER positions_refuse_entry_intent_id_rebind")
            connection.exec_driver_sql(
                "CREATE TRIGGER positions_refuse_entry_intent_id_rebind BEFORE UPDATE ON positions "
                "BEGIN SELECT 1; END")
    else:
        _rewrite_sqlite_table(
            engine, "positions",
            "mode != 'paper' OR paper_entry_charge_schedule_id IS NULL OR entry_intent_id IS NOT NULL",
            "1 = 1")
    before = set(sa.inspect(engine).get_table_names())
    with pytest.raises(RuntimeError, match="Paper lifecycle"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0046")
    assert migrate.schema_version(engine) == "0045"
    assert set(sa.inspect(engine).get_table_names()) == before
    assert not ({name for name in before if name.startswith("platform_")})


@pytest.mark.parametrize("heads", [("0044",), ("0045", "0044")])
def test_managed_stale_or_branch_source_refuses_before_alembic_writes(tmp_path, heads):
    engine = _sqlite(tmp_path, "stale-" + "-".join(heads) + ".db")
    _prepare_0045(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM alembic_version"))
        for head in heads:
            connection.execute(sa.text(
                "INSERT INTO alembic_version(version_num) VALUES (:head)"), {"head": head})
    before = set(sa.inspect(engine).get_table_names())
    with pytest.raises(RuntimeError, match="exact accepted 0048"):
        migrate.upgrade_to_head(engine)
    assert set(sa.inspect(engine).get_table_names()) == before
    with engine.connect() as connection:
        assert tuple(connection.execute(sa.text(
            "SELECT version_num FROM alembic_version ORDER BY version_num")).scalars()) == tuple(sorted(heads))


def test_sqlite_model_migration_constraints_indexes_and_triggers_match(tmp_path):
    fresh = _sqlite(tmp_path, "fresh.db")
    Base.metadata.create_all(fresh)
    upgraded = _sqlite(tmp_path, "model-upgrade.db")
    _prepare_0045(upgraded)
    with upgraded.begin() as connection:
        connection.exec_driver_sql("DROP TABLE account_trial_uses")
        connection.exec_driver_sql("DROP TABLE account_profile_evidence")
        connection.exec_driver_sql("DROP TABLE ir_v2_editor_presentations")
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0049")
    for table_name in sorted(OPERATIONS_TABLES):
        fresh_i, upgraded_i = sa.inspect(fresh), sa.inspect(upgraded)
        def columns(inspector):
            return [(item["name"], str(item["type"]), item["nullable"],
                     item.get("default"), item["primary_key"])
                    for item in inspector.get_columns(table_name)]
        assert columns(fresh_i) == columns(upgraded_i)
        assert fresh_i.get_pk_constraint(table_name) == upgraded_i.get_pk_constraint(table_name)
        assert fresh_i.get_foreign_keys(table_name) == upgraded_i.get_foreign_keys(table_name)
        assert fresh_i.get_unique_constraints(table_name) == upgraded_i.get_unique_constraints(table_name)
        assert fresh_i.get_check_constraints(table_name) == upgraded_i.get_check_constraints(table_name)
        assert fresh_i.get_indexes(table_name) == upgraded_i.get_indexes(table_name)
    with upgraded.connect() as connection:
        upgraded_triggers = {
            name: " ".join(sql.split())
            for name, sql in connection.execute(sa.text(
                "SELECT name,sql FROM sqlite_master WHERE type='trigger' "
                "AND name LIKE 'platform_%'"))
        }
    with fresh.connect() as connection:
        fresh_triggers = {
            name: " ".join(sql.split())
            for name, sql in connection.execute(sa.text(
                "SELECT name,sql FROM sqlite_master WHERE type='trigger' "
                "AND name LIKE 'platform_%'"))
        }
    triggers = set(upgraded_triggers)
    for table_name in OPERATIONS_TABLES:
        assert f"{table_name}_privacy_insert" in triggers
        assert f"{table_name}_privacy_update" in triggers
    assert "platform_entitlement_events_source_exact" in triggers
    assert "platform_coupon_redemptions_capacity" in triggers
    assert "platform_operator_bindings_refuse_update" in triggers
    for name in (
        "platform_coupon_definitions_privacy_insert",
        "platform_coupon_definitions_privacy_update",
    ):
        assert upgraded_triggers[name] == fresh_triggers[name]


def test_revision_0046_replay_is_frozen_against_future_model_mutation(tmp_path):
    import ast
    from pathlib import Path

    revision_path = Path(migrate.MIGRATIONS_DIR) / "versions" / "20260830_0046_v0_platform_operations.py"
    imports = []
    for node in ast.walk(ast.parse(revision_path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert "app.db.models" not in imports

    engine = _sqlite(tmp_path, "frozen-revision.db")
    _prepare_0045(engine)
    table = Base.metadata.tables["platform_plan_versions"]
    future = sa.Column("future_model_only", sa.String(12), nullable=True)
    table.append_column(future)
    try:
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0046")
        columns = {item["name"] for item in sa.inspect(engine).get_columns(
            "platform_plan_versions")}
        assert "future_model_only" not in columns
    finally:
        table._columns.remove(future)


def test_postgresql_16_exact_upgrade_roles_denials_and_concurrent_owner(pg_sandbox, tmp_path):
    fresh = sa.create_engine(pg_sandbox.url("operations_fresh"), future=True)
    assert migrate.init_schema(
        fresh, create_all=lambda: Base.metadata.create_all(fresh),
        legacy_migrate=lambda: pytest.fail("fresh PostgreSQL cannot use historical migration"),
        expected_tables=Base.metadata.tables) == "0049"
    assert {name for name in sa.inspect(fresh).get_view_names()
            if name.startswith("platform_")} == {
                "platform_analytics_event_counts", "platform_operator_entitlement_counts",
                "platform_operator_support_counts",
            }
    fresh.dispose()
    stale = sa.create_engine(pg_sandbox.url("operations_stale"), future=True)
    _prepare_0045(stale)
    with stale.begin() as connection:
        connection.execute(sa.text("UPDATE alembic_version SET version_num='0044'"))
    with pytest.raises(RuntimeError, match="exact accepted 0048"):
        migrate.upgrade_to_head(stale)
    assert migrate.schema_version(stale) == "0044"
    assert not ({name for name in sa.inspect(stale).get_table_names()
                 if name.startswith("platform_")})
    stale.dispose()
    interrupted = sa.create_engine(pg_sandbox.url("operations_interrupted"), future=True)
    _prepare_0045(interrupted)
    injected = False
    def interrupt(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal injected
        if not injected and "CREATE TABLE platform_billing_bindings" in statement:
            injected = True
            raise RuntimeError("injected PostgreSQL 0046 interruption")
    sa.event.listen(interrupted, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected PostgreSQL"):
            with interrupted.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0046")
    finally:
        sa.event.remove(interrupted, "before_cursor_execute", interrupt)
    assert migrate.schema_version(interrupted) == "0045"
    assert not ({name for name in sa.inspect(interrupted).get_table_names()
                 if name.startswith("platform_")})
    with interrupted.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0046")
    assert migrate.schema_version(interrupted) == "0046"
    interrupted.dispose()
    engine = sa.create_engine(pg_sandbox.url("operations_upgrade"), future=True)
    _prepare_0045(engine)
    first = engine.connect()
    second = engine.connect()
    transaction = first.begin()
    first.exec_driver_sql("SELECT pg_advisory_xact_lock(4200046)")
    try:
        with pytest.raises(sa.exc.DBAPIError, match="lock timeout"):
            with second.begin():
                second.exec_driver_sql("SET LOCAL lock_timeout='100ms'")
                second.exec_driver_sql("SELECT pg_advisory_xact_lock(4200046)")
        assert migrate.schema_version(engine) == "0045"
        assert not ({name for name in sa.inspect(engine).get_table_names()
                     if name.startswith("platform_")})
    finally:
        transaction.rollback()
        first.close()
        second.close()
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0046")
    assert migrate.schema_version(engine) == "0046"
    revision_0046 = __import__(
        "migrations.versions.20260830_0046_v0_platform_operations",
        fromlist=["_revision_metadata"],
    )
    migrate._validate_current_schema(
        engine, revision_0046._revision_metadata("postgresql").tables)
    assert {name for name in sa.inspect(engine).get_table_names()
            if name.startswith("platform_")} == OPERATIONS_TABLES
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE OR REPLACE FUNCTION positions_refuse_entry_intent_id_rebind_fn() "
            "RETURNS trigger AS $$ BEGIN RETURN NEW; END; $$ LANGUAGE plpgsql")
        with pytest.raises(RuntimeError, match="positions trigger"):
            migrate.validate_paper_entry_lifecycle_manifest(connection)
        connection.exec_driver_sql(
            "CREATE OR REPLACE FUNCTION positions_refuse_entry_intent_id_rebind_fn() "
            "RETURNS trigger AS $$ BEGIN IF NEW.entry_intent_id IS DISTINCT FROM "
            "OLD.entry_intent_id THEN RAISE EXCEPTION 'positions entry_intent_id is immutable'; "
            "END IF; RETURN NEW; END; $$ LANGUAGE plpgsql")
        migrate.validate_paper_entry_lifecycle_manifest(connection)
        connection.exec_driver_sql(
            "ALTER TABLE positions DROP CONSTRAINT ck_positions_paper_entry_intent_required")
        connection.exec_driver_sql(
            "ALTER TABLE positions ADD CONSTRAINT ck_positions_paper_entry_intent_required "
            "CHECK (true)")
        with pytest.raises(RuntimeError, match="positions CHECK"):
            migrate.validate_paper_entry_lifecycle_manifest(connection)
        connection.exec_driver_sql(
            "ALTER TABLE positions DROP CONSTRAINT ck_positions_paper_entry_intent_required")
        connection.exec_driver_sql(
            "ALTER TABLE positions ADD CONSTRAINT ck_positions_paper_entry_intent_required "
            "CHECK (mode != 'paper' OR paper_entry_charge_schedule_id IS NULL OR "
            "entry_intent_id IS NOT NULL)")
        migrate.validate_paper_entry_lifecycle_manifest(connection)
    with engine.begin() as connection:
        triggers = set(connection.execute(sa.text(
            "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal "
            "AND tgname LIKE 'platform_%'" )).scalars())
        for table_name in OPERATIONS_TABLES:
            assert f"{table_name}_privacy_guard" in triggers
        assert "platform_coupon_redemptions_capacity" in triggers
        assert "platform_entitlement_events_source_exact" in triggers
        for table_name in {
            "platform_plan_versions", "platform_coupon_redemptions",
            "platform_billing_event_receipts", "platform_entitlement_events",
            "platform_complimentary_entitlement_grants", "platform_analytics_events",
            "platform_support_replies", "platform_operator_audit_events",
            "platform_operator_bindings",
        }:
            assert f"{table_name}_refuse_mutation" in triggers
        privileges = connection.execute(sa.text(
            "SELECT "
            "has_table_privilege('operations_billing','platform_plan_versions','SELECT'),"
            "has_table_privilege('operations_billing','platform_analytics_events','SELECT'),"
            "has_table_privilege('operations_analytics','platform_analytics_event_counts','SELECT'),"
            "has_table_privilege('operations_analytics','platform_analytics_subjects','SELECT'),"
            "has_table_privilege('operations_support','platform_support_requests','INSERT'),"
            "has_table_privilege('operations_support','platform_billing_bindings','SELECT'),"
            "has_table_privilege('operations_billing','platform_billing_event_receipts','INSERT'),"
            "has_table_privilege('operations_billing','platform_complimentary_entitlement_grants','INSERT'),"
            "has_table_privilege('operations_support','platform_support_replies','INSERT'),"
            "has_table_privilege('operations_operator','platform_operator_support_counts','SELECT'),"
            "has_table_privilege('operations_operator','memberships','SELECT')"
        )).one()
        assert privileges == (
            True, False, True, False, True, False, False, False, False, True, False)
        for role, sql in (
            ("operations_billing", "SELECT count(*) FROM platform_analytics_events"),
            ("operations_analytics", "SELECT count(*) FROM platform_analytics_subjects"),
            ("operations_support", "SELECT count(*) FROM platform_billing_bindings"),
            ("operations_billing", "INSERT INTO platform_complimentary_entitlement_grants "
             "VALUES('forged','owner.alpha','PRODUCT_ACCESS','GRANT','sha256:" + "a" * 64 +
             "',CURRENT_TIMESTAMP,NULL,'operator.founder',CURRENT_TIMESTAMP)"),
            ("operations_support", "INSERT INTO platform_support_replies "
             "VALUES('forged','support.alpha','owner.alpha',1,'operator.founder',"
             "'ACKNOWLEDGED',CURRENT_TIMESTAMP)"),
            ("operations_operator", "SELECT count(*) FROM memberships"),
        ):
            with pytest.raises(sa.exc.DBAPIError, match="permission denied"):
                with engine.begin() as denied:
                    denied.exec_driver_sql(f"SET LOCAL ROLE {role}")
                    denied.exec_driver_sql(sql).scalar_one()
    engine.dispose()
    engine = pg_sandbox.engine("operations_current_0049")
    assert migrate.init_schema(
        engine,
        create_all=lambda: Base.metadata.create_all(engine),
        legacy_migrate=lambda: pytest.fail("current PostgreSQL must not adopt"),
        expected_tables=Base.metadata.tables,
    ) == "0049"
    from app.operations.postgresql_backup import resolve_postgresql16_tools
    from app.platform_operations.repository import (
        PlatformOperationsRepository, validate_persisted_operations,
    )
    from app.platform_operations.contracts import (
        BillingEventState, BillingEventType, BillingInterval, BillingMode,
        BillingVerifierAuthority, BindingState, CouponState, EntitlementSource, EntitlementState,
        EntitlementTransition, MembershipState, OperationsConflict, OperationsNotFound,
        OperationsRefused,
        OperatorAuthority, PolicyState, SupportCategory, TenantAuthority,
    )
    import datetime as dt
    now = dt.datetime(2026, 8, 30, 9, 0, tzinfo=dt.timezone.utc)
    with Session(engine) as session:
        bootstrap = PlatformOperationsRepository(session)
        bootstrap.bind_founder(
            binding_id="operator.founder", principal_ref="principal.founder",
            permission_profile_address="sha256:" + "a" * 64,
            bootstrap_evidence_address="sha256:" + "b" * 64, created_at=now)
        operator = PlatformOperationsRepository(
            session, operator=OperatorAuthority("operator.founder", "principal.founder")
        )
        operator.create_plan_version(
            plan_version_id="plan.restore", plan_code="RESTORE", version=1,
            amount_minor=100, currency_code="EUR",
            billing_interval=BillingInterval.UNKNOWN,
            entitlement_set_address="sha256:" + "a" * 64,
            policy_state=PolicyState.UNKNOWN, created_at=now)
        operator.define_coupon(
            coupon_id="coupon.restore", coupon_digest="a" * 64,
            plan_version_id="plan.restore", policy_address="sha256:" + "a" * 64,
            valid_from=now, valid_until=None, max_redemptions=2,
            per_owner_limit=1, status=CouponState.ACTIVE, created_at=now,
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_valid_from=now, entitlement_valid_until=None)
        operator.define_coupon(
            coupon_id="coupon.concurrent.pg", coupon_digest="c" * 64,
            plan_version_id="plan.restore", policy_address="sha256:" + "a" * 64,
            valid_from=now, valid_until=None, max_redemptions=1,
            per_owner_limit=1, status=CouponState.ACTIVE, created_at=now,
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_valid_from=now, entitlement_valid_until=None)
        alpha = PlatformOperationsRepository(session, tenant=TenantAuthority(
            "owner.alpha", "principal.alpha", MembershipState.ACTIVE))
        beta = PlatformOperationsRepository(session, tenant=TenantAuthority(
            "owner.beta", "principal.beta", MembershipState.ACTIVE))
        alpha.redeem_coupon(
            coupon_digest="a" * 64, redemption_id="redemption.alpha",
            policy_address="sha256:" + "a" * 64, redeemed_at=now)
        alpha.create_billing_binding(
            binding_id="billing.alpha", mode=BillingMode.TEST,
            merchant_address="sha256:" + "a" * 64,
            integration_address="sha256:" + "b" * 64,
            status=BindingState.PENDING, created_at=now,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha")
        verifier = PlatformOperationsRepository(session, verifier=BillingVerifierAuthority(
            "verifier.local", BillingMode.TEST,
            "sha256:" + "a" * 64, "sha256:" + "b" * 64))
        receipt = verifier.receive_billing_event(
            receipt_id="receipt.alpha", binding_id="billing.alpha",
            provider_event_ref="event.alpha", event_type=BillingEventType.PAYMENT_CAPTURED,
            event_state=BillingEventState.VERIFIED, raw_body_digest="b" * 64,
            occurred_at=now, received_at=now,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha",
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_policy_address="sha256:" + "a" * 64,
            entitlement_valid_from=now, entitlement_valid_until=None)
        assert verifier.receive_billing_event(
            receipt_id="receipt.alpha", binding_id="billing.alpha",
            provider_event_ref="event.alpha", event_type=BillingEventType.PAYMENT_CAPTURED,
            event_state=BillingEventState.VERIFIED, raw_body_digest="b" * 64,
            occurred_at=now, received_at=now,
            provider_customer_ref="customer.alpha",
            provider_subscription_ref="subscription.alpha",
            entitlement_code="PRODUCT_ACCESS",
            entitlement_transition=EntitlementTransition.GRANT,
            entitlement_policy_address="sha256:" + "a" * 64,
            entitlement_valid_from=now, entitlement_valid_until=None) == receipt
        with pytest.raises(OperationsNotFound):
            beta.receive_billing_event(
                receipt_id="receipt.beta", binding_id="billing.alpha",
                provider_event_ref="event.beta", event_type=BillingEventType.PAYMENT_CAPTURED,
                event_state=BillingEventState.REJECTED, raw_body_digest="b" * 64,
                occurred_at=now, received_at=now,
                provider_customer_ref="customer.alpha",
                provider_subscription_ref="subscription.alpha")
        alpha.append_entitlement_event(
            event_id="entitlement.alpha", entitlement_code="PRODUCT_ACCESS",
            mode=BillingMode.TEST, source_kind=EntitlementSource.BILLING_RECEIPT,
            source_ref=receipt.receipt_id, transition=EntitlementTransition.GRANT,
            policy_address="sha256:" + "a" * 64, valid_from=now, valid_until=None,
            effective_at=now, recorded_at=now)
        assert alpha.rebuild_entitlements(rebuilt_at=now)[0].state is EntitlementState.ACTIVE
        alpha.create_support_request(
            request_id="support.alpha", category=SupportCategory.ACCOUNT_ACCESS,
            detail_code="LOGIN_FAILED", created_at=now)
        session.commit()
    with pytest.raises(sa.exc.DBAPIError, match="immutable"):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE platform_operator_bindings SET principal_ref='principal.replacement' "
                "WHERE operator_slot='FOUNDER'")
    barrier = threading.Barrier(2)
    def redeem_concurrently(owner):
        with Session(engine) as session:
            barrier.wait()
            repository = PlatformOperationsRepository(session, tenant=TenantAuthority(
                owner, f"principal.{owner}", MembershipState.ACTIVE))
            try:
                repository.redeem_coupon(
                    coupon_digest="c" * 64, redemption_id=f"redemption.{owner}",
                    policy_address="sha256:" + "a" * 64, redeemed_at=now)
                session.commit()
                return "ACCEPTED"
            except (OperationsConflict, OperationsRefused):
                session.rollback()
                return "REFUSED"
    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent_results = list(pool.map(
            redeem_concurrently, ("owner.concurrent.a", "owner.concurrent.b")))
    assert sorted(concurrent_results) == ["ACCEPTED", "REFUSED"]
    with engine.connect() as connection:
        assert connection.scalar(sa.text(
            "SELECT count(*) FROM platform_coupon_redemptions "
            "WHERE coupon_id='coupon.concurrent.pg' AND status='ACCEPTED'")) == 1
    with pytest.raises(sa.exc.DBAPIError, match="forbidden content"):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE platform_support_requests SET detail_code='STRATEGY_ID'")
    with engine.begin() as connection:
        connection.exec_driver_sql("SET LOCAL ROLE operations_operator")
        connection.execute(sa.text(
            "SELECT platform_append_operator_audit(:event,:binding,:permission,:action,"
            ":target,:redacted,:outcome,:occurred)"), {
                "event": "audit.restore", "binding": "operator.founder",
                "permission": "AUDIT_WRITE", "action": "VIEW_AGGREGATE",
                "target": "SUBSCRIPTION", "redacted": "c" * 64,
                "outcome": "SUCCEEDED", "occurred": now.replace(tzinfo=None),
            })
    with pytest.raises(sa.exc.DBAPIError, match="permission denied"):
        with engine.begin() as connection:
            connection.exec_driver_sql("SET LOCAL ROLE operations_operator")
            connection.exec_driver_sql(
                "INSERT INTO platform_operator_audit_events(audit_event_id,operator_binding_id,"
                "permission_class,action_class,target_class,target_redacted_id,outcome,occurred_at) "
                "VALUES('audit.denied','operator.founder','AUDIT_WRITE','VIEW_AGGREGATE',"
                "'SUBSCRIPTION','" + "d" * 64 + "','SUCCEEDED',CURRENT_TIMESTAMP)")
    pg_dump, pg_restore = resolve_postgresql16_tools()
    artifact = tmp_path / "operations.dump"
    source_url = str(sa.engine.make_url(pg_sandbox.url("operations_current_0049")).set(
        drivername="postgresql"))
    target_url = str(sa.engine.make_url(pg_sandbox.url("operations_restore")).set(
        drivername="postgresql"))
    subprocess.run([str(pg_dump), "--format=custom", "--no-owner",
                    f"--file={artifact}", source_url], check=True,
                   capture_output=True, text=True)
    from scripts.run_disposable_postgres import run_disposable_postgres
    clean_restore_code = r'''
import importlib.util
import os
from pathlib import Path
import subprocess
import sqlalchemy as sa
from app.db import migrate
from app.operations.postgresql_backup import resolve_postgresql16_tools

url = os.environ["PT_TEST_POSTGRES_URL"]
path = Path("migrations/versions/20260830_0046_v0_platform_operations.py").resolve()
spec = importlib.util.spec_from_file_location("operations_0046", path)
revision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(revision)
engine = sa.create_engine(url, future=True)
with engine.begin() as connection:
    assert connection.scalar(sa.text(
        "SELECT count(*) FROM pg_roles WHERE rolname LIKE 'operations_%'")) == 0
    revision.bootstrap_postgresql_roles(connection)
engine.dispose()
_dump, restore = resolve_postgresql16_tools()
target = str(sa.engine.make_url(url).set(drivername="postgresql"))
subprocess.run([str(restore), "--no-owner", "--exit-on-error", f"--dbname={target}",
                os.environ["OPS_DUMP"]], check=True, capture_output=True, text=True)
engine = sa.create_engine(url, future=True)
assert migrate.schema_version(engine) == "0049"
with engine.connect() as connection:
    assert connection.scalar(sa.text(
        "SELECT has_table_privilege('operations_operator',"
        "'platform_operator_support_counts','SELECT')")) is True
try:
    with engine.begin() as connection:
        connection.exec_driver_sql("SET LOCAL ROLE operations_operator")
        connection.exec_driver_sql("SELECT count(*) FROM memberships").scalar_one()
except sa.exc.DBAPIError:
    pass
else:
    raise AssertionError("clean-cluster restored operator role read memberships")
engine.dispose()
'''
    clean_environment = dict(os.environ)
    clean_environment["OPS_DUMP"] = str(artifact)
    assert run_disposable_postgres(
        [sys.executable, "-c", clean_restore_code], environ=clean_environment) == 0
    subprocess.run([str(pg_restore), "--no-owner", "--exit-on-error",
                    f"--dbname={target_url}", str(artifact)], check=True,
                   capture_output=True, text=True)
    restored = sa.create_engine(pg_sandbox.url("operations_restore"), future=True)
    assert migrate.schema_version(restored) == "0049"
    with restored.connect() as connection:
        validate_persisted_operations(connection)
        assert connection.scalar(sa.text(
            "SELECT count(*) FROM platform_plan_versions")) == 1
        assert connection.scalar(sa.text(
            "SELECT count(*) FROM platform_operator_bindings")) == 1
        assert connection.scalar(sa.text(
            "SELECT count(*) FROM user_sessions WHERE revoked_at IS NULL")) == 0
        assert connection.scalar(sa.text(
            "SELECT has_table_privilege('operations_operator',"
            "'platform_operator_support_counts','SELECT')")) is True
    restored.dispose()
    engine.dispose()
