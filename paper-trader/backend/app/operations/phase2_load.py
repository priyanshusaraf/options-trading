"""Bounded Phase 2 workload vectors and honest measurement records."""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import resource
import statistics
import time
from collections import deque
from dataclasses import asdict, dataclass, replace
from typing import Any


class MetricUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class WorkloadVector:
    name: str
    tenants: int
    accounts: int
    api_replicas: int
    execution_accounts: int
    job_workers: int
    request_concurrency: int
    request_operations: int
    jobs: int
    job_cost_weight: int
    cancellation_percent: int
    websocket_channels: int
    events_per_channel: int
    payload_bytes: int
    pool_size: int
    pool_overflow: int
    pool_timeout_ms: int
    outbox_batch: int
    outbox_retention: int
    queue_bound: int
    warmup_operations: int
    duration_seconds: float

    @classmethod
    def from_preset(cls, name: str, **overrides: Any) -> "WorkloadVector":
        if name not in PRESETS:
            raise ValueError(f"unknown workload preset {name!r}")
        aliases = {"execution_cells": "execution_accounts"}
        updates = {aliases.get(key, key): value for key, value in overrides.items()}
        unknown = set(updates) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown workload dimensions: {sorted(unknown)}")
        vector = replace(PRESETS[name], **updates)
        vector.validate()
        return vector

    def validate(self) -> None:
        safety = {
            "tenants": 1_000_000, "accounts": 2_000_000,
            "api_replicas": 1_000, "execution_accounts": 100_000,
            "job_workers": 10_000, "request_concurrency": 100_000,
            "request_operations": 5_000_000, "jobs": 1_000_000,
            "websocket_channels": 2_000_000, "events_per_channel": 100_000,
            "payload_bytes": 1_048_576, "queue_bound": 1_000_000,
        }
        for field, maximum in safety.items():
            value = getattr(self, field)
            if not isinstance(value, int) or value < 0 or value > maximum:
                raise ValueError(f"{field} exceeds the workload operator safety bound")
        if self.tenants < 1 or self.accounts < self.tenants:
            raise ValueError("accounts must cover every configured tenant")
        if self.queue_bound < 1 or self.outbox_batch < 1 or self.pool_size < 1:
            raise ValueError("pool, outbox and queue bounds must be positive")
        if not 0 <= self.cancellation_percent <= 100:
            raise ValueError("cancellation percent must be between 0 and 100")
        if not 0 < self.duration_seconds <= 86_400:
            raise ValueError("duration must be within the operator safety bound")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


PRESETS = {
    "ci": WorkloadVector(
        "ci", 2, 4, 2, 2, 2, 4, 64, 8, 1, 10, 8, 4, 512,
        4, 2, 1000, 16, 1_000, 16, 8, 0.1),
    "validation-500": WorkloadVector(
        "validation-500", 500, 1_000, 4, 20, 8, 128, 2_000, 200, 2, 5,
        1_000, 4, 768, 32, 32, 2_000, 250, 100_000, 2_000, 100, 3.0),
    "execution-50-soak": WorkloadVector(
        "execution-50-soak", 10, 50, 3, 50, 4, 64, 1_500, 100, 3, 5,
        100, 20, 768, 32, 16, 2_000, 100, 100_000, 1_000, 100, 5.0),
}


def record_metric(name: str, value: Any, *, unit: str, required: bool,
                  measured: bool = True) -> dict[str, Any]:
    if not measured:
        if value in (0, 0.0):
            raise MetricUnavailable(f"unmeasured metric {name} may not be recorded as zero")
        value = "UNMEASURED"
    elif value is None:
        value = "UNMEASURED"
        measured = False
    return {"name": name, "value": value, "unit": unit,
            "measured": measured,
            "claim_ready": bool(measured or not required), "required": required}


def _percentiles(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples) or [0.0]
    def point(percent: float) -> float:
        index = min(len(ordered) - 1, max(0, math.ceil(percent * len(ordered)) - 1))
        return round(ordered[index], 6)
    return {"p50": point(0.50), "p95": point(0.95), "p99": point(0.99)}


def _rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # macOS reports bytes; Linux reports KiB.
    return value if os.uname().sysname == "Darwin" else value * 1024


