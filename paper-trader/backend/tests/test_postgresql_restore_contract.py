from __future__ import annotations

import copy

import pytest

from app.db.restore_contract import (
    RestoreRefusal,
    canonical_manifest,
    finalize_manifest,
    validate_manifest,
    verify_manifest_signature,
)


def _manifest() -> dict:
    generation = "restore-20260813-a"
    return {
        "schema_version": 1,
        "generation_id": generation,
        "created_at": "2026-08-13T12:00:00+00:00",
        "backup_started_at": "2026-08-13T11:59:00+00:00",
        "backup_completed_at": "2026-08-13T12:00:00+00:00",
        "source_build": "d982428",
        "postgresql_major": 16,
        "coherence": {"maintenance_quiesced": True, "mode": "three-plane-maintenance",
                      "evidence_address": "sha256:" + "6" * 64},
        "planes": [
            {
                "plane": name,
                "generation_id": generation,
                "source_authority": "sha256:" + str(index) * 64,
                "source_physical_authority": "sha256:" + str(index + 3) * 64,
                "schema_head": "head",
                "table_inventory": [f"{name}_table"],
                "tables": {f"{name}_table": {
                    "rows": 1, "pk_digest": "0" * 64,
                    "row_digest": "1" * 64, "partition_counts": {},
                }},
                "sequences": [],
                "state_counts": {},
                "content_addresses": [],
                "artifact": {"identifier": f"{name}.dump", "sha256": "2" * 64},
            }
            for index, name in enumerate(("execution", "research", "ledger"), start=1)
        ],
        "cross_plane": {"execution_organizations": "3" * 64,
                          "research_owners": "4" * 64,
                          "ledger_owner_accounts": "5" * 64},
        "capabilities": {"logical_restore": "PROVEN", "managed_pitr": "UNPROVEN"},
    }


def test_manifest_is_canonical_content_addressed_and_operator_signed():
    manifest = finalize_manifest(_manifest(), signing_key=b"operator-signing-key-32-bytes!!")
    assert manifest["content_address"].startswith("sha256:")
    assert manifest["signature"]["status"] == "signed"
    assert canonical_manifest(manifest).endswith("\n")
    verify_manifest_signature(manifest, signing_key=b"operator-signing-key-32-bytes!!",
                              require_signed=True)


def test_manifest_signature_rejects_load_bearing_row_mutation():
    manifest = finalize_manifest(_manifest(), signing_key=b"operator-signing-key-32-bytes!!")
    tampered = copy.deepcopy(manifest)
    tampered["planes"][0]["tables"]["execution_table"]["rows"] = 2
    with pytest.raises(RestoreRefusal, match="content address|signature"):
        verify_manifest_signature(tampered,
                                  signing_key=b"operator-signing-key-32-bytes!!",
                                  require_signed=True)


def test_manifest_refuses_mixed_or_incoherent_generations():
    manifest = _manifest()
    manifest["planes"][1]["generation_id"] = "another-generation"
    with pytest.raises(RestoreRefusal, match="mixed generation"):
        validate_manifest(manifest)
    manifest = _manifest()
    manifest["coherence"]["maintenance_quiesced"] = False
    with pytest.raises(RestoreRefusal, match="quiesced"):
        validate_manifest(manifest)
    manifest = _manifest()
    manifest["coherence"]["evidence_address"] = "UNRECORDED"
    with pytest.raises(RestoreRefusal, match="maintenance evidence"):
        validate_manifest(manifest)


def test_manifest_refuses_reversed_backup_timestamps():
    manifest = _manifest()
    manifest["backup_started_at"] = "2026-08-13T12:01:00+00:00"
    with pytest.raises(RestoreRefusal, match="timestamp ordering"):
        validate_manifest(manifest)


def test_unsigned_development_manifest_never_satisfies_production_approval():
    manifest = finalize_manifest(_manifest())
    assert manifest["signature"] == {"algorithm": "none", "status": "unsigned-development"}
    with pytest.raises(RestoreRefusal, match="signed"):
        verify_manifest_signature(manifest, signing_key=None, require_signed=True)
