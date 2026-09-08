from __future__ import annotations

import datetime as dt
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.backtest.dataset_store import (
    DatasetManifest, DatasetSegment, dataset_byte_digest, verify_dataset_manifest,
)
from app.db.models import AuthorityMarketTruthSnapshot, Base
from app.ir.hashing import canonical_json
from app.ir.validity import valid
from app.market_data.authority import (
    persist_capability_profile, persist_provider_conformance,
)
from app.market_data.capability import CapabilityProfile, ProviderConformance
from app.market_data.capability import assess_capability
from app.market_data.dataset_authority import (
    AdjustmentPolicy, AlignmentPolicy, DatasetCorrection, DatasetCreationEvidence,
    DeterministicAlgorithm, MissingDataPolicy, NormalizationTransform, RawSchema,
    RollPolicy, persist_adjustment_policy, persist_alignment_policy,
    persist_dataset_correction, persist_dataset_creation_evidence, persist_deterministic_algorithm,
    persist_missing_data_policy, persist_normalization_transform, persist_raw_schema,
    persist_roll_policy,
)
from app.market_data.observations import (
    NormalizedMarketObservation, ProviderObservation, RawObservationSegment,
    persist_normalized_observation, persist_provider_observation, persist_raw_segment,
)
from app.market_truth.authority import load_market_truth_snapshot, persist_market_truth_snapshot
from app.market_truth.identity import (
    CanonicalPhysicalInstrument, ProviderContract, ProviderEntity,
    ProviderInstrumentAlias, ProviderProduct, Quality, persist_canonical_instrument,
    persist_provider_alias, persist_provider_identity,
)
from app.market_truth.rulebook import MarketTruthSnapshot, RulebookRecord
from app.market_truth.temporal import to_sql_utc_naive
from research.domain.migrate import migrate_research_db
from research.domain.models import ResearchDatasetManifestV2
from research.domain.strategy_admissions import (
    load_verified_dataset_authority, persist_verified_dataset_authority,
)
from tests.test_market_truth_domain import (
    LEGACY_V2_SNAPSHOT_ADDRESS, LEGACY_V2_SNAPSHOT_BYTES,
)

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 8, 1, tzinfo=UTC)


def address(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


def _offer(*, field: str = "CLOSE", timeframe: int = 60,
           depth_kind: str = "NONE", depth_levels: int | None = None):
    return {"instrument": {"role": "primary", "type": "PHYSICAL"}, "field": field,
        "timeframes": [timeframe], "maximum_history_bars": 21,
        "available_from": T0 - dt.timedelta(days=1),
        "available_to": T0 + dt.timedelta(days=1),
        "maximum_freshness_seconds": 60,
        "depth": {"kind": depth_kind, "levels": depth_levels},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60},
        "derived_local": False, "entitled": True, "known": True}


def _coverage(*, field: str = "CLOSE", timeframe: int = 60,
              depth_kind: str = "NONE", depth_levels: int | None = None):
    return {"instrument": {"role": "primary", "type": "PHYSICAL"},
        "field": field, "resolution_seconds": timeframe,
        "history": {"from": T0 - dt.timedelta(days=1),
            "to": T0 + dt.timedelta(days=1), "bars": 21},
        "maximum_freshness_seconds": 60,
        "depth": {"kind": depth_kind, "levels": depth_levels},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60},
        "derived_local": False, "entitlement": "VERIFIED"}


