from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.market_data.dataset_authority import (
    AdjustmentPolicy, AlignmentPolicy, DatasetCorrection, DatasetCreationEvidence,
    DeterministicAlgorithm, MissingDataPolicy, NormalizationTransform, RawSchema,
    RollPolicy, load_dataset_correction, persist_dataset_correction,
)
from tests.test_phase4_dataset_assessment_authority import T0, _seed_execution, address


def test_nine_closed_schemas_reconstruct_exact_canonical_bytes():
    algorithm = DeterministicAlgorithm(
        "owner-a", "algorithm", "1", address("implementation"), (address("vector"),), T0)
    facts = (
        algorithm,
        RawSchema("owner-a", address("product"), address("contract"), "raw/1",
                  (("close", "decimal"),), address("evidence"), T0),
        NormalizationTransform("owner-a", (address("schema"),), "normalized/1", (),
                               algorithm.address, T0),
        AlignmentPolicy("owner-a", "XNSE", "regular", "Asia/Kolkata", 60,
                        address("truth"), algorithm.address, T0),
        MissingDataPolicy("owner-a", "REFUSE", (), algorithm.address, T0),
        AdjustmentPolicy("owner-a", (address("instrument"),), (address("truth"),),
                         "NONE", algorithm.address, T0),
        RollPolicy("owner-a", (address("instrument"),), (address("truth"),),
                   "NONE", algorithm.address, T0, "NOT_APPLICABLE"),
        DatasetCreationEvidence("owner-a", "fixture", (address("source"),),
                                (address("artifact"),), algorithm.address, T0),
        DatasetCorrection("owner-a", address("product"), address("contract"), 0, None,
                          "initial", address("creation"), algorithm.address, T0),
    )
    assert {fact.SCHEMA for fact in facts} == {
        "raw-schema/1", "normalization-transform/1", "alignment-policy/1",
        "missing-data-policy/1", "adjustment-policy/1", "roll-policy/1",
        "dataset-correction/1", "dataset-creation-evidence/1",
        "deterministic-algorithm/1",
    }
    for fact in facts:
        reconstructed = type(fact).from_bytes(fact.canonical_bytes)
        assert reconstructed.canonical_bytes == fact.canonical_bytes
        assert reconstructed.address == fact.address


@pytest.mark.parametrize("handling", ["FILL", "FORWARD_FILL", "INTERPOLATE", "DROP"])
def test_missing_data_policy_refuses_implicit_or_synthetic_gap_handling(handling):
    with pytest.raises(ValueError, match="not closed"):
        MissingDataPolicy(
            "owner-a", handling, (), address("algorithm"), T0)
    with pytest.raises(ValueError, match="REFUSE cannot"):
        MissingDataPolicy(
            "owner-a", "REFUSE", ("unknown",), address("algorithm"), T0)


def test_correction_replay_is_idempotent_and_forks_cross_owner_refuse():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        values = _seed_execution(session)
        root = values["correction"]
        persist_dataset_correction(session, root)
        persist_dataset_correction(session, root)
        assert load_dataset_correction(session, root.address).canonical_bytes == root.canonical_bytes
        fork = DatasetCorrection(
            "owner-a", values["product"].address, values["contract"].address, 0, None,
            "competing root", values["creation"].address, values["algorithm"].address,
            T0 + dt.timedelta(hours=3, seconds=1))
        with pytest.raises(ValueError, match="fork"):
            persist_dataset_correction(session, fork)
        cross_owner = DatasetCorrection(
            "owner-b", values["product"].address, values["contract"].address, 0, None,
            "cross owner", values["creation"].address, values["algorithm"].address,
            T0 + dt.timedelta(hours=3, seconds=2))
        with pytest.raises(ValueError, match="cross authority"):
            persist_dataset_correction(session, cross_owner)


@pytest.mark.parametrize("count", [2480, 20000])
def test_creation_evidence_reconstructs_supported_csv_provenance(count):
    sources = tuple(sorted(address(f"observation-{index}") for index in range(count)))
    fact = DatasetCreationEvidence("owner-a", "strategy-os-user-csv/1", sources,
        (address("artifact"),), address("algorithm"), T0)
    assert DatasetCreationEvidence.from_bytes(fact.canonical_bytes).source_addresses == sources
    assert len(fact.canonical_bytes) < 2 * 1024 * 1024


def test_creation_source_bound_does_not_expand_other_fact_limits():
    from app.market_truth.identity import canonical_fact_bytes, MarketTruthError
    sources = tuple(sorted(address(f"observation-{index}") for index in range(20001)))
    with pytest.raises(ValueError, match="bounded immutable address tuple"):
        DatasetCreationEvidence("owner-a", "csv", sources, (address("artifact"),), address("algorithm"), T0)
    with pytest.raises(ValueError, match="bounded immutable address tuple"):
        DatasetCreationEvidence("owner-a", "csv", (address("source"),), sources[:1025], address("algorithm"), T0)
    with pytest.raises(MarketTruthError, match="persistence bound"):
        canonical_fact_bytes("unrelated-fact/1", {"sources": list(sources[:20000])})
    small = DatasetCreationEvidence("owner-a", "csv", (address("source"),), (address("artifact"),), address("algorithm"), T0)
    assert small.canonical_bytes == canonical_fact_bytes(small.SCHEMA, small.fact())
