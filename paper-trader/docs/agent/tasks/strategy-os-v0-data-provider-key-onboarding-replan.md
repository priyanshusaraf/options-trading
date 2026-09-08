---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-data-provider-key-onboarding-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_provider_credential_onboarding_replan",
  "goal": "Split the blocked data-provider onboarding proposal into the largest safe V0 fake-provider implementation foundation and an exact external activation gate, preserving encrypted owner-scoped credentials and false-green readiness refusal.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write decision freezes local direct-V1 API, persistence/migration, Precision Slate flow, state/notification, privacy/tenant/deployability/ablation evidence and the exact vendor/data-rights activation boundary."},
  "risk_tags": ["critical", "provider", "credentials", "auth", "tenancy", "privacy", "migration", "frontend", "deployability"],
  "depends_on": ["strategy-os-v0-account-commerce-shared-assembly", "strategy-os-v0-data-only-connection-contract"],
  "dependency_gate": {"shared_package_sha256": "69015fd9169921f62d8823c6a41c0bd4622b6673124f241ff2b4401166b73d22", "shared_verdict_sha256": "44110aa6f5d2115835b4c00c803268bacfbed9af21b1364111953adcce6bd0d4", "provider_proposal_sha256": "02e375a4a7d7a145fd5288e4aead9d19b06538b425ed531dc54b71ff65fc5311", "policy": "Account publication paths are released. Real provider credentials/network/readiness/expiry and data-rights claims remain closed; plan a fake-provider local foundation separately from activation."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-account-commerce-shared-assembly-replan/provider-successor-capsule.md", "sections": ["all"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-data-only-connection-contract.md", "sections": ["goal", "scope", "acceptance", "review_result"]},
    {"path": "paper-trader/backend/app/providers/connection_store.py", "sections": ["DataOnlyConnection", "OwnedConnectionStore data-only methods", "credential and revocation semantics"]},
    {"path": "paper-trader/backend/app/api/connection_routes.py", "sections": ["data connection creation", "store_credential", "_start_oauth", "oauth_callback", "revoke_connection"]},
    {"path": "paper-trader/backend/app/core/release_profile.py", "sections": ["V0 provider capability and blocked state"]},
    {"path": "paper-trader/backend/app/db/models.py", "sections": ["BrokerConnection", "OAuthCallbackState"]},
    {"path": "paper-trader/backend/app/db/migrate.py", "sections": ["head and startup validation"]},
    {"path": "paper-trader/backend/AGENTS.md", "sections": ["Backend execution rules"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-data-provider-key-onboarding-replan.md", ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-data-provider-key-onboarding-replan.md", ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Inventory the accepted owner-scoped data-only connection, vault, OAuth state, principal, release-profile and frontend transport boundaries. Keep data provider and execution broker roles separate and execution/order/account/funds/positions/margin unreachable.",
    "Split local foundation from external activation. Local may publish direct-V1 owner-derived state/create/app-key/rotate/initiate/callback/revoke routes, a Precision Slate /account/provider workflow, encrypted persistence and fake-provider E2E. External activation retains real credentials/network, official response conformance, rights, expiry/quota/readiness and production publication gates.",
    "Verify whether one additive 0050 completion fact is the smallest way to distinguish consumed OAuth state from credential stored for the current browser session. Freeze expand/backfill/reader-writer/quiescence/rollback/restore behavior for SQLite and PostgreSQL 16 without inferring readiness from timestamps.",
    "Freeze stable app-key behavior: initial explicit write and Rotate keys only; ordinary reconnect retains encrypted api_key/api_secret while replacing session tokens; no secret readback, browser storage, logs, analytics, support, URL or exception disclosure.",
    "Freeze closed states CONNECTION_REQUIRED, APP_KEYS_REQUIRED, REAUTH_REQUIRED, SESSION_PRESENT_UNVERIFIED, REVOKED and UNAVAILABLE. credential_expiry/rate_quota stay UNVERIFIED and ready stays false until external evidence passes. Notifications are in-app and status-derived only.",
    "Define exact direct routes, CSRF/origin/session/tenant inputs, concurrent initiate/callback/rotate/revoke behavior, restart/failure semantics, poisoned execution dependencies and two-owner negative matrix.",
    "Freeze smallest serialized backend/migration/frontend paths, fake-provider tests, privacy/tenant/migration/deployability evidence, post-implementation ablations and one Critical review."
  ],
  "acceptance": [
    "Decision authorizes only the largest safe local foundation and names every real-provider/data-rights/readiness fact still blocked; no false provider-green state is possible.",
    "One direct-V1 route and UI state machine reuses the existing vault/store/principal authority with no mixed-role public surface or second credential store.",
    "If 0050 is required, migration shape and supported-state matrix are exact, additive and independently reviewable on SQLite/PostgreSQL 16; otherwise the decision proves an existing durable fact is sufficient.",
    "Secrets and owner facts have a complete privacy/retention/deletion/restart map; two-owner, revoked membership, stale session, collision/concurrency and poisoned execution cases are exact.",
    "Successor includes a named ablation for server-derived state/readiness refusal and secret-retention behavior, RED then exact restore GREEN, plus one Critical review and deployment obligations."
  ],
  "test_plan": ["Read-only route/store/vault/model/migration/frontend/deployment inventory; current-head and source-hash capture; fake-provider and failure-hypothesis matrix; seal exact local successor and external activation gate. No product implementation in this replan."],
  "risk_classification": {"tier": "Critical", "reason": "Credential storage, tenant ownership, OAuth completion and schema changes can expose secrets, cross users or falsely claim provider readiness."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_data_provider_key_onboarding_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-provider-onboarding-replan", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-data-provider-key-onboarding-replan.md", ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan"], "output": ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_data_provider_key_onboarding_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only Critical replan; implementation/migration successor receives independent Critical review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-data-provider-key-onboarding-replan.md", ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan/decision.json", "verdicts": ["LOCAL_FOUNDATION", "MIGRATION", "PROVIDER_TRUTH", "PRIVACY_TENANCY", "SUCCESSOR"], "max_rechecks": 0},
  "owner_gates": ["No product/schema/migration/frontend edit, real provider credential/network, provider/rights/readiness claim, execution/live/money, production data, commit, deploy or V0 completion claim."],
  "stop_conditions": ["A safe local foundation cannot be separated from real provider I/O or a legal/data-rights decision.", "Existing vault/store cannot retain stable app keys without a second secret authority or destructive migration.", "Shared accepted source receives concurrent ownership."],
  "deployment_impact": {"classification": "none for read-only replan; successor migration and shared HTTP/frontend changing", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No provider onboarding implementation, real provider conformance/rights, credential expiry/quota/readiness, external call, deployment, release readiness or V0 completion."],
  "result": {
    "verdict": "KEEP + HARDEN",
    "decision_path": ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan/decision.json",
    "decision_sha256": "01c4d612c47ca03561f55baa52e1a1af2325a90a967d07f8e48d20039d585995",
    "evidence_path": ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan/evidence.json",
    "evidence_sha256": "851e3a0b1370e0b827df5af096ba9ca41f6e3b691ffe444c57c2ebc79c68d389",
    "report_path": ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan/report.md",
    "report_sha256": "5c4bb5d484cf6752b0e6fb85e6a1abfaccc9b00c826dd557340d5c4269b0f455",
    "successor_path": ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan/local-foundation-successor.md",
    "successor_sha256": "f8f2f7f6aa056a04b9b66b0bbfc0c66361138f3be1e3115b20b6a2e3f9f53ab5",
    "replan_seal_path": ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan/replan-seal.json",
    "replan_seal_sha256": "bf8503a06b8537e2b0cc769a27069c0695b460bebfa53017ee83d832fddec1f4",
    "migration_fact": "credential_stored_at is required; 0050 is provisional on a fresh exact-0049 rebind",
    "owner_authorization_required": "AUTHORIZE V0 DATA-PROVIDER KEY ONBOARDING LOCAL FAKE-PROVIDER FOUNDATION",
    "local_provider": "fake_only_closed_default",
    "real_provider_activation": "CLOSED",
    "product_writes": 0,
    "deployment": false
  }
}
---

# Data-provider key onboarding replan

Build the safe encrypted local workflow and keep real provider activation behind
an explicit conformance, rights and owner gate.
