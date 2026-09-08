---
{
  "id": "phase5-custom-node-contracts",
  "phase": "phase5",
  "status": "failed_recheck_exhausted",
  "kind": "custom_node_contract",
  "goal": "Implement closed admission and resource contracts for fork, formula, sandboxed-Python and external-signal nodes while keeping Level 3/4 runtime disabled without a separate security owner gate.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after all four levels have immutable lineage, family/resource/data/causal contracts, forbidden capabilities fail closed, Levels 1/2 pass conformance, and Levels 3/4 remain runtime-disabled unless separately owner-authorized."},
  "risk_tags": ["critical", "custom-code", "security", "tenancy", "causality"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md", "sections": ["First-party node contract", "Canonical ResourcePlan schema", "Closed V1 catalogue inventory"]}],
  "dependency_gate": "phase5-state-execution-derivatives-catalogue",
  "additional_dependencies": ["phase5-adv-006-runtime-assurance", "phase5-language-resource-assurance"],
  "allowed_paths": ["paper-trader/backend/app/ir/custom_nodes.py", "paper-trader/backend/tests/test_phase5_custom_node_contracts.py", ".agent/runs/phase5-custom-node-contracts", "paper-trader/docs/agent/tasks/phase5-custom-node-contracts.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "nonclaims": ["No executable arbitrary Python, external network listener, broker access, credentials, live, order, or money authority.", "Level 3/4 contract acceptance is not runtime enablement."],
  "owner_gates": ["Stop before enabling Python execution or external ingress, adopting sandbox dependencies, network/secret access, provider/broker connections, or commercial external-signal scope."],
  "stop_conditions": ["A node lacks family/resource bounds; hidden data/network/import/broker access is possible; another tenant is readable; causal policy is bypassed; Level 3/4 becomes executable without the explicit security gate."],
  "deployment_impact": {"classification": "architecture-changing", "required_evidence": "Contract-only local behavior; future sandbox/network service, security, configuration, health, observability and capacity remain separately owner-gated."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["All four levels have closed immutable lineage and exact node/resource/data/causal contracts.", "Forks inherit and version the source contract; formulas use only declared typed inputs.", "Missing family/profile, unbounded rate/state, unknown import, filesystem/network/broker access, cross-tenant lookup, and direct order paths refuse.", "Levels 3/4 return typed runtime-unavailable decisions until a future security capsule and owner gate pass."],
  "test_plan": ["Closed schema and content-address vectors.", "Fork/formula conformance and lineage.", "Forbidden import/network/filesystem/broker/tenant/causality mutation corpus.", "CPU/memory/state/rate bound and unavailable-runtime tests."],
  "review": {"required": true, "assignment_id": "phase5_custom_node_reviewer", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "base_sha": "HEAD", "package": ".agent/runs/phase5-custom-node-contracts/review-package.json", "review_paths": ["paper-trader/backend/app/ir/custom_nodes.py", "paper-trader/backend/tests/test_phase5_custom_node_contracts.py"], "exclude_paths": [], "output": ".agent/runs/phase5-custom-node-contracts/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "implementation": {"status": "corrected_evidence_ready", "report_sha256": "73a350323c588a6314a0b22d5694d902853c42145201b25cdaeb9b11dea93116", "deployability_sha256": "c4e012602d5d6b8298bb5be5b839d9bd3f82d038dcf96aadddb30aef41c39215", "evidence_sha256": "dbf0ce739deea48ad63a4399e53f8ebc70d6b752d8ebf6925dc944c87ca97cd3", "focused_passed": 69, "integrated_passed": 565, "mutations": 4, "product_sha256": "f2fb0b7de1c9aaced0f8644cfdf01608f98f4c47904a82d0a20d4766475f4a06", "test_sha256": "e4fd0511d7a218e6451378505dfe3f9077b7a9c028016a58b08f80bbb1571f7b"},
  "first_review": {"spec": "FAIL", "quality": "FAIL", "overall": "FAIL", "package_sha256": "47cd42deedde905a8980b604219ff1b472715e8c9cc36e9b673d661924380d8a", "verdict": ".agent/runs/phase5-custom-node-contracts/review/verdict.json", "verdict_sha256": "9f19deebd8468afa4d7f6e9024a9c85c39af6a2f804a54c50df60ce7642bf690", "findings": ["P5-CN-001", "P5-CN-002", "P5-CN-003", "P5-CN-004"], "rechecks_remaining": 1},
  "correction": {"status": "failed_recheck_exhausted", "report_sha256": "d6f7b1568a534fb0706b5e9e46bd50a28f37fc86b0c53f7426ca7e2a3ab93e2f", "evidence_sha256": "275053ad90c547c31feb352acf806539797a8bacf4f73725457c4034212e98f7"},
  "recheck": {"spec": "FAIL", "quality": "FAIL", "overall": "FAIL", "package_sha256": "67dbd994a01d76181934182f4b7746dca2ab925c5024cd1397787127b4648dd8", "verdict": ".agent/runs/phase5-custom-node-contracts/review/recheck-verdict.json", "verdict_sha256": "6ec153b1e09222bff2677cbb8c754b18db05fef69c9724dc5c66d894289f6c68", "open_findings": ["P5-CN-001", "P5-CN-002"], "closed_findings": ["P5-CN-003", "P5-CN-004"], "rechecks_remaining": 0, "successor": "paper-trader/docs/agent/tasks/phase5-custom-node-authority-recovery.md"}
}
---

# Phase 5 custom-node contracts

Levels 3 and 4 remain runtime-disabled. Enabling code execution or network ingress requires a new explicit security and owner gate.
