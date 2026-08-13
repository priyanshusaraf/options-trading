"""Causal-admission gates for new durable backtest work."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.backtest import repository, sweep
from app.core.instruments import get_instrument
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal, init_db
from app.providers.mock import MockProvider
from app.strategy.registry import get_strategy


@pytest.fixture(autouse=True)
def _database():
    init_db(reset=True)


def _assert_missing_admission_is_rejected():
    with SessionLocal() as session:
        with pytest.raises(repository.AdmissionRequired, match="ADMISSION_REQUIRED"):
            repository.enqueue_run(
                session, owner_id="owner", scope="NIFTY", intervals="5minute",
                capital=50_000.0, total=1, admission_address=None,
            )


def test_backtest_without_admission_is_rejected():
    """Hypothesis: a new durable backtest can bypass causal admission at enqueue."""
    _assert_missing_admission_is_rejected()


def test_backtest_refuses_one_receipt_for_multiple_strategies():
    """Hypothesis: one run receipt can silently cover several strategy artifacts."""
    with pytest.raises(repository.AdmissionRequired, match="ADMISSION_REQUIRED"):
        sweep.start_sweep(
            owner_id="owner-a", scope="liquid", intervals=["15minute"],
            strategies=["trend_impulse_v3", "expanding_z_v4"],
            admission_address="sha256:" + "a" * 64,
        )


def test_run_and_results_copy_the_admission_address(monkeypatch):
    """Hypothesis: a verified run can persist rows detached from its receipt."""
    address = "sha256:" + "3" * 64
    monkeypatch.setattr(
        repository, "load_verified_admission",
        lambda _session, **_kwargs: SimpleNamespace(
            admission_address=address, strategy=get_strategy("trend_impulse_v3")),
    )
    run_id = sweep.start_sweep(
        owner_id="owner", scope="liquid", intervals=["15minute"],
        instruments=["NIFTY"], provider=MockProvider(), admission_address=address,
    )
    sweep._join()
    with SessionLocal() as session:
        run = session.get(BacktestRun, run_id)
        rows = list(session.scalars(select(BacktestResult).where(BacktestResult.run_id == run_id)))
    assert run is not None and run.admission_address == address
    assert rows and {row.admission_address for row in rows} == {address}


def test_start_sweep_reverifies_the_claimed_receipt_before_provider_or_universe(monkeypatch):
    """A receipt revoked after reservation must stop before any data boundary."""
    address = "sha256:" + "4" * 64
    admitted = SimpleNamespace(
        admission_address=address, strategy=get_strategy("trend_impulse_v3"))
    calls = {"verify": 0, "provider": 0, "universe": 0}

    def staged_admission(*_args, **_kwargs):
        calls["verify"] += 1
        if calls["verify"] == 3:
            raise repository.AdmissionRequired("RECEIPT_STALE")
        return admitted

    def poison_provider():
        calls["provider"] += 1
        raise AssertionError("stale admission reached provider construction")

    def poison_universe(_provider):
        calls["universe"] += 1
        raise AssertionError("stale admission reached universe I/O")

    monkeypatch.setattr(repository, "load_verified_admission", staged_admission)
    monkeypatch.setattr(sweep, "get_provider", poison_provider)
    monkeypatch.setattr(sweep, "liquid_universe", poison_universe)
    with pytest.raises(repository.AdmissionRequired, match="RECEIPT_STALE"):
        sweep.start_sweep(
            owner_id="owner", scope="liquid", intervals=["15minute"],
            admission_address=address,
        )
    assert calls == {"verify": 3, "provider": 0, "universe": 0}
    with SessionLocal() as session:
        run = session.scalar(select(BacktestRun).where(BacktestRun.owner_id == "owner"))
        assert run is not None and run.status == "error" and run.note == "RECEIPT_STALE"
        assert session.scalar(select(BacktestResult).where(BacktestResult.run_id == run.id)) is None


def bypass_backtest_enqueue(monkeypatch):
    """Mutation: remove only the enqueue receipt check."""
    monkeypatch.setattr(repository, "_verify_enqueue_admission", lambda *_args, **_kwargs: None)


def test_enqueue_bypass_mutant_is_killed(monkeypatch):
    """Removing only the enqueue check makes the real missing-address guard fail."""
    bypass_backtest_enqueue(monkeypatch)
    with pytest.raises(pytest.fail.Exception):
        _assert_missing_admission_is_rejected()


def _claimed_run():
    with SessionLocal() as session:
        run = BacktestRun(
            owner_id="owner", scope="liquid", intervals="15minute",
            capital=50_000.0, total=1, status="pending",
            admission_address="sha256:" + "1" * 64,
        )
        session.add(run)
        session.flush()
        claim = repository.claim_run(
            session, owner_id="owner", run_id=run.id, claimed_by="test", lease_seconds=60)
        session.commit()
    assert claim is not None
    return run.id, claim.claim_token


class _ProviderTripwire:
    def __init__(self):
        self.reads = 0

    def get_candles(self, *_args, **_kwargs):
        self.reads += 1
        raise AssertionError("worker reached provider after admission refusal")


def _assert_worker_refuses_before_provider(run_id: int, claim_token: str,
                                            admission_address: str,
                                            provider: _ProviderTripwire) -> None:
    sweep._run(
        run_id, provider, [get_instrument("NIFTY")], ["15minute"], 50_000.0,
        {"lookback_days": None, "start": None, "end": None, "label": "max"},
        [], None, 1, admission_address, owner_id="owner", claim_token=claim_token,
    )
    assert provider.reads == 0
    with SessionLocal() as session:
        run = session.get(BacktestRun, run_id)
        assert run is not None and run.status == "error" and run.note == "RECEIPT_STALE"
        assert session.scalar(select(BacktestResult).where(BacktestResult.run_id == run_id)) is None


def test_worker_reverifies_receipt_before_provider_access(monkeypatch):
    """Hypothesis: an enqueued receipt remains trusted when the worker starts."""
    address = "sha256:" + "1" * 64
    run_id, claim_token = _claimed_run()
    monkeypatch.setattr(
        repository, "load_verified_admission",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(repository.AdmissionRequired("RECEIPT_STALE")),
    )
    _assert_worker_refuses_before_provider(run_id, claim_token, address, _ProviderTripwire())


def bypass_backtest_worker(monkeypatch, admitted):
    """Mutation: remove only the worker's fresh receipt verification."""
    monkeypatch.setattr(sweep, "_verify_worker_admission", lambda **_kwargs: admitted)


