---
{
  "id": "phase1-4-foundation-audit",
  "phase": "interphase-4-5",
  "status": "accepted",
  "goal": "Run one independent, read-only Sol-high adversarial audit of the Strategy OS Phase 1-4 foundation, reconstructing contracts from repository evidence without trusting historical PASS verdicts and producing a risk-ranked correction and evidence-invalidation map before Phase 5 architecture can start.",
  "goal_contract": {
    "create_before_work": true,
    "dispatch_mode": "separate-user-owned-task",
    "owner_authorization": "On 2026-08-17 the owner explicitly authorized one rare independent foundation-audit task after Phase 4 completes. The repository contract caps it at Sol high. The first pass is read-only and may not repair or redesign product code. Hard architecture, frontend, provider, deployment, credential, production, live-authority, and money boundaries remain closed.",
    "stopping_condition": "Complete only after the independent owner reconstructs the Phase 1-4 foundational contracts, answers what assumptions have never actually been tested, executes the declared adversarial edge-case matrix with explicit evidence classifications, traces at least one real lifecycle for every cross-layer Critical invariant, writes a transitive evidence-invalidation map, updates no product or programme state, and issues a severity-ranked audit report. The stage may complete with findings, but phase1-4-foundation-critical-closure remains blocked until every Critical finding is closed or an evidence-backed no-Critical disposition is recorded."
  },
  "risk_tags": [
    "critical",
    "programme-foundation-audit",
    "identity",
    "immutability",
    "authority",
    "tenancy",
    "causality",
    "persistence",
    "migration",
    "cache-provenance",
    "cross-version",
    "deployability"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "Strategy OS defect-pattern register",
        "Status and evidence rules",
        "DP-001 — Distinct facts collapsed into one representation",
        "DP-002 — Syntactic self-consistency mistaken for authority",
        "DP-003 — Mocked seam presented as lifecycle evidence",
        "DP-004 — Immutable envelope over mutable or time-incoherent facts"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md",
      "sections": [
        "Global constraints",
        "Phase 1: Ownership and tenant foundation",
        "Phase 2: PostgreSQL and production-concurrency foundation",
        "Phase 3: Causal strategy admission",
        "Interphase 3 → 4: Component IR v2 structural Port contract",
        "Phase 4: Market truth, numeric validity, and data capability",
        "Programme closure"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-11-multi-user-contract-design.md",
      "sections": [
        "Outcome",
        "Identity model",
        "First vertical slice",
        "Remaining Phase 1 boundaries",
        "Invariants",
        "Acceptance evidence"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-12-user-research-ownership-design.md",
      "sections": [
        "Purpose",
        "Ownership rules",
        "Canonical graph identity and private IP",
        "Relational application database",
        "Research database",
        "Repository and service contract",
        "Failure and privacy behavior",
        "Acceptance tests",
        "Deferred boundaries"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/2026-08-12-phase2-postgresql-production-concurrency.md",
      "sections": [
        "Global constraints",
        "Task 1: Database URL and PostgreSQL execution-plane profile",
        "Task 2: Portable transaction, claim and query primitives",
        "Task 3: PostgreSQL research and ledger planes",
        "Task 4: Verified SQLite-to-PostgreSQL copy and cutover",
        "Task 5: Shared account leases, fencing and replicated control APIs",
        "Task 6: Shared event delivery and cache invalidation",
        "Task 7: Backup, restore, failure and workload proof"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-phase3-causal-strategy-contract-design.md",
      "sections": [
        "1. Outcome",
        "2. Scope",
        "3. Governing constraints",
        "4. Decisions and rejected alternatives",
        "5. Causal registry contract",
        "6. Admission model",
        "7. Reference and vectorised parity",
        "9. Persistence",
        "10. End-to-end wiring",
        "11. Failure behavior",
        "12. Acceptance and mutation gates",
        "13. Completion evidence"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md",
      "sections": [
        "1. Decision",
        "2. Current accepted boundary",
        "3. Scope and exclusions",
        "4. One public architecture",
        "5. Canonical v2 document",
        "8. Edge and binding contract",
        "10. Compound components",
        "11. Validation",
        "12. Evaluation",
        "13. Serialization and identity",
        "14. Admission and persistence",
        "15. Versioning",
        "17. Phase 4 handoff",
        "18. Deployability impact",
        "20. Acceptance conditions"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "1. Decision and boundary",
        "2. Existing architecture verdicts",
        "3. One accepted executable architecture",
        "4. Closed numeric validity contract",
        "5. Canonical instrument and market-truth model",
        "6. Data observations, alignment, and causality",
        "7. Data requirement and provider capability contracts",
        "8. Dataset provenance and cache identity",
        "9. Ownership, authority, and persistence",
        "10. Acceptance scenarios and refusals",
        "11. Deployment contract",
        "12. Deferred homes and nonclaims"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Proven foundations",
        "Open obligations",
        "Foundation blockers",
        "Reproducibility and operations blockers",
        "Phase 4 ownership",
        "Phase 5 ownership",
        "V1 release gate"
      ]
    }
  ],
  "dependency_gate": "phase4-final-review-5",
  "allowed_paths": [
    ".agent/runs/phase1-4-foundation-audit"
  ],
  "product_paths_read_only": [
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/docs",
    ".agent/runs"
  ],
  "nonclaims": [
    "The audit does not repair, refactor, redesign, migrate, deploy, or accept product code. It reports evidence, affected contracts, and proposed bounded corrections only.",
    "A Phase 4 PASS remains scoped to its reviewed boundary. If the audit invalidates an assumption, the affected PASS becomes STALE/REQUIRES RECHECK without rewriting historical evidence.",
    "The audit grants no Phase 5 implementation, frontend, provider/broker, credentials, deployment, production-data/use, capacity, live-authority, order, or money permission.",
    "Lower-severity findings do not automatically block Phase 5. They require explicit rationale, owner, containment proof, and future capsule or deadline. Every Critical architecture/invariant finding blocks Phase 5 until closed."
  ],
  "owner_gates": [
    "Stop before any product, test, migration, documentation, programme, package, or retained-evidence edit outside the audit evidence directory.",
    "Stop before frontend implementation, provider/broker action, credentials, VPS, deployment, production data/use, destructive work, live authority, money, legal/regulatory/commercial decisions, or automatic adoption of a proposed redesign.",
    "If a Critical finding appears, report it immediately and continue the read-only audit. Do not implement it; route it to phase1-4-foundation-critical-closure after owner and root disposition."
  ],
  "stop_conditions": [
    "phase4-final-review-5 lacks exact dual SPEC and QUALITY PASS or its package/evidence lineage is stale.",
    "The audit cannot bind its intake and final snapshots, distinguish repository fact from measured evidence and inference, or reproduce a claimed cross-layer path.",
    "The task begins changing product architecture instead of completing the read-only diagnosis, edge-case matrix, invalidation map, and correction proposals."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "owner_agent_role": "default",
    "dispatch_mode": "separate-user-owned-task",
    "mechanical_children": "gpt-5.6-luna",
    "mechanical_child_reasoning_effort": "medium",
    "service_tier": "default"
  },
  "parallel_budget": 4,
  "owner_milestones": [
    "owner_foundational_contract_map_frozen"
  ],
  "assignments": [
    {
      "id": "foundation_identity_authority_matrix",
      "agent": "default",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "medium",
      "mode": "read-only-evidence",
      "depends_on": [
        "owner_foundational_contract_map_frozen"
      ],
      "read_paths": [
        "paper-trader/backend/app/ir",
        "paper-trader/backend/app/strategy",
        "paper-trader/backend/app/core",
        "paper-trader/backend/app/db/models.py",
        "paper-trader/backend/research/domain"
      ],
      "write_paths": [
        ".agent/runs/phase1-4-foundation-audit/foundation_identity_authority_matrix"
      ],
      "output": ".agent/runs/phase1-4-foundation-audit/foundation_identity_authority_matrix/report.md"
    },
    {
      "id": "foundation_persistence_migration_matrix",
      "agent": "default",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "medium",
      "mode": "read-only-evidence",
      "depends_on": [
        "owner_foundational_contract_map_frozen"
      ],
      "read_paths": [
        "paper-trader/backend/app/db",
        "paper-trader/backend/migrations",
        "paper-trader/backend/research/domain",
        "paper-trader/backend/tests",
        "paper-trader/backend/research_tests"
      ],
      "write_paths": [
        ".agent/runs/phase1-4-foundation-audit/foundation_persistence_migration_matrix"
      ],
      "output": ".agent/runs/phase1-4-foundation-audit/foundation_persistence_migration_matrix/report.md"
    },
    {
      "id": "foundation_causality_cache_provenance_matrix",
      "agent": "default",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "medium",
      "mode": "read-only-evidence",
      "depends_on": [
        "owner_foundational_contract_map_frozen"
      ],
      "read_paths": [
        "paper-trader/backend/app/backtest",
        "paper-trader/backend/app/market_data",
        "paper-trader/backend/app/market_truth",
        "paper-trader/backend/app/strategy",
        "paper-trader/backend/tests"
      ],
      "write_paths": [
        ".agent/runs/phase1-4-foundation-audit/foundation_causality_cache_provenance_matrix"
      ],
      "output": ".agent/runs/phase1-4-foundation-audit/foundation_causality_cache_provenance_matrix/report.md"
    },
    {
      "id": "foundation_adversarial_evidence_matrix",
      "agent": "default",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "medium",
      "mode": "read-only-evidence",
      "depends_on": [
        "owner_foundational_contract_map_frozen"
      ],
      "read_paths": [
        "paper-trader/backend/tests",
        "paper-trader/backend/research_tests",
        ".agent/runs"
      ],
      "write_paths": [
        ".agent/runs/phase1-4-foundation-audit/foundation_adversarial_evidence_matrix"
      ],
      "output": ".agent/runs/phase1-4-foundation-audit/foundation_adversarial_evidence_matrix/report.md"
    }
  ],
  "adversarial_edge_case_matrix": [
    "process restart",
    "crash between writes",
    "partial transaction",
    "duplicate or replayed request",
    "stale worker",
    "worker reclaim",
    "cache hit after restart",
    "cache poisoning or collision",
    "malformed serialized state",
    "valid-but-hostile values",
    "v1 to v2 migration",
    "mixed v1 and v2 state",
    "upgrade, downgrade, and version skew",
    "migration from zero",
    "migration from an actual old database",
    "missing catalogue or provider",
    "duplicate identity",
    "forged identity",
    "stale receipt",
    "deleted or replaced dependency",
    "concurrency races",
    "owner or tenant mismatch",
    "clock and timezone boundary",
    "empty inputs",
    "huge inputs",
    "resource exhaustion",
    "cancellation midway through work"
  ],
  "audit_domains": [
    "identity",
    "immutability",
    "admission authority",
    "tenancy and ownership",
    "causal evaluation",
    "persistence",
    "reconstruction",
    "migration",
    "cache identity",
    "result provenance",
    "numeric validity",
    "dataset identity",
    "cross-version boundaries"
  ],
  "acceptance": [
    "The independent Sol-high owner reconstructs the foundational contracts from repository code, schemas, migrations, tests, and current authoritative design sections without inheriting historical PASS verdicts as facts.",
    "The report answers exactly: What assumptions have we never actually tested? It distinguishes undocumented assumptions, untested assumptions, disproven assumptions, and directly verified invariants.",
    "Every adversarial edge-case row is classified by applicable domain, current behavior, evidence class, severity, affected boundary, and required action. Not applicable rows require a concrete rationale.",
    "Every cross-layer Critical invariant has at least one real create/admit → persist → process death → reload → verify → consume trace. A monkeypatched critical seam is labelled unit-only and cannot satisfy acceptance.",
    "Every serious defect includes root cause, prevention invariant, permanent adversarial regression proposal, and a proposed defect-pattern-register entry with named search surfaces.",
    "The transitive invalidation map links each changed or disproven invariant to affected contracts, phases, tests, review verdicts, and exact revalidation. Historical PASS evidence remains immutable but is marked STALE/REQUIRES RECHECK wherever its assumption is invalid.",
    "The report separates Critical blockers from High/Medium/Low findings. All Critical architecture/invariant findings block Phase 5. Lower-severity findings may be deferred only with containment evidence, rationale, owner, and exact future capsule or deadline.",
    "The first pass writes evidence only, proposes bounded corrections, and does not redesign or implement product code. It binds intake/final HEAD and dirty fingerprints, commands, cwd, exits, evidence hashes, protected boundaries, and explicit nonclaims."
  ],
  "test_plan": [
    "Freeze a contract-and-assumption map before dispatching mechanical matrix children. Record each fact as repository fact, measured current-tree evidence, inference, historical claim, or unresolved assumption.",
    "Use targeted code inspection and focused read-only tests or disposable local databases. Do not run broad suites merely for confidence, touch live credentials/data/money, or deploy.",
    "Exercise real lifecycle paths for cross-layer Critical invariants and compare cold/restart behavior with in-process and cache-hit behavior. Record every mocked boundary.",
    "Produce the edge-case matrix, defect-pattern proposals, transitive invalidation map, risk-ranked findings, correction capsule proposals, residual nonclaims, and exact evidence manifest."
  ],
  "review": {
    "required": false,
    "assignment_id": "phase1_4_foundation_audit_owner",
    "agent": "default",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend",
      "paper-trader/frontend",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-audit.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/CURRENT.md",
      ".agent/runs/phase1-4-foundation-audit"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/phase1-4-foundation-audit/report.md",
    "verdicts": [
      "FOUNDATION_RISK",
      "EVIDENCE_CURRENTNESS"
    ],
    "max_rechecks": 0
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 1-4 foundation audit

This is the owner-authorized rare independent Sol-high task after Phase 4 completes. It is a focused foundation audit, not a generic code review and not an implementation task. It reconstructs and attacks the contracts on which Phase 5 will depend. Its first pass may only report findings, evidence impact, and bounded correction proposals.
