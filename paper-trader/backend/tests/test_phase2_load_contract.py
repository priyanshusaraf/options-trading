from __future__ import annotations
import json

import pytest

from app.operations.phase2_load import (
    PRESETS,
    MetricUnavailable,
    WorkloadVector,
    record_metric,
    run_workload,
)


def test_named_validation_presets_are_measurement_points_not_admission_caps():
    assert PRESETS["validation-500"].tenants == 500
    assert PRESETS["execution-50-soak"].execution_accounts == 50
    custom = WorkloadVector.from_preset("ci", tenants=731, accounts=900)
    assert custom.tenants == 731 and custom.accounts == 900
    assert "tenant_cap" not in custom.as_dict()


def test_missing_required_metric_is_unmeasured_never_zero():
    metric = record_metric("database.wal_bytes", None, unit="bytes", required=True)
    assert metric["value"] == "UNMEASURED"
    assert metric["claim_ready"] is False
    with pytest.raises(MetricUnavailable):
        record_metric("database.wal_bytes", 0, unit="bytes", required=True,
                      measured=False)


def test_small_workload_is_bounded_machine_readable_and_separates_rejection():
    report = run_workload(WorkloadVector.from_preset("ci"), seed=17)
    encoded = json.dumps(report, sort_keys=True)
    assert report["workload"]["queue_bound"] > 0
    assert report["outcomes"]["attempted"] == (
        report["outcomes"]["completed"] + report["outcomes"]["rejected"]
        + report["outcomes"]["failed"])
    assert report["metrics"]["rss_bytes"]["value"] > 0
    assert report["metrics"]["request_latency_ms"]["p99"] >= 0
    assert "tenant_cap" not in encoded


def test_operator_overrides_are_bounded_for_harness_safety_not_product_capacity():
    with pytest.raises(ValueError, match="operator safety bound"):
        WorkloadVector.from_preset("ci", tenants=1_000_001)
