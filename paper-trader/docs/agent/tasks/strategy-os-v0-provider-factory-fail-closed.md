---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-provider-factory-fail-closed",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_provider_configuration_fail_closed_correction",
  "goal": "Make the process-wide provider factory reject unknown or V0-unopened provider configuration instead of silently returning Mock synthetic data.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Unknown, empty and V0-unopened configured provider names raise the typed UnknownProvider before any Mock or real adapter construction; explicit mock/replay/upstox/kite retain existing behavior; focused and affected provider/configuration tests, an isolated fallback mutation and one independent Critical SPEC/QUALITY review pass."
  },
  "risk_tags": ["critical", "provider-adapter", "configuration", "false-market", "paper-live-separation"],
  "depends_on": ["strategy-os-v0-data-only-connection-contract"],
  "dependency_gate": {
    "queue": ".agent/runs/strategy-os-v0-launch-convergence/capsule-queue.json",
    "queue_id": "strategy-os-v0-provider-factory-fail-closed",
    "accepted_static_observation_successor_verdict_sha256": "aeb7949cbc50c31b2e87cfb6124f66a37c4e9520a67729023be04b222e835629"
  },
  "required_docs": [
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/capsule-queue.json",
      "sections": ["strategy-os-v0-provider-factory-fail-closed"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/strategy-os-v0-data-only-connection-contract.md",
      "sections": ["acceptance", "nonclaims"]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md",
      "sections": ["8. Live versus historical capability", "14. Provider capability changes"]
    }
  ],
  "allowed_paths": [
    "paper-trader/backend/app/providers/factory.py",
    "paper-trader/backend/tests/test_v0_provider_factory.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-provider-factory-fail-closed.md",
    ".agent/runs/strategy-os-v0-provider-factory-fail-closed"
  ],
  "new_paths": [
    "paper-trader/backend/tests/test_v0_provider_factory.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-provider-factory-fail-closed.md",
    ".agent/runs/strategy-os-v0-provider-factory-fail-closed"
  ],
  "protected_paths": [
    "paper-trader/backend/app/core/config.py",
    "paper-trader/backend/app/providers/base.py",
    "paper-trader/backend/app/providers/brokers.py",
    "paper-trader/backend/app/providers/connection.py",
    "paper-trader/backend/app/providers/connection_store.py",
    "paper-trader/backend/app/providers/mock.py",
    "paper-trader/backend/app/providers/replay.py",
    "paper-trader/backend/app/providers/kite.py",
    "paper-trader/backend/app/providers/upstox.py",
    "paper-trader/backend/app/providers/dhan.py",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ledger",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Normalize the configured provider name once and construct only the explicitly supported process-wide names mock, replay, upstox and kite.",
    "Reject empty, unknown and V0-unopened names before importing or constructing MockProvider or any real adapter. A typo must never create a synthetic market.",
    "Keep `provider_named`'s existing explicit registry behavior unchanged; this capsule only closes the process configuration fallback in `get_provider`.",
    "Dhan remains outside the V0 process-wide configured provider path in this slice. Existing legacy adapter/registry code is protected and no data capability is opened.",
    "Preserve singleton reuse, explicit mock/replay/upstox/kite logging and zero provider network during tests."
  ],
  "acceptance": [
    "Unknown, whitespace-only and Dhan configured names raise UnknownProvider and construct neither Mock nor a real adapter.",
    "Explicit mock returns MockProvider; replay, upstox and kite dispatch their existing constructors without network and retain singleton reuse.",
    "A configured name matching `provider_named` cannot bypass the fail-closed `get_provider` path.",
    "An isolated mutation restoring the final else-to-Mock fallback fails the exact unknown-provider regression and production bytes restore.",
    "Focused factory/configuration/connection tests and the affected provider cone pass with no credentials, sockets or execution activation.",
    "One independent Critical SPEC and QUALITY review passes."
  ],
  "test_plan": [
    "Add RED unknown/empty/Dhan configuration tests with constructor spies, make the smallest get_provider dispatch correction, then run focused factory and existing connection/provider configuration tests.",
    "Run an isolated fallback mutation, exact restoration, compile/diff/architecture and protected-source checks before Critical review."
  ],
  "risk_classification": {
    "tier": "Critical",
    "reason": "A configuration typo that silently supplies Mock data can falsify research, monitoring or Paper results and hide the absence of a real provider."
  },
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "owner_task": "/root",
  "implementation_result": {
    "status": "IMPLEMENTATION PASS / REVIEW PENDING",
    "red": "empty, unknown and Dhan configured names constructed Mock and did not raise",
    "green": "empty, unknown and V0-unopened configured names raise UnknownProvider before adapter construction",
    "focused": 5,
    "affected": 199,
    "fallback_mutation": "four intended failures, exact production restoration passes",
    "architecture_files": 435,
    "provider_open": false,
    "report": ".agent/runs/strategy-os-v0-provider-factory-fail-closed/report.md"
  },
  "first_review": {
    "review_task": "/root/provider_factory_review",
    "review_package_sha256": "667758dd7aab339e5e67433f87510a221cb9a298ef4b85f303e792d8c6b656df",
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "open_findings": ["SPEC-P0-001", "QUALITY-P1-001", "QUALITY-P2-001"],
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "SPEC-P0-001/QUALITY-P1-001: normalize and reject unsupported configuration before returning a warm singleton; add warm unknown/Dhan tests through get_provider and configured-match provider_named.",
    "QUALITY-P2-001: remove stale documentation that described get_provider as retaining a Mock fallback.",
    "Evidence: bind exact commands and mutant bytes/diff, then prove complete repository and external-frontend protected manifests before/after."
  ],
  "correction_result": {
    "status": "CORRECTION PASS / FOCUSED RECHECK PENDING",
    "red": "warm unknown and Dhan singleton bypasses reproduced through get_provider",
    "green": "configured name validates before any warm singleton return through both entry points",
    "focused": 7,
    "affected": 201,
    "warm_ordering_mutation": {
      "status": "killed_and_restored",
      "production_sha256": "15130a32fd4e03fa58323e1c8ccf2e0ffdb52afca09980007b40c167ab3735ed",
      "mutant_sha256": "020e90517d355305dca07f49041ea49247382eb5b8053c40b5ae55dbec851da0"
    },
    "protected_repo_files": 306,
    "protected_external_frontend_files": 996,
    "protected_deltas": 0,
    "architecture_files": 435,
    "command_manifest": ".agent/runs/strategy-os-v0-provider-factory-fail-closed/correction-command-manifest.md"
  },
  "final_review": {
    "review_task": "/root/provider_factory_review",
    "review_package_sha256": "5a9b8c3171e52cee29604bcbb60db399df884961149a7710a1897ebd61dc3190",
    "verdict": "SPEC PASS / QUALITY PASS",
    "closed_findings": ["SPEC-P0-001", "QUALITY-P1-001", "QUALITY-P2-001"],
    "open_findings": [],
    "evidence_gaps": [],
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "highest_claim": "locally runnable compatible provider-configuration safety correction",
    "provider_open": false,
    "deployment": false
  },
  "review": {
    "required": true,
    "assignment_id": "v0_provider_factory_fail_closed_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Provider configuration selects market truth; silent Mock fallback is a Critical false-market boundary.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-provider-factory-fail-closed/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/providers/factory.py",
      "paper-trader/backend/tests/test_v0_provider_factory.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-provider-factory-fail-closed.md",
      ".agent/runs/strategy-os-v0-provider-factory-fail-closed"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/core/config.py",
      "paper-trader/backend/app/providers/base.py",
      "paper-trader/backend/app/providers/brokers.py",
      "paper-trader/backend/app/providers/connection.py",
      "paper-trader/backend/app/providers/connection_store.py",
      "paper-trader/backend/app/providers/mock.py",
      "paper-trader/backend/app/providers/replay.py",
      "paper-trader/backend/app/providers/kite.py",
      "paper-trader/backend/app/providers/upstox.py",
      "paper-trader/backend/app/providers/dhan.py",
      "paper-trader/backend/app/api",
      "paper-trader/backend/app/db",
      "paper-trader/backend/migrations",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/app/ledger",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-provider-factory-fail-closed/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "Standing V0 development authority permits this offline configuration correction and review.",
    "No real provider credentials/network/conformance, data-right entitlement, public capability, capture, frontend, monitoring/Paper activation, deployment, live/order or money action."
  ],
  "stop_conditions": [
    "The correction requires changing Settings validation, provider registries/adapters, connection lifecycle, release profile, schema/migration, API or frontend paths.",
    "A protected adapter must be constructed with real credentials or network to prove dispatch.",
    "Concurrent work changes the owned factory or test path without exact attribution."
  ],
  "deployment_impact": {
    "classification": "compatible configuration safety correction; no provider opening",
    "required_evidence": "Offline constructor-spy and affected configuration tests, fallback mutation, protected-source equality and explicit configuration release note ownership.",
    "release_deployable": false,
    "production_rehearsed": false,
    "deployed": false
  },
  "nonclaims": [
    "No real Kite/Dhan/Upstox conformance, provider entitlement, expiry/reconnect guarantee, public connection, capture, monitoring, Paper, frontend, release deployability, deployment or V0 completion."
  ]
}
---

# V0 provider factory fail-closed correction

Reject unsupported process configuration. Never let a typo present Mock synthetic
data as the configured provider.
