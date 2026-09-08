"""Causal-admission gates for new durable backtest work."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.backtest import repository, sweep
from app.core.instruments import get_instrument
from app.db.models import (
    Base,
    BacktestResult,
    BacktestRun,
    IrV2GraphVersion,
    Organization,
    StrategyAdmission,
)
from app.db.session import SessionLocal, init_db
from app.ir.hashing import canonical_json, content_address
from app.ir.v2_graph_versions import facts_from_row
from app.strategy.admission import derive_v2_graph_facts
from app.providers.mock import MockProvider
from app.strategy.registry import get_strategy


@pytest.fixture(autouse=True)
def _database():
    init_db(reset=True)


def _phase4_binding(owner_id: str = "owner") -> dict:
    def address(char: str) -> str:
        return "sha256:" + char * 64

    return {
        "owner_id": owner_id,
        "authored_ir_address": address("a"),
        "registry_snapshot_address": address("b"),
        "resolved_graph_address": address("c"),
        "implementation_closure_address": address("d"),
        "declaration_addresses": (address("e"),),
        "plan_address": address("f"),
        "capability_assessment_address": address("1"),
        "dataset_manifest_address": address("2"),
        "market_truth_snapshot_address": address("3"),
        "evaluation_policy_address": address("4"),
    }


def _admitted(address: str, *, phase4_binding=None):
    strategy = get_strategy("trend_impulse_v3")
    return SimpleNamespace(
        admission_address=address, strategy=strategy,
        strategy_key=strategy.key, strategy_version=strategy.version,
        graph_address=None, attribution_state="NON_GRAPH",
        phase4_binding=phase4_binding)


def _persist_phase4_fixture():
    """Persist a constructor-authorized v2 receipt with its injected registry.

    The shipped executable catalogue is intentionally not involved.  The fixture
    module owns a small ``PlatformRegistry`` containing only the accepted test
    component and its data declaration.
    """
    from app.core.strategy_admissions import put
    from tests.test_phase4_capability_admission import _phase4_fixture

    registry, _document, _plan, _assessment, wrapper = _phase4_fixture()
    with SessionLocal() as session:
        session.add(Organization(organization_id="owner-a", name="Owner A"))
        session.flush()
        put(session, wrapper)
        session.commit()
    return registry, wrapper


def _fixture_graph_row_values(wrapper, **changes):
    values = dict(derive_v2_graph_facts(wrapper).__dict__)
    values.update(changes)
    return values


def _fixture_receipt_values(document):
    return {
        "owner_id": document["owner_id"],
        "admission_address": content_address(document),
        "graph_identifier": document["graph_identifier"],
        "graph_version": document["graph_version"],
        "graph_address": document["graph_address"],
        "artifact_json": canonical_json(document),
        "scheme": document["scheme"],
        "contract_suite": document["contract_suite"],
        "parity_suite": document["parity_suite"],
        "format_version": document["format_version"],
        "content_address": document["content_address"],
    }


def _memory_phase4_session(wrapper, *, graph_changes=None, document=None,
                           include_graph=True):
    """Build a SQLAlchemy-only fixture for explicit tamper/collision cases."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Organization(organization_id="owner-a", name="Owner A"))
    payload = document or wrapper.to_dict()
    if include_graph:
        session.execute(IrV2GraphVersion.__table__.insert().values(
            **_fixture_graph_row_values(wrapper, **(graph_changes or {}))))
    session.execute(StrategyAdmission.__table__.insert().values(
        **_fixture_receipt_values(payload)))
    session.commit()
    return engine, session, content_address(payload)


def test_phase4_loader_positive_verification_then_stable_runtime_refusal(
        monkeypatch):
    """A contextless v2 caller refuses before any Phase 4 authority work."""
    registry, wrapper = _persist_phase4_fixture()
    with SessionLocal() as session:
        graph = session.get(IrV2GraphVersion,
                            ("owner-a", wrapper.graph_identifier, wrapper.graph_version))
        assert graph is not None
        # The graph fact is intentionally present: missing explicit research
        # context, not a missing execution row, is the decisive refusal.
        facts = facts_from_row(graph)
        assert facts.content_address == wrapper.content_address

        constructed = []

        def forbidden_strategy(*_args, **_kwargs):
            constructed.append(True)
            raise AssertionError("v2 refusal reached legacy IRGraphStrategy")

        monkeypatch.setattr(
            "app.strategy.ir_adapter.IRGraphStrategy", forbidden_strategy)

        # This replacement is only a tripwire: a Phase 4 dispatch must not import
        # or query the legacy executable GraphVersion at all.
        class ForbiddenLegacyGraphVersion:
            def __new__(cls, *_args, **_kwargs):
                raise AssertionError("v2 refusal reached legacy GraphVersion")

        monkeypatch.setattr("app.db.models.GraphVersion", ForbiddenLegacyGraphVersion)
        with pytest.raises(repository.AdmissionRequired) as caught:
            repository.load_verified_admission(
                session, owner_id="owner-a",
                admission_address=wrapper.admission_address, registry=registry)

    assert caught.value.args == ("PHASE4_CONTEXT_REQUIRED",)
    assert constructed == []


