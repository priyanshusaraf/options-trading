---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-precision-slate-account-commerce-feature-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "important_read_only_precision_slate_account_commerce_feature_replan",
  "goal": "Define one desktop-first, feature-only Precision Slate account/onboarding/access/trial/coupon surface over the accepted strict account-commerce contracts, without publishing backend routes or wiring provider-backed billing.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write plan freezes the account UX, injected API boundary, exact external frontend paths/tests, privacy/accessibility states and a smallest feature-only successor before shared publication."},
  "risk_tags": ["important", "frontend", "auth", "privacy", "entitlements", "coupon", "onboarding", "desktop"],
  "depends_on": ["strategy-os-v0-account-commerce-strict-consumer-fixture-correction"],
  "dependency_gate": {"review_verdict": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction/review/verdict.json", "review_verdict_sha256": "487daa4c5f54e90e80f8025e86ec238e646a7fb85c6267e9d5d0586f6fdbf952", "policy": "Accepted unregistered API contracts may drive a feature-only external frontend successor; backend/shared route publication, Razorpay/provider flows, admin and deployment remain closed."},
  "owner_direction": {"accepted": true, "scope": "Desktop Strategy OS UX should follow the established strategy-os-frontend Precision Slate experience; account, required details, access and trial/coupon experience may be implemented while shared publication and external provider authority remain gated."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-account-commerce-strict-consumer-fixture-correction/review/verdict.json", "sections": ["SPEC", "QUALITY", "closed_findings", "nonclaims"]},
    {"path": ".agent/runs/strategy-os-v0-account-commerce-service-integration-replan/decision.json", "sections": ["serialized_queue", "commercial_and_external_gates", "privacy_and_admin_boundaries"]},
    {"path": ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan/route-matrix.json", "sections": ["consumer_contract", "route_inventory", "errors", "precision_slate_consumer"]},
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/package.json", "sections": ["scripts", "dependencies"]},
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product/routes.tsx", "sections": ["registry", "productRouteObjects", "RouteTransitionBoundary"]},
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx", "sections": ["global navigation", "topbar", "load and error patterns"]},
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts", "sections": ["transport", "error", "abort", "strict parsing"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-precision-slate-account-commerce-feature-replan.md", ".agent/runs/strategy-os-v0-precision-slate-account-commerce-feature-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-precision-slate-account-commerce-feature-replan.md", ".agent/runs/strategy-os-v0-precision-slate-account-commerce-feature-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": ["Inventory the actual React/Vite Precision Slate shell, navigation, transport/contracts, tokens, route tests and existing dirty ownership before naming any external frontend path.", "Define a desktop-first Account surface with stable loading/error/empty/ready states for current access and account status, a required-details form with inline plus focusable-summary validation, beta activation, coupon redemption and explicit access expiry/source facts.", "Represent checkout/payment/subscription/refund as clear unavailable states from the accepted typed API contract; do not simulate provider success, collect card data or hardcode production prices.", "Keep support-message/reply, Google identity, password recovery and admin/operator surfaces absent unless already accepted exact APIs exist; founder ordinary-user access is not an admin presentation shortcut.", "Use an injected, same-origin, credentialed, no-store, abortable strict account-commerce client for feature tests; do not register shared backend routes or publish the new product route in this replan.", "Preserve the existing Precision Slate visual language and desktop information density. Avoid a generic SaaS settings page; use the access lifecycle as the page's structural signature, while keeping keyboard focus, error proximity and contrast explicit."],
  "acceptance": ["Plan names exact external frontend source/test/style paths with hashes and no collision with inherited product work.", "Information architecture and state matrix cover required details, access, trial, coupon, unavailable billing, retry/expiry and privacy without exposing raw coupon/profile values after submission.", "Transport contract matches accepted same-origin/CSRF/no-store/abort/strict parser semantics and remains injected/unpublished until shared assembly.", "Desktop wireframe, token reuse and signature interaction match Precision Slate; no mobile optimization work is introduced.", "One smallest feature-only successor, one Important review, shared-assembly dependency and later local E2E gate are sealed; architecture and protected hashes pass with zero product writes."],
  "test_plan": ["Read-only external frontend route/API/token/test inventory, focused UI/UX guidance search, accessibility/state/error matrix, dirty-tree attribution, architecture and protected-hash checks. Implementation tests belong to the successor."],
  "risk_classification": {"tier": "Important", "reason": "The feature presents tenant-scoped profile/access/trial facts and transient coupon/details, but stays injected, feature-only and disconnected from provider/publication effects."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_precision_slate_account_commerce_feature_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-external-frontend-feature-replan", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-precision-slate-account-commerce-feature-replan.md", ".agent/runs/strategy-os-v0-precision-slate-account-commerce-feature-replan"], "output": ".agent/runs/strategy-os-v0-precision-slate-account-commerce-feature-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_precision_slate_account_commerce_feature_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only frontend feature replan; the successor receives the Important review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-precision-slate-account-commerce-feature-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-precision-slate-account-commerce-feature-replan.md", ".agent/runs/strategy-os-v0-precision-slate-account-commerce-feature-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-precision-slate-account-commerce-feature-replan/decision.json", "verdicts": ["UX", "TRANSPORT", "PRIVACY", "SUCCESSOR"], "max_rechecks": 0},
  "owner_gates": ["No external frontend product edit until this replan seals exact paths; no shared backend/frontend publication, Razorpay/provider/Google/email/admin authority, production data, credentials, money, deployment or V0-complete claim."],
  "stop_conditions": ["Existing external frontend ownership collides on required paths.", "Feature requires a backend contract beyond the accepted unregistered API.", "Any design would collect payment credentials or reveal raw profile/coupon material."],
  "deployment_impact": {"classification": "none; read-only feature replan", "highest_claim": "locally_runnable unregistered API and accepted Precision Slate shell", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No frontend implementation, product-route publication, shared API registration, provider billing, admin, Google/email, deployment, release readiness or V0 completion."]
}
---

# Precision Slate account-commerce feature replan

Plan one desktop-first account and access feature that belongs inside the
established Precision Slate workspace. Keep provider money and shared
publication closed.

## Sealed replan receipt

Decision: `KEEP + SEAL FEATURE-ONLY SUCCESSOR`. Five new external feature paths
were absent and collision-free. The successor uses the existing Precision Slate
tokens and an injected client; route publication, shared transport, providers,
admin and deployment remain closed.

## Sealed decision

**KEEP + SEAL FEATURE-ONLY SUCCESSOR.** Build one desktop Precision Slate
Account workspace around the server-evaluated lifecycle `Required details ->
Access source -> Product access`. Use an injected strict account-commerce client
and the existing shell tokens. Do not publish `/account`, change the shared API
client, register backend routes, or add provider billing in the feature successor.

The exact decision and matrices are under
`.agent/runs/strategy-os-v0-precision-slate-account-commerce-feature-replan/`:

- `decision.json`
- `state-matrix.json`
- `interaction-matrix.json`
- `transport-matrix.json`
- `privacy-matrix.json`
- `ux-spec.md`
- `architecture.json`
- `successor-capsule.json`
- `protected-hashes.json`

The smallest successor is
`strategy-os-v0-precision-slate-account-commerce-feature-foundation`. It owns
only five new external frontend feature files, then receives one Important
review. Shared route/API assembly and safe local E2E remain serialized later
gates. Admin/support replies, Google identity, email verification/recovery and
checkout/payment/subscription/refund controls remain absent.

No product implementation, product route, backend registration, provider or
network action, money, commit, deployment, release-readiness or V0-complete
claim is made.
