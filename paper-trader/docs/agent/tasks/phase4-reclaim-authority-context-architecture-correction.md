---
{
  "id": "phase4-reclaim-authority-context-architecture-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Freeze the smallest explicit authority-context contract that lets the real public Phase 4 reclaim-dispatch seam verify the complete current chain and reach exact V2_RUNTIME_UNAVAILABLE before claim or any other side effect, without enabling Component IR v2 execution or weakening the later P5-ADV-006-RUNTIME obligation.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner authorized all bounded work required to finish Phase 4. This capsule permits one fresh Sol-medium architecture owner to inspect the current reclaim, loader, startup, authority, and plan-construction seams and edit only the declared documentation, capsule, programme, CURRENT, and ignored evidence paths. Product, tests, schemas, migrations, package, frontend, providers, deployment, credentials, production, live, and money bytes remain read-only.",
    "stopping_condition": "Complete only when one explicit typed reclaim-authority context and lifecycle is frozen from application startup through dispatch_all_reclaimable and dispatch_reclaimable into both actual load_verified_admission calls; the canonical plan is derived internally from the exact persisted receipt and explicit registry rather than accepted from a caller; research-session ownership, aware cutoff creation, disabled-research startup behavior, stale and missing refusal order, complete-current terminal V2_RUNTIME_UNAVAILABLE, legacy-v1 compatibility, and every no-side-effect boundary are exact; the implementation capsule has disjoint bounded ownership and direct evidence requirements; and Phase 5 operational reclaim remains blocked. Stop if closure needs hidden globals, a generic authority dispatcher, a second verifier, schema or migration work, provider/broker behavior, runtime enablement, deployment, or live/money authority."
  },
  "risk_tags": [
    "critical",
    "architecture-correction",
    "authority-context",
    "job-reclaim",
    "consumer-side-effects",
    "phase-boundary"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "9. Ownership, authority, and persistence",
        "13.2 Persistence, reconstruction, and refusal",
        "13.3 Adversarial owner matrix",
        "13.4 High findings and blocked use",
        "13.5 Stale evidence and revalidation"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "5. Verification cadence",
        "8. Authority-correction serial route"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "Phase 4 ownership"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "DP-008 — Manual prerequisite verification substituted for the consuming seam"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase4-adversarial-matrix-closure.md",
      "sections": [
        "Phase 4 adversarial matrix closure"
      ]
    }
  ],
  "dependency_gate": "phase4-adversarial-contract-correction",
  "input_evidence": [
    ".agent/runs/phase4-adversarial-contract-correction/root_acceptance/acceptance.md",
    ".agent/runs/phase4-adversarial-matrix-closure/owner/residual_contract.md",
    ".agent/runs/phase4-adversarial-matrix-closure/owner/owner_gate_adv006.md",
    ".agent/runs/phase4-adversarial-matrix-closure/owner/adv006-public-seam-signature.log",
    ".agent/runs/phase4-adversarial-matrix-closure/owner/adv006-existing-contextless-selector.log"
  ],
  "architecture_contract": {
    "context_type": "One frozen ReclaimAuthorityContext contains exactly the current immutable PlatformRegistry and the existing lifespan-owned synchronous research SQLAlchemy sessionmaker; it contains no Session, plan, cutoff, admission, owner, dataset, assessment, mode, or callback.",
    "session_lifetime": "dispatch_reclaimable opens at most one synchronous research Session lazily for a v2 owner mutation set, reuses that exact Session at both existing loader calls, and closes it on every success, refusal, and exception. Research-disabled startup supplies no context and opens no hidden research engine, factory, or Session.",
    "cutoff_lifetime": "dispatch_reclaimable creates one timezone-aware UTC cutoff at public entry and reuses that exact cutoff with the same registry and research Session at both loader calls.",
    "canonical_plan": "reconstruct_phase4_artifact alone compiles the canonical DataRequirementPlan from the exact persisted receipt's embedded document plus the explicit current registry and returns it in PersistedPhase4Artifact; load_verified_admission accepts no caller Phase 4 plan and passes the returned plan to the sole require_phase4_current verifier.",
    "atomic_order": "dispatch_all_reclaimable never reconciles before dispatch. In one execution transaction SQLite acquires the existing backtest:admission BEGIN IMMEDIATE reservation before enumeration, while PostgreSQL locks the exact deterministic candidate rows SELECT FOR UPDATE. The snapshot records every predicate for pending, expired-running, and claimless-running rows and preflights every v2 row. An all-v1 startup path may reconcile only those explicit locked legacy ids and claim one explicit classified id through conditional mutations preserving owner, state, admission, cancellation, token, and expiry predicates; it never runs a broad owner update or fresh selector. A concurrent insert remains outside the closed ids, and a row transition produces zero affected rows, rollback, and refusal. Direct dispatch retains its legacy no-pre-reconcile policy; startup selects this internal explicit-id policy.",
    "mixed_version_rule": "One v2 row anywhere in the deterministic locked owner mutation set causes accepted owner-level head-of-line refusal and zero row mutation for every v1 and v2 row. Only a locked all-v1 set runs the explicit-id legacy reconciliation and dispatcher with byte/row-equivalent values and effects.",
    "terminal_rule": "Missing context or disabled research refuses before session creation and every mutation or downstream effect; missing/stale authority refuses before terminal refusal; complete current authority reaches exact V2_RUNTIME_UNAVAILABLE before claim. The post-claim loader stays wired to the same context/session/cutoff but current v2 cannot reach it in Phase 4.",
    "non_enabling_rule": "No successful v2 claim/reclaim, provider, cache, worker, result, broker, order, or money behavior is enabled. P5-ADV-006-RUNTIME remains separate and blocked."
  },
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/reports/phase4-source-coverage.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase4-reclaim-authority-context-architecture-correction.md",
    "paper-trader/docs/agent/tasks/phase4-reclaim-authority-context-correction.md",
    "paper-trader/docs/agent/tasks/phase4-adversarial-matrix-closure.md",
    "paper-trader/docs/agent/tasks/phase4-final-review-4.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/runs/phase4-reclaim-authority-context-architecture-correction"
  ],
  "product_paths_read_only": [
    "paper-trader/backend",
    "paper-trader/frontend"
  ],
  "nonclaims": [
    "This capsule freezes architecture only. It does not change product or test behavior and does not make the adversarial matrix, final review, Phase 4, or any later phase ready.",
    "The context contract permits only complete-current authority verification followed by fail-closed V2_RUNTIME_UNAVAILABLE before claim. It does not enable successful v2 claim, reclaim, worker execution, result finalization, provider, broker, order, or money behavior.",
    "P5-ADV-006-RUNTIME remains a separate mandatory Phase 5 obligation after its non-enabling schema prerequisite and exclusive runtime capsule.",
    "No local architecture or test evidence proves deployment, production capacity, provider correctness, live authority, or release readiness."
  ],
  "owner_gates": [
    "Stop before any product, test, schema, migration, package, provider, frontend, deployment, credential, production, live, money, destructive, legal, or commercial change.",
    "Stop if explicit context cannot be supplied without hidden process state, inferred caller plan, a second authority verifier, or Phase 5 runtime reachability."
  ],
  "stop_conditions": [
    "The architecture leaves session ownership, registry identity, canonical plan derivation, aware cutoff, disabled-research startup, or either pre-claim/post-claim loader call implicit.",
    "The implementation capsule could accept a caller-forged plan, skip the sole require_phase4_current verifier, permit any named side effect before refusal, or change legacy v1 behavior.",
    "ADV-006 could be interpreted as successful operational reclaim evidence or P5-ADV-006-RUNTIME is weakened, reordered, or made reachable.",
    "Scoped validation, protected hashes, source coverage, programme seriality, or capsule contracts fail."
  ],
  "deployment_impact": {
    "classification": "documentation-only-phase4-reclaim-authority-context-architecture",
    "required_evidence": "Trace the explicit context from startup to both reclaim loader invocations; prove the design remains schema-free and fail-closed; bind implementation and test ownership; preserve v1, current migration heads, Phase 5 blocks, protected paths, frontend exclusion, and all production/release nonclaims."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The architecture retains the sole load_verified_admission and require_phase4_current authority seams and defines one typed Phase 4 reclaim context rather than a parallel loader or generic dispatcher.",
    "The application owns the synchronous research-session lifetime explicitly. Startup supplies the lifespan-owned synchronous sessionmaker only when the research plane is configured; one lazy Session per owner invocation is closed on every exit, and disabled research remains a stable fail-closed path without a hidden engine, factory, or Session.",
    "The reclaim seam derives the canonical plan from the exact persisted Phase 4 receipt and explicit current registry inside the bounded context path. A caller cannot supply or substitute a plan, registry snapshot, assessment, dataset, owner, mode, or cutoff fact.",
    "An aware cutoff is created at the public dispatch boundary and remains exact for every verification attempt. Missing context returns PHASE4_CONTEXT_REQUIRED before claim; stale or missing authority refuses earlier than terminal V2_RUNTIME_UNAVAILABLE; a complete current chain alone reaches exact V2_RUNTIME_UNAVAILABLE before claim, reclaim, provider, cache, worker, claim token, result, broker, order, or money side effects.",
    "Both pre-claim inspection and post-claim verification call the actual loader with the same context, registry, synchronous research Session, and aware cutoff. SQLite BEGIN IMMEDIATE or PostgreSQL exact-row FOR UPDATE locking closes the classified mutation set; only explicit legacy ids may be conditionally reconciled or claimed, concurrent inserts stay outside it, predicate transitions roll back and refuse, a mixed v1/v2 set refuses the whole owner with zero mutation, and pure-v1 signatures, values, row bytes, and effects remain unchanged.",
    "The implementation capsule names exact exclusive product/test paths, one Terra-medium owner, at most one Luna-medium evidence-only child after product/test freeze, controlled mutations with byte restoration, current SQLite evidence, proportional disposable PostgreSQL 16 evidence only where a dialect boundary is exercised, and exact protected/scoped checks.",
    "Design, plan, source coverage, deployability, defect pattern, matrix, final-review, CURRENT, and programme contracts agree that this closes only Phase 4 containment. Matrix restart and final review remain serially blocked until implementation acceptance and fresh complete evidence."
  ],
  "test_plan": [
    "Inspect only the current public reclaim, startup, loader, authority-verifier, receipt, registry, and plan-construction code required to freeze the interface. Run no product tests or services.",
    "Validate JSON/TOML, programme order/dependencies, capsule contracts, source coverage, deployability statements, protected hashes, frontend exclusion, and scoped diffs.",
    "Write an evidence-backed architecture report and exact implementation route under the ignored assignment directory."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_reclaim_authority_context_architect",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "paper-trader/docs/reports/phase4-source-coverage.json",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/tasks/phase4-reclaim-authority-context-architecture-correction.md",
      "paper-trader/docs/agent/tasks/phase4-reclaim-authority-context-correction.md",
      "paper-trader/docs/agent/tasks/phase4-adversarial-matrix-closure.md",
      "paper-trader/docs/agent/tasks/phase4-final-review-4.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md"
    ],
    "exclude_paths": [
      "paper-trader/backend",
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/phase4-reclaim-authority-context-architecture-correction/owner/report.md",
    "verdicts": [
      "ARCHITECTURE"
    ]
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 4 reclaim authority-context architecture correction

The public reclaim dispatcher currently reaches the verified Phase 4 loader
without the explicit authority context that loader requires. This capsule
freezes the smallest fail-closed context route before any implementation work.

The architecture must keep the sole loader and verifier, derive rather than
accept the canonical plan, and preserve the current non-executable Component IR
v2 boundary. Successful operational reclaim remains a separate Phase 5 task.

Accepted architecture freezes a synchronous sessionmaker-backed context, one
lazy Session and one aware cutoff per owner invocation, internally derived plan
identity, and an atomic full-set preflight/recheck under the existing
`backtest:admission` reservation. Mixed owner sets deliberately head-of-line
refuse without row mutation. This acceptance changes no product or test byte.
