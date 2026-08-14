---
{
  "id": "phase5-architecture",
  "phase": "phase5",
  "status": "blocked",
  "goal": "Architect Strategy OS phase5: First-party language and scalable research, producing bounded goal capsules and evidence gates without implementing product code.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after the Phase 5 design, implementation plan, source-coverage matrix, dependency-ordered implementation goal capsules, exact Sol-high review capsule, and programme expansion validate. Stop with the goal active for an owner gate or unresolved conflict."
  },
  "risk_tags": [
    "critical",
    "phase-architecture",
    "phase5"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md",
      "sections": [
        "Phase 5: First-party language and scalable research",
        "Global constraints",
        "Programme closure"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md",
      "sections": [
        "Strategy OS — Product Architecture Steer",
        "Purpose",
        "1. The five user-facing node families",
        "Type 1 — Execution & Position",
        "Type 2 — Indicators & Derived Features",
        "Type 3 — Market Structure, Derivatives & Cross-Instrument",
        "Type 4 — Price, Instrument & Market Data",
        "Type 5 — Logic, Math & State",
        "2. Hidden platform layers",
        "A. Instrument Resolver",
        "B. Point-in-Time Market Rulebook",
        "C. Data Contract Engine",
        "D. Causality Engine",
        "E. Provider Capability Matrix",
        "F. Subscription & Resource Planner",
        "G. Numeric Validity System",
        "H. Deployment Binding System",
        "7. Position and strategy state",
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
        "Strategy Language & Node System Steer",
        "Goal",
        "1. Node contract required for every first-party node",
        "2. First-party indicator starter pack",
        "Moving averages",
        "Trend",
        "Momentum",
        "Volatility",
        "Advanced realized-vol estimators",
        "Volume / participation",
        "Price transforms",
        "Statistics",
        "Regression / relative value",
        "Returns",
        "Market/session structure",
        "Pattern/event primitives",
        "3. Type 3 derivative/microstructure library",
        "Option structure",
        "Options analytics",
        "Futures",
        "Order book / ladder",
        "Trade-flow features where the provider truly supplies enough data",
        "4. Type 1 execution starter pack",
        "Entry/exit",
        "Order type",
        "Position sizing",
        "Protection",
        "Pyramiding / scaling",
        "Position/portfolio inputs",
        "5. Type 5 logic, temporal and state pack",
        "Boolean / comparison",
        "Arithmetic",
        "Reducers",
        "Temporal",
        "Confirmation",
        "Noise/state control",
        "Scheduling",
        "Validity",
        "6. Custom-node hierarchy",
        "Level 1 — Fork first-party node",
        "Level 2 — Formula node",
        "Level 3 — Sandboxed custom Python",
        "Level 4 — External signal",
        "7. Numerical validity",
        "8. Node versioning"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md",
      "sections": [
        "12. Corporate actions",
        "13. Dataset provenance"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md",
      "sections": [
        "Runtime Economics & Provider Capability Steer",
        "Goal",
        "1. Compile a resource plan with every strategy",
        "Static",
        "Dynamic",
        "2. Incremental streaming runtime",
        "3. Batch/vector research runtime",
        "4. Evaluation clocks/triggers",
        "5. Shared calculations",
        "6. Cache identity",
        "7. Order-book/ladder processing",
        "13. Cost telemetry"
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
        "4. First-party node conformance harness",
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
  "dependency_gate": "phase4-review",
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase5-strategy-os.md",
    "paper-trader/docs/reports/phase5-source-coverage.json",
    "paper-trader/docs/agent/tasks",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase5-architecture"
  ],
  "nonclaims": [
    "This architecture goal does not implement or accept Phase 5.",
    "It grants no live authority, deployment, VPS, credential, production-data, destructive, or unrelated future-phase authority."
  ],
  "owner_gates": [
    "Stop before product implementation.",
    "Stop before live authority, material live execution-semantics changes, live credentials, VPS, production data, deployment, destructive work, or licence-sensitive adoption.",
    "Frontend paths may appear only when this phase's master-sequence scope requires them and the generated implementation capsule opens them explicitly."
  ],
  "stop_conditions": [
    "The dependency gate phase4-review lacks dual passing SPEC and QUALITY verdicts.",
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
        ".agent/runs/phase5-architecture/existing_capability_audit"
      ],
      "output": ".agent/runs/phase5-architecture/existing_capability_audit/report.md"
    },
    {
      "id": "source_coverage_audit",
      "agent": "luna-worker",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "medium",
      "mode": "read",
      "depends_on": [],
      "read_paths": [
        "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md",
        "paper-trader/docs/program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md",
        "paper-trader/docs/program/owner-steers/01-STRATEGY-LANGUAGE-NODE-SYSTEM.md",
        "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md",
        "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md",
        "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md"
      ],
      "write_paths": [
        ".agent/runs/phase5-architecture/source_coverage_audit"
      ],
      "output": ".agent/runs/phase5-architecture/source_coverage_audit/report.md"
    }
  ],
  "acceptance": [
    "Accepted preceding contracts and existing implementation are audited before proposing changes.",
    "Every SOURCE_MAP.json phase5 entry has an explicit design, task, test, nonclaim, or deferral disposition.",
    "The design and plan preserve one canonical IR and existing ownership/authority boundaries.",
    "Implementation work is split into fresh durable-goal capsules with exact dependencies, allowed paths, exclusive write ownership, observable acceptance, and proportional tests.",
    "The programme implementation placeholder is expanded into ordered slice stages and an exact phase-review capsule.",
    "The final phase gate requires one Sol-high goal with separate SPEC and QUALITY verdicts."
  ],
  "test_plan": [
    "Validate all structured artifacts and references.",
    "Compare the source-coverage matrix to SOURCE_MAP.json phase view phase5.",
    "Validate goal-capsule dependencies, routes, parallel budgets, path ownership, owner gates, and test cadence.",
    "Run the complete .codex architecture test suite and git diff --check."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase5_architecture_handoff",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase5-review/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  }
}
---

# Phase 5 architecture goal

This capsule stays blocked until phase4-review is accepted. It creates future implementation goals; it does not implement them.
