---
{
  "id": "post-phase5-indicator-accuracy-complete-universe-assurance",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "independent_accuracy_assurance",
  "goal": "Independently verify the integrated 125-component disposition universe and all real research/cache/runtime boundaries before final accuracy review.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Independently verify the integrated 125-component disposition universe and all real research/cache/runtime boundaries before final accuracy review. Complete only with named source-bound evidence, protected-byte proof and the acceptance checks below; this does not authorize later scope."
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
  "dependency_gate": "post-phase5-indicator-accuracy-registry-lineage-integration",
  "allowed_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_complete_universe.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_lineage_assurance.py",
    ".agent/runs/post-phase5-indicator-accuracy-complete-universe-assurance",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-complete-universe-assurance.md"
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
    "classification": "evidence-only",
    "required_evidence": "Name exact artifacts, locked runtime, resource bounds, semantic/cache identity and refusal evidence; unresolved release assembly belongs to strategy-os-v0-security-operations-deployability before its acceptance."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "owner_task": "01a04d8b-8612-70e1-8131-b1df67fced48",
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
    "All 125 explicit outcomes, every named output/parameter/contract field/binding rule, every source and every consumer in the impact matrix are independently enumerated.",
    "No numerical PASS is counted for unavailable components; each has tested stable refusal at the advertised boundary.",
    "Omission, duplicate, stale, reordered, self-derived and wrong-binding mutations are killed by independent consumers.",
    "V1 invariance, batch/stream/restart/causality, locked environments, source licences, resource ceilings and cache/result preservation have direct evidence.",
    "One sealed final package binds exact dirty source bytes, artifacts and all logs; no deployment or frontend claim."
  ],
  "test_plan": [
    "Run the complete scoped conformance matrix and relevant backend/research subsystem selectors once after integration.",
    "Independently recompute full-universe closure and legacy/current identity differences.",
    "Test a failed/reclaimed research job cannot resume under changed source or component semantics; retain historical result evidence."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_complete_universe_assurance_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-complete-universe-assurance/review-package.json",
    "review_paths": [
      "paper-trader/backend/tests/test_indicator_accuracy_complete_universe.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_lineage_assurance.py",
      ".agent/runs/post-phase5-indicator-accuracy-complete-universe-assurance"
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
    "output": ".agent/runs/post-phase5-indicator-accuracy-complete-universe-assurance/report.md",
    "verdicts": [
      "ASSURANCE"
    ],
    "max_rechecks": 0
  },
  "independence": "Must be a different owner from the corresponding implementation. Read product code, but author expected vectors independently; no product mutation. Product-changing findings return to an explicitly bounded correction.",
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
  "assurance_result": {
    "verdict": "ASSURANCE PASS",
    "owner_task": "01a04d8b-8612-70e1-8131-b1df67fced48",
    "report_sha256": "4d8bcbe34d95c2e4b5328b073a1af5f96e2926903d8d3ce427351530d166ef29",
    "evidence_sha256": "cd8da7af6d2c91e0fcd09c247f162552bbc507a111d9fa43b82c8df58611f370",
    "review_package_sha256": "c20eef43ba5fe7a1e0964366b3a1ad623fd68ce5ede6527a94b13c8f07269be9",
    "closure_seal_sha256": "f325e4f1b7fed6945d8fffa11b284e1f959a214377f977a32ec85540e567ec3e",
    "focused_checks": 14,
    "affected_passed": 169,
    "affected_skipped_postgresql": 3,
    "publication": false,
    "deployment": false
  }
}

---

# Complete universe assurance

Independently verify the integrated 125-component disposition universe and all real research/cache/runtime boundaries before final accuracy review.

This capsule is a future bounded assignment. The architecture replan does not start it.
