"""Managed, non-authoritative shadow deployments — the lifecycle of an observed graph.

**What this is for.** Before L1.3A the IR shadow lane paired a graph to an instrument by
*convention*: whichever graph happened to mirror the instrument's authoritative strategy
key, decided at runtime, recorded nowhere, gone on restart. That is fine for a one-graph
experiment and useless as a platform statement. This module makes the pairing a server-owned
record with lineage, so the system can say

    this approved immutable graph version is deployed to this instrument at this interval
    in shadow mode, with this evidence and this admission state

durably, after a restart, and with every identity separately attributable.

**What it deliberately cannot do.** It cannot express authority. There is no mode
parameter, no authority parameter, and no code path that writes anything but
`ir_graph` / `shadow` / `non_authoritative`. ADR 0012 §3.2 — paper authority as a
source-and-mode pair — is the owner's decision and is not implemented here.

**Three independent refusals, on purpose.** `AUTHORITY_BY_SOURCE` maps `ir_graph` to
`SHADOW`; the table CHECK-constrains the mode and authority columns; and this service has
no vocabulary for anything else. Any one alone would be a convention that a future edit
could relax without noticing. Together, granting authority requires a reviewed change in
three places, which is the visibility the owner gate is for.

**Verification, not declaration.** Rows record a graph content address and a research
decision. Both are *claims*, and a claim stops being true the moment something moves under
it — so activation re-derives the address from the stored artefact bytes and re-checks the
decision through the read-only research bridge, and every reload re-derives the address
again. What reload does not do is re-open the research database: that lineage was verified
at activation, the row records when, and a control-loop boundary is the wrong place to make
a cross-plane read.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import GraphVersion, IrShadowDeployment
from app.ir.hashing import canonical_json, content_address

#: The lifecycle. Four states, and no more: each one answers a question an operator
#: actually asks, and a state nobody can act on differently is a comment in a column.
STAGED = "staged"              # described and verified enough to exist; not evaluated
SHADOW_ACTIVE = "shadow_active"  # evaluated by the observer
PAUSED = "paused"              # not evaluated; may resume without re-approval
RETIRED = "retired"            # terminal; the record of what once ran here
STATES = (STAGED, SHADOW_ACTIVE, PAUSED, RETIRED)

#: The only source/mode/authority triple this module can write. Not parameters.
SOURCE = "ir_graph"
MODE = "shadow"
AUTHORITY = "non_authoritative"

#: States that hold the (deployment, instrument, interval) slot. Mirrors the partial unique
#: index; kept beside it so a change to one is visibly a change to the other.
LIVE_STATES = (STAGED, SHADOW_ACTIVE, PAUSED)

#: **What this service permits from each state.** Same shape and same discipline as
#: `paper_authority.TRANSITIONS` — descriptive metadata mirroring the guards below, proven
#: against them by driving the real services from every state.
#:
#: Deliberately a **separate** table rather than a shared one. The two planes look alike and
#: are not: retiring paper authority must name a rollback target, and retiring an observer
#: has nothing to hand back. One table would have to be widened for the union, and a
#: capability contract that over-promises on one plane is worse than two small tables.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    STAGED: ("activate", "retire"),
    SHADOW_ACTIVE: ("pause", "retire"),
    PAUSED: ("resume", "retire"),
    RETIRED: (),
}

#: A shadow transition needs nothing beyond the row id and its revision — there is no
#: authority to hand back.
TRANSITION_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "activate": (), "pause": (), "resume": (), "retire": (),
}


def permitted_transitions(state: str) -> tuple[str, ...]:
    """The lifecycle actions this service accepts from `state`. Pure."""
    return TRANSITIONS.get(state, ())


def transition_requirements(action: str) -> tuple[str, ...]:
    return TRANSITION_ARGUMENTS.get(action, ())


class ShadowDeploymentError(Exception):
    """Base for every refusal here, so a caller can catch the family."""


class IllegalTransition(ShadowDeploymentError):
    """The lifecycle does not allow this move from this state."""


class RevisionConflict(ShadowDeploymentError):
    """The caller acted on a revision that is no longer current."""


class BindingUnverifiable(ShadowDeploymentError):
    """The graph, instrument or interval this row names cannot be confirmed."""


class EvidenceUnverified(ShadowDeploymentError):
    """The research lineage does not approve *this* artefact."""


class NotAdmissible(ShadowDeploymentError):
    """The configured history cannot satisfy the graph's declared warmup."""


