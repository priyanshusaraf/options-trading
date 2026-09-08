#!/usr/bin/env python3
"""Deterministic, offline evidence for the Strategy OS V0 local substrate.

This program inventories and exercises existing authorities.  It is deliberately
not a deployer, service supervisor, migration runner, backup implementation, or
release signer.  A PASS receipt can establish only ``locally_runnable``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, NamedTuple


SCHEMA = "strategy-os-v0-local-release-evidence/1"
ANSWER_SCHEMA = "strategy-os-v0-local-release-answer/1"
MAX_BOUND_FILES = 64
MAX_BOUND_BYTES = 64 * 1024 * 1024
MAX_STEP_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_CHILD_FILE_BYTES = 1024 * 1024 * 1024
MAX_CHILD_MEMORY_BYTES = 2 * 1024 * 1024 * 1024
MAX_OPEN_FILES = 256
STREAM_CHUNK_BYTES = 64 * 1024
DEFAULT_STEP_TIMEOUT_SECONDS = 900
QUERY_BUDGET_AUTHORITY = (
    "tests/test_phase4_typed_market_authority.py::test_loader_query_count_is_bounded"
)
QUERY_BUDGET_STATEMENTS = 24

SAFE_CONFIGURATION_KEYS = (
    "PT_DISABLE_DOTENV",
    "PT_PROVIDER",
    "PT_EXECUTION",
    "PT_LIVE_ACK",
    "PT_RELEASE_PROFILE",
    "PT_RELEASE_SERVICE_ROLE",
    "PT_EXECUTION_WORKER",
    "PT_RESEARCH_ENABLED",
    "PT_DATABASE_URL",
    "PT_DB_PATH",
    "PT_LEDGER_DB_PATH",
    "PT_RESEARCH_DB_PATH",
)

# Closed inputs only.  No caller-selected source tree or recursive scan exists.
REPOSITORY_FILES = (
    ".github/workflows/strategy-os-ci.yml",
    "paper-trader/docker-compose.postgres.yml",
    "paper-trader/backend/requirements.lock",
    "paper-trader/backend/app/core/release_profile.py",
    "paper-trader/backend/app/core/config.py",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/app/db/migrate.py",
    "paper-trader/backend/app/db/restore_contract.py",
    "paper-trader/backend/scripts/postgresql_backup_restore.py",
    "paper-trader/backend/scripts/verify_postgresql_restore.py",
    "paper-trader/backend/scripts/copy_sqlite_to_postgres.py",
    "paper-trader/backend/scripts/run_disposable_postgres.py",
    "paper-trader/backend/scripts/run_research_worker.py",
    "paper-trader/backend/migrations/versions/20260829_0043_browser_auth.py",
    "paper-trader/backend/research/domain/migrate.py",
    "paper-trader/backend/research/domain/migrations/__init__.py",
    "paper-trader/frontend/package-lock.json",
    "paper-trader/backend/tests/test_v0_release_profile.py",
    "paper-trader/backend/tests/test_browser_auth_migration.py",
    "paper-trader/backend/tests/test_postgresql_restore_contract.py",
    "paper-trader/backend/tests/test_postgresql_restore_live.py",
    "paper-trader/backend/tests/test_restore_cli_preflight.py",
    "paper-trader/backend/tests/test_restore_boot_gate.py",
    "paper-trader/backend/tests/test_health_schema_version.py",
    "paper-trader/backend/tests/test_phase5_research_runtime_packaging.py",
    "paper-trader/backend/research_tests/test_foundation_direct_migration_0011.py",
    "paper-trader/backend/tests/test_phase4_typed_market_authority.py",
    "paper-trader/backend/scripts/v0_local_release_evidence.py",
    "paper-trader/backend/tests/test_v0_local_release_operations.py",
    "paper-trader/backend/research_tests/test_v0_local_release_operations.py",
)
EXTERNAL_FRONTEND_FILE = "package-lock.json"

HISTORICAL_RELEASE_BLOCKERS = (
    "no_clean_signed_v0_artifact_or_sbom",
    "no_production_secret_role_tls_topology",
    "no_production_shaped_three_plane_upgrade",
    "no_encrypted_retained_backup_or_measured_rpo_rto",
    "no_complete_service_restart_or_graceful_shutdown_rehearsal",
    "no_complete_build_head_worker_provider_frontend_health_gate",
    "no_observability_capacity_or_failure_drill_acceptance",
    "no_accepted_rollout_forward_repair_or_post_deploy_smoke",
    "inherited_broker_check_copy_refusal_open",
    "fixed_0041_capital_test_red_open",
)


class EvidenceRefusal(RuntimeError):
    """The evidence request crossed or failed the closed local contract."""


class StepInterrupted(KeyboardInterrupt):
    """A child group was interrupted after its bounded artifacts were sealed."""

    def __init__(self, result: dict[str, Any]):
        super().__init__("local evidence step interrupted")
        self.result = result


class Step(NamedTuple):
    label: str
    argv: tuple[str, ...]


def _canonical_json(value: Any) -> str:
    # Same JSON contract as app.ir.hashing.canonical_json.  Importing the app here
    # would execute package initialization before path and environment preflight.
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def _address(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_root(raw: str | Path, *, name: str, must_exist: bool) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        raise EvidenceRefusal(f"{name} must be an explicit absolute path")
    if candidate.is_symlink():
        raise EvidenceRefusal(f"{name} cannot be a symlink")
    if must_exist and (not candidate.is_dir() or not candidate.exists()):
        raise EvidenceRefusal(f"{name} must be an existing directory")
    resolved = candidate.resolve(strict=must_exist)
    if resolved == Path(resolved.anchor):
        raise EvidenceRefusal(f"{name} cannot be a filesystem root")
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_regular_file(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise EvidenceRefusal(f"unsafe input path: {relative}")
    candidate = root / rel
    current = root
    for part in rel.parts:
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError as error:
            raise EvidenceRefusal(f"required input is missing: {relative}") from error
        if stat.S_ISLNK(mode):
            raise EvidenceRefusal(f"symlink input is forbidden: {relative}")
    if not candidate.is_file() or not stat.S_ISREG(candidate.stat().st_mode):
        raise EvidenceRefusal(f"special or non-regular input is forbidden: {relative}")
    if not _is_relative_to(candidate.resolve(strict=True), root):
        raise EvidenceRefusal(f"input escapes its explicit root: {relative}")
    return candidate


def _validate_output(checkout: Path, output_root: Path, output_name: str) -> Path:
    if output_root == checkout:
        raise EvidenceRefusal("output root cannot equal the checkout input root")
    if output_root.exists() and (output_root.is_symlink() or not output_root.is_dir()):
        raise EvidenceRefusal("output root must be a real directory")
    rel = Path(output_name)
    if rel.is_absolute() or ".." in rel.parts or len(rel.parts) != 1:
        raise EvidenceRefusal("output name must be one plain filename")
    if rel.suffix != ".json":
        raise EvidenceRefusal("receipt output must use .json")
    output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = output_root / rel
    if target.exists() and (target.is_symlink() or not target.is_file()):
        raise EvidenceRefusal("receipt target must be a regular file")
    return target


def _run_capture(
    argv: Sequence[str], *, cwd: Path, env: Mapping[str, str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            list(argv), cwd=cwd, env=None if env is None else dict(env), check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EvidenceRefusal(f"structured subprocess failed: {argv[0]}") from error
    if len(result.stdout) + len(result.stderr) > MAX_STEP_OUTPUT_BYTES:
        raise EvidenceRefusal("subprocess output exceeded the local evidence bound")
    return result


def _required_text(argv: Sequence[str], *, cwd: Path) -> str:
    result = _run_capture(argv, cwd=cwd)
    if result.returncode != 0:
        raise EvidenceRefusal(f"required inventory command failed: {argv[0]}")
    return result.stdout.decode("utf-8", errors="strict").strip()


def _tool_identity(name: str, argv: Sequence[str], *, cwd: Path) -> dict[str, Any]:
    try:
        result = _run_capture(argv, cwd=cwd)
    except EvidenceRefusal:
        return {"name": name, "available": False, "version": None}
    text = (result.stdout or result.stderr).decode("utf-8", errors="replace").strip()
    return {
        "name": name,
        "available": result.returncode == 0,
        "version": text.splitlines()[0][:240] if result.returncode == 0 and text else None,
    }


def _postgres_identity(*, cwd: Path) -> dict[str, Any]:
    candidates = [shutil.which("postgres")]
    candidates.extend(str(root / "postgres") for root in (
        Path("/opt/homebrew/opt/postgresql@16/bin"),
        Path("/usr/local/opt/postgresql@16/bin"),
        Path("/opt/local/lib/postgresql16/bin"),
    ))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            identity = _tool_identity("postgresql", [candidate, "--version"], cwd=cwd)
            if identity["available"]:
                return identity
    return {"name": "postgresql", "available": False, "version": None}


def _bound_files(checkout: Path, frontend_root: Path) -> tuple[list[dict[str, Any]], int]:
    logical = list(REPOSITORY_FILES) + ["external-frontend/package-lock.json"]
    if len(logical) != len(set(logical)):
        raise EvidenceRefusal("duplicate path in closed evidence inventory")
    if len(logical) > MAX_BOUND_FILES:
        raise EvidenceRefusal("closed evidence inventory exceeds file-count bound")
    facts: list[dict[str, Any]] = []
    total = 0
    for relative in REPOSITORY_FILES:
        file_path = _safe_regular_file(checkout, relative)
        size = file_path.stat().st_size
        total += size
        facts.append({"path": relative, "bytes": size, "sha256": _sha256_bytes(file_path.read_bytes())})
    external = _safe_regular_file(frontend_root, EXTERNAL_FRONTEND_FILE)
    size = external.stat().st_size
    total += size
    facts.append({
        "path": "external-frontend/package-lock.json",
        "bytes": size,
        "sha256": _sha256_bytes(external.read_bytes()),
    })
    if total > MAX_BOUND_BYTES:
        raise EvidenceRefusal("closed evidence inventory exceeds byte bound")
    return facts, total


def collect_inventory(checkout: Path, frontend_root: Path) -> dict[str, Any]:
    backend = checkout / "paper-trader/backend"
    files, total_bytes = _bound_files(checkout, frontend_root)
    branch = _required_text(["git", "branch", "--show-current"], cwd=checkout)
    head = _required_text(["git", "rev-parse", "HEAD"], cwd=checkout)
    index_digest = _required_text(["git", "write-tree"], cwd=checkout)
    dirty = bool(_required_text(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"], cwd=checkout
    ))
    execution_head = _required_text([
        sys.executable, "-c", "from app.db.migrate import head_revision; print(head_revision())",
    ], cwd=backend)
    research_head = _required_text([
        sys.executable, "-c", "from research.domain.migrate import head_version; print(head_version())",
    ], cwd=backend)
    tools = [
        {"name": "python", "available": True, "version": sys.version.split()[0]},
        _tool_identity("node", ["node", "--version"], cwd=checkout),
        _tool_identity("npm", ["npm", "--version"], cwd=checkout),
        _postgres_identity(cwd=checkout),
    ]
    return {
        "schema": "strategy-os-v0-local-inventory/1",
        "git": {"branch": branch, "head": head, "index_digest": index_digest, "dirty": dirty},
        "tools": tools,
        "migration_heads": {"execution": execution_head, "research": research_head},
        "release_contract": {
            "profile": "v0_research_signal",
            "service_roles": ["api", "research_worker", "monitor", "scheduler"],
            "execution_worker": "absent",
            "live_authority": False,
        },
        "safe_configuration_presence": {
            key: key in os.environ for key in SAFE_CONFIGURATION_KEYS
        },
        "bound_files": files,
        "bounds": {
            "file_count": len(files), "total_bytes": total_bytes,
            "max_file_count": MAX_BOUND_FILES, "max_total_bytes": MAX_BOUND_BYTES,
        },
        "historical_release_blockers": list(HISTORICAL_RELEASE_BLOCKERS),
    }


def preflight_steps() -> tuple[Step, ...]:
    """Return the closed, reviewable subprocess plan.  No shell is involved."""
    return (
        Step("sqlite-profile-migration-restore", (
            "$PYTHON", "-m", "pytest", "-q",
            "tests/test_v0_release_profile.py",
            "tests/test_browser_auth_migration.py::test_sqlite_upgrade_interruption_restore_and_preservation",
            "tests/test_browser_auth_migration.py::test_partial_schema_and_destructive_downgrade_refuse",
            "tests/test_postgresql_restore_contract.py", "tests/test_restore_cli_preflight.py",
            "tests/test_restore_boot_gate.py",
        )),
        Step("research-0011-restart-resource-worker", (
            "$PYTHON", "-m", "pytest", "-q",
            "research_tests/test_foundation_direct_migration_0011.py::test_research_head_is_discovered_as_0011",
            "research_tests/test_foundation_direct_migration_0011.py::test_clean_sqlite_reaches_exact_0011_and_is_deterministic",
            "research_tests/test_foundation_direct_migration_0011.py::test_exact_populated_sqlite_0010_preserves_all_rows_sequences_and_bytes",
            "research_tests/test_foundation_direct_migration_0011.py::test_every_sqlite_immutable_guard_rejects_real_sql",
            "research_tests/test_foundation_direct_migration_0011.py::test_sqlite_secret_insert_guard_rejects_real_insert",
            "research_tests/test_foundation_direct_migration_0011.py::test_every_unsupported_sqlite_state_refuses_before_write_with_identical_digest",
            "research_tests/test_foundation_direct_migration_0011.py::test_sqlite_interruption_is_atomic_and_restart_is_deterministic",
            "tests/test_phase5_research_runtime_packaging.py::test_forced_death_reclaims_and_fences_old_claim",
            "tests/test_phase5_research_runtime_packaging.py::test_snapshot_restart_requires_no_active_claim_and_preserves_terminal_rows",
            "tests/test_phase5_research_runtime_packaging.py::test_worker_run_once_graceful_stop_and_handler_failure_are_safe",
            "tests/test_phase5_research_runtime_packaging.py::test_memory_disk_and_retention_refuse_first_above_bound",
            "tests/test_phase5_research_runtime_packaging.py::test_health_is_never_false_green_for_stale_execution_head",
            "tests/test_phase5_research_runtime_packaging.py::test_health_is_never_false_green_for_stale_research_head",
            "tests/test_phase5_research_runtime_packaging.py::test_ready_health_binds_real_heads_capacity_roles_and_dependencies",
            "tests/test_phase5_research_runtime_packaging.py::test_entrypoint_imports_no_provider_broker_order_live_or_deployment_path",
            QUERY_BUDGET_AUTHORITY,
        )),
        Step("postgresql16-three-plane-upgrade-restore", (
            "$PYTHON", "scripts/run_disposable_postgres.py", "--", "$PYTHON", "-m", "pytest", "-q",
            "tests/test_browser_auth_migration.py::test_pg16_upgrade_restore_concurrency",
            "tests/test_postgresql_restore_live.py::test_pg16_dump_restore_three_plane_generation_is_digest_identical",
            "research_tests/test_foundation_direct_migration_0011.py::test_clean_postgresql16_reaches_exact_0011_and_is_deterministic",
            "research_tests/test_foundation_direct_migration_0011.py::test_postgresql_interruption_rolls_back_and_restart_reaches_0011",
            "research_tests/test_foundation_direct_migration_0011.py::test_postgresql_version_only_marker_and_sqlite_cookie_contract",
        )),
    )


def _safe_environment(temp_root: Path) -> dict[str, str]:
    keep = ("PATH", "LANG", "LC_ALL", "TMPDIR", "USER", "LOGNAME", "SHELL")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env.update({
        "PT_DISABLE_DOTENV": "1", "PT_PROVIDER": "mock", "PT_EXECUTION": "paper",
        "PT_LIVE_ACK": "", "PT_PRODUCTION": "0", "PT_DATABASE_URL": "",
        "PT_RELEASE_PROFILE": "v0_research_signal", "PT_RELEASE_SERVICE_ROLE": "api",
        "PT_EXECUTION_WORKER": "api", "PT_RESEARCH_ENABLED": "1",
        "PT_EXECUTION_PROVIDER": "", "PT_EXECUTION_CONNECTION": "",
        "PT_EXECUTION_OWNER_ID": "", "PT_EXECUTION_BROKER_ACCOUNT_ID": "",
        "PT_EXECUTION_CELL_ID": "", "PT_DB_PATH": str(temp_root / "execution.sqlite"),
        "PT_LEDGER_DB_PATH": str(temp_root / "ledger.sqlite"),
        "PT_RESEARCH_DB_PATH": str(temp_root / "research.sqlite"),
        "PT_BACKTEST_DATASET_DIR": str(temp_root / "datasets"),
    })
    return env


def _resolve_argv(argv: Sequence[str]) -> list[str]:
    return [sys.executable if value == "$PYTHON" else value for value in argv]


def _resource_policy(timeout: int = DEFAULT_STEP_TIMEOUT_SECONDS) -> dict[str, Any]:
    return {
        "max_steps": len(preflight_steps()),
        "step_timeout_seconds": timeout,
        "max_output_bytes_per_step": MAX_STEP_OUTPUT_BYTES,
        "max_open_files": MAX_OPEN_FILES,
        "max_child_file_bytes": MAX_CHILD_FILE_BYTES,
        "max_child_memory_bytes": MAX_CHILD_MEMORY_BYTES,
        "memory_enforcement": "live POSIX ps process-tree RSS ceiling with group termination",
        "query_budget": {
            "cli_direct_database_queries": 0,
            "authority": QUERY_BUDGET_AUTHORITY,
            "max_statements": QUERY_BUDGET_STATEMENTS,
        },
        "network": "no provider or external network; disposable PG16 binds loopback only",
    }


def _limit_child_resources(timeout: int) -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout + 5))
    # PostgreSQL 16 creates 16 MiB WAL segments even for a tiny disposable cluster;
    # the file bound must cover that real storage contract rather than reuse the
    # much smaller captured-output bound.
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_CHILD_FILE_BYTES, MAX_CHILD_FILE_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (MAX_OPEN_FILES, MAX_OPEN_FILES))


def _process_tree_rss_bytes(root_pid: int) -> int:
    """Return live RSS for the exact child tree without adding a dependency."""
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,rss="], check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EvidenceRefusal("could not enforce the process-tree memory ceiling") from error
    if result.returncode != 0 or len(result.stdout) > 4 * 1024 * 1024:
        raise EvidenceRefusal("process-tree memory inventory failed or exceeded its bound")
    rows: dict[int, tuple[int, int]] = {}
    for raw in result.stdout.decode("ascii", errors="strict").splitlines():
        fields = raw.split()
        if len(fields) != 3:
            continue
        pid, parent, rss_kib = map(int, fields)
        rows[pid] = (parent, rss_kib)
    descendants = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, (parent, _rss) in rows.items():
            if parent in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True
    return sum(rows[pid][1] * 1024 for pid in descendants if pid in rows)


def _tracked_process_group_members(process_group_id: int) -> tuple[int, ...]:
    """Return members of the exact session/process group created by the runner."""
    if process_group_id <= 1:
        raise EvidenceRefusal("unsafe child process-group identity")
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,pgid="], check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise EvidenceRefusal("could not inspect the child process group") from error
    if result.returncode != 0 or len(result.stdout) > 4 * 1024 * 1024:
        raise EvidenceRefusal("child process-group inventory failed or exceeded its bound")
    members: list[int] = []
    for raw in result.stdout.decode("ascii", errors="strict").splitlines():
        fields = raw.split()
        if len(fields) != 2:
            continue
        pid, group_id = map(int, fields)
        if group_id != process_group_id:
            continue
        try:
            session_id = os.getsid(pid)
        except ProcessLookupError:
            continue
        if session_id != process_group_id:
            raise EvidenceRefusal("child process-group identity no longer matches its session")
        members.append(pid)
    return tuple(members)


def _wait_process_group_empty(process: subprocess.Popen[bytes], timeout: float) -> bool:
    process_group_id = process.pid
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        process.poll()
        if not _tracked_process_group_members(process_group_id):
            return True
        time.sleep(0.02)
    process.poll()
    return not _tracked_process_group_members(process_group_id)


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    """Bounded TERM→KILL of the exact session created for one evidence step."""
    process_group_id = process.pid
    if not _tracked_process_group_members(process_group_id):
        return
    try:
        os.killpg(process_group_id, signal.SIGTERM)
    except ProcessLookupError:
        return
    if _wait_process_group_empty(process, 2):
        process.wait(timeout=2)
        return
    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except ProcessLookupError:
        return
    if not _wait_process_group_empty(process, 2):
        raise EvidenceRefusal("child process group did not terminate after SIGKILL")
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired as error:
        raise EvidenceRefusal("child process group did not terminate after SIGKILL") from error


def _normalise_evidence_output(value: bytes, *, checkout: Path) -> bytes:
    """Remove local path/port/PID/time noise while retaining assertion output."""
    text = value.decode("utf-8", errors="replace")
    text = text.replace(str(checkout), "$CHECKOUT")
    patterns = (
        (r"/(?:private/)?var/folders/[^\s'\"]+/(?:strategy-os-postgres|pytest-of-)[^\s'\"]+", "$LOCAL_TMP"),
        (r"/tmp/(?:strategy-os-postgres|pytest-of-)[^\s'\"]+", "$LOCAL_TMP"),
        (r"pt_harness_[0-9a-f]{32}", "$PG_DATABASE"),
        (r"127\.0\.0\.1:\d{2,5}", "127.0.0.1:$PORT"),
        (r"port \d{2,5}", "port $PORT"),
        (r"\.s\.PGSQL\.\d{2,5}", ".s.PGSQL.$PORT"),
        (r"\[\d{2,8}\]", "[$PID]"),
        (r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)? [A-Z]{2,5}", "$TIMESTAMP"),
        (r"in \d+(?:\.\d+)?s", "in $SECONDS"),
    )
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    text = re.sub(
        r"\$TIMESTAMP \[\$PID\] LOG:  checkpoint complete:.*",
        "$TIMESTAMP [$PID] LOG:  checkpoint complete: $LOCAL_METRICS",
        text,
    )
    return text.encode("utf-8")


def _seal_stream_artifact(
    raw_path: Path, final_path: Path, *, checkout: Path,
) -> dict[str, Any]:
    data = _normalise_evidence_output(raw_path.read_bytes(), checkout=checkout)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".step-output-", dir=final_path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, final_path)
    finally:
        temporary.unlink(missing_ok=True)
        raw_path.unlink(missing_ok=True)
    return {
        "file": final_path.name,
        "bytes": len(data),
        "sha256": _sha256_bytes(data),
    }


def _artifact_names(index: int, label: str) -> tuple[str, str]:
    if not re.fullmatch(r"[a-z0-9-]+", label):
        raise EvidenceRefusal("unsafe step label")
    prefix = f"{index:02d}-{label}"
    return f"{prefix}.stdout.log", f"{prefix}.stderr.log"


def run_step(
    step: Step, *, backend: Path, env: Mapping[str, str], timeout: int,
    artifact_root: Path, step_index: int,
    popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Run one exact argv with bounded streaming evidence and group cleanup."""
    if timeout != DEFAULT_STEP_TIMEOUT_SECONDS:
        raise EvidenceRefusal("step timeout differs from the closed preflight contract")
    stdout_name, stderr_name = _artifact_names(step_index, step.label)
    stdout_raw = artifact_root / f".{stdout_name}.raw"
    stderr_raw = artifact_root / f".{stderr_name}.raw"
    stdout_path = artifact_root / stdout_name
    stderr_path = artifact_root / stderr_name
    if any(path.exists() for path in (stdout_raw, stderr_raw, stdout_path, stderr_path)):
        raise EvidenceRefusal("step artifact path already exists")

    resolved = _resolve_argv(step.argv)
    try:
        process = popen(
            resolved, cwd=backend, env=dict(env), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True,
            preexec_fn=lambda: _limit_child_resources(timeout),
        )
    except OSError as error:
        raise EvidenceRefusal(f"could not launch preflight step: {step.label}") from error
    if process.stdout is None or process.stderr is None:
        _terminate_process_group(process)
        raise EvidenceRefusal("preflight child pipes were not created")

    lock = threading.Lock()
    total = 0
    overflow = threading.Event()

    def pump(source: Any, target: Path) -> None:
        nonlocal total
        with target.open("xb") as handle:
            while True:
                chunk = source.read(STREAM_CHUNK_BYTES)
                if not chunk:
                    return
                with lock:
                    remaining = MAX_STEP_OUTPUT_BYTES - total
                    accepted = chunk[:max(0, remaining)]
                    total += len(accepted)
                    if len(accepted) != len(chunk):
                        overflow.set()
                if accepted:
                    handle.write(accepted)
                    handle.flush()
                if overflow.is_set():
                    return

    threads = (
        threading.Thread(target=pump, args=(process.stdout, stdout_raw), daemon=True),
        threading.Thread(target=pump, args=(process.stderr, stderr_raw), daemon=True),
    )
    for thread in threads:
        thread.start()

    deadline = monotonic() + timeout
    next_memory_check = monotonic()
    termination = "completed"
    interrupted = False
    try:
        while process.poll() is None:
            if overflow.is_set():
                termination = "output_overflow"
                _terminate_process_group(process)
                break
            now = monotonic()
            if now >= next_memory_check:
                if _process_tree_rss_bytes(process.pid) > MAX_CHILD_MEMORY_BYTES:
                    termination = "memory_overflow"
                    _terminate_process_group(process)
                    break
                next_memory_check = now + 0.25
            if now >= deadline:
                termination = "timeout"
                _terminate_process_group(process)
                break
            time.sleep(0.02)
    except KeyboardInterrupt:
        interrupted = True
        termination = "interrupted"
        _terminate_process_group(process)
    finally:
        if process.poll() is None:
            _terminate_process_group(process)
        for thread in threads:
            thread.join(timeout=5)
        if any(thread.is_alive() for thread in threads):
            raise EvidenceRefusal("output capture thread did not terminate")
        process.stdout.close()
        process.stderr.close()

    if termination == "completed" and overflow.is_set():
        termination = "output_overflow"
        _terminate_process_group(process)

    checkout = backend.parents[1]
    artifacts = {
        "stdout": _seal_stream_artifact(stdout_raw, stdout_path, checkout=checkout),
        "stderr": _seal_stream_artifact(stderr_raw, stderr_path, checkout=checkout),
    }
    returncode = (
        130 if interrupted else 126 if termination == "memory_overflow"
        else 125 if termination == "output_overflow"
        else 124 if termination == "timeout" else int(process.returncode)
    )
    outcome = {
        "label": step.label,
        "argv": list(step.argv),
        "returncode": returncode,
        "timeout_seconds": timeout,
        "termination": termination,
        "artifacts": artifacts,
    }
    outcome["result_address"] = _address(outcome)
    if interrupted:
        raise StepInterrupted(outcome)
    return outcome


