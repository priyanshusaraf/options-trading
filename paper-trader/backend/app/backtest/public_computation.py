"""Ownerless reuse of proven public backtest computations.

The database row is deliberately a small, versioned interchange format.  It is
not an ORM row with a few columns removed: source/run identity and any future
local column are rejected at the boundary.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.backtest.cache import CACHED_RESULT_FIELDS, SCHEMA_VERSION
from app.db.models import BacktestComputation


MARKET_PUBLIC = "MARKET_PUBLIC"
PUBLIC_PAYLOAD_VERSION = 1
# Explicit and checked against the ordinary warm-cache contract below.  `cell_key`
# is a run-local persistence identity even though it predates RUN_LOCAL_FIELDS;
# timestamps/cache flags are local observation metadata, never public evidence.
PUBLIC_RESULT_FIELDS = (
    "instrument_key", "name", "segment", "strategy_key", "interval",
    "strategy_version", "trades", "wins", "win_rate", "profit_factor",
    "max_drawdown_pct", "return_pct", "net_pnl", "gross_pnl", "charges",
    "expectancy", "cagr", "calmar", "consistency", "sharpe",
    "max_consec_losses", "time_underwater_pct", "worst_trade_pnl",
    "worst_mae_pct", "notional", "lots", "affordable", "option_cost",
    "open_at_end", "win_rate_realised", "return_pct_realised", "bh_return_pct",
    "first_ts", "last_ts", "effective_days", "clamped", "bars", "curve_json",
    "bh_curve_json", "trades_json", "error", "premium_trades", "premium_win_rate",
    "premium_net_pnl", "premium_return_pct", "premium_profit_factor",
    "premium_max_drawdown_pct", "premium_expectancy", "premium_charges",
    "premium_trades_json", "premium_error", "params_hash", "last_candle_ts",
    "schema_version",
)
_PUBLIC_RESULT_FIELD_SET = frozenset(PUBLIC_RESULT_FIELDS)
assert _PUBLIC_RESULT_FIELD_SET <= set(CACHED_RESULT_FIELDS)
assert not ({"cell_key", "computed_at", "from_cache"} & _PUBLIC_RESULT_FIELD_SET)

# A runtime registry entry cannot join this catalog. Updating executable strategy
# code requires deliberately updating this checked-in publication manifest too.
PUBLIC_STRATEGY_CATALOG = {
    "trend_impulse_v3": {
        "module": "app.strategy.registry.trend_impulse_v3",
        "version": "5ffd4ed3bfbda8e63122a77e8744dbf44ca3f9888fc8c97609a1dc80ed9cf4f2",
        "defaults": {"ema_length": 50, "entry_z": 1.0, "slope_lookback": 5, "z_length": 50},
        "source_digest": "2fecaebba6ac34fedbab4544b34e2fb2739f2d522fb5351347f05ee043e4906d",
    },
    "expanding_z_v4": {
        "module": "app.strategy.registry.expanding_z_v4",
        "version": "62d1af82680c8aabe672b29a0d924b71a21276de9798a41e9e8ff5a7955bd6f3",
        "defaults": {"adapt_length": 200, "allow_reexpansion": True, "atr_length": 14,
                     "ema_length": 50, "entry_pct": 65.0, "exit_on_drift_flip": True,
                     "exit_on_ema_cross": True, "exit_pct": 35.0, "max_signal_atr": 2.75,
                     "min_abs_z": 0.6, "min_drift_atr": 0.08, "require_expansion": True,
                     "slope_lookback": 5, "use_absz_contraction_exit": False,
                     "z_length": 50},
        "source_digest": "1873e3f0c6ac6723a0aec97f1cce4724feb1e279124a34b39c7663c37a662063",
    },
}
_REQUIRED_MANIFEST_KEYS = frozenset({"dataset_address", "dataset_verified"})


class PublicComputationIntegrityError(RuntimeError):
    """A public address or public payload cannot be authenticated."""


def _is_address(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _canonical_json(value: Mapping) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise PublicComputationIntegrityError("public computation payload is not canonical JSON") from exc


def canonical_public_payload(payload: Mapping) -> str:
    """Encode only the closed v1 pure-result representation.

    Every payload must match the exact checked-in v1 field set; missing and unknown
    fields both fail closed.
    """
    if not isinstance(payload, Mapping):
        raise PublicComputationIntegrityError("public computation payload must be a mapping")
    keys = set(payload)
    if keys != _PUBLIC_RESULT_FIELD_SET:
        missing = sorted(_PUBLIC_RESULT_FIELD_SET - keys)
        unknown = sorted(keys - _PUBLIC_RESULT_FIELD_SET)
        raise PublicComputationIntegrityError(
            f"public computation payload must contain the exact v{PUBLIC_PAYLOAD_VERSION} schema; "
            f"missing={missing!r} unknown={unknown!r}")
    return _canonical_json({"version": PUBLIC_PAYLOAD_VERSION,
                            "result": {key: payload[key] for key in PUBLIC_RESULT_FIELDS if key in payload}})


def public_result_payload(values: Mapping) -> dict:
    """The only sweep-to-public boundary: copy the closed semantic field set."""
    # Error rows are rejected before publication, so the ordinary successful
    # serializer need not carry the ORM's empty-error default itself.
    missing = _PUBLIC_RESULT_FIELD_SET - set(values) - {"error"}
    if missing:
        raise PublicComputationIntegrityError(
            f"public result source misses required semantic fields: {sorted(missing)!r}")
    return {key: values[key] if key in values else "" for key in PUBLIC_RESULT_FIELDS}


def _decode_public_payload(payload_json: str) -> dict:
    try:
        envelope = json.loads(payload_json)
    except (TypeError, ValueError):
        raise PublicComputationIntegrityError("public computation payload is corrupt") from None
    if (not isinstance(envelope, dict) or envelope.get("version") != PUBLIC_PAYLOAD_VERSION
            or not isinstance(envelope.get("result"), dict)
            or set(envelope) != {"version", "result"}
            or set(envelope["result"]) != _PUBLIC_RESULT_FIELD_SET):
        raise PublicComputationIntegrityError("public computation payload has an invalid v1 envelope")
    return dict(envelope["result"])


def _digest(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _module_source_digest(strategy) -> str | None:
    module = __import__(type(strategy).__module__, fromlist=["__file__"])
    source = getattr(module, "__file__", None)
    if not source:
        return None
    path = Path(source)
    if path.suffix in {".pyc", ".pyo"}:
        path = path.with_suffix(".py")
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def strategy_is_platform_public(strategy) -> bool:
    """Only an immutable checked-in catalog entry can enter the public namespace."""
    key = getattr(strategy, "key", "")
    item = PUBLIC_STRATEGY_CATALOG.get(key)
    if item is None or type(strategy).__module__ != item["module"]:
        return False
    try:
        defaults = json.loads(json.dumps(getattr(strategy, "default_params", {}), sort_keys=True))
    except (TypeError, ValueError):
        return False
    return (getattr(strategy, "version", None) == item["version"]
            and defaults == item["defaults"]
            and _module_source_digest(strategy) == item["source_digest"])


def is_eligible(*, dataset_classification: str | None, strategy_key: str,
                strategy_module: str, execution_manifest: Mapping) -> bool:
    """Deny by default before a caller can probe shared state."""
    if dataset_classification != MARKET_PUBLIC or not isinstance(execution_manifest, Mapping):
        return False
    if set(execution_manifest) != _REQUIRED_MANIFEST_KEYS:
        return False
    address = execution_manifest.get("dataset_address")
    return (_is_address(address)
            and execution_manifest.get("dataset_verified") is True
            and strategy_key in PUBLIC_STRATEGY_CATALOG
            and strategy_module == PUBLIC_STRATEGY_CATALOG[strategy_key]["module"])


def _lookup(session, *, execution_address: str) -> BacktestComputation | None:
    return session.scalar(select(BacktestComputation).where(
        BacktestComputation.execution_address == execution_address))


def maybe_materialize(session, *, execution_address: str, dataset_classification: str | None,
                      strategy_key: str, strategy_module: str, strategy_version: str,
                      policy_address: str, execution_manifest: Mapping) -> dict | None:
    """Authenticate expected metadata before touching the ownerless table."""
    if not is_eligible(dataset_classification=dataset_classification, strategy_key=strategy_key,
                       strategy_module=strategy_module, execution_manifest=execution_manifest):
        return None
    item = PUBLIC_STRATEGY_CATALOG.get(strategy_key)
    if (item is None or strategy_version != item["version"]
            or not (_is_address(execution_address) and _is_address(policy_address))
            or policy_address != execution_address):
        return None
    row = _lookup(session, execution_address=execution_address)
    if row is None:
        return None
    if (row.dataset_address != execution_manifest["dataset_address"]
            or row.strategy_key != strategy_key or row.strategy_version != strategy_version
            or row.policy_address != policy_address or row.schema_version != SCHEMA_VERSION):
        raise PublicComputationIntegrityError("public computation metadata mismatch")
    if _digest(row.payload_json) != row.payload_digest:
        raise PublicComputationIntegrityError("public computation payload digest mismatch")
    payload = _decode_public_payload(row.payload_json)
    if (payload["strategy_key"] != strategy_key
            or payload["strategy_version"] != strategy_version
            or payload["params_hash"] != execution_address):
        raise PublicComputationIntegrityError("public computation payload semantic identity mismatch")
    return dict(payload, from_cache=True, computed_at=None)


def put_immutable(session, *, execution_address: str, dataset_address: str,
                  strategy_key: str, strategy_version: str, policy_address: str,
                  payload: Mapping) -> BacktestComputation:
    """Publish once; concurrent identical writers converge, conflicts refuse."""
    if not (_is_address(execution_address) and _is_address(dataset_address)
            and _is_address(policy_address) and policy_address == execution_address):
        raise PublicComputationIntegrityError("public computation address identity is invalid")
    if (payload.get("strategy_key") != strategy_key
            or payload.get("strategy_version") != strategy_version
            or payload.get("params_hash") != execution_address):
        raise PublicComputationIntegrityError("public computation payload semantic identity mismatch")
    payload_json = canonical_public_payload(payload)
    digest = _digest(payload_json)
    candidate = BacktestComputation(
        execution_address=execution_address, dataset_address=dataset_address,
        strategy_key=strategy_key, strategy_version=strategy_version,
        policy_address=policy_address, schema_version=SCHEMA_VERSION,
        payload_json=payload_json, payload_digest=digest)
    try:
        with session.begin_nested():
            session.add(candidate)
            session.flush()
        return candidate
    except IntegrityError:
        existing = _lookup(session, execution_address=execution_address)
        if existing is None:
            raise
        if not (existing.dataset_address == dataset_address and existing.strategy_key == strategy_key
                and existing.strategy_version == strategy_version
                and existing.policy_address == policy_address
                and existing.schema_version == SCHEMA_VERSION
                and existing.payload_digest == digest and existing.payload_json == payload_json):
            raise PublicComputationIntegrityError(
                "conflicting bytes for immutable public computation address")
        return existing
