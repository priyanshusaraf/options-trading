"""Required-owner persistence boundary for durable backtest evidence."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
import hashlib
import json
import uuid
from typing import Any, Mapping

from sqlalchemy import and_, func, or_, select, update

from app.db.concurrency import caller_owned_savepoint, locked_rows
from app.db.models import BacktestResult, BacktestRun, StrategyAdmission


class AdmissionRequired(RuntimeError):
    """Stable refusal for a backtest that lacks a current causal receipt."""

    def __init__(self, code: str = "ADMISSION_REQUIRED") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class VerifiedBacktestAdmission:
    """Current owner-local receipt and its only executable graph authority."""

    admission_address: str
    artifact: Any
    graph: dict[str, Any]
    strategy: Any
    strategy_key: str
    strategy_version: str
    graph_address: str | None
    attribution_state: str
    phase4_binding: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class VerifiedV2LifecycleAdmission:
    """Exact current Phase 4 authority exposed only to P5's lifecycle seam."""

    admission_address: str
    artifact: Any
    strategy_key: str
    strategy_version: str
    graph_address: str
    attribution_state: str
    phase4_binding: Mapping[str, Any]


def _reconstruct_phase4_artifact(document: Mapping[str, Any], *, owner_id: str,
                                 registry: Any) -> Any:
    """Compatibility name for the shared durable Phase 4 verifier."""
    from app.strategy.admission import reconstruct_phase4_artifact

    return reconstruct_phase4_artifact(document, owner_id=owner_id, registry=registry)


def _admission_refusal(code: str = "RECEIPT_STALE") -> AdmissionRequired:
    return AdmissionRequired(code)


def _load_result_attribution_artifact(session, *, owner_id: str,
                                      admission_address: str):
    """Reconstruct the durable receipt/graph tuple at the fenced result write.

    Full runtime/parity admission is performed before worker/provider execution.
    Persistence needs the immutable receipt and canonical GraphVersion facts again,
    not another evaluation of the strategy over the parity corpus per ten-row batch.
    """
    from app.core import strategy_admissions
    from app.db.models import GraphVersion
    from app.ir.hashing import canonical_json, content_address
    from app.strategy.admission import artifact_from_dict

    receipt = strategy_admissions.get(
        session, owner_id=owner_id, admission_address=admission_address)
    if receipt is None:
        raise _admission_refusal()
    try:
        document = json.loads(receipt.artifact_json)
        artifact = artifact_from_dict(document)
        strategy_admissions.require_current(session, artifact)
        version = session.get(
            GraphVersion,
            (owner_id, artifact.graph_identifier, artifact.graph_version))
        if (version is None or version.content_address != artifact.graph_address
                or (version.admission_address is not None
                    and version.admission_address != admission_address)
                or artifact.owner_id != owner_id
                or artifact.admission_address != admission_address):
            raise _admission_refusal("GRAPH_ATTRIBUTION_MISMATCH")
        graph = json.loads(version.artifact_json)
        if (canonical_json(graph) != version.artifact_json
                or content_address(graph) != artifact.graph_address):
            raise _admission_refusal("GRAPH_ATTRIBUTION_MISMATCH")
        return artifact
    except AdmissionRequired:
        raise
    except (TypeError, ValueError, json.JSONDecodeError,
            strategy_admissions.AdmissionPersistenceError) as exc:
        raise _admission_refusal("GRAPH_ATTRIBUTION_MISMATCH") from exc


def load_verified_v2_lifecycle_admission(
        session, *, owner_id: str, admission_address: str | None,
        authority_context: Any, research_session: Any,
        at_time: dt.datetime) -> VerifiedV2LifecycleAdmission:
    """Run the sole persisted Phase 4 authority chain and return immutable facts.

    The generic backtest loader calls this function and still terminates at
    ``V2_RUNTIME_UNAVAILABLE``.  Only ``app.backtest.v2_lifecycle`` may consume
    the successful value, and only with an explicitly supplied test executor.
    """
    from app.backtest.reclaim_authority import ReclaimAuthorityContext
    from app.core import strategy_admissions
    from app.ir.registry import PlatformRegistry
    from app.ir.v2_graph_versions import PHASE4_SCHEME
    from sqlalchemy.orm import Session

    if not isinstance(admission_address, str) or not admission_address:
        raise _admission_refusal("ADMISSION_REQUIRED")
    if (not isinstance(authority_context, ReclaimAuthorityContext)
            or not isinstance(authority_context.registry, PlatformRegistry)
            or not callable(authority_context.research_sessionmaker)
            or not isinstance(research_session, Session)
            or not isinstance(at_time, dt.datetime)
            or at_time.tzinfo is None
            or at_time.utcoffset() is None):
        raise _admission_refusal("PHASE4_CONTEXT_REQUIRED")
    receipt = strategy_admissions.get(
        session, owner_id=owner_id, admission_address=admission_address)
    if receipt is None:
        raise _admission_refusal()
    try:
        artifact = strategy_admissions.load_current_phase4_artifact(
            session, owner_id=owner_id, admission_address=admission_address,
            registry=authority_context.registry, research_session=research_session,
        )
        strategy_admissions.require_phase4_current(
            session, artifact, research_session=research_session,
            plan=artifact.plan, at_time=at_time)
        binding = artifact.document.get("phase4_data_binding")
        if not isinstance(binding, Mapping):
            raise _admission_refusal("ARTEFACT_MISMATCH")
        return VerifiedV2LifecycleAdmission(
            admission_address=admission_address,
            artifact=artifact,
            strategy_key=f"ir.{artifact.graph_identifier}",
            strategy_version=str(artifact.graph_version),
            graph_address=artifact.graph_address,
            attribution_state="VERIFIED_GRAPH",
            phase4_binding=binding,
        )
    except AdmissionRequired:
        raise
    except (TypeError, ValueError, json.JSONDecodeError,
            strategy_admissions.AdmissionPersistenceError) as exc:
        raise _admission_refusal() from exc