def _claims(status: str) -> dict[str, Any]:
    return {
        "highest_readiness_level": "locally_runnable" if status == "PASS" else "none",
        "local_evidence_interface": status == "PASS",
        "release_deployable": False, "production_rehearsed": False, "deployed": False,
        "provider_approved": False, "legally_approved": False, "v0_complete": False,
    }


def _receipt(answer: dict[str, Any], observed_at: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "observed_at": observed_at, "answer": answer,
        "answer_address": _address(answer),
        "integrity": {"algorithm": "sha256", "status": "unsigned-local"},
    }


def _atomic_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    encoded = _canonical_json(receipt) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".v0-evidence-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def inventory_command(args: argparse.Namespace) -> int:
    checkout = _safe_root(args.checkout_root, name="checkout root", must_exist=True)
    frontend = _safe_root(args.frontend_root, name="frontend root", must_exist=True)
    output_root = _safe_root(args.output_root, name="output root", must_exist=False)
    target = _validate_output(checkout, output_root, args.output_name)
    inventory = collect_inventory(checkout, frontend)
    answer = {
        "schema": ANSWER_SCHEMA, "kind": "inventory", "status": "PASS",
        "inventory": inventory, "claims": _claims("INVENTORY_ONLY"),
    }
    _atomic_receipt(target, _receipt(answer, args.observed_at))
    return 0


