"""The engine consults the binding contract, and consults nothing else.

`app/core/execution_binding.py` was written to reconcile the six mechanisms that each
express part of "what strategy runs where". It shipped as a *description*: correct, tested,
and called by nothing in production — which is this codebase's defining defect, and exactly
the shape the contract was written to fix. Describing the engine without being consulted by
it is not reconciliation; it is a seventh mechanism.

This module is the wiring and its proof. Two claims have to hold at once:

* **Equivalence.** For every assignment the engine can hold, routing through the contract
  selects the same strategy object, from the same map, at the same moment as before. A
  refactor of the strategy-selection path in a live-money engine is only acceptable if it
  is provably a no-op.
* **Authority.** After the wiring there is one place that may grant execution, it is
  re-checked where it is used, and no path — registry fallback, route mutation, deployment
  lookup, restart — routes around it.

The mutations that turn these red are listed in `scripts/ir_shadow_mutations.py`.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from app.core import execution_binding as binding
from app.db.models import LEGACY_DEPLOYMENT_ID, InstrumentState
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.strategy.registry import DEFAULT_STRATEGY_KEY, StrategyNotFound, get_strategy

RUNNER_SOURCE = pathlib.Path(__file__).resolve().parents[1] / "app" / "engine" / "runner.py"


def setup_function() -> None:
    init_db(reset=True)


def assign(instrument_key: str, strategy_key: str | None) -> None:
    """Write the assignment the way a stale row or a migration would — straight to the
    table, bypassing every service. The engine must be safe against what is *in* the
    database, not only against what its own setters would have put there."""
    with SessionLocal() as session:
        row = session.get(InstrumentState, ("owner", instrument_key))
        if row is None:
            row = InstrumentState(instrument_key=instrument_key)
            session.add(row)
        row.strategy_key = strategy_key
        session.commit()


def graph_strategy(monkeypatch):
    """A registered graph-backed strategy — the Stage 2 state, arriving early.

    Every authority test needs this: while no `ir.*` key is registered, the gate is
    unreachable and every proof about it would be vacuous.

    `strategy_keys()` first, deliberately: `_discover()` is a no-op once `_REGISTRY` is
    non-empty, so inserting into an empty registry convinces it that discovery already
    happened and the real strategies never load. That passes when an earlier test in the
    file has warmed the registry and fails when this one runs alone — a suite-order
    dependency, which is the failure shape this project has already been bitten by three
    times. State the condition rather than inheriting it.
    """
    from app.engine import ir_shadow
    from app.strategy.registry import _REGISTRY, strategy_keys

    strategy_keys()
    strategy = ir_shadow.pairing_for("expanding_z_v4").adapter()
    monkeypatch.setitem(_REGISTRY, strategy.key, strategy)
    return strategy


# ── equivalence: the contract must describe the engine before it changes it ──────

def test_every_assignment_the_engine_can_hold_selects_the_same_strategy_as_before():
    """The equivalence proof, over the whole space of values `strategy_keys` can take:
    unset, the default, another registered strategy, and a stale key that no longer
    resolves. `get_strategy` is what the engine called before this slice."""
    runner = EngineRunner()
    for assigned in (None, DEFAULT_STRATEGY_KEY, "expanding_z_v4", "no_such_strategy"):
        if assigned is None:
            runner.strategy_keys.pop("NIFTY", None)
        else:
            runner.strategy_keys["NIFTY"] = assigned
        assert runner._strategy_for("NIFTY") is get_strategy(assigned), assigned


def test_the_engine_asks_the_contract_rather_than_resolving_on_its_own(monkeypatch):
    """Equivalence alone would also be satisfied by not wiring anything. This pins that
    the answer actually comes through `bind` — the same decision `resolve_binding` makes,
    with the reads the engine has already done."""
    seen = []
    real = binding.bind

    def spy(**kwargs):
        seen.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(binding, "bind", spy)
    runner = EngineRunner()
    runner.strategy_keys["NIFTY"] = "expanding_z_v4"
    runner._strategy_for("NIFTY")

    assert [c["instrument_key"] for c in seen] == ["NIFTY"]
    assert seen[0]["assigned_key"] == "expanding_z_v4"
    assert seen[0]["deployment_id"] == LEGACY_DEPLOYMENT_ID


def test_a_full_signal_scan_resolves_every_instrument_through_the_contract(monkeypatch):
    """The call site that matters. A contract consulted by a helper nobody runs is the
    defect again, so this asserts the *scan* goes through it, for every enabled name."""
    seen = []
    real = binding.bind
    monkeypatch.setattr(binding, "bind",
                        lambda **kw: (seen.append(kw["instrument_key"]), real(**kw))[1])

    runner = EngineRunner()
    runner.scan_signals()

    assert seen, "the scan resolved no strategy through the contract"
    assert set(seen) <= set(runner.enabled)


def test_the_binding_the_engine_uses_carries_its_provenance():
    """What the wiring buys: the engine's selection is now an artefact that can be
    reviewed — version, source, deciding layer, reason — not a bare key."""
    runner = EngineRunner()
    runner.strategy_keys["NIFTY"] = "expanding_z_v4"
    result = runner._binding_for("NIFTY")

    assert result.strategy_key == "expanding_z_v4"
    assert result.strategy_version
    assert result.source == binding.SOURCE_HANDWRITTEN
    assert result.authority == binding.AUTHORITATIVE
    assert result.origin == binding.ORIGIN_INSTRUMENT
    assert result.deployment_id == runner.deployment_id
    assert "expanding_z_v4" in result.reason


def test_a_stale_assignment_still_falls_back_and_the_book_keeps_trading():
    """The legacy fail-safe is deliberate and must survive the refactor: one stale config
    row must not stop the book. What is new is that the substitution is *reported*."""
    runner = EngineRunner()
    runner.strategy_keys["NIFTY"] = "withdrawn_strategy"
    result = runner._binding_for("NIFTY")

    assert result.strategy_key == DEFAULT_STRATEGY_KEY
    assert result.origin == binding.ORIGIN_FALLBACK
    assert "withdrawn_strategy" in result.reason


def test_reconstructing_the_runner_produces_the_same_binding():
    """Restart equivalence. The decision must come from persisted state, not from
    whatever the previous process happened to hold in memory."""
    assign("NIFTY", "expanding_z_v4")
    first = EngineRunner()._binding_for("NIFTY")
    second = EngineRunner()._binding_for("NIFTY")
    assert first == second
    assert first.strategy_key == "expanding_z_v4"


def test_a_watchlist_assignment_reaches_the_engine_through_the_same_contract():
    """The watchlist overlay is how an assignment is changed at runtime without touching
    the instrument row. It is a third mechanism only if it resolves on a third path."""
    from app.core import watchlists as wl

    assign("NIFTY", DEFAULT_STRATEGY_KEY)
    with SessionLocal() as session:
        w = wl.create_watchlist(session, "momentum", "expanding_z_v4")
        wl.assign_instrument(session, "NIFTY", w.id)
        session.commit()

    result = EngineRunner()._binding_for("NIFTY")
    assert result.strategy_key == "expanding_z_v4"
    assert result.origin == binding.ORIGIN_INSTRUMENT


# ── the authority boundary, after wiring ────────────────────────────────────────

def test_a_registered_graph_strategy_is_refused_execution_by_the_engine(monkeypatch):
    """The hazard the gate exists for, now asserted against the engine rather than the
    contract in isolation: once a graph-backed strategy is registered, the registry
    resolves it and the pre-wiring engine would have traded it."""
    strategy = graph_strategy(monkeypatch)
    runner = EngineRunner()
    runner.strategy_keys["NIFTY"] = strategy.key

    with pytest.raises(binding.AuthorityNotGranted):
        runner._strategy_for("NIFTY")


def test_the_engine_skips_a_refused_instrument_and_substitutes_nothing(monkeypatch):
    """Requirement 15, and the difference between failing closed and failing quietly. A
    refusal must not become "trade the default instead" — that is the silent-substitution
    class the whole registry split exists to prevent — and it must not stop the other
    instruments either, because the risk lane must never be blocked."""
    strategy = graph_strategy(monkeypatch)
    runner = EngineRunner()
    for key in list(runner.enabled):
        runner.strategy_keys[key] = DEFAULT_STRATEGY_KEY
    refused = sorted(runner.enabled)[0]
    runner.strategy_keys[refused] = strategy.key

    runner.scan_signals()

    assert refused not in runner.state, "a refused instrument was evaluated anyway"
    assert len(runner.state) >= 1, "the refusal stopped instruments it had no claim over"


def test_a_refused_instrument_reaches_no_broker_or_order_seam(monkeypatch):
    """Requirement 12. Refusing authority is only meaningful if nothing downstream ran."""
    from app.engine import broker as broker_module

    strategy = graph_strategy(monkeypatch)
    runner = EngineRunner()
    for key in list(runner.enabled):
        runner.strategy_keys[key] = strategy.key

    sprung = []
    for name in ("open_position", "open_equity_position", "open_futures_position",
                 "close_position", "reinforce_position", "update_stop_protection"):
        monkeypatch.setattr(broker_module.PaperBroker, name,
                            lambda *a, _n=name, **k: sprung.append(_n), raising=False)

    runner.scan_signals()
    assert sprung == []


def test_assigning_a_graph_strategy_through_the_route_is_refused(monkeypatch):
    """Requirement 5: a route mutation may not become the authority decision. The API
    validates against the registry, and the registry resolves a registered graph — so
    without the gate at the write, `POST /api/instruments/NIFTY/strategy` is the whole
    path from "a graph exists" to "a graph trades real money"."""
    strategy = graph_strategy(monkeypatch)
    runner = EngineRunner()

    with pytest.raises(binding.AuthorityNotGranted):
        runner.set_strategy("NIFTY", strategy.key)

    with SessionLocal() as session:
        row = session.get(InstrumentState, ("owner", "NIFTY"))
    assert row is None or row.strategy_key != strategy.key
    assert runner.strategy_keys.get("NIFTY") != strategy.key


def test_a_deployment_pinning_a_graph_is_refused_rather_than_falling_through(monkeypatch):
    """Requirement 7: contradictory claims fail closed. A deployment pin that may not
    execute must not quietly hand the decision back to the instrument row — that would
    resolve the contradiction in favour of the *weaker* claim, silently."""
    strategy = graph_strategy(monkeypatch)
    with pytest.raises(binding.AuthorityNotGranted):
        binding.bind(deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY",
                     deployment_pin=strategy, assigned_key="expanding_z_v4")


def test_an_unregistered_graph_assignment_fails_with_a_stable_explicit_error():
    """Requirement 8. The message must name the key: "some strategy is missing" is not
    actionable at 09:20 on a Monday."""
    runner = EngineRunner()
    runner.strategy_keys["NIFTY"] = "ir.strategy.no_such_graph"
    with pytest.raises(StrategyNotFound) as raised:
        runner._strategy_for("NIFTY")
    assert "ir.strategy.no_such_graph" in str(raised.value)


def test_the_shadow_lane_still_observes_what_authority_refuses(monkeypatch):
    """Requirement 11. The gate must not have closed the lane it was written to protect:
    the same key the engine refuses to execute is still evaluable, and still shadow."""
    strategy = graph_strategy(monkeypatch)
    observed = binding.resolve_shadow_binding(strategy.key, "NIFTY")
    assert observed.authority == binding.SHADOW
    assert observed.source == binding.SOURCE_IR_GRAPH

    runner = EngineRunner()
    monkeypatch.setitem(runner.params, "ir_shadow_enabled", True)
    for key in list(runner.enabled):
        runner.strategy_keys[key] = "expanding_z_v4"
    runner.scan_signals()
    assert runner.shadow_metrics.snapshot()["bars_observed"] > 0


# ── no bypasses ─────────────────────────────────────────────────────────────────

def _called_names(tree) -> set[str]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                out.add(func.id)
            elif isinstance(func, ast.Attribute):
                out.add(func.attr)
    return out


def test_the_engine_never_calls_a_strategy_resolver_directly():
    """Requirement 5, as a guard rather than a promise. An AST check, not a grep: this
    module and the runner both *discuss* `get_strategy` in prose, and a substring search
    would be satisfied by a comment — which is the vacuous-guard shape already recorded
    twice in this project.

    The whole point of the wiring is that there is one path. A second `get_strategy` call
    added to the runner in six months would restore the contradiction silently.
    """
    tree = ast.parse(RUNNER_SOURCE.read_text())
    called = _called_names(tree)
    assert "get_strategy" not in called
    assert "resolve_strategy" not in called


def test_the_engine_reaches_the_registry_only_through_the_contract():
    """The complement: not merely "does not call the resolvers" but "resolves through
    `execution_binding`". Deleting the call site would pass the test above."""
    tree = ast.parse(RUNNER_SOURCE.read_text())
    called = _called_names(tree)
    assert "bind" in called, "the runner no longer consults the binding contract"
    assert "strategy_for_execution" in called, (
        "the runner takes a strategy without re-checking that it may execute")


