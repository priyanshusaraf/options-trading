"""Golden admission and identity checks for the frozen v1 dispatch path."""
from __future__ import annotations

import copy

import pytest

from app.ir.hashing import content_address
from app.ir.library import REGISTRY
from app.ir.strategies.expanding_z import GRAPH
from app.strategy.admission import (
    AdmissionRefusalCode,
    IRGraphAdmissionInput,
    ParityEvidence,
    admitted_artifact,
    admit_strategy,
    inspect_strategy,
)


def _v1_input(graph=None) -> IRGraphAdmissionInput:
    return IRGraphAdmissionInput(graph or GRAPH, {}, None)


def test_v1_admission_identity_and_receipt_are_golden():
    decision = inspect_strategy(
        owner_id="golden-owner",
        source_input=_v1_input(),
        registry=REGISTRY,
    )

    assert decision.refusal_code is None
    structural = decision.structural
    assert structural is not None
    assert structural.graph_address == (
        "sha256:d78b424e8247e26663728b19980e197fb5e84a4e21c08c4df00ac704db1ae02b"
    )
    assert structural.graph_identifier == "strategy.expanding_z_impulse"
    assert structural.graph_version == 4
    assert structural.declared_warmup == 302
    assert structural.canonical_mapping == {
        "longEntry": "longEntry",
        "longExit": "longExit",
        "shortEntry": "shortEntry",
        "shortExit": "shortExit",
    }

    artifact = admitted_artifact(
        structural,
        ParityEvidence(
            "sha256:" + "1" * 64,
            "sha256:" + "2" * 64,
            "sha256:" + "2" * 64,
        ),
    )
    assert artifact.admission_address == (
        "sha256:1cf49ddd89c382047c1bd45e128bce5e4650d15a0e608e4de243df282385d85e"
    )
    assert artifact.admission_address == content_address(artifact.to_dict())


@pytest.mark.parametrize("version", [None, True, 1.0, "1", 2, 99])
def test_unsupported_v1_admission_refuses_before_partial_state(version):
    graph = copy.deepcopy(GRAPH)
    if version is None:
        graph.pop("format_version")
    else:
        graph["format_version"] = version
    receipts = {"before": ["existing-receipt"]}
    before = copy.deepcopy(receipts)

    decision = admit_strategy(
        owner_id="golden-owner",
        source_input=_v1_input(graph),
        registry=REGISTRY,
    )

    assert decision.artifact is None
    assert decision.refusal_code is AdmissionRefusalCode.IR_INVALID
    assert "F1" in decision.detail
    assert receipts == before
