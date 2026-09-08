"""Golden evidence for the frozen v1 validation contract at the dispatch seam."""
from __future__ import annotations

import copy
import hashlib
import json

import pytest

from app.ir.validate import Violation, validate
from tests.test_ir_conformance import a_component, a_graph


def _canonical_bytes(document: dict) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


@pytest.mark.parametrize(
    ("factory", "expected_sha256"),
    [
        (a_component, "09ffb534f2f25491088cb42e136e82da648a0dcce1c0b8b71bb3efe4d78d806d"),
        (a_graph, "fa37d02170a8fba6e84ee3906cd0cceb989bc366855c1177eab15253bd8aba97"),
    ],
)
def test_v1_golden_documents_keep_bytes_and_validate(factory, expected_sha256):
    document = factory()
    before = _canonical_bytes(document)

    assert hashlib.sha256(before).hexdigest() == expected_sha256
    assert validate(document) == []
    assert _canonical_bytes(document) == before


def test_v1_validation_error_contract_is_stable():
    document = a_component()
    document["identifier"] = ""

    assert validate(document) == [
        Violation(
            "F2",
            "$.identifier",
            "must be a non-empty immutable identifier",
        )
    ]


def test_missing_format_version_fails_closed():
    document = a_component()
    del document["format_version"]
    document["identifier"] = ""

    assert validate(document) == [Violation("F1", "$.format_version", "missing")]


@pytest.mark.parametrize("version", [True, False, 1.0, "1", 2, -1])
def test_non_integer_or_unknown_format_versions_fail_closed(version):
    document = a_component()
    document["format_version"] = version
    document["identifier"] = ""

    assert validate(document) == [
        Violation(
            "F1",
            "$.format_version",
            f"{version!r} is not understood (this reader knows 1)",
        )
    ]


def test_validate_does_not_mutate_a_v1_document():
    document = a_graph()
    original = copy.deepcopy(document)

    validate(document)

    assert document == original
