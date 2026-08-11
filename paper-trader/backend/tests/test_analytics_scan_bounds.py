"""A reporting query must not read the whole money record to return a page of it.

This is the second home of the defect that caused the 2026-07-23 outage. That
post-mortem fixed `equity_curve` and `signal_counts` — both had materialised entire
tables per call under a 5-second dashboard poll, at ~72k rows on the live VPS, and
`equity_curve`'s comment still records it. `recent_trades` sat 100 lines below with the
identical shape and was not fixed: it selected **every** `Trade` row, filtered in Python,
and applied `limit` with a list slice. The `limit` parameter did nothing at the database
level.

At 72 production trades that is invisible. It is a latent production-scale defect on the
exact path the outage taught about, and multi-user V1 multiplies the row count by the
user count, so it is fixed here rather than after the second outage.

Two proofs, and both are needed:

  * **Equivalence** — the SQL normalisation must be *exactly* the Python normalisation it
    replaces, including the legacy-NULL coalescing (`segment` → 'options',
    `strategy_key` → the default strategy). A reference implementation of the old
    behaviour lives in this file and every filter combination is compared against it.
    Without this the bound could be bought with a behaviour change.
  * **Boundedness** — the emitted SQL must carry a LIMIT and the session must materialise
    no more rows than were asked for. Asserting only on the returned list length would
    pass against the old code, which returned the right answer by over-reading.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import event, text

from app.core.execution_book import LIVE, PAPER
from app.db.models import Trade
from app.db.session import SessionLocal, init_db
from app.engine import analytics
from tests.legacy_money_scope import LegacyMoneyScope

analytics = LegacyMoneyScope(analytics, "recent_trades")
from app.strategy.registry import DEFAULT_STRATEGY_KEY

BASE = dt.datetime(2026, 8, 1, 10, 0, 0)


@pytest.fixture(scope="module", autouse=True)
def a_seeded_ledger():
    """Seeded ONCE for the module, not per test.

    Every test here is read-only, so a per-test `init_db(reset=True)` would buy nothing
    and cost 37 schema resets — each of which disposes the connection pool. That churn is
    not free in the full suite: it measurably raised pool pressure and tipped an unrelated
    test into `QueuePool limit ... connection timed out` while passing in isolation, which
    is precisely the pass-alone/fail-in-suite shape this repository has been bitten by
    before. Reset once, read many.
    """
    init_db(reset=True)
    _seed(40)
    yield


def _seed(n: int = 40) -> None:
    """A book with every shape the normalisation has to survive: both segments, both
    modes, an explicit strategy key, and the legacy NULLs that are the reason the
    filtering was in Python in the first place."""
    segments = ["options", "equity_intraday", None]
    strategies = ["expanding_z_v4", None]
    with SessionLocal() as s:
        for i in range(n):
            s.add(Trade(
                instrument_key=f"NSE:SYM{i % 5}",
                segment=segments[i % 3],
                strategy_key=strategies[i % 2],
                mode=LIVE if i % 4 == 0 else PAPER,
                direction="long",
                option_type="CE",
                tradingsymbol=f"SYM{i % 5}CE",
                exchange="NFO",
                strike=100.0,
                expiry=dt.date(2026, 8, 27),
                qty=1,
                entry_premium=100.0,
                entry_cost=100.0,
                entry_spot=1000.0,
                entry_time=BASE + dt.timedelta(minutes=i),
                exit_premium=101.0,
                exit_charges=0.1,
                exit_spot=1010.0,
                exit_time=BASE + dt.timedelta(minutes=i + 1),
                exit_reason="TARGET",
                gross_pnl=1.0,
                charges_total=0.1,
                net_pnl=0.9,
                return_pct=0.9,
                holding_minutes=1.0,
                win=True,
            ))
        s.commit()

    # Seeding the *unset* shapes needs care, and getting it wrong made an earlier version
    # of this file vacuous.
    #
    #   * `Trade(segment=None)` does NOT store NULL — the column carries a Python-side
    #     default of "options", so the ORM substitutes it and the legacy shape is never
    #     created. A mutation removing the segment normalisation stayed green against it.
    #   * `trades.segment` is NOT NULL in the schema, so NULL is unreachable there at all.
    #     The empty string is the only reachable unset segment, and it is exactly the case
    #     `COALESCE` alone gets wrong while Python's `or` gets right.
    #
    # So both unset shapes are written by direct SQL, bypassing the ORM default.
    with SessionLocal() as s:
        s.execute(text("UPDATE trades SET segment = '' WHERE id % 3 = 0"))
        s.execute(text("UPDATE trades SET strategy_key = '' WHERE id % 5 = 0"))
        s.commit()
        blank_seg = s.execute(
            text("SELECT COUNT(*) FROM trades WHERE segment = ''")).scalar_one()
        null_strat = s.execute(
            text("SELECT COUNT(*) FROM trades WHERE strategy_key IS NULL")).scalar_one()
        blank_strat = s.execute(
            text("SELECT COUNT(*) FROM trades WHERE strategy_key = ''")).scalar_one()
    # Without these the normalisation assertions below describe rows that do not exist.
    assert blank_seg > 0, "no empty-string segment seeded — normalisation coverage is vacuous"
    assert null_strat > 0, "no NULL strategy_key seeded — normalisation coverage is vacuous"
    assert blank_strat > 0, "no empty-string strategy_key seeded — normalisation coverage is vacuous"


# ── the reference: what the Python-side implementation did, preserved verbatim ──

def _reference(s, limit, mode=None, segment=None, strategy=None, since=None):
    from sqlalchemy import select
    q = select(Trade).order_by(Trade.exit_time.desc())
    if mode in ("paper", "live"):
        q = q.where(Trade.mode == mode)
    trades = list(s.scalars(q))
    if since is not None:
        cut = since.replace(tzinfo=None) if since.tzinfo else since
        trades = [t for t in trades if t.exit_time >= cut]
    if segment:
        trades = [t for t in trades if (t.segment or "options") == segment]
    if strategy:
        trades = [t for t in trades if (t.strategy_key or DEFAULT_STRATEGY_KEY) == strategy]
    return [t.to_dict() for t in trades[:limit]]


_COMBINATIONS = [
    dict(),
    dict(mode=LIVE),
    dict(mode=PAPER),
    dict(segment="options"),
    dict(segment="equity_intraday"),
    dict(strategy="expanding_z_v4"),
    dict(strategy=DEFAULT_STRATEGY_KEY),
    dict(segment="options", strategy=DEFAULT_STRATEGY_KEY),
    dict(mode=LIVE, segment="options"),
    dict(since=BASE + dt.timedelta(minutes=20)),
    dict(mode=PAPER, segment="equity_intraday", strategy="expanding_z_v4",
         since=BASE + dt.timedelta(minutes=5)),
]


@pytest.mark.parametrize("kwargs", _COMBINATIONS)
@pytest.mark.parametrize("limit", [1, 7, 500])
def test_sql_filtering_equals_the_python_filtering_it_replaces(kwargs, limit):
    """Every filter combination, including the legacy-NULL coalescing, must produce
    byte-identical output to the implementation that read the whole table."""
    with SessionLocal() as s:
        expected = _reference(s, limit, **kwargs)
    with SessionLocal() as s:
        actual = analytics.recent_trades(s, limit, **kwargs)
    assert actual == expected


def test_the_scan_is_bounded_by_the_limit():
    """The database must not be asked for more rows than the caller wants.

    Proven by counting the rows the driver actually returned, not by the length of the
    result — the old code returned the correct length while reading everything.
    """
    fetched: list[int] = []

    with SessionLocal() as s:
        conn = s.connection()

        @event.listens_for(conn, "after_cursor_execute")
        def _count(conn_, cursor, statement, parameters, context, executemany):
            if "FROM trades" in statement:
                fetched.append(len(cursor.fetchall()))

        analytics.recent_trades(s, 5)

    assert fetched, "no query against `trades` was observed — the probe is vacuous"
    assert max(fetched) <= 5, (
        f"read {max(fetched)} rows to return 5 — the limit is not reaching the database"
    )


def test_the_emitted_sql_carries_a_limit():
    """A direct statement-level guard, so the bound cannot regress into a Python slice."""
    statements: list[str] = []

    with SessionLocal() as s:
        conn = s.connection()

        @event.listens_for(conn, "after_cursor_execute")
        def _capture(conn_, cursor, statement, parameters, context, executemany):
            if "FROM trades" in statement:
                statements.append(statement)

        analytics.recent_trades(s, 3)

    assert statements, "no query against `trades` was observed — the probe is vacuous"
    assert all("LIMIT" in st.upper() for st in statements), statements


def _oracle_count(s, column: str, default: str, wanted: str) -> int:
    """How many rows `wanted` should match, computed in Python with the ORIGINAL
    truthiness semantics (`value or default`) over raw column bytes.

    Deliberately not expressed as SQL: an oracle written with the same COALESCE/NULLIF the
    implementation uses would agree with a wrong implementation. And it cannot read the
    serialised dicts either — `Trade.to_dict()` normalises `segment` itself, so an unset
    row is invisible downstream and an assertion over the output would be vacuous.
    """
    raw = s.execute(text(f"SELECT {column} FROM trades")).scalars().all()
    return sum(1 for v in raw if (v or default) == wanted)


def test_an_unset_segment_still_reads_as_options():
    """Pinned directly: the equivalence totals can stay green while this normalisation is
    wrong for a minority of rows."""
    with SessionLocal() as s:
        expected = _oracle_count(s, "segment", "options", "options")
        rows = analytics.recent_trades(s, 1000, segment="options")
    assert expected > 0, "oracle found no options rows — the seed is not exercising this"
    assert len(rows) == expected, (
        f"expected {expected} rows to normalise to 'options', got {len(rows)}"
    )


def test_an_unset_strategy_reads_as_the_default_strategy():
    """Both unset shapes — NULL and empty string — must match the default key."""
    with SessionLocal() as s:
        expected = _oracle_count(s, "strategy_key", DEFAULT_STRATEGY_KEY, DEFAULT_STRATEGY_KEY)
        rows = analytics.recent_trades(s, 1000, strategy=DEFAULT_STRATEGY_KEY)
    assert expected > 0, "oracle found no default-strategy rows — the seed is not exercising this"
    assert len(rows) == expected, (
        f"expected {expected} rows to normalise to the default strategy, got {len(rows)}"
    )
