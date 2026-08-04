"""One answer to "what executes here", and one place that may grant authority.

Six mechanisms in this codebase currently express some part of "what strategy runs":
`Deployment.strategy_key`, `InstrumentState.strategy_key`, watchlist assignments,
`StrategyLifecycle`, `GeneratedStrategyRow`, and `GraphArtifact`/`GraphVersion`. They were
built at different times for different reasons, and nothing reconciles them — in particular
`resolve_deployment_strategy` has tests and **no production caller**, so the object the
architecture calls "THE primary execution object" does not currently decide what executes.

This module is that reconciliation, and it is **non-authoritative by construction**: it
reports a binding, it does not install one. The engine keeps resolving exactly as it does
today. What it adds is a single typed answer that every future caller can agree on, and one
place where authority is granted — so granting it to a graph becomes a visible, owner-gated
code change rather than a config row nobody reviews.
"""
from __future__ import annotations

import pytest

from app.core import deployments as dep
from app.core import execution_binding as binding
from app.db.models import LEGACY_DEPLOYMENT_ID, InstrumentState
from app.db.session import SessionLocal, init_db
from app.strategy.registry import DEFAULT_STRATEGY_KEY, StrategyNotFound


def setup_function() -> None:
    init_db(reset=True)


def resolve(instrument_key="NIFTY", deployment_id=LEGACY_DEPLOYMENT_ID):
    with SessionLocal() as session:
        return binding.resolve_binding(session, deployment_id=deployment_id,
                                       instrument_key=instrument_key)


def assign(instrument_key: str, strategy_key: str | None) -> None:
    with SessionLocal() as session:
        row = session.get(InstrumentState, instrument_key)
        if row is None:
            row = InstrumentState(instrument_key=instrument_key)
            session.add(row)
        row.strategy_key = strategy_key
        session.commit()


# ── what the binding says ────────────────────────────────────────────────────────

def test_the_legacy_deployment_with_no_assignment_binds_the_default_strategy():
    result = resolve()
    assert result.strategy_key == DEFAULT_STRATEGY_KEY
    assert result.origin == binding.ORIGIN_DEFAULT
    assert result.source == binding.SOURCE_HANDWRITTEN
    assert result.authority == binding.AUTHORITATIVE


def test_a_per_instrument_assignment_wins_over_the_default():
    assign("NIFTY", "expanding_z_v4")
    result = resolve()
    assert result.strategy_key == "expanding_z_v4"
    assert result.origin == binding.ORIGIN_INSTRUMENT


def test_a_deployment_that_pins_a_strategy_wins_over_the_instrument_row():
    """A deployment is a promise about which strategy is trading. If it pins one, a
    per-instrument row cannot quietly override it — that would make the promise false."""
    assign("NIFTY", "expanding_z_v4")
    with SessionLocal() as session:
        created = dep.create_deployment(session, "pinned",
                                        strategy_key=DEFAULT_STRATEGY_KEY)
        session.commit()
        deployment_id = created.id

    result = resolve(deployment_id=deployment_id)
    assert result.strategy_key == DEFAULT_STRATEGY_KEY
    assert result.origin == binding.ORIGIN_DEPLOYMENT


def test_every_binding_carries_the_version_that_makes_it_an_artefact():
    """`key` alone cannot identify what ran: re-deploying an edited strategy overwrites
    its row in place. `(key, version)` is the execution artefact."""
    result = resolve()
    assert result.strategy_version
    assert result.strategy_version == binding.strategy_for(result).version


def test_the_binding_says_which_layer_decided_and_why():
    """A binding nobody can explain is a binding nobody can review."""
    assign("NIFTY", "expanding_z_v4")
    result = resolve()
    assert "instrument" in result.reason.lower()
    assert "expanding_z_v4" in result.reason


# ── failure posture, which differs by layer on purpose ───────────────────────────

def test_an_unresolvable_deployment_pin_fails_closed():
    """A deployment that pins a strategy the registry cannot resolve must halt, never
    substitute: the trade rows would claim a strategy that never ran."""
    with SessionLocal() as session:
        created = dep.create_deployment(session, "broken", strategy_key="no_such_strategy")
        session.commit()
        deployment_id = created.id

    with pytest.raises(StrategyNotFound):
        resolve(deployment_id=deployment_id)


def test_an_unresolvable_instrument_assignment_falls_back_and_says_so():
    """The legacy per-instrument path keeps its deliberate fail-safe — one bad config row
    must not stop the book trading — but the binding reports the substitution rather than
    presenting the default as if it had been chosen."""
    assign("NIFTY", "no_such_strategy")
    result = resolve()
    assert result.strategy_key == DEFAULT_STRATEGY_KEY
    assert result.origin == binding.ORIGIN_FALLBACK
    assert "no_such_strategy" in result.reason


def test_an_unresolvable_ir_assignment_never_falls_back():
    """A graph-backed key that resolves to the default would trade one logic and attribute
    another. The registry already refuses; the binding must not undo that."""
    assign("NIFTY", "ir.strategy.no_such_graph")
    with pytest.raises(StrategyNotFound):
        resolve()


