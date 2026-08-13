"""Replica projection reloads never substitute unrelated lease state."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, BrokerAccount, Deployment
from app.events.outbox import PrincipalScope


def _store():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    sm = sessionmaker(engine, expire_on_commit=False, future=True)
    with sm.begin() as session:
        session.add_all([
            BrokerAccount(broker_account_id="account-a", owner_id="owner-a", broker="kite",
                          external_account_id="a", display_name="A"),
            BrokerAccount(broker_account_id="account-b", owner_id="owner-b", broker="kite",
                          external_account_id="b", display_name="B"),
            Deployment(id=11, owner_id="owner-a", broker_account_id="account-a",
                       name="A deployment", status="active", armed=False),
            Deployment(id=12, owner_id="owner-b", broker_account_id="account-b",
                       name="B deployment", status="active", armed=False),
        ])
    return engine, sm


def test_deployment_event_reloads_only_the_scoped_deployment_projection(monkeypatch):
    """Mapping deployment changes to LeaseRepository.status must make this fail."""
    from app.events.projections import reload_durable_projection

    def refuse_lease(*_args, **_kwargs):
        raise AssertionError("deployment projection reached execution lease status")

    monkeypatch.setattr("app.execution.leases.LeaseRepository.status", refuse_lease)
    engine, sm = _store()
    try:
        got = reload_durable_projection(
            PrincipalScope("owner-a", "account-a"), "deployments",
            execution_sessionmaker=sm,
        )
        assert got == {
            "projection": "deployments",
            "deployments": [{
                "id": 11, "name": "A deployment", "status": "active", "armed": False,
            }],
        }
    finally:
        engine.dispose()


def test_lifecycle_event_returns_typed_invalidation_instead_of_lease_snapshot(monkeypatch):
    """A projection with no bounded read model must identify itself as invalidation."""
    from app.events.projections import reload_durable_projection

    monkeypatch.setattr(
        "app.execution.leases.LeaseRepository.status",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("lifecycle projection reached lease status")),
    )
    engine, sm = _store()
    try:
        got = reload_durable_projection(
            PrincipalScope("owner-a", "account-a"), "execution_lifecycle",
            execution_sessionmaker=sm,
        )
        assert got == {
            "projection": "execution_lifecycle",
            "kind": "durable_invalidation",
        }
    finally:
        engine.dispose()
