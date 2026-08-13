"""Immutable app-owned fixtures for causal strategy admission."""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

import numpy as np
import pandas as pd

from app.ir.hashing import content_address


@dataclass(frozen=True)
class CausalFixture:
    name: str
    inputs: Mapping[str, pd.Series]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("fixture name must be non-empty")
        copied = {
            name: series.copy(deep=True)
            for name, series in sorted(self.inputs.items())
        }
        object.__setattr__(self, "inputs", MappingProxyType(copied))


@dataclass(frozen=True)
class CausalFixtureSuite:
    fixtures: tuple[CausalFixture, ...]
    scheme: str = "causal-fixtures/1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "fixtures", tuple(self.fixtures))
        if self.scheme != "causal-fixtures/1":
            raise ValueError("unsupported causal fixture scheme")
        names = tuple(fixture.name for fixture in self.fixtures)
        if not names or len(names) != len(set(names)):
            raise ValueError("fixture names must be non-empty and unique")

    @property
    def address(self) -> str:
        return content_address(canonical_fixture_manifest(self))


def canonical_fixture_manifest(suite: CausalFixtureSuite) -> dict:
    return {
        "scheme": suite.scheme,
        "fixtures": [
            {
                "name": fixture.name,
                "inputs": {
                    name: {
                        "index_utc_ns": [
                            int(item) for item in
                            series.index.tz_convert("UTC").as_unit("ns").asi8
                        ],
                        "values": [_closed_number(value) for value in series.tolist()],
                    }
                    for name, series in sorted(fixture.inputs.items())
                },
            }
            for fixture in suite.fixtures
        ],
    }


def _closed_number(value: object) -> object:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("fixture values must be finite or NaN")
    return number


class _FixtureSuites:
    def __init__(self, suites: Mapping[str, CausalFixtureSuite]) -> None:
        self._suites = MappingProxyType(dict(suites))
        self._addresses = MappingProxyType({
            name: suite.address for name, suite in suites.items()
        })

    def require(self, identifier: str) -> CausalFixtureSuite:
        try:
            suite = self._suites[identifier]
        except KeyError as exc:
            raise KeyError(f"unknown fixture suite {identifier!r}") from exc
        if suite.address != self._addresses[identifier]:
            raise ValueError(f"fixture suite {identifier!r} changed after registration")
        return suite


def _frame(name: str, close: np.ndarray,
           *, index: pd.DatetimeIndex | None = None,
           nan_prefix: int = 0) -> CausalFixture:
    if index is None:
        index = pd.date_range(
            "2026-08-10 09:15", periods=len(close), freq="15min", tz="Asia/Kolkata")
    close = close.astype(float, copy=True)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + 0.75
    low = np.minimum(open_, close) - 0.75
    volume = np.linspace(100.0, 100.0 + len(close) - 1, len(close))
    if nan_prefix:
        for values in (open_, high, low, close, volume):
            values[:nan_prefix] = np.nan
    return CausalFixture(name, {
        "open": pd.Series(open_, index=index, name="open"),
        "high": pd.Series(high, index=index, name="high"),
        "low": pd.Series(low, index=index, name="low"),
        "close": pd.Series(close, index=index, name="close"),
        "volume": pd.Series(volume, index=index, name="volume"),
    })


def _build_suite() -> CausalFixtureSuite:
    length = 24
    rng = np.random.default_rng(20260813)
    sessions = pd.DatetimeIndex([
        *pd.date_range("2026-08-10 09:15", periods=12, freq="15min", tz="Asia/Kolkata"),
        *pd.date_range("2026-08-11 09:15", periods=12, freq="15min", tz="Asia/Kolkata"),
    ])
    fixtures = (
        _frame("monotonic", np.linspace(100.0, 112.0, length)),
        _frame("alternating", 100.0 + np.where(np.arange(length) % 2, 4.0, -3.0)),
        _frame("constant", np.full(length, 100.0)),
        _frame("gapped", np.r_[np.linspace(100, 104, 12), np.linspace(115, 108, 12)]),
        _frame("duplicated-values", np.repeat(np.linspace(99, 105, 12), 2)),
        _frame("regime-change", np.r_[np.linspace(100, 101, 12), np.linspace(101, 120, 12)]),
        _frame("session-boundary", np.linspace(100, 108, length), index=sessions),
        _frame("nan-prefix", np.linspace(100, 110, length), nan_prefix=3),
        _frame("seeded-random", 100.0 + np.cumsum(rng.normal(0.0, 1.5, length))),
    )
    return CausalFixtureSuite(fixtures)


FIXTURE_SUITES = _FixtureSuites({"causal-fixtures/1": _build_suite()})


__all__ = [
    "CausalFixture", "CausalFixtureSuite", "FIXTURE_SUITES",
    "canonical_fixture_manifest",
]
