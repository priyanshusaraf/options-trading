---
{
  "id": "phase7-architecture",
  "phase": "phase7",
  "status": "blocked",
  "goal": "Architect Strategy OS phase7: Dynamic derivatives, incremental runtime, and operational economics, producing bounded goal capsules and evidence gates without implementing product code.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after the Phase 7 design, implementation plan, source-coverage matrix, dependency-ordered implementation goal capsules, exact Sol-high review capsule, and programme expansion validate. Stop with the goal active for an owner gate or unresolved conflict."
  },
  "risk_tags": [
    "critical",
    "phase-architecture",
    "phase7"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "Phase 7 ownership",
        "V1 release gate"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md",
      "sections": [
        "Phase 7: Dynamic derivatives, incremental runtime, and operational economics",
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
        "5. Dynamic derivative identity",
        "Critical invariant",
        "6. Options lifecycle model",
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
        "7. Numerical validity"
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
        "9. Degraded deployment states"
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
        "8. Dynamic option-window subscription management",
        "9. Resource QoS priorities",
        "10. Per-deployment resource ceilings",
        "11. Provider capability matrix",
        "Data",
        "Execution",
        "Historical market support",
        "12. Provider fallback",
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
        "4. Owner seed scenarios",
        "5. Mandatory adversarial discovery matrix",
        "Instrument and contract identity",
        "Deployment and control-plane races",
        "Order lifecycle and reconciliation",
        "Account-wide capital and risk",
        "Multi-leg and portfolio actions",
        "Safety and degraded operation",
        "Derivatives-market and tier stress",
        "Observability and economics",
        "8. Requirements carried through Phase 7",
        "9. Post-Phase-7 audit gate",
        "10. Acceptance evidence",
        "11. Nonclaims and owner gates"
      ]
    }
  ],
  "dependency_gate": "phase6-review",
  "allowed_paths": [
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/superpowers/specs/phase7-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase7-strategy-os.md",
    "paper-trader/docs/reports/phase7-source-coverage.json",
    "paper-trader/docs/agent/tasks",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase7-architecture"
  ],
  "nonclaims": [
    "This architecture goal does not implement or accept Phase 7.",
    "It grants no live authority, deployment, VPS, credential, production-data, destructive, or unrelated future-phase authority."
  ],
  "owner_gates": [
    "Stop before product implementation.",
    "Stop before live authority, material live execution-semantics changes, live credentials, VPS, production data, deployment, destructive work, or licence-sensitive adoption.",
    "Frontend paths may appear only when this phase's master-sequence scope requires them and the generated implementation capsule opens them explicitly."
  ],
  "stop_conditions": [
    "The dependency gate phase6-review lacks dual passing SPEC and QUALITY verdicts.",
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
        ".agent/runs/phase7-architecture/existing_capability_audit"
      ],
      "output": ".agent/runs/phase7-architecture/existing_capability_audit/report.md"
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
        ".agent/runs/phase7-architecture/source_coverage_audit"
      ],
      "output": ".agent/runs/phase7-architecture/source_coverage_audit/report.md"
    }
  ],
  "acceptance": [
    "Every affected deployment-contract dimension has current evidence or an exact owning future capsule; no deployment debt is deferred vaguely.",
    "Accepted preceding contracts and existing implementation are audited before proposing changes.",
    "Every SOURCE_MAP.json phase7 entry has an explicit design, task, test, nonclaim, or deferral disposition.",
    "The design and plan preserve one canonical IR and existing ownership/authority boundaries.",
    "Dynamic derivatives and options are a separate Critical capacity class: the design publishes measured Standard, Pro, and Desk envelopes for exact-contract requests, option-chain windows, quote/OI/depth/trade-flow subscriptions, incremental recomputation, cache fan-out, and concurrent permitted user queries.",
    "Derivatives accounting uses physical instruments, provider products/contracts, fields, depth, update/event rate, recomputation fan-out, retention, and concurrency; strike distance or an ATM-relative label is not a cost proxy, and one exact deep-ITM or deep-OTM contract is not penalized merely for distance.",
    "The capacity gate covers market-open, market-close, expiry-day and expiry-roll bursts, high-volatility turnover, deep-ITM/deep-OTM exact selectors, simultaneous broad and narrow chains, multiple expiries/underlyings, held-contract priority, cache stampedes, cold starts, mass reconnects, provider throttling/outage, and cross-tenant bursts.",
    "Standard, Pro, and Desk are tested at representative ordinary load, every admitted structural/resource maximum, simultaneous maxima allowed by the conjunctive policy, and deliberate over-limit abuse; Pro and Desk receive materially deeper and more concurrent testing than Standard.",
    "Backpressure preserves exits, protection, held-position data, broker reconciliation, and other P0 work before entries, research, scans, broad option windows, and UI refresh; overload must remain bounded and observable without cross-tenant starvation or unbounded queue, memory, database-pool, or provider-quota growth.",
    "Measured workloads include same-instrument authority-conflict bursts, different-instrument account saturation, one-strategy/many-instrument signals, reservation release and recovery, and derivative alias/expiry/roll ambiguity so capacity evidence covers the authority and account-risk paths under load rather than isolated query throughput alone.",
    "Every tier envelope states fairness, admission, refusal, queue, reservation, provider, database, cache, memory, compute, and recovery bounds. Higher tiers receive more measured headroom and concurrency but no weaker identity, account-risk, exit, protection, isolation, or reconciliation guarantee.",
    "The Phase 5 beta node caps may change only from dated reproducible Phase 7 measurements with workload definitions, duration, repetitions, hardware/service configuration, provider simulators or approved fixture contracts, p95/p99 and saturation evidence, recovery behavior, and unit-cost/tier-margin formulas; local benchmarks alone never imply production readiness.",
    "Implementation work is split into fresh durable-goal capsules with exact dependencies, allowed paths, exclusive write ownership, observable acceptance, and proportional tests.",
    "The programme implementation placeholder is expanded into ordered slice stages and an exact phase-review capsule.",
    "The final phase gate requires one Sol-high goal with separate SPEC and QUALITY verdicts."
  ],
  "test_plan": [
    "Validate all structured artifacts and references.",
    "Compare the source-coverage matrix to SOURCE_MAP.json phase view phase7.",
    "Run a risk-weighted derivatives matrix across Standard, Pro, and Desk covering exact deep-ITM/deep-OTM contracts, narrow and broad option chains, multiple quote/OI/depth/trade-flow requests, multiple underlyings and expiries, expiry overlap, held contracts, burst reconnects, provider throttling, and concurrent tenants.",
    "For every workload publish exact request mix, graph/resource vector, concurrency, duration, repetitions, dataset/provider-fixture contract, compute/memory/database/cache/provider consumption, queue age, p50/p95/p99 latency, error/refusal/degradation counts, recovery time, and cost per active strategy/tenant/minute.",
    "Prove admitted-max workloads stay inside the declared envelope, over-limit workloads refuse or shed lower-priority work before saturation, no P0 event is lost or starved, no cross-tenant leakage occurs, and resource use returns to a bounded baseline after the burst.",
    "During market-open, expiry, volatility and reconnect bursts, contend same-instrument entry authority and saturate one account with different-instrument signals; measure one-winner behavior, reservation fairness, refusal latency, leaked-capacity alarms, exit/protection latency, recovery, and steady-state resource return.",
    "Run exact derivative identity and provider-ambiguity cases across aliases, weekly/monthly overlap, expiry, roll, rapid ATM movement, deep-ITM/deep-OTM contracts, held-contract priority, multiple underlyings and expiries, and cold-cache or throttled-provider conditions.",
    "For Standard, Pro, and Desk publish ordinary, individual-maximum, simultaneous-conjunctive-maximum, sustained saturation, and deliberate-abuse results; report p50/p95/p99, fairness and starvation, cost, recovery, and the measured headroom that justifies every commercial limit.",
    "Calibrate the Phase 5 structural hypotheses and Phase 6 weighted/concurrency ceilings only from these measurements, preserving a dated decision record and explicit commercial margin sensitivity for Standard, Pro, and Desk.",
    "Validate goal-capsule dependencies, routes, parallel budgets, path ownership, owner gates, and test cadence.",
    "Run the complete .codex architecture test suite and git diff --check."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase7_architecture_handoff",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase7-review/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  }
}
---

# Phase 7 architecture goal

This capsule stays blocked until phase6-review is accepted. It creates future implementation goals; it does not implement them.

## Owner derivatives-capacity directive

The options path must be tested as a bursty shared-data system, not as a larger copy of an equity strategy. Phase 7 must distinguish provider subscriptions from user requests, deduplicate safe shared calculations without sharing tenant authority, and meter both the physical upstream footprint and downstream per-tenant compute/fan-out. The ordinary Standard experience must still support exact deep contracts and useful bounded windows. Pro and Desk buy wider windows, more strategies, and more concurrency only when the measured server and provider envelope supports them.