def _seed_execution(
    session: Session, owner_id: str = "owner-a", *,
    instrument: CanonicalPhysicalInstrument | None = None,
    supporting_instruments: tuple[CanonicalPhysicalInstrument, ...] = (),
    additional_truth_records: tuple[RulebookRecord, ...] = (),
    provider_token: str = "token-1", provider_symbol: str = "NIFTY",
    field: str = "CLOSE", timeframe: int = 60,
    offer_depth_kind: str = "NONE", offer_depth_levels: int | None = None,
    venue_timezone: str = "Asia/Kolkata",
):
    instrument = instrument or CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "INDEX", "SPOT", "INR", None)
    entity = ProviderEntity("strategy-os", "vendor-a", "Vendor A Ltd")
    product = ProviderProduct(entity.address, "history-v1", "vendor-bars", "1")
    contract = ProviderContract(
        owner_id, product.address, "RESEARCH", ("HISTORICAL",), T0, None,
        address("contract-evidence"))
    alias = ProviderInstrumentAlias(
        product.address, provider_token, provider_symbol, instrument.address, "1", T0, None,
        "vendor-bars", address("alias-evidence"))
    payload = b'{"close":123.5}'
    raw_segment = RawObservationSegment(
        owner_id, product.address, contract.address, "application/json", "vendor-bar/1",
        payload, T0 + dt.timedelta(minutes=2))
    observation = ProviderObservation(
        owner_id, entity.address, product.address, contract.address, alias.address,
        provider_token, "vendor-bar/1", field.lower(), timeframe, T0, T0 + dt.timedelta(minutes=1),
        T0 + dt.timedelta(minutes=1, seconds=2), T0 + dt.timedelta(minutes=2), "seq-1",
        "original", raw_segment.address, 0, len(payload), hashlib.sha256(payload).hexdigest(),
        valid(1).state)
    algorithm = DeterministicAlgorithm(
        owner_id, "dataset-normalize", "1", address("implementation"),
        (address("vector"),), T0 + dt.timedelta(hours=2))
    raw_schema = RawSchema(
        owner_id, product.address, contract.address, "vendor-bar/1",
        ((field.lower(), "decimal"),), address("schema-evidence"), T0 + dt.timedelta(hours=2))
    truth_record = RulebookRecord(
        "venue-calendar", (("venue", instrument.venue_code),), (("timezone", venue_timezone),),
        T0, T0 + dt.timedelta(days=1), T0 + dt.timedelta(hours=1))
    truth_instruments = tuple(sorted({
        instrument.address,
        *(supporting.address for supporting in supporting_instruments),
    }))
    truth = MarketTruthSnapshot(
        (truth_record, *additional_truth_records),
        T0, T0 + dt.timedelta(days=1), T0 + dt.timedelta(hours=2),
        Quality.OBSERVED, authority_scope="RESEARCH",
        instrument_addresses=truth_instruments, source_evidence=(address("truth-evidence"),))
    alignment = AlignmentPolicy(
        owner_id, instrument.venue_code, "regular", venue_timezone, 60, truth.address,
        algorithm.address, T0 + dt.timedelta(hours=2))
    missing = MissingDataPolicy(
        owner_id, "REFUSE", (), algorithm.address, T0 + dt.timedelta(hours=2))
    adjustment = AdjustmentPolicy(
        owner_id, (instrument.address,), (truth.address,), "NONE", algorithm.address,
        T0 + dt.timedelta(hours=2))
    roll = RollPolicy(
        owner_id, (instrument.address,), (truth.address,), "NONE", algorithm.address,
        T0 + dt.timedelta(hours=2), "NOT_APPLICABLE")
    transform = NormalizationTransform(
        owner_id, (raw_schema.address,), "strategy-bar/1", (), algorithm.address,
        T0 + dt.timedelta(hours=2))
    normalized = NormalizedMarketObservation(
        instrument.address, (observation.address,), transform.address, "1", alignment.address,
        algorithm.address, "1", truth.address, "strategy-bar/1", field.lower(), timeframe, T0,
        T0 + dt.timedelta(minutes=1), T0 + dt.timedelta(minutes=1, seconds=2),
        T0 + dt.timedelta(minutes=2), valid(123.5))
    creation = DatasetCreationEvidence(
        owner_id, "phase4-test", tuple(sorted((observation.address, normalized.address))),
        (raw_segment.address,), algorithm.address, T0 + dt.timedelta(hours=2))
    correction = DatasetCorrection(
        owner_id, product.address, contract.address, 0, None, "initial correction",
        creation.address, algorithm.address, T0 + dt.timedelta(hours=2))
    conformance = ProviderConformance(
        product.address, (field,), (timeframe,), "fixture", "1", T0,
        T0 + dt.timedelta(days=2), (address("conformance-evidence"),), "PASS",
        (_coverage(field=field, timeframe=timeframe, depth_kind=offer_depth_kind,
            depth_levels=offer_depth_levels),))
    profile = CapabilityProfile(
        owner_id, "RESEARCH", 1, T0 + dt.timedelta(hours=2),
        T0 + dt.timedelta(hours=12), conformance.address, (_offer(
            field=field, timeframe=timeframe, depth_kind=offer_depth_kind,
            depth_levels=offer_depth_levels),), 0,
        entity.address, product.address, contract.address)

    for supporting_instrument in supporting_instruments:
        persist_canonical_instrument(session, supporting_instrument)
    persist_canonical_instrument(session, instrument)
    persist_provider_identity(session, entity, product, contract)
    persist_provider_alias(session, alias)
    persist_raw_segment(session, raw_segment)
    persist_provider_observation(session, observation)
    persist_normalized_observation(session, normalized)
    persist_market_truth_snapshot(session, truth)
    persist_provider_conformance(session, conformance)
    persist_capability_profile(session, profile)
    persist_deterministic_algorithm(session, algorithm)
    persist_raw_schema(session, raw_schema)
    persist_normalization_transform(session, transform)
    persist_alignment_policy(session, alignment)
    persist_missing_data_policy(session, missing)
    persist_adjustment_policy(session, adjustment)
    persist_roll_policy(session, roll)
    persist_dataset_creation_evidence(session, creation)
    persist_dataset_correction(session, correction)
    session.flush()
    return locals()


