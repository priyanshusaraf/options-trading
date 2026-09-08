---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-account-commerce-shared-assembly-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "important_read_only_account_commerce_shared_assembly_replan",
  "goal": "Define the smallest coordinated backend/frontend assembly that publishes the accepted Account workspace and account-commerce router, while preserving provider-key onboarding as the next explicit V0 dependency.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write route/transport/navigation/onboarding decision names exact shared assembly paths/tests, rollout order, provider-key successor and local E2E gate."},
  "risk_tags": ["important", "auth", "csrf", "frontend", "api", "account", "entitlements", "publication"],
  "depends_on": ["strategy-os-v0-account-commerce-strict-consumer-fixture-correction", "strategy-os-v0-precision-slate-account-commerce-feature-foundation", "strategy-os-v0-catalogue-formula-help-authority-contract"],
  "dependency_gate": {"account_api_review_sha256": "487daa4c5f54e90e80f8025e86ec238e646a7fb85c6267e9d5d0586f6fdbf952", "account_feature_recheck_sha256": "b51621f1e4d73dbf921de62f5b7a35e30cef63d83ea7798787aafea08e18fd69", "formula_help_verdict_sha256": "6ec1cf8cbdbeb3d17abd88c08f9600df4f02499a31842adae57bd9d91fbba54f", "policy": "Publish only accepted account contracts and the existing strict feature. Provider connections, billing provider, admin, Google/email and deployment remain separate."},
  "owner_direction": {"workflow": "Invited beta users enroll/sign in by email, can change passwords, complete required details, obtain beta/coupon access, then proceed to a separately accepted data-provider key/reauth onboarding flow without repeatedly entering stable application keys.", "provider_truth": "Current provider connection backend is encrypted and owner-scoped but release-profile BLOCKED, has no frontend onboarding, and reports credential expiry UNVERIFIED. Do not claim this assembly completes provider onboarding."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan/decision.json", "sections": ["shared_assembly_gate", "precision_slate_gate", "provider_gate"]},
    {"path": ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan/route-matrix.json", "sections": ["route_inventory", "consumer_contract", "errors"]},
    {"path": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction/review/verdict.json", "sections": ["SPEC", "QUALITY", "closed_findings", "nonclaims"]},
    {"path": ".agent/runs/strategy-os-v0-precision-slate-account-commerce-feature-foundation/review/recheck-verdict.json", "sections": ["SPEC", "QUALITY", "PRIVACY", "ACCESSIBILITY", "closed_findings", "nonclaims"]},
    {"path": "paper-trader/backend/app/main.py", "sections": ["router registration", "release profile middleware"]},
    {"path": "paper-trader/backend/app/api/routes.py", "sections": ["mounted routers", "direct V1 boundaries"]},
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product/routes.tsx", "sections": ["registry", "productRouteObjects", "transition boundary"]},
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts", "sections": ["sole transport", "auth/CSRF/abort/request"]},
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx", "sections": ["global navigation", "topbar", "account shell"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-shared-assembly-replan.md", ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-shared-assembly-replan.md", ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": ["Inventory exact backend router-registration/versioning/release-profile collision points and define one direct-V1 account-commerce registration without mount_versioned or unversioned mirror.", "Inventory the sole StrategyApi transport and define one adapter satisfying AccountCommerceTransport with same-origin credentials, no-store, redirect-error, exact CSRF and mandatory abort; no second fetch client.", "Define /account route, navigation, transition/error boundaries and accepted AccountAccessWorkspace composition inside Precision Slate without changing strategy routes or exposing provider/admin/payment controls.", "Define onboarding entry: after invited enrollment or sign-in, incomplete profile/inactive access reaches Account; active returning access may continue to Strategies. Browser flags never grant access and redirects must not loop or flash private stale content.", "Keep checkout/payment/subscription/refund typed unavailable; no provider or fake billing success.", "Name the next exact V0 data-provider onboarding successor using the accepted encrypted owner-scoped data-only connection backend, including stable app-key retention, daily/session reauth, readiness/expiry/revocation states and user notification. Do not implement it here.", "Define coordinated backend/frontend rollout/rollback and safe local synthetic E2E; catalogue help mixed-version rule remains respected."],
  "acceptance": ["Decision names exact shared backend/frontend paths, route inventory and no-collision proof with direct-V1 account API registered once.", "Sole transport adapter and strict feature preserve auth/CSRF/privacy/abort/no-store contracts; no second transport/global account authority appears.", "Route/navigation/onboarding matrix covers invited enrollment, login, password change continuity, incomplete/active/expired access, trial/coupon and typed unavailable billing without redirect loops.", "Provider onboarding remains an exact next V0 capsule with current gaps stated: release blocked, no frontend, expiry unverified; no false completion claim.", "Coordinated rollout/rollback and local E2E plan include synthetic users, restart, tenant separation and no live/provider/money action; architecture/protected hashes pass with zero product writes."],
  "test_plan": ["Read-only backend/frontend route/transport/auth/collision inventory, onboarding state machine, provider gap matrix, rollout ordering, architecture and protected hashes. Implementation tests belong to successor."],
  "risk_classification": {"tier": "Important", "reason": "Shared publication crosses browser auth, CSRF, tenancy and access routing but does not open provider money or live authority."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_account_commerce_shared_assembly_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-shared-assembly-replan", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-shared-assembly-replan.md", ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan"], "output": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_account_commerce_shared_assembly_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only Important assembly replan; implementation receives integrated review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-shared-assembly-replan.md", ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan/decision.json", "verdicts": ["ROUTES", "TRANSPORT", "ONBOARDING", "QUEUE"], "max_rechecks": 0},
  "owner_gates": ["No backend/frontend product edit, provider keys/network, billing provider, Google/email, admin/support reply, production data, money, commit, deployment or V0-complete claim."],
  "stop_conditions": ["Accepted API/feature contracts cannot compose without schema change.", "Direct-V1 registration collides with versioning or another owner.", "Onboarding needs provider lifecycle fields not yet accepted."],
  "deployment_impact": {"classification": "none; read-only shared assembly replan", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "replan_result": {
    "status": "sealed_read_only_replan",
    "decision": "KEEP + HARDEN IN ONE COORDINATED SUCCESSOR",
    "decision_path": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan/decision.json",
    "route_matrix": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan/route-matrix.json",
    "onboarding_matrix": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan/onboarding-matrix.json",
    "shared_successor": "strategy-os-v0-account-commerce-shared-assembly",
    "shared_successor_capsule": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan/shared-successor-capsule.md",
    "provider_successor": "strategy-os-v0-data-provider-key-onboarding-foundation",
    "provider_successor_capsule": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan/provider-successor-capsule.md",
    "backend_registration": "one direct /api/v1/account-commerce include in main.py outside routes.router and mount_versioned",
    "frontend_publication": "/account through the sole route registry, StrategyApi transport and shared Precision Slate frame",
    "onboarding_authority": "fresh server account-commerce status after verified session; no browser flags",
    "catalogue_rollout": "backend and frontend remain one coordinated compatibility unit unless a separately authorized versioned transition precedes them",
    "provider_current_truth": "release BLOCKED; frontend ABSENT; credential expiry/readiness UNVERIFIED",
    "product_writes": 0,
    "deployment": false
  },
  "nonclaims": ["No shared publication, provider onboarding, billing/admin/Google/email, deployment, release readiness or V0 completion."]
}
---

# Account-commerce shared assembly replan

Plan one coordinated publication of the accepted Account workspace, then route
provider-key onboarding as the next explicit V0 dependency.

The sealed decision is `KEEP + HARDEN IN ONE COORDINATED SUCCESSOR`. The account
router remains unpublished in this capsule. Its successor must register the
direct-V1 router once, adapt the accepted client through the sole `StrategyApi`
transport, publish `/account` inside the shared Precision Slate frame and make a
fresh server status the only onboarding authority. The next provider-key capsule
remains blocked on private provider conformance, data rights and publication
authority; current release status is BLOCKED, its frontend is absent and expiry
and readiness remain UNVERIFIED.
