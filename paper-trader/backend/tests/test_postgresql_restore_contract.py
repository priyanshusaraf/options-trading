from __future__ import annotations

import copy

import pytest

from tests.test_static_scopes import db


def test_execution_copy_orders_intents_before_positions_and_trades():
    from app.db.models import Base

    order = [table.name for table in Base.metadata.sorted_tables]
    assert order.index("execution_intents") < order.index("positions")
    assert order.index("execution_intents") < order.index("trades")


def test_copy_restore_validator_recomputes_paper_charge_schedule_address(
        admitted_entry_identity):
    """FH-07/FH-15: valid-looking corrupt attribution cannot cross copy/restore."""
    import sqlalchemy as sa
    from app.core.instruments import get_instrument
    from app.db.copy_contract import (
        CopyRefusal, validate_content_addresses, validate_semantic_ownership,
    )
    from app.db.models import Base, ExecutionIntent
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.providers.mock import MockProvider

    init_db(reset=True)
    broker = PaperBroker(MockProvider(), owner_id="owner",
                         broker_account_id="account.default")
    instrument = get_instrument("NIFTY")
    chain = broker.provider.get_option_chain(instrument)
    quote = next(item for item in chain.quotes if item.option_type == "CE")
    position = broker.open_position(
        instrument, "LONG", quote, "COPY", broker.provider.now(), chain.spot,
        **admitted_entry_identity(broker.s),
    )
    validate_content_addresses(broker.s.connection(), Base.metadata)
    validate_semantic_ownership(broker.s.connection(), Base.metadata)
    broker.s.execute(sa.text(
        "UPDATE positions SET paper_entry_charge_schedule_address=:wrong WHERE id=:id"),
        {"wrong": "sha256:" + "0" * 64, "id": position.id})
    broker.s.flush()
    with pytest.raises(CopyRefusal, match="schedule address"):
        validate_content_addresses(broker.s.connection(), Base.metadata)
    broker.s.rollback()
    intent = broker.s.get(ExecutionIntent, position.entry_intent_id)
    intent.instrument_key = "BANKNIFTY"
    broker.s.flush()
    with pytest.raises(CopyRefusal, match="intent content or scope"):
        validate_content_addresses(broker.s.connection(), Base.metadata)
    broker.s.rollback()
    broker.s.execute(sa.text(
        "DROP TRIGGER positions_refuse_entry_intent_id_rebind"))
    with pytest.raises(CopyRefusal, match="immutability triggers"):
        validate_content_addresses(broker.s.connection(), Base.metadata)
    broker.s.rollback()


@pytest.mark.parametrize('mutation', ['digest', 'owner', 'predecessor', 'membership', 'root'])
def test_static_scope_restore_rejects_tampered_identity(db, mutation):
    """Simulate damaged offline backup bytes, after explicitly removing the SQL guard."""
    import sqlalchemy as sa
    from app.db.models import Base
    from app.db.copy_contract import validate_content_addresses, CopyRefusal
    from tests.test_static_scopes import create
    engine, members = db
    create(engine, members[:1])
    with engine.begin() as c:
        validate_content_addresses(c, Base.metadata)
        c.exec_driver_sql('DROP TRIGGER static_instrument_scope_revisions_refuse_update')
        if mutation == 'root':
            c.exec_driver_sql('UPDATE static_instrument_scopes SET revision=2')
        else:
            # Disable FK checks only on this disposable corruption fixture.
            c.exec_driver_sql('PRAGMA foreign_keys=OFF')
            updates = {'digest': "address='sha256:" + 'f'*64 + "'",
                       'owner': "owner_id='b'", 'membership': "membership_address='sha256:"+'e'*64+"'",
                       'predecessor': "revision=2, predecessor='sha256:"+'d'*64+"'"}
            c.exec_driver_sql('UPDATE static_instrument_scope_revisions SET ' + updates[mutation])
        with pytest.raises(CopyRefusal, match='static scope'):
            validate_content_addresses(c, Base.metadata)

from app.db.restore_contract import (
    RestoreRefusal,
    canonical_manifest,
    finalize_manifest,
    validate_manifest,
    verify_manifest_signature,
)


@pytest.mark.parametrize("mutation", ("address", "forbidden"))
def test_monitoring_copy_restore_gate_rejects_tampered_canonical_event(tmp_path, mutation):
    from sqlalchemy.orm import Session
    from app.db.copy_contract import CopyRefusal, validate_content_addresses
    from app.db.models import Base
    from app.monitoring.repository import MonitoringRepository
    from tests.test_v0_monitoring_persistence import _engine, _facts, _spec, T0

    engine = _engine(tmp_path, f"monitoring-restore-{mutation}.db")
    before, after, event, _alert = _facts()
    with Session(engine, expire_on_commit=False) as session, session.begin():
        repository = MonitoringRepository(session, owner_id="tenant.alpha")
        repository.create_assignment(_spec(), now=T0)
        repository.append_state_snapshot(before, created_at=T0)
        repository.append_state_snapshot(after, created_at=event.event_at)
        repository.append_event(event, created_at=event.knowledge_cutoff_at)
        validate_content_addresses(session.connection(), Base.metadata)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER monitoring_signal_events_refuse_update")
        if mutation == "address":
            connection.exec_driver_sql(
                "UPDATE monitoring_signal_events SET canonical_json = "
                "json_set(canonical_json, '$.reason_code', 'FORGED_REASON')")
        else:
            connection.exec_driver_sql(
                "UPDATE monitoring_signal_events SET canonical_json = "
                "json_set(canonical_json, '$.order_id', 'forbidden')")
        with pytest.raises(CopyRefusal, match="monitoring persistence"):
            validate_content_addresses(connection, Base.metadata)
    engine.dispose()