def _authority(values, raw: bytes = b"one-row", owner_id: str | None = None):
    owner_id = values["profile"].owner_id if owner_id is None else owner_id
    segment = DatasetSegment(
        owner_id=owner_id, object_address=address("dataset-object"),
        byte_digest=dataset_byte_digest(raw), byte_length=len(raw),
        media_type="application/x-test", raw_schema_address=values["raw_schema"].address,
        row_start=0, row_end=1, instrument_addresses=(values["instrument"].address,),
        fields=(values["field"].lower(),), event_start=T0.isoformat(),
        event_end=(T0 + dt.timedelta(minutes=1)).isoformat(),
        availability_start=T0.isoformat(),
        availability_end=(T0 + dt.timedelta(minutes=2)).isoformat(),
        provider_product_addresses=(values["product"].address,),
        provider_contract_addresses=(values["contract"].address,),
        provider_observation_addresses=(values["observation"].address,),
        normalized_observation_addresses=(values["normalized"].address,),
        normalization_transform_addresses=(values["transform"].address,),
        algorithm_addresses=(values["algorithm"].address,),
        correction_addresses=(values["correction"].address,),
        creation_evidence_address=values["creation"].address)
    manifest = DatasetManifest(
        owner_id=owner_id, purpose="research", mode="RESEARCH",
        segment_addresses=(segment.segment_address,), aggregate_byte_digest=dataset_byte_digest(raw),
        aggregate_byte_length=len(raw), instrument_addresses=segment.instrument_addresses,
        fields=segment.fields, event_start=segment.event_start, event_end=segment.event_end,
        availability_start=segment.availability_start, availability_end=segment.availability_end,
        gaps=(), correction_addresses=segment.correction_addresses,
        provider_entity_addresses=(values["entity"].address,),
        provider_product_addresses=segment.provider_product_addresses,
        provider_contract_addresses=segment.provider_contract_addresses,
        provider_observation_addresses=segment.provider_observation_addresses,
        normalized_observation_addresses=segment.normalized_observation_addresses,
        raw_schema_addresses=(segment.raw_schema_address,),
        normalization_transform_addresses=segment.normalization_transform_addresses,
        truth_snapshot_addresses=(values["truth"].address,),
        creation_evidence_addresses=(segment.creation_evidence_address,),
        capability_profile_address=values["profile"].capability_profile_address,
        alignment_policy_address=values["alignment"].address,
        missing_data_policy_address=values["missing"].address,
        adjustment_policy_address=values["adjustment"].address,
        roll_policy_address=values["roll"].address,
        algorithm_addresses=segment.algorithm_addresses,
        created_at=(T0 + dt.timedelta(hours=2)).isoformat(),
        recorded_at=(T0 + dt.timedelta(hours=2, seconds=1)).isoformat())
    return manifest, {segment.segment_address: (segment, raw)}


def _engines(tmp_path):
    execution = create_engine(f"sqlite:///{tmp_path / 'execution.db'}")
    Base.metadata.create_all(execution)
    research = create_engine(f"sqlite:///{tmp_path / 'research.db'}")
    migrate_research_db(research)
    return execution, research


def test_manifest_is_acyclic_closed_and_identity_refuses_mutation(tmp_path):
    execution, _research = _engines(tmp_path)
    with Session(execution) as session:
        values = _seed_execution(session)
        manifest, segments = _authority(values)
        assert verify_dataset_manifest(manifest, segments)[0].segment_address in segments
        with pytest.raises(ValueError, match="fields are not closed"):
            DatasetManifest(**{**manifest.fact(),
                "capability_assessment_address": address("assessment")})
        with pytest.raises(ValueError, match="digest mismatch"):
            verify_dataset_manifest(manifest, {
                key: (segment, b"changed") for key, (segment, _raw) in segments.items()})
        other = DatasetManifest(**{**manifest.fact(), "owner_id": "owner-b"})
        assert other.manifest_address != manifest.manifest_address
        with pytest.raises(ValueError, match="owner mismatch"):
            verify_dataset_manifest(other, segments)


@pytest.mark.parametrize(("field", "replacement"), (
    ("aggregate_byte_digest", address("changed-bytes")),
    ("aggregate_byte_length", 99),
    ("event_end", (T0 + dt.timedelta(minutes=2)).isoformat()),
    ("correction_addresses", (address("changed-correction"),)),
    ("truth_snapshot_addresses", (address("changed-truth"),)),
    ("normalization_transform_addresses", (address("changed-transform"),)),
    ("alignment_policy_address", address("changed-alignment")),
    ("missing_data_policy_address", address("changed-missing")),
    ("adjustment_policy_address", address("changed-adjustment")),
    ("roll_policy_address", address("changed-roll")),
    ("algorithm_addresses", (address("changed-algorithm"),)),
    ("owner_id", "owner-b"),
    ("provider_product_addresses", (address("changed-product"),)),
    ("provider_contract_addresses", (address("changed-contract"),)),
))
def test_manifest_transitive_authority_changes_identity(tmp_path, field, replacement):
    execution, _research = _engines(tmp_path)
    with Session(execution) as session:
        values = _seed_execution(session)
        manifest, _segments = _authority(values)
        changed = DatasetManifest(**{**manifest.fact(), field: replacement})
        assert changed.manifest_address != manifest.manifest_address


