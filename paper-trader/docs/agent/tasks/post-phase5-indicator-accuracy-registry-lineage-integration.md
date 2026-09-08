---
{
  "id": "post-phase5-indicator-accuracy-registry-lineage-integration",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "critical_accuracy_correction",
  "goal": "Integrate only independently accepted version-2 contributors through the single registry and verify V0 eligibility, cache/result identity and legacy historical preservation at real consumers.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Integrate only independently accepted version-2 contributors through the single registry and verify V0 eligibility, cache/result identity and legacy historical preservation at real consumers. Complete only with named source-bound evidence, protected-byte proof and the acceptance checks below; this does not authorize later scope."
  },
  "implementation_result": {
    "verdict": "IMPLEMENTATION PASS",
    "registry_snapshot_address": "sha256:6eaf07bf7024826ec1a3b2b250289ba92b59fe2420924ab050d0e536405acd09",
    "complete_names": 125,
    "accepted_v2": 108,
    "unavailable": 17,
    "v1_exact": 125,
    "report": ".agent/runs/post-phase5-indicator-accuracy-registry-lineage-integration/report.md",
    "review_package": ".agent/runs/post-phase5-indicator-accuracy-registry-lineage-integration/review-package.json",
    "closure_seal": ".agent/runs/post-phase5-indicator-accuracy-registry-lineage-integration/closure-seal.json",
    "closure_seal_sha256": "4c43600682b65dba73a77a8c5324cc0673cf020c8b92603cecf5623a3717cacb",
    "protected_hashes_unchanged": true,
    "publication": false,
    "deployment": false,
    "later_stage_advanced": false
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "semantic-versioning",
    "complete-universe"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/architecture-decision.md",
      "sections": [
        "Immutable version 1",
        "Parameter-dependent contracts: bounded extension, no expression language",
        "Validity, sessions and outputs",
        "Source and oracle independence",
        "Sequencing and stopping rule"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/legacy-cache-result-policy.md",
      "sections": [
        "Version and graph identity",
        "Cache and result disposition",
        "Authority and compatibility"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/binding-contract-spec.json",
      "sections": [
        "source_contract",
        "binding_registration",
        "bound_contract",
        "validation_rules",
        "legacy"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/source-access-policy.md",
      "sections": [
        "Inspected sources",
        "Reference environment gate",
        "Deferred numerical conventions"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/verification-contract.md",
      "sections": [
        "Thresholds",
        "Complete-array comparators",
        "Adversarial fixtures",
        "Operational evidence"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-recursive-sar-source-replan/decision.json",
      "sections": [
        "controlling_reference",
        "native_comparison_policy",
        "corrected_target_delta",
        "source_provenance_update",
        "retained_gates",
        "version_and_history"
      ]
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-remaining-oracles-assurance",
  "allowed_paths": [
    "paper-trader/backend/app/ir/library.py",
    "paper-trader/backend/app/ir/catalogue.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/ir/streaming_reference.py",
    "paper-trader/backend/app/ir/incremental_runtime.py",
    "paper-trader/backend/app/ir/resource_plan.py",
    "paper-trader/backend/app/ir/v2_graph_versions.py",
    "paper-trader/backend/app/backtest/artifacts.py",
    "paper-trader/backend/app/backtest/cache.py",
    "paper-trader/backend/app/backtest/identity.py",
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/app/backtest/public_computation.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/research/domain/strategy_admissions.py",
    "paper-trader/backend/research/domain/admissions.py",
    "paper-trader/backend/research/orchestrator/graph_experiment.py",
    "paper-trader/backend/tests/test_indicator_accuracy_contract_foundation.py",
    "paper-trader/backend/tests/test_indicator_accuracy_registry_lineage.py",
    ".agent/runs/post-phase5-indicator-accuracy-registry-lineage-integration",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-registry-lineage-integration.md",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md"
  ],
  "protected_paths": [
    "paper-trader/backend/app/ir/first_party/analytical.py",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/migrations",
    "paper-trader/scripts/deploy.sh"
  ],
  "nonclaims": [
    "No frontend, provider network/credentials, private TradingView, dependency adoption, SQL migration, deployment/VPS, live/order/money, or Phase 6 work. No edits to legacy analytical.py or accepted component semantics.",
    "Planning records and test totals are not a numerical or deployment acceptance."
  ],
  "owner_gates": [
    "Start only after the predecessor is accepted and this exact bounded assignment is authorized by the programme/owner.",
    "Stop before an in-place v1 semantic/address change, an undeclared schema/dependency/provider/execution change, or a cross-wave shared-file edit."
  ],
  "stop_conditions": [
    "Any claimed component/output/contract field is missing or a test expected value is self-derived from product math.",
    "A v1 source, descriptor, contract, declaration or implementation address changes.",
    "An unaccepted v2 implementation becomes product-eligible, or registry/cache/result identity is silently rewritten.",
    "A writer reaches a path owned by another wave without serial integration ownership."
  ],
  "deployment_impact": {
    "classification": "compatible versioned analytical/runtime change; no SQL migration authorized",
    "required_evidence": "Name exact artifacts, locked runtime, resource bounds, semantic/cache identity and refusal evidence; unresolved release assembly belongs to strategy-os-v0-security-operations-deployability before its acceptance."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "owner_task": "01a04d63-4ff7-7833-9ee9-a77f72fe2c97",
  "parallel_budget": 0,
  "assignments": [],
  "component_scope": [
    "ACCUMULATION_DISTRIBUTION",
    "ADX",
    "ALPHA",
    "ANCHORED_VWAP",
    "ASK",
    "ATR",
    "BARS_SINCE_SESSION_OPEN",
    "BETA",
    "BETA_ADJUSTED_SPREAD",
    "BID",
    "BOLLINGER_BANDS",
    "BOLLINGER_BANDWIDTH",
    "BOLLINGER_PERCENT_B",
    "BOOK_DEPTH",
    "CCI",
    "CHAIKIN_MONEY_FLOW",
    "CHAIKIN_OSCILLATOR",
    "CLOSE",
    "CORRELATION",
    "COVARIANCE",
    "CROSS_ABOVE",
    "CROSS_BELOW",
    "CUMULATIVE_RETURN",
    "DISTANCE_FROM_SESSION_HIGH_LOW",
    "DONCHIAN_CHANNELS",
    "DTE",
    "EMA",
    "EWMA_VOLATILITY",
    "EXPIRY_CALENDAR",
    "FALLING",
    "GAP",
    "GAP_DOWN",
    "GAP_UP",
    "GARMAN_KLASS",
    "HIGH",
    "HL2",
    "HLC3",
    "ICHIMOKU_COMPONENTS",
    "INSIDE_BAR",
    "INSTRUMENT_METADATA",
    "KAMA",
    "KELTNER_CHANNELS",
    "LINEAR_REGRESSION_INTERCEPT",
    "LINEAR_REGRESSION_SLOPE",
    "LOG_RETURN",
    "LOW",
    "LTP",
    "MACD",
    "MAD",
    "MARKET_CLOCK",
    "MA_SLOPE",
    "MFI",
    "MID",
    "MIDPOINT",
    "MINUS_DI",
    "MOMENTUM",
    "NATR",
    "OBV",
    "OHLC4",
    "OHLCV",
    "OPEN",
    "OPENING_RANGE",
    "OPEN_INTEREST",
    "OUTSIDE_BAR",
    "PARABOLIC_SAR",
    "PARKINSON",
    "PERCENTILE",
    "PERCENTILE_RANK",
    "PERCENT_RETURN",
    "PLUS_DI",
    "POINT_CHANGE",
    "PPO",
    "PREVIOUS_SESSION_FIELDS",
    "PREVIOUS_SESSION_OHLC",
    "PRICE_MA_DISTANCE",
    "PRICE_VOLUME_TREND",
    "RATIO",
    "REALIZED_VOLATILITY",
    "RELATIVE_VOLUME",
    "RESAMPLING",
    "RESIDUAL",
    "RISING",
    "RMA_WILDER",
    "ROC",
    "ROGERS_SATCHELL",
    "ROLLING_HEDGE_RATIO",
    "ROLLING_HIGH",
    "ROLLING_LOW",
    "ROLLING_MAX",
    "ROLLING_MEAN",
    "ROLLING_MEDIAN",
    "ROLLING_MIN",
    "ROLLING_RANK",
    "ROLLING_REGRESSION",
    "ROLLING_RETURN",
    "ROLLING_STDDEV",
    "ROLLING_VARIANCE",
    "ROLLING_VOLUME_PERCENTILE",
    "RSI",
    "R_SQUARED",
    "SESSION_CALENDAR",
    "SESSION_HIGH",
    "SESSION_LOW",
    "SESSION_OPEN",
    "SESSION_OPEN_HIGH_LOW",
    "SMA",
    "SPREAD",
    "STOCHASTIC",
    "STOCH_RSI",
    "SUPERTREND",
    "TIMEFRAME",
    "TIME_TO_SESSION_CLOSE",
    "TREND_PERSISTENCE",
    "TRUE_RANGE",
    "TYPICAL_PRICE",
    "VOLATILITY_PERCENTILE",
    "VOLATILITY_RANK",
    "VOLUME_ZSCORE",
    "VWAP",
    "VWMA",
    "WEIGHTED_CLOSE",
    "WILLIAMS_R",
    "WMA",
    "YANG_ZHANG",
    "ZSCORE"
  ],
  "acceptance": [
    "Single app.ir.library composition; all 125 names have an explicit accepted-v2 or unavailable disposition, and all v1 bytes/addresses remain exact.",
    "No aggregate contributor or cache-version shortcut silently relabels old graphs/results; complete template/bound/source/implementation identity reaches actual cache and job consumers.",
    "New V0 analytical research rejects unaccepted dependencies; standard-profile execution and existing risk reduction remain unchanged.",
    "Unknown historical environment/snapshot is explicitly unreproducible, never replayed with current code under an old identity.",
    "Frozen numerical-wave module hashes remain unchanged through integration; any correction returns to its exact owning capsule.",
    "No frontend/API catalogue exposure beyond the later owner-gated verified-language capsule."
  ],
  "test_plan": [
    "Actual authoring/resolution/job claim/reclaim/cache hit+miss/result load/public computation consumers, not only cache-key helper tests.",
    "Stale source/template/bound contract/registry/implementation/parameter/session identities miss or refuse; cross-tenant and restored old-row cases.",
    "V0 no-runner/no-lease/execution denial and ordinary standard compatibility selectors; source, dependency and protected-byte freezes."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_registry_lineage_integration_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-registry-lineage-integration/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/library.py",
      "paper-trader/backend/app/ir/catalogue.py",
      "paper-trader/backend/app/ir/runtime.py",
      "paper-trader/backend/app/ir/streaming_reference.py",
      "paper-trader/backend/app/ir/incremental_runtime.py",
      "paper-trader/backend/app/ir/resource_plan.py",
      "paper-trader/backend/app/ir/v2_graph_versions.py",
      "paper-trader/backend/app/backtest/artifacts.py",
      "paper-trader/backend/app/backtest/cache.py",
      "paper-trader/backend/app/backtest/identity.py",
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/app/backtest/public_computation.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/research/domain/strategy_admissions.py",
      "paper-trader/backend/research/domain/admissions.py",
      "paper-trader/backend/research/orchestrator/graph_experiment.py",
      "paper-trader/backend/tests/test_indicator_accuracy_contract_foundation.py",
      "paper-trader/backend/tests/test_indicator_accuracy_registry_lineage.py",
      ".agent/runs/post-phase5-indicator-accuracy-registry-lineage-integration"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/ir/first_party/analytical.py",
      "paper-trader/frontend",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/app/providers",
      "paper-trader/backend/migrations",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/post-phase5-indicator-accuracy-registry-lineage-integration/report.md",
    "verdicts": [
      "IMPLEMENTATION"
    ],
    "max_rechecks": 0
  },
  "accepted_source_addenda": [
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-recursive-sar-source-replan/decision.json",
      "sha256": "4d5d654326d8665fc94f44aaf08736305d59843e2cd9ecbd726de143ebec5e0e",
      "component": "PARABOLIC_SAR",
      "scope": "New unpublished mathematical source target only; old strict-native promise remains rejected. No formula, threshold, domain, precision or mask change.",
      "superseded_fields": [
        "source",
        "variant",
        "zero_undefined_policy strict-native promise"
      ],
      "original_replan_bytes_immutable": true
    }
  ],
  "implementation_result": {
    "verdict": "IMPLEMENTATION PASS",
    "owner_task": "01a04d63-4ff7-7833-9ee9-a77f72fe2c97",
    "report": ".agent/runs/post-phase5-indicator-accuracy-registry-lineage-integration/report.md",
    "report_sha256": "36237b15c36840e1133e137cb1c44899c94111395313ae2b59bbae30e3e93e44",
    "review_package_sha256": "041527847934434566c9c432345bb526108217c786a1ebf012d5e1d4770db479",
    "closure_seal_sha256": "4c43600682b65dba73a77a8c5324cc0673cf020c8b92603cecf5623a3717cacb",
    "accepted_v2": 108,
    "unavailable": 17,
    "v1_exact": 125,
    "affected_checks": 163,
    "final_f03_cache_registry_checks": 108,
    "publication": false,
    "deployment": false
  }
}

---

# Registry lineage integration

Integrate only independently accepted version-2 contributors through the single registry and verify V0 eligibility, cache/result identity and legacy historical preservation at real consumers.

This capsule is a future bounded assignment. The architecture replan does not start it.
