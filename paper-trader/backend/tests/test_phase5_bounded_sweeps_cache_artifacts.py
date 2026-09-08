from __future__ import annotations

import copy
import threading
import time

import pytest

from app.backtest.artifacts import (
    BoundedResearchArtifactStore,
    ResearchArtifactRefusal,
    ResearchArtifactSnapshot,
    research_cache_identity,
    research_cache_identity_document,
)
from app.backtest.sweep import (
    WorkloadAdmissionError,
    admit_phase5_research_bounds,
)
from app.ir.hashing import content_address
from research_tests.test_phase5_research_execution import _runtime


def _address(name: str) -> str:
    return content_address({"phase5-cache-fixture": name})


def _identity_values(*, owner_id="owner-a", licence_scope="OWNER_PRIVATE", suffix="a"):
    return {
        "owner_id": owner_id,
        "licence_scope": licence_scope,
        "semantic_nodes": [
            {"component_id": "analytical.sma", "component_version": 1},
            {"component_id": "logic.counter", "component_version": 1},
        ],
        "parameters_address": _address(f"parameters-{suffix}"),
        "instrument_addresses": [_address(f"instrument-{suffix}")],
        "registry_snapshot_address": _address(f"registry-{suffix}"),
        "dataset_manifest_address": _address(f"dataset-{suffix}"),
        "provider_evidence_addresses": [_address(f"provider-{suffix}")],
        "event_start": "2026-01-01T00:00:00+00:00",
        "event_end": "2026-01-02T00:00:00+00:00",
        "segment_addresses": [_address(f"segment-{suffix}")],
        "adjustment_policy_address": _address(f"adjustment-{suffix}"),
        "session_policy_address": _address(f"session-{suffix}"),
        "resampling_policy_address": _address(f"resampling-{suffix}"),
        "missing_data_policy_address": _address(f"missing-{suffix}"),
        "alignment_policy_address": _address(f"alignment-{suffix}"),
        "implementation_closure_address": _address(f"implementation-{suffix}"),
        "resolved_graph_address": _address(f"graph-{suffix}"),
        "resource_plan_address": _address(f"resource-{suffix}"),
        "evaluation_policy_address": _address(f"evaluation-{suffix}"),
        "node_context_resolver_address": _address(f"resolver-{suffix}"),
        "run_authority_address": _address(f"run-{suffix}"),
    }


def _identity(**overrides):
    values = _identity_values(**overrides)
    return research_cache_identity(research_cache_identity_document(**values))


def _store(**overrides):
    values = {
        "owner_id": "owner-a", "licence_scope": "OWNER_PRIVATE",
        "cache_bytes_upper_bound": 1024, "artifact_bytes_upper_bound": 512,
        "entry_upper_bound": 4, "concurrency_upper_bound": 1,
        "queue_depth_upper_bound": 2,
    }
    values.update(overrides)
    return BoundedResearchArtifactStore(**values)


@pytest.mark.parametrize("field", tuple(sorted(
    set(_identity_values()) - {"owner_id", "licence_scope", "semantic_nodes"}
)))
def test_every_cache_provenance_dimension_changes_identity(field):
    baseline = _identity_values()
    changed = copy.deepcopy(baseline)
    if field == "event_start": changed[field] = "2025-12-31T23:00:00+00:00"
    elif field == "event_end": changed[field] = "2026-01-03T00:00:00+00:00"
    elif isinstance(changed[field], list): changed[field] = [_address(f"changed-{field}")]
    else: changed[field] = _address(f"changed-{field}")
    left = research_cache_identity(research_cache_identity_document(**baseline))
    right = research_cache_identity(research_cache_identity_document(**changed))
    assert left.identity_address != right.identity_address


@pytest.mark.parametrize("field", tuple(sorted(_identity_values())))
def test_cache_identity_refuses_every_missing_dimension(field):
    document = dict(research_cache_identity_document(**_identity_values()))
    document.pop(field)
    with pytest.raises(ResearchArtifactRefusal):
        research_cache_identity(document)