def test_worker_bypass_mutant_is_killed(monkeypatch):
    """Removing only the worker check makes the provider-before-refusal guard fail."""
    address = "sha256:" + "1" * 64
    run_id, claim_token = _claimed_run()
    admitted = SimpleNamespace(
        admission_address=address, strategy=get_strategy("trend_impulse_v3"))
    monkeypatch.setattr(
        repository, "load_verified_admission",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(repository.AdmissionRequired("RECEIPT_STALE")),
    )
    bypass_backtest_worker(monkeypatch, admitted)
    provider = _ProviderTripwire()
    with pytest.raises(AssertionError):
        _assert_worker_refuses_before_provider(
            run_id, claim_token, address, provider)
    assert provider.reads == 1, "the bypass mutant must reach the provider tripwire"


def test_claimed_batch_rejects_a_result_bound_to_another_receipt():
    """A current lease cannot mix result provenance from a second run receipt."""
    run_id, claim_token = _claimed_run()
    with SessionLocal() as session:
        with pytest.raises(repository.AdmissionRequired, match="ARTEFACT_MISMATCH"):
            repository.append_claimed_result_batch(
                session, owner_id="owner", run_id=run_id, claim_token=claim_token,
                values=[{
                    "instrument_key": "NIFTY", "interval": "15minute",
                    "strategy_key": "trend_impulse_v3", "strategy_version": "v1",
                    "admission_address": "sha256:" + "2" * 64,
                }],
            )
        assert session.scalar(select(BacktestResult).where(
            BacktestResult.owner_id == "owner", BacktestResult.run_id == run_id)) is None


def _reclaimable_run(address: str) -> int:
    descriptor = {
        "scope": "liquid", "intervals": ["15minute"], "capital": 50_000.0,
        "strategies": [{"key": "trend_impulse_v3", "version": "ignored"}],
        "admission_address": address,
    }
    with SessionLocal() as session:
        run = BacktestRun(
            owner_id="owner", scope="liquid", intervals="15minute", capital=50_000.0,
            total=1, status="pending", admission_address=address,
            request_json=__import__("json").dumps(descriptor),
        )
        session.add(run)
        session.commit()
        return run.id


def test_reclaim_stale_receipt_persists_only_its_stable_code_before_provider(monkeypatch):
    """Reclaim terminalizes a stale receipt without constructing a provider."""
    address = "sha256:" + "5" * 64
    run_id = _reclaimable_run(address)
    calls = {"provider": 0}

    def poison_provider():
        calls["provider"] += 1
        raise AssertionError("stale reclaim reached provider construction")

    monkeypatch.setattr(
        repository, "load_verified_admission",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            repository.AdmissionRequired("RECEIPT_STALE")),
    )
    monkeypatch.setattr("app.providers.factory.get_provider", poison_provider)
    assert sweep.dispatch_reclaimable(owner_id="owner", maximum=1) == []
    assert calls == {"provider": 0}
    with SessionLocal() as session:
        run = session.get(BacktestRun, run_id)
        assert run is not None and run.status == "error" and run.note == "RECEIPT_STALE"
        assert session.scalar(select(BacktestResult).where(BacktestResult.run_id == run_id)) is None
