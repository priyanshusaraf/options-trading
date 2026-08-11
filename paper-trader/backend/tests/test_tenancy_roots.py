"""Tenancy roots are durable identities, not route-level filters."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.db.models import Base
from app.db.planes import Plane, TABLE_PLANES
from app.db.session import SessionLocal, init_db


ROOTS = {
    "organizations": Plane.USER,
    "users": Plane.USER,
    "memberships": Plane.USER,
    "broker_accounts": Plane.MONEY,
}


def test_tenancy_root_models_have_the_declared_identity_contract():
    tables = Base.metadata.tables
    assert set(ROOTS) <= set(tables)
    assert [column.name for column in tables["organizations"].primary_key] == ["organization_id"]
    assert [column.name for column in tables["users"].primary_key] == ["user_id"]
    assert [column.name for column in tables["memberships"].primary_key] == [
        "organization_id", "user_id"
    ]
    assert [column.name for column in tables["broker_accounts"].primary_key] == [
        "broker_account_id"
    ]
    assert {name: TABLE_PLANES[name] for name in ROOTS} == ROOTS


def test_tenancy_root_models_enforce_normalized_identity_constraints(tmp_path):
    models = __import__("app.db.models", fromlist=["Organization", "User", "Membership", "BrokerAccount"])
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'roots.db'}")
    Base.metadata.create_all(engine)

    with sa.orm.Session(engine) as session:
        session.add_all([
            models.Organization(organization_id="org.a", name="A"),
            models.User(user_id="user.a", email_normalized="a@example.test", display_name="A"),
            models.Membership(organization_id="org.a", user_id="user.a", role="owner"),
            models.BrokerAccount(
                broker_account_id="account.a", owner_id="org.a", broker="kite",
                external_account_id="external-a", display_name="A account"),
        ])
        session.commit()
        session.add(models.User(
            user_id="user.b", email_normalized=" A@EXAMPLE.TEST ", display_name="B"))
        with __import__("pytest").raises(IntegrityError):
            session.commit()


def test_fresh_reset_bootstrap_seeds_exactly_one_legacy_root_set_idempotently():
    """`create_all` does not run migration DML, so init_db owns this compatibility seed."""
    from app.db.models import (BrokerAccount, LEGACY_BROKER_ACCOUNT_ID, LEGACY_OWNER_ID,
                               LEGACY_USER_ID, Membership, Organization, User)

    init_db(reset=True)
    init_db(reset=False)
    with SessionLocal() as session:
        assert session.query(Organization).filter_by(organization_id=LEGACY_OWNER_ID).count() == 1
        assert session.query(User).filter_by(user_id=LEGACY_USER_ID).count() == 1
        assert session.query(Membership).filter_by(
            organization_id=LEGACY_OWNER_ID, user_id=LEGACY_USER_ID).count() == 1
        assert session.query(BrokerAccount).filter_by(
            broker_account_id=LEGACY_BROKER_ACCOUNT_ID).count() == 1
        assert session.query(Organization).count() == 1
        assert session.query(User).count() == 1
        assert session.query(Membership).count() == 1
        assert session.query(BrokerAccount).count() == 1
        organization = session.get(Organization, LEGACY_OWNER_ID)
        user = session.get(User, LEGACY_USER_ID)
        assert (organization.name, organization.status) == ("Legacy owner", "active")
        assert (user.email_normalized, user.display_name, user.status) == (
            "owner@legacy.local", "Legacy owner", "active")
        membership = session.get(Membership, (LEGACY_OWNER_ID, LEGACY_USER_ID))
        assert (membership.role, membership.status) == ("owner", "active")
        account = session.get(BrokerAccount, LEGACY_BROKER_ACCOUNT_ID)
        assert (account.owner_id, account.broker, account.external_account_id,
                account.display_name, account.status) == (
                    LEGACY_OWNER_ID, "legacy", "default", "Default account", "active")


def test_membership_refuses_dangling_same_plane_roots(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'membership-fks.db'}")
    with engine.connect() as connection:
        connection.execute(sa.text("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with sa.orm.Session(engine) as session:
        session.add_all([
            __import__("app.db.models", fromlist=["Organization"]).Organization(
                organization_id="org.a", name="A"),
            __import__("app.db.models", fromlist=["User"]).User(
                user_id="user.a", email_normalized="a@example.test", display_name="A"),
        ])
        session.commit()
        session.add(__import__("app.db.models", fromlist=["Membership"]).Membership(
            organization_id="org.a", user_id="missing", role="member"))
        with __import__("pytest").raises(IntegrityError):
            session.commit()