def test_sqlite_persist_replay_restart_and_forged_column_refusal(tmp_path):
    execution, research = _engines(tmp_path)
    with Session(execution) as execution_session, Session(research) as research_session:
        values = _seed_execution(execution_session)
        manifest, segments = _authority(values)
        persisted = persist_verified_dataset_authority(
            research_session, manifest=manifest, segments=segments,
            execution_session=execution_session, at_time=T0 + dt.timedelta(hours=3))
        assert persisted.manifest.manifest_address == manifest.manifest_address
        execution_session.commit(); research_session.commit()
    execution.dispose(); research.dispose()
    execution = create_engine(f"sqlite:///{tmp_path / 'execution.db'}")
    research = create_engine(f"sqlite:///{tmp_path / 'research.db'}")
    with Session(execution) as execution_session, Session(research) as research_session:
        loaded = load_verified_dataset_authority(
            research_session, owner_id=manifest.owner_id,
            manifest_address=manifest.manifest_address, execution_session=execution_session,
            at_time=T0 + dt.timedelta(hours=3))
        assert loaded.object_bytes == (b"one-row",)
        research_session.execute(text("DROP TRIGGER trg_research_dataset_manifests_v2_no_update"))
        research_session.execute(text(
            "UPDATE research_dataset_manifests_v2 SET aggregate_byte_length=99 "
            "WHERE owner_id=:owner AND manifest_address=:address"),
            {"owner": manifest.owner_id, "address": manifest.manifest_address})
        research_session.commit()
        with pytest.raises(ValueError, match="copied columns"):
            load_verified_dataset_authority(
                research_session, owner_id=manifest.owner_id,
                manifest_address=manifest.manifest_address, execution_session=execution_session,
                at_time=T0 + dt.timedelta(hours=3))


@pytest.mark.parametrize("fail", [False, True])
def test_dependency_row_references_end_with_the_pass_even_on_error(tmp_path, fail):
    import gc
    import weakref
    from app.db.models import AuthorityProviderProduct
    from app.market_data.observations import retain_observation_dependencies
    execution, research = _engines(tmp_path)
    with Session(execution) as session:
        values = _seed_execution(session)
        session.commit()
        before = (len(session.dispatch.loaded_as_persistent), len(session.dispatch.pending_to_persistent))
        observed = []

        @retain_observation_dependencies
        def inspect(execution_session):
            row = execution_session.get(AuthorityProviderProduct, values["product"].address)
            reference = weakref.ref(row)
            observed.append(reference)
            del row
            gc.collect()
            assert reference() is not None
            if fail:
                raise ValueError("synthetic pass failure")

        if fail:
            with pytest.raises(ValueError, match="synthetic pass failure"):
                inspect(session)
        else:
            inspect(session)
        gc.collect()
        assert observed[0]() is None
        assert (len(session.dispatch.loaded_as_persistent), len(session.dispatch.pending_to_persistent)) == before
        # A later pass obtains a fresh ORM row; there is no session-lifetime pin.
        row = session.get(AuthorityProviderProduct, values["product"].address)
        assert row.product_code == values["product"].product_code
    execution.dispose(); research.dispose()


def test_dependency_row_retention_does_not_bypass_current_row_validation(tmp_path):
    from app.db.models import AuthorityProviderProduct
    from app.market_data.observations import retain_observation_dependencies
    from app.market_truth.identity import load_provider_identity, MarketTruthError
    execution, research = _engines(tmp_path)
    with Session(execution) as session:
        values = _seed_execution(session)
        session.commit()

        @retain_observation_dependencies
        def inspect(execution_session):
            load_provider_identity(execution_session, values["contract"].address)
            row = execution_session.get(AuthorityProviderProduct, values["product"].address)
            row.product_code = "forged"
            with pytest.raises(MarketTruthError, match="copied columns"):
                load_provider_identity(execution_session, values["contract"].address)

        inspect(session)
        session.rollback()
        assert load_provider_identity(session, values["contract"].address)[1] == values["product"]
    execution.dispose(); research.dispose()


def test_dependency_row_retention_leaves_batched_session_facades_unchanged():
    from app.market_data.observations import retain_observation_dependencies
    facade = object()
    @retain_observation_dependencies
    def inspect(execution_session):
        return execution_session
    assert inspect(facade) is facade


