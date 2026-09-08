---
{
  "id": "strategy-os-v0-monitoring-signals-review",
  "lineage_id": "strategy-os-v0-provider-private-conformance-rights-and-runtime-policy",
  "programme_stage": "strategy-os-v0-monitoring-signals-review",
  "phase": "v0",
  "status": "accepted_offline_external_gate",
  "kind": "critical_zerodha_data_only_runtime_and_private_conformance",
  "goal": "Implement and independently verify the first V0 Zerodha data-only authentication and runtime boundary, record the exact official data-use constraints, and prepare a privacy-safe private conformance run without enabling any provider order route or using Zerodha live data for paper trading.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Production OAuth is available only through the existing owner-scoped encrypted vault; the dedicated data client cannot reach account, portfolio, order or mutation endpoints; expiry, revocation, 429 and outage outcomes are typed; response-shape evidence is secret-free; underlying candle and LTP behavior has offline and private evidence; unsupported historical options behavior remains refused; official Zerodha and NSE use restrictions are explicit; all declared tests, ablations and one Critical review pass, or the task stops with an exact external gate."},
  "authorization_resolution": {
    "status": "OWNER_AUTHORIZED_PROVIDER_SELECTED_PRIVATE_TEST_ALLOWED",
    "recorded_at": "2026-09-04",
    "owner_direction": "Zerodha is the first V0 data provider. A dedicated data-only account may be tested. Privacy-safe private response capture and the remaining requested owner-side controls are approved.",
    "bounded_scope": "Data-only login, market-data conformance and private redacted evidence. No order execution, live authority, production deployment or secret transfer through chat, shell arguments, files, logs, analytics or screenshots.",
    "external_rights_nonclaim": "Owner approval does not replace Zerodha or NSE permission. Official restrictions are a separate acceptance fact."
  },
  "risk_tags": ["critical", "provider", "credentials", "data-rights", "privacy", "tenant-isolation", "market-truth", "availability", "resource-limits", "external-gate", "deployability"],
  "required_skills": ["strategyos-repo-orientation", "provider-adapter-conformance", "provider-change-impact-review", "privacy-data-flow-review", "tenant-isolation-audit", "anti-lookahead-and-market-truth", "resource-plan-and-cost-audit", "auditing-strategy-os-deployability", "risk-weighted-verification"],
  "depends_on": ["strategy-os-v0-provider-private-conformance-readiness-packet", "strategy-os-v0-monitoring-signals-local-integration-correction", "strategy-os-v0-data-provider-key-onboarding-local-foundation"],
  "dependency_gate": {"readiness_decision_sha256": "51f6891339b60432ad597828b7f463f37580f7ba4077cf9f8474f4e32c28b888", "monitoring_local_closure_sha256": "368bb6934d27caf1057662feeab15d7ed9e668bb3cb3fe51afc162903f08b538", "provider_local_foundation_recheck_sha256": "86e103fcf6503093db8d814c3f42ee43fe85763170e157656895931798e3c717", "owner_gate": "AUTHORIZED", "provider": "ZERODHA", "role": "DATA", "credentials_present": false, "private_network_run": false},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-provider-private-conformance-readiness-packet/decision.json", "sections": ["secret_ingress", "conformance_evidence", "v0_typed_unavailable", "pass_gate"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-data-provider-key-onboarding-local-foundation.md", "sections": ["authorization_resolution", "scope", "acceptance", "external_successor", "nonclaims"]},
    {"path": "paper-trader/backend/app/providers/connection_store.py", "sections": ["DataOnlyConnection", "OwnedConnectionStore data-only methods", "revocation"]},
    {"path": "paper-trader/backend/app/providers/data_connection_service.py", "sections": ["production_data_authenticator", "status", "initiate", "complete"]},
    {"path": "paper-trader/backend/app/providers/broker_auth.py", "sections": ["KiteAuthenticator"]},
    {"path": "paper-trader/backend/app/providers/safe_kite.py", "sections": ["SafePaperKite", "transport allowlist"]},
    {"path": "paper-trader/backend/app/market_data/kite_observations.py", "sections": ["map_historical_candles", "map_quote_snapshot", "map_instrument_dump"]},
    {"path": "paper-trader/backend/app/market_data/capability.py", "sections": ["ProviderConformance"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/app/providers/data_connection_service.py",
    "paper-trader/backend/app/providers/connection_store.py",
    "paper-trader/backend/app/providers/broker_auth.py",
    "paper-trader/backend/app/providers/safe_kite.py",
    "paper-trader/backend/app/providers/kite.py",
    "paper-trader/backend/app/providers/zerodha_data_runtime.py",
    "paper-trader/backend/app/api/data_connection_routes.py",
    "paper-trader/backend/tests/test_v0_data_connection_onboarding.py",
    "paper-trader/backend/tests/test_v0_zerodha_data_runtime.py",
    "paper-trader/backend/tests/test_v0_kite_observations.py",
    "paper-trader/backend/tests/test_connection_store.py",
    "paper-trader/backend/tests/test_connection_routes.py",
    "paper-trader/backend/tests/test_safe_kite_construction_invariant.py",
    "paper-trader/backend/tests/test_safety.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy.md",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy"
  ],
  "new_paths": [
    "paper-trader/backend/app/providers/zerodha_data_runtime.py",
    "paper-trader/backend/tests/test_v0_zerodha_data_runtime.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy.md",
    ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy"
  ],
  "protected_paths": [
    "paper-trader/backend/app/core/credential_vault.py",
    "paper-trader/backend/app/providers/brokers.py",
    "paper-trader/backend/app/market_data/capability.py",
    "paper-trader/backend/app/market_data/authority.py",
    "paper-trader/backend/app/market_data/kite_observations.py",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ledger",
    "paper-trader/backend/app/monitoring",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/migrations",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Activate the production Zerodha login factory only through the existing server-side BrokerSpec/KiteAuthenticator and owner-scoped encrypted connection vault. Keep OAuth state single-use, current-session-bound and non-renderable.",
    "Add a distinct Zerodha data client or equivalent closed construction path whose transport permits only authentication, instrument, quote/LTP/OHLC and historical-data endpoints required by this capsule. It must deny profile, funds, positions, holdings, orders, trades, margins, GTT and every mutation or unknown route before network access.",
    "Eliminate process-global access_token.json and process-wide key fallback from the direct-V1 data connection path. Each invocation late-reads the current owner connection and cannot expose the provider object or wire client.",
    "Classify TokenException/403 as REAUTH_REQUIRED and atomically remove only the failed access token while retaining stable app keys. A concurrent rotation or newer callback must not be overwritten. Classify 429, timeout, 502, 503 and 504 without falsely expiring the token.",
    "Bind the official documented request rates: quote at no more than one request per second and historical candles at no more than three requests per second. Unknown limits remain UNKNOWN and block claims beyond the tested workload.",
    "Keep response capture in memory for mapping. Durable evidence may contain endpoint class, HTTP/error class, timing, byte/row counts, closed key/type summaries and content addresses only; it must reject credential, user/account, strategy, graph, alert, paper position, trade, PnL and review-note fields.",
    "Prove only underlying candle and LTP candidates for V0 monitoring. Current option-chain use may remain unavailable until directly proven. Historical options depth, expired option-token recovery, options order flow and options backtests remain typed unavailable; current futures continuous history must not be generalized to options.",
    "Record the official Zerodha and NSE restrictions. Zerodha live data must not feed V0 paper trading unless written provider permission or a separate licensed data source explicitly permits that use. Public redistribution is forbidden. Owner-private alert display/storage/derived use remains conditional on the applicable agreement.",
    "Prepare, but do not fake, one private conformance run. It may start only after the owner enters credentials through the authenticated Account screen. The run stores no secret or account value and makes no order/account/portfolio request."
  ],
  "acceptance": [
    "The normal V0 OAuth initiate route returns a Zerodha provider-hosted login URL after encrypted app-key setup; no production dependency override is required and no network call occurs during URL construction.",
    "The callback exchanges a one-time token through the data-only transport, persists the bundle only in the encrypted owner-scoped vault, and never returns or logs any credential or provider account field.",
    "The data-only client has a closed allowlist and direct tests prove that account, portfolio, order, GTT, margin, mutation and unknown routes fail before transport.",
    "A 403/TokenException changes the affected owner connection to REAUTH_REQUIRED while retaining app keys. A newer token written concurrently survives. A 429 or provider outage remains a transient typed state and does not erase valid credentials.",
    "Two owners, stale sessions, removed membership, revoked connection, duplicate callback, restart, concurrent rotation and vault failure remain isolated and fail closed.",
    "Offline official-shape fixtures prove candle/LTP mapping, completed-bar causality, missing/gap/stale behavior, instrument identity and sensitive pre-raw refusal. The private run must confirm the actual response shape before ready=true or worker activation.",
    "The runtime policy respects official request rates and contains bounded backoff, no provider substitution and no stale-value fallback that can create a signal.",
    "The terms assessment cites official Zerodha and NSE sources, distinguishes private display from public redistribution and paper trading, and marks every unresolved contractual fact as BLOCKED_EXTERNAL rather than PASS.",
    "One independent Critical SPEC PASS and QUALITY PASS is required after offline implementation and, for the final provider-ready claim, after the private run. A review may pass the implementation while leaving provider_ready=false if credentials or written rights are absent.",
    "No schema/migration, frontend, monitoring worker, public monitoring API, Paper runtime wiring, live order, deployment or V0-complete claim is introduced by this capsule."
  ],
  "test_plan": [
    "Write RED then GREEN tests for production authenticator construction, strict route allowlisting, no token-file/process-key fallback, owner isolation, callback privacy, token-expiry invalidation, concurrent rotation fencing, 429/outage preservation and runtime bounds.",
    "Run the existing data-onboarding, connection-store, broker-auth, safety, no-live, privacy/log and Kite observation tests. Run architecture validation and compare protected hashes.",
    "Run isolated ablations that admit an account route, omit token invalidation, erase concurrent-token fencing, retain an access token in an evidence summary and lower the quote interval below one second. Each must turn an exact test RED, then restore identical production bytes and GREEN.",
    "When credentials exist, run one private conformance session through the authenticated server flow. Persist only sanitized summaries and direct mapping outcomes. Do not place orders or call account/portfolio endpoints."
  ],
  "risk_classification": {"tier": "Critical", "reason": "This slice crosses real provider authentication, tenant secrets, market-time truth, external data-use restrictions and the signal input boundary."},
  "parallel_budget": 3,
  "assignments": [
    {
      "id": "v0_zerodha_data_runtime_owner",
      "agent": "worker",
      "model": "gpt-5.6-sol",
      "reasoning_effort": "medium",
      "fork_turns": "none",
      "mode": "implementation",
      "depends_on": [],
      "write_paths": [
        "paper-trader/backend/app/providers/data_connection_service.py",
        "paper-trader/backend/app/providers/connection_store.py",
        "paper-trader/backend/app/providers/broker_auth.py",
        "paper-trader/backend/app/providers/safe_kite.py",
        "paper-trader/backend/app/providers/kite.py",
        "paper-trader/backend/app/providers/zerodha_data_runtime.py",
        "paper-trader/backend/app/api/data_connection_routes.py",
        "paper-trader/backend/tests/test_v0_data_connection_onboarding.py",
        "paper-trader/backend/tests/test_v0_zerodha_data_runtime.py",
        "paper-trader/backend/tests/test_v0_kite_observations.py",
        "paper-trader/backend/tests/test_connection_store.py",
        "paper-trader/backend/tests/test_connection_routes.py",
        "paper-trader/backend/tests/test_safe_kite_construction_invariant.py",
        "paper-trader/backend/tests/test_safety.py",
        ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy/runtime"
      ],
      "output": ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy/runtime/report.md"
    },
    {
      "id": "v0_zerodha_data_terms_owner",
      "agent": "worker",
      "model": "gpt-5.6-sol",
      "reasoning_effort": "medium",
      "fork_turns": "none",
      "mode": "read_only_official_source_assessment",
      "depends_on": [],
      "write_paths": [
        ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy/terms"
      ],
      "output": ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy/terms/assessment.json"
    },
    {
      "id": "v0_zerodha_data_runtime_review_correction",
      "agent": "worker",
      "model": "gpt-5.6-sol",
      "reasoning_effort": "medium",
      "fork_turns": "none",
      "mode": "focused_review_correction",
      "depends_on": ["v0_zerodha_data_runtime_critical_review"],
      "write_paths": [
        "paper-trader/backend/app/providers/data_connection_service.py",
        "paper-trader/backend/app/providers/zerodha_data_runtime.py",
        "paper-trader/backend/tests/test_v0_data_connection_onboarding.py",
        "paper-trader/backend/tests/test_v0_zerodha_data_runtime.py",
        ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy/correction"
      ],
      "output": ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy/correction/report.md"
    }
  ],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "path": ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy/review/verdict.json",
    "sha256": "364ad546a4faab92ccd82475ce33dbd72b4bdc8fb2e914c0c2b2eb4fe142bafa",
    "open_findings": ["V0-ZDR-CR-001", "V0-ZDR-CR-002", "V0-ZDR-CR-003"],
    "rechecks_used": 0,
    "rechecks_remaining": 1,
    "provider_ready": false,
    "deployment": false
  },
  "final_review": {
    "verdict": "SPEC PASS / QUALITY PASS",
    "path": ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy/review/recheck-verdict.json",
    "sha256": "f95fbffe377f0e679a864c9d78f7b337b677137c37bc15156715bad7a11f1bc3",
    "closed_findings": ["V0-ZDR-CR-001", "V0-ZDR-CR-002", "V0-ZDR-CR-003"],
    "open_findings": [],
    "focused_tests": 46,
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "offline_implementation_accepted": true,
    "provider_ready": false,
    "private_conformance_run": false,
    "rights_clearance": false,
    "worker_activation": false,
    "deployment": false
  },
  "review": {
    "required": true,
    "assignment_id": "v0_zerodha_data_runtime_critical_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Real provider credentials, tenant isolation, data rights, market truth and signal availability are Critical boundaries.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/providers/data_connection_service.py",
      "paper-trader/backend/app/providers/connection_store.py",
      "paper-trader/backend/app/providers/broker_auth.py",
      "paper-trader/backend/app/providers/safe_kite.py",
      "paper-trader/backend/app/providers/kite.py",
      "paper-trader/backend/app/providers/zerodha_data_runtime.py",
      "paper-trader/backend/app/api/data_connection_routes.py",
      "paper-trader/backend/tests/test_v0_data_connection_onboarding.py",
      "paper-trader/backend/tests/test_v0_zerodha_data_runtime.py",
      "paper-trader/backend/tests/test_v0_kite_observations.py",
      "paper-trader/backend/tests/test_connection_store.py",
      "paper-trader/backend/tests/test_connection_routes.py",
      "paper-trader/backend/tests/test_safe_kite_construction_invariant.py",
      "paper-trader/backend/tests/test_safety.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy.md",
      ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/core/credential_vault.py",
      "paper-trader/backend/app/providers/brokers.py",
      "paper-trader/backend/app/market_data",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/app/ledger",
      "paper-trader/backend/app/monitoring",
      "paper-trader/backend/app/db/models.py",
      "paper-trader/backend/migrations",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json"
    ],
    "output": ".agent/runs/strategy-os-v0-provider-private-conformance-rights-and-runtime-policy/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "Do not accept a credential through chat, a shell argument, an environment dump, a repository file, a test fixture, a log, analytics, a screenshot or browser storage. The existing authenticated Account screen and encrypted server vault are the only ingress.",
    "Do not call any Zerodha account, portfolio, order, GTT, margin or mutation endpoint. Do not enable live order authority or deploy.",
    "Do not route Zerodha live data into paper trading while the official virtual/mock-trading restriction lacks written provider permission. Uploaded or licensed replay data may continue to serve Paper independently.",
    "Do not set ready=true, start the monitor worker or publish monitoring until the private response run and Critical review close the applicable facts."
  ],
  "stop_conditions": [
    "A dedicated data-only boundary cannot be constructed without an object or route that can access account or order APIs.",
    "Correct session-expiry handling requires storing a secret or account value outside the accepted vault.",
    "The private conformance run requires credentials outside the authenticated Account flow.",
    "Zerodha or NSE terms prohibit the intended private alert use, or written permission is required and absent.",
    "A schema migration, new dependency, frontend change, monitoring worker activation, Paper wiring, live execution or deployment is required."
  ],
  "deployment_impact": {"classification": "production authentication and provider-runtime behavior without schema change", "configuration_change": false, "dependency_change": false, "schema_change": false, "runtime_wiring": true, "locally_runnable_gate": "mock/paper safe runtime plus encrypted vault configuration and no provider network", "release_deployable": false, "production_rehearsed": false, "deployed": false, "external_inputs_remaining": ["owner-entered Zerodha app credentials through Account UI", "private conformance response", "applicable written data-use permission for paper use"]},
  "nonclaims": ["No provider-ready, options-history, options-backtest, worker, public monitoring, frontend monitoring, Zerodha-powered paper trading, live order, release-deployable, production-rehearsed, deployed or V0-complete claim follows until the named evidence exists."]
}
---

# V0 Zerodha data-only conformance and runtime policy

This slice turns the owner’s provider choice into a closed data-only runtime.
It keeps provider authentication and market data separate from order execution.
It also records the official restriction that prevents Zerodha live data from
feeding Paper until written permission or a separately licensed source exists.
