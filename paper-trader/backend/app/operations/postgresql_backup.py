"""Credential-safe PostgreSQL 16 logical backup/restore process boundaries."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from research.guards import _search_path


class BackupToolRefusal(RuntimeError):
    pass


@dataclass(frozen=True)
class PostgresProcessSpec:
    command: tuple[str, ...]
    environment: dict[str, str]
    password: str | None
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


def postgres_process_spec(url: str, *, executable: Path, action: str,
                          artifact: Path) -> PostgresProcessSpec:
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        raise BackupToolRefusal("logical backup tools require PostgreSQL")
    search_path = _search_path(url)
    if not search_path:
        raise BackupToolRefusal("one explicit private search_path is required")
    if action not in {"dump", "restore"}:
        raise BackupToolRefusal("action must be dump or restore")
    artifact = artifact.expanduser().resolve()
    if action == "dump" and artifact.exists():
        raise BackupToolRefusal("backup artifact already exists")
    if action == "restore" and not artifact.is_file():
        raise BackupToolRefusal("restore artifact does not exist")
    host = parsed.host or "localhost"
    port = int(parsed.port or 5432)
    user = parsed.username or ""
    database = parsed.database or ""
    if not user or not database:
        raise BackupToolRefusal("bounded PostgreSQL user and database are required")
    environment = {
        "PGHOST": host, "PGPORT": str(port), "PGUSER": user,
        "PGDATABASE": database, "PGOPTIONS": f"-c search_path={search_path[0]}",
    }
    if action == "dump":
        command = (str(executable), "--format=custom", "--no-owner", "--no-acl",
                   "--schema", search_path[0], "--file", str(artifact), database)
    else:
        command = (str(executable), "--exit-on-error", "--no-owner", "--no-acl",
                   "--dbname", database, str(artifact))
    return PostgresProcessSpec(command, environment, parsed.password, host, port,
                               user, database, search_path[0], artifact, action)


def _pgpass_field(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace(":", "\\:")


def run_process_spec(spec: PostgresProcessSpec, *, timeout_seconds: int = 900) -> dict[str, object]:
    if timeout_seconds < 1 or timeout_seconds > 86_400:
        raise BackupToolRefusal("backup tool timeout exceeds operator safety bound")
    environment = {**os.environ, **spec.environment}
    pgpass_path: str | None = None
    try:
        if spec.password is not None:
            descriptor, pgpass_path = tempfile.mkstemp(prefix="strategy-os-pgpass-")
            os.fchmod(descriptor, 0o600)
            line = ":".join(_pgpass_field(value) for value in (
                spec.host, spec.port, spec.database, spec.user, spec.password)) + "\n"
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(line)
            environment["PGPASSFILE"] = pgpass_path
        started = time.monotonic()
        result = subprocess.run(list(spec.command), env=environment, check=False,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                timeout=timeout_seconds)
        duration = time.monotonic() - started
        if result.returncode != 0:
            # The URL and password are never in argv. Keep stderr bounded because
            # provider notices can contain database object names.
            detail = result.stderr.strip().replace("\n", " ")[:400]
            raise BackupToolRefusal(f"{spec.action} tool failed: {detail}")
        return {"action": spec.action, "duration_seconds": duration,
                "artifact": spec.artifact.name,
                "artifact_bytes": spec.artifact.stat().st_size if spec.artifact.exists() else 0}
    finally:
        if pgpass_path is not None:
            try:
                os.unlink(pgpass_path)
            except FileNotFoundError:
                pass


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
