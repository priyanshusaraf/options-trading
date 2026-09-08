from __future__ import annotations

import contextlib
import datetime as dt
from types import SimpleNamespace

import pytest

from app.chart import annotation_context as context
from app.ir.hashing import canonical_json
from research.data.canonical_dataset import CanonicalCandle, CanonicalDatasetRefused

UTC = dt.timezone.utc


def address(digit: str) -> str:
    return "sha256:" + digit * 64


def saved_run(*, as_of: str = "2026-01-01T10:03:00+00:00") -> dict:
    graph = {"project_id": "project.a", "identifier": "strategy.a", "version": 1,
             "content_address": address("a")}
    binding = {
        "manifest_address": address("b"), "instrument_address": address("c"),
        "as_of": as_of,
        "instrument": {"venue_code": "XNSE", "asset_class": "EQUITY",
                       "contract_kind": "SPOT"},
        "time_interpretation": {"resolution_seconds": 60},
    }
    evidence = {"schema": "terminal", "provenance": {"graph_provenance": {
        "graph": graph, "canonical_dataset_bindings": {
            "schema": "canonical-dataset-bindings/1", "bindings": {"only": binding}}}}}
    return {"evidence_state": "verified", "evidence": evidence, "graph": graph}


def dataset(candles: tuple[CanonicalCandle, ...]):
    binding = {"manifest_address": address("b"), "instrument_address": address("c"),
               "time_interpretation": {"resolution_seconds": 60}}
    return SimpleNamespace(bar_count=len(candles), candles=candles, binding=binding)


def candles(count: int = 3) -> tuple[CanonicalCandle, ...]:
    start = dt.datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    return tuple(CanonicalCandle(start + dt.timedelta(minutes=index),
        100.0 + index, 102.0 + index, 99.0 + index, 101.0 + index, 10.0 + index)
        for index in range(count))


@contextlib.contextmanager
def null_session():
    yield object()


def install(monkeypatch: pytest.MonkeyPatch, rows: tuple[CanonicalCandle, ...]) -> None:
    monkeypatch.setattr(context.research_read, "get_graph_run",
                        lambda *_args, **_kwargs: saved_run())
    monkeypatch.setattr(context.research_read, "_research_session", null_session)
    monkeypatch.setattr(context, "SessionLocal", null_session)
    monkeypatch.setattr(context, "load_canonical_datasets",
        lambda *_args, **_kwargs: [(SimpleNamespace(key="instrument-key"),
                                    SimpleNamespace(**{**dataset(rows).__dict__,
                                        "instrument_key": "instrument-key"}))])


def test_market_context_contract_is_available(monkeypatch: pytest.MonkeyPatch):
    install(monkeypatch, candles())
    result = context.build_market_context("project.a", 7, owner_id="owner.a")
    assert result["schema"] == "strategy-os-market-context/1"
    assert result["instrument_label"] == "XNSE · EQUITY · SPOT"
    assert [row["cursor"] for row in result["bars"]] == [1, 2, 3]
    assert result["page"]["next_cursor"] is None


def test_replay_excludes_bar_until_completed_at(monkeypatch: pytest.MonkeyPatch):
    install(monkeypatch, candles())
    replay = dt.datetime(2026, 1, 1, 10, 1, tzinfo=UTC)
    result = context.build_market_context("project.a", 7, owner_id="owner.a", replay_at=replay)
    assert [row["event_time"] for row in result["bars"]] == ["2026-01-01T10:00:00+00:00"]
    assert all(row["completed_at"] <= result["replay_at"] for row in result["bars"])


def test_future_append_does_not_change_earlier_prefix(monkeypatch: pytest.MonkeyPatch):
    replay = dt.datetime(2026, 1, 1, 10, 2, tzinfo=UTC)
    install(monkeypatch, candles(2))
    before = context.build_market_context("project.a", 7, owner_id="owner.a", replay_at=replay)
    install(monkeypatch, candles(3))
    after = context.build_market_context("project.a", 7, owner_id="owner.a", replay_at=replay)
    assert after["bars"] == before["bars"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_candle_is_refused(monkeypatch: pytest.MonkeyPatch, bad: float):
    row = CanonicalCandle(dt.datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
                          bad, 102.0, 99.0, 101.0, 1.0)
    install(monkeypatch, (row,))
    with pytest.raises(context.MarketContextUnavailable):
        context.build_market_context("project.a", 7, owner_id="owner.a")


def test_non_utc_or_future_replay_is_refused(monkeypatch: pytest.MonkeyPatch):
    install(monkeypatch, candles())
    with pytest.raises(context.MarketContextUnavailable):
        context.build_market_context("project.a", 7, owner_id="owner.a",
                                     replay_at=dt.datetime(2026, 1, 1, 10, 1))
    with pytest.raises(context.MarketContextUnavailable):
        context.build_market_context("project.a", 7, owner_id="owner.a",
                                     replay_at=dt.datetime(2026, 1, 1, 10, 4, tzinfo=UTC))


def test_loader_refusal_is_privacy_safe(monkeypatch: pytest.MonkeyPatch):
    install(monkeypatch, candles())
    monkeypatch.setattr(context, "load_canonical_datasets",
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(CanonicalDatasetRefused()))
    with pytest.raises(context.MarketContextUnavailable, match="market context is unavailable"):
        context.build_market_context("project.a", 7, owner_id="owner.a")


def test_two_thousand_bar_ceiling_pages_at_500_under_one_mebibyte(monkeypatch: pytest.MonkeyPatch):
    install(monkeypatch, candles(2_000))
    monkeypatch.setattr(context.research_read, "get_graph_run",
                        lambda *_args, **_kwargs: saved_run(as_of="2026-01-03T00:00:00+00:00"))
    first = context.build_market_context("project.a", 7, owner_id="owner.a", limit=500)
    assert len(first["bars"]) == 500 and first["page"]["next_cursor"] == 500
    assert len(canonical_json(first).encode()) <= context.MAX_RESPONSE_BYTES
    last = context.build_market_context("project.a", 7, owner_id="owner.a", after=1_500, limit=500)
    assert len(last["bars"]) == 500 and last["page"]["next_cursor"] is None


def test_market_context_contract_is_available() -> None:
    from app.chart.annotation_context import MARKET_CONTEXT_SCHEMA

    assert MARKET_CONTEXT_SCHEMA == "strategy-os-market-context/1"
