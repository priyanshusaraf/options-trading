---
{
  "id": "phase5-architecture",
  "phase": "phase5",
  "status": "accepted",
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
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "Strategy OS defect-pattern register",
        "Status and evidence rules"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "Phase 5 ownership",
        "V1 release gate"
      ]
    },
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
    },
    {
      "path": "paper-trader/docs/program/owner-steers/06-POST-PHASE7-DERIVATIVES-EXECUTION-ASSURANCE.md",
      "sections": [
        "Goal",
        "1. Timing and authority",
        "2. Current evidence boundary",
        "3. Entry authority and position ownership",
        "Concurrent bindings",
        "4. Owner seed scenarios",
        "Derivatives-market and tier stress",
        "Observability and economics",
        "6. Requirements carried through Phase 5",
        "9. Post-Phase-7 audit gate",
        "10. Acceptance evidence",
        "11. Nonclaims and owner gates"
      ]
    }
  ],
  "dependency_gate": "phase1-4-foundation-critical-closure",
  "allowed_paths": [
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase5-strategy-os.md",
    "paper-trader/docs/reports/phase5-source-coverage.json",
    "paper-trader/docs/reports/phase5-v1-catalogue.json",
    "paper-trader/docs/reports/phase5-architecture-validation.json",
    "paper-trader/docs/agent/tasks",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".codex/scripts/validate_agent_architecture.py",
    ".codex/tests/test_tools.py",
    ".codex/tests/test_repository_contract.py",
    ".codex/tests/test_programme_orchestration.py",
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
    "The dependency gate phase1-4-foundation-critical-closure is not accepted after a completed Phase 1-4 foundation audit and closure or explicit deferral of its findings.",
    "The design would duplicate an accepted IR, identity, authority, provider, deployment, or research abstraction.",
    "Any mapped owner-steer section remains uncovered or in unresolved conflict.",
    "A generated slice has overlapping write ownership, no observable acceptance criterion, or no proportional test command."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "default",
    "implementation_owner": "gpt-5.6-sol",
    "implementation_reasoning_effort": "medium",
    "phase_reviewer": "gpt-5.6-sol",
    "phase_reviewer_reasoning_effort": "high"
  },
  "parallel_budget": 2,
  "assignments": [
    {
      "id": "existing_capability_audit",
      "agent": "default",
      "model": "gpt-5.6-sol",
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
      "agent": "default",
      "model": "gpt-5.6-sol",
      "reasoning_effort": "medium",
      "mode": "read",
      "depends_on": [],
      "read_paths": [
        "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md",
        "paper-trader/docs/program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md",
        "paper-trader/docs/program/owner-steers/01-STRATEGY-LANGUAGE-NODE-SYSTEM.md",
        "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md",
        "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md",
        "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md",
        "paper-trader/docs/program/owner-steers/06-POST-PHASE7-DERIVATIVES-EXECUTION-ASSURANCE.md"
      ],
      "write_paths": [
        ".agent/runs/phase5-architecture/source_coverage_audit"
      ],
      "output": ".agent/runs/phase5-architecture/source_coverage_audit/report.md"
    }
  ],
  "assignment_results": {
    "existing_capability_audit": {"output": ".agent/runs/phase5-architecture/existing_capability_audit/report.md", "sha256": "c6784211611defcabebb61aaa3a7d638f85db3a1553c6047fdf2d3be3a4d2330", "decision": "KEEP + HARDEN"},
    "source_coverage_audit": {"output": ".agent/runs/phase5-architecture/source_coverage_audit/report.md", "sha256": "30eb896d5bbbcc5403c6974fa796b6cf3df3e7d89f319e3cf6f74c1d48d7af10", "decision": "COVERAGE_COMPLETE_AFTER_ROOT_RESOLUTION"}
  },
  "architecture_acceptance": {
    "decision": "ACCEPT_PHASE5_ARCHITECTURE_AND_AUTHORIZE_FIRST_HANDOFF_ONLY",
    "validation": "paper-trader/docs/reports/phase5-architecture-validation.json",
    "validation_sha256": "8d6faa0596a0a3859b481f8eb61d0613d00a6a58d796aaf726c30db487d4fe5e",
    "programme_stage_count": 95,
    "phase5_stage_count": 18,
    "source_map_entries": 103,
    "catalogue_entries": 332,
    "exclusive_runtime_capsule": "phase5-adv-006-runtime",
    "first_handoff": "phase5-graph-paper-attribution-schema",
    "evidence_level": "architecture_accepted; implementation_unstarted"
  },
  "acceptance": [
    "Every affected deployment-contract dimension has current evidence or an exact owning future capsule; no deployment debt is deferred vaguely.",
    "Accepted preceding contracts and existing implementation are audited before proposing changes.",
    "Every SOURCE_MAP.json phase5 entry has an explicit design, task, test, nonclaim, or deferral disposition.",
    "The design and plan preserve one canonical IR and existing ownership/authority boundaries.",
    "The design publishes a dated provisional beta strategy-complexity table for Standard, Pro, and Desk with separate Type 1 through Type 5 family maxima, authored-total, fully-lowered-total, authored-edge, compound-depth, and single-output-fan-out limits.",
    "The initial beta hypotheses are: Standard Type 1/2/3/4/5 = 32/128/32/64/192, authored total 256, lowered total 1024, authored edges 1024, compound depth 16, fan-out 32; Pro = 96/384/128/192/576, authored total 768, lowered total 4096, authored edges 4096, compound depth 32, fan-out 64; Desk = 256/1024/384/512/1536, authored total 2048, lowered total 12288, authored edges 16384, compound depth 48, fan-out 128.",
    "All strategy-complexity limits are conjunctive and intentionally non-combinable: satisfying a family maximum never overrides the lower total, lowered graph, edge, depth, fan-out, weighted resource, provider, tenant, or concurrency ceilings.",
    "Family consumption is charged to fully lowered atomic nodes by originating user-visible family so compounds, reusable components, custom nodes, or nesting cannot hide cost; custom nodes without a declared family and bounded resource profile refuse admission.",
    "The strategy and ResourcePlan contracts retain exact canonical instrument roles, separately addressed per-instrument deployment bindings, trigger-rate, state, history, subscription, provider-product/contract, memory, compute, and fan-out requirements so Phase 6 can enforce authority and Phase 7 can measure physical cost without changing strategy semantics.",
    "One immutable strategy version can describe several distinct future instrument bindings, but Phase 5 grants no deployment, entry, account-reservation, broker, or money authority; those facts remain separate and are owned by Phase 6.",
    "Tier policy and capacity-calibration versions remain outside executable strategy semantics and semantic identity; changing a commercial limit cannot silently change an accepted strategy's logic or make an existing deployment authoritative.",
    "The resolver's engineering safety ceilings remain separate absolute parser/compiler protections and are never advertised as tier entitlements.",
    "Implementation work is split into fresh durable-goal capsules with exact dependencies, allowed paths, exclusive write ownership, observable acceptance, and proportional tests.",
    "Every material failure inherits the programme durable-failure-learning contract and records the violated invariant, why evidence missed it, false assumption, minimal permanent regression, adversarial or mutation proof, generalization, inheriting capsules, and invalidated dependent evidence before reroute.",
    "At every critical boundary the architecture asks 'What is the 4-of-24-tables equivalent?', enumerates the complete claimed universe, and assigns an independently authored consumer plus adversarial or mutation proof; implementation cannot self-certify that boundary.",
    "Any extra or deferred work names its exact owner, capsule, and deadline; vague later-phase deferral is invalid.",
    "The architecture generates exactly one exclusive runtime capsule carrying the exact contract identifier P5-ADV-006-RUNTIME. It depends on accepted phase5-graph-paper-attribution-schema and must close before any v2 claim, reclaim, worker, result, cache, broker, order, or money consumer becomes reachable; the generic phase5-implementation placeholder does not count as this capsule.",
    "The P5-ADV-006-RUNTIME capsule preserves one existing job lifecycle and sole authority loader/verifier. Its acceptance directly proves on SQLite and disposable PostgreSQL 16 that a job is claimed, ownership is lost, reclaim occurs through the public seam after real process death, the exact current persisted authority chain reloads, the stale claimant is fenced, and only the current claimant finalizes exactly once.",
    "The accepted graph-paper attribution schema is a necessary dependency and grants no claim/reclaim or other runtime reachability by itself.",
    "The programme implementation placeholder is expanded into ordered slice stages and an exact phase-review capsule.",
    "The final phase gate requires one Sol-high goal with separate SPEC and QUALITY verdicts."
  ],
  "test_plan": [
    "Validate all structured artifacts and references.",
    "Compare the source-coverage matrix to SOURCE_MAP.json phase view phase5.",
    "For each tier and each of the five node families, prove a representative graph at the individual family limit is classifiable and the first node above it refuses with a stable typed reason.",
    "Prove the family maxima cannot be combined past the authored-total, lowered-total, edge, compound-depth, fan-out, or weighted-resource limits; include nested compounds and custom-node classification attempts.",
    "Prove the generated design and capsules retain separately addressed canonical instrument roles, per-instrument binding inputs, provider product/contract requirements, and complete resource accounting for the GOLD/CRUDEOIL and one-strategy/three-instrument seed cases without granting runtime authority.",
    "Prove reusable components, nested compounds, custom nodes, dynamic option windows, shared calculations, and provider subscriptions cannot hide family, lowered-node, trigger-rate, memory, compute, history, state, fan-out, or provider demand from the ResourcePlan.",
    "Prove tier and calibration metadata do not enter executable semantic identity, while the separately addressed ResourcePlan and policy decision do change when resource consumption or tier policy changes.",
    "Validate goal-capsule dependencies, routes, parallel budgets, path ownership, owner gates, and test cadence.",
    "Validate durable failure-learning fields, complete-universe coverage, independent-assurance ownership, invalidated-evidence links, and exact owner/capsule/deadline for every deferral.",
    "Fail architecture validation unless exactly one generated capsule owns P5-ADV-006-RUNTIME, depends on accepted phase5-graph-paper-attribution-schema, includes direct SQLite and disposable PostgreSQL 16 process-restart/adversarial evidence, and precedes reachability of every named v2 consumer.",
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

This capsule is active after the reviewed finite Phase 1-4 foundation closure returned separate SPEC PASS and QUALITY PASS. It creates future implementation goals; it does not implement product code.

It must generate one exclusive runtime capsule for the exact `P5-ADV-006-RUNTIME` contract after `phase5-graph-paper-attribution-schema` and before any v2 claim, reclaim, worker, result, cache, broker, order, or money consumer can become reachable. The schema is necessary but non-enabling. A generic dynamic implementation placeholder does not satisfy this generation requirement.

## Owner capacity directive

The numeric table above is a conservative, deliberately roomy beta hypothesis, not a permanent commercial promise. Phase 5 must define the five-family accounting vocabulary and compile a separately addressed static ResourcePlan. A reusable component consumes the counts of its expanded leaves; shared runtime work may reduce measured cost but never erases structural accounting. Draft authoring may remain available up to the absolute engineering safety ceiling, but research admission, deployment preflight, and activation must show the applicable tier envelope and refuse rather than truncate or silently simplify a graph.
