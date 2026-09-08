---
{
  "id": "post-phase5-indicator-accuracy-core-math",
  "phase": "post-phase5",
  "status": "accepted",
  "kind": "critical_accuracy_correction",
  "goal": "Implement only the 58 declared core-math component decisions, with fresh version-2 contracts and typed refusals where specified; no legacy or shared-file edits.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Implement only the 58 declared core-math component decisions, with fresh version-2 contracts and typed refusals where specified; no legacy or shared-file edits. Complete only with named source-bound evidence, protected-byte proof and the acceptance checks below; this does not authorize later scope."
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
    }
  ],
  "dependency_gate": "post-phase5-indicator-accuracy-contract-assurance",
  "allowed_paths": [
    "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
    "paper-trader/backend/tests/test_indicator_accuracy_core_math.py",
    ".agent/runs/post-phase5-indicator-accuracy-core-math",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-core-math.md",
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
    "Exactly component_scope is accounted for; no omitted outputs, parameters, input roles or validity masks.",
    "Every KEEP/REPLACE candidate has immutable semantic v2 definitions; REFUSE records have stable negative evidence and no executable placeholder version.",
    "All mathematical variants, bounds, first-valid indices, seeds, zero cases and resets match the matrix and pinned sources.",
    "Batch, streaming and serialized restart agree; state/compute/history bounds are measured over the declared parameter domain.",
    "Existing pandas/numpy lock is unchanged; TA-Lib is reference-only unless a separate oracle-environment owner gate is satisfied.",
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
    "assignment_id": "post_phase5_indicator_accuracy_core_math_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/runs/post-phase5-indicator-accuracy-core-math/v0-authorized-resume/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
      "paper-trader/backend/tests/test_indicator_accuracy_core_math.py",
      ".agent/runs/post-phase5-indicator-accuracy-core-math"
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
    "output": ".agent/runs/post-phase5-indicator-accuracy-core-math/v0-authorized-resume/report.md",
    "verdicts": [
      "IMPLEMENTATION"
    ],
    "max_rechecks": 0
  },
  "standing_owner_authorization": {
    "source_thread_id": "01a0451b-223b-7101-b3b0-40d638c7ab4b",
    "continuation_thread_id": "01a0477e-5e27-7862-b309-09643d2684dc",
    "date": "2026-08-28",
    "owner_instruction": "stop asking me to authorise all this, you already know what to do, do it without stopping. start a new chat for the same. get this done.",
    "scope": "Remaining accepted indicator accuracy correction programme, ordinary stage transitions, independent assurance, necessary bounded serial local correction capsules, registry/lineage integration, complete-universe assurance, and exactly one final evidence-backed critical review. No repeated routine AUTHORIZE token required.",
    "excluded_authority": [
      "live/VPS/credentials/provider networks",
      "orders/money/deployment",
      "SQL migrations",
      "dependencies/locks",
      "separately gated reference environment",
      "frontend/catalogue UI",
      "later Phase 6",
      "deferred-source replan"
    ]
  },
  "progress": {
    "status": "accepted_implementation_pending_independent_assurance",
    "verdict": "IMPLEMENTATION PASS",
    "report": ".agent/runs/post-phase5-indicator-accuracy-core-math/v0-authorized-resume/report.md",
    "report_sha256": "7aa7c2269f1e4f03a067f8dbc5928a4de895d4b793169933daaf5b0294674c4e",
    "evidence_sha256": "da79964200cb102bf9fd8ba8500646b4e8d2cd440a23a08d70240bdb7a287bc1",
    "native_default_comparisons_passed": 26,
    "raw_native_extended_failures_preserved": 5,
    "exact_specification_counterchecks_passed": 5,
    "independent_assurance_accepted": false,
    "publication": false,
    "deployment": false
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
  "resolved_authorization_blocker": {
    "code": "EXACT_REFERENCE_EXECUTOR_AUTHORIZATION_REQUIRED",
    "scope": "26 TA-Lib-backed core-math parity checks",
    "required_permission": "Explicit approval to provision a disposable reference-only TA-Lib native core v0.7.1 (2247d599bddf37ed37e3a709371517e46efc66f6) and Python wrapper v0.7.1 (a9ff1b47b3ddbd57274116645d688c0ed677338b), recording compiler/platform, source/package/build hashes and settings. No product dependency or lock change.",
    "why_indispensable": "The accepted source-access and verification contracts require a pinned executable reference. No exact approved executor exists in the available assurance receipt; the current product venv has no talib module. Source inspection, hand-calculated vectors and the old unpinned audit outputs cannot establish required native parity.",
    "asked_during_local_work": true,
    "authorization_received": false,
    "routine_continuation_authorization_remains_valid": true,
    "resolved_by": "v0_standing_development_authorization"
  },
  "reference_environment_addendum": {
    "owner": "current core-math capsule owner, serial; no child",
    "allowed_path": ".agent/runs/post-phase5-indicator-accuracy-core-math/reference-environment",
    "authorization": "latest explicit V0 development instruction, in direct response to the reference-environment approval request",
    "scope": "Review pinned core/wrapper build inputs and licences, provision isolated reference-only executor, record exact compiler/platform/artifact/settings identities and generate native parity evidence. Preserve the immutable predecessor assurance package. No product dependency/lock changes.",
    "parallel_budget": 0
  },
  "completion": {
    "status": "accepted_implementation_pending_independent_assurance",
    "verdict": "IMPLEMENTATION PASS",
    "report": ".agent/runs/post-phase5-indicator-accuracy-core-math/v0-authorized-resume/report.md",
    "report_sha256": "7aa7c2269f1e4f03a067f8dbc5928a4de895d4b793169933daaf5b0294674c4e",
    "evidence_sha256": "da79964200cb102bf9fd8ba8500646b4e8d2cd440a23a08d70240bdb7a287bc1",
    "native_default_comparisons_passed": 26,
    "raw_native_extended_failures_preserved": 5,
    "exact_specification_counterchecks_passed": 5,
    "independent_assurance_accepted": false,
    "publication": false,
    "deployment": false
  }
}