# ── every write that becomes an engine assignment passes the same gate ───────────

def test_adding_an_instrument_with_a_graph_strategy_is_refused(monkeypatch):
    """`universe_resolver.add_instrument` writes `InstrumentState.strategy_key` directly
    and validates only against the registry — so it is a second route from "a graph is
    registered" to "a graph is assigned". One gate means every writer consults it."""
    from app.core import universe_resolver

    strategy = graph_strategy(monkeypatch)
    with pytest.raises(binding.AuthorityNotGranted):
        universe_resolver.add_instrument("NIFTY", EngineRunner().provider,
                                         strategy_key=strategy.key, owner_id="owner")

    with SessionLocal() as session:
        row = session.get(InstrumentState, ("owner", "NIFTY"))
    assert row is None or row.strategy_key != strategy.key


def test_creating_a_watchlist_on_a_graph_strategy_is_refused(monkeypatch):
    """A watchlist's strategy overrides the per-instrument assignment for every member,
    so it is an engine assignment by another name — `effective_strategy_map` is read
    straight into `strategy_keys`."""
    from app.core import watchlists as wl

    strategy = graph_strategy(monkeypatch)
    with SessionLocal() as session:
        with pytest.raises(binding.AuthorityNotGranted):
            wl.create_watchlist(session, "graphs", strategy.key)