@dataclass(frozen=True)
class ShadowBinding:
    """What the observer is told, and the whole of what it is told.

    Frozen, and carrying **no strategy object, broker, or callable** — only identities and
    the verified addresses. The engine holds these every tick; if one carried something an
    entry path could invoke, "non-authoritative" would be a naming convention rather than a
    property. Resolving the adapter stays the observer's job, through the shadow-only
    boundary in `execution_binding`.
    """

    deployment_row_id: int
    project_id: str
    graph_identifier: str
    graph_version: int
    content_address: str
    evidence_run_id: int | None
    evidence_candidate_id: int | None
    evidence_content_address: str
    deployment_id: int
    instrument_key: str
    interval: str
    strategy_key: str
    runtime_source: str
    execution_mode: str
    authority: str


def strategy_key_for(graph_identifier: str) -> str:
    """The stable execution identity of a graph-backed strategy.

    Stable **across versions** on purpose: `InstrumentState.strategy_key` and persisted
    rows must keep resolving after an edit. That is exactly why it cannot identify the
    artefact — `(identifier, version)` and the content address do that, in their own
    columns.
    """
    from app.strategy.registry import IR_NAMESPACE

    return f"{IR_NAMESPACE}{graph_identifier}"


def verified_decision(*, project_id: str, graph_identifier: str, graph_version: int):
    """The verified research approval for one graph version, or None.

    A thin seam over the read-only research bridge. It exists as a module-level name so the
    cross-plane read has exactly one call site, and so tests can state a verdict instead of
    reaching across an isolation boundary that hard invariant 5 puts there on purpose.
    """
    from app.core.research_read import verified_graph_decision

    return verified_graph_decision(project_id=project_id,
                                   graph_identifier=graph_identifier,
                                   graph_version=graph_version)


# ── writing ─────────────────────────────────────────────────────────────────────

def stage(session, *, project_id: str, graph_identifier: str, graph_version: int,
          deployment_id: int, instrument_key: str, interval: str,
          note: str = "") -> IrShadowDeployment:
    """Describe a shadow deployment. Verified enough to exist; not yet evaluated.

    Staging checks what is knowable without a decision — that the artefact exists, that its
    bytes hash to what they claim, that the instrument and interval are real. Evidence and
    admission are checked at activation, because those are the things that make it *run*.
    """
    version = _graph_version(session, graph_identifier, graph_version)
    address = _verified_address(version)
    _require_known_instrument(instrument_key)
    _require_known_interval(interval)

    now = dt.datetime.now()
    row = IrShadowDeployment(
        project_id=project_id, graph_identifier=graph_identifier,
        graph_version=graph_version, graph_content_address=address,
        deployment_id=deployment_id, instrument_key=instrument_key, interval=interval,
        strategy_key=strategy_key_for(graph_identifier),
        runtime_source=SOURCE, execution_mode=MODE, authority=AUTHORITY,
        state=STAGED, revision=0, note=note, created_at=now, updated_at=now)
    session.add(row)
    session.flush()
    return row


def activate(session, row_id: int, *, revision: int) -> IrShadowDeployment:
    """Staged or paused → shadow-active, after re-verifying everything that could move.

    Deliberately the heaviest transition in the module: it is the only one that starts
    evaluation, so it is the only place worth paying for full verification.
    """
    row = _for_update(session, row_id, revision)
    if row.state not in (STAGED, PAUSED):
        raise IllegalTransition(
            f"shadow deployment {row_id} is {row.state!r}; only {STAGED!r} or {PAUSED!r} "
            f"can be activated")

    version = _graph_version(session, row.graph_identifier, row.graph_version)
    address = _verified_address(version)
    if address != row.graph_content_address:
        raise BindingUnverifiable(
            f"shadow deployment {row_id} records content address "
            f"{row.graph_content_address!r} but {row.graph_identifier!r} v"
            f"{row.graph_version} hashes to {address!r} — the bytes moved under a row that "
            f"claims to name them")

    decision = _require_evidence(row)
    admission = _admission_for(row, version.artifact_json)
    row.admission_ok = admission.ok
    row.admission_reason = admission.reason[:400]
    if not admission.ok:
        session.flush()
        raise NotAdmissible(admission.reason)

    row.evidence_run_id = decision.get("run_id")
    row.evidence_candidate_id = decision.get("candidate_id")
    row.evidence_content_address = decision.get("content_address") or ""
    row.evidence_verified_at = dt.datetime.now()
    return _transition(session, row, SHADOW_ACTIVE)


