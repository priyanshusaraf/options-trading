---
{
  "id": "strategy-os-v0-chart-context-release-mutation-classification-correction",
  "lineage_id": "strategy-os-v0-research-market-context-annotation-replay-implementation",
  "programme_stage": "strategy-os-v0-monitoring-signals-review",
  "phase": "v0",
  "status": "active_parallel_critical_correction",
  "kind": "critical_release_route_classification_correction",
  "goal": "Keep the accepted owner-scoped V0 research drawing mutations reachable while restoring exact proof that every other mutation on the composed legacy router is denied.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "An explicit exact method/path allowlist contains only the three accepted review-drawing mutations; the mutation inventory equals denied plus accepted research routes; removing one classification returns RED; chart-context and V0 release-profile suites, architecture, protected hashes, and one Critical review pass."},
  "authorization_resolution": {"status": "ROOT_ROUTED_ACCEPTED_V0_INTEGRATION_CORRECTION", "evidence": "The accepted V0 market-context capsule added four non-executable owner-scoped research drawing routes. The provider execution-seam gate found that three of their mutation methods were not classified by the older exact V0 mutation inventory."},
  "risk_tags": ["critical", "release-profile", "route-authority", "research", "annotations", "no-execution"],
  "required_skills": ["strategyos-repo-orientation", "executing-strategy-os-slices", "risk-weighted-verification", "reviewing-strategy-os-critical-changes", "auditing-strategy-os-deployability"],
  "depends_on": ["strategy-os-v0-chart-annotation-replay"],
  "required_docs": [
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-research-market-context-annotation-replay-implementation.md", "sections": ["scope", "acceptance", "review_result", "nonclaims"]},
    {"path": "paper-trader/backend/app/core/release_profile.py", "sections": ["V0_NONMUTATING_POST_ROUTES", "V0_DENIED_MUTATION_ROUTES"]},
    {"path": ".agent/runs/strategy-os-v0-zerodha-data-account-bootstrap-correction/owner/correction-provider-execution-seams.log", "sections": ["exact unclassified route failure"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/app/core/release_profile.py",
    "paper-trader/backend/tests/test_v0_release_profile.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-chart-context-release-mutation-classification-correction.md",
    ".agent/runs/strategy-os-v0-chart-context-release-mutation-classification-correction"
  ],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-chart-context-release-mutation-classification-correction.md", ".agent/runs/strategy-os-v0-chart-context-release-mutation-classification-correction"],
  "protected_paths": ["paper-trader/backend/app/api", "paper-trader/backend/app/chart", "paper-trader/backend/app/providers", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Add an immutable exact method/path allowlist for only POST collection, PUT item and DELETE item market-context review-drawing routes. Do not classify the GET routes as mutations.",
    "Change the inventory test to subtract only those exact pairs and separately prove the allowlist equals the three accepted mutation operations present in the composed router.",
    "Keep annotations owner-scoped, non-executable and outside strategy identity. Do not change route handlers, schemas, migration, provider, execution, money or deployment behavior."
  ],
  "acceptance": [
    "The V0 mutation inventory is exactly the denied execution-shaped set after subtracting the exact accepted research-drawing pairs.",
    "No prefix or wildcard exemption exists. A new or misspelled mutation remains an inventory failure.",
    "Every allowlisted pair resolves to an actual composed route and denied_route returns None for it; all V0 execution-shaped mutations remain denied.",
    "Removing one exact allowlist pair reproduces the inventory failure; restoration returns GREEN.",
    "Focused chart-context/release suites, architecture, protected hashes and one independent Critical SPEC/QUALITY review pass."
  ],
  "test_plan": ["Run the exact failing inventory RED, implement the exact allowlist, run V0 release-profile and chart-context release/route suites, one ablation, architecture, then independent review."],
  "risk_classification": {"tier": "Critical", "reason": "A broad or wrong release-route exception could expose execution mutations in the V0 no-execution profile."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_chart_context_release_mutation_classification_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-chart-context-release-mutation-classification-correction/review-package.json", "review_paths": ["paper-trader/backend/app/core/release_profile.py", "paper-trader/backend/tests/test_v0_release_profile.py", "paper-trader/docs/agent/tasks/strategy-os-v0-chart-context-release-mutation-classification-correction.md", ".agent/runs/strategy-os-v0-chart-context-release-mutation-classification-correction"], "exclude_paths": ["paper-trader/backend/app/api", "paper-trader/backend/app/chart", "paper-trader/backend/app/providers", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-chart-context-release-mutation-classification-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["No wildcard/prefix exemption and no route, schema, migration, frontend, provider, execution, money or deploy edit."],
  "stop_conditions": ["Any accepted drawing route is executable or changes strategy/research identity, or any exemption must be broader than three exact method/path pairs."],
  "deployment_impact": {"classification": "compatible release-profile classification", "schema_change": false, "dependency_change": false, "configuration_change": false, "runtime_wiring": false, "locally_runnable": true, "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No new chart feature, executable annotation, provider, live authority, release deployability, deployment or V0 completion."]
}
---

# V0 chart-context release mutation classification correction

Classify three already accepted owner-scoped research drawing mutations without
creating a broad release-profile escape hatch.
