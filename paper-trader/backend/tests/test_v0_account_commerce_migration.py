from __future__ import annotations

import datetime as dt
import importlib
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
import sqlalchemy as sa
from alembic import command

from app.db import migrate
from app.db.models import Base
from app.account_commerce import AccountCommerceRefused
from app.account_commerce.repository import validate_persisted_account_commerce


TABLES = {"account_profile_evidence", "account_trial_uses"}


def _engine(tmp_path, name):
    engine = sa.create_engine(f"sqlite:///{tmp_path / name}", future=True)

    @sa.event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def _prepare_0047(engine):
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0049")
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0047")
    assert migrate.schema_version(engine) == "0047"
    assert not TABLES.intersection(sa.inspect(engine).get_table_names())


def _shape(engine, table):
    inspector = sa.inspect(engine)
    checks = {
        item["name"]: " ".join((item.get("sqltext") or "").split())
        for item in inspector.get_check_constraints(table)
    }
    return {
        "columns": [
            (item["name"], str(item["type"]), item["nullable"])
            for item in inspector.get_columns(table)
        ],
        "pk": tuple(inspector.get_pk_constraint(table)["constrained_columns"]),
        "fks": sorted(
            (item["name"], tuple(item["constrained_columns"]),
             item["referred_table"], tuple(item["referred_columns"]))
            for item in inspector.get_foreign_keys(table)
        ),
        "uniques": sorted(
            (item["name"], tuple(item["column_names"]))
            for item in inspector.get_unique_constraints(table)
        ),
        "checks": checks,
        "indexes": sorted(
            (item["name"], tuple(item["column_names"]), item["unique"])
            for item in inspector.get_indexes(table)
        ),
    }


def _triggers(engine, table):
    with engine.connect() as connection:
        return {
            name: " ".join(sql.split())
            for name, sql in connection.exec_driver_sql(
                "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
                (table,),
            )
        }


def _startup(engine):
    return migrate.init_schema(
        engine,
        create_all=lambda: pytest.fail("current startup must not create"),
        legacy_migrate=lambda: pytest.fail("current startup must not adopt"),
        expected_tables=Base.metadata.tables,
    )


def _replace_sqlite_table_sql(engine, old, new):
    with engine.begin() as connection:
        original = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' "
            "AND name='platform_coupon_definitions'"
        ).scalar_one()
        assert original.count(old) == 1
        version = connection.exec_driver_sql("PRAGMA schema_version").scalar_one()
        connection.exec_driver_sql("PRAGMA writable_schema=ON")
        try:
            connection.exec_driver_sql(
                "UPDATE sqlite_master SET sql=? WHERE type='table' "
                "AND name='platform_coupon_definitions'",
                (original.replace(old, new),),
            )
        finally:
            connection.exec_driver_sql("PRAGMA writable_schema=OFF")
        connection.exec_driver_sql(f"PRAGMA schema_version={version + 1}")
    return original


def _exact_rows(connection, table, order_by):
    rows = connection.exec_driver_sql(
        f"SELECT * FROM {table} ORDER BY {order_by}"
    ).all()
    return tuple(tuple(
        None if value is None else str(value).encode("utf-8") for value in row
    ) for row in rows)


def _coupon_state(connection):
    return (
        connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version").scalar_one(),
        _exact_rows(connection, "platform_coupon_definitions", "coupon_id"),
        _exact_rows(connection, "platform_coupon_redemptions", "redemption_id"),
        _exact_rows(connection, "platform_entitlement_events", "event_id"),
    )


def _sqlite_trigger_sql(connection, name):
    return connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)
    ).scalar_one()


def _replace_sqlite_trigger(connection, name, transform):
    original = _sqlite_trigger_sql(connection, name)
    replacement = transform(original)
    assert replacement != original
    connection.exec_driver_sql(f"DROP TRIGGER {name}")
    connection.exec_driver_sql(replacement)


def test_coupon_semantic_sql_normalization_preserves_quoted_bytes():
    source = """ SELECT  'It''s ACCEPTED'  ,  "Case""Identifier" , """ \
             "$tag$Body 'ACCEPTED'$tag$ "
    expected = """select 'It''s ACCEPTED' , "Case""Identifier" , """ \
               "$tag$Body 'ACCEPTED'$tag$"
    assert migrate._compact_semantic_sql(source) == expected
    assert migrate._compact_semantic_sql(source.replace("SELECT", "select")) == expected
    assert migrate._compact_semantic_sql(
        source.replace("'ACCEPTED'", "'accepted'")
    ) != expected
    assert migrate._compact_semantic_sql(
        source.replace('"Case""Identifier"', '"case""Identifier"')
    ) != expected
    assert migrate._compact_semantic_sql(
        source.replace("$tag$Body", "$tag$body")
    ) != expected
    escaped = r" SELECT  E'It\'s ACCEPTED' "
    assert migrate._compact_semantic_sql(escaped) == r"select e'It\'s ACCEPTED'"
    assert migrate._compact_semantic_sql(
        escaped.replace("ACCEPTED", "accepted")
    ) != r"select e'It\'s ACCEPTED'"


def _seed_profile(connection):
    connection.exec_driver_sql(
        "INSERT INTO organizations(organization_id,name,status,created_at,updated_at) "
        "VALUES('owner.alpha','Synthetic','active','2026-09-01','2026-09-01')"
    )
    connection.exec_driver_sql(
        "INSERT INTO users(user_id,email_normalized,display_name,status,created_at,updated_at) "
        "VALUES('user.alpha','synthetic@example.invalid','Synthetic','active',"
        "'2026-09-01','2026-09-01')"
    )
    connection.exec_driver_sql(
        "INSERT INTO memberships(organization_id,user_id,role,status,created_at,updated_at) "
        "VALUES('owner.alpha','user.alpha','member','active','2026-09-01','2026-09-01')"
    )
    connection.exec_driver_sql(
        "INSERT INTO account_profile_evidence(profile_evidence_id,owner_ref,user_ref,"
        "policy_address,evidence_address,satisfied_fields_json,attested_at) VALUES("
        "'profile.one','owner.alpha','user.alpha',?,?,'[]','2026-09-01')",
        ("sha256:" + "a" * 64, "sha256:" + "b" * 64),
    )


def _insert_trial(connection, trial_id, event_id):
    connection.exec_driver_sql(
        "INSERT INTO account_trial_uses(trial_use_id,owner_ref,user_ref,policy_address,"
        "profile_evidence_id,source_kind,source_ref,eligibility_authority_address,"
        "prior_use_authority_address,decision_basis_address,entitlement_code,"
        "entitlement_transition,entitlement_event_id,valid_from,valid_until,used_at) "
        "VALUES(?,'owner.alpha','user.alpha',?,'profile.one','BETA_TRIAL',?,?,?,?,"
        "'PRODUCT_ACCESS','GRANT',?,'2026-09-01','2026-09-16','2026-09-01')",
        (trial_id, "sha256:" + "a" * 64, trial_id,
         "sha256:" + "c" * 64, "sha256:" + "d" * 64,
         "sha256:" + "e" * 64, event_id),
    )


def _prepare_0048(engine):
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0049")
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0048")
    assert migrate.schema_version(engine) == "0048"