def test_deploying_a_graph_strategy_onto_an_existing_watchlist_is_refused(monkeypatch):
    """The deploy bridge reassigns an existing watchlist's strategy in place, which never
    passes through `create_watchlist`. A gate on the constructor alone would miss it."""
    from app.core import deploy_bridge
    from app.core import watchlists as wl

    strategy = graph_strategy(monkeypatch)
    with SessionLocal() as session:
        wl.create_watchlist(session, "momentum", "expanding_z_v4")
        session.commit()
        req = deploy_bridge.DeployRequest(watchlist_name="momentum",
                                          strategy_key=strategy.key,
                                          proposals=[("NIFTY", 1.0)])
        with pytest.raises(binding.AuthorityNotGranted):
            deploy_bridge.deploy(session, req)


def test_the_strategy_route_reports_a_refusal_instead_of_crashing(monkeypatch):
    """The gate's verdict is consumed at the edge, not re-derived there: the route
    catches `AuthorityNotGranted` rather than testing for a namespace itself. A 500 would
    also be safe, but it reads as a bug in the platform rather than as a refusal, and the
    reason — that this is an owner-gated decision — would never reach the operator."""
    from fastapi.testclient import TestClient

    from app.main import app

    strategy = graph_strategy(monkeypatch)
    with TestClient(app) as client:
        response = client.post(f"/api/instruments/NIFTY/strategy",
                               json={"strategy_key": strategy.key})
    assert response.status_code == 409
    assert strategy.key in response.json()["detail"]


