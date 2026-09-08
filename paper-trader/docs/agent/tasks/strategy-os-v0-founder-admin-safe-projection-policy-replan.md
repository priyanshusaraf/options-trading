---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-founder-admin-safe-projection-policy-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_founder_admin_privacy_replan",
  "goal": "Define the smallest useful founder/admin projection boundary over accepted account, entitlement, support, analytics and operations facts while keeping operator authentication, PII, private strategy/money data and publication closed.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "A source-to-admin matrix classifies safe fields, structural exclusions, small-cell and operator-authority gates, separates pure projection from privileged access/mutation, and seals one pure unpublished successor with zero product writes."},
  "risk_tags": ["critical", "admin", "privacy", "tenant-isolation", "operator-authority", "small-cell"],
  "depends_on": ["strategy-os-v0-platform-operations-persistence", "strategy-os-v0-entitlement-policy-contract-foundation", "strategy-os-v0-structured-support-contract-foundation", "strategy-os-v0-product-analytics-context-validation-correction", "strategy-os-v0-account-lifecycle-contract-foundation"],
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-owner-direction-extension-2026-08-29/report.md", "sections": ["Founder operator and complimentary entitlement"]},
    {"path": ".agent/runs/strategy-os-v0-post-0045-parallel-materialization-audit/account-commerce-operations/report.md", "sections": ["Authority model", "Tenant and operator data-flow matrix", "Founder operator journey acceptance", "Failure hypotheses", "Verification gates for successors", "Owner, legal, commercial and external gates"]},
    {"path": ".agent/runs/strategy-os-v0-account-lifecycle-local-authority-policy-replan/decision.json", "sections": ["accepted_authority", "safe_pure_contract", "fact_separation", "unresolved_owner_external_legal"]},
    {"path": ".agent/runs/strategy-os-v0-product-analytics-policy-replan/decision.json", "sections": ["safe_pure_contract", "prohibited", "owner_privacy_security_gates"]},
    {"path": ".agent/runs/strategy-os-v0-structured-support-policy-replan/decision.json", "sections": ["safe_structured_contract", "prohibited", "unresolved_owner_privacy_security"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-safe-projection-policy-replan.md", ".agent/runs/strategy-os-v0-founder-admin-safe-projection-policy-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-safe-projection-policy-replan.md", ".agent/runs/strategy-os-v0-founder-admin-safe-projection-policy-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
  "scope": ["Inventory accepted platform-operations views/contracts and accepted pure account/entitlement/support/analytics candidates without importing tenant private or money domains.", "Define useful pure admin-safe account-state, entitlement-class, structured-support, thresholded-product-aggregate and operational-health projection ceilings.", "Keep PlatformOperatorBinding, operator step-up/session/permission, admin projection, operator mutation and audit as distinct facts.", "Prohibit tenant impersonation, generic search, raw logs/payloads, contact PII by default, small-cell output without approved threshold, private strategy/research/monitoring/money/provider/payment facts and arbitrary properties.", "Do not choose step-up/MFA/recovery, operator session lifetime, permissions/staffing, small-cell threshold, contact fields, retention, DB role, API/frontend or deployment."],
  "acceptance": ["Matrix names exact safe sources/fields and forbidden imports/joins with no invented production policy.", "Safe successor is pure/unpublished and consumes only already-safe projections plus injected operator/threshold policy proofs; it authenticates nobody and publishes nothing.", "Projection output is structurally blind to strategy/research/monitoring detail/money/provider/payment/credential/free-text/raw transport facts and cannot carry tenant impersonation authority.", "Operator auth/session/permissions, small-cell threshold, contact PII, persistence/SQL roles, routes/frontend and deployment remain exact gates.", "Architecture passes with zero product/test/schema/frontend/deploy writes."],
  "test_plan": ["Read-only operations/account/analytics/support contract/source inventory, policy matrix and architecture validation; product tests belong to successor."],
  "risk_classification": {"tier": "Critical", "reason": "An admin projection can become a cross-tenant exfiltration or authority surface even when every source contract is individually safe."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_founder_admin_safe_projection_policy_replan", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only privileged-boundary routing; any projection or operator successor receives Critical review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-policy-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-founder-admin-safe-projection-policy-replan.md", ".agent/runs/strategy-os-v0-founder-admin-safe-projection-policy-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-founder-admin-safe-projection-policy-replan/decision.json", "verdicts": ["ARCHITECTURE", "PRIVACY", "AUTHORITY"], "max_rechecks": 1},
  "owner_gates": ["No operator step-up/MFA/recovery/session, permission/staffing, small-cell threshold, contact/PII, retention, persistence/DB role, mutation/audit route, API/frontend or deployment without explicit owner/security/privacy authority."],
  "stop_conditions": ["Useful projection requires private table joins, generic search, stable strategy/provider/payment identifiers, PII by default, small-cell publication or tenant impersonation.", "Shared product/schema/API/frontend paths need mutation."],
  "deployment_impact": {"classification": "none; read-only founder/admin projection replan", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "replan_result": {"verdict": "FOUNDER ADMIN PROJECTION REPLAN PASS", "decision": "START PURE THRESHOLDED NON-PUBLISHABLE AGGREGATES; DEFER INDIVIDUAL AND PRIVILEGED ADMIN", "decision_sha256": "9036546b0be41c52deaa3a521ea6d4cf02f4b6397d47c7e98c09a5a87171d53d", "policy_matrix_sha256": "f54e87f26e7f60a7c6729365087311cc3a970f3d14a16d78b80ff7501be62052", "successor_capsule_sha256": "39a8c13a3eb9c3ce4a589afca819020cf70e0821edf43c8a088a86ae4a54b37b", "successor": "strategy-os-v0-founder-admin-safe-projection-contract-foundation", "product_writes": 0, "deployment": false},
  "nonclaims": ["No operator login/session, admin projection, account/support/entitlement mutation, dashboard, API/frontend, deployment or V0 completion."]
}
---

# Founder/admin safe projection policy replan

Define useful operator visibility without private tenant content, money facts,
impersonation or publication authority.

## Replan evidence receipt

Existing operations count views remain inputs only because they have no approved
small-cell threshold. The pure successor is aggregate-only, thresholded and
non-publishable. Individual account/support access and operator authentication
remain separate later gates.
