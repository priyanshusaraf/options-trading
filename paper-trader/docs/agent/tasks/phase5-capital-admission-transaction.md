---
{
  "id": "phase5-capital-admission-transaction",
  "phase": "phase5",
  "status": "accepted",
  "kind": "implementation_sequence",
  "goal": "Implement the sole fenced closed-batch capital-admission transaction under the existing account lease and PostgreSQL reservation-head lock without wiring an order path.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after two sessions/processes on PostgreSQL prove no double reservation, stale actors and conflicting duplicates have zero effects, every batch is complete/atomic/deterministic, command preparation requires the exact active reservation and all lock/fence/idempotency mutations fail with exact restoration."},
  "risk_tags": ["critical", "money", "concurrency", "postgresql", "lease", "transaction"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase5-capital-admission-design.md", "sections": ["Deterministic admission policy", "Concurrency proof", "Pending-order and broker-uncertainty behavior"]}, {"path": "paper-trader/docs/engineering/decisions/0017-sizing-target-position-and-reservation.md", "sections": ["Closed batch admission", "PostgreSQL transaction and fencing", "Reservation lifecycle and recovery"]}],
  "dependency_gate": "phase5-capital-admission-schema",
  "allowed_paths": ["paper-trader/backend/app/execution/capital_admission.py", "paper-trader/backend/app/execution/leases.py", "paper-trader/backend/tests/test_capital_admission.py", "paper-trader/backend/tests/test_capital_admission_postgresql.py", "paper-trader/backend/tests/test_capital_admission_schema.py", "paper-trader/backend/tests/test_execution_leases.py", "paper-trader/backend/tests/test_postgres_execution_leases.py", "paper-trader/backend/tests/test_portable_concurrency_integration.py", "paper-trader/docs/agent/DEPLOYABILITY.md", "paper-trader/docs/agent/tasks/phase5-capital-admission-transaction.md", ".agent/runs/phase5-capital-admission-transaction"],
  "nonclaims": ["No runner, provider, broker I/O, order submission, behavior switch, live/money activation, deployment or production claim."],
  "owner_gates": ["Stop before any caller can use an admission to submit or resize an order."],
  "stop_conditions": ["Account lease or reservation head is bypassed; broker I/O occurs in transaction; partial batch commits; stale fence writes; uncertainty releases capital."],
  "deployment_impact": {"classification": "architecture-changing", "highest_claim": "locally_runnable", "future_owner": "Shadow/recovery and assurance are exact following capsules; production topology remains Phase 6/V1."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["One account/fence/head transaction owns every batch/decision/reservation effect.", "Stable replay is byte-identical and complete.", "Duplicate delivery converges only on exact bytes.", "Direct PostgreSQL races and lock/fence mutations prove the authority."],
  "test_plan": ["Two-instance double spend; stale fence; complete batch; deterministic tie; group semantics; duplicate conflict; rollback; response loss; active balance; outbox; five critical mutations."],
  "review": {"required": false, "assignment_id": "phase5_capital_transaction_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/execution/capital_admission.py", "paper-trader/backend/app/execution/leases.py"], "exclude_paths": ["paper-trader/backend/app/providers", "paper-trader/frontend"], "output": ".agent/runs/phase5-capital-admission-transaction/report.md", "verdicts": ["TRANSACTION"]},
  "acceptance_record": {"decision": "ACCEPTED", "report": ".agent/runs/phase5-capital-admission-transaction/report.md", "report_sha256": "a04c8b9629b9ea84a8cc78ce0643ef20147e7d7e3b9e3b3315382510e3e58fcd", "scope_correction": ".agent/runs/phase5-capital-admission-transaction/scope-correction.md", "scope_correction_sha256": "718c38278f5dd9cc49784b08cd882d6a2b86460d0cf72b074ab20e503cc71120", "verdict": "TRANSACTION PASS"}
}
---

# Phase 5 capital-admission transaction

This service is unwired and cannot submit an order.

The schema-stage zero-consumer assertion is an exact transitive regression path for
this first writer. Its allowlist addition does not add a production path; it replaces
the obsolete zero-consumer expectation with the two named transaction consumers and
continues to refuse every campaign, tranche, fill, runner, provider and broker consumer.
