---
{
  "id": "strategy-os-v0-frontend-route-attribution-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_frontend_authority_correction_after_replan",
  "goal": "Eliminate every observable URL/project/graph mismatch with a synchronous neutral transition barrier for programmatic and popstate navigation.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "The unchanged reviewer attribution probe plus picker/back/forward MutationObserver regressions pass repeatedly with zero stale states, while all accepted manifest/auth/router/API/artifact/protected/build/browser gates remain green."},
  "risk_tags": ["critical", "frontend", "tenant-attribution", "route-state", "replan"],
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-frontend-route-attribution-replan/decision.md", "sections": ["Frontend route-attribution replan"]},
    {"path": ".agent/runs/strategy-os-v0-frontend-production-convergence-foundation/review/recheck-verdict.json", "sections": ["blocking_findings", "closed_findings", "recheck"]}
  ],
  "dependency_gate": "strategy-os-v0-frontend-production-convergence-foundation consumed recheck",
  "allowed_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product/routes.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product/routes.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
    "paper-trader/docs/agent/tasks/strategy-os-v0-frontend-route-attribution-correction.md",
    ".agent/runs/strategy-os-v0-frontend-route-attribution-correction"
  ],
  "protected_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package-lock.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/auth",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/components",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/data",
    "paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Add a synchronous neutral route-transition state before programmatic navigate and during popstate; it exposes no project/graph facts.",
    "Use installed React/React Router APIs only; no package/lock change.",
    "Keep manifest, AuthGate, one REST transport, capability registry, routes and current Strategies semantics unchanged.",
    "Close only the remaining attribution finding; preserve closed protected-manifest and transport-guard evidence."
  ],
  "acceptance": [
    "The unchanged reviewer Chrome probe passes at least six consecutive picker/back/forward runs with zero stale project/graph/URL state.",
    "Removing/bypassing the barrier makes the targeted probe fail and exact bytes are restored.",
    "Neutral state is announced and contains no project/graph identifiers or record facts.",
    "Lint, typecheck, full tests, build, standard browser and production-boundary tests pass.",
    "One fresh independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  ],
  "test_plan": ["Targeted MutationObserver/Chrome RED-GREEN and barrier mutation, then full lint/typecheck/tests/build/browser/protected gates."],
  "parallel_budget": 0, "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root/v0_frontend_production_convergence",
  "review": {
    "required": true, "assignment_id": "v0_frontend_route_attribution_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Cross-project route attribution is a Critical tenant/IP truth boundary.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-frontend-route-attribution-correction/review-package.json",
    "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-frontend-route-attribution-correction.md", ".agent/runs/strategy-os-v0-frontend-route-attribution-correction"],
    "exclude_paths": ["paper-trader/backend", "paper-trader/frontend"], "output": ".agent/runs/strategy-os-v0-frontend-route-attribution-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1
  },
  "owner_gates": ["Latest owner desktop/frontend authority covers this correction. No deployment or new capability."],
  "stop_conditions": ["A backend, dependency, new route/feature, prototype or package/lock change is required.", "The reviewer probe remains scheduling-sensitive after the synchronous barrier."],
  "deployment_impact": {"classification": "compatible frontend authority correction; final release assembly remains V0-I"},
  "nonclaims": ["No new feature, mobile construction, provider/payment/backend/schema/deployment/live/order/money or V0 completion."],
  "final_review": {
    "review_task": "/root/v0_frontend_route_attribution_review",
    "verdict": "SPEC PASS / QUALITY PASS",
    "verdict_path": ".agent/runs/strategy-os-v0-frontend-route-attribution-correction/review/verdict.json",
    "verdict_sha256": "dfaeeb47bf88f737b03b3b67343c911029b8d588b964baa7afaee0b407ebbcab",
    "review_package_sha256": "f4b79019da4a61069b1fc4152a52e4a75a2ae65d4dbd24fbec6df29772869f23",
    "rechecks_used": 0,
    "rechecks_remaining": 1,
    "deployment": false,
    "v0_complete": false
  }
}
---

# Route attribution correction

Make route and displayed project/graph facts atomically consistent through a neutral synchronous transition barrier.
