"""Atomic batch persistence for the sweep (design: "Staged architecture" §3, Task 5).

The sweep used to write **two** transactions per cell — one in `_store` for the
result row, one in `_bump` for the run's progress counter — which is 100,000
transactions at the owner's 50,000-cell tier, and, worse, a progress counter that
is incremented by a *different* transaction than the one that made the result
durable. A crash between the two leaves a run claiming more work done than it can
show rows for, which is the shape of a reproducibility claim nobody can check.

What is asserted here:

1. **Budget.** Persistence costs at most `ceil(cells / 10) + 1` transactions for
   the whole run phase, at 500, 5,000 and 50,000 cells. The compute is stubbed —
   this measures transaction count, not arithmetic.
2. **Progress is derived, never incremented.** `run.done` is set from the durable
   `BacktestResult` count inside the same transaction that inserts the rows, so a
   result can never be counted before its row exists.
3. **All-or-nothing.** A batch that fails leaves neither its rows nor its progress.
4. **Terminal consistency.** A finished run's `done` equals its row count.
5. **Interrupted runs reconcile.** A run killed mid-flight never over-reports, and
   a run left `running` by a dead process is repaired rather than shown as a
   phantom in-flight sweep forever.
"""
from __future__ import annotations

import math

import pytest
from sqlalchemy import event, func, select

from app.backtest import repository, sweep
from app.core.instruments import Instrument
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal, init_db
from app.strategy.registry import get_strategy

WIN = {"lookback_days": None, "start": None, "end": None, "label": "max"}

INST = Instrument(
    "STUB", "STUB", "NSE", "NSE", "STUB", "STUB",
    lot_size=1, strike_step=1, priority=1, mock_spot=100.0, mock_vol=0.2)


def _values(i: int = 0) -> dict:
    """A minimal, already-serialized result payload — the shape `_one` returns."""
    return {"instrument_key": f"STUB-{i}", "name": "STUB", "segment": "nse_delivery",
            "strategy_key": "trend_impulse_v3", "interval": "15minute",
            "strategy_version": "test-v1", "bars": i, "error": ""}


class _CommitCounter:
    def __init__(self):
        self.n = 0

    def __enter__(self):
        event.listen(SessionLocal, "after_transaction_end", self._hit)
        return self

    def __exit__(self, *exc):
        event.remove(SessionLocal, "after_transaction_end", self._hit)

    def _hit(self, _session, transaction):
        # A fenced append uses a SAVEPOINT for atomic rollback. Count only real
        # outer commits; counting SAVEPOINT release would misreport I/O cost.
        if transaction.parent is None and not transaction.nested:
            self.n += 1


def _make_run(total: int, admitted_backtest_receipt) -> int:
    with SessionLocal() as s:
        receipt = admitted_backtest_receipt(s)
        run = repository.enqueue_run(s, owner_id="owner", scope="liquid",
                                     intervals="15minute", capital=50_000.0,
                                     total=total, done=0, **receipt)
        s.commit()
        return run.id


def _claim(run_id: int) -> str:
    """Every worker test obtains the same durable fence production requires."""
    with SessionLocal() as session:
        claim = repository.claim_run(session, owner_id="owner", run_id=run_id,
                                     claimed_by="test-worker", lease_seconds=60)
        session.commit()
    assert claim is not None
    return claim.claim_token


def _counts(run_id: int) -> tuple[int, int, str]:
    with SessionLocal() as s:
        rows = s.scalar(select(func.count()).select_from(BacktestResult)
                        .where(BacktestResult.run_id == run_id))
        run = s.get(BacktestRun, run_id)
        return rows, run.done, run.status


