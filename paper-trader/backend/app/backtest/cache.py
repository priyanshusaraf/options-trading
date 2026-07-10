"""
Reusable backtest cache. A sweep result is reusable when the *content* it would
recompute is identical: same instrument, interval, strategy/params signature,
schema version, and the same last completed candle. Then we copy the stored
metrics into the new run instead of re-simulating. SQLite stays the source of
truth; nothing here uses the browser or any external store.
"""
from __future__ import annotations

import hashlib

from sqlalchemy import select

from app.db.models import BacktestResult

# v2: return%/equity/CAGR switched from a flat ₹50k base to compounding return on
#     the position's own notional (leverage-free, comparable across instruments).
# v3: added smoothness metrics (calmar/consistency/streak/underwater) + a candle
#     window to the signature so different lookback ranges don't collide in cache.
# v4: honest sizing (affordable-lots, notional, affordable flag) + realised-vs-open
#     split + buy-and-hold benchmark + annualised Sharpe + worst-trade/MAE + true
#     per-cell span (first/last/effective_days/clamped). The stored metric shape
#     changed, so bump to force a clean recompute (no stale-row mixing).
# v5: fixed 1-lot ADDITIVE return model (equity = base + Σ 1-lot net P&L, real
#     rupees; return% = total P&L / base) replacing compounding-%-on-notional, and
#     an estimated ATM option_cost for the options-affordability flag. Return/curve
#     semantics changed -> force a clean recompute.
# v6: fills moved to next-bar-open for ALL strategies (Pine parity) and a
#     strategy's declared risk_model (ratchet overlay) joined the signature.
#     Both change trade outcomes for every cell -> force a clean recompute.
# v7: the synthetic-premium backtest (audit C6) runs alongside the spot cell —
#     iv_rv_multiplier/premium_spread_pct/entry_dte_days joined the signature so
#     a premium-model knob change never silently reuses a stale premium result.
SCHEMA_VERSION = 7

# defaults mirrored from app.backtest.premium.DEFAULT_PREMIUM_PARAMS (not
# imported, to keep this module's dependency graph shallow — cache.py is on the
# hot path for every cached-cell lookup).
_PREMIUM_SIG_DEFAULTS = {"iv_rv_multiplier": 1.15, "premium_spread_pct": 0.02,
                         "entry_dte_days": 14}


def params_signature(capital: float, *, ema_length: int = 50, z_length: int = 50,
                     entry_z: float = 1.0, slope_lookback: int = 5,
                     window: str = "", strategy=None,
                     iv_rv_multiplier: float = _PREMIUM_SIG_DEFAULTS["iv_rv_multiplier"],
                     premium_spread_pct: float = _PREMIUM_SIG_DEFAULTS["premium_spread_pct"],
                     entry_dte_days: int = _PREMIUM_SIG_DEFAULTS["entry_dte_days"]) -> str:
    """Stable hash of everything that affects a backtest result other than the
    candle data itself. Changing any knob — including the requested date window,
    the STRATEGY, or a synthetic-premium model param — invalidates the cache so a
    1-year run never reuses a 10-year run's metrics and an Expanding-Z run never
    reuses a Trend-Impulse run's.

    Back-compat note: through v5 the default strategy reproduced its historical
    signature so the owner's v3 cache stayed valid; v6's fill-model change makes
    every pre-v6 cell stale BY DESIGN, so that guarantee is intentionally reset
    at v6 (the format is kept stable from here so future v3 caches survive
    non-breaking bumps)."""
    from app.strategy.registry import DEFAULT_STRATEGY_KEY
    prem = f"ivrv={iv_rv_multiplier}|psprd={premium_spread_pct}|dte={entry_dte_days}"
    if strategy is None or strategy.key == DEFAULT_STRATEGY_KEY:
        raw = (f"v{SCHEMA_VERSION}|cap={capital}|ema={ema_length}|z={z_length}"
               f"|ez={entry_z}|sl={slope_lookback}|win={window}|{prem}")
    else:
        ps = ",".join(f"{k}={strategy.default_params[k]}"
                      for k in sorted(strategy.default_params))
        rm = getattr(strategy, "risk_model", None)
        rs = ("none" if not rm else
              ",".join(f"{k}={rm[k]}" for k in sorted(rm)))
        raw = (f"v{SCHEMA_VERSION}|cap={capital}|win={window}"
               f"|strat={strategy.key}|params={ps}|risk={rs}|{prem}")
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def find_reusable(session, key: str, interval: str, params_hash: str,
                  last_candle_ts: int) -> BacktestResult | None:
    """Most recent successful result with an identical content key, or None."""
    if last_candle_ts <= 0:
        return None
    q = (select(BacktestResult)
         .where(BacktestResult.instrument_key == key,
                BacktestResult.interval == interval,
                BacktestResult.params_hash == params_hash,
                BacktestResult.last_candle_ts == last_candle_ts,
                BacktestResult.schema_version == SCHEMA_VERSION,
                BacktestResult.error == "")
         .order_by(BacktestResult.id.desc()))
    return session.scalars(q).first()
