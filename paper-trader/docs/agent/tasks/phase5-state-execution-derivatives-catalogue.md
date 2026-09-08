---
{
  "id": "phase5-state-execution-derivatives-catalogue",
  "phase": "phase5",
  "status": "failed_recheck_exhausted",
  "kind": "catalogue_implementation",
  "goal": "Implement the frozen V1 Type 1, Type 3 and Type 5 intent, derivative, logic, temporal, validity and state catalogue in the sole registry without broker calls or runtime authority.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after every claimed entry and supported capability-gated entry is registered with exact contracts, selectors use point-in-time accepted facts, state/reset and validity semantics pass batch/prefix conformance, Type 1 lowers to intent only, and all unsupported capability paths refuse."},
  "risk_tags": ["critical", "catalogue", "execution-intent", "derivatives", "state", "causality"],
  "required_docs": [{"path": "paper-trader/docs/reports/phase5-v1-catalogue.json", "sections": []}, {"path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md", "sections": ["Canonical role and binding-input vocabulary", "Research execution and cache boundary", "Closed V1 catalogue inventory"]}],
  "dependency_gate": "phase5-first-party-analytical-catalogue",
  "additional_dependencies": ["phase5-adv-006-runtime-assurance", "phase5-language-resource-assurance", "phase5-provider-evidence-compatibility"],
  "allowed_paths": ["paper-trader/backend/app/ir/first_party/execution_intent.py", "paper-trader/backend/app/ir/first_party/derivatives.py", "paper-trader/backend/app/ir/first_party/logic_state.py", "paper-trader/backend/app/ir/library.py", "paper-trader/backend/tests/test_phase5_state_execution_derivatives_catalogue.py", "paper-trader/backend/tests/test_phase5_first_party_analytical_catalogue.py", ".agent/runs/phase5-state-execution-derivatives-catalogue", "paper-trader/docs/agent/tasks/phase5-state-execution-derivatives-catalogue.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "nonclaims": ["Type 1 produces intent descriptions only; no broker, routing, live, order, or money authority.", "Capability-gated derivatives/order-book/trade-flow nodes may remain unsupported.", "No provider breadth or current-market-as-history claim."],
  "owner_gates": ["Stop before material sizing/routing/risk/execution changes, broker/protection adoption, provider/network work, licence-sensitive code, or money behavior."],
  "stop_conditions": ["Any intent calls engine/broker code; selector uses current contracts as history; aggressor flow is inferred without evidence; state reset/parity universe is incomplete; unsupported capability silently falls back."],
  "deployment_impact": {"classification": "architecture-changing", "required_evidence": "Pure registry/runtime modules only at this slice; provider, service and live topology remain unchanged and gated."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["The production registry equals the claimed Type 1/3/5 inventory with exact contracts and no hidden entry.", "Type 1 emits typed intent and never imports broker, venue, engine or money modules.", "Derivative selectors bind canonical roles, point-in-time rulebook facts, dynamic-window bounds and provider requirements.", "Provider-supplied and locally derived analytics remain distinct; unsupported trade-flow/depth/Greeks/OI refuse.", "Logic, temporal, scheduling, validity and state primitives pass truth, causal-prefix, restart/reset and batch/stream conformance.", "Risk-reducing exits remain expressible under every entry-blocking state."],
  "test_plan": ["Exact inventory/registry comparison and no forbidden imports.", "Point-in-time options/futures/ladder selector fixtures and unsupported capability refusals.", "Intent golden lowering without side effects.", "Truth tables, invalid domains, temporal prefixes and reset/restart state matrix.", "Killed/restored complete-universe and no-fallback mutations."],
  "review": {"required": true, "assignment_id": "phase5_state_execution_derivatives_reviewer", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "base_sha": "HEAD", "package": ".agent/runs/phase5-state-execution-derivatives-catalogue/review-package.json", "review_paths": ["paper-trader/backend/app/ir/first_party", "paper-trader/backend/app/ir/library.py", "paper-trader/backend/tests/test_phase5_state_execution_derivatives_catalogue.py"], "exclude_paths": [], "output": ".agent/runs/phase5-state-execution-derivatives-catalogue/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "first_review": {"spec": "FAIL", "quality": "FAIL", "overall": "FAIL", "package_sha256": "dc2313737cbca885193feda8a4e18010171a6c1bfecec1cede7066e26c8773d7", "verdict": ".agent/runs/phase5-state-execution-derivatives-catalogue/review/verdict.json", "verdict_sha256": "d3e70f76eb1c79ad1d275ea5d772f32bba7122983d5642b057601121433290a0", "findings": ["P5-SED-001", "P5-SED-002", "P5-SED-003", "P5-SED-004"], "rechecks_remaining": 1},
  "correction": {"status": "failed_recheck_exhausted", "write_paths": ["paper-trader/backend/app/ir/first_party/logic_state.py", "paper-trader/backend/tests/test_phase5_state_execution_derivatives_catalogue.py"], "required": "accepted point-in-time Type 3 facts, exact Type 5 semantics/domains, snapshot/reset/restart parity, and non-vacuous semantic mutations"},
  "recheck": {"spec": "FAIL", "quality": "FAIL", "overall": "FAIL", "package": ".agent/runs/phase5-state-execution-derivatives-catalogue/recheck-package.json", "package_sha256": "f5b53b2545238afec4d2ad0a6f74121b69366852649b656513c27160ecd8e7ee", "verdict": ".agent/runs/phase5-state-execution-derivatives-catalogue/review/recheck-verdict.json", "verdict_sha256": "07cfbe4c40d35cfcdbeb0b87aa36eeebe62fa087daa4414b72decb036ce71293", "open_findings": ["P5-SED-001", "P5-SED-003"], "closed_findings": ["P5-SED-002", "P5-SED-004"], "rechecks_remaining": 0, "successor": "paper-trader/docs/agent/tasks/phase5-state-authority-snapshot-correction.md"}
}
---

# Phase 5 state, execution-intent and derivatives catalogue

All execution-facing entries remain intent descriptions. This capsule cannot call a broker or grant money authority.
