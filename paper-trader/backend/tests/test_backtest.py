"""Backtest engine + metrics: the strategy must produce charged trades on a
realistic series, and the metric arithmetic (profit factor, drawdown, net) must
be exact. Net P&L is always gross minus the full charge stack."""
import pytest

from app.backtest.engine import backtest_qty, simulate
from app.backtest.metrics import BTTrade, compute_metrics
from app.core.instruments import get_instrument
from app.providers.mock import MockProvider


def _mk(net, t0, t1, direction="LONG", entry=1000.0):
    # entry×qty is the notional the return% is measured against
    return BTTrade(direction, t0, entry, t1, entry + net, 1,
                   gross_pnl=net, charges=0.0, net_pnl=net, reason="X", bars_held=1)


def test_metrics_compound_return_on_notional():
    # notional 1000 each; nets +50 (+5%), -20 (-2%), +100 (+10%)
    trades = [_mk(50, 0, 86400), _mk(-20, 86400, 172800), _mk(100, 172800, 259200)]
    m = compute_metrics(trades, 100_000)
    assert (m.trades, m.wins, m.losses) == (3, 2, 1)
    assert m.net_pnl == 130                                   # raw rupees unchanged
    assert m.profit_factor == pytest.approx(150 / 20)         # 7.5
    # compounding 1.05 × 0.98 × 1.10 − 1 = 13.19%
    assert m.return_pct == pytest.approx((1.05 * 0.98 * 1.10 - 1) * 100, abs=0.01)
    # drawdown: peak after +5%, dips to +2.9% -> 2% peak-to-trough on the % curve
    assert m.max_drawdown_pct == pytest.approx(2.0, abs=0.01)
    assert m.win_rate == pytest.approx(100 * 2 / 3)


def test_return_pct_is_honest_and_anchor_independent():
    # one NIFTY-sized lot: notional ≈ ₹18L, net +₹54k = a +3% underlying move —
    # must read ~+3%, NOT the old +108% (54k/50k), and must not depend on the anchor.
    t = BTTrade("LONG", 0, 24000.0, 86400, 24720.0, 75,
                gross_pnl=54_000, charges=0.0, net_pnl=54_000, reason="X", bars_held=1)
    m1 = compute_metrics([t], 50_000)
    m2 = compute_metrics([t], 100_000)
    assert m1.return_pct == pytest.approx(m2.return_pct, abs=0.001)        # anchor-independent
    assert m1.return_pct == pytest.approx(54_000 / (24000 * 75) * 100, abs=0.01)  # ≈ +3%
    assert m1.return_pct < 5                                               # not the ₹50k-base fiction


def test_smoothness_metrics_basic():
    # +5%, -2%, +10% on notional 1000 each
    trades = [_mk(50, 0, 86400), _mk(-20, 86400, 172800), _mk(100, 172800, 259200)]
    m = compute_metrics(trades, 100_000)
    assert m.max_consec_losses == 1                 # one isolated loser
    assert 0 < m.time_underwater_pct < 100          # dips, then recovers to new highs
    assert m.consistency is not None                # 3 trades -> defined
    d = m.to_dict()
    assert d["max_consec_losses"] == 1 and "time_underwater_pct" in d


def test_max_consecutive_losses_streak():
    trades = [_mk(50, 0, 1), _mk(-10, 1, 2), _mk(-10, 2, 3), _mk(-10, 3, 4), _mk(20, 4, 5)]
    m = compute_metrics(trades, 100_000)
    assert m.max_consec_losses == 3                 # the 3-in-a-row run, not the lone first win


def test_metrics_empty():
    m = compute_metrics([], 50_000)
    assert m.trades == 0 and m.profit_factor is None
    assert m.max_consec_losses == 0 and m.calmar is None and m.consistency is None


def test_metrics_profit_factor_none_without_losses():
    m = compute_metrics([_mk(10, 0, 86400), _mk(20, 86400, 172800)], 50_000)
    assert m.profit_factor is None  # no losing trades -> undefined


def test_cash_equity_sizing_uses_capital():
    # force the cash path by faking a cash segment via a stand-in
    class Cash:
        segment = "NSE_EQ"
        lot_size = 1
    assert backtest_qty(Cash(), price=2500.0, capital=50_000) == 20
    # whole shares only, capped by capital (no leverage)
    assert backtest_qty(Cash(), price=2500.0, capital=49_999) == 19


