---
{
  "id": "phase5-state-execution-derivatives-catalogue",
  "phase": "phase5",
  "status": "accepted",
  "kind": "critical_correction",
  "goal": "Close the exhausted Type 3 accepted-authority and canonical state-snapshot findings without changing the accepted catalogue semantics or adding runtime authority.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after P5-SED-001 and P5-SED-003 have direct hostile evidence, the inherited 571-check gate remains green, new guards have killed/restored mutations, and one fresh critical-review lineage returns SPEC PASS and QUALITY PASS."},
  "risk_tags": ["critical", "catalogue", "authority", "state", "causality"],
  "required_docs": [{"path": "paper-trader/docs/reports/phase5-v1-catalogue.json", "sections": []}, {"path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md", "sections": ["Canonical role and binding-input vocabulary", "Research execution and cache boundary", "Closed V1 catalogue inventory"]}],
  "dependency_gate": "phase5-first-party-analytical-catalogue",
  "historical_failed_capsule": "paper-trader/docs/agent/tasks/phase5-state-execution-derivatives-catalogue.md",
  "immutable_first_verdict_sha256": "d3e70f76eb1c79ad1d275ea5d772f32bba7122983d5642b057601121433290a0",
  "immutable_recheck_verdict_sha256": "07cfbe4c40d35cfcdbeb0b87aa36eeebe62fa087daa4414b72decb036ce71293",
  "open_findings": ["P5-SED-001", "P5-SED-003"],
  "closed_frozen_findings": ["P5-SED-002", "P5-SED-004"],
  "allowed_paths": ["paper-trader/backend/app/ir/first_party/logic_state.py", "paper-trader/backend/tests/test_phase5_state_execution_derivatives_catalogue.py", ".agent/runs/phase5-state-authority-snapshot-correction", "paper-trader/docs/agent/tasks/phase5-state-authority-snapshot-correction.md", "paper-trader/docs/agent/tasks/phase5-state-execution-derivatives-catalogue.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "protected_paths": ["paper-trader/backend/app/ir/first_party/analytical.py", "paper-trader/backend/app/ir/first_party/derivatives.py", "paper-trader/backend/app/ir/first_party/execution_intent.py", "paper-trader/backend/app/ir/library.py", "paper-trader/backend/app/ir/node_contracts.py", "paper-trader/backend/app/ir/resource_plan.py", "paper-trader/backend/app/ir/validity.py", "paper-trader/backend/app/market_data/capability.py"],
  "nonclaims": ["Transient evaluator contexts carry already accepted facts and create no persisted or execution authority.", "Type 1 remains description-only and Type 5 accepted semantics remain frozen.", "No provider networking, broker, order, live, money, deployment, production, frontend, or Phase 6 claim."],
  "owner_gates": ["Stop before changing any persisted authority, runtime consumer, schema, provider route, broker/protection behavior, sizing/routing/risk behavior, order path, live state, or money behavior."],
  "stop_conditions": ["A context can be supplied through graph inputs or authored parameters; a local/provider declaration disagrees; a noncanonical snapshot restores; any closed finding regresses; any successor work starts before fresh dual review pass."],
  "deployment_impact": {"classification": "architecture-changing", "required_evidence": "Pure registry evaluation only; locally runnable is the highest allowed claim."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["All Type 3 node contracts, declarations, roles, policies and capability facts agree exactly on local versus provider supply.", "Type 3 facts match a keyword-only immutable evaluator context; coordinated graph-input readdressing and input-carried context substitution refuse.", "Restore requires the exact canonical StateSnapshot and complete reconstruction, then matches a keyword-only immutable restore context pinned to the accepted snapshot and next causal event.", "Incomplete duck objects and coordinated snapshot/context mutations refuse; snapshot last-event, creation-evidence and reset facts are consumed.", "The inherited 571 checks and new hostile/mutation matrix pass without changing P5-SED-002 or P5-SED-004 behavior."],
  "test_plan": ["Complete 63-operation local/provider agreement matrix.", "Coordinated Type 3 authority replacement and missing/out-of-band context refusals.", "Exact StateSnapshot type/reconstruction and trusted restore-context hostile matrix.", "Inherited 571-check replay plus killed/restored context and snapshot mutations."],
  "review": {"required": true, "assignment_id": "phase5_state_authority_snapshot_fresh_reviewer", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "base_sha": "HEAD", "package": ".agent/runs/phase5-state-authority-snapshot-correction/review-package.json", "review_paths": ["paper-trader/backend/app/ir/first_party/logic_state.py", "paper-trader/backend/tests/test_phase5_state_execution_derivatives_catalogue.py"], "exclude_paths": [], "output": ".agent/runs/phase5-state-authority-snapshot-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "implementation": {"status": "accepted", "report_sha256": "d4a6b41b2d3a87031c8d1d85556b95fcbd95214b813ac98077863c2e3109d46e", "deployability_sha256": "e472d43d3517de3437418dca4af87b2f4b96d6b7b267602bdabdfbd2fc8a7c97", "evidence_sha256": "0e5cb4af0ce90f161dc47112acbf660116f33690a63f0faa51638021ecf1279e", "integrated_passed": 643, "mutations": 3, "logic_state_sha256": "31ea8e62e1d07cce07a53ccef21bf1411ca7727d3f584c73ed4644c815250463", "test_sha256": "7c8aeb936f267cd144f0bff7f073c66b42d1fb2d8ccd9b6baef87b9f87b189f3"},
  "review_result": {"spec": "PASS", "quality": "PASS", "overall": "PASS", "package_sha256": "c36604d0631cf45dbdcaaa75170741bb0e31954e1683acb3f6292b761faab14f", "verdict": ".agent/runs/phase5-state-authority-snapshot-correction/review/verdict.json", "verdict_sha256": "8f5a5701cc260488ff6a0f81b6865079480e7b12a510364638117981728e853a", "open_findings": 0}
}
---

# Phase 5 Type 3 authority and canonical snapshot correction

This is the owner-authorized fresh correction lineage after the prior review and sole
recheck failed. It cannot broaden into runtime consumption or Phase 6.
