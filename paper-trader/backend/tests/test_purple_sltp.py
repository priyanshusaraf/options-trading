"""Purple-flagged intraday names get wider SL/TP (owner: 1.5%/3% vs 1%/2%
normal), frozen onto the position at entry so a mid-trade flag toggle can't
reshape an open trade."""
import datetime as dt
import inspect

import pytest

from app.core.config import Settings
from app.core.instruments import get_instrument
from app.db.session import SessionLocal, init_db
from app.engine.broker import PaperBroker


def test_purple_sltp_defaults_exist_and_are_wider_than_normal():
    s = Settings()
    assert s.intraday_purple_stop_loss_pct == 0.015
    assert s.intraday_purple_target_pct == 0.03
    assert s.intraday_purple_stop_loss_pct > s.intraday_stop_loss_pct
    assert s.intraday_purple_target_pct > s.intraday_target_pct


def _broker():
    init_db(reset=True)
    return PaperBroker(SessionLocal())


def _now():
    return dt.datetime(2026, 7, 17, 10, 0)


def test_purple_entry_gets_wider_band_and_persists_pcts():
    broker = _broker()
    pos = broker.open_equity_position(
        get_instrument("NIFTY"), "LONG", price=100.0, qty=200,
        charge_segment="NSE_INTRADAY", reason="test", now=_now(),
        sl_pct=0.015, tp_pct=0.03)
    assert pos.entry_sl_pct == 0.015
    assert pos.entry_tp_pct == 0.03
    assert pos.stop_price == pytest.approx(100.0 * 0.985, rel=1e-6)
    assert pos.target_price == pytest.approx(100.0 * 1.03, rel=1e-6)


def test_normal_entry_leaves_pcts_none_and_uses_global_defaults():
    broker = _broker()
    pos = broker.open_equity_position(
        get_instrument("NIFTY"), "LONG", price=100.0, qty=200,
        charge_segment="NSE_INTRADAY", reason="test", now=_now())  # legacy call shape
    assert pos.entry_sl_pct is None
    assert pos.entry_tp_pct is None
    assert pos.stop_price == pytest.approx(100.0 * 0.99, rel=1e-6)
    assert pos.target_price == pytest.approx(100.0 * 1.02, rel=1e-6)


def test_purple_short_band_is_direction_aware():
    broker = _broker()
    pos = broker.open_equity_position(
        get_instrument("NIFTY"), "SHORT", price=100.0, qty=200,
        charge_segment="NSE_INTRADAY", reason="test", now=_now(),
        sl_pct=0.015, tp_pct=0.03)
    # a SHORT's stop sits ABOVE entry and its target BELOW
    assert pos.stop_price == pytest.approx(100.0 * 1.015, rel=1e-6)
    assert pos.target_price == pytest.approx(100.0 * 0.97, rel=1e-6)


def test_live_broker_override_accepts_and_forwards_the_purple_pair():
    """The runner calls broker.open_equity_position — which IS LiveBroker in live
    mode. If the override doesn't accept sl_pct/tp_pct, every live intraday entry
    dies on TypeError; if it accepts but drops them, purple bands silently vanish
    live while passing every paper test."""
    from app.engine.live_broker import LiveBroker
    sig = inspect.signature(LiveBroker.open_equity_position)
    assert {"sl_pct", "tp_pct"} <= set(sig.parameters), \
        "LiveBroker.open_equity_position must accept the purple pair"
    src = inspect.getsource(LiveBroker.open_equity_position)
    assert "sl_pct=sl_pct" in src and "tp_pct=tp_pct" in src, \
        "LiveBroker must FORWARD the purple pair to PaperBroker, not swallow it"


def test_lockstep_uses_frozen_purple_pcts_not_global_defaults():
    """A purple position's ratchet must derive its initial band from the FROZEN
    entry_sl_pct/entry_tp_pct, not whatever the global intraday_stop_loss_pct
    happens to be right now — this is what makes a mid-trade flag toggle inert."""
    from app.engine.equity_entry import lockstep_band
    entry, qty, margin = 100.0, 10, 1000.0
    stop, target = lockstep_band(
        "LONG", entry, qty, margin, entry * 0.985, entry * 1.03, price=entry,
        trigger_pct=0.02, sl_pct=0.015, tp_pct=0.03,   # <- the FROZEN pair
        breakeven_price=entry)
    assert stop == pytest.approx(entry * 0.985, rel=1e-6)
    assert target == pytest.approx(entry * 1.03, rel=1e-6)


def test_apply_lockstep_prefers_frozen_pcts_over_changed_globals():
    """End-to-end: a purple position whose globals have since been retuned must
    still ratchet on its own frozen 1.5%/3% band."""
    from app.engine.runner import EngineRunner
    broker = _broker()
    pos = broker.open_equity_position(
        get_instrument("NIFTY"), "LONG", price=100.0, qty=200,
        charge_segment="NSE_INTRADAY", reason="test", now=_now(),
        sl_pct=0.015, tp_pct=0.03)
    pos.last_premium = 100.0

    r = EngineRunner(session=broker.s) if "session" in inspect.signature(
        EngineRunner.__init__).parameters else EngineRunner()
    r.broker = broker
    # globals retuned AFTER entry to something narrower — must be ignored for this row
    r.params = {"intraday_lockstep_enabled": True, "intraday_lockstep_trigger_pct": 0.02,
                "intraday_stop_loss_pct": 0.001, "intraday_target_pct": 0.002,
                "intraday_profit_lock_threshold": 200.0, "intraday_profit_lock_frac": 0.5}
    r._apply_lockstep(pos)
    # band unchanged at flat price, and still the FROZEN purple width (not 0.1%/0.2%)
    assert pos.stop_price == pytest.approx(100.0 * 0.985, rel=1e-6)
    assert pos.target_price == pytest.approx(100.0 * 1.03, rel=1e-6)
