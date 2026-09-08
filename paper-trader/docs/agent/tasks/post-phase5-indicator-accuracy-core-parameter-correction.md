---
{
  "id": "post-phase5-indicator-accuracy-core-parameter-correction",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "critical_accuracy_correction",
  "goal": "Resolve F01 by preserving canonical finite-number parameter representation through the real resolver, data planner and evaluator; do not weaken replay or alter mathematical formulas.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Resolve F01 by preserving canonical finite-number parameter representation through the real resolver, data planner and evaluator; do not weaken replay or alter mathematical formulas. Complete only with focused RED/GREEN and mutation proof, exact source/identity preservation evidence, and a sealed local correction package. Independent numerical acceptance and publication remain separate."
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
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-correction-replan/semantic-contracts.md",
      "sections": [
        "PERCENTILE"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-core-math-assurance/report.md",
      "sections": [
        "Required corrections",
        "Direct evidence",
        "Source and environment proof"
      ]
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-core-math",
  "allowed_paths": [
    "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
    "paper-trader/backend/tests/test_indicator_accuracy_core_math.py",
    ".agent/runs/post-phase5-indicator-accuracy-core-parameter-correction",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-core-parameter-correction.md",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    ".codex/tests/test_programme_orchestration.py",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-recursive-state.md"
  ],
  "protected_paths": [
    "paper-trader/backend/app/ir/first_party/analytical.py",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/migrations",
    "paper-trader/scripts/deploy.sh",
    "paper-trader/backend/app/ir/node_contracts.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/common.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/contracts.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/resolve.py",
    "paper-trader/backend/app/market_data/requirements.py",
    "paper-trader/backend/tests/test_indicator_accuracy_core_math_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_core_math_oracle.py"
  ],
  "nonclaims": [
    "No frontend, provider network/credentials, private TradingView, dependency adoption, SQL migration, deployment/VPS, live/order/money, or Phase 6 work. No edits to legacy analytical.py or accepted component semantics.",
    "Planning records and test totals are not a numerical or deployment acceptance."
  ],
  "owner_gates": [
    "Standing V0 development authority authorizes this exact correction; no routine token is required.",
    "Do not modify shared contracts, v1, execution/provider/deployment code, either frontend, product dependencies/locks, or the sealed independent oracle/tests."
  ],
  "stop_conditions": [
    "Any claimed component/output/contract field is missing or a test expected value is self-derived from product math.",
    "A v1 source, descriptor, contract, declaration or implementation address changes.",
    "An unaccepted v2 implementation becomes product-eligible, or registry/cache/result identity is silently rewritten.",
    "A writer reaches a path owned by another wave without serial integration ownership."
  ],
  "deployment_impact": {
    "classification": "compatible unpublished candidate correction; no SQL/dependency/service/provider/deployment change",
    "required_evidence": "F01 focused proof in the parameter capsule; final 58-component resource/compatibility/source evidence in post-phase5-indicator-accuracy-core-return-stability-correction; different-owner acceptance in post-phase5-indicator-accuracy-core-correction-assurance; actual consumer and release gates remain at registry-lineage integration and strategy-os-v0-security-operations-deployability."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "component_scope": [
    "PERCENTILE"
  ],
  "acceptance": [
    "Default, integer, floating, boundary and fractional q cross the real resolve_v2 \u2192 compile/verify_data_requirement_plan \u2192 evaluate_v2 path and return complete expected arrays/masks.",
    "Reintroducing the old float coercion in an isolated copy kills the actual consumer regression; exact restoration passes.",
    "All F01 independent regressions pass. F02 remains visibly open for the next named correction; do not claim the full assurance suite passes yet.",
    "Record the implementation-derived receipt-fixture failure pattern and exact inheriting capsules.",
    "The replay guard and unrelated mathematics remain unchanged.",
    "Record exact source/test hashes and all remaining findings; no numerical publication or deployment claim."
  ],
  "test_plan": [
    "Default, integer, floating, boundary and fractional q cross the real resolve_v2 \u2192 compile/verify_data_requirement_plan \u2192 evaluate_v2 path and return complete expected arrays/masks.",
    "Reintroducing the old float coercion in an isolated copy kills the actual consumer regression; exact restoration passes.",
    "All F01 independent regressions pass. F02 remains visibly open for the next named correction; do not claim the full assurance suite passes yet.",
    "Record the implementation-derived receipt-fixture failure pattern and exact inheriting capsules."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_core_parameter_correction_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-core-parameter-correction/review-package-final.json",
    "review_paths": [
      "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
      "paper-trader/backend/tests/test_indicator_accuracy_core_math.py",
      ".agent/runs/post-phase5-indicator-accuracy-core-parameter-correction",
      ".codex/tests/test_programme_orchestration.py",
      "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-recursive-state.md"
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
    "output": ".agent/runs/post-phase5-indicator-accuracy-core-parameter-correction/report-final.md",
    "verdicts": [
      "CORRECTION"
    ],
    "max_rechecks": 0
  },
  "v0_standing_development_authorization": {
    "date": "2026-08-28",
    "owner_instruction": "bro remove these requirements you have full authority to do as needed to continue developing this application, nothing should stop you from delivering v0. don't stop till the end of v0 now",
    "scope": "Execute the accepted development programme through strategy-os-v0-review, including the isolated pinned reference executor, bounded local corrections, independent assurance, registry/lineage integration, V0 frontend/catalogue implementation, necessary reviewed development dependencies and local test migrations under their declared capsules. Routine repeated authorization phrases are no longer required.",
    "reference_environment_approval": {
      "approved": true,
      "native_core_commit": "2247d599bddf37ed37e3a709371517e46efc66f6",
      "python_wrapper_commit": "a9ff1b47b3ddbd57274116645d688c0ed677338b",
      "version": "0.7.1",
      "isolation": "reference-only local environment; product venv and requirements/locks unchanged by this provisioning",
      "network": "public upstream/package retrieval for the isolated reference build"
    },
    "retained_evidence_gates": [
      "exact scope/ownership and source identity",
      "correctness and complete-array validity proof",
      "independent assurance and required SPEC/QUALITY review",
      "honest refusals and no fabricated parity",
      "deployment readiness evidence before readiness claims"
    ],
    "external_action_boundary": "Development authority does not require or imply orders, money movement, live trading activation, changes to the trading bot/VPS, destructive production data work, paid subscriptions, private-library access, or a live deployment. Do not perform these as a shortcut to V0 development."
  },
  "allowed_product_symbols": [
    "parameters_for only; tests may add the real-consumer fixture/regressions. _check_bound, _number and all other product functions are byte-protected."
  ],
  "identity_blast_radius": "All 58 unpublished defining-module binding/implementation identities move on source edits. Preserve every v1 identity and keep the default platform registry unchanged; never rewrite prior evidence.",
  "completion": {
    "verdict": "F01_CORRECTION_PASS",
    "source_sha256": "0b2c3a93ac0be3edf44f6a76a0d46d0f918730dee9c23495639a0ad8f83bc00c",
    "tests_passed": 98,
    "coordinator_tests_passed": 9,
    "legacy_identities_unchanged": 125,
    "remaining_finding": "F02",
    "publication": false,
    "deployment": false,
    "report": ".agent/runs/post-phase5-indicator-accuracy-core-parameter-correction/report-final.md",
    "report_sha256": "23c1d8d6eea013a79ef6f2bad7288657280abd0ced45cb44636c522bf998b625",
    "evidence_sha256": "bcce820ce5df99fa371dee1c91306876350dfd1261b9361c9effcdd53d5b1bd8"
  },
  "coordination_addendum": {
    "reason": "The recovery changes the executable stage sequence. Keep the original REJECT historical and repair only its orchestration fixture and matching successor/scope metadata.",
    "owner": "current F01 owner, serial",
    "test_path": ".codex/tests/test_programme_orchestration.py",
    "invariants": "Do not weaken exact predecessor, component-scope, protection, independence or model-route checks.",
    "proof": "All nine existing orchestration tests plus architecture validation must pass before F01 closes."
  }
}

---

# post-phase5-indicator-accuracy-core-parameter-correction

Resolve F01 by preserving canonical finite-number parameter representation through the real resolver, data planner and evaluator; do not weaken replay or alter mathematical formulas.

The immutable independent REJECT remains authoritative negative evidence. Work only this bounded correction under the standing V0 instruction.
