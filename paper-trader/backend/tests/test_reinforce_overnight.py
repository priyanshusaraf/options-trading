"""Reinforcement ratchet + overnight-holding eligibility (recommended defaults)."""
import datetime as dt

from app.engine.exit_monitor import apply_reinforcement
from app.engine.overnight import overnight_decision

PARAMS = {
    "reinforce_enabled": True, "reinforce_min_profit_pct": 0.10, "reinforce_lock_pct": 0.05,
    "reinforce_extend_tp": True, "reinforce_tp_extend_pct": 0.20, "reinforce_tp_max_pct": 1.50,
    "reinforce_cooldown_minutes": 15.0, "max_reinforcements": 3,
    "overnight_enabled": True, "overnight_auto_pct": 0.10, "overnight_max_pct": 0.25,
    "overnight_min_reinforcements": 1, "overnight_min_days_to_expiry": 2,
    "block_overnight_into_weekend": False, "max_holding_days": 5,
}
NOW = dt.datetime(2026, 6, 19, 12, 0, 0)

# Owner's crude example: short via put bought at 300, -30% SL (210), +60% TP (480).
ENTRY, SL0, TP0 = 300.0, 210.0, 480.0


def test_reinforcement_matches_owner_example():
    # profitable (+20%), first reinforcement -> SL locks to 315, count 1
    r = apply_reinforcement(ENTRY, SL0, TP0, current_premium=360.0, count=0,
                            last_reinforce_time=None, now=NOW, params=PARAMS)
    assert r["applied"] is True
    assert r["stop_price"] == 315.0          # entry * 1.05 — exactly the owner's ₹315
    assert r["count"] == 1
    assert r["target_price"] == 540.0        # 480 + 0.20*300, under the +150% cap (750)


def test_reinforcement_min_profit_gate():
    r = apply_reinforcement(ENTRY, SL0, TP0, current_premium=315.0, count=0,  # only +5%
                            last_reinforce_time=None, now=NOW, params=PARAMS)
    assert r["applied"] is False and r["stop_price"] == SL0


def test_reinforcement_cooldown_and_cap():
    recent = NOW - dt.timedelta(minutes=5)
    r = apply_reinforcement(ENTRY, SL0, TP0, 360.0, 0, recent, NOW, PARAMS)
    assert r["applied"] is False and "cooldown" in r["reason"]
    r = apply_reinforcement(ENTRY, SL0, TP0, 360.0, 3, None, NOW, PARAMS)
    assert r["applied"] is False and "max" in r["reason"]


def test_reinforcement_never_loosens_stop():
    r = apply_reinforcement(ENTRY, 320.0, TP0, 360.0, 0, None, NOW, PARAMS)
    assert r["stop_price"] == 320.0          # already above the 315 floor -> preserved


def test_overnight_bands():
    cap = 50000.0
    # small (8%) -> auto
    keep, _ = overnight_decision(4000, cap, 0, 30, 1, False, PARAMS); assert keep
    # mid (12%) no reinforcement -> square off
    keep, why = overnight_decision(6000, cap, 0, 30, 1, False, PARAMS); assert not keep and "reinforcement" in why
    # mid (12%) reinforced -> hold
    keep, _ = overnight_decision(6000, cap, 1, 30, 1, False, PARAMS); assert keep
    # too big (28%) even reinforced -> square off
    keep, _ = overnight_decision(14000, cap, 3, 30, 1, False, PARAMS); assert not keep


def test_overnight_expiry_and_holding_caps():
    cap = 50000.0
    keep, why = overnight_decision(4000, cap, 0, 1, 1, False, PARAMS)   # expiry in 1d (<2)
    assert not keep and "expiry" in why
    keep, why = overnight_decision(4000, cap, 0, 30, 5, False, PARAMS)  # held 5 days
    assert not keep and "holding" in why