@pytest.mark.parametrize("helper,fact,field,value", [
    ("_verify_provider_observation_roles", "observation", "owner_id", "owner-b"),
    ("_verify_provider_observation_roles", "observation", "provider_entity_address", address("foreign")),
    ("_verify_provider_observation_roles", "observation", "provider_product_address", address("foreign")),
    ("_verify_provider_observation_roles", "observation", "provider_contract_address", address("foreign")),
    ("_verify_normalized_observation_roles", "normalized", "provider_observation_addresses", (address("foreign"),)),
    ("_verify_normalized_observation_roles", "normalized", "canonical_instrument_address", address("foreign")),
    ("_verify_normalized_observation_roles", "normalized", "transform_address", address("foreign")),
    ("_verify_normalized_observation_roles", "normalized", "policy_address", address("foreign")),
    ("_verify_normalized_observation_roles", "normalized", "algorithm_address", address("foreign")),
    ("_verify_normalized_observation_roles", "normalized", "market_truth_address", address("foreign")),
    ("_verify_raw_schema_roles", "raw_schema", "provider_product_address", address("foreign")),
    ("_verify_raw_schema_roles", "raw_schema", "provider_contract_address", address("foreign")),
    ("_verify_transform_roles", "transform", "input_raw_schema_addresses", (address("foreign"),)),
    ("_verify_transform_roles", "transform", "algorithm_address", address("foreign")),
    ("_verify_creation_roles", "creation", "algorithm_address", address("foreign")),
    ("_verify_creation_roles", "creation", "source_addresses", (address("foreign"),)),
    ("_verify_correction_roles", "correction", "provider_product_address", address("foreign")),
    ("_verify_correction_roles", "correction", "provider_contract_address", address("foreign")),
    ("_verify_correction_roles", "correction", "creation_evidence_address", address("foreign")),
    ("_verify_correction_roles", "correction", "algorithm_address", address("foreign")),
])
def test_dependency_role_checks_refuse_cross_manifest_facts(tmp_path, helper, fact, field, value):
    from research.domain import strategy_admissions as admissions
    execution, research = _engines(tmp_path)
    with Session(execution) as session:
        values = _seed_execution(session)
        manifest, _ = _authority(values)
        verify = getattr(admissions, helper)
        verify(manifest, [values[fact]])
        wrong = replace(values[fact], **{field: value})
        with pytest.raises(ValueError, match="do not match manifest"):
            verify(manifest, [wrong])
    execution.dispose(); research.dispose()


@pytest.mark.parametrize("helper,field,value", [
    ("_verify_policy_scope", "owner_id", "owner-b"),
    ("_verify_policy_scope", "instrument_addresses", (address("foreign"),)),
    ("_verify_policy_dependencies", "algorithm_address", address("foreign")),
    ("_verify_policy_dependencies", "truth_snapshot_addresses", (address("foreign"),)),
])
def test_dependency_policy_checks_keep_owner_and_source_boundaries(tmp_path, helper, field, value):
    from research.domain import strategy_admissions as admissions
    execution, research = _engines(tmp_path)
    with Session(execution) as session:
        values = _seed_execution(session)
        manifest, _ = _authority(values)
        verify = getattr(admissions, helper)
        verify(manifest, values["adjustment"], "adjustment policy")
        wrong = replace(values["adjustment"], **{field: value})
        with pytest.raises(ValueError, match="dataset adjustment policy"):
            verify(manifest, wrong, "adjustment policy")
        if helper == "_verify_policy_dependencies":
            wrong_alignment = replace(values["alignment"], truth_snapshot_address=address("foreign"))
            with pytest.raises(ValueError, match="truth does not match"):
                verify(manifest, wrong_alignment, "alignment policy")
    execution.dispose(); research.dispose()


@pytest.mark.parametrize("field,value", [("owner_id", "owner-b"), ("mode", "PAPER"),
    ("provider_entity_addresses", (address("foreign"),)),
    ("provider_product_addresses", (address("foreign"),)),
    ("provider_contract_addresses", (address("foreign"),))])
def test_dependency_profile_checks_reject_mismatched_manifest_roles(tmp_path, field, value):
    from research.domain import strategy_admissions as admissions
    execution, research = _engines(tmp_path)
    with Session(execution) as session:
        values = _seed_execution(session)
        manifest, _ = _authority(values)
        admissions._verify_profile_roles(session, manifest, T0 + dt.timedelta(hours=3))
        wrong = DatasetManifest(**{**manifest.fact(), field: value})
        with pytest.raises(ValueError, match="capability-profile roles"):
            admissions._verify_profile_roles(session, wrong, T0 + dt.timedelta(hours=3))
    execution.dispose(); research.dispose()


@pytest.mark.parametrize("field,value", [("owner_id", "owner-b"),
    ("provider_entity_addresses", (address("foreign"),)),
    ("provider_product_addresses", (address("foreign"),))])
def test_dependency_provider_identity_roles_remain_exact(tmp_path, field, value):
    from research.domain import strategy_admissions as admissions
    execution, research = _engines(tmp_path)
    with Session(execution) as session:
        values = _seed_execution(session)
        manifest, _ = _authority(values)
        admissions._verify_provider_identity_roles(session, manifest)
        with pytest.raises(ValueError, match="dataset provider"):
            admissions._verify_provider_identity_roles(session, DatasetManifest(**{**manifest.fact(), field: value}))
        with pytest.raises(ValueError, match="owner mismatch"):
            admissions._load_fixed_roles(session, DatasetManifest(**{**manifest.fact(), "owner_id": "owner-b"}))
    execution.dispose(); research.dispose()


