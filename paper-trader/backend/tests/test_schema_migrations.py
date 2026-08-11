"""The migration framework proves itself on every run.

The whole point of Phase A is that a schema change can now be expressed as a
reversible, versioned revision instead of an ADD COLUMN line. That only holds if
two things stay true forever, and neither is checked by any other test:

  1. A database built from the ORM models and a database migrated up from the
     pre-Alembic baseline end up with the SAME schema. If someone adds a column to
     `models.py` and forgets the revision (or writes a revision that does something
     subtly different), fresh installs and the owner's live ledger silently diverge
     — the class of bug that only surfaces as a production 500 weeks later.

  2. A pre-Alembic database is ADOPTED, not rebuilt. The live ledger holds real
     money rows; `init_schema` must stamp it, never drop it.
"""
from __future__ import annotations

import sqlalchemy as sa
import pytest
from alembic import command
from sqlalchemy.exc import DatabaseError, IntegrityError

from app.db import migrate
from app.db.models import Base


#: The migration head, pinned in ONE place and deliberately a literal rather than a call to
#: `migrate.head_revision()`. Deriving it would make every assertion below compare the head to
#: itself and pass for any value — the vacuous shape. Bumping this by hand when a migration
#: lands is the point: it is the moment someone states that the new head is intended.
HEAD = "0019"


def _schema(engine) -> dict:
    """Comparable description of a database: columns (name/type/nullable/default)
    and indexes per table. `alembic_version` is excluded — it records *where* a
    database is, and the two sides of the comparison get there differently."""
    insp = sa.inspect(engine)
    out = {}
    for table in sorted(insp.get_table_names()):
        if table == "alembic_version":
            continue
        cols = {c["name"]: (str(c["type"]), bool(c["nullable"]), str(c.get("default")))
                for c in insp.get_columns(table)}
        idx = sorted((i["name"], tuple(i["column_names"]), bool(i.get("unique")))
                     for i in insp.get_indexes(table))
        out[table] = {"columns": cols, "indexes": idx}
    return out


def _fresh_engine(tmp_path, name: str):
    engine = sa.create_engine(f"sqlite:///{tmp_path / name}")

    @sa.event.listens_for(engine, "connect")
    def _enforce_runtime_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def _apply_baseline_ddl(engine) -> None:
    """Execute the checked-in baseline DDL, building a pre-Alembic database.

    Comment lines are stripped BEFORE splitting on `;`. Splitting first and then
    skipping chunks that start with `--` silently swallowed the first CREATE TABLE
    (it shares a chunk with the file header), which produced a confusing "no such
    table" from the index that followed it."""
    with open(migrate.BASELINE_SCHEMA_SQL) as fh:
        ddl = "\n".join(line for line in fh.read().splitlines()
                        if not line.strip().startswith("--"))
    statements = [s.strip() for s in ddl.split(";") if s.strip()]
    assert len(statements) > 20, \
        f"baseline DDL parsed to only {len(statements)} statements — parser is broken"
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(sa.text(stmt))


def _build_from_models(tmp_path):
    """State 1 — an empty database adopted by init_schema."""
    engine = _fresh_engine(tmp_path, "fresh.db")
    migrate.init_schema(engine,
                        create_all=lambda: Base.metadata.create_all(engine),
                        legacy_migrate=lambda: None)
    return engine


def _build_from_baseline(tmp_path):
    """State 2 — a synthetic PRE-ALEMBIC database, built by executing the checked-in
    baseline DDL, then adopted and migrated forward."""
    engine = _fresh_engine(tmp_path, "legacy.db")
    _apply_baseline_ddl(engine)
    migrate.init_schema(engine,
                        create_all=lambda: Base.metadata.create_all(engine),
                        legacy_migrate=lambda: None)
    return engine


def test_models_and_migrations_agree(tmp_path):
    """THE invariant. A fresh install and a migrated legacy database must be the
    same shape. A failure here means models.py and migrations/versions/ disagree —
    fix the revision, do not weaken this test."""
    fresh = _schema(_build_from_models(tmp_path))
    migrated = _schema(_build_from_baseline(tmp_path))

    assert set(migrated) == set(fresh), (
        "table sets differ between a fresh create_all and a migrated legacy DB: "
        f"only-in-migrated={sorted(set(migrated) - set(fresh))} "
        f"only-in-fresh={sorted(set(fresh) - set(migrated))}"
    )
    for table in fresh:
        assert migrated[table]["columns"] == fresh[table]["columns"], (
            f"column mismatch in {table!r} — models.py and the revision chain "
            f"disagree. Fresh: {fresh[table]['columns']}. "
            f"Migrated: {migrated[table]['columns']}"
        )
        assert migrated[table]["indexes"] == fresh[table]["indexes"], \
            f"index mismatch in {table!r}"


