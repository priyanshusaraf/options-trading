---
{
  "id": "strategy-os-v0-verified-language-catalogue",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_verified_language_publication",
  "goal": "Publish one server-derived, accuracy-allowlisted five-family v2 catalogue from the canonical PlatformRegistry, with monitoring-only Type 1 and typed unavailable dispositions.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "The authenticated versioned catalogue route exposes exactly one immutable registry-derived five-family projection, accepted components and typed exclusions with full identity/resource/capability facts; monitoring intent is registered without execution authority; one independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  },
  "risk_tags": ["critical", "canonical-registry", "public-language", "research-integrity", "authority-separation", "api-contract"],
  "required_docs": [
    {"path": ".agent/runs/post-phase5-indicator-accuracy-final-review/recheck-verdict.json", "sections": ["final_verdict", "finding_ids", "verified_counts", "nonclaims"]},
    {"path": ".agent/runs/strategy-os-v0-launch-convergence/architecture-decision.md", "sections": ["Five-family and desktop palette mapping", "Monitoring-only lifecycle", "Architecture invariant matrix"]},
    {"path": ".agent/runs/strategy-os-v0-launch-convergence/agents/nodes-signals/report.md", "sections": ["Five-family and Precision Slate mapping", "V0-G0: canonical palette projection"]},
    {"path": "paper-trader/docs/program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md", "sections": ["The five user-facing node families", "Strategy definition is not deployment"]},
    {"path": "paper-trader/docs/program/owner-steers/01-STRATEGY-LANGUAGE-NODE-SYSTEM.md", "sections": ["Type 1 execution starter pack", "Numerical validity", "Node versioning"]},
    {"path": ".agent/runs/strategy-os-v0-monitoring-intent-contract/report.md", "sections": ["Verdict", "Evidence", "Boundary"]},
    {"path": ".agent/runs/strategy-os-v0-signal-alert-attention-correction/review/verdict.json", "sections": ["SPEC", "QUALITY", "final", "finding_disposition"]},
    {"path": ".agent/runs/post-phase5-indicator-accuracy-recursive-sar-source-replan/decision.json", "sections": ["controlling_reference", "native_comparison_policy", "corrected_target_delta", "source_provenance_update", "retained_gates", "version_and_history"]}
  ],
  "dependency_gate": "Terminal indicator final review SPEC PASS / QUALITY PASS plus accepted monitoring-intent and signal-alert contracts; Q02 and Q14 accepted. No frontend/runtime/persistence authority follows.",
  "allowed_paths": [
    "paper-trader/backend/app/ir/library.py",
    "paper-trader/backend/app/editor/v2_catalogue.py",
    "paper-trader/backend/app/api/catalogue_routes.py",
    "paper-trader/backend/app/api/principal.py",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/tests/test_v0_verified_language_catalogue.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-verified-language-catalogue.md",
    ".agent/runs/strategy-os-v0-verified-language-catalogue"
  ],
  "new_paths": [
    "paper-trader/backend/app/editor/v2_catalogue.py",
    "paper-trader/backend/app/api/catalogue_routes.py",
    "paper-trader/backend/tests/test_v0_verified_language_catalogue.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-verified-language-catalogue.md",
    ".agent/runs/strategy-os-v0-verified-language-catalogue"
  ],
  "protected_paths": [
    "paper-trader/backend/app/ir/first_party",
    "paper-trader/backend/app/ir/registry.py",
    "paper-trader/backend/app/ir/node_contracts.py",
    "paper-trader/backend/app/ir/runtime.py",
    "paper-trader/backend/app/ir/resource_plan.py",
    "paper-trader/backend/app/editor/descriptors.py",
    "paper-trader/backend/app/api/ir_edit_routes.py",
    "paper-trader/backend/app/core/release_profile.py",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "frozen_projection": {
    "groups": [
      {"order": 1, "display_name": "Price, Instrument & Market Data", "visible_family": "TYPE_4"},
      {"order": 2, "display_name": "Indicators & Derived Features", "visible_family": "TYPE_2"},
      {"order": 3, "display_name": "Market Structure, Derivatives & Cross-Instrument", "visible_family": "TYPE_3"},
      {"order": 4, "display_name": "Logic, Math & State", "visible_family": "TYPE_5"},
      {"order": 5, "display_name": "Execution & Position", "visible_family": "TYPE_1"}
    ],
    "type_1_rule": "Expose only accepted monitoring-intent semantic-v2 components in V0. Exclude legacy execution/account/capital/order/position controls with typed reasons.",
    "analytical_rule": "Expose only the 108 independently accepted analytical v2 rows. Return the 17 REFUSE rows as unavailable dispositions, never components or numerical successes.",
    "conditional_data_rule": "Capability-gated Type 3/data nodes remain descriptors with exact declared capability/data requirements and conditional availability; catalogue presence is not provider support or backtest eligibility."
  },
  "scope": [
    "Add the accepted monitoring_intent_v2 contributor to the existing literal V2_CONTRIBUTORS tuple. Preserve every existing component/contract/implementation identity; only the aggregate registry snapshot may change additively.",
    "Implement a pure immutable editor projection from REGISTRY and ANALYTICAL_V2_DISPOSITIONS. Do not create a second registry, static frontend truth or caller-controlled filter.",
    "Each admitted component carries component/version, visible family, presentation order/name, display/domain/structural metadata, closed parameter/port descriptors, node-contract/implementation/data-requirement addresses, mode eligibility, provider requirements, resource profile and availability.",
    "Return typed exclusions for 17 analytical refusals and every non-monitoring Type 1 operation. Exclusions have stable codes and no executable descriptor.",
    "Add one authenticated GET `/api/ir/catalogue` route and its `/api/v1/ir/catalogue` mirror; classify it as read:project. Response is tenant-independent global product metadata but still requires an authorized product session.",
    "Keep the existing v1 editor document catalogue and Precision Slate unchanged; later frontend integration consumes this route."
  ],
  "acceptance": [
    "Exactly five groups appear once in order TYPE_4, TYPE_2, TYPE_3, TYPE_5, TYPE_1; execution is fifth and stable visible-family identities do not change.",
    "All admitted components are derived from REGISTRY, carry exact content addresses and have complete component/contract/implementation/data/resource facts. Reordering contributors cannot change canonical response bytes.",
    "Analytical closure is exactly 108 admitted and 17 unavailable; no REFUSE row is executable. Monitoring Type 1 admits exactly the 12 accepted v2 target/protection components and excludes unsupported Type 1 v1 operations.",
    "No admitted V0 Type 1 component exposes broker/account/order/capital/quantity/position/deployment/live authority; SL/TP facts remain monitoring-only.",
    "Capability-gated data nodes state conditional availability without provider conformance, rights or history claims.",
    "Both route versions require auth and read:project scope, have byte-equivalent bodies, bounded size/query/memory, immutable ETag/registry identity and no tenant strategy/research/PnL facts.",
    "Cold import/restart, affected IR/editor/auth/release-profile tests, 100,000 projection/resource check, omission/reorder/refusal/authority mutations and protected hashes pass.",
    "One fresh independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  ],
  "test_plan": [
    "Author the five-group and admitted/unavailable identity fixtures from accepted evidence before implementation, then RED/GREEN the pure projection and route.",
    "Run exact counts/addresses, contributor reorder, response determinism, auth/version mirrors, resource limits, restart/import and genuine isolated mutations with exact restoration.",
    "Run affected platform-library, complete-universe, editor/API auth, no-live-under-pytest and V0 release-profile selectors."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "01a04df0-2c15-7433-a0be-7353a0772ced",
  "review": {
    "required": true,
    "assignment_id": "strategy_os_v0_verified_language_catalogue_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Public catalogue publication changes canonical language visibility, identity and the execution-authority boundary.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-verified-language-catalogue/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/ir/library.py",
      "paper-trader/backend/app/editor/v2_catalogue.py",
      "paper-trader/backend/app/api/catalogue_routes.py",
      "paper-trader/backend/app/api/principal.py",
      "paper-trader/backend/app/main.py",
      "paper-trader/backend/tests/test_v0_verified_language_catalogue.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-verified-language-catalogue.md",
      ".agent/runs/strategy-os-v0-verified-language-catalogue"
    ],
    "exclude_paths": ["paper-trader/backend/app/ir/first_party", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/frontend"],
    "output": ".agent/runs/strategy-os-v0-verified-language-catalogue/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "Standing V0 authority permits this exact backend catalogue stage after accepted final accuracy review.",
    "Stop before frontend implementation, monitoring persistence/runtime, provider capability opening, schema, dependency, execution, money or deployment behavior."
  ],
  "stop_conditions": [
    "Any accepted first-party component/contract/implementation byte must change rather than being projected.",
    "A second registry, static client catalogue, provider-support inference or execution-authority field is required.",
    "Exact admitted/unavailable counts or five-family ownership cannot be derived from accepted evidence."
  ],
  "deployment_impact": {"classification": "compatible API/registry publication; no schema, dependency, provider or service change", "release_owner": "strategy-os-v0-security-operations-deployability"},
  "nonclaims": [
    "No frontend palette, monitoring assignment/runtime/alert delivery, provider/data-rights/backtest eligibility, persistence/schema, deployment, live/order/money or whole-V0 completion.",
    "Catalogue presence never means a provider supplies historical options/depth data or that a strategy can be backtested."
  ],
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-verified-language-catalogue/review/verdict.json",
    "verdict_sha256": "7a9353312a4843b5ebc04c6924f98a4b61f855e0a2dd6cebf45212523596a681",
    "finding_ids": [
      "F01_AUTHORITY_PRIVATE_GUARDS_NONVACUOUS",
      "F02_ANALYTICAL_CLOSURE_FIXTURE_UNSEALED",
      "F03_EXTERNAL_PROTECTED_PATH_UNSEALED"
    ],
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "Validate each admitted Type 1 row against the exact accepted monitoring_intent_v2 component, contract, implementation and data-requirement identities before projecting any nested descriptor value. Add a closed recursive public-surface validator and nested sentinel mutations for authority and tenant-private values.",
    "Embed the exact 108 accepted analytical identities and 17 unavailable reason codes in tracked test bytes, or a new tracked allowed fixture, and remove every test dependency on ignored `.agent` matrix state.",
    "Use the authentic pre-catalogue root seal `.agent/runs/strategy-os-v0-signal-alert-attention-correction-replan/root/protected-successor-start-final.log` (SHA-256 `1d565d18de9394e69740121d142e2621f9fa3f079b315a27ca6ac81ff5ab9568`, captured 2026-08-29 17:41:13) as the external source/config baseline. Compare all external-frontend entries to a correction-final capture and stop on any mismatch.",
    "The corrected external protected universe is source/config only: `.gitignore`, `.oxlintrc.json`, `README.md`, `index.html`, package/lock, tsconfig files, `vite.config.ts`, and all `src` files. VCS internals, installed node_modules, build/test output and caches are explicitly generated exclusions, not product source.",
    "Generate JUnit or collected-count evidence for the final affected selector. Do not infer 203 from dot counting; correct report/evidence totals to the exact executed value.",
    "Rebuild the same package lineage and route only the single allowed focused reviewer recheck."
  ],
  "correction_external_protected_scope": {
    "baseline": ".agent/runs/strategy-os-v0-signal-alert-attention-correction-replan/root/protected-successor-start-final.log",
    "baseline_sha256": "1d565d18de9394e69740121d142e2621f9fa3f079b315a27ca6ac81ff5ab9568",
    "namespace": "external-frontend",
    "targets": [".gitignore", ".oxlintrc.json", "README.md", "index.html", "package.json", "package-lock.json", "tsconfig.app.json", "tsconfig.json", "tsconfig.node.json", "vite.config.ts", "src"],
    "generated_exclusions": [".git", "node_modules", "dist", "coverage", "playwright-report", "test-results", ".vite", "caches"]
  }
}
---

# Verified language catalogue

Publish one authenticated server-derived five-family v2 palette from the canonical registry. Keep Execution & Position fifth and monitoring-only in V0.

## Implementation receipt

The bounded backend implementation is complete and locally verified. The catalogue contains
exactly 243 admitted rows: 108 accepted analytical v2 rows, 63 Type 3 rows, 60 Type 5 rows,
and 12 monitoring-only Type 1 v2 rows. It returns 17 analytical unavailable dispositions and
61 legacy Type 1 exclusions without executable descriptors.

Evidence is sealed under `.agent/runs/strategy-os-v0-verified-language-catalogue/`. The final
affected gate passed 203 tests; two cold imports produced identical catalogue and registry
identities and response bytes; the architecture validator passed 399 files with zero failures;
and the protected baseline and final manifests are byte-identical. Deployment impact remains a
compatible API/registry publication. The highest evidenced deployment level is locally verified;
release-deployable, production-rehearsed, deployed, frontend, persistence, runtime monitoring,
provider opening, schema, execution, live, money, and whole-V0 claims remain excluded.

Stop pending the declared fresh Critical `SPEC` and `QUALITY` review. Do not advance the
programme stage from this receipt.

## Critical-review correction receipt

The first Critical review is immutable at
`.agent/runs/strategy-os-v0-verified-language-catalogue/review/verdict.json`, SHA-256
`7a9353312a4843b5ebc04c6924f98a4b61f855e0a2dd6cebf45212523596a681`. Its three P1
findings are corrected without changing accepted catalogue membership, response bytes,
registry identity, ETag, provider facts, resource facts, or runtime semantics.

- F01: every monitoring Type 1 row must match the accepted contributor's exact component,
  contract, implementation, and data-requirement addresses. A recursive public-surface guard
  rejects nested authority and private-fact markers. Real count-preserving registry mutations
  now fail closed.
- F02: the tracked test contains the complete 108 accepted identities and all 17 unavailable
  identities with exact reason codes. It has no `.agent` fixture dependency.
- F03: the authentic pre-catalogue external baseline at
  `.agent/runs/strategy-os-v0-signal-alert-attention-correction-replan/root/protected-successor-start-final.log`
  (SHA-256 `1d565d18de9394e69740121d142e2621f9fa3f079b315a27ca6ac81ff5ab9568`)
  matches the correction-final external source/config capture across all 56 declared entries.

JUnit records exactly 14 focused and 203 affected passing tests, with zero failures, errors,
or skips. Fresh restart, 100,000 resource, mutation, repository-protected, external-protected,
and 405-file architecture gates pass. Stop for the one allowed same-lineage Critical recheck;
do not advance the programme stage.

## Terminal Critical-review receipt

The one allowed same-lineage recheck returned `SPEC PASS / QUALITY PASS / final PASS` at
`.agent/runs/strategy-os-v0-verified-language-catalogue/review/recheck-verdict.json`, SHA-256
`76ac68d907fc69866e94d9ab2a82c67c0ec45469ebc304ae30668b008ce09e11`.
F01-F03 are closed, evidence gaps are empty, and the recheck is consumed with zero remaining.

The accepted reviewed package is
`.agent/runs/strategy-os-v0-verified-language-catalogue/recheck-review-package.json`, SHA-256
`84b24f43d1b12b0d13df5a8945edb743d6b4ab85a061775aae96a36d221afd3d`, with reviewed
dirty-tree fingerprint `98f772b23e1bbe40c9f298a2b80c8ca68c63dfad144af6698986f183917aba49`.
No programme transition or later-stage advance is part of this receipt. All frontend,
monitoring-runtime, provider, schema, dependency, execution, live, money, deployment,
production-readiness, and whole-V0 nonclaims remain in force.
