"""Re-test priority — how research remembers failure without permanently banning it.

Decay lives HERE, on the hypothesis's priority, not on a Finding's confidence (a
well-powered negative stays a fact). A just-tested idea sits near the floor;
priority *rises* toward the cap as it goes stale, so markets evolving eventually
reopens it. A decisively-killed idea stays suppressed longer than a coin-flip kill.
The floor is strictly positive: nothing is ever permanently banned.
"""
from __future__ import annotations

import math


def retest_priority(*, days_since_test: float, kill_strength: float = 0.0,
                    regime_half_life_days: float = 270.0,
                    floor: float = 0.05, cap: float = 1.0) -> float:
    """`kill_strength` in [0,1] = how decisively the hypothesis was last rejected
    (0 = coin flip, 1 = crushed). `regime_half_life_days` ~ how fast the market
    regime turns over. Returns a priority in [floor, cap]."""
    staleness = 1.0 - math.exp(-max(0.0, days_since_test) / regime_half_life_days)
    base = floor + (cap - floor) * staleness
    suppression = 1.0 - 0.5 * min(max(kill_strength, 0.0), 1.0)
    return max(floor, min(cap, base * suppression))
