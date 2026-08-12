"""Neutral, immutable artifacts for *provably public* backtest computations.

This module deliberately has no owner argument.  A caller must first establish
eligibility from inputs it already holds; this code never probes a public address
for a private request.  The stored payload excludes run/result provenance and is
materialized into a new owner-local result by the sweep layer.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.backtest.cache import SCHEMA_VERSION
from app.db.models import BacktestComputation


MARKET_PUBLIC = "MARKET_PUBLIC"
_FORBIDDEN_SOURCE_FIELDS = frozenset({"id", "owner_id", "run_id", "cell_key"})
_LOCAL_RESULT_FIELDS = frozenset({"from_cache", "computed_at"})
_REQUIRED_MANIFEST_KEYS = frozenset({"dataset_address", "dataset_verified"})


class PublicComputationIntegrityError(RuntimeError):
    """The same content address was offered two different immutable payloads."""


def _canonical_payload(payload: Mapping) -> str:
    """Canonical pure-result bytes; provenance is rejected rather than copied."""
    forbidden = _FORBIDDEN_SOURCE_FIELDS & set(payload)
    if forbidden:
        raise PublicComputationIntegrityError(
            f"public computation payload contains source identity: {sorted(forbidden)!r}")
    public = {str(key): value for key, value in payload.items() if key not in _LOCAL_RESULT_FIELDS}
    try:
        encoded = json.dumps(public, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise PublicComputationIntegrityError("public computation payload is not canonical JSON") from exc
    return encoded


def _digest(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def is_eligible(*, dataset_classification: str | None, strategy_key: str,
                strategy_module: str, execution_manifest: Mapping) -> bool:
    """Conservative policy for the public namespace: every predicate is required."""
    if dataset_classification != MARKET_PUBLIC:
        return False
    if not isinstance(execution_manifest, Mapping) or not _REQUIRED_MANIFEST_KEYS <= set(execution_manifest):
        return False
    address = execution_manifest.get("dataset_address")
    if not isinstance(address, str) or len(address) != 64 or any(c not in "0123456789abcdef" for c in address):
        return False
    if execution_manifest.get("dataset_verified") is not True:
        return False
    # Checked-in registry modules are the sole V1 platform-public code path.
    if not strategy_key or strategy_key.startswith(("gen_", "ir.")):
        return False
    return strategy_module.startswith("app.strategy.registry.")


def strategy_is_platform_public(strategy) -> bool:
    """Prove provenance from the concrete checked-in registry implementation.

    Keys are not enough: a generated strategy and an IR adapter can both expose
    plausible keys.  Their classes are never defined in registry source modules.
    """
    key = getattr(strategy, "key", "")
    module = type(strategy).__module__
    if not is_eligible(dataset_classification=MARKET_PUBLIC, strategy_key=key,
                       strategy_module=module,
                       execution_manifest={"dataset_address": "0" * 64,
                                           "dataset_verified": True}):
        return False
    try:
        from app.strategy.registry import all_strategies
        return any(candidate is strategy for candidate in all_strategies())
    except Exception:
        return False


def _lookup(session, *, execution_address: str) -> BacktestComputation | None:
    return session.scalar(select(BacktestComputation).where(
        BacktestComputation.execution_address == execution_address))


def maybe_materialize(session, *, execution_address: str, dataset_classification: str | None,
                      strategy_key: str, strategy_module: str,
                      execution_manifest: Mapping) -> dict | None:
    """Return a local payload only after public eligibility, never before it."""
    if not is_eligible(dataset_classification=dataset_classification,
                       strategy_key=strategy_key, strategy_module=strategy_module,
                       execution_manifest=execution_manifest):
        return None
    return materialize(session, execution_address=execution_address)


def materialize(session, *, execution_address: str) -> dict | None:
    row = _lookup(session, execution_address=execution_address)
    if row is None:
        return None
    try:
        payload = json.loads(row.payload_json)
    except (TypeError, ValueError):
        raise PublicComputationIntegrityError("public computation payload is corrupt") from None
    if _digest(row.payload_json) != row.payload_digest or not isinstance(payload, dict):
        raise PublicComputationIntegrityError("public computation payload digest mismatch")
    # These fields are local result metadata and are never persisted globally.
    return dict(payload, from_cache=True, computed_at=None)


def put_immutable(session, *, execution_address: str, dataset_address: str,
                  strategy_key: str, strategy_version: str, policy_address: str,
                  payload: Mapping) -> BacktestComputation:
    """Insert once, converge on exact bytes, and refuse a conflicting address."""
    payload_json = _canonical_payload(payload)
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
        same = (existing.dataset_address == dataset_address
                and existing.strategy_key == strategy_key
                and existing.strategy_version == strategy_version
                and existing.policy_address == policy_address
                and existing.schema_version == SCHEMA_VERSION
                and existing.payload_digest == digest
                and existing.payload_json == payload_json)
        if not same:
            raise PublicComputationIntegrityError(
                "conflicting bytes for immutable public computation address")
        return existing