def test_nmt_001_snapshot_persistence_reopen_and_canonical_mutation_refusal(tmp_path):
    execution, _research = _engines(tmp_path)
    with Session(execution) as session:
        values = _seed_execution(session)
        legacy_snapshot = MarketTruthSnapshot.from_bytes(LEGACY_V2_SNAPSHOT_BYTES)
        with pytest.raises(ValueError, match="reconstruction-only"):
            persist_market_truth_snapshot(session, legacy_snapshot)
        session.add(AuthorityMarketTruthSnapshot(
            address=legacy_snapshot.address,
            schema=legacy_snapshot.schema,
            canonical_json=LEGACY_V2_SNAPSHOT_BYTES.decode("utf-8"),
            authority_scope=legacy_snapshot.authority_scope,
            quality=legacy_snapshot.quality.value,
            knowledge_cutoff=to_sql_utc_naive(
                legacy_snapshot.knowledge_cutoff, "knowledge_cutoff"
            ),
            effective_from=to_sql_utc_naive(
                legacy_snapshot.effective_from, "effective_from"
            ),
            effective_to=to_sql_utc_naive(
                legacy_snapshot.effective_to, "effective_to", nullable=True
            ),
            authority_state="VERIFIED_V2",
        ))
        cutoff_snapshot = values["truth"]
        earlier_snapshot = replace(
            cutoff_snapshot,
            recorded_at=cutoff_snapshot.recorded_at - dt.timedelta(minutes=30),
        )
        persist_market_truth_snapshot(session, earlier_snapshot)
        session.commit()
        expected = {
            cutoff_snapshot.address: cutoff_snapshot.recorded_at,
            earlier_snapshot.address: earlier_snapshot.recorded_at,
            LEGACY_V2_SNAPSHOT_ADDRESS: legacy_snapshot.knowledge_cutoff,
        }
    execution.dispose()

    execution = create_engine(f"sqlite:///{tmp_path / 'execution.db'}")
    with Session(execution) as session:
        loaded = {
            address_value: load_market_truth_snapshot(session, address_value)
            for address_value in expected
        }
        assert {key: value.recorded_at for key, value in loaded.items()} == expected
        assert loaded[cutoff_snapshot.address].canonical_bytes != loaded[
            earlier_snapshot.address
        ].canonical_bytes
        assert loaded[cutoff_snapshot.address].schema == MarketTruthSnapshot.SCHEMA
        assert loaded[earlier_snapshot.address].schema == MarketTruthSnapshot.SCHEMA
        assert loaded[LEGACY_V2_SNAPSHOT_ADDRESS].canonical_bytes == (
            LEGACY_V2_SNAPSHOT_BYTES
        )
        assert loaded[LEGACY_V2_SNAPSHOT_ADDRESS].schema == (
            MarketTruthSnapshot.LEGACY_SCHEMA
        )

        legacy_row = session.get(
            AuthorityMarketTruthSnapshot, LEGACY_V2_SNAPSHOT_ADDRESS
        )
        original_legacy_cutoff = legacy_row.knowledge_cutoff
        with session.no_autoflush:
            legacy_row.knowledge_cutoff = original_legacy_cutoff + dt.timedelta(seconds=1)
            with pytest.raises(ValueError, match="copied columns"):
                load_market_truth_snapshot(session, LEGACY_V2_SNAPSHOT_ADDRESS)
            legacy_row.knowledge_cutoff = original_legacy_cutoff

        row = session.get(AuthorityMarketTruthSnapshot, earlier_snapshot.address)
        original_json = row.canonical_json
        document = json.loads(original_json)
        document["fact"].pop("recorded_at")
        with session.no_autoflush:
            row.canonical_json = canonical_json(document)
            with pytest.raises(ValueError, match="not closed"):
                load_market_truth_snapshot(session, earlier_snapshot.address)

            document = json.loads(original_json)
            document["fact"]["recorded_at"] = document["fact"]["knowledge_cutoff"]
            row.canonical_json = canonical_json(document)
            with pytest.raises(ValueError, match="copied columns"):
                load_market_truth_snapshot(session, earlier_snapshot.address)
            row.canonical_json = original_json

        assert load_market_truth_snapshot(
            session, earlier_snapshot.address
        ).canonical_bytes == earlier_snapshot.canonical_bytes
    execution.dispose()

    backend_dir = Path(__file__).resolve().parents[1]
    program = (
        "import sys;"
        "from sqlalchemy import create_engine;"
        "from sqlalchemy.orm import Session;"
        "from app.market_truth.authority import load_market_truth_snapshot;"
        "engine=create_engine(sys.argv[1],future=True);"
        "session=Session(engine);"
        "snapshot=load_market_truth_snapshot(session,sys.argv[2]);"
        "assert snapshot.address==sys.argv[2];"
        "assert snapshot.canonical_bytes.hex()==sys.argv[3];"
        "assert snapshot.schema=='market-truth-snapshot/2';"
        "print(snapshot.address);"
        "session.close();engine.dispose()"
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            program,
            f"sqlite:///{tmp_path / 'execution.db'}",
            LEGACY_V2_SNAPSHOT_ADDRESS,
            LEGACY_V2_SNAPSHOT_BYTES.hex(),
        ],
        cwd=backend_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == LEGACY_V2_SNAPSHOT_ADDRESS


