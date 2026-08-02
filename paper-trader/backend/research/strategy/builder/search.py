"""Bounded, deterministic composition generator — the bot proposing its own strategies.

The space is deliberately small and economically constrained (the anti-overfitting
principle): a directional TREND gate ANDed with a MOMENTUM trigger for entry, an optional
VOLATILITY quiet-bar gate, and mirrored short logic with reversion/trend-flip exits. Only
sensible pairings are enumerated — the generator never bolts arbitrary blocks together.

Every composition is constructed through `Composition.from_dict`, so it is grammar-valid
by the time it is returned, and `build_strategy` (emit → AST-validate → sandbox) is the
final proof it is safe to run.

DEFLATION — corrected 2026-08-01. This paragraph used to claim that the trial count
(compositions × folds) "feeds the Deflated Sharpe deflation downstream, so a wider search
*raises* the significance bar rather than manufacturing a winner." That was FALSE for as
long as it was written. `n_trials` was threaded through, but `var_sr` — the dispersion of
the trial Sharpes — never was, and `expected_max_sharpe()` returns exactly 0 whenever
var_sr is 0. The benchmark sat at zero on every candidate the lab ever scored, the DSR
degraded to a PSR against zero, and widening the search moved the bar not at all.

`OptimizationResult.var_sr` now computes it and the orchestrator passes it, so the claim
above is true as of `research/pipeline/optimize.py`. Note it holds only for the OPTIMIZE
path: single-pass validation searches nothing, so n_trials=1 and there is no selection to
deflate. If you widen this search, check the logged `var_sr` and `SR0` actually move —
a claim in a docstring is not a mechanism.
"""
from __future__ import annotations

import random

from research.strategy.builder.blocks import BLOCKS, PRICE_SOURCES, SMOOTHINGS
from research.strategy.builder.grammar import Composition

# Each entry: (long_trend, short_trend) mirror pair, keyed by a short code.
_TREND = {
    "emaSlope30": ("ema_slope_up(30, 5)", "ema_slope_down(30, 5)"),
    "emaSlope50": ("ema_slope_up(50, 5)", "ema_slope_down(50, 5)"),
    "priceEma50": ("price_above_ema(50)", "price_below_ema(50)"),
}
_MOMENTUM = {
    "zx10": ("zscore_cross_up(50, 1.0)", "zscore_cross_down(50, 1.0)"),
    "zx15": ("zscore_cross_up(50, 1.5)", "zscore_cross_down(50, 1.5)"),
    "roc10": ("roc_gt(10, 0.0)", "roc_lt(10, 0.0)"),
}
_VOL = {
    "": None,
    "quiet": "range_atr_lt(14, 2.5)",
}
# exits are shared: revert through the EMA (z back through 0) OR the trend flips
_LONG_EXIT = ["zscore_lt(50, 0.0)", "ema_slope_down(50, 5)"]
_SHORT_EXIT = ["zscore_gt(50, 0.0)", "ema_slope_up(50, 5)"]


def enumerate_compositions(limit: int = 24) -> list[Composition]:
    """Return up to `limit` grammar-valid compositions in a stable, deterministic order."""
    out: list[Composition] = []
    for tcode, (t_up, t_dn) in _TREND.items():
        for mcode, (m_up, m_dn) in _MOMENTUM.items():
            for vcode, vgate in _VOL.items():
                long_entry = [t_up, m_up] + ([vgate] if vgate else [])
                short_entry = [t_dn, m_dn] + ([vgate] if vgate else [])
                key = f"gen_{tcode}_{mcode}" + (f"_{vcode}" if vcode else "")
                out.append(Composition.from_dict({
                    "key": key,
                    "longEntry": {"all": long_entry},
                    "shortEntry": {"all": short_entry},
                    "longExit": {"any": list(_LONG_EXIT)},
                    "shortExit": {"any": list(_SHORT_EXIT)},
                }))
                if len(out) >= limit:
                    return out
    return out


