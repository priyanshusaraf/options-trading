---
{
  "id": "post-phase5-indicator-accuracy-core-level-moment-correction",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "critical_accuracy_correction",
  "goal": "Correct reproduced F04 level-moment cancellation/underflow after an explicit seven-consumer impact audit, preserving strict numbers/masks and all prior corrections.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "All reproduced affected level-moment cases pass full-array independent expectations and actual consumers; prior corrections, 58-component regression/resource/identity checks, mutations and exact preservation pass; seal local correction for different-owner assurance."
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
        "BETA_ADJUSTED_SPREAD",
        "CORRELATION",
        "COVARIANCE",
        "LINEAR_REGRESSION_INTERCEPT",
        "LINEAR_REGRESSION_SLOPE",
        "ROLLING_HEDGE_RATIO",
        "R_SQUARED"
      ]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-core-correction-assurance/report.md",
      "sections": [
        "F04 \u2014 level-moment cancellation and underflow (P1)",
        "Verified coverage and limits",
        "Reference and runtime",
        "Identity, preservation and deployment impact"
      ]
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-core-return-stability-correction",
  "allowed_paths": [
    "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
    "paper-trader/backend/tests/test_indicator_accuracy_core_math.py",
    ".codex/tests/test_programme_orchestration.py",
    ".agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-core-level-moment-correction.md",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-core-level-moment-assurance.md",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-recursive-state.md",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md"
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
    "paper-trader/backend/research_tests/test_indicator_accuracy_core_math_oracle.py",
    "paper-trader/backend/tests/test_indicator_accuracy_core_correction_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_core_correction_oracle.py",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-core-correction-assurance.md"
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
    "classification": "compatible unpublished numerical correction; no installed dependency/lock, SQL, provider, service, frontend or deployment change",
    "required_evidence": "Local numerical/resource/state/identity evidence in post-phase5-indicator-accuracy-core-level-moment-correction; independent acceptance in post-phase5-indicator-accuracy-core-level-moment-assurance; actual composition/job/cache/result/resource consumers at post-phase5-indicator-accuracy-registry-lineage-integration; release assembly at strategy-os-v0-security-operations-deployability."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "component_scope": [
    "BETA_ADJUSTED_SPREAD",
    "CORRELATION",
    "COVARIANCE",
    "LINEAR_REGRESSION_INTERCEPT",
    "LINEAR_REGRESSION_SLOPE",
    "ROLLING_HEDGE_RATIO",
    "R_SQUARED"
  ],
  "acceptance": [
    "Retain and kill the independent F04 actual-consumer reproductions; exact two-point positive correlation and tiny-scale y=2x identities pass complete numbers and masks.",
    "Read-only impact audit covers all seven named consumers at minimum/default/maximum windows and finite near-flat/tiny/large scales; record passes and failures without inferring failures for the three unproven consumers.",
    "Any additional numerical ownership is explicitly amended from direct reproduction before implementation.",
    "All prior F01/F02/F03 checks, complete 58-component/60-output arrays, parameter/domain, role/timeframe, causal, stream/restart, resource and affected compatibility checks pass.",
    "Existing immutable independent oracle/tests supply expectations; do not alter them, derive expected output from product code, relax thresholds or invent a floor.",
    "Relevant isolated numerical mutation is killed/restored; all legacy/protected identities and default composition remain exact.",
    "Nine orchestration tests and architecture validation pass after the exact recovery-route fixture is updated without weakening its invariants.",
    "Seal exact local evidence with no independent acceptance, publication, deployment or V0-completion claim."
  ],
  "test_plan": [
    "Retain and kill the independent F04 actual-consumer reproductions; exact two-point positive correlation and tiny-scale y=2x identities pass complete numbers and masks.",
    "Read-only impact audit covers all seven named consumers at minimum/default/maximum windows and finite near-flat/tiny/large scales; record passes and failures without inferring failures for the three unproven consumers.",
    "Any additional numerical ownership is explicitly amended from direct reproduction before implementation.",
    "All prior F01/F02/F03 checks, complete 58-component/60-output arrays, parameter/domain, role/timeframe, causal, stream/restart, resource and affected compatibility checks pass.",
    "Existing immutable independent oracle/tests supply expectations; do not alter them, derive expected output from product code, relax thresholds or invent a floor.",
    "Relevant isolated numerical mutation is killed/restored; all legacy/protected identities and default composition remain exact.",
    "Nine orchestration tests and architecture validation pass after the exact recovery-route fixture is updated without weakening its invariants.",
    "Seal exact local evidence with no independent acceptance, publication, deployment or V0-completion claim."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase5_indicator_accuracy_core_level_moment_correction_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
      "paper-trader/backend/tests/test_indicator_accuracy_core_math.py",
      ".agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction"
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
    "output": ".agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction/report.md",
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
    "F04 branches in _number and narrowly required pure exact/precision arithmetic helpers in core_math.py only. _level_regression may be refactored solely to share its already accepted exact level-moment calculation; its numbers and masks must remain unchanged.",
    "All seven inspected consumers are directly reproduced and in scope. Correct those seven only; other formulas and shared files remain protected.",
    "parameters_for, _check_bound, state/evaluate machinery, accepted SPECS and all other formulas remain unchanged. Resource profile changes require measured evidence and explicit recorded deltas."
  ],
  "exploration_scope": [
    "BETA_ADJUSTED_SPREAD",
    "CORRELATION",
    "COVARIANCE",
    "LINEAR_REGRESSION_INTERCEPT",
    "LINEAR_REGRESSION_SLOPE",
    "ROLLING_HEDGE_RATIO",
    "R_SQUARED"
  ],
  "identity_blast_radius": "All 58 unpublished defining-module binding/implementation identities move on source edits. Preserve every v1 identity and keep the default platform registry unchanged; never rewrite prior evidence.",
  "coordination_scope": {
    "owner": "current coordinator, serial",
    "reason": "Retain the sealed F04 REJECT outside the executable chain and insert correction/assurance successors; update only exact route fixtures and pointers.",
    "old_reject_is_immutable": true
  },
  "prior_reject": {
    "path": ".agent/runs/post-phase5-indicator-accuracy-core-correction-assurance/closure-seal.json",
    "sha256": "c9cebd567443836e1537cf240dc620a728ba13b606d038083b616d80a17a1001",
    "findings": [
      "F04"
    ]
  },
  "scope_amendment": {
    "date": "2026-08-28",
    "finding": ".agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction/impact-finding.json",
    "added_components": [
      "COVARIANCE",
      "LINEAR_REGRESSION_INTERCEPT",
      "LINEAR_REGRESSION_SLOPE"
    ],
    "authority": "v0_standing_development_authorization",
    "before_product_edit": true
  },
  "completion": {
    "schema": "core-level-moment-correction-review-package/1",
    "verdict": "F04_LOCAL_CORRECTION_PASS_PENDING_INDEPENDENT_ASSURANCE",
    "report": ".agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction/report.md",
    "report_sha256": "83b6745681975e9e64901243f99feb3a9534afde5eacae5263af6579451f06f3",
    "evidence": ".agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction/evidence.json",
    "evidence_sha256": "04867c448fb44896bff53de914dbba98332ea94a033ade24ea9c1b5fbe943716",
    "source_proof": ".agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction/source-proof.json",
    "product_source_sha256": "bf8ac8d4e87e53bd96b97462a13379baa88a54b97606ba2550248fa8d4e6ccc6",
    "product_test_sha256": "ff661d588271e896fce3eb397e99a756ae5728175e1c77da4dd0271636689ba4",
    "required_next_owner": "post-phase5-indicator-accuracy-core-level-moment-assurance",
    "independent_acceptance": false,
    "publication": false,
    "deployment": false
  }
}

---

# F04 core level-moment correction

Execute only this explicit serial recovery under standing V0 authority. The predecessor REJECT is negative evidence, not numerical acceptance.
