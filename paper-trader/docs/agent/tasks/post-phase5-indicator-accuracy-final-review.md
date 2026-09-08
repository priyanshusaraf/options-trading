---
{
  "id": "post-phase5-indicator-accuracy-final-review",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "phase_review",
  "goal": "Independently review the sealed integrated accuracy correction programme and return separate SPEC and QUALITY verdicts without product mutation.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Independently review the sealed integrated accuracy correction programme and return separate SPEC and QUALITY verdicts without product mutation. Complete only with named source-bound evidence, protected-byte proof and the acceptance checks below; this does not authorize later scope."
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
  "dependency_gate": "post-phase5-indicator-accuracy-complete-universe-assurance",
  "allowed_paths": [
    ".agent/runs/post-phase5-indicator-accuracy-final-review",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-final-review.md"
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
    "owner_reasoning_effort": "high",
    "service_tier": "priority"
  },
  "owner_task": "01a04dad-2fc1-7fd3-b8e0-183a4d88bcfd",
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
    "SPEC PASS and QUALITY PASS on the exact integrated package are required before V0 verified catalogue readiness.",
    "Reject any omitted component/output, self-derived numerical oracle, stale runtime/source binding, silent legacy change or missing cache/result/resource proof.",
    "REFUSE dispositions remain unavailable and cannot be counted as numerical successes.",
    "All deployment/provider/TradingView/dependency/production gates remain explicit and closed."
  ],
  "test_plan": [
    "Inspect protected snapshots, all implementation/assurance logs, source provenance, actual consumer/mutation evidence and complete-universe coverage.",
    "One focused recheck at most; a second rejection requires a new bounded replan."
  ],
  "review": {
    "required": true,
    "assignment_id": "post_phase5_indicator_accuracy_final_review_reviewer",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-final-review/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/backtest/artifacts.py",
      "paper-trader/backend/app/backtest/cache.py",
      "paper-trader/backend/app/backtest/identity.py",
      "paper-trader/backend/app/backtest/public_computation.py",
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/app/ir/catalogue.py",
      "paper-trader/backend/app/ir/first_party/analytical_v2/common.py",
      "paper-trader/backend/app/ir/first_party/analytical_v2/contracts.py",
      "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
      "paper-trader/backend/app/ir/first_party/analytical_v2/multi_output.py",
      "paper-trader/backend/app/ir/first_party/analytical_v2/recursive_state.py",
      "paper-trader/backend/app/ir/first_party/analytical_v2/remaining_oracles.py",
      "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py",
      "paper-trader/backend/app/ir/implementation_identity.py",
      "paper-trader/backend/app/ir/incremental_runtime.py",
      "paper-trader/backend/app/ir/library.py",
      "paper-trader/backend/app/ir/node_contracts.py",
      "paper-trader/backend/app/ir/registry.py",
      "paper-trader/backend/app/ir/resolve.py",
      "paper-trader/backend/app/ir/resource_plan.py",
      "paper-trader/backend/app/ir/runtime.py",
      "paper-trader/backend/app/ir/streaming_reference.py",
      "paper-trader/backend/app/ir/v2_graph_versions.py",
      "paper-trader/backend/app/market_data/requirements.py",
      "paper-trader/backend/research/domain/admissions.py",
      "paper-trader/backend/research/domain/strategy_admissions.py",
      "paper-trader/backend/research/orchestrator/graph_experiment.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_core_math_oracle.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_lineage_assurance.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_multi_output_oracle.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_recursive_state_oracle.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_remaining_oracles_oracle.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_session_data_oracle.py",
      "paper-trader/backend/tests/test_indicator_accuracy_complete_universe.py",
      "paper-trader/backend/tests/test_indicator_accuracy_contract_assurance.py",
      "paper-trader/backend/tests/test_indicator_accuracy_contract_foundation.py",
      "paper-trader/backend/tests/test_indicator_accuracy_core_math.py",
      "paper-trader/backend/tests/test_indicator_accuracy_core_math_assurance.py",
      "paper-trader/backend/tests/test_indicator_accuracy_multi_output.py",
      "paper-trader/backend/tests/test_indicator_accuracy_multi_output_assurance.py",
      "paper-trader/backend/tests/test_indicator_accuracy_recursive_state.py",
      "paper-trader/backend/tests/test_indicator_accuracy_recursive_state_assurance.py",
      "paper-trader/backend/tests/test_indicator_accuracy_registry_lineage.py",
      "paper-trader/backend/tests/test_indicator_accuracy_remaining_oracles.py",
      "paper-trader/backend/tests/test_indicator_accuracy_remaining_oracles_assurance.py",
      "paper-trader/backend/tests/test_indicator_accuracy_session_data.py",
      "paper-trader/backend/tests/test_indicator_accuracy_session_data_assurance.py",
      ".agent/runs/post-phase5-indicator-accuracy-final-review"
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
    "output": ".agent/runs/post-phase5-indicator-accuracy-final-review/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1,
    "reason": "One bounded independent final critical review after every correction/assurance and integrated source/evidence package is sealed."
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
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "verdict_path": ".agent/runs/post-phase5-indicator-accuracy-final-review/verdict.json",
    "verdict_sha256": "45831006d549f005e091e4cb9ca45cee1231146b90ae4faea91b9db04f146a00",
    "review_package_sha256": "28b18f28e6f983055017f96b1c88662ab436921ad22cf66d1dc4d738588c477d",
    "finding_ids": ["F01"],
    "rechecks_used": 0,
    "rechecks_remaining": 1,
    "correction_capsule": "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-unavailable-proof-correction.md"
  },
  "final_recheck": {
    "verdict": "SPEC PASS / QUALITY PASS",
    "verdict_path": ".agent/runs/post-phase5-indicator-accuracy-final-review/recheck-verdict.json",
    "verdict_sha256": "eaaade1dfe2d9cc3ce61c48f43d515cdf75579dca8ca54fa8a1a80d67435326f",
    "review_package_sha256": "bad2132851a75b1ec199d488a8675d5f6d2e3116fb36e635c2593c49a723940c",
    "closure_seal_sha256": "7bd30c63eb2bd6eb52d4fe765ff556c8ad770a1c2206c06ba571ae049c7a451a",
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "finding_F01": "CLOSED",
    "publication": false,
    "deployment": false
  }
}

---

# Final review

Independently review the sealed integrated accuracy correction programme and return separate SPEC and QUALITY verdicts without product mutation.

This capsule is a future bounded assignment. The architecture replan does not start it.
