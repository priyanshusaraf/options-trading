---
{
  "id": "post-phase7-derivatives-execution-critical-closure",
  "phase": "interphase-7-8",
  "status": "blocked",
  "goal": "Close every Critical derivatives, execution-authority, account-risk, concurrency, capacity, recovery, or runtime-economics finding from the post-Phase-7 assurance audit before Phase 8 architecture starts.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "This closure gate is authorized as programme structure. It may route newly defined bounded correction capsules after the read-only audit, but it grants no standing product rewrite, deployment, frontend, provider, credential, live, money, or commercial authority.",
    "stopping_condition": "Complete only when the audit is immutable and every Critical finding has either an independently reviewed bounded correction with permanent real-path regressions and transitive revalidation or an evidence-backed no-Critical disposition. Every lower-severity deferral must have containment, rationale, owner, and an exact capsule or deadline."
  },
  "risk_tags": [
    "critical",
    "programme-gate",
    "derivatives",
    "execution-authority",
    "account-risk",
    "capacity",
    "transitive-evidence",
    "architecture-closure"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/program/owner-steers/06-POST-PHASE7-DERIVATIVES-EXECUTION-ASSURANCE.md",
      "sections": [
        "9. Post-Phase-7 audit gate",
        "10. Acceptance evidence",
        "11. Nonclaims and owner gates"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/post-phase7-derivatives-execution-assurance-audit.md",
      "sections": [
        "Post-Phase-7 derivatives and execution assurance audit"
      ]
    }
  ],
  "dependency_gate": "post-phase7-derivatives-execution-assurance-audit",
  "allowed_paths": [
    "paper-trader/docs/agent/tasks",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/post-phase7-derivatives-execution-critical-closure"
  ],
  "nonclaims": [
    "This stage is a coordinator and gate, not a generic implementation capsule. Each product correction requires its own exact ownership, dependencies, migration and deployment impact, tests, evidence, and independent review.",
    "Phase 5 through 7 historical verdicts remain immutable. A correction must revalidate every dependent claim marked STALE/REQUIRES RECHECK.",
    "Acceptance grants only readiness for Phase 8 architecture. It grants no frontend, provider, credential, deployment, production, live-authority, order, money, legal, regulatory, licence, pricing, or commercial permission."
  ],
  "owner_gates": [
    "Stop before live IR authority, material live sizing, routing, risk, protection or execution changes, provider or broker adoption, frontend implementation, credentials, production data/use, deployment, destructive work, or legal, regulatory, licence, pricing and commercial decisions.",
    "Stop before combining unrelated findings into an uncontrolled rewrite. Every Critical pattern needs the smallest coherent correction and one independent current-tree review."
  ],
  "stop_conditions": [
    "The audit report, finding register, machine-readable evidence manifest, workload results, or transitive invalidation map is missing, mutable, or not bound to the audited tree.",
    "Any Critical finding lacks a root cause, prevention invariant, permanent real-path adversarial regression, affected-evidence revalidation, deployment disposition, and independent PASS.",
    "Any concurrency claim lacks disposable PostgreSQL multi-session or multi-process evidence, or any tier/capacity claim lacks reproducible workload and cost evidence.",
    "A lower-severity deferral lacks containment, rationale, owner, and an exact future capsule or deadline."
  ],
  "model_route": {
    "coordinator": "gpt-5.6-sol",
    "coordinator_reasoning_effort": "medium",
    "normal_implementation": "gpt-5.6-terra",
    "repeated_or_architecture_correction_owner": "gpt-5.6-sol",
    "repeated_or_architecture_correction_reasoning_effort": "medium",
    "mechanical_children": "gpt-5.6-luna",
    "critical_reviewer": "gpt-5.6-sol",
    "critical_reviewer_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The immutable audit and exact evidence manifest are present, and every finding and dependent historical claim has a recorded disposition.",
    "Each Critical finding is closed by a bounded correction and independent review with a root cause, prevention invariant, permanent real-path regression, mutation evidence where a Critical guard changed, migration and deployability evidence where relevant, and complete transitive revalidation.",
    "The final current tree proves the one-entry-authority, multi-instrument concurrency, account-wide reservation, position succession, exit continuity, broker-netting attribution, derivative identity, tier-capacity, bounded-recovery, and cost contracts named by the audit.",
    "If the audit reports no Critical findings, an independently reviewed closure record binds that conclusion to the audit evidence and final tree without inventing production readiness.",
    "Every High, Medium, or Low deferral records containment, rationale, owner, exact capsule or deadline, and why it cannot cross money, authority, tenancy, persistence, research-integrity, provider, or capacity boundaries.",
    "Only a passing independent closure verdict may make phase8-architecture ready and unstarted."
  ],
  "test_plan": [
    "Validate audit hashes, severity inventory, defect-pattern coverage, workload evidence, and transitive invalidation completeness.",
    "For every Critical correction verify focused real lifecycle tests, PostgreSQL concurrency where relevant, killed-and-restored mutations for changed guards, supported migration and restart paths, protected boundaries, package lineage, and independent verdict.",
    "Re-run the complete Critical assurance matrix on the integrated final tree, including the owner seed cases and every added defect-pattern case, without mocked authority, persistence, account-risk, or recovery seams.",
    "Validate every lower-severity deferral and the Phase 8 dependency. Do not deploy or run broad suites merely for confidence."
  ],
  "review": {
    "required": true,
    "assignment_id": "post_phase7_derivatives_execution_critical_closure",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/program/owner-steers/06-POST-PHASE7-DERIVATIVES-EXECUTION-ASSURANCE.md",
      "paper-trader/docs/agent/tasks/post-phase7-derivatives-execution-assurance-audit.md",
      "paper-trader/docs/agent/tasks/post-phase7-derivatives-execution-critical-closure.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md",
      ".agent/runs/post-phase7-derivatives-execution-assurance-audit",
      ".agent/runs/post-phase7-derivatives-execution-critical-closure"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/post-phase7-derivatives-execution-critical-closure/verdict.json",
    "verdicts": [
      "CRITICAL_CLOSURE",
      "EVIDENCE_CURRENTNESS"
    ],
    "max_rechecks": 1
  }
}
---

# Post-Phase-7 derivatives and execution Critical closure

This gate prevents the assurance audit from becoming a report that Phase 8 can ignore. It routes only bounded corrections, requires independent closure of every Critical finding, and preserves the existing live-money and deployment owner gates.
