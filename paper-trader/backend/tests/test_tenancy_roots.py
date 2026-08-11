"""Tenancy roots are durable identities, not route-level filters."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.db.models import Base
from app.db.planes import Plane, TABLE_PLANES


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