def test_product_object_schema_owns_graph_versions_and_sparse_layouts(tmp_path):
    engine = _build_from_baseline(tmp_path)
    schema = _schema(engine)

    assert migrate.head_revision() == HEAD
    assert set(schema["projects"]["columns"]) == {
        "project_id", "name", "description", "status", "created_at", "updated_at",
    }
    assert set(schema["graph_artifacts"]["columns"]) == {
        "identifier", "project_id", "display_name", "draft_json", "draft_revision",
        "published_revision", "current_version", "created_at", "updated_at",
    }
    assert set(schema["graph_versions"]["columns"]) == {
        "graph_identifier", "version", "artifact_json", "content_address", "created_at",
    }
    assert set(schema["ir_graph_layouts"]["columns"]) == {
        "graph_identifier", "graph_version", "revision", "updated_at",
    }
    assert set(schema["ir_graph_layout_positions"]["columns"]) == {
        "graph_identifier", "graph_version", "instance_id", "x", "y",
    }
    assert set(schema["ir_graph_layout_groups"]["columns"]) == {
        "graph_identifier", "graph_version", "identifier", "display_name",
        "x", "y", "width", "height", "collapsed",
    }
    assert set(schema["ir_graph_layout_group_members"]["columns"]) == {
        "graph_identifier", "graph_version", "group_identifier", "instance_id",
    }
    assert set(schema["project_review_notes"]["columns"]) == {
        "note_id", "project_id", "event_id", "event_type", "body", "created_by",
        "revision", "deleted_at", "created_at", "updated_at",
    }
    assert set(schema["project_review_saved_views"]["columns"]) == {
        "view_id", "project_id", "name", "filters_json", "created_by", "revision",
        "deleted_at", "created_at", "updated_at",
    }
    assert set(schema["project_review_snapshots"]["columns"]) == {
        "snapshot_id", "project_id", "label", "capture_key", "manifest_json",
        "content_address", "created_by", "capture_started_at", "capture_completed_at",
    }
    assert any(
        name == "uq_project_review_saved_views_active_name"
        and columns == ("project_id", "name") and unique
        for name, columns, unique in schema["project_review_saved_views"]["indexes"]
    )
    assert any(
        name == "uq_project_review_snapshots_capture_key"
        and columns == ("project_id", "capture_key") and unique
        for name, columns, unique in schema["project_review_snapshots"]["indexes"]
    )
    assert set(schema["ir_graph_layout_orphan_archive"]["columns"]) == {
        "graph_identifier", "graph_version", "revision", "updated_at", "archived_at",
    }
    assert set(schema["ir_graph_layout_position_orphan_archive"]["columns"]) == {
        "graph_identifier", "graph_version", "instance_id", "x", "y",
    }

    graph_version_fks = sa.inspect(engine).get_foreign_keys("ir_graph_layouts")
    assert any(
        fk["referred_table"] == "graph_versions"
        and fk["constrained_columns"] == ["graph_identifier", "graph_version"]
        for fk in graph_version_fks
    )


