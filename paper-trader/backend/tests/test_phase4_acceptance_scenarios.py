"""Composed Phase 4 acceptance scenarios over the accepted local contracts.

These scenarios use deterministic local facts only.  They do not claim a real
provider feed, order placement, entry/exit runtime policy, production migration,
or release rehearsal.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.backtest.cache import phase4_cache_identity
from app.core.strategy_admissions import put
from app.db.models import Base, Organization
from app.ir.hashing import content_address
from app.ir.registry import DependencyBoundary, PlatformRegistry, registered_v2_implementation
from app.ir.resolve import resolve_v2
from app.ir.validity import ValidityState, invalid, valid
from app.market_data.authority import persist_capability_assessment
from app.market_data.capability import assess_capability
from app.market_data.observations import AlignmentPolicy, DataObservation, align_observation, align_required_series
from app.market_data.requirements import compile_data_requirement_plan
from app.market_truth.authority import load_market_truth_snapshot
from app.market_truth.identity import (
    CanonicalInstrumentId,
    InstrumentSelector,
    ProviderInstrumentMapping,
    Quality,
    preserve_held_identity,
    validate_provider_mappings,
)
from app.market_truth.identity import load_canonical_instrument
from app.market_truth.rulebook import MarketTruthSnapshot, RulebookRecord
from app.strategy.admission import AdmissionRefused, V2AdmissionEvidence, admit_phase4_v2_strategy
from research.domain.admissions import store_admission
from research.domain.base import ResearchBase
from research.domain.strategy_admissions import persist_verified_dataset_authority
from tests.test_phase4_dataset_assessment_authority import (
    T0, _authority, _engines, _seed_execution, address,
)
from app.market_truth.identity import CanonicalPhysicalInstrument


UTC = timezone.utc
ANCHOR = datetime(2026, 1, 2, tzinfo=UTC)


def _address(character: str) -> str:
    return "sha256:" + character * 64


def _implementation(parameters, inputs):
    return {}


def _equity(*, venue: str, underlying: str, currency: str) -> CanonicalInstrumentId:
    return CanonicalInstrumentId(
        venue=venue,
        asset_class="EQUITY",
        economic_underlying=underlying,
        contract_kind="SPOT",
        currency=currency,
    )


def _weekly_call(*, strike: str) -> CanonicalInstrumentId:
    return CanonicalInstrumentId(
        venue="NSE",
        asset_class="OPTION",
        economic_underlying="NIFTY",
        contract_kind="WEEKLY_OPTION",
        currency="INR",
        expiry=ANCHOR + timedelta(days=7),
        strike=strike,
        option_right="CALL",
        multiplier="50",
    )


def _session_record(
    instrument: CanonicalInstrumentId,
    *,
    calendar: str,
    timezone_name: str,
    state: str,
    effective_from: datetime = ANCHOR,
    effective_to: datetime | None = ANCHOR + timedelta(days=30),
    record_kind: str = "session",
) -> RulebookRecord:
    return RulebookRecord(
        record_kind=record_kind,
        natural_key=(("instrument", instrument.address),),
        terms=(("calendar", calendar), ("state", state), ("timezone", timezone_name)),
        effective_from=effective_from,
        effective_to=effective_to,
        recorded_at=ANCHOR + timedelta(hours=1),
    )


def _snapshot(records: tuple[RulebookRecord, ...]) -> MarketTruthSnapshot:
    snapshot = MarketTruthSnapshot(
        records=records,
        effective_from=ANCHOR,
        effective_to=ANCHOR + timedelta(days=30),
        recorded_at=ANCHOR + timedelta(hours=2),
        quality=Quality.OBSERVED,
    )
    snapshot.require_observed_ground_truth()
    return snapshot


def _observation(
    instrument: CanonicalInstrumentId,
    *,
    field: str,
    event_time: datetime,
    available_at: datetime | None = None,
    completed_at: datetime | None = None,
    source_address: str = _address("a"),
    market_truth_address: str,
    numeric,
) -> DataObservation:
    return DataObservation(
        instrument=instrument.address,
        field=field,
        timeframe_seconds=60,
        event_time=event_time,
        available_at=available_at or event_time + timedelta(seconds=10),
        completed_at=completed_at or event_time + timedelta(seconds=10),
        source_address=source_address,
        market_truth_address=market_truth_address,
        numeric=numeric,
    )


def _scenario(
    *,
    requirement_id: str,
    field: str,
    timeframe: int,
    owner_id: str = "owner-a",
    strategy_id: str | None = None,
    instrument_type: str = "PHYSICAL",
    depth_kind: str = "NONE",
    depth_levels: int | None = None,
    offer_depth_kind: str | None = None,
    offer_depth_levels: int | None = None,
    session: str = "INSTRUMENT_CALENDAR",
    alignment_kind: str = "ASOF_BACKWARD",
    maximum_skew_seconds: int = 60,
    dataset_manifest_address: str | None = None,
    market_truth_snapshot_address: str | None = None,
    evaluation_policy_address: str | None = None,
    assessment_evidence_address: str | None = None,
):
    """Build one canonical local graph, plan, assessment, and evidence receipt."""
    component = {
        "component_id": "phase4.leaf",
        "component_version": 1,
        "domain_family": "transform",
        "structural_role": "transform",
        "ports": [],
        "parameters": {},
    }
    declaration = {
        "schema": "data-requirement-declaration/1",
        "classification": "REQUIRES_DATA",
        "requirements": [
            {
                "requirement_id": requirement_id,
                "instrument": {"literal": {"role": "primary", "type": instrument_type}},
                "field": {"literal": field},
                "timeframe": {"literal": timeframe},
                "history": {"literal": {"minimum_bars": 1, "warmup_bars": 20}},
                "freshness": {"literal": {"maximum_age_seconds": 60}},
                "depth": {"literal": {"kind": depth_kind, "levels": depth_levels}},
                "session": {"literal": session},
                "alignment": {
                    "literal": {
                        "kind": alignment_kind,
                        "maximum_skew_seconds": maximum_skew_seconds,
                    }
                },
                "derived_local": {"literal": False},
            }
        ],
    }
    registration = registered_v2_implementation(
        component=("phase4.leaf", 1),
        implementation=_implementation,
        dependency_boundary=DependencyBoundary("defining_module"),
    )
    registry = PlatformRegistry(
        components={},
        bodies={},
        registrations={},
        v2_types={},
        v2_components={("phase4.leaf", 1): component},
        v2_implementations={("phase4.leaf", 1): registration},
        data_requirement_declarations={("phase4.leaf", 1): declaration},
    )
    authored_strategy_id = strategy_id or requirement_id
    document = {
        "format_version": 2,
        "strategy_id": authored_strategy_id,
        "strategy_version": 1,
        "metadata": {
            "metadata_version": 1,
            "name": authored_strategy_id,
            "description": None,
            "tags": [],
        },
        "graph_inputs": [],
        "graph_outputs": [],
        "nodes": [
            {
                "node_id": "leaf",
                "component": {"component_id": "phase4.leaf", "component_version": 1},
                "parameters": {},
            }
        ],
        "edges": [],
    }
    plan = compile_data_requirement_plan(resolve_v2(document, registry))
    offer = {
        "instrument": {"role": "primary", "type": instrument_type},
        "field": field,
        "timeframes": [timeframe],
        "maximum_history_bars": 21,
        "maximum_freshness_seconds": 60,
        "depth": {
            "kind": offer_depth_kind or depth_kind,
            "levels": offer_depth_levels if offer_depth_kind is not None else depth_levels,
        },
        "session": session,
        "alignment": {"kind": alignment_kind, "maximum_skew_seconds": maximum_skew_seconds},
        "derived_local": False,
        "entitled": True,
        "known": True,
    }
    evidence = V2AdmissionEvidence(*(_address(character) for character in "1234567"))
    return registry, document, plan, evidence


def _persisted_scenario(tmp_path, *, registry, document, plan, instrument,
                        provider_token: str, provider_symbol: str, field: str,
                        timeframe: int, offer_depth_kind: str = "NONE",
                        offer_depth_levels: int | None = None,
                        supporting_instruments=(), venue_timezone="Asia/Kolkata",
                        additional_truth_records=(),
                        owner_id: str = "owner-a"):
    """Persist and reload the complete current authority chain for one scenario."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    execution, research = _engines(tmp_path)
    at_time = T0 + timedelta(hours=3)
    with Session(execution) as execution_session, Session(research) as research_session:
        values = _seed_execution(
            execution_session, owner_id=owner_id, instrument=instrument,
            supporting_instruments=tuple(supporting_instruments),
            additional_truth_records=tuple(additional_truth_records),
            provider_token=provider_token, provider_symbol=provider_symbol,
            field=field, timeframe=timeframe, offer_depth_kind=offer_depth_kind,
            offer_depth_levels=offer_depth_levels, venue_timezone=venue_timezone,
        )
        manifest, segments = _authority(values)
        persist_verified_dataset_authority(
            research_session, manifest=manifest, segments=segments,
            execution_session=execution_session, at_time=at_time,
        )
        assessment = assess_capability(
            plan=plan, profile=values["profile"], owner_id=owner_id, mode="RESEARCH",
            dataset_manifest_address=manifest.manifest_address,
            market_truth_snapshot_address=values["truth"].address,
            evaluation_policy_address=address(f"{provider_symbol}-evaluation-policy"),
            assessment_evidence_address=address(f"{provider_symbol}-assessment-evidence"),
            at_time=int(at_time.timestamp()), conformance=values["conformance"],
            provider_contract=values["contract"],
        )
        persist_capability_assessment(
            execution_session, assessment, plan=plan, at_time=at_time,
        )
        execution_session.commit()
        research_session.commit()
    return execution, research, manifest, assessment, values["truth"].address, at_time