def preflight_command(args: argparse.Namespace) -> int:
    checkout = _safe_root(args.checkout_root, name="checkout root", must_exist=True)
    frontend = _safe_root(args.frontend_root, name="frontend root", must_exist=True)
    output_root = _safe_root(args.output_root, name="output root", must_exist=False)
    target = _validate_output(checkout, output_root, args.output_name)
    artifact_root = target.parent / f"{target.stem}.artifacts"
    if artifact_root.exists() or artifact_root.is_symlink():
        raise EvidenceRefusal("preflight artifact directory already exists; retry in a new output")
    artifact_root.mkdir(mode=0o700)
    inventory = collect_inventory(checkout, frontend)
    results: list[dict[str, Any]] = []
    attempted: str | None = None
    attempted_result: dict[str, Any] | None = None
    status = "PASS"
    with tempfile.TemporaryDirectory(prefix="strategy-os-v0-local-evidence-") as temp:
        env = _safe_environment(Path(temp))
        try:
            for index, step in enumerate(preflight_steps()):
                attempted = step.label
                result = run_step(
                    step, backend=checkout / "paper-trader/backend", env=env,
                    timeout=args.step_timeout, artifact_root=artifact_root,
                    step_index=index,
                )
                results.append(result)
                if result["returncode"] != 0:
                    status = "FAIL"
                    break
        except StepInterrupted as interrupted:
            attempted_result = interrupted.result
            status = "INCOMPLETE"
    answer = {
        "schema": ANSWER_SCHEMA, "kind": "preflight", "status": status,
        "inventory": inventory, "steps": results, "attempted_step": attempted,
        "attempted_result": attempted_result,
        "resource_policy": _resource_policy(args.step_timeout),
        "claims": _claims(status),
    }
    _atomic_receipt(target, _receipt(answer, args.observed_at))
    return 0 if status == "PASS" else (130 if status == "INCOMPLETE" else 1)


