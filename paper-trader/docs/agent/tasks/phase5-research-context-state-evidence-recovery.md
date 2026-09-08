---
{
  "id": "phase5-research-context-state-evidence-recovery",
  "phase": "phase5",
  "status": "failed_review_owner_replan_required",
  "kind": "critical_evidence_recovery",
  "goal": "Close P5-RCSB-REV-001 and P5-RCSB-REV-002 without changing product, tests or catalogue semantics by sealing protected hashes and assigning every deployability obligation to an exact capsule owner.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after complete protected pre/post manifests match, the frozen 525-case golden gate passes, exact future deployment owners are recorded, all product/test hashes remain unchanged, and fresh critical review returns SPEC PASS and QUALITY PASS."},
  "risk_tags": ["critical", "read-only", "research", "deployability", "evidence"],
  "required_docs": [{"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Phase 5 ownership", "Phase 6 ownership", "Phase 7 ownership", "V1 release gate"]}],
  "dependency_gate": "phase5-research-context-state-boundary-recovery",
  "failed_review": {"path": ".agent/runs/phase5-research-context-state-boundary-recovery/review/verdict.json", "sha256": "466d64a026e525c9246cdcab07bc7cfb57b52a6a6862039e7ac86241c803f2b5", "findings": ["P5-RCSB-REV-001", "P5-RCSB-REV-002"]},
  "replan": {"path": ".agent/runs/phase5-research-context-state-evidence-replan/report.md", "sha256": "a2b7094a5d5a9cab907114c3e36928a1002d0ccb6dca9543f2b69b37eee44252", "decision": "KEEP BYTES + COMPLETE EVIDENCE"},
  "allowed_paths": [".agent/runs/phase5-research-context-state-evidence-recovery", "paper-trader/docs/agent/tasks/phase5-research-context-state-evidence-recovery.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "protected_paths": ["paper-trader/backend/app/ir/first_party", "paper-trader/backend/tests/test_phase5_first_party_analytical_catalogue.py", "paper-trader/backend/tests/test_phase5_state_execution_derivatives_catalogue.py", "paper-trader/backend/app/ir/runtime.py", "paper-trader/backend/app/ir/streaming_reference.py", "paper-trader/backend/app/ir/incremental_runtime.py", "paper-trader/backend/research/evaluation/phase5_runtime.py", "paper-trader/backend/research_tests/test_phase5_research_execution.py"],
  "nonclaims": ["No product/test/catalogue change, parity acceptance, deployment, provider, live, order or money claim."],
  "owner_gates": ["Stop on any protected hash mismatch or behavioral failure; do not rerun parity assurance until fresh review passes."],
  "deployment_impact": {"classification": "read-only evidence recovery", "required_evidence": "Exact ownership mapping only; no operational change or deployment."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["Every protected catalogue implementation and golden test path has exact pre/post SHA-256 and the manifests match.", "The 525-case frozen catalogue gate passes between manifests.", "All five reviewed recovery paths retain the failed review's exact hashes.", "Queue/cache/artifact, packaging/restart/health, deployment foundation, capacity/economics, release rehearsal and actual deployment each have an exact capsule or gate owner.", "Fresh review returns SPEC PASS and QUALITY PASS without product/test changes."],
  "test_plan": ["Protected manifest before and after.", "525-case catalogue golden replay.", "Failed-review scoped hash preservation.", "Deployability-owner mapping validation.", "Fresh critical review."],
  "review": {"required": true, "assignment_id": "phase5_research_context_state_evidence_recovery_reviewer", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "base_sha": "HEAD", "package": ".agent/runs/phase5-research-context-state-evidence-recovery/review-package.json", "review_paths": [".agent/runs/phase5-research-context-state-evidence-recovery", "paper-trader/docs/agent/DEPLOYABILITY.md"], "exclude_paths": [], "output": ".agent/runs/phase5-research-context-state-evidence-recovery/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 0},
  "implementation": {"status": "historical_anchor_gap", "report_sha256": "71610b468341a384bb5dd1b9e374aefff0f7d3b93d9538ac5bc998622ea6302a", "evidence_sha256": "00c349574a377bc5d308508e5a93680c84caa0d63c146d9ece45e249727b9687", "protected_manifest_sha256": "ac984bc3611ea0ead1f26fddbf7324c874e06fbe2295f77bf75064abbb2c1642", "protected_paths": 13, "golden_passed": 525, "ownership_dimensions": 7, "product_test_changes": 0},
  "review_result": {"spec": "UNVERIFIABLE", "quality": "FAIL", "overall": "FAIL", "package_sha256": "b85b24550761a3df0d4d2d8239b252a9c742a1154b4e95a401417fd9d47d75fa", "verdict": ".agent/runs/phase5-research-context-state-evidence-recovery/review/verdict.json", "verdict_sha256": "5a154f5f2385309256ebbd8b3f8cda66bdf296c2686d1725a7814b18a78f9934", "closed_findings": ["P5-RCSB-REV-002"], "open_findings": ["P5-RCSB-REV-001"], "successor": "paper-trader/docs/agent/tasks/phase5-research-semantic-baseline-recovery.md"}
}
---

# Phase 5 research context/state evidence recovery

Product, tests and catalogue semantics are immutable in this evidence-only recovery.