def _admit(*, registry, document, plan, assessment, evidence, manifest_address,
           truth_address, execution_session, research_session, at_time,
           assessment_address: str | None = None, owner_id: str = "owner-a"):
    return admit_phase4_v2_strategy(
        owner_id=owner_id,
        mode="RESEARCH",
        document=document,
        registry=registry,
        evidence=evidence,
        plan=plan,
        assessment_address=assessment_address or assessment.authority_address,
        dataset_manifest_address=manifest_address,
        market_truth_snapshot_address=truth_address,
        evaluation_policy_address=assessment.evaluation_policy_address,
        execution_session=execution_session,
        research_session=research_session,
        at_time=at_time,
    )


def _cache_key(wrapper) -> str:
    binding = wrapper.phase4_data_binding
    return phase4_cache_identity(
        owner_id=binding["owner_id"],
        authored_ir_address=binding["authored_ir_address"],
        manifest_address=binding["dataset_manifest_address"],
        registry_snapshot_address=binding["registry_snapshot_address"],
        resolved_graph_address=binding["resolved_graph_address"],
        implementation_closure_address=binding["implementation_closure_address"],
        declaration_addresses=tuple(binding["declaration_addresses"]),
        plan_address=binding["plan_address"],
        capability_assessment_address=binding["capability_assessment_address"],
        market_truth_address=binding["market_truth_snapshot_address"],
        evaluation_policy_address=binding["evaluation_policy_address"],
        admission_address=wrapper.admission_address,
    )