def _strict_keys(value: Mapping[str, Any], expected: set[str], where: str) -> None:
    if set(value) != expected:
        raise EvidenceRefusal(f"{where} has missing or extra fields")


def _verify_artifact(
    receipt_path: Path, artifact: Mapping[str, Any], *, expected_file: str,
) -> None:
    _strict_keys(artifact, {"file", "bytes", "sha256"}, "step artifact")
    if artifact["file"] != expected_file:
        raise EvidenceRefusal("step artifact filename differs from the closed contract")
    artifact_root = receipt_path.parent / f"{receipt_path.stem}.artifacts"
    if not artifact_root.is_dir() or artifact_root.is_symlink():
        raise EvidenceRefusal("step artifact directory is missing or unsafe")
    path = _safe_regular_file(artifact_root, expected_file)
    data = path.read_bytes()
    if len(data) != artifact["bytes"] or _sha256_bytes(data) != artifact["sha256"]:
        raise EvidenceRefusal("retained step artifact bytes or digest changed")


def _validate_step(
    step: Mapping[str, Any], *, expected: Step, timeout: int, index: int,
    receipt_path: Path,
) -> None:
    expected_keys = {
        "label", "argv", "returncode", "timeout_seconds", "termination",
        "artifacts", "result_address",
    }
    _strict_keys(step, expected_keys, "step result")
    body = {key: step[key] for key in expected_keys - {"result_address"}}
    if step["result_address"] != _address(body):
        raise EvidenceRefusal("step result digest changed")
    if step["label"] != expected.label or step["argv"] != list(expected.argv):
        raise EvidenceRefusal("step argv, label, or order differs from the closed contract")
    if step["timeout_seconds"] != timeout:
        raise EvidenceRefusal("step timeout differs from the closed contract")
    if step["termination"] not in {
        "completed", "timeout", "output_overflow", "memory_overflow", "interrupted"
    }:
        raise EvidenceRefusal("unknown step termination state")
    artifacts = step["artifacts"]
    if not isinstance(artifacts, Mapping):
        raise EvidenceRefusal("step artifacts must be an object")
    _strict_keys(artifacts, {"stdout", "stderr"}, "step artifacts")
    stdout_name, stderr_name = _artifact_names(index, expected.label)
    for stream, file_name in (("stdout", stdout_name), ("stderr", stderr_name)):
        if not isinstance(artifacts[stream], Mapping):
            raise EvidenceRefusal("step artifact must be an object")
        _verify_artifact(receipt_path, artifacts[stream], expected_file=file_name)


