---
{
  "id": "phase1-4-foundation-migration-numeric-architecture-correction",
  "phase": "interphase-4-5",
  "status": "accepted",
  "goal": "Freeze one forward-safe migration recovery contract for A-01, A-03, A-04, and A-05, plus one shared pre-coercion market-number contract for A-02, before any correction changes product, test, schema, or migration bytes.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The mission handoff explicitly routes a Critical migration or cross-plane foundation defect to one fresh Sol-high architecture/recovery owner. This capsule authorizes documentation, bounded correction-capsule design, defect-pattern registration, and ignored evidence only. Product, tests, schema implementations, migrations, review packages, frontend, providers, brokers, deployment, production, live, and money paths are read-only.",
    "stopping_condition": "Complete only when the architect explains the exact 0005-to-0010 SQLite failure, freezes the supported start-state and dialect matrix, chooses a forward-safe trigger and marker repair, decides genuine populated-old PostgreSQL support or an explicit safe narrowing, classifies every retained fixture, freezes one source-type-before-coercion numeric rule, separates the migration and numeric implementation ownership, and names every transitive test, mutation, deployability obligation, package, and independent review input. Stop if the design needs destructive production data work, a second schema authority, silent migration-support narrowing, provider or runtime expansion, or live or money authority."
  },
  "risk_tags": [
    "critical",
    "architecture-recovery",
    "research-migrations",
    "sqlite-postgresql-parity",
    "numeric-ingress",
    "transitive-evidence"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/phase1-4-foundation-audit/report.md",
      "sections": [
        "Owner disposition",
        "Serious findings",
        "Evidence invalidation and correction route"
      ]
    },
    {
      "path": ".agent/runs/phase1-4-foundation-audit/transitive-invalidation-map.md",
      "sections": [
        "A-01: supported SQLite research 0005 upgrade does not reach head",
        "A-02: boolean OHLC values become executable prices",
        "A-03: genuine populated-old PostgreSQL research upgrade is unproved",
        "A-04: retained migration tests mix genuine regression evidence with stale fixtures"
      ]
    },
    {
      "path": ".agent/runs/phase1-4-foundation-audit/correction-capsule-proposals.md",
      "sections": [
        "Required serial chain",
        "Correction acceptance gates",
        "Failure routing",
        "Forbidden scope"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "4. Closed numeric validity contract",
        "8. Dataset provenance and cache identity",
        "9. Ownership, authority, and persistence",
        "11. Deployment contract",
        "13.5 Stale evidence and revalidation"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "Strategy OS defect-pattern register",
        "Status and evidence rules",
        "DP-009 — Logical ORM transaction mistaken for a physical outer transaction"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "Foundation blockers",
        "Phase 4 ownership"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md",
      "sections": [
        "Phase 1-4 foundation critical closure"
      ]
    }
  ],
  "dependency_gate": "phase1-4-foundation-audit",
  "input_evidence": [
    ".agent/runs/phase1-4-foundation-critical-closure/audit-freeze.json",
    ".agent/runs/phase1-4-foundation-audit/owner/diagnose-research-upgrade-3.log",
    ".agent/runs/phase1-4-foundation-audit/owner/exact-0005-upgrade.db",
    ".agent/runs/phase1-4-foundation-audit/owner/probe-causality-numeric.log",
    ".agent/runs/phase1-4-foundation-audit/foundation_persistence_migration_matrix/report.md",
    ".agent/runs/phase1-4-foundation-audit/foundation_causality_cache_provenance_matrix/report.md"
  ],
  "architecture_questions": [
    "Which exact SQLite and PostgreSQL research prefixes are supported as upgrade starts, and what independently projected schema, index, trigger, marker, and populated-row contract defines each one?",
    "How can every supported SQLite prefix install its full target trigger contract before marker advancement while preserving exact rows and canonical JSON bytes across interruption and restart?",
    "Does closure require both amended historical migration routines for not-yet-upgraded databases and a new forward repair for databases already marked at a later head, or can direct evidence safely reject one branch?",
    "What safe operator action applies to PostgreSQL databases whose actual historical projection is unsupported, and what evidence prevents a current-schema rewind from masquerading as support?",
    "Why does SQLite bind version plus schema cookie while PostgreSQL binds version only, and which explicit dialect invariant and tests make that difference acceptable?",
    "Where is the single authoritative source-type-before-coercion market-number rule, and which OHLCV, dataset, identity, causal, cache, and execution-price consumers must call it?",
    "Which historical Phase 4 claims and packages stay immutable, which dependent claims remain stale, and which exact selectors make them current again?"
  ],
  "required_decisions": {
    "disposition_vocabulary": [
      "KEEP",
      "KEEP + HARDEN",
      "REFACTOR",
      "REPLACE",
      "DEFER"
    ],
    "migration": "Choose one coherent repair with an exact supported-start matrix, marker atomicity, interruption behavior, existing-install handling, downgrade and drift refusal, and SQLite/PostgreSQL parity or explicit limitation.",
    "numeric": "Choose one shared raw market-number validator that rejects bool before conversion and leaves valid finite numeric identity unchanged unless a versioned identity change is explicitly accepted.",
    "fixture_taxonomy": "Classify each retained fixture as exact historical projection, current head, hybrid fault injection, or retired. Only exact projections may prove actual-old support.",
    "implementation_split": "Emit disjoint Terra-medium migration and numeric capsules, followed by a root-owned transitive integration package and one independent critical review."
  },
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-migration-numeric-architecture-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-numeric-ingress-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-transitive-revalidation.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-review.md",
    ".agent/runs/phase1-4-foundation-migration-numeric-architecture-correction"
  ],
  "product_paths_read_only": [
    "paper-trader/backend",
    "paper-trader/frontend",
    ".agent/review-package.json",
    ".agent/runs/phase1-4-foundation-audit"
  ],
  "nonclaims": [
    "Architecture acceptance changes no product, test, schema, migration, runtime, provider, frontend, deployment, production, live, or money behavior.",
    "The audit package and historical Phase 4 final-review-5 verdict remain immutable. This design may only classify their dependent claims as stale or current from new evidence.",
    "A disposable SQLite or PostgreSQL test does not prove deployability, production upgrade safety, rollback readiness, or backup and restore."
  ],
  "owner_gates": [
    "Stop before product, test, schema, migration, review-package, verdict, provider, broker, frontend, credential, service, infrastructure, deployment, production-data, live, money, destructive, legal, regulatory, or commercial change.",
    "Stop if the migration decision would silently abandon a previously supported start state, rewrite persisted user facts, require destructive repair, or make current model metadata a historical schema authority.",
    "Stop if the numeric decision changes valid finite numeric identity or execution semantics beyond rejecting booleans without a separately versioned and owner-approved contract."
  ],
  "stop_conditions": [
    "Any supported historical prefix, target-stage trigger set, marker rule, restart outcome, or existing-install repair path remains implicit.",
    "Genuine populated-old PostgreSQL behavior remains labelled supported without an independent historical projection, or is narrowed without safe operational handling and explicit owner disposition.",
    "Migration and numeric implementation ownership overlaps, or either capsule can widen into runtime, provider, frontend, broker, deployment, production, live, or money work.",
    "DP-010, DP-011, transitive invalidation, reversible mutation requirements, protected hashes, and independent review inputs are incomplete."
  ],
  "deployment_impact": {
    "classification": "architecture-only-foundation-migration-and-numeric-recovery",
    "required_evidence": "State whether migration code, schema head, supported upgrade starts, package dependencies, configuration, services, rollback, backup and restore, or operator procedure changes. Prove only local SQLite and disposable PostgreSQL behavior here; assign every production-shaped check to an exact later gate."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "priority",
    "routing_basis": "Explicit mission handoff for a Critical migration architecture/recovery defect. The primary owner's Ultra exception does not propagate."
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The architect reproduces and explains A-01 from current bytes and binds the decision to the immutable audit hashes.",
    "One exact supported-start and dialect matrix covers fresh, 0005 through current SQLite states, genuine PostgreSQL historical states or an explicit safe limitation, target contracts, markers, interruption, restart, downgrade, drift, and existing-install handling.",
    "The repair uses one schema authority per version, installs complete trigger contracts before marker advancement, preserves rows and canonical bytes, and refuses unsupported or ambiguous prefixes without pretending a hybrid fixture is historical evidence.",
    "One pre-coercion numeric rule rejects bool across every assigned OHLCV ingress while preserving ordinary finite numeric behavior and identity.",
    "DP-010 and DP-011 are registered at OPEN with exact root causes, invariants, surfaces, permanent regressions, invalidation rules, owners, and evidence requirements.",
    "Disjoint migration, numeric, transitive-revalidation, and independent-review capsules exist with exact paths, models, tests, mutations, deployability impact, owner gates, failure triggers, and stopping conditions.",
    "The architecture report returns one explicit disposition and contains no unsupported foundation, deployment, runtime, live, or money claim."
  ],
  "test_plan": [
    "Inspect the exact research migration modules, schema validators, marker code, historical fixtures, raw candle and dataset numeric boundaries, and named audit evidence without editing product or tests.",
    "Run only bounded read-only probes needed to compare supported prefixes, target trigger inventories, dialect marker semantics, fixture provenance, and bool coercion surfaces.",
    "Validate capsule JSON, documentation consistency, exact paths, protected hashes, audit-freeze hashes, scoped diff, and evidence manifest."
  ],
  "review": {
    "required": false,
    "assignment_id": "foundation_migration_numeric_architect",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-migration-numeric-architecture-correction.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-correction.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-numeric-ingress-correction.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-transitive-revalidation.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-review.md",
      ".agent/runs/phase1-4-foundation-migration-numeric-architecture-correction"
    ],
    "exclude_paths": [
      "paper-trader/backend",
      "paper-trader/frontend",
      ".agent/review-package.json",
      ".agent/runs/phase1-4-foundation-audit"
    ],
    "output": ".agent/runs/phase1-4-foundation-migration-numeric-architecture-correction/owner/report.md",
    "verdicts": [
      "ARCHITECTURE_ACCEPTABLE",
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

# Phase 1-4 foundation migration and numeric architecture correction

This capsule freezes the correction contract before implementation. It keeps the migration and numeric changes separate, binds both to the immutable audit, and routes one serial independent review after integrated revalidation.

## Accepted architecture disposition

The correction is `KEEP + HARDEN` for the forward runner, marker, and 0007/0008
upgrade intent; `REPLACE` for current-model-derived historical projections and
permissive pre-check numeric coercion; `REFACTOR` for hybrid fixtures and
existing-install treatment; `KEEP` for canonical IR, identity, attribution,
tenancy, and fail-closed authority; and `DEFER` for every provider, frontend,
deployment, production, live, and money concern outside this boundary.

The supported matrix preserves SQLite empty, exact unversioned legacy, and
markers 0001 through 0010, plus PostgreSQL 16 empty and markers 0003 through
0010. All supported states reach new research head 0011. Each historical
version owns one independent dialect-specific projection. The implementation
cannot narrow a start state without a new owner-approved architecture decision.

The forward repair hardens 0007 and 0008 trigger installation for databases
that have not crossed those steps and adds 0011 certification/repair for exact
later states. It accepts only complete source contracts or the enumerated
missing-trigger audit shapes. It validates the complete target before marker
advancement, preserves exact facts and canonical bytes, resumes only declared
SQLite prefixes, uses transactional PostgreSQL DDL and marker updates, and
refuses downgrade, drift, hybrid, unknown, and unsupported states.

One public conversion in `app.market_data.candles` checks raw source type before
coercion. Python booleans and boolean scalars refuse in every OHLCV field.
Every assigned preparation, dataframe, storage, identity, cache, causal, and
execution-price path uses that rule or a value already certified by it. Valid
finite conversion, bytes, identity, causal behavior, and execution semantics
stay unchanged.

The exact serial route is
`phase1-4-foundation-research-migration-correction`,
`phase1-4-foundation-numeric-ingress-correction`,
`phase1-4-foundation-transitive-revalidation`, then
`phase1-4-foundation-critical-review`. Architecture acceptance changes no
product or runtime byte and makes no foundation or deployability claim.
