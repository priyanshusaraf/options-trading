"""Reusable, content-addressed backtest result cache."""
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
# v8: cache identity binds the complete ordered candle dataset, execution source,
#     strategy version, instrument economics, and every simulation policy.  Full
#     SHA-256 addresses replace the old timestamp-plus-truncated-params key.
SCHEMA_VERSION = 8

RUN_LOCAL_FIELDS = frozenset({"id", "owner_id", "run_id", "from_cache"})
CACHED_RESULT_FIELDS = tuple(
    column.name for column in BacktestResult.__table__.columns
    if column.name not in RUN_LOCAL_FIELDS
)


def cached_result_values(source: BacktestResult) -> dict:
    """Every cold-result value that a warm row must reproduce exactly."""
    return {name: getattr(source, name) for name in CACHED_RESULT_FIELDS}

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
    """Legacy model-only signature retained for callers outside sweep.

    Sweep reuse uses :func:`execution_result_address`, which also binds exact data,
    source modules, instrument economics, slippage, and policy globals.
    """
    from app.strategy.registry import DEFAULT_STRATEGY_KEY, get_strategy
    strategy = strategy or get_strategy(DEFAULT_STRATEGY_KEY)
    version = getattr(strategy, "version", "unknown")
    prem = f"ivrv={iv_rv_multiplier}|psprd={premium_spread_pct}|dte={entry_dte_days}"
    if strategy.key == DEFAULT_STRATEGY_KEY:
        raw = (f"v{SCHEMA_VERSION}|cap={capital}|ema={ema_length}|z={z_length}"
               f"|ez={entry_z}|sl={slope_lookback}|win={window}"
               f"|stratver={version}|{prem}")
    else:
        ps = ",".join(f"{k}={strategy.default_params[k]}"
                      for k in sorted(strategy.default_params))
        rm = getattr(strategy, "risk_model", None)
        rs = ("none" if not rm else
              ",".join(f"{k}={rm[k]}" for k in sorted(rm)))
        raw = (f"v{SCHEMA_VERSION}|cap={capital}|win={window}"
               f"|strat={strategy.key}|stratver={version}"
               f"|params={ps}|risk={rs}|{prem}")
    return hashlib.sha256(raw.encode()).hexdigest()


def find_reusable(session, key: str, interval: str, params_hash: str,
                  last_candle_ts: int, *, owner_id: str,
                  expected_premium_error: str = "") \
        -> BacktestResult | None:
    """Most recent successful result with an identical content key, or None."""
    if last_candle_ts <= 0:
        return None
    q = (select(BacktestResult)
         .where(BacktestResult.owner_id == owner_id,
                BacktestResult.instrument_key == key,
                BacktestResult.interval == interval,
                BacktestResult.params_hash == params_hash,
                BacktestResult.last_candle_ts == last_candle_ts,
                BacktestResult.schema_version == SCHEMA_VERSION,
                BacktestResult.error == "",
                BacktestResult.premium_error == expected_premium_error)
         .order_by(BacktestResult.id.desc()))
    return session.scalars(q).first()
