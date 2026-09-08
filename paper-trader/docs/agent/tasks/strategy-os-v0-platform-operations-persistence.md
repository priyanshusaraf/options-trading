---
{
  "id": "strategy-os-v0-platform-operations-persistence",
  "phase": "v0",
  "status": "accepted_via_fresh_paper_guard_semantic_manifest_successor",
  "kind": "critical_platform_operations_schema_foundation",
  "implementation_receipt": {
    "owner_task": "/root/platform_operations_persistence",
    "source_head": "0045",
    "target_head": "0046",
    "operations_tables": 14,
    "sqlite_evidence": ".agent/runs/strategy-os-v0-platform-operations-persistence/v0_platform_operations_persistence_owner/operations-all-sqlite.log",
    "postgresql16_evidence": ".agent/runs/strategy-os-v0-platform-operations-persistence/v0_platform_operations_persistence_owner/postgres-sealed.log",
    "schema_regression_evidence": ".agent/runs/strategy-os-v0-platform-operations-persistence/v0_platform_operations_persistence_owner/schema-regression-final.log",
    "copy_restore_evidence": ".agent/runs/strategy-os-v0-platform-operations-persistence/v0_platform_operations_persistence_owner/copy-restore-contracts.log",
    "report": ".agent/runs/strategy-os-v0-platform-operations-persistence/report.md",
    "first_review_verdict_sha256": "822c7dbab2ad66b7dbf56e1fe9d3bd55b7e961e9214beadafd1b845291a6aa87",
    "correction_sqlite_evidence": ".agent/runs/strategy-os-v0-platform-operations-persistence/v0_platform_operations_persistence_owner/correction-operations-sqlite-all.log",
    "correction_postgresql16_evidence": ".agent/runs/strategy-os-v0-platform-operations-persistence/v0_platform_operations_persistence_owner/correction-postgres-focused-final.log",
    "correction_schema_regression": ".agent/runs/strategy-os-v0-platform-operations-persistence/v0_platform_operations_persistence_owner/correction-schema-regression.log",
    "correction_counterexamples": ".agent/runs/strategy-os-v0-platform-operations-persistence/v0_platform_operations_persistence_owner/correction-seven-counterexamples.log",
    "correction_complete": true,
    "final_reseal": {
      "reason": "Accepted v2 editor successor and control-document materialization after the correction seal",
      "package": ".agent/runs/strategy-os-v0-platform-operations-persistence/review-package-recheck-final-reseal.json",
      "root_receipt": ".agent/runs/root-v0-convergence/root/v2-editor-successor-materialized-platform-reseal.log",
      "platform_product_test_evidence_unchanged": true,
      "implementation_gates_rerun": false
    },
    "review_dispatched": false,
    "deployment": false
  },
  "successor_acceptance": {
    "capsule": "strategy-os-v0-paper-guard-semantic-manifest-correction",
    "review_package_sha256": "7ac09db69d51d73b12731c759de6abb5aa9210731f96e5e435661b8cb921feb4",
    "review_verdict_sha256": "a376e4bc90e7510b75a85f9546488977b6c2bc132d9b2953f1c577f361a4d509",
    "SPEC": "PASS",
    "QUALITY": "PASS",
    "closed_finding": "V0-POP-CR-003",
    "migration_head": "0046",
    "deployment": false
  },
  "goal": "Add the trusted platform billing, coupon/trial, entitlement, product-analytics, structured-support and operator-audit persistence foundation without strategy, research, broker-secret, position, balance or PnL access.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Exact additive migration, closed models/repositories, plane/copy/restore contracts and privacy/authority guards pass SQLite and PostgreSQL 16 fresh/0044-upgrade/restart/partial-refusal/restore/concurrency evidence. No Razorpay transport, entitlement policy effect, analytics producer, support API, operator auth, frontend or deployment change."
  },
  "risk_tags": [
    "critical",
    "schema",
    "migration",
    "billing",
    "entitlement",
    "privacy",
    "tenant-isolation",
    "operator-authority"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/strategy-os-v0-platform-operations-authority-rebase/report.md",
      "sections": ["Verdict", "Topology and authority decision", "Authority matrix", "Structural blindness contract", "Migration and recovery matrix", "Owner, legal, commercial and processor unknowns"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-correction/review/recheck-verdict.json",
      "sections": ["all output"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/architecture-decision.md",
      "sections": [
        "Billing and entitlement authority",
        "Privacy-safe operator administration",
        "Deployment architecture and evidence",
        "Architecture invariant matrix"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/data-flow-matrix.md",
      "sections": [
        "V0 data-flow and operator-visibility matrix",
        "Structural controls required",
        "Unresolved owner/counsel questions"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/agents/billing-admin-privacy/report.md",
      "sections": [
        "Controlling privacy boundary",
        "Existing seam inventory",
        "Critical invariants",
        "Candidate test matrix",
        "Disjoint implementation slices and dependency DAG"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/external-source-receipt.md",
      "sections": [
        "Razorpay Subscriptions",
        "Adoption decision"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "V1 release gate"
      ]
    }
  ],
  "dependency_gate": "strategy-os-v0-platform-operations-authority-rebase accepted and strategy-os-v0-paper-entry-lifecycle-identity-correction accepted at exact single head 0045",
  "stale_revision_reservation": {
    "status": "resolved_by_accepted_rebase",
    "reserved_revision": "0045",
    "active_owner": "strategy-os-v0-paper-charge-authority-and-legacy-identity-correction",
    "accepted_predecessor": "0045",
    "allocated_revision": "0046",
    "allocated_path": "paper-trader/backend/migrations/versions/20260830_0046_v0_platform_operations.py",
    "required_next_action": "Implement only the allocated linear 0046 over accepted 0045; any head/path collision stops and replans.",
    "source_audit_sha256": "4cabdfa7c850c2b8c240d7d49ac4d16ae9acb9537b675444225d5d2f045963e4"
  },
  "start_prerequisites": [
    "strategy-os-v0-monitoring-persistence accepted with migration 0044",
    "Paper entry lifecycle/charge authority 0045 is accepted through verdict SHA-256 531519fa266b1e2bf568461de3d96c360c5a7ef8ea9d0d582837693bf9ab289b and releases shared schema paths",
    "actual execution/user source head is exactly one accepted 0045 and revision/path 0046 is absent and unowned",
    "final pricing/tax/refund/retention values are not required for schema; unknown policy fields remain explicit and fail closed"
  ],
  "allowed_paths": [
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/app/db/planes.py",
    "paper-trader/backend/app/db/copy_contract.py",
    "paper-trader/backend/app/db/restore_contract.py",
    "paper-trader/backend/app/db/migrate.py",
    "paper-trader/backend/app/engine/broker.py",
    "paper-trader/backend/app/monitoring/repository.py",
    "paper-trader/backend/app/platform_operations/__init__.py",
    "paper-trader/backend/app/platform_operations/contracts.py",
    "paper-trader/backend/app/platform_operations/repository.py",
    "paper-trader/backend/migrations/versions/20260830_0046_v0_platform_operations.py",
    "paper-trader/backend/tests/test_v0_platform_operations_migration.py",
    "paper-trader/backend/tests/test_v0_platform_operations_persistence.py",
    "paper-trader/backend/tests/test_v0_platform_operations_privacy.py",
    "paper-trader/backend/tests/test_v0_monitoring_migration.py",
    "paper-trader/backend/tests/test_schema_migrations.py",
    "paper-trader/backend/tests/test_db_planes.py",
    "paper-trader/backend/tests/test_database_copy_contract.py",
    "paper-trader/backend/tests/test_postgresql_restore_contract.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-platform-operations-persistence.md",
    ".agent/runs/strategy-os-v0-platform-operations-persistence"
  ],
  "new_paths": [
    "paper-trader/backend/app/platform_operations/__init__.py",
    "paper-trader/backend/app/platform_operations/contracts.py",
    "paper-trader/backend/app/platform_operations/repository.py",
    "paper-trader/backend/migrations/versions/20260830_0046_v0_platform_operations.py",
    "paper-trader/backend/tests/test_v0_platform_operations_migration.py",
    "paper-trader/backend/tests/test_v0_platform_operations_persistence.py",
    "paper-trader/backend/tests/test_v0_platform_operations_privacy.py",
    ".agent/runs/strategy-os-v0-platform-operations-persistence"
  ],
  "protected_paths": [
    "paper-trader/backend/app/accounts",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/app/core/config.py",
    "paper-trader/backend/app/core/release_profile.py",
    "paper-trader/backend/app/core/credential_vault.py",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/backtest",
    "paper-trader/backend/app/engine/live_broker.py",
    "paper-trader/backend/app/engine/runner.py",
    "paper-trader/backend/app/engine/charges.py",
    "paper-trader/backend/app/engine/execution_lifecycle.py",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ledger",
    "paper-trader/backend/research",
    "paper-trader/backend/requirements.lock",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "schema_contract": {
    "plane": "USER",
    "tables": [
      "platform_plan_versions",
      "platform_coupon_definitions",
      "platform_coupon_redemptions",
      "platform_billing_bindings",
      "platform_billing_event_receipts",
      "platform_entitlement_events",
      "platform_current_entitlements",
      "platform_complimentary_entitlement_grants",
      "platform_analytics_subjects",
      "platform_analytics_events",
      "platform_support_requests",
      "platform_support_replies",
      "platform_operator_bindings",
      "platform_operator_audit_events"
    ],
    "forbidden_columns_or_content": [
      "strategy_id",
      "strategy_name",
      "graph_id",
      "graph_hash",
      "graph_body",
      "component_id",
      "parameters",
      "annotation",
      "dataset_id",
      "research_result",
      "signal_context",
      "instrument_symbol",
      "broker_account_id",
      "provider_account_id",
      "credential",
      "token",
      "position",
      "order",
      "balance",
      "capital",
      "pnl",
      "raw_request",
      "raw_response",
      "raw_webhook",
      "card",
      "upi",
      "free_text",
      "attachment"
    ]
  },
  "scope": [
    "Use the allocated additive migration 0046 over exact accepted 0045 only. A changed/branch head, existing 0046 file/revision or competing shared-schema owner stops before writes.",
    "Add one application migration-runner preflight: when build head is 0046, a populated managed database may advance only from exact 0045 or remain idempotently at 0046. Empty create_all/stamp remains supported; 0044/older/unknown/branch managed states refuse before Alembic upgrade so the accepted 0045 backup/quiescence boundary cannot be skipped.",
    "Advance Paper entry-lifecycle runtime marker compatibility only to the explicit closed set {0045, 0046}; require the complete accepted 0045 intent checks/triggers on both heads and refuse 0044, 0047, branch, multiple, unknown or drifted catalogs before Paper entry effects.",
    "Advance MonitoringRepository marker compatibility only to the explicit closed set {0044, 0045, 0046}; retain the complete accepted monitoring table/112-CHECK/trigger/relational manifest and refuse future/branch/multiple/unknown/drift before monitoring writes.",
    "Store immutable trusted plan versions with integer minor-unit amount, ISO currency, billing interval, entitlement-set address and optional mode-specific provider plan/offer IDs. No browser-supplied amount becomes durable authority.",
    "Store coupon definitions by secret-safe digest plus plan/version, trial/discount policy address, validity/use bounds and status. Redemption is unique per coupon/owner/policy and concurrency-safe.",
    "Store billing bindings and verified event receipts by owner, mode, merchant/integration address, provider customer/subscription/payment IDs, event type/state, exact raw-body digest and a closed allowlisted extracted-facts envelope. Do not store payment instruments or full raw payloads.",
    "Store append-only entitlement events separately from the rebuildable current-entitlement projection. No table/field/import links billing access to execution, capital, broker credentials or tenant strategy/research content.",
    "Product analytics subjects are random/pseudonymous and separately mapped under owner scope. Events use closed schema/version/type, bounded dimensions and no arbitrary property/context bag.",
    "Support requests use closed category/detail/status fields with no attachment, raw diagnostic or unrestricted user free text. Replies use closed response codes plus bounded operator-authored public copy if separately validated.",
    "Operator audit stores platform-operator subject, permission/action class, safe target class/redacted ID, outcome and time. Tenant Membership.admin is never accepted as operator identity.",
    "All repositories derive owner/operator identity server-side, bound list queries and return safe DTOs only. No admin projection is implemented in this capsule."
  ],
  "acceptance": [
    "Fresh SQLite and PostgreSQL 16 install and exact accepted 0045 upgrade reach 0046; repeated start is idempotent; stale/partial/unknown/branch head or schema drift refuses before writes.",
    "Application `upgrade_to_head` accepts exact 0045→0046 and 0046 idempotence, preserves empty create_all/stamp, and refuses managed 0044/older/unknown/branch states before applying any revision.",
    "Paper entry runtime opens on exact compatible heads 0045 and 0046 only when all accepted intent checks/triggers remain present; unlisted heads and drift refuse before money effects.",
    "MonitoringRepository opens on exact 0044/0045/0046 only with the complete accepted manifest; 0043/0047/future/branch/multiple/unknown/drift refuse before writes.",
    "Model/schema/index/check/unique/FK parity is exact. Cross-domain FKs/imports to strategy/research/money/provider credentials are absent; organization/owner references are by validated value.",
    "Interrupted migration and clean backup/restore verify heads, rows, PKs, content digests, sequences, coupon redemption, billing event dedupe, entitlement reconstruction and no session/entitlement resurrection.",
    "Concurrent coupon redemption, duplicate/reordered billing events, receipt-before-effect crash, stale entitlement event and projection rebuild are deterministic and cannot duplicate/regress access.",
    "Closed analytics/support/operator envelopes reject every forbidden sentinel before persistence and after copy/restore; one legitimate record per domain passes so universal denial cannot pass.",
    "Two unrelated owners, anonymous/revoked tenant and future operator placeholder cover repository IDOR, pagination/counts, export/delete markers and same-owner positive controls without strategy/research/money reads.",
    "Schema/AST/SQL-role design guards reject tenant Membership.admin as operator and forbid imports/queries/DTO fields from graph/research/engine/execution/ledger/provider credential modules.",
    "Resource bounds cover plan/coupon/event/analytics/support rows, event bodies, list limits, indexes, transactions, DB pools and retention assumptions for 5–15 users without production-capacity claim.",
    "One independent critical SPEC/QUALITY review passes the integrated migration/repository/privacy evidence."
  ],
  "test_plan": [
    "RED/GREEN closed contract/repository/dedup/concurrency/privacy tests, actual head query, SQLite and real disposable PG16 fresh/upgrade/interruption/restore.",
    "Copy/restore/plane/model guards, forbidden-sentinel matrix, isolated authority/privacy mutations and resource measurements.",
    "No Razorpay network/SDK, checkout, webhook route, entitlement API, analytics producer, support API, operator auth or frontend test in this schema capsule."
  ],
  "risk_classification": {
    "tier": "Critical",
    "reason": "Wrong payment/entitlement state can charge or deny access incorrectly, while an admin/analytics schema leak can expose proprietary tenant strategy or financial facts."
  },
  "parallel_budget": 1,
  "assignments": [{
    "id": "v0_platform_operations_persistence_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-product-test-schema-and-evidence", "depends_on": [],
    "write_paths": ["paper-trader/backend/app/db/models.py", "paper-trader/backend/app/db/planes.py", "paper-trader/backend/app/db/copy_contract.py", "paper-trader/backend/app/db/restore_contract.py", "paper-trader/backend/app/db/migrate.py", "paper-trader/backend/app/engine/broker.py", "paper-trader/backend/app/monitoring/repository.py", "paper-trader/backend/app/platform_operations/__init__.py", "paper-trader/backend/app/platform_operations/contracts.py", "paper-trader/backend/app/platform_operations/repository.py", "paper-trader/backend/migrations/versions/20260830_0046_v0_platform_operations.py", "paper-trader/backend/tests/test_v0_platform_operations_migration.py", "paper-trader/backend/tests/test_v0_platform_operations_persistence.py", "paper-trader/backend/tests/test_v0_platform_operations_privacy.py", "paper-trader/backend/tests/test_v0_monitoring_migration.py", "paper-trader/backend/tests/test_schema_migrations.py", "paper-trader/backend/tests/test_db_planes.py", "paper-trader/backend/tests/test_database_copy_contract.py", "paper-trader/backend/tests/test_postgresql_restore_contract.py", "paper-trader/docs/agent/tasks/strategy-os-v0-platform-operations-persistence.md", ".agent/runs/strategy-os-v0-platform-operations-persistence"],
    "output": ".agent/runs/strategy-os-v0-platform-operations-persistence/report.md"
  }],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "owner_task": "/root/platform_operations_persistence",
  "review": {
    "required": true,
    "assignment_id": "v0_platform_operations_persistence_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Shared payment/entitlement/privacy/operator schema and migration are Critical.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-platform-operations-persistence/review-package-recheck-final-reseal.json",
    "review_paths": ["paper-trader/backend/app/db/models.py", "paper-trader/backend/app/db/planes.py", "paper-trader/backend/app/db/copy_contract.py", "paper-trader/backend/app/db/restore_contract.py", "paper-trader/backend/app/db/migrate.py", "paper-trader/backend/app/engine/broker.py", "paper-trader/backend/app/monitoring/repository.py", "paper-trader/backend/app/platform_operations/__init__.py", "paper-trader/backend/app/platform_operations/contracts.py", "paper-trader/backend/app/platform_operations/repository.py", "paper-trader/backend/migrations/versions/20260830_0046_v0_platform_operations.py", "paper-trader/backend/tests/test_v0_platform_operations_migration.py", "paper-trader/backend/tests/test_v0_platform_operations_persistence.py", "paper-trader/backend/tests/test_v0_platform_operations_privacy.py", "paper-trader/backend/tests/test_v0_monitoring_migration.py", "paper-trader/backend/tests/test_schema_migrations.py", "paper-trader/backend/tests/test_db_planes.py", "paper-trader/backend/tests/test_database_copy_contract.py", "paper-trader/backend/tests/test_postgresql_restore_contract.py", "paper-trader/docs/agent/tasks/strategy-os-v0-platform-operations-persistence.md", ".agent/runs/strategy-os-v0-platform-operations-persistence"],
    "exclude_paths": [
      "paper-trader/backend/app/ir",
      "paper-trader/backend/app/engine/live_broker.py",
      "paper-trader/backend/app/engine/runner.py",
      "paper-trader/backend/app/engine/charges.py",
      "paper-trader/backend/app/engine/execution_lifecycle.py",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/research",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-platform-operations-persistence/review/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL / final FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-platform-operations-persistence/review/verdict.json",
    "verdict_sha256": "822c7dbab2ad66b7dbf56e1fe9d3bd55b7e961e9214beadafd1b845291a6aa87",
    "finding_ids": ["V0-POP-CR-001", "V0-POP-CR-002", "V0-POP-CR-003", "V0-POP-CR-004", "V0-POP-CR-005", "V0-POP-CR-006", "V0-POP-CR-007"],
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "Derive or exact-match entitlement code/action/policy/validity from the source grant/billing fact in reducers and persisted validation; source inversion or substitution refuses on SQLite and PostgreSQL.",
    "Make provider-event identity unique at merchant/integration/mode boundary, bind receipt to owner/mode/binding/customer/subscription facts, and require a distinct internal BillingVerifierAuthority for VERIFIED creation; TenantAuthority cannot assert verification.",
    "Replace Paper marker name checks with exact dialect-specific 0045 CHECK/trigger semantic manifests before 0046 migration and Paper effects; kill same-name no-op/altered-CHECK mutations on both dialects.",
    "Make founder identity/bootstrap evidence immutable and lifecycle changes append-only/unimplemented pending owner ceremony; add local grant/reply operator and owner/request constraints; narrow billing/support SQL roles to non-forgeable seams.",
    "Replace open support/reply/analytics codes with closed versioned allowlists, extend sensitive classes, and rescan every operations text field after copy/restore independently of triggers.",
    "Freeze explicit revision-owned 0046 DDL instead of importing current Base; prove future model mutation cannot change 0046 replay.",
    "Remove invented INR/USD durable allowlist and retain only ISO-shaped currency until owner policy exists.",
    "Add command/test identity logs, real PG concurrent coupon proof, clean-cluster role bootstrap/denial restore, and mutations for every review counterexample; reseal for the one focused recheck."
  ],
  "focused_recheck": {
    "verdict": "SPEC FAIL / QUALITY FAIL / final FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-platform-operations-persistence/review/recheck-verdict.json",
    "verdict_sha256": "8368bc6120eb23ae746d3f455d5cede3e59037e8e2841eaa9e37071af9cfe6",
    "closed_findings": ["V0-POP-CR-001", "V0-POP-CR-002", "V0-POP-CR-004", "V0-POP-CR-005", "V0-POP-CR-006", "V0-POP-CR-007"],
    "open_findings": ["V0-POP-CR-003"],
    "rechecks_remaining": 0,
    "next_state": "REPLAN_REQUIRED",
    "successor_replan": "strategy-os-v0-paper-guard-semantic-manifest-replan"
  },
  "owner_gates": [
    "Standing V0 authority permits the local additive migration after exact head/stable-input rebind and serial ownership. No repeated user token is required.",
    "Final pricing, tax, refund/cancellation/grace, retention, processor and legal policies remain external decisions; schema must represent unknown/unapproved policy without inventing defaults.",
    "No real payment/provider key, charge/refund, production database/data, destructive migration, deployment or live/order/money action."
  ],
  "stop_conditions": [
    "Source head is not exact accepted 0045, revision/path 0046 exists or has another owner, or the graph branches.",
    "A strategy/research/signal-context/provider-secret/position/balance/PnL/raw-payload/free-text field or cross-domain FK/import is required.",
    "The migration cannot be additive/restart-safe or old/new writers require destructive data rewrite.",
    "Coupon/billing/entitlement/event/analytics/support/audit identity cannot be made idempotent, owner/mode scoped and reconstructible without external provider calls."
  ],
  "deployment_impact": {
    "classification": "migration-required",
    "required_evidence": "Exact accepted 0045→0046/fresh PG16, least-privilege billing/analytics/operator roles, service consumers, secret/config inventory, retention/capacity, backup/restore and rollback/forward repair. No deployment claim."
  },
  "nonclaims": [
    "No Razorpay conformance, checkout/webhook, entitlement activation, product analytics collection, support messaging, operator login/admin UI, external processor, frontend, deployment or V0 completion.",
    "No legal compliance, anonymization or infrastructure zero-knowledge claim."
  ]
}
---

# V0 platform operations persistence

Create additive billing, entitlement, analytics, structured-support and operator-audit facts with structural strategy/research/money blindness.
