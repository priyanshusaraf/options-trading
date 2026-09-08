---
{
  "id": "phase5-first-party-analytical-catalogue",
  "phase": "phase5",
  "status": "accepted",
  "kind": "catalogue_implementation",
  "goal": "Populate the sole production registry with the frozen V1 Type 2 and Type 4 analytical catalogue and prove every registered entry through one shared conformance harness.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after every V1_REQUIRED and supported capability-gated Type 2/4 inventory entry is registered once with its exact node/resource/data contract, all registered entries pass the shared reference/vector/prefix/warmup/invalidity/causality harness, unsupported entries refuse, and complete-registry mutations pass."},
  "risk_tags": ["important", "catalogue", "mathematics", "causality", "registry"],
  "required_docs": [{"path": "paper-trader/docs/reports/phase5-v1-catalogue.json", "sections": []}, {"path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md", "sections": ["First-party node contract", "Closed V1 catalogue inventory", "Verification and complete-universe gates"]}],
  "dependency_gate": "phase5-provider-evidence-compatibility",
  "additional_dependencies": ["phase5-adv-006-runtime-assurance", "phase5-language-resource-assurance"],
  "allowed_paths": ["paper-trader/backend/app/ir/first_party/analytical.py", "paper-trader/backend/app/ir/first_party/conformance.py", "paper-trader/backend/app/ir/library.py", "paper-trader/backend/tests/test_phase5_first_party_analytical_catalogue.py", ".agent/runs/phase5-first-party-analytical-catalogue", "paper-trader/docs/agent/tasks/phase5-first-party-analytical-catalogue.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "nonclaims": ["No Type 1/3/5, custom node, deployment, provider correctness, live, order, or money authority.", "Catalogue count alone is not acceptance."],
  "owner_gates": ["Stop before licence-sensitive adoption, network/provider work, a second registry/evaluator, or changed live semantics."],
  "stop_conditions": ["Inventory and registry differ; reference provenance is absent; vector/prefix parity, warmup, invalidity, causality, or resource declaration is sampled; a deferred or unsupported entry is silently enabled."],
  "deployment_impact": {"classification": "compatible", "required_evidence": "Reproducible dependency/licence inventory and registry identity coexistence; worker packaging remains later."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["The production v2 registry equals the claimed Type 2/4 inventory and has no undeclared entry.", "Each component has one implementation, exact 22-field contract, family/resource/data declarations, output mapping and reference provenance.", "Independent golden/reference, vector, prefix-stream, warmup, invalidity, causal-prefix, reorder, and deterministic-result cases pass through one harness.", "Capability-gated fields refuse without accepted facts and preserve supplied-versus-derived attribution.", "Deleting a registry entry, implementation, conformance row, family, resource profile, output, or reference makes the normal gate fail."],
  "test_plan": ["Inventory-to-registry exact set comparison.", "Shared conformance matrix per registered entry.", "Representative independent mathematical vectors per subgroup.", "Batch/prefix/warmup/invalidity/causality adversarial cases.", "Complete-universe killed/restored mutations and subsystem tests."],
  "review": {"required": false, "assignment_id": "phase5_analytical_catalogue_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/review-package.json", "review_paths": ["paper-trader/backend/app/ir/first_party/analytical.py", "paper-trader/backend/app/ir/first_party/conformance.py", "paper-trader/backend/app/ir/library.py", "paper-trader/backend/tests/test_phase5_first_party_analytical_catalogue.py"], "exclude_paths": [], "output": ".agent/runs/phase5-first-party-analytical-catalogue/owner/report.md", "verdicts": ["CATALOGUE"]},
  "result": {"verdict": "CATALOGUE PASS", "report": ".agent/runs/phase5-first-party-analytical-catalogue/owner/report.md", "report_sha256": "2d4747037f6063f160dbee11e4762f9c8e7ca02fbe394f7c008d7db99d9394ce", "deployability": ".agent/runs/phase5-first-party-analytical-catalogue/owner/deployability.md", "deployability_sha256": "913cf6e59c615c73f91bfd28bf861709ffd2debb71dd0cc4f38e5e4b8cabb62e", "entries": 125, "conformance_passed": 169, "mutations": 1}
}
---

# Phase 5 analytical catalogue

This capsule implements only the frozen Type 2/4 inventory in the sole registry.
