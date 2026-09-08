---
{
  "id": "phase3-4-ir-v2-admission-persistence",
  "phase": "component-ir-v2-interphase",
  "status": "accepted",
  "goal": "Extend the single causal admission receipt and additive execution/research persistence for v2 without rewriting v1 evidence or creating a second downstream execution authority.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after one Terra owner proves v2 receipt reproducibility, mismatch refusal, immutable idempotency, owner isolation, additive SQLite and PostgreSQL populated upgrades, rollback/refusal, restart, concurrency, recovery, and downstream admission_address compatibility; then make phase3-4-ir-v2-api-contract review-ready."
  },
  "risk_tags": ["critical", "money-authority", "admission", "migrations", "postgresql", "research-integrity"],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "sections": ["13. Serialization and identity", "14. Admission and persistence", "15. Versioning", "18. Deployability impact"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-ir-v2-port-contract.md",
      "sections": ["3. Accepted baseline", "4. Architectural context", "5. Scope boundaries", "7. Migration and compatibility", "9. Dependency order and chat structure", "10.4 phase3-4-ir-v2-admission-persistence", "11. Tests and evidence", "14. Stop and owner gates", "15. Required nonclaims"]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": ["Open obligations", "Phase 4 ownership"]
    }
  ],
  "allowed_paths": [
    "paper-trader/backend/app/strategy/admission.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/app/db/migrate.py",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/migrations/versions/20260816_0035_ir_v2_admissions.py",
    "paper-trader/backend/research/domain/admissions.py",
    "paper-trader/backend/research/domain/migrate.py",
    "paper-trader/backend/research/domain/models.py",
    "paper-trader/backend/research/domain/migrations/0006_ir_v2_admissions.py",
    "paper-trader/backend/tests/test_ir_v2_admission_receipt.py",
    "paper-trader/backend/tests/test_ir_v2_execution_migration.py",
    "paper-trader/backend/research_tests/test_ir_v2_research_migration.py",
    "paper-trader/backend/tests/test_ir_v2_legacy_compatibility.py",
    "paper-trader/docs/operations/strategy-admission.md",
    "paper-trader/docs/agent/tasks/phase3-4-ir-v2-admission-persistence.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase3-4-ir-v2-admission-persistence"
  ],
  "nonclaims": [
    "Local migration evidence does not prove production recovery, capacity, security, deployability, or readiness.",
    "V2 admission does not grant live authority, frontend support, provider truth, or Phase 4 semantics."
  ],
  "owner_gates": [
    "The Terra owner alone edits migrations, models, repositories, and admission semantics.",
    "Stop before destructive data work, guessed legacy backfill, duplicate money-row identity, live authority, deployment, credentials, or production data."
  ],
  "stop_conditions": [
    "The current migration heads differ from the capsule assumptions and cannot be additively reconciled.",
    "An admitted v1 row would be rewritten or a downstream fact would gain a second authority.",
    "PostgreSQL evidence is unavailable, a migration mutation survives, or protected/inherited work conflicts."
  ],
  "deployment_impact": {
    "classification": "schema-and-runtime-additive",
    "affected_dimensions": ["Application", "Execution database", "Research database", "Migrations", "Recovery", "PostgreSQL"],
    "required_evidence": "SQLite and disposable PostgreSQL empty/populated upgrade, restart, concurrency, rollback/refusal, recovery, schema parity, and immutable receipt evidence. No production readiness claim."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 4,
  "owner_milestones": ["owner_migration_and_model_interfaces"],
  "assignments": [
    {
      "id": "v2_admission_receipt_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_migration_and_model_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_admission_receipt.py"],
      "output": ".agent/runs/phase3-4-ir-v2-admission-persistence/v2_admission_receipt_cases/report.md"
    },
    {
      "id": "v2_execution_migration_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_migration_and_model_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_execution_migration.py"],
      "output": ".agent/runs/phase3-4-ir-v2-admission-persistence/v2_execution_migration_cases/report.md"
    },
    {
      "id": "v2_research_migration_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_migration_and_model_interfaces"],
      "write_paths": ["paper-trader/backend/research_tests/test_ir_v2_research_migration.py"],
      "output": ".agent/runs/phase3-4-ir-v2-admission-persistence/v2_research_migration_cases/report.md"
    },
    {
      "id": "v2_legacy_restart_concurrency_cases",
      "agent": "luna-worker",
      "mode": "write",
      "depends_on": ["owner_migration_and_model_interfaces"],
      "write_paths": ["paper-trader/backend/tests/test_ir_v2_legacy_compatibility.py"],
      "output": ".agent/runs/phase3-4-ir-v2-admission-persistence/v2_legacy_restart_concurrency_cases/report.md"
    }
  ],
  "acceptance": [
    "The v2 receipt binds exact canonical content/graph addresses and resolved compound parameter-target provenance while admission_address remains the only downstream execution authority.",
    "No admitted v1 fact is rewritten and no unverifiable legacy value is guessed.",
    "Execution and research migrations pass empty/populated SQLite and PostgreSQL upgrade, restart, concurrency, recovery, and rollback/refusal evidence.",
    "Receipt mismatches, partial evidence, foreign ownership, and mutable conflicts fail closed; the required mutation is killed."
  ],
  "test_plan": [
    "Run four new admission/migration clusters plus focused existing admission, schema-migration, concurrency, and owner-isolation tests.",
    "Run the accepted disposable PostgreSQL harness for execution and research migrations.",
    "Run receipt mutations for canonical content bytes and compound parameter provenance plus migration killed mutations, exact head/schema checks, diff, protected hashes, and deployability audit."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase3_4_ir_v2_persistence_owner_integration",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/strategy/admission.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/app/db",
      "paper-trader/backend/research/domain",
      "paper-trader/backend/tests/test_ir_v2_admission_receipt.py",
      "paper-trader/backend/tests/test_ir_v2_execution_migration.py",
      "paper-trader/backend/research_tests/test_ir_v2_research_migration.py",
      "paper-trader/backend/tests/test_ir_v2_legacy_compatibility.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase3-4-ir-v2-admission-persistence/owner_integration/report.md",
    "verdicts": ["INTEGRATION"],
    "max_rechecks": 0
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# IR v2 admission and persistence goal

Migrations and admission authority remain with one Terra owner. Luna children start only after the owner’s schema milestone and may edit their four new test files, never the governing implementation.