def load_verified_admission(session, *, owner_id: str,
                            admission_address: str | None,
                            authority_context: Any | None = None,
                            research_session: Any | None = None,
                            at_time: dt.datetime | None = None,
                            registry: Any | None = None) -> VerifiedBacktestAdmission:
    """Load and freshly verify one exact owner-local graph receipt.

    A durable address by itself is never authority.  This reconstructs canonical
    receipt bytes, binds them to the immutable graph version bytes, and verifies
    them against the current platform registry before a backtest can obtain a
    strategy or touch a provider.  A Phase 4 receipt requires explicit context,
    a lifecycle-owned research Session, and an aware cutoff; its plan comes from
    the exact persisted receipt and current registry.
    """
    from app.core import strategy_admissions
    from app.ir.v2_graph_versions import PHASE4_SCHEME, V2_RUNTIME_UNAVAILABLE
    from app.strategy.admission import (
        AdmissionRefused, HandwrittenAdapterInput, IRGraphAdmissionInput,
        artifact_from_dict,
        verify_admission,
    )

    if not isinstance(admission_address, str) or not admission_address:
        raise _admission_refusal("ADMISSION_REQUIRED")
    receipt = strategy_admissions.get(
        session, owner_id=owner_id, admission_address=admission_address)
    if receipt is None:
        raise _admission_refusal()
    try:
        document = json.loads(receipt.artifact_json)
        if not isinstance(document, dict):
            raise _admission_refusal("RECEIPT_STALE")
        if document.get("scheme") == PHASE4_SCHEME:
            load_verified_v2_lifecycle_admission(
                session, owner_id=owner_id, admission_address=admission_address,
                authority_context=authority_context, research_session=research_session,
                at_time=at_time)
            raise _admission_refusal(V2_RUNTIME_UNAVAILABLE)

        # The v1 seam retains its established optional caller registry.  Phase
        # 4 never reaches this import or its process-global fallback.
        from app.ir.library import REGISTRY
        active_registry = REGISTRY if registry is None else registry
        artifact = artifact_from_dict(document)
        strategy_admissions.require_current(session, artifact)
        from app.db.models import GraphVersion
        from app.ir.hashing import canonical_json, content_address
        version = session.get(
            GraphVersion,
            (owner_id, artifact.graph_identifier, artifact.graph_version),
        )
        if (version is None
                or (version.admission_address is not None
                    and version.admission_address != admission_address)
                or version.content_address != artifact.graph_address):
            raise _admission_refusal("ARTEFACT_MISMATCH")
        graph = json.loads(version.artifact_json)
        if canonical_json(graph) != version.artifact_json \
                or content_address(graph) != artifact.graph_address:
            raise _admission_refusal("ARTEFACT_MISMATCH")
        if artifact.owner_id != owner_id or artifact.admission_address != admission_address:
            raise _admission_refusal("ARTEFACT_MISMATCH")
        equivalent_ir = IRGraphAdmissionInput(graph=graph, parameters={}, risk_model=None)
        if artifact.source == "handwritten_adapter":
            from scripts.backfill_strategy_admissions import expanding_z_adapter_input
            source = expanding_z_adapter_input(
                strategy_key=artifact.source_evidence.strategy_key,
                strategy_version=artifact.source_evidence.strategy_version,
                graph=graph,
            )
            if not isinstance(source, HandwrittenAdapterInput):
                raise _admission_refusal("ARTEFACT_MISMATCH")
        else:
            source = equivalent_ir
        verify_admission(
            artifact=artifact, owner_id=owner_id,
            source_input=source, registry=active_registry)
        from app.strategy.ir_adapter import IRGraphStrategy
        strategy = IRGraphStrategy(
            graph, (active_registry.library, active_registry.implementations))
    except AdmissionRequired:
        raise
    except AdmissionRefused as exc:
        raise _admission_refusal(exc.code.value) from exc
    except (TypeError, ValueError, json.JSONDecodeError,
            strategy_admissions.AdmissionPersistenceError) as exc:
        raise _admission_refusal() from exc
    if artifact.source == "ir_graph":
        strategy_key = f"ir.{artifact.graph_identifier}"
        strategy_version = str(artifact.graph_version)
        graph_address = artifact.graph_address
        attribution_state = "VERIFIED_GRAPH"
    else:
        strategy_key = artifact.source_evidence.strategy_key
        strategy_version = artifact.source_evidence.strategy_version
        graph_address = None
        attribution_state = "NON_GRAPH"
    return VerifiedBacktestAdmission(
        admission_address, artifact, graph, strategy,
        strategy_key, strategy_version, graph_address, attribution_state)


