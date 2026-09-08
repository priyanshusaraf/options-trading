---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-account-commerce-unregistered-api-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "important_read_only_unregistered_account_access_api_replan",
  "goal": "Define dedicated authenticated but unregistered V0 account/profile/access/trial/coupon API routes over the accepted local account-commerce service, with provider-backed billing/support/admin endpoints closed or typed unavailable until their authorities exist.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write route/auth/CSRF/error/privacy/idempotency matrix names the smallest unregistered API successor, exact paths/tests and serialized provider/frontend/shared-assembly gates."},
  "risk_tags": ["important", "auth", "csrf", "tenancy", "entitlements", "privacy", "api", "unregistered"],
  "depends_on": ["strategy-os-v0-account-commerce-local-service-foundation"],
  "dependency_gate": {"service_recheck_sha256": "bee8a881077b8be086ec5d3c1de4616e571a27445b2656aa5914e77d2a937a2e", "policy": "Dedicated local routes may be designed; Razorpay/provider billing, operator/admin activation, shared main registration, frontend publication and deployment remain closed."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-account-commerce-service-integration-replan/decision.json", "sections": ["account_to_access_invariants", "beta_resolution", "founder_resolution", "privacy_minimization", "serialized_queue", "commercial_and_external_gates"]},
    {"path": ".agent/runs/strategy-os-v0-account-commerce-local-service-foundation/review/recheck-verdict.json", "sections": ["SPEC", "QUALITY", "findings", "owner_gates", "nonclaims"]},
    {"path": "paper-trader/backend/AGENTS.md", "sections": ["API and authentication constraints"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-unregistered-api-replan.md", ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-unregistered-api-replan.md", ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
  "scope": ["Inventory existing authenticated route factories, principal/session/CSRF dependencies, error envelopes, owner resolution and main/router registration boundaries.", "Define read current access, record required profile evidence, grant beta trial, redeem trial-access coupon and read privacy-safe account status over the accepted service; request owner/email/client-valid flags never carry authority.", "Define exact request size/field/code limits, response vocabulary, idempotency/retry behavior, expiry semantics, no-cache headers, redaction and uniform tenant/auth failures.", "Keep checkout/order/payment/subscription/refund endpoints typed BILLING_PROVIDER_UNAVAILABLE until accepted Razorpay adapter and commercial policy exist.", "Keep operator/admin, Google, email recovery and support reply routes closed; ordinary user founder access is not an admin API.", "Do not register router in shared routes/main, edit external frontend, call providers, access keys, activate entitlements outside synthetic local tests or deploy."],
  "acceptance": ["Route matrix names method/path/auth/CSRF/input/output/effect/idempotency/privacy/error for every endpoint and closed provider/admin endpoint.", "Mutation endpoints use exact current browser user authority and CSRF/session semantics; anonymous/stale/service/cross-owner failures are uniform before service calls.", "Profile, beta and coupon inputs cannot carry raw secrets, owner ids, client price, entitlement, validity or access flags; responses expose no email, coupon plaintext, strategy/PnL/credential/payment payload.", "Provider-backed billing and operator/admin endpoints remain typed unavailable with zero provider/session calls.", "One exact unregistered API successor and later Precision Slate/shared assembly gates are sealed; architecture passes with zero product writes."],
  "test_plan": ["Read-only route/auth/CSRF/error/privacy/collision/source inspection and architecture validation; implementation tests belong to successor."],
  "risk_classification": {"tier": "Important", "reason": "The routes expose tenant-scoped access mutations but remain unregistered, local and provider-free."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_account_commerce_api_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-api-auth-privacy-evidence", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-unregistered-api-replan.md", ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan"], "output": ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_account_commerce_api_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only Important API routing; successor receives affected auth/privacy review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-unregistered-api-replan.md", ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan/decision.json", "verdicts": ["API", "AUTH", "PRIVACY", "TENANCY"], "max_rechecks": 0},
  "owner_gates": ["No Razorpay/Google/email/provider credentials/network, production commercial policy, operator/admin activation, shared route/frontend publication, production account/data, VPS/deployment or money action."],
  "stop_conditions": ["Safe route needs provider/commercial/operator authority or shared registration.", "Existing auth/CSRF/error envelope cannot compose without canonical change.", "Route path ownership collides with concurrent shared API work."],
  "deployment_impact": {"classification": "none; read-only unregistered API replan", "highest_current_claim": "locally_runnable", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "replan_result": {"verdict": "KEEP + HARDEN", "decision_sha256": "21f7132a4381599e007a7b48996b9b566ee285d1e7ab53c6e3136e1e420b895e", "route_matrix_sha256": "1e926670fe88caf9fc05aacbd1a77b30d75177e6e5de275f37f644893256daeb", "successor": "strategy-os-v0-account-commerce-unregistered-api-foundation", "product_writes": 0, "registered": false, "deployment": false},
  "nonclaims": ["No API implementation/registration, provider billing, frontend, payment/refund, deployment, release readiness or V0 completion."]
}
---

# Account-commerce unregistered API replan

Define the local authenticated route boundary over accepted account access without
publishing shared routes or implying provider billing.

## Terminal replan receipt

The read-only owner selected `KEEP + HARDEN` and sealed one smallest successor,
`strategy-os-v0-account-commerce-unregistered-api-foundation`. Its factory owns
the direct-V1 prefix `/api/v1/account-commerce`; it remains unregistered and must
not enter the legacy version mirror. The exact route/auth/CSRF/input/output/error/
privacy/idempotency matrix is in `.agent/runs/strategy-os-v0-account-commerce-unregistered-api-replan/route-matrix.json`.

Authenticated access/status reads, server-attested profile evidence, a single-use
15-day beta grant and trial-access coupon redemption are open only to that fresh
successor. Checkout, payment, subscription and refund remain fixed typed
`BILLING_PROVIDER_UNAVAILABLE` responses with no handler provider or session calls.
Operator/admin/founder lifecycle, Google/email recovery and support replies remain
absent. Precision Slate feature work and shared publication are serialized owner
gates after API acceptance.

This replan changed no backend, frontend, shared router, auth, schema, provider,
credential, money, runtime or deployment byte. It issues no implementation,
publication, deployability, release-readiness or V0-complete claim.
