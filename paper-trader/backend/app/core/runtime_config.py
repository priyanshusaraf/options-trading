"""
Runtime parameter overrides — manual-override mode.

Each row in `runtime_config` overrides one Settings field by name. `effective()`
returns the merged, type-coerced parameter dict the engine reads, so the owner
can retune reinforcement / overnight / trailing behaviour live, without editing
code. Only whitelisted Settings fields are accepted (a typo can't inject junk),
and every value is coerced to the type of its code default.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.db.models import RuntimeConfig
from app.db.session import SessionLocal

# Fields the Settings UI may override at runtime. Each maps 1:1 to a Settings field.
OVERRIDABLE = (
    "stop_loss_pct", "target_pct",
    "max_open_positions", "reentry_cooldown_minutes", "max_capital_per_trade",
    "trail_enabled", "trail_trigger_pct", "trail_first_step_lock_pct", "trail_step_lock_pct",
    "reinforce_enabled", "reinforce_min_profit_pct", "reinforce_lock_pct",
    "reinforce_extend_tp", "reinforce_tp_extend_pct", "reinforce_tp_max_pct",
    "reinforce_cooldown_minutes", "max_reinforcements",
    "overnight_enabled", "overnight_auto_pct", "overnight_max_pct",
    "overnight_min_reinforcements", "overnight_min_days_to_expiry",
    "block_overnight_into_weekend", "max_holding_days", "square_off_buffer_minutes",
    "option_cache_enabled", "option_cache_snapshot_minutes",
    "max_stale_seconds", "position_loop_seconds", "signal_loop_seconds",
    "notify_enabled", "notify_on_signal", "alert_proximity_pct",
    "entry_order_mode",
    "exec_market_max_spread_pct", "exec_limit_max_spread_pct",
    "exec_max_slippage_pct", "exec_min_top_qty_lots", "max_daily_loss",
    "max_open_drawdown", "max_round_trips_per_day",
    "daily_profit_lock_pct", "daily_profit_giveback_frac",
    "bot_capital_cap", "capital_reserve", "gtt_stop_enabled",
    # intraday-equity segment (MIS) — also the channel by which these reach the
    # engine's self.params (effective() only surfaces OVERRIDABLE keys).
    "intraday_enabled", "intraday_max_positions", "intraday_min_margin",
    "intraday_max_margin", "intraday_purple_margin", "intraday_leverage",
    "intraday_square_off_buffer_minutes", "intraday_entry_cutoff_minutes",
    "intraday_stop_loss_pct", "intraday_target_pct",
    "intraday_purple_stop_loss_pct", "intraday_purple_target_pct",
    "intraday_lockstep_enabled", "intraday_lockstep_trigger_pct",
    "intraday_profit_lock_threshold", "intraday_profit_lock_frac",
    # overtrading guard (advisory)
    "overtrade_today_threshold", "overtrade_rolling_threshold", "overtrade_rolling_days",
    # journal — manual-trade detection. Read-only against the broker: it polls
    # the orderbook for trades the OWNER placed and never writes the ledger.
    "manual_detect_enabled", "manual_detect_seconds",
    # entry guards (theta-cliff / expiry)
    "entry_min_days_to_expiry",
    # day-shape guards: no-entries weekday (NIFTY-expiry Tuesdays) + which keys it
    # scopes to, stale-crossover age cap, start-of-day entry window
    "intraday_block_weekday", "expiry_day_block_keys", "intraday_override_date",
    "max_signal_age_minutes", "entry_window_start",
    # fix D: Nifty opening-gap guard
    "gap_guard_enabled", "gap_guard_pct", "gap_guard_resume", "gap_guard_index",
    # #14 live order-failure circuit breaker
    "order_failure_disarm_count",
    # telemetry retention — bounded DB growth on a 1GB box (money record never pruned)
    "retention_enabled", "retention_option_data_days", "retention_signal_events_days",
    "retention_equity_full_days", "retention_equity_downsample_minutes",
    # ledger honesty — daily re-anchor of the internal ledger to real broker equity
    "ledger_auto_reanchor", "ledger_reanchor_tolerance",
    # scheduled-event risk (EIA releases, index weekdays, bullion expiry, earnings)
    "event_risk_enabled", "event_risk_flatten", "event_risk_flatten_lead_minutes",
    # L1 Stage 1 — the Component IR shadow lane. Observer only; overridable so it can be
    # switched off on a live box without a deploy or a restart (ADR 0011 criterion 5).
    "ir_shadow_enabled",
)

CHOICES: dict[str, tuple[str, ...]] = {
    "entry_order_mode": ("AUTO", "MARKET", "LIMIT"),
}


# Inclusive [min, max] bounds per numeric key. Anything outside is rejected so a
# typo or fat-finger can't produce a negative/inverted stop or a busy-spin loop
# that breaches Kite's rate limits. Booleans need no bounds.
BOUNDS: dict[str, tuple[float, float]] = {
    "stop_loss_pct": (0.001, 0.99),          # a positive fraction strictly below full premium
    "target_pct": (0.001, 10.0),
    "max_open_positions": (0, 100),          # 0 = unlimited
    "reentry_cooldown_minutes": (0.0, 1440.0),  # 0 = off
    "max_capital_per_trade": (0.0, 100000000.0),  # 0 = no cap
    "trail_trigger_pct": (0.001, 1.0),
    "trail_first_step_lock_pct": (0.0, 1.0),
    "trail_step_lock_pct": (0.0, 1.0),
    "reinforce_min_profit_pct": (0.0, 5.0),
    "reinforce_lock_pct": (0.0, 1.0),
    "reinforce_tp_extend_pct": (0.0, 5.0),
    "reinforce_tp_max_pct": (0.0, 10.0),
    "reinforce_cooldown_minutes": (0.0, 1440.0),
    "max_reinforcements": (0, 100),
    "overnight_auto_pct": (0.0, 1.0),
    "overnight_max_pct": (0.0, 1.0),
    "overnight_min_reinforcements": (0, 100),
    "overnight_min_days_to_expiry": (0, 365),
    "max_holding_days": (0, 365),
    "square_off_buffer_minutes": (0.0, 360.0),
    "option_cache_snapshot_minutes": (0.0, 1440.0),
    "max_stale_seconds": (1.0, 3600.0),
    "position_loop_seconds": (0.5, 600.0),   # floor keeps the risk loop under Kite's quote limit
    "signal_loop_seconds": (0.5, 600.0),
    "alert_proximity_pct": (0.01, 0.90),
    "exec_market_max_spread_pct": (0.0, 0.50),
    "exec_limit_max_spread_pct": (0.0, 0.90),
    "exec_max_slippage_pct": (0.0, 0.50),
    "exec_min_top_qty_lots": (0.0, 10000.0),
    "max_daily_loss": (0.0, 100000000.0),   # 0 disables the halt
    "max_open_drawdown": (0.0, 100000000.0),  # 0 disables the realized+unrealized halt
    "daily_profit_lock_pct": (0.0, 1.0),        # 0 disables the give-back halt
    "daily_profit_giveback_frac": (0.0, 1.0),
    "bot_capital_cap": (0.0, 100000000.0),  # 0 = no extra cap
    "capital_reserve": (0.0, 100000000.0),
    # intraday-equity segment
    "intraday_max_positions": (0, 50),       # 0 = no intraday positions
    "intraday_min_margin": (0.0, 100000000.0),
    "intraday_max_margin": (0.0, 100000000.0),
    "intraday_purple_margin": (0.0, 100000000.0),
    "intraday_leverage": (1.0, 20.0),
    "intraday_square_off_buffer_minutes": (0.0, 360.0),
    "intraday_entry_cutoff_minutes": (0.0, 360.0),
    "intraday_stop_loss_pct": (0.001, 0.50),
    "intraday_target_pct": (0.001, 2.0),
    "intraday_purple_stop_loss_pct": (0.001, 0.50),
    "intraday_purple_target_pct": (0.001, 2.0),
    "intraday_lockstep_trigger_pct": (0.001, 1.0),
    "intraday_profit_lock_threshold": (0.0, 1000000.0),
    "intraday_profit_lock_frac": (0.0, 1.0),
    "overtrade_today_threshold": (0, 200),       # 0 disables the today arm of the suggestion
    "overtrade_rolling_threshold": (0, 1000),    # 0 disables the rolling arm
    "overtrade_rolling_days": (1, 90),
    "entry_min_days_to_expiry": (0, 30),
    "intraday_block_weekday": (-1, 6),
    "max_signal_age_minutes": (0.0, 1440.0),   # 0 disables the stale-crossover guard
    "gap_guard_pct": (0.0, 10.0),              # 0 disables the opening-gap guard
    "order_failure_disarm_count": (0, 100),    # 0 disables the order circuit breaker
    "max_round_trips_per_day": (0, 100),
    # ₹ of ledger-vs-broker drift tolerated before the daily re-anchor corrects it. Too
    # tight and the ledger churns on rounding; too loose and the equity curve drifts.
    "ledger_reanchor_tolerance": (0.0, 1000000.0),
    "event_risk_flatten_lead_minutes": (0.0, 120.0),
    # 0 = keep forever (never "delete everything" — see engine/retention.py)
    "retention_option_data_days": (0, 3650),
    "retention_signal_events_days": (0, 3650),
    "retention_equity_full_days": (0, 3650),
    "retention_equity_downsample_minutes": (0, 1440),
}


def _coerce(default, raw: str):
    if isinstance(default, bool):
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        return int(float(raw))
    if isinstance(default, float):
        return float(raw)
    return str(raw)


def _coerce_for_key(key: str, default, raw):
    value = _coerce(default, raw)
    if key in CHOICES:
        return str(value).strip().upper()
    return value


def validate(key: str, value) -> str | None:
    """Return an error string if `value` is out of bounds for `key`, else None."""
    default = getattr(get_settings(), key)
    try:
        coerced = _coerce_for_key(key, default, value)
    except (TypeError, ValueError):
        return f"'{value}' is not a valid value for {key}"
    choices = CHOICES.get(key)
    if choices is not None and coerced not in choices:
        return f"{key} must be one of {', '.join(choices)} (got {coerced})"
    bounds = BOUNDS.get(key)
    if bounds is None:
        return None
    lo, hi = bounds
    if not (lo <= coerced <= hi):
        return f"{key} must be between {lo} and {hi} (got {coerced})"
    return None


def get_overrides(*, owner_id: str) -> dict[str, str]:
    with SessionLocal() as s:
        return {r.key: r.value for r in s.scalars(select(RuntimeConfig).where(
            RuntimeConfig.owner_id == owner_id))}


def set_override(key: str, value, *, owner_id: str) -> dict:
    if key not in OVERRIDABLE:
        return {"error": f"'{key}' is not an overridable parameter"}
    err = validate(key, value)
    if err:
        return {"error": err}
    value = _coerce_for_key(key, getattr(get_settings(), key), value)
    with SessionLocal() as s:
        row = s.get(RuntimeConfig, (owner_id, key))
        if row is None:
            s.add(RuntimeConfig(owner_id=owner_id, key=key, value=str(value), updated_at=dt.datetime.now()))
        else:
            row.value = str(value)
            row.updated_at = dt.datetime.now()
        s.commit()
    return {"key": key, "value": str(value)}


def clear_override(key: str, *, owner_id: str) -> None:
    with SessionLocal() as s:
        row = s.get(RuntimeConfig, (owner_id, key))
        if row is not None:
            s.delete(row)
            s.commit()


def effective(settings: Settings | None = None, *, owner_id: str) -> dict:
    """Code defaults merged with runtime overrides; values type-coerced."""
    settings = settings or get_settings()
    out = {k: getattr(settings, k) for k in OVERRIDABLE}
    for k, raw in get_overrides(owner_id=owner_id).items():
        if k in out:
            try:
                out[k] = _coerce_for_key(k, out[k], raw)
            except Exception:
                pass  # keep the default if a stored value can't be coerced
    return out


def schema(*, owner_id: str) -> list[dict]:
    """Per-field metadata for the Settings UI: key, type, default, current value.

    `overridden` reports whether a DB override row exists — it is NOT inferable
    from `value != default`. A stored override equal to the code default shadows
    that default forever while looking untouched, so shipping a new default
    would silently have no effect. That has already cost this project time; the
    UI must be able to show it.
    """
    s = get_settings()
    eff = effective(s, owner_id=owner_id)
    stored = get_overrides(owner_id=owner_id)
    rows = []
    for k in OVERRIDABLE:
        default = getattr(s, k)
        rows.append({
            "key": k,
            "type": ("bool" if isinstance(default, bool) else
                     "int" if isinstance(default, int) else
                     "float" if isinstance(default, float) else "str"),
            "default": default,
            "value": eff[k],
            "overridden": k in stored,
            "choices": list(CHOICES[k]) if k in CHOICES else None,
        })
    return rows