def _seed_0048_fixed_coupon(connection, *, suffix="one"):
    address = "sha256:" + "a" * 64
    digest = ("b" if suffix == "one" else "c") * 64
    connection.exec_driver_sql(
        "INSERT INTO platform_plan_versions(plan_version_id,plan_code,version,amount_minor,"
        "currency,billing_interval,entitlement_set_address,policy_state,created_at) VALUES("
        "?, 'BETA',1,0,'INR','UNKNOWN',?,'APPROVED','2026-09-01')",
        (f"plan.{suffix}", address),
    )
    connection.exec_driver_sql(
        "INSERT INTO platform_coupon_definitions(coupon_id,coupon_digest,plan_version_id,"
        "policy_address,trial_policy_address,discount_policy_address,entitlement_code,"
        "entitlement_transition,entitlement_valid_from,entitlement_valid_until,valid_from,"
        "valid_until,max_redemptions,per_owner_limit,status,created_at) VALUES(?,?,?,?,?,NULL,"
        "'PRODUCT_ACCESS','GRANT','2026-09-01 01:02:03.123456',"
        "'2026-09-16 01:02:03.123456','2026-09-01',NULL,5,1,'ACTIVE','2026-09-01')",
        (f"coupon.{suffix}", digest, f"plan.{suffix}", address, address),
    )


def test_0049_exact_0048_backfill_preserves_fixed_semantics_and_restart(tmp_path):
    engine = _engine(tmp_path, "0049-fixed-upgrade.db")
    _prepare_0048(engine)
    with engine.begin() as connection:
        _seed_0048_fixed_coupon(connection)
        before = connection.exec_driver_sql(
            "SELECT coupon_id,coupon_digest,entitlement_valid_from,"
            "entitlement_valid_until FROM platform_coupon_definitions"
        ).one()
    assert migrate.upgrade_to_head(engine) == "0049"
    assert migrate.upgrade_to_head(engine) == "0049"
    with engine.connect() as connection:
        after = connection.exec_driver_sql(
            "SELECT coupon_id,coupon_digest,entitlement_valid_from,entitlement_valid_until,"
            "entitlement_effect_timing,entitlement_duration_seconds "
            "FROM platform_coupon_definitions"
        ).one()
    assert after[:4] == before
    assert after[4:] == ("FIXED_ABSOLUTE", None)
    columns = {item["name"]: item for item in sa.inspect(engine).get_columns(
        "platform_coupon_definitions")}
    assert columns["entitlement_valid_from"]["nullable"] is True
    assert columns["entitlement_effect_timing"]["nullable"] is False
    checks = _shape(engine, "platform_coupon_definitions")["checks"]
    assert "ck_platform_coupon_entitlement_shape" in checks
    assert "1296000" in checks["ck_platform_coupon_entitlement_shape"]


SQLITE_COUPON_TRIGGER_RELATIONS = (
    ("platform_coupon_definitions_privacy_insert", "platform_coupon_definitions"),
    ("platform_coupon_definitions_privacy_update", "platform_coupon_definitions"),
    ("platform_coupon_redemptions_capacity", "platform_coupon_redemptions"),
    ("platform_coupon_redemptions_privacy_insert", "platform_coupon_redemptions"),
    ("platform_coupon_redemptions_privacy_update", "platform_coupon_redemptions"),
    ("platform_entitlement_events_source_exact", "platform_entitlement_events"),
    ("platform_entitlement_events_privacy_insert", "platform_entitlement_events"),
    ("platform_entitlement_events_privacy_update", "platform_entitlement_events"),
)


def test_current_0049_startup_accepts_exact_sqlite_trigger_multiset_without_writes(tmp_path):
    engine = _engine(tmp_path, "0049-current-trigger-control.db")
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0049")
    with engine.connect() as connection:
        before = _coupon_state(connection)
    assert _startup(engine) == "0049"
    with engine.connect() as connection:
        assert _coupon_state(connection) == before


@pytest.mark.parametrize(
    ("mutation", "trigger_name"),
    tuple(("wrong_relation", name) for name, _relation in SQLITE_COUPON_TRIGGER_RELATIONS)
    + (
        ("same_name_true_check", None),
        ("missing_trigger", "platform_coupon_redemptions_capacity"),
        ("wrong_timing", "platform_coupon_redemptions_capacity"),
        ("wrong_operation", "platform_coupon_redemptions_capacity"),
        ("wrong_when", "platform_coupon_redemptions_capacity"),
        ("literal_case", "platform_coupon_redemptions_capacity"),
        ("wrong_body", "platform_coupon_redemptions_capacity"),
        ("wrong_schema", "platform_entitlement_events_source_exact"),
        ("duplicate_catalog_row", "platform_coupon_definitions_privacy_insert"),
        ("missing_duration_column", None),
    ),
    ids=lambda value: value,
)
def test_current_0049_startup_refuses_partial_coupon_semantics_without_writes(
    tmp_path, mutation, trigger_name,
):
    engine = _engine(tmp_path, f"0049-current-tamper-{mutation}.db")
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0049")
    with engine.connect() as connection:
        before = _coupon_state(connection)
    if mutation == "wrong_relation":
        relation = dict(SQLITE_COUPON_TRIGGER_RELATIONS)[trigger_name]
        wrong_relation = next(
            item for item in migrate._COUPON_READINESS_TABLES if item != relation)
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA writable_schema=ON")
            try:
                connection.exec_driver_sql(
                    "UPDATE sqlite_master SET tbl_name=? "
                    "WHERE type='trigger' AND name=?",
                    (wrong_relation, trigger_name),
                )
            finally:
                connection.exec_driver_sql("PRAGMA writable_schema=OFF")
    elif mutation == "same_name_true_check":
        check = _shape(engine, "platform_coupon_definitions")["checks"][
            "ck_platform_coupon_entitlement_shape"]
        _replace_sqlite_table_sql(
            engine,
            f"CONSTRAINT ck_platform_coupon_entitlement_shape CHECK ({check})",
            "CONSTRAINT ck_platform_coupon_entitlement_shape CHECK (1=1)",
        )
    elif mutation == "missing_trigger":
        with engine.begin() as connection:
            connection.exec_driver_sql(f"DROP TRIGGER {trigger_name}")
    elif mutation in {
        "wrong_timing", "wrong_operation", "wrong_when", "literal_case", "wrong_body",
    }:
        with engine.begin() as connection:
            if mutation == "wrong_timing":
                transform = lambda sql: sql.replace("BEFORE INSERT", "AFTER INSERT", 1)
            elif mutation == "wrong_operation":
                transform = lambda sql: sql.replace("BEFORE INSERT", "BEFORE UPDATE", 1)
            elif mutation == "wrong_when":
                transform = lambda sql: sql.replace("WHEN NEW.status", "WHEN 0 AND NEW.status", 1)
            elif mutation == "literal_case":
                transform = lambda sql: sql.replace("'ACCEPTED'", "'accepted'")
            else:
                transform = lambda _sql: (
                    "CREATE TRIGGER platform_coupon_redemptions_capacity BEFORE INSERT "
                    "ON platform_coupon_redemptions BEGIN SELECT 1; END")
            _replace_sqlite_trigger(connection, trigger_name, transform)
    elif mutation == "wrong_schema":
        with engine.begin() as connection:
            original = _sqlite_trigger_sql(connection, trigger_name)
            connection.exec_driver_sql(f"DROP TRIGGER {trigger_name}")
            connection.exec_driver_sql(
                original.replace("CREATE TRIGGER", "CREATE TEMP TRIGGER", 1))
    elif mutation == "duplicate_catalog_row":
        with engine.begin() as connection:
            row = connection.exec_driver_sql(
                "SELECT type,name,tbl_name,rootpage,sql FROM sqlite_master "
                "WHERE type='trigger' AND name=?", (trigger_name,)
            ).one()
            connection.exec_driver_sql("PRAGMA writable_schema=ON")
            try:
                connection.exec_driver_sql(
                    "INSERT INTO sqlite_master(type,name,tbl_name,rootpage,sql) "
                    "VALUES(?,?,?,?,?)", tuple(row))
            finally:
                connection.exec_driver_sql("PRAGMA writable_schema=OFF")
    else:
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0048")
            command.stamp(migrate.alembic_config(connection), "0049", purge=True)
    with pytest.raises(RuntimeError, match="coupon readiness|current execution relational model"):
        _startup(engine)
    with engine.connect() as connection:
        assert _coupon_state(connection) == before
        assert before[0] == "0049"