def test_revision_0014_round_trips_without_rewriting_legacy_rows(tmp_path):
    """Lifecycle links are additive: 0014 must leave old journal facts untouched."""
    engine = _fresh_engine(tmp_path, "execution-lifecycle-round-trip.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0013")
        connection.execute(sa.text(
            "INSERT INTO order_journal "
            "(deployment_id, order_id, tradingsymbol, instrument_key, side, kind, intent, "
            "qty, status, filled_qty, avg_price, placed_at) "
            "VALUES (1, 'legacy-order', 'RELIANCE', 'NSE_EQ|INE002A01018', 'BUY', "
            "'options', 'ENTRY', 1, 'WORKING', 0, 0.0, '2026-08-09 09:15:00')"
        ))
        command.upgrade(migrate.alembic_config(connection), HEAD)

    inspector = sa.inspect(engine)
    assert migrate.schema_version(engine) == HEAD
    assert {"execution_intents", "execution_order_events"} <= set(
        inspector.get_table_names())
    assert {column["name"] for column in inspector.get_columns("execution_intents")} == {
        # `owner_id` arrived in 0016. This test upgrades to HEAD, so it asserts the CURRENT
        # shape; the 0014-specific property it guards is that the legacy rows are not rewritten,
        # which the value assertions below still check.
        "client_intent_id", "deployment_id", "owner_id", "broker_account_id",
        "broker", "account_scope",
        "connection_scope",
        "broker_tag", "intent", "instrument_key", "tradingsymbol", "exchange", "side",
        "product", "order_type", "requested_qty", "limit_price", "decision_price",
        "signal_at", "strategy_key", "strategy_version", "context_json", "created_at",
    }
    assert {column["name"] for column in inspector.get_columns("execution_order_events")} == {
        # `owner_id` arrived in 0017, for the same reason it is asserted above rather than
        # excluded: this test upgrades to HEAD, so it pins the CURRENT shape.
        "id", "client_intent_id", "owner_id", "broker_account_id", "source",
        "source_event_id", "kind",
        "broker_order_id",
        "broker_status", "cumulative_filled_qty", "avg_price", "observed_at", "payload_json",
        "anomaly",
    }
    for table in ("positions", "trades"):
        assert "entry_intent_id" in {column["name"] for column in inspector.get_columns(table)}
        assert any(
            index["name"] == f"ix_{table}_entry_intent_id"
            and index["column_names"] == ["entry_intent_id"]
            for index in inspector.get_indexes(table)
        )
        with engine.connect() as connection:
            foreign_keys = connection.execute(sa.text(
                f"PRAGMA foreign_key_list({table})"
            )).mappings().all()
        assert any(
            foreign_key["from"] == "entry_intent_id"
            and foreign_key["table"] == "execution_intents"
            and foreign_key["to"] == "client_intent_id"
            and foreign_key["on_delete"] == "RESTRICT"
            for foreign_key in foreign_keys
        )
    assert any(
        constraint["name"] == "uq_execution_event_source_identity"
        and constraint["column_names"] == ["client_intent_id", "source", "source_event_id"]
        for constraint in inspector.get_unique_constraints("execution_order_events")
    )
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT order_id, status, filled_qty FROM order_journal "
            "WHERE order_id = 'legacy-order'"
        )).one() == ("legacy-order", "WORKING", 0)

    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO execution_intents "
            "(client_intent_id, deployment_id, broker, account_scope, connection_scope, "
            " broker_tag, intent, instrument_key, tradingsymbol, exchange, side, order_type, "
            " requested_qty, created_at) "
            "VALUES ('entry-000000000000000000000002', 1, 'upstox', 'account.default', "
            "'connection.default', 'entry-000000000000002', 'ENTRY', "
            "'NSE_EQ|INE002A01018', 'RELIANCE', 'NSE', 'BUY', 'MARKET', 1, "
            "'2026-08-09 09:15:00')"
        ))
        connection.execute(sa.text(
            "INSERT INTO execution_order_events "
            "(client_intent_id, source, source_event_id, kind, observed_at) "
            "VALUES ('entry-000000000000000000000002', 'broker', 'event-1', "
            "'INTENT_CREATED', '2026-08-09 09:15:00')"
        ))
        connection.execute(sa.text(
            "INSERT INTO positions "
            "(deployment_id, entry_intent_id, instrument_key, direction, option_type, "
            " tradingsymbol, exchange, segment, strike, expiry, lot_size, qty, entry_premium, "
            " entry_charges, entry_cost, entry_spot, entry_time, entry_reason, stop_price, "
            " target_price, last_premium, last_spot, high_water_premium, mfe, mae, "
            " reinforcement_count, held_overnight, overnight_pnl, session_close_premium, "
            " manual_target, no_take_profit, mode) "
            "VALUES (1, 'entry-000000000000000000000002', 'NSE_EQ|INE002A01018', 'LONG', "
            "'CE', 'RELIANCE', 'NSE', 'options', 1.0, '2026-08-28', 1, 1, 10.0, 0.0, "
            "10.0, 100.0, '2026-08-09 09:15:00', '', 5.0, 15.0, 10.0, 100.0, 10.0, "
            "0.0, 0.0, 0, 0, 0.0, 0.0, 0, 0, 'paper')"
        ))
        for statement in (
            "UPDATE execution_order_events SET kind = 'CHANGED' WHERE id = 1",
            "DELETE FROM execution_order_events WHERE id = 1",
        ):
            with pytest.raises(IntegrityError, match="execution_order_events are immutable"):
                connection.execute(sa.text(statement))

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0013")
    inspector = sa.inspect(engine)
    assert migrate.schema_version(engine) == "0013"
    assert "execution_intents" not in inspector.get_table_names()
    assert "execution_order_events" not in inspector.get_table_names()
    assert "entry_intent_id" not in {column["name"] for column in inspector.get_columns("positions")}
    assert "entry_intent_id" not in {column["name"] for column in inspector.get_columns("trades")}

    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), HEAD)
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT order_id, status, filled_qty FROM order_journal "
            "WHERE order_id = 'legacy-order'"
        )).one() == ("legacy-order", "WORKING", 0)


