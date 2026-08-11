"""Capital books are always addressed within a broker account."""
from __future__ import annotations

import pytest

from app.core import execution_book as eb
from app.core.execution_book import LIVE, PAPER
from app.db.models import (BrokerAccount, LEGACY_BROKER_ACCOUNT_ID, Organization,
                           CapitalState)
from app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def a_fresh_ledger():
    init_db(reset=True)
    yield


def test_seeded_ledger_is_the_legacy_accounts_live_book():
    with SessionLocal() as session:
        row = session.get(CapitalState, (LEGACY_BROKER_ACCOUNT_ID, LIVE))
        assert row is not None


def test_each_book_gets_its_own_row_within_an_account():
    with SessionLocal() as session:
        live = eb.capital_for_book(session, LIVE, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
        paper = eb.capital_for_book(session, PAPER, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
        assert (live.broker_account_id, live.book) != (paper.broker_account_id, paper.book)


def test_identical_book_names_are_isolated_by_account():
    with SessionLocal() as session:
        session.add(Organization(organization_id="org.second", name="Second"))
        session.add(BrokerAccount(broker_account_id="account.second", owner_id="org.second",
                                  broker="paper", external_account_id="second",
                                  display_name="Second account"))
        session.commit()
        legacy = eb.capital_for_book(session, PAPER, broker_account_id=LEGACY_BROKER_ACCOUNT_ID)
        other = eb.capital_for_book(session, PAPER, broker_account_id="account.second")
        other.cash -= 5_000.0
        session.commit()
        assert eb.capital_for_book(
            session, PAPER, broker_account_id=LEGACY_BROKER_ACCOUNT_ID).cash == legacy.cash
        assert eb.capital_for_book(session, PAPER, broker_account_id="account.second").cash == (
            legacy.cash - 5_000.0)


def test_account_scope_is_required_and_unknown_books_are_refused():
    with SessionLocal() as session:
        with pytest.raises(TypeError):
            eb.capital_for_book(session, LIVE)
        with pytest.raises(ValueError):
            eb.capital_for_book(session, "shadow", broker_account_id=LEGACY_BROKER_ACCOUNT_ID)


@pytest.mark.parametrize("book", (LIVE, PAPER))
def test_missing_broker_account_refuses_even_when_a_named_capital_row_exists(book):
    with SessionLocal() as session:
        session.add(CapitalState(broker_account_id="missing.account", book=book,
                                 initial_capital=1, cash=1, realized_pnl=0))
        session.commit()
        with pytest.raises(ValueError, match="broker account.*missing.account"):
            eb.capital_for_book(session, book, broker_account_id="missing.account")


def test_missing_broker_account_refuses_before_creating_capital_state():
    with SessionLocal() as session:
        with pytest.raises(ValueError, match="broker account.*missing.account"):
            eb.capital_for_book(session, PAPER, broker_account_id="missing.account")
        assert session.get(CapitalState, ("missing.account", PAPER)) is None