def test_atomic_failure_exposes_no_manifest(tmp_path):
    execution, research = _engines(tmp_path)
    with Session(execution) as execution_session, Session(research) as research_session:
        values = _seed_execution(execution_session)
        manifest, segments = _authority(values)
        def fail(boundary):
            if boundary == "manifest":
                raise RuntimeError("injected")
        with pytest.raises(RuntimeError, match="injected"):
            persist_verified_dataset_authority(
                research_session, manifest=manifest, segments=segments,
                execution_session=execution_session, at_time=T0 + dt.timedelta(hours=3),
                failure_hook=fail)
        assert research_session.get(
            ResearchDatasetManifestV2, (manifest.owner_id, manifest.manifest_address)) is None


def test_actual_admission_and_cache_bind_manifest_then_assessment(tmp_path):
    from app.backtest.cache import verified_phase4_cache_identity
    from app.market_data.authority import persist_capability_assessment
    from app.strategy.admission import AdmissionRefused, admit_phase4_v2_strategy
    from tests.test_phase4_capability_admission import _evidence, _plan

    execution, research = _engines(tmp_path)
    registry, document, plan = _plan()
    at_time = T0 + dt.timedelta(hours=3)
    with Session(execution) as execution_session, Session(research) as research_session:
        values = _seed_execution(execution_session)
        manifest, segments = _authority(values)
        persist_verified_dataset_authority(
            research_session, manifest=manifest, segments=segments,
            execution_session=execution_session, at_time=at_time)
        assessment = assess_capability(
            plan=plan, profile=values["profile"], owner_id="owner-a", mode="RESEARCH",
            dataset_manifest_address=manifest.manifest_address,
            market_truth_snapshot_address=values["truth"].address,
            evaluation_policy_address=address("evaluation-policy"),
            assessment_evidence_address=address("assessment-evidence"),
            at_time=int(at_time.timestamp()), conformance=values["conformance"],
            provider_contract=values["contract"])
        persist_capability_assessment(
            execution_session, assessment, plan=plan, at_time=at_time)
        other_manifest, other_segments = _authority(values, b"two-row")
        persist_verified_dataset_authority(
            research_session, manifest=other_manifest, segments=other_segments,
            execution_session=execution_session, at_time=at_time)
        other_assessment = assess_capability(
            plan=plan, profile=values["profile"], owner_id="owner-a", mode="RESEARCH",
            dataset_manifest_address=other_manifest.manifest_address,
            market_truth_snapshot_address=values["truth"].address,
            evaluation_policy_address=address("evaluation-policy"),
            assessment_evidence_address=address("assessment-evidence"),
            at_time=int(at_time.timestamp()), conformance=values["conformance"],
            provider_contract=values["contract"])
        persist_capability_assessment(
            execution_session, other_assessment, plan=plan, at_time=at_time)
        execution_session.commit(); research_session.commit()

        wrapper = admit_phase4_v2_strategy(
            owner_id="owner-a", mode="RESEARCH", document=document, registry=registry,
            evidence=_evidence(), plan=plan, assessment_address=assessment.authority_address,
            dataset_manifest_address=manifest.manifest_address,
            market_truth_snapshot_address=values["truth"].address,
            evaluation_policy_address=assessment.evaluation_policy_address,
            research_session=research_session, execution_session=execution_session,
            at_time=at_time)
        cache_address = verified_phase4_cache_identity(
            research_session=research_session, execution_session=execution_session,
            owner_id="owner-a", authored_ir_address=plan.authored_ir_address,
            manifest_address=manifest.manifest_address,
            registry_snapshot_address=plan.registry_snapshot_address,
            resolved_graph_address=plan.resolved_graph_address,
            implementation_closure_address=plan.implementation_closure_address,
            declaration_addresses=plan.declaration_addresses, plan_address=plan.plan_address,
            capability_assessment_address=assessment.authority_address,
            market_truth_address=values["truth"].address,
            evaluation_policy_address=assessment.evaluation_policy_address,
            admission_address=wrapper.admission_address, plan=plan, at_time=at_time)
        assert len(cache_address) == 64

        def cache_pair(manifest_address, assessment_address):
            return verified_phase4_cache_identity(
                research_session=research_session, execution_session=execution_session,
                owner_id="owner-a", authored_ir_address=plan.authored_ir_address,
                manifest_address=manifest_address,
                registry_snapshot_address=plan.registry_snapshot_address,
                resolved_graph_address=plan.resolved_graph_address,
                implementation_closure_address=plan.implementation_closure_address,
                declaration_addresses=plan.declaration_addresses, plan_address=plan.plan_address,
                capability_assessment_address=assessment_address,
                market_truth_address=values["truth"].address,
                evaluation_policy_address=assessment.evaluation_policy_address,
                admission_address=wrapper.admission_address, plan=plan, at_time=at_time)

        def admit_pair(manifest_address, assessment_address):
            return admit_phase4_v2_strategy(
                owner_id="owner-a", mode="RESEARCH", document=document, registry=registry,
                evidence=_evidence(), plan=plan, assessment_address=assessment_address,
                dataset_manifest_address=manifest_address,
                market_truth_snapshot_address=values["truth"].address,
                evaluation_policy_address=assessment.evaluation_policy_address,
                research_session=research_session, execution_session=execution_session,
                at_time=at_time)

        refused_pairs = (
            (manifest.manifest_address, address("missing-assessment")),
            (address("missing-manifest"), assessment.authority_address),
            (other_manifest.manifest_address, assessment.authority_address),
            (manifest.manifest_address, other_assessment.authority_address),
        )
        for manifest_address, assessment_address in refused_pairs:
            with pytest.raises(ValueError):
                cache_pair(manifest_address, assessment_address)
            with pytest.raises(AdmissionRefused):
                admit_pair(manifest_address, assessment_address)