def test_current_0049_startup_rejects_preexisting_malformed_row_with_exact_guard(tmp_path):
    engine = _engine(tmp_path, "0049-current-malformed-row.db")
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0049")
    check = _shape(engine, "platform_coupon_definitions")["checks"][
        "ck_platform_coupon_entitlement_shape"]
    original = _replace_sqlite_table_sql(
        engine,
        f"CONSTRAINT ck_platform_coupon_entitlement_shape CHECK ({check})",
        "CONSTRAINT ck_platform_coupon_entitlement_shape CHECK (1=1)",
    )
    address = "sha256:" + "a" * 64
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO platform_plan_versions(plan_version_id,plan_code,version,amount_minor,"
            "currency,billing_interval,entitlement_set_address,policy_state,created_at) VALUES("
            "'plan.malformed','BETA',1,0,'INR','UNKNOWN',?,'APPROVED','2026-09-01')",
            (address,),
        )
        connection.exec_driver_sql(
            "INSERT INTO platform_coupon_definitions(coupon_id,coupon_digest,plan_version_id,"
            "policy_address,trial_policy_address,discount_policy_address,entitlement_code,"
            "entitlement_transition,entitlement_valid_from,entitlement_valid_until,valid_from,"
            "valid_until,max_redemptions,per_owner_limit,status,created_at,"
            "entitlement_effect_timing,entitlement_duration_seconds) VALUES("
            "'coupon.malformed',?,'plan.malformed',?,?,NULL,'PRODUCT_ACCESS','GRANT',NULL,NULL,"
            "'2026-09-01',NULL,1,1,'ACTIVE','2026-09-01','DYNAMIC_DURATION',1)",
            ("b" * 64, address, address),
        )
        version = connection.exec_driver_sql("PRAGMA schema_version").scalar_one()
        connection.exec_driver_sql("PRAGMA writable_schema=ON")
        try:
            connection.exec_driver_sql(
                "UPDATE sqlite_master SET sql=? WHERE type='table' "
                "AND name='platform_coupon_definitions'", (original,))
        finally:
            connection.exec_driver_sql("PRAGMA writable_schema=OFF")
        connection.exec_driver_sql(f"PRAGMA schema_version={version + 1}")
    with pytest.raises(RuntimeError, match="malformed definition envelope"):
        _startup(engine)
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT count(*) FROM platform_coupon_definitions").scalar_one() == 1
        assert connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version").scalar_one() == "0049"


def test_0049_interruption_rolls_back_then_retry_converges(tmp_path):
    engine = _engine(tmp_path, "0049-interruption.db")
    _prepare_0048(engine)
    with engine.begin() as connection:
        _seed_0048_fixed_coupon(connection)
    fired = False

    def interrupt(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal fired
        if not fired and "UPDATE platform_coupon_definitions SET entitlement_effect_timing" in statement:
            fired = True
            raise RuntimeError("injected 0049 interruption")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected 0049 interruption"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0049")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    assert fired and migrate.schema_version(engine) == "0048"
    assert "entitlement_effect_timing" not in {
        item["name"] for item in sa.inspect(engine).get_columns(
            "platform_coupon_definitions")
    }
    assert migrate.upgrade_to_head(engine) == "0049"


def test_0049_partial_and_stale_sources_refuse_before_migration_writes(tmp_path):
    partial = _engine(tmp_path, "0049-partial.db")
    _prepare_0048(partial)
    with partial.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE platform_coupon_definitions "
            "ADD COLUMN entitlement_effect_timing VARCHAR(24)"
        )
    with pytest.raises(RuntimeError, match="partial or unexpected"):
        with partial.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0049")
    assert migrate.schema_version(partial) == "0048"
    assert "entitlement_duration_seconds" not in {
        item["name"] for item in sa.inspect(partial).get_columns(
            "platform_coupon_definitions")
    }

    stale = _engine(tmp_path, "0049-stale.db")
    _prepare_0048(stale)
    with stale.begin() as connection:
        connection.exec_driver_sql("UPDATE alembic_version SET version_num='0047'")
    with pytest.raises(RuntimeError, match="exact accepted 0048"):
        migrate.upgrade_to_head(stale)
    assert migrate.schema_version(stale) == "0047"


def test_0049_conditional_downgrade_and_forward_repair_barrier(tmp_path):
    fixed = _engine(tmp_path, "0049-fixed-down.db")
    _prepare_0048(fixed)
    with fixed.begin() as connection:
        _seed_0048_fixed_coupon(connection)
    assert migrate.upgrade_to_head(fixed) == "0049"
    with fixed.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0048")
    assert migrate.schema_version(fixed) == "0048"
    with fixed.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT entitlement_valid_from,entitlement_valid_until "
            "FROM platform_coupon_definitions"
        ).one()
    assert row == ("2026-09-01 01:02:03.123456", "2026-09-16 01:02:03.123456")
    assert migrate.upgrade_to_head(fixed) == "0049"

    dynamic = _engine(tmp_path, "0049-dynamic-down.db")
    Base.metadata.create_all(dynamic)
    migrate.stamp(dynamic, "0049")
    with dynamic.begin() as connection:
        address = "sha256:" + "a" * 64
        connection.exec_driver_sql(
            "INSERT INTO platform_plan_versions(plan_version_id,plan_code,version,amount_minor,"
            "currency,billing_interval,entitlement_set_address,policy_state,created_at) VALUES("
            "'plan.dynamic','BETA',1,0,'INR','UNKNOWN',?,'APPROVED','2026-09-01')",
            (address,),
        )
        connection.exec_driver_sql(
            "INSERT INTO platform_coupon_definitions(coupon_id,coupon_digest,plan_version_id,"
            "policy_address,trial_policy_address,discount_policy_address,entitlement_code,"
            "entitlement_transition,entitlement_valid_from,entitlement_valid_until,"
            "entitlement_effect_timing,entitlement_duration_seconds,valid_from,valid_until,"
            "max_redemptions,per_owner_limit,status,created_at) VALUES('coupon.dynamic',?,"
            "'plan.dynamic',?,?,NULL,'PRODUCT_ACCESS','GRANT',NULL,NULL,'DYNAMIC_DURATION',"
            "1296000,'2026-09-01',NULL,5,1,'ACTIVE','2026-09-01')",
            ("b" * 64, address, address),
        )
    with dynamic.connect() as connection:
        before = _exact_rows(connection, "platform_coupon_definitions", "coupon_id")
    with pytest.raises(RuntimeError, match="forward repair"):
        with dynamic.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0048")
    assert migrate.schema_version(dynamic) == "0049"
    with dynamic.connect() as connection:
        assert _exact_rows(connection, "platform_coupon_definitions", "coupon_id") == before


