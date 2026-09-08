---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-account-commerce-service-integration-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_account_entitlement_billing_service_replan",
  "goal": "Define the smallest complete V0 account-to-access service sequence over accepted browser auth, account lifecycle, entitlement/coupon/trial/founder policy, platform operations and privacy-safe admin contracts, while keeping Razorpay live money and shared publication externally gated.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write decision maps account/session, founder complimentary access, 15-day beta coupon/trial, subscription/payment facts, entitlement derivation, support/admin privacy, persistence/API/frontend/deployment seams and names the next dependency-ready successor."},
  "risk_tags": ["critical", "auth", "billing", "entitlements", "coupons", "trials", "privacy", "tenancy", "deployability"],
  "depends_on": ["strategy-os-v0-paper-runtime-admission-command-authority-correction", "strategy-os-v0-entitlement-policy-contract-foundation", "strategy-os-v0-account-lifecycle-contract-foundation", "strategy-os-v0-platform-operations-persistence", "strategy-os-v0-founder-admin-numeric-projection-correction"],
  "dependency_gate": {"paper_runtime_recheck_sha256": "3a2bff32cb81d0e065ae986a9232cddec530b752c107d0b1c7044dd3545172a5", "policy": "Account/commerce service architecture may proceed locally; real Razorpay keys, prices/tax/refund policy, Google/email providers, shared publication and deployment remain external gates."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-post-foundations-launch-convergence-replan/decision.json", "sections": ["accepted_local_foundations", "missing_local_integrations", "external_prerequisite_gates", "deployment_matrix", "effects"]},
    {"path": ".agent/runs/strategy-os-v0-entitlement-policy-contract-foundation/review/recheck-verdict.json", "sections": ["SPEC", "QUALITY", "owner_gates"]},
    {"path": ".agent/runs/strategy-os-v0-account-lifecycle-contract-foundation/review/recheck-verdict.json", "sections": ["SPEC", "QUALITY", "owner_gates"]},
    {"path": ".agent/runs/strategy-os-v0-founder-admin-numeric-projection-correction/review/recheck-verdict.json", "sections": ["SPEC", "QUALITY", "owner_gates"]},
    {"path": ".agent/runs/strategy-os-v0-platform-operations-persistence/report.md", "sections": ["Outcome", "Persistence contract", "Privacy and operator boundaries", "Deployment impact"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-service-integration-replan.md", ".agent/runs/strategy-os-v0-account-commerce-service-integration-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-service-integration-replan.md", ".agent/runs/strategy-os-v0-account-commerce-service-integration-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
  "scope": ["Inventory exact browser-auth/session, account lifecycle, entitlement/coupon/trial/founder, billing policy, platform operations, support/analytics/admin projection and existing API/frontend seams.", "Separate account identity, payment/order/subscription facts, coupon redemption, trial grant and derived entitlement; browser amounts/labels/coupon strings never grant access.", "Define founder email complimentary access as an explicit owner-scoped policy fact, not a hard-coded hidden admin bypass; admin/operator authority remains separate from ordinary user access.", "Define test/live Razorpay isolation, server-owned catalogue/order, checkout signature, raw-body webhook verification, idempotent/reordered events, entitlement convergence, reconciliation/refund nonclaims and exact external pricing/tax/key gates.", "Preserve customer strategy/PnL/broker-credential privacy: operations/admin sees only approved aggregate/platform/support facts.", "Serialize dedicated unregistered service/API/frontend successors before shared route/router assembly and name exact paths/collisions/deployment impact."],
  "acceptance": ["Account-to-access matrix names one authority for session, account lifecycle, founder complimentary policy, coupon/trial, payment/subscription facts and derived entitlement with tenant isolation.", "15-day beta access requires the declared user details and explicit redemption/grant facts; no client or email string alone grants access.", "Razorpay matrix follows server order/signature/raw-body webhook/idempotency/test-live/reconciliation constraints and lists pricing/tax/refund/key owner gates without initiating money.", "Admin privacy matrix excludes strategy graph, research inputs/results, PnL, positions, broker credentials and payment payloads while retaining approved usage/subscription/support aggregates.", "One smallest local successor and later serialized service/API/frontend/deployment queue are sealed; architecture passes with zero product writes."],
  "test_plan": ["Read-only source, contract, route, frontend, data-flow, tenant, billing and deployability inspection; implementation tests belong to successors."],
  "risk_classification": {"tier": "Critical", "reason": "Account and billing defects can create unauthorized access, payment misattribution, privacy leakage or cross-tenant effects."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_account_commerce_service_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-architecture-privacy-billing-evidence", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-service-integration-replan.md", ".agent/runs/strategy-os-v0-account-commerce-service-integration-replan"], "output": ".agent/runs/strategy-os-v0-account-commerce-service-integration-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_account_commerce_service_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only Critical architecture/privacy/billing replan; implementations receive their declared reviews.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-account-commerce-service-integration-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-account-commerce-service-integration-replan.md", ".agent/runs/strategy-os-v0-account-commerce-service-integration-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-account-commerce-service-integration-replan/decision.json", "verdicts": ["ARCHITECTURE", "AUTH", "BILLING", "PRIVACY", "DEPLOYABILITY"], "max_rechecks": 0},
  "owner_gates": ["No real Razorpay/Google/email/provider credentials or network calls, pricing/tax/refund/commercial decision, live execution authority, shared API/frontend publication, production account/data, VPS/deployment or money action."],
  "stop_conditions": ["Safe local successor requires a commercial price/tax/refund decision or real provider key.", "Existing account/entitlement/platform-operations authorities cannot compose without schema or canonical semantic change.", "Shared route/frontend ownership collision cannot be serialized."],
  "deployment_impact": {"classification": "none; read-only account/commerce service replan", "highest_current_claim": "locally_runnable", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "replan_result": {"verdict": "KEEP + HARDEN", "decision_sha256": "6b572af858372d7af6163b1dd1bb845e7a90fc9ccb48bba57dd926afcc4d9370", "evidence_manifest_sha256": "ddea162ec2d8a72eb4eb4be4be64af584d64319be5c0ae70167195998f2f59b8", "successor": "strategy-os-v0-account-commerce-local-service-foundation", "migration_required": true, "product_writes": 0, "deployment": false},
  "nonclaims": ["No auth/billing/admin service implementation, payment/order/refund, real provider integration, shared API/frontend, deployment, release readiness or V0 completion."]
}
---

# Account and commerce service integration replan

Compose accepted local account, entitlement and operations foundations into the next
V0 user-access journey without initiating payments or publishing shared routes.

## Sealed decision

`KEEP + HARDEN`: build one dedicated unpublished local account-commerce service
foundation next. It must bind the current browser session and active membership to
one server-derived owner authority, record required profile evidence, reduce only
durable coupon, trial, verified-payment, or explicit complimentary facts into the
current entitlement projection, and expose privacy-safe service results without
registering an API route or changing Precision Slate.

Founder complimentary access is ordinary-user product access from an immutable,
explicit owner-scoped grant. Founder email is bootstrap input only. It never grants
access at request time and never creates operator authority. The founder operator is
a separate principal and permission boundary; operator mutation stays closed until
the owner approves its session, step-up, MFA/recovery, replacement, permission, and
audit ceremony.

The named beta policy is 15 days. A grant requires server-attested required profile
details and a durable eligibility/prior-use plus coupon-redemption or trial-grant
fact. Client amounts, plan labels, coupon strings, email addresses, and browser
success callbacks are inputs only and never access authority.

The exact decision, authority/privacy matrices, Razorpay review, serialized queue,
deployment obligations, source register, validation receipts, and hashes are under
`.agent/runs/strategy-os-v0-account-commerce-service-integration-replan/`.

No product source, shared route, external frontend, provider, credential, payment,
refund, deployment, CURRENT, or PROGRAMME write belongs to this capsule.