def test_the_engine_rejects_a_forged_binding_from_a_drifted_resolver(monkeypatch):
    """Requirement 14, and the reason `_strategy_for` re-checks authority rather than
    trusting the binding it was handed.

    The obvious version of this test — assign a graph key and watch the engine refuse —
    does not exercise the re-check at all: `bind` already refuses at resolution, so the
    check downstream is never reached and a mutation removing it stays green. The
    mutation harness caught exactly that. The re-check earns its place against a
    *resolver* that returns an authoritative-looking binding: a future caller assembling
    one by hand, a stub, or this contract drifting. Then it is the last thing between a
    graph and a real order, and it must reject before any evaluation happens.
    """
    strategy = graph_strategy(monkeypatch)
    forged = binding.ExecutionBinding(
        deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY",
        strategy_key=strategy.key, strategy_version=strategy.version,
        source=binding.SOURCE_IR_GRAPH, authority=binding.AUTHORITATIVE,
        origin=binding.ORIGIN_INSTRUMENT, reason="a resolver that granted itself authority")
    monkeypatch.setattr(binding, "bind", lambda **kw: forged)

    runner = EngineRunner()
    with pytest.raises(binding.AuthorityNotGranted):
        runner._strategy_for("NIFTY")

    evaluated = []
    monkeypatch.setattr(type(strategy), "signals",
                        lambda self, *a, **k: evaluated.append(1), raising=False)
    runner.scan_signals()
    assert evaluated == [], "a forged binding reached strategy evaluation"
    assert runner.state == {}