# ── the authority gate ───────────────────────────────────────────────────────────

def test_a_graph_backed_key_is_recognised_as_such():
    assert binding.source_of("ir.strategy.expanding_z_impulse") == binding.SOURCE_IR_GRAPH
    assert binding.source_of("gen_abc123") == binding.SOURCE_GENERATED
    assert binding.source_of("expanding_z_v4") == binding.SOURCE_HANDWRITTEN


def test_authority_is_granted_by_source_and_the_graph_source_does_not_have_it():
    """The owner gate, in code. Stage 1 is shadow-only: IR output may be observed and
    recorded, never executed. Granting authority is a change to this table, which is a
    reviewed code change, not a config row."""
    assert binding.AUTHORITY_BY_SOURCE[binding.SOURCE_HANDWRITTEN] == binding.AUTHORITATIVE
    assert binding.AUTHORITY_BY_SOURCE[binding.SOURCE_GENERATED] == binding.AUTHORITATIVE
    assert binding.AUTHORITY_BY_SOURCE[binding.SOURCE_IR_GRAPH] == binding.SHADOW


def test_binding_a_registered_graph_to_an_instrument_is_refused_not_silently_shadowed(
        monkeypatch):
    """The hazard this gate exists for. Once Stage 2 registers a graph-backed strategy,
    nothing else in the system would stop an ordinary per-instrument assignment from making
    it authoritative — the registry resolves it and the engine trades it. Resolving such a
    binding raises here instead, so the path to live IR execution runs through an owner
    decision rather than through `POST /api/instruments/NIFTY/strategy`."""
    from app.engine import ir_shadow
    from app.strategy.registry import _REGISTRY

    graph_strategy = ir_shadow.pairing_for("expanding_z_v4").adapter()
    monkeypatch.setitem(_REGISTRY, graph_strategy.key, graph_strategy)
    assign("NIFTY", graph_strategy.key)

    with pytest.raises(binding.AuthorityNotGranted) as raised:
        resolve()
    assert graph_strategy.key in str(raised.value)
    assert "shadow" in str(raised.value).lower()


def test_the_shadow_lane_can_still_evaluate_what_authority_refuses(monkeypatch):
    """The complement: refusing authority must not refuse observation, or Stage 1 would
    have been undone by Stage 1's own gate."""
    from app.engine import ir_shadow
    from app.strategy.registry import _REGISTRY

    graph_strategy = ir_shadow.pairing_for("expanding_z_v4").adapter()
    monkeypatch.setitem(_REGISTRY, graph_strategy.key, graph_strategy)
    assign("NIFTY", graph_strategy.key)

    observed = binding.resolve_shadow_binding(graph_strategy.key)
    assert observed.strategy_key == graph_strategy.key
    assert observed.authority == binding.SHADOW
    assert observed.source == binding.SOURCE_IR_GRAPH


# ── equivalence: this must describe today's engine, not a new one ────────────────

def test_the_binding_agrees_with_what_the_engine_actually_resolves():
    """The contract is only worth having if it is a description. For every assignment the
    engine can hold, the binding's answer and `get_strategy`'s answer are the same object."""
    from app.strategy.registry import get_strategy

    for assigned in (None, "expanding_z_v4", DEFAULT_STRATEGY_KEY, "no_such_strategy"):
        assign("NIFTY", assigned)
        result = resolve()
        assert binding.strategy_for(result) is get_strategy(assigned), assigned


# ── one model, not six ───────────────────────────────────────────────────────────

def test_every_mechanism_that_can_express_a_binding_is_declared():
    """A registry of the things that already claim to answer "what runs here".

    It exists so that adding a seventh is a deliberate edit to this list with a test to
    justify it — the "no second deployment model" rule, enforced rather than asserted. The
    list is prose-free identifiers so a new table or column cannot join it by accident.
    """
    assert binding.BINDING_MECHANISMS == (
        "deployments.strategy_key",
        "instrument_state.strategy_key",
        "watchlists.strategy_key",
        "strategy_lifecycle.deployed_watchlist_id",
        "generated_strategies.key",
        "graph_artifacts.current_version",
    )


def test_the_declared_mechanisms_all_still_exist():
    """A registry that names columns which have since been renamed is worse than none: it
    would pass forever while describing a schema nobody has."""
    from app.db.models import Base

    for mechanism in binding.BINDING_MECHANISMS:
        table_name, column = mechanism.split(".")
        table = Base.metadata.tables[table_name]
        assert column in table.columns, mechanism


# ── the decision, separated from the lookup ──────────────────────────────────────

def test_the_decision_is_a_pure_function_of_what_the_layers_said():
    """The engine resolves a strategy per instrument on a ~2.5 s loop from an in-memory
    map. If consulting the canonical resolver meant two DB reads per instrument per tick,
    "route the engine through the contract" would mean "make the engine slower", and the
    wiring would be rejected for the wrong reason.

    So the contract is split: `bind` is the decision — precedence, resolution, authority —
    and takes what the layers said as arguments. `resolve_binding` is that decision plus
    the reads. The engine calls `bind` with the values it already holds."""
    result = binding.bind(deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY",
                          deployment_pin=None, assigned_key="expanding_z_v4")
    assert result.strategy_key == "expanding_z_v4"
    assert result.origin == binding.ORIGIN_INSTRUMENT
    assert result.authority == binding.AUTHORITATIVE


