---
{
  "id": "post-phase5-indicator-accuracy-core-correction-assurance",
  "phase": "post-phase5",
  "status": "active",
  "kind": "independent_accuracy_assurance",
  "goal": "Independently accept or reject the corrected 58-component/60-output wave after F01/F02/F03 recovery; preserve all historical negative evidence.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Independently verify both corrected boundaries and the complete 58-component/60-output universe, including canonical parameters, strict numerical validity, causality, restart, resources and legacy/protected identity; seal the exact verdict without publication or deployment claims."
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
        "ALPHA",
        "BETA",
        "BETA_ADJUSTED_SPREAD",
        "CCI",
        "CHAIKIN_MONEY_FLOW",
        "CORRELATION",
        "COVARIANCE",
        "CROSS_ABOVE",
        "CROSS_BELOW",
        "FALLING",
        "GAP",
        "GAP_DOWN",
        "GAP_UP",
        "HL2",
        "HLC3",
        "INSIDE_BAR",
        "LINEAR_REGRESSION_INTERCEPT",
        "LINEAR_REGRESSION_SLOPE",
        "LOG_RETURN",
        "MAD",
        "MFI",
        "MIDPOINT",
        "MOMENTUM",
        "OHLC4",
        "OUTSIDE_BAR",
        "PERCENTILE",
        "PERCENTILE_RANK",
        "PERCENT_RETURN",
        "POINT_CHANGE",
        "RATIO",
        "RELATIVE_VOLUME",
        "RESIDUAL",
        "RISING",
        "ROC",
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
        "R_SQUARED",
        "SMA",
        "TREND_PERSISTENCE",
        "TRUE_RANGE",
        "TYPICAL_PRICE",
        "VOLUME_ZSCORE",
        "VWMA",
        "WEIGHTED_CLOSE",
        "WILLIAMS_R",
        "WMA",
        "ZSCORE"
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
      "path": ".agent/runs/post-phase5-indicator-accuracy-core-return-stability-correction/report.md",
      "sections": [
        "Required independent verification",
        "Source and environment",
        "Deployment and programme"
      ]
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-core-return-stability-correction",
  "allowed_paths": [
    "paper-trader/backend/tests/test_indicator_accuracy_core_correction_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_core_correction_oracle.py",
    ".agent/runs/post-phase5-indicator-accuracy-core-correction-assurance",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-core-correction-assurance.md"
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
    "paper-trader/backend/tests/test_indicator_accuracy_core_math_assurance.py",
    "paper-trader/backend/research_tests/test_indicator_accuracy_core_math_oracle.py",
    "paper-trader/backend/app",
    "paper-trader/backend/tests/test_indicator_accuracy_core_math.py",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json"
  ],
  "nonclaims": [
    "No frontend, provider network/credentials, private TradingView, dependency adoption, SQL migration, deployment/VPS, live/order/money, or Phase 6 work. No edits to legacy analytical.py or accepted component semantics.",
    "Planning records and test totals are not a numerical or deployment acceptance."
  ],
  "owner_gates": [
    "Standing V0 authority and the sealed predecessor authorize this exact independent assignment. No routine owner token is required.",
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
    "ALPHA",
    "BETA",
    "BETA_ADJUSTED_SPREAD",
    "CCI",
    "CHAIKIN_MONEY_FLOW",
    "CORRELATION",
    "COVARIANCE",
    "CROSS_ABOVE",
    "CROSS_BELOW",
    "FALLING",
    "GAP",
    "GAP_DOWN",
    "GAP_UP",
    "HL2",
    "HLC3",
    "INSIDE_BAR",
    "LINEAR_REGRESSION_INTERCEPT",
    "LINEAR_REGRESSION_SLOPE",
    "LOG_RETURN",
    "MAD",
    "MFI",
    "MIDPOINT",
    "MOMENTUM",
    "OHLC4",
    "OUTSIDE_BAR",
    "PERCENTILE",
    "PERCENTILE_RANK",
    "PERCENT_RETURN",
    "POINT_CHANGE",
    "RATIO",
    "RELATIVE_VOLUME",
    "RESIDUAL",
    "RISING",
    "ROC",
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
    "R_SQUARED",
    "SMA",
    "TREND_PERSISTENCE",
    "TRUE_RANGE",
    "TYPICAL_PRICE",
    "VOLUME_ZSCORE",
    "VWMA",
    "WEIGHTED_CLOSE",
    "WILLIAMS_R",
    "WMA",
    "ZSCORE"
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
    "assignment_id": "post_phase5_indicator_accuracy_core_correction_assurance_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-core-correction-assurance/review-package.json",
    "review_paths": [
      "paper-trader/backend/tests/test_indicator_accuracy_core_correction_assurance.py",
      "paper-trader/backend/research_tests/test_indicator_accuracy_core_correction_oracle.py",
      ".agent/runs/post-phase5-indicator-accuracy-core-correction-assurance"
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
    "output": ".agent/runs/post-phase5-indicator-accuracy-core-correction-assurance/report.md",
    "verdicts": [
      "ASSURANCE"
    ],
    "max_rechecks": 0
  },
  "independence": "Must be a different owner from the corresponding implementation. Read product code, but author expected vectors independently; no product mutation. Product-changing findings return to an explicitly bounded correction.",
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
  "reference_environment": {
    "receipt": ".agent/runs/post-phase5-indicator-accuracy-core-math/reference-environment/environment-receipt.json",
    "receipt_sha256": "4009d26ff3949641700d59b33ec8a55d284eaa86ae759bc25a694a8e9396153a",
    "executable": "/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation/.agent/runs/post-phase5-indicator-accuracy-core-math/reference-environment/venv/bin/python",
    "authorization": "v0_standing_development_authorization",
    "usage": "Use this exact isolated executor with DEFAULT compatibility and unstable periods zero. Do not install reference packages into the product venv."
  },
  "required_reference_limit_checks": {
    "path": ".agent/runs/post-phase5-indicator-accuracy-core-math/v0-authorized-resume/reference-limit-findings.md",
    "requirements": [
      "Author fresh independent mathematical vectors for extended-window OLS and two-point/cancellation correlation.",
      "Confirm exact-zero beta/MFI handling without weakening the declared zero/nonzero thresholds.",
      "Preserve the raw native FAIL evidence; do not claim universal parity or reuse implementation-owner expected arrays.",
      "Do not read/import the implementation test or countercheck/generator code to author expected values; use accepted specifications and pinned upstream sources."
    ]
  },
  "recovery_findings": [
    "F01",
    "F02",
    "F03_NEAR_FLAT_CANCELLATION"
  ],
  "prior_reject": {
    "path": ".agent/runs/post-phase5-indicator-accuracy-core-math-assurance/closure-seal.json",
    "sha256": "ece95de4fa793cae8f86ffb2ac30367a79b0d76b147a715e27ed216fb2ecac0d"
  },
  "prior_assurance_result": {
    "verdict": "ASSURANCE REJECT",
    "owner_task": "01a04748-debe-76a1-bc69-4d3d3a8ae038",
    "report": ".agent/runs/post-phase5-indicator-accuracy-core-math-assurance/report.md",
    "findings": [
      "F01",
      "F02"
    ],
    "independent_tests": 822,
    "passed": 799,
    "failed": 23,
    "compatibility_passed": 389,
    "product_edits": 0,
    "mutations_killed_restored": 3,
    "publication_authority": false,
    "next_transition": "Coordinating owner creates bounded candidate normalization and stable-return corrections under standing V0 authority, then new independent assurance."
  },
  "assurance": {
    "status": "rejected",
    "owner_task": "01a04883-7dc6-71a1-bb51-9e9dff45c450",
    "verdict": "ASSURANCE REJECT",
    "report": ".agent/runs/post-phase5-indicator-accuracy-core-correction-assurance/report.md",
    "report_sha256": "ad27e97adfe36a2c82e9be1c2dc9b426e2da8dddcbff837d55e124aee0fcf081",
    "evidence": ".agent/runs/post-phase5-indicator-accuracy-core-correction-assurance/evidence.json",
    "closure_seal": ".agent/runs/post-phase5-indicator-accuracy-core-correction-assurance/closure-seal.json",
    "findings": [
      "F04"
    ],
    "independent_checks": {
      "tests": 1023,
      "passed": 1013,
      "failed": 10
    },
    "compatibility_passed": 389,
    "product_edits": 0,
    "publication": false,
    "deployment": false
  },
  "predecessor_completion": {
    "schema": "core-stability-correction-review-package/1",
    "verdict": "LOCAL_CORRECTION_PASS_PENDING_INDEPENDENT_ASSURANCE",
    "source_proof": ".agent/runs/post-phase5-indicator-accuracy-core-return-stability-correction/source-proof.json",
    "evidence": ".agent/runs/post-phase5-indicator-accuracy-core-return-stability-correction/evidence.json",
    "evidence_sha256": "6a8727990a5fa94456264ee7ff9a3b6887a7fbc31281a86f7bf8dd3d598cacfc",
    "report": ".agent/runs/post-phase5-indicator-accuracy-core-return-stability-correction/report.md",
    "report_sha256": "bcb693f4469f8b0dfa03d4087f3e6338b1f3b2293b0625d06edea05926aadfeb",
    "product_source_sha256": "acf0d2367d3b0401cff7551360e551fc90b690de266e41be943a3aa7ac7897d6",
    "product_test_sha256": "cab28309877cb62a87ecc78ee8dcf2b5aaff20c4ce010381c6f13d49c9836a00",
    "required_next_owner": "post-phase5-indicator-accuracy-core-correction-assurance",
    "independent_acceptance": false,
    "publication": false,
    "deployment": false
  },
  "oracle_extension_requirements": [
    "Preserve the original sealed tests/oracle; their four constant fractional peer-ratio failures are new counterexamples, not permission to weaken masks.",
    "Author fresh exact-rational/analytical and high-precision log expectations for F02/F03, constant fractional ratios, finite extreme normalized windows and exact large linear levels before reading product helpers or implementation-owner tests.",
    "Reuse unaffected original independent checks read-only, retaining the same strict thresholds and complete-array masks.",
    "Verify current source/contract resource bounds, all 58 outputs/contracts/roles and actual consumer paths; no numerical publication is authorized."
  ],
  "concurrent_documentation_owner": {
    "capsule": "paper-trader/docs/research/kleppmann/INTAKE-CAPSULE.md",
    "scope": [
      "AGENTS.md appended professional-reference section",
      "paper-trader/docs/engineering-references/",
      "paper-trader/docs/research/kleppmann/"
    ],
    "handling": "Preserve and separately reconcile authorized documentation-only changes; any product/control drift is a blocker."
  },
  "fresh_owner_assignment": {
    "owner_task": "01a04883-7dc6-71a1-bb51-9e9dff45c450",
    "title": "Corrected core indicator assurance",
    "coordinator_task": "01a0487e-b73b-76a0-bffd-870f6f6bc6af",
    "previous_owner_task": "01a04748-debe-76a1-bc69-4d3d3a8ae038",
    "reason": "Previous owner requested a fresh independent context before starting this capsule; no goal, tests/oracle, formula-helper inspection or product/control edits started there.",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "parallel_budget": 0,
    "history_fork": false,
    "environment": "local saved worktree, no clone/replacement worktree",
    "authority": "Explicit owner routing delegations and v0_standing_development_authorization",
    "routing_seal": ".agent/runs/post-phase5-indicator-accuracy-core-correction-assurance-routing/closure-seal.json",
    "numerical_verdict": null
  }
}

---

# Corrected core-math independent assurance

Use a different owner from both corrections. Preserve the immutable original tests, oracle and REJECT. Author the declared fresh extension in the two new assurance-owned files, then confirm the complete wave before PASS.
