"""Task 6 owner-local universe preference regression proof."""
from sqlalchemy import select

from app.core import universe_resolver
from app.core.instruments import all_instruments, home_instruments
from app.db.models import Organization, UniverseInstrument, UniversePreference
from app.db.session import SessionLocal, init_db
from app.providers.mock import MockProvider


def test_organizations_share_canonical_facts_but_not_portfolio_choices():
    init_db(reset=True)
    with SessionLocal() as s:
        s.add(Organization(organization_id="org-b", name="Org B"))
        s.add(UniversePreference(owner_id="org-b", instrument_key="NIFTY",
                                 active=True, on_home=False, source="seed"))
        s.commit()

    result = universe_resolver.add_instrument("NIFTY", MockProvider(), owner_id="org-b", on_home=True)
    assert result["added"] is True
    with SessionLocal() as s:
        canonical = s.get(UniverseInstrument, "NIFTY")
        owner = s.get(UniversePreference, ("owner", "NIFTY"))
        other = s.get(UniversePreference, ("org-b", "NIFTY"))
        assert canonical is not None
        assert owner is not None and owner.on_home is True
        assert other is not None and other.on_home is True
        other.on_home = False
        s.commit()

    owner_view = {fact.key: preference for fact, preference in universe_resolver.composed_universe("owner")}
    other_view = {fact.key: preference for fact, preference in universe_resolver.composed_universe("org-b")}
    assert owner_view["NIFTY"].on_home is True
    assert other_view["NIFTY"].on_home is False
    assert [item.key for item in home_instruments("owner")] == ["NIFTY", "GOLDM", "CRUDEOIL", "BANKNIFTY"]
    assert "NIFTY" not in [item.key for item in home_instruments("org-b")]
    assert "NIFTY" in [item.key for item in all_instruments("org-b")]
    # The owner predicate is structural: a preference identity cannot be read
    # or written without both dimensions of its composite primary key.
    assert UniversePreference.__table__.primary_key.columns.keys() == ["owner_id", "instrument_key"]
