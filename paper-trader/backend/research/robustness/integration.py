"""Bind the accepted stationary bootstrap to terminal experiment evidence."""
from __future__ import annotations

import copy
import json
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any

from app.engine.charges import ChargeScheduleRefusal, monetary_minor
from research.evidence import EvidenceRejected, encode_terminal_evidence
from research.robustness.monte_carlo import (
    ALGORITHM_VERSION,
    BOUNDS,
    PRNG_VERSION,
    SCHEMA,
    StationaryTradeBootstrapRefusal,
    reconstruct_stationary_trade_bootstrap,
    stationary_trade_bootstrap,
)


PROJECTION_SCHEMA = "strategy-os-run-robustness/1"
NOT_REQUESTED = "NOT_REQUESTED"
AVAILABLE = "AVAILABLE"
UNAVAILABLE = "UNAVAILABLE"

_SETTINGS_FIELDS = frozenset({
    "enabled", "iterations", "restart_probability_ppm",
})
_UNAVAILABLE_REASONS = frozenset({
    "INSUFFICIENT_LOCKED_OOS_TRADES",
    "LOCKED_OOS_TRADES_UNAVAILABLE",
    "MULTI_INSTRUMENT_AMBIGUITY",
    "STATIONARY_BOOTSTRAP_METHOD_REFUSED",
    "TERMINAL_EVIDENCE_SIZE_REFUSED",
})


class RobustnessEvidenceRejected(ValueError):
    """Stored or requested robustness evidence is open, corrupt, or ambiguous."""


def _reject(message: str) -> None:
    raise RobustnessEvidenceRejected(message)


