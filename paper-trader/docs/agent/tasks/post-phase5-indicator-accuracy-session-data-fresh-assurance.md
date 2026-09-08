---
{
  "id": "post-phase5-indicator-accuracy-session-data-fresh-assurance",
  "phase": "post-phase5",
  "status": "rejected",
  "kind": "independent_accuracy_assurance",
  "goal": "Independently accept or reject the corrected 31-component session-data wave after the sealed missing-first-session-prefix F01 recovery.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Seal ASSURANCE PASS or REJECT for all 31 decisions, 17 candidates, 14 refusals, complete arrays/masks/session-prefix/state/restart/resource/identity and prior-F01 boundaries using independently authored evidence. No product mutation, publication or later-scope work."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "semantic-versioning",
    "complete-universe",
    "independent-assurance"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/report.md",
      "sections": [
        "Verdict",
        "F01 — missing first-session history is silently accepted",
        "Evidence accepted within the rejected wave",
        "Required correction route"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/findings.json",
      "sections": [
        "findings"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-session-data/report.md",
      "sections": [
        "Verdict",
        "Verification",
        "Limits"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-session-data/closure-seal.json",
      "sections": [
        "counts",
        "protected_sha256",
        "artifacts"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-assurance/report.md",
      "sections": [
        "Session context binding independent assurance"
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
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-session-data",
  "allowed_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_session_data_fresh_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_session_data_fresh_oracle.py",
    ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-data-fresh-assurance.md"
  ],
  "new_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_session_data_fresh_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_session_data_fresh_oracle.py",
    ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance"
  ],
  "protected_paths": [
    "paper-trader/backend/app",
    "paper-trader/backend/research",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data.py",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_session_data_oracle.py",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/backend/migrations",
    "paper-trader/scripts/deploy.sh"
  ],
  "stable_input_hashes": {
    "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py": "7dd508c41cb267f7fe571b60fef414c3244b6c3373178c043226811213a4b897",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data.py": "6b7924a0ea1a3d5aaf768aec9c72b2023ffcd81a6677fda785413841815cc714",
    ".agent/runs/post-phase5-indicator-accuracy-session-data/closure-seal.json": "6de01a2b59e4a07eee68bd5c58777d8d0152d3f62063f5e7c36d6e35750454ec",
    ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/report.md": "747e0ec93508e18a21ccf1685f9411e9cf7121533154a0804fab47be1949bfb4",
    ".agent/runs/post-phase5-indicator-accuracy-session-data-assurance/findings.json": "44ee328a8218044b31c66da37fa6c1c179db1e82e4531cccee31aba58cf9ddf0",
    ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-assurance/closure-seal.json": "4c04161d7d390914981f8f8fe56eee549faf0cca854267d4fbcb61e21e2b91ef",
    "paper-trader/backend/app/ir/registry.py": "4c1d83e9f8714d9e8a11e571426cde6b7a896fe47aec3d3fe1a44b4f58bf120f",
    "paper-trader/backend/app/ir/node_contracts.py": "a1e16b735cd8decfcad4356aa82c10a20d65c5129f25d78ae7931ad9596af284",
    "paper-trader/backend/app/market_data/requirements.py": "d1d0a4b278a4d2d503667197c384ee07b0d58c790fa1726ada8e9bfbea8354d4"
  },
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
  "scope": [
    "Use a fresh owner distinct from implementation and the previous rejected assurance owner. Do not import product math or owner expected-value helpers into independent oracles.",
    "Reproduce the previous F01 against the archived pre-correction behavior or isolated mutation, then prove every affected current candidate refuses a missing first canonical session bar using explicit session-open evidence.",
    "Independently verify all 31 decisions, every output/parameter/validity/refusal, complete arrays, overnight/shortened/holiday sessions, missing internal/first bars, anchors, batch/stream/restart and max/first-above resource bounds.",
    "Preserve the 125 legacy and 84 previously accepted v2 identities and explain every corrected session candidate identity. No registry publication."
  ],
  "acceptance": [
    "Exactly 17 candidates and 14 typed refusals are accounted for; no executable placeholder or omitted output.",
    "All eight prior F01 candidates refuse a second-slot start and incomplete prior-session aggregate; complete canonical prefixes still pass.",
    "Every complete array/mask and threshold class passes independent expected values in the locked product environment.",
    "Batch, stream, snapshot/restart and cold replay agree across warmup, gaps, reversals, session boundaries and anchors.",
    "Resource/state/history upper bounds and first-above-domain refusals are independently challenged.",
    "At least three genuine isolated omissions/guard mutations fail intended assertions and restore exact source/test bytes.",
    "Protected/current hashes and historical rejection artifacts remain exact. PASS authorizes only this wave, not registry publication, provider data, frontend or deployment."
  ],
  "test_plan": [
    "Fresh independent focused tests and Decimal/specification/canonical-session oracles, then current owner compatibility and applicable real resolver/materializer/runtime consumers.",
    "Record every failure and skip. Do not weaken thresholds, overwrite fixtures or convert unavailable data to zero/HOLD."
  ],
  "independence": {
    "owner_must_differ": true,
    "history_fork": false,
    "agents": 0,
    "product_edits": 0
  },
  "concurrent_side_assignments": [
    "v0_data_only_connection",
    "v0_local_release_operations",
    "v0_frontend_production_convergence_foundation"
  ],
  "parallel_budget": 3,
  "assignments": [
    {
      "id": "v0_data_only_connection",
      "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-data-only-connection-contract.md",
      "owner_task": "/root/v0_data_only_connection",
      "write_paths": [
        "paper-trader/backend/app/api/connection_routes.py",
        "paper-trader/backend/app/providers/connection_store.py",
        "paper-trader/backend/tests/test_connection_routes.py",
        "paper-trader/backend/tests/test_connection_store.py",
        ".agent/runs/strategy-os-v0-data-only-connection-contract"
      ],
      "status": "active"
    },
    {
      "id": "v0_local_release_operations",
      "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-local-release-operations.md",
      "owner_task": "/root/v0_local_release_operations",
      "write_paths": [
        "paper-trader/backend/scripts/v0_local_release_evidence.py",
        "paper-trader/backend/tests/test_v0_local_release_operations.py",
        "paper-trader/backend/research_tests/test_v0_local_release_operations.py",
        ".agent/runs/strategy-os-v0-local-release-operations"
      ],
      "status": "active"
    },
    {
      "id": "v0_frontend_production_convergence_foundation",
      "capsule": "paper-trader/docs/agent/tasks/strategy-os-v0-frontend-production-convergence-foundation.md",
      "owner_task": "/root/v0_frontend_production_convergence",
      "write_paths": [
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/main.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product",
        ".agent/runs/strategy-os-v0-frontend-production-convergence-foundation"
      ],
      "status": "active"
    }
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "owner_task": "/root/session_data_fresh_assurance",
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_session_data_fresh_assurance",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/review-package.json",
    "review_paths": [
      "paper-trader/backend/tests/test_indicator_accuracy_session_data_fresh_assurance.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_session_data_fresh_oracle.py",
      "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-data-fresh-assurance.md",
      ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance"
    ],
    "exclude_paths": [
      "paper-trader/backend/app",
      "paper-trader/frontend",
      "paper-trader/backend/migrations",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/report.md",
    "verdicts": [
      "ASSURANCE"
    ],
    "max_rechecks": 0
  },
  "owner_gates": [
    "Standing V0 authority and the accepted current implementation seal open this fresh assurance. No repeated user token is required.",
    "Stop before any product correction, registry/publication, provider/network, frontend, migration, deployment, live/order/money or later-stage work."
  ],
  "stop_conditions": [
    "Any protected product/source byte or accepted expected fixture must change to make assurance pass.",
    "Any claimed component/output/parameter/mask/session-prefix case is omitted or expected values derive from product math.",
    "The previous F01 cannot be independently reproduced/killed or any affected current candidate still accepts a missing first canonical session bar.",
    "A legacy or previously accepted v2 identity changes outside the exact corrected session candidate closure."
  ],
  "closure": {
    "verdict": "ASSURANCE REJECT",
    "finding_ids": [
      "F01-FRESH"
    ],
    "reason": "The protected implementation still omits SESSION_OPEN_AT from the eight prior-F01 candidate contracts. All eight accept a second-slot suffix, and the two previous-session candidates can expose the resulting incomplete aggregate as a completed prior session.",
    "passing_remainder": 56,
    "focused_failures": 2,
    "compatibility_passed": 89,
    "compatibility_failed": 1,
    "mutations_killed": 4,
    "product_edits": 0,
    "report": ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/report.md",
    "closure_seal": ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/closure-seal.json"
  },
  "deployment_impact": {
    "classification": "evidence-only; no deployment change"
  },
  "nonclaims": [
    "No provider/calendar real-data certification, registry publication, frontend, schema, paper/live, order, money, deployment or V0 completion.",
    "Passing test counts alone do not establish complete-universe or release acceptance."
  ]
}
---

# Fresh corrected session-data assurance

Independently challenge the corrected session-data wave and the exact previous missing-first-session-prefix failure. Product bytes are read-only.