def test_revision_0019_preserves_every_account_money_payload_and_adds_real_scope(tmp_path):
    """0019 copies complete rows, not selected fields, and creates enforceable account scope."""
    engine = _fresh_engine(tmp_path, "money-account-scope.db")
    _apply_baseline_ddl(engine)
    migrate.stamp(engine, "0001")
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), "0018")
        connection.execute(sa.text(
            "UPDATE deployments SET notes='deployment-marker', created_at='2026-08-11 09:00:01', "
            "updated_at='2026-08-11 09:00:02' WHERE id=1"))
        connection.execute(sa.text(
            "INSERT INTO execution_intents (client_intent_id,deployment_id,broker,account_scope,"
            "connection_scope,broker_tag,intent,instrument_key,tradingsymbol,exchange,side,product,"
            "order_type,requested_qty,limit_price,decision_price,signal_at,strategy_key,"
            "strategy_version,context_json,created_at,owner_id) VALUES "
            "('intent-marker',1,'kite','external-marker','kite:marker','tag-marker','ENTRY',"
            "'RELIANCE','RELIANCE','NSE','BUY','MIS','LIMIT',7,101.25,100.5,"
            "'2026-08-11 09:01:01','s','v','{}','2026-08-11 09:01:02','owner')"))
        connection.execute(sa.text(
            "INSERT INTO execution_order_events (id,client_intent_id,source,source_event_id,kind,"
            "broker_order_id,broker_status,cumulative_filled_qty,avg_price,observed_at,payload_json,"
            "anomaly,owner_id) VALUES (91,'intent-marker','broker','event-marker','ACKNOWLEDGED',"
            "'order-marker','OPEN',3,101.5,'2026-08-11 09:02:01','{}',"
            "'event-anomaly','owner')"))
        connection.execute(sa.text(
            "INSERT INTO positions (id,instrument_key,direction,option_type,tradingsymbol,exchange,"
            "segment,strategy_key,strike,expiry,lot_size,qty,entry_premium,entry_charges,entry_cost,"
            "entry_spot,entry_time,entry_reason,stop_price,target_price,last_premium,last_spot,"
            "high_water_premium,mfe,mae,reinforcement_count,held_overnight,overnight_pnl,"
            "session_close_premium,manual_target,no_take_profit,mode,deployment_id,strategy_version,"
            "entry_intent_id,owner_id) VALUES (92,'RELIANCE','LONG','EQ','RELIANCE','NSE',"
            "'equity_intraday','s',0,'2026-08-28',7,7,100.5,1.25,704.75,100.5,"
            "'2026-08-11 09:03:01','position-marker',90,120,101,101,102,5,-2,1,0,0,0,0,0,"
            "'live',1,'v','intent-marker','owner')"))
        connection.execute(sa.text(
            "INSERT INTO trades (id,instrument_key,direction,option_type,tradingsymbol,exchange,"
            "segment,strategy_key,strike,expiry,qty,entry_premium,entry_cost,entry_spot,entry_time,"
            "exit_premium,exit_charges,exit_spot,exit_time,exit_reason,gross_pnl,charges_total,"
            "net_pnl,return_pct,holding_minutes,win,held_overnight,overnight_pnl,intraday_pnl,"
            "reinforcements,mode,exit_price_estimated,mfe,mae,build_sha,deployment_id,"
            "strategy_version,entry_intent_id,owner_id) VALUES (93,'RELIANCE','LONG','EQ',"
            "'RELIANCE','NSE','equity_intraday','s',0,'2026-08-28',7,100.5,704.75,100.5,"
            "'2026-08-11 09:03:01',103.5,1.5,103.5,'2026-08-11 09:08:01','trade-marker',"
            "21,2.75,18.25,2.5,5,1,0,0,18.25,1,'live',0,5,-2,'sha-marker',1,'v',"
            "'intent-marker','owner')"))
        connection.execute(sa.text(
            "INSERT INTO equity_snapshots (id,time,equity,cash,invested,realized_pnl,open_count,"
            "segment,strategy_key,deployment_id,book,owner_id) VALUES (94,'2026-08-11 09:09:01',"
            "1234.5,1000.5,234,18.25,1,'equity_intraday','s',1,'live','owner')"))
        connection.execute(sa.text(
            "INSERT INTO order_journal (id,order_id,tradingsymbol,instrument_key,side,kind,intent,"
            "qty,context_json,status,resolution,filled_qty,avg_price,placed_at,deployment_id,owner_id)"
            " VALUES (95,'order-marker','RELIANCE','RELIANCE','BUY','equity','ENTRY',7,"
            "'{}','TERMINAL','FILLED',7,101.5,'2026-08-11 09:10:01',1,'owner')"))
        connection.execute(sa.text(
            "INSERT INTO signal_events (id,time,instrument_key,signal,z,slope,close,acted,note,"
            "deployment_id,owner_id) VALUES (96,'2026-08-11 09:11:01','RELIANCE','LONG_ENTRY',"
            "1.2,0.3,100.5,1,'signal-marker',1,'owner')"))
        connection.execute(sa.text(
            "INSERT INTO broker_connections (id,owner_id,broker,scope,label,capabilities_json,"
            "credential_ciphertext,credential_key_id,status,created_at,updated_at,"
            "last_authenticated_at,revoked_at) VALUES (97,'owner','kite','kite:marker',"
            "'connection-marker','[\"orders\"]','cipher-marker','key-marker','active',"
            "'2026-08-11 09:12:01','2026-08-11 09:12:02','2026-08-11 09:12:03',NULL)"))
        connection.execute(sa.text(
            "INSERT INTO projects (project_id,name,description,status,created_at,updated_at) VALUES "
            "('project-marker','Project','marker','active','2026-08-11 09:13:01',"
            "'2026-08-11 09:13:02')"))
        connection.execute(sa.text(
            "INSERT INTO graph_artifacts (identifier,project_id,display_name,draft_json,"
            "draft_revision,published_revision,current_version,created_at,updated_at) VALUES "
            "('graph-marker','project-marker','Graph','{}',1,1,1,'2026-08-11 09:13:03',"
            "'2026-08-11 09:13:04')"))
        connection.execute(sa.text(
            "INSERT INTO graph_versions (graph_identifier,version,artifact_json,content_address,"
            "created_at) VALUES ('graph-marker',1,json_object('identifier','graph-marker',"
            "'version',1),'sha256:graph-marker','2026-08-11 09:13:05')"))
        connection.execute(sa.text(
            "INSERT INTO ir_paper_deployments (id,project_id,graph_identifier,graph_version,"
            "graph_content_address,evidence_run_id,evidence_candidate_id,evidence_content_address,"
            "evidence_verified_at,deployment_id,instrument_key,interval,strategy_key,"
            "rollback_strategy_key,runtime_source,execution_mode,authority,admission_ok,"
            "admission_reason,state,revision,note,created_at,updated_at,owner_id) VALUES "
            "(98,'project-marker','graph-marker',1,'sha256:graph-marker',1,2,'sha256:graph-marker',"
            "'2026-08-11 09:14:01',1,'RELIANCE','5minute','s',NULL,'ir_graph','paper',"
            "'authoritative',1,'ok','staged',3,'paper-marker','2026-08-11 09:14:02',"
            "'2026-08-11 09:14:03','owner')"))
        connection.execute(sa.text(
            "INSERT INTO ir_shadow_deployments (id,project_id,graph_identifier,graph_version,"
            "graph_content_address,evidence_run_id,evidence_candidate_id,evidence_content_address,"
            "evidence_verified_at,deployment_id,instrument_key,interval,strategy_key,runtime_source,"
            "execution_mode,authority,admission_ok,admission_reason,state,revision,note,created_at,"
            "updated_at,owner_id) VALUES (99,'project-marker','graph-marker',1,"
            "'sha256:graph-marker',1,2,'sha256:graph-marker','2026-08-11 09:15:01',1,"
            "'RELIANCE','15minute','s','ir_graph','shadow','non_authoritative',1,'ok','staged',"
            "4,'shadow-marker','2026-08-11 09:15:02','2026-08-11 09:15:03','owner')"))
        connection.execute(sa.text(
            "INSERT INTO ir_shadow_divergences (id,observed_at,bar_time,instrument_key,"
            "authoritative_strategy_key,shadow_strategy_key,graph_address,authoritative_json,"
            "ir_json,warmup_state,declared_warmup,frame_id,frame_bars,frame_first_ts,frame_last_ts,"
            "reason,detail,eval_ms,market_open,owner_id) VALUES (100,'2026-08-11 09:16:01',"
            "'2026-08-11 09:15:00','RELIANCE','a','s','sha256:graph-marker','{}','{}','settled',"
            "10,'frame-marker',20,'2026-08-11 08:00:00','2026-08-11 09:15:00','VALUE',"
            "'divergence-marker',1.25,1,'owner')"))

        tables = {
            "deployments": 1, "execution_intents": "intent-marker",
            "execution_order_events": 91, "positions": 92, "trades": 93,
            "equity_snapshots": 94, "order_journal": 95, "signal_events": 96,
            "broker_connections": 97, "ir_paper_deployments": 98,
            "ir_shadow_deployments": 99, "ir_shadow_divergences": 100,
        }
        before = {}
        for table, key in tables.items():
            pk = "client_intent_id" if table == "execution_intents" else "id"
            before[table] = dict(connection.execute(sa.text(
                f"SELECT * FROM {table} WHERE {pk}=:key"), {"key": key}).mappings().one())

        command.upgrade(migrate.alembic_config(connection), HEAD)

        for table, key in tables.items():
            pk = "client_intent_id" if table == "execution_intents" else "id"
            after = dict(connection.execute(sa.text(
                f"SELECT * FROM {table} WHERE {pk}=:key"), {"key": key}).mappings().one())
            for column, value in before[table].items():
                if table == "deployments" and column == "account_id":
                    continue
                assert after[column] == value, f"0019 changed {table}.{column}"
            assert after["broker_account_id"] == "account.default"

    inspector = sa.inspect(engine)
    account_tables = (
        "positions", "trades", "equity_snapshots", "order_journal", "signal_events",
        "execution_intents", "execution_order_events", "broker_connections",
        "ir_paper_deployments", "ir_shadow_deployments", "ir_shadow_divergences",
    )
    for table in account_tables:
        column = next(c for c in inspector.get_columns(table)
                      if c["name"] == "broker_account_id")
        assert column["nullable"] is False
        assert any(
            fk["constrained_columns"] == ["broker_account_id"]
            and fk["referred_table"] == "broker_accounts"
            for fk in inspector.get_foreign_keys(table)
        )
        assert any(
            index["column_names"] == ["owner_id", "broker_account_id"]
            for index in inspector.get_indexes(table)
        )

    assert "account_id" not in {c["name"] for c in inspector.get_columns("deployments")}
    assert any(
        set(constraint["column_names"]) == {"owner_id", "name"}
        for constraint in inspector.get_unique_constraints("deployments")
    )