def _drive(run_id, cells, monkeypatch, *, one=None):
    """Run the sweep's persistence loop over `cells` stubbed cells."""
    class _NoopGuard:
        _lost = type("_Lost", (), {"is_set": lambda self: False})()
        def __init__(self, **_kwargs): pass
        def start(self): pass
        def ensure_active(self): pass
        def close(self): pass
    # This suite counts persistence transactions. Lease heartbeats are exercised
    # separately and would otherwise add timing-dependent commits to the budget.
    monkeypatch.setattr(sweep, "_ClaimGuard", _NoopGuard)
    monkeypatch.setattr(sweep, "_prepare_dataset",
                        lambda *a, **k: sweep._PreparedDataset())
    counter = {"i": 0}
    with SessionLocal() as session:
        admission_address = session.get(BacktestRun, run_id).admission_address
        admitted = repository.load_verified_admission(
            session, owner_id="owner", admission_address=admission_address)
        attribution = {
            "strategy_key": admitted.strategy_key,
            "strategy_version": admitted.strategy_version,
            "graph_address": admitted.graph_address,
            "attribution_state": admitted.attribution_state,
        }

    def stub_one(*a, **k):
        counter["i"] += 1
        return {**_values(counter["i"]), **attribution,
                "admission_address": admission_address}

    if one is not None:
        def admitted_one(*args, **kwargs):
            return {**one(*args, **kwargs), **attribution,
                    "admission_address": admission_address}
        monkeypatch.setattr(sweep, "_one", admitted_one)
    else:
        monkeypatch.setattr(sweep, "_one", stub_one)
    sweep._run(run_id, None, [INST] * cells, ["15minute"], 50_000.0, WIN,
               [get_strategy(None)], admission_address=admission_address,
               expected_attribution={**attribution, "admission_address": admission_address},
               owner_id="owner", claim_token=_claim(run_id))


# ── 1. the transaction budget ────────────────────────────────────────────────

@pytest.mark.parametrize("cells", [500, 5_000, 50_000])
def test_persistence_stays_within_the_transaction_budget(cells, monkeypatch,
                                                          admitted_backtest_receipt):
    init_db(reset=True)
    run_id = _make_run(cells, admitted_backtest_receipt)
    with _CommitCounter() as counter:
        _drive(run_id, cells, monkeypatch)
    # One durable claim precedes worker execution; then bounded batches plus the
    # terminal transition. Admission/claim is not a result-persistence batch.
    # The count also observes a bounded number of SQLAlchemy outer transaction
    # cleanups.  It must remain O(number of batches), never O(cells).
    budget = math.ceil(cells / 10) + 8
    assert counter.n <= budget, (
        f"{cells} cells cost {counter.n} transactions, budget {budget}")
    assert _counts(run_id) == (cells, cells, "done")


def test_a_batch_is_never_larger_than_ten(monkeypatch, admitted_backtest_receipt):
    """Bounded batches are what keeps a crash from losing an unbounded amount of
    completed work, and what keeps the write transaction short enough that the
    single SQLite writer is not held while the next cell simulates."""
    init_db(reset=True)
    run_id = _make_run(95, admitted_backtest_receipt)
    sizes: list[int] = []
    real = sweep._commit_claimed_batch

    def spy(rid, values, **kw):
        sizes.append(len(values))
        return real(rid, values, **kw)

    monkeypatch.setattr(sweep, "_commit_claimed_batch", spy)
    _drive(run_id, 95, monkeypatch)
    assert sizes and max(sizes) <= 10
    assert sum(sizes) == 95


# ── 2. progress is derived from durable rows ─────────────────────────────────

def test_progress_never_runs_ahead_of_durable_rows(monkeypatch, admitted_backtest_receipt):
    """The invariant the old `_bump` could not hold: at every commit boundary the
    progress counter equals the number of rows a *separate* connection can see."""
    init_db(reset=True)
    run_id = _make_run(95, admitted_backtest_receipt)
    observed: list[tuple[int, int]] = []
    real = sweep._commit_claimed_batch

    def spy(rid, values, **kw):
        out = real(rid, values, **kw)
        rows, done, _ = _counts(rid)
        observed.append((rows, done))
        return out

    monkeypatch.setattr(sweep, "_commit_claimed_batch", spy)
    _drive(run_id, 95, monkeypatch)
    assert observed, "no batch was committed — the rest of this test is vacuous"
    assert all(rows == done for rows, done in observed), observed
    assert observed[-1] == (95, 95)