def test_backtest_qty_affordable_lots():
    # BANKNIFTY: lot 35. At 52,000 one lot's notional is 52000×35 = 1.82M.
    class BN:
        segment = "NFO"
        lot_size = 35
    # ₹50k cannot afford even one lot of a ₹1.82M position -> 0 (unaffordable)
    assert backtest_qty(BN(), price=52_000.0, capital=50_000) == 0
    # exactly one lot fits inside ₹2.5M (1.82M), but two (3.64M) do not -> 35
    assert backtest_qty(BN(), price=52_000.0, capital=2_500_000) == 35
    # 4M affords two whole lots (3.64M) but not three (5.46M) -> 70, whole-lot multiple
    q = backtest_qty(BN(), price=52_000.0, capital=4_000_000)
    assert q == 70 and q % 35 == 0
    # never exceeds capital (no leverage): notional of the sized position fits
    assert 52_000.0 * q <= 4_000_000


def test_unaffordable_instrument_is_flagged_not_silently_one_lot():
    # an F&O instrument whose single lot already costs more than the capital must
    # be reported as a DISTINCT unaffordable result (lots=0, affordable=False),
    # NOT silently sized to one lot.
    prov = MockProvider()
    inst = get_instrument("BANKNIFTY")          # mock_spot 52000, lot 35 -> ~1.82M/lot
    candles = prov.get_candles(inst, "15minute", 90)
    trades, m = simulate(candles, inst, "15minute", capital=50_000)
    assert trades == []                          # nothing was traded at this size
    assert m.affordable is False and m.lots == 0
    assert m.notional > 50_000                    # one lot's notional, the thing that didn't fit
    d = m.to_dict()
    assert d["affordable"] is False and d["lots"] == 0
    # with enough capital the SAME instrument becomes tradable (affordable=True)
    trades2, m2 = simulate(candles, inst, "15minute", capital=3_000_000)
    assert m2.affordable is True and m2.lots >= 1


def test_simulate_charges_every_trade_and_nets():
    prov = MockProvider()
    inst = get_instrument("NIFTY")
    candles = prov.get_candles(inst, "15minute", 90)
    assert len(candles) > 60
    # NIFTY lot 75 @ ~24,000 = ~₹1.8M/lot; give the backtest enough capital so the
    # instrument is affordable and trades actually fire (honest sizing).
    trades, m = simulate(candles, inst, "15minute", capital=5_000_000)
    assert m.affordable is True
    assert m.trades == len(trades)
    for t in trades:
        assert t.charges > 0                       # full charge stack applied
        assert t.net_pnl == pytest.approx(t.gross_pnl - t.charges, abs=0.01)
    if trades:
        assert m.net_pnl == pytest.approx(sum(t.net_pnl for t in trades), abs=0.1)
        assert 0 <= m.win_rate <= 100
        assert m.max_drawdown_pct >= 0
        # net must be strictly worse than gross because charges are real
        assert m.net_pnl < m.gross_pnl


def test_open_at_end_is_separable():
    # two realised winners + one favourable OPEN_AT_END trade. The realised win
    # rate must EXCLUDE the open trade and differ from the blended figure when the
    # open trade changes the picture.
    realised_loss = BTTrade("LONG", 0, 1000.0, 86400, 980.0, 1,
                            gross_pnl=-20, charges=0.0, net_pnl=-20,
                            reason="STRATEGY_EXIT", bars_held=1)
    realised_win = BTTrade("LONG", 86400, 1000.0, 172800, 1050.0, 1,
                           gross_pnl=50, charges=0.0, net_pnl=50,
                           reason="STRATEGY_EXIT", bars_held=1)
    open_win = BTTrade("LONG", 172800, 1000.0, 259200, 1100.0, 1,
                       gross_pnl=100, charges=0.0, net_pnl=100,
                       reason="OPEN_AT_END", bars_held=1)
    m = compute_metrics([realised_loss, realised_win, open_win], 100_000)
    d = m.to_dict()
    assert d["open_at_end"] is True
    assert m.trades_realised == 2
    # blended win rate = 2/3 ≈ 66.7; realised (excl. the favourable open) = 1/2 = 50
    assert m.win_rate == pytest.approx(100 * 2 / 3)
    assert m.win_rate_realised == pytest.approx(50.0)
    assert m.win_rate_realised != pytest.approx(m.win_rate)
    # realised return excludes the +10% open trade -> strictly below the blended one
    assert m.return_pct_realised < m.return_pct


