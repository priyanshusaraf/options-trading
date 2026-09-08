---
{
  "id": "phase5-capital-plane-ownership-correction",
  "phase": "phase5",
  "status": "accepted",
  "kind": "correction",
  "goal": "Assign all twelve Phase 5 capital tables to the existing MONEY plane and close complete ownership accounting without changing physical schema or runtime behavior.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after all twelve tables are MONEY, no new cross-plane FK exists, every money table has an explicit or parent/content-address ownership decision, direct plane/ownership/copy/restore tests pass, mutations remove one table and one ownership category, and exact bytes restore."},
  "risk_tags": ["critical", "money", "persistence-plane", "deployability", "correction"],
  "required_docs": [{"path": "paper-trader/docs/agent/tasks/phase5-integration-evidence-recovery-replan.md", "sections": ["decision_questions", "acceptance", "nonclaims"]}, {"path": ".agent/runs/phase5-implementation/owner-replan-proposal.md", "sections": ["Capital database-plane ownership", "Boundaries"]}],
  "dependency_gate": "phase5-integration-evidence-recovery-replan",
  "allowed_paths": ["paper-trader/backend/app/db/planes.py", "paper-trader/backend/tests/test_db_planes.py", "paper-trader/backend/tests/test_money_plane_ownership.py", ".agent/runs/phase5-capital-plane-ownership-correction", "paper-trader/docs/agent/tasks/phase5-capital-plane-ownership-correction.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md"],
  "nonclaims": ["No table/model/migration/copy implementation/runtime/provider/broker/order/live/frontend/deployment/production/Phase 6 change."],
  "owner_gates": ["Stop before physical schema, cross-plane-FK, runtime, deployment or scope beyond the twelve frozen tables and complete money ownership accounting."],
  "stop_conditions": ["Any proposed table is not MONEY; a new crossing appears; a money table is unaccounted; copy/restore evidence is missing; protected schema bytes drift."],
  "deployment_impact": {"classification": "compatible logical ownership hardening; no physical schema change", "required_evidence": "Plane totality, zero new crossings, complete money ownership categories, database-copy and restore regression replay.", "highest_claim": "locally_runnable"},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["All twelve tables are Plane.MONEY with architecture rationale.", "The FK graph creates zero new crossings.", "Global content-addressed, explicit account and parent-scoped facts are completely accounted in the money ownership ratchet.", "Direct plane, money ownership, tenancy root, database-copy and restore selectors pass.", "Two killed/restored mutations prove table totality and ownership accounting."],
  "test_plan": ["Direct plane and ownership tests; crossing matrix; copy/restore selectors; two mutations; protected hashes; architecture/programme validation."],
  "review": {"required": true, "separate_stage": "phase5-review", "assignment_id": "phase5_capital_plane_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/runs/phase5-review/review-package.json", "review_paths": ["paper-trader/backend/app/db/planes.py", "paper-trader/backend/tests/test_db_planes.py", "paper-trader/backend/tests/test_money_plane_ownership.py"], "exclude_paths": ["paper-trader/frontend"], "output": ".agent/runs/phase5-capital-plane-ownership-correction/report.md", "verdicts": ["CORRECTION"], "max_rechecks": 0},
  "result": {"verdict": "CORRECTION PASS", "report": ".agent/runs/phase5-capital-plane-ownership-correction/report.md", "report_sha256": "764b777142c59c4534cbc07c160b8c5958af1be1a1ae2d4930447f270eef5a93", "deployability": ".agent/runs/phase5-capital-plane-ownership-correction/deployability.md", "deployability_sha256": "4b4d02e7385dab479bd373f3332f33b46909c48f2e63a49f06126985286b1e6f", "tables": 12, "new_crossings": 0, "money_tables_accounted": 37, "mutations": 2}
}
---

# Phase 5 capital plane ownership correction

All twelve additive capital facts remain in the existing MONEY authority and physical schema.