def stationary_bootstrap_recipe_binding(
    settings: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the closed request and accepted method identity for ExperimentSpec."""
    if settings is None:
        return None
    if not isinstance(settings, Mapping) or set(settings) != _SETTINGS_FIELDS:
        _reject("stationary bootstrap settings are open or incomplete")
    enabled = settings["enabled"]
    iterations = settings["iterations"]
    restart_probability_ppm = settings["restart_probability_ppm"]
    if type(enabled) is not bool:
        _reject("stationary bootstrap enabled must be boolean")
    if type(iterations) is not int or not 100 <= iterations <= 5_000:
        _reject("stationary bootstrap iterations must be in 100..5000")
    if type(restart_probability_ppm) is not int \
            or not 1 <= restart_probability_ppm <= 1_000_000:
        _reject("stationary bootstrap restart probability must be in 1..1000000 ppm")
    return {
        "stationary_bootstrap": {
            "enabled": enabled,
            "iterations": iterations,
            "restart_probability_ppm": restart_probability_ppm,
            "method": {
                "schema": SCHEMA,
                "algorithm_version": ALGORITHM_VERSION,
                "prng_version": PRNG_VERSION,
                "bounds": dict(BOUNDS),
            },
        }
    }


def _unavailable(reason_code: str) -> dict[str, str]:
    if reason_code not in _UNAVAILABLE_REASONS:
        _reject("unknown robustness unavailable reason")
    return {
        "schema": PROJECTION_SCHEMA,
        "state": UNAVAILABLE,
        "reason_code": reason_code,
    }


def _stationary_request_from_recipe(
    recipe_binding: Mapping[str, Any],
) -> Mapping[str, Any]:
    if not isinstance(recipe_binding, Mapping) or set(recipe_binding) != {
        "stationary_bootstrap"
    }:
        _reject("robustness recipe binding is open or incomplete")
    request = recipe_binding["stationary_bootstrap"]
    if not isinstance(request, Mapping) or set(request) != {
        *_SETTINGS_FIELDS, "method"
    }:
        _reject("stationary bootstrap recipe binding is open or incomplete")
    expected_binding = stationary_bootstrap_recipe_binding({
        name: request[name] for name in _SETTINGS_FIELDS
    })
    if expected_binding != recipe_binding:
        _reject("stationary bootstrap method identity is stale or forged")
    return request


def stationary_bootstrap_request_enabled(
    recipe_binding: Mapping[str, Any] | None,
) -> bool:
    """Validate persisted request identity before interpreting a missing result."""
    if recipe_binding is None:
        return False
    return bool(_stationary_request_from_recipe(recipe_binding)["enabled"])


def _signed_minor(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise RobustnessEvidenceRejected(
            "locked OOS net PnL must be a real non-boolean number"
        )
    try:
        negative = value < 0
        magnitude = monetary_minor(abs(value))
    except (ChargeScheduleRefusal, TypeError, ValueError) as exc:
        raise RobustnessEvidenceRejected(
            "locked OOS net PnL is not accepted monetary input"
        ) from exc
    return -magnitude if negative else magnitude


def build_stationary_bootstrap_evidence(
    recipe_binding: Mapping[str, Any] | None,
    *,
    locked_oos_trades: Sequence[Any] | None,
    starting_capital: Any,
    seed: int,
    instrument_count: int,
) -> dict[str, Any]:
    """Create one closed run-level projection from ordered pooled locked OOS trades."""
    if recipe_binding is None:
        return {"schema": PROJECTION_SCHEMA, "state": NOT_REQUESTED}
    request = _stationary_request_from_recipe(recipe_binding)
    if not request["enabled"]:
        return {"schema": PROJECTION_SCHEMA, "state": NOT_REQUESTED}
    if type(instrument_count) is not int or instrument_count != 1:
        return _unavailable("MULTI_INSTRUMENT_AMBIGUITY")
    if locked_oos_trades is None:
        return _unavailable("LOCKED_OOS_TRADES_UNAVAILABLE")
    trade_count = len(locked_oos_trades)
    if trade_count < BOUNDS["minimum_trades"]:
        return _unavailable("INSUFFICIENT_LOCKED_OOS_TRADES")
    if trade_count > BOUNDS["maximum_trades"]:
        return _unavailable("STATIONARY_BOOTSTRAP_METHOD_REFUSED")
    try:
        trade_pnl = tuple(_signed_minor(trade.net_pnl) for trade in locked_oos_trades)
        starting_capital_paise = monetary_minor(starting_capital)
        result = stationary_trade_bootstrap(
            trade_pnl,
            starting_capital_paise=starting_capital_paise,
            seed=seed,
            iterations=request["iterations"],
            restart_probability_ppm=request["restart_probability_ppm"],
        )
    except (AttributeError, ChargeScheduleRefusal, StationaryTradeBootstrapRefusal,
            RobustnessEvidenceRejected):
        return _unavailable("STATIONARY_BOOTSTRAP_METHOD_REFUSED")
    return {
        "schema": PROJECTION_SCHEMA,
        "state": AVAILABLE,
        "method": {
            "address": result.address,
            "canonical_payload": result.canonical_bytes().decode("utf-8"),
        },
    }


def reconstruct_robustness_projection(stored: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a stored projection and semantically replay AVAILABLE method bytes."""
    if not isinstance(stored, Mapping) or stored.get("schema") != PROJECTION_SCHEMA:
        _reject("robustness projection schema is invalid")
    state = stored.get("state")
    if state == NOT_REQUESTED:
        if set(stored) != {"schema", "state"}:
            _reject("not-requested robustness projection is open")
        return {"schema": PROJECTION_SCHEMA, "state": NOT_REQUESTED}
    if state == UNAVAILABLE:
        if set(stored) != {"schema", "state", "reason_code"} \
                or stored.get("reason_code") not in _UNAVAILABLE_REASONS:
            _reject("unavailable robustness projection is open or invalid")
        return dict(stored)
    if state != AVAILABLE or set(stored) != {"schema", "state", "method"}:
        _reject("robustness projection state is invalid")
    method = stored["method"]
    if not isinstance(method, Mapping) or set(method) != {
        "address", "canonical_payload"
    } or not isinstance(method["canonical_payload"], str):
        _reject("available robustness method evidence is open or incomplete")
    try:
        result = reconstruct_stationary_trade_bootstrap(
            method["canonical_payload"].encode("utf-8"), method["address"]
        )
    except (AttributeError, UnicodeEncodeError, StationaryTradeBootstrapRefusal) as exc:
        raise RobustnessEvidenceRejected(
            "stored stationary bootstrap evidence failed semantic reconstruction"
        ) from exc
    return {
        "schema": PROJECTION_SCHEMA,
        "state": AVAILABLE,
        "method_address": result.address,
        "method": json.loads(result.canonical_bytes()),
    }


def encode_terminal_evidence_with_robustness_fallback(
    evidence: Mapping[str, Any],
) -> str:
    """Persist the base result if only the complete robustness artifact exceeds its cap."""
    try:
        return encode_terminal_evidence(evidence)
    except EvidenceRejected as exc:
        if "exceeds the persisted size limit" not in str(exc):
            raise
        results = evidence.get("results") if isinstance(evidence, Mapping) else None
        robustness = results.get("robustness") if isinstance(results, Mapping) else None
        if not isinstance(robustness, Mapping) or robustness.get("state") != AVAILABLE:
            raise
        fallback = copy.deepcopy(dict(evidence))
        fallback["results"]["robustness"] = _unavailable(
            "TERMINAL_EVIDENCE_SIZE_REFUSED"
        )
        return encode_terminal_evidence(fallback)


__all__ = [
    "AVAILABLE",
    "NOT_REQUESTED",
    "PROJECTION_SCHEMA",
    "RobustnessEvidenceRejected",
    "UNAVAILABLE",
    "build_stationary_bootstrap_evidence",
    "encode_terminal_evidence_with_robustness_fallback",
    "reconstruct_robustness_projection",
    "stationary_bootstrap_request_enabled",
    "stationary_bootstrap_recipe_binding",
]
