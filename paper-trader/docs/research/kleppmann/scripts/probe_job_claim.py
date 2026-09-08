#!/usr/bin/env python3
"""Independent real-repository claim probe, using the existing isolated fixture.

Run from paper-trader/backend with .venv/bin/python. No product bytes change.
The optional mutant removes the token predicate in this process only; it must fail.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import json
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path.cwd()))
import conftest  # noqa: E402 — isolates every database before any app import

safety = conftest._forbid_live_execution.__wrapped__()
next(safety)

from sqlalchemy import and_  # noqa: E402
from app.backtest import repository  # noqa: E402
from app.db.models import BacktestRun  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from tests.admitted_entry import persist_admitted_entry  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mutate-token-fence', action='store_true')
    args = parser.parse_args()
    init_db(reset=True)
    moment = dt.datetime(2026, 8, 28, 10, tzinfo=dt.timezone.utc)
    with SessionLocal() as session:
        identity = persist_admitted_entry(session, owner_id='audit-owner')
        run = repository.enqueue_run(
            session, owner_id='audit-owner', scope='liquid', intervals='day',
            capital=1.0, total=1, admission_address=identity['admission_address'])
        run_id = run.id
        session.commit()

    barrier = threading.Barrier(2)

    def compete(worker):
        with SessionLocal() as session:
            barrier.wait(timeout=15)
            row = repository.claim_run(session, owner_id='audit-owner', run_id=run_id,
                                       claimed_by=worker, now=moment, lease_seconds=1)
            token = row.claim_token if row is not None else None
            session.commit()
            return token

    with ThreadPoolExecutor(max_workers=2) as pool:
        tokens = list(pool.map(compete, ('worker-a', 'worker-b')))
    winners = [token for token in tokens if token is not None]
    assert len(winners) == 1, f'claim race had {len(winners)} winners'
    old_token = winners[0]
    with SessionLocal() as session:
        row = repository.claim_run(session, owner_id='audit-owner', run_id=run_id,
                                   claimed_by='replacement', now=moment + dt.timedelta(seconds=2),
                                   lease_seconds=30)
        assert row is not None
        new_token = row.claim_token
        session.commit()
    assert old_token != new_token

    if args.mutate_token_fence:
        def missing_token(owner_id, run_id, token, now, *, allow_cancel=False):
            clauses = [BacktestRun.owner_id == owner_id, BacktestRun.id == run_id,
                       BacktestRun.status == 'running', BacktestRun.claim_expires_at.is_not(None),
                       BacktestRun.claim_expires_at > now]
            if not allow_cancel: clauses.append(BacktestRun.cancel_requested_at.is_(None))
            return and_(*clauses)
        repository._active_claim = missing_token

    later = moment + dt.timedelta(seconds=3)
    with SessionLocal() as session:
        stale = repository.complete_claim(session, owner_id='audit-owner', run_id=run_id,
                                          claim_token=old_token, status='error', now=later)
        assert stale is False, 'stale claimant committed after replacement: token guard missing'
        wrong_owner = repository.heartbeat_claim(session, owner_id='other-owner', run_id=run_id,
                                                 claim_token=new_token, now=later)
        assert wrong_owner is False, 'another owner renewed the claim'
        current = repository.complete_claim(session, owner_id='audit-owner', run_id=run_id,
                                            claim_token=new_token, status='error', now=later)
        assert current is True
        session.commit()
    with SessionLocal() as session:
        row = repository.get_run(session, owner_id='audit-owner', run_id=run_id)
        assert row.status == 'error' and row.claim_token == new_token and row.attempt_count == 2
    print(json.dumps({'result': 'PASS', 'database': 'private SQLite via root conftest',
                      'real_concurrent_claimants': 2, 'winners': len(winners),
                      'stale_terminal_write': 'rejected', 'foreign_heartbeat': 'rejected',
                      'current_terminal_write': 'persisted', 'product_bytes_changed': False}))


if __name__ == '__main__': main()