def _manifest() -> dict:
    generation = "restore-20260813-a"
    return {
        "schema_version": 1,
        "generation_id": generation,
        "created_at": "2026-08-13T12:00:00+00:00",
        "backup_started_at": "2026-08-13T11:59:00+00:00",
        "backup_completed_at": "2026-08-13T12:00:00+00:00",
        "source_build": "d982428",
        "postgresql_major": 16,
        "coherence": {"maintenance_quiesced": True, "mode": "three-plane-maintenance",
                      "evidence_address": "sha256:" + "6" * 64},
        "planes": [
            {
                "plane": name,
                "generation_id": generation,
                "source_authority": "sha256:" + str(index) * 64,
                "source_physical_authority": "sha256:" + str(index + 3) * 64,
                "schema_head": "head",
                "table_inventory": [f"{name}_table"],
                "tables": {f"{name}_table": {
                    "rows": 1, "pk_digest": "0" * 64,
                    "row_digest": "1" * 64, "partition_counts": {},
                }},
                "sequences": [],
                "state_counts": {},
                "content_addresses": [],
                "artifact": {"identifier": f"{name}.dump", "sha256": "2" * 64},
            }
            for index, name in enumerate(("execution", "research", "ledger"), start=1)
        ],
        "cross_plane": {"execution_organizations": "3" * 64,
                          "research_owners": "4" * 64,
                          "ledger_owner_accounts": "5" * 64},
        "capabilities": {"logical_restore": "PROVEN", "managed_pitr": "UNPROVEN"},
    }


def test_manifest_is_canonical_content_addressed_and_operator_signed():
    manifest = finalize_manifest(_manifest(), signing_key=b"operator-signing-key-32-bytes!!")
    assert manifest["content_address"].startswith("sha256:")
    assert manifest["signature"]["status"] == "signed"
    assert canonical_manifest(manifest).endswith("\n")
    verify_manifest_signature(manifest, signing_key=b"operator-signing-key-32-bytes!!",
                              require_signed=True)


def test_manifest_signature_rejects_load_bearing_row_mutation():
    manifest = finalize_manifest(_manifest(), signing_key=b"operator-signing-key-32-bytes!!")
    tampered = copy.deepcopy(manifest)
    tampered["planes"][0]["tables"]["execution_table"]["rows"] = 2
    with pytest.raises(RestoreRefusal, match="content address|signature"):
        verify_manifest_signature(tampered,
                                  signing_key=b"operator-signing-key-32-bytes!!",
                                  require_signed=True)


def test_manifest_refuses_mixed_or_incoherent_generations():
    manifest = _manifest()
    manifest["planes"][1]["generation_id"] = "another-generation"
    with pytest.raises(RestoreRefusal, match="mixed generation"):
        validate_manifest(manifest)
    manifest = _manifest()
    manifest["coherence"]["maintenance_quiesced"] = False
    with pytest.raises(RestoreRefusal, match="quiesced"):
        validate_manifest(manifest)
    manifest = _manifest()
    manifest["coherence"]["evidence_address"] = "UNRECORDED"
    with pytest.raises(RestoreRefusal, match="maintenance evidence"):
        validate_manifest(manifest)


def test_manifest_refuses_reversed_backup_timestamps():
    manifest = _manifest()
    manifest["backup_started_at"] = "2026-08-13T12:01:00+00:00"
    with pytest.raises(RestoreRefusal, match="timestamp ordering"):
        validate_manifest(manifest)


def test_unsigned_development_manifest_never_satisfies_production_approval():
    manifest = finalize_manifest(_manifest())
    assert manifest["signature"] == {"algorithm": "none", "status": "unsigned-development"}
    with pytest.raises(RestoreRefusal, match="signed"):
        verify_manifest_signature(manifest, signing_key=None, require_signed=True)


def test_restore_manifest_summarizes_v2_presentation_revision_and_bytes(tmp_path):
    import datetime as dt
    import json
    import sqlalchemy as sa
    from app.db.models import Base
    from app.db.restore_contract import _content_summary, _state_counts

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'v2-presentation-restore.db'}", future=True)
    Base.metadata.create_all(engine)
    now = dt.datetime.now()
    document = json.dumps({
        "schema": "strategy-os-v2-presentation/1", "positions": {}, "groups": {},
        "viewport": None, "selection": {"nodes": [], "edges": [], "outputs": []},
    }, sort_keys=True, separators=(",", ":"))
    with engine.begin() as connection:
        connection.execute(Base.metadata.tables["organizations"].insert(), {
            "organization_id": "restore-owner", "name": "Restore", "created_at": now,
            "updated_at": now,
        })
        connection.execute(Base.metadata.tables["projects"].insert(), {
            "project_id": "restore-project", "owner_id": "restore-owner", "name": "Restore",
            "description": "", "status": "active", "created_at": now, "updated_at": now,
        })
        connection.execute(Base.metadata.tables["graph_artifacts"].insert(), {
            "owner_id": "restore-owner", "identifier": "restore-graph",
            "project_id": "restore-project", "display_name": "Restore", "draft_json": "{}",
            "draft_revision": 0, "published_revision": None, "current_version": None,
            "created_at": now, "updated_at": now,
        })
        connection.execute(Base.metadata.tables["ir_v2_editor_presentations"].insert(), {
            "owner_id": "restore-owner", "graph_identifier": "restore-graph",
            "format_version": 2, "presentation_json": document, "revision": 7,
            "updated_at": now,
        })
        assert _state_counts(connection, Base.metadata)["ir_v2_editor_presentations"] == {
            "rows": 1, "max_revision": 7,
        }
        row = next(item for item in _content_summary(connection, Base.metadata)
                   if item["table"] == "ir_v2_editor_presentations")
        assert row["count"] == 1
        assert len(row["set_digest"]) == 64
