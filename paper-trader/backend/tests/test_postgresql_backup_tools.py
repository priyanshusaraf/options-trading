from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.operations.postgresql_backup import (
    BackupToolRefusal,
    assert_fresh_restore_target,
    managed_pitr_capability,
    postgres_process_spec,
    run_process_spec,
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
    assert "p@ss" not in repr(spec) and "environment=" not in repr(spec)


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
    for url in (
        "postgresql://db/strategy?options=-csearch_path%3Dexecution",
        "postgresql://operator@db/?options=-csearch_path%3Dexecution",
    ):
        with pytest.raises(BackupToolRefusal, match="user and database"):
            postgres_process_spec(
                url, executable=Path("pg_dump"), action="dump",
                artifact=tmp_path / "identity.dump",
            )
    with pytest.raises(BackupToolRefusal, match="single-host"):
        postgres_process_spec(
            "postgresql://operator@host1:5432,host2:5433/strategy"
            "?options=-csearch_path%3Dexecution",
            executable=Path("pg_dump"), action="dump", artifact=tmp_path / "multi.dump",
        )


@pytest.mark.parametrize("action", ["dump", "restore"])
def test_postgres_tool_preserves_explicit_libpq_tls_policy(tmp_path, action):
    artifact = tmp_path / "execution.dump"
    if action == "restore":
        artifact.write_bytes(b"archive")
    spec = postgres_process_spec(
        "postgresql://operator@db.internal/strategy"
        "?options=-csearch_path%3Dexecution&sslmode=verify-full"
        "&sslrootcert=%2Fcerts%2Froot.pem&sslcert=%2Fcerts%2Fclient.pem"
        "&sslkey=%2Fcerts%2Fclient.key&ssl_min_protocol_version=TLSv1.2"
        "&ssl_max_protocol_version=TLSv1.3&channel_binding=require"
        "&require_auth=scram-sha-256&sslcertmode=require"
        "&gssdelegation=1&load_balance_hosts=disable",
        executable=Path(f"pg_{action}"), action=action, artifact=artifact,
    )
    assert spec.environment == {
        "PGHOST": "db.internal", "PGPORT": "5432", "PGUSER": "operator",
        "PGDATABASE": "strategy", "PGOPTIONS": "-c search_path=execution",
        "PGSSLMODE": "verify-full", "PGSSLROOTCERT": "/certs/root.pem",
        "PGSSLCERT": "/certs/client.pem", "PGSSLKEY": "/certs/client.key",
        "PGSSLMINPROTOCOLVERSION": "TLSv1.2",
        "PGSSLMAXPROTOCOLVERSION": "TLSv1.3",
        "PGCHANNELBINDING": "require",
        "PGREQUIREAUTH": "scram-sha-256", "PGSSLCERTMODE": "require",
        "PGGSSDELEGATION": "1", "PGLOADBALANCEHOSTS": "disable",
    }
    assert all("certs" not in argument for argument in spec.command)


@pytest.mark.parametrize("query", [
    "sslnegotiation=direct", "sslpassword=secret", "keepalives=1",
    "keepalives_idle=30", "keepalives_interval=10", "keepalives_count=3",
    "tcp_user_timeout=1000", "sslmode=verify-full&sslmode=require", "sslkey=",
    "host=other.internal", "port=5433", "user=other", "password=secret",
    "dbname=other", "application_name=backup",
    "requiressl=1&requiressl=1",
])
def test_postgres_tool_refuses_unsupported_or_malformed_security_options(
        tmp_path, query):
    with pytest.raises(BackupToolRefusal, match="option"):
        postgres_process_spec(
            "postgresql://operator@db/strategy"
            f"?options=-csearch_path%3Dexecution&{query}",
            executable=Path("pg_dump"), action="dump",
            artifact=tmp_path / "x.dump",
        )


def test_explicit_tls_policy_overrides_ambient_libpq_environment(
        tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.operations.postgresql_backup.os",
        SimpleNamespace(environ={"PGSSLMODE": "prefer"}),
    )
    monkeypatch.setattr(
        "app.operations.postgresql_backup.subprocess.run",
        lambda *_args, **kwargs: captured.update(kwargs) or SimpleNamespace(
            returncode=0, stderr="",
        ),
    )
    spec = postgres_process_spec(
        "postgresql://operator@db/strategy"
        "?options=-csearch_path%3Dexecution&sslmode=verify-full",
        executable=Path("pg_dump"), action="dump", artifact=tmp_path / "x.dump",
    )
    run_process_spec(spec)
    assert captured["env"]["PGSSLMODE"] == "verify-full"

    captured.clear()
    ambient = postgres_process_spec(
        "postgresql://operator@db/strategy?options=-csearch_path%3Dexecution",
        executable=Path("pg_dump"), action="dump",
        artifact=tmp_path / "ambient.dump",
    )
    run_process_spec(ambient)
    assert captured["env"]["PGSSLMODE"] == "prefer"


def test_bounded_process_environment_removes_ambient_service_override(
        tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.operations.postgresql_backup.os",
        SimpleNamespace(environ={
            "PGSERVICE": "test-service",
            "PGSERVICEFILE": "/test/pg_service.conf",
            "PGPASSWORD": "test-ambient-password",
            "PGHOSTADDR": "192.0.2.10",
        }),
    )
    monkeypatch.setattr(
        "app.operations.postgresql_backup.subprocess.run",
        lambda *_args, **kwargs: captured.update(kwargs) or SimpleNamespace(
            returncode=0, stderr="",
        ),
    )
    spec = postgres_process_spec(
        "postgresql://operator@db.internal/strategy"
        "?options=-csearch_path%3Dexecution&sslmode=verify-full",
        executable=Path("pg_dump"), action="dump", artifact=tmp_path / "x.dump",
    )
    run_process_spec(spec)
    service_keys = sorted({
        "PGSERVICE", "PGSERVICEFILE", "PGPASSWORD", "PGHOSTADDR",
    }.intersection(
        captured["env"]
    ))
    assert service_keys == []
    assert captured["env"]["PGHOST"] == "db.internal"
    assert captured["env"]["PGSSLMODE"] == "verify-full"


def test_explicit_hostaddr_and_legacy_required_tls_win_over_ambient(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.operations.postgresql_backup.os",
        SimpleNamespace(environ={
            "PGHOSTADDR": "192.0.2.10", "PGSSLMODE": "disable",
        }),
    )
    monkeypatch.setattr(
        "app.operations.postgresql_backup.subprocess.run",
        lambda *_args, **kwargs: captured.update(kwargs) or SimpleNamespace(
            returncode=0, stderr="",
        ),
    )
    spec = postgres_process_spec(
        "postgresql://operator@db.internal/strategy"
        "?options=-csearch_path%3Dexecution&hostaddr=192.0.2.20&requiressl=1",
        executable=Path("pg_dump"), action="dump", artifact=tmp_path / "x.dump",
    )
    run_process_spec(spec)
    assert captured["env"]["PGHOSTADDR"] == "192.0.2.20"
    assert captured["env"]["PGSSLMODE"] == "require"


def test_failure_redacts_paths_and_password_and_removes_private_pgpass(
        tmp_path, monkeypatch):
    captured = {}
    safe_os = SimpleNamespace(
        environ={"PGPASSWORD": "test-ambient-password"},
        fchmod=os.fchmod, fdopen=os.fdopen, unlink=os.unlink,
    )
    monkeypatch.setattr("app.operations.postgresql_backup.os", safe_os)

    def fail_process(*_args, **kwargs):
        pgpass = Path(kwargs["env"]["PGPASSFILE"])
        assert pgpass.read_text() == "db:5432:strategy:operator:test-url-password\n"
        captured["pgpass"] = pgpass
        captured["mode"] = pgpass.stat().st_mode & 0o777
        captured["ambient_password_present"] = "PGPASSWORD" in kwargs["env"]
        return SimpleNamespace(
            returncode=1,
            stderr=("failed with test-url-password at /test/client.key "
                    f"while writing {tmp_path / 'x.dump'}"),
        )

    monkeypatch.setattr(
        "app.operations.postgresql_backup.subprocess.run", fail_process,
    )
    spec = postgres_process_spec(
        "postgresql://operator:test-url-password@db/strategy"
        "?options=-csearch_path%3Dexecution&sslkey=%2Ftest%2Fclient.key",
        executable=Path("pg_dump"), action="dump", artifact=tmp_path / "x.dump",
    )
    with pytest.raises(BackupToolRefusal) as error:
        run_process_spec(spec)
    assert captured["mode"] == 0o600
    assert captured["ambient_password_present"] is False
    assert not captured["pgpass"].exists()
    message = str(error.value)
    assert message.count("[redacted]") == 3
    assert "test-url-password" not in message
    assert "/test/client.key" not in message
    assert str(tmp_path / "x.dump") not in message


def test_pgpass_is_removed_when_writing_fails(tmp_path, monkeypatch):
    import app.operations.postgresql_backup as backup

    captured = {}
    real_tempfile = backup.tempfile.NamedTemporaryFile

    @contextmanager
    def failing_tempfile(**kwargs):
        with real_tempfile(dir=tmp_path, **kwargs) as handle:
            captured["path"] = Path(handle.name)
            write = handle.write

            def fail_after_write(line):
                write(line)
                handle.flush()
                captured["bytes"] = Path(handle.name).stat().st_size
                raise OSError("simulated write failure")

            handle.write = fail_after_write
            yield handle

    monkeypatch.setattr(backup, "os", SimpleNamespace(environ={}))
    monkeypatch.setattr(backup.tempfile, "NamedTemporaryFile", failing_tempfile)
    spec = postgres_process_spec(
        "postgresql://operator:test-only-password@db/strategy"
        "?options=-csearch_path%3Dexecution",
        executable=Path("pg_dump"), action="dump", artifact=tmp_path / "write.dump",
    )
    with pytest.raises(OSError, match="simulated write failure"):
        run_process_spec(spec)
    assert captured["bytes"] > 0
    assert not captured["path"].exists()


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
