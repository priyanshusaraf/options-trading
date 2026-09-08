"""Reusable, content-addressed backtest result cache."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import select

from app.db.models import BacktestResult
from app.backtest.artifacts import (
    ResearchCacheIdentity,
    research_cache_identity,
    research_cache_identity_document,
)

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
# v9: cache identity also binds the verified Phase 4 authority chain: owner, authored
#     IR, registry snapshot, resolved graph, implementation closure, declarations,
#     plan, capability assessment, dataset manifest, market truth, evaluation policy
#     and admission. A v8 artifact cannot prove that authority and must not be reused.
SCHEMA_VERSION = 9


def phase4_cache_identity(*, owner_id: str, authored_ir_address: str, manifest_address: str, registry_snapshot_address: str,
                          resolved_graph_address: str, implementation_closure_address: str,
                          declaration_addresses: tuple[str, ...], plan_address: str,
                          capability_assessment_address: str, market_truth_address: str,
                          evaluation_policy_address: str, admission_address: str) -> str:
    """Return a complete Phase 4 cache key; incomplete legacy facts fail closed."""
    from app.backtest.identity import phase4_binding_payload, require_content_address
    payload = phase4_binding_payload({
        "owner_id": owner_id, "authored_ir_address": authored_ir_address,
        "registry_snapshot_address": registry_snapshot_address,
        "resolved_graph_address": resolved_graph_address,
        "implementation_closure_address": implementation_closure_address,
        "declaration_addresses": declaration_addresses, "plan_address": plan_address,
        "capability_assessment_address": capability_assessment_address,
        "dataset_manifest_address": manifest_address,
        "market_truth_snapshot_address": market_truth_address,
        "evaluation_policy_address": evaluation_policy_address,
    })
    payload = {"scheme": "phase4-cache/1",
               "admission_address": require_content_address(admission_address),
               **payload}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verified_phase4_cache_identity(
    *, research_session, execution_session, owner_id: str, authored_ir_address: str,
    manifest_address: str, registry_snapshot_address: str, resolved_graph_address: str,
    implementation_closure_address: str, declaration_addresses: tuple[str, ...],
    plan_address: str, capability_assessment_address: str, market_truth_address: str,
    evaluation_policy_address: str, admission_address: str, plan, at_time: datetime,
) -> str:
    """Rebuild both-plane authority before minting a reusable result identity."""
    from app.market_data.authority import load_capability_assessment
    from research.domain.strategy_admissions import load_verified_dataset_authority

    dataset = load_verified_dataset_authority(
        research_session, owner_id=owner_id, manifest_address=manifest_address,
        execution_session=execution_session, at_time=at_time)
    assessment = load_capability_assessment(
        execution_session, capability_assessment_address, plan=plan, at_time=at_time)
    manifest = dataset.manifest
    if (manifest.owner_id != owner_id or manifest.manifest_address != manifest_address
            or assessment.authority_address != capability_assessment_address
            or assessment.owner_id != owner_id
            or assessment.dataset_manifest_address != manifest_address
            or assessment.plan_address != plan_address
            or assessment.registry_snapshot_address != registry_snapshot_address
            or assessment.market_truth_snapshot_address != market_truth_address
            or assessment.evaluation_policy_address != evaluation_policy_address):
        raise ValueError("Phase 4 cache authority chain is stale or mismatched")
    return phase4_cache_identity(
        owner_id=owner_id, authored_ir_address=authored_ir_address,
        manifest_address=manifest.manifest_address,
        registry_snapshot_address=registry_snapshot_address,
        resolved_graph_address=resolved_graph_address,
        implementation_closure_address=implementation_closure_address,
        declaration_addresses=declaration_addresses, plan_address=plan_address,
        capability_assessment_address=assessment.authority_address,
        market_truth_address=market_truth_address,
        evaluation_policy_address=evaluation_policy_address,
        admission_address=admission_address,
    )

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
    from app.backtest.identity import is_legacy_result_compatibility_alias
    if is_legacy_result_compatibility_alias(params_hash):
        return None
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