def test_cache_identity_semantic_owner_and_licence_are_exact():
    baseline = _identity()
    changed_nodes = _identity_values()
    changed_nodes["semantic_nodes"][0]["component_version"] = 2
    changed = research_cache_identity(research_cache_identity_document(**changed_nodes))
    assert changed.identity_address != baseline.identity_address
    assert _identity(owner_id="owner-b").identity_address != baseline.identity_address
    assert _identity(licence_scope="PLATFORM_PUBLIC").identity_address \
        != baseline.identity_address
    forged = copy.copy(baseline)
    object.__setattr__(forged, "identity_address", _address("forged"))
    with pytest.raises(ResearchArtifactRefusal, match="stale"):
        _store().get_or_compute(forged, lambda: {"value": 1})


def test_cold_warm_defensive_materialization_and_cost_attribution():
    store = _store(); identity = _identity(); calls = 0
    def compute():
        nonlocal calls; calls += 1
        return {"rows": [1, 2, 3], "metric": 4.5}
    cold = store.get_or_compute(identity, compute)
    assert not cold.from_cache and cold.cost.document["category"] == "COLD_COMPUTE"
    cold.payload["rows"][0] = 99
    warm = store.get_or_compute(identity, compute)
    assert warm.from_cache and warm.payload["rows"] == [1, 2, 3]
    assert warm.cost.document["category"] == "CACHE_HIT"
    assert warm.artifact_address == cold.artifact_address and calls == 1
    metrics = store.metrics()
    assert metrics["cold_computes"] == metrics["cache_hits"] == 1
    assert set(metrics) == set(BoundedResearchArtifactStore._METRIC_NAMES) | {
        "active", "queued", "entries", "cache_bytes",
    }


def test_cross_owner_and_licence_reuse_refuses_without_probe():
    private = _store()
    with pytest.raises(ResearchArtifactRefusal, match="cross-owner"):
        private.get_or_compute(_identity(owner_id="owner-b"), lambda: {"secret": 1})
    with pytest.raises(ResearchArtifactRefusal, match="licence"):
        private.get_or_compute(
            _identity(licence_scope="PLATFORM_PUBLIC"), lambda: {"public": 1},
        )
    assert private.metrics()["entries"] == 0


def test_artifact_and_cache_bytes_pass_at_limit_and_refuse_first_over():
    payload = {"value": "x" * 20}
    from app.backtest.artifacts import _canonical_payload
    size = len(_canonical_payload(payload))
    at_limit = _store(cache_bytes_upper_bound=size, artifact_bytes_upper_bound=size)
    assert at_limit.get_or_compute(_identity(), lambda: payload).payload == payload
    with pytest.raises(ResearchArtifactRefusal, match="artifact exceeds"):
        _store(artifact_bytes_upper_bound=size-1).get_or_compute(
            _identity(), lambda: payload,
        )
    with pytest.raises(ResearchArtifactRefusal, match="cannot fit"):
        _store(cache_bytes_upper_bound=size-1).get_or_compute(
            _identity(), lambda: payload,
        )


def test_lru_eviction_and_missing_artifact_recompute_preserve_identity():
    store = _store(entry_upper_bound=1)
    first, second = _identity(suffix="a"), _identity(suffix="b")
    a = store.get_or_compute(first, lambda: {"value": "a"})
    store.get_or_compute(second, lambda: {"value": "b"})
    assert store.metrics()["evictions"] == 1
    again = store.get_or_compute(first, lambda: {"value": "a"})
    assert not again.from_cache and again.artifact_address == a.artifact_address


def test_corruption_refuses_then_retry_recomputes_without_reuse():
    store = _store(); identity = _identity()
    store.get_or_compute(identity, lambda: {"value": 1})
    store._entries[identity.identity_address].payload_bytes = b'{"value":999}'
    with pytest.raises(ResearchArtifactRefusal, match="corrupt"):
        store.get_or_compute(identity, lambda: {"value": 2})
    restored = store.get_or_compute(identity, lambda: {"value": 2})
    assert not restored.from_cache and restored.payload == {"value": 2}
    assert store.metrics()["corruption_refusals"] == 1


