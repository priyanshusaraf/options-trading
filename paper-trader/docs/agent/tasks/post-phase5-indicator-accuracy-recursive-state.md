---
{
  "id": "post-phase5-indicator-accuracy-recursive-state",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "critical_accuracy_correction",
  "goal": "Implement only the 17 declared recursive-state component decisions, with fresh version-2 contracts and typed refusals where specified; no legacy or shared-file edits.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Implement only the 17 declared recursive-state component decisions, with fresh version-2 contracts and typed refusals where specified; no legacy or shared-file edits. Complete only with named source-bound evidence, protected-byte proof and the acceptance checks below; this does not authorize later scope."
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
        "ACCUMULATION_DISTRIBUTION",
        "ADX",
        "ATR",
        "CHAIKIN_OSCILLATOR",
        "CUMULATIVE_RETURN",
        "EMA",
        "KAMA",
        "MA_SLOPE",
        "MINUS_DI",
        "NATR",
        "OBV",
        "PARABOLIC_SAR",
        "PLUS_DI",
        "PRICE_MA_DISTANCE",
        "PRICE_VOLUME_TREND",
        "RMA_WILDER",
        "RSI"
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
  "dependency_gate": "post-phase5-indicator-accuracy-core-level-moment-assurance",
  "allowed_paths": [
    "paper-trader/backend/app/ir/first_party/analytical_v2/recursive_state.py",
    "paper-trader/backend/tests/test_indicator_accuracy_recursive_state.py",
    ".agent/runs/post-phase5-indicator-accuracy-recursive-state",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-recursive-state.md",
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
    "paper-trader/scripts/deploy.sh",
    "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/common.py",
    "paper-trader/backend/app/ir/first_party/analytical_v2/contracts.py",
    "paper-trader/backend/app/ir/node_contracts.py",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/resolve.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/market_data/requirements.py",
    "paper-trader/backend/tests/test_indicator_accuracy_core_math.py",
    "paper-trader/backend/tests/test_indicator_accuracy_core_level_moment_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_core_level_moment_oracle.py"
  ],
  "nonclaims": [
    "No frontend, provider network/credentials, private TradingView, dependency adoption, SQL migration, deployment/VPS, live/order/money, or Phase 6 work. No edits to legacy analytical.py or accepted component semantics.",
    "Planning records and test totals are not a numerical or deployment acceptance."
  ],
  "owner_gates": [
    "Verified core ASSURANCE PASS and standing V0 authority activate this exact 17-component capsule; no routine owner token is required.",
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
  "parallel_budget": 0,
  "assignments": [],
  "component_scope": [
    "ACCUMULATION_DISTRIBUTION",
    "ADX",
    "ATR",
    "CHAIKIN_OSCILLATOR",
    "CUMULATIVE_RETURN",
    "EMA",
    "KAMA",
    "MA_SLOPE",
    "MINUS_DI",
    "NATR",
    "OBV",
    "PARABOLIC_SAR",
    "PLUS_DI",
    "PRICE_MA_DISTANCE",
    "PRICE_VOLUME_TREND",
    "RMA_WILDER",
    "RSI"
  ],
  "acceptance": [
    "Exactly component_scope is accounted for; no omitted outputs, parameters, input roles or validity masks.",
    "Every KEEP/REPLACE candidate has immutable semantic v2 definitions; REFUSE records have stable negative evidence and no executable placeholder version.",
    "All mathematical variants, bounds, first-valid indices, seeds, zero cases and resets match the matrix and pinned sources.",
    "Batch, streaming and serialized restart agree; state/compute/history bounds are measured over the declared parameter domain.",
    "Existing pandas/numpy lock is unchanged. TA-Lib remains reference-only in the already approved isolated executor; no product dependency or lock change is authorized.",
    "The module can be inspected/tested as a contributor but is not registered or made product-eligible here."
  ],
  "test_plan": [
    "Defaults, nondefault parameters, minimum, maximum and first-above-bound values; missing field, wrong role, NaN/infinity, flat/zero, impulse, reversal and gap cases.",
    "Every named output and every validity bit compared, not only overlap or a final value.",
    "Complete-prefix tests plus batch/stream/state snapshot/restart at warmup, gaps, reversal and session boundaries.",
    "Source-specific default parity and independent extended-parameter vectors; no self-derived expected values."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_recursive_state_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-recursive-state/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/first_party/analytical_v2/recursive_state.py",
      "paper-trader/backend/tests/test_indicator_accuracy_recursive_state.py",
      ".agent/runs/post-phase5-indicator-accuracy-recursive-state"
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
    "output": ".agent/runs/post-phase5-indicator-accuracy-recursive-state/report.md",
    "verdicts": [
      "IMPLEMENTATION"
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
  "predecessor_acceptance": {
    "status": "accepted_unpublished",
    "verdict": "ASSURANCE PASS",
    "owner_task": "01a048c6-8031-7c93-9b05-2fef7b25c499",
    "seal": ".agent/runs/post-phase5-indicator-accuracy-core-level-moment-assurance/closure-seal.json",
    "seal_sha256": "cd45378b3b750b3f6f6a8f89a697b840251e319afab68579c6a02ad579e4e380",
    "report": ".agent/runs/post-phase5-indicator-accuracy-core-level-moment-assurance/report.md",
    "report_sha256": "18f0704e03f25dcdfc551d9198eb45f6d50d133999acba00d7d39b07f0e453c4",
    "evidence_sha256": "ba9db809d0bc2937f41333ba3a7b3b74c03c580343eb4fe2cdb5d7444a7e4a4a",
    "review_package_sha256": "adf0612a1edb4414f457a8730e18350ab3dc6dc62f5683e003b87be2ebcdc47d",
    "sealed_capsule_sha256": "1f994ecd20aca69bc149bf2c958707d43a589bbe4244f8857267721743496e70",
    "distinct_passing_test_identities": 2698,
    "components": 58,
    "outputs": 60,
    "resource_points": 222,
    "legacy_identities_unchanged": 125,
    "publication": false,
    "deployment": false
  },
  "reference_environment": {
    "receipt": ".agent/runs/post-phase5-indicator-accuracy-core-math/reference-environment/environment-receipt.json",
    "receipt_sha256": "4009d26ff3949641700d59b33ec8a55d284eaa86ae759bc25a694a8e9396153a",
    "executable": "/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation/.agent/runs/post-phase5-indicator-accuracy-core-math/reference-environment/venv/bin/python",
    "authority": "v0_standing_development_authorization",
    "settings": "DEFAULT compatibility; unstable periods zero; no provisioning or product adoption"
  },
  "completion": {
    "schema": "recursive-state-implementation-review-package/1",
    "verdict": "RECURSIVE_LOCAL_PASS_PENDING_INDEPENDENT_ASSURANCE",
    "report": ".agent/runs/post-phase5-indicator-accuracy-recursive-state/report.md",
    "report_sha256": "46fcf5a0da0a3fa8eada671a7239c3f5ee78f5519257827c7eee6ce6eddc8e44",
    "evidence": ".agent/runs/post-phase5-indicator-accuracy-recursive-state/evidence.json",
    "evidence_sha256": "ed5c23f6148d72f5ec0ce75998817e959be76af47c78ebc712391b2d29b70b01",
    "source_proof": ".agent/runs/post-phase5-indicator-accuracy-recursive-state/source-proof.json",
    "source_sha256": "a7cb21314c4930a8165dd02e7448b3f1d680d404aa7b8834303e04423eb4c828",
    "test_sha256": "f7d89ba8ce4f2fc832a7ea4d7a15c28ae9add91e0f9ef9a3a44302f9ae00f2dd",
    "implementation_owner": "01a048c2-42d6-7850-94e9-af0f2ed5e0e1",
    "next_owner": "01a0491b-0144-72e2-be50-e0e5b353a6a3",
    "next_stage": "post-phase5-indicator-accuracy-recursive-state-assurance",
    "independent_acceptance": false,
    "publication": false,
    "deployment": false,
    "v0_complete": false
  }
}

---

# Recursive state

Implement only the 17 declared decisions under standing V0 authority. The core predecessor is independently accepted and remains unpublished and byte-frozen. Shared-file, legacy, frontend and external-action boundaries remain closed.
