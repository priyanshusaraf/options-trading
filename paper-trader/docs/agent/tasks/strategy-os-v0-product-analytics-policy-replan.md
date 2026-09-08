---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-product-analytics-policy-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "important_read_only_product_analytics_privacy_replan",
  "goal": "Translate the owner's need for platform usage and operational analytics into the smallest privacy-safe V0 first-party event contract, separating pure event candidates and aggregate dimensions from unresolved purpose, preference, retention, deletion, small-cell and processor policies.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "An event/destination/purpose matrix classifies allowed typed product outcomes, server authority, subject/tenant handling, admin-safe aggregate dimensions, prohibited strategy/money/credential content and unresolved preference/retention/deletion/threshold decisions; one safe pure unpublished successor is sealed with zero product writes."},
  "risk_tags": ["important", "analytics", "privacy", "admin-blindness", "tenant-isolation", "data-egress", "retention"],
  "depends_on": ["strategy-os-v0-platform-operations-persistence", "strategy-os-v0-entitlement-policy-contract-foundation", "strategy-os-v0-structured-support-contract-foundation"],
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-post-0045-parallel-materialization-audit/account-commerce-operations/report.md", "sections": ["Tenant and operator data-flow matrix", "Failure hypotheses", "Verification gates for successors", "Owner, legal, commercial and external gates"]},
    {"path": ".agent/runs/strategy-os-v0-launch-convergence/data-flow-matrix.md", "sections": ["V0 data-flow and operator-visibility matrix", "Structural controls required", "Unresolved owner/counsel questions"]},
    {"path": ".agent/runs/strategy-os-v0-post-0045-parallel-materialization-audit/account-commerce-operations/proposed-successor-capsules.json", "sections": ["strategy-os-v0-product-analytics-privacy", "strategy-os-v0-founder-operator-admin-boundary"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-policy-replan.md", ".agent/runs/strategy-os-v0-product-analytics-policy-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-policy-replan.md", ".agent/runs/strategy-os-v0-product-analytics-policy-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
  "owner_direction_facts": ["The founder/admin needs platform usage, subscription/support and operational analytics.", "User strategies, graphs, parameters, symbols, signals, PnL, positions, balances and credentials never enter operator analytics.", "Strategy OS must not expose session replay, screenshots, raw URLs/payloads or arbitrary properties."],
  "scope": [
    "Inventory existing event producers, SDKs, tag managers, collectors, destinations and dashboards without adding or activating any.",
    "Decide whether a pure unpublished event-candidate contract can proceed with injected finite event types, purposes, route templates and bounded enum/boolean/integer dimensions and no storage/emission.",
    "Separate subject-scoped event candidate, preference/authority fact, first-party storage fact, admin aggregate fact and operational telemetry fact.",
    "Define an admin-safe dimension ceiling and prohibit strategy/research/monitoring-detail/money/provider/payment/personal/free-form/raw transport/session-replay fields, including nested or encoded property bags.",
    "Do not choose production event purposes/catalogue, consent/preference behavior, pseudonymous identifier lifetime, retention/export/delete, small-cell threshold, region, external processor or operator access; keep them exact gates.",
    "Name later account-lifecycle, persistence/collector, reducer/admin, API/frontend and deployability owners."
  ],
  "acceptance": [
    "Matrix marks fixed, configurable, unresolved and prohibited event/data-flow facts with no invented production default.",
    "Safe successor is pure and unpublished, accepts only injected finite machine catalogues and server-supplied authority/time/build/subject facts, and emits/stores nothing.",
    "Admin dimensions are structurally blind to subject/tenant/session/strategy/symbol/signal/PnL/position/credential/payment/free-text/raw transport facts and preserve a small-cell gate.",
    "Preference/consent, subject rotation, retention/delete/export/restore, collector/retry, external processors, admin publication and deployment remain exact later gates.",
    "Architecture validates with zero product/test/schema/frontend/external/deploy writes."
  ],
  "test_plan": ["Read-only producer/dependency/config/source inspection, policy matrix, collision check and architecture validator; contract tests belong to the successor."],
  "risk_classification": {"tier": "Important", "reason": "Even a first-party analytics shape can exfiltrate proprietary strategy, financial, credential or personal facts and later make admin ignorance false."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_product_analytics_policy_replan", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only analytics/privacy routing; any collector, persistence, admin or external processor successor receives Critical privacy review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-product-analytics-policy-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-product-analytics-policy-replan.md", ".agent/runs/strategy-os-v0-product-analytics-policy-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-product-analytics-policy-replan/decision.json", "verdicts": ["ARCHITECTURE", "PRIVACY"], "max_rechecks": 1},
  "owner_gates": ["No production purpose/event catalogue, preference/consent policy, subject lifetime, retention/export/delete/restore, small-cell threshold, external processor, collector, operator access, API/frontend or deployment without explicit owner/privacy/security authority."],
  "stop_conditions": ["A useful V0 contract requires arbitrary properties, raw URLs/bodies/headers, stable strategy/provider/payment identifiers, personal data, external SDK/destination or unapproved retention.", "Persistence/schema/shared API/frontend paths are not released."],
  "deployment_impact": {"classification": "none; read-only product analytics privacy replan", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "replan_result": {"verdict": "PRODUCT ANALYTICS PRIVACY REPLAN PASS", "decision": "KEEP FIRST-PARTY SERVER-AUTHORED ANALYTICS; DEFER COLLECTION AND PUBLICATION", "decision_sha256": "0183efb0a1e8acb3d5506f8f031a18cdc80897898c42848ed7b3b596e155e7ff", "policy_matrix_sha256": "3399a192d793beee18db1691307352c1aea4f77adde237e21ccf94471c3158ca", "inventory_sha256": "45c4bebaa79e29d4d88fcc199ac7ca67a213a71df8b2a7ceddc54128f8a25698", "successor_capsule_sha256": "f07eda715009e3fa8cf7529b4654f8d9e84cf772220b235668f5f2a9b7a4a3d2", "successor": "strategy-os-v0-product-analytics-contract-foundation", "product_writes": 0, "collector": false, "external_processor": false, "deployment": false},
  "nonclaims": ["No analytics event, preference, subject, store, collector, retry, export/delete, admin dashboard, SDK, external processor, API/frontend, deployment or V0 completion."
  ]
}
---

# Product analytics policy replan

Define useful platform analytics without creating a path for strategy, money,
credential, personal, raw transport or free-form data to reach an operator.

## Replan evidence receipt

No active product-analytics package, SDK, tag manager, browser auto-capture,
session replay, first-party product event store or admin analytics dashboard was
found. Existing execution analytics, the legacy P&L dashboard, unavailable
execution `/api/analytics`, and the arbitrary private outbox are rejected as
product-analytics sources. The pure successor may implement only the closed,
server-authored, non-emitting candidate language sealed in the decision.