def test_revision_0019_refuses_lossy_tenant_name_downgrade(tmp_path):
    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO organizations VALUES ('org-b','B','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(sa.text(
            "INSERT INTO broker_accounts (broker_account_id,owner_id,broker,external_account_id,"
            "display_name,status,created_at,updated_at) VALUES ('account.b','org-b','kite','b','B',"
            "'active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(sa.text(
            "INSERT INTO deployments (owner_id,broker_account_id,name,created_at,updated_at) "
            "VALUES ('org-b','account.b','default',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        with pytest.raises(RuntimeError, match="lossy"):
            command.downgrade(migrate.alembic_config(connection), "0018")


def test_catalogue_graph_is_seeded_with_derived_identity(tmp_path):
    from app.ir.hashing import canonical_json, content_address
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    with engine.connect() as connection:
        artifact = connection.execute(sa.text(
            "SELECT project_id, draft_json, draft_revision, published_revision, "
            "current_version "
            "FROM graph_artifacts WHERE identifier = :identifier"
        ), {"identifier": GRAPH["identifier"]}).one()
        version = connection.execute(sa.text(
            "SELECT artifact_json, content_address FROM graph_versions "
            "WHERE graph_identifier = :identifier AND version = :version"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]}).one()

    assert artifact.project_id
    assert artifact.draft_json == canonical_json(GRAPH)
    assert artifact.draft_revision == 0
    assert artifact.published_revision == 0
    assert artifact.current_version == GRAPH["version"]
    assert version.artifact_json == canonical_json(GRAPH)
    assert version.content_address == content_address(GRAPH)


