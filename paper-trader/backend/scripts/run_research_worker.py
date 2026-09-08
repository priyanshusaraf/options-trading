#!/usr/bin/env python3
"""Safe production-shaped local research worker; never a deployment script."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


BACKEND = Path(__file__).resolve().parents[1]
_CREDENTIAL_ENV = (
    "KITE_API_KEY", "KITE_API_SECRET", "KITE_ACCESS_TOKEN",
    "DHAN_CLIENT_ID", "DHAN_ACCESS_TOKEN", "UPSTOX_ACCESS_TOKEN",
)
_MINIMUM_PROCESS_MEMORY = 256 * 1024 * 1024


class WorkerBootstrapRefusal(RuntimeError):
    pass


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--health", action="store_true")
    result.add_argument("--once", action="store_true")
    result.add_argument("--submit-json")
    result.add_argument("--state-dir")
    result.add_argument("--execution-database")
    result.add_argument("--execution-database-url")
    result.add_argument("--research-database-url")
    result.add_argument("--owner-id", default="local-owner")
    result.add_argument("--worker-id", default="local-research-worker")
    result.add_argument("--queue-depth", type=int, default=8)
    result.add_argument("--concurrency", type=int, default=1)
    result.add_argument("--maximum-attempts", type=int, default=3)
    result.add_argument("--cache-bytes", type=int, default=8 * 1024 * 1024)
    result.add_argument("--artifact-bytes", type=int, default=2 * 1024 * 1024)
    result.add_argument("--database-connections", type=int, default=2)
    result.add_argument("--memory-bytes", type=int, default=4 * 1024 * 1024 * 1024)
    result.add_argument("--memory-probe-bytes", type=int)
    result.add_argument("--disk-bytes", type=int, default=8 * 1024 * 1024)
    result.add_argument("--retention-entries", type=int, default=128)
    result.add_argument("--supervised-child", action="store_true", help=argparse.SUPPRESS)
    return result


def _safe_local_environment() -> None:
    if os.environ.get("PT_LIVE_TRADING", "").lower() in {"1", "true", "yes"}:
        raise WorkerBootstrapRefusal("local research worker refuses live trading")
    if os.environ.get("PT_PRODUCTION", "").lower() in {"1", "true", "yes"}:
        raise WorkerBootstrapRefusal("local research worker refuses production mode")
    if os.environ.get("PT_PROVIDER", "mock").lower() != "mock":
        raise WorkerBootstrapRefusal("local research worker requires mock provider")
    os.environ.update({name: "" for name in _CREDENTIAL_ENV})
    os.environ.update({
        "PT_PROVIDER": "mock", "PT_EXECUTION": "paper", "PT_LIVE_ACK": "",
        "PT_PRODUCTION": "0", "PT_LIVE_TRADING": "0", "PT_DISABLE_DOTENV": "1",
    })


def _descendant_rss_bytes(root_pid: int) -> int:
    result = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,rss="], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    if result.returncode != 0:
        raise WorkerBootstrapRefusal("worker memory supervisor cannot inspect processes")
    children: dict[int, list[tuple[int, int]]] = {}
    for line in result.stdout.splitlines():
        try:
            pid_text, parent_text, rss_text = line.split()
            children.setdefault(int(parent_text), []).append((int(pid_text), int(rss_text)))
        except (TypeError, ValueError):
            continue
    pending, seen, total_kib = [root_pid], set(), 0
    while pending:
        parent = pending.pop()
        for pid, rss_kib in children.get(parent, ()):
            if pid in seen:
                continue
            seen.add(pid); total_kib += rss_kib; pending.append(pid)
    return total_kib * 1024


def _supervise(argv: list[str], args) -> int:
    if type(args.memory_bytes) is not int or args.memory_bytes < _MINIMUM_PROCESS_MEMORY:
        raise WorkerBootstrapRefusal(
            f"worker aggregate memory bound must be at least {_MINIMUM_PROCESS_MEMORY}"
        )
    command = [sys.executable, str(Path(__file__).resolve()), "--supervised-child", *argv]
    environment = {
        **os.environ,
        "PT_WORKER_MEMORY_LIMIT_BYTES": str(args.memory_bytes),
        "PT_WORKER_SUPERVISOR_PID": str(os.getpid()),
    }
    child = subprocess.Popen(
        command, cwd=BACKEND, env=environment, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
    )
    forwarded = {"signal": None}

    def forward(signum, _frame):
        forwarded["signal"] = int(signum)
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    previous = {
        signum: signal.signal(signum, forward)
        for signum in (signal.SIGTERM, signal.SIGINT)
    }
    peak = 0
    try:
        while child.poll() is None:
            measured = _descendant_rss_bytes(os.getpid())
            peak = max(peak, measured)
            if measured > args.memory_bytes:
                os.killpg(child.pid, signal.SIGKILL)
                stdout, stderr = child.communicate(timeout=10)
                if stderr:
                    sys.stderr.write(stderr)
                print(json.dumps({
                    "schema": "research-worker-supervisor/1",
                    "status": "MEMORY_REFUSED",
                    "limit_bytes": args.memory_bytes,
                    "observed_bytes": measured,
                    "peak_bytes": peak,
                }, sort_keys=True))
                return 75
            time.sleep(0.02)
        stdout, stderr = child.communicate(timeout=10)
        if stdout:
            sys.stdout.write(stdout)
        if stderr:
            sys.stderr.write(stderr)
        return int(child.returncode or 0)
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _state_root(value: str | None) -> tuple[Path, tempfile.TemporaryDirectory | None]:
    if value is None:
        temporary = tempfile.TemporaryDirectory(prefix="strategy-os-phase5-worker-")
        return Path(temporary.name), temporary
    root = Path(value).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root, None


def _safe_postgresql_url(url, make_url) -> None:
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        return
    if parsed.host not in {"127.0.0.1", "localhost"} \
            or not str(parsed.database or "").startswith("pt_sandbox_"):
        raise WorkerBootstrapRefusal(
            "local research worker requires a loopback disposable PostgreSQL sandbox"
        )


def _bounded_engine(authority: str, *, connections: int, sqlalchemy):
    make_url = sqlalchemy.engine.make_url
    parsed = make_url(authority)
    backend = parsed.get_backend_name()
    if backend not in {"sqlite", "postgresql"}:
        raise WorkerBootstrapRefusal("worker database must use SQLite or PostgreSQL")
    _safe_postgresql_url(authority, make_url)
    options = {
        "future": True, "pool_pre_ping": True,
        "pool_size": connections, "max_overflow": 0, "pool_timeout": 1,
    }
    if backend == "sqlite":
        options["connect_args"] = {"check_same_thread": False}
    engine = sqlalchemy.create_engine(authority, **options)
    if backend == "sqlite":
        @sqlalchemy.event.listens_for(engine, "connect")
        def _configure(dbapi_connection, _record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()
    return engine


def runtime(args):
    from importlib import import_module
    sqlalchemy = import_module("sqlalchemy")
    sessionmaker = import_module("sqlalchemy.orm").sessionmaker
    artifacts = import_module("app.backtest.artifacts")
    worker_contract = import_module("app.backtest.worker")

    root, temporary = _state_root(args.state_dir)
    if args.execution_database and args.execution_database_url:
        raise WorkerBootstrapRefusal("execution database path and URL are mutually exclusive")
    execution_url = args.execution_database_url or (
        f"sqlite:///{Path(args.execution_database).resolve()}"
        if args.execution_database else f"sqlite:///{root / 'execution.db'}"
    )
    research_url = args.research_database_url or f"sqlite:///{root / 'research.db'}"
    os.environ.update({
        "PT_DATABASE_URL": execution_url,
        "PT_RESEARCH_DATABASE_URL": research_url,
        "PT_BACKTEST_DATASET_DIR": str(root / "datasets"),
    })
    limits = worker_contract.ResearchWorkerLimits(
        queue_depth=args.queue_depth, concurrency=args.concurrency,
        maximum_attempts=args.maximum_attempts,
        cache_bytes=args.cache_bytes, artifact_bytes=args.artifact_bytes,
        database_connections=args.database_connections,
        memory_bytes=args.memory_bytes, disk_bytes=args.disk_bytes,
        retention_entries=args.retention_entries,
    )
    execution_engine = _bounded_engine(
        execution_url, connections=limits.database_connections,
        sqlalchemy=sqlalchemy,
    )
    research_engine = _bounded_engine(
        research_url, connections=limits.database_connections,
        sqlalchemy=sqlalchemy,
    )

    db_session = import_module("app.db.session")
    old_engine = db_session.engine
    db_session.engine = execution_engine
    db_session.SessionLocal = sessionmaker(
        bind=execution_engine, future=True, expire_on_commit=False,
    )
    old_engine.dispose()
    db_models = import_module("app.db.models")
    db_migrate = import_module("app.db.migrate")
    if not sqlalchemy.inspect(execution_engine).get_table_names():
        db_migrate.init_schema(
            execution_engine,
            create_all=lambda: db_models.Base.metadata.create_all(execution_engine),
            legacy_migrate=lambda: (_ for _ in ()).throw(
                WorkerBootstrapRefusal("legacy database adoption is unavailable")
            ),
            expected_tables=db_models.Base.metadata.tables,
        )
    import_module("research.domain.base").init_research_db(research_engine)

    sweep = import_module("app.backtest.sweep")
    artifact_store = artifacts.BoundedResearchArtifactStore(
        owner_id=args.owner_id, licence_scope="OWNER_PRIVATE",
        cache_bytes_upper_bound=limits.cache_bytes,
        artifact_bytes_upper_bound=limits.artifact_bytes,
        entry_upper_bound=limits.retention_entries,
        concurrency_upper_bound=limits.concurrency,
        queue_depth_upper_bound=limits.queue_depth,
    )
    observations = worker_contract.BoundedWorkerObservationStore(
        root=root / "observations",
        disk_bytes_upper_bound=limits.disk_bytes,
        retention_upper_bound=limits.retention_entries,
    )
    lock = worker_contract.verify_locked_environment(BACKEND / "requirements.lock")
    build = worker_contract.research_worker_build_address(lock, source_paths=(
        BACKEND / "app/backtest/worker.py",
        BACKEND / "app/backtest/artifacts.py",
        Path(__file__),
    ))
    worker = worker_contract.ResearchWorkerRuntime(
        worker_id=args.worker_id,
        queue=worker_contract.BoundedLocalResearchQueue(
            depth_upper_bound=limits.queue_depth,
            maximum_attempts=limits.maximum_attempts,
        ),
        limits=limits, build_address=build,
        dependencies=worker_contract.ResearchWorkerDependencies(
            execution_engine=execution_engine, research_engine=research_engine,
            artifact_store=artifact_store,
            durable_dispatch=sweep.dispatch_all_reclaimable,
            durable_wait=sweep._join,
            api_submit=worker_contract.submit_durable_research_request,
        ),
        observations=observations,
    )
    worker._temporary_state = temporary  # type: ignore[attr-defined]
    worker._canonical_sweep = sweep  # type: ignore[attr-defined]
    worker._sessionmaker = sessionmaker  # type: ignore[attr-defined]
    return worker


def _plain(value):
    if hasattr(value, "items"):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    args = parser().parse_args(arguments)
    _safe_local_environment()
    if not args.supervised_child:
        return _supervise(arguments, args)
    if args.once and args.submit_json is not None:
        raise WorkerBootstrapRefusal("API and worker roles require separate processes")
    worker = runtime(args)
    terminating = {"requested": False, "signal": None}

    def request_stop(signum, _frame):
        terminating.update({"requested": True, "signal": int(signum)})
        worker.stop()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    submitted_run_id = None
    if args.submit_json is not None:
        request = json.loads(args.submit_json)
        with worker._sessionmaker(
            bind=worker.dependencies.execution_engine, future=True,
            expire_on_commit=False,
        )() as session:
            submitted_run_id = worker.dependencies.api_submit(
                session, owner_id=args.owner_id, request=request,
                limits=worker.limits,
            )
    memory_probe = None
    if args.memory_probe_bytes is not None:
        try:
            allocation = bytearray(args.memory_probe_bytes)
            memory_probe = {"status": "PASS", "bytes": len(allocation)}
        except MemoryError:
            memory_probe = {"status": "REFUSED", "bytes": args.memory_probe_bytes}
    launched = worker.run_durable_once() if args.once else ()
    health = worker.health()
    document = {
        **_plain(health), "launched_run_ids": list(launched),
        "submitted_run_id": submitted_run_id,
        "memory_probe": memory_probe,
        "termination_requested": terminating["requested"],
        "termination_signal": terminating["signal"],
    }
    if args.health or args.submit_json is not None or not args.once:
        print(json.dumps(document, sort_keys=True))
    if terminating["requested"] and health["status"] == "STOPPING":
        return 0
    return 0 if health["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
