"""Closed authority proofs for the 0038 truth, conformance, profile, and assessment rows."""
from __future__ import annotations

import datetime as dt
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models import (AuthorityCapabilityAssessment, AuthorityCapabilityProfile,
    AuthorityMarketTruthSnapshot, AuthorityProviderConformance, Base)
from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2
from app.market_data.authority import (load_capability_assessment, load_capability_profile,
    load_provider_conformance, persist_capability_assessment, persist_capability_profile,
    persist_provider_conformance)
from app.market_data.capability import (CapabilityProfile, CapabilityRefusal,
    ProviderConformance, assess_capability, verify_assessment_coverage)
from app.market_data.requirements import compile_data_requirement_plan
from app.market_truth.authority import load_market_truth_snapshot, persist_market_truth_snapshot
from app.market_truth.identity import (CanonicalPhysicalInstrument, MarketTruthError,
    ProviderContract, ProviderEntity, ProviderProduct, Quality,
    persist_canonical_instrument, persist_provider_identity)
from app.market_truth.rulebook import MarketTruthSnapshot, RulebookRecord


UTC = dt.timezone.utc
T0 = dt.datetime(2026, 8, 1, tzinfo=UTC)


def A(letter: str) -> str:
    return "sha256:" + letter * 64


def _plan():
    declaration = {"schema": "data-requirement-declaration/1", "classification": "REQUIRES_DATA",
        "requirements": [{"requirement_id": "primary_close",
            "instrument": {"literal": {"role": "primary", "type": "PHYSICAL"}},
            "field": {"literal": "CLOSE"}, "timeframe": {"literal": 60},
            "history": {"literal": {"minimum_bars": 1, "warmup_bars": 20}},
            "freshness": {"literal": {"maximum_age_seconds": 60}},
            "depth": {"literal": {"kind": "NONE", "levels": None}},
            "session": {"literal": "INSTRUMENT_CALENDAR"},
            "alignment": {"literal": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60}},
            "derived_local": {"literal": False}}]}
    component = {"component_id": "leaf.close", "component_version": 1,
        "domain_family": "transform", "structural_role": "transform", "ports": [],
        "parameters": {}}
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types={},
        v2_components={("leaf.close", 1): component},
        data_requirement_declarations={("leaf.close", 1): declaration})
    document = {"format_version": 2, "strategy_id": "phase4", "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "P4", "description": None, "tags": []},
        "graph_inputs": [], "graph_outputs": [], "nodes": [{"node_id": "close",
            "component": {"component_id": "leaf.close", "component_version": 1},
            "parameters": {}}], "edges": []}
    return compile_data_requirement_plan(resolve_v2(document, registry))


def _offer(**changes):
    value = {"instrument": {"role": "primary", "type": "PHYSICAL"}, "field": "CLOSE",
        "timeframes": [60], "maximum_history_bars": 21,
        "available_from": T0 - dt.timedelta(days=1),
        "available_to": T0 + dt.timedelta(days=1),
        "maximum_freshness_seconds": 60, "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60},
        "derived_local": False, "entitled": True, "known": True}
    value.update(changes)
    return value


def _coverage():
    return {"instrument": {"role": "primary", "type": "PHYSICAL"},
        "field": "CLOSE", "resolution_seconds": 60,
        "history": {"from": T0 - dt.timedelta(days=1),
            "to": T0 + dt.timedelta(days=1), "bars": 21},
        "maximum_freshness_seconds": 60,
        "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60},
        "derived_local": False, "entitlement": "VERIFIED"}


