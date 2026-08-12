"""Required-owner persistence boundary for durable backtest evidence."""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.models import BacktestResult, BacktestRun


def create_run(session, *, owner_id: str, scope: str, intervals: str,
               capital: float, total: int, **values) -> BacktestRun:
    run = BacktestRun(owner_id=owner_id, scope=scope, intervals=intervals,
                      capital=capital, total=total, **values)
    session.add(run)
    session.flush()
    return run


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
    if get_run(session, owner_id=owner_id, run_id=run_id) is None:
        raise ValueError("no such backtest run")
    for value in values:
        session.add(BacktestResult(owner_id=owner_id, run_id=run_id, **value))


def durable_result_count(session, *, owner_id: str, run_id: int) -> int:
    return int(session.scalar(select(func.count()).select_from(BacktestResult).where(
        BacktestResult.owner_id == owner_id, BacktestResult.run_id == run_id)) or 0)


def update_run(session, *, owner_id: str, run_id: int, status: str = "",
               note: str = "") -> BacktestRun | None:
    run = get_run(session, owner_id=owner_id, run_id=run_id)
    if run is None:
        return None
    run.done = durable_result_count(session, owner_id=owner_id, run_id=run_id)
    if status:
        run.status = status
    if note:
        run.note = note[:400]
    return run


def reconcile_stale_runs(session, *, owner_id: str, note: str) -> int:
    runs = list(session.scalars(select(BacktestRun).where(
        BacktestRun.owner_id == owner_id, BacktestRun.status == "running")))
    for run in runs:
        run.status = "error"
        run.done = durable_result_count(session, owner_id=owner_id, run_id=run.id)
        run.note = note[:400]
    return len(runs)
