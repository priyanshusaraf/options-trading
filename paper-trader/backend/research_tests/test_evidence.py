import json

import pytest

from app.ir.hashing import content_address
from research.evidence import (
    EvidenceMissing,
    EvidenceRejected,
    decode_terminal_evidence,
    encode_terminal_evidence,
)


EVIDENCE = {
    "run": {"id": 7, "status": "completed", "decision": "archive"},
    "graph": {
        "identifier": "strategy.example",
        "version": 3,
        "content_address": "sha256:" + "a" * 64,
    },
    "instruments": [
        {"instrument": "AAA", "qualified": False, "reason": "insufficient trades"}
    ],
}


def test_terminal_evidence_is_canonical_and_content_addressed():
    raw = encode_terminal_evidence(EVIDENCE)
    envelope = json.loads(raw)

    assert raw == json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    assert envelope == {
        "schema_version": 1,
        "content_address": content_address(EVIDENCE),
        "evidence": EVIDENCE,
    }
    assert decode_terminal_evidence(raw) == EVIDENCE


def test_key_order_does_not_change_terminal_evidence_identity():
    reordered = {"instruments": EVIDENCE["instruments"], "graph": EVIDENCE["graph"],
                 "run": EVIDENCE["run"]}
    assert encode_terminal_evidence(reordered) == encode_terminal_evidence(EVIDENCE)


def test_missing_evidence_is_explicitly_legacy_unbound():
    with pytest.raises(EvidenceMissing, match="legacy-unbound"):
        decode_terminal_evidence(None)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda envelope: envelope.update(schema_version=2),
        lambda envelope: envelope.update(content_address="sha256:" + "0" * 64),
        lambda envelope: envelope.update(extra="client evidence"),
        lambda envelope: envelope.update(evidence=[]),
    ],
)
def test_malformed_or_tampered_evidence_fails_closed(mutation):
    envelope = json.loads(encode_terminal_evidence(EVIDENCE))
    mutation(envelope)
    raw = json.dumps(envelope)
    with pytest.raises(EvidenceRejected):
        decode_terminal_evidence(raw)


def test_non_json_nonfinite_and_oversized_evidence_are_rejected():
    for raw in ("not-json", '{"value":NaN}', "{" + "x" * 2_000_001):
        with pytest.raises(EvidenceRejected):
            decode_terminal_evidence(raw)


def test_server_cannot_encode_nonfinite_or_non_mapping_evidence():
    with pytest.raises(EvidenceRejected):
        encode_terminal_evidence({"score": float("nan")})
    with pytest.raises(EvidenceRejected):
        encode_terminal_evidence(["not", "an", "evidence", "object"])
