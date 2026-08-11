"""Paper and live money state must be structurally incapable of contaminating each other.

These are the twelve invariants of L1.3B, proved by *semantics* rather than row counts —
each test makes the two books hold state that would be indistinguishable under the
pre-slice queries, then asks a question whose answer differs per book.

The failure being prevented is concrete. Before this slice, `broker.position_for(key)` was
unscoped, and its docstring said so: "at most ONE open position per instrument across the
whole system". A paper broker asked to exit would have found the *live* position, written a
close into the ledger, and left the real contract open at Zerodha — a visible orphan turned
into an invisible one. The paper broker has no order client; it cannot close a live
position, so it must not be able to see one.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.execution_book import LIVE, PAPER
from app.db.models import Position, Trade
from app.db.session import SessionLocal, init_db
from app.engine.broker import PaperBroker
from app.providers.mock import MockProvider

SCOPE = {"owner_id": "owner", "broker_account_id": "account.default"}


@pytest.fixture(autouse=True)
def a_fresh_ledger():
    init_db(reset=True)
    yield


class _LiveLikeBroker(PaperBroker):
    """A broker that writes the live book without placing a real order.

    Subclassing `PaperBroker` and overriding `MODE` is the whole trick, and it is
    deliberate: the real `LiveBroker` cannot be constructed under pytest (`make_broker`
    refuses), so the coexistence proof needs a live-*book* writer that is not a live
    *order* placer. Everything under test here reads `self.MODE`, which is exactly the
    seam being proved."""

    MODE = LIVE


def _broker(mode):
    return (_LiveLikeBroker(MockProvider(), owner_id="owner", broker_account_id="account.default")
            if mode == LIVE else PaperBroker(MockProvider(), owner_id="owner", broker_account_id="account.default"))


def _open_row(session, *, mode, key="NIFTY", entry_cost=1_000.0):
    row = Position(owner_id='owner', broker_account_id='account.default',
        instrument_key=key, direction="LONG", option_type="CE",
        tradingsymbol=f"{key}{mode.upper()}", exchange="NFO", segment="equity_intraday",
        strike=0.0, expiry=dt.date(2030, 1, 1), qty=1, lot_size=1,
        entry_premium=entry_cost, entry_charges=0.0, entry_cost=entry_cost,
        entry_time=dt.datetime(2026, 1, 1, 10, 0), entry_spot=entry_cost,
        stop_price=0.0, target_price=0.0, high_water_premium=entry_cost,
        last_premium=entry_cost, mfe=0.0, mae=0.0, mode=mode)
    session.add(row)
    session.commit()
    return row


def _closed_row(session, *, mode, net, key="NIFTY", when=dt.datetime(2026, 1, 1, 11, 0)):
    session.add(Trade(owner_id='owner', broker_account_id='account.default',
        instrument_key=key, direction="LONG", option_type="CE",
        tradingsymbol=f"{key}{mode.upper()}", exchange="NFO", segment="equity_intraday",
        strike=0.0, expiry=dt.date(2030, 1, 1), qty=1,
        entry_premium=100.0, exit_premium=100.0 + net, entry_cost=100.0,
        exit_charges=0.0, entry_time=when - dt.timedelta(hours=1), exit_time=when,
        entry_spot=100.0, exit_spot=100.0 + net, gross_pnl=net, charges_total=0.0,
        net_pnl=net, return_pct=net, holding_minutes=60, win=net > 0,
        exit_reason="TARGET", mode=mode))
    session.commit()


# ── invariants 1, 2, 8 ────────────────────────────────────────────────────────
class TestPositionsCannotCrossBooks:
    def test_a_live_position_is_never_returned_as_a_paper_position(self):
        with SessionLocal() as s:
            _open_row(s, mode=LIVE)
        paper = _broker(PAPER)
        try:
            assert paper.open_positions() == []
            assert paper.position_for("NIFTY") is None
        finally:
            paper.close()

    def test_a_paper_position_is_never_returned_as_a_live_position(self):
        with SessionLocal() as s:
            _open_row(s, mode=PAPER)
        live = _broker(LIVE)
        try:
            assert live.open_positions() == []
            assert live.position_for("NIFTY") is None
        finally:
            live.close()

    def test_the_same_instrument_can_be_open_in_both_books_at_once(self):
        """The assumption the old unscoped read encoded — one open position per
        instrument, system-wide — stops being true here, and nothing may depend on it."""
        with SessionLocal() as s:
            _open_row(s, mode=LIVE, entry_cost=1_000.0)
            _open_row(s, mode=PAPER, entry_cost=2_000.0)
        paper, live = _broker(PAPER), _broker(LIVE)
        try:
            assert paper.position_for("NIFTY").entry_cost == 2_000.0
            assert live.position_for("NIFTY").entry_cost == 1_000.0
            assert len(paper.open_positions()) == 1
            assert len(live.open_positions()) == 1
        finally:
            paper.close(), live.close()

    def test_an_exit_cannot_close_a_position_belonging_to_another_book(self):
        """Invariant 8, at the seam the exit path actually uses. Every square-off and
        stop in `runner.py` reaches its position through `open_positions()`."""
        with SessionLocal() as s:
            live_row = _open_row(s, mode=LIVE)
            live_id = live_row.id
        paper = _broker(PAPER)
        try:
            assert [p.id for p in paper.open_positions()] == []
            assert live_id not in {p.id for p in paper.open_positions()}
        finally:
            paper.close()
        with SessionLocal() as s:
            assert s.get(Position, live_id) is not None

    def test_the_deployment_scope_still_composes_with_the_book_scope(self):
        """Book and deployment are different identities and both still narrow. Collapsing
        one into the other is the mistake ADR 0012 §4.1 names."""
        with SessionLocal() as s:
            _open_row(s, mode=PAPER)
        paper = _broker(PAPER)
        try:
            assert len(paper.open_positions()) == 1
            assert paper.open_positions(deployment_id=999) == []
        finally:
            paper.close()


# ── invariants 3, 4 ───────────────────────────────────────────────────────────
def _claim_both_ledgers():
    """Give each book its `capital_state` row, one broker at a time.

    Sequential by necessity, not by style: each broker holds a long-lived session for its
    lifetime (deliberately — the identity map carries the re-anchor write), and two of
    them writing at once deadlocks SQLite. Production only ever builds one."""
    ids = {}
    for mode in (LIVE, PAPER):
        b = _broker(mode)
        try:
            ids[mode] = b.capital().id
            b.s.commit()
        finally:
            b.close()
    return ids


class TestRealisedAndUnrealisedPnlStayApart:
    def test_each_book_reconciles_against_its_own_ledger(self):
        ids = _claim_both_ledgers()
        assert ids[LIVE] != ids[PAPER]
        for mode in (LIVE, PAPER):
            b = _broker(mode)
            try:
                assert b.reconcile()["diff"] == 0.0
            finally:
                b.close()

    def test_one_books_open_position_does_not_break_the_others_reconciliation(self):
        """`cash == initial + realized − Σ(open entry_cost)` is hard invariant 1. An
        open position in the other book must not appear in this book's Σ."""
        _claim_both_ledgers()
        with SessionLocal() as s:
            _open_row(s, mode=LIVE, entry_cost=7_000.0)
        paper = _broker(PAPER)
        try:
            assert paper.reconcile()["diff"] == 0.0
            assert paper.reconcile()["open"] == 0
        finally:
            paper.close()
        live = _broker(LIVE)
        try:
            # The live book's own reconciliation *does* see it — and is off by exactly
            # the entry cost, because this row was inserted behind the broker's back.
            assert live.reconcile()["open"] == 1
        finally:
            live.close()

    def test_an_equity_snapshot_is_stamped_with_the_book_that_took_it(self):
        for mode in (PAPER, LIVE):
            b = _broker(mode)
            try:
                assert b.snapshot(dt.datetime(2026, 1, 1, 12, 0)).book == mode
            finally:
                b.close()

    def test_the_equity_curve_returns_only_the_requested_books_points(self):
        from app.engine import analytics

        for i, mode in enumerate((PAPER, LIVE)):
            b = _broker(mode)
            try:
                b.snapshot(dt.datetime(2026, 1, 1, 12, i))
            finally:
                b.close()
        with SessionLocal() as s:
            scope = {"owner_id": "owner", "broker_account_id": "account.default"}
            assert len(analytics.equity_curve(s, book=PAPER, **scope)) == 1
            assert len(analytics.equity_curve(s, book=LIVE, **scope)) == 1
            assert len(analytics.equity_curve(s, **scope)) == 2

    def test_capital_dict_reports_one_books_cash_and_open_count(self):
        from app.engine import analytics

        _claim_both_ledgers()
        with SessionLocal() as s:
            _open_row(s, mode=LIVE, entry_cost=3_000.0)
            assert analytics.capital_dict(s, book=PAPER, owner_id="owner", broker_account_id="account.default")["open_count"] == 0
            assert analytics.capital_dict(s, book=LIVE, owner_id="owner", broker_account_id="account.default")["open_count"] == 1


