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
)


def _coerce(default, raw: str):
    if isinstance(default, bool):
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        return int(float(raw))
    if isinstance(default, float):
        return float(raw)
    return str(raw)


def get_overrides() -> dict[str, str]:
    with SessionLocal() as s:
        return {r.key: r.value for r in s.scalars(select(RuntimeConfig))}


def set_override(key: str, value) -> dict:
    if key not in OVERRIDABLE:
        return {"error": f"'{key}' is not an overridable parameter"}
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