def pause(session, row_id: int, *, revision: int) -> IrShadowDeployment:
    row = _for_update(session, row_id, revision)
    if row.state != SHADOW_ACTIVE:
        raise IllegalTransition(f"only a {SHADOW_ACTIVE!r} deployment can be paused; "
                                f"{row_id} is {row.state!r}")
    return _transition(session, row, PAUSED)


def resume(session, row_id: int, *, revision: int) -> IrShadowDeployment:
    """Paused → active. Re-verifies exactly as activation does: a pause is a gap during
    which the world could have changed, and resuming on trust would make the pause the one
    window in which a graph could move unnoticed."""
    row = _for_update(session, row_id, revision)
    if row.state != PAUSED:
        raise IllegalTransition(f"only a {PAUSED!r} deployment can be resumed; {row_id} "
                                f"is {row.state!r}")
    return activate(session, row_id, revision=revision)


def retire(session, row_id: int, *, revision: int) -> IrShadowDeployment:
    """Terminal, and terminal on purpose. A retired binding that could be revived would let
    a graph nobody re-approved come back — quietly, and most likely across a restart."""
    row = _for_update(session, row_id, revision)
    if row.state == RETIRED:
        raise IllegalTransition(f"shadow deployment {row_id} is already retired")
    return _transition(session, row, RETIRED)


# ── reading ─────────────────────────────────────────────────────────────────────

def active_bindings(session, *, on_problem=None) -> list[ShadowBinding]:
    """Every binding the observer should evaluate, re-verified.

    Called at startup and at controlled refresh boundaries — never per instrument per tick.
    A binding whose graph no longer hashes to its recorded address is **dropped and
    reported**, not repaired: silently rebinding to whatever bytes are there now is the
    silent-substitution failure this project keeps closing, one plane at a time.
    """
    out: list[ShadowBinding] = []
    rows = session.scalars(
        select(IrShadowDeployment)
        .where(IrShadowDeployment.state == SHADOW_ACTIVE)
        .order_by(IrShadowDeployment.id))
    for row in rows:
        try:
            version = _graph_version(session, row.graph_identifier, row.graph_version)
            address = _verified_address(version)
            if address != row.graph_content_address:
                raise BindingUnverifiable(
                    f"{row.graph_identifier!r} v{row.graph_version} content address "
                    f"changed under shadow deployment {row.id}")
            if (row.execution_mode, row.authority, row.runtime_source) != (
                    MODE, AUTHORITY, SOURCE):
                raise BindingUnverifiable(
                    f"shadow deployment {row.id} claims "
                    f"{row.runtime_source}/{row.execution_mode}/{row.authority}, which is "
                    f"not the one reviewed pair")
        except ShadowDeploymentError as exc:
            if on_problem is not None:
                on_problem(str(exc))
            continue
        out.append(ShadowBinding(
            deployment_row_id=row.id, project_id=row.project_id,
            graph_identifier=row.graph_identifier, graph_version=row.graph_version,
            content_address=row.graph_content_address,
            evidence_run_id=row.evidence_run_id,
            evidence_candidate_id=row.evidence_candidate_id,
            evidence_content_address=row.evidence_content_address,
            deployment_id=row.deployment_id, instrument_key=row.instrument_key,
            interval=row.interval, strategy_key=row.strategy_key,
            runtime_source=row.runtime_source, execution_mode=row.execution_mode,
            authority=row.authority))
    return out


def listing(session, *, include_retired: bool = False) -> list[dict]:
    stmt = select(IrShadowDeployment).order_by(IrShadowDeployment.id)
    if not include_retired:
        stmt = stmt.where(IrShadowDeployment.state != RETIRED)
    return [row.to_dict() for row in session.scalars(stmt)]


# ── internals ───────────────────────────────────────────────────────────────────

