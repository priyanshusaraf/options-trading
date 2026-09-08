---
{
  "id": "phase6-architecture",
  "phase": "phase6",
  "status": "blocked",
  "goal": "Architect Strategy OS phase6: Deployment binding and Strategy Preflight, producing bounded goal capsules and evidence gates without implementing product code.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after the Phase 6 design, implementation plan, source-coverage matrix, dependency-ordered implementation goal capsules, exact Sol-high review capsule, and programme expansion validate. Stop with the goal active for an owner gate or unresolved conflict."
  },
  "risk_tags": [
    "critical",
    "phase-architecture",
    "phase6"
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
        "Phase 6 ownership",
        "V1 release gate"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md",
      "sections": [
        "Phase 6: Deployment binding and Strategy Preflight",
        "Global constraints",
        "Programme closure"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md",
      "sections": [
        "Strategy OS — Product Architecture Steer",
        "Purpose",
        "Type 1 — Execution & Position",
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
        "3. Strategy definition is not deployment",
        "Two equivalent UI entry points",
        "4. Named secondary instrument roles",
        "7. Position and strategy state",
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
        "Strategy Language & Node System Steer",
        "Goal",
        "1. Node contract required for every first-party node",
        "4. Type 1 execution starter pack",
        "Entry/exit",
        "Order type",
        "Position sizing",
        "Protection",
        "Pyramiding / scaling",
        "Position/portfolio inputs",
        "7. Numerical validity",
        "8. Node versioning"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md",
      "sections": [
        "Market Truth & Data Contracts Steer",
        "Goal",
        "1. Point-in-time market rulebook",
        "4. Contract identity",
        "7. Data sufficiency",
        "8. Live versus historical capability",
        "9. Missing-data semantics",
        "10. Cross-instrument alignment",
        "11. Cross-timeframe causality",
        "14. Provider capability changes"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/03-DEPLOYMENT-EXECUTION-TRUST.md",
      "sections": [
        "Deployment, Execution & Trader Trust Steer",
        "Goal",
        "1. Deployment object",
        "2. Deployment preflight",
        "3. Position sizing hierarchy",
        "4. Multi-strategy position ownership",
        "5. Open-position version ownership",
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
        "User control",
        "11. Sharing scope"
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
        "10. Per-deployment resource ceilings",
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
    },
    {
      "path": "paper-trader/docs/program/owner-steers/06-POST-PHASE7-DERIVATIVES-EXECUTION-ASSURANCE.md",
      "sections": [
        "Goal",
        "1. Timing and authority",
        "2. Current evidence boundary",
        "3. Entry authority and position ownership",
        "Entry-authority lease",
        "Position succession",
        "Research and shadow coexistence",
        "Concurrent bindings",
        "Broker netting and internal books",
        "4. Owner seed scenarios",
        "Deployment and control-plane races",
        "Order lifecycle and reconciliation",
        "Account-wide capital and risk",
        "Multi-leg and portfolio actions",
        "Safety and degraded operation",
        "7. Requirements carried through Phase 6",
        "9. Post-Phase-7 audit gate",
        "10. Acceptance evidence",
        "11. Nonclaims and owner gates"
      ]
    }
  ],
  "dependency_gate": "phase5-review",
  "allowed_paths": [
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/superpowers/specs/phase6-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase6-strategy-os.md",
    "paper-trader/docs/reports/phase6-source-coverage.json",
    "paper-trader/docs/agent/tasks",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase6-architecture"
  ],
  "nonclaims": [
    "This architecture goal does not implement or accept Phase 6.",
    "It grants no live authority, deployment, VPS, credential, production-data, destructive, or unrelated future-phase authority."
  ],
  "owner_gates": [
    "Stop before product implementation.",
    "Stop before live authority, material live execution-semantics changes, live credentials, VPS, production data, deployment, destructive work, or licence-sensitive adoption.",
    "Frontend paths may appear only when this phase's master-sequence scope requires them and the generated implementation capsule opens them explicitly."
  ],
  "stop_conditions": [
    "The dependency gate phase5-review lacks dual passing SPEC and QUALITY verdicts.",
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
        ".agent/runs/phase6-architecture/existing_capability_audit"
      ],
      "output": ".agent/runs/phase6-architecture/existing_capability_audit/report.md"
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
        "paper-trader/docs/program/owner-steers/03-DEPLOYMENT-EXECUTION-TRUST.md",
        "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md",
        "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md",
        "paper-trader/docs/program/owner-steers/06-POST-PHASE7-DERIVATIVES-EXECUTION-ASSURANCE.md"
      ],
      "write_paths": [
        ".agent/runs/phase6-architecture/source_coverage_audit"
      ],
      "output": ".agent/runs/phase6-architecture/source_coverage_audit/report.md"
    }
  ],
  "acceptance": [
    "Every affected deployment-contract dimension has current evidence or an exact owning future capsule; no deployment debt is deferred vaguely.",
    "Accepted preceding contracts and existing implementation are audited before proposing changes.",
    "Every SOURCE_MAP.json phase6 entry has an explicit design, task, test, nonclaim, or deferral disposition.",
    "The design and plan preserve one canonical IR and existing ownership/authority boundaries.",
    "Deployment preflight compiles the exact fully lowered static and dynamic ResourcePlan, then atomically intersects every Phase 5 family, total, edge, depth, fan-out, weighted-compute, memory, provider, tenant, and concurrency ceiling; no single passing dimension can admit an otherwise over-budget strategy.",
    "Research admission and deployment activation refuse before reserving subscriptions, workers, database capacity, or provider quota when any conjunctive ceiling is exceeded; no partial graph, hidden truncation, or silent lower-fidelity execution is permitted.",
    "Standard, Pro, and Desk buy bounded capacity and concurrency, never different correctness, causality, isolation, protection, or exit guarantees; P0 safety work has the same priority across tiers.",
    "Exactly one entry-authoritative active deployment may hold the PostgreSQL-backed fenced lease for `(owner_id, broker_account_id, execution_mode_or_book, canonical_instrument_address)`; activation, replacement, pause, retirement, expiry, roll, restart, and reclaim serialize on that exact physical-contract key and every losing contender receives a stable typed refusal.",
    "Open positions remain owned by the deployment and immutable strategy version that created them. Replaced or retired deployments retain only exit, protection, cancel, and reconciliation authority for those positions; any transfer requires an explicit lineage-preserving takeover record, and entry limits never block risk-reducing actions.",
    "Research and non-money shadow evaluations may coexist on the same instrument without acquiring entry authority. One account may run different strategies on different instruments, and one immutable strategy version may bind to several instruments, while every binding keeps exact independent attribution.",
    "Every new-risk action atomically acquires the instrument entry lease and one account-wide reservation covering available funds, margin, fees, taxes, slippage allowance, gross and net exposure, concentration, leverage, loss, open orders, open positions, order rate, tenant, provider, and tier limits; no process may observe a passing preflight and then double-spend the same capacity.",
    "Reservation, order, fill, release, and reconciliation state is idempotent and crash-safe across reject, cancel, cancel-replace, partial fill, ambiguous timeout, retry, stale command, worker reclaim, process death, external account change, and delayed broker correction. Broker netting never erases separate virtual deployment books or creator-version attribution.",
    "Multi-leg or portfolio actions declare atomic or compensating semantics, acquire all required leases and account reservations in a deterministic deadlock-free order, and preserve exit/protection priority under partial-leg failure.",
    "Policy changes are versioned outside executable semantic identity and have an explicit grandfather, re-preflight, pause, or migration result for existing deployments; they never silently mutate or reactivate accepted authority.",
    "Implementation work is split into fresh durable-goal capsules with exact dependencies, allowed paths, exclusive write ownership, observable acceptance, and proportional tests.",
    "Every material failure inherits the programme durable-failure-learning contract and records the violated invariant, why evidence missed it, false assumption, minimal permanent regression, adversarial or mutation proof, generalization, inheriting capsules, and invalidated dependent evidence before reroute.",
    "At every critical boundary the architecture asks 'What is the 4-of-24-tables equivalent?', enumerates the complete claimed universe, and assigns an independently authored consumer plus adversarial or mutation proof; implementation cannot self-certify that boundary.",
    "Any extra or deferred work names its exact owner, capsule, and deadline; vague later-phase deferral is invalid.",
    "The programme implementation placeholder is expanded into ordered slice stages and an exact phase-review capsule.",
    "The final phase gate requires one Sol-high goal with separate SPEC and QUALITY verdicts."
  ],
  "test_plan": [
    "Validate all structured artifacts and references.",
    "Compare the source-coverage matrix to SOURCE_MAP.json phase view phase6.",
    "Exercise every tier at each individual family cap and at the conjunctive total/expanded/edge/depth/fan-out/resource boundaries, then prove one-over and simultaneous-dimension violations fail before allocation with stable operator-visible reasons.",
    "Exercise multiple deployments for one tenant and multiple isolated tenants so per-strategy success cannot bypass tenant concurrency, provider-subscription, worker, memory, or database ceilings.",
    "Use disposable PostgreSQL with genuinely concurrent sessions or processes to prove same-key activation has exactly one winner; aliases, stale epochs, retries, restarts, pause/resume, replace/retire, expiry, and roll cannot create a second entry authority.",
    "Run the GOLD/CRUDEOIL simultaneous-buy case and one immutable strategy bound to three instruments under both sufficient and insufficient account capacity; prove deterministic outcomes, exact per-binding lineage, no double-spend, no starvation, and atomic aggregate account limits.",
    "Exercise reject, cancel, cancel-replace, partial and multiple fills, out-of-order events, ambiguous broker acknowledgement, publish-success/local-mark failure, crash and restart at every reservation/order boundary, external/manual positions, and delayed fee or balance changes; prove idempotent recovery and no leaked or over-released capacity.",
    "Prove old-position exit/protection/cancel/reconcile authority survives replacement and every entry-blocking condition, while the old deployment cannot regain entry authority and the new deployment cannot silently inherit the old position.",
    "Exercise paper/live book separation, broker-level netting with distinct virtual books, ordered multi-leg leases, account kill and risk-stop races, provider/data staleness, and concurrent tenants on PostgreSQL; no SQLite-only result may satisfy a concurrency or migration claim.",
    "Prove policy-version changes preserve semantic strategy hashes, preserve exact attribution, and produce explicit grandfather/re-preflight/pause outcomes without granting deployment or live authority.",
    "Validate goal-capsule dependencies, routes, parallel budgets, path ownership, owner gates, and test cadence.",
    "Validate durable failure-learning fields, complete-universe coverage, independent-assurance ownership, invalidated-evidence links, and exact owner/capsule/deadline for every deferral.",
    "Run the complete .codex architecture test suite and git diff --check."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase6_architecture_handoff",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase6-review/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  }
}
---

# Phase 6 architecture goal

This capsule stays blocked until phase5-review is accepted. It creates future implementation goals; it does not implement them.

## Owner capacity directive

The Phase 5 numeric table is only the structural front door. Phase 6 must enforce it together with the compiled physical ResourcePlan and tenant/provider allocations. The UI may help users reduce or upgrade an over-budget strategy, but the authority path must return an exact refusal and must not auto-delete nodes, narrow an option window, reduce data quality, or substitute a cheaper execution plan without a new explicit user decision and binding.
