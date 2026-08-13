from __future__ import annotations
import datetime as dt

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models import AccountExecutionLease, Base, BrokerAccount
from app.execution.disaster_recovery import RestoreTakeoverRefused, claim_restored_execution_lease
from app.execution.leases import LeaseRepository, StaleLease


@pytest.fixture()
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'restore-lease.db'}", future=True)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, future=True, expire_on_commit=False)
    with sessions.begin() as session:
        session.add(BrokerAccount(
            broker_account_id="account-a", owner_id="tenant-a", broker="fake",
            external_account_id="a", display_name="A"))
    yield LeaseRepository(sessions), sessions
    engine.dispose()


def test_restored_active_lease_is_historical_and_new_holder_gets_higher_recovering_epoch(store):
    repo, sessions = store
    old = repo.claim(owner_id="tenant-a", broker_account_id="account-a",
                     cell_id="old-cell", worker_id="old-boot")
    repo.activate(old, reconciliation_evidence="empty fake broker")
    new = claim_restored_execution_lease(
        repo, owner_id="tenant-a", broker_account_id="account-a",
        cell_id="new-cell", worker_id="new-boot",
        verification_address="sha256:" + "b" * 64,
        old_primary_isolated=True,
    )
    assert new.fence_epoch == old.fence_epoch + 1
    with sessions() as session:
        row = session.scalar(select(AccountExecutionLease))
        assert row.state == "recovering"
        assert row.desired_state == row.effective_state == "disabled"
    with pytest.raises(StaleLease):
        repo.heartbeat(old)


def test_restore_takeover_requires_old_primary_isolation_and_verified_report(store):
    repo, _sessions = store
    repo.claim(owner_id="tenant-a", broker_account_id="account-a",
               cell_id="old-cell", worker_id="old-boot")
    with pytest.raises(RestoreTakeoverRefused, match="old primary"):
        claim_restored_execution_lease(
            repo, owner_id="tenant-a", broker_account_id="account-a",
            cell_id="new-cell", worker_id="new-boot",
            verification_address="sha256:" + "b" * 64,
            old_primary_isolated=False)
    with pytest.raises(RestoreTakeoverRefused, match="verification"):
        claim_restored_execution_lease(
            repo, owner_id="tenant-a", broker_account_id="account-a",
            cell_id="new-cell", worker_id="new-boot",
            verification_address="unsigned", old_primary_isolated=True)
