"""C1: a Settings override of stop_loss_pct/target_pct must reach NEW positions.

Before the fix, broker.open_position read the static get_settings() defaults
(0.35/0.60), so changing SL/TP in the Settings UI had no effect on new entries.
"""
import pytest

from app.db.session import init_db
from app.providers.mock import MockProvider
from app.engine.broker import PaperBroker
from app.core.instruments import get_instrument
from app.core.runtime_config import set_override, clear_override, effective


def _broker():
    init_db(reset=True)
    return PaperBroker(MockProvider())


def test_sltp_override_applies_to_new_entry():
    b = _broker()
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    q = chain.quotes[0]
    try:
        set_override("stop_loss_pct", "0.10")
        set_override("target_pct", "0.20")
        pos = b.open_position(inst, "LONG", q, "test", b.provider.now(), chain.spot)
        assert pos.stop_price == pytest.approx(q.ltp * 0.90)
        assert pos.target_price == pytest.approx(q.ltp * 1.20)
    finally:
        clear_override("stop_loss_pct")
        clear_override("target_pct")


def test_override_rejects_out_of_band_values():
    """H2: insane overrides (negative/inverted stop, busy-spin loop) are rejected
    with an error and never persisted, so a fixed C1 can't become a foot-gun."""
    init_db(reset=True)
    assert "error" in set_override("stop_loss_pct", "5.0")    # > 100% → negative stop
    assert "error" in set_override("stop_loss_pct", "0")      # zero stop
    assert "error" in set_override("target_pct", "-1")        # inverted target
    assert "error" in set_override("position_loop_seconds", "0")  # busy-spin
    assert "error" in set_override("max_stale_seconds", "-5")
    # rejected values must NOT be stored — effective() still shows the defaults
    eff = effective()
    assert eff["stop_loss_pct"] == 0.30
    assert eff["target_pct"] == 0.60


def test_override_accepts_in_band_values():
    """H2: sane overrides are accepted and applied."""
    init_db(reset=True)
    try:
        res = set_override("stop_loss_pct", "0.20")
        assert "error" not in res
        assert effective()["stop_loss_pct"] == pytest.approx(0.20)
    finally:
        clear_override("stop_loss_pct")


def test_sltp_default_when_no_override():
    b = _broker()
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    q = chain.quotes[0]
    pos = b.open_position(inst, "LONG", q, "test", b.provider.now(), chain.spot)
    # default -30% / +60%
    assert pos.stop_price == pytest.approx(q.ltp * 0.70)
    assert pos.target_price == pytest.approx(q.ltp * 1.60)
