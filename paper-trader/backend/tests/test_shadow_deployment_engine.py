"""The observer consumes managed shadow deployments, and still reaches nothing.

L1.3A's engine half. Two claims:

* **One boundary decides what is shadowed.** `execution_binding.shadow_source_for` answers
  "what should be observed on this instrument", from a managed deployment when one exists
  and from the legacy key pairing otherwise. Two independent pairing mechanisms is what the
  slice exists to remove; two *sources* behind one boundary, with stated precedence, is not
  the same thing.
* **A managed deployment is still an observer.** Everything Stage 1 proved about the
  runtime pairing has to keep holding when the pairing comes from a durable record — it
  would be a poor trade to gain lineage and lose isolation.
"""
from __future__ import annotations

import pytest

from app.core import execution_binding as binding
from app.core import shadow_deployments as sd
from app.db.models import LEGACY_DEPLOYMENT_ID
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner

from tests.test_shadow_deployments import (  # noqa: F401 — the fixture is used by name
    GRAPH,
    PROJECT,
    approved_evidence,
    evidence_bridge,
    seed_graph,
)

INSTRUMENT = "SILVERM"
INTERVAL = "30minute"


def setup_function() -> None:
    init_db(reset=True)


def activate_binding(instrument_key: str = INSTRUMENT, interval: str = INTERVAL):
    with SessionLocal() as session:
        seed_graph(session, 1)
        row = sd.stage(session, project_id=PROJECT, graph_identifier=GRAPH,
                       graph_version=1, deployment_id=LEGACY_DEPLOYMENT_ID,
                       instrument_key=instrument_key, interval=interval)
        session.commit()
        sd.activate(session, row.id, revision=row.revision)
        session.commit()
        return row.id


# ── one boundary, two sources, stated precedence ────────────────────────────────

def test_a_managed_deployment_is_the_shadow_source_when_one_exists():
    activate_binding()
    with SessionLocal() as session:
        managed = {b.instrument_key: b for b in sd.active_bindings(session)}

    source = binding.shadow_source_for(
        instrument_key=INSTRUMENT, authoritative_key="expanding_z_v4",
        managed=managed.get(INSTRUMENT), interval=INTERVAL)

    assert source is not None
    assert source.origin == binding.ORIGIN_MANAGED_DEPLOYMENT
    assert source.graph_identifier == GRAPH
    assert source.authority == binding.SHADOW
    assert source.content_address


def test_the_legacy_pairing_is_the_fallback_and_says_so():
    """Retiring the runtime pairing before anything replaces it would take shadow coverage
    to zero. It stays as the *named* fallback, so which source answered is always visible."""
    source = binding.shadow_source_for(
        instrument_key=INSTRUMENT, authoritative_key="expanding_z_v4",
        managed=None, interval=INTERVAL)

    assert source is not None
    assert source.origin == binding.ORIGIN_LEGACY_PAIRING
    assert source.authority == binding.SHADOW


def test_an_instrument_with_neither_source_is_not_shadowed():
    assert binding.shadow_source_for(
        instrument_key=INSTRUMENT, authoritative_key="some_other_strategy",
        managed=None, interval=INTERVAL) is None


def test_a_managed_deployment_bound_to_another_interval_does_not_apply():
    """The interval is part of the binding, not decoration: a graph admitted for 30-minute
    bars has not been admitted for 5-minute ones."""
    activate_binding()
    with SessionLocal() as session:
        managed = sd.active_bindings(session)[0]

    assert binding.shadow_source_for(
        instrument_key=INSTRUMENT, authoritative_key="expanding_z_v4",
        managed=managed, interval="5minute") is None


def test_the_shadow_source_can_never_be_authoritative():
    activate_binding()
    with SessionLocal() as session:
        managed = sd.active_bindings(session)[0]
    source = binding.shadow_source_for(
        instrument_key=INSTRUMENT, authoritative_key="expanding_z_v4",
        managed=managed, interval=INTERVAL)

    assert source.authority == binding.SHADOW
    assert (source.runtime_source, source.execution_mode) in {
        (binding.SOURCE_IR_GRAPH, "shadow")}