def test_head_empty_install_exact_0047_upgrade_restart_and_model_parity(tmp_path):
    assert migrate.head_revision() == "0049"
    fresh = _engine(tmp_path, "fresh.db")
    Base.metadata.create_all(fresh)
    migrate.stamp(fresh, "0049")
    assert migrate.schema_version(fresh) == "0049"

    upgraded = _engine(tmp_path, "upgraded.db")
    _prepare_0047(upgraded)
    before = set(sa.inspect(upgraded).get_table_names())
    with upgraded.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0048")
    assert migrate.upgrade_to_head(upgraded) == "0049"
    assert migrate.schema_version(upgraded) == "0049"
    assert set(sa.inspect(upgraded).get_table_names()) - before == TABLES
    assert migrate.init_schema(
        upgraded,
        create_all=lambda: pytest.fail("current startup must not create"),
        legacy_migrate=lambda: pytest.fail("current startup must not adopt"),
        expected_tables=Base.metadata.tables,
    ) == "0049"
    for table in TABLES:
        assert _shape(upgraded, table) == _shape(fresh, table)
        assert _triggers(upgraded, table) == _triggers(fresh, table)
    fresh_event = _shape(fresh, "platform_entitlement_events")
    upgraded_event = _shape(upgraded, "platform_entitlement_events")
    assert fresh_event["checks"] == upgraded_event["checks"]
    assert "BETA_TRIAL" in upgraded_event["checks"]["ck_platform_entitlement_source"]


def test_populated_migration_built_exact_0047_preserves_0046_and_editor_facts(tmp_path):
    engine = _engine(tmp_path, "populated-exact-0047.db")
    Base.metadata.create_all(engine)
    revision_0046 = importlib.import_module(
        "migrations.versions.20260830_0046_v0_platform_operations"
    )
    with engine.begin() as connection:
        for table_name in (
            "account_trial_uses", "account_profile_evidence",
            "ir_v2_editor_presentations",
        ):
            Base.metadata.tables[table_name].drop(connection, checkfirst=False)
        metadata_0046 = revision_0046._revision_metadata("sqlite")
        for table in reversed(metadata_0046.sorted_tables):
            table.drop(connection, checkfirst=False)
    migrate.stamp(engine, "0045")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0047")
    assert migrate.schema_version(engine) == "0047"

    address = "sha256:" + "a" * 64
    coupon_digest = "b" * 64
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO organizations(organization_id,name,status,created_at,updated_at) "
            "VALUES('owner.fixture','Fixture','active','2026-09-01','2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO projects(project_id,owner_id,name,description,status,created_at,updated_at) "
            "VALUES('project.fixture','owner.fixture','Fixture Project','','active',"
            "'2026-09-01','2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO graph_artifacts(owner_id,identifier,project_id,display_name,draft_json,"
            "draft_revision,published_revision,current_version,created_at,updated_at) VALUES("
            "'owner.fixture','graph.fixture','project.fixture','Fixture Graph','{}',3,NULL,NULL,"
            "'2026-09-01','2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO ir_v2_editor_presentations(owner_id,graph_identifier,format_version,"
            "presentation_json,revision,updated_at) VALUES("
            "'owner.fixture','graph.fixture',2,'{\"nodes\":{\"entry\":{\"x\":12,\"y\":34}}}',"
            "7,'2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO platform_plan_versions(plan_version_id,plan_code,version,amount_minor,"
            "currency,billing_interval,entitlement_set_address,policy_state,"
            "test_provider_plan_address,live_provider_plan_address,created_at) VALUES("
            "'plan.fixture','BETA',1,0,'INR','UNKNOWN',?,'APPROVED',NULL,NULL,'2026-09-01')",
            (address,),
        )
        connection.exec_driver_sql(
            "INSERT INTO platform_coupon_definitions(coupon_id,coupon_digest,plan_version_id,"
            "policy_address,trial_policy_address,discount_policy_address,entitlement_code,"
            "entitlement_transition,entitlement_valid_from,entitlement_valid_until,valid_from,"
            "valid_until,max_redemptions,per_owner_limit,status,created_at) VALUES("
            "'coupon.fixture',?,'plan.fixture',?,?,NULL,'PRODUCT_ACCESS','GRANT','2026-09-01',"
            "'2026-09-16','2026-09-01','2026-09-02',5,1,'ACTIVE','2026-09-01')",
            (coupon_digest, address, address),
        )
        connection.exec_driver_sql(
            "INSERT INTO platform_coupon_redemptions(redemption_id,coupon_id,owner_ref,"
            "policy_address,status,entitlement_code,entitlement_transition,"
            "entitlement_valid_from,entitlement_valid_until,redeemed_at) VALUES("
            "'redemption.fixture','coupon.fixture','owner.fixture',?,'ACCEPTED',"
            "'PRODUCT_ACCESS','GRANT','2026-09-01','2026-09-16','2026-09-01')",
            (address,),
        )
        connection.exec_driver_sql(
            "INSERT INTO platform_entitlement_events(event_id,owner_ref,entitlement_code,mode,"
            "source_kind,source_ref,transition,policy_address,valid_from,valid_until,effective_at,"
            "recorded_at) VALUES('event.fixture','owner.fixture','PRODUCT_ACCESS','INTERNAL',"
            "'COUPON_REDEMPTION','redemption.fixture','GRANT',?,'2026-09-01','2026-09-16',"
            "'2026-09-01','2026-09-01')",
            (address,),
        )
        connection.exec_driver_sql(
            "INSERT INTO platform_current_entitlements(owner_ref,entitlement_code,mode,state,"
            "source_event_id,effective_at,valid_until,projection_version,rebuilt_at) VALUES("
            "'owner.fixture','PRODUCT_ACCESS','INTERNAL','ACTIVE','event.fixture','2026-09-01',"
            "'2026-09-16',1,'2026-09-01')"
        )

    preserved = {
        table: None for table in (
            "platform_plan_versions", "platform_coupon_definitions",
            "platform_coupon_redemptions", "platform_entitlement_events",
            "platform_current_entitlements", "ir_v2_editor_presentations",
        )
    }
    with engine.connect() as connection:
        for table in preserved:
            preserved[table] = _exact_rows(connection, table, "1")
        source_trigger_before = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='trigger' "
            "AND name='platform_entitlement_events_source_exact'"
        ).scalar_one()
    assert "BETA_TRIAL" not in source_trigger_before
    fixture_ids = {
        row[0].decode("utf-8") for table in preserved for row in preserved[table]
    }
    assert {
        "plan.fixture", "coupon.fixture", "redemption.fixture", "event.fixture",
        "owner.fixture",
    } <= fixture_ids

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0048")
    with engine.connect() as connection:
        for table, before in preserved.items():
            assert _exact_rows(connection, table, "1") == before
        source_trigger_after = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='trigger' "
            "AND name='platform_entitlement_events_source_exact'"
        ).scalar_one()
    for exact_source in (
        "NEW.source_kind='BILLING_RECEIPT'", "NEW.source_kind='COUPON_REDEMPTION'",
        "NEW.source_kind='COMPLIMENTARY_GRANT'",
    ):
        assert exact_source in source_trigger_before
        assert exact_source in source_trigger_after
    assert "NEW.source_kind='BETA_TRIAL'" in source_trigger_after


