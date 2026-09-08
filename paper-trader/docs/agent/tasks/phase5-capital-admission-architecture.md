---
{
  "id": "phase5-capital-admission-architecture",
  "phase": "phase5",
  "status": "accepted",
  "goal": "Freeze the Phase 5 sizing, target-position, deterministic simultaneous portfolio-admission, campaign/tranche and transactional capital-reservation architecture without changing money behavior.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The 24 August programme rebase assigns the owner-mandated Phase 5 capital foundation to a bounded architecture capsule after the graph-address and v2 runtime lifecycle gates. Architecture work may specify schemas, migrations, APIs, tests and owner gates, but cannot implement or enable sizing, routing, risk, execution, orders or money.",
    "stopping_condition": "Complete only after one additive design and dependency-ordered implementation plan freeze sizing hierarchy, dynamic numeric inputs, target-position semantics, pending-order awareness, Execution Product Policy seam, campaign/tranche ownership, DecisionBatch, PortfolioAdmissionDecision, CapitalReservation, stable tie-breakers, PostgreSQL transaction/recovery behavior, receipts, migrations, rollback, deployability and one exact critical-review route."
  },
  "risk_tags": ["critical", "architecture", "money", "capital-concurrency", "sizing", "migration"],
  "required_docs": [
    {"path": "paper-trader/docs/strategy-os-v1-v2-v3/REVISED-V1-PROGRESS-MAPPER-2026-08-24.md", "sections": ["Phase 5 — execution identity, sizing and deterministic capital admission"]},
    {"path": "paper-trader/docs/strategy-os-v1-v2-v3/architecture/CAPITAL-CONTENTION-AND-RESERVATION-SPEC.md", "sections": ["Decision", "Durable facts", "Concurrency proof", "Recovery", "Required tests"]},
    {"path": "paper-trader/docs/strategy-os-v1-v2-v3/CONTRACT-AND-ADR-PLAN.md", "sections": ["ADRs required before implementation", "Minimum contract shapes"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Open obligations", "Phase 5 ownership", "V1 release gate"]}
  ],
  "dependency_gate": "phase5-adv-006-runtime-assurance",
  "allowed_paths": ["paper-trader/docs/superpowers/specs/phase5-capital-admission-design.md", "paper-trader/docs/superpowers/plans/phase5-capital-admission.md", "paper-trader/docs/engineering/decisions/0016-execution-product-policy.md", "paper-trader/docs/engineering/decisions/0017-sizing-target-position-and-reservation.md", "paper-trader/docs/engineering/decisions/0018-position-campaign-tranche-lineage.md", "paper-trader/docs/agent/tasks", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md", ".agent/runs/phase5-capital-admission-architecture"],
  "nonclaims": ["No schema, product, frontend, provider, credential, deployment, production, live, sizing, routing, risk, execution, order, or money behavior changes.", "Architecture acceptance will not authorize implementation or live activation."],
  "owner_gates": ["Stop before any material live sizing/routing/risk/execution decision, broker behavior, order, money, destructive migration, deployment, production or customer-capital claim."],
  "stop_conditions": ["A design creates a second money, position, deployment, provider, strategy or research authority.", "Risk-reducing exits depend on a new entry reservation.", "A concurrent admission claim lacks direct PostgreSQL transaction/recovery evidence and a reversible guard mutation plan."],
  "deployment_impact": {"classification": "architecture-changing", "required_evidence": "Assign exact empty-install/upgrade/restart/restore/rollback, service, health, security, observability, capacity and cutover evidence to generated implementation capsules; no vague release deferral."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "default", "root_owner_recommendation": "gpt-5.6-sol xhigh"},
  "parallel_budget": 2,
  "assignments": [],
  "architecture": {"decision": "KEEP + HARDEN", "design": "paper-trader/docs/superpowers/specs/phase5-capital-admission-design.md", "design_sha256": "fb580f955b6d772597c06dd051d923224c6e05e41797c31670517f3e916a5f67", "plan": "paper-trader/docs/superpowers/plans/phase5-capital-admission.md", "plan_sha256": "860f6ec069a1ff4774f199adde705f761dc66aa5219aada28ec59ee0db719f03", "adrs": [{"path": "paper-trader/docs/engineering/decisions/0016-execution-product-policy.md", "sha256": "71d93f19239f94e5fed1f2610115a53515486aab2161fd7a59aa5875c993237e"}, {"path": "paper-trader/docs/engineering/decisions/0017-sizing-target-position-and-reservation.md", "sha256": "6ec58e799bdacbc3c63dc33db4797fe602684490e6ec4051b5ba4e8f8650646d"}, {"path": "paper-trader/docs/engineering/decisions/0018-position-campaign-tranche-lineage.md", "sha256": "e5b2863008350deffeca68a8a717ca88ae261c305384ec0b61276aafd1a812e0"}], "audit": ".agent/runs/phase5-capital-admission-architecture/audit.json", "audit_sha256": "7d2976881fcc0f74b860f6851e0243cf5b36c762ad1208855f58de2adb071346", "matrix": ".agent/runs/phase5-capital-admission-architecture/matrix.json", "matrix_sha256": "b2b359a7fc9c0c7d4d7362c4a155e268587e3a205f7524b41bab401fa5609f3c", "behavior_switch": false, "live_authority": false},
  "acceptance": ["One sizing and target-position contract preserves current supported behavior and exact pending-order/position identity.", "One durable DecisionBatch/PortfolioAdmissionDecision/CapitalReservation model owns deterministic simultaneous admission under the existing account lease/fence.", "Campaign/tranche lineage remains additive and never infers unsupported historical facts.", "Every implementation and assurance slice has exact paths, failures, tests, migration, rollback and owner gates."],
  "test_plan": ["Repository object and money-flow audit", "PostgreSQL transaction/fence architecture cases", "Crash and broker-uncertainty failure model", "Sizing/rounding/pending-order parity matrix", "Reversible lock/fence/silent-resize/exit-availability mutation plan", "Structured programme and diff validation"],
  "review": {"required": false, "assignment_id": "phase5_capital_architecture_handoff", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/runs/phase5-capital-admission-architecture/review-package.md", "review_paths": ["paper-trader/docs/superpowers/specs/phase5-capital-admission-design.md", "paper-trader/docs/superpowers/plans/phase5-capital-admission.md"], "exclude_paths": [], "output": ".agent/runs/phase5-capital-admission-architecture/handoff.json", "verdicts": ["BOUND"], "max_rechecks": 0},
  "result": {"verdict": "BOUND", "status": "PASS", "handoff": ".agent/runs/phase5-capital-admission-architecture/handoff.json", "handoff_sha256": "333426b4c77144775fbbda43708ae7b8348233b302efbc5c7fffde16a393c817", "report": ".agent/runs/phase5-capital-admission-architecture/report.md", "report_sha256": "2cae136483d9b5a144d562848fe2dd4fda64143319fbda653d998316c7d4201d", "product_test_manifest_sha256": "53f154edb2de082c5b34bc747e35e9a9cc4cb097c6454fd350b8fffd635d4622"}
}
---

# Phase 5 capital-admission architecture

This capsule is ready after accepted runtime assurance. It is the next architecture gate after the graph-address/runtime debt and does not authorize product or money behavior.