def _validate_preflight_semantics(answer: Mapping[str, Any], receipt_path: Path) -> None:
    declared = preflight_steps()
    timeout = DEFAULT_STEP_TIMEOUT_SECONDS
    if answer["resource_policy"] != _resource_policy(timeout):
        raise EvidenceRefusal("preflight resource or query policy differs from the closed contract")
    status = answer["status"]
    if status not in {"PASS", "FAIL", "INCOMPLETE"}:
        raise EvidenceRefusal("unknown preflight status")
    if answer["claims"] != _claims(status):
        raise EvidenceRefusal("readiness claims differ from the closed status contract")
    steps = answer["steps"]
    if not isinstance(steps, list) or len(steps) > len(declared):
        raise EvidenceRefusal("invalid preflight step count")
    for index, result in enumerate(steps):
        if not isinstance(result, Mapping):
            raise EvidenceRefusal("step result must be an object")
        _validate_step(
            result, expected=declared[index], timeout=timeout, index=index,
            receipt_path=receipt_path,
        )

    attempted = answer["attempted_step"]
    attempted_result = answer["attempted_result"]
    if status == "PASS":
        if len(steps) != len(declared) or attempted != declared[-1].label or attempted_result is not None:
            raise EvidenceRefusal("PASS attempted-step or count semantics changed")
        if any(item["returncode"] != 0 or item["termination"] != "completed" for item in steps):
            raise EvidenceRefusal("failed, bounded, or interrupted step cannot produce PASS")
    elif status == "FAIL":
        if not steps or attempted_result is not None or attempted != declared[len(steps) - 1].label:
            raise EvidenceRefusal("FAIL attempted-step semantics changed")
        if any(item["returncode"] != 0 or item["termination"] != "completed" for item in steps[:-1]):
            raise EvidenceRefusal("FAIL contains an earlier unsuccessful step")
        last = steps[-1]
        if last["returncode"] == 0 or last["termination"] == "interrupted":
            raise EvidenceRefusal("FAIL does not end in one failed completed/timeout/overflow step")
        if last["termination"] == "timeout" and last["returncode"] != 124:
            raise EvidenceRefusal("timeout result code changed")
        if last["termination"] == "output_overflow" and last["returncode"] != 125:
            raise EvidenceRefusal("overflow result code changed")
        if last["termination"] == "memory_overflow" and last["returncode"] != 126:
            raise EvidenceRefusal("memory-overflow result code changed")
    else:
        if len(steps) >= len(declared) or attempted != declared[len(steps)].label:
            raise EvidenceRefusal("INCOMPLETE attempted-step semantics changed")
        if any(item["returncode"] != 0 or item["termination"] != "completed" for item in steps):
            raise EvidenceRefusal("INCOMPLETE contains an unsuccessful completed step")
        if not isinstance(attempted_result, Mapping):
            raise EvidenceRefusal("INCOMPLETE must retain the interrupted result artifacts")
        _validate_step(
            attempted_result, expected=declared[len(steps)], timeout=timeout,
            index=len(steps), receipt_path=receipt_path,
        )
        if attempted_result["returncode"] != 130 or attempted_result["termination"] != "interrupted":
            raise EvidenceRefusal("INCOMPLETE result is not an interrupted child group")

    expected_files: set[str] = set()
    result_records = list(steps)
    if isinstance(attempted_result, Mapping):
        result_records.append(attempted_result)
    for record in result_records:
        expected_files.update(
            artifact["file"] for artifact in record["artifacts"].values()
        )
    artifact_root = receipt_path.parent / f"{receipt_path.stem}.artifacts"
    actual_files = {
        item.name for item in artifact_root.iterdir()
        if item.is_file() and not item.is_symlink()
    }
    if actual_files != expected_files:
        raise EvidenceRefusal("retained result artifact set has missing or extra files")


