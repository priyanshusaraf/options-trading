"""Direction-aware resolution of an owner SL/TP edit. A SHORT-equity position keeps
its stop ABOVE entry and target BELOW; long options/equity keep stop below / target
above. Pinned because the old long-only resolver inverted a short's percentages and
rejected a valid short config (stop above target)."""
from app.engine.equity_entry import resolve_sltp


def test_long_pct_geometry():
    stop, target, err = resolve_sltp(is_short=False, entry=100.0, cur_stop=70.0,
                                     cur_target=160.0, stop_pct=0.30, target_pct=0.60)
    assert err is None and stop == 70.0 and target == 160.0


def test_short_pct_geometry_inverts():
    # a SHORT: stop ABOVE entry, target BELOW
    stop, target, err = resolve_sltp(is_short=True, entry=100.0, cur_stop=101.0,
                                     cur_target=98.0, stop_pct=0.02, target_pct=0.05)
    assert err is None and stop == 102.0 and target == 95.0


def test_short_absolute_stop_above_target_is_accepted():
    # exactly the config the old long-only validation REJECTED
    stop, target, err = resolve_sltp(is_short=True, entry=100.0, cur_stop=101.0,
                                     cur_target=98.0, stop_price=104.0, target_price=95.0)
    assert err is None and stop == 104.0 and target == 95.0


def test_short_rejects_stop_below_target():
    _, _, err = resolve_sltp(is_short=True, entry=100.0, cur_stop=101.0, cur_target=98.0,
                             stop_price=95.0, target_price=104.0)
    assert err is not None


def test_long_rejects_inverted():
    _, _, err = resolve_sltp(is_short=False, entry=100.0, cur_stop=70.0, cur_target=160.0,
                             stop_price=900.0, target_price=100.0)
    assert err is not None


def test_omitted_side_keeps_current():
    stop, target, err = resolve_sltp(is_short=False, entry=100.0, cur_stop=70.0,
                                     cur_target=160.0, target_price=200.0)
    assert err is None and stop == 70.0 and target == 200.0
