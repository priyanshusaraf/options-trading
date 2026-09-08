---
{
  "id": "phase5-cache-version-contract-correction",
  "phase": "phase5",
  "status": "accepted",
  "kind": "correction",
  "goal": "Make the accepted backtest cache schema-version-9 contract explicit and current across its two stale literal tests without changing cache behavior.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after the v9 semantic invalidation is documented, both direct contracts assert 9, every dynamic consumer remains green, a reversible 9-to-8 mutation fails the exact tests, and bytes restore."},
  "risk_tags": ["cache-identity", "research-integrity", "compatibility", "correction"],
  "required_docs": [{"path": "paper-trader/docs/agent/tasks/phase5-integration-evidence-recovery-replan.md", "sections": ["decision_questions", "acceptance", "nonclaims"]}, {"path": ".agent/runs/phase5-implementation/owner-replan-proposal.md", "sections": ["Cache schema version contract", "Boundaries"]}],
  "dependency_gate": "phase5-capital-plane-ownership-correction",
  "allowed_paths": ["paper-trader/backend/app/backtest/cache.py", "paper-trader/backend/tests/test_backtest_cache_risk_model.py", "paper-trader/backend/tests/test_backtest_premium.py", ".agent/runs/phase5-cache-version-contract-correction", "paper-trader/docs/agent/tasks/phase5-cache-version-contract-correction.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md"],
  "nonclaims": ["No cache algorithm/address behavior, stored row, migration, runtime, provider, order, live, deployment, production or Phase 6 change."],
  "owner_gates": ["Stop if v9 cannot be justified from the accepted authority-bound cache identity or if correction requires behavior/migration changes."],
  "stop_conditions": ["Any consumer beyond documentation/two stale literals requires repair; dynamic cache selectors fail; mutation survives; protected product bytes other than the v9 comment drift."],
  "deployment_impact": {"classification": "compatible contract documentation/test correction", "required_evidence": "Dynamic cache reuse, premium, risk, tenant and Phase 4 identity selectors.", "highest_claim": "locally_runnable"},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Version 9 is documented as the Phase 4 authority-bound cache invalidation.", "Only the two stale literal tests change from 8 to 9.", "All dynamic cache consumers pass.", "A 9-to-8 mutation fails both direct contracts and restores exact bytes."],
  "test_plan": ["Direct v9 tests; cache/premium/risk/tenant/Phase4 identity selectors; one mutation; product/test hash audit."],
  "review": {"required": true, "separate_stage": "phase5-review", "assignment_id": "phase5_cache_version_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/runs/phase5-review/review-package.json", "review_paths": ["paper-trader/backend/app/backtest/cache.py", "paper-trader/backend/tests/test_backtest_cache_risk_model.py", "paper-trader/backend/tests/test_backtest_premium.py"], "exclude_paths": ["paper-trader/frontend"], "output": ".agent/runs/phase5-cache-version-contract-correction/report.md", "verdicts": ["CORRECTION"], "max_rechecks": 0},
  "result": {"verdict": "CORRECTION PASS", "report": ".agent/runs/phase5-cache-version-contract-correction/report.md", "report_sha256": "24116ca5ea1cc9abc5b64ae22c81f95ce01909d50d60f5107f506c356370e742", "deployability": ".agent/runs/phase5-cache-version-contract-correction/deployability.md", "deployability_sha256": "bdca7f05ed5c66043efbc1b51a2aae5af0868e79467d3464e44b6879199a1e1f", "schema_version": 9, "stale_literal_contracts_corrected": 2, "dynamic_selectors_passed": 110, "mutations": 1}
}
---

# Phase 5 cache version contract correction

This slice documents and tests the already-current version 9 identity; it changes no cache behavior.
