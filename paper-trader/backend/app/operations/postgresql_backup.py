"""Credential-safe PostgreSQL 16 logical backup/restore process boundaries."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qsl, urlsplit

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from research.guards import _search_path


_LIBPQ_URL_ENV = {
    "hostaddr": "PGHOSTADDR",
    "connect_timeout": "PGCONNECT_TIMEOUT",
    "target_session_attrs": "PGTARGETSESSIONATTRS",
    "sslmode": "PGSSLMODE",
    "sslcompression": "PGSSLCOMPRESSION",
    "sslcert": "PGSSLCERT",
    "sslkey": "PGSSLKEY",
    "sslrootcert": "PGSSLROOTCERT",
    "sslcrl": "PGSSLCRL",
    "sslcrldir": "PGSSLCRLDIR",
    "sslsni": "PGSSLSNI",
    "requirepeer": "PGREQUIREPEER",
    "ssl_min_protocol_version": "PGSSLMINPROTOCOLVERSION",
    "ssl_max_protocol_version": "PGSSLMAXPROTOCOLVERSION",
    "gssencmode": "PGGSSENCMODE",
    "krbsrvname": "PGKRBSRVNAME",
    "gsslib": "PGGSSLIB",
    "channel_binding": "PGCHANNELBINDING",
    "require_auth": "PGREQUIREAUTH",
    "sslcertmode": "PGSSLCERTMODE",
    "gssdelegation": "PGGSSDELEGATION",
    "load_balance_hosts": "PGLOADBALANCEHOSTS",
}
_PROCESS_PATH_VARIABLES = {
    "PGSSLCERT", "PGSSLKEY", "PGSSLROOTCERT", "PGSSLCRL", "PGSSLCRLDIR",
}


class BackupToolRefusal(RuntimeError):
    pass


@dataclass(frozen=True)
class PostgresProcessSpec:
    command: tuple[str, ...]
    environment: dict[str, str] = field(repr=False)
    password: str | None = field(repr=False)
    host: str
    port: int
    user: str
    database: str
    schema: str
    artifact: Path
    action: str


def resolve_postgresql16_tools(*, environment: Mapping[str, str] | None = None) -> tuple[Path, Path]:
    env = os.environ if environment is None else environment
    override = str(env.get("PT_PG_BIN_DIR", "")).strip()
    candidates = []
    if override:
        root = Path(override).expanduser()
        candidates.append((root / "pg_dump", root / "pg_restore"))
    found_dump, found_restore = shutil.which("pg_dump"), shutil.which("pg_restore")
    if found_dump and found_restore:
        candidates.append((Path(found_dump), Path(found_restore)))
    candidates.append((Path("/opt/homebrew/opt/postgresql@16/bin/pg_dump"),
                       Path("/opt/homebrew/opt/postgresql@16/bin/pg_restore")))
    for dump, restore in candidates:
        if not (dump.is_file() and restore.is_file()):
            continue
        versions = []
        for executable in (dump, restore):
            result = subprocess.run([str(executable), "--version"], check=False,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, timeout=10)
            match = re.search(r"\b(\d+)(?:\.\d+)*\b", result.stdout)
            versions.append(int(match.group(1)) if result.returncode == 0 and match else None)
        if versions == [16, 16]:
            return dump.resolve(), restore.resolve()
    raise BackupToolRefusal("PostgreSQL 16 pg_dump and pg_restore are required")


def _set_legacy_ssl_mode(environment, seen, name: str, value: str) -> bool:
    if name != "requiressl":
        return False
    if value != "1" or "sslmode" in seen or name in seen:
        raise BackupToolRefusal("PostgreSQL requiressl option must be the sole TLS mode")
    environment["PGSSLMODE"] = "require"
    seen.add(name)
    return True


def _set_libpq_url_option(environment, seen, name: str, value: str) -> None:
    if name == "options":
        return
    if _set_legacy_ssl_mode(environment, seen, name, value):
        return
    variable = _LIBPQ_URL_ENV.get(name)
    if variable is None:
        raise BackupToolRefusal(
            f"PostgreSQL 16 connection option {name!r} is unsupported"
        )
    if "requiressl" in seen and name == "sslmode":
        raise BackupToolRefusal("PostgreSQL requiressl must be the sole TLS mode")
    if name in seen:
        raise BackupToolRefusal(f"PostgreSQL option {name!r} must appear once")
    seen.add(name)
    environment[variable] = value


def _libpq_url_environment(url: str) -> dict[str, str]:
    environment, seen = {}, set()
    for raw_name, value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        name = raw_name.lower()
        if name != "options" and (not value or "\x00" in value):
            raise BackupToolRefusal(
                f"PostgreSQL option {name!r} must have one nonempty value"
            )
        _set_libpq_url_option(environment, seen, name, value)
    return environment


def _postgres_identity(url: str, parsed) -> tuple[str, int, str, str, str]:
    if parsed.get_backend_name() != "postgresql":
        raise BackupToolRefusal("logical backup tools require PostgreSQL")
    search_path = _search_path(url)
    if not search_path:
        raise BackupToolRefusal("one explicit private search_path is required")
    host, port = parsed.host or "localhost", int(parsed.port or 5432)
    user, database = parsed.username or "", parsed.database or ""
    if not user or not database:
        raise BackupToolRefusal("bounded PostgreSQL user and database are required")
    return host, port, user, database, search_path[0]


def _validated_artifact(artifact: Path, action: str) -> Path:
    if action not in {"dump", "restore"}:
        raise BackupToolRefusal("action must be dump or restore")
    resolved = artifact.expanduser().resolve()
    if action == "dump" and resolved.exists():
        raise BackupToolRefusal("backup artifact already exists")
    if action == "restore" and not resolved.is_file():
        raise BackupToolRefusal("restore artifact does not exist")
    return resolved


def _postgres_command(executable: Path, action: str, artifact: Path,
                      database: str, schema: str) -> tuple[str, ...]:
    if action == "dump":
        return (str(executable), "--format=custom", "--no-owner", "--no-acl",
                "--schema", schema, "--file", str(artifact), database)
    return (str(executable), "--exit-on-error", "--no-owner", "--no-acl",
            "--dbname", database, str(artifact))


def postgres_process_spec(url: str, *, executable: Path, action: str,
                          artifact: Path) -> PostgresProcessSpec:
    try:
        parsed = make_url(url)
    except (sa.exc.ArgumentError, ValueError):
        raise BackupToolRefusal("a supported single-host PostgreSQL URL is required") from None
    host, port, user, database, schema = _postgres_identity(url, parsed)
    artifact = _validated_artifact(artifact, action)
    environment = {
        "PGHOST": host, "PGPORT": str(port), "PGUSER": user,
        "PGDATABASE": database, "PGOPTIONS": f"-c search_path={schema}",
    }
    environment.update(_libpq_url_environment(url))
    command = _postgres_command(executable, action, artifact, database, schema)
    return PostgresProcessSpec(command, environment, parsed.password, host, port,
                               user, database, schema, artifact, action)


def _pgpass_field(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace(":", "\\:")


def _process_environment(spec: PostgresProcessSpec) -> dict[str, str]:
    environment = {**os.environ, **spec.environment}
    for name in ("PGSERVICE", "PGSERVICEFILE", "PGPASSWORD"):
        environment.pop(name, None)
    if "PGHOSTADDR" not in spec.environment:
        environment.pop("PGHOSTADDR", None)
    return environment


@contextmanager
def _pgpass_environment(spec: PostgresProcessSpec, environment):
    if spec.password is None:
        yield
        return
    with tempfile.NamedTemporaryFile(
            mode="w", prefix="strategy-os-pgpass-", encoding="utf-8") as handle:
        line = ":".join(_pgpass_field(value) for value in (
            spec.host, spec.port, spec.database, spec.user, spec.password,
        )) + "\n"
        handle.write(line)
        handle.flush()
        environment["PGPASSFILE"] = handle.name
        yield


def _redacted_detail(spec: PostgresProcessSpec, stderr: str) -> str:
    sensitive = [spec.password, str(spec.artifact)]
    sensitive.extend(spec.environment.get(name) for name in _PROCESS_PATH_VARIABLES)
    detail = stderr.strip().replace("\n", " ")
    for value in sorted(filter(None, sensitive), key=len, reverse=True):
        detail = detail.replace(value, "[redacted]")
    return detail[:400]


def _process_receipt(spec: PostgresProcessSpec, duration: float) -> dict[str, object]:
    return {
        "action": spec.action, "duration_seconds": duration,
        "artifact": spec.artifact.name,
        "artifact_bytes": spec.artifact.stat().st_size if spec.artifact.exists() else 0,
    }


def run_process_spec(spec: PostgresProcessSpec, *, timeout_seconds: int = 900) -> dict[str, object]:
    if timeout_seconds < 1 or timeout_seconds > 86_400:
        raise BackupToolRefusal("backup tool timeout exceeds operator safety bound")
    environment = _process_environment(spec)
    with _pgpass_environment(spec, environment):
        started = time.monotonic()
        result = subprocess.run(list(spec.command), env=environment, check=False,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                timeout=timeout_seconds)
        duration = time.monotonic() - started
        if result.returncode != 0:
            detail = _redacted_detail(spec, result.stderr)
            raise BackupToolRefusal(f"{spec.action} tool failed: {detail}")
        return _process_receipt(spec, duration)


def assert_fresh_restore_target(url: str, *, expected_schemas: set[str] | None = None) -> None:
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not _search_path(url):
        raise BackupToolRefusal("restore target requires one private PostgreSQL search_path")
    engine = sa.create_engine(url, future=True, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                raise BackupToolRefusal("restore target schema is nonempty")
            if expected_schemas is not None:
                schemas = set(connection.scalars(sa.text("""
                    SELECT schema_name FROM information_schema.schemata
                    WHERE schema_name NOT IN ('information_schema', 'public')
                      AND schema_name NOT LIKE 'pg_%'
                """)))
                if schemas - expected_schemas:
                    raise BackupToolRefusal("restore target contains an unknown application schema")
                application_tables = int(connection.scalar(sa.text("""
                    SELECT count(*) FROM information_schema.tables
                    WHERE table_schema = ANY(:schemas) AND table_type = 'BASE TABLE'
                """), {"schemas": sorted(expected_schemas)}) or 0)
                if application_tables:
                    raise BackupToolRefusal("restore target contains application tables")
            active = int(connection.scalar(sa.text("""
                SELECT count(*) FROM pg_stat_activity
                WHERE datname = current_database() AND pid <> pg_backend_pid()
                  AND state <> 'idle'
            """)) or 0)
            if active:
                raise BackupToolRefusal("restore target has current application activity")
    finally:
        engine.dispose()


def sha256_file(path: Path, *, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def managed_pitr_capability(evidence: Mapping[str, object] | None) -> dict[str, object]:
    required = {
        "provider_cluster", "immutable_backup_generation", "wal_range",
        "target_timestamp", "before_marker", "after_marker", "restore_log_sha256",
        "verifier_content_address", "rpo_seconds", "rto_seconds",
        "old_primary_isolated", "encrypted", "off_account",
    }
    if evidence is None or not required <= set(evidence):
        return {"status": "UNPROVEN", "rpo_seconds": "UNMEASURED",
                "rto_seconds": "UNMEASURED",
                "missing": sorted(required - set(evidence or {}))}
    if (evidence.get("old_primary_isolated") is not True
            or evidence.get("encrypted") is not True
            or evidence.get("off_account") is not True):
        return {"status": "FAILED", "rpo_seconds": evidence.get("rpo_seconds", "UNMEASURED"),
                "rto_seconds": evidence.get("rto_seconds", "UNMEASURED")}
    return {"status": "PROVEN", "rpo_seconds": evidence["rpo_seconds"],
            "rto_seconds": evidence["rto_seconds"],
            "verifier_content_address": evidence["verifier_content_address"]}
