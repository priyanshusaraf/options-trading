---
{
  "id": "post-phase5-indicator-accuracy-session-prefix-correction",
  "phase": "post-phase5",
  "status": "implementation_complete_pending_assurance",
  "kind": "critical_accuracy_correction",
  "goal": "Correct only F01-FRESH by requiring canonical SESSION_OPEN_AT for the eight affected unpublished session-prefix candidates, regenerating the module through a new sealed correction producer and preserving every other semantic/output/resource/refusal fact.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "All eight affected source/binding/implementation identities move honestly, missing-first-bar and incomplete-prior-session cases refuse through real consumers, complete prefixes/numbers/masks/state/restart/resources remain exact, 125 legacy and 84 accepted v2 identities remain exact, and local evidence is sealed for another fresh independent assurance."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "session-prefix",
    "semantic-identity",
    "generated-source"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/report.md",
      "sections": [
        "Verdict",
        "F01-FRESH — missing first-session history remains accepted",
        "Evidence accepted within the rejected wave",
        "Identity disposition",
        "Required correction route and limits"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/findings.json",
      "sections": [
        "findings"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/architecture-decision.md",
      "sections": [
        "Immutable version 1",
        "Parameter-dependent contracts: bounded extension, no expression language",
        "Validity, sessions and outputs",
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
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/verification-contract.md",
      "sections": [
        "Thresholds",
        "Complete-array comparators",
        "Adversarial fixtures",
        "Operational evidence"
      ]
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-session-data-fresh-assurance",
  "allowed_paths": [
    "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py",
    "paper-trader/backend/tests/test_indicator_accuracy_session_prefix_correction.py",
    ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-prefix-correction.md"
  ],
  "new_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_session_prefix_correction.py",
    ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction"
  ],
  "protected_paths": [
    ".agent/runs/post-phase5-indicator-accuracy-session-data/build_product.py",
    ".agent/runs/post-phase5-indicator-accuracy-session-data/session_data_body.py",
    ".agent/runs/post-phase5-indicator-accuracy-correction-replan/specification.py",
    ".agent/runs/post-phase5-indicator-accuracy-correction-replan/component-matrix.json",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data.py",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_session_data_oracle.py",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data_fresh_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_session_data_fresh_oracle.py",
    "paper-trader/backend/app/ir/first_party/analytical.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/contracts.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/recursive_state.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/multi_output.py",
    "paper-trader/backend/app/ir/library.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/node_contracts.py",
    "paper-trader/backend/app/market_data/requirements.py",
    "paper-trader/backend/app/backtest",
    "paper-trader/backend/research",
    "paper-trader/backend/migrations",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "stable_input_hashes": {
    "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py": "7dd508c41cb267f7fe571b60fef414c3244b6c3373178c043226811213a4b897",
    "paper-trader/backend/tests/test_indicator_accuracy_session_data.py": "6b7924a0ea1a3d5aaf768aec9c72b2023ffcd81a6677fda785413841815cc714",
    ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/report.md": "0dd77b7b138419b815bbd4b7d44b24d5d14cc4bd2cd9edb3550928f22f4a71ec",
    ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/evidence.json": "8945fe2819afac71f06870eda43e1d5060c1b5eac7632a064e849e659b471ae5",
    ".agent/runs/post-phase5-indicator-accuracy-session-data-fresh-assurance/closure-seal.json": "0f7b86f8b4f1124c56073adb80bb730d702a7a0adcaffb0871beea300f1d2361"
  },
  "affected_components": [
    "DISTANCE_FROM_SESSION_HIGH_LOW",
    "PREVIOUS_SESSION_FIELDS",
    "PREVIOUS_SESSION_OHLC",
    "SESSION_HIGH",
    "SESSION_LOW",
    "SESSION_OPEN",
    "SESSION_OPEN_HIGH_LOW",
    "VWAP"
  ],
  "correction_contract": [
    "Create a new correction-owned generator under `.agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/` that consumes the sealed original specification/body and overlays exactly `session_open_at` into each affected component's declared inputs before regenerating the complete module. Do not edit the accepted original producer/specification/body by hand.",
    "The product module's immutable SPECS facts, descriptors, data fields, source contracts, binding rules and transitive implementation identities must all include the new session-open requirement for exactly affected_components.",
    "At the first event of a session, require explicit canonical SESSION_OPEN_AT and require `event_time == session_open_at + bound_timeframe`. Missing/wrong role/non-derived-local/wrong address/misaligned session-open facts refuse.",
    "Subsequent events must retain the same session-open identity and exact next-slot continuity. A suffix beginning at slot two or later refuses before aggregate/state mutation.",
    "Only the eight affected source/binding/implementation addresses may move. The other nine candidates, 14 refusal records, 125 legacy and 84 accepted earlier v2 identities remain exact.",
    "Do not change formula outputs, precision, masks, session-close rules, state/restart format, parameter domains, resource profiles, provider/calendar authority or eligibility."
  ],
  "acceptance": [
    "Generator output is deterministic and an immediate regeneration produces byte-identical session_data.py; generated header and source receipt name the correction decision.",
    "Every affected component source contract/bound plan requires exact derived-local SESSION_OPEN_AT; every unaffected component/refusal remains byte/identity exact unless the shared defining-module implementation closure necessarily changes and is fully recorded.",
    "Both fresh F01 assertions pass: all eight names refuse second-slot start and previous-session outputs never expose an incomplete aggregate.",
    "Complete owner and fresh independent arrays/masks for all 31 decisions pass unchanged except archived historical expected identities; overnight/holiday/short/session/internal-gap/anchor cases remain exact.",
    "Batch, stream, snapshot/restart, cold replay, real resolver/materializer/compiler/verifier/runtime and stale receipt/state refusal pass.",
    "Two 100,000-event resource workloads remain within existing bounds and first-above counters refuse; no resource claim is weakened.",
    "At least three isolated missing-input/prefix/identity mutations fail intended assertions and restore exact source/test/generator bytes.",
    "Local closure explicitly remains pending another fresh independent assurance and authorizes no registry/publication/provider/frontend/deployment work."
  ],
  "test_plan": [
    "Focused RED/GREEN against the exact two failed assertions plus contract/binding/identity/generator tests, then all existing session-data owner and both assurance suites with historical failures reclassified only by exact identity.",
    "Real consumer/restart/resource checks and isolated killed/restored mutations; record every failure/skip and preserve archived rejection evidence."
  ],
  "risk_classification": {
    "tier": "Critical",
    "reason": "Accepting a mid-session suffix corrupts session open/high/low/VWAP and can publish a false previous-session aggregate used by research or signals."
  },
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
      "status": "implementation_complete_pending_review"
    }
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "owner_task": "/root/v0_nodes_signals_inventory",
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_session_prefix_correction",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py",
      "paper-trader/backend/tests/test_indicator_accuracy_session_prefix_correction.py",
      "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-prefix-correction.md",
      ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/ir/first_party/analytical.py",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/providers",
      "paper-trader/backend/migrations",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/report.md",
    "verdicts": [
      "IMPLEMENTATION"
    ],
    "max_rechecks": 0
  },
  "owner_gates": [
    "Standing V0 authority and sealed F01-FRESH rejection authorize this exact bounded correction. No repeated user token is required.",
    "Stop before any shared registry/runtime, provider, frontend, schema, publication, deployment, live/order/money or later-stage change."
  ],
  "stop_conditions": [
    "Any ninth component, formula/output/mask/parameter/resource/refusal semantic or accepted upstream producer/specification must change.",
    "A shared registry/validator/compiler/runtime/provider/calendar change is required.",
    "A legacy or accepted prior-v2 identity changes without exact transitive explanation and stale-consumer refusal.",
    "A test expected value derives from current product math or historical rejection evidence is overwritten."
  ],
  "deployment_impact": {
    "classification": "compatible unpublished analytical contract/identity correction; no schema/service/provider/dependency change",
    "required_evidence": "Exact generator/source/binding/implementation/stale-consumer/resource identities. Final registry and release assembly remain later owners."
  },
  "nonclaims": [
    "No independent acceptance, registry publication, provider/calendar availability, frontend, paper/live, order, money, deployment or V0 completion."
  ],
  "implementation_closure": {
    "verdict": "IMPLEMENTATION PASS PENDING FRESH INDEPENDENT ASSURANCE",
    "report": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/report.md",
    "evidence": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/evidence.json",
    "identity_transition": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/identity-transition.json",
    "closure_seal": ".agent/runs/post-phase5-indicator-accuracy-session-prefix-correction/closure-seal.json",
    "publication": false,
    "deployment": false,
    "fresh_independent_assurance_pending": true
  }
}
---

# Session-prefix F01 correction

Require canonical session-open evidence for exactly the eight affected unpublished candidates and regenerate through a new correction-owned producer.