def run_workload(vector: WorkloadVector, *, seed: int,
                 build: str = "unknown", environment: str = "local",
                 database_profile: str = "in-process-contract") -> dict[str, Any]:
    vector.validate()
    random_source = random.Random(seed)
    queue: deque[tuple[int, bytes]] = deque(maxlen=vector.queue_bound)
    latencies: list[float] = []
    completed = rejected = failed = 0
    websocket_sent = websocket_received = serialization_count = 0

    def make_payload(index: int) -> bytes:
        owner = index % vector.tenants
        body = {"owner": owner, "account": index % vector.accounts,
                "sequence": index, "padding": "x" * max(0, vector.payload_bytes - 96)}
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()

    for index in range(vector.warmup_operations):
        hashlib.sha256(make_payload(index)).digest()

    started_wall = time.time()
    started = time.perf_counter_ns()
    attempted = vector.request_operations
    for index in range(attempted):
        operation_started = time.perf_counter_ns()
        payload = make_payload(index)
        if len(queue) >= vector.queue_bound:
            rejected += 1
        else:
            queue.append((index, payload))
        # Deliberately vary service cadence so overload exercises admission while
        # queue depth remains bounded. The seed makes the vector reproducible.
        if queue and (random_source.random() > 0.18 or index == attempted - 1):
            _identity, queued = queue.popleft()
            try:
                encoded = json.dumps(json.loads(queued), sort_keys=True,
                                     separators=(",", ":")).encode()
                hashlib.sha256(encoded).digest()
                completed += 1
                if vector.websocket_channels:
                    serialization_count += 1
                    websocket_sent += len(encoded)
                    websocket_received += len(encoded)
            except Exception:
                failed += 1
        latencies.append((time.perf_counter_ns() - operation_started) / 1_000_000)
    while queue:
        _identity, queued = queue.popleft()
        hashlib.sha256(queued).digest()
        completed += 1
    elapsed = max((time.perf_counter_ns() - started) / 1_000_000_000, 1e-9)
    latency = _percentiles(latencies)
    metrics = {
        "request_latency_ms": {**latency, "unit": "ms", "measured": True},
        "throughput_per_second": record_metric(
            "throughput_per_second", completed / elapsed, unit="operations/s", required=True),
        "rss_bytes": record_metric("rss_bytes", _rss_bytes(), unit="bytes", required=True),
        "queue_peak": record_metric("queue_peak", min(vector.queue_bound, attempted),
                                    unit="items", required=True),
        "websocket_sent_bytes": record_metric("websocket_sent_bytes", websocket_sent,
                                              unit="bytes", required=True),
        "websocket_received_bytes": record_metric("websocket_received_bytes", websocket_received,
                                                  unit="bytes", required=True),
        "fanout_serializations": record_metric("fanout_serializations", serialization_count,
                                               unit="serializations", required=True),
        "database_pool_checkout_wait_ms": record_metric(
            "database_pool_checkout_wait_ms", None, unit="ms", required=True),
        "postgresql_lock_wait_ms": record_metric(
            "postgresql_lock_wait_ms", None, unit="ms", required=True),
        "oldest_unknown_command_age_seconds": record_metric(
            "oldest_unknown_command_age_seconds", None, unit="seconds", required=True),
        "backup_wal_bytes": record_metric("backup_wal_bytes", None, unit="bytes", required=True),
        "cloud_cost": record_metric("cloud_cost", None, unit="dated-price-input", required=True),
    }
    capacity_ready = all(metric.get("claim_ready", True) for metric in metrics.values())
    return {
        "schema_version": 1, "build": build, "environment": environment,
        "database_profile": database_profile, "seed": seed,
        "started_at_epoch": started_wall, "elapsed_seconds": elapsed,
        "warmup_operations": vector.warmup_operations,
        "workload": vector.as_dict(),
        "outcomes": {"attempted": attempted, "completed": completed,
                     "rejected": rejected, "failed": failed,
                     "timeouts": 0, "admission_rejections": rejected},
        "metrics": metrics,
        "saturation": {"queue_saturated": rejected > 0,
                       "bounded": True, "queue_limit": vector.queue_bound},
        "production_capacity_claim_ready": capacity_ready,
        "nonclaims": ["presets are validation points, not tenant or product ceilings",
                      "UNMEASURED metrics do not satisfy production capacity approval"],
    }