def test_phase4_reusable_equities_separate_identity_session_manifest_and_cache(tmp_path):
    """One graph admits two exact equities without identity or cache reuse.

    This is local admission and persistence evidence only: no real provider feed,
    order placement, entry/exit runtime policy, production migration, or release
    rehearsal is exercised.
    """
    nse = _equity(venue="NSE", underlying="RELIANCE", currency="INR")
    nasdaq = _equity(venue="NASDAQ", underlying="AAPL", currency="USD")
    assert nse.address != nasdaq.address
    assert nse.contract_kind == nasdaq.contract_kind == "SPOT"
    assert nse.expiry is None and nse.strike is None and nse.multiplier is None

    nse_truth = _snapshot((_session_record(nse, calendar="NSE_EQUITY", timezone_name="Asia/Kolkata", state="OPEN"),))
    nasdaq_truth = _snapshot((
        _session_record(nasdaq, calendar="NASDAQ_EQUITY", timezone_name="America/New_York", state="OPEN"),
    ))
    assert nse_truth.record_at("session", (("instrument", nse.address),), ANCHOR + timedelta(hours=10)).terms[2] == (
        "timezone",
        "Asia/Kolkata",
    )
    assert nasdaq_truth.record_at("session", (("instrument", nasdaq.address),), ANCHOR + timedelta(hours=10)).terms[2] == (
        "timezone",
        "America/New_York",
    )
    nse_observation = _observation(
        nse,
        field="CLOSE",
        event_time=ANCHOR + timedelta(hours=10),
        market_truth_address=nse_truth.digest,
        numeric=valid(2_900.0),
    )
    nasdaq_observation = _observation(
        nasdaq,
        field="CLOSE",
        event_time=ANCHOR + timedelta(hours=10),
        market_truth_address=nasdaq_truth.digest,
        source_address=_address("b"),
        numeric=valid(190.0),
    )
    assert nse_observation.instrument != nasdaq_observation.instrument
    observation_policy = AlignmentPolicy(maximum_age_seconds=60, maximum_skew_seconds=60)
    assert align_observation(
        (nse_observation,),
        at=nse_observation.event_time + timedelta(seconds=20),
        policy=observation_policy,
    ) == nse_observation
    assert align_observation(
        (nasdaq_observation,),
        at=nasdaq_observation.event_time + timedelta(seconds=20),
        policy=observation_policy,
    ) == nasdaq_observation
    nse_manifest = content_address({
        "dataset": "equity-close",
        "instrument": nse.identity_payload(),
        "session_truth": nse_truth.digest,
        "observations": [nse_observation.value],
    })
    nasdaq_manifest = content_address({
        "dataset": "equity-close",
        "instrument": nasdaq.identity_payload(),
        "session_truth": nasdaq_truth.digest,
        "observations": [nasdaq_observation.value],
    })
    assert nse_manifest != nasdaq_manifest

    nse_registry, nse_document, nse_plan, nse_evidence = _scenario(
        requirement_id="equity_close",
        strategy_id="reusable_equity_graph",
        field="CLOSE",
        timeframe=60,
    )
    nasdaq_registry, nasdaq_document, nasdaq_plan, nasdaq_evidence = _scenario(
        requirement_id="equity_close",
        strategy_id="reusable_equity_graph",
        field="CLOSE",
        timeframe=60,
    )
    assert nse_document == nasdaq_document
    assert nse_plan.plan_address == nasdaq_plan.plan_address
    nse_execution, nse_research, nse_dataset, nse_assessment, nse_truth_address, nse_at = _persisted_scenario(
        tmp_path / "nse", registry=nse_registry, document=nse_document, plan=nse_plan,
        instrument=CanonicalPhysicalInstrument("strategy-os", "1", "XNSE", "EQUITY", "SPOT", "INR", None),
        provider_token="NSE-RELIANCE", provider_symbol="RELIANCE", field="CLOSE", timeframe=60,
    )
    nasdaq_execution, nasdaq_research, nasdaq_dataset, nasdaq_assessment, nasdaq_truth_address, nasdaq_at = _persisted_scenario(
        tmp_path / "nasdaq", registry=nasdaq_registry, document=nasdaq_document, plan=nasdaq_plan,
        instrument=CanonicalPhysicalInstrument("strategy-os", "1", "XNAS", "EQUITY", "SPOT", "USD", None),
        provider_token="NASDAQ-AAPL", provider_symbol="AAPL", field="CLOSE", timeframe=60,
        venue_timezone="America/New_York",
    )
    assert nse_dataset.instrument_addresses != nasdaq_dataset.instrument_addresses
    with Session(nse_execution) as execution_session, Session(nse_research) as research_session:
        nse_wrapper = _admit(
            registry=nse_registry, document=nse_document, plan=nse_plan, assessment=nse_assessment,
            evidence=nse_evidence, manifest_address=nse_dataset.manifest_address,
            truth_address=nse_truth_address, execution_session=execution_session,
            research_session=research_session, at_time=nse_at,
        )
    with Session(nasdaq_execution) as execution_session, Session(nasdaq_research) as research_session:
        nasdaq_wrapper = _admit(
            registry=nasdaq_registry, document=nasdaq_document, plan=nasdaq_plan, assessment=nasdaq_assessment,
            evidence=nasdaq_evidence, manifest_address=nasdaq_dataset.manifest_address,
            truth_address=nasdaq_truth_address, execution_session=execution_session,
            research_session=research_session, at_time=nasdaq_at,
        )
    assert nse_wrapper.phase4_data_binding["dataset_manifest_address"] != nasdaq_wrapper.phase4_data_binding["dataset_manifest_address"]
    assert nse_wrapper.phase4_data_binding["market_truth_snapshot_address"] != nasdaq_wrapper.phase4_data_binding["market_truth_snapshot_address"]
    assert _cache_key(nse_wrapper) != _cache_key(nasdaq_wrapper)

    execution, research = create_engine("sqlite:///:memory:"), create_engine("sqlite:///:memory:")
    Base.metadata.create_all(execution); ResearchBase.metadata.create_all(research)
    with Session(execution) as session:
        session.add(Organization(organization_id="owner-a", name="A"))
        session.commit()
        nse_bytes = put(session, nse_wrapper).artifact_json
        nasdaq_bytes = put(session, nasdaq_wrapper).artifact_json
    with Session(research) as session:
        nse_research_bytes = store_admission(session, nse_wrapper).artifact_json
        nasdaq_research_bytes = store_admission(session, nasdaq_wrapper).artifact_json
    assert nse_bytes == nse_research_bytes
    assert nasdaq_bytes == nasdaq_research_bytes
    assert nse_bytes != nasdaq_bytes


