"""Backtest engine + metrics: the strategy must produce charged trades on a
realistic series, and the metric arithmetic (profit factor, drawdown, net) must
be exact. Net P&L is always gross minus the full charge stack."""
import pytest

from app.backtest.engine import backtest_qty, simulate
from app.backtest.metrics import BTTrade, compute_metrics
from app.core.instruments import get_instrument
from app.providers.mock import MockProvider


def _mk(net, t0, t1, direction="LONG"):
    return BTTrade(direction, t0, 100.0, t1, 100.0 + net, 1,
                   gross_pnl=net, charges=0.0, net_pnl=net, reason="X", bars_held=1)


def test_metrics_on_known_trades():
    trades = [_mk(100, 0, 86400), _mk(-50, 86400, 172800), _mk(200, 172800, 259200)]
    m = compute_metrics(trades, 50_000)
    assert (m.trades, m.wins, m.losses) == (3, 2, 1)
    assert m.net_pnl == 250
    assert m.profit_factor == pytest.approx((100 + 200) / 50)  # 6.0
    assert m.max_drawdown_abs == 50  # 50100 -> 50050
    assert m.win_rate == pytest.approx(100 * 2 / 3)


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
