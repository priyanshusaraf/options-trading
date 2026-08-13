"""The pinned immutable warm path (design: "Truthful warm modes", Task 4).

Two warm modes exist and they must never be confused:

* **Refresh warm** — acquire every dataset once, then skip the simulations whose
  execution address already has a result. Budget: one provider read per dataset.
* **Pinned warm** — evaluate against dataset addresses the caller named
  explicitly. Zero provider reads, and that claim is truthful only because the
  caller asked for exactly these bytes.

The whole risk of this task is that the second quietly becomes the first, or the
first quietly becomes the second. So:

1. a pinned rerun makes ZERO provider calls and reproduces every stored result
   column (test 1);
2. a pin that cannot be honoured — missing, corrupted, or describing a different
   series than the cell asks for — FAILS CLOSED for that cell and never falls
   back to a fetch (tests 2-5);
3. a sweep without the pin parameter reads exactly what it read before, even
   with a fully populated store (test 6).
"""
from __future__ import annotations

import zlib
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.backtest import dataset_store, repository, sweep
from app.backtest.universe import liquid_universe
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal, init_db
from app.providers.mock import MockProvider
from app.strategy.registry import get_strategy

INTERVALS = ["15minute", "30minute"]
STRATEGIES = ["trend_impulse_v3", "expanding_z_v4"]


def _admission_address(owner_id: str) -> str:
    return "sha256:" + "d" * 64


@pytest.fixture(autouse=True)
def _admitted_sweeps(monkeypatch):
    original = sweep.start_sweep
    monkeypatch.setattr(
        repository, "load_verified_admission",
        lambda _session, *, admission_address, **_kwargs: SimpleNamespace(
            admission_address=admission_address, strategy=get_strategy("trend_impulse_v3")),
    )

    def start(*args, **kwargs):
        kwargs.setdefault("admission_address", _admission_address(kwargs["owner_id"]))
        kwargs.pop("strategies", None)
        return original(*args, **kwargs)

    monkeypatch.setattr(sweep, "start_sweep", start)


class CountingMockProvider(MockProvider):
    def __init__(self):
        super().__init__()
        self.candle_reads = []

    def get_candles(self, inst, interval, days, end=None):
        self.candle_reads.append((inst.key, interval, days, end))
        return super().get_candles(inst, interval, days, end=end)


def _nifty(provider):
    return [i for i in liquid_universe(provider) if i.key == "NIFTY"][0]


@pytest.fixture()
def store_root(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset_store, "store_root", lambda: tmp_path / "datasets")
    dataset_store.reset_default_store()
    yield tmp_path / "datasets"
    dataset_store.reset_default_store()


def _artifacts(run_id) -> dict:
    """Every stored column except run-local identity, keyed by cell."""
    excluded = {"id", "run_id", "from_cache", "computed_at"}
    with SessionLocal() as session:
        rows = list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == run_id)))
        return {
            (row.instrument_key, row.interval, row.strategy_key): {
                column.name: getattr(row, column.name)
                for column in BacktestResult.__table__.columns
                if column.name not in excluded
            }
            for row in rows
        }


def _cold_run(provider, **kwargs):
    run_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=INTERVALS, capital=50_000,
        instruments=["NIFTY"], provider=provider, strategies=STRATEGIES,
        **kwargs)
    sweep._join()
    return run_id


# ── 1. a pinned rerun is free and exact ──────────────────────────────────────

def test_pinned_rerun_makes_no_provider_call_and_reproduces_every_artifact(
        store_root):
    init_db(reset=True)
    cold_provider = CountingMockProvider()
    cold_id = _cold_run(cold_provider)
    assert [r[:2] for r in cold_provider.candle_reads] == [
        ("NIFTY", "15minute"), ("NIFTY", "30minute")]
    cold = _artifacts(cold_id)
    assert len(cold) == 2 and all(a["error"] == "" for a in cold.values())

    pins = sweep.resolve_pinned_datasets(
        cold_provider, [_nifty(cold_provider)], INTERVALS)
    assert set(pins) == {sweep.pin_key("NIFTY", i) for i in INTERVALS}

    # Drop every prior result so the RESULT cache cannot serve this rerun: what
    # follows is a real recomputation on stored bytes, not a row copy.
    init_db(reset=True)
    pinned_provider = CountingMockProvider()
    pinned_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=INTERVALS, capital=50_000,
        instruments=["NIFTY"], provider=pinned_provider, strategies=STRATEGIES,
        pinned_datasets=pins)
    sweep._join()

    assert pinned_provider.candle_reads == []          # empty, not merely fewer
    warm = _artifacts(pinned_id)
    assert set(warm) == set(cold)
    assert all(not row.from_cache for row in _rows(pinned_id))
    assert warm == cold
    with SessionLocal() as session:
        run = session.get(BacktestRun, pinned_id)
    assert run.status == "done" and run.done == run.total == 2