def test_phase4_weekly_option_contract_and_held_identity_refuse_missing_order_flow_truth(tmp_path):
    """Historical listed weekly contracts retain held identity and refuse OI/depth gaps.

    The listed contracts are supplied local rulebook facts; this test does not
    resolve a selector or claim a real provider feed, order placement, entry/exit
    runtime policy, production migration, or release rehearsal.
    """
    first_contract = _weekly_call(strike="22000")
    second_contract = _weekly_call(strike="22100")
    assert first_contract.address != second_contract.address
    assert first_contract.contract_kind == "WEEKLY_OPTION"
    assert first_contract.expiry == second_contract.expiry
    assert first_contract.option_right == "CALL"
    assert first_contract.multiplier == "50"

    listing_end = ANCHOR + timedelta(days=14)
    first_listing = RulebookRecord(
        record_kind="listed_contract",
        natural_key=(("contract", first_contract.address),),
        terms=(("multiplier", "50"), ("right", "CALL"), ("status", "LISTED"), ("strike", "22000")),
        effective_from=ANCHOR,
        effective_to=listing_end,
        recorded_at=ANCHOR + timedelta(hours=1),
    )
    second_listing = RulebookRecord(
        record_kind="listed_contract",
        natural_key=(("contract", second_contract.address),),
        terms=(("multiplier", "50"), ("right", "CALL"), ("status", "LISTED"), ("strike", "22100")),
        effective_from=ANCHOR,
        effective_to=listing_end,
        recorded_at=ANCHOR + timedelta(hours=1),
    )
    truth = _snapshot((first_listing, second_listing))
    as_of = ANCHOR + timedelta(days=2)
    assert truth.record_at("listed_contract", (("contract", first_contract.address),), as_of) == first_listing
    assert truth.record_at("listed_contract", (("contract", second_contract.address),), as_of) == second_listing

    initial_selector = InstrumentSelector("nearest_eligible_weekly_call", (("delta_band", "0.25"),))
    recentered_selector = InstrumentSelector("nearest_eligible_weekly_call", (("delta_band", "0.35"),))
    held_contract = preserve_held_identity(first_contract, recentered_selector)
    assert preserve_held_identity(held_contract, initial_selector) == first_contract
    assert held_contract.address == first_contract.address

    unavailable_oi = _observation(
        held_contract,
        field="OPEN_INTEREST",
        event_time=as_of,
        market_truth_address=truth.digest,
        numeric=invalid(ValidityState.PROVIDER_UNAVAILABLE),
    )
    assert unavailable_oi.validity is ValidityState.PROVIDER_UNAVAILABLE
    assert align_observation(
        (unavailable_oi,),
        at=as_of + timedelta(seconds=20),
        policy=AlignmentPolicy(maximum_age_seconds=60, maximum_skew_seconds=60),
    ) is None

    manifest = content_address({
        "dataset": "historical-weekly-option-order-flow",
        "listed_contracts": [first_contract.identity_payload(), second_contract.identity_payload()],
        "market_truth": truth.digest,
        "as_of": as_of.isoformat(),
    })
    registry, document, plan, evidence = _scenario(
        requirement_id="weekly_order_flow",
        field="OPEN_INTEREST",
        timeframe=300,
        instrument_type="PHYSICAL",
        depth_kind="BOOK",
        depth_levels=5,
        offer_depth_kind="BOOK",
        offer_depth_levels=1,
    )
    weekly_underlier = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "INDEX", "SPOT", "INR", None)
    weekly_contract = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "OPTION", "WEEKLY_OPTION", "INR",
        weekly_underlier.address, T0 + timedelta(days=7), "22000", "CALL", "50")
    persisted_listing = RulebookRecord(
        record_kind="listed_contract",
        natural_key=(("contract", weekly_contract.address),),
        terms=(
            ("expiry", weekly_contract.expiry.isoformat()),
            ("multiplier", weekly_contract.multiplier),
            ("option_right", weekly_contract.option_right),
            ("session", "regular"),
            ("status", "LISTED"),
            ("strike", weekly_contract.strike),
            ("underlier_address", weekly_underlier.address),
        ),
        effective_from=T0,
        effective_to=T0 + timedelta(days=1),
        recorded_at=T0 + timedelta(hours=1),
    )
    execution, research, dataset, assessment, truth_address, at_time = _persisted_scenario(
        tmp_path / "weekly", registry=registry, document=document, plan=plan,
        instrument=weekly_contract, supporting_instruments=(weekly_underlier,),
        additional_truth_records=(persisted_listing,),
        provider_token="NSE-NIFTY-22000CE", provider_symbol="NIFTY24AUG22000CE",
        field="OPEN_INTEREST", timeframe=300, offer_depth_kind="BOOK", offer_depth_levels=1,
    )
    assert dataset.instrument_addresses == (weekly_contract.address,)
    with Session(execution) as execution_session:
        reloaded_contract = load_canonical_instrument(execution_session, weekly_contract.address)
        reloaded_truth = load_market_truth_snapshot(execution_session, truth_address)
    assert reloaded_contract.canonical_bytes == weekly_contract.canonical_bytes
    assert reloaded_contract.economic_underlier_address == weekly_underlier.address
    assert reloaded_truth.instrument_addresses == tuple(sorted((
        weekly_contract.address, weekly_underlier.address,
    )))
    assert reloaded_truth.record_at(
        "listed_contract", (("contract", weekly_contract.address),), at_time,
    ) == persisted_listing
    result = assessment.requirement_results[0]
    assert result["result"] == "UNAVAILABLE"
    assert result["reason"] == "no single offer covers the complete requirement"
    with Session(execution) as execution_session, Session(research) as research_session:
        with pytest.raises(AdmissionRefused):
            _admit(
                registry=registry, document=document, plan=plan, assessment=assessment,
                evidence=evidence, manifest_address=dataset.manifest_address,
                truth_address=truth_address, execution_session=execution_session,
                research_session=research_session, at_time=at_time,
            )


