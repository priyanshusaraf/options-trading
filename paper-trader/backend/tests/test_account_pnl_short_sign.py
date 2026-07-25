"""E8 — `account_pnl` must not use a LONG-only unrealized formula.

It computed `(last - entry) * qty` for every open position, which INVERTS the sign of
an open equity SHORT, so the bot-vs-you dashboard split showed a winning short as a
loss (and mis-attributed the difference to the owner's own trades). `Position` already
has the direction-aware `unrealized_pnl()`; the duplicate formula must defer to it.
"""
from app.core.instruments import get_instrument
from app.db.session import init_db, SessionLocal
from app.engine.analytics import account_pnl
from app.engine.runner import EngineRunner


class FakeKite:
    """`account_pnl` only computes the split for the live Kite provider."""
    name = "kite"

    def account_equity(self):
        return 100_000.0


def _short_in_profit():
    init_db(reset=True)
    r = EngineRunner()
    pos = r.broker.open_equity_position(get_instrument("NIFTY"), "SHORT", 100.0, 10,
                                        "NSE_INTRADAY", "t", r.provider.now(), params={})
    pos.last_premium = 95.0        # price FELL 5 → a short is up 5 × 10 = +50
    r.broker.commit()
    return pos


def test_a_winning_equity_short_reads_as_a_profit():
    pos = _short_in_profit()
    assert pos.unrealized_pnl() == 50.0        # the direction-aware truth

    with SessionLocal() as s:
        res = account_pnl(s, FakeKite())

    assert res["available"] is True
    assert res["bot_pnl"] == 50.0, (
        f"short's unrealized P&L is sign-inverted in the account split: {res}")


def test_a_long_is_unaffected():
    """Guard against fixing the short by breaking the long."""
    init_db(reset=True)
    r = EngineRunner()
    pos = r.broker.open_equity_position(get_instrument("NIFTY"), "LONG", 100.0, 10,
                                        "NSE_INTRADAY", "t", r.provider.now(), params={})
    pos.last_premium = 105.0                   # price rose 5 → a long is up +50
    r.broker.commit()

    with SessionLocal() as s:
        res = account_pnl(s, FakeKite())

    assert res["bot_pnl"] == 50.0, res