def _recompute_bound_files(
    inventory: Mapping[str, Any], checkout: Path, frontend: Path,
) -> None:
    expected_files, total = _bound_files(checkout, frontend)
    if inventory.get("bound_files") != expected_files:
        raise EvidenceRefusal("a bound source, lock, migration, operation, or test file changed")
    bounds = inventory.get("bounds")
    if not isinstance(bounds, Mapping) or bounds.get("total_bytes") != total:
        raise EvidenceRefusal("bound file totals changed")


def verify_receipt_command(args: argparse.Namespace) -> int:
    checkout = _safe_root(args.checkout_root, name="checkout root", must_exist=True)
    frontend = _safe_root(args.frontend_root, name="frontend root", must_exist=True)
    receipt_path = Path(args.receipt)
    if not receipt_path.is_absolute() or receipt_path.is_symlink():
        raise EvidenceRefusal("receipt must be an explicit non-symlink absolute path")
    if not receipt_path.is_file() or not stat.S_ISREG(receipt_path.stat().st_mode):
        raise EvidenceRefusal("receipt must be a regular file")
    if receipt_path.stat().st_size > MAX_STEP_OUTPUT_BYTES:
        raise EvidenceRefusal("receipt exceeds byte bound")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceRefusal("receipt is truncated or not strict JSON") from error
    if not isinstance(receipt, dict):
        raise EvidenceRefusal("receipt must be an object")
    _strict_keys(receipt, {"schema", "observed_at", "answer", "answer_address", "integrity"}, "receipt")
    if receipt["schema"] != SCHEMA or receipt["answer_address"] != _address(receipt["answer"]):
        raise EvidenceRefusal("receipt answer digest changed")
    if receipt["integrity"] != {"algorithm": "sha256", "status": "unsigned-local"}:
        raise EvidenceRefusal("unknown receipt integrity state")
    if args.require_signed:
        raise EvidenceRefusal("this local evidence slice has no signing-key lifecycle")
    answer = receipt["answer"]
    if not isinstance(answer, dict) or answer.get("schema") != ANSWER_SCHEMA:
        raise EvidenceRefusal("unknown answer schema")
    kind = answer.get("kind")
    if kind == "inventory":
        _strict_keys(answer, {"schema", "kind", "status", "inventory", "claims"}, "inventory answer")
        if answer["status"] != "PASS" or answer["claims"] != _claims("INVENTORY_ONLY"):
            raise EvidenceRefusal("inventory status or claims differ from the closed contract")
    elif kind == "preflight":
        _strict_keys(answer, {
            "schema", "kind", "status", "inventory", "steps", "attempted_step",
            "attempted_result", "resource_policy", "claims",
        }, "preflight answer")
        _validate_preflight_semantics(answer, receipt_path)
    else:
        raise EvidenceRefusal("unknown receipt kind")
    inventory = answer["inventory"]
    if not isinstance(inventory, dict):
        raise EvidenceRefusal("inventory must be an object")
    _recompute_bound_files(inventory, checkout, frontend)
    current = collect_inventory(checkout, frontend)
    if inventory != current:
        raise EvidenceRefusal("inventory facts changed after receipt creation")
    print(_canonical_json({
        "schema": "strategy-os-v0-local-release-verification/1",
        "answer_address": receipt["answer_address"], "verified": True,
        "authenticity": "UNPROVEN", "deployment_authority": False,
    }))
    return 0


