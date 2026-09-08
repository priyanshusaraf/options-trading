---
{
  "id": "strategy-os-v0-zerodha-data-account-bootstrap-correction",
  "lineage_id": "strategy-os-v0-provider-private-conformance-rights-and-runtime-policy",
  "programme_stage": "strategy-os-v0-monitoring-signals-review",
  "phase": "v0",
  "status": "correction_active_after_critical_unverifiable",
  "kind": "critical_provider_tenancy_lifecycle_correction",
  "goal": "Let a newly enrolled owner create the one Zerodha DATA connection without a pre-seeded broker-account row, while preserving owner isolation and granting no execution authority.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "A no-account owner sees CONNECTION_REQUIRED; the first create atomically materializes exactly one deterministic owner-scoped data-only account and one closed DATA connection; repeat, ambiguous, disabled and foreign-owner cases fail closed; no execution lease, deployment, credential, provider network or order authority is created; focused and affected tests, enrollment-to-provider browser evidence, isolated ablation, protected hashes, architecture and one independent Critical review pass."},
  "authorization_resolution": {"status": "EXPLICIT_OWNER_PROVIDER_DIRECTION", "evidence": "The owner required Zerodha as the first V0 data provider and a dedicated data-only account, then reported that access still did not work. The live isolated browser reproduced UNAVAILABLE because newly enrolled owners have no BrokerAccount row."},
  "risk_tags": ["critical", "provider", "zerodha", "tenancy", "account-lifecycle", "credential-boundary", "no-live", "deployment-impact"],
  "required_skills": ["strategyos-repo-orientation", "executing-strategy-os-slices", "provider-adapter-conformance", "tenant-isolation-audit", "risk-weighted-verification", "reviewing-strategy-os-critical-changes", "running-strategy-os-safely"],
  "depends_on": ["strategy-os-v0-provider-private-conformance-rights-and-runtime-policy"],
  "required_docs": [
    {"path": "paper-trader/docs/agent/CURRENT.md", "sections": ["v0_provider_private_conformance_readiness"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy.md", "sections": ["final_review", "owner_gates", "nonclaims"]},
    {"path": ".agent/runs/strategy-os-v0-builder-direct-manipulation-and-shell-utility-correction/browser-final-failure.json", "sections": ["Zerodha access could not be verified"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/app/providers/data_connection_service.py",
    "paper-trader/backend/app/providers/connection_store.py",
    "paper-trader/backend/tests/test_v0_data_connection_onboarding.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-zerodha-data-account-bootstrap-correction.md",
    ".agent/runs/strategy-os-v0-zerodha-data-account-bootstrap-correction"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-zerodha-data-account-bootstrap-correction.md",
    ".agent/runs/strategy-os-v0-zerodha-data-account-bootstrap-correction"
  ],
  "protected_paths": [
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/scripts/deploy.sh",
    "/Users/priyanshusaraf/dev/strategy-os-frontend"
  ],
  "scope": [
    "Change only the closed V0 data-connection service and its direct tests. Reuse BrokerAccount as the existing owner/account foreign-key anchor; do not add a schema, migration, general account factory or provider SDK dependency.",
    "Treat exactly zero owner-local Zerodha account rows as first-time setup. Status returns CONNECTION_REQUIRED without mutation. The explicit create request may add one deterministic owner-scoped, provider-unbound data-only account before creating the closed DATA connection in the same transaction. The generated account is disabled to every general execution seam and is admitted only by the exact DATA-role store constructor.",
    "Treat any disabled account, multiple accounts, conflicting connection or foreign-owner identifier as unavailable or conflict. Never select or mutate a foreign row.",
    "The data-only account is not a request, resolution or grant of execution authority. General connection creation, credential storage and live_connection remain unavailable on its DATA-role store. Create no AccountExecutionLease, Deployment, order, position, capital, credential, OAuth or provider-network fact.",
    "Preserve all accepted Zerodha OAuth, encryption, rate, capability, revocation and stable-refusal behavior. No live orders, production credential use, vendor conformance or data-rights claim."
  ],
  "acceptance": [
    "With an active owner session and no BrokerAccount row, GET status is 200 CONNECTION_REQUIRED with only create available. It performs no write.",
    "POST create from that state returns 201 APP_KEYS_REQUIRED and atomically persists one deterministic active owner-scoped Zerodha data-only BrokerAccount plus one active strategy-os-v0:data connection with only historical_data and live_quotes.",
    "The account carries an explicit provider-unbound data-only external identity, status disabled, and no credential. The normal execution-account resolver, lease claim, deployment-account predicate, PaperBroker construction and general live connection path all reject it, while an active normal account passes the positive controls.",
    "A repeat create conflicts. A disabled or ambiguous owner account fails closed. Two unrelated owners receive distinct account and connection rows; switching principals cannot read, alter or infer the other tenant's row.",
    "A forced derived-ID collision with a foreign owner, two simultaneous first-create requests, and a forced downstream connection failure all close generically. The foreign row is unchanged, the race leaves exactly one account/connection pair, and downstream failure leaves no orphan account.",
    "The prior seeded-account lifecycle, OAuth, rotation, revocation, restart and runtime tests remain green.",
    "ABL-DATA-ACCOUNT-BOOTSTRAP removes first-time account materialization; the exact no-account lifecycle test returns RED, exact bytes restore, and the test returns GREEN.",
    "One independent Critical reviewer returns SPEC PASS and QUALITY PASS against the sealed review package."
  ],
  "test_plan": [
    "Add RED HTTP tests for a newly enrolled-style owner with no broker account, status no-write, first create, repeat create, malformed/ambiguous state and two-tenant isolation.",
    "Assert exact persisted account/connection fields, disabled execution posture, generic connection-store refusal, normal execution-account positive controls, derived-ID collision, simultaneous first create, downstream rollback and absence of execution authority records. Run the full provider onboarding/runtime set and affected authentication/account tests.",
    "Run a safe enrollment-to-provider browser journey against temporary SQLite, mock/Paper, armed=false and no provider network. Run one isolated ablation and architecture validation.",
    "Seal an evidence-backed package and route exactly one Critical reviewer."
  ],
  "risk_classification": {"tier": "Critical", "reason": "The correction materializes a tenant-owned BrokerAccount foreign-key anchor adjacent to credential and execution domains; a wrong owner or implicit authority could expose credentials or create a live-account path."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {
    "required": true,
    "assignment_id": "v0_zerodha_data_account_bootstrap_critical_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-zerodha-data-account-bootstrap-correction/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/providers/data_connection_service.py",
      "paper-trader/backend/app/providers/connection_store.py",
      "paper-trader/backend/tests/test_v0_data_connection_onboarding.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-zerodha-data-account-bootstrap-correction.md",
      ".agent/runs/strategy-os-v0-zerodha-data-account-bootstrap-correction"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/db/models.py",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/frontend",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-zerodha-data-account-bootstrap-correction/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "Use synthetic owners and temporary databases only. Never use or print a real app key, secret, access token, provider account field or owner strategy.",
    "No provider network, live IR, execution account binding, order, money, deployment or schema change.",
    "Do not change BrokerAccount schema. The existing disabled status must remain the structural rejection used by general execution seams; only the exact DATA-role store may admit the provider-unbound sentinel."
  ],
  "stop_conditions": [
    "The existing disabled BrokerAccount cannot safely represent a provider-unbound DATA-only foreign-key anchor without a schema change.",
    "Any general execution resolver, lease, deployment, PaperBroker, connection or preflight test accepts the created row.",
    "The fix requires provider access, real credentials, a migration, live configuration or deployment."
  ],
  "deployment_impact": {"classification": "backend provider-account lifecycle correction", "schema_change": false, "migration_change": false, "dependency_change": false, "configuration_change": false, "runtime_wiring": true, "locally_runnable": true, "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No provider conformance, data rights, real credential acceptance, Paper rights, live authority, release deployability, deployment or V0 completion follows from this correction."]
}
---

# V0 Zerodha data-account bootstrap correction

Repair the first-time owner path that the live isolated browser exposed. The
account row exists only as the current schema's owner/account anchor for the
closed DATA connection. It must not become execution authority.
