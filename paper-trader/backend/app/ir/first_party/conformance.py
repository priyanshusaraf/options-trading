"""Shared conformance checks for first-party v2 catalogue contributors."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd


class CatalogueConformanceError(AssertionError):
    pass


def assert_catalogue_complete(registry: Any, expected_components: Sequence[tuple[str, int]]) -> None:
    expected = set(expected_components)
    actual = set(registry.v2_components)
    if actual != expected:
        raise CatalogueConformanceError(
            f"catalogue differs; missing={sorted(expected-actual)}, extra={sorted(actual-expected)}"
        )
    for label, values in (
        ("implementations", registry.v2_implementation_registrations),
        ("contracts", registry.node_contracts),
        ("data requirements", registry.data_requirement_declarations),
    ):
        if set(values) != expected:
            raise CatalogueConformanceError(f"{label} closure differs from catalogue")
    for key, component in registry.v2_components.items():
        outputs = [port for port in component["ports"] if port["direction"] == "output"]
        contract = registry.node_contracts[key]
        if len(outputs) != 1 or outputs[0]["port_id"] not in contract["output_types"]:
            raise CatalogueConformanceError(f"output mapping differs for {key}")
        if not contract["reference_provenance"] or not contract["resource_profile"]:
            raise CatalogueConformanceError(f"reference/resource declaration absent for {key}")


def reference_frame(length: int = 96) -> Mapping[str, pd.Series]:
    index = pd.date_range("2026-01-01", periods=length, freq="min", tz="UTC")
    base = pd.Series(np.linspace(100.0, 130.0, length) + np.sin(np.arange(length) / 3), index=index)
    return {
        "open": base.shift(1).fillna(base.iloc[0]),
        "high": base + 1.5,
        "low": base - 1.25,
        "close": base,
        "last": base,
        "volume": pd.Series(np.arange(length) + 100, index=index, dtype=float),
        "peer": base * 0.8 + 7,
        "bid": base - 0.05,
        "ask": base + 0.05,
        "open_interest": pd.Series(np.arange(length) + 1000, index=index, dtype=float),
    }


def assert_prefix_causal(implementation: Any, frame: Mapping[str, pd.Series], parameters: Mapping[str, Any]) -> None:
    full = implementation(parameters, {"frame": frame})["value"]
    for end in (16, 32, len(next(iter(frame.values())))):
        prefix_frame = {key: value.iloc[:end] for key, value in frame.items()}
        prefix = implementation(parameters, {"frame": prefix_frame})["value"]
        _equal_prefix(full, prefix, end)


def _equal_prefix(full: Any, prefix: Any, end: int) -> None:
    if isinstance(full, pd.DataFrame):
        pd.testing.assert_frame_equal(full.iloc[:end], prefix)
    elif isinstance(full, pd.Series):
        pd.testing.assert_series_equal(full.iloc[:end], prefix)
    else:
        assert full == prefix


def assert_deterministic(implementation: Any, frame: Mapping[str, pd.Series], parameters: Mapping[str, Any]) -> None:
    left = implementation(parameters, {"frame": frame})["value"]
    right = implementation(parameters, {"frame": frame})["value"]
    _equal_prefix(left, right, len(next(iter(frame.values()))))


__all__ = [
    "CatalogueConformanceError", "assert_catalogue_complete", "assert_deterministic",
    "assert_prefix_causal", "reference_frame",
]
