---
{
  "id": "strategy-os-v0-monitoring-persistence-materialization",
  "phase": "v0",
  "status": "active",
  "kind": "critical_read_only_migration_materialization",
  "goal": "Freeze the exact migration head, dependency acceptance, contract/schema ownership, stable inputs and deployment proof plan for monitoring persistence without product or schema mutation.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Produce a sealed START/STOP decision proving actual 0043 head/no 0044 owner, accepted dependency identities, collision-free paths, exact table-to-domain mapping, migration/recovery/tenant/resource gates and stable hashes; no product write."},
  "risk_tags": ["critical", "schema-planning", "migration-head", "tenant-isolation", "authority-separation", "parallel-materialization"],
  "required_docs": [
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence.md", "sections": ["V0 monitoring persistence"]},
    {"path": ".agent/runs/strategy-os-v0-v6-handoff-reconciliation/report.md", "sections": ["Controlling decisions", "Revised V0 ownership order", "Programme integration outcome"]},
    {"path": ".agent/runs/strategy-os-v0-signal-alert-attention-correction/review/verdict.json", "sections": ["SPEC", "QUALITY", "final", "finding_disposition"]},
    {"path": ".agent/runs/strategy-os-v0-data-only-connection-contract/review.md", "sections": ["Final verdict", "Recheck binding", "Finding closure"]},
    {"path": ".agent/runs/strategy-os-v0-local-release-output-exit-race-correction/review/verdict.json", "sections": ["verdicts", "final_verdict", "deployability"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Current verdict", "Open obligations"]}
  ],
  "dependency_gate": "Read-only materialization may run while catalogue correction completes; product START remains blocked until monitoring-intent publication is accepted.",
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence-materialization.md", ".agent/runs/strategy-os-v0-monitoring-persistence-materialization"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence-materialization.md", ".agent/runs/strategy-os-v0-monitoring-persistence-materialization"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence.md", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Query migration modules and runtime discovery to prove the current execution/user head is exactly 0043, research head remains 0011, and no 0044 revision/path/owner exists.",
    "Reconcile the accepted pure monitoring contracts with the persistence capsule. `app/monitoring/contracts.py` and `__init__.py` are accepted inputs, not persistence-writer paths; identify every required capsule correction without applying it.",
    "Map all nine declared tables to MonitoringAssignment, MonitoringSignalEvent, SignalAlert, AlertDeliveryAttempt, AlertAttentionEvent/projection, state snapshots/latest state and reviews. Name append-only versus rebuildable facts and exact uniques/indexes/checks/FKs.",
    "Inspect current models, planes, copy, restore and migration conventions; record exact stable hashes and all concurrent dirty deltas/owners.",
    "Define SQLite and PostgreSQL 16 fresh/0043-upgrade/interruption/restart/restore/downgrade-forward-repair/concurrency proof, least-privilege/service consumer owner, resource bounds and rollback/nonclaims.",
    "Return START only if paths are collision-free and all dependencies except catalogue publication are accepted; otherwise return STOP with the exact missing gate."
  ],
  "acceptance": [
    "Machine-discovered 0043/0011 heads and absent 0044 are directly evidenced, not inferred from filenames.",
    "Stable-input manifest covers every future allowed/protected schema path and accepted monitoring contract source.",
    "Table/constraint/index/dedupe/projection/tenant/authority matrix has no legacy SignalEvent reuse, money FK or operator visibility.",
    "Capsule ownership correction removes accepted contract files from the future writer and preserves them as inputs.",
    "Implementation packet names one Sol-medium owner, one Critical reviewer, exact tests/log paths and deployment/nonclaim gates without starting work.",
    "Architecture validator and protected hashes pass; no product/CURRENT/PROGRAMME/queue/capsule-source mutation."
  ],
  "test_plan": ["Read-only migration graph/head discovery and path-overlap scripts.", "Schema/copy/restore/plane source inspection plus exact hash manifests and queue/capsule consistency validation."],
  "parallel_budget": 1,
  "assignments": [{"id": "v0_monitoring_persistence_materialization", "kind": "read_only_migration_materialization", "owner_task": "/root/v0_monitoring_persistence_materialization", "allowed_paths": [".agent/runs/strategy-os-v0-monitoring-persistence-materialization"], "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root/v0_monitoring_persistence_materialization",
  "review": {"required": false, "assignment_id": "v0_monitoring_persistence_materialization_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-monitoring-persistence-materialization/review-package.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence-materialization.md", ".agent/runs/strategy-os-v0-monitoring-persistence-materialization"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-monitoring-persistence-materialization/report.md", "verdicts": ["MATERIALIZATION"], "max_rechecks": 0},
  "owner_gates": ["This capsule authorizes read-only planning/evidence only; root integrates any capsule amendment and starts implementation after the catalogue gate.", "No schema, migration, product, branch, frontend, provider, execution, money or deployment mutation."],
  "stop_conditions": ["Actual head differs from 0043 or 0044 exists/has an owner.", "Accepted contract files would need modification or any writer path overlaps the active catalogue.", "A monitoring fact requires a broker/account execution/money relation or destructive backfill."],
  "deployment_impact": {"classification": "read-only migration planning; no runtime/schema/service change"},
  "nonclaims": ["No migration, repository, runtime, API, frontend, provider, execution, deployment or V0 completion is implemented by this materialization."]
}
---

# Monitoring persistence materialization

Freeze the exact schema-owner packet now; start product writes only after the verified catalogue accepts monitoring intent.
