"""
The best-value-for-money option picker.

Given a fired signal's direction it looks at the right side of the chain
(CE for long, PE for short) and:
  1. prices each contract — inverts IV from the LTP (Black-Scholes), derives delta
  2. applies the liquidity floor — open interest >= min_oi AND bid/ask spread
     <= max_spread_pct of premium (so paper fills are realistic, not phantom
     fills on a contract nobody trades)
  3. among survivors keeps those with |delta| inside the target band
     (default 0.35..0.65) and picks the one whose |delta| is closest to the
     target (default 0.50) — balancing directional punch against premium cost

It always returns the full evaluated candidate table (for the Options-Calc view)
and a human-readable reason, even when nothing qualifies (instrument skipped).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time

from app.options.pricing import bs_delta, implied_vol
from app.providers.base import OptionChain, OptionQuote


@dataclass
class PickResult:
    chosen: OptionQuote | None
    candidates: list[dict] = field(default_factory=list)
    reason: str = ""


def _years_to_expiry(expiry, now: datetime) -> float:
    expiry_dt = datetime.combine(expiry, time(15, 30))
    return max((expiry_dt - now).total_seconds() / (365 * 86400), 0.5 / 365)


def pick_option(chain: OptionChain, direction: str, settings, now: datetime) -> PickResult:
    flag, otype = ("c", "CE") if direction == "LONG" else ("p", "PE")
    r = settings.risk_free_rate
    spot = chain.spot
    T = _years_to_expiry(chain.expiry, now)

    candidates: list[dict] = []
    best: tuple[float, OptionQuote] | None = None  # (distance-to-target, quote)

    for q in chain.quotes:
        if q.option_type != otype:
            continue
        iv = implied_vol(q.ltp, spot, q.strike, T, r, flag)
        delta = bs_delta(spot, q.strike, T, r, iv, flag) if iv else None
        q.iv, q.delta = iv, delta

        liquid = (q.oi >= settings.min_oi
                  and q.ltp > 0
                  and q.spread_pct <= settings.max_spread_pct
                  and iv is not None)
        in_band = (delta is not None
                   and settings.delta_low <= abs(delta) <= settings.delta_high)
        eligible = liquid and in_band

        candidates.append({
            "tradingsymbol": q.tradingsymbol,
            "strike": q.strike,
            "option_type": q.option_type,
            "ltp": round(q.ltp, 2),
            "oi": q.oi,
            "spread_pct": round(q.spread_pct, 4),
            "iv": round(iv, 4) if iv else None,
            "delta": round(delta, 4) if delta is not None else None,
            "passed_liquidity": bool(liquid),
            "in_delta_band": bool(in_band),
            "eligible": bool(eligible),
        })

        if eligible:
            dist = abs(abs(delta) - settings.target_delta)
            if best is None or dist < best[0]:
                best = (dist, q)

    if best is None:
        n_side = sum(1 for c in candidates)
        n_liquid = sum(1 for c in candidates if c["passed_liquidity"])
        reason = (f"no {otype} contract passed liquidity+delta filters "
                  f"({n_liquid}/{n_side} liquid; need OI>={settings.min_oi}, "
                  f"spread<={settings.max_spread_pct:.0%}, "
                  f"|delta| in {settings.delta_low:.2f}-{settings.delta_high:.2f})")
        return PickResult(chosen=None, candidates=candidates, reason=reason)

    chosen = best[1]
    reason = (f"{chosen.tradingsymbol}: delta {chosen.delta:+.2f} closest to "
              f"target {settings.target_delta:.2f}; OI {chosen.oi}, "
              f"spread {chosen.spread_pct:.1%}, IV {chosen.iv:.0%}, "
              f"premium {chosen.ltp:.2f}")
    return PickResult(chosen=chosen, candidates=candidates, reason=reason)