def test_graph_versions_refuse_direct_sql_update_and_delete(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    for statement in (
        "UPDATE graph_versions SET artifact_json = '{}' "
        "WHERE graph_identifier = :identifier AND version = :version",
        "DELETE FROM graph_versions "
        "WHERE graph_identifier = :identifier AND version = :version",
    ):
        with pytest.raises(DatabaseError, match="immutable"):
            with engine.begin() as connection:
                connection.execute(sa.text(statement), {
                    "identifier": GRAPH["identifier"],
                    "version": GRAPH["version"],
                })


def test_graph_version_insert_requires_json_identity_to_match_row_identity(tmp_path):
    from app.ir.hashing import canonical_json, content_address
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    mismatched = dict(GRAPH)
    mismatched["version"] = GRAPH["version"] + 1
    for row_version, document in (
        (GRAPH["version"] + 2, mismatched),
        (GRAPH["version"] + 3, {}),
    ):
        with pytest.raises(DatabaseError, match="CHECK constraint"):
            with engine.begin() as connection:
                connection.execute(sa.text(
                    "INSERT INTO graph_versions "
                    "(graph_identifier, version, artifact_json, content_address, created_at) "
                    "VALUES (:identifier, :version, :artifact_json, :address, "
                    "'2026-08-03 10:00:00')"
                ), {
                    "identifier": GRAPH["identifier"],
                    "version": row_version,
                    "artifact_json": canonical_json(document),
                    "address": content_address(document),
                })


def test_product_object_upgrade_attaches_valid_layout_and_removes_orphans(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0005")
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))
        for identifier, version in (
            (GRAPH["identifier"], GRAPH["version"]),
            ("strategy.orphan", 99),
        ):
            connection.execute(sa.text(
                "INSERT INTO ir_graph_layouts "
                "(graph_identifier, graph_version, revision, updated_at) "
                "VALUES (:identifier, :version, 1, '2026-08-03 10:00:00')"
            ), {"identifier": identifier, "version": version})
            connection.execute(sa.text(
                "INSERT INTO ir_graph_layout_positions "
                "(graph_identifier, graph_version, instance_id, x, y) "
                "VALUES (:identifier, :version, 'n_ema', 10.0, 20.0)"
            ), {"identifier": identifier, "version": version})

    assert migrate.upgrade_to_head(engine) == HEAD
    with engine.connect() as connection:
        layouts = connection.execute(sa.text(
            "SELECT graph_identifier, graph_version FROM ir_graph_layouts"
        )).all()
        positions = connection.execute(sa.text(
            "SELECT graph_identifier, graph_version, instance_id "
            "FROM ir_graph_layout_positions"
        )).all()
        capital = connection.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state WHERE id = 1"
        )).one()
        archived_layouts = connection.execute(sa.text(
            "SELECT graph_identifier, graph_version, revision "
            "FROM ir_graph_layout_orphan_archive"
        )).all()
        archived_positions = connection.execute(sa.text(
            "SELECT graph_identifier, graph_version, instance_id, x, y "
            "FROM ir_graph_layout_position_orphan_archive"
        )).all()

    assert layouts == [(GRAPH["identifier"], GRAPH["version"])]
    assert positions == [(GRAPH["identifier"], GRAPH["version"], "n_ema")]
    assert archived_layouts == [("strategy.orphan", 99, 1)]
    assert archived_positions == [("strategy.orphan", 99, "n_ema", 10.0, 20.0)]
    assert capital == (50000.0, 49000.0, -1000.0)

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0005")
    with engine.connect() as connection:
        restored_layout = connection.execute(sa.text(
            "SELECT revision FROM ir_graph_layouts "
            "WHERE graph_identifier = 'strategy.orphan' AND graph_version = 99"
        )).one()
        restored_position = connection.execute(sa.text(
            "SELECT instance_id, x, y FROM ir_graph_layout_positions "
            "WHERE graph_identifier = 'strategy.orphan' AND graph_version = 99"
        )).one()
    assert restored_layout == (1,)
    assert restored_position == ("n_ema", 10.0, 20.0)


def test_product_object_downgrade_refuses_non_seed_history(tmp_path):
    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO projects "
            "(project_id, name, description, status, created_at, updated_at) "
            "VALUES ('project.user', 'User project', '', 'active', "
            "'2026-08-03 10:00:00', '2026-08-03 10:00:00')"
        ))

    with pytest.raises(RuntimeError, match="non-seed"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0005")

    assert migrate.schema_version(engine) == HEAD

    with engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM projects WHERE project_id = 'project.user'"))
        connection.execute(sa.text(
            "UPDATE graph_artifacts SET draft_revision = 1 "
            "WHERE identifier = 'strategy.expanding_z_impulse'"
        ))
    with pytest.raises(RuntimeError, match="modified"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0005")

    assert migrate.schema_version(engine) == HEAD


def test_product_object_rollback_preserves_seed_layout_and_money_record(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layouts "
            "(graph_identifier, graph_version, revision, updated_at) "
            "VALUES (:identifier, :version, 1, '2026-08-03 10:00:00')"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_positions "
            "(graph_identifier, graph_version, instance_id, x, y) "
            "VALUES (:identifier, :version, 'n_ema', 10.0, 20.0)"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        command.downgrade(migrate.alembic_config(connection), "0005")

    tables = set(sa.inspect(engine).get_table_names())
    assert {"projects", "graph_artifacts", "graph_versions"}.isdisjoint(tables)
    with engine.connect() as connection:
        layout = connection.execute(sa.text(
            "SELECT revision FROM ir_graph_layouts "
            "WHERE graph_identifier = :identifier AND graph_version = :version"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]}).one()
        position = connection.execute(sa.text(
            "SELECT instance_id, x, y FROM ir_graph_layout_positions "
            "WHERE graph_identifier = :identifier AND graph_version = :version"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]}).one()
        capital = connection.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state WHERE id = 1"
        )).one()
    assert layout == (1,)
    assert position == ("n_ema", 10.0, 20.0)
    assert capital == (50000.0, 49000.0, -1000.0)

    assert migrate.upgrade_to_head(engine) == HEAD