def _facts():
    instrument = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "INDEX", "SPOT", "INR", None)
    entity = ProviderEntity("strategy-os", "vendor-a", "Vendor A Ltd")
    product = ProviderProduct(entity.address, "history-v1", "vendor-a-bars", "1")
    contract = ProviderContract("owner-a", product.address, "RESEARCH", ("HISTORICAL",),
        T0, T0 + dt.timedelta(days=30), A("a"))
    conformance = ProviderConformance(product.address, ("CLOSE",), (60,),
        "fixture-conformance", "1", T0, T0 + dt.timedelta(days=2), (A("b"),), "PASS",
        (_coverage(),))
    record = RulebookRecord("venue-calendar", (("venue", "XNSE"),),
        (("timezone", "Asia/Kolkata"),), T0, T0 + dt.timedelta(days=1),
        T0 + dt.timedelta(hours=1))
    truth = MarketTruthSnapshot((record,), T0, T0 + dt.timedelta(days=1),
        T0 + dt.timedelta(hours=2), Quality.OBSERVED, authority_scope="RESEARCH",
        instrument_addresses=(instrument.address,), source_evidence=(A("c"),))
    profile = CapabilityProfile("owner-a", "RESEARCH", 1, T0 + dt.timedelta(hours=2),
        T0 + dt.timedelta(hours=12), conformance.address, (_offer(),), 0,
        entity.address, product.address, contract.address)
    assessment = assess_capability(plan=_plan(), profile=profile, owner_id="owner-a",
        mode="RESEARCH", dataset_manifest_address=A("d"),
        market_truth_snapshot_address=truth.address, evaluation_policy_address=A("e"),
        assessment_evidence_address=A("f"), at_time=int(T0.timestamp()) + 3 * 3600,
        conformance=conformance, provider_contract=contract)
    return instrument, entity, product, contract, conformance, truth, profile, assessment


def _seed(session: Session):
    values = _facts()
    instrument, entity, product, contract, conformance, truth, profile, assessment = values
    persist_canonical_instrument(session, instrument)
    persist_provider_identity(session, entity, product, contract)
    persist_market_truth_snapshot(session, truth)
    persist_provider_conformance(session, conformance)
    persist_capability_profile(session, profile)
    persist_capability_assessment(session, assessment, plan=_plan(),
        at_time=T0 + dt.timedelta(hours=3))
    session.commit()
    return values


def test_legacy_v1_conformance_persists_and_reopens_but_cannot_certify_profile(tmp_path):
    _instrument, entity, product, contract, _current, _truth, profile, _assessment = _facts()
    legacy = ProviderConformance(
        product.address, ("CLOSE",), (60,), "fixture-conformance", "1",
        T0, T0 + dt.timedelta(days=2), (A("b"),), "PASS")
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'legacy-conformance.db'}", future=True)
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            persist_provider_identity(session, entity, product, contract)
            persist_provider_conformance(session, legacy)
            session.commit()
        with Session(engine) as session:
            loaded = load_provider_conformance(session, legacy.address)
            assert loaded == legacy
            assert loaded.schema == "provider-conformance/1"
            legacy_profile = CapabilityProfile(
                profile.owner_id, profile.mode, profile.profile_version,
                profile.observed_at, profile.expires_at, legacy.address,
                profile.offers, profile.change_level, profile.provider_entity_address,
                profile.provider_product_address, profile.provider_contract_address)
            with pytest.raises(CapabilityRefusal, match="exceeds conformance coverage"):
                persist_capability_profile(session, legacy_profile)
    finally:
        engine.dispose()


@pytest.fixture
def authority(tmp_path):
    path = tmp_path / "typed-authority.db"
    engine = sa.create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        values = _seed(session)
    yield path, engine, values
    engine.dispose()


def _load_all(session, values):
    conformance, truth, profile, assessment = values[4:]
    loaded_truth = load_market_truth_snapshot(session, truth.address)
    loaded_conformance = load_provider_conformance(session, conformance.address)
    loaded_profile = load_capability_profile(session, profile.capability_profile_address,
        at_time=T0 + dt.timedelta(hours=3))
    loaded_assessment = load_capability_assessment(session, assessment.authority_address,
        plan=_plan(), at_time=T0 + dt.timedelta(hours=3))
    verify_assessment_coverage(loaded_assessment, _plan())
    return loaded_truth, loaded_conformance, loaded_profile, loaded_assessment


def _corrupt(engine, model, address, **changes):
    """Model a corrupted/restored database file while testing loader defence in depth."""
    table = model.__table__.name
    with engine.begin() as connection:
        connection.exec_driver_sql(f'DROP TRIGGER "{table}_refuse_update"')
        connection.execute(sa.update(model).where(model.address == address).values(changes))