def test_writer_death_fresh_interpreter_reconstructs_admission_and_cold_warm_cache(tmp_path):
    from app.market_data.authority import persist_capability_assessment
    from tests.test_phase4_capability_admission import _plan

    execution, research = _engines(tmp_path)
    _registry, _document, plan = _plan()
    at_time = T0 + dt.timedelta(hours=3)
    with Session(execution) as execution_session, Session(research) as research_session:
        values = _seed_execution(execution_session)
        manifest, segments = _authority(values)
        persist_verified_dataset_authority(
            research_session, manifest=manifest, segments=segments,
            execution_session=execution_session, at_time=at_time)
        assessment = assess_capability(
            plan=plan, profile=values["profile"], owner_id="owner-a", mode="RESEARCH",
            dataset_manifest_address=manifest.manifest_address,
            market_truth_snapshot_address=values["truth"].address,
            evaluation_policy_address=address("evaluation-policy"),
            assessment_evidence_address=address("assessment-evidence"),
            at_time=int(at_time.timestamp()), conformance=values["conformance"],
            provider_contract=values["contract"])
        persist_capability_assessment(
            execution_session, assessment, plan=plan, at_time=at_time)
        execution_session.commit(); research_session.commit()
        arguments = (manifest.manifest_address, assessment.authority_address,
                     values["truth"].address, assessment.evaluation_policy_address)
    execution.dispose(); research.dispose()
    program = r'''
import json, sys
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.backtest.cache import verified_phase4_cache_identity
from app.strategy.admission import admit_phase4_v2_strategy
from tests.test_phase4_capability_admission import _evidence, _plan
execution=sa.create_engine("sqlite:///"+sys.argv[1])
research=sa.create_engine("sqlite:///"+sys.argv[2])
registry, document, plan = _plan()
manifest, assessment, truth, policy = sys.argv[3:7]
at_time=__import__("datetime").datetime.fromisoformat("2026-08-01T03:00:00+00:00")
with Session(execution) as execution_session, Session(research) as research_session:
    wrapper=admit_phase4_v2_strategy(owner_id="owner-a", mode="RESEARCH", document=document,
        registry=registry, evidence=_evidence(), plan=plan, assessment_address=assessment,
        dataset_manifest_address=manifest, market_truth_snapshot_address=truth,
        evaluation_policy_address=policy, research_session=research_session,
        execution_session=execution_session, at_time=at_time)
    kwargs=dict(research_session=research_session, execution_session=execution_session,
        owner_id="owner-a", authored_ir_address=plan.authored_ir_address,
        manifest_address=manifest, registry_snapshot_address=plan.registry_snapshot_address,
        resolved_graph_address=plan.resolved_graph_address,
        implementation_closure_address=plan.implementation_closure_address,
        declaration_addresses=plan.declaration_addresses, plan_address=plan.plan_address,
        capability_assessment_address=assessment, market_truth_address=truth,
        evaluation_policy_address=policy, admission_address=wrapper.admission_address,
        plan=plan, at_time=at_time)
    cold=verified_phase4_cache_identity(**kwargs)
    warm=verified_phase4_cache_identity(**kwargs)
print(json.dumps([wrapper.admission_address, cold, warm]))
'''
    result = subprocess.run(
        [sys.executable, "-c", program, str(tmp_path / "execution.db"),
         str(tmp_path / "research.db"), *arguments], check=True, capture_output=True, text=True)
    reconstructed = json.loads(result.stdout)
    assert reconstructed[1] == reconstructed[2]
    assert reconstructed[0].startswith("sha256:")
