"""audit H9: an out-of-sample split so a 1-lucky-trade / in-sample-only cell can't be
promoted. The sweep fits no parameters per cell, so the hazard is grid selection bias
(600 cells sorted by return); the OOS gate + the min_trades default raise close it."""
from app.backtest.metrics import BTTrade, oos_pass, split_metrics


def _t(entry_ts, net):
    return BTTrade(direction="LONG", entry_time=entry_ts, entry_price=100.0,
                   exit_time=entry_ts + 60, exit_price=100.0, qty=1, gross_pnl=net,
                   charges=0.0, net_pnl=net, reason="STRATEGY_EXIT", bars_held=1)


def test_split_partitions_by_entry_time():
    is_m, oos_m = split_metrics([_t(10, 5), _t(20, -3), _t(80, 7), _t(90, 4)],
                                100000.0, split_ts=50)
    assert is_m.trades == 2 and oos_m.trades == 2


def test_straddling_trade_counts_in_sample_by_entry():
    # opens before the split, exits after -> in-sample by entry time
    is_m, oos_m = split_metrics([_t(40, 5)], 100000.0, split_ts=50)
    assert is_m.trades == 1 and oos_m.trades == 0


def test_all_in_sample_fails_the_gate():
    _, oos_m = split_metrics([_t(10, 5), _t(20, 5)], 100000.0, split_ts=50)
    assert oos_m.trades == 0 and oos_pass(oos_m) is False


def test_oos_pass_requires_enough_positive_trades():
    _, oos = split_metrics([_t(60 + i, 5) for i in range(25)], 100000.0, split_ts=50)
    assert oos_pass(oos) is True
    _, oos_few = split_metrics([_t(60 + i, 5) for i in range(19)], 100000.0, split_ts=50)
    assert oos_pass(oos_few) is False                 # too few OOS trades
    _, oos_neg = split_metrics([_t(60 + i, -5) for i in range(25)], 100000.0, split_ts=50)
    assert oos_pass(oos_neg) is False                 # negative expectancy