def test_adv_001_fresh_process_reconstructs_exact_bytes_addresses_and_copied_columns(authority):
    path, _engine, values = authority
    expected = [[value.address if hasattr(value, "address") else
                 (value.capability_profile_address if isinstance(value, CapabilityProfile)
                  else value.authority_address), value.canonical_bytes.hex()]
                for value in (values[5], values[4], values[6], values[7])]
    program = r'''
import json, runpy, sys, sqlalchemy as sa
from sqlalchemy.orm import Session
from app.market_data.authority import load_capability_assessment, load_capability_profile, load_provider_conformance
from app.market_data.capability import verify_assessment_coverage
from app.market_truth.authority import load_market_truth_snapshot
m=runpy.run_path(sys.argv[2]); plan=m['_plan'](); T0=m['T0']
engine=sa.create_engine('sqlite:///'+sys.argv[1], future=True)
with Session(engine) as s:
    truth=load_market_truth_snapshot(s, sys.argv[3])
    conf=load_provider_conformance(s, sys.argv[4])
    profile=load_capability_profile(s, sys.argv[5], at_time=T0+m['dt'].timedelta(hours=3))
    assessment=load_capability_assessment(s, sys.argv[6], plan=plan, at_time=T0+m['dt'].timedelta(hours=3))
    verify_assessment_coverage(assessment, plan)
print(json.dumps([[truth.address,truth.canonical_bytes.hex()],[conf.address,conf.canonical_bytes.hex()],
 [profile.capability_profile_address,profile.canonical_bytes.hex()],[assessment.authority_address,assessment.canonical_bytes.hex()]]))
'''
    result = subprocess.run([sys.executable, "-c", program, str(path), str(Path(__file__)),
        values[5].address, values[4].address, values[6].capability_profile_address,
        values[7].authority_address], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == expected


@pytest.mark.parametrize("model,index", [
    (AuthorityMarketTruthSnapshot, 5), (AuthorityProviderConformance, 4),
    (AuthorityCapabilityProfile, 6), (AuthorityCapabilityAssessment, 7)])
def test_adv_009_malformed_and_noncanonical_stored_evidence_refuses(authority, model, index):
    _path, engine, values = authority
    address = (values[index].capability_profile_address if index == 6 else
               values[index].authority_address if index == 7 else values[index].address)
    _corrupt(engine, model, address, canonical_json="{}")
    with Session(engine) as session, pytest.raises((CapabilityRefusal, MarketTruthError)):
        _load_all(session, values)


def test_adv_010_hostile_temporal_and_cardinality_bounds_refuse():
    values = _facts()
    with pytest.raises(CapabilityRefusal):
        ProviderConformance(values[2].address, ("CLOSE",), (60,), "x", "1", T0, T0,
            (A("1"),), "PASS")
    with pytest.raises(CapabilityRefusal, match="bound"):
        CapabilityProfile("owner-a", "RESEARCH", 1, T0, T0 + dt.timedelta(hours=1),
            values[4].address, tuple(_offer() for _ in range(10_001)), 0,
            values[1].address, values[2].address, values[3].address)


@pytest.mark.parametrize("model,index", [
    (AuthorityMarketTruthSnapshot, 5), (AuthorityProviderConformance, 4),
    (AuthorityCapabilityProfile, 6), (AuthorityCapabilityAssessment, 7)])
def test_adv_016_missing_or_unverified_authority_dependency_refuses(authority, model, index):
    _path, engine, values = authority
    address = (values[index].capability_profile_address if index == 6 else
               values[index].authority_address if index == 7 else values[index].address)
    _corrupt(engine, model, address, authority_state="LEGACY_UNVERIFIED")
    with Session(engine) as session, pytest.raises((CapabilityRefusal, MarketTruthError)):
        _load_all(session, values)


def test_adv_016_missing_authority_addresses_refuse(authority):
    _path, engine, _values = authority
    with Session(engine) as session:
        with pytest.raises(MarketTruthError, match="absent"):
            load_market_truth_snapshot(session, A("0"))
        with pytest.raises(CapabilityRefusal, match="absent"):
            load_provider_conformance(session, A("1"))
        with pytest.raises(CapabilityRefusal, match="absent"):
            load_capability_profile(session, A("2"), at_time=T0)
        with pytest.raises(CapabilityRefusal, match="absent"):
            load_capability_assessment(session, A("3"), plan=_plan(), at_time=T0)


@pytest.mark.parametrize("model,index,column,value", [
    (AuthorityMarketTruthSnapshot, 5, "quality", "UNKNOWN"),
    (AuthorityProviderConformance, 4, "product_address", A("9")),
    (AuthorityCapabilityProfile, 6, "owner_id", "owner-b"),
    (AuthorityCapabilityAssessment, 7, "mode", "PAPER")])
def test_adv_018_forged_address_or_copied_column_refuses(authority, model, index, column, value):
    _path, engine, values = authority
    address = (values[index].capability_profile_address if index == 6 else
               values[index].authority_address if index == 7 else values[index].address)
    _corrupt(engine, model, address, **{column: value})
    with Session(engine) as session, pytest.raises((CapabilityRefusal, MarketTruthError)):
        _load_all(session, values)


def test_adv_020_wrong_provider_dependency_bytes_under_requested_address_refuse(authority):
    _path, engine, values = authority
    other_entity = ProviderEntity("strategy-os", "vendor-b", "Vendor B Ltd")
    other_product = ProviderProduct(other_entity.address, "history-v2", "vendor-b-bars", "2")
    from app.db.models import AuthorityProviderProduct
    _corrupt(engine, AuthorityProviderProduct, values[2].address,
             canonical_json=other_product.canonical_bytes.decode())
    with Session(engine) as session, pytest.raises(CapabilityRefusal):
        load_provider_conformance(session, values[4].address)


@pytest.mark.parametrize("column,value", [
    ("owner_id", "wrong-owner"), ("mode", "PAPER"),
    ("product_address", A("8")), ("contract_address", A("7"))])
def test_adv_022_wrong_owner_mode_product_or_contract_substitution_refuses(authority, column, value):
    _path, engine, values = authority
    _corrupt(engine, AuthorityCapabilityProfile, values[6].capability_profile_address,
             **{column: value})
    with Session(engine) as session, pytest.raises(CapabilityRefusal):
        load_capability_profile(session, values[6].capability_profile_address,
            at_time=T0 + dt.timedelta(hours=3))


def test_adv_023_future_recorded_truth_and_stale_or_future_profile_refuse(authority):
    _path, engine, values = authority
    truth = values[5]
    forged = json.loads(truth.canonical_bytes)
    forged["fact"]["records"][0]["recorded_at"] = (T0 + dt.timedelta(hours=3)).isoformat()
    forged_json = json.dumps(forged, sort_keys=True, separators=(",", ":"))
    _corrupt(engine, AuthorityMarketTruthSnapshot, truth.address, canonical_json=forged_json)
    with Session(engine) as session, pytest.raises(MarketTruthError):
        load_market_truth_snapshot(session, truth.address)
    with Session(engine) as session, pytest.raises(CapabilityRefusal, match="stale"):
        load_capability_profile(session, values[6].capability_profile_address,
            at_time=T0 + dt.timedelta(days=2))


def test_adv_024_explicit_empty_capability_is_unknown_and_absent_conformance_refuses():
    values = _facts()
    empty = CapabilityProfile("owner-a", "RESEARCH", 1, T0, T0 + dt.timedelta(hours=1),
        values[4].address, (), 0, values[1].address, values[2].address, values[3].address)
    result = assess_capability(plan=_plan(), profile=empty, owner_id="owner-a", mode="RESEARCH",
        dataset_manifest_address=A("1"), market_truth_snapshot_address=A("2"),
        evaluation_policy_address=A("3"), assessment_evidence_address=A("4"),
        at_time=int(T0.timestamp()) + 1, conformance=values[4], provider_contract=values[3])
    assert result.requirement_results[0]["result"] == "UNKNOWN"
    with pytest.raises(CapabilityRefusal, match="fields"):
        ProviderConformance(values[2].address, (), (60,), "x", "1", T0,
            T0 + dt.timedelta(hours=1), (A("5"),), "PASS")


def test_adv_025_ten_thousand_offer_limit_is_closed():
    values = _facts()
    offers = tuple(_offer() for _ in range(10_000))
    profile = CapabilityProfile("owner-a", "RESEARCH", 1, T0, T0 + dt.timedelta(hours=1),
        values[4].address, offers, 0, values[1].address, values[2].address, values[3].address)
    assert len(profile.offers) == 10_000
    with pytest.raises(CapabilityRefusal, match="bound"):
        CapabilityProfile("owner-a", "RESEARCH", 1, T0, T0 + dt.timedelta(hours=1),
            values[4].address, offers + (_offer(),), 0, values[1].address,
            values[2].address, values[3].address)


def test_loader_query_count_is_bounded(authority):
    _path, engine, values = authority
    statements = []
    def record_query(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)
    sa.event.listen(engine, "before_cursor_execute", record_query)
    try:
        with Session(engine) as session:
            _load_all(session, values)
    finally:
        sa.event.remove(engine, "before_cursor_execute", record_query)
    assert len(statements) <= 24


def test_adv_026_database_failure_never_returns_authority_and_retry_reconstructs(authority):
    path, engine, values = authority
    connection = engine.connect()
    session = Session(bind=connection)
    connection.close()
    with pytest.raises(sa.exc.ResourceClosedError):
        load_market_truth_snapshot(session, values[5].address)
    session.close()
    retry_engine = sa.create_engine(f"sqlite:///{path}", future=True)
    with Session(retry_engine) as retry:
        assert _load_all(retry, values)[0].canonical_bytes == values[5].canonical_bytes
    retry_engine.dispose()


def test_adv_027_rollback_at_cancellation_boundary_leaves_no_authoritative_prefix(tmp_path):
    path = tmp_path / "cancel.db"
    engine = sa.create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    values = _facts()
    writer = Session(engine)
    try:
        persist_canonical_instrument(writer, values[0])
        persist_provider_identity(writer, values[1], values[2], values[3])
        persist_market_truth_snapshot(writer, values[5])
        persist_provider_conformance(writer, values[4])
        persist_capability_profile(writer, values[6])
        persist_capability_assessment(writer, values[7], plan=_plan(),
            at_time=T0 + dt.timedelta(hours=3))
        raise asyncio.CancelledError
    except asyncio.CancelledError:
        writer.rollback()
    finally:
        writer.close()
    with Session(engine) as reader, pytest.raises(CapabilityRefusal, match="absent"):
        load_capability_assessment(reader, values[7].authority_address, plan=_plan(), at_time=T0)
    with Session(engine) as retry:
        _seed(retry)
        assert _load_all(retry, values)[3].canonical_bytes == values[7].canonical_bytes


@pytest.mark.skipif(not os.environ.get("PT_TEST_POSTGRES_URL"),
                    reason="disposable PostgreSQL 16 URL not supplied")
def test_sqlite_postgresql16_authority_reconstruction_parity(pg_sandbox, tmp_path):
    sqlite_engine = sa.create_engine(f"sqlite:///{tmp_path / 'parity.db'}", future=True)
    postgres_engine = pg_sandbox.engine(
        "execution", connect_args={"options": "-c timezone=UTC"})
    results = []
    try:
        for engine in (sqlite_engine, postgres_engine):
            Base.metadata.create_all(engine)
            with Session(engine) as session:
                values = _seed(session)
            engine.dispose()
            reopened = sa.create_engine(str(engine.url), future=True)
            with Session(reopened) as session:
                results.append(tuple(item.canonical_bytes for item in _load_all(session, values)))
            reopened.dispose()
        assert results[0] == results[1]
    finally:
        sqlite_engine.dispose()
        postgres_engine.dispose()
