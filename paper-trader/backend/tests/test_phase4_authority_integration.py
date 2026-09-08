"""Evidence-only integration checks for the complete Phase 4 authority chain.

The focused correction tests remain the owners of individual constructors and
loaders.  This file crosses the real execution and research persistence planes,
then starts a new interpreter which has only the databases and canonical source
needed to reconstruct the registry.  No loader, database seam, or terminal
consumer is replaced.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.strategy_admissions import put
from app.backtest.cache import phase4_cache_identity
from app.ir.hashing import content_address
from app.ir.validity import ValidityState, invalid, valid
from app.db.models import Base
from app.market_data.authority import persist_capability_assessment
from app.market_data.capability import assess_capability
from app.market_data.observations import AlignmentPolicy, align_observation
from app.market_truth.identity import (
    CanonicalPhysicalInstrument,
    InstrumentSelector,
    preserve_held_identity,
)
from app.market_truth.rulebook import RulebookRecord
from app.strategy.admission import admit_phase4_v2_strategy
from research.domain.admissions import (
    AdmissionPersistenceError as ResearchAdmissionPersistenceError,
    load_admission as load_research_admission,
    store_admission,
)
from research.domain.base import ResearchBase
from research.domain.models import ResearchIrV2GraphVersion, ResearchStrategyAdmission
from research.domain.migrate import migrate_research_db
from research.domain.strategy_admissions import persist_verified_dataset_authority
from tests.test_phase4_capability_admission import _evidence, _plan
from tests.test_phase4_dataset_assessment_authority import (
    T0,
    _authority,
    _engines,
    _seed_execution,
    address,
)
from tests.test_phase4_acceptance_scenarios import (
    ANCHOR,
    _address,
    _equity,
    _observation,
    _persisted_scenario,
    _scenario,
    _session_record,
    _snapshot,
    _weekly_call,
)
from tests.test_phase4_v2_graph_persistence import _phase4_fixture


def _scenario_cache_identity(*, plan, assessment, admission_label: str) -> str:
    return phase4_cache_identity(
        owner_id=assessment.owner_id,
        authored_ir_address=plan.authored_ir_address,
        manifest_address=assessment.dataset_manifest_address,
        registry_snapshot_address=plan.registry_snapshot_address,
        resolved_graph_address=plan.resolved_graph_address,
        implementation_closure_address=plan.implementation_closure_address,
        declaration_addresses=plan.declaration_addresses,
        plan_address=plan.plan_address,
        capability_assessment_address=assessment.authority_address,
        market_truth_address=assessment.market_truth_snapshot_address,
        evaluation_policy_address=assessment.evaluation_policy_address,
        admission_address=address(admission_label),
    )


def test_current_reusable_equity_scenario_keeps_identity_truth_manifest_and_cache_separate(tmp_path: Path):
    """Recheck the reusable graph scenario without the retired admission interface."""
    nse = _equity(venue="NSE", underlying="RELIANCE", currency="INR")
    nasdaq = _equity(venue="NASDAQ", underlying="AAPL", currency="USD")
    assert nse.address != nasdaq.address
    nse_truth = _snapshot((
        _session_record(nse, calendar="NSE_EQUITY", timezone_name="Asia/Kolkata", state="OPEN"),
    ))
    nasdaq_truth = _snapshot((
        _session_record(nasdaq, calendar="NASDAQ_EQUITY", timezone_name="America/New_York", state="OPEN"),
    ))
    at = ANCHOR + timedelta(hours=10)
    nse_observation = _observation(
        nse, field="CLOSE", event_time=at,
        market_truth_address=nse_truth.digest, numeric=valid(2_900.0),
    )
    nasdaq_observation = _observation(
        nasdaq, field="CLOSE", event_time=at,
        market_truth_address=nasdaq_truth.digest,
        source_address=_address("b"), numeric=valid(190.0),
    )
    policy = AlignmentPolicy(maximum_age_seconds=60, maximum_skew_seconds=60)
    assert align_observation((nse_observation,), at=at + timedelta(seconds=20), policy=policy) == nse_observation
    assert align_observation((nasdaq_observation,), at=at + timedelta(seconds=20), policy=policy) == nasdaq_observation
    nse_manifest = content_address({
        "dataset": "equity-close", "instrument": nse.identity_payload(),
        "session_truth": nse_truth.digest, "observations": [nse_observation.value],
    })
    nasdaq_manifest = content_address({
        "dataset": "equity-close", "instrument": nasdaq.identity_payload(),
        "session_truth": nasdaq_truth.digest, "observations": [nasdaq_observation.value],
    })
    assert nse_manifest != nasdaq_manifest
    nse_registry, nse_document, nse_plan, _nse_evidence = _scenario(
        requirement_id="equity_close", strategy_id="reusable_equity_graph",
        field="CLOSE", timeframe=60,
    )
    nasdaq_registry, nasdaq_document, nasdaq_plan, _nasdaq_evidence = _scenario(
        requirement_id="equity_close", strategy_id="reusable_equity_graph",
        field="CLOSE", timeframe=60,
    )
    assert nse_document == nasdaq_document
    assert nse_plan.plan_address == nasdaq_plan.plan_address
    _, _, _, nse_assessment, _, _ = _persisted_scenario(
        tmp_path / "nse", registry=nse_registry, document=nse_document, plan=nse_plan,
        instrument=CanonicalPhysicalInstrument(
            "strategy-os", "1", "XNSE", "EQUITY", "SPOT", "INR", None,
        ),
        provider_token="NSE-RELIANCE", provider_symbol="RELIANCE",
        field="CLOSE", timeframe=60,
    )
    _, _, _, nasdaq_assessment, _, _ = _persisted_scenario(
        tmp_path / "nasdaq", registry=nasdaq_registry, document=nasdaq_document,
        plan=nasdaq_plan,
        instrument=CanonicalPhysicalInstrument(
            "strategy-os", "1", "XNAS", "EQUITY", "SPOT", "USD", None,
        ),
        provider_token="NASDAQ-AAPL", provider_symbol="AAPL",
        field="CLOSE", timeframe=60, venue_timezone="America/New_York",
    )
    assert nse_assessment.authority_address != nasdaq_assessment.authority_address
    assert _scenario_cache_identity(
        plan=nse_plan, assessment=nse_assessment, admission_label="equity-admission",
    ) != _scenario_cache_identity(
        plan=nasdaq_plan, assessment=nasdaq_assessment, admission_label="equity-admission",
    )


def test_current_weekly_option_scenario_keeps_held_contract_and_refuses_incomplete_order_flow(tmp_path: Path):
    """Recheck listed weekly identity and incomplete order-flow authority."""
    first = _weekly_call(strike="22000")
    second = _weekly_call(strike="22100")
    assert first.address != second.address
    listing_end = ANCHOR + timedelta(days=14)
    listings = tuple(
        RulebookRecord(
            record_kind="listed_contract",
            natural_key=(("contract", contract.address),),
            terms=(("multiplier", "50"), ("right", "CALL"), ("status", "LISTED"), ("strike", strike)),
            effective_from=ANCHOR, effective_to=listing_end,
            recorded_at=ANCHOR + timedelta(hours=1),
        )
        for contract, strike in ((first, "22000"), (second, "22100"))
    )
    truth = _snapshot(listings)
    as_of = ANCHOR + timedelta(days=2)
    held = preserve_held_identity(
        first, InstrumentSelector("nearest_eligible_weekly_call", (("delta_band", "0.35"),)),
    )
    assert held.address == first.address
    unavailable_oi = _observation(
        held, field="OPEN_INTEREST", event_time=as_of,
        market_truth_address=truth.digest,
        numeric=invalid(ValidityState.PROVIDER_UNAVAILABLE),
    )
    assert align_observation(
        (unavailable_oi,), at=as_of + timedelta(seconds=20),
        policy=AlignmentPolicy(maximum_age_seconds=60, maximum_skew_seconds=60),
    ) is None
    manifest = content_address({
        "dataset": "historical-weekly-option-order-flow",
        "listed_contracts": [first.identity_payload(), second.identity_payload()],
        "market_truth": truth.digest, "as_of": as_of.isoformat(),
    })
    registry, document, plan, _evidence_value = _scenario(
        requirement_id="weekly_order_flow", field="OPEN_INTEREST", timeframe=300,
        instrument_type="PHYSICAL", depth_kind="BOOK", depth_levels=5,
        offer_depth_kind="BOOK", offer_depth_levels=1,
    )
    weekly_underlier = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "INDEX", "SPOT", "INR", None,
    )
    weekly_contract = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "OPTION", "WEEKLY_OPTION", "INR",
        weekly_underlier.address, T0 + timedelta(days=7), "22000", "CALL", "50",
    )
    _, _, _, assessment, _, _ = _persisted_scenario(
        tmp_path / "weekly", registry=registry, document=document, plan=plan,
        instrument=weekly_contract, supporting_instruments=(weekly_underlier,),
        provider_token="NSE-NIFTY-22000CE", provider_symbol="NIFTY24AUG22000CE",
        field="OPEN_INTEREST", timeframe=300,
        offer_depth_kind="BOOK", offer_depth_levels=1,
    )
    assert assessment.requirement_results == ({
        "selector": assessment.requirement_results[0]["selector"],
        "result": "UNAVAILABLE",
        "reason": "no single offer covers the complete requirement",
    },)


def test_current_research_retry_collision_and_owner_local_loader_isolation():
    """Cover ADV-004 through the current fixture and public research seams."""
    _registry, wrapper = _phase4_fixture()
    _variant_registry, variant = _phase4_fixture(name="different-bytes")
    engine = create_engine("sqlite:///:memory:", future=True)
    ResearchBase.metadata.create_all(engine)
    with Session(engine) as session:
        first = store_admission(session, wrapper)
        retry = store_admission(session, wrapper)
        assert retry.artifact_json == first.artifact_json
        session.commit()
        assert load_research_admission(
            session, owner_id="owner-a", admission_address=wrapper.admission_address,
        ) is not None
        assert load_research_admission(
            session, owner_id="owner-b", admission_address=wrapper.admission_address,
        ) is None
        with pytest.raises(ResearchAdmissionPersistenceError, match="v2 graph version"):
            store_admission(session, variant)
        session.rollback()
        assert session.scalar(select(func.count()).select_from(ResearchIrV2GraphVersion)) == 1
        assert session.scalar(select(func.count()).select_from(ResearchStrategyAdmission)) == 1


def test_cur_h3_h4_forbidden_consumers_have_no_phase4_authority_entrypoint():
    """Keep Phase 4 receipts outside paper/live and generated-version consumers."""
    backend = Path(__file__).resolve().parents[1]
    forbidden_consumers = (
        "app/core/deploy_bridge.py",
        "app/core/deployments.py",
        "app/core/paper_authority.py",
        "app/core/shadow_deployments.py",
        "app/engine/runner.py",
        "app/engine/live_broker.py",
        "research/orchestrator/generate.py",
        "research/orchestrator/run.py",
        "app/core/generated_strategies.py",
        "app/core/research_read.py",
    )
    phase4_entrypoints = (
        "PHASE4_SCHEME",
        "strategy-admission/phase4-data/1",
        "admit_phase4_v2_strategy",
        "reconstruct_phase4_artifact",
        "require_phase4_current",
    )
    observed = {}
    for relative in forbidden_consumers:
        source = (backend / relative).read_text(encoding="utf-8")
        observed[relative] = [token for token in phase4_entrypoints if token in source]
    assert observed == {relative: [] for relative in forbidden_consumers}


def test_real_two_plane_process_death_reconstruction_and_terminal_refusal(
    tmp_path: Path, request: pytest.FixtureRequest,
):
    """Create, admit, persist, die, reconstruct, verify, and refuse at runtime."""
    postgres_url = os.environ.get("PT_TEST_POSTGRES_URL")
    if postgres_url:
        from tests.postgres_sandbox import PostgresSandbox

        # Shared sandbox contract: private, verified-empty, uniquely named
        # databases per target. No fixed names are created or force-dropped;
        # the sandbox owns creation and cleanup (via finalizer, which runs on
        # assertion and setup failures alike).
        sandbox = PostgresSandbox(postgres_url)
        request.addfinalizer(sandbox.close)
        execution = create_engine(sandbox.execution_url)
        request.addfinalizer(execution.dispose)
        Base.metadata.create_all(execution)
        research_url = sandbox.research_url
        isolated_research_url = sandbox.url("research_invalid")
        research = create_engine(research_url)
        migrate_research_db(research)
        isolated_research = create_engine(isolated_research_url)
        migrate_research_db(isolated_research)
        isolated_research.dispose()
        execution_url = sandbox.execution_url
    else:
        execution, research = _engines(tmp_path)
        execution_url = f"sqlite:///{tmp_path / 'execution.db'}"
        research_url = f"sqlite:///{tmp_path / 'research.db'}"
        isolated_research_url = "sqlite:///:memory:"
    registry, document, plan = _plan()
    at_time = T0 + dt.timedelta(hours=3)
    with Session(execution) as execution_session, Session(research) as research_session:
        values = _seed_execution(execution_session)
        manifest, segments = _authority(values)
        persist_verified_dataset_authority(
            research_session,
            manifest=manifest,
            segments=segments,
            execution_session=execution_session,
            at_time=at_time,
        )
        assessment = assess_capability(
            plan=plan,
            profile=values["profile"],
            owner_id="owner-a",
            mode="RESEARCH",
            dataset_manifest_address=manifest.manifest_address,
            market_truth_snapshot_address=values["truth"].address,
            evaluation_policy_address=address("evaluation-policy"),
            assessment_evidence_address=address("assessment-evidence"),
            at_time=int(at_time.timestamp()), conformance=values["conformance"],
            provider_contract=values["contract"],
        )
        persist_capability_assessment(
            execution_session, assessment, plan=plan, at_time=at_time
        )
        wrapper = admit_phase4_v2_strategy(
            owner_id="owner-a",
            mode="RESEARCH",
            document=document,
            registry=registry,
            evidence=_evidence(),
            plan=plan,
            assessment_address=assessment.authority_address,
            dataset_manifest_address=manifest.manifest_address,
            market_truth_snapshot_address=values["truth"].address,
            evaluation_policy_address=assessment.evaluation_policy_address,
            research_session=research_session,
            execution_session=execution_session,
            at_time=at_time,
        )
        execution_receipt = put(execution_session, wrapper)
        research_receipt = store_admission(research_session, wrapper)
        execution_session.commit()
        research_session.commit()
        assert execution_receipt.artifact_json == research_receipt.artifact_json
        expected = {
            "admission_address": wrapper.admission_address,
            "assessment_address": assessment.authority_address,
            "assessment_bytes": assessment.canonical_bytes.decode(),
            "manifest_address": manifest.manifest_address,
            "manifest_bytes": manifest.canonical_bytes.decode(),
            "owner": assessment.owner_id,
            "mode": assessment.mode,
            "product": values["product"].address,
            "contract": values["contract"].address,
            "truth": values["truth"].address,
            "policy": assessment.evaluation_policy_address,
            "artifact_json": execution_receipt.artifact_json,
            "graph_address": wrapper.graph_address,
            "dependency_addresses": sorted({
                values["instrument"].address, values["entity"].address,
                values["product"].address, values["contract"].address,
                values["observation"].address, values["normalized"].address,
                values["raw_schema"].address, values["transform"].address,
                values["truth"].address, values["creation"].address,
                values["profile"].capability_profile_address,
                values["alignment"].address, values["missing"].address,
                values["adjustment"].address, values["roll"].address,
                values["algorithm"].address, values["correction"].address,
                *manifest.segment_addresses,
            }),
        }
    execution.dispose()
    research.dispose()

    expected_path = tmp_path / "expected.json"
    expected_path.write_text(json.dumps(expected), encoding="utf-8")
    backend_dir = Path(__file__).resolve().parents[1]
    program = r'''
import datetime as dt
import json
import sys
from dataclasses import replace
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtest.cache import verified_phase4_cache_identity
from app.backtest.reclaim_authority import ReclaimAuthorityContext
from app.backtest.repository import AdmissionRequired, load_verified_admission
import research.domain.strategy_admissions as research_strategy_admissions
from app.db.models import IrV2GraphVersion, StrategyAdmission
from app.ir.hashing import content_address
from app.strategy.admission import reconstruct_phase4_artifact
from app.ir.v2_graph_versions import (
    V2GraphVerificationError, V2_RUNTIME_UNAVAILABLE,

)
from app.market_data.authority import load_capability_assessment
from research.domain.admissions import require_admission
from research.domain.base import ResearchBase
from research.domain.models import ResearchIrV2GraphVersion, ResearchStrategyAdmission
from research.domain.strategy_admissions import load_verified_dataset_authority
from tests.test_phase4_capability_admission import _plan

expected = json.load(open(sys.argv[3], encoding="utf-8"))
execution = sa.create_engine(sys.argv[1], future=True)
research = sa.create_engine(sys.argv[2], future=True)
isolated_research_url = sys.argv[4]
registry, _document, plan = _plan()
at_time = dt.datetime.fromisoformat("2026-08-01T03:00:00+00:00")
with Session(execution) as execution_session, Session(research) as research_session:
    authority_context = ReclaimAuthorityContext(
        registry=registry, research_sessionmaker=lambda: Session(research))
    # This direct loader case is deliberately before the complete-current call.
    # If the research verifier moved below dataset authority, the tripwire would
    # fail instead of the stable public receipt refusal.
    original_dataset_loader = research_strategy_admissions.load_verified_dataset_authority
    def dataset_must_not_run(*_args, **_kwargs):
        raise AssertionError("invalid research authority reached dataset authority")

    research_receipt = research_session.scalar(select(ResearchStrategyAdmission).where(
        ResearchStrategyAdmission.owner_id == expected["owner"],
        ResearchStrategyAdmission.admission_address == expected["admission_address"]))
    research_graph = research_session.get(
        ResearchIrV2GraphVersion, (expected["owner"], "phase4", 1))
    assert research_receipt is not None and research_graph is not None

    def seed_receipt(target, *, artifact_json=None, owner_id=None, graph_address=None):
        target.execute(sa.text("""
            INSERT INTO research_strategy_admission (
                owner_id, admission_address, graph_identifier, graph_version,
                graph_address, artifact_json, scheme, contract_suite, parity_suite,
                format_version, content_address, created_at
            ) VALUES (
                :owner_id, :admission_address, :graph_identifier, :graph_version,
                :graph_address, :artifact_json, :scheme, :contract_suite, :parity_suite,
                :format_version, :content_address, :created_at
            )
        """), {
            "owner_id": owner_id if owner_id is not None else research_receipt.owner_id,
            "admission_address": research_receipt.admission_address,
            "graph_identifier": research_receipt.graph_identifier,
            "graph_version": research_receipt.graph_version,
            "graph_address": graph_address if graph_address is not None else research_receipt.graph_address,
            "artifact_json": artifact_json if artifact_json is not None else research_receipt.artifact_json,
            "scheme": research_receipt.scheme,
            "contract_suite": research_receipt.contract_suite,
            "parity_suite": research_receipt.parity_suite,
            "format_version": research_receipt.format_version,
            "content_address": research_receipt.content_address,
            "created_at": research_receipt.created_at,
        })

    def seed_graph(target, *, artifact_json=None):
        target.execute(sa.text("""
            INSERT INTO research_ir_v2_graph_versions (
                owner_id, graph_identifier, graph_version, artifact_json,
                format_version, content_address, graph_address,
                registry_snapshot_address, created_at
            ) VALUES (
                :owner_id, :graph_identifier, :graph_version, :artifact_json,
                :format_version, :content_address, :graph_address,
                :registry_snapshot_address, :created_at
            )
        """), {
            "owner_id": research_graph.owner_id,
            "graph_identifier": research_graph.graph_identifier,
            "graph_version": research_graph.graph_version,
            "artifact_json": artifact_json if artifact_json is not None else research_graph.artifact_json,
            "format_version": research_graph.format_version,
            "content_address": research_graph.content_address,
            "graph_address": research_graph.graph_address,
            "registry_snapshot_address": research_graph.registry_snapshot_address,
            "created_at": research_graph.created_at,
        })

    def direct_refusal(label, seed):
        isolated = sa.create_engine(isolated_research_url, future=True)
        ResearchBase.metadata.drop_all(isolated)
        with isolated.begin() as connection:
            connection.exec_driver_sql("DROP TABLE IF EXISTS research_schema_version")
        ResearchBase.metadata.create_all(isolated)
        try:
            with Session(isolated) as isolated_session:
                seed(isolated_session)
                isolated_session.commit()
                isolated_context = ReclaimAuthorityContext(
                    registry=registry, research_sessionmaker=lambda: Session(isolated))
                research_strategy_admissions.load_verified_dataset_authority = dataset_must_not_run
                try:
                    load_verified_admission(
                        execution_session, owner_id=expected["owner"],
                        admission_address=expected["admission_address"],
                        authority_context=isolated_context, research_session=isolated_session,
                        at_time=at_time)
                except AdmissionRequired as exc:
                    assert exc.code == "RECEIPT_STALE", label
                else:
                    raise AssertionError(label + " reached a terminal outcome")
        finally:
            research_strategy_admissions.load_verified_dataset_authority = original_dataset_loader
            isolated.dispose()

    try:
        direct_refusal("missing research receipt", lambda _target: None)
        direct_refusal("missing research graph", seed_receipt)
        direct_refusal("tampered research receipt bytes", lambda target: seed_receipt(
            target, artifact_json=research_receipt.artifact_json + " "))
        direct_refusal("tampered research receipt copied column", lambda target: seed_receipt(
            target, artifact_json=research_receipt.artifact_json.replace(
                research_receipt.graph_address, "sha256:" + "f" * 64),
            graph_address="sha256:" + "f" * 64))
        direct_refusal("tampered research graph bytes", lambda target: (
            seed_receipt(target), seed_graph(target, artifact_json=research_graph.artifact_json + " ")))
        direct_refusal("wrong-owner cross-plane research substitution", lambda target: seed_receipt(
            target,
            artifact_json=research_receipt.artifact_json.replace(
                '"owner-a"', '"owner-b"'), owner_id="owner-b"))
    finally:
        research_strategy_admissions.load_verified_dataset_authority = original_dataset_loader
    # The production boundary runs before any diagnostic loader in this fresh
    # interpreter.  Its terminal refusal therefore proves it reconstructed the
    # persisted research and execution authority chain itself.
    try:
        load_verified_admission(
            execution_session, owner_id=expected["owner"],
            admission_address=expected["admission_address"],
            authority_context=authority_context, research_session=research_session,
            at_time=at_time)
    except AdmissionRequired as exc:
        assert exc.code == V2_RUNTIME_UNAVAILABLE
        refusal = exc.code
    else:
        raise AssertionError("verified Phase 4 v2 authority reached a runtime consumer")

    dataset = load_verified_dataset_authority(
        research_session, owner_id=expected["owner"],
        manifest_address=expected["manifest_address"],
        execution_session=execution_session, at_time=at_time)
    assessment = load_capability_assessment(
        execution_session, expected["assessment_address"], plan=plan, at_time=at_time)
    execution_receipt = execution_session.scalar(select(StrategyAdmission).where(
        StrategyAdmission.owner_id == expected["owner"],
        StrategyAdmission.admission_address == expected["admission_address"]))
    research_receipt = research_session.scalar(select(ResearchStrategyAdmission).where(
        ResearchStrategyAdmission.owner_id == expected["owner"],
        ResearchStrategyAdmission.admission_address == expected["admission_address"]))
    execution_graph = execution_session.get(
        IrV2GraphVersion, (expected["owner"], "phase4", 1))
    research_graph = research_session.get(
        ResearchIrV2GraphVersion, (expected["owner"], "phase4", 1))
    assert execution_receipt is not None and research_receipt is not None
    assert execution_graph is not None and research_graph is not None
    assert execution_receipt.artifact_json == expected["artifact_json"]
    assert research_receipt.artifact_json == expected["artifact_json"]
    assert execution_graph.artifact_json == research_graph.artifact_json
    assert dataset.manifest.canonical_bytes.decode() == expected["manifest_bytes"]
    assert assessment.canonical_bytes.decode() == expected["assessment_bytes"]
    assert assessment.owner_id == expected["owner"]
    assert assessment.mode == expected["mode"]
    assert assessment.dataset_manifest_address == expected["manifest_address"]
    assert assessment.market_truth_snapshot_address == expected["truth"]
    assert expected["product"] in dataset.manifest.provider_product_addresses
    assert expected["contract"] in dataset.manifest.provider_contract_addresses
    manifest_fact = dataset.manifest.fact()
    assert "capability_assessment_address" not in manifest_fact
    dependency_addresses = sorted({
        item for key, value in manifest_fact.items()
        if key.endswith("_address") or key.endswith("_addresses")
        for item in (value if isinstance(value, list) else [value])
        if isinstance(item, str) and item.startswith("sha256:")
    })
    assert dependency_addresses == expected["dependency_addresses"]
    manifest_recorded_at = dt.datetime.fromisoformat(dataset.manifest.recorded_at)
    assessment_at = dt.datetime.fromtimestamp(assessment.assessed_at, dt.timezone.utc)
    assert manifest_recorded_at <= assessment_at

    receipt_document = json.loads(research_receipt.artifact_json)
    try:
        artifact = reconstruct_phase4_artifact(
            receipt_document, owner_id=expected["owner"], registry=registry)
    except V2GraphVerificationError:
        print(json.dumps({
            "binding_assessment_address": receipt_document[
                "phase4_data_binding"
            ]["capability_assessment_address"],
            "embedded_assessment_address_used_by_reconstruction": content_address(
                receipt_document["capability_assessment"]
            ),
            "embedded_assessment_keys": sorted(
                receipt_document["capability_assessment"]
            ),
            "loaded_typed_authority_address": assessment.authority_address,
            "loaded_typed_fact_keys": sorted(assessment.fact()),
        }, sort_keys=True), file=sys.stderr)
        raise
    require_admission(research_session, artifact)
    cache_kwargs = dict(
        research_session=research_session, execution_session=execution_session,
        owner_id=expected["owner"], authored_ir_address=plan.authored_ir_address,
        manifest_address=expected["manifest_address"],
        registry_snapshot_address=plan.registry_snapshot_address,
        resolved_graph_address=plan.resolved_graph_address,
        implementation_closure_address=plan.implementation_closure_address,
        declaration_addresses=plan.declaration_addresses, plan_address=plan.plan_address,
        capability_assessment_address=expected["assessment_address"],
        market_truth_address=expected["truth"],
        evaluation_policy_address=expected["policy"],
        admission_address=expected["admission_address"], plan=plan, at_time=at_time)
    cold = verified_phase4_cache_identity(**cache_kwargs)
    warm = verified_phase4_cache_identity(**cache_kwargs)
    assert cold == warm
print(json.dumps({
    "admission_address": expected["admission_address"],
    "assessment_address": assessment.authority_address,
    "manifest_address": dataset.manifest.manifest_address,
    "graph_address": expected["graph_address"],
    "owner": assessment.owner_id,
    "mode": assessment.mode,
    "product": expected["product"],
    "contract": expected["contract"],
    "cache_address": cold,
    "terminal_refusal": refusal,
    "manifest_before_assessment": manifest_recorded_at <= assessment_at,
    "dependency_count": len(dependency_addresses),
}, sort_keys=True))
'''
    environment = os.environ.copy()
    python_path = [str(backend_dir), str(backend_dir / "tests")]
    if environment.get("PYTHONPATH"):
        python_path.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_path)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            program,
            execution_url,
            research_url,
            str(expected_path),
            isolated_research_url,
        ],
        cwd=backend_dir,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    assert observed == {
        "admission_address": expected["admission_address"],
        "assessment_address": expected["assessment_address"],
        "cache_address": observed["cache_address"],
        "contract": expected["contract"],
        "manifest_address": expected["manifest_address"],
        "graph_address": expected["graph_address"],
        "manifest_before_assessment": True,
        "mode": expected["mode"],
        "owner": expected["owner"],
        "product": expected["product"],
        "terminal_refusal": "V2_RUNTIME_UNAVAILABLE",
        "dependency_count": len(expected["dependency_addresses"]),
    }
    assert len(observed["cache_address"]) == 64
    print(json.dumps({"integration_observation": observed}, sort_keys=True))