def test_phase4_loader_refuses_owner_collision_without_cross_tenant_read():
    registry, wrapper = _persist_phase4_fixture()
    with SessionLocal() as session:
        with pytest.raises(repository.AdmissionRequired) as caught:
            repository.load_verified_admission(
                session, owner_id="owner-b",
                admission_address=wrapper.admission_address, registry=registry)
    # The owner-scoped receipt lookup must fail closed before reconstructing bytes
    # or considering the owner-a graph row.
    assert caught.value.args == ("RECEIPT_STALE",)


def test_phase4_loader_refuses_a_receipt_with_tampered_assessment():
    # Reuse the constructor-authorized wrapper bytes, but insert a tampered receipt
    # through SQLAlchemy Core.  The database identity checks still apply; this case
    # models bytes changed outside the trusted admission seam.
    from tests.test_phase4_capability_admission import _phase4_fixture

    registry, _document, _plan, _assessment, wrapper = _phase4_fixture()
    payload = wrapper.to_dict()
    payload["capability_assessment"]["fact"]["requirement_results"][0]["result"] = "UNKNOWN"
    engine, session, address = _memory_phase4_session(
        wrapper, document=payload)
    try:
        with pytest.raises(repository.AdmissionRequired) as caught:
            repository.load_verified_admission(
                session, owner_id="owner-a", admission_address=address,
                registry=registry)
        assert caught.value.args == ("PHASE4_CONTEXT_REQUIRED",)
    finally:
        session.close()
        engine.dispose()


@pytest.mark.parametrize("field", ["graph_address", "registry_snapshot_address"])
def test_phase4_loader_refuses_tampered_graph_or_registry_fact(field):
    from tests.test_phase4_capability_admission import _phase4_fixture

    registry, _document, _plan, _assessment, wrapper = _phase4_fixture()
    forged = "sha256:" + ("f" if field == "graph_address" else "e") * 64
    engine, session, address = _memory_phase4_session(
        wrapper, graph_changes={field: forged})
    try:
        with pytest.raises(repository.AdmissionRequired) as caught:
            repository.load_verified_admission(
                session, owner_id="owner-a", admission_address=address,
                registry=registry)
        assert caught.value.args == ("PHASE4_CONTEXT_REQUIRED",)
    finally:
        session.close()
        engine.dispose()


def test_phase4_loader_refuses_receipt_without_its_durable_graph():
    from tests.test_phase4_capability_admission import _phase4_fixture

    registry, _document, _plan, _assessment, wrapper = _phase4_fixture()
    engine, session, address = _memory_phase4_session(
        wrapper, include_graph=False)
    try:
        with pytest.raises(repository.AdmissionRequired) as caught:
            repository.load_verified_admission(
                session, owner_id="owner-a", admission_address=address,
                registry=registry)
        assert caught.value.args == ("PHASE4_CONTEXT_REQUIRED",)
    finally:
        session.close()
        engine.dispose()


def test_legacy_v1_loader_dispatch_and_bytes_remain_unchanged(
        admitted_backtest_receipt):
    """The v2 refusal branch must not alter the legacy receipt path."""
    init_db(reset=True)
    identity = admitted_backtest_receipt()
    with SessionLocal() as session:
        admitted = repository.load_verified_admission(
            session, owner_id="owner", admission_address=identity["admission_address"])
    assert admitted.admission_address == identity["admission_address"]
    assert admitted.strategy is not None


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


def test_run_and_results_copy_the_admission_address(admitted_backtest_receipt):
    """Hypothesis: a verified run can persist rows detached from its receipt."""
    identity = admitted_backtest_receipt()
    address = identity["admission_address"]
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
    admitted = _admitted(address)
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


