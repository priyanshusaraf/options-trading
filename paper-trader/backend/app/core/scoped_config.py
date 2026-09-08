"""Owner platform configuration with deployment and instrument overlays.

Account risk constraints always retain the owner's platform value. Other validated
parameters resolve narrowest first: instrument, deployment, then platform.
Existing runtime rows remain owner operating decisions; no values are migrated.
"""
from __future__ import annotations

import json

from app.core.config import Settings, get_settings
from app.core.logging import log
from app.core.runtime_config import BOUNDS, CHOICES, OVERRIDABLE, _coerce_for_key, effective

# Scope names, narrowest last. The order IS the precedence — do not reorder without
# changing what "narrowest wins" means.
PLATFORM = "platform"
DEPLOYMENT = "deployment"
INSTRUMENT = "instrument"
SCOPES = (PLATFORM, DEPLOYMENT, INSTRUMENT)
ACCOUNT_RISK_KEYS = frozenset({
    "max_daily_loss", "max_open_drawdown", "max_daily_profit",
    "daily_profit_lock_pct", "daily_profit_giveback_frac",
})


class ScopeRejection(ValueError):
    """A scoped override that the platform's own validation would not accept."""


def validate_override(key: str, value, base_type_source: Settings | None = None):
    """Coerce + bounds-check one override, or raise `ScopeRejection`.

    The same gate `runtime_config` applies to a platform row. Raising rather than
    silently dropping is deliberate here: a platform row is written through a UI
    that shows the result, whereas a deployment's params arrive as a JSON blob that
    nobody re-reads. A silently ignored risk parameter is the worst outcome of the
    three — the deployment looks configured and is not.
    """
    if key in ACCOUNT_RISK_KEYS:
        raise ScopeRejection(
            f"{key!r} is an account-wide risk constraint. Change it in global Settings; "
            "strategy and instrument overrides cannot change it.")
    if key not in OVERRIDABLE:
        raise ScopeRejection(
            f"{key!r} is not an overridable parameter. Add it to "
            f"runtime_config.OVERRIDABLE if it should be tunable at all.")
    settings = base_type_source or get_settings()
    default = getattr(settings, key)
    try:
        coerced = _coerce_for_key(key, default, value)
    except Exception as e:
        raise ScopeRejection(f"{key!r}: cannot coerce {value!r} to "
                             f"{type(default).__name__} ({e})") from e
    _validate_value(key, coerced)
    return coerced


def _validate_value(key: str, coerced) -> None:
    """Apply the existing platform choices and bounds to a coerced value."""
    choices = CHOICES.get(key)
    if choices is not None and coerced not in choices:
        raise ScopeRejection(
            f"{key!r} must be one of {', '.join(choices)} (got {coerced!r})")
    lo_hi = BOUNDS.get(key)
    if lo_hi is not None and isinstance(coerced, (int, float)) \
            and not isinstance(coerced, bool):
        lo, hi = lo_hi
        if not (lo <= coerced <= hi):
            raise ScopeRejection(
                f"{key!r}={coerced} is outside the permitted range [{lo}, {hi}]")


def _apply_layer(out: dict, overrides: dict, scope: str, who: str,
                 settings: Settings, scope_of: dict) -> None:
    """Merge one scope's overrides over `out`, skipping anything invalid.

    A bad value is skipped and LOGGED rather than raising: this runs inside the
    signal loop's per-iteration `refresh_params()`, and one malformed row must not
    be able to stop the engine from managing open positions. `validate_override`
    raises for the write path (where a human is watching); this is the read path
    (where nobody is).
    """
    for key, raw in (overrides or {}).items():
        if key not in out:
            log.warn(f"scoped config: {scope} {who} sets unknown/non-overridable "
                     f"key {key!r} — ignored", event="SCOPED_CONFIG_REJECT")
            continue
        try:
            out[key] = validate_override(key, raw, settings)
            scope_of[key] = scope
        except ScopeRejection as e:
            log.warn(f"scoped config: {scope} {who} rejected — {e}",
                     event="SCOPED_CONFIG_REJECT")


def _json_params(raw: str | None) -> dict:
    """Parse a params_json column. Malformed => {} ("inherit everything").

    Never raises. A corrupt JSON blob on one deployment must degrade that
    deployment to platform defaults, not take down every other deployment sharing
    the process.
    """
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _resolve_with_sources(session=None, settings: Settings | None = None, *,
            deployment_id: int | None = None,
            instrument_key: str | None = None,
            owner_id: str,
            broker_account_id: str | None = None) -> tuple[dict, dict]:
    """Resolve values and provenance together; rejected overrides affect neither."""
    settings = settings or get_settings()
    out = effective(settings, owner_id=owner_id)   # platform: defaults + runtime_config

    scope_of = {key: PLATFORM for key in out}
    if session is None:
        return out, scope_of

    if deployment_id is not None:
        if broker_account_id is None:
            raise TypeError("broker_account_id is required for deployment config")
        from app.core.deployments import get_deployment
        row = get_deployment(session, deployment_id, owner_id=owner_id,
                             broker_account_id=broker_account_id)
        if row is not None:
            _apply_layer(out, _json_params(row.params_json), DEPLOYMENT,
                         f"#{deployment_id} ({row.name})", settings, scope_of)

    if instrument_key is not None:
        from app.db.models import InstrumentState
        row = session.get(InstrumentState, (owner_id, instrument_key))
        if row is not None:
            _apply_layer(out, _json_params(getattr(row, "params_json", None)),
                         INSTRUMENT, instrument_key, settings, scope_of)

    return out, scope_of


def resolve(session=None, settings: Settings | None = None, *,
            deployment_id: int | None = None,
            instrument_key: str | None = None,
            owner_id: str,
            broker_account_id: str | None = None) -> dict:
    """Validated scoped values; account constraints always retain platform values."""
    values, _ = _resolve_with_sources(session, settings, deployment_id=deployment_id,
        instrument_key=instrument_key, owner_id=owner_id, broker_account_id=broker_account_id)
    return values


def explain(session, settings: Settings | None = None, *,
            deployment_id: int | None = None,
            instrument_key: str | None = None,
            owner_id: str,
            broker_account_id: str | None = None) -> dict[str, dict]:
    """Per-key provenance: which scope decided each value.

    Exists because "why is this stop 0.8%?" is a question that gets asked during an
    incident, and with three scopes the answer stops being obvious. Returns
    {key: {"value": ..., "scope": ..., "platform_default": ...}}.
    """
    settings = settings or get_settings()
    final, scope_of = _resolve_with_sources(session, settings, deployment_id=deployment_id,
        instrument_key=instrument_key, owner_id=owner_id, broker_account_id=broker_account_id)

    return {k: {"value": final[k], "scope": scope_of[k],
                "platform_default": getattr(settings, k, None)}
            for k in final}
