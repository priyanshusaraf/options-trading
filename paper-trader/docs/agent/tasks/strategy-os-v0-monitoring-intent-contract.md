---
{
  "id": "strategy-os-v0-monitoring-intent-contract",
  "phase": "v0",
  "status": "implementation_complete_pending_assurance",
  "kind": "critical_unpublished_language_contract",
  "goal": "Define the additive unpublished Type 1 semantic-v2 monitoring target and SL/TP node contracts required for exact V0 BUY/SELL/EXIT/HOLD alerts, without registry publication or execution authority.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Every declared V0 monitoring target/protection component has a closed immutable v2 descriptor, contract, data declaration and pure implementation with exact parameters, units, validity, resource bounds, complete output tests and typed unsupported-operation refusals. No existing component or registry byte changes."
  },
  "risk_tags": [
    "critical",
    "strategy-language",
    "signal-semantics",
    "protection-geometry",
    "authority-boundary"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/architecture-decision.md",
      "sections": [
        "Five-family and desktop palette mapping",
        "Monitoring-only lifecycle",
        "SignalTransition",
        "Protection intent",
        "Architecture invariant matrix"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/agents/nodes-signals/report.md",
      "sections": [
        "Five-family and Precision Slate mapping",
        "Existing producers, consumers, schemas, persistence, APIs, and tests",
        "Smallest V0 monitoring-only lifecycle",
        "Contradictions and missing seams",
        "Candidate tests and false results prevented"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md",
      "sections": [
        "The five user-facing node families",
        "Strategy definition is not deployment"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/01-STRATEGY-LANGUAGE-NODE-SYSTEM.md",
      "sections": [
        "Type 1 execution starter pack",
        "Numerical validity",
        "Node versioning"
      ]
    }
  ],
  "dependency_gate": "strategy-os-v0-launch-convergence-replan",
  "allowed_paths": [
    "paper-trader/backend/app/ir/first_party/monitoring_intent_v2.py",
    "paper-trader/backend/tests/test_v0_monitoring_intent_contract.py",
    ".agent/runs/strategy-os-v0-monitoring-intent-contract",
    "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-intent-contract.md"
  ],
  "new_paths": [
    "paper-trader/backend/app/ir/first_party/monitoring_intent_v2.py",
    "paper-trader/backend/tests/test_v0_monitoring_intent_contract.py",
    ".agent/runs/strategy-os-v0-monitoring-intent-contract"
  ],
  "protected_paths": [
    "paper-trader/backend/app/ir/first_party/execution_intent.py",
    "paper-trader/backend/app/ir/first_party/logic_state.py",
    "paper-trader/backend/app/ir/library.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/node_contracts.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "component_scope": [
    "BUY",
    "SELL",
    "ENTER_LONG",
    "ENTER_SHORT",
    "CLOSE_POSITION",
    "SESSION_EXIT",
    "EXPIRY_EXIT",
    "FIXED_STOP_PERCENT",
    "POINT_STOP",
    "ATR_STOP",
    "TAKE_PROFIT_PERCENT",
    "RISK_REWARD_TARGET"
  ],
  "semantic_decisions": [
    "BUY/ENTER_LONG resolve target LONG; SELL/ENTER_SHORT resolve target SHORT; CLOSE_POSITION/SESSION_EXIT/EXPIRY_EXIT resolve target FLAT. HOLD is derived only when a valid evaluation requests no target-state change; it is not a terminal node or missing-data fallback.",
    "Entry/exit outputs are `monitoring-target-intent/1` and contain operation, target state, risk-reducing flag, authored node identity and validity. They contain no order type, quantity, capital, broker, account, position or deployment field.",
    "Protection outputs are `monitoring-protection/1` with kind STOP_LOSS or TAKE_PROFIT, basis PERCENT_FROM_ENTRY_REFERENCE, DISTANCE_FROM_ENTRY_REFERENCE, ABSOLUTE_PRICE or VERIFIED_INDICATOR_DISTANCE, exact decimal value/units and authored provenance.",
    "FIXED_STOP_PERCENT and TAKE_PROFIT_PERCENT use positive bounded decimal rates; POINT_STOP uses positive canonical price-distance units; ATR_STOP and RISK_REWARD_TARGET require exact accepted input identity and positive bounded multipliers.",
    "The language contract does not resolve a display price without a typed entry-reference observation. Runtime resolution belongs to the later transition compiler.",
    "Long geometry requires resolved stop < entry < target; short geometry requires target < entry < stop. Invalid/missing/stale/undefined inputs refuse and never become HOLD.",
    "PARTIAL_EXIT, ADD_POSITION, REVERSE, pyramiding/scaling, sizing, portfolio/account facts, broker protection and order-type nodes are excluded from the simple V0 monitoring allowlist with `V0_MONITORING_OPERATION_UNAVAILABLE`; their existing v1 records remain unchanged."
  ],
  "acceptance": [
    "Exactly component_scope is present at semantic version 2 in the new unregistered contributor; every existing v1 component/contract/implementation address remains exact.",
    "Descriptors, ports, parameters, output types, validity, first-valid behavior, mode eligibility and resource profiles are closed and reject missing/extra/mistyped/nonfinite/bool-as-number inputs.",
    "Complete table tests cover every target/protection operation, long/short geometry inputs, boundary/min/max/first-above values and all unsupported Type 1 operation refusals.",
    "Pure implementations import no engine, broker, order, execution, capital, position, ledger, credential, database, clock or provider module and cause no external effect.",
    "Batch/prefix identity is deterministic; appending future inputs cannot change earlier output bytes.",
    "Measured conservative compute/memory/history/state bounds cover the declared domains and first-above refusal.",
    "At least three isolated contract/operation/authority mutations fail intended tests and restore exact bytes.",
    "No library/registry/editor/runtime publication. Fresh independent Type 1/3/5 assurance and the final five-family catalogue own acceptance/publication."
  ],
  "test_plan": [
    "RED/GREEN closed descriptor/parameter/output tests, complete target/protection tables, validity and unsupported-operation refusals.",
    "Prefix/serialization/resource tests and AST/module import authority guard with isolated killed/restored mutations.",
    "Affected existing Phase 5 Type 1 catalogue/IR identity tests run only after focused evidence passes."
  ],
  "risk_classification": {
    "tier": "Critical",
    "reason": "Wrong target direction, SL/TP semantics or authority fields can publish materially false trading signals or create a future signal-to-order bypass."
  },
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "owner_task": "/root/v0_nodes_signals_inventory",
  "review": {
    "required": false,
    "assignment_id": "v0_monitoring_intent_contract_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-monitoring-intent-contract/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/first_party/monitoring_intent_v2.py",
      "paper-trader/backend/tests/test_v0_monitoring_intent_contract.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-intent-contract.md",
      ".agent/runs/strategy-os-v0-monitoring-intent-contract"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/migrations",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-monitoring-intent-contract/report.md",
    "verdicts": [
      "IMPLEMENTATION"
    ],
    "max_rechecks": 0
  },
  "owner_gates": [
    "Standing V0 and accepted launch-convergence authority permit this additive unpublished contract when routed. No routine user token is required.",
    "Stop before registry/library/editor publication, runtime monitoring, schema, provider, frontend, deployment, order or money work."
  ],
  "stop_conditions": [
    "An existing component/version/address or shared registry/runtime byte must change.",
    "Any output requires broker/account/order/capital/position/deployment data or effect.",
    "A protection parameter cannot be expressed with closed exact numeric/unit semantics or a public V0 operation lacks an unambiguous target state.",
    "Expected values derive from the product implementation rather than the frozen semantic tables."
  ],
  "deployment_impact": {
    "classification": "compatible unpublished IR contributor; no schema/service/provider/dependency change",
    "required_evidence": "Exact source/contract/implementation/resource identities; final registry and release assembly remain later owners."
  },
  "nonclaims": [
    "No public node, signal event, alert, monitoring assignment, provider data, paper/live execution, order, position, money, frontend, deployment or V0 completion.",
    "SL/TP outputs are authored monitoring specifications, not broker-resident protection."
  ],
  "implementation_closure": {
    "verdict": "IMPLEMENTATION PASS PENDING INDEPENDENT NONANALYTICAL-FAMILY ASSURANCE",
    "report": ".agent/runs/strategy-os-v0-monitoring-intent-contract/report.md",
    "evidence": ".agent/runs/strategy-os-v0-monitoring-intent-contract/evidence.json",
    "identity_receipt": ".agent/runs/strategy-os-v0-monitoring-intent-contract/identities.json",
    "closure_seal": ".agent/runs/strategy-os-v0-monitoring-intent-contract/closure-seal.json",
    "publication": false,
    "deployment": false,
    "independent_assurance_pending": true
  }
}
---

# V0 monitoring intent language contract

Define the additive unpublished Type 1 monitoring target and protection semantics. Do not publish or connect them to execution.
