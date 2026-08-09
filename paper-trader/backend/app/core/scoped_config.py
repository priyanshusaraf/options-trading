"""Scoped configuration: Platform → Deployment → Instrument, resolved once.

Before Phase C every knob was process-global. `Settings` is a singleton,
`runtime_config` is a flat key/value table, and `effective()` merged them into one
`params` dict that the whole engine read. That is correct for one book and
impossible for two: `max_daily_loss`, `intraday_stop_loss_pct` and the arm switch
are all properties of *a strategy running*, not of *the machine*.

The three scopes, narrowest wins
--------------------------------
    Platform    `Settings` code defaults, then `runtime_config` rows.
    Deployment  `deployments.params_json`.
    Instrument  `instrument_state.params_json`.

The owner's ten live `runtime_config` overrides become PLATFORM scope with no data
migration and no change in meaning — they are the platform's operating decisions
(see CLAUDE.md: they are deliberate, not drift, and must not be "reconciled" away).
Anything narrower is opt-in and empty today, so `resolve()` with no scope arguments
returns byte-identical output to `effective()`. That equivalence is asserted in
`tests/test_scoped_config.py` and is what makes this migration safe to land while
the engine is live.

Why validation is reused rather than reimplemented
--------------------------------------------------
`runtime_config` already owns `OVERRIDABLE` (which keys exist) and `BOUNDS` (what
values are sane) — the guard that stops a fat-finger producing an inverted stop or
a busy-spin loop that breaches Kite's rate limit. A second scope with its own
notion of "valid" would be a second place for that to be wrong, so narrower scopes
are validated through exactly the same gate. A deployment cannot set a key the
platform would refuse, and cannot set it to a value the platform would refuse.
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
    return coerced


def _apply_layer(out: dict, overrides: dict, scope: str, who: str,
                 settings: Settings) -> None:
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


def resolve(session=None, settings: Settings | None = None, *,
            deployment_id: int | None = None,
            instrument_key: str | None = None) -> dict:
    """THE configuration resolution path. Returns the merged parameter dict.

    With no scope arguments this is exactly `effective()` — same keys, same values.
    That is not a coincidence to be preserved by care; it is asserted by test.

    `session` is optional so callers that only want platform scope (tests, the
    backtester, anything with no deployment in hand) do not have to open one.
    """
    settings = settings or get_settings()
    out = effective(settings)                      # platform: defaults + runtime_config

    if session is None or (deployment_id is None and instrument_key is None):
        return out

    if deployment_id is not None:
        from app.core.deployments import get_deployment
        row = get_deployment(session, deployment_id)
        if row is not None:
            _apply_layer(out, _json_params(row.params_json), DEPLOYMENT,
                         f"#{deployment_id} ({row.name})", settings)

    if instrument_key is not None:
        from app.db.models import InstrumentState
        row = session.get(InstrumentState, instrument_key)
        if row is not None:
            _apply_layer(out, _json_params(getattr(row, "params_json", None)),
                         INSTRUMENT, instrument_key, settings)

    return out


def explain(session, settings: Settings | None = None, *,
            deployment_id: int | None = None,
            instrument_key: str | None = None) -> dict[str, dict]:
    """Per-key provenance: which scope decided each value.

    Exists because "why is this stop 0.8%?" is a question that gets asked during an
    incident, and with three scopes the answer stops being obvious. Returns
    {key: {"value": ..., "scope": ..., "platform_default": ...}}.
    """
    settings = settings or get_settings()
    platform = effective(settings)
    final = resolve(session, settings, deployment_id=deployment_id,
                    instrument_key=instrument_key)

    scope_of = {k: PLATFORM for k in platform}
    if deployment_id is not None:
        from app.core.deployments import get_deployment
        row = get_deployment(session, deployment_id) if session else None
        if row is not None:
            for k in _json_params(row.params_json):
                if k in scope_of and final.get(k) != platform.get(k):
                    scope_of[k] = DEPLOYMENT
    if instrument_key is not None:
        from app.db.models import InstrumentState
        row = session.get(InstrumentState, instrument_key) if session else None
        if row is not None:
            for k in _json_params(getattr(row, "params_json", None)):
                if k in scope_of:
                    scope_of[k] = INSTRUMENT

    return {k: {"value": final[k], "scope": scope_of[k],
                "platform_default": getattr(settings, k, None)}
            for k in final}