def test_enqueue_persists_verified_phase4_context_as_reserved_descriptor_data(monkeypatch):
    address = "sha256:" + "6" * 64
    binding = _phase4_binding()
    admitted = _admitted(address, phase4_binding=binding)
    monkeypatch.setattr(
        repository, "_verify_enqueue_admission",
        lambda *_args, **_kwargs: admitted)
    with SessionLocal() as session:
        run = repository.enqueue_run(
            session, owner_id="owner", scope="liquid", intervals="15minute",
            capital=50_000.0, total=1, admission_address=address,
            request_json=json.dumps({
                "scope": "liquid", "intervals": ["15minute"],
                "admission_address": address,
            }),
        )
        descriptor = json.loads(run.request_json)
    assert descriptor["_phase4_binding"] == {
        **binding, "declaration_addresses": [binding["declaration_addresses"][0]],
    }


def test_enqueue_refuses_forged_phase4_context_before_persisting(monkeypatch):
    address = "sha256:" + "7" * 64
    binding = _phase4_binding()
    admitted = _admitted(address, phase4_binding=binding)
    monkeypatch.setattr(
        repository, "_verify_enqueue_admission",
        lambda *_args, **_kwargs: admitted)
    forged = {**binding, "plan_address": "sha256:" + "0" * 64}
    with SessionLocal() as session:
        with pytest.raises(repository.AdmissionRequired, match="ARTEFACT_MISMATCH"):
            repository.enqueue_run(
                session, owner_id="owner", scope="liquid", intervals="15minute",
                capital=50_000.0, total=1, admission_address=address,
                request_json=json.dumps({
                    "admission_address": address,
                    "_phase4_binding": {
                        **forged,
                        "declaration_addresses": list(forged["declaration_addresses"]),
                    },
                }),
            )


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


def test_worker_refuses_phase4_binding_mismatch_before_provider(monkeypatch):
    address = "sha256:" + "8" * 64
    expected = _phase4_binding()
    run_id, claim_token = _claimed_run()
    admitted = _admitted(address, phase4_binding=expected)
    monkeypatch.setattr(
        repository, "load_verified_admission",
        lambda *_args, **_kwargs: admitted)
    forged = {**expected, "plan_address": "sha256:" + "0" * 64}
    provider = _ProviderTripwire()
    sweep._run(
        run_id, provider, [get_instrument("NIFTY")], ["15minute"], 50_000.0,
        {"lookback_days": None, "start": None, "end": None, "label": "max"},
        [], None, 1, address, forged, owner_id="owner", claim_token=claim_token,
    )
    assert provider.reads == 0
    with SessionLocal() as session:
        run = session.get(BacktestRun, run_id)
        assert run is not None and run.status == "error" and run.note == "ARTEFACT_MISMATCH"
        assert session.scalar(select(BacktestResult).where(BacktestResult.run_id == run_id)) is None


def bypass_backtest_worker(monkeypatch, admitted):
    """Mutation: remove only the worker's fresh receipt verification."""
    monkeypatch.setattr(sweep, "_verify_worker_admission", lambda **_kwargs: admitted)


def test_worker_bypass_mutant_is_killed(monkeypatch):
    """Removing only the worker check makes the provider-before-refusal guard fail."""
    address = "sha256:" + "1" * 64
    run_id, claim_token = _claimed_run()
    admitted = _admitted(address)
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


def test_native_graph_claim_refuses_a_forged_non_graph_result_without_progress(
        admitted_entry_identity):
    """A claimed graph run cannot downgrade its result source/state tuple."""
    with SessionLocal() as session:
        identity = admitted_entry_identity(session, owner_id="owner")
        run = BacktestRun(
            owner_id="owner", scope="liquid", intervals="15minute",
            capital=50_000.0, total=1, status="pending",
            admission_address=identity["admission_address"],
        )
        session.add(run)
        session.flush()
        claim = repository.claim_run(
            session, owner_id="owner", run_id=run.id, claimed_by="test",
            lease_seconds=60)
        session.commit()
        assert claim is not None
        run_id, claim_token = run.id, claim.claim_token

    with SessionLocal() as session:
        before = session.execute(select(
            BacktestRun.done, BacktestRun.heartbeat_at,
            BacktestRun.claim_expires_at).where(
                BacktestRun.owner_id == "owner", BacktestRun.id == run_id)).one()
        with pytest.raises(repository.AdmissionRequired,
                           match="GRAPH_ATTRIBUTION_MISMATCH"):
            repository.append_claimed_result_batch(
                session, owner_id="owner", run_id=run_id,
                claim_token=claim_token, values=[{
                    "instrument_key": "NIFTY", "interval": "15minute",
                    "strategy_key": "trend_impulse_v3",
                    "strategy_version": "forged-content-v1",
                    "graph_address": None,
                    "attribution_state": "NON_GRAPH",
                    "admission_address": identity["admission_address"],
                }])
        after = session.execute(select(
            BacktestRun.done, BacktestRun.heartbeat_at,
            BacktestRun.claim_expires_at).where(
                BacktestRun.owner_id == "owner", BacktestRun.id == run_id)).one()
        assert after == before
        assert session.scalar(select(BacktestResult).where(
            BacktestResult.owner_id == "owner",
            BacktestResult.run_id == run_id)) is None