# ── the runner loads them, and reloads them deterministically ───────────────────

def started(runner: EngineRunner) -> EngineRunner:
    """A runner as the signal lane leaves it at startup.

    Construction deliberately reads no database — the suite builds hundreds of runners
    around `init_db(reset=True)`, and a read per construction made an unrelated
    options-entry test fail three runs in four while pointing at the wrong code. The load
    happens where the lane starts, which is also the restart boundary the requirement
    names.
    """
    runner.refresh_shadow_deployments()
    return runner


def test_the_runner_loads_active_managed_deployments_at_startup():
    activate_binding()
    runner = started(EngineRunner())
    assert INSTRUMENT in runner.shadow_deployments
    assert runner.shadow_deployments[INSTRUMENT].graph_identifier == GRAPH


def test_paused_and_retired_deployments_do_not_resurrect_across_a_restart():
    row_id = activate_binding()
    with SessionLocal() as session:
        row = session.get(type(session.get(__import__(
            "app.db.models", fromlist=["IrShadowDeployment"]).IrShadowDeployment, row_id)),
            row_id)
        sd.pause(session, row.id, revision=row.revision)
        session.commit()

    assert started(EngineRunner()).shadow_deployments == {}

    with SessionLocal() as session:
        from app.db.models import IrShadowDeployment
        row = session.get(IrShadowDeployment, row_id)
        sd.retire(session, row.id, revision=row.revision)
        session.commit()

    assert started(EngineRunner()).shadow_deployments == {}


def test_two_runners_built_from_the_same_database_agree():
    activate_binding()
    first, second = started(EngineRunner()), started(EngineRunner())
    assert first.shadow_deployments == second.shadow_deployments


def test_a_binding_whose_graph_moved_is_dropped_and_reported():
    row_id = activate_binding()
    with SessionLocal() as session:
        from app.db.models import IrShadowDeployment
        session.get(IrShadowDeployment, row_id).graph_content_address = (
            "sha256:" + "9" * 64)
        session.commit()

    runner = started(EngineRunner())
    assert runner.shadow_deployments == {}
    assert runner.shadow_deployment_problems


def test_the_runner_does_not_read_deployments_per_instrument_per_tick(monkeypatch):
    """Loaded at startup and at controlled refresh boundaries. A DB round-trip per
    instrument per ~2.5 s scan is the shape that took the box down in July."""
    activate_binding()
    runner = started(EngineRunner())

    reads = []
    real = sd.active_bindings
    monkeypatch.setattr(sd, "active_bindings",
                        lambda *a, **k: (reads.append(1), real(*a, **k))[1])
    monkeypatch.setitem(runner.params, "ir_shadow_enabled", True)
    runner.scan_signals()
    assert reads == []


def test_refreshing_picks_up_a_new_activation_without_a_restart():
    runner = started(EngineRunner())
    assert runner.shadow_deployments == {}
    activate_binding()
    runner.refresh_shadow_deployments()
    assert INSTRUMENT in runner.shadow_deployments


# ── it is still an observer ─────────────────────────────────────────────────────

def test_a_managed_shadow_scan_reaches_no_broker_or_order_seam(monkeypatch):
    from app.engine import broker as broker_module
    from app.engine import kite_order_client

    activate_binding()
    runner = started(EngineRunner())
    monkeypatch.setitem(runner.params, "ir_shadow_enabled", True)

    sprung: list[str] = []
    for name in ("open_position", "open_equity_position", "open_futures_position",
                 "close_position", "close_equity_position", "close_futures_position",
                 "book_partial_close", "reinforce_position", "manual_open",
                 "update_stop_protection", "ensure_stop_protection", "reconcile_orphans",
                 "adopt_pending_entries", "cancel_working_entries", "recover_journal"):
        monkeypatch.setattr(broker_module.PaperBroker, name,
                            lambda *a, _n=name, **k: sprung.append(f"broker.{_n}"),
                            raising=False)
    for name in dir(kite_order_client.KiteOrderClient):
        if not name.startswith("_"):
            monkeypatch.setattr(kite_order_client.KiteOrderClient, name,
                                lambda *a, _n=name, **k: sprung.append(f"kite.{_n}"),
                                raising=False)

    runner.scan_signals()
    assert sprung == []


