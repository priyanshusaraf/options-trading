"""Reproducible, bounded local research-worker packaging contracts."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import platform
from pathlib import Path
import sys
import threading
from types import MappingProxyType
from typing import Any, Callable, Mapping

from app.backtest.artifacts import (
    BoundedResearchArtifactStore,
    MaterializedArtifact,
    ResearchArtifactRefusal,
    research_cache_identity,
)
from app.ir.hashing import content_address


class ResearchWorkerRefusal(RuntimeError):
    pass


WORKER_ROLES = ("API", "ARTIFACT", "CACHE", "QUEUE", "RESEARCH_WORKER")


@dataclass(frozen=True)
class LockedEnvironment:
    requirements: Mapping[str, str]
    lock_address: str


def verify_locked_environment(path: str | Path) -> LockedEnvironment:
    path = Path(path)
    try: raw = path.read_bytes()
    except OSError as exc: raise ResearchWorkerRefusal("worker lock is unavailable") from exc
    requirements: dict[str, str] = {}
    for line in raw.decode().splitlines():
        value = line.split("#", 1)[0].strip()
        if not value: continue
        if value.count("==") != 1:
            raise ResearchWorkerRefusal("worker lock contains a mutable requirement")
        name, expected = value.split("==")
        normalized = name.strip().lower().replace("_", "-")
        if not normalized or not expected or normalized in requirements:
            raise ResearchWorkerRefusal("worker lock contains a duplicate requirement")
        try: actual = version(normalized)
        except PackageNotFoundError as exc:
            raise ResearchWorkerRefusal(f"locked package is absent: {normalized}") from exc
        if actual != expected:
            raise ResearchWorkerRefusal(
                f"locked package differs: {normalized} expected {expected} actual {actual}"
            )
        requirements[normalized] = expected
    if not requirements:
        raise ResearchWorkerRefusal("worker lock is empty")
    return LockedEnvironment(
        MappingProxyType(dict(sorted(requirements.items()))),
        "sha256:" + hashlib.sha256(raw).hexdigest(),
    )


def research_worker_build_address(
    lock: LockedEnvironment, *, source_paths: tuple[str | Path, ...],
) -> str:
    sources = []
    for value in sorted(Path(item).resolve() for item in source_paths):
        try: digest = "sha256:" + hashlib.sha256(value.read_bytes()).hexdigest()
        except OSError as exc: raise ResearchWorkerRefusal("worker source is unavailable") from exc
        sources.append({"name": value.name, "sha256": digest})
    if not sources:
        raise ResearchWorkerRefusal("worker build has no source closure")
    return content_address({
        "schema": "research-worker-build/2",
        "lock_address": lock.lock_address,
        "runtime": {
            "implementation": sys.implementation.name,
            "python": platform.python_version(),
            "platform": platform.system().lower(),
            "machine": platform.machine().lower(),
        },
        "sources": sources,
    })


@dataclass(frozen=True)
class ResearchWorkerLimits:
    queue_depth: int
    concurrency: int
    maximum_attempts: int
    cache_bytes: int
    artifact_bytes: int
    database_connections: int
    memory_bytes: int
    disk_bytes: int
    retention_entries: int

    def __post_init__(self) -> None:
        for name in (
            "queue_depth", "concurrency", "maximum_attempts", "cache_bytes",
            "artifact_bytes", "database_connections", "memory_bytes",
            "disk_bytes", "retention_entries",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < (1 if name in {
                "concurrency", "maximum_attempts", "database_connections",
                "memory_bytes", "disk_bytes", "retention_entries",
            } else 0):
                raise ResearchWorkerRefusal(f"worker {name} bound is invalid")


@dataclass(frozen=True)
class ResearchWorkerDependencies:
    """Actual local role bindings; none of these fields is a readiness claim."""

    execution_engine: Any
    research_engine: Any
    artifact_store: BoundedResearchArtifactStore
    durable_dispatch: Callable[..., list[int]]
    durable_wait: Callable[[], None]
    api_submit: Callable[..., Any]

    def __post_init__(self) -> None:
        if self.execution_engine is self.research_engine:
            raise ResearchWorkerRefusal("execution and research databases must be separate")
        if not isinstance(self.artifact_store, BoundedResearchArtifactStore):
            raise ResearchWorkerRefusal("bounded research artifact store is required")
        if not callable(self.durable_dispatch) or not callable(self.durable_wait) \
                or not callable(self.api_submit):
            raise ResearchWorkerRefusal(
                "API, durable worker and completion-wait bindings are required"
            )


@dataclass(frozen=True)
class DurableArtifactReceipt:
    run_id: int
    identity_address: str
    artifact_address: str
    from_cache: bool
    payload_address: str


class BoundedWorkerObservationStore:
    """Disk-backed local diagnostics with refusal-only retention and byte ceilings."""

    def __init__(self, *, root: str | Path, disk_bytes_upper_bound: int,
                 retention_upper_bound: int) -> None:
        if type(disk_bytes_upper_bound) is not int or disk_bytes_upper_bound < 1 \
                or type(retention_upper_bound) is not int or retention_upper_bound < 1:
            raise ResearchWorkerRefusal("worker observation bounds are invalid")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise ResearchWorkerRefusal("worker observation root is unavailable")
        self.disk_bytes_upper_bound = disk_bytes_upper_bound
        self.retention_upper_bound = retention_upper_bound
        self._lock = threading.RLock()

    def record(self, document: Mapping[str, Any]) -> str:
        plain = _closed_plain(document)
        address = content_address(plain)
        payload = (json.dumps(
            plain, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ) + "\n").encode()
        with self._lock:
            files = self._files()
            destination = self.root / f"{address.removeprefix('sha256:')}.json"
            if destination.exists():
                return address
            if len(files) >= self.retention_upper_bound:
                raise ResearchWorkerRefusal("worker observation retention exceeds bound")
            if sum(path.stat().st_size for path in files) + len(payload) \
                    > self.disk_bytes_upper_bound:
                raise ResearchWorkerRefusal("worker observation disk exceeds bound")
            temporary = destination.with_suffix(".tmp")
            temporary.write_bytes(payload)
            temporary.replace(destination)
        return address

    def metrics(self) -> Mapping[str, int]:
        with self._lock:
            files = self._files()
            return MappingProxyType({
                "entries": len(files),
                "disk_bytes": sum(path.stat().st_size for path in files),
            })

    def _files(self) -> list[Path]:
        return sorted(path for path in self.root.glob("*.json") if path.is_file())


@dataclass(frozen=True)
class ClaimedResearchJob:
    job_address: str
    owner_id: str
    payload: Mapping[str, Any]
    claim_token: str
    attempt: int


@dataclass
class _Job:
    owner_id: str
    payload: Mapping[str, Any]
    status: str = "PENDING"
    token: str | None = None
    attempt: int = 0
    generation: int = 0
    result_address: str | None = None


@dataclass(frozen=True)
class ResearchQueueSnapshot:
    document: Mapping[str, Any]
    snapshot_address: str


class BoundedLocalResearchQueue:
    """Deterministic queue evidence adapter; durable production queue remains future scope."""

    def __init__(self, *, depth_upper_bound: int, maximum_attempts: int) -> None:
        if type(depth_upper_bound) is not int or depth_upper_bound < 0 \
                or type(maximum_attempts) is not int or maximum_attempts < 1:
            raise ResearchWorkerRefusal("research queue bounds are invalid")
        self.depth_upper_bound = depth_upper_bound
        self.maximum_attempts = maximum_attempts
        self._lock = threading.RLock()
        self._jobs: dict[str, _Job] = {}

    def enqueue(self, *, owner_id: str, payload: Mapping[str, Any]) -> str:
        if not isinstance(owner_id, str) or not owner_id or not isinstance(payload, Mapping):
            raise ResearchWorkerRefusal("research queue job is malformed")
        plain = _closed_plain(payload)
        address = content_address({
            "schema": "research-worker-job/1", "owner_id": owner_id,
            "payload": plain,
        })
        with self._lock:
            existing = self._jobs.get(address)
            if existing is not None:
                if existing.owner_id != owner_id or _plain(existing.payload) != plain:
                    raise ResearchWorkerRefusal("research job identity collision")
                return address
            pending = sum(job.status in {"PENDING", "CLAIMED"} for job in self._jobs.values())
            if pending >= self.depth_upper_bound:
                raise ResearchWorkerRefusal("research queue depth exceeds bound")
            self._jobs[address] = _Job(owner_id, _freeze(plain))
        return address

    def claim(self, *, worker_id: str) -> ClaimedResearchJob | None:
        if not isinstance(worker_id, str) or not worker_id:
            raise ResearchWorkerRefusal("research worker identity is absent")
        with self._lock:
            for address, job in sorted(self._jobs.items()):
                if job.status != "PENDING": continue
                if job.attempt >= self.maximum_attempts:
                    job.status = "FAILED"
                    continue
                job.generation += 1; job.attempt += 1; job.status = "CLAIMED"
                job.token = content_address({
                    "schema": "research-worker-claim/1", "job_address": address,
                    "worker_id": worker_id, "generation": job.generation,
                })
                return ClaimedResearchJob(
                    address, job.owner_id, job.payload, job.token, job.attempt,
                )
        return None

    def complete(self, claim: ClaimedResearchJob, *, result_address: str) -> bool:
        with self._lock:
            job = self._matching_claim(claim)
            if job.status == "COMPLETED": return job.result_address == result_address
            if job.status != "CLAIMED": return False
            if not isinstance(result_address, str) or not result_address.startswith("sha256:"):
                raise ResearchWorkerRefusal("research result address is invalid")
            job.status = "COMPLETED"; job.result_address = result_address; job.token = None
            return True

    def fail(self, claim: ClaimedResearchJob, *, retry: bool) -> bool:
        with self._lock:
            job = self._matching_claim(claim)
            if job.status != "CLAIMED": return False
            job.token = None
            job.status = (
                "PENDING" if retry and job.attempt < self.maximum_attempts else "FAILED"
            )
            return True

    def cancel(self, *, owner_id: str, job_address: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_address)
            if job is None or job.owner_id != owner_id or job.status in {
                "COMPLETED", "FAILED", "CANCELLED",
            }:
                return False
            job.status = "CANCELLED"; job.token = None
            return True

    def expire_claims(self) -> int:
        """Forced-death evidence: stale tokens fence and the exact retry ceiling wins."""
        count = 0
        with self._lock:
            for job in self._jobs.values():
                if job.status == "CLAIMED":
                    job.status = (
                        "PENDING" if job.attempt < self.maximum_attempts else "FAILED"
                    )
                    job.token = None; count += 1
        return count

    def snapshot(self) -> ResearchQueueSnapshot:
        with self._lock:
            rows = [{
                "job_address": address, "owner_id": job.owner_id,
                "payload": _plain(job.payload), "status": job.status,
                "attempt": job.attempt, "generation": job.generation,
                "result_address": job.result_address,
            } for address, job in sorted(self._jobs.items())]
        document = {
            "schema": "research-worker-queue-snapshot/1",
            "depth_upper_bound": self.depth_upper_bound,
            "maximum_attempts": self.maximum_attempts,
            "jobs": rows,
        }
        return ResearchQueueSnapshot(_freeze(document), content_address(document))

    @classmethod
    def from_snapshot(cls, snapshot: ResearchQueueSnapshot):
        if not isinstance(snapshot, ResearchQueueSnapshot) \
                or content_address(_plain(snapshot.document)) != snapshot.snapshot_address:
            raise ResearchWorkerRefusal("research queue snapshot is stale")
        document = snapshot.document
        result = cls(
            depth_upper_bound=document["depth_upper_bound"],
            maximum_attempts=document["maximum_attempts"],
        )
        for row in document["jobs"]:
            expected = content_address({
                "schema": "research-worker-job/1", "owner_id": row["owner_id"],
                "payload": _plain(row["payload"]),
            })
            if expected != row["job_address"] or row["status"] == "CLAIMED":
                raise ResearchWorkerRefusal("research queue snapshot job is stale")
            result._jobs[expected] = _Job(
                row["owner_id"], _freeze(row["payload"]), row["status"], None,
                row["attempt"], row["generation"], row["result_address"],
            )
        return result

    def counts(self) -> Mapping[str, int]:
        with self._lock:
            return MappingProxyType({
                status: sum(job.status == status for job in self._jobs.values())
                for status in ("PENDING", "CLAIMED", "COMPLETED", "FAILED", "CANCELLED")
            })

    def _matching_claim(self, claim: ClaimedResearchJob) -> _Job:
        if not isinstance(claim, ClaimedResearchJob):
            raise ResearchWorkerRefusal("canonical research claim is required")
        job = self._jobs.get(claim.job_address)
        if job is None or job.owner_id != claim.owner_id \
                or job.token != claim.claim_token or job.attempt != claim.attempt:
            raise ResearchWorkerRefusal("research claim token is stale")
        return job


class ResearchWorkerRuntime:
    def __init__(
        self, *, worker_id: str, queue: BoundedLocalResearchQueue,
        limits: ResearchWorkerLimits, build_address: str,
        dependencies: ResearchWorkerDependencies | None = None,
        observations: BoundedWorkerObservationStore | None = None,
    ) -> None:
        if not worker_id or not build_address.startswith("sha256:"):
            raise ResearchWorkerRefusal("research worker identity is incomplete")
        self.worker_id, self.queue, self.limits = worker_id, queue, limits
        self.build_address = build_address
        self.dependencies, self.observations = dependencies, observations
        self._validate_dependency_limits()
        self._stopping = threading.Event()
        self._capacity = threading.BoundedSemaphore(limits.concurrency)
        self._database_capacity = threading.BoundedSemaphore(limits.database_connections)
        self._state_lock = threading.RLock()
        self._active = 0
        self._last_artifact_error: str | None = None
        self._last_materializations: tuple[DurableArtifactReceipt, ...] = ()

    def run_once(self, handler: Callable[[Mapping[str, Any]], str]) -> bool:
        if self._stopping.is_set() or not self._capacity.acquire(blocking=False):
            return False
        claim = None
        try:
            claim = self.queue.claim(worker_id=self.worker_id)
            if claim is None:
                return False
            self._enter_active()
            self._require_memory(claim.payload)
            result_address = handler(claim.payload)
            if self._stopping.is_set():
                self.queue.fail(claim, retry=True)
                return False
            completed = self.queue.complete(claim, result_address=result_address)
            self._record({
                "schema": "research-worker-observation/1",
                "event": "local_job_completed", "job_address": claim.job_address,
                "attempt": claim.attempt, "result_address": result_address,
            })
            return completed
        except Exception:
            if claim is not None:
                self.queue.fail(claim, retry=True)
            raise
        finally:
            if claim is not None:
                self._leave_active()
            self._capacity.release()

    def run_durable_once(self, *, authority_context: Any = None) -> tuple[int, ...]:
        """Consume only the canonical durable BacktestRun dispatcher seam."""
        if self._stopping.is_set() or not self._capacity.acquire(blocking=False):
            return ()
        if self.dependencies is None:
            self._capacity.release()
            raise ResearchWorkerRefusal("durable worker dependencies are absent")
        if not self._database_capacity.acquire(blocking=False):
            self._capacity.release()
            raise ResearchWorkerRefusal("worker database connection bound is saturated")
        self._enter_active()
        try:
            unavailable = tuple(sorted(
                name for name, probe in self._probe_dependencies().items()
                if not probe["ready"]
            ))
            if unavailable:
                raise ResearchWorkerRefusal(
                    "durable worker dependencies are unavailable: "
                    + ",".join(unavailable)
                )
            launched = self.dependencies.durable_dispatch(
                authority_context=authority_context,
            )
            if not isinstance(launched, list) or any(type(item) is not int for item in launched):
                raise ResearchWorkerRefusal("durable dispatcher returned malformed run ids")
            self.dependencies.durable_wait()
            materialized = tuple(
                self._materialize_durable_run(run_id) for run_id in launched
            )
            with self._state_lock:
                self._last_materializations = materialized
                self._last_artifact_error = None
            self._record({
                "schema": "research-worker-observation/1",
                "event": "durable_dispatch", "run_ids": launched,
                "artifact_addresses": [
                    receipt.artifact_address for receipt in materialized
                ],
            })
            return tuple(launched)
        except ResearchArtifactRefusal as exc:
            with self._state_lock:
                self._last_artifact_error = str(exc)
            raise ResearchWorkerRefusal(
                "durable research artifact materialization refused"
            ) from exc
        finally:
            self._leave_active()
            self._database_capacity.release()
            self._capacity.release()

    def stop(self) -> None:
        self._stopping.set()

    @property
    def last_materializations(self) -> tuple[DurableArtifactReceipt, ...]:
        with self._state_lock:
            return self._last_materializations

    def health(self) -> Mapping[str, Any]:
        probes = self._probe_dependencies()
        readiness = {name: bool(value["ready"]) for name, value in probes.items()}
        degraded = tuple(sorted(name for name, ready in readiness.items() if not ready))
        execution = probes["execution_database"]
        research = probes["research_database"]
        role_readiness = {
            "API": readiness["api"] and readiness["configuration"] \
                and readiness["execution_database"],
            "QUEUE": readiness["queue"] and readiness["execution_database"],
            "CACHE": readiness["cache"],
            "ARTIFACT": readiness["artifact"] and readiness["disk"],
            "RESEARCH_WORKER": all(readiness.values()),
        }
        with self._state_lock:
            active = self._active
            artifact_error = self._last_artifact_error
            materializations = self._last_materializations
        document = {
            "schema": "research-worker-health/2",
            "status": "STOPPING" if self._stopping.is_set() else (
                "READY" if not degraded else "DEGRADED"
            ),
            "build_address": self.build_address,
            "execution_head": execution.get("current"),
            "research_head": research.get("current"),
            "roles": list(WORKER_ROLES),
            "role_dependencies": {
                "API": ["configuration", "execution_database", "queue"],
                "QUEUE": ["execution_database"],
                "CACHE": ["artifact_store"],
                "ARTIFACT": ["artifact_store", "observation_disk"],
                "RESEARCH_WORKER": [
                    "execution_database", "research_database", "queue",
                    "configuration", "artifact_store", "observation_disk",
                    "process_memory",
                ],
            },
            "role_readiness": role_readiness,
            "readiness": readiness,
            "probes": probes,
            "degraded_reasons": list(degraded),
            "active": active,
            "capacity": self.limits.concurrency,
            "queue_counts": dict(self.queue.counts()),
            "last_artifact_error": artifact_error,
            "materializations": [
                {
                    "run_id": item.run_id,
                    "identity_address": item.identity_address,
                    "artifact_address": item.artifact_address,
                    "from_cache": item.from_cache,
                    "payload_address": item.payload_address,
                }
                for item in materializations
            ],
        }
        return _freeze({**document, "health_address": content_address(document)})

    def _validate_dependency_limits(self) -> None:
        if self.dependencies is None:
            return
        store = self.dependencies.artifact_store
        exact = {
            "cache_bytes_upper_bound": self.limits.cache_bytes,
            "artifact_bytes_upper_bound": self.limits.artifact_bytes,
            "entry_upper_bound": self.limits.retention_entries,
            "concurrency_upper_bound": self.limits.concurrency,
            "queue_depth_upper_bound": self.limits.queue_depth,
        }
        for name, expected in exact.items():
            if getattr(store, name) != expected:
                raise ResearchWorkerRefusal(f"artifact store {name} differs from worker bound")
        if self.observations is None \
                or self.observations.disk_bytes_upper_bound != self.limits.disk_bytes \
                or self.observations.retention_upper_bound != self.limits.retention_entries:
            raise ResearchWorkerRefusal("worker disk/retention store differs from bound")

    def _probe_dependencies(self) -> dict[str, dict[str, Any]]:
        dependencies = self.dependencies
        result = {
            name: {"ready": False, "reason": "dependency_absent"}
            for name in (
                "api", "configuration", "execution_database", "research_database", "queue",
                "cache", "artifact", "disk", "capacity", "process_memory",
                "durable_dispatch",
            )
        }
        if dependencies is None:
            return result
        try:
            import os
            from app.core.config import get_settings
            settings = get_settings()
            credential_names = (
                "kite_api_key", "kite_api_secret", "kite_access_token",
                "dhan_client_id", "dhan_access_token", "upstox_access_token",
            )
            credential_environment = (
                "KITE_API_KEY", "KITE_API_SECRET", "KITE_ACCESS_TOKEN",
                "DHAN_CLIENT_ID", "DHAN_ACCESS_TOKEN", "UPSTOX_ACCESS_TOKEN",
            )
            credentials_empty = (
                all(not getattr(settings, name, "") for name in credential_names)
                and all(not os.environ.get(name, "") for name in credential_environment)
            )
            result["configuration"] = {
                "ready": (
                    os.environ.get("PT_DISABLE_DOTENV") == "1"
                    and type(settings).model_config.get("env_file") is None
                    and settings.provider == "mock" and settings.execution != "live"
                    and not settings.production and credentials_empty
                ),
                "dotenv_disabled": os.environ.get("PT_DISABLE_DOTENV") == "1",
                "env_file": type(settings).model_config.get("env_file"),
                "provider": settings.provider, "execution": settings.execution,
                "production": settings.production,
                "credentials_empty": credentials_empty,
            }
        except Exception as exc:
            result["configuration"] = {"ready": False, "reason": type(exc).__name__}
        try:
            from sqlalchemy import func, select, text
            from app.db.migrate import head_revision, schema_version
            from app.db.models import BacktestRun

            with dependencies.execution_engine.connect() as connection:
                connection.execute(text("SELECT 1")).scalar_one()
            execution_current = schema_version(dependencies.execution_engine)
            execution_expected = head_revision()
            pool = _pool_probe(dependencies.execution_engine)
            execution_ready = (
                execution_current == execution_expected
                and pool["maximum_connections"] <= self.limits.database_connections
            )
            result["execution_database"] = {
                "ready": execution_ready, "current": execution_current,
                "expected": execution_expected, **pool,
            }
            with dependencies.execution_engine.connect() as connection:
                queue_counts = {
                    status: int(connection.execute(select(func.count()).select_from(
                        BacktestRun,
                    ).where(BacktestRun.status == status)).scalar_one())
                    for status in ("pending", "running", "done", "error", "cancelled")
                }
            active_queue = queue_counts["pending"] + queue_counts["running"]
            result["queue"] = {
                "ready": active_queue <= self.limits.queue_depth,
                "active": active_queue, "upper_bound": self.limits.queue_depth,
                "counts": queue_counts,
            }
        except Exception as exc:
            result["execution_database"] = {
                "ready": False, "reason": type(exc).__name__,
            }
            result["queue"] = {"ready": False, "reason": "execution_probe_failed"}
        try:
            from sqlalchemy import text
            from research.domain.migrate import head_version

            with dependencies.research_engine.connect() as connection:
                connection.execute(text("SELECT 1")).scalar_one()
                research_current = connection.execute(text(
                    "SELECT version FROM research_schema_version",
                )).scalar_one()
            research_expected = head_version()
            pool = _pool_probe(dependencies.research_engine)
            result["research_database"] = {
                "ready": (
                    research_current == research_expected
                    and pool["maximum_connections"] <= self.limits.database_connections
                ),
                "current": research_current, "expected": research_expected, **pool,
            }
        except Exception as exc:
            result["research_database"] = {
                "ready": False, "reason": type(exc).__name__,
            }
        store = dependencies.artifact_store
        try:
            metrics = dict(store.metrics())
            with self._state_lock:
                artifact_error = self._last_artifact_error
            result["cache"] = {
                "ready": metrics["cache_bytes"] <= self.limits.cache_bytes,
                "bytes": metrics["cache_bytes"], "upper_bound": self.limits.cache_bytes,
            }
            result["artifact"] = {
                "ready": (
                    artifact_error is None
                    and metrics["failures"] == 0
                    and store.artifact_bytes_upper_bound == self.limits.artifact_bytes
                    and store.entry_upper_bound == self.limits.retention_entries
                ),
                "artifact_bytes_upper_bound": store.artifact_bytes_upper_bound,
                "retention_upper_bound": store.entry_upper_bound,
                "failures": metrics["failures"],
                "last_error": artifact_error,
            }
        except Exception as exc:
            result["cache"] = result["artifact"] = {
                "ready": False, "reason": type(exc).__name__,
            }
        try:
            disk = dict(self.observations.metrics()) if self.observations else {}
            result["disk"] = {
                "ready": bool(self.observations) \
                    and disk.get("disk_bytes", self.limits.disk_bytes + 1) \
                    <= self.limits.disk_bytes \
                    and disk.get("entries", self.limits.retention_entries + 1) \
                    <= self.limits.retention_entries,
                **disk, "disk_upper_bound": self.limits.disk_bytes,
                "retention_upper_bound": self.limits.retention_entries,
            }
        except Exception as exc:
            result["disk"] = {"ready": False, "reason": type(exc).__name__}
        with self._state_lock:
            active = self._active
        result["capacity"] = {
            "ready": active <= self.limits.concurrency,
            "active": active, "upper_bound": self.limits.concurrency,
        }
        result["process_memory"] = _process_memory_probe(self.limits.memory_bytes)
        result["api"] = {
            "ready": (
                dependencies.api_submit.__module__ == "app.backtest.worker"
                and dependencies.api_submit.__name__ == "submit_durable_research_request"
            ),
            "binding": f"{dependencies.api_submit.__module__}.{dependencies.api_submit.__name__}",
        }
        result["durable_dispatch"] = {
            "ready": (
                dependencies.durable_dispatch.__module__ == "app.backtest.sweep"
                and dependencies.durable_dispatch.__name__ == "dispatch_all_reclaimable"
            ),
            "binding": (
                f"{dependencies.durable_dispatch.__module__}."
                f"{dependencies.durable_dispatch.__name__}"
            ),
        }
        return result

    def _materialize_durable_run(self, run_id: int) -> DurableArtifactReceipt:
        from sqlalchemy import select
        from sqlalchemy.orm import Session
        from app.db.models import BacktestResult, BacktestRun

        with Session(self.dependencies.execution_engine, future=True) as session:
            run = session.get(BacktestRun, run_id)
            if run is None or run.owner_id != self.dependencies.artifact_store.owner_id:
                raise ResearchArtifactRefusal(
                    "durable run is absent or crosses artifact-store owner"
                )
            if run.status not in {"done", "error", "cancelled"}:
                raise ResearchArtifactRefusal("durable run is not terminal")
            try:
                request = json.loads(run.request_json)
                identity = research_cache_identity(request["research_cache_identity"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ResearchArtifactRefusal(
                    "durable run lacks canonical research artifact identity"
                ) from exc
            if identity.document["owner_id"] != run.owner_id \
                    or identity.document["licence_scope"] \
                    != self.dependencies.artifact_store.licence_scope:
                raise ResearchArtifactRefusal(
                    "durable run artifact identity crosses owner or licence"
                )
            rows = list(session.scalars(select(BacktestResult).where(
                BacktestResult.owner_id == run.owner_id,
                BacktestResult.run_id == run.id,
            ).order_by(
                BacktestResult.cell_key,
                BacktestResult.instrument_key,
                BacktestResult.interval,
                BacktestResult.strategy_key,
                BacktestResult.id,
            )))
            if run.status == "done" and (
                    len(rows) != run.total or run.done != run.total):
                raise ResearchArtifactRefusal(
                    "terminal durable result universe is incomplete"
                )
            excluded = {"id", "run_id", "computed_at", "from_cache"}
            payload_rows = [{
                column.name: _closed_plain_value(getattr(row, column.name))
                for column in BacktestResult.__table__.columns
                if column.name not in excluded
            } for row in rows]
            payload = {
                "schema": "durable-research-artifact/1",
                "owner_id": run.owner_id,
                "identity_address": identity.identity_address,
                "run_status": run.status,
                "result_count": len(payload_rows),
                "rows": payload_rows,
            }
        materialized: MaterializedArtifact = \
            self.dependencies.artifact_store.get_or_compute(
                identity, lambda: payload,
            )
        if materialized.payload != payload:
            raise ResearchArtifactRefusal(
                "warm durable research artifact differs from canonical result bytes"
            )
        payload_address = content_address(payload)
        return DurableArtifactReceipt(
            run_id=run_id, identity_address=identity.identity_address,
            artifact_address=materialized.artifact_address,
            from_cache=materialized.from_cache,
            payload_address=payload_address,
        )

    def _require_memory(self, value: Any) -> None:
        size = len(json.dumps(
            _plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode())
        if size > self.limits.memory_bytes:
            raise ResearchWorkerRefusal("worker payload memory exceeds bound")

    def _record(self, document: Mapping[str, Any]) -> None:
        if self.observations is not None:
            self.observations.record(document)

    def _enter_active(self) -> None:
        with self._state_lock:
            self._active += 1

    def _leave_active(self) -> None:
        with self._state_lock:
            self._active -= 1


def submit_durable_research_request(
    session: Any, *, owner_id: str, request: Mapping[str, Any],
    limits: ResearchWorkerLimits,
) -> int:
    """Local API role: admit one canonical pending BacktestRun without a worker."""
    if not isinstance(owner_id, str) or not owner_id or not isinstance(request, Mapping):
        raise ResearchWorkerRefusal("research API request is malformed")
    document = _closed_plain(request)
    required = {
        "scope", "intervals", "capital", "instruments", "lookback_days",
        "start_date", "end_date", "strategies", "attribution",
        "admission_address", "pinned_datasets", "workers",
        "research_cache_identity",
    }
    if set(document) != required:
        raise ResearchWorkerRefusal("research API request schema is incomplete")
    intervals, instruments, strategies = (
        document["intervals"], document["instruments"], document["strategies"],
    )
    if not isinstance(intervals, list) or not intervals \
            or not isinstance(instruments, list) or not instruments \
            or not isinstance(strategies, list) or len(strategies) != 1 \
            or type(document["workers"]) is not int or document["workers"] < 1:
        raise ResearchWorkerRefusal("research API workload is malformed")
    if not isinstance(limits, ResearchWorkerLimits):
        raise ResearchWorkerRefusal("research API worker limits are absent")
    try:
        identity = research_cache_identity(document["research_cache_identity"])
    except (TypeError, ValueError) as exc:
        raise ResearchWorkerRefusal(
            "research API artifact identity is invalid"
        ) from exc
    if identity.document["owner_id"] != owner_id:
        raise ResearchWorkerRefusal("research API artifact owner differs")
    from app.backtest import repository, sweep

    total = len(intervals) * len(instruments) * len(strategies)
    admit_durable_queue_slot(session, upper_bound=limits.queue_depth)
    sweep._admit_workload(
        owner_id=owner_id, total=total, workers=document["workers"], session=session,
    )
    run = repository.enqueue_run(
        session, owner_id=owner_id, scope=str(document["scope"]),
        intervals=",".join(str(value) for value in intervals),
        capital=float(document["capital"]), total=total,
        admission_address=document["admission_address"],
        requested_workers=document["workers"],
        window=(f"{document['lookback_days']}d" if document["lookback_days"] else "max"),
        instruments=",".join(sorted(str(value) for value in instruments)),
        strategies=str(document["attribution"]["strategy_key"]),
        request_json=json.dumps(document, sort_keys=True, separators=(",", ":")),
        note="queued by bounded local research API role",
    )
    session.commit()
    return int(run.id)


def admit_durable_queue_slot(session: Any, *, upper_bound: int) -> int:
    """Serialize and admit one durable queue slot in the caller's transaction."""
    if type(upper_bound) is not int or upper_bound < 0:
        raise ResearchWorkerRefusal("durable research queue bound is invalid")
    from app.db.concurrency import begin_reservation
    from app.db.models import BacktestRun
    from sqlalchemy import func, select

    begin_reservation(session, scope="backtest:admission")
    durable_depth = int(session.scalar(select(func.count()).select_from(
        BacktestRun,
    ).where(BacktestRun.status.in_(("pending", "running")))))
    if durable_depth >= upper_bound:
        raise ResearchWorkerRefusal("durable research queue depth exceeds bound")
    return durable_depth


