---
{
  "id": "phase6-generated-strategy-version-lineage",
  "phase": "phase6",
  "status": "blocked",
  "goal": "Close CUR-H4 by replacing mutable generated-strategy current-slot identity with immutable version records and append-only lineage.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The accepted authority-foundation architecture correction assigns CUR-H4 to this bounded Phase 6 lineage capsule, but work remains unauthorized until the phase6-architecture dependency gate opens it. Authority is then limited to the listed generated-strategy, model, migration, test, and evidence paths; automatic promotion, consumer enablement, activation, deployment, production, live, and money authority remain closed.",
    "stopping_condition": "Complete only after generated strategies use immutable canonical version records and append-only lineage; creating or promoting version two cannot alter version-one bytes, address, attribution, or fresh-process exact-version replay; unverifiable legacy current-slot rows refuse replay, promotion, and activation; SQLite and disposable PostgreSQL prove migration and restart parity; and every named forbidden consumer remains blocked. Stop with the goal active before enabling a forbidden consumer or granting mutable current-slot state historical authority."
  },
  "risk_tags": ["high", "immutable-lineage", "schema", "deployment-boundary"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["13. Authority-foundation correction contract"]}, {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Phase 6 ownership"]}],
  "dependency_gate": "phase6-architecture",
  "hard_pre_use_dependency_for": ["generated-strategy replay", "promotion", "current-slot replacement as evidence", "paper or live assignment", "activation", "deployment binding", "release evidence"],
  "deadline": "Before the first Phase 6 activation or deployment-binding capsule and before any forbidden consumer is reachable.",
  "allowed_paths": ["paper-trader/backend/app/core/generated_strategies.py", "paper-trader/backend/app/db/models.py", "paper-trader/backend/migrations/versions/20260818_0040_generated_strategy_lineage.py", "paper-trader/backend/tests/test_phase6_generated_strategy_version_lineage.py", ".agent/runs/phase6-generated-strategy-version-lineage"],
  "nonclaims": ["No automatic promotion, activation, deployment, live, or money authority."],
  "owner_gates": ["Stop before enabling a forbidden consumer or treating a mutable stable key/current pointer as immutable historical identity."],
  "stop_conditions": ["Creating version two overwrites or changes version one; replay resolves through a mutable current slot; legacy lineage gains synthetic authority."],
  "deployment_impact": {"classification": "additive-generated-version-lineage-schema", "required_evidence": "Execution exact-head migration, model-DDL parity, immutable collision/refusal, SQLite and disposable PostgreSQL 16 fresh/upgrade/restart/rollback-path evidence."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "default"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Each generated version has immutable canonical identity and source/admission lineage.", "A stable key may point to a current version but cannot identify historical bytes.", "Creating or promoting a later version leaves earlier bytes, address, attribution, and replay unchanged.", "Unverifiable legacy current-slot rows refuse replay/promotion/activation.", "Forbidden consumers remain blocked until direct evidence and critical review pass."],
  "test_plan": ["Two-version immutable lineage and collision tests; fresh-process exact-version replay; SQLite/PostgreSQL migration parity; forbidden-consumer search; protected hashes and scoped diff."],
  "review": {"required": true, "assignment_id": "phase6_generated_lineage_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/core/generated_strategies.py","paper-trader/backend/app/db/models.py","paper-trader/backend/migrations/versions/20260818_0040_generated_strategy_lineage.py","paper-trader/backend/tests/test_phase6_generated_strategy_version_lineage.py"], "exclude_paths": [], "output": ".agent/runs/phase6-generated-strategy-version-lineage/owner/report.md", "verdicts": ["LINEAGE", "AUTHORITY"]}
}
---

# Phase 6 generated-strategy version lineage

CUR-H4 is contained only while every named consumer remains forbidden. This capsule must prove two-version immutability and fresh-process replay by exact version before activation work starts.
