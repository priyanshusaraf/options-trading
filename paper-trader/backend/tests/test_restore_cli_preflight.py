from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from app.db.restore_contract import RestoreRefusal


def _script_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "postgresql_backup_restore.py"
    spec = importlib.util.spec_from_file_location("task7_backup_restore", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_invalid_manifest_signature_opens_zero_target_and_runs_zero_restore(monkeypatch, tmp_path):
    module = _script_module()
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"schema_version":999}', encoding="utf-8")
    calls = []
    monkeypatch.setattr(module, "_urls", lambda *_args: calls.append("target") or {})
    monkeypatch.setattr(module, "run_process_spec", lambda *_args, **_kwargs: calls.append("restore"))
    args = type("Args", (), {
        "manifest": manifest, "signing_key_env": "MISSING_TASK7_KEY",
        "require_signed": True, "pg_restore": Path("pg_restore"),
        "timeout": 5, "output": tmp_path / "report.json",
    })()
    with pytest.raises(RestoreRefusal):
        module.restore(args)
    assert calls == []


def test_shared_target_preflights_all_planes_before_first_restore(monkeypatch, tmp_path):
    module = _script_module()
    manifest = {
        "planes": [{"plane": plane, "artifact": {
            "identifier": f"{plane}.dump", "sha256": "a" * 64}}
                   for plane in ("execution", "research", "ledger")]
    }
    path = tmp_path / "manifest.json"
    path.write_text(__import__("json").dumps(manifest), encoding="utf-8")
    for plane in ("execution", "research", "ledger"):
        (tmp_path / f"{plane}.dump").write_bytes(b"dump")
    calls = []
    monkeypatch.setattr(module, "verify_manifest_signature", lambda *_a, **_k: None)
    monkeypatch.setattr(module, "_urls", lambda *_a: {
        plane: f"postgresql://u@db/target?options=-csearch_path%3D{plane}"
        for plane in ("execution", "research", "ledger")})
    monkeypatch.setattr(module, "sha256_file", lambda _path: "a" * 64)
    monkeypatch.setattr(module, "assert_fresh_restore_target",
                        lambda url, **_k: calls.append(("preflight", url)))
    monkeypatch.setattr(module, "postgres_process_spec", lambda url, **_k: url)
    monkeypatch.setattr(module, "run_process_spec",
                        lambda spec, **_k: calls.append(("restore", spec)))
    monkeypatch.setattr(module, "configured_restore_planes", lambda **_k: [])
    monkeypatch.setattr(module, "verify_restore", lambda *_a, **_k: {
        "generation_id": "g", "cutover_ready": True})
    monkeypatch.setattr(module, "_atomic_text", lambda *_a: None)
    args = type("Args", (), {
        "manifest": path, "signing_key_env": "MISSING_TASK7_KEY",
        "require_signed": False, "pg_restore": Path("pg_restore"),
        "timeout": 5, "output": tmp_path / "report.json",
    })()
    module.restore(args)
    assert [kind for kind, _value in calls] == [
        "preflight", "restore", "restore", "restore"]