def _pool_probe(engine: Any) -> dict[str, int]:
    pool = engine.pool
    size = int(pool.size()) if callable(getattr(pool, "size", None)) else 1
    maximum_overflow = int(getattr(pool, "_max_overflow", 0))
    maximum = size + max(0, maximum_overflow)
    checked_out = int(pool.checkedout()) if callable(
        getattr(pool, "checkedout", None),
    ) else 0
    return {"maximum_connections": maximum, "checked_out": checked_out}


def _process_memory_probe(expected: int) -> dict[str, Any]:
    try:
        import os
        declared = int(os.environ["PT_WORKER_MEMORY_LIMIT_BYTES"])
        supervisor_pid = int(os.environ["PT_WORKER_SUPERVISOR_PID"])
        return {
            "ready": declared == expected and supervisor_pid == os.getppid(),
            "limit_bytes": declared, "expected_bytes": expected,
            "supervisor_pid": supervisor_pid, "worker_pid": os.getpid(),
        }
    except Exception as exc:
        return {"ready": False, "reason": type(exc).__name__}


def _closed_plain(value: Any) -> Any:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return json.loads(encoded)


def _closed_plain_value(value: Any) -> Any:
    if hasattr(value, "isoformat") and callable(value.isoformat):
        return value.isoformat()
    return _closed_plain(value)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping): return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple): return [_plain(item) for item in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(value[key]) for key in sorted(value)})
    if isinstance(value, (tuple, list)): return tuple(_freeze(item) for item in value)
    return value


__all__ = [
    "BoundedLocalResearchQueue", "BoundedWorkerObservationStore",
    "admit_durable_queue_slot",
    "ClaimedResearchJob", "DurableArtifactReceipt", "LockedEnvironment",
    "ResearchWorkerDependencies", "ResearchWorkerLimits", "ResearchWorkerRefusal",
    "ResearchWorkerRuntime", "WORKER_ROLES", "research_worker_build_address",
    "submit_durable_research_request", "verify_locked_environment",
]
