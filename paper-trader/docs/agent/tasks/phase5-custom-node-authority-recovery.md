---
{
  "id": "phase5-custom-node-contracts",
  "phase": "phase5",
  "status": "accepted",
  "kind": "critical_correction",
  "goal": "Close custom-admission reconstruction and transitive-lineage authority gaps by retaining replayable typed proof while Levels 3/4 remain unavailable.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after P5-CN-001/P5-CN-002 have direct private/object reconstruction refusals, inherited gates and closed findings remain green, new mutations are killed/restored, and one fresh critical-review lineage returns SPEC PASS and QUALITY PASS."},
  "risk_tags": ["critical", "custom-code", "authority", "tenancy", "lineage", "security"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md", "sections": ["First-party node contract", "Canonical ResourcePlan schema", "Closed V1 catalogue inventory"]}],
  "dependency_gate": "phase5-state-execution-derivatives-catalogue",
  "historical_failed_capsule": "paper-trader/docs/agent/tasks/phase5-custom-node-contracts.md",
  "immutable_first_verdict_sha256": "9f19deebd8468afa4d7f6e9024a9c85c39af6a2f804a54c50df60ce7642bf690",
  "immutable_recheck_verdict_sha256": "6ec153b1e09222bff2677cbb8c754b18db05fef69c9724dc5c66d894289f6c68",
  "open_findings": ["P5-CN-001", "P5-CN-002"],
  "closed_frozen_findings": ["P5-CN-003", "P5-CN-004"],
  "allowed_paths": ["paper-trader/backend/app/ir/custom_nodes.py", "paper-trader/backend/tests/test_phase5_custom_node_contracts.py", ".agent/runs/phase5-custom-node-authority-recovery", "paper-trader/docs/agent/tasks/phase5-custom-node-authority-recovery.md", "paper-trader/docs/agent/tasks/phase5-custom-node-contracts.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "protected_paths": ["paper-trader/backend/app/ir/node_contracts.py", "paper-trader/backend/app/ir/resource_plan.py", "paper-trader/backend/app/ir/validity.py", "paper-trader/backend/app/ir/first_party/logic_state.py", "paper-trader/backend/tests/test_phase5_state_execution_derivatives_catalogue.py"],
  "nonclaims": ["Retained proof replays admission but creates no persisted or execution authority.", "Level 3 static replay is not sandbox security; Level 4 contract replay is not ingress authentication.", "No provider, broker, credential, order, live, money, deployment, production, frontend, or Phase 6 claim."],
  "owner_gates": ["Stop before executing Python, adding sandbox dependencies, external ingress, listeners, authentication services, server tenant integration, provider/broker access, orders, live state, or money behavior."],
  "stop_conditions": ["A wrapper validates without exact retained proof; a fork cannot reconstruct full source ancestry; an inner Level 3/4 address is not bound to lineage/provenance; Level 3/4 becomes executable; P5-CN-003/P5-CN-004 regresses."],
  "deployment_impact": {"classification": "architecture-changing", "required_evidence": "Pure in-process admission replay; locally runnable is the highest claim."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Level 1 retains and recursively validates the exact source admission, inherited contracts, formula, version and full transitive lineage.", "Level 3 retains source text only as non-executed proof, reruns the exact static scan, and binds its derived source address to admission lineage and node provenance.", "Level 4 binds schema/auth/replay addresses to both admission lineage and node provenance and reconstructs the exact stored contract.", "Private-factory and object reconstruction with substituted source/provenance or dropped lineage refuse before evaluation.", "Levels 3/4 remain runtime-unavailable and closed ImportFrom/short-circuit behavior remains unchanged."],
  "test_plan": ["Private/object fork-source substitution and transitive-lineage-drop corpus across multiple generations.", "Level 3 retained-source re-scan and source-address/provenance substitution refusals.", "Level 4 schema/auth/replay lineage/provenance substitution refusals.", "Inherited focused/integrated replay plus killed/restored retained-proof guards."],
  "review": {"required": true, "assignment_id": "phase5_custom_node_authority_fresh_reviewer", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "base_sha": "HEAD", "package": ".agent/runs/phase5-custom-node-authority-recovery/review-package.json", "review_paths": ["paper-trader/backend/app/ir/custom_nodes.py", "paper-trader/backend/tests/test_phase5_custom_node_contracts.py"], "exclude_paths": [], "output": ".agent/runs/phase5-custom-node-authority-recovery/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "implementation": {"status": "accepted", "report_sha256": "82ff62a43d35ffde45b92db1f186768125a89c9d3c0b1c8df8d2c231770710a1", "deployability_sha256": "420647aab0a3601fef3aa6b57ec9ca9c9eddca5d924384343a35a72c6a01a067", "evidence_sha256": "d4723f77dbe84a3e078a1c136ff7beae929974b3a17a8cb6ab72caf64e24212c", "focused_passed": 76, "integrated_passed": 572, "mutations": 3, "product_sha256": "7e6bc8d63f3696a4cee4afd0db4b9f9ff8283f32ec0c7ac8e724ee5e984cbf1c", "test_sha256": "43c98cb020380779cbf03fc9566024b7850685c72e7b15b766ca4a96870d4a89"},
  "review_result": {"spec": "PASS", "quality": "PASS", "overall": "PASS", "package_sha256": "f5e077a1a0049a0a40d0a65e532d7851a350981c17e2ff619e032d2ba1a73060", "verdict": ".agent/runs/phase5-custom-node-authority-recovery/review/verdict.json", "verdict_sha256": "9e6081641ee82fd434e6914f25db7c7464aa1a2dcc0e5242da90251c7c4b454b", "open_findings": 0}
}
---

# Phase 5 custom-node authority recovery

This fresh correction lineage retains replayable proof and cannot enable custom-code or
external-signal runtime behavior.
