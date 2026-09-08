---
{
  "id": "phase5-capital-admission-schema",
  "phase": "phase5",
  "status": "accepted",
  "kind": "implementation_sequence",
  "goal": "Add execution migration 0041 and exact ORM contracts for sizing, target requests, closed admission batches, reservations and campaign/tranche lineage without enabling a writer.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after SQLite and PostgreSQL 16 prove empty and exact-0040 upgrade, interruption/restart, all constraints/triggers/indexes/FKs, full row and sequence preservation, restore-based rollback and destructive-downgrade refusal while no product writer consumes the new schema."},
  "risk_tags": ["critical", "schema", "migration", "money", "postgresql", "rollback"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase5-capital-admission-design.md", "sections": ["Contract shapes", "Migration and rollback", "Invariants"]}],
  "dependency_gate": "phase5-sizing-target-position-contracts",
  "allowed_paths": ["paper-trader/backend/app/db/models.py", "paper-trader/backend/migrations/versions/20260825_0041_capital_admission.py", "paper-trader/backend/tests/test_capital_admission_schema.py", "paper-trader/backend/tests/test_schema_migrations.py", "paper-trader/backend/tests/test_postgres_execution_schema.py", "paper-trader/backend/tests/test_postgresql_restore_live.py", "paper-trader/backend/tests/test_database_copy_contract.py", "paper-trader/docs/agent/DEPLOYABILITY.md", "paper-trader/docs/agent/tasks/phase5-capital-admission-schema.md", ".agent/runs/phase5-capital-admission-schema"],
  "nonclaims": ["No schema consumer, sizing behavior, reservation writer, broker/order/live/money behavior, deployment or production readiness."],
  "owner_gates": ["Stop before destructive populated-data work, deployment, production data or a consumer outside the exact schema contract."],
  "stop_conditions": ["Historical lineage is inferred; money uses Float; downgrade deletes new facts; dialect contracts diverge; a new table becomes authority without its later fenced writer."],
  "deployment_impact": {"classification": "migration-required", "highest_claim": "locally_runnable", "future_owner": "Production upgrade, backup retention, cutover and rollback rehearsal remain Phase 6/V1 release gates."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Execution head is 0041 and research remains 0011.", "All new facts are additive, owner/account scoped and constraint-complete.", "Legacy bytes remain exact and lineage absence is explicit.", "SQLite/PostgreSQL install, upgrade, restart, restore and downgrade refusal pass."],
  "test_plan": ["Empty/exact-0040 dialect upgrades; interruption/restart; constraints/triggers/FKs/indexes; common digest and fixed-point boundaries; full restore; no-consumer inventory; killed/restored schema guards."],
  "review": {"required": false, "assignment_id": "phase5_capital_schema_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/db/models.py", "paper-trader/backend/migrations/versions/20260825_0041_capital_admission.py"], "exclude_paths": ["paper-trader/frontend"], "output": ".agent/runs/phase5-capital-admission-schema/report.md", "verdicts": ["SCHEMA"]},
  "result": {"verdict": "SCHEMA", "status": "PASS", "report": ".agent/runs/phase5-capital-admission-schema/report.md", "report_sha256": "fc9b73777228e94aaa6c782bda0a52e8774099882c664c6c2519a47a4a0aec76", "execution_head": "0041", "research_head": "0011", "tables": 12, "schema_consumers": 0, "mutations": 9}
}
---

# Phase 5 capital-admission schema

This slice creates durable facts only and enables no writer.
