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

from app.core.execution_book import LIVE, PAPER, configured_execution_mode
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

#: **The reviewed grants, as (source, execution_mode, authority) triples.** A gate keyed
#: on source alone cannot express ADR 0012 §3.2's smallest safe future step — "`ir_graph`
#: is authoritative *in paper mode*" — so the reviewed unit is the pair of source and
#: mode, and anything not in this set is unreviewed and refused.
#:
#: `(ir_graph, paper)` is **absent, deliberately**. L1.3B made authority mode-aware
#: precisely so that granting it later is one visible line here rather than a side effect
#: of some unrelated change; the decision itself stays with the owner.
#:
#: This is also what makes an `ExecutionBinding` unable to grant itself authority by
#: asserting a field: `strategy_for_execution` checks membership here, at the point of
#: use, and recomputes both the source and the mode rather than trusting the binding.
GRANTS = frozenset({
    (SOURCE_HANDWRITTEN, PAPER, AUTHORITATIVE),
    (SOURCE_HANDWRITTEN, LIVE, AUTHORITATIVE),
    (SOURCE_GENERATED, PAPER, AUTHORITATIVE),
    (SOURCE_GENERATED, LIVE, AUTHORITATIVE),
    #: **Granted by the owner on 2026-08-07 (L1.3C).** An approved immutable graph version
    #: may be authoritative for one instrument in the paper book. `(SOURCE_IR_GRAPH, LIVE,
    #: AUTHORITATIVE)` is deliberately absent and is the next owner gate.
    (SOURCE_IR_GRAPH, PAPER, AUTHORITATIVE),
})

#: Which layer decided the binding. Narrowest that spoke, not narrowest that exists.
ORIGIN_DEPLOYMENT = "deployment"
#: A verified paper-authority deployment (`core/paper_authority.py`). The **only** origin
#: through which a graph-backed key may execute, which is why membership in `GRANTS` is
#: necessary but not sufficient — see `strategy_for_execution`.
ORIGIN_PAPER_AUTHORITY = "paper_authority_deployment"
ORIGIN_INSTRUMENT = "instrument"
ORIGIN_DEFAULT = "default"
ORIGIN_FALLBACK = "fallback"

