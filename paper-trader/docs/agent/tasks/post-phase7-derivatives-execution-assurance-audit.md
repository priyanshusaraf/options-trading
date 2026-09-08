---
{
  "id": "post-phase7-derivatives-execution-assurance-audit",
  "phase": "interphase-7-8",
  "status": "blocked",
  "goal": "Run one independent read-only Sol-high audit of the completed Phase 5 through 7 derivatives, execution-authority, account-risk, concurrency, tier-capacity, and runtime-economics foundation before Phase 8 begins.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "On 2026-08-18 the owner authorized this post-Phase-7 deep dive, using the listed same-instrument, different-instrument, one-strategy-many-instrument, and derivatives-load scenarios as starting points rather than a closed test list. The first pass is read-only and may not become an uncontrolled rewrite.",
    "stopping_condition": "Complete only after phase7-review has current separate SPEC and QUALITY PASS verdicts; the audit binds its intake and final snapshots; reconstructs the Phase 5 through 7 contracts without trusting historical acceptance claims; executes the mandatory and newly discovered adversarial cases through real persistence and authority paths; publishes tier-specific derivatives measurements; writes a severity-ranked finding register and transitive evidence-invalidation map; and issues an exact closure recommendation. The audit may complete with findings, but Phase 8 remains blocked until post-phase7-derivatives-execution-critical-closure passes."
  },
  "risk_tags": [
    "critical",
    "programme-assurance",
    "derivatives",
    "execution-authority",
    "account-risk",
    "postgresql-concurrency",
    "capacity",
    "runtime-economics",
    "commercial-tiers",
    "recovery"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/program/owner-steers/06-POST-PHASE7-DERIVATIVES-EXECUTION-ASSURANCE.md",
      "sections": [
        "Goal",
        "1. Timing and authority",
        "2. Current evidence boundary",
        "3. Entry authority and position ownership",
        "4. Owner seed scenarios",
        "5. Mandatory adversarial discovery matrix",
        "6. Requirements carried through Phase 5",
        "7. Requirements carried through Phase 6",
        "8. Requirements carried through Phase 7",
        "9. Post-Phase-7 audit gate",
        "10. Acceptance evidence",
        "11. Nonclaims and owner gates"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/03-DEPLOYMENT-EXECUTION-TRUST.md",
      "sections": [
        "Goal",
        "1. Deployment object",
        "2. Deployment preflight",
        "4. Multi-strategy position ownership",
        "5. Open-position version ownership",
        "6. Protection semantics",
        "7. Order semantics",
        "9. Degraded deployment states"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md",
      "sections": [
        "Goal",
        "1. Compile a resource plan with every strategy",
        "2. Incremental streaming runtime",
        "5. Shared calculations",
        "8. Dynamic option-window subscription management",
        "9. Resource QoS priorities",
        "10. Per-deployment resource ceilings",
        "11. Provider capability matrix",
        "13. Cost telemetry"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md",
      "sections": [
        "Goal",
        "1. Risk-weighted verification",
        "2. Test rule",
        "3. Test cadence",
        "7. Canonical acceptance scenarios",
        "8. Guard against scope drift"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md",
      "sections": [
        "Global constraints",
        "Phase 5: First-party language and scalable research",
        "Phase 6: Deployment binding and Strategy Preflight",
        "Phase 7: Dynamic derivatives, incremental runtime, and operational economics",
        "Programme closure"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase5-architecture.md",
      "sections": [
        "Phase 5 architecture goal",
        "Owner capacity directive"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase6-architecture.md",
      "sections": [
        "Phase 6 architecture goal",
        "Owner capacity directive"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase7-architecture.md",
      "sections": [
        "Phase 7 architecture goal",
        "Owner derivatives-capacity directive"
      ]
    }
  ],
  "dependency_gate": "phase7-review",
  "allowed_paths": [
    ".agent/runs/post-phase7-derivatives-execution-assurance-audit"
  ],
  "product_paths_read_only": [
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/docs",
    ".agent/runs"
  ],
  "nonclaims": [
    "The audit does not repair, refactor, redesign, migrate, deploy, price, or accept product code. It records evidence and proposes the smallest bounded corrections.",
    "Historical Phase 5 through 7 PASS verdicts are inputs, not proof. A failed assumption makes dependent evidence STALE/REQUIRES RECHECK without rewriting immutable verdicts.",
    "Disposable PostgreSQL, provider simulators, and controlled load tests establish only their named local evidence. They do not prove production readiness, live authority, real provider capacity, legal data rights, or final commercial economics.",
    "No frontend, provider, broker, credential, VPS, deployment, production-data, destructive, live-order, or money action is authorized."
  ],
  "owner_gates": [
    "Stop before any retained edit outside the audit evidence directory.",
    "Stop before accessing live credentials, provider accounts, production data, VPS or cloud resources, placing orders, moving money, deploying, or making legal, regulatory, licence, pricing, tax, or commercial commitments.",
    "Report a Critical finding immediately and continue the bounded read-only pattern search. Route corrections to the closure stage; do not implement them in this audit."
  ],
  "stop_conditions": [
    "phase7-review lacks current separate SPEC and QUALITY PASS verdicts or its package lineage is stale.",
    "The audit cannot bind the complete dirty tree, evidence manifest, current migrations, current schemas, or actual test and benchmark commands.",
    "A claimed authority or reservation result uses only SQLite, one process, mocked loaders, or synthetic metadata rather than disposable PostgreSQL concurrency and real persistence paths.",
    "Tier or derivatives conclusions omit workload definitions, admitted resource vectors, durations, repetitions, service configuration, p95 and p99, saturation, recovery, refusal behavior, or unit-cost formulas."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "owner_agent_role": "default",
    "dispatch_mode": "separate-user-owned-task",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The audit binds exact repository, programme, package, evidence, schema, migration, frontend, and runtime boundaries at intake and completion and labels every material claim as repository fact, measured evidence, inference, policy, historical claim, or unknown.",
    "Disposable PostgreSQL multi-session and multi-process tests prove exactly one entry-authority winner for one account/book/mode/canonical-instrument key, stale fencing refusal, and stable conflict behavior across activation, replacement, pause, retirement, expiry, roll, restart, and reclaim.",
    "The GOLD/CRUDEOIL concurrent-signal case and one immutable strategy bound to three instruments run with sufficient and insufficient account capacity, preserving exact per-binding attribution, deterministic account-wide decisions, no double-spend, and no leaked reservation.",
    "Every entry-blocking case preserves exit, protection, cancel, kill, and reconciliation authority; old positions retain creator-version ownership and cannot be silently transferred.",
    "The audit exercises crash, retry, duplicate, reorder, partial fill, ambiguous timeout, external account change, multi-leg, manual-position, provider ambiguity, derivative alias, expiry, roll, cache, queue, and degraded-service cases and adds any plausible cases discovered from the final code.",
    "Standard, Pro, and Desk have reproducible ordinary, admitted-maximum, simultaneous-conjunctive-maximum, sustained-saturation, burst, recovery, and abuse measurements across exact contracts, option windows, quotes, OI, Greeks, depth, trade flow, multiple underlyings and expiries, with fairness and cost evidence.",
    "The final report maps each finding to affected claims and evidence, distinguishes Critical closure blockers from contained lower-severity debt, and recommends no production, provider, live, or commercial readiness beyond the evidence."
  ],
  "test_plan": [
    "Reconstruct request or activation through binding, lease, account reservation, signal, order, acknowledgement, fill, virtual position, exit, release, reconciliation, restart, and operator evidence without monkeypatching a Critical seam.",
    "Run disposable PostgreSQL concurrency cases with barriers and independent processes; repeat enough to expose ordering races and record database state, lock or lease epoch, reservation state, outcomes, latency, and recovery.",
    "Run the complete steer §5 adversarial matrix plus discovered cases, retaining one machine-readable row per case with expected invariant, real path, database/process boundary, observation, classification, and artifact hashes.",
    "Run controlled derivatives and tier workloads with fixture or approved provider contracts and publish physical subscriptions, events, compute, memory, database, cache, queue, storage, provider demand, p50/p95/p99, refusal and degradation counts, recovery, and cost formulas.",
    "Validate source coverage, transitive evidence invalidation, protected boundaries, exact package lineage, scoped diff checks, and report consistency without broad mutation or deployment."
  ],
  "review": {
    "required": false,
    "assignment_id": "post_phase7_derivatives_execution_assurance_audit",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend",
      "paper-trader/frontend",
      "paper-trader/docs",
      ".agent/runs"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/post-phase7-derivatives-execution-assurance-audit/report.md",
    "verdicts": [
      "ASSURANCE",
      "EVIDENCE_CURRENTNESS"
    ],
    "max_rechecks": 0
  }
}
---

# Post-Phase-7 derivatives and execution assurance audit

Run this independent read-only audit only after Phase 7 has current dual PASS. The owner's scenarios are mandatory seeds, not the boundary of the investigation. Phase 8 remains blocked until the following Critical-closure stage passes.
