---
{
  "id": "phase5-canonical-scenario-gate",
  "phase": "phase5",
  "status": "accepted",
  "kind": "integration_gate",
  "goal": "Prove the reusable-equity, weekly-options/order-flow and cross-market scenarios plus Phase 5 resource/binding seed cases through the integrated accepted language, runtime, provider-fact, research, cache and packaging seams.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after all scenarios create immutable strategies, verified requirements/ResourcePlans/results and exact refusals through fresh-process SQLite and PostgreSQL evidence, every tier and carry-through fact is accounted, no broker-specific workaround exists, and no deployment/live authority is inferred."},
  "risk_tags": ["critical", "integration", "scenarios", "research-integrity"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md", "sections": ["Operator outcome", "Instrument roles and future bindings", "Verification and complete-universe gates"]}],
  "dependency_gate": "phase5-research-runtime-packaging-recovery-correction",
  "additional_dependencies": ["phase5-provider-evidence-compatibility", "phase5-first-party-analytical-catalogue", "phase5-state-execution-derivatives-catalogue", "phase5-custom-node-contracts", "phase5-research-parity-assurance"],
  "allowed_paths": ["paper-trader/backend/tests/test_phase5_canonical_scenarios.py", "paper-trader/backend/research_tests/test_phase5_canonical_scenarios.py", ".agent/runs/phase5-canonical-scenario-gate", "paper-trader/docs/agent/tasks/phase5-canonical-scenario-gate.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "nonclaims": ["No deployment binding, account reservation, provider correctness, broker protection, live, order, or money authority.", "Scenario evidence is local and does not prove production capacity or commercial tiers."],
  "owner_gates": ["Stop before frontend, real provider/credential, deployment, sizing/routing/risk/execution changes, broker/order/money, or commercial tier decisions."],
  "stop_conditions": ["Any scenario uses broker-specific hacks, current market truth as history, missing provider facts, stale alignment, incomplete ResourcePlan, hidden demand, cloned graph for binding, or mocked critical authority seam."],
  "deployment_impact": {"classification": "architecture-changing", "required_evidence": "Integrated locally_runnable scenario and packaging evidence only; release and production rows remain open."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Scenario A uses one immutable EMA/RSI/ATR graph across several SELF/primary binding requirements with sizing, stops and pyramiding intent and exact ResourcePlans.", "Scenario B uses point-in-time weekly option/strike/lot/session truth, ATM bounded windows, OI/depth capability decisions, weekday scheduling and arbitrary exits/protection intent with unsupported facts refusing.", "Scenario C aligns multiple observation markets/providers with exact sessions/timezones/freshness/missing policies and one separate execution target.", "GOLD/CRUDEOIL simultaneous-strategy and one-strategy/three-instrument fixtures preserve complete role, binding-input, provider and resource facts without leases/reservations.", "Standard/Pro/Desk at-limit and first-over classifications plus simultaneous conjunctive maxima pass/refuse exactly.", "All results reload after process death with exact graph, implementation, dataset, truth, policy, ResourcePlan, owner and job lineage."],
  "test_plan": ["Direct scenario fixtures through real registry/resolver/data/capability/research/lifecycle seams.", "SQLite and disposable PostgreSQL 16 persist/reload/consume traces.", "Tier/resource/provider/role complete matrices and refusal mutations.", "No broker/provider network/credential side effects.", "Integrated affected suites and frozen evidence manifest."],
  "review": {"required": false, "assignment_id": "phase5_scenario_gate_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/tests/test_phase5_canonical_scenarios.py", "paper-trader/backend/research_tests/test_phase5_canonical_scenarios.py", ".agent/runs/phase5-canonical-scenario-gate"], "exclude_paths": [], "output": ".agent/runs/phase5-canonical-scenario-gate/owner/report.md", "verdicts": ["SCENARIOS"]},
  "implementation": {"status": "accepted", "report_sha256": "811f56676851d9e3899b82f58dc8307dfe7d9b62cf41913f5af5740099367db1", "evidence_sha256": "7a855d6242ec031e1a28af691ce64e2d37c78695784399f038004cc074b5d8be", "deployability_sha256": "5a7c8441889caff3809723de4d23efa02c66c8dbacdc0840a132d7a49f1b5e59", "focused_passed": 44, "focused_skipped": 1, "postgresql16_passed": 1, "affected_passed": 232, "mutations": 5, "verdict": "SCENARIOS PASS"}
}
---

# Phase 5 canonical scenario gate

This gate proves architecture scenarios and exact nonclaims. It does not deploy or trade.