@pytest.mark.parametrize("heads", [("0046",), ("0046", "0047")])
def test_managed_stale_or_branched_source_refuses_before_0048_writes(tmp_path, heads):
    engine = _engine(tmp_path, "stale-" + "-".join(heads) + ".db")
    _prepare_0047(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM alembic_version")
        for head in heads:
            connection.exec_driver_sql(
                "INSERT INTO alembic_version(version_num) VALUES(?)", (head,)
            )
    before = set(sa.inspect(engine).get_table_names())
    with pytest.raises(RuntimeError, match="exact accepted 0048"):
        migrate.upgrade_to_head(engine)
    assert set(sa.inspect(engine).get_table_names()) == before
    assert not TABLES.intersection(before)


def test_partial_or_preexisting_table_refuses_without_touching_0047(tmp_path):
    engine = _engine(tmp_path, "partial.db")
    _prepare_0047(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE account_profile_evidence(profile_evidence_id VARCHAR(128) PRIMARY KEY)"
        )
    before = set(sa.inspect(engine).get_table_names())
    with pytest.raises(RuntimeError, match="partial or pre-existing"):
        with engine.begin() as connection:
            command.upgrade(migrate.alembic_config(connection), "0048")
    assert migrate.schema_version(engine) == "0047"
    assert set(sa.inspect(engine).get_table_names()) == before
    event_check = _shape(engine, "platform_entitlement_events")["checks"]
    assert "BETA_TRIAL" not in event_check["ck_platform_entitlement_source"]


@pytest.mark.parametrize("needle", (
    "CREATE TABLE account_trial_uses",
    "CREATE TRIGGER platform_entitlement_events_source_exact",
))
def test_interrupted_0048_rolls_back_and_retry_converges(tmp_path, needle):
    engine = _engine(tmp_path, "interrupted-" + str(abs(hash(needle))) + ".db")
    _prepare_0047(engine)
    interrupted = False

    def interrupt(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal interrupted
        if not interrupted and needle in statement:
            interrupted = True
            raise RuntimeError("injected 0048 interruption")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected 0048 interruption"):
            with engine.begin() as connection:
                command.upgrade(migrate.alembic_config(connection), "0048")
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    assert interrupted
    assert migrate.schema_version(engine) == "0047"
    assert not TABLES.intersection(sa.inspect(engine).get_table_names())
    assert "BETA_TRIAL" not in _shape(
        engine, "platform_entitlement_events"
    )["checks"]["ck_platform_entitlement_source"]
    assert "platform_entitlement_events_source_exact" in _triggers(
        engine, "platform_entitlement_events"
    )
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0048")
    assert migrate.schema_version(engine) == "0048"


def test_empty_downgrade_is_lossless_but_durable_facts_require_restore(tmp_path):
    empty = _engine(tmp_path, "empty-down.db")
    Base.metadata.create_all(empty)
    migrate.stamp(empty, "0048")
    with empty.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0047")
    assert migrate.schema_version(empty) == "0047"
    assert not TABLES.intersection(sa.inspect(empty).get_table_names())
    assert "BETA_TRIAL" not in _shape(
        empty, "platform_entitlement_events"
    )["checks"]["ck_platform_entitlement_source"]

    populated = _engine(tmp_path, "populated-down.db")
    Base.metadata.create_all(populated)
    migrate.stamp(populated, "0048")
    with populated.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO organizations(organization_id,name,status,created_at,updated_at) "
            "VALUES('owner.alpha','Synthetic','active','2026-09-01','2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO users(user_id,email_normalized,display_name,status,created_at,updated_at) "
            "VALUES('user.alpha','synthetic@example.invalid','Synthetic','active','2026-09-01','2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO memberships(organization_id,user_id,role,status,created_at,updated_at) "
            "VALUES('owner.alpha','user.alpha','member','active','2026-09-01','2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO account_profile_evidence(profile_evidence_id,owner_ref,user_ref,"
            "policy_address,evidence_address,satisfied_fields_json,attested_at) VALUES("
            "'profile.one','owner.alpha','user.alpha',?,?,'[]','2026-09-01')",
            ("sha256:" + "a" * 64, "sha256:" + "b" * 64),
        )
    with pytest.raises(RuntimeError, match="destructive downgrade"):
        with populated.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0047")
    assert migrate.schema_version(populated) == "0048"
    assert TABLES.issubset(sa.inspect(populated).get_table_names())


def test_account_facts_are_immutable_and_direct_invalid_source_is_rejected(tmp_path):
    engine = _engine(tmp_path, "guards.db")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO organizations(organization_id,name,status,created_at,updated_at) "
            "VALUES('owner.alpha','Synthetic','active','2026-09-01','2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO users(user_id,email_normalized,display_name,status,created_at,updated_at) "
            "VALUES('user.alpha','synthetic@example.invalid','Synthetic','active','2026-09-01','2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO memberships(organization_id,user_id,role,status,created_at,updated_at) "
            "VALUES('owner.alpha','user.alpha','member','active','2026-09-01','2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO account_profile_evidence(profile_evidence_id,owner_ref,user_ref,"
            "policy_address,evidence_address,satisfied_fields_json,attested_at) VALUES("
            "'profile.one','owner.alpha','user.alpha',?,?,'[]','2026-09-01')",
            ("sha256:" + "a" * 64, "sha256:" + "b" * 64),
        )
    with pytest.raises(sa.exc.IntegrityError, match="immutable"):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE account_profile_evidence SET satisfied_fields_json='[\"profile.country\"]'"
            )
    with pytest.raises(sa.exc.IntegrityError, match="forbidden content"):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO account_profile_evidence(profile_evidence_id,owner_ref,user_ref,"
                "policy_address,evidence_address,satisfied_fields_json,attested_at) VALUES("
                "'profile.private','owner.alpha','user.alpha',?,?,'[\"strategy.secret\"]',"
                "'2026-09-01')",
                ("sha256:" + "a" * 64, "sha256:" + "c" * 64),
            )
    with pytest.raises(sa.exc.IntegrityError, match="source mismatch"):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO platform_entitlement_events(event_id,owner_ref,entitlement_code,mode,"
                "source_kind,source_ref,transition,policy_address,valid_from,valid_until,effective_at,"
                "recorded_at) VALUES('event.invalid','owner.alpha','PRODUCT_ACCESS','INTERNAL',"
                "'BETA_TRIAL','trial.missing','GRANT',?,'2026-09-01','2026-09-16',"
                "'2026-09-01','2026-09-01')",
                ("sha256:" + "a" * 64,),
            )
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO account_profile_evidence(profile_evidence_id,owner_ref,user_ref,"
            "policy_address,evidence_address,satisfied_fields_json,attested_at) VALUES("
            "'profile.noncanonical','owner.alpha','user.alpha',?,?,'[ \"profile.country\" ]',"
            "'2026-09-01')",
            ("sha256:" + "a" * 64, "sha256:" + "d" * 64),
        )
    with engine.connect() as connection:
        with pytest.raises(AccountCommerceRefused, match="noncanonical"):
            validate_persisted_account_commerce(connection)


def test_postgresql16_historical_0047_target_is_constructed_explicitly(pg_sandbox):
    engine = pg_sandbox.engine("account_commerce_historical_0047")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        for view in (
            "platform_analytics_event_counts", "platform_operator_entitlement_counts",
            "platform_operator_support_counts",
        ):
            connection.exec_driver_sql(f"DROP VIEW IF EXISTS {view}")
        for table_name in (
            "account_trial_uses", "account_profile_evidence",
            "ir_v2_editor_presentations",
        ):
            Base.metadata.tables[table_name].drop(connection)
        operations = __import__(
            "app.platform_operations.repository", fromlist=["OPERATIONS_TABLES"]
        ).OPERATIONS_TABLES
        for table in [item for item in Base.metadata.sorted_tables
                      if item.name in operations][::-1]:
            table.drop(connection)
        command.stamp(migrate.alembic_config(connection), "0045", purge=True)
        command.upgrade(migrate.alembic_config(connection), "0047")
    assert migrate.schema_version(engine) == "0047"
    assert not TABLES.intersection(sa.inspect(engine).get_table_names())
    assert "ir_v2_editor_presentations" in sa.inspect(engine).get_table_names()
    checks = {item["name"]: item["sqltext"] for item in sa.inspect(
        engine).get_check_constraints("platform_entitlement_events")}
    assert "BETA_TRIAL" not in checks["ck_platform_entitlement_source"]