def _observed_at(value: str | None) -> str:
    if value:
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise argparse.ArgumentTypeError("observed-at must be an ISO-8601 timestamp") from error
        if parsed.tzinfo is None:
            raise argparse.ArgumentTypeError("observed-at must include an offset")
        return value
    return dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("inventory", "preflight"):
        child = subparsers.add_parser(name)
        child.add_argument("--checkout-root", required=True)
        child.add_argument("--frontend-root", required=True)
        child.add_argument("--output-root", required=True)
        child.add_argument("--output-name", default=f"{name}.json")
        child.add_argument("--observed-at", type=_observed_at, default=_observed_at(None))
        if name == "preflight":
            child.add_argument(
                "--step-timeout", type=int, default=DEFAULT_STEP_TIMEOUT_SECONDS,
                choices=(DEFAULT_STEP_TIMEOUT_SECONDS,), metavar="900",
            )
    verify = subparsers.add_parser("verify-receipt")
    verify.add_argument("--checkout-root", required=True)
    verify.add_argument("--frontend-root", required=True)
    verify.add_argument("--receipt", required=True)
    verify.add_argument("--require-signed", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "inventory":
            return inventory_command(args)
        if args.command == "preflight":
            return preflight_command(args)
        return verify_receipt_command(args)
    except EvidenceRefusal as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