def _for_update(session, row_id: int, revision: int) -> IrShadowDeployment:
    row = session.get(IrShadowDeployment, row_id)
    if row is None:
        raise BindingUnverifiable(f"no shadow deployment with id {row_id}")
    if row.revision != revision:
        raise RevisionConflict(
            f"shadow deployment {row_id} is at revision {row.revision}, not {revision} — "
            f"somebody else changed it since this decision was made")
    return row


def _transition(session, row: IrShadowDeployment, state: str) -> IrShadowDeployment:
    row.state = state
    row.revision += 1
    row.updated_at = dt.datetime.now()
    session.flush()
    return row


def _graph_version(session, graph_identifier: str, graph_version: int) -> GraphVersion:
    version = session.get(GraphVersion, (graph_identifier, graph_version))
    if version is None:
        raise BindingUnverifiable(
            f"graph {graph_identifier!r} v{graph_version} does not exist")
    return version


def _verified_address(version: GraphVersion) -> str:
    """Re-derive the address from the artefact bytes rather than trusting the column."""
    import json

    document = json.loads(version.artifact_json)
    if canonical_json(document) != version.artifact_json:
        raise BindingUnverifiable(
            f"graph {version.graph_identifier!r} v{version.version} is not stored as "
            f"canonical JSON; its content address cannot be trusted")
    return content_address(document)


def _require_known_instrument(instrument_key: str) -> None:
    from app.core.instruments import all_instruments

    if instrument_key not in {i.key for i in all_instruments()}:
        raise BindingUnverifiable(f"unknown instrument {instrument_key!r}")


def _require_known_interval(interval: str) -> None:
    from app.engine.ir_shadow import INTERVAL_MINUTES

    if interval not in INTERVAL_MINUTES:
        raise BindingUnverifiable(
            f"unknown interval {interval!r}; expected one of "
            f"{sorted(INTERVAL_MINUTES)}")


def _require_evidence(row: IrShadowDeployment) -> dict:
    decision = verified_decision(project_id=row.project_id,
                                 graph_identifier=row.graph_identifier,
                                 graph_version=row.graph_version)
    if not decision:
        raise EvidenceUnverified(
            f"no verified research decision approves {row.graph_identifier!r} v"
            f"{row.graph_version} for project {row.project_id!r}")
    mismatches = [
        f"project {decision.get('project_id')!r} != {row.project_id!r}"
        if decision.get("project_id") != row.project_id else "",
        f"graph {decision.get('graph_identifier')!r} != {row.graph_identifier!r}"
        if decision.get("graph_identifier") != row.graph_identifier else "",
        f"version {decision.get('graph_version')!r} != {row.graph_version!r}"
        if decision.get("graph_version") != row.graph_version else "",
        f"decision is {decision.get('decision')!r}, not 'approved'"
        if decision.get("decision") != "approved" else "",
    ]
    named = [m for m in mismatches if m]
    if named:
        raise EvidenceUnverified(
            f"the research decision does not approve this artefact: {'; '.join(named)}")
    return decision


def _admission_for(row: IrShadowDeployment, version_json: str):
    """The Stage 1 warmup/history contract, applied before activation instead of being
    discovered once per scan for a whole session."""
    import json

    from app.core.instruments import get_instrument
    from app.engine import ir_shadow

    instrument = get_instrument(row.instrument_key)
    if instrument is None:
        raise BindingUnverifiable(f"unknown instrument {row.instrument_key!r}")
    warmup = ir_shadow.declared_warmup_for_graph(json.loads(version_json))
    return ir_shadow.admit(
        instrument_key=row.instrument_key,
        segment=getattr(instrument, "segment", "") or "",
        interval=row.interval,
        history_days=get_settings().history_days,
        warmup=warmup)


__all__ = [
    "AUTHORITY", "LIVE_STATES", "MODE", "PAUSED", "RETIRED", "SHADOW_ACTIVE", "SOURCE",
    "STAGED", "STATES", "BindingUnverifiable", "EvidenceUnverified", "IllegalTransition",
    "NotAdmissible", "RevisionConflict", "ShadowBinding", "ShadowDeploymentError",
    "activate", "active_bindings", "listing", "pause", "resume", "retire", "stage",
    "strategy_key_for", "verified_decision",
]