def test_buy_and_hold_from_same_candles():
    # a known monotonic up series: buy-and-hold = last/first - 1, from the SAME
    # clipped candles the strategy used.
    from app.providers.base import Candle
    import datetime as dt
    base = dt.datetime(2025, 1, 1, 9, 15)
    closes = [100.0 + i for i in range(120)]   # 100 -> 219, strictly increasing
    candles = [Candle(ts=base + dt.timedelta(minutes=15 * i),
                      open=c, high=c + 1, low=c - 1, close=c, volume=1000.0)
               for i, c in enumerate(closes)]

    class Cash:
        segment = "NSE_EQ"
        lot_size = 1
    _, m = simulate(candles, Cash(), "15minute", capital=1_000_000)
    expected = (closes[-1] / closes[0] - 1.0) * 100.0
    assert m.bh_return_pct == pytest.approx(expected, abs=1e-6)
    assert m.to_dict()["bh_return_pct"] == pytest.approx(round(expected, 2), abs=0.01)


def test_annualised_sharpe_scales_with_frequency():
    # identical per-trade mean/std, but one set is packed into a shorter span
    # (higher trade frequency) -> higher annualised Sharpe, same consistency.
    def _ret(net, t0, t1):
        return BTTrade("LONG", t0, 1000.0, t1, 1000.0 + net, 1,
                       gross_pnl=net, charges=0.0, net_pnl=net,
                       reason="STRATEGY_EXIT", bars_held=1)
    nets = [50, -20, 60, -10, 40, -30]
    day = 86400
    # slow: trades spread over ~2 years
    slow = [_ret(n, i * 120 * day, i * 120 * day + day) for i, n in enumerate(nets)]
    # fast: identical nets spread over ~30 days
    fast = [_ret(n, i * 6 * day, i * 6 * day + day) for i, n in enumerate(nets)]
    ms, mf = compute_metrics(slow, 100_000), compute_metrics(fast, 100_000)
    # consistency (per-trade mean/std) is frequency-independent -> identical
    assert ms.consistency == pytest.approx(mf.consistency, abs=1e-9)
    # annualised Sharpe scales with √(trades/year): the packed set is higher
    assert ms.sharpe is not None and mf.sharpe is not None
    assert mf.sharpe > ms.sharpe
    assert "sharpe" in mf.to_dict()


def test_worst_trade_pnl_surfaced():
    trades = [_mk(50, 0, 1), _mk(-30, 1, 2), _mk(-120, 2, 3), _mk(-45, 3, 4), _mk(80, 4, 5)]
    m = compute_metrics(trades, 100_000)
    assert m.worst_trade_pnl == -120          # the single most-negative net P&L
    assert m.to_dict()["worst_trade_pnl"] == -120


def test_intra_trade_mae_detected():
    # A LONG that dips hard intra-trade (bar low far below entry) must register a
    # positive Maximum Adverse Excursion even though the bar CLOSE is flat — the
    # close-to-close drawdown would miss this. Test the MAE updater directly so it
    # is independent of signal timing.
    from app.backtest.engine import _update_mae
    pos = {"direction": "LONG", "entry_price": 100.0, "mae_pct": 0.0}
    # bar closes at entry but its low plunged to 80 -> 20% adverse excursion
    _update_mae(pos, {"high": 101.0, "low": 80.0})
    assert pos["mae_pct"] == pytest.approx(20.0)
    # a later, milder bar must NOT shrink the running worst
    _update_mae(pos, {"high": 102.0, "low": 95.0})
    assert pos["mae_pct"] == pytest.approx(20.0)
    # SHORT: the adverse direction is the HIGH
    short = {"direction": "SHORT", "entry_price": 100.0, "mae_pct": 0.0}
    _update_mae(short, {"high": 130.0, "low": 99.0})
    assert short["mae_pct"] == pytest.approx(30.0)
    # the metric surfaces worst_mae_pct as the max across trades
    t1 = BTTrade("LONG", 0, 100.0, 1, 100.0, 1, gross_pnl=0.0, charges=0.0,
                 net_pnl=0.0, reason="STRATEGY_EXIT", bars_held=1, mae_pct=20.0)
    t2 = BTTrade("LONG", 1, 100.0, 2, 105.0, 1, gross_pnl=5.0, charges=0.0,
                 net_pnl=5.0, reason="STRATEGY_EXIT", bars_held=1, mae_pct=8.0)
    m = compute_metrics([t1, t2], 100_000)
    # close-to-close DD is ~0 (both trades net >= 0) yet MAE flags real pain
    assert m.worst_mae_pct == pytest.approx(20.0)
    assert m.max_drawdown_pct == pytest.approx(0.0, abs=0.01)
