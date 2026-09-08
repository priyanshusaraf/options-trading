---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-monitoring-persistence-orchestration-foundation",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_monitoring_transaction_orchestration_foundation",
  "goal": "Persist one accepted compiled monitoring transition as one successor snapshot, one event and at most one alert inside the caller-owned transaction, with exact retry/rollback semantics and no provider, worker, API, execution or money authority.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "BUY/SELL/EXIT/HOLD, duplicate retry, two-event chain, injected failure rollback, inactive assignment and alert/no-alert persistence pass on accepted repository bytes; protected/resource/architecture evidence and one Critical review pass."},
  "risk_tags": ["critical", "monitoring-persistence", "transaction-atomicity", "idempotency", "restart", "tenant-isolation", "no-money-authority"],
  "depends_on": ["strategy-os-v0-monitoring-evaluation-transition-foundation", "strategy-os-v0-monitoring-check-expression-semantics-correction"],
  "dependency_gate": {
    "compiler_recheck_verdict_sha256": "fe64a98ed42b823b46f0389a1f8f0a3bd11e028f37d61e83fc9c9fc25b5274d6",
    "monitoring_persistence_verdict_sha256": "95a4f27ebb10961eefa36156fc92f398078abf0de3fe55da5f039b74c259b208",
    "decision": "KEEP + HARDEN: integrate only caller-owned transactional persistence; provider and worker remain blocked"
  },
  "required_docs": [
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-evaluation-transition-foundation.md", "sections": ["V0 monitoring evaluation transition foundation"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence.md", "sections": ["V0 monitoring persistence"]},
    {"path": ".agent/runs/strategy-os-v0-owner-direction-extension-2026-08-29/report.md", "sections": ["Alerts, Paper and Both orchestration", "Verification and deployment decision"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/app/monitoring/runtime.py",
    "paper-trader/backend/tests/test_v0_monitoring_persistence_orchestration.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence-orchestration-foundation.md",
    ".agent/runs/strategy-os-v0-monitoring-persistence-orchestration-foundation"
  ],
  "new_paths": [
    "paper-trader/backend/app/monitoring/runtime.py",
    "paper-trader/backend/tests/test_v0_monitoring_persistence_orchestration.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence-orchestration-foundation.md",
    ".agent/runs/strategy-os-v0-monitoring-persistence-orchestration-foundation"
  ],
  "protected_paths": [
    "paper-trader/backend/app/monitoring/contracts.py",
    "paper-trader/backend/app/monitoring/state_contracts.py",
    "paper-trader/backend/app/monitoring/evaluation.py",
    "paper-trader/backend/app/monitoring/repository.py",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/market_data",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ledger",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Accept only the exact MonitoringEvaluationTransition produced by the accepted compiler and an exact owner-scoped MonitoringRepository whose session transaction is caller-owned.",
    "Within one caller-owned savepoint append the successor snapshot, event and canonical alert when AlertDerived; NoAlert creates no alert row. Return only repository-reloaded exact facts.",
    "Byte-identical retry is idempotent. A conflicting identity, inactive assignment, foreign owner, stale predecessor or injected failure refuses/rolls back without a partial durable prefix.",
    "Do not commit, begin an independent outer transaction, create delivery/attention facts, acquire provider data, run a worker, expose an API, or import execution/order/position/capital/PnL/money paths."
  ],
  "acceptance": [
    "BUY/SELL/EXIT persist one snapshot, one event and one alert; HOLD persists one snapshot/event and zero alerts.",
    "Byte-identical retry returns the same facts and row counts; a second causal event advances exactly one predecessor sequence.",
    "Injected failure after snapshot, after event and before alert rolls back the entire orchestration savepoint; restart/retry then succeeds once.",
    "Paused/withdrawn/foreign/stale transitions refuse before partial writes.",
    "Alert persistence and later failed delivery-attempt evidence are independent; delivery failure cannot erase event or alert.",
    "Source/import guards prove no provider, worker, API, broker, execution, order, position, capital, PnL, credential, network or deployment reachability.",
    "Focused SQLite, accepted persistence/migration affected suites, resource/protected/architecture gates and one independent Critical review pass."
  ],
  "test_plan": [
    "Use actual accepted compiler fixtures and current SQLite monitoring schema; run exact row-count, retry, rollback and two-event chain tests.",
    "Inject exceptions at each orchestration step and prove caller transaction remains usable after rollback.",
    "Kill/restore the outer savepoint, exact transition type and alert-canonicality guards.",
    "Run monitoring persistence/migration affected gates; PostgreSQL remains the accepted repository dependency and any unavailable harness is explicit."
  ],
  "risk_classification": {"tier": "Critical", "reason": "A partial or duplicate event/alert prefix can mislead users, cross tenant state, or make restart non-reconstructible."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "implementation_result": {
    "status": "CORRECTION PASS / FOCUSED RECHECK PASS",
    "focused_passed": 14,
    "affected_passed": 195,
    "affected_skipped": 17,
    "mutations_killed_restored": 4,
    "resource_probe": {"runs": 100, "deterministic_address_sets": 1, "row_counts": [2, 1, 1, 0], "elapsed_seconds": 1.818021, "peak_traced_bytes": 1215135},
    "protected_repo_files": 353,
    "protected_external_frontend_files": 996,
    "protected_deltas": 0,
    "architecture_files": 440,
    "report": ".agent/runs/strategy-os-v0-monitoring-persistence-orchestration-foundation/report.md"
  },
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "verdict_sha256": "a912ddd7a31226ec9d8caa80ef388fad594b4949197fe9f1e46a0897b173b396",
    "open_findings": ["V0-MPO-CR-001", "V0-MPO-EG-001"],
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "correction_result": {
    "status": "CORRECTION PASS / FOCUSED RECHECK PASS",
    "canonical_alert_derivation": "derive_signal_alert(event) must equal the supplied AlertDerived or NoAlert before any write",
    "sell_persistence": "Explicit SELL -> SHORT snapshot/event/alert row evidence passes",
    "rechecks_used": 1,
    "rechecks_remaining": 0
  },
  "final_review": {
    "verdict": "SPEC PASS / QUALITY PASS / final PASS",
    "recheck_verdict_sha256": "85564aa72643f5df16568f8aeb50159699f86ab329cfb06b4e7ce4461b657210",
    "closed_findings": ["V0-MPO-CR-001", "V0-MPO-EG-001"],
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "deployment": false
  },
  "review": {
    "required": true,
    "assignment_id": "v0_monitoring_persistence_orchestration_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Monitoring transaction atomicity, tenant scope and restart/idempotency are Critical.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-monitoring-persistence-orchestration-foundation/review-package.json",
    "review_paths": ["paper-trader/backend/app/monitoring/runtime.py", "paper-trader/backend/tests/test_v0_monitoring_persistence_orchestration.py", "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence-orchestration-foundation.md", ".agent/runs/strategy-os-v0-monitoring-persistence-orchestration-foundation"],
    "exclude_paths": ["paper-trader/backend/app/monitoring/contracts.py", "paper-trader/backend/app/monitoring/state_contracts.py", "paper-trader/backend/app/monitoring/evaluation.py", "paper-trader/backend/app/monitoring/repository.py", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/ir", "paper-trader/backend/app/providers", "paper-trader/backend/app/api", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"],
    "output": ".agent/runs/strategy-os-v0-monitoring-persistence-orchestration-foundation/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": ["No provider/network/right decision, schema/migration, worker/service, API/frontend, Paper/live execution, order, position, capital, PnL, money or deployment action."],
  "stop_conditions": ["Accepted repository/compiler behavior must change.", "The slice needs a new schema, worker, provider, shared API/frontend or delivery transport.", "An outer transaction or commit would be hidden inside the orchestration helper."],
  "deployment_impact": {"classification": "compatible unpublished transaction helper; monitor service remains architecture-changing and blocked", "required_evidence": "Atomicity/retry/restart and protected evidence only. No service or deployment claim.", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No provider acquisition, worker, delivery transport, attention mutation, API, Alerts Inbox, Paper/live execution, order, position, capital, PnL, readiness, release deployability, deployment or V0 completion."]
}
---

# Monitoring persistence orchestration foundation

This slice persists already-compiled monitoring facts inside the caller-owned
transaction. It does not acquire data or run a monitor service.
