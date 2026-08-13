"""Pure content identities for reusable backtest results.

The dataset address is deliberately stricter than the old final-timestamp key:
it binds ordered candle bytes and the context needed to explain which series
was requested.  Execution identity is built below from a closed manifest.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import importlib
import inspect
import json
import math
from pathlib import Path
import struct
import sys
from collections.abc import Mapping, Sequence
from typing import Any
from zoneinfo import ZoneInfo


DATASET_IDENTITY_SCHEME = "backtest-dataset/1"
EXECUTION_IDENTITY_SCHEME = "backtest-execution/1"
_IST = ZoneInfo("Asia/Kolkata")
_UTC = dt.timezone.utc
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=_UTC)
_CANDLE_FLOATS = ("open", "high", "low", "close", "volume")
# The exact field sets `ordered_dataset_address` resolves its source context
# from.  A store that persists a dataset must record the SAME resolution, or a
# reloaded dataset re-addresses differently and is (correctly) refused.
PROVIDER_IDENTITY_FIELDS = ("key", "name", "provider")
INSTRUMENT_IDENTITY_FIELDS = ("key", "spot_exchange", "spot_symbol")


def _stable(value: Any) -> Any:
    """A deterministic JSON value, preserving distinctions relevant to identity."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"identity metadata contains non-finite float {value!r}")
        return {"__float_hex__": value.hex()}
    if isinstance(value, dt.datetime):
        return {"__timestamp_us__": _timestamp_us(value)}
    if isinstance(value, dt.date):
        return {"__date__": value.isoformat()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _stable(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _stable(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [_stable(v) for v in value]
    if isinstance(value, (set, frozenset)):
        items = [_stable(v) for v in value]
        return sorted(items, key=lambda item: _canonical_json(item))
    raise ValueError(f"identity metadata cannot encode {type(value).__name__}")


def _canonical_json(value: Any) -> str:
    return json.dumps(_stable(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def _timestamp_us(value: Any) -> int:
    if not isinstance(value, dt.datetime):
        raise ValueError(f"candle timestamp must be datetime, not {type(value).__name__}")
    aware = value.replace(tzinfo=_IST) if value.tzinfo is None else value.astimezone(_UTC)
    utc = aware.astimezone(_UTC)
    delta = utc - _EPOCH
    return ((delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds)


def _field(candle: Any, name: str) -> Any:
    if isinstance(candle, Mapping):
        return candle.get(name)
    return getattr(candle, name, None)


def _named_identity(value: Any, *, fields: Sequence[str]) -> Any:
    if isinstance(value, (str, int, float, bool, Mapping)) or value is None:
        return value
    explicit = getattr(value, "cache_identity", None)
    if callable(explicit):
        explicit = explicit()
    if explicit is not None:
        return explicit
    found = {name: getattr(value, name) for name in fields if hasattr(value, name)}
    found["type"] = f"{type(value).__module__}.{type(value).__qualname__}"
    return found


def source_identity(value: Any, *, fields: Sequence[str]) -> Any:
    """Public form of the source-context resolution used by the dataset address."""
    return _named_identity(value, fields=fields)


def ordered_dataset_address(candles: Sequence[Any], *, provider: Any,
                            instrument: Any, interval: str,
                            requested_window: Any,
                            effective_window: Any) -> str:
    """Return SHA-256 for the exact ordered OHLCV dataset and its source context.

    Naive timestamps are the project's native naive-IST clock.  Aware timestamps
    are normalized to the same instant, at microsecond precision.  Floats are
    packed as IEEE-754 binary64, avoiding rounded display serialization.
    """
    metadata = {
        "scheme": DATASET_IDENTITY_SCHEME,
        "provider": _named_identity(provider, fields=PROVIDER_IDENTITY_FIELDS),
        "instrument": _named_identity(
            instrument, fields=INSTRUMENT_IDENTITY_FIELDS),
        "interval": interval,
        "requested_window": requested_window,
        "effective_window": effective_window,
    }
    digest = hashlib.sha256()
    encoded = _canonical_json(metadata).encode("utf-8")
    digest.update(struct.pack(">I", len(encoded)))
    digest.update(encoded)
    digest.update(struct.pack(">Q", len(candles)))

    for index, candle in enumerate(candles):
        stamp = _timestamp_us(_field(candle, "ts"))
        values = []
        for name in _CANDLE_FLOATS:
            raw = _field(candle, name)
            try:
                number = float(raw)
            except (TypeError, ValueError):
                raise ValueError(f"candle {index} {name} must be a finite number") from None
            if not math.isfinite(number):
                raise ValueError(f"candle {index} {name} must be finite, got {raw!r}")
            values.append(number)
        digest.update(struct.pack(">q5d", stamp, *values))
    return digest.hexdigest()


def _module_bytes(module: Any) -> bytes | None:
    """Read source bytes afresh so an in-process deploy cannot reuse old code."""
    path = getattr(module, "__file__", None)
    if not path:
        return None
    source = Path(path)
    if source.suffix in {".pyc", ".pyo"}:
        source = source.with_suffix(".py")
    try:
        return source.read_bytes()
    except OSError:
        return None


def _callable_identity(fn: Any) -> dict[str, Any] | None:
    target = getattr(fn, "__func__", fn)
    try:
        source = inspect.getsource(target)
    except (OSError, TypeError):
        return None
    return {
        "module": getattr(target, "__module__", ""),
        "qualname": getattr(target, "__qualname__", ""),
        "source": source,
    }


def transitive_module_source_digest(*, modules: Sequence[Any],
                                    implementation_maps: Sequence[Mapping] = ()) \
        -> str | None:
    """Hash executable module bytes plus dynamically selected implementations.

    A missing source is a safe cache miss, represented by ``None``.  Falling back
    to a module name would be a plausible-looking identity that survives a code
    change, which is the unsafe direction for a result cache.
    """
    all_modules = {getattr(module, "__name__", ""): module for module in modules}
    implementation_rows = []
    for map_index, impl_map in enumerate(implementation_maps):
        for address, fn in sorted(impl_map.items(), key=lambda item: str(item[0])):
            manifest = _callable_identity(fn)
            module_name = getattr(fn, "__module__", "")
            module = sys.modules.get(module_name)
            if manifest is None or module is None:
                return None
            all_modules[module_name] = module
            implementation_rows.append({
                "map": map_index, "address": str(address), "callable": manifest,
            })

    digest = hashlib.sha256()
    digest.update(b"backtest-module-source/1\0")
    for name, module in sorted(all_modules.items()):
        name = getattr(module, "__name__", "")
        source = _module_bytes(module)
        if not name or source is None:
            return None
        name_bytes = name.encode("utf-8")
        digest.update(struct.pack(">I", len(name_bytes)))
        digest.update(name_bytes)
        digest.update(struct.pack(">Q", len(source)))
        digest.update(source)

    encoded = _canonical_json(implementation_rows).encode()
    digest.update(struct.pack(">I", len(encoded)))
    digest.update(encoded)
    return digest.hexdigest()


def _execution_modules(strategy: Any) -> tuple[Any, ...]:
    names = {
        "app.backtest.engine",
        "app.backtest.metrics",
        "app.backtest.premium",
        "app.backtest.ratchet",
        "app.engine.charges",
        "app.engine.decision_kernel",
        "app.engine.event_risk",
        "app.engine.exit_monitor",
        "app.market_data.candles",
        "app.options.pricing",
        type(strategy).__module__,
    }
    try:
        return tuple(sys.modules.get(name) or importlib.import_module(name)
                     for name in sorted(names))
    except (ImportError, ValueError):
        return ()


def execution_result_address(*, dataset_address: str, instrument: Any,
                             strategy: Any, parameters: Mapping[str, Any],
                             capital: float, window: Any, slippage_pct: float,
                             admission_address: str,
                             implementation_maps: Sequence[Mapping] = ()) -> str | None:
    """Return the full address of one deterministic backtest computation.

    The manifest deliberately reads mutable policy globals at call time.  A rate,
    event rule, premium assumption, exit policy, or selected implementation change
    must make the next run cold even when candle data and timestamps are unchanged.
    """
    from app.backtest import engine, premium
    from app.engine import charges, event_risk

    version = getattr(strategy, "version", None)
    if not version or str(version).lower() == "unknown":
        return None
    if len(dataset_address) != 64 or any(c not in "0123456789abcdefABCDEF"
                                         for c in dataset_address):
        return None
    if (not isinstance(admission_address, str)
            or len(admission_address) != 71
            or not admission_address.startswith("sha256:")
            or any(c not in "0123456789abcdef" for c in admission_address[7:])):
        return None
    if not math.isfinite(float(capital)) or not math.isfinite(float(slippage_pct)):
        return None
    maps = list(implementation_maps)
    strategy_implementations = getattr(strategy, "implementations", None)
    if isinstance(strategy_implementations, Mapping) and not any(
            strategy_implementations is item for item in maps):
        maps.append(strategy_implementations)
    modules = _execution_modules(strategy)
    if not modules:
        return None
    source_address = transitive_module_source_digest(
        modules=modules, implementation_maps=maps)
    if source_address is None:
        return None

    resolved_premium = dict(premium.DEFAULT_PREMIUM_PARAMS)
    resolved_premium.update({
        key: value for key, value in parameters.items()
        if key in resolved_premium
    })
    manifest = {
        "scheme": EXECUTION_IDENTITY_SCHEME,
        "dataset_address": dataset_address.lower(),
        "admission_address": admission_address,
        "instrument": _named_identity(
            instrument,
            fields=("key", "name", "segment", "lot_size", "strike_step", "has_options"),
        ),
        "strategy": {
            "key": getattr(strategy, "key", ""),
            "version": str(version),
            "default_params": getattr(strategy, "default_params", {}),
            "declared_warmup": getattr(strategy, "declared_warmup", None),
            "risk_model": getattr(strategy, "risk_model", None),
        },
        "parameters": parameters,
        "capital": capital,
        "window": window,
        "slippage_pct": slippage_pct,
        "source_address": source_address,
        "charge_schedule": charges.CHARGE_SCHEDULE,
        "backtest_segment_map": engine._BACKTEST_SEGMENT,
        "spot_charge_segment": engine.backtest_charge_segment(instrument),
        "event_rules": event_risk.DEFAULT_RULES,
        "backtest_exit_policy": engine.BACKTEST_EXIT_POLICY,
        "premium_model": {
            "parameters": resolved_premium,
            "risk_free_rate": premium.RISK_FREE_RATE,
            "rv_window_days": premium.RV_WINDOW_DAYS,
            "iv_floor": premium.IV_FLOOR,
            "iv_ceil": premium.IV_CEIL,
            "expiry_floor_years": premium.EXPIRY_FLOOR_YEARS,
            "min_entry_premium": premium.MIN_ENTRY_PREMIUM,
            "seconds_per_year": premium.SECONDS_PER_YEAR,
        },
    }
    return hashlib.sha256(_canonical_json(manifest).encode("utf-8")).hexdigest()


__all__ = ["DATASET_IDENTITY_SCHEME", "EXECUTION_IDENTITY_SCHEME",
           "PROVIDER_IDENTITY_FIELDS", "INSTRUMENT_IDENTITY_FIELDS",
           "source_identity", "ordered_dataset_address",
           "transitive_module_source_digest", "execution_result_address"]
