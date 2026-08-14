---
{
  "id": "phase9-architecture",
  "phase": "phase9",
  "status": "blocked",
  "goal": "Architect Strategy OS phase9: Provider and broker breadth, producing bounded goal capsules and evidence gates without implementing product code.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after the Phase 9 design, implementation plan, source-coverage matrix, dependency-ordered implementation goal capsules, exact Sol-high review capsule, and programme expansion validate. Stop with the goal active for an owner gate or unresolved conflict."
  },
  "risk_tags": [
    "critical",
    "phase-architecture",
    "phase9"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md",
      "sections": [
        "Phase 9: Provider and broker breadth",
        "Global constraints",
        "Programme closure"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md",
      "sections": [
        "Strategy OS — Product Architecture Steer",
        "Purpose",
        "Type 3 — Market Structure, Derivatives & Cross-Instrument",
        "Type 4 — Price, Instrument & Market Data",
        "2. Hidden platform layers",
        "A. Instrument Resolver",
        "B. Point-in-Time Market Rulebook",
        "C. Data Contract Engine",
        "D. Causality Engine",
        "E. Provider Capability Matrix",
        "F. Subscription & Resource Planner",
        "G. Numeric Validity System",
        "H. Deployment Binding System",
        "5. Dynamic derivative identity",
        "Critical invariant",
        "6. Options lifecycle model",
        "8. Trust is a product requirement",
        "9. V1 acceptance scenarios",
        "Scenario A — reusable equity strategy",
        "Scenario B — Indian options/order-flow strategy",
        "Scenario C — cross-market strategy",
        "10. Non-negotiable product rules"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/01-STRATEGY-LANGUAGE-NODE-SYSTEM.md",
      "sections": [
        "3. Type 3 derivative/microstructure library",
        "Option structure",
        "Options analytics",
        "Futures",
        "Order book / ladder",
        "Trade-flow features where the provider truly supplies enough data",
        "8. Node versioning"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md",
      "sections": [
        "Market Truth & Data Contracts Steer",
        "Goal",
        "1. Point-in-time market rulebook",
        "2. Historical derivative truth",
        "3. Strike-grid evolution",
        "4. Contract identity",
        "5. Futures and continuous series",
        "6. Option-window policies",
        "7. Data sufficiency",
        "8. Live versus historical capability",
        "9. Missing-data semantics",
        "10. Cross-instrument alignment",
        "11. Cross-timeframe causality",
        "12. Corporate actions",
        "13. Dataset provenance",
        "14. Provider capability changes"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/03-DEPLOYMENT-EXECUTION-TRUST.md",
      "sections": [
        "Deployment, Execution & Trader Trust Steer",
        "Goal",
        "6. Protection semantics",
        "Strategy-managed exits",
        "Software-managed hard protection",
        "Broker/exchange-resident protection",
        "7. Order semantics",
        "8. Pyramiding and scaling",
        "9. Degraded deployment states",
        "10. Senior-trader trust requirements",
        "Strategy IP confidentiality",
        "No silent semantic change",
        "Reproducibility",
        "Explainability without exposing secrets",
        "User control"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md",
      "sections": [
        "Runtime Economics & Provider Capability Steer",
        "Goal",
        "7. Order-book/ladder processing",
        "8. Dynamic option-window subscription management",
        "11. Provider capability matrix",
        "Data",
        "Execution",
        "Historical market support",
        "12. Provider fallback"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md",
      "sections": [
        "V1 Implementation Priorities & Verification Policy",
        "Goal",
        "1. Risk-weighted verification",
        "Critical",
        "Important",
        "Routine",
        "Trivial",
        "2. Test rule",
        "3. Test cadence",
        "5. V1 product priorities",
        "Must have",
        "Can be deferred",
        "6. Implementation sequencing",
        "7. Canonical acceptance scenarios",
        "A. Reusable equity",
        "B. Weekly-options/order-flow",
        "C. Cross-market",
        "8. Guard against scope drift",
        "Core-abstraction issue",
        "Local implementation edge case"
      ]
    }
  ],
  "dependency_gate": "phase8-review",
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase9-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase9-strategy-os.md",
    "paper-trader/docs/reports/phase9-source-coverage.json",
    "paper-trader/docs/agent/tasks",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase9-architecture"
  ],
  "nonclaims": [
    "This architecture goal does not implement or accept Phase 9.",
    "It grants no live authority, deployment, VPS, credential, production-data, destructive, or unrelated future-phase authority."
  ],
  "owner_gates": [
    "Stop before product implementation.",
    "Stop before live authority, material live execution-semantics changes, live credentials, VPS, production data, deployment, destructive work, or licence-sensitive adoption.",
    "Frontend paths may appear only when this phase's master-sequence scope requires them and the generated implementation capsule opens them explicitly."
  ],
  "stop_conditions": [
    "The dependency gate phase8-review lacks dual passing SPEC and QUALITY verdicts.",
    "The design would duplicate an accepted IR, identity, authority, provider, deployment, or research abstraction.",
    "Any mapped owner-steer section remains uncovered or in unresolved conflict.",
    "A generated slice has overlapping write ownership, no observable acceptance criterion, or no proportional test command."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "default",
    "implementation_owner": "gpt-5.6-terra",
    "implementation_reasoning_effort": "medium",
    "phase_reviewer": "gpt-5.6-sol",
    "phase_reviewer_reasoning_effort": "high"
  },
  "parallel_budget": 2,
  "assignments": [
    {
      "id": "existing_capability_audit",
      "agent": "terra-worker",
      "model": "gpt-5.6-terra",
      "reasoning_effort": "medium",
      "mode": "read",
      "depends_on": [],
      "read_paths": [
        "paper-trader/backend",
        "paper-trader/frontend",
        "paper-trader/docs/engineering"
      ],
      "write_paths": [
        ".agent/runs/phase9-architecture/existing_capability_audit"
      ],
      "output": ".agent/runs/phase9-architecture/existing_capability_audit/report.md"
    },
    {
      "id": "source_coverage_audit",
      "agent": "luna-worker",
      "model": "gpt-5.6-terra",
      "reasoning_effort": "medium",
      "mode": "read",
      "depends_on": [],
      "read_paths": [
        "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md",
        "paper-trader/docs/program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md",
        "paper-trader/docs/program/owner-steers/01-STRATEGY-LANGUAGE-NODE-SYSTEM.md",
        "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md",
        "paper-trader/docs/program/owner-steers/03-DEPLOYMENT-EXECUTION-TRUST.md",
        "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md",
        "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md"
      ],
      "write_paths": [
        ".agent/runs/phase9-architecture/source_coverage_audit"
      ],
      "output": ".agent/runs/phase9-architecture/source_coverage_audit/report.md"
    }
  ],
  "acceptance": [
    "Accepted preceding contracts and existing implementation are audited before proposing changes.",
    "Every SOURCE_MAP.json phase9 entry has an explicit design, task, test, nonclaim, or deferral disposition.",
    "The design and plan preserve one canonical IR and existing ownership/authority boundaries.",
    "Implementation work is split into fresh durable-goal capsules with exact dependencies, allowed paths, exclusive write ownership, observable acceptance, and proportional tests.",
    "The programme implementation placeholder is expanded into ordered slice stages and an exact phase-review capsule.",
    "The final phase gate requires one Sol-high goal with separate SPEC and QUALITY verdicts."
  ],
  "test_plan": [
    "Validate all structured artifacts and references.",
    "Compare the source-coverage matrix to SOURCE_MAP.json phase view phase9.",
    "Validate goal-capsule dependencies, routes, parallel budgets, path ownership, owner gates, and test cadence.",
    "Run the complete .codex architecture test suite and git diff --check."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase9_architecture_handoff",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase9-review/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  }
}
---

# Phase 9 architecture goal

This capsule stays blocked until phase8-review is accepted. It creates future implementation goals; it does not implement them.
