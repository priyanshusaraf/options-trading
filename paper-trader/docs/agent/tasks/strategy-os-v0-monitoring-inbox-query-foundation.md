---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-monitoring-inbox-query-foundation",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_owner_scoped_alert_inbox_query_foundation",
  "goal": "Provide newest-first owner-scoped SignalAlert plus attention read models with signed opaque filter-bound cursors, without routes, shared auth changes, writes, provider access, execution or public capability.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Two-owner newest-first list/detail, unread/assignment filters, cursor tamper/cross-owner/filter refusal, page bounds and zero-write evidence pass with protected/resource/architecture gates and one Critical review."},
  "risk_tags": ["critical", "tenant-isolation", "alerts-inbox", "cursor-integrity", "privacy", "read-only"],
  "depends_on": ["strategy-os-v0-monitoring-persistence-orchestration-foundation", "strategy-os-v0-auth-session-transport"],
  "dependency_gate": {"persistence_recheck_verdict_sha256": "85564aa72643f5df16568f8aeb50159699f86ab329cfb06b4e7ce4461b657210", "decision": "KEEP + HARDEN: build unregistered read/query seam before shared API assembly"},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-post-0045-parallel-materialization-audit/monitoring-runtime-api/report.md", "sections": ["Exact user journeys", "Authority and privacy flow", "Collision and serialization matrix"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-signal-alert-attention-correction.md", "sections": ["Signal alert truth and provenance correction"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/monitoring/cursor.py", "paper-trader/backend/app/monitoring/query_service.py", "paper-trader/backend/tests/test_v0_monitoring_inbox_query.py", "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-inbox-query-foundation.md", ".agent/runs/strategy-os-v0-monitoring-inbox-query-foundation"],
  "new_paths": ["paper-trader/backend/app/monitoring/cursor.py", "paper-trader/backend/app/monitoring/query_service.py", "paper-trader/backend/tests/test_v0_monitoring_inbox_query.py", "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-inbox-query-foundation.md", ".agent/runs/strategy-os-v0-monitoring-inbox-query-foundation"],
  "protected_paths": ["paper-trader/backend/app/monitoring/contracts.py", "paper-trader/backend/app/monitoring/state_contracts.py", "paper-trader/backend/app/monitoring/evaluation.py", "paper-trader/backend/app/monitoring/runtime.py", "paper-trader/backend/app/monitoring/repository.py", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/api", "paper-trader/backend/app/api/principal.py", "paper-trader/backend/app/core/release_profile.py", "paper-trader/backend/app/main.py", "paper-trader/backend/app/providers", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Accept one exact owner-scoped MonitoringRepository and one exact cursor codec secret supplied by the future shared assembly.",
    "Return newest-first canonical SignalAlert with its rebuildable attention projection. Assignment/unread filters and cursor position are bound into the signature.",
    "Cursor payload exposes no owner, symbol, strategy name, note or credential; owner is HMAC associated data. Cross-owner/filter replay, tamper, malformed and oversized tokens refuse uniformly.",
    "Default page 50, maximum 100. List/detail perform no append, projection rebuild or delivery/attention/review mutation.",
    "No route registration, principal/release/main change, session parsing, provider, worker, execution, analytics or frontend."
  ],
  "acceptance": [
    "Two owners prove newest-first list/detail, private absence, assignment and unread filters and stable page continuation.",
    "Cursor tamper, cross-owner, cross-filter, malformed, stale-shape and oversized cases refuse; decoded token contains no owner/symbol/strategy/note/credential text.",
    "Repeated GET-equivalent calls leave every ORM new/dirty/deleted set and monitoring row count unchanged.",
    "Source/import guards forbid API/principal/release/main/provider/engine/execution/analytics/frontend imports.",
    "Focused/affected/resource/protected/architecture gates and one Critical review pass."
  ],
  "test_plan": ["SQLite two-owner alert/attention fixtures and bounded keyset pages.", "Kill/restore owner-associated-data, filter-digest and read-only guards.", "Run accepted monitoring persistence/migration affected suites."],
  "risk_classification": {"tier": "Critical", "reason": "A cursor or query ownership defect can disclose tenant alert, strategy and instrument facts."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "implementation_result": {"status": "CORRECTION PASS / FOCUSED RECHECK PASS", "focused_passed": 16, "affected_passed": 211, "affected_skipped": 17, "mutations_killed_restored": 4, "resource_probe": {"runs": 100, "deterministic_page_sets": 1, "all_monitoring_rows_unchanged": true, "elapsed_seconds": 1.118497, "peak_traced_bytes": 451044}, "protected_repo_files": 354, "protected_external_frontend_files": 996, "protected_deltas": 0, "architecture_files": 441, "report": ".agent/runs/strategy-os-v0-monitoring-inbox-query-foundation/report.md"},
  "first_review": {"verdict": "SPEC FAIL / QUALITY FAIL", "verdict_sha256": "d1216c62d55b08fd14fcc786979bd82c09a3938386d5ac46b11ac21b3dbb57cf", "open_findings": ["V0-MIQ-CR-001", "V0-MIQ-EG-001"], "rechecks_used": 0, "rechecks_remaining": 1},
  "correction_result": {"status": "CORRECTION PASS / FOCUSED RECHECK PASS", "postgresql_cursor_time": "Verified UTC cursor time is converted to the repository naive-UTC database representation before SQL comparison", "all_table_evidence": "All nine monitoring tables counted before and after repeated reads", "rechecks_used": 1, "rechecks_remaining": 0},
  "final_review": {"verdict": "SPEC PASS / QUALITY PASS / final PASS", "recheck_verdict_sha256": "518fe4a69c39f9d799f054fcf668be49e07a7eb37eb157ce287eb9fb1d016794", "closed_findings": ["V0-MIQ-CR-001", "V0-MIQ-EG-001"], "rechecks_used": 1, "rechecks_remaining": 0, "deployment": false},
  "review": {"required": true, "assignment_id": "v0_monitoring_inbox_query_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Tenant alert reads and cursor isolation are Critical privacy boundaries.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-monitoring-inbox-query-foundation/review-package.json", "review_paths": ["paper-trader/backend/app/monitoring/cursor.py", "paper-trader/backend/app/monitoring/query_service.py", "paper-trader/backend/tests/test_v0_monitoring_inbox_query.py", "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-inbox-query-foundation.md", ".agent/runs/strategy-os-v0-monitoring-inbox-query-foundation"], "exclude_paths": ["paper-trader/backend/app/monitoring/contracts.py", "paper-trader/backend/app/monitoring/evaluation.py", "paper-trader/backend/app/monitoring/runtime.py", "paper-trader/backend/app/monitoring/repository.py", "paper-trader/backend/app/db", "paper-trader/backend/migrations", "paper-trader/backend/app/api", "paper-trader/backend/app/providers", "paper-trader/backend/app/engine", "paper-trader/backend/app/execution", "paper-trader/backend/app/ledger", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-monitoring-inbox-query-foundation/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "owner_gates": ["No API registration, auth vocabulary, provider/network/right decision, schema/migration, worker, frontend, execution, money or deployment action."],
  "stop_conditions": ["Accepted repository/model/index behavior must change.", "A route/principal/release/main/frontend path is required.", "A cursor secret would be stored or defaulted in product code."],
  "deployment_impact": {"classification": "compatible unpublished read service; public API remains blocked", "required_evidence": "Query/cursor privacy only; no deployment claim.", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No route, browser session action, public Alerts Inbox, provider, worker, delivery mutation, Paper/live execution, analytics, release deployability, deployment or V0 completion."]
}
---

# Monitoring inbox query foundation

This slice exposes no route. It builds the owner-scoped read model and opaque
cursor contract consumed later by the shared API assembly.
