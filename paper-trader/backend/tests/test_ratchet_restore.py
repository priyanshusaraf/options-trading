"""audit H2: RatchetState.restore rebuilds live ratchet state from persisted fields so
a restart continues the EXACT same ratchet (no re-derivation) — the parity property the
live-onto-backtest unification depends on."""
from app.backtest.ratchet import RatchetState

RM = {"atr_length": 14, "initial_risk_atr": 1.25, "trail_start_r": 1.75, "trail_atr": 3.0,
      "use_mfe_capture_floor": True, "capture_start_r": 1.25, "capture_pct": 0.35}
BARS = [(105, 100, 104), (110, 103, 109), (112, 107, 108), (111, 106, 107), (114, 109, 113)]


def test_restore_continues_the_identical_ratchet():
    atr = 2.0
    uninterrupted = RatchetState("LONG", 100.0, atr, RM)
    for h, l, c in BARS:
        uninterrupted.update(h, l, c, atr)

    mid = RatchetState("LONG", 100.0, atr, RM)
    for h, l, c in BARS[:2]:
        mid.update(h, l, c, atr)
    resumed = RatchetState.restore("LONG", 100.0, atr, RM, hw=mid.hw, stop=mid.stop)
    for h, l, c in BARS[2:]:
        resumed.update(h, l, c, atr)

    assert resumed.stop == uninterrupted.stop
    assert resumed.hw == uninterrupted.hw


def test_restore_preserves_the_stop_and_hw():
    rs = RatchetState.restore("SHORT", 100.0, 2.0, RM, hw=94.0, stop=97.0)
    assert rs.hw == 94.0 and rs.stop == 97.0 and rs.d == -1.0