def test_a_managed_shadow_deployment_writes_no_money_record(monkeypatch):
    from sqlalchemy import select

    from app.db.models import Position, Trade

    activate_binding()
    runner = started(EngineRunner())
    monkeypatch.setitem(runner.params, "ir_shadow_enabled", True)
    runner.scan_signals()

    with SessionLocal() as session:
        assert session.scalars(select(Position)).first() is None
        assert session.scalars(select(Trade)).first() is None


def test_a_managed_shadow_deployment_is_never_the_author_of_a_signal(monkeypatch):
    """`publish_signal` binds a signal to the strategy that produced it, and that is what a
    fill is attributed to. A shadow source reaching it would put a graph's identity onto a
    money record — the one thing L1.2b just finished making impossible."""
    activate_binding()
    runner = started(EngineRunner())
    monkeypatch.setitem(runner.params, "ir_shadow_enabled", True)

    authors: list[str] = []
    real = EngineRunner.publish_signal
    monkeypatch.setattr(EngineRunner, "publish_signal",
                        lambda self, key, execution, state: (
                            authors.append(execution.strategy_key),
                            real(self, key, execution, state))[1])
    runner.scan_signals()

    assert authors, "the scan published nothing — the assertion below would be vacuous"
    assert not any(a.startswith("ir.") for a in authors)


def test_the_managed_binding_does_not_change_authoritative_selection(monkeypatch):
    """The comparison that makes this a shadow: the authoritative strategy chosen for each
    instrument is identical with the managed deployment active and absent."""
    without = {k: EngineRunner()._binding_for(k).strategy_key
               for k in sorted(EngineRunner().enabled)}
    activate_binding()
    with_managed = {k: EngineRunner()._binding_for(k).strategy_key
                    for k in sorted(EngineRunner().enabled)}
    assert with_managed == without


def test_the_shadow_source_type_carries_nothing_executable():
    import dataclasses

    activate_binding()
    with SessionLocal() as session:
        managed = sd.active_bindings(session)[0]
    source = binding.shadow_source_for(
        instrument_key=INSTRUMENT, authoritative_key="expanding_z_v4",
        managed=managed, interval=INTERVAL)

    fields = {f.name for f in dataclasses.fields(source)}
    assert not fields & {"strategy", "broker", "adapter", "order", "position"}
    assert source.__dataclass_params__.frozen


def test_the_runner_consumes_a_boundary_refusal_rather_than_evaluating(monkeypatch):
    """`shadow_source_for` returning None is an *answer*, and the observer has to act on it.

    A managed deployment bound to a different interval than the instrument actually runs is
    the case: the graph was admitted for 5-minute bars and this instrument is not on them,
    so there is nothing to observe. If the runner pushed past that refusal it would fault
    on a source that does not exist — contained by the lane's own try, and therefore
    invisible except as an error the operator has no way to act on.

    Asserted through the log rather than a counter: "the lane recorded no error" is the
    property that distinguishes honouring a refusal from stumbling over it.
    """
    from app.core.logging import log

    activate_binding(interval="5minute")
    runner = started(EngineRunner())
    assert runner.shadow_deployments[INSTRUMENT].interval == "5minute"
    assert runner._interval_for(INSTRUMENT) != "5minute", (
        "the instrument runs the interval the deployment names — no refusal to consume")
    monkeypatch.setitem(runner.params, "ir_shadow_enabled", True)

    runner.scan_signals()

    faults = [e for e in log.recent(300) if e.get("event") == "IR_SHADOW"]
    assert faults == [], f"the lane faulted instead of skipping: {faults}"