def _rows(run_id):
    with SessionLocal() as session:
        return list(session.scalars(
            select(BacktestResult).where(BacktestResult.run_id == run_id)))


# ── 2-5. a pin that cannot be honoured fails closed ──────────────────────────

def test_unpinned_cell_fails_closed_and_the_run_continues(store_root):
    init_db(reset=True)
    cold_provider = CountingMockProvider()
    _cold_run(cold_provider)
    pins = sweep.resolve_pinned_datasets(
        cold_provider, [_nifty(cold_provider)], INTERVALS)
    pins.pop(sweep.pin_key("NIFTY", "30minute"))

    init_db(reset=True)
    pinned_provider = CountingMockProvider()
    run_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=INTERVALS, capital=50_000,
        instruments=["NIFTY"], provider=pinned_provider,
        strategies=["trend_impulse_v3"], pinned_datasets=pins)
    sweep._join()

    assert pinned_provider.candle_reads == []       # NO silent fall-back fetch
    rows = {row.interval: row for row in _rows(run_id)}
    assert rows["15minute"].error == "" and rows["15minute"].bars > 0
    assert "pinned" in rows["30minute"].error
    assert "no dataset address" in rows["30minute"].error
    with SessionLocal() as session:
        assert session.get(BacktestRun, run_id).status == "done"


def test_pinned_dataset_missing_from_the_store_fails_closed(store_root):
    init_db(reset=True)
    provider = CountingMockProvider()
    run_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], capital=50_000,
        instruments=["NIFTY"], provider=provider,
        strategies=["trend_impulse_v3"],
        pinned_datasets={sweep.pin_key("NIFTY", "15minute"): "a" * 64})
    sweep._join()

    assert provider.candle_reads == []
    (row,) = _rows(run_id)
    assert row.bars == 0 and row.trades == 0
    assert "pinned" in row.error and "missing" in row.error


def test_pinned_dataset_whose_content_changed_is_refused_not_refetched(store_root):
    init_db(reset=True)
    cold_provider = CountingMockProvider()
    _cold_run(cold_provider)
    pins = sweep.resolve_pinned_datasets(
        cold_provider, [_nifty(cold_provider)], ["15minute"])
    address = pins[sweep.pin_key("NIFTY", "15minute")]

    # A readable, decodable blob whose bars were revised: only the address
    # recomputation can catch this.
    path = dataset_store.get_store().blob_path(address)
    payload = bytearray(zlib.decompress(path.read_bytes()))
    payload[-1] ^= 0x01
    path.write_bytes(zlib.compress(bytes(payload), 6))

    init_db(reset=True)
    pinned_provider = CountingMockProvider()
    run_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], capital=50_000,
        instruments=["NIFTY"], provider=pinned_provider,
        strategies=["trend_impulse_v3"], pinned_datasets=pins)
    sweep._join()

    assert pinned_provider.candle_reads == []
    (row,) = _rows(run_id)
    assert "pinned" in row.error and "missing" in row.error


def test_pinned_address_describing_another_series_is_refused(store_root):
    """The manifest-mismatch case the address check alone CANNOT catch.

    A 30-minute dataset recomputes to its own address perfectly. Serving it to
    a 15-minute cell would be a silently wrong backtest — the worst outcome
    available here — so the manifest must be compared against the request.
    """
    init_db(reset=True)
    cold_provider = CountingMockProvider()
    _cold_run(cold_provider)
    pins = sweep.resolve_pinned_datasets(
        cold_provider, [_nifty(cold_provider)], INTERVALS)
    swapped = {sweep.pin_key("NIFTY", "15minute"):
               pins[sweep.pin_key("NIFTY", "30minute")]}

    init_db(reset=True)
    pinned_provider = CountingMockProvider()
    run_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], capital=50_000,
        instruments=["NIFTY"], provider=pinned_provider,
        strategies=["trend_impulse_v3"], pinned_datasets=swapped)
    sweep._join()

    assert pinned_provider.candle_reads == []
    (row,) = _rows(run_id)
    assert "pinned" in row.error and "interval" in row.error