def test_postgresql16_0049_exact_upgrade_lock_interruption_and_shape(pg_sandbox):
    engine = pg_sandbox.engine("coupon_dynamic_0049")
    _prepare_0048(engine)
    address = "sha256:" + "a" * 64
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO platform_plan_versions(plan_version_id,plan_code,version,amount_minor,"
            "currency,billing_interval,entitlement_set_address,policy_state,created_at) VALUES("
            "'plan.pg','BETA',1,0,'INR','UNKNOWN',:address,'APPROVED','2026-09-01')"
        ), {"address": address})
        connection.execute(sa.text(
            "INSERT INTO platform_coupon_definitions(coupon_id,coupon_digest,plan_version_id,"
            "policy_address,trial_policy_address,discount_policy_address,entitlement_code,"
            "entitlement_transition,entitlement_valid_from,entitlement_valid_until,valid_from,"
            "valid_until,max_redemptions,per_owner_limit,status,created_at) VALUES("
            "'coupon.pg',:digest,'plan.pg',:address,:address,NULL,'PRODUCT_ACCESS','GRANT',"
            "'2026-09-01 01:02:03.123456','2026-09-16 01:02:03.123456',"
            "'2026-09-01',NULL,5,1,'ACTIVE','2026-09-01')"
        ), {"digest": "b" * 64, "address": address})

    owner = engine.connect()
    contender = engine.connect()
    transaction = owner.begin()
    owner.exec_driver_sql("SELECT pg_advisory_xact_lock(4200049)")
    try:
        with pytest.raises(sa.exc.DBAPIError, match="lock timeout"):
            with contender.begin():
                contender.exec_driver_sql("SET LOCAL lock_timeout='100ms'")
                contender.exec_driver_sql("SELECT pg_advisory_xact_lock(4200049)")
        assert migrate.schema_version(engine) == "0048"
    finally:
        transaction.rollback()
        owner.close()
        contender.close()

    fired = False

    def interrupt(_connection, _cursor, statement, _parameters, _context, _many):
        nonlocal fired
        if not fired and "ADD COLUMN entitlement_duration_seconds" in statement:
            fired = True
            raise RuntimeError("injected PostgreSQL 0049 interruption")

    sa.event.listen(engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(RuntimeError, match="injected PostgreSQL 0049"):
            migrate.upgrade_to_head(engine)
    finally:
        sa.event.remove(engine, "before_cursor_execute", interrupt)
    assert fired and migrate.schema_version(engine) == "0048"
    assert "entitlement_effect_timing" not in {
        item["name"] for item in sa.inspect(engine).get_columns(
            "platform_coupon_definitions")
    }
    assert migrate.init_schema(
        engine,
        create_all=lambda: pytest.fail("exact 0048 PostgreSQL must migrate, not create"),
        legacy_migrate=lambda: pytest.fail("managed PostgreSQL must not adopt"),
        expected_tables=Base.metadata.tables,
    ) == "0049"
    with engine.connect() as connection:
        row = connection.execute(sa.text(
            "SELECT entitlement_effect_timing,entitlement_duration_seconds,"
            "entitlement_valid_from,entitlement_valid_until FROM "
            "platform_coupon_definitions WHERE coupon_id='coupon.pg'"
        )).one()
    assert row == (
        "FIXED_ABSOLUTE", None,
        dt.datetime(2026, 9, 1, 1, 2, 3, 123456),
        dt.datetime(2026, 9, 16, 1, 2, 3, 123456),
    )
    with pytest.raises(sa.exc.IntegrityError, match="entitlement_shape"):
        with engine.begin() as connection:
            connection.execute(sa.text(
                "UPDATE platform_coupon_definitions "
                "SET entitlement_effect_timing='DYNAMIC_DURATION' "
                "WHERE coupon_id='coupon.pg'"
            ))


def test_postgresql16_0049_concurrent_migration_owners_wait_then_refuse(pg_sandbox):
    engine = pg_sandbox.engine("coupon_dynamic_0049_concurrent")
    _prepare_0048(engine)
    address = "sha256:" + "a" * 64
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO platform_plan_versions(plan_version_id,plan_code,version,amount_minor,"
            "currency,billing_interval,entitlement_set_address,policy_state,created_at) VALUES("
            "'plan.concurrent.pg','BETA',1,0,'INR','UNKNOWN',:address,'APPROVED','2026-09-01')"
        ), {"address": address})
        connection.execute(sa.text(
            "INSERT INTO platform_coupon_definitions(coupon_id,coupon_digest,plan_version_id,"
            "policy_address,trial_policy_address,discount_policy_address,entitlement_code,"
            "entitlement_transition,entitlement_valid_from,entitlement_valid_until,valid_from,"
            "valid_until,max_redemptions,per_owner_limit,status,created_at) VALUES("
            "'coupon.concurrent.pg',:digest,'plan.concurrent.pg',:address,:address,NULL,"
            "'PRODUCT_ACCESS','GRANT','2026-09-01','2026-09-16','2026-09-01',NULL,5,1,"
            "'ACTIVE','2026-09-01')"), {"digest": "c" * 64, "address": address})
    with engine.connect() as connection:
        before = connection.execute(sa.text(
            "SELECT coupon_id,coupon_digest,entitlement_valid_from,entitlement_valid_until "
            "FROM platform_coupon_definitions ORDER BY coupon_id")).all()
    owner_thread: dict[str, int | None] = {"id": None}
    contender_seen = threading.Event()
    owner_lock = threading.Lock()
    barrier = threading.Barrier(2)

    def before_execute(_connection, _cursor, statement, _parameters, _context, _many):
        if "pg_advisory_xact_lock(4200049)" not in statement:
            return
        current = threading.get_ident()
        with owner_lock:
            if owner_thread["id"] is None:
                owner_thread["id"] = current
            elif owner_thread["id"] != current:
                contender_seen.set()

    def after_execute(_connection, _cursor, statement, _parameters, _context, _many):
        if "pg_advisory_xact_lock(4200049)" not in statement:
            return
        current = threading.get_ident()
        if owner_thread["id"] == current:
            assert contender_seen.wait(timeout=10), "second migration owner never contended"

    sa.event.listen(engine, "before_cursor_execute", before_execute)
    sa.event.listen(engine, "after_cursor_execute", after_execute)

    def migrate_once():
        barrier.wait(timeout=10)
        try:
            return ("RETURNED", migrate.upgrade_to_head(engine))
        except RuntimeError as exc:
            return ("REFUSED", str(exc))

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _item: migrate_once(), range(2)))
    finally:
        sa.event.remove(engine, "before_cursor_execute", before_execute)
        sa.event.remove(engine, "after_cursor_execute", after_execute)
    assert sorted(result[0] for result in results) == ["REFUSED", "RETURNED"]
    assert any(result == ("RETURNED", "0049") for result in results)
    assert any("concurrent migration owner" in result[1] for result in results
               if result[0] == "REFUSED")
    assert migrate.schema_version(engine) == "0049"
    with engine.connect() as connection:
        after = connection.execute(sa.text(
            "SELECT coupon_id,coupon_digest,entitlement_valid_from,entitlement_valid_until "
            "FROM platform_coupon_definitions ORDER BY coupon_id")).all()
        timing = connection.execute(sa.text(
            "SELECT entitlement_effect_timing,entitlement_duration_seconds "
            "FROM platform_coupon_definitions WHERE coupon_id='coupon.concurrent.pg'"
        )).one()
    assert after == before
    assert timing == ("FIXED_ABSOLUTE", None)


POSTGRESQL_COUPON_TRIGGERS = (
    ("platform_coupon_definitions_privacy_guard", "platform_coupon_definitions",
     "BEFORE INSERT OR UPDATE", "platform_coupon_definitions_privacy_guard_fn"),
    ("platform_coupon_redemptions_capacity", "platform_coupon_redemptions",
     "BEFORE INSERT", "platform_coupon_redemptions_capacity_fn"),
    ("platform_coupon_redemptions_privacy_guard", "platform_coupon_redemptions",
     "BEFORE INSERT OR UPDATE", "platform_coupon_redemptions_privacy_guard_fn"),
    ("platform_entitlement_events_source_exact", "platform_entitlement_events",
     "BEFORE INSERT", "platform_entitlement_events_source_exact_fn"),
    ("platform_entitlement_events_privacy_guard", "platform_entitlement_events",
     "BEFORE INSERT OR UPDATE", "platform_entitlement_events_privacy_guard_fn"),
)