# ── seeded sampling (Phase 2) ────────────────────────────────────────────────
# The grid above is a fixed 3x3x2 of hand-picked strings, so adding a block to
# BLOCKS widened the whitelist and the search not at all — the RSI family was
# registered and never sampled.
#
# CORRECTED 2026-08-02. This comment used to continue: "Sampling draws from the
# registry itself, which is what makes a new block reachable the moment it is
# registered." That was false the day it was written, and stayed false. The draw
# functions below are still hand-written string templates; they are simply a wider
# set of them. Measured across 200 seeds, SEVEN of twenty-three registered blocks
# were unreachable, four of them dead since the day they landed.
#
# Registering a block does NOT make it reachable. Wiring it into `_mirror_trend`,
# `_mirror_momentum` or `_filter` does. `research_tests/test_every_block_is_reachable.py`
# now fails the build on the next one, which is what makes this paragraph safe to
# write down — a docstring asserting a property is not the property.
#
# DETERMINISTIC per seed, without exception: a composition that cannot be
# regenerated from its seed cannot be reproduced, and reproducibility is the
# premise the whole plane rests on (immutable specs, content-hashed datasets).
# Widening the draw changes WHAT a seed produces, and that is fine: a past finding
# replays from the `composition_json` + `source` stored against its strategy key,
# not by re-running the sampler.

_LENGTH_CHOICES = (10, 14, 20, 30, 50, 100)
_Z_THRESHOLDS = (0.5, 1.0, 1.5, 2.0)
_RSI_HI = (55.0, 60.0, 65.0, 70.0)
_RSI_LO = (30.0, 35.0, 40.0, 45.0)


def _mirror_trend(rng) -> tuple:
    n = rng.choice(_LENGTH_CHOICES)
    if rng.random() < 0.5:
        return f"ema_slope_up({n}, 5)", f"ema_slope_down({n}, 5)", f"emaSlope{n}"
    return f"price_above_ema({n})", f"price_below_ema({n})", f"priceEma{n}"


def _mirror_momentum(rng) -> tuple:
    """A directional trigger and its short mirror.

    Every arm must be a genuine MIRROR pair. A long/short asymmetry here does not
    fail loudly — it produces a composition that trades one side well and the other
    by accident, which reads as a mediocre edge rather than as a bug.
    """
    pick = rng.random()
    if pick < 0.30:
        thr = rng.choice(_Z_THRESHOLDS)
        n = rng.choice((20, 50, 100))
        return (f"zscore_cross_up({n}, {thr})", f"zscore_cross_down({n}, {thr})",
                f"zx{int(thr * 10)}n{n}")
    if pick < 0.50:
        n = rng.choice((5, 10, 20))
        return f"roc_gt({n}, 0.0)", f"roc_lt({n}, 0.0)", f"roc{n}"
    if pick < 0.70:
        # The Phase-2 family: one RSI block, but source and smoothing are drawn, so
        # a single grammar slot covers len(PRICE_SOURCES) x len(SMOOTHINGS) variants.
        n = rng.choice((7, 14, 21))
        hi, lo = rng.choice(_RSI_HI), rng.choice(_RSI_LO)
        src = rng.randrange(len(PRICE_SOURCES))
        sm = rng.randrange(len(SMOOTHINGS))
        return (f"rsi_gt({n}, {hi}, {src}, {sm})", f"rsi_lt({n}, {lo}, {src}, {sm})",
                f"rsi{n}{PRICE_SOURCES[src][:2]}{SMOOTHINGS[sm][:1]}")
    if pick < 0.85:
        # Session-aware trigger: break out of the day's own opening range. This is
        # the first draw in the search whose meaning depends on where a session
        # STARTS rather than on bar math alone.
        bars = rng.choice((2, 3, 4, 6))
        buf = rng.choice((0.05, 0.1, 0.25))
        return (f"opening_range_break_up({bars}, {buf})",
                f"opening_range_break_down({bars}, {buf})", f"orb{bars}")
    # Overnight gap as the trigger. Mirrored, and deliberately last: a gap fires on
    # far fewer bars than the other arms, so it draws thinner samples.
    pct = rng.choice((0.3, 0.5, 1.0))
    return f"gap_up_pct({pct})", f"gap_down_pct({pct})", f"gap{int(pct * 10)}"