def test_phase4_cross_market_completed_observations_refuse_age_skew_and_states():
    """UTC-normalized cross-market observations distinguish causal refusal states.

    Provider mappings and session facts are local declarations only.  No real
    provider feed, order placement, entry/exit runtime policy, production migration,
    or release rehearsal is claimed.
    """
    india = _equity(venue="NSE", underlying="RELIANCE", currency="INR")
    new_york = _equity(venue="NYSE", underlying="IBM", currency="USD")
    validate_provider_mappings((
        ProviderInstrumentMapping(india, "provider.nse", "NSE-RELIANCE", "adapter-1", ANCHOR, None),
        ProviderInstrumentMapping(new_york, "provider.nyse", "NYSE-IBM", "adapter-2", ANCHOR, None),
    ))

    closed_at = ANCHOR + timedelta(days=1)
    truth = _snapshot((
        _session_record(india, calendar="NSE_EQUITY", timezone_name="Asia/Kolkata", state="OPEN"),
        _session_record(new_york, calendar="NYSE_EQUITY", timezone_name="America/New_York", state="OPEN"),
        _session_record(
            new_york,
            calendar="NYSE_EQUITY",
            timezone_name="America/New_York",
            state="CLOSED",
            effective_from=closed_at,
            effective_to=closed_at + timedelta(hours=2),
            record_kind="market_state",
        ),
    ))
    assert truth.record_at("session", (("instrument", india.address),), ANCHOR + timedelta(hours=12)).terms[2] == ("timezone", "Asia/Kolkata")
    assert truth.record_at("session", (("instrument", new_york.address),), ANCHOR + timedelta(hours=12)).terms[2] == ("timezone", "America/New_York")
    assert truth.record_at("market_state", (("instrument", new_york.address),), closed_at + timedelta(minutes=1)).terms[1] == ("state", "CLOSED")

    at = datetime(2026, 1, 2, 15, 0, tzinfo=UTC)
    india_event = datetime(2026, 1, 2, 20, 29, 40, tzinfo=ZoneInfo("Asia/Kolkata"))
    new_york_event = datetime(2026, 1, 2, 9, 59, 45, tzinfo=ZoneInfo("America/New_York"))
    assert india_event.astimezone(UTC) == datetime(2026, 1, 2, 14, 59, 40, tzinfo=UTC)
    assert new_york_event.astimezone(UTC) == datetime(2026, 1, 2, 14, 59, 45, tzinfo=UTC)
    policy = AlignmentPolicy(maximum_age_seconds=60, maximum_skew_seconds=60)
    india_observation = _observation(
        india,
        field="CLOSE",
        event_time=india_event,
        market_truth_address=truth.digest,
        source_address=_address("c"),
        numeric=valid(2_900.0),
    )
    new_york_observation = _observation(
        new_york,
        field="CLOSE",
        event_time=new_york_event,
        market_truth_address=truth.digest,
        source_address=_address("d"),
        numeric=valid(190.0),
    )
    aligned = align_required_series(
        {"nse": (india_observation,), "nyse": (new_york_observation,)},
        at=at,
        policy=policy,
    )
    assert aligned is not None
    assert aligned["nse"].source_address == _address("c")
    assert aligned["nyse"].source_address == _address("d")

    stale = _observation(
        india,
        field="CLOSE",
        event_time=at - timedelta(seconds=61),
        market_truth_address=truth.digest,
        numeric=valid(2_899.0),
    )
    assert align_observation((stale,), at=at, policy=policy) is None
    skewed = _observation(
        new_york,
        field="CLOSE",
        event_time=at - timedelta(seconds=40),
        available_at=at - timedelta(seconds=30),
        completed_at=at - timedelta(seconds=30),
        market_truth_address=truth.digest,
        numeric=valid(191.0),
    )
    assert align_required_series({"nse": (india_observation,), "nyse": (skewed,)}, at=at, policy=AlignmentPolicy(60, 10)) is None
    forming = _observation(
        india,
        field="CLOSE",
        event_time=at + timedelta(seconds=1),
        available_at=at + timedelta(seconds=1),
        completed_at=at + timedelta(seconds=1),
        market_truth_address=truth.digest,
        numeric=valid(2_901.0),
    )
    assert align_observation((forming,), at=at, policy=policy) is None

    closed = _observation(
        new_york,
        field="CLOSE",
        event_time=closed_at,
        market_truth_address=truth.digest,
        numeric=invalid(ValidityState.NOT_IN_SESSION),
    )
    stale_state = _observation(
        india,
        field="CLOSE",
        event_time=at,
        market_truth_address=truth.digest,
        numeric=invalid(ValidityState.STALE),
    )
    unavailable = _observation(
        india,
        field="CLOSE",
        event_time=at,
        market_truth_address=truth.digest,
        numeric=invalid(ValidityState.PROVIDER_UNAVAILABLE),
    )
    missing = _observation(
        new_york,
        field="CLOSE",
        event_time=at,
        market_truth_address=truth.digest,
        numeric=invalid(ValidityState.MISSING),
    )
    states = (closed, stale_state, unavailable, missing)
    assert {row.validity for row in states} == {
        ValidityState.NOT_IN_SESSION,
        ValidityState.STALE,
        ValidityState.PROVIDER_UNAVAILABLE,
        ValidityState.MISSING,
    }
    for row in states:
        row_at = closed_at + timedelta(seconds=20) if row is closed else at
        assert align_observation((row,), at=row_at, policy=policy) is None