def test_resolve_binding_is_that_same_decision_plus_the_database_reads():
    """Two entry points that disagree would be two resolvers again."""
    assign("NIFTY", "expanding_z_v4")
    from_db = resolve()
    pure = binding.bind(deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY",
                        deployment_pin=None, assigned_key="expanding_z_v4")
    assert from_db == pure


# ── source alone is not authority ────────────────────────────────────────────────

def test_authority_is_a_reviewed_source_and_mode_pair_not_a_source_alone():
    """ADR 0012 §3.2: the smallest safe future grant is not "`ir_graph` is authoritative"
    but "`ir_graph` is authoritative *in paper mode*". A gate keyed on source alone cannot
    express that, so the reviewed unit is the pair. Today exactly three pairs are granted;
    anything else is unreviewed and fails closed."""
    assert binding.GRANTS == frozenset({
        (binding.SOURCE_HANDWRITTEN, binding.AUTHORITATIVE),
        (binding.SOURCE_GENERATED, binding.AUTHORITATIVE),
        (binding.SOURCE_IR_GRAPH, binding.SHADOW),
    })


def test_a_binding_that_claims_an_unreviewed_pairing_is_refused_at_consumption(monkeypatch):
    """Requirement 14, and the reason authority is re-checked where it is *used* rather
    than trusted from where it was produced. A resolver — a real one that drifted, a stub
    in a test, a future caller that builds an `ExecutionBinding` by hand — cannot grant
    execution by asserting a field."""
    from app.engine import ir_shadow
    from app.strategy.registry import _REGISTRY

    graph_strategy = ir_shadow.pairing_for("expanding_z_v4").adapter()
    monkeypatch.setitem(_REGISTRY, graph_strategy.key, graph_strategy)

    forged = binding.ExecutionBinding(
        deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY",
        strategy_key=graph_strategy.key, strategy_version=graph_strategy.version,
        source=binding.SOURCE_IR_GRAPH, authority=binding.AUTHORITATIVE,
        origin=binding.ORIGIN_INSTRUMENT, reason="forged")

    with pytest.raises(binding.AuthorityNotGranted):
        binding.strategy_for_execution(forged)


def test_a_binding_whose_source_contradicts_its_key_is_refused(monkeypatch):
    """The other half of the same check: a binding may not launder a graph key through an
    authoritative-looking source label."""
    from app.engine import ir_shadow
    from app.strategy.registry import _REGISTRY

    graph_strategy = ir_shadow.pairing_for("expanding_z_v4").adapter()
    monkeypatch.setitem(_REGISTRY, graph_strategy.key, graph_strategy)

    forged = binding.ExecutionBinding(
        deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY",
        strategy_key=graph_strategy.key, strategy_version=graph_strategy.version,
        source=binding.SOURCE_HANDWRITTEN, authority=binding.AUTHORITATIVE,
        origin=binding.ORIGIN_INSTRUMENT, reason="forged")

    with pytest.raises(binding.AuthorityNotGranted):
        binding.strategy_for_execution(forged)


def test_an_unknown_source_fails_closed_rather_than_defaulting_to_authoritative():
    forged = binding.ExecutionBinding(
        deployment_id=LEGACY_DEPLOYMENT_ID, instrument_key="NIFTY",
        strategy_key=DEFAULT_STRATEGY_KEY, strategy_version="v",
        source="marketplace_purchase", authority=binding.AUTHORITATIVE,
        origin=binding.ORIGIN_INSTRUMENT, reason="a source nobody has reviewed")
    with pytest.raises(binding.AuthorityNotGranted):
        binding.strategy_for_execution(forged)


def test_the_execution_accessor_returns_the_same_object_the_registry_holds():
    """The gate must not become a copy: the engine's `is` comparisons and the strategy's
    own caches depend on there being one instance per key."""
    from app.strategy.registry import get_strategy

    assign("NIFTY", "expanding_z_v4")
    assert binding.strategy_for_execution(resolve()) is get_strategy("expanding_z_v4")


# ── the write side: an assignment may not smuggle in an unauthorised source ──────

def test_assigning_a_strategy_that_may_not_execute_is_refused_at_the_write(monkeypatch):
    """Read-side gating alone would let the row be stored and fail every tick afterwards.
    Refusing the write says no once, at the moment somebody asked."""
    from app.engine import ir_shadow
    from app.strategy.registry import _REGISTRY

    graph_strategy = ir_shadow.pairing_for("expanding_z_v4").adapter()
    monkeypatch.setitem(_REGISTRY, graph_strategy.key, graph_strategy)

    with pytest.raises(binding.AuthorityNotGranted):
        binding.assert_may_execute(graph_strategy.key)

    binding.assert_may_execute("expanding_z_v4")        # the incumbent is unaffected
    binding.assert_may_execute(None)                    # "the default" is not a claim
