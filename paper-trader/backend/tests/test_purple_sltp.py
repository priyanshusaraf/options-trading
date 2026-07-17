"""Purple-flagged intraday names get wider SL/TP (owner: 1.5%/3% vs 1%/2%
normal), frozen onto the position at entry so a mid-trade flag toggle can't
reshape an open trade."""
from app.core.config import Settings


def test_purple_sltp_defaults_exist_and_are_wider_than_normal():
    s = Settings()
    assert s.intraday_purple_stop_loss_pct == 0.015
    assert s.intraday_purple_target_pct == 0.03
    assert s.intraday_purple_stop_loss_pct > s.intraday_stop_loss_pct
    assert s.intraday_purple_target_pct > s.intraday_target_pct