def test_phase4_refusal_chain_is_closed_for_missing_stale_mismatched_and_owner_inputs(tmp_path):
    """Every stale, missing, mismatched, or cross-owner fact reaches its loader."""
    registry, document, plan, evidence = _scenario(
        requirement_id="closed_refusal",
        field="CLOSE",
        timeframe=60,
    )
    execution, research, dataset, assessment, truth_address, at_time = _persisted_scenario(
        tmp_path / "refusal", registry=registry, document=document, plan=plan,
        instrument=CanonicalPhysicalInstrument("strategy-os", "1", "XNSE", "EQUITY", "SPOT", "INR", None),
        provider_token="NSE-RELIANCE", provider_symbol="RELIANCE", field="CLOSE", timeframe=60,
    )
    with Session(execution) as execution_session, Session(research) as research_session:
        common = dict(
            registry=registry, document=document, assessment=assessment, evidence=evidence,
            manifest_address=dataset.manifest_address, execution_session=execution_session,
            research_session=research_session,
        )
        cases = (
            ("mismatched-plan", replace(plan, plan_address=address("wrong-plan")), assessment.authority_address, truth_address, at_time, "owner-a"),
            ("missing-assessment", plan, address("missing-assessment"), truth_address, at_time, "owner-a"),
            ("mismatched-truth", plan, assessment.authority_address, address("wrong-truth"), at_time, "owner-a"),
            ("stale-profile", plan, assessment.authority_address, truth_address, T0 + timedelta(hours=13), "owner-a"),
            ("wrong-owner", plan, assessment.authority_address, truth_address, at_time, "owner-b"),
        )
        for _label, bad_plan, assessment_address, bad_truth, case_time, owner_id in cases:
            with pytest.raises(AdmissionRefused):
                _admit(
                    **common, plan=bad_plan, assessment_address=assessment_address,
                    truth_address=bad_truth, at_time=case_time, owner_id=owner_id,
                )
