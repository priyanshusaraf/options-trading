---
{
  "id": "strategy-os-v0-monitoring-signals-review",
  "lineage_id": "strategy-os-v0-provider-private-conformance-readiness-packet",
  "programme_stage": "strategy-os-v0-monitoring-signals-review",
  "phase": "v0",
  "status": "paused_owner_gate",
  "kind": "read_only_external_provider_gate_readiness_packet",
  "goal": "Prepare the exact owner, provider, rights, credential-handling and conformance evidence required to open the real V0 data-only provider gate without receiving secrets, contacting a provider or changing product code.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "The current local provider and monitoring foundations are bound by hash, required owner decisions and secret ingress are explicit, the conformance matrix has pass/fail evidence targets, unsupported options-history claims remain refused, resume and stop conditions are exact, product bytes remain unchanged, and architecture passes."},
  "observable_outcome": "When the owner selects and authorizes the first V0 data provider, the conformance task can start without another scope discovery pass. Until then, provider readiness, monitoring worker, public monitoring and frontend integration remain false.",
  "risk_tags": ["critical", "provider", "credentials", "data-rights", "privacy", "tenant-isolation", "market-truth", "availability", "resource-limits", "external-gate"],
  "required_skills": ["strategyos-repo-orientation", "provider-adapter-conformance", "provider-change-impact-review", "privacy-data-flow-review", "tenant-isolation-audit", "anti-lookahead-and-market-truth", "resource-plan-and-cost-audit", "risk-weighted-verification"],
  "depends_on": ["strategy-os-v0-monitoring-signals-local-integration-correction", "strategy-os-v0-data-provider-key-onboarding-local-foundation"],
  "dependency_gate": {"monitoring_local_closure_sha256": "368bb6934d27caf1057662feeab15d7ed9e668bb3cb3fe51afc162903f08b538", "provider_local_foundation_recheck_sha256": "86e103fcf6503093db8d814c3f42ee43fe85763170e157656895931798e3c717", "monitoring_publication_decision_sha256": "62c6316fd9f9a4acf4cfae9bea92925266c492ecf9b2d4eb1eb5873b41851cbe", "execution_head": "0051", "research_head": "0011", "external_gate_status": "NOT_AUTHORIZED"},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-data-provider-key-onboarding-replan/decision.json", "sections": ["external_activation_gate"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-data-provider-key-onboarding-local-foundation.md", "sections": ["external_successor", "nonclaims", "implementation"]},
    {"path": ".agent/runs/strategy-os-v0-monitoring-publication-readiness-replan/decision.json", "sections": ["external_gate", "serialization"]},
    {"path": ".agent/runs/strategy-os-v0-monitoring-signals-local-integration-correction/closure-seal.json", "sections": ["external_gate", "local_alerts_paper_both_integration"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-provider-private-conformance-readiness-packet.md", ".agent/runs/strategy-os-v0-provider-private-conformance-readiness-packet"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-provider-private-conformance-readiness-packet.md", ".agent/runs/strategy-os-v0-provider-private-conformance-readiness-packet"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
  "acceptance": [
    "The packet fixes the current local provider contract to ZERODHA/DATA. Choosing another first provider requires a separate provider-change architecture decision rather than silent substitution.",
    "The owner must authorize a dedicated provider app/account for data-only conformance, redacted capture of private responses, and the exact beta collection/display/storage/derived-use purpose. No chat, repository, log, screenshot or evidence artifact accepts a secret value.",
    "The existing encrypted vault and browser callback are the only secret ingress. The packet requires api_key/api_secret entry through the authenticated Account screen, provider-hosted login, server callback exchange, secret rotation and revocation. It accepts no localStorage or client-returned secret.",
    "The conformance matrix requires direct evidence for authentication success/failure, session expiry/revocation, reconnect, timeout, 429/quota behavior, provider outage, stale data, duplicate callback, restart, account switching and concurrent rotation.",
    "Market-data evidence covers only the exact V0 underlying candle and LTP offer needed for monitoring and Paper. Instrument identity, exchange/event/availability time, sessions, freshness, gaps, missing data and causal completed-bar behavior are retained. Options-history, order-flow/depth history and unsupported instruments remain typed unavailable.",
    "Provider responses are mapped at the adapter boundary and never contain strategy, graph, SL/TP, alert, paper position, trade, PnL, review note or operator context. Captures use synthetic sentinel account values and a redacted local sink.",
    "Observed quota and recovery results produce a bounded runtime policy. Unknown or unobserved behavior remains UNKNOWN and blocks readiness. No provider switching, stale fallback or dropped required evaluation is inferred.",
    "Written owner/vendor/legal disposition covers app registration authority and collection, display, storage, derived use, retention and redistribution for the intended private beta. This packet makes no legal conclusion.",
    "Gate PASS requires one Critical provider-conformance review. Only then may strategy-os-v0-monitoring-worker-assignment-activation-replan start. Failure leaves local research, builder and paper simulation available while real monitoring stays blocked.",
    "No credential use, provider network, private response capture, SDK exchange, product/test change, worker, public API, frontend integration, live order, deployment or V0 completion occurs in this readiness packet."
  ],
  "test_plan": ["Recompute the named accepted hashes and architecture only. Review the packet for secret-free fields, closed decisions, evidence targets, typed nonclaims and exact successor order. No provider or product test runs are authorized."],
  "risk_classification": {"tier": "Critical", "reason": "Wrong provider authority, rights, expiry, quota or market-time claims could expose secrets, misstate monitoring readiness or produce false signals."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_provider_private_conformance_readiness_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-provider-private-conformance-readiness-packet/review-package.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-provider-private-conformance-readiness-packet.md", ".agent/runs/strategy-os-v0-provider-private-conformance-readiness-packet"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts"], "output": ".agent/runs/strategy-os-v0-provider-private-conformance-readiness-packet/report.md", "verdicts": ["READINESS"], "max_rechecks": 0},
  "owner_gates": ["Do not enter provider secrets in chat, shell arguments, repository files, evidence, logs or screenshots.", "Do not contact a provider, create an app, exchange a token, capture a private response or decide data rights without explicit owner authority.", "Do not start the monitor worker, register public routes, enable the release manifest, integrate the frontend or deploy before provider Critical acceptance."],
  "stop_conditions": ["The owner has not selected ZERODHA as the first V0 data provider or requests another provider.", "Dedicated data-only app/account authority or private-response capture permission is absent.", "Data-right, retention or redistribution disposition is unresolved.", "Any required evidence would place a secret or private account value in an artifact."],
  "deployment_impact": {"classification": "read-only external-gate readiness packet", "schema_change": false, "configuration_change": false, "runtime_wiring": false, "locally_testable": false, "locally_runnable_product": false, "release_deployable": false, "production_rehearsed": false, "deployed": false, "successor_after_gate": "strategy-os-v0-monitoring-worker-assignment-activation-replan"},
  "nonclaims": ["No provider selection by default beyond the current accepted ZERODHA/DATA contract, credential, provider conformance, rights, expiry, quota, readiness, monitoring worker, public API, frontend integration, live execution, release deployability, deployment or V0 completion."]
}
---

# Provider private-conformance readiness packet

This packet contains no secrets and performs no provider operation. It defines
the evidence and owner decisions required before real V0 monitoring can start.
