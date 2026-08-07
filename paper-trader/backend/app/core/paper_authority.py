"""Paper-authoritative IR deployments — the lifecycle of a graph that may trade on paper.

**What changed, and what did not.** The owner granted `(ir_graph, paper, authoritative)` on
2026-08-07. That grant changes *who may author a paper signal*; it changes nothing about
how execution works afterwards. Everything downstream of the signal — entry processing,
sizing, routing, the position and trade models, `PaperBroker`, accounting, exits,
reconciliation, risk and kill controls, restart recovery — is the existing machinery,
untouched. There is no IR paper trader.

**Why this is a separate module from `shadow_deployments`.** That one is an observer: no
capital, no orders, no arm state, no authority, and — structurally — no vocabulary for a
mode. This one means authority. Merging them would produce a single service whose meaning
depends on a column, which is the collapse ADR 0012 keeps refusing. The two share a shape
because the failure modes are identical; they share no code path that could let one become
the other.

**Three independent refusals, still.** `GRANTS` refuses live IR authority in code; the
table CHECK-constrains `execution_mode` to `paper`; and this service has no mode or
authority parameter. Any one alone would be a convention a later edit could relax without
noticing.

**Verification, not declaration.** A row records a content address and a research decision,
and both are claims that stop being true the moment something moves underneath them. So the
address is re-derived from the stored artefact bytes at activation, again on every reload,
**and a third time at the authority gate** against the adapter the registry actually
resolves. Three places, deliberately: the first two protect the record, the last protects
the trade.

**Rollback is named, never inferred.** Retiring a binding restores a strategy somebody
wrote down at the moment of retirement, or nothing at all. "Whatever the instrument row
said before" and "the platform default" are runtime guesses, and silent substitution is the
failure this project has now closed twice.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import GraphVersion, InstrumentState, IrPaperDeployment
from app.ir.hashing import canonical_json, content_address

#: The lifecycle. Four states, mirroring the shadow record's because an operator asks the
#: same four questions of anything deployed.
STAGED = "staged"                # described and verified enough to exist; not authoritative
PAPER_ACTIVE = "paper_active"    # authoritative for this instrument, in the paper book
PAUSED = "paused"                # not authoritative; may resume after re-verification
RETIRED = "retired"              # terminal; the record of what once traded here
STATES = (STAGED, PAPER_ACTIVE, PAUSED, RETIRED)

#: The only source/mode/authority triple this module can write. Not parameters — see the
#: module docstring on why the absence of a keyword argument is itself a control.
SOURCE = "ir_graph"
MODE = "paper"
AUTHORITY = "authoritative"

#: States that hold the (deployment, instrument, interval) slot. Mirrors the partial unique
#: index; kept beside it so a change to one is visibly a change to the other.
LIVE_STATES = (STAGED, PAPER_ACTIVE, PAUSED)


class PaperAuthorityError(Exception):
    """Base for every refusal here, so a caller can catch the family."""


class IllegalTransition(PaperAuthorityError):
    """The lifecycle does not allow this move from this state."""


class RevisionConflict(PaperAuthorityError):
    """The caller acted on a revision that is no longer current."""


class BindingUnverifiable(PaperAuthorityError):
    """The graph, instrument or interval this row names cannot be confirmed."""


class EvidenceUnverified(PaperAuthorityError):
    """The research lineage does not approve *this* artefact."""


class NotAdmissible(PaperAuthorityError):
    """The instrument/interval cannot supply the history this graph declares it needs."""


class RollbackTargetInvalid(PaperAuthorityError):
    """The named rollback target is not a strategy that may hold authority."""


@dataclass(frozen=True)
class PaperBinding:
    """What the engine is told, and the whole of what it is told.

    Frozen, and carrying **no strategy object, broker or callable** — only identities and
    verified addresses. The engine holds these for the life of a session; if one carried
    something invocable, the authority gate would be advisory, because anything holding the
    binding could simply call it. Resolving the adapter stays the binding layer's job, and
    it re-checks the content address when it does.
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

    Stable **across versions** on purpose: persisted rows must keep resolving after an
    edit. That is exactly why it cannot identify the artefact — `(identifier, version)` and
    the content address do that, in their own columns.
    """
    from app.strategy.registry import IR_NAMESPACE

    return f"{IR_NAMESPACE}{graph_identifier}"


def verified_decision(*, project_id: str, graph_identifier: str, graph_version: int):
    """The verified research approval for one graph version, or None.

    One call site for the cross-plane read, so the isolation boundary hard invariant 5 puts
    there has exactly one door, and tests can state a verdict instead of reaching through it.
    """
    from app.core.research_read import verified_graph_decision

    return verified_graph_decision(project_id=project_id,
                                   graph_identifier=graph_identifier,
                                   graph_version=graph_version)


# ── writing ─────────────────────────────────────────────────────────────────────

def stage(session, *, project_id: str, graph_identifier: str, graph_version: int,
          deployment_id: int, instrument_key: str, interval: str,
          note: str = "") -> IrPaperDeployment:
    """Describe a paper-authority deployment. Verified enough to exist; not yet authoritative.

    Staging checks what is knowable without a decision — the artefact exists, its bytes hash
    to what they claim, the instrument and interval are real. Evidence and admission are
    checked at activation, because those are what make it *trade*.
    """
    version = _graph_version(session, graph_identifier, graph_version)
    address = _verified_address(version)
    _require_known_instrument(instrument_key)
    _require_known_interval(interval)

    now = dt.datetime.now()
    row = IrPaperDeployment(
        project_id=project_id, graph_identifier=graph_identifier,
        graph_version=graph_version, graph_content_address=address,
        deployment_id=deployment_id, instrument_key=instrument_key, interval=interval,
        strategy_key=strategy_key_for(graph_identifier),
        runtime_source=SOURCE, execution_mode=MODE, authority=AUTHORITY,
        state=STAGED, revision=0, note=note, created_at=now, updated_at=now)
    session.add(row)
    session.flush()
    return row


def activate(session, row_id: int, *, revision: int) -> IrPaperDeployment:
    """Staged or paused → paper-active, after re-verifying everything that could move.

    The heaviest transition in the module, deliberately: it is the only one that lets a
    graph author a signal that becomes a position.
    """
    row = _for_update(session, row_id, revision)
    if row.state not in (STAGED, PAUSED):
        raise IllegalTransition(
            f"paper deployment {row_id} is {row.state!r}; only {STAGED!r} or {PAUSED!r} "
            f"can be activated")

    version = _graph_version(session, row.graph_identifier, row.graph_version)
    address = _verified_address(version)
    if address != row.graph_content_address:
        raise BindingUnverifiable(
            f"paper deployment {row_id} records content address "
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
    return _transition(session, row, PAPER_ACTIVE)


def pause(session, row_id: int, *, revision: int) -> IrPaperDeployment:
    """Active → paused. Authority stops at the next refresh boundary; nothing is rewritten,
    and any position the graph already opened stays under the ordinary risk lane."""
    row = _for_update(session, row_id, revision)
    if row.state != PAPER_ACTIVE:
        raise IllegalTransition(f"only a {PAPER_ACTIVE!r} deployment can be paused; "
                                f"{row_id} is {row.state!r}")
    return _transition(session, row, PAUSED)


def resume(session, row_id: int, *, revision: int) -> IrPaperDeployment:
    """Paused → active, re-verifying exactly as activation does. A pause is a gap in which
    the world can move, and resuming on trust would make it the one window where a graph
    could change unnoticed."""
    row = _for_update(session, row_id, revision)
    if row.state != PAUSED:
        raise IllegalTransition(f"only a {PAUSED!r} deployment can be resumed; {row_id} "
                                f"is {row.state!r}")
    return activate(session, row_id, revision=revision)


def retire(session, row_id: int, *, revision: int,
           restore_strategy_key: str | None) -> IrPaperDeployment:
    """Terminal, and the only place authority is handed back.

    `restore_strategy_key` is **required** — passing it explicitly, even as `None`, is the
    point. `None` means "there was no previous authority here"; a key means "put this back".
    Neither is inferred, because the alternative is a runtime guess about which strategy
    should trade an instrument, and that is the silent-substitution failure this project has
    closed twice. A target that cannot itself hold authority is refused: rolling back onto a
    graph key would revoke authority and re-grant it through the door left shut.

    Terminal on purpose. A retired binding that could be revived would let a graph nobody
    re-approved come back, most likely across a restart.
    """
    row = _for_update(session, row_id, revision)
    if row.state == RETIRED:
        raise IllegalTransition(f"paper deployment {row_id} is already retired")
    _validate_rollback_target(restore_strategy_key)
    row.rollback_strategy_key = restore_strategy_key
    _restore_instrument_authority(session, row.instrument_key, restore_strategy_key)
    return _transition(session, row, RETIRED)


# ── reading ─────────────────────────────────────────────────────────────────────

def active_bindings(session, *, on_problem=None) -> list[PaperBinding]:
    """Every paper-authority binding the engine should honour, re-verified.

    Called at startup and at controlled refresh boundaries — never per instrument per tick.
    A binding whose graph no longer hashes to its recorded address is **dropped and
    reported**, not repaired: rebinding to whatever bytes are there now is the silent
    substitution this project keeps closing, and here it would do it with authority.
    """
    out: list[PaperBinding] = []
    rows = session.scalars(
        select(IrPaperDeployment)
        .where(IrPaperDeployment.state == PAPER_ACTIVE)
        .order_by(IrPaperDeployment.id))
    for row in rows:
        try:
            version = _graph_version(session, row.graph_identifier, row.graph_version)
            address = _verified_address(version)
            if address != row.graph_content_address:
                raise BindingUnverifiable(
                    f"{row.graph_identifier!r} v{row.graph_version} content address "
                    f"changed under paper deployment {row.id}")
            if (row.execution_mode, row.authority, row.runtime_source) != (
                    MODE, AUTHORITY, SOURCE):
                raise BindingUnverifiable(
                    f"paper deployment {row.id} claims "
                    f"{row.runtime_source}/{row.execution_mode}/{row.authority}, which is "
                    f"not the one reviewed triple")
        except PaperAuthorityError as exc:
            if on_problem is not None:
                on_problem(str(exc))
            continue
        out.append(PaperBinding(
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


def adapter_for(session, binding: PaperBinding):
    """Build the graph adapter for a binding, from the exact stored bytes it names.

    Not from the shipped `app/ir/strategies` module and not from a builder table: the
    deployment approved one artefact, identified by content address, and the adapter that
    trades must be that artefact or nothing. The address is re-derived here as well —
    the second of the three checks (activation, here, and the authority gate).

    The *components* it resolves against are the platform library's, not one strategy's.
    That distinction is what the 2026-08-07 G-1 correction established: the bytes come from
    the deployment's approved artefact, and the vocabulary they resolve against belongs to
    the platform.
    """
    import json

    from app.ir.library import IMPLEMENTATIONS, LIBRARY
    from app.strategy.ir_adapter import IRGraphStrategy

    version = _graph_version(session, binding.graph_identifier, binding.graph_version)
    address = _verified_address(version)
    if address != binding.content_address:
        raise BindingUnverifiable(
            f"{binding.graph_identifier!r} v{binding.graph_version} hashes to {address!r}, "
            f"not the {binding.content_address!r} paper deployment "
            f"{binding.deployment_row_id} approved")
    return IRGraphStrategy(json.loads(version.artifact_json), (LIBRARY, IMPLEMENTATIONS))


def register_active_adapters(session, *, on_problem=None) -> list[PaperBinding]:
    """Load every paper-authoritative binding and make its graph resolvable.

    Registration is what lets the ONE registry answer for a graph-backed key, so nothing
    here is a second registry — it is the existing one being told about a strategy that was
    reconstructed from the database, exactly as generated strategies already are.

    Registering does **not** grant anything. A registered graph is resolvable by name, and
    `execution_binding` still refuses it unless the binding came from this record and the
    adapter's address matches. That separation is deliberate: resolvability and authority
    are different questions, and the L1.2 hazard is what happens when they are answered by
    the same lookup.
    """
    from app.strategy.registry import register

    bindings = active_bindings(session, on_problem=on_problem)
    out: list[PaperBinding] = []
    for binding in bindings:
        try:
            register(adapter_for(session, binding))
        except Exception as exc:   # a graph that will not build must not stop the others
            if on_problem is not None:
                on_problem(f"paper deployment {binding.deployment_row_id}: {exc}")
            continue
        out.append(binding)
    return out


def listing(session, *, include_retired: bool = False) -> list[dict]:
    stmt = select(IrPaperDeployment).order_by(IrPaperDeployment.id)
    if not include_retired:
        stmt = stmt.where(IrPaperDeployment.state != RETIRED)
    return [row.to_dict() for row in session.scalars(stmt)]


# ── internals ───────────────────────────────────────────────────────────────────

def _for_update(session, row_id: int, revision: int) -> IrPaperDeployment:
    row = session.get(IrPaperDeployment, row_id)
    if row is None:
        raise BindingUnverifiable(f"no paper deployment with id {row_id}")
    if row.revision != revision:
        raise RevisionConflict(
            f"paper deployment {row_id} is at revision {row.revision}, not {revision} — "
            f"somebody else changed it since this decision was made")
    return row


def _transition(session, row: IrPaperDeployment, state: str) -> IrPaperDeployment:
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
            f"unknown interval {interval!r}; expected one of {sorted(INTERVAL_MINUTES)}")


def _require_evidence(row: IrPaperDeployment) -> dict:
    decision = verified_decision(project_id=row.project_id,
                                 graph_identifier=row.graph_identifier,
                                 graph_version=row.graph_version)
    if not decision:
        raise EvidenceUnverified(
            f"no verified research decision approves {row.graph_identifier!r} v"
            f"{row.graph_version} for project {row.project_id!r}")
    named = [m for m in (
        f"project {decision.get('project_id')!r} != {row.project_id!r}"
        if decision.get("project_id") != row.project_id else "",
        f"graph {decision.get('graph_identifier')!r} != {row.graph_identifier!r}"
        if decision.get("graph_identifier") != row.graph_identifier else "",
        f"version {decision.get('graph_version')!r} != {row.graph_version!r}"
        if decision.get("graph_version") != row.graph_version else "",
        f"decision is {decision.get('decision')!r}, not 'approved'"
        if decision.get("decision") != "approved" else "",
    ) if m]
    if named:
        raise EvidenceUnverified(
            f"the research decision does not approve this artefact: {'; '.join(named)}")
    return decision


def _admission_for(row: IrPaperDeployment, version_json: str):
    """The warmup/history contract, applied before activation instead of being discovered
    once per scan for a whole session."""
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


def _validate_rollback_target(strategy_key: str | None) -> None:
    """`None` is valid and means "no previous authority". Anything else must be a strategy
    that exists and may itself execute."""
    if strategy_key is None:
        return
    from app.core.execution_binding import AuthorityNotGranted, assert_may_execute
    from app.strategy.registry import StrategyNotFound, resolve_strategy

    try:
        resolve_strategy(strategy_key)
        assert_may_execute(strategy_key)
    except (StrategyNotFound, AuthorityNotGranted) as exc:
        raise RollbackTargetInvalid(
            f"{strategy_key!r} cannot be the rollback target: {exc}") from exc


def _restore_instrument_authority(session, instrument_key: str,
                                  strategy_key: str | None) -> None:
    """Write the named target onto the instrument row, or clear it.

    Clearing means "the platform default applies", which is what the instrument row means
    when it is NULL everywhere else in this codebase. It is chosen explicitly by passing
    `None`, never arrived at by omission.
    """
    row = session.get(InstrumentState, instrument_key)
    if row is None:
        if strategy_key is None:
            return
        row = InstrumentState(instrument_key=instrument_key)
        session.add(row)
    row.strategy_key = strategy_key
    session.flush()


__all__ = [
    "AUTHORITY", "LIVE_STATES", "MODE", "PAPER_ACTIVE", "PAUSED", "RETIRED", "SOURCE",
    "STAGED", "STATES", "BindingUnverifiable", "EvidenceUnverified", "IllegalTransition",
    "NotAdmissible", "PaperAuthorityError", "PaperBinding", "RevisionConflict",
    "RollbackTargetInvalid", "activate", "active_bindings", "adapter_for",
    "listing", "pause", "register_active_adapters", "resume",
    "retire", "stage", "strategy_key_for", "verified_decision",
]
