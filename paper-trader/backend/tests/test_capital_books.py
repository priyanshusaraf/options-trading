"""One ledger per book, and how the single pre-slice ledger is attributed.

`capital_state` held exactly one row (`id=1`, hardcoded at six call sites) whose `cash`
and `realized_pnl` were mutated in place by whichever broker booked a fill. That is the
invariant this slice could not express by filtering: there is no `WHERE` clause to add to
an aggregate that is already a single mutable number.

The claim rule is deterministic and derives only from immutable evidence — the `mode`
already stamped on every `positions` and `trades` row. Production is unambiguous: 72 live
rows, zero paper.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from app.core import execution_book as eb
from app.core.execution_book import LIVE, PAPER
from app.db.models import CapitalState, Position, Trade
from app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def a_fresh_ledger():
    init_db(reset=True)
    yield


def _position(session, *, mode, key="NIFTY"):
    session.add(Position(
        instrument_key=key, direction="LONG", option_type="CE",
        tradingsymbol=f"{key}TEST", exchange="NFO", segment="equity_intraday",
        strike=0.0, expiry=dt.date(2030, 1, 1), qty=1, lot_size=1,
        entry_premium=100.0, entry_charges=0.0, entry_cost=100.0,
        entry_time=dt.datetime(2026, 1, 1, 10, 0), entry_spot=100.0,
        stop_price=90.0, target_price=110.0, high_water_premium=100.0,
        mfe=0.0, mae=0.0, mode=mode))


def _trade(session, *, mode, key="NIFTY"):
    session.add(Trade(
        instrument_key=key, direction="LONG", option_type="CE",
        tradingsymbol=f"{key}TEST", exchange="NFO", segment="equity_intraday",
        strike=0.0, expiry=dt.date(2030, 1, 1), qty=1,
        entry_premium=100.0, exit_premium=101.0, entry_cost=100.0, exit_charges=0.0,
        entry_time=dt.datetime(2026, 1, 1, 10, 0),
        exit_time=dt.datetime(2026, 1, 1, 11, 0),
        entry_spot=100.0, exit_spot=101.0, gross_pnl=1.0, charges_total=0.0,
        net_pnl=1.0, return_pct=1.0, holding_minutes=60, win=True,
        exit_reason="TARGET", mode=mode))


class TestClaimingTheLegacyLedger:
    def test_the_seeded_ledger_starts_unclaimed(self):
        with SessionLocal() as s:
            assert s.get(CapitalState, 1).book is None

    def test_an_empty_ledger_is_claimed_by_whichever_book_asks_first(self):
        with SessionLocal() as s:
            row = eb.capital_for_book(s, PAPER)
            s.commit()
            assert row.id == 1 and row.book == PAPER

    def test_a_ledger_holding_only_live_rows_is_claimed_by_live(self):
        """Production's exact shape. The cash and realised P&L on that row were produced
        by live fills, so the live book keeps them and paper starts fresh."""
        with SessionLocal() as s:
            _trade(s, mode=LIVE)
            s.commit()
            row = eb.capital_for_book(s, LIVE)
            s.commit()
            assert row.id == 1 and row.book == LIVE

    def test_a_ledger_holding_only_live_rows_is_not_claimed_by_paper(self):
        with SessionLocal() as s:
            _trade(s, mode=LIVE)
            s.commit()
            row = eb.capital_for_book(s, PAPER)
            s.commit()
            assert row.id != 1
            assert row.book == PAPER
            assert s.get(CapitalState, 1).book is None

    def test_open_positions_count_as_evidence_too(self):
        with SessionLocal() as s:
            _position(s, mode=LIVE)
            s.commit()
            assert eb.capital_for_book(s, PAPER).id != 1

    def test_a_ledger_with_rows_from_both_books_is_left_unattributed(self):
        """A state production has never been in and one this slice makes unreachable.

        Guessing which book owns the cash is the failure this prevents — but *raising*
        is not the remedy. A broker that cannot construct is an engine that cannot run
        its risk lane, and hard invariant 2 says not getting out is worse than any
        accounting defect. So both books start fresh, the legacy row keeps its cash, and
        the ambiguity is logged rather than resolved by guesswork."""
        with SessionLocal() as s:
            _trade(s, mode=LIVE)
            _trade(s, mode=PAPER, key="BANKNIFTY")
            s.commit()
            legacy_cash = s.get(CapitalState, 1).cash

            fresh = eb.capital_for_book(s, LIVE)

            assert fresh.id != 1 and fresh.book == LIVE
            assert s.get(CapitalState, 1).book is None
            assert s.get(CapitalState, 1).cash == legacy_cash

    def test_a_claim_is_permanent(self):
        with SessionLocal() as s:
            eb.capital_for_book(s, LIVE)
            s.commit()
        with SessionLocal() as s:
            assert eb.capital_for_book(s, LIVE).id == 1
            _trade(s, mode=PAPER)
            s.commit()
            assert eb.capital_for_book(s, LIVE).id == 1


class TestTwoLedgersCoexisting:
    def test_each_book_gets_its_own_row(self):
        with SessionLocal() as s:
            live = eb.capital_for_book(s, LIVE)
            s.commit()
            paper = eb.capital_for_book(s, PAPER)
            s.commit()
            assert live.id != paper.id
            assert {live.book, paper.book} == {LIVE, PAPER}

    def test_a_new_book_is_seeded_at_the_configured_initial_capital(self):
        from app.core.config import get_settings
        with SessionLocal() as s:
            eb.capital_for_book(s, LIVE)
            s.commit()
            paper = eb.capital_for_book(s, PAPER)
            s.commit()
            assert paper.initial_capital == get_settings().initial_capital
            assert paper.cash == get_settings().initial_capital
            assert paper.realized_pnl == 0.0

    def test_spending_one_books_cash_leaves_the_other_untouched(self):
        with SessionLocal() as s:
            live = eb.capital_for_book(s, LIVE)
            s.commit()
            paper = eb.capital_for_book(s, PAPER)
            s.commit()
            before = live.cash
            paper.cash -= 5_000.0
            paper.realized_pnl -= 5_000.0
            s.commit()
        with SessionLocal() as s:
            assert eb.capital_for_book(s, LIVE).cash == before
            assert eb.capital_for_book(s, LIVE).realized_pnl == 0.0
            assert eb.capital_for_book(s, PAPER).cash == before - 5_000.0

    def test_the_lookup_is_by_book_not_by_primary_key(self):
        """`s.get(CapitalState, 1)` is the shape this replaces. Whichever row the paper
        book owns, asking for it must never return row 1 once live has claimed it."""
        with SessionLocal() as s:
            eb.capital_for_book(s, LIVE)
            s.commit()
            assert eb.capital_for_book(s, PAPER).id != 1
            s.commit()
        with SessionLocal() as s:
            rows = list(s.scalars(select(CapitalState)))
            assert len(rows) == 2
            assert sorted(r.book for r in rows) == [LIVE, PAPER]


class TestAnUnknownBookIsRefused:
    def test_asking_for_a_book_that_does_not_exist_raises(self):
        with SessionLocal() as s:
            with pytest.raises(ValueError):
                eb.capital_for_book(s, "shadow")
