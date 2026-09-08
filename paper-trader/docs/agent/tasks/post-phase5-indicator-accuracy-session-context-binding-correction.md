---
{
  "id": "post-phase5-indicator-accuracy-session-context-binding-correction",
  "phase": "post-phase5",
  "status": "assigned_waiting_sealed_START",
  "kind": "critical_contract_correction",
  "goal": "Add only the three typed locally-derived session context field identities required by the accepted session-data contracts, preserving every older semantic source and proving the transitive unpublished-v2 identity move.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only when the three-field grammar extension, 84-component transitive identity audit, old receipt/state refusal, unchanged numerical behavior, resources and genuine mutations are sealed. Local completion is not independent acceptance or publication."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "contract-identity",
    "complete-universe"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/architecture-decision.md",
      "sections": [
        "Parameter-dependent contracts: bounded extension, no expression language",
        "Validity, sessions and outputs",
        "Sequencing and stopping rule"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/binding-contract-spec.json",
      "sections": [
        "source_contract",
        "bound_contract",
        "validation_rules",
        "legacy"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/legacy-cache-result-policy.md",
      "sections": [
        "Version and graph identity",
        "Cache and result disposition"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-data.md",
      "sections": [
        "Session data"
      ]
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-multi-output-band-ppo-source-assurance",
  "parent_capsule": "post-phase5-indicator-accuracy-session-data",
  "allowed_paths": [
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/tests/test_indicator_accuracy_session_context_binding_correction.py",
    ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-context-binding-correction.md"
  ],
  "new_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_session_context_binding_correction.py"
  ],
  "protected_paths": [
    "paper-trader/backend/app/ir/node_contracts.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/contracts.py",
    "paper-trader/backend/app/market_data/requirements.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/recursive_state.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/multi_output.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py",
    "paper-trader/backend/app/ir/first_party/analytical.py",
    "paper-trader/backend/app/ir/library.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/ir/incremental_runtime.py",
    "paper-trader/backend/app/backtest",
    "paper-trader/backend/research",
    "paper-trader/backend/migrations",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "stable_input_hashes": [
    {
      "path": "paper-trader/backend/app/ir/registry.py",
      "sha256": "5571b38754046713903fc036f74e88c2791d03264f65bb0e3c040644d5fb99f0"
    },
    {
      "path": "paper-trader/backend/app/market_data/requirements.py",
      "sha256": "d1d0a4b278a4d2d503667197c384ee07b0d58c790fa1726ada8e9bfbea8354d4"
    },
    {
      "path": "paper-trader/backend/app/ir/first_party/analytical_v2/contracts.py",
      "sha256": "95e0ae03d2f3dc93fb959c9522cb636c517d7ebd5766e3ae3524d95964be0ba3"
    },
    {
      "path": "paper-trader/backend/app/ir/node_contracts.py",
      "sha256": "a1e16b735cd8decfcad4356aa82c10a20d65c5129f25d78ae7931ad9596af284"
    },
    {
      "path": "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
      "sha256": "bf8ac8d4e87e53bd96b97462a13379baa88a54b97606ba2550248fa8d4e6ccc6"
    },
    {
      "path": "paper-trader/backend/app/ir/first_party/analytical_v2/recursive_state.py",
      "sha256": "dd658c9ac72c94a0df68e5bbb0aeedcb7f1e12b3a90b107b8ec51b9e44943d4c"
    },
    {
      "path": "paper-trader/backend/app/ir/first_party/analytical_v2/multi_output.py",
      "sha256": "744610d2280d87edb61b032a3b02e441adc949e25039993af51ab7921d839760"
    },
    {
      "path": "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py",
      "sha256": "4db6a5d57cb443ee5ed695860e3222129bf147770721ed66e831ff10ae08b0d3"
    }
  ],
  "scope": [
    "Extend only registry._DATA_FIELDS with SESSION_ID, SESSION_OPEN_AT and SESSION_CLOSE_AT. No other grammar, validator, resolver, compiler, runtime or provider behavior changes.",
    "Capture the genuine pre-change source/binding/implementation identities and representative plans/states for all accepted unpublished core58, recursive17 and multi-output9 candidates before mutation.",
    "Prove all 125 legacy identities and every v2 source/binding contract exact; the transitive 84 implementation identities must move honestly, old receipts/state must refuse, and complete numerical/compatibility suites must remain unchanged.",
    "Context fields remain locally derived and unavailable to published components until the session-data module's own binding rule and later registry integration enforce exact role/session/derived-local facts. This capsule publishes nothing."
  ],
  "acceptance": [
    "Exactly three closed field literals are added; wrong spelling/case, extra context facts, capability flags and provider-like substitution refuse.",
    "The real resolver/data-plan compiler accepts independently constructed exact derived-local canonical session context rows and rejects forged role/session/derived-local/address variants.",
    "Existing core, recursive and multi-output numerical tests pass on current bytes; old plan/receipt/state evidence is captured and refuses after the identity change.",
    "Resource demand is measured and at least four genuine isolated consumer mutations fail intended assertions with zero errors/skips and exact restoration."
  ],
  "test_plan": [
    "Focused RED/green field grammar and real contract-binding/data-plan tests, then accepted core/recursive/multi-output compatibility and identity audits.",
    "Safe mock/paper/disabled dotenv/empty live ack/distinct temp DBs. No HOME/CODEX_HOME overrides, networks, credentials, dependencies, migrations or deployment."
  ],
  "owner_gates": [
    "Start only after the coordinator's exact routing seal and ACTUAL START; no routine user token.",
    "Local correction evidence cannot resume session-data product work until a fresh different-owner assurance PASS is accepted."
  ],
  "stop_conditions": [
    "Any fourth field, shared validator/compiler/runtime edit, provider-like context substitution or session-data product edit is required.",
    "Any legacy v1 identity changes, any accepted v2 semantic output changes, or old receipts/state fail to refuse after the transitive identity move."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "owner_task": "01a04b00-dbce-7d40-a15d-2234b756bce2",
  "review": {
    "required": true,
    "assignment_id": "post_phase5_indicator_accuracy_session_context_binding_assurance",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/registry.py",
      "paper-trader/backend/tests/test_indicator_accuracy_session_context_binding_correction.py",
      ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/report.md",
    "verdicts": [
      "IMPLEMENTATION"
    ],
    "max_rechecks": 0
  },
  "independent_assurance": {
    "required": true,
    "owner_must_differ": true,
    "route": "fresh Sol medium, no history fork, zero agents after local seal"
  },
  "deployment_impact": {
    "classification": "compatible unpublished contract-identity correction; no SQL migration",
    "required_evidence": "Exact transitive identities, stale receipt refusal and locked-runtime compatibility. No release/deployment claim."
  },
  "nonclaims": [
    "No numerical publication, provider/calendar availability, frontend, dependency, schema migration, paper/live, order, money, deployment or V0 completion."
  ],
  "standing_authority": {
    "source": "v0_standing_development_authorization",
    "routine_token_required": false
  },
  "routing": {
    "path": ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction/routing/decision.json",
    "sha256": "432a852ebe62d604837e41618ff7b8b24c08d12bcacaf8be06b2f62a942dafbe"
  }
}
---

# Session context binding correction

The accepted session-data semantics require three canonical, locally-derived context fields that the current closed data-field grammar refuses. Add only those literals and prove the complete unpublished-v2 identity impact before session-data implementation resumes.