def test_layout_migration_downgrades_without_touching_the_money_record(tmp_path):
    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))

    with engine.begin() as connection:
        command.downgrade(migrate.alembic_config(connection), "0004")

    tables = set(sa.inspect(engine).get_table_names())
    assert migrate.schema_version(engine) == "0004"
    assert "ir_graph_layouts" not in tables
    assert "ir_graph_layout_positions" not in tables
    assert "trades" in tables
    with engine.connect() as connection:
        capital = connection.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state WHERE id = 1"
        )).one()
    assert capital == (50000.0, 49000.0, -1000.0)

    assert migrate.upgrade_to_head(engine) == HEAD


def test_visual_group_migration_rolls_back_without_touching_layout_or_money(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layouts "
            "(graph_identifier, graph_version, revision, updated_at) "
            "VALUES (:identifier, :version, 1, '2026-08-03 10:00:00')"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_positions "
            "(graph_identifier, graph_version, instance_id, x, y) "
            "VALUES (:identifier, :version, 'n_ema', 10.0, 20.0)"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_groups "
            "(graph_identifier, graph_version, identifier, display_name, "
            " x, y, width, height, collapsed) "
            "VALUES (:identifier, :version, 'g_signal', 'Signal', "
            " 1.0, 2.0, 300.0, 180.0, 0)"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        connection.execute(sa.text(
            "INSERT INTO ir_graph_layout_group_members "
            "(graph_identifier, graph_version, group_identifier, instance_id) "
            "VALUES (:identifier, :version, 'g_signal', 'n_ema')"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]})
        command.downgrade(migrate.alembic_config(connection), "0006")

    tables = set(sa.inspect(engine).get_table_names())
    assert "ir_graph_layout_groups" not in tables
    assert "ir_graph_layout_group_members" not in tables
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT instance_id, x, y FROM ir_graph_layout_positions"
        )).one() == ("n_ema", 10.0, 20.0)
        assert connection.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state WHERE id = 1"
        )).one() == (50000.0, 49000.0, -1000.0)

    assert migrate.upgrade_to_head(engine) == HEAD


def test_review_state_migration_empty_rollback_preserves_existing_records(tmp_path):
    from app.ir.strategies.expanding_z import GRAPH

    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))
        command.downgrade(migrate.alembic_config(connection), "0007")

    tables = set(sa.inspect(engine).get_table_names())
    assert migrate.schema_version(engine) == "0007"
    assert "project_review_notes" not in tables
    assert "project_review_saved_views" not in tables
    with engine.connect() as connection:
        capital = connection.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state WHERE id = 1"
        )).one()
        graph = connection.execute(sa.text(
            "SELECT content_address FROM graph_versions "
            "WHERE graph_identifier = :identifier AND version = :version"
        ), {"identifier": GRAPH["identifier"], "version": GRAPH["version"]}).one()
    assert capital == (50000.0, 49000.0, -1000.0)
    assert graph.content_address.startswith("sha256:")
    assert migrate.upgrade_to_head(engine) == HEAD


def test_review_state_migration_refuses_populated_downgrade(tmp_path):
    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO project_review_notes "
            "(note_id, project_id, event_id, event_type, body, created_by, revision, "
            " deleted_at, created_at, updated_at) VALUES "
            "('note-1', 'project.repository_catalogue', 'run:1', 'experiment_run', "
            " 'Retain this note', 'owner', 0, NULL, "
            " '2026-08-03 10:00:00', '2026-08-03 10:00:00')"
        ))

    with pytest.raises(RuntimeError, match="review notes or saved views exist"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0007")

    assert migrate.schema_version(engine) == HEAD


def test_review_snapshot_migration_empty_rollback_preserves_review_and_money(tmp_path):
    engine = _build_from_baseline(tmp_path)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO capital_state "
            "(id, initial_capital, cash, realized_pnl, updated_at) "
            "VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-03 10:00:00')"
        ))
        connection.execute(sa.text(
            "INSERT INTO project_review_notes "
            "(note_id, project_id, event_id, event_type, body, created_by, revision, "
            " deleted_at, created_at, updated_at) VALUES "
            "('note-keep', 'project.repository_catalogue', 'run:1', 'experiment_run', "
            " 'Keep this note', 'owner', 0, NULL, "
            " '2026-08-03 10:00:00', '2026-08-03 10:00:00')"
        ))
        command.downgrade(migrate.alembic_config(connection), "0008")

    assert migrate.schema_version(engine) == "0008"
    assert "project_review_snapshots" not in set(sa.inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.execute(sa.text(
            "SELECT body FROM project_review_notes WHERE note_id = 'note-keep'"
        )).scalar_one() == "Keep this note"
        assert connection.execute(sa.text(
            "SELECT cash FROM capital_state WHERE id = 1"
        )).scalar_one() == 49000.0
    assert migrate.upgrade_to_head(engine) == HEAD


def test_review_snapshot_migration_refuses_populated_downgrade(tmp_path):
    from app.ir.hashing import canonical_json, content_address

    engine = _build_from_baseline(tmp_path)
    manifest = {
        "schema_version": 1,
        "project_id": "project.repository_catalogue",
        "events": [],
        "captured_queues": {
            "review_needed_runs": [], "pending_candidates": [], "active_findings": [],
        },
        "notes": [],
        "source_errors": [],
    }
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO project_review_snapshots "
            "(snapshot_id, project_id, label, capture_key, manifest_json, content_address, "
            " created_by, capture_started_at, capture_completed_at) VALUES "
            "('snapshot.1', 'project.repository_catalogue', 'Daily', "
            " '2ba56d22-7094-4a8d-9bf5-b84a4e8f083f', :manifest, :address, 'owner', "
            " '2026-08-03 10:00:00', '2026-08-03 10:00:01')"
        ), {"manifest": canonical_json(manifest), "address": content_address(manifest)})

    with pytest.raises(RuntimeError, match="review snapshots exist"):
        with engine.begin() as connection:
            command.downgrade(migrate.alembic_config(connection), "0008")

    assert migrate.schema_version(engine) == HEAD