def _verify_enqueue_admission(session, *, owner_id: str,
                              admission_address: str | None) -> VerifiedBacktestAdmission:
    """Named enqueue seam kept separate so the authority mutation is isolated."""
    return load_verified_admission(
        session, owner_id=owner_id, admission_address=admission_address)


def _clock(now: dt.datetime | None = None) -> dt.datetime:
    """SQLite stores naive UTC timestamps; normalize injected clocks likewise."""
    value = now or dt.datetime.now(dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def enqueue_run(session, *, owner_id: str, scope: str, intervals: str,
                capital: float, total: int, admission_address: str | None,
                now: dt.datetime | None = None,
                **values) -> BacktestRun:
    """Create durable pending work before any provider read or worker launch."""
    admitted = _verify_enqueue_admission(
        session, owner_id=owner_id, admission_address=admission_address)
    if admitted is not None and admitted.phase4_binding is not None:
        try:
            descriptor = json.loads(values.get("request_json", ""))
        except (TypeError, json.JSONDecodeError) as exc:
            raise _admission_refusal("ARTEFACT_MISMATCH") from exc
        if not isinstance(descriptor, dict):
            raise _admission_refusal("ARTEFACT_MISMATCH")
        supplied = descriptor.get("_phase4_binding")
        canonical = dict(admitted.phase4_binding)
        canonical["declaration_addresses"] = list(canonical["declaration_addresses"])
        if supplied is not None and supplied != canonical:
            raise _admission_refusal("ARTEFACT_MISMATCH")
        descriptor["_phase4_binding"] = canonical
        values["request_json"] = json.dumps(
            descriptor, sort_keys=True, separators=(",", ":"))
    queued_at = _clock(now)
    run = BacktestRun(owner_id=owner_id, scope=scope, intervals=intervals,
                      capital=capital, total=total, status="pending",
                      queued_at=queued_at, admission_address=admission_address, **values)
    session.add(run)
    session.flush()
    from app.events.producers import append_execution_change
    append_execution_change(
        session, owner_id=owner_id, broker_account_id=None,
        aggregate_type="backtest_run", aggregate_id=str(run.id),
        event_type="execution.backtest.changed", projection="backtest_runs",
        producer_key=f"backtest:{owner_id}:{run.id}:pending",
        facts={"state": "pending"},
    )
    return run


def create_run(session, *, owner_id: str, scope: str, intervals: str,
               capital: float, total: int, **values) -> BacktestRun:
    run = BacktestRun(owner_id=owner_id, scope=scope, intervals=intervals,
                      capital=capital, total=total, **values)
    session.add(run)
    session.flush()
    return run


def _claimable(now: dt.datetime):
    return or_(BacktestRun.status == "pending", and_(
        BacktestRun.status == "running", BacktestRun.claim_expires_at.is_not(None),
        BacktestRun.claim_expires_at <= now))


def claim_run(session, *, owner_id: str, run_id: int, claimed_by: str,
              now: dt.datetime | None = None, lease_seconds: int = 30) -> BacktestRun | None:
    """Atomically take pending/expired work and fence its former writer."""
    moment = _clock(now)
    token = uuid.uuid4().hex
    expires = moment + dt.timedelta(seconds=max(1, int(lease_seconds)))
    result = session.execute(update(BacktestRun).where(
        BacktestRun.owner_id == owner_id, BacktestRun.id == run_id,
        BacktestRun.cancel_requested_at.is_(None), _claimable(moment)).values(
            status="running", claim_token=token, claimed_by=claimed_by,
            claim_expires_at=expires, heartbeat_at=moment,
            started_at=func.coalesce(BacktestRun.started_at, moment),
            attempt_count=BacktestRun.attempt_count + 1))
    if result.rowcount != 1:
        return None
    # An expired running row is a genuine takeover; a pending row is its first
    # admission.  This durable counter is derived from attempt_count in metrics.
    return get_run(session, owner_id=owner_id, run_id=run_id)


def claim_next_run(session, *, owner_id: str, claimed_by: str,
                   now: dt.datetime | None = None, lease_seconds: int = 30) -> BacktestRun | None:
    """Find a candidate then use ``claim_run`` as the sole race authority."""
    moment = _clock(now)
    statement = select(BacktestRun.id).where(
        BacktestRun.owner_id == owner_id, BacktestRun.cancel_requested_at.is_(None),
        _claimable(moment)).order_by(BacktestRun.queued_at, BacktestRun.id).limit(1)
    candidate = session.scalar(locked_rows(statement, session, skip_locked=True))
    if candidate is None:
        return None
    return claim_run(session, owner_id=owner_id, run_id=int(candidate),
                     claimed_by=claimed_by, now=moment, lease_seconds=lease_seconds)


@dataclass(frozen=True)
class FrozenReclaimRun:
    """Immutable scalar facts from one locked owner reclaim enumeration."""
    id: int
    owner_id: str
    status: str
    admission_address: str | None
    cancel_requested_at: dt.datetime | None
    claim_token: str | None
    claim_expires_at: dt.datetime | None


@dataclass(frozen=True)
class FrozenClaimedRun:
    """Committed scalar claim facts safe after the claiming Session closes."""

    id: int
    owner_id: str
    attempt_count: int
    queued_at: dt.datetime | None
    claim_token: str
    request_json: str
    total: int
    requested_workers: int
    capital: float
    admission_address: str | None


def _freeze_reclaim_run(row) -> FrozenReclaimRun:
    return FrozenReclaimRun(row.id, row.owner_id, row.status, row.admission_address,
                            row.cancel_requested_at, row.claim_token,
                            row.claim_expires_at)


def freeze_claimed_run(row: BacktestRun) -> FrozenClaimedRun:
    """Freeze one successful claim before commit expires its ORM attributes."""
    if (row.status != "running" or not isinstance(row.claim_token, str)
            or not row.claim_token):
        raise ValueError("cannot freeze a row without one active claim")
    return FrozenClaimedRun(
        row.id, row.owner_id, row.attempt_count, row.queued_at,
        row.claim_token, row.request_json, row.total, row.requested_workers,
        row.capital, row.admission_address)


def snapshot_claimable_runs(session, *, owner_id: str,
                            now: dt.datetime | None = None) -> list[FrozenReclaimRun]:
    """Return the closed owner-local mutation set under the caller's lock."""
    moment = _clock(now)
    statement = select(BacktestRun).where(
        BacktestRun.owner_id == owner_id,
        or_(and_(BacktestRun.status == "pending",
                 BacktestRun.cancel_requested_at.is_(None)),
            and_(BacktestRun.status == "running",
                 BacktestRun.claim_token.is_not(None),
                 BacktestRun.claim_expires_at.is_not(None),
                 BacktestRun.claim_expires_at <= moment),
            and_(BacktestRun.status == "running",
                 BacktestRun.claim_token.is_(None),
                 BacktestRun.claim_expires_at.is_(None)))).order_by(
            BacktestRun.queued_at, BacktestRun.id)
    return [_freeze_reclaim_run(row) for row in session.scalars(locked_rows(statement, session))]


def _frozen_run_predicates(frozen: FrozenReclaimRun) -> list[Any]:
    """Bind a reclaim transition to exactly the row observed in its snapshot."""
    def exact(column, value):
        return column.is_(None) if value is None else column == value
    return [BacktestRun.owner_id == frozen.owner_id, BacktestRun.id == frozen.id,
            BacktestRun.status == frozen.status,
            exact(BacktestRun.admission_address, frozen.admission_address),
            exact(BacktestRun.cancel_requested_at, frozen.cancel_requested_at),
            exact(BacktestRun.claim_token, frozen.claim_token),
            exact(BacktestRun.claim_expires_at, frozen.claim_expires_at)]


def reconcile_frozen_run(session, *, frozen: FrozenReclaimRun,
                         now: dt.datetime | None = None) -> tuple[bool, FrozenReclaimRun | None]:
    """Reconcile only one locked legacy ID and report a transition race."""
    moment = _clock(now)
    predicates = _frozen_run_predicates(frozen)
    if (frozen.status == "running" and frozen.claim_token is None
            and frozen.claim_expires_at is None):
        result = session.execute(update(BacktestRun).where(*predicates).values(
            status="error", completed_at=moment,
            done=select(func.count()).select_from(BacktestResult).where(
                BacktestResult.owner_id == BacktestRun.owner_id,
                BacktestResult.run_id == BacktestRun.id).scalar_subquery(),
            note="interrupted legacy run without a durable worker claim"))
        return result.rowcount == 1, None
    if (frozen.status == "running" and frozen.claim_token is not None
            and frozen.claim_expires_at is not None
            and frozen.claim_expires_at <= moment):
        cancelled = frozen.cancel_requested_at is not None
        values = {
            "status": "cancelled" if cancelled else "pending",
            "claim_token": None,
            "claimed_by": None,
            "claim_expires_at": None,
            "heartbeat_at": None,
            "note": ("cancelled: worker claim expired after cancellation request; durable progress retained"
                     if cancelled else "interrupted: expired worker claim; durable progress retained"),
        }
        # Reconciliation must leave the original completion time alone unless a
        # cancellation makes this the terminal transition.
        if cancelled:
            values["completed_at"] = moment
        result = session.execute(update(BacktestRun).where(*predicates).values(**values))
        if result.rowcount != 1:
            return False, None
        if cancelled:
            return True, None
        # The conditional update itself is the transition authority.  Construct
        # its known scalar successor without selecting candidate state again.
        return True, replace(frozen, status="pending", claim_token=None,
                             claim_expires_at=None)
    return True, frozen


def claim_frozen_run(session, *, frozen: FrozenReclaimRun, claimed_by: str,
                     now: dt.datetime | None = None,
                     lease_seconds: int = 30) -> BacktestRun | None:
    """Claim an enumerated legacy row only if every frozen predicate survives."""
    moment = _clock(now)
    token = uuid.uuid4().hex
    expires = moment + dt.timedelta(seconds=max(1, int(lease_seconds)))
    predicates = [*_frozen_run_predicates(frozen),
                  BacktestRun.cancel_requested_at.is_(None), _claimable(moment)]
    result = session.execute(update(BacktestRun).where(*predicates).values(
        status="running", claim_token=token, claimed_by=claimed_by,
        claim_expires_at=expires, heartbeat_at=moment,
        started_at=func.coalesce(BacktestRun.started_at, moment),
        attempt_count=BacktestRun.attempt_count + 1))
    if result.rowcount != 1:
        return None
    return get_run(session, owner_id=frozen.owner_id, run_id=frozen.id)


def reclaim_admission_format(session, *, owner_id: str,
                             admission_address: str | None) -> int | None:
    """Classify a frozen receipt; only exact persisted versions are actionable."""
    if not admission_address:
        return None
    artifact_json = session.scalar(select(StrategyAdmission.artifact_json).where(
        StrategyAdmission.owner_id == owner_id,
        StrategyAdmission.admission_address == admission_address))
    if not isinstance(artifact_json, str):
        return None
    try:
        document = json.loads(artifact_json)
    except (TypeError, ValueError):
        return None
    if not isinstance(document, dict):
        return None
    from app.ir.v2_graph_versions import PHASE4_SCHEME
    if document.get("scheme") == PHASE4_SCHEME:
        return 2
    # V1's canonical durable receipt has the required graph/artifact facts but
    # no additive Phase 4 scheme. Parsing it is stricter than treating a null
    # database column or unknown receipt as legacy work.
    try:
        from app.strategy.admission import AdmissionRefused, artifact_from_dict
        artifact_from_dict(document)
    except (TypeError, ValueError, KeyError, AdmissionRefused):
        return None
    return 1


def _active_claim(owner_id: str, run_id: int, token: str, now: dt.datetime,
                  *, allow_cancel: bool = False):
    clauses = [BacktestRun.owner_id == owner_id, BacktestRun.id == run_id,
               BacktestRun.status == "running", BacktestRun.claim_token == token,
               BacktestRun.claim_expires_at.is_not(None), BacktestRun.claim_expires_at > now]
    if not allow_cancel:
        clauses.append(BacktestRun.cancel_requested_at.is_(None))
    return and_(*clauses)


def heartbeat_claim(session, *, owner_id: str, run_id: int, claim_token: str,
                    now: dt.datetime | None = None, lease_seconds: int = 30) -> bool:
    moment = _clock(now)
    result = session.execute(update(BacktestRun).where(
        _active_claim(owner_id, run_id, claim_token, moment)).values(
            heartbeat_at=moment,
            claim_expires_at=moment + dt.timedelta(seconds=max(1, int(lease_seconds)))))
    return result.rowcount == 1


def release_claim(session, *, owner_id: str, run_id: int, claim_token: str,
                  note: str, now: dt.datetime | None = None) -> bool:
    """Return a current claim to the queue without pretending the run failed.

    Used when a restart cannot obtain the immutable execution artifact named by a
    descriptor.  The same fence as all writers prevents an old dispatcher from
    releasing a newer worker's claim.
    """
    moment = _clock(now)
    result = session.execute(update(BacktestRun).where(
        _active_claim(owner_id, run_id, claim_token, moment)).values(
            status="pending", claim_token=None, claimed_by=None,
            claim_expires_at=None, heartbeat_at=None, queued_at=moment,
            note=note[:400]))
    return result.rowcount == 1


def get_run(session, *, owner_id: str, run_id: int) -> BacktestRun | None:
    return session.scalar(select(BacktestRun).where(
        BacktestRun.owner_id == owner_id, BacktestRun.id == run_id))


def latest_run(session, *, owner_id: str) -> BacktestRun | None:
    return session.scalar(select(BacktestRun).where(
        BacktestRun.owner_id == owner_id).order_by(BacktestRun.id.desc()).limit(1))


def list_runs_with_counts(session, *, owner_id: str, limit: int) -> list[tuple[BacktestRun, int]]:
    counts = (select(BacktestResult.run_id.label("run_id"), func.count().label("result_count"))
              .where(BacktestResult.owner_id == owner_id, BacktestResult.error == "")
              .group_by(BacktestResult.run_id).subquery())
    query = (select(BacktestRun, func.coalesce(counts.c.result_count, 0))
             .outerjoin(counts, counts.c.run_id == BacktestRun.id)
             .where(BacktestRun.owner_id == owner_id)
             .order_by(BacktestRun.id.desc()).limit(limit))
    return [(run, int(count)) for run, count in session.execute(query)]


def list_results(session, *, owner_id: str, run_id: int, limit: int | None = None,
                 offset: int = 0, order_by=None) -> list[BacktestResult]:
    query = select(BacktestResult).where(BacktestResult.owner_id == owner_id,
                                         BacktestResult.run_id == run_id)
    if order_by is not None:
        query = query.order_by(order_by)
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    return list(session.scalars(query))


def result_count(session, *, owner_id: str, run_id: int, successful_only: bool = False) -> int:
    query = select(func.count()).select_from(BacktestResult).where(
        BacktestResult.owner_id == owner_id, BacktestResult.run_id == run_id)
    if successful_only:
        query = query.where(BacktestResult.error == "")
    return int(session.scalar(query) or 0)


def result_detail(session, *, owner_id: str, run_id: int, instrument_key: str,
                  interval: str, strategy_key: str | None = None) -> BacktestResult | None:
    query = select(BacktestResult).where(
        BacktestResult.owner_id == owner_id, BacktestResult.run_id == run_id,
        BacktestResult.instrument_key == instrument_key, BacktestResult.interval == interval)
    if strategy_key:
        query = query.where(BacktestResult.strategy_key == strategy_key)
    return session.scalar(query)


def filtered_results(session, *, owner_id: str, run_id: int, interval: str | None,
                     strategy_key: str | None, min_win_rate: float,
                     min_profit_factor: float, max_drawdown: float, min_return: float,
                     min_trades: int, sort_column, descending: bool, limit: int,
                     offset: int) -> list[BacktestResult]:
    """Apply the public grid filters in SQL; never load a run to filter in Python."""
    query = select(BacktestResult).where(
        BacktestResult.owner_id == owner_id, BacktestResult.run_id == run_id,
        BacktestResult.error == "", BacktestResult.trades >= min_trades,
        BacktestResult.win_rate >= min_win_rate,
        func.coalesce(BacktestResult.profit_factor, 1e9) >= min_profit_factor,
        BacktestResult.max_drawdown_pct <= max_drawdown,
        BacktestResult.return_pct >= min_return)
    if interval:
        query = query.where(BacktestResult.interval == interval)
    if strategy_key:
        query = query.where(BacktestResult.strategy_key == strategy_key)
    direction = sort_column.desc() if descending else sort_column.asc()
    return list(session.scalars(query.order_by(direction, BacktestResult.id)
                                .offset(offset).limit(limit)))


def filtered_counts(session, *, owner_id: str, run_id: int, interval: str | None,
                       strategy_key: str | None, min_win_rate: float,
                       min_profit_factor: float, max_drawdown: float, min_return: float,
                       min_trades: int) -> tuple[int, int, int, int]:
    base = [BacktestResult.owner_id == owner_id, BacktestResult.run_id == run_id]
    if interval:
        base.append(BacktestResult.interval == interval)
    if strategy_key:
        base.append(BacktestResult.strategy_key == strategy_key)
    errored = int(session.scalar(select(func.count()).select_from(BacktestResult).where(
        *base, BacktestResult.error != "")) or 0)
    low = int(session.scalar(select(func.count()).select_from(BacktestResult).where(
        *base, BacktestResult.error == "", BacktestResult.trades < min_trades)) or 0)
    valid = [BacktestResult.error == "", BacktestResult.trades >= min_trades,
             BacktestResult.win_rate >= min_win_rate,
             func.coalesce(BacktestResult.profit_factor, 1e9) >= min_profit_factor,
             BacktestResult.max_drawdown_pct <= max_drawdown,
             BacktestResult.return_pct >= min_return]
    total_eligible = int(session.scalar(select(func.count()).select_from(BacktestResult).where(
        *base, BacktestResult.error == "", BacktestResult.trades >= min_trades)) or 0)
    visible = int(session.scalar(select(func.count()).select_from(BacktestResult).where(*base, *valid)) or 0)
    return visible, errored, low, total_eligible - visible


def iter_successful_results(*, owner_id: str, run_id: int, batch_size: int):
    """Fresh bounded sessions for CSV streaming; no transaction retains a whole run."""
    from app.db.session import SessionLocal
    after_id = 0
    while True:
        with SessionLocal() as session:
            batch = list(session.scalars(select(BacktestResult).where(
                BacktestResult.owner_id == owner_id, BacktestResult.run_id == run_id,
                BacktestResult.error == "", BacktestResult.id > after_id).order_by(
                    BacktestResult.id).limit(batch_size)))
        if not batch:
            return
        for row in batch:
            yield row
        after_id = batch[-1].id


def append_result_batch(session, *, owner_id: str, run_id: int,
                        values: list[dict]) -> None:
    """Removed unfenced write seam retained only as an explicit refusal.

    Results can be durable only through ``append_claimed_result_batch``.  Keeping
    a callable non-fenced writer would let a future worker bypass the lease.
    """
    raise RuntimeError("backtest result persistence requires a fenced claim token")


def _cell_key(value: dict) -> str:
    """Stable within-run identity for a simulated strategy cell.

    Run ids are already owner-scoped by the composite FK.  Include strategy
    identity here so adding a second strategy never aliases its result with the
    same instrument/interval pair.  Values originate from internal simulation,
    but reject malformed ones rather than silently creating an unresumable row.
    """
    parts = (value.get("instrument_key"), value.get("interval"),
             value.get("strategy_key"), value.get("strategy_version"),
             value.get("graph_address") or "", value.get("attribution_state"))
    if not all(isinstance(part, str) for part in parts) or not all(parts[index] for index in (0, 1, 2, 3, 5)):
        raise ValueError("backtest result lacks a stable cell identity")
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def append_claimed_result_batch(session, *, owner_id: str, run_id: int,
                                claim_token: str, values: list[dict],
                                now: dt.datetime | None = None,
                                lease_seconds: int = 30,
                                verified_v2_admission: VerifiedV2LifecycleAdmission | None = None) -> bool:
    """Insert a bounded result batch and its progress under one fenced savepoint.

    A false result has no side effect, including no pending ORM rows that a caller
    might accidentally commit after a lost lease.
    """
    moment = _clock(now)
    with caller_owned_savepoint(session, scope="backtest_claimed_result_batch"):
        # Check before inserting so a cancellation/replacement cannot make a
        # stale process create rows. The same predicate is repeated after flush
        # to fence a takeover that wins while this worker computes its count.
        if session.execute(update(BacktestRun).where(
            _active_claim(owner_id, run_id, claim_token, moment)).values(
                heartbeat_at=moment,
                claim_expires_at=moment + dt.timedelta(seconds=max(1, int(lease_seconds))))).rowcount != 1:
            return False
        # A result is durable evidence for this exact run, so it may not borrow
        # a receipt from another run (or omit its receipt) while holding a valid
        # claim.  This lookup and the following inserts share the same fenced
        # savepoint as the lease update; a mismatch rolls back the whole batch.
        expected_admission = session.scalar(select(BacktestRun.admission_address).where(
            BacktestRun.owner_id == owner_id, BacktestRun.id == run_id))
        if not isinstance(expected_admission, str) or not expected_admission:
            raise AdmissionRequired("ADMISSION_REQUIRED")
        if any(value.get("admission_address") != expected_admission for value in values):
            raise AdmissionRequired("ARTEFACT_MISMATCH")
        from app.strategy.admission import (
            matches_execution_identity, require_attribution_tuple,
        )
        submitted_tuples = set()
        for value in values:
            require_attribution_tuple(
                strategy_key=value.get("strategy_key"),
                strategy_version=value.get("strategy_version"),
                graph_address=value.get("graph_address"),
                admission_address=value.get("admission_address"),
                attribution_state=value.get("attribution_state"))
            submitted_tuples.add((
                value.get("strategy_key"), value.get("strategy_version"),
                value.get("graph_address"), value.get("attribution_state")))
        if submitted_tuples:
            if verified_v2_admission is not None:
                if (not isinstance(verified_v2_admission, VerifiedV2LifecycleAdmission)
                        or verified_v2_admission.artifact.owner_id != owner_id
                        or verified_v2_admission.admission_address != expected_admission):
                    raise AdmissionRequired("GRAPH_ATTRIBUTION_MISMATCH")
                expected_tuple = (
                    verified_v2_admission.strategy_key,
                    verified_v2_admission.strategy_version,
                    verified_v2_admission.graph_address,
                    verified_v2_admission.attribution_state,
                )
                if any(value != expected_tuple for value in submitted_tuples):
                    raise AdmissionRequired("GRAPH_ATTRIBUTION_MISMATCH")
            else:
                artifact = _load_result_attribution_artifact(
                    session, owner_id=owner_id, admission_address=expected_admission)
                if any(not matches_execution_identity(
                        artifact, strategy_key=key, strategy_version=version,
                        graph_address=address, attribution_state=state)
                        for key, version, address, state in submitted_tuples):
                    raise AdmissionRequired("GRAPH_ATTRIBUTION_MISMATCH")
        # Resume/replacement re-computes cells after a process death.  The first
        # claimant may already have committed part of a batch, so append only
        # identities not yet durable.  The DB constraint makes this invariant
        # survive mistakes in future callers as well.
        unique: dict[str, dict] = {}
        for value in values:
            payload = dict(value)
            key = _cell_key(payload)
            payload["cell_key"] = key
            unique.setdefault(key, payload)
        existing = set(session.scalars(select(BacktestResult.cell_key).where(
            BacktestResult.owner_id == owner_id, BacktestResult.run_id == run_id,
            BacktestResult.cell_key.in_(tuple(unique))))) if unique else set()
        for key, value in unique.items():
            if key not in existing:
                session.add(BacktestResult(owner_id=owner_id, run_id=run_id, **value))
        session.flush()
        done = durable_result_count(session, owner_id=owner_id, run_id=run_id)
        if session.execute(update(BacktestRun).where(
            _active_claim(owner_id, run_id, claim_token, moment)).values(done=done)).rowcount != 1:
            raise RuntimeError("backtest claim changed while persisting batch")
    return True


def durable_result_count(session, *, owner_id: str, run_id: int) -> int:
    return int(session.scalar(select(func.count()).select_from(BacktestResult).where(
        BacktestResult.owner_id == owner_id, BacktestResult.run_id == run_id)) or 0)


def update_run(session, *, owner_id: str, run_id: int, status: str = "",
               note: str = "") -> BacktestRun | None:
    """Removed unfenced run mutation seam retained only as a refusal."""
    raise RuntimeError("backtest run mutation requires a fenced claim token")


def complete_claim(session, *, owner_id: str, run_id: int, claim_token: str,
                   status: str, note: str = "", now: dt.datetime | None = None) -> bool:
    """Only the current, unexpired claimant can make a run terminal."""
    if status not in {"done", "error", "cancelled"}:
        raise ValueError("invalid terminal backtest status")
    moment = _clock(now)
    predicate = _active_claim(owner_id, run_id, claim_token, moment,
                              allow_cancel=status == "cancelled")
    if status == "cancelled":
        predicate = and_(predicate, BacktestRun.cancel_requested_at.is_not(None))
    with caller_owned_savepoint(session, scope="backtest_complete_claim"):
        done = durable_result_count(session, owner_id=owner_id, run_id=run_id)
        result = session.execute(update(BacktestRun).where(predicate).values(
            status=status, done=done, note=note[:400] if note else BacktestRun.note,
            completed_at=moment, heartbeat_at=moment))
        if result.rowcount != 1:
            return False
        from app.events.producers import append_execution_change
        append_execution_change(
            session, owner_id=owner_id, broker_account_id=None,
            aggregate_type="backtest_run", aggregate_id=str(run_id),
            event_type="execution.backtest.changed", projection="backtest_runs",
            producer_key=f"backtest:{owner_id}:{run_id}:terminal:{status}",
            facts={"state": status},
        )
    return True


def request_cancel(session, *, owner_id: str, run_id: int,
                   now: dt.datetime | None = None) -> bool:
    """Cancel pending work immediately; ask an active claimant to stop safely."""
    moment = _clock(now)
    pending = session.execute(update(BacktestRun).where(
        BacktestRun.owner_id == owner_id, BacktestRun.id == run_id,
        BacktestRun.status == "pending", BacktestRun.cancel_requested_at.is_(None)).values(
            status="cancelled", cancel_requested_at=moment, completed_at=moment,
            done=select(func.count()).select_from(BacktestResult).where(
                BacktestResult.owner_id == BacktestRun.owner_id,
                BacktestResult.run_id == BacktestRun.id).scalar_subquery()))
    if pending.rowcount == 1:
        from app.events.producers import append_execution_change
        append_execution_change(
            session, owner_id=owner_id, broker_account_id=None,
            aggregate_type="backtest_run", aggregate_id=str(run_id),
            event_type="execution.backtest.changed", projection="backtest_runs",
            producer_key=f"backtest:{owner_id}:{run_id}:cancelled",
            facts={"state": "cancelled"},
        )
        return True
    result = session.execute(update(BacktestRun).where(
        BacktestRun.owner_id == owner_id, BacktestRun.id == run_id,
        BacktestRun.status == "running",
        BacktestRun.cancel_requested_at.is_(None)).values(cancel_requested_at=moment))
    if result.rowcount == 1:
        from app.events.producers import append_execution_change
        append_execution_change(
            session, owner_id=owner_id, broker_account_id=None,
            aggregate_type="backtest_run", aggregate_id=str(run_id),
            event_type="execution.backtest.changed", projection="backtest_runs",
            producer_key=f"backtest:{owner_id}:{run_id}:cancel_requested",
            facts={"state": "cancel_requested"},
        )
        return True
    return False


def is_cancel_requested(session, *, owner_id: str, run_id: int,
                        claim_token: str, now: dt.datetime | None = None) -> bool:
    moment = _clock(now)
    return session.scalar(select(BacktestRun.id).where(
        _active_claim(owner_id, run_id, claim_token, moment, allow_cancel=True),
        BacktestRun.cancel_requested_at.is_not(None)).limit(1)) is not None
