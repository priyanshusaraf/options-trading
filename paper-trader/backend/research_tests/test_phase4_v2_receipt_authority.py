"""Research-plane authority and restart regressions for Phase 4 v2 receipts."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.ir.hashing import canonical_json, content_address
from app.ir.v2_graph_versions import (
    PersistedPhase4Artifact,
    V2GraphVerificationError,
)
from app.strategy.admission import reconstruct_phase4_artifact
from research.domain.admissions import (
    AdmissionPersistenceError,
    store_admission,
)
from research.domain.base import ResearchBase
from tests.test_phase4_capability_admission import _phase4_fixture


def _raw_receipt(wrapper):
    """Model a fresh process receiving only canonical persisted JSON."""
    return json.loads(canonical_json(wrapper.to_dict()))


def _research_session():
    engine = create_engine("sqlite:///:memory:")
    ResearchBase.metadata.create_all(engine)
    return engine


def test_reconstructed_receipt_is_research_evidence_not_new_write_authority():
    registry, _document, _plan, _assessment, wrapper = _phase4_fixture()
    raw_receipt = _raw_receipt(wrapper)
    reconstructed = reconstruct_phase4_artifact(
        raw_receipt, owner_id="owner-a", registry=registry
    )

    assert type(reconstructed) is PersistedPhase4Artifact
    assert reconstructed.to_dict() == raw_receipt
    assert reconstructed.admission_address == content_address(raw_receipt)

    with Session(_research_session()) as session:
        with pytest.raises(AdmissionPersistenceError, match="constructor-authorized"):
            store_admission(session, reconstructed)
        table = ResearchBase.metadata.tables["research_strategy_admission"]
        assert session.scalar(select(func.count()).select_from(table)) == 0


def test_research_store_has_an_exact_type_gate_for_forged_lookalikes():
    _registry, _document, _plan, _assessment, wrapper = _phase4_fixture()
    raw_receipt = _raw_receipt(wrapper)
    lookalike = SimpleNamespace(
        **{
            name: getattr(wrapper, name)
            for name in (
                "owner_id",
                "graph_identifier",
                "graph_version",
                "graph_address",
                "scheme",
                "contract_suite",
                "parity_suite",
                "format_version",
                "content_address",
            )
        },
        admission_address=content_address(raw_receipt),
        to_dict=lambda: raw_receipt,
    )

    with Session(_research_session()) as session:
        with pytest.raises(AdmissionPersistenceError, match="constructor-authorized"):
            store_admission(session, lookalike)


@pytest.mark.parametrize(
    "label, mutate",
    [
        (
            "receipt assessment address",
            lambda receipt: receipt["phase4_data_binding"].update(
                capability_assessment_address="sha256:" + "f" * 64
            ),
        ),
        (
            "receipt owner",
            lambda receipt: receipt.update(owner_id="owner-b"),
        ),
        (
            "receipt graph address",
            lambda receipt: receipt.update(graph_address="sha256:" + "f" * 64),
        ),
    ],
)
def test_research_process_reload_refuses_tampered_receipt_identity(label, mutate):
    del label
    registry, _document, _plan, _assessment, wrapper = _phase4_fixture()
    raw_receipt = _raw_receipt(wrapper)
    mutate(raw_receipt)
    with pytest.raises(V2GraphVerificationError):
        reconstruct_phase4_artifact(
            raw_receipt, owner_id="owner-a", registry=registry
        )
