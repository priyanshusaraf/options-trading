"""Cross-database contract for copied Phase 4 authority timestamps."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models import (
    AuthorityAdjustmentPolicy,
    AuthorityAlignmentPolicy,
    AuthorityCapabilityAssessment,
    AuthorityCapabilityProfile,
    AuthorityDatasetCorrection,
    AuthorityDatasetCreationEvidence,
    AuthorityDeterministicAlgorithm,
    AuthorityMarketTruthSnapshot,
    AuthorityMissingDataPolicy,
    AuthorityNormalizationTransform,
    AuthorityNormalizedObservation,
    AuthorityProviderAlias,
    AuthorityProviderConformance,
    AuthorityProviderContract,
    AuthorityProviderObservation,
    AuthorityRawSchema,
    AuthorityRollPolicy,
    Base,
)
from app.market_data.authority import (
    load_capability_assessment,
    load_capability_profile,
    load_provider_conformance,
    persist_capability_assessment,
)
from app.market_data.capability import assess_capability
from app.market_data.dataset_authority import (
    load_adjustment_policy,
    load_alignment_policy,
    load_dataset_correction,
    load_dataset_creation_evidence,
    load_deterministic_algorithm,
    load_missing_data_policy,
    load_normalization_transform,
    load_raw_schema,
    load_roll_policy,
)
from app.market_data.observations import (
    load_normalized_observation,
    load_provider_observation,
)
from app.market_truth.authority import load_market_truth_snapshot
from app.market_truth.identity import (
    ProviderContract,
    ProviderInstrumentAlias,
    load_provider_alias,
    load_provider_identity,
    persist_provider_alias,
)
from app.market_truth.temporal import require_sql_utc_naive, to_sql_utc_naive
from tests.test_phase4_dataset_assessment_authority import T0, _seed_execution, address
from tests.test_phase4_typed_market_authority import _plan


UTC = dt.timezone.utc
AT_TIME = T0 + dt.timedelta(hours=3)


def _fact_address(fact) -> str:
    for name in ("authority_address", "capability_profile_address", "address"):
        value = getattr(fact, name, None)
        if value is not None:
            return value
    raise AssertionError("authority fact has no content address")


def _loaders(plan):
    return {
        "provider_contract": lambda session, key: load_provider_identity(session, key)[2],
        "provider_alias": load_provider_alias,
        "truth_snapshot": load_market_truth_snapshot,
        "provider_conformance": load_provider_conformance,
        "capability_profile": lambda session, key: load_capability_profile(
            session, key, at_time=AT_TIME),
        "capability_assessment": lambda session, key: load_capability_assessment(
            session, key, plan=plan, at_time=AT_TIME),
        "provider_observation": load_provider_observation,
        "normalized_observation": load_normalized_observation,
        "deterministic_algorithm": load_deterministic_algorithm,
        "raw_schema": load_raw_schema,
        "normalization_transform": load_normalization_transform,
        "alignment_policy": load_alignment_policy,
        "missing_data_policy": load_missing_data_policy,
        "adjustment_policy": load_adjustment_policy,
        "roll_policy": load_roll_policy,
        "dataset_creation_evidence": load_dataset_creation_evidence,
        "dataset_correction": load_dataset_correction,
    }


def _specs(values, assessment):
    return (
        ("provider_contract", AuthorityProviderContract, values["contract"], "effective_from"),
        ("provider_alias", AuthorityProviderAlias, values["alias"], "effective_from"),
        ("truth_snapshot", AuthorityMarketTruthSnapshot, values["truth"], "knowledge_cutoff"),
        ("provider_conformance", AuthorityProviderConformance, values["conformance"], "observed_from"),
        ("capability_profile", AuthorityCapabilityProfile, values["profile"], "observed_at"),
        ("capability_assessment", AuthorityCapabilityAssessment, assessment, "assessed_at"),
        ("provider_observation", AuthorityProviderObservation, values["observation"], "event_time"),
        ("normalized_observation", AuthorityNormalizedObservation, values["normalized"], "event_time"),
        ("deterministic_algorithm", AuthorityDeterministicAlgorithm, values["algorithm"], "recorded_at"),
        ("raw_schema", AuthorityRawSchema, values["raw_schema"], "recorded_at"),
        ("normalization_transform", AuthorityNormalizationTransform, values["transform"], "recorded_at"),
        ("alignment_policy", AuthorityAlignmentPolicy, values["alignment"], "recorded_at"),
        ("missing_data_policy", AuthorityMissingDataPolicy, values["missing"], "recorded_at"),
        ("adjustment_policy", AuthorityAdjustmentPolicy, values["adjustment"], "recorded_at"),
        ("roll_policy", AuthorityRollPolicy, values["roll"], "recorded_at"),
        ("dataset_creation_evidence", AuthorityDatasetCreationEvidence, values["creation"], "recorded_at"),
        ("dataset_correction", AuthorityDatasetCorrection, values["correction"], "recorded_at"),
    )


def _seed_assessment(session: Session, values):
    plan = _plan()
    assessment = assess_capability(
        plan=plan,
        profile=values["profile"],
        owner_id="owner-a",
        mode="RESEARCH",
        dataset_manifest_address=address("timestamp-manifest"),
        market_truth_snapshot_address=values["truth"].address,
        evaluation_policy_address=address("timestamp-evaluation-policy"),
        assessment_evidence_address=address("timestamp-assessment-evidence"),
        at_time=int(AT_TIME.timestamp()), conformance=values["conformance"],
        provider_contract=values["contract"],
    )
    persist_capability_assessment(session, assessment, plan=plan, at_time=AT_TIME)
    session.flush()
    return plan, assessment


def _reload(url: str, addresses: dict[str, str]) -> dict[str, list[str]]:
    engine = sa.create_engine(url, future=True)
    plan = _plan()
    loaders = _loaders(plan)
    result = {}
    with Session(engine) as session:
        for label, key in addresses.items():
            fact = loaders[label](session, key)
            result[label] = [_fact_address(fact), fact.canonical_bytes.hex()]
    engine.dispose()
    return result


def _assert_offset_identity(values) -> None:
    positive = dt.datetime(2026, 8, 1, 5, 30,
        tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))
    negative = dt.datetime(2026, 7, 31, 20, 0,
        tzinfo=dt.timezone(-dt.timedelta(hours=4)))
    expected = dt.datetime(2026, 8, 1)
    assert to_sql_utc_naive(positive, "positive") == expected
    assert to_sql_utc_naive(negative, "negative") == expected
    assert require_sql_utc_naive(expected, "stored") == expected
    utc_contract = ProviderContract(
        "owner-a", values["product"].address, "RESEARCH", ("HISTORICAL",),
        T0, None, address("contract-evidence"))
    positive_contract = ProviderContract(
        "owner-a", values["product"].address, "RESEARCH", ("HISTORICAL",),
        positive, None, address("contract-evidence"))
    negative_contract = ProviderContract(
        "owner-a", values["product"].address, "RESEARCH", ("HISTORICAL",),
        negative, None, address("contract-evidence"))
    assert positive_contract.canonical_bytes == utc_contract.canonical_bytes
    assert negative_contract.address == utc_contract.address


def _assert_alias_overlap_uses_sql_representation(session: Session, values) -> None:
    overlapping = ProviderInstrumentAlias(
        values["product"].address,
        values["alias"].provider_token,
        "NIFTY-OVERLAP",
        values["instrument"].address,
        "2",
        dt.datetime(2026, 8, 1, 5, 31,
            tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30))),
        None,
        values["alias"].observation_namespace,
        address("overlap-evidence"),
    )
    with pytest.raises(ValueError, match="overlap"):
        persist_provider_alias(session, overlapping)


def test_database_neutral_authority_timestamp_lifecycle(tmp_path):
    postgres_url = os.environ.get("PT_TEST_POSTGRES_URL")
    url = postgres_url or f"sqlite:///{tmp_path / 'authority-timestamps.db'}"
    engine = sa.create_engine(url, future=True)
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        timezone_name = (connection.scalar(sa.text("SHOW TIMEZONE"))
            if postgres_url else "SQLite/UTC-naive contract")
    print(f"DATABASE_TIMEZONE={timezone_name}")
    if postgres_url:
        assert timezone_name == "Asia/Kolkata"

    with Session(engine) as session:
        values = _seed_execution(session)
        plan, assessment = _seed_assessment(session, values)
        _assert_offset_identity(values)
        _assert_alias_overlap_uses_sql_representation(session, values)
        loaders = _loaders(plan)
        specs = _specs(values, assessment)
        expected = {
            label: [_fact_address(fact), fact.canonical_bytes.hex()]
            for label, _model, fact, _column in specs
        }

        refusal_ledger = []
        for label, model, fact, column in specs:
            key = _fact_address(fact)
            row = session.get(model, key)
            original_time = getattr(row, column)
            with session.no_autoflush:
                setattr(row, column, original_time + dt.timedelta(hours=1))
                with pytest.raises(ValueError):
                    loaders[label](session, key)
                setattr(row, column, original_time)

                original_json = row.canonical_json
                document = json.loads(original_json)
                document["schema"] = "tampered-authority-document/1"
                row.canonical_json = json.dumps(document, sort_keys=True, separators=(",", ":"))
                with pytest.raises(ValueError):
                    loaders[label](session, key)
                row.canonical_json = original_json
            refusal_ledger.append({"family": label, "address": key,
                "copied_column": column, "copied_plus_one_hour": "REFUSED",
                "canonical_document": "REFUSED"})

        contract_row = session.get(AuthorityProviderContract, values["contract"].address)
        original = contract_row.effective_from
        with session.no_autoflush:
            contract_row.effective_from = original.replace(tzinfo=UTC)
            with pytest.raises(ValueError, match="UTC-naive"):
                load_provider_identity(session, values["contract"].address)
            contract_row.effective_from = original

        print("REFUSAL_LEDGER=" + json.dumps(refusal_ledger, sort_keys=True))
        session.commit()
    engine.dispose()

    addresses = {label: pair[0] for label, pair in expected.items()}
    program = (
        "import json,runpy,sys;"
        "m=runpy.run_path(sys.argv[1]);"
        "print(json.dumps(m['_reload'](sys.argv[2],json.loads(sys.argv[3])),sort_keys=True))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program, str(Path(__file__)), url,
            json.dumps(addresses, sort_keys=True)],
        check=True, capture_output=True, text=True,
    )
    reloaded = json.loads(completed.stdout.strip().splitlines()[-1])
    assert reloaded == expected
    print("FRESH_PROCESS=PASS")
    print("PARITY_JSON=" + json.dumps(reloaded, sort_keys=True))