def _filter(rng) -> tuple:
    """A NON-directional gate, applied identically to the long and short arms.

    Anything drawn here must be direction-neutral. A directional block in this slot
    would be ANDed into both entries and silently disable one of them.
    """
    pick = rng.random()
    if pick < 0.12:
        # Regime conditioning: "only trade this idea in THIS kind of market".
        # Drawing it here means the composition count already reflects it, and
        # `run_generated` additionally inflates the deflation count because
        # choosing WHICH regime is itself a selection over four.
        from research.regime import REGIMES
        code = rng.randrange(len(REGIMES))
        return f"regime_is({code})", f"rg{code}"
    if pick < 0.40:
        return None, ""
    if pick < 0.52:
        return "range_atr_lt(14, 2.5)", "quiet"
    if pick < 0.62:
        # Absolute volatility ceiling, as opposed to range_atr_lt's relative one.
        return f"atr_pct_lt(14, {rng.choice((1.5, 3.0, 5.0))})", "calm"
    if pick < 0.74 and "volume_surge" in BLOCKS:
        return f"volume_surge(20, {rng.choice((1.5, 2.0))})", "vol"
    if pick < 0.84:
        # Time-of-day window. Drawn from real NSE session segments rather than
        # arbitrary minutes: 09:15-11:30 (the morning trend), 11:30-14:00 (the
        # midday lull), 09:15-15:00 (everything but the square-off run-in).
        start, end, code = rng.choice((
            (555, 690, "am"), (690, 840, "mid"), (555, 900, "day")))
        return f"time_of_day({start}, {end})", code
    if pick < 0.92:
        return f"still_expanding_z({rng.choice((20, 50))})", "expand"
    return f"body_frac_gt({rng.choice((0.4, 0.5, 0.6))})", "body"


def _accepts(refs, weights: dict, rng) -> bool:
    """Rejection-sample a drawn composition against the edge map's weights.

    Suppression only ever says NO. This is the other half: a family that has
    actually worked on this universe gets drawn more often. Without it the loop
    can avoid what fails but never pursue what succeeds, which is half a
    reinforcement loop.

    The acceptance floor is the exploration guarantee — no composition is ever
    impossible, however poor its history, because a search that can only revisit
    past winners stops being a search. Same principle as the suppression cap.
    """
    if not weights:
        return True
    ws = [weights.get(r.split("(")[0], 1.0) for r in refs]
    if not ws:
        return True
    mean = sum(ws) / len(ws)
    # weights are bounded [0.25, 2.0] by edge_weights(); map to an acceptance
    # probability that never drops below the floor.
    p = max(0.25, min(1.0, mean / 1.5))
    return rng.random() < p


def sample_compositions(limit: int = 12, seed: int = 0,
                        suppressed: set | None = None,
                        weights: dict | None = None) -> list:
    """`limit` grammar-valid compositions drawn from the block registry.

    Duplicate keys are skipped rather than emitted: two records with the same key
    would collide in `research_generated_strategy` and one composition would
    silently overwrite the other's source.
    """
    if limit <= 0:
        return []
    rng = random.Random(seed)
    blocked = set(suppressed or ())
    out, seen = [], set()
    # Bounded attempts so an unlucky seed cannot spin: the draw space is far
    # larger than any realistic limit, but a cap makes that a guarantee.
    for _ in range(limit * 20):
        if len(out) >= limit:
            break
        t_up, t_dn, tcode = _mirror_trend(rng)
        m_up, m_dn, mcode = _mirror_momentum(rng)
        gate, gcode = _filter(rng)
        key = f"gen_{tcode}_{mcode}" + (f"_{gcode}" if gcode else "")
        if key in seen:
            continue
        # Knowledge from previous nights: a family with a well-powered negative
        # record on this universe is skipped. Skipped, not banned — the draw is
        # simply retried, and `suppressed_blocks` recomputes from the full record
        # every night, so later evidence lets a family back in.
        refs = [t_up, t_dn, m_up, m_dn] + ([gate] if gate else [])
        if blocked and any(r.split("(")[0] in blocked for r in refs):
            continue
        # Favour families with a positive record here (see _accepts).
        if not _accepts(refs, weights or {}, rng):
            continue
        seen.add(key)
        out.append(Composition.from_dict({
            "key": key,
            "longEntry": {"all": [t_up, m_up] + ([gate] if gate else [])},
            "shortEntry": {"all": [t_dn, m_dn] + ([gate] if gate else [])},
            "longExit": {"any": list(_LONG_EXIT)},
            "shortExit": {"any": list(_SHORT_EXIT)},
        }))
    # Last-resort floor. Suppression is a PREFERENCE, never a cage: if knowledge
    # has blocked every draw the grammar can make, explore anyway rather than
    # returning nothing. A night that searches nothing learns nothing, and the
    # loop would never escape the state that silenced it.
    if not out and (blocked or weights):
        # Same last-resort floor as suppression: if knowledge has blocked or
        # down-weighted every lawful draw, explore anyway. A night that searches
        # nothing learns nothing.
        return sample_compositions(limit=limit, seed=seed, suppressed=None, weights=None)
    return out
