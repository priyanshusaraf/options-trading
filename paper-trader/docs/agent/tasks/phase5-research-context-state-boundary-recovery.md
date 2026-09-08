---
{
  "id": "phase5-research-context-state-boundary-recovery",
  "phase": "phase5",
  "status": "failed_review_evidence_recovery_required",
  "kind": "research_parity_recovery",
  "goal": "Close P5-RPA-001 and P5-RPA-002 so every registered Type 3 and recursive Type 5 component executes through the accepted vector/incremental research boundary with exact context, causal event and immutable result provenance.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after all 63 Type 3 and 18 recursive Type 5 nodes pass accepted-boundary parity against frozen independent semantics, hostile contexts and nested event mismatches refuse, all prior research findings remain closed, and fresh critical review passes."},
  "risk_tags": ["critical", "research", "parity", "causality", "state", "authority"],
  "required_docs": [{"path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md", "sections": ["Research execution and cache boundary", "Verification and complete-universe gates"]}],
  "dependency_gate": "phase5-research-execution",
  "historical_assurance": {"capsule": "paper-trader/docs/agent/tasks/phase5-research-parity-assurance.md", "report_sha256": "0283012d0343be3b682b2bfbeacfe833ffa9cd2322106be57f79da9f31d8cad3", "evidence_sha256": "46e4d24971036e58b48b839b19f196e5759d0f1ab45cc4989f3a9190b9459b6d", "findings": ["P5-RPA-001", "P5-RPA-002"]},
  "replan": {"path": ".agent/runs/phase5-research-complete-boundary-replan/report.md", "sha256": "22670079501558d14cd848929e1e45dc8055fd69bcc33d2402494ee493408bf9", "decision": "KEEP + HARDEN"},
  "allowed_paths": ["paper-trader/backend/app/ir/runtime.py", "paper-trader/backend/app/ir/streaming_reference.py", "paper-trader/backend/app/ir/incremental_runtime.py", "paper-trader/backend/research/evaluation/phase5_runtime.py", "paper-trader/backend/research_tests/test_phase5_research_execution.py", ".agent/runs/phase5-research-context-state-boundary-recovery", "paper-trader/docs/agent/tasks/phase5-research-context-state-boundary-recovery.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"],
  "protected_paths": ["paper-trader/backend/app/ir/first_party", "paper-trader/backend/tests/test_phase5_first_party_analytical_catalogue.py", "paper-trader/backend/tests/test_phase5_state_execution_derivatives_catalogue.py"],
  "nonclaims": ["No new catalogue semantics, cache reuse, worker, queue, provider, broker, order, live or money authority.", "No performance, capacity, release, deployment or production claim."],
  "owner_gates": ["Stop before new catalogue semantics, provider subscriptions, dependency adoption, worker/cache adoption, deployment, live-loop adoption or Phase 6."],
  "stop_conditions": ["A graph-authored context becomes authoritative; vector/prefix context rules differ; nested event count or slicing is ambiguous; StateSeriesResult identity is mutable; any P5-REX finding regresses."],
  "deployment_impact": {"classification": "architecture-changing", "required_evidence": "Local in-process calling convention and result serialization only; worker packaging, health, capacity and deployment remain later capsules."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["An addressed accepted resolver derives Type 3 contexts from exact assembled facts and accepted policy/data authority for both vector and independent prefix walks.", "All 63 Type 3 nodes pass accepted-boundary semantics and hostile context/time/owner/mode cases refuse.", "Nested recursive state inputs expose exact causal event count and prefix slices to both walks.", "StateSeriesResult has one immutable closed research representation and defensive materializer.", "All 18 recursive Type 5 nodes pass vector/incremental equality, cancellation, last-event and result provenance through accepted execution.", "All earlier research authority, dataset, ResourcePlan, result and restart regressions remain green."],
  "test_plan": ["Complete 63 Type 3 accepted-boundary matrix against frozen Type 3 golden map.", "Context omission, graph-authored, wrong owner/mode/fact/time/policy/capability refusals.", "Complete 18 recursive Type 5 accepted-boundary matrix and five resets.", "Nested event count, length/time, prefix append, cancellation and immutable output cases.", "Affected subsystem and killed/restored context/state-result mutations."],
  "review": {"required": true, "assignment_id": "phase5_research_context_state_boundary_recovery_reviewer", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "base_sha": "HEAD", "package": ".agent/runs/phase5-research-context-state-boundary-recovery/review-package.json", "review_paths": ["paper-trader/backend/app/ir/runtime.py", "paper-trader/backend/app/ir/streaming_reference.py", "paper-trader/backend/app/ir/incremental_runtime.py", "paper-trader/backend/research/evaluation/phase5_runtime.py", "paper-trader/backend/research_tests/test_phase5_research_execution.py"], "exclude_paths": [], "output": ".agent/runs/phase5-research-context-state-boundary-recovery/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 0},
  "implementation": {"status": "behavior_pass_evidence_gap", "report_sha256": "8710c4f4d9242e6a6f49a78e479b2a84a83f8dafaabdb02545e27e7aebe35918", "deployability_sha256": "cc0fc3854ba5180963ace303bd228d12cbae1cc594695911a560d26d24d39abb", "evidence_sha256": "99883126a0b3f9d014144a2ad82edd2b47e1c23e838f6014bedfca286153983c", "focused_passed": 153, "subsystem_passed": 1571, "subsystem_skipped": 58, "mutations": 3, "type3_components": 63, "recursive_type5_components": 18},
  "review_result": {"spec": "UNVERIFIABLE", "quality": "FAIL", "overall": "FAIL", "package_sha256": "36bd882fa469078b880f139a33ee267ff86e6b317bd5478e8f4483dc2451c0db", "verdict": ".agent/runs/phase5-research-context-state-boundary-recovery/review/verdict.json", "verdict_sha256": "466d64a026e525c9246cdcab07bc7cfb57b52a6a6862039e7ac86241c803f2b5", "findings": ["P5-RCSB-REV-001", "P5-RCSB-REV-002"], "successor": "paper-trader/docs/agent/tasks/phase5-research-context-state-evidence-recovery.md"}
}
---

# Phase 5 research context/state boundary recovery

This bounded recovery changes no catalogue semantics and creates no operational or
live authority. Read-only parity assurance must rerun after fresh review acceptance.
