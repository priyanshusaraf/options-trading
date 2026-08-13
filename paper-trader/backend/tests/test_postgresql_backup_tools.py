from __future__ import annotations

from pathlib import Path

import pytest

from app.operations.postgresql_backup import (
    BackupToolRefusal,
    assert_fresh_restore_target,
    managed_pitr_capability,
    postgres_process_spec,
)


def test_postgres_tool_process_spec_never_contains_full_or_password_url(tmp_path):
    spec = postgres_process_spec(
        "postgresql+psycopg://operator:p%40ss@db.internal:5433/strategy"
        "?options=-csearch_path%3Dexecution",
        executable=Path("/opt/homebrew/opt/postgresql@16/bin/pg_dump"),
        action="dump", artifact=tmp_path / "execution.dump")
    joined = " ".join(spec.command)
    assert "://" not in joined and "p@ss" not in joined
    assert "PGPASSWORD" not in spec.environment
    assert spec.password == "p@ss"  # caller writes a mode-0600 temporary pgpass
    assert spec.schema == "execution"


def test_postgres_tool_requires_one_private_schema_and_fresh_artifact(tmp_path):
    with pytest.raises(BackupToolRefusal, match="search_path"):
        postgres_process_spec("postgresql://operator@db/strategy",
                              executable=Path("pg_dump"), action="dump",
                              artifact=tmp_path / "x.dump")
    existing = tmp_path / "existing.dump"
    existing.write_bytes(b"do-not-overwrite")
    with pytest.raises(BackupToolRefusal, match="already exists"):
        postgres_process_spec(
            "postgresql://operator@db/strategy?options=-csearch_path%3Dexecution",
            executable=Path("pg_dump"), action="dump", artifact=existing)


def test_managed_pitr_is_unproven_without_actual_rehearsal_evidence():
    result = managed_pitr_capability(None)
    assert result["status"] == "UNPROVEN"
    assert result["rpo_seconds"] == "UNMEASURED"
    assert result["rto_seconds"] == "UNMEASURED"


def test_restore_target_refuses_unknown_application_schema(monkeypatch):
    class Inspector:
        def get_table_names(self): return []
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def scalars(self, _statement): return ["execution", "rogue"]
        def scalar(self, _statement, _params=None): return 0
    class Engine:
        def connect(self): return Connection()
        def dispose(self): pass
    monkeypatch.setattr("app.operations.postgresql_backup.sa.create_engine", lambda *_a, **_k: Engine())
    monkeypatch.setattr("app.operations.postgresql_backup.inspect", lambda _connection: Inspector())
    with pytest.raises(BackupToolRefusal, match="unknown application schema"):
        assert_fresh_restore_target(
            "postgresql://operator@db/strategy?options=-csearch_path%3Dexecution",
            expected_schemas={"execution", "research", "ledger"})