def test_legacy_database_is_adopted_not_rebuilt(tmp_path):
    """A pre-Alembic database keeps its rows. This is the live-ledger case: the
    owner's paper_trader.db holds 72 real trades and must survive adoption."""
    engine = _fresh_engine(tmp_path, "withdata.db")
    _apply_baseline_ddl(engine)
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO capital_state (id, initial_capital, cash, realized_pnl, "
            "updated_at) VALUES (1, 50000.0, 49000.0, -1000.0, '2026-08-02 10:00:00')"))

    assert migrate.schema_version(engine) is None, "precondition: unmanaged database"

    migrate.init_schema(engine,
                        create_all=lambda: Base.metadata.create_all(engine),
                        legacy_migrate=lambda: None)

    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT initial_capital, cash, realized_pnl FROM capital_state "
            "WHERE id = 1")).one()
    assert row == (50000.0, 49000.0, -1000.0), "adoption destroyed existing rows"
    assert migrate.schema_version(engine) == migrate.head_revision()


def test_empty_database_is_stamped_at_head(tmp_path):
    engine = _build_from_models(tmp_path)
    assert migrate.schema_version(engine) == migrate.head_revision()
    state = migrate.schema_state(engine)
    assert state["up_to_date"] is True
    assert state["current"] == state["head"]


def test_init_schema_is_idempotent(tmp_path):
    """Boot happens more than once. Re-running must be a no-op, not an error."""
    engine = _build_from_models(tmp_path)
    first = migrate.schema_version(engine)
    for _ in range(2):
        migrate.init_schema(engine,
                            create_all=lambda: Base.metadata.create_all(engine),
                            legacy_migrate=lambda: None)
    assert migrate.schema_version(engine) == first


def test_unmanaged_database_reports_no_version(tmp_path):
    """`None` means "pre-Alembic", and must be distinguishable from head. The
    health endpoint reports it, so it must never be confused with up-to-date."""
    engine = _fresh_engine(tmp_path, "bare.db")
    assert migrate.schema_version(engine) is None
    assert migrate.schema_state(engine)["up_to_date"] is False


def test_baseline_tables_constant_matches_the_baseline_ddl():
    """`BASELINE_TABLES` decides what adoption is allowed to create. If it drifts
    from the actual baseline, adoption either misses a table an old database needs
    or creates one a later revision is about to create — the exact collision that
    broke revision 0002 the first time it ran."""
    import re
    with open(migrate.BASELINE_SCHEMA_SQL) as fh:
        ddl = fh.read()
    in_ddl = set(re.findall(r"CREATE TABLE (\w+)", ddl))
    assert in_ddl == set(migrate.BASELINE_TABLES), (
        f"only-in-DDL={sorted(in_ddl - set(migrate.BASELINE_TABLES))} "
        f"only-in-constant={sorted(set(migrate.BASELINE_TABLES) - in_ddl)}"
    )


def test_baseline_ddl_is_shippable():
    """The baseline must reach the VPS. `scripts/deploy.sh` excludes `*.sql` (that
    is how ledger backups are kept off the box), so a `.sql` extension here would
    silently strip a checked-in source file from every deploy — and nothing else
    would notice, because runtime does not read it. See the file's own header."""
    import os
    assert os.path.exists(migrate.BASELINE_SCHEMA_SQL)
    assert not migrate.BASELINE_SCHEMA_SQL.endswith(".sql"), (
        "the baseline DDL must not use a .sql extension — deploy.sh excludes '*.sql' "
        "from the rsync, so this file would never ship"
    )


def test_every_revision_declares_a_downgrade():
    """A revision that cannot be rolled back is a one-way door on a live money
    ledger. `downgrade` may raise NotImplementedError for genuinely destructive
    changes, but it must be written and say so — never silently absent."""
    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(migrate.alembic_config())
    for rev in script.walk_revisions():
        module = rev.module
        assert hasattr(module, "downgrade"), \
            f"revision {rev.revision} has no downgrade()"
        assert rev.doc, f"revision {rev.revision} has no docstring saying what it does"
