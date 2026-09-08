---
{
  "id": "strategy-os-v1-data-provider-rights-inventory",
  "source_thread_id": "01a04c7c-257a-7210-9dd3-f639c661db00",
  "phase": "v1-planning",
  "status": "complete",
  "kind": "read_only_provider_capability_and_rights_inventory",
  "goal": "Create an official-source inventory of candidate Indian market-data, reference/event, historical derivatives and execution products without selecting a provider or creating product authority.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Produce a role-separated report, official-source registry, capability matrix, conformance hypotheses, failure modes and open owner/legal questions; preserve every unresolved right as UNKNOWN; make no provider, licence, dependency, credential, network, schema, adapter, commercial or execution commitment; and require revalidation against future V0_FREEZE_SHA before any adoption work."
  },
  "risk_tags": ["important", "provider-boundary", "data-rights", "research-integrity", "future-execution"],
  "required_docs": [
    {"path": "paper-trader/docs/agent/CURRENT.md", "sections": ["Current resume state"]},
    {"path": ".agent/runs/strategy-os-v1-parallelization-audit/safe-now-capsule-queue.json", "sections": ["strategy-os-v1-data-provider-rights-inventory"]},
    {"path": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/report.md", "sections": ["Verdict", "Role-separated inventory", "Cross-provider findings", "Revalidation gate"]},
    {"path": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/source-registry.json", "sections": ["sources"]},
    {"path": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/capability-matrix.csv", "sections": ["all rows"]},
    {"path": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/conformance-hypotheses.md", "sections": ["Hypotheses", "Shared failure modes"]},
    {"path": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/open-owner-legal-questions.md", "sections": ["Owner decisions", "Legal and commercial questions"]}
  ],
  "dependency_gate": "The owner authorized public-document research only. V0_FREEZE_SHA is not yet available. No provider access, contract review, implementation or selection is authorized.",
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v1-data-provider-rights-inventory.md",
    ".agent/runs/strategy-os-v1-data-provider-rights-inventory"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v1-data-provider-rights-inventory.md",
    ".agent/runs/strategy-os-v1-data-provider-rights-inventory"
  ],
  "protected_paths": [
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/engineering/decisions",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Inventory current public documentation for Zerodha Kite Connect, DhanHQ, Upstox, NSE Data & Analytics and BSE Self Data Feed.",
    "Keep market data, fundamentals/reference/events, historical derivatives/options/OI/depth and execution broker roles distinct even when one company offers more than one role.",
    "Record products, documented windows and depth, point-in-time and correction fields, instrument identity, quotas, display/redistribution/retention/non-display constraints, service-change evidence, conformance hypotheses and failure modes.",
    "Use only official public pages and documents retrieved on 2026-08-29. Record absent or agreement-specific facts as UNKNOWN.",
    "Preserve Strategy OS canonical instrument authority. Provider identifiers remain aliases or transport identifiers and never enter canonical strategy identity."
  ],
  "acceptance": [
    "Every inventory row has exactly one provider and one role class.",
    "Zerodha and Dhan are covered, with Upstox, NSE Data & Analytics and BSE as credible alternatives without a ranking or selection claim.",
    "Each row identifies exact documented products, time/depth scope, identity fields, quota evidence, rights state, correction state, sources, hypotheses and failure modes.",
    "Public product documentation is not treated as a licence grant. UNKNOWN is preserved for missing rights, retention, correction lineage and service terms.",
    "The package contains no credentials, provider calls, SDK/dependency adoption, product code, schema change, commercial commitment, frontend change, live authority or deployment action.",
    "A future owner must supply V0_FREEZE_SHA and revalidate the frozen connection, capability, observation and canonical-instrument contracts before implementation planning."
  ],
  "test_plan": [
    "Validate source URLs against the official-domain allowlist and require a retrieval date and claim boundary for each source.",
    "Validate matrix role values, source references, UNKNOWN rights states and absence of provider-selection fields.",
    "Run scoped-diff, secret-pattern, product-code extension and protected-hash checks.",
    "Re-run the source review and architecture reconciliation after V0_FREEZE_SHA exists; public documentation may change before then."
  ],
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {
    "required": false,
    "assignment_id": "strategy_os_v1_data_provider_rights_inventory_owner",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/review-package.json",
    "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v1-data-provider-rights-inventory.md", ".agent/runs/strategy-os-v1-data-provider-rights-inventory"],
    "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
    "output": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/report.md",
    "verdicts": ["INVENTORY"]
  },
  "owner_gates": [
    "Owner approval is required before naming a preferred provider, buying a product, accepting terms, creating an account, supplying credentials, calling a provider endpoint, installing an SDK or dependency, or implementing an adapter.",
    "Legal or qualified commercial review is required before display, external distribution, redistribution, derived-data distribution, retention, non-display use, research sharing or audit-log policy is treated as permitted.",
    "Stop before live IR authority, live sizing/routing/risk/execution changes, licence-sensitive adoption, frontend implementation, credentials, provider networks, money or deployment."
  ],
  "stop_conditions": [
    "A conclusion requires a private agreement, entitlement, credential or provider call; record an open question instead.",
    "A provider transport identifier would become canonical strategy identity; reject the design and retain provider aliases behind canonical instruments.",
    "A market-data capability is used to infer execution capability, or execution availability is used to infer data rights; keep the facts separate.",
    "V0_FREEZE_SHA is absent or the frozen V0 contracts conflict with an inventory hypothesis; do not start adoption work."
  ],
  "deployment_impact": {"classification": "planning-only; no runtime, schema, dependency, service, credential, provider-call, live or deployment change"},
  "result": {
    "verdict": "INVENTORY COMPLETE; PROVIDER SELECTION AND RIGHTS CLEARANCE NOT CLAIMED",
    "retrieved_at": "2026-08-29",
    "research_base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "v0_freeze_sha": "V0_FREEZE_SHA_PENDING",
    "report": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/report.md",
    "source_registry": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/source-registry.json",
    "capability_matrix": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/capability-matrix.csv",
    "conformance_hypotheses": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/conformance-hypotheses.md",
    "open_questions": ".agent/runs/strategy-os-v1-data-provider-rights-inventory/open-owner-legal-questions.md",
    "protected_state": "Concurrent backend drift was detected after the baseline and recorded in owner/protected-hash-comparison-final.log; frontend, CURRENT, PROGRAMME and deploy hashes remained exact."
  },
  "nonclaims": [
    "No provider is supported, preferred, selected, approved, contracted or technically conformant.",
    "No public page proves display, redistribution, retention, derived-data, non-display or research-sharing permission unless the matrix names an explicit statement; UNKNOWN does not mean allowed.",
    "No provider identifier becomes part of canonical strategy, graph, research, deployment or execution identity.",
    "No adapter, schema, key, credential, provider call, SDK, dependency, account, entitlement, payment, commercial commitment, product code, frontend, live authority, order, money movement or deployment is created."
  ]
}
---

# Strategy OS V1 data-provider rights inventory

This capsule records public evidence and unresolved gates. It does not choose a provider or grant permission to use any data product.
