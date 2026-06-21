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


def test_metrics_empty():
    m = compute_metrics([], 50_000)
    assert m.trades == 0 and m.profit_factor is None


def test_metrics_profit_factor_none_without_losses():
    m = compute_metrics([_mk(10, 0, 86400), _mk(20, 86400, 172800)], 50_000)
    assert m.profit_factor is None  # no losing trades -> undefined


def test_cash_equity_sizing_uses_capital():
    inst = get_instrument("NIFTY")
    # force the cash path by faking a cash segment via a stand-in
    class Cash:
        segment = "NSE_EQ"
        lot_size = 1
    assert backtest_qty(Cash(), price=2500.0, capital=50_000) == 20
    # F&O instrument always trades 1 lot
    assert backtest_qty(inst, price=24000.0, capital=50_000) == inst.lot_size


def test_simulate_charges_every_trade_and_nets():
    prov = MockProvider()
    inst = get_instrument("NIFTY")
    candles = prov.get_candles(inst, "15minute", 90)
    assert len(candles) > 60
    trades, m = simulate(candles, inst, "15minute", capital=50_000)
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
