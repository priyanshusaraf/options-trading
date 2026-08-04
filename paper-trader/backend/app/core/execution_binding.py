"""One typed answer to "what executes here", and the one place authority is granted.

**Why this exists.** Six mechanisms in this codebase already express some part of "what
strategy runs where" — `Deployment.strategy_key`, `InstrumentState.strategy_key`, watchlist
assignments, `StrategyLifecycle`, `GeneratedStrategyRow`, and `GraphArtifact`/`GraphVersion`.
They were built at different times for different reasons and nothing reconciles them. Most
tellingly, `resolve_deployment_strategy` has tests and **no production caller**: the object
the architecture calls "THE primary execution object" does not currently decide what
executes. Adding a seventh mechanism for IR-backed strategies would be the second deployment
model this project has a standing rule against, so this module reconciles instead.

**What it is not.** It is not a new execution path and it installs nothing. The engine keeps
resolving exactly as it does today; `test_execution_binding.py` pins that the two agree for
every assignment the engine can hold. This is a *description* with a gate attached, and a
description that drifts from what it describes is worse than none — hence that test.

**The gate.** `AUTHORITY_BY_SOURCE` is the single place where a source of strategy logic is
granted the right to execute. IR-graph-backed keys are `SHADOW`: observable, recordable,
never executable. That is what makes live IR execution an owner-gated *code* change rather
than a config row nobody reviews — once Stage 2 registers a graph-backed strategy, nothing
else in the system would stop `POST /api/instruments/NIFTY/strategy` from making it
authoritative.

**Failure posture differs by layer, deliberately.** A deployment that pins an unresolvable
strategy raises: a deployment is a promise about which strategy is trading, and substituting
the default makes that promise false while the trade rows still name the customer's strategy.
The legacy per-instrument path keeps its fail-safe — one stale config row must not stop the
book trading — but the binding *reports* the substitution instead of presenting the default
as though it had been chosen.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.strategy.registry import (
    DEFAULT_STRATEGY_KEY,
    IR_NAMESPACE,
    StrategyNotFound,
    resolve_strategy,
)

#: Where a strategy's logic comes from.
SOURCE_HANDWRITTEN = "handwritten"
SOURCE_GENERATED = "generated"
SOURCE_IR_GRAPH = "ir_graph"

#: Whether that source may execute.
AUTHORITATIVE = "authoritative"
SHADOW = "shadow"

#: **The owner gate, in code.** Granting a source the right to execute is an edit here,
#: reviewed as a code change. Stage 1 is shadow-only: IR output may be observed and
#: recorded, never executed, never allowed to influence an order. Moving `SOURCE_IR_GRAPH`
#: to `AUTHORITATIVE` is exactly the Stage 2/3 decision ADR 0011 reserves to the owner.
AUTHORITY_BY_SOURCE = {
    SOURCE_HANDWRITTEN: AUTHORITATIVE,
    SOURCE_GENERATED: AUTHORITATIVE,
    SOURCE_IR_GRAPH: SHADOW,
}

#: The same grant, as the set of **reviewed pairs**. A gate keyed on source alone cannot
#: express ADR 0012 §3.2's smallest safe future step — "`ir_graph` is authoritative *in
#: paper mode*" — so the reviewed unit is the pair, and anything not in this set is
#: unreviewed and refused. This is what makes an `ExecutionBinding` unable to grant
#: itself authority by asserting a field: `strategy_for_execution` checks membership
#: here, at the point of use, rather than trusting where the binding came from.
GRANTS = frozenset(AUTHORITY_BY_SOURCE.items())

#: Which layer decided the binding. Narrowest that spoke, not narrowest that exists.
ORIGIN_DEPLOYMENT = "deployment"
ORIGIN_INSTRUMENT = "instrument"
ORIGIN_DEFAULT = "default"
ORIGIN_FALLBACK = "fallback"

#: Everything that already claims to answer "what runs here". Declared so that adding a
#: seventh is a deliberate edit with a test to justify it, rather than a new table quietly
#: becoming a second deployment model. Column names, not prose, so the guard test can check
#: they still exist.
BINDING_MECHANISMS = (
    "deployments.strategy_key",
    "instrument_state.strategy_key",
    "watchlists.strategy_key",
    "strategy_lifecycle.deployed_watchlist_id",
    "generated_strategies.key",
    "graph_artifacts.current_version",
)

#: Prefix of a generated strategy's key (`app/core/generated_strategies.py`).
GENERATED_NAMESPACE = "gen_"


class AuthorityNotGranted(Exception):
    """A binding named a strategy whose source may not execute.

    Its own type, not a `ValueError`: a caller that means "halt this deployment" must be
    able to tell "this logic is not allowed to trade" apart from "this logic does not
    exist" (`StrategyNotFound`). They call for different actions.
    """

    def __init__(self, strategy_key: str, source: str) -> None:
        self.strategy_key, self.source = strategy_key, source
        super().__init__(
            f"{strategy_key!r} comes from {source!r}, which is {SHADOW} and may not "
            f"execute. It can be evaluated and recorded by the shadow lane; making it "
            f"authoritative is an owner-gated change to AUTHORITY_BY_SOURCE "
            f"(ADR 0011 Stage 2/3), not a configuration change.")


@dataclass(frozen=True)
class ExecutionBinding:
    """What executes for one instrument under one deployment, and on whose say-so."""

    deployment_id: int
    instrument_key: str
    strategy_key: str
    strategy_version: str | None
    source: str
    authority: str
    origin: str
    reason: str


def source_of(strategy_key: str | None) -> str:
    if strategy_key and strategy_key.startswith(IR_NAMESPACE):
        return SOURCE_IR_GRAPH
    if strategy_key and strategy_key.startswith(GENERATED_NAMESPACE):
        return SOURCE_GENERATED
    return SOURCE_HANDWRITTEN


def strategy_for(binding: ExecutionBinding):
    """The `Strategy` object a binding names. Fail-closed — the binding already resolved
    once, so anything unresolvable here is drift, not a config problem."""
    return resolve_strategy(binding.strategy_key)


def strategy_for_execution(binding: ExecutionBinding):
    """The `Strategy` a binding names, **for the purpose of executing it** — refused
    unless its (source, authority) pair is one this project has reviewed.

    Authority is re-checked here, where it is used, rather than trusted from where the
    binding was produced. A binding is a plain dataclass: a resolver that drifted, a stub
    in a test, or a future caller assembling one by hand could all set
    `authority=AUTHORITATIVE` on a graph-backed key. Checking at the consumption point
    means granting execution requires an edit to `GRANTS`, not an assignment to a field.
    The key's own source is recomputed too, so an authoritative-looking label cannot
    launder a graph key past the gate.
    """
    claimed, actual = binding.source, source_of(binding.strategy_key)
    if claimed != actual or (actual, binding.authority) not in GRANTS \
            or binding.authority != AUTHORITATIVE:
        raise AuthorityNotGranted(binding.strategy_key, actual)
    return resolve_strategy(binding.strategy_key)


def assert_may_execute(strategy_key: str | None) -> None:
    """Refuse, at the moment somebody asks, to record an assignment that could never
    execute. `None` means "the platform default", which is not a claim about a source.

    The read side already refuses, so this is not the gate — it is the gate saying no
    once, at the write, instead of once per scan for the life of the row.
    """
    if strategy_key is None:
        return
    source = source_of(strategy_key)
    if AUTHORITY_BY_SOURCE.get(source, SHADOW) != AUTHORITATIVE:
        raise AuthorityNotGranted(strategy_key, source)


def _describe(*, deployment_id, instrument_key, strategy, origin, reason,
              enforce_authority=True) -> ExecutionBinding:
    source = source_of(strategy.key)
    authority = AUTHORITY_BY_SOURCE.get(source, SHADOW)
    if enforce_authority and authority != AUTHORITATIVE:
        raise AuthorityNotGranted(strategy.key, source)
    return ExecutionBinding(
        deployment_id=deployment_id, instrument_key=instrument_key,
        strategy_key=strategy.key, strategy_version=strategy.version, source=source,
        authority=authority, origin=origin, reason=reason)


def bind(*, deployment_id: int, instrument_key: str, deployment_pin,
         assigned_key: str | None) -> ExecutionBinding:
    """The decision, with the reads already done — what executes, and on whose say-so.

    Split out from `resolve_binding` because the engine resolves a strategy per instrument
    on a ~2.5 s loop from an in-memory map it refreshes deliberately. If consulting the
    canonical contract meant two database reads per instrument per tick, routing the
    engine through it would mean slowing the engine down, and the wiring would be rejected
    for a reason that has nothing to do with whether the contract is right. So the *reads*
    live in `resolve_binding` and the *decision* lives here, and there is still exactly one
    decision.

    Precedence is narrowest-that-spoke: a deployment that pins a strategy wins, then the
    per-instrument assignment, then the platform default.

    `deployment_pin` is the already-resolved `Strategy` a deployment pins, or `None` for
    the legacy deployment, which pins nothing and resolves per instrument by design.
    """
    if deployment_pin is not None:
        return _describe(deployment_id=deployment_id, instrument_key=instrument_key,
                         strategy=deployment_pin, origin=ORIGIN_DEPLOYMENT,
                         reason=(f"deployment {deployment_id} pins "
                                 f"{deployment_pin.key!r}, which overrides any "
                                 f"per-instrument assignment"))
    return _bind_assigned(deployment_id, instrument_key, assigned_key)


def resolve_binding(session, *, deployment_id: int, instrument_key: str) -> ExecutionBinding:
    """`bind`, with the deployment pin and the instrument assignment read from the
    database. The entry point for callers that hold a session and no cached config."""
    from app.core.deployments import resolve_deployment_strategy

    return bind(deployment_id=deployment_id, instrument_key=instrument_key,
                deployment_pin=resolve_deployment_strategy(session, deployment_id),
                assigned_key=_assigned_strategy_key(session, instrument_key))


def _bind_assigned(deployment_id, instrument_key, assigned) -> ExecutionBinding:
    if not assigned:
        return _describe(deployment_id=deployment_id, instrument_key=instrument_key,
                         strategy=resolve_strategy(DEFAULT_STRATEGY_KEY),
                         origin=ORIGIN_DEFAULT,
                         reason=(f"no deployment pin and no instrument assignment for "
                                 f"{instrument_key}; the platform default applies"))
    try:
        strategy = resolve_strategy(assigned)
    except StrategyNotFound:
        if source_of(assigned) == SOURCE_IR_GRAPH:
            # A graph-backed key never falls back: it would trade one logic while the
            # instrument row, the trade row and the experiment binding all name another.
            raise
        strategy = resolve_strategy(DEFAULT_STRATEGY_KEY)
        return _describe(deployment_id=deployment_id, instrument_key=instrument_key,
                         strategy=strategy, origin=ORIGIN_FALLBACK,
                         reason=(f"instrument {instrument_key} is assigned {assigned!r}, "
                                 f"which is not registered; the legacy path substitutes "
                                 f"{strategy.key!r} so one stale row cannot stop the book"))
    return _describe(deployment_id=deployment_id, instrument_key=instrument_key,
                     strategy=strategy, origin=ORIGIN_INSTRUMENT,
                     reason=f"instrument {instrument_key} is assigned {strategy.key!r}")


def resolve_shadow_binding(strategy_key: str,
                           instrument_key: str = "") -> ExecutionBinding:
    """The same description for a strategy that may be *observed* but not executed.

    Refusing authority must not refuse observation, or the gate would have undone the
    shadow lane it exists to protect.
    """
    return _describe(deployment_id=0, instrument_key=instrument_key,
                     strategy=resolve_strategy(strategy_key), origin=ORIGIN_INSTRUMENT,
                     reason=(f"{strategy_key!r} is observed by the shadow lane, "
                             f"never executed"),
                     enforce_authority=False)


def _assigned_strategy_key(session, instrument_key: str) -> str | None:
    from app.db.models import InstrumentState

    row = session.get(InstrumentState, instrument_key)
    return (row.strategy_key or None) if row is not None else None


__all__ = [
    "AUTHORITATIVE", "AUTHORITY_BY_SOURCE", "BINDING_MECHANISMS", "GENERATED_NAMESPACE",
    "GRANTS", "ORIGIN_DEFAULT", "ORIGIN_DEPLOYMENT", "ORIGIN_FALLBACK",
    "ORIGIN_INSTRUMENT", "SHADOW", "SOURCE_GENERATED", "SOURCE_HANDWRITTEN",
    "SOURCE_IR_GRAPH", "AuthorityNotGranted", "ExecutionBinding", "assert_may_execute",
    "bind", "resolve_binding", "resolve_shadow_binding", "source_of", "strategy_for",
    "strategy_for_execution",
]