---

# Core math

Implement only the 58 declared core-math component decisions, with fresh version-2 contracts and typed refusals where specified; no legacy or shared-file edits.

Activated after accepted contract assurance under the owner’s 2026-08-28 standing continuation instruction. Parallel budget remains zero. Only the declared core-math paths and evidence are writable. The latest owner instruction now authorizes the isolated reference-executor addendum; registry publication still requires its evidence and integration gates.


## Local evidence checkpoint

All 58 candidates are implemented and unpublished. Final local/compatibility checks pass; source/protected-byte and four isolated mutation receipts pass. At the sealed local checkpoint, the exact reference executor was not yet authorized or available. That permission has since been granted under the expanded V0 instruction. This capsule remains incomplete until the required source-specific parity gate is satisfied. See `.agent/runs/post-phase5-indicator-accuracy-core-math/report.md` and `blocker.json`. Do not resume with another routine stage-token request; preserve standing authorization.


## Expanded V0 authorization supersedes the reference-environment pause

The latest owner instruction approves the isolated reference environment and standing development continuation through V0. The prior local checkpoint and blocker remain immutable historical records, not the current permission state. Continue the declared serial core-math work and preserve all correctness/independence gates. No further routine stage authorization is required.


## Implementation acceptance

The source-specific default gate passes for all 26 native-backed components. Five extended/adversarial native failures remain preserved and pass complete-array exact-specification counterchecks; no universal native parity is claimed. The implementation is accepted for handoff to a different assurance owner, with no numerical publication or deployment authority. Current evidence is under `v0-authorized-resume/`; the old incomplete checkpoint is historical and unchanged.