def _recreate_postgresql_trigger(
    connection, trigger_name, relation, timing_operations, function, *,
    target_relation=None, when="",
):
    connection.exec_driver_sql(f"DROP TRIGGER {trigger_name} ON {relation}")
    connection.exec_driver_sql(
        f"CREATE TRIGGER {trigger_name} {timing_operations} ON "
        f"{target_relation or relation} FOR EACH ROW {when} "
        f"EXECUTE FUNCTION {function}()")


def test_postgresql16_current_0049_accepts_exact_coupon_trigger_multiset_without_writes(
    pg_sandbox,
):
    engine = pg_sandbox.engine("coupon_readiness_exact_control")
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0049")
    with engine.connect() as connection:
        before = _coupon_state(connection)
    assert _startup(engine) == "0049"
    with engine.connect() as connection:
        assert _coupon_state(connection) == before


@pytest.mark.parametrize(
    ("mutation", "trigger_spec"),
    tuple(("wrong_relation", spec) for spec in POSTGRESQL_COUPON_TRIGGERS)
    + (
        ("same_name_true_check", None),
        ("unvalidated_exact_check", None),
        ("wrong_relation_schema", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("duplicate_relation", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("duplicate_schema", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("disabled", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("internal", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("missing", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("wrong_tgtype", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("wrong_when", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("wrong_function", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("wrong_function_schema", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("wrong_function_body", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("literal_case", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("wrong_language", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("security_definer", POSTGRESQL_COUPON_TRIGGERS[1]),
        ("missing_duration_column", None),
        ("malformed_redemption", None),
    ),
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_postgresql16_current_0049_startup_refuses_coupon_tamper(
    pg_sandbox, mutation, trigger_spec,
):
    engine = pg_sandbox.engine(f"coupon_readiness_{mutation}")
    Base.metadata.create_all(engine)
    migrate.stamp(engine, "0049")
    with engine.begin() as connection:
        if trigger_spec is not None:
            trigger_name, relation, timing_operations, function = trigger_spec
        if mutation == "same_name_true_check":
            connection.exec_driver_sql(
                "ALTER TABLE platform_coupon_definitions DROP CONSTRAINT "
                "ck_platform_coupon_entitlement_shape")
            connection.exec_driver_sql(
                "ALTER TABLE platform_coupon_definitions ADD CONSTRAINT "
                "ck_platform_coupon_entitlement_shape CHECK (true)")
        elif mutation == "unvalidated_exact_check":
            check = next(
                item for item in Base.metadata.tables[
                    "platform_coupon_definitions"].constraints
                if item.name == "ck_platform_coupon_entitlement_shape")
            expression = str(check.sqltext.compile(dialect=connection.dialect))
            connection.exec_driver_sql(
                "ALTER TABLE platform_coupon_definitions DROP CONSTRAINT "
                "ck_platform_coupon_entitlement_shape")
            connection.exec_driver_sql(
                "ALTER TABLE platform_coupon_definitions ADD CONSTRAINT "
                f"ck_platform_coupon_entitlement_shape CHECK ({expression}) NOT VALID")
        elif mutation == "wrong_relation":
            wrong_relation = next(
                item for item in migrate._COUPON_READINESS_TABLES if item != relation)
            _recreate_postgresql_trigger(
                connection, trigger_name, relation, timing_operations, function,
                target_relation=wrong_relation)
        elif mutation in {"wrong_relation_schema", "duplicate_schema"}:
            schema = "coupon_tamper_schema"
            connection.exec_driver_sql(f"CREATE SCHEMA {schema}")
            connection.exec_driver_sql(
                f"CREATE TABLE {schema}.{relation} "
                f"(LIKE {relation} INCLUDING ALL)")
            target = f"{schema}.{relation}"
            if mutation == "wrong_relation_schema":
                _recreate_postgresql_trigger(
                    connection, trigger_name, relation, timing_operations, function,
                    target_relation=target)
            else:
                connection.exec_driver_sql(
                    f"CREATE TRIGGER {trigger_name} {timing_operations} ON {target} "
                    f"FOR EACH ROW EXECUTE FUNCTION {function}()")
        elif mutation == "duplicate_relation":
            wrong_relation = next(
                item for item in migrate._COUPON_READINESS_TABLES if item != relation)
            connection.exec_driver_sql(
                f"CREATE TRIGGER {trigger_name} {timing_operations} ON {wrong_relation} "
                f"FOR EACH ROW EXECUTE FUNCTION {function}()")
        elif mutation == "disabled":
            connection.exec_driver_sql(
                f"ALTER TABLE {relation} DISABLE TRIGGER {trigger_name}")
        elif mutation == "internal":
            connection.execute(sa.text(
                "UPDATE pg_trigger SET tgisinternal=true WHERE tgname=:name "
                "AND tgrelid=CAST(:relation AS regclass)"),
                {"name": trigger_name, "relation": relation})
        elif mutation == "missing":
            connection.exec_driver_sql(f"DROP TRIGGER {trigger_name} ON {relation}")
        elif mutation == "wrong_tgtype":
            _recreate_postgresql_trigger(
                connection, trigger_name, relation, "AFTER INSERT", function)
        elif mutation == "wrong_when":
            _recreate_postgresql_trigger(
                connection, trigger_name, relation, timing_operations, function,
                when="WHEN (true)")
        elif mutation == "wrong_function":
            connection.exec_driver_sql(
                "CREATE FUNCTION coupon_tamper_wrong_fn() RETURNS trigger AS $$ "
                "BEGIN RETURN NEW; END; $$ LANGUAGE plpgsql")
            _recreate_postgresql_trigger(
                connection, trigger_name, relation, timing_operations,
                "coupon_tamper_wrong_fn")
        elif mutation == "wrong_function_schema":
            connection.exec_driver_sql("CREATE SCHEMA coupon_tamper_schema")
            connection.exec_driver_sql(
                f"ALTER FUNCTION {function}() SET SCHEMA coupon_tamper_schema")
        elif mutation == "wrong_function_body":
            connection.exec_driver_sql(
                f"CREATE OR REPLACE FUNCTION {function}() "
                "RETURNS trigger AS $$ BEGIN RETURN NEW; END; $$ LANGUAGE plpgsql")
        elif mutation == "literal_case":
            definition = connection.execute(sa.text(
                "SELECT pg_get_functiondef(CAST(:function AS regprocedure))"
            ), {"function": f"{function}()"}).scalar_one()
            assert definition.count("'ACCEPTED'") > 0
            mutated = definition.replace("'ACCEPTED'", "'accepted'")
            assert mutated != definition
            connection.exec_driver_sql(mutated)
        elif mutation == "wrong_language":
            connection.execute(sa.text(
                "UPDATE pg_proc SET prolang=(SELECT oid FROM pg_language "
                "WHERE lanname='internal') WHERE oid=CAST(:function AS regprocedure)"),
                {"function": f"{function}()"})
        elif mutation == "security_definer":
            connection.exec_driver_sql(
                f"ALTER FUNCTION {function}() SECURITY DEFINER")
        elif mutation == "missing_duration_column":
            connection.exec_driver_sql(
                "ALTER TABLE platform_coupon_definitions DROP CONSTRAINT "
                "ck_platform_coupon_entitlement_shape")
            connection.exec_driver_sql(
                "ALTER TABLE platform_coupon_definitions "
                "DROP COLUMN entitlement_duration_seconds")
        else:
            address = "sha256:" + "a" * 64
            connection.execute(sa.text(
                "INSERT INTO platform_plan_versions(plan_version_id,plan_code,version,"
                "amount_minor,currency,billing_interval,entitlement_set_address,policy_state,"
                "created_at) VALUES('plan.tamper','BETA',1,0,'INR','UNKNOWN',:address,"
                "'APPROVED','2026-09-01')"), {"address": address})
            connection.execute(sa.text(
                "INSERT INTO platform_coupon_definitions(coupon_id,coupon_digest,plan_version_id,"
                "policy_address,trial_policy_address,discount_policy_address,entitlement_code,"
                "entitlement_transition,entitlement_valid_from,entitlement_valid_until,valid_from,"
                "valid_until,max_redemptions,per_owner_limit,status,created_at,"
                "entitlement_effect_timing,entitlement_duration_seconds) VALUES("
                "'coupon.tamper',:digest,'plan.tamper',:address,:address,NULL,'PRODUCT_ACCESS',"
                "'GRANT','2026-09-01','2026-09-16','2026-09-01',NULL,2,1,'ACTIVE',"
                "'2026-09-01','FIXED_ABSOLUTE',NULL)"),
                {"digest": "b" * 64, "address": address})
            connection.execute(sa.text(
                "INSERT INTO platform_coupon_redemptions(redemption_id,coupon_id,owner_ref,"
                "policy_address,status,entitlement_code,entitlement_transition,"
                "entitlement_valid_from,entitlement_valid_until,redeemed_at) VALUES("
                "'redemption.tamper','coupon.tamper','owner.alpha',:address,'ACCEPTED',"
                "'PRODUCT_ACCESS','GRANT','2026-09-02','2026-09-17','2026-09-02')"),
                {"address": address})
    with engine.connect() as connection:
        before = _coupon_state(connection)
    with pytest.raises(RuntimeError, match="coupon readiness|current execution relational model"):
        _startup(engine)
    with engine.connect() as connection:
        assert _coupon_state(connection) == before
        assert before[0] == "0049"


def test_prior_use_source_and_privacy_guards_are_killed_then_restored(tmp_path):
    unique_engine = _engine(tmp_path, "unique-mutation.db")
    Base.metadata.create_all(unique_engine)
    with unique_engine.begin() as connection:
        _seed_profile(connection)
    connection = unique_engine.connect()
    transaction = connection.begin()
    original = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='account_trial_uses'"
    ).scalar_one()
    needle = (
        "CONSTRAINT uq_account_trial_use_owner_user_policy "
        "UNIQUE (owner_ref, user_ref, policy_address),"
    )
    assert needle in original
    version = connection.exec_driver_sql("PRAGMA schema_version").scalar_one()
    connection.exec_driver_sql("PRAGMA writable_schema=ON")
    connection.exec_driver_sql(
        "UPDATE sqlite_master SET sql=? WHERE type='table' AND name='account_trial_uses'",
        (original.replace(
            needle,
            "CONSTRAINT uq_account_trial_use_owner_user_policy "
            "UNIQUE (trial_use_id, owner_ref, user_ref, policy_address),",
        ),),
    )
    connection.exec_driver_sql("PRAGMA writable_schema=OFF")
    connection.exec_driver_sql(f"PRAGMA schema_version={version + 1}")
    _insert_trial(connection, "trial.one", "event.one")
    _insert_trial(connection, "trial.two", "event.two")
    assert connection.exec_driver_sql("SELECT count(*) FROM account_trial_uses").scalar_one() == 2
    transaction.rollback()
    connection.close()
    with unique_engine.begin() as connection:
        _insert_trial(connection, "trial.one", "event.one")
    with pytest.raises(sa.exc.IntegrityError, match="UNIQUE"):
        with unique_engine.begin() as connection:
            _insert_trial(connection, "trial.two", "event.two")

    source_engine = _engine(tmp_path, "source-mutation.db")
    Base.metadata.create_all(source_engine)
    event_sql = (
        "INSERT INTO platform_entitlement_events(event_id,owner_ref,entitlement_code,mode,"
        "source_kind,source_ref,transition,policy_address,valid_from,valid_until,effective_at,"
        "recorded_at) VALUES('event.invalid','owner.alpha','PRODUCT_ACCESS','INTERNAL',"
        "'BETA_TRIAL','trial.missing','GRANT',?,'2026-09-01','2026-09-16',"
        "'2026-09-01','2026-09-01')"
    )
    connection = source_engine.connect()
    transaction = connection.begin()
    source_trigger_sql = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='trigger' "
        "AND name='platform_entitlement_events_source_exact'"
    ).scalar_one()
    connection.exec_driver_sql("DROP TRIGGER platform_entitlement_events_source_exact")
    connection.exec_driver_sql(event_sql, ("sha256:" + "a" * 64,))
    assert connection.exec_driver_sql(
        "SELECT count(*) FROM platform_entitlement_events"
    ).scalar_one() == 1
    transaction.rollback()
    connection.close()
    if "platform_entitlement_events_source_exact" not in _triggers(
        source_engine, "platform_entitlement_events"
    ):
        with source_engine.begin() as connection:
            connection.exec_driver_sql(source_trigger_sql)
    with pytest.raises(sa.exc.IntegrityError, match="source mismatch"):
        with source_engine.begin() as connection:
            connection.exec_driver_sql(event_sql, ("sha256:" + "a" * 64,))

    privacy_engine = _engine(tmp_path, "privacy-mutation.db")
    Base.metadata.create_all(privacy_engine)
    with privacy_engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO organizations(organization_id,name,status,created_at,updated_at) "
            "VALUES('owner.alpha','Synthetic','active','2026-09-01','2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO users(user_id,email_normalized,display_name,status,created_at,updated_at) "
            "VALUES('user.alpha','synthetic@example.invalid','Synthetic','active',"
            "'2026-09-01','2026-09-01')"
        )
        connection.exec_driver_sql(
            "INSERT INTO memberships(organization_id,user_id,role,status,created_at,updated_at) "
            "VALUES('owner.alpha','user.alpha','member','active','2026-09-01','2026-09-01')"
        )
    private_sql = (
        "INSERT INTO account_profile_evidence(profile_evidence_id,owner_ref,user_ref,"
        "policy_address,evidence_address,satisfied_fields_json,attested_at) VALUES("
        "'profile.private','owner.alpha','user.alpha',?,?,'[\"strategy.secret\"]',"
        "'2026-09-01')"
    )
    connection = privacy_engine.connect()
    transaction = connection.begin()
    privacy_trigger_sql = connection.exec_driver_sql(
        "SELECT sql FROM sqlite_master WHERE type='trigger' "
        "AND name='account_profile_evidence_privacy_insert'"
    ).scalar_one()
    connection.exec_driver_sql("DROP TRIGGER account_profile_evidence_privacy_insert")
    connection.exec_driver_sql(
        private_sql, ("sha256:" + "a" * 64, "sha256:" + "b" * 64)
    )
    assert connection.exec_driver_sql(
        "SELECT count(*) FROM account_profile_evidence"
    ).scalar_one() == 1
    transaction.rollback()
    connection.close()
    if "account_profile_evidence_privacy_insert" not in _triggers(
        privacy_engine, "account_profile_evidence"
    ):
        with privacy_engine.begin() as connection:
            connection.exec_driver_sql(privacy_trigger_sql)
    with pytest.raises(sa.exc.IntegrityError, match="forbidden content"):
        with privacy_engine.begin() as connection:
            connection.exec_driver_sql(
                private_sql, ("sha256:" + "a" * 64, "sha256:" + "b" * 64)
            )