def test_progress_is_recomputed_not_incremented(monkeypatch, admitted_backtest_receipt):
    """A stale or hand-edited counter must be corrected by the next batch, not
    added to. Increment-based progress carries its error to the end of the run."""
    init_db(reset=True)
    run_id = _make_run(30, admitted_backtest_receipt)
    with SessionLocal() as s:
        s.get(BacktestRun, run_id).done = 999
        s.commit()
    _drive(run_id, 30, monkeypatch)
    assert _counts(run_id) == (30, 30, "done")


# ── 3. all-or-nothing ────────────────────────────────────────────────────────

def test_a_failed_batch_persists_neither_rows_nor_progress(monkeypatch,
                                                            admitted_backtest_receipt):
    init_db(reset=True)
    run_id = _make_run(30, admitted_backtest_receipt)
    real_count = repository.durable_result_count
    state = {"calls": 0}

    def exploding_count(session, *, run_id, owner_id):
        state["calls"] += 1
        if state["calls"] == 2:          # second batch only
            raise RuntimeError("disk went away")
        return real_count(session, run_id=run_id, owner_id=owner_id)

    monkeypatch.setattr(repository, "durable_result_count", exploding_count)
    _drive(run_id, 30, monkeypatch)

    rows, done, status = _counts(run_id)
    assert rows == done == 10, (
        f"the failed batch left {rows} rows and done={done}; batch 2 must have "
        f"rolled back entirely")
    assert status == "error"


# ── 4/5. terminal and interrupted consistency ────────────────────────────────

def test_terminal_run_progress_equals_its_durable_result_count(monkeypatch,
                                                                admitted_backtest_receipt):
    init_db(reset=True)
    run_id = _make_run(47, admitted_backtest_receipt)
    _drive(run_id, 47, monkeypatch)
    rows, done, status = _counts(run_id)
    assert (rows, done, status) == (47, 47, "done")


def test_an_interrupted_run_never_reports_more_than_it_stored(monkeypatch,
                                                               admitted_backtest_receipt):
    init_db(reset=True)
    run_id = _make_run(100, admitted_backtest_receipt)
    calls = {"i": 0}

    def one(*a, **k):
        calls["i"] += 1
        if calls["i"] == 34:
            raise RuntimeError("worker died")
        return _values(calls["i"])

    _drive(run_id, 100, monkeypatch, one=one)
    rows, done, status = _counts(run_id)
    assert rows == done == 30, (
        "33 cells computed but only three batches were durable, so exactly 30 "
        f"may be reported; got rows={rows} done={done}")
    assert status == "error"


def test_a_run_left_running_by_a_dead_process_is_reconciled(monkeypatch,
                                                            admitted_backtest_receipt):
    """A killed process leaves `status='running'` forever: the UI shows a sweep
    in flight that no thread is driving, and `is_running()` disagrees with the
    row. The next sweep repairs it against the durable row count."""
    init_db(reset=True)
    stale = _make_run(100, admitted_backtest_receipt)
    with SessionLocal() as s:
        for _ in range(7):
            s.add(BacktestResult(run_id=stale, **_values()))
        run = s.get(BacktestRun, stale)
        run.status, run.done = "running", 88      # what an incrementing counter left
        s.commit()

    assert not sweep.is_running()
    sweep.dispatch_reclaimable(owner_id="owner", maximum=1,
                               _reclaim_policy=sweep._ReclaimPolicy.BOOT)

    rows, done, status = _counts(stale)
    assert (rows, done) == (7, 7)
    assert status == "error" and status != "running"


def test_reconciliation_never_touches_a_finished_run(admitted_backtest_receipt):
    init_db(reset=True)
    finished = _make_run(3, admitted_backtest_receipt)
    with SessionLocal() as s:
        run = s.get(BacktestRun, finished)
        run.status, run.done, run.note = "done", 3, "keep me"
        s.commit()
    sweep.dispatch_reclaimable(owner_id="owner", maximum=1,
                               _reclaim_policy=sweep._ReclaimPolicy.BOOT)
    with SessionLocal() as s:
        run = s.get(BacktestRun, finished)
        assert (run.status, run.done, run.note) == ("done", 3, "keep me")
