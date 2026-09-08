---
{
  "id": "post-phase5-indicator-accuracy-session-data-assurance",
  "phase": "post-phase5",
  "status": "rejected",
  "kind": "independent_accuracy_assurance",
  "goal": "Independently accept or reject the exact session-data component/parameter/output universe and its resource/state evidence before integration.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Independently accept or reject the exact session-data component/parameter/output universe and its resource/state evidence before integration. Complete only with named source-bound evidence, protected-byte proof and the acceptance checks below; this does not authorize later scope."
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
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/semantic-contracts.md",
      "sections": [
        "ANCHORED_VWAP",
        "ASK",
        "BARS_SINCE_SESSION_OPEN",
        "BID",
        "BOOK_DEPTH",
        "CLOSE",
        "DISTANCE_FROM_SESSION_HIGH_LOW",
        "DTE",
        "EXPIRY_CALENDAR",
        "HIGH",
        "INSTRUMENT_METADATA",
        "LOW",
        "LTP",
        "MARKET_CLOCK",
        "MID",
        "OHLCV",
        "OPEN",
        "OPENING_RANGE",
        "OPEN_INTEREST",
        "PREVIOUS_SESSION_FIELDS",
        "PREVIOUS_SESSION_OHLC",
        "RESAMPLING",
        "SESSION_CALENDAR",
        "SESSION_HIGH",
        "SESSION_LOW",
        "SESSION_OPEN",
        "SESSION_OPEN_HIGH_LOW",
        "SPREAD",
        "TIMEFRAME",
        "TIME_TO_SESSION_CLOSE",
        "VWAP"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/source-authority.json",
      "sections": [
        "records"
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
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-session-data",
  "allowed_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_session_data_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_session_data_oracle.py",
    ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-data-assurance.md"
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
  "parallel_budget": 0,
  "assignments": [],
  "component_scope": [
    "ANCHORED_VWAP",
    "ASK",
    "BARS_SINCE_SESSION_OPEN",
    "BID",
    "BOOK_DEPTH",
    "CLOSE",
    "DISTANCE_FROM_SESSION_HIGH_LOW",
    "DTE",
    "EXPIRY_CALENDAR",
    "HIGH",
    "INSTRUMENT_METADATA",
    "LOW",
    "LTP",
    "MARKET_CLOCK",
    "MID",
    "OHLCV",
    "OPEN",
    "OPENING_RANGE",
    "OPEN_INTEREST",
    "PREVIOUS_SESSION_FIELDS",
    "PREVIOUS_SESSION_OHLC",
    "RESAMPLING",
    "SESSION_CALENDAR",
    "SESSION_HIGH",
    "SESSION_LOW",
    "SESSION_OPEN",
    "SESSION_OPEN_HIGH_LOW",
    "SPREAD",
    "TIMEFRAME",
    "TIME_TO_SESSION_CLOSE",
    "VWAP"
  ],
  "acceptance": [
    "Different assurance owner; oracle imports no product math or its helper code.",
    "Every claimed component/output and valid/invalid/seed/session state is tested in the locked product environment.",
    "An omission, wrong output binding or real numerical/state guard mutation fails the relevant consumer and is restored.",
    "No approved expected fixture is overwritten from product results; failures preserve rejected evidence.",
    "Pass is evidence for this wave only, not registry/publication or deployment authority."
  ],
  "test_plan": [
    "Read exact source and version/licence receipts before using a reference.",
    "Compare complete arrays/masks and threshold classes; separately verify parameter/output closure.",
    "Audit parameter-derived resource/state upper bounds, including max-domain and first-above-domain cases."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_session_data_assurance_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/review-package.json",
    "review_paths": [
      "paper-trader/backend/tests/test_indicator_accuracy_session_data_assurance.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_session_data_oracle.py",
      ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance"
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
    "output": ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/report.md",
    "verdicts": [
      "ASSURANCE"
    ],
    "max_rechecks": 0
  },
  "independence": "Must be a different owner from the corresponding implementation. Read product code, but author expected vectors independently; no product mutation. Product-changing findings return to an explicitly bounded correction.",
  "owner_task": "01a04b52-24fa-7ef0-80e9-add2c3de999c",
  "routing": {
    "path": ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/routing/decision.json",
    "sha256": "8b3919b8c20f7422e1af270f47e916e3da87c480b308583e4b845e713d2236ea"
  },
  "assurance_result": {
    "verdict": "ASSURANCE REJECT",
    "finding_ids": [
      "F01"
    ],
    "report": ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/report.md",
    "report_sha256": "747e0ec93508e18a21ccf1685f9411e9cf7121533154a0804fab47be1949bfb4",
    "evidence": ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/evidence.json",
    "evidence_sha256": "85d841b75ba2e1769b7c76412474947358352dabad1d05d3a8327fac3a634847",
    "review_package": ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/review-package.json",
    "review_package_sha256": "99922cbf12ad7994c124fc11ec722d96889536614fdddd00654f8832d56ca73d",
    "product_changes": 0,
    "publication": false,
    "deployment": false
  }
}
---

# Session data assurance

Independently accept or reject the exact session-data component/parameter/output universe and its resource/state evidence before integration.

This capsule is a future bounded assignment. The architecture replan does not start it.
