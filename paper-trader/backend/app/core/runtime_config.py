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
    "trail_enabled", "trail_trigger_pct", "trail_lock_pct", "trail_target_pct",
    "reinforce_enabled", "reinforce_min_profit_pct", "reinforce_lock_pct",
    "reinforce_extend_tp", "reinforce_tp_extend_pct", "reinforce_tp_max_pct",
    "reinforce_cooldown_minutes", "max_reinforcements",
    "overnight_enabled", "overnight_auto_pct", "overnight_max_pct",
    "overnight_min_reinforcements", "overnight_min_days_to_expiry",
    "block_overnight_into_weekend", "max_holding_days", "square_off_buffer_minutes",
    "option_cache_enabled", "option_cache_snapshot_minutes",
    "max_stale_seconds", "position_loop_seconds", "signal_loop_seconds",
    "notify_enabled", "notify_on_signal", "alert_proximity_pct",
    "exec_market_max_spread_pct", "exec_limit_max_spread_pct",
    "exec_max_slippage_pct", "exec_min_top_qty_lots", "max_daily_loss",
)


# Inclusive [min, max] bounds per numeric key. Anything outside is rejected so a
# typo or fat-finger can't produce a negative/inverted stop or a busy-spin loop
# that breaches Kite's rate limits. Booleans need no bounds.
BOUNDS: dict[str, tuple[float, float]] = {
    "stop_loss_pct": (0.001, 0.99),          # a positive fraction strictly below full premium
    "target_pct": (0.001, 10.0),
    "trail_trigger_pct": (0.001, 1.0),
    "trail_lock_pct": (0.0, 1.0),
    "trail_target_pct": (0.001, 10.0),
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
}


def _coerce(default, raw: str):
    if isinstance(default, bool):
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        return int(float(raw))
    if isinstance(default, float):
        return float(raw)
    return str(raw)


def validate(key: str, value) -> str | None:
    """Return an error string if `value` is out of bounds for `key`, else None."""
    bounds = BOUNDS.get(key)
    if bounds is None:
        return None
    default = getattr(get_settings(), key)
    try:
        coerced = _coerce(default, value)
    except (TypeError, ValueError):
        return f"'{value}' is not a valid value for {key}"
    lo, hi = bounds
    if not (lo <= coerced <= hi):
        return f"{key} must be between {lo} and {hi} (got {coerced})"
    return None


def get_overrides() -> dict[str, str]:
    with SessionLocal() as s:
        return {r.key: r.value for r in s.scalars(select(RuntimeConfig))}


def set_override(key: str, value) -> dict:
    if key not in OVERRIDABLE:
        return {"error": f"'{key}' is not an overridable parameter"}
    err = validate(key, value)
    if err:
        return {"error": err}
    with SessionLocal() as s:
        row = s.get(RuntimeConfig, key)
        if row is None:
            s.add(RuntimeConfig(key=key, value=str(value), updated_at=dt.datetime.now()))
        else:
            row.value = str(value)
            row.updated_at = dt.datetime.now()
        s.commit()
    return {"key": key, "value": str(value)}


def clear_override(key: str) -> None:
    with SessionLocal() as s:
        row = s.get(RuntimeConfig, key)
        if row is not None:
            s.delete(row)
            s.commit()


def effective(settings: Settings | None = None) -> dict:
    """Code defaults merged with runtime overrides; values type-coerced."""
    settings = settings or get_settings()
    out = {k: getattr(settings, k) for k in OVERRIDABLE}
    for k, raw in get_overrides().items():
        if k in out:
            try:
                out[k] = _coerce(out[k], raw)
            except Exception:
                pass  # keep the default if a stored value can't be coerced
    return out


def schema() -> list[dict]:
    """Per-field metadata for the Settings UI: key, type, default, current value."""
    s = get_settings()
    eff = effective(s)
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
        })
    return rows