#: Everything that already claims to answer "what runs here". Declared so that adding a
#: seventh is a deliberate edit with a test to justify it, rather than a new table quietly
#: becoming a second deployment model. Column names, not prose, so the guard test can check
#: they still exist.
BINDING_MECHANISMS = (
    "deployments.strategy_key",
    "deployments.admission_address",
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
    #: The execution mode in force when this binding was described. Recorded so the
    #: decision is auditable, and **never trusted** — the gate recomputes it. Defaulted
    #: so a hand-built binding that omits it is refused rather than accidentally allowed.
    execution_mode: str = ""
    owner_id: str | None = None
    #: Immutable causal-admission receipt. None is explicit legacy quarantine.
    admission_address: str | None = None


def source_of(strategy_key: str | None) -> str:
    if strategy_key and strategy_key.startswith(IR_NAMESPACE):
        return SOURCE_IR_GRAPH
    if strategy_key and strategy_key.startswith(GENERATED_NAMESPACE):
        return SOURCE_GENERATED
    return SOURCE_HANDWRITTEN


def strategy_for(binding: ExecutionBinding):
    """The `Strategy` object a binding names. Fail-closed — the binding already resolved
    once, so anything unresolvable here is drift, not a config problem."""
    return resolve_strategy(binding.strategy_key, owner_id=binding.owner_id)


def strategy_for_execution(binding: ExecutionBinding, *, admission_loader=None):
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
    mode = configured_execution_mode()
    if claimed != actual or binding.execution_mode != mode \
            or (actual, mode, binding.authority) not in GRANTS \
            or binding.authority != AUTHORITATIVE:
        raise AuthorityNotGranted(binding.strategy_key, actual)
    strategy = resolve_strategy(binding.strategy_key, owner_id=binding.owner_id)
    if actual == SOURCE_IR_GRAPH:
        _require_paper_authority(binding, strategy, mode)
    # The final money boundary supplies this loader. Keeping it explicit means that
    # a receipt read cannot be hidden inside a descriptive strategy resolver.
    if admission_loader is not None:
        if not binding.admission_address or not admission_loader(binding):
            raise AuthorityNotGranted(binding.strategy_key, "ADMISSION_REQUIRED")
    return strategy


def _require_paper_authority(binding, strategy, mode) -> None:
    """The two extra proofs a graph-backed binding must pass, both recomputed here.

    **Why the grant alone is not enough.** This slice registers graph adapters so they are
    resolvable, which means `POST /api/instruments/NIFTY/strategy {ir.…}` now names
    something the registry can find. If membership in `GRANTS` were the whole test, that
    route would be an authoritative paper assignment — the exact hazard L1.2 closed. So the
    grant says *a graph may execute in paper*, and these say *this one, decided this way*.

    1. **Origin.** Only a verified paper-authority deployment may decide it. An instrument
       row, a watchlist, the platform default and the fail-safe fallback all still refuse.
    2. **Exact content address.** The adapter's `version` *is* the graph's content address,
       so comparing it against the address the deployment approved is what makes authority
       bind to bytes rather than to a name. A published edit re-registers the same stable
       key with a different address, and the binding that named the old one stops matching
       — authority is not inherited, it is re-granted or it is gone.

    Both are recomputed rather than trusted, for the same reason `source_of` is: a binding
    is a plain dataclass, and a field is a claim.

    **The mode is deliberately not re-checked here.** `GRANTS` above already refuses
    `(ir_graph, live, authoritative)`, and an earlier draft checked it in both places. That
    looked like defence in depth and was not: with two lines refusing the same thing,
    neither could be shown to work — disabling either left the other to catch it, and the
    mutation harness reported both as vacuous. A layer nobody can watch fail is decoration,
    not defence. One line, observable, is worth more than two that alibi each other.
    """
    if binding.origin != ORIGIN_PAPER_AUTHORITY:
        raise AuthorityNotGranted(binding.strategy_key, SOURCE_IR_GRAPH)
    if not binding.strategy_version or binding.strategy_version != strategy.version:
        raise AuthorityNotGranted(binding.strategy_key, SOURCE_IR_GRAPH)


def assert_may_execute(strategy_key: str | None, *, owner_id: str | None = None) -> None:
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
    if source == SOURCE_GENERATED:
        # Generated code is an owner-local artefact. Namespace authority alone cannot
        # prove that this owner has the bytes the key names.
        resolve_strategy(strategy_key, owner_id=owner_id)


def _describe(*, deployment_id, instrument_key, strategy, origin, reason,
              enforce_authority=True, owner_id: str | None = None,
              admission_address: str | None = None) -> ExecutionBinding:
    source = source_of(strategy.key)
    authority = AUTHORITY_BY_SOURCE.get(source, SHADOW)
    if enforce_authority and authority != AUTHORITATIVE:
        raise AuthorityNotGranted(strategy.key, source)
    return ExecutionBinding(
        deployment_id=deployment_id, instrument_key=instrument_key,
        strategy_key=strategy.key, strategy_version=strategy.version, source=source,
        authority=authority, origin=origin, reason=reason,
        execution_mode=configured_execution_mode(), owner_id=owner_id,
        admission_address=admission_address)


def bind(*, deployment_id: int, instrument_key: str, deployment_pin,
         assigned_key: str | None, paper_authority=None, owner_id: str | None = None,
         admission_address: str | None = None) -> ExecutionBinding:
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
    if paper_authority is not None and configured_execution_mode() == PAPER:
        return _describe_paper_authority(
            deployment_id, instrument_key, paper_authority, owner_id=owner_id)
    if deployment_pin is not None:
        return _describe(deployment_id=deployment_id, instrument_key=instrument_key,
                         strategy=deployment_pin, origin=ORIGIN_DEPLOYMENT,
                         reason=(f"deployment {deployment_id} pins "
                                 f"{deployment_pin.key!r}, which overrides any "
                                 f"per-instrument assignment"), owner_id=owner_id,
                         admission_address=admission_address)
    return _bind_assigned(deployment_id, instrument_key, assigned_key, owner_id=owner_id,
                          admission_address=admission_address)


def _describe_paper_authority(deployment_id, instrument_key,
                              record, *, owner_id: str | None = None) -> ExecutionBinding:
    """The binding a paper-authority deployment produces, verified as it is produced.

    **Precedence: first.** A record that names *this instrument*, *this interval* and one
    exact graph version is narrower than a deployment pin (which speaks for a whole book)
    and narrower than an instrument assignment (which names only a key). Narrowest that
    spoke wins, as everywhere else here.

    **Only in paper.** The caller checks the mode before reaching this, so in a live
    process the record is not consulted at all and the instrument resolves exactly as it
    did before this slice — no refusal, no skipped scan, no change to live behaviour. The
    gate refuses a forged paper binding separately, at consumption; the two are independent
    and both are required.

    **Fail closed on a version mismatch.** If the registry now resolves different bytes
    than the deployment approved, this raises rather than substituting. That means the
    instrument does not trade, which is the same posture a deployment pin already takes:
    an authoritative binding that cannot be honoured is not an invitation to trade
    something else.
    """
    strategy = resolve_strategy(record.strategy_key, owner_id=owner_id)
    if not record.content_address or strategy.version != record.content_address:
        raise AuthorityNotGranted(record.strategy_key, SOURCE_IR_GRAPH)
    return ExecutionBinding(
        deployment_id=deployment_id, instrument_key=instrument_key,
        strategy_key=record.strategy_key, strategy_version=record.content_address,
        source=SOURCE_IR_GRAPH, authority=AUTHORITATIVE,
        execution_mode=PAPER, origin=ORIGIN_PAPER_AUTHORITY,
        reason=(f"paper deployment {record.deployment_row_id} makes "
                f"{record.graph_identifier!r} v{record.graph_version} "
                f"({record.content_address[:19]}…) authoritative for {instrument_key} "
                f"at {record.interval} in the paper book"), owner_id=owner_id,
        admission_address=getattr(record, "admission_address", None))


def resolve_binding(session, *, deployment_id: int, instrument_key: str,
                    owner_id: str, broker_account_id: str) -> ExecutionBinding:
    """`bind`, with the deployment pin and the instrument assignment read from the
    database. The entry point for callers that hold a session and no cached config."""
    from app.core.deployments import resolve_deployment_strategy

    from app.db.models import Deployment
    deployment = session.get(Deployment, deployment_id)
    return bind(deployment_id=deployment_id, instrument_key=instrument_key,
                deployment_pin=resolve_deployment_strategy(
                    session, deployment_id, owner_id=owner_id,
                    broker_account_id=broker_account_id),
                assigned_key=_assigned_strategy_key(session, instrument_key, owner_id=owner_id),
                owner_id=owner_id,
                admission_address=(deployment.admission_address if deployment is not None else None))


def _bind_assigned(deployment_id, instrument_key, assigned, *, owner_id: str | None = None,
                   admission_address: str | None = None) -> ExecutionBinding:
    if not assigned:
        return _describe(deployment_id=deployment_id, instrument_key=instrument_key,
                         strategy=resolve_strategy(DEFAULT_STRATEGY_KEY),
                         origin=ORIGIN_DEFAULT,
                         reason=(f"no deployment pin and no instrument assignment for "
                                 f"{instrument_key}; the platform default applies"), owner_id=owner_id,
                         admission_address=admission_address)
    try:
        strategy = resolve_strategy(assigned, owner_id=owner_id)
    except StrategyNotFound:
        if source_of(assigned) in (SOURCE_IR_GRAPH, SOURCE_GENERATED):
            # Graph-backed and generated keys never fall back: they would trade one logic while the
            # instrument row, the trade row and the experiment binding all name another.
            raise
        strategy = resolve_strategy(DEFAULT_STRATEGY_KEY)
        return _describe(deployment_id=deployment_id, instrument_key=instrument_key,
                         strategy=strategy, origin=ORIGIN_FALLBACK,
                         reason=(f"instrument {instrument_key} is assigned {assigned!r}, "
                                 f"which is not registered; the legacy path substitutes "
                                 f"{strategy.key!r} so one stale row cannot stop the book"), owner_id=owner_id,
                         admission_address=admission_address)
    return _describe(deployment_id=deployment_id, instrument_key=instrument_key,
                     strategy=strategy, origin=ORIGIN_INSTRUMENT,
                     reason=f"instrument {instrument_key} is assigned {strategy.key!r}", owner_id=owner_id,
                     admission_address=admission_address)


def resolve_shadow_binding(strategy_key: str,
                           instrument_key: str = "", *, owner_id: str | None = None) -> ExecutionBinding:
    """The same description for a strategy that may be *observed* but not executed.

    Refusing authority must not refuse observation, or the gate would have undone the
    shadow lane it exists to protect.
    """
    return _describe(deployment_id=0, instrument_key=instrument_key,
                     strategy=resolve_strategy(strategy_key, owner_id=owner_id), origin=ORIGIN_INSTRUMENT,
                     reason=(f"{strategy_key!r} is observed by the shadow lane, "
                             f"never executed"),
                     enforce_authority=False, owner_id=owner_id)


#: Which layer decided what gets *observed*. Two sources, one boundary, stated precedence —
#: a managed deployment is a durable, evidence-backed record and outranks a runtime
#: convention. `ORIGIN_LEGACY_PAIRING` is the Stage 1 mechanism, kept because retiring it
#: before anything replaces it would take shadow coverage to zero, and named because a
#: fallback nobody can see is a fallback nobody reviews.
ORIGIN_MANAGED_DEPLOYMENT = "managed_shadow_deployment"
ORIGIN_LEGACY_PAIRING = "legacy_key_pairing"


@dataclass(frozen=True)
class ShadowSource:
    """What to observe on one instrument, and on whose say-so.

    Carries identities only — no strategy object, no adapter, no callable. The observer
    resolves what it needs from the graph identifier; handing it something invocable would
    make "non-authoritative" a naming convention rather than a property of the type.
    """

    instrument_key: str
    graph_identifier: str
    content_address: str
    strategy_key: str
    pairing_key: str
    interval: str
    origin: str
    runtime_source: str
    execution_mode: str
    authority: str
    deployment_row_id: int | None


def shadow_source_for(*, instrument_key: str, authoritative_key: str | None,
                      managed, interval: str) -> ShadowSource | None:
    """The one place that answers "what should be shadowed here".

    Precedence: a managed shadow deployment, then the legacy key pairing, then nothing.
    Both sources come through this function so the observer has a single question to ask —
    two independent pairing mechanisms is exactly what L1.3A removes, while two *sources*
    behind one boundary with a stated order is not the same thing.

    Returns None rather than raising: having nothing to shadow on an instrument is an
    ordinary state, not a failure.
    """
    from app.engine.ir_shadow import PAIRING_BUILDERS_BY_GRAPH, pairing_for

    if managed is not None and managed.instrument_key == instrument_key:
        # The interval is part of the binding. A graph admitted for 30-minute bars has not
        # been admitted for 5-minute ones, and evaluating it there would produce refusals
        # the admission contract already ruled out.
        if managed.interval != interval:
            return None
        pairing_key = PAIRING_BUILDERS_BY_GRAPH.get(managed.graph_identifier)
        if pairing_key is None:
            return None
        return ShadowSource(
            instrument_key=instrument_key, graph_identifier=managed.graph_identifier,
            content_address=managed.content_address, strategy_key=managed.strategy_key,
            pairing_key=pairing_key, interval=managed.interval,
            origin=ORIGIN_MANAGED_DEPLOYMENT, runtime_source=managed.runtime_source,
            execution_mode=managed.execution_mode, authority=SHADOW,
            deployment_row_id=managed.deployment_row_id)

    pairing = pairing_for(authoritative_key)
    if pairing is None:
        return None
    return ShadowSource(
        instrument_key=instrument_key,
        graph_identifier=str(pairing.graph.get("identifier") or ""),
        content_address="", strategy_key="", pairing_key=authoritative_key or "",
        interval=interval, origin=ORIGIN_LEGACY_PAIRING, runtime_source=SOURCE_IR_GRAPH,
        execution_mode="shadow", authority=SHADOW, deployment_row_id=None)


def _assigned_strategy_key(session, instrument_key: str, *, owner_id: str) -> str | None:
    from app.db.models import InstrumentState

    row = session.get(InstrumentState, (owner_id, instrument_key))
    return (row.strategy_key or None) if row is not None else None


__all__ = [
    "AUTHORITATIVE", "AUTHORITY_BY_SOURCE", "BINDING_MECHANISMS", "GENERATED_NAMESPACE",
    "GRANTS", "ORIGIN_DEFAULT", "ORIGIN_DEPLOYMENT", "ORIGIN_FALLBACK",
    "ORIGIN_INSTRUMENT", "SHADOW", "SOURCE_GENERATED", "SOURCE_HANDWRITTEN",
    "ORIGIN_PAPER_AUTHORITY", "SOURCE_IR_GRAPH", "AuthorityNotGranted",
    "ExecutionBinding", "assert_may_execute",
    "bind", "resolve_binding", "resolve_shadow_binding", "source_of", "strategy_for",
    "strategy_for_execution",
]