def test_snapshot_restart_verifies_bytes_owner_and_identity():
    store = _store(); identity = _identity()
    original = store.get_or_compute(identity, lambda: {"value": 7})
    snapshot = store.snapshot()
    restarted = BoundedResearchArtifactStore.from_snapshot(
        snapshot, cache_bytes_upper_bound=1024, artifact_bytes_upper_bound=512,
        entry_upper_bound=4, concurrency_upper_bound=1, queue_depth_upper_bound=2,
    )
    warm = restarted.get_or_compute(identity, lambda: {"value": 9})
    assert warm.from_cache and warm.payload == {"value": 7}
    assert warm.artifact_address == original.artifact_address
    document, payload = snapshot.entries[0]
    corrupt = ResearchArtifactSnapshot(
        snapshot.owner_id, snapshot.licence_scope, ((document, payload+b"x"),),
    )
    with pytest.raises(ResearchArtifactRefusal, match="corrupt"):
        BoundedResearchArtifactStore.from_snapshot(
            corrupt, cache_bytes_upper_bound=1024, artifact_bytes_upper_bound=512,
            entry_upper_bound=4, concurrency_upper_bound=1, queue_depth_upper_bound=2,
        )


def test_stampede_single_flight_computes_once():
    store = _store(); identity = _identity()
    started, release = threading.Event(), threading.Event()
    calls = 0; results = []
    def compute():
        nonlocal calls; calls += 1; started.set(); release.wait(2)
        return {"value": 1}
    def run(): results.append(store.get_or_compute(identity, compute))
    first = threading.Thread(target=run); second = threading.Thread(target=run)
    first.start(); assert started.wait(1); second.start(); time.sleep(0.05); release.set()
    first.join(2); second.join(2)
    assert calls == 1 and len(results) == 2
    assert sorted(item.from_cache for item in results) == [False, True]
    assert store.metrics()["waits"] == 1


def test_queue_first_over_cancellation_failure_and_retry_do_not_mint_cache():
    store = _store(queue_depth_upper_bound=0)
    identity = _identity(); started, release = threading.Event(), threading.Event()
    thread = threading.Thread(target=lambda: store.get_or_compute(
        identity, lambda: (started.set(), release.wait(2), {"value": 1})[-1],
    ))
    thread.start(); assert started.wait(1)
    with pytest.raises(ResearchArtifactRefusal, match="queue depth"):
        store.get_or_compute(identity, lambda: {"value": 2})
    release.set(); thread.join(2)

    cancelled = iter((False, False, True))
    with pytest.raises(ResearchArtifactRefusal, match="cancelled"):
        store.get_or_compute(
            _identity(suffix="cancel"), lambda: {"value": 3},
            cancelled=lambda: next(cancelled),
        )
    attempts = 0
    def flaky():
        nonlocal attempts; attempts += 1
        if attempts == 1: raise RuntimeError("boom")
        return {"value": 4}
    with pytest.raises(RuntimeError, match="boom"):
        store.get_or_compute(_identity(suffix="retry"), flaky)
    retry = store.get_or_compute(_identity(suffix="retry"), flaky)
    assert not retry.from_cache and retry.payload == {"value": 4}


@pytest.mark.parametrize("dimension", (
    "requested_cells", "worker_slots", "queue_depth", "dynamic_members",
))
def test_sweep_lowest_bound_passes_at_limit_and_refuses_first_over(dimension):
    _graph, _registry, plan, _dataset, _policy = _runtime()
    limits = {
        "requested_cells": 4, "worker_slots": 1,
        "queue_depth": 3, "dynamic_members": 2,
    }
    admission = admit_phase5_research_bounds(
        plan, requested_cells=4, requested_workers=1,
        requested_queue_depth=3, requested_dynamic_members=2,
        tier_limits=limits, tenant_limits={**limits, "requested_cells": 5},
        provider_limits={**limits, "requested_cells": 6},
    )
    assert admission.document["effective_limits"] == limits
    requests = dict(
        requested_cells=4, requested_workers=1,
        requested_queue_depth=3, requested_dynamic_members=2,
    )
    key = {
        "requested_cells": "requested_cells", "worker_slots": "requested_workers",
        "queue_depth": "requested_queue_depth",
        "dynamic_members": "requested_dynamic_members",
    }[dimension]
    requests[key] += 1
    with pytest.raises(WorkloadAdmissionError, match="research_bound"):
        admit_phase5_research_bounds(
            plan, **requests, tier_limits=limits,
            tenant_limits={**limits, "requested_cells": 5},
            provider_limits={**limits, "requested_cells": 6},
        )