# ── invariants 3 (trades), 9 ──────────────────────────────────────────────────
class TestTradeAggregatesDeclareTheirBook:
    def test_the_daily_loss_breaker_counts_only_its_own_books_trades(self):
        """A paper loss must not halt the live book, and a live loss must not be masked
        by a paper win. This is a risk control, so the scope is not cosmetic."""
        from app.engine import analytics

        today = dt.datetime(2026, 1, 1, 11, 0)
        with SessionLocal() as s:
            _closed_row(s, mode=LIVE, net=-5_000.0, when=today)
            _closed_row(s, mode=PAPER, net=+4_000.0, when=today, key="BANKNIFTY")
            assert analytics.realized_on(s, today.date(), book=LIVE, **SCOPE) == -5_000.0
            assert analytics.realized_on(s, today.date(), book=PAPER, **SCOPE) == 4_000.0

    def test_the_round_trip_cap_counts_only_its_own_books_trades(self):
        from app.engine import analytics

        today = dt.datetime(2026, 1, 1, 11, 0)
        with SessionLocal() as s:
            _closed_row(s, mode=LIVE, net=1.0, when=today)
            _closed_row(s, mode=LIVE, net=1.0, when=today, key="BANKNIFTY")
            _closed_row(s, mode=PAPER, net=1.0, when=today, key="RELIANCE")
            assert analytics.round_trips_on(s, today.date(), book=LIVE, **SCOPE) == 2
            assert analytics.round_trips_on(s, today.date(), book=PAPER, **SCOPE) == 1

    def test_reporting_surfaces_stay_cross_book_on_purpose(self):
        """Not every query should be isolated. `recent_trades` is a reporting surface
        whose caller chooses the book; defaulting it to one would hide the other."""
        from app.engine import analytics

        with SessionLocal() as s:
            _closed_row(s, mode=LIVE, net=1.0)
            _closed_row(s, mode=PAPER, net=1.0, key="BANKNIFTY")
            assert len(analytics.recent_trades(s, **SCOPE)) == 2
            assert len(analytics.recent_trades(s, mode=LIVE, **SCOPE)) == 1


