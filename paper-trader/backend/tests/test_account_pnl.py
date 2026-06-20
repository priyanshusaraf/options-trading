"""Bot-vs-you P&L split. On the shared real account, the bot's P&L is tracked
exactly; everything else (your own discretionary trades + deposits/withdrawals) is
the 'unrecorded' remainder = account change since baseline − bot P&L."""
from app.engine.analytics import bot_vs_you


def test_split_separates_bot_from_your_trades():
    r = bot_vs_you(account_equity_now=110000, account_baseline=100000,
                   bot_realized=3000, bot_unrealized=500)
    assert r["available"] is True
    assert r["account_change"] == 10000
    assert r["bot_pnl"] == 3500
    assert r["your_pnl_unrecorded"] == 6500     # 10000 account change − 3500 bot


def test_negative_account_change_attributed_correctly():
    r = bot_vs_you(95000, 100000, -1000, 0)     # account down 5k, bot lost 1k
    assert r["your_pnl_unrecorded"] == -4000    # your own trades account for -4k


def test_unavailable_without_a_live_baseline():
    assert bot_vs_you(110000, None, 0, 0)["available"] is False
    assert bot_vs_you(None, 100000, 0, 0)["available"] is False