def test_pinned_address_from_a_different_window_is_refused(store_root):
    """A pin is bound to the window it was fetched for. Honouring it under a
    different requested window would be a clone wearing a rerun's name."""
    init_db(reset=True)
    cold_provider = CountingMockProvider()
    _cold_run(cold_provider)
    pins = sweep.resolve_pinned_datasets(
        cold_provider, [_nifty(cold_provider)], ["15minute"])

    init_db(reset=True)
    pinned_provider = CountingMockProvider()
    run_id = sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=["15minute"], capital=50_000,
        instruments=["NIFTY"], provider=pinned_provider,
        strategies=["trend_impulse_v3"], lookback_days=30,
        pinned_datasets=pins)
    sweep._join()

    assert pinned_provider.candle_reads == []
    (row,) = _rows(run_id)
    assert "pinned" in row.error and "window" in row.error


def test_a_malformed_pinned_address_is_rejected_before_the_run_exists(store_root):
    init_db(reset=True)
    provider = CountingMockProvider()
    with SessionLocal() as session:
        before = len(list(session.scalars(select(BacktestRun))))
    with pytest.raises(RuntimeError, match="dataset address"):
        sweep.start_sweep(owner_id="owner",
            scope="liquid", intervals=["15minute"], capital=50_000,
            instruments=["NIFTY"], provider=provider,
            pinned_datasets={sweep.pin_key("NIFTY", "15minute"): "nope"})
    assert not sweep.is_running()
    assert provider.candle_reads == []
    with SessionLocal() as session:
        assert len(list(session.scalars(select(BacktestRun)))) == before


# ── 6. absent the parameter, nothing changed ─────────────────────────────────

def test_a_sweep_without_the_pin_parameter_reads_exactly_what_it_always_read(
        store_root):
    """Pinning is opt-in. A fully populated store must not shorten a refresh by
    one single read — that is the stale-history defect cache schema v8 fixed."""
    init_db(reset=True)
    cold_provider = CountingMockProvider()
    _cold_run(cold_provider)
    assert len(dataset_store.get_store().stored_addresses()) == 2

    init_db(reset=True)
    warm_provider = CountingMockProvider()
    _cold_run(warm_provider)

    assert warm_provider.candle_reads == cold_provider.candle_reads
    assert warm_provider.candle_reads == [
        ("NIFTY", "15minute", sweep.MAX_DAYS["15minute"], None),
        ("NIFTY", "30minute", sweep.MAX_DAYS["30minute"], None)]


def test_resolution_is_explicit_and_returns_nothing_for_an_empty_store(
        store_root):
    """`start_sweep` never calls the resolver itself — that is what keeps a
    refresh from becoming a pin. With nothing stored it resolves to nothing."""
    provider = CountingMockProvider()
    assert sweep.resolve_pinned_datasets(
        provider, [_nifty(provider)], INTERVALS) == {}
    assert provider.candle_reads == []


def test_the_happy_path_actually_reads_the_store(store_root, monkeypatch):
    """Zero provider reads is necessary but not sufficient evidence.

    Test 1 proves a pinned rerun makes no provider call and reproduces every
    artifact, and because it also wipes `BacktestResult` and asserts
    `from_cache is False`, the bytes can only have come from the store. That is a
    sound argument, but it is an argument — it holds by elimination rather than by
    observation, so a future change that satisfied a pinned run from some third
    source (an in-process dataset cache across runs, say) would keep every
    assertion in test 1 green while the store went untouched.

    So count the reads directly. One `DatasetStore.get` per pinned cell.
    """
    init_db(reset=True)
    cold_provider = CountingMockProvider()
    _cold_run(cold_provider)
    pins = sweep.resolve_pinned_datasets(
        cold_provider, [_nifty(cold_provider)], INTERVALS)
    assert pins, "nothing was stored, so the rest of this test would be vacuous"

    reads: list[str] = []
    real_get = dataset_store.DatasetStore.get

    def counting_get(self, address):
        reads.append(address)
        return real_get(self, address)

    monkeypatch.setattr(dataset_store.DatasetStore, "get", counting_get)

    init_db(reset=True)
    pinned_provider = CountingMockProvider()
    sweep.start_sweep(owner_id="owner",
        scope="liquid", intervals=INTERVALS, capital=50_000,
        instruments=["NIFTY"], provider=pinned_provider, strategies=STRATEGIES,
        pinned_datasets=pins)
    sweep._join()

    assert pinned_provider.candle_reads == []
    assert sorted(reads) == sorted(pins.values()), (
        f"expected one store read per pinned cell ({sorted(pins.values())}), "
        f"observed {sorted(reads)}")