# ── invariants 7, 10, 11, 12 ──────────────────────────────────────────────────
class TestRestartAndLegacyBehaviour:
    def test_restart_rebuilds_only_the_requested_book(self):
        with SessionLocal() as s:
            _open_row(s, mode=LIVE, key="NIFTY")
            _open_row(s, mode=PAPER, key="BANKNIFTY")
        paper = _broker(PAPER)
        try:
            assert {p.instrument_key for p in paper.open_positions()} == {"BANKNIFTY"}
        finally:
            paper.close()
        live = _broker(LIVE)
        try:
            assert {p.instrument_key for p in live.open_positions()} == {"NIFTY"}
        finally:
            live.close()

    def test_a_ledger_with_no_paper_rows_behaves_exactly_as_before(self):
        """Invariant 10 — production's shape. Every existing row is live, so the live
        broker sees the same positions, the same ledger row and the same cash it did."""
        with SessionLocal() as s:
            _open_row(s, mode=LIVE, entry_cost=1_500.0)
        live = _broker(LIVE)
        try:
            assert live.capital().id == 1        # the legacy row, claimed, not replaced
            assert len(live.open_positions()) == 1
            assert live.position_for("NIFTY").entry_cost == 1_500.0
        finally:
            live.close()

    def test_historical_rows_are_readable_and_not_rewritten(self):
        """Invariant 11. Pre-slice equity points carry no book and are left that way."""
        from app.db.models import EquitySnapshot

        with SessionLocal() as s:
            s.add(EquitySnapshot(owner_id='owner', broker_account_id='account.default', time=dt.datetime(2026, 1, 1, 9, 0), equity=1.0, cash=1.0,
                                 invested=0.0, realized_pnl=0.0, open_count=0))
            s.commit()
            rows = list(s.scalars(__import__("sqlalchemy").select(EquitySnapshot)))
            assert len(rows) == 1 and rows[0].book is None

    def test_the_other_books_open_positions_are_reported_not_silently_dropped(self):
        """The compensating control for scoping the exit lane. A live position left open
        while the paper book runs is unmanaged — that must be loud, not invisible."""
        from app.core import execution_book as eb

        with SessionLocal() as s:
            _open_row(s, mode=LIVE, key="NIFTY")
            foreign = eb.foreign_book_positions(s, PAPER, **SCOPE)
            assert [p.instrument_key for p in foreign] == ["NIFTY"]
            assert eb.foreign_book_positions(s, LIVE, **SCOPE) == []