def _reclaimable_run(address: str, phase4_binding: dict | None = None) -> int:
    carrier = _admitted(address, phase4_binding=phase4_binding)
    descriptor = {
        "scope": "liquid", "intervals": ["15minute"], "capital": 50_000.0,
        "strategies": [{"key": "trend_impulse_v3", "version": "ignored"}],
        "admission_address": address,
        "attribution": sweep._admission_attribution(carrier),
    }
    if phase4_binding is not None:
        descriptor["_phase4_binding"] = {
            **phase4_binding,
            "declaration_addresses": list(phase4_binding["declaration_addresses"]),
        }
    with SessionLocal() as session:
        run = BacktestRun(
            owner_id="owner", scope="liquid", intervals="15minute", capital=50_000.0,
            total=1, status="pending", admission_address=address,
            request_json=json.dumps(descriptor),
        )
        session.add(run)
        session.commit()
        return run.id


PHASE4_MUTATIONS = ("missing", *_phase4_binding().keys())


@pytest.mark.parametrize("mutation", PHASE4_MUTATIONS)
def test_reclaim_refuses_missing_or_mutated_phase4_context_before_provider(
        monkeypatch, mutation):
    address = "sha256:" + "9" * 64
    expected = _phase4_binding()
    descriptor_binding = None
    if mutation != "missing":
        descriptor_binding = dict(expected)
        if mutation == "owner_id":
            descriptor_binding[mutation] = "owner-b"
        elif mutation == "declaration_addresses":
            descriptor_binding[mutation] = ("sha256:" + "f" * 64,)
        else:
            descriptor_binding[mutation] = "sha256:" + "f" * 64
    run_id = _reclaimable_run(address, descriptor_binding)
    admitted = _admitted(address, phase4_binding=expected)
    calls = {"provider": 0, "cache": 0}

    def poison_provider():
        calls["provider"] += 1
        raise AssertionError("forged Phase 4 context reached provider construction")

    def poison_cache(*_args, **_kwargs):
        calls["cache"] += 1
        raise AssertionError("forged Phase 4 context reached cache access")

    monkeypatch.setattr(repository, "load_verified_admission",
                        lambda *_args, **_kwargs: admitted)
    # This test owns the post-claim descriptor binding seam.  The closed-set
    # classifier is covered separately with real persisted receipt bytes.
    monkeypatch.setattr(repository, "reclaim_admission_format",
                        lambda *_args, **_kwargs: 1)
    monkeypatch.setattr("app.providers.factory.get_provider", poison_provider)
    monkeypatch.setattr(sweep, "_execution_address", poison_cache)
    assert sweep.dispatch_reclaimable(owner_id="owner", maximum=1) == []
    assert calls == {"provider": 0, "cache": 0}
    with SessionLocal() as session:
        run = session.get(BacktestRun, run_id)
        assert run is not None and run.status == "error" and run.note == "ARTEFACT_MISMATCH"
        assert session.scalar(select(BacktestResult).where(BacktestResult.run_id == run_id)) is None


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
    monkeypatch.setattr(repository, "reclaim_admission_format",
                        lambda *_args, **_kwargs: 1)
    monkeypatch.setattr("app.providers.factory.get_provider", poison_provider)
    assert sweep.dispatch_reclaimable(owner_id="owner", maximum=1) == []
    assert calls == {"provider": 0}
    with SessionLocal() as session:
        run = session.get(BacktestRun, run_id)
        assert run is not None and run.status == "error" and run.note == "RECEIPT_STALE"
        assert session.scalar(select(BacktestResult).where(BacktestResult.run_id == run_id)) is None
