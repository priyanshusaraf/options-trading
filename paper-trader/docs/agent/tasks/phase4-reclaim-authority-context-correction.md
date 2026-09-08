---
{
  "id": "phase4-reclaim-authority-context-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Implement the accepted explicit Phase 4 reclaim-authority context so the real public reclaim dispatcher verifies the complete current authority chain and refuses at exact V2_RUNTIME_UNAVAILABLE before claim or any other side effect, while preserving v1 and keeping operational v2 reclaim disabled.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "After the preceding Sol-medium architecture capsule is accepted, one fresh Terra-medium implementation owner may edit only the declared product, test, report, deployability, defect-pattern, capsule-evidence paths, and may dispatch exactly one declared Luna-medium evidence-only child after the owner freezes product and tests. No Phase 5, schema, migration, frontend, provider, broker, deployment, credentials, production, live, or money work is authorized.",
    "stopping_condition": "Complete only when the real public dispatch_all_reclaimable and dispatch_reclaimable route supplies the accepted closed authority context to both loader calls; the canonical plan is internally derived from persisted receipt plus current registry; missing, stale, incomplete, and complete-current paths refuse in the required order before every named side effect; v1 and disabled-research startup behavior remain exact; focused current-byte SQLite and proportional PostgreSQL evidence, controlled mutation kills with exact restoration, protected/scoped hashes, and one attributable evidence package pass. Stop if the architecture is not accepted or implementation needs a schema, migration, hidden global, generic dispatcher, second verifier, operational v2 runtime, provider/broker change, deployment, or live/money authority."
  },
  "risk_tags": [
    "critical",
    "authority-context",
    "job-reclaim",
    "consumer-side-effects",
    "fresh-process",
    "v1-compatibility"
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
    }
  ],
  "dependency_gate": "phase4-reclaim-authority-context-architecture-correction",
  "allowed_paths": [
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/app/backtest/sweep.py",
    "paper-trader/backend/app/backtest/reclaim_authority.py",
    "paper-trader/backend/app/ir/v2_graph_versions.py",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/tests/test_phase4_reclaim_authority_context.py",
    "paper-trader/backend/tests/test_backtest_job_claims.py",
    "paper-trader/backend/tests/test_backtest_admission.py",
    "paper-trader/backend/tests/test_phase4_loader_authority_consumers.py",
    "paper-trader/backend/tests/test_backtest_batch_persistence.py",
    "paper-trader/backend/tests/test_backtest_tenant_isolation.py",
    "paper-trader/backend/tests/test_backtest_cache.py",
    "paper-trader/backend/tests/test_research_flag.py",
    "paper-trader/docs/reports/phase4-implementation.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase4-reclaim-authority-context-correction.md",
    ".agent/runs/phase4-reclaim-authority-context-correction"
  ],
  "product_paths_read_only": [
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/research",
    "paper-trader/backend/migrations",
    "paper-trader/frontend"
  ],
  "nonclaims": [
    "A passing correction proves only Phase 4 authority-verified pre-claim containment. It does not enable Component IR v2 execution, successful claim/reclaim, workers, results, providers, brokers, orders, or money paths.",
    "No schema, migration, dependency, service, configuration, provider, frontend, deployment, production, capacity, live, or release claim follows.",
    "P5-ADV-006-RUNTIME remains blocked behind Phase 5 architecture, its non-enabling graph-paper attribution schema, and a separately authorized exclusive runtime capsule.",
    "The adversarial matrix must restart under a fresh owner and prove every row independently after root accepts this bounded correction."
  ],
  "owner_gates": [
    "Stop if any code outside the accepted architecture's exact exclusive paths must change; the architecture owner may refine those paths before acceptance, but the implementation owner may not expand them.",
    "Stop before schema, migration, provider, broker, frontend, deployment, credentials, production data/use, operational v2 runtime, live, money, destructive, legal, or commercial action."
  ],
  "stop_conditions": [
    "A caller can supply or substitute the canonical plan or any authority fact, context is hidden in global/process state, or the sole actual loader/complete verifier is bypassed.",
    "Complete current authority reaches claim or another named side effect instead of exact V2_RUNTIME_UNAVAILABLE, or missing/stale authority does not refuse earlier.",
    "The public dispatcher, startup path, exact-id transactional classification, post-claim loader call, disabled-research behavior, or legacy v1 behavior is untested through the real seam.",
    "A required mutation survives, restored bytes differ, a protected hash changes, frontend/provider/deployment scope changes, or attributable evidence is incomplete."
  ],
  "deployment_impact": {
    "classification": "schema-free-phase4-reclaim-authority-context-hardening",
    "required_evidence": "Prove explicit startup-to-dispatch context ownership, internally derived canonical plan, both real loader invocations, stable refusal ordering, zero named side effects, v1 compatibility, disabled-research behavior, exact current migration heads, focused SQLite and proportional disposable PostgreSQL 16 behavior where persistence dialect matters, protected hashes, and local-only nonclaims."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "children": "gpt-5.6-luna",
    "child_reasoning_effort": "medium",
    "child_agent_role": "luna-worker",
    "service_tier": "default"
  },
  "parallel_budget": 1,
  "owner_milestones": [
    "owner_product_test_source_map_frozen",
    "owner_attributable_evidence_frozen"
  ],
  "assignments": [
    {
      "id": "phase4_reclaim_authority_context_evidence",
      "agent": "luna-worker",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "medium",
      "mode": "write-evidence-only",
      "depends_on": [
        "owner_product_test_source_map_frozen"
      ],
      "read_paths": [
        "paper-trader/backend/app/backtest/repository.py",
        "paper-trader/backend/app/backtest/sweep.py",
        "paper-trader/backend/app/backtest/reclaim_authority.py",
        "paper-trader/backend/app/ir/v2_graph_versions.py",
        "paper-trader/backend/app/main.py",
        "paper-trader/backend/tests/test_phase4_reclaim_authority_context.py",
        "paper-trader/backend/tests/test_backtest_job_claims.py",
        "paper-trader/backend/tests/test_backtest_admission.py",
        "paper-trader/backend/tests/test_phase4_loader_authority_consumers.py",
        "paper-trader/backend/tests/test_backtest_batch_persistence.py",
        "paper-trader/backend/tests/test_backtest_tenant_isolation.py",
        "paper-trader/backend/tests/test_backtest_cache.py",
        "paper-trader/backend/tests/test_research_flag.py"
      ],
      "write_paths": [
        ".agent/runs/phase4-reclaim-authority-context-correction/luna_evidence"
      ],
      "output": ".agent/runs/phase4-reclaim-authority-context-correction/luna_evidence/report.md"
    }
  ],
  "acceptance": [
    "The implementation follows the accepted architecture exactly and uses one typed explicit context through startup, dispatch_all_reclaimable, dispatch_reclaimable, and both actual loader invocations; no hidden session, global registry, caller plan, generic authority dispatcher, or second verifier exists.",
    "In one execution transaction SQLite takes admission-scoped BEGIN IMMEDIATE before enumeration and PostgreSQL locks the exact candidate rows FOR UPDATE. The immutable snapshot records id, owner, state, admission address, cancellation, claim token, and expiry. Only explicit classified legacy ids may be conditionally reconciled or claimed with every predicate preserved; no broad owner mutation or fresh selector is allowed.",
    "A v2 candidate anywhere in the locked owner set receives the actual loader preflight and causes deterministic owner-level head-of-line refusal with zero mutation for all rows. Insert-after-enumeration stays outside the closed ids; any state, owner, admission, cancellation, token, or expiry transition causes zero affected rows, rollback, and refusal.",
    "The canonical plan is derived internally from the exact persisted receipt and current registry before complete verification. Missing context returns PHASE4_CONTEXT_REQUIRED before claim; missing or stale persisted authority refuses earlier than terminal refusal; only the complete current chain reaches exact V2_RUNTIME_UNAVAILABLE before claim, reclaim, provider, cache, worker, claim token, result, broker, order, or money effects.",
    "Real public-seam tests use genuine persisted execution and research authority, process-death or independently reconstructed context where required, an aware cutoff, and direct side-effect tripwires. They do not monkeypatch the decisive loader/verifier or manually preverify authority.",
    "Startup with research disabled remains fail closed and does not create hidden research state. Startup with research configured owns one lifespan synchronous sessionmaker; each dispatch lazily opens at most one synchronous Session, reuses its exact registry and aware cutoff at both loader calls, and closes it on every success, refusal, and exception.",
    "Legacy v1 reclaim call shape, claim/reclaim behavior, returned values, persistence bytes, and supported startup behavior remain unchanged.",
    "Controlled reversible mutations kill missing-context routing, canonical-plan derivation, the complete verifier invocation, terminal-refusal ordering, no-side-effect guards, removal of SQLite reservation or PostgreSQL row lock, restoration of a broad owner update, and removal of each transition predicate; all owned product/test bytes are restored exactly before final selectors.",
    "The exact focused current-tree selectors, syntax, scoped diff, protected hashes, frontend/provider/deployment exclusions, evidence hashes, and report accuracy pass. Root acceptance may make only a fresh adversarial-matrix owner ready."
  ],
  "test_plan": [
    "Preserve the current contextless public-reclaim counterexample before editing, then implement only the frozen interface and tests.",
    "Run focused public reclaim, loader authority, job claim/reclaim, startup-disabled, fresh-process, pure-v1 direct/startup golden compatibility, mixed-v1-v2 head-of-line, insert-after-enumeration, transition-race, Session-close, and side-effect tripwire selectors on SQLite plus proportional PostgreSQL locking evidence. Avoid broad suites for confidence.",
    "After product/test/source-map freeze, dispatch only the declared Luna-medium evidence child. Run controlled mutations, restore exact hashes, rerun the focused selector, and seal attributable command/cwd/selector/node/exit evidence."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_reclaim_authority_context_owner",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/app/backtest/sweep.py",
      "paper-trader/backend/app/backtest/reclaim_authority.py",
      "paper-trader/backend/app/ir/v2_graph_versions.py",
      "paper-trader/backend/app/main.py",
      "paper-trader/backend/tests/test_phase4_reclaim_authority_context.py",
      "paper-trader/backend/tests/test_backtest_job_claims.py",
      "paper-trader/backend/tests/test_backtest_admission.py",
      "paper-trader/backend/tests/test_phase4_loader_authority_consumers.py",
      "paper-trader/backend/tests/test_backtest_batch_persistence.py",
      "paper-trader/backend/tests/test_backtest_tenant_isolation.py",
      "paper-trader/backend/tests/test_backtest_cache.py",
      "paper-trader/backend/tests/test_research_flag.py",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md"
    ],
    "exclude_paths": [
      "paper-trader/frontend",
      "paper-trader/backend/app/engine/kite_venue.py",
      "paper-trader/backend/app/engine/venue.py",
      "paper-trader/backend/app/providers/brokers.py"
    ],
    "output": ".agent/runs/phase4-reclaim-authority-context-correction/owner/report.md",
    "verdicts": [
      "CORRECTED",
      "BLOCKED"
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

# Phase 4 reclaim authority-context correction

This implementation capsule opens only after the preceding architecture
capsule is accepted. It hardens the public reclaim path so complete Phase 4
authority is verified by the actual loader before the existing terminal v2
refusal, without enabling operational v2 reclaim.