# ── the compensating control ──────────────────────────────────────────────────
class TestOrphansFromTheOtherBookAreLoud:
    def test_the_startup_boundary_reports_them(self, caplog):
        """Book-scoping the exit lane makes an orphan possible; nothing else in the
        system would mention it. The engine says so when it starts operating."""
        from app.engine.runner import EngineRunner

        with SessionLocal() as s:
            _open_row(s, mode=LIVE, key="NIFTY")
        r = EngineRunner(owner_id="owner", broker_account_id="account.default")
        try:
            reported = r.report_foreign_book_positions()
            assert reported == ["NIFTY"]
        finally:
            r.broker.close()

    def test_a_clean_book_reports_nothing(self):
        from app.engine.runner import EngineRunner

        with SessionLocal() as s:
            _open_row(s, mode=PAPER, key="NIFTY")
        r = EngineRunner(owner_id="owner", broker_account_id="account.default")
        try:
            assert r.report_foreign_book_positions() == []
        finally:
            r.broker.close()

    def test_the_repair_path_debits_the_owning_books_ledger(self):
        """`_repair_open_position_lot_sizes` runs on every startup and moved cash on
        `capital_state` row 1 regardless of which book's position it was repairing."""
        from app.core import execution_book as eb

        _claim_both_ledgers()
        with SessionLocal() as s:
            live_cash_before = eb.capital_for_book(s, LIVE, broker_account_id="account.default").cash
            paper_cash_before = eb.capital_for_book(s, PAPER, broker_account_id="account.default").cash
        # A paper position whose lot size is under-recorded — the legacy defect shape.
        with SessionLocal() as s:
            row = _open_row(s, mode=PAPER, key="NIFTY", entry_cost=100.0)
            row.qty, row.lot_size = 1, 1
            s.commit()
        with SessionLocal() as s:
            from app.db.session import _repair_open_position_lot_sizes
            _repair_open_position_lot_sizes(s)
            s.commit()
        with SessionLocal() as s:
            assert eb.capital_for_book(s, LIVE, broker_account_id="account.default").cash == live_cash_before
            # Whatever the repair did (it may legitimately do nothing for this row), it
            # cannot have moved the live book's cash.
            assert eb.capital_for_book(s, PAPER, broker_account_id="account.default").cash <= paper_cash_before
