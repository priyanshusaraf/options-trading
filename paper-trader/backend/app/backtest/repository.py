"""Required-owner persistence boundary for durable backtest evidence."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import and_, func, or_, select, update

from app.db.models import BacktestResult, BacktestRun


def _clock(now: dt.datetime | None = None) -> dt.datetime:
    """SQLite stores naive UTC timestamps; normalize injected clocks likewise."""
    value = now or dt.datetime.now(dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def enqueue_run(session, *, owner_id: str, scope: str, intervals: str,
                capital: float, total: int, now: dt.datetime | None = None,
                **values) -> BacktestRun:
    """Create durable pending work before any provider read or worker launch."""
    queued_at = _clock(now)
    run = BacktestRun(owner_id=owner_id, scope=scope, intervals=intervals,
                      capital=capital, total=total, status="pending",
                      queued_at=queued_at, **values)
    session.add(run)
    session.flush()
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
    candidate = session.scalar(select(BacktestRun.id).where(
        BacktestRun.owner_id == owner_id, BacktestRun.cancel_requested_at.is_(None),
        _claimable(moment)).order_by(BacktestRun.queued_at, BacktestRun.id).limit(1))
    if candidate is None:
        return None
    return claim_run(session, owner_id=owner_id, run_id=int(candidate),
                     claimed_by=claimed_by, now=moment, lease_seconds=lease_seconds)


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
             value.get("strategy_key"), value.get("strategy_version"))
    if not all(isinstance(part, str) and part for part in parts):
        raise ValueError("backtest result lacks a stable cell identity")
    return "\x1f".join(parts)


def append_claimed_result_batch(session, *, owner_id: str, run_id: int,
                                claim_token: str, values: list[dict],
                                now: dt.datetime | None = None,
                                lease_seconds: int = 30) -> bool:
    """Insert a bounded result batch and its progress under one fenced savepoint.

    A false result has no side effect, including no pending ORM rows that a caller
    might accidentally commit after a lost lease.
    """
    moment = _clock(now)
    with session.begin_nested():
        # Check before inserting so a cancellation/replacement cannot make a
        # stale process create rows. The same predicate is repeated after flush
        # to fence a takeover that wins while this worker computes its count.
        if session.execute(update(BacktestRun).where(
            _active_claim(owner_id, run_id, claim_token, moment)).values(
                heartbeat_at=moment,
                claim_expires_at=moment + dt.timedelta(seconds=max(1, int(lease_seconds))))).rowcount != 1:
            return False
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
    with session.begin_nested():
        done = durable_result_count(session, owner_id=owner_id, run_id=run_id)
        result = session.execute(update(BacktestRun).where(predicate).values(
            status=status, done=done, note=note[:400] if note else BacktestRun.note,
            completed_at=moment, heartbeat_at=moment))
        if result.rowcount != 1:
            return False
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
        return True
    result = session.execute(update(BacktestRun).where(
        BacktestRun.owner_id == owner_id, BacktestRun.id == run_id,
        BacktestRun.status == "running",
        BacktestRun.cancel_requested_at.is_(None)).values(cancel_requested_at=moment))
    return result.rowcount == 1


def is_cancel_requested(session, *, owner_id: str, run_id: int,
                        claim_token: str, now: dt.datetime | None = None) -> bool:
    moment = _clock(now)
    return session.scalar(select(BacktestRun.id).where(
        _active_claim(owner_id, run_id, claim_token, moment, allow_cancel=True),
        BacktestRun.cancel_requested_at.is_not(None)).limit(1)) is not None


def reconcile_expired_claims(session, *, owner_id: str,
                             now: dt.datetime | None = None) -> int:
    """Requeue only expired leases; a live process is never inferred dead."""
    moment = _clock(now)
    result = session.execute(update(BacktestRun).where(
        BacktestRun.owner_id == owner_id, BacktestRun.status == "running",
        BacktestRun.claim_expires_at.is_not(None), BacktestRun.claim_expires_at <= moment).values(
            status="pending", claim_token=None, claimed_by=None,
            claim_expires_at=None, heartbeat_at=None,
            note="interrupted: expired worker claim; durable progress retained"))
    reclaimed = int(result.rowcount or 0)
    # A pre-0025 row cannot name any worker or lease. It is historical phantom
    # state, not an expired live claim; preserve its results but make its outcome
    # explicit once so legacy status APIs do not report an immortal worker.
    legacy = session.execute(update(BacktestRun).where(
        BacktestRun.owner_id == owner_id, BacktestRun.status == "running",
        BacktestRun.claim_token.is_(None), BacktestRun.claim_expires_at.is_(None)).values(
            status="error", completed_at=moment,
            done=select(func.count()).select_from(BacktestResult).where(
                BacktestResult.owner_id == BacktestRun.owner_id,
                BacktestResult.run_id == BacktestRun.id).scalar_subquery(),
            note="interrupted legacy run without a durable worker claim"))
    return reclaimed + int(legacy.rowcount or 0)
