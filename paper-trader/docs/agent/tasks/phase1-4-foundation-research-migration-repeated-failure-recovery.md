---
{
  "id": "phase1-4-foundation-research-migration-repeated-failure-recovery",
  "phase": "interphase-4-5",
  "status": "accepted",
  "goal": "Recover one executable, authority-complete research-migration correction route after two evidence-backed implementation attempts left the same Critical defect unresolved, without adding compatibility shims or changing product bytes from inside this architecture capsule.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The mission handoff requires a fresh Sol-high architecture recovery after the same material defect survives two evidence-backed implementation attempts. This capsule authorizes read-only source and history analysis, disposable evidence-only probes, exact correction architecture, downstream capsule drafting, and ignored evidence. Product, tests, schemas, migrations, CURRENT, PROGRAMME, review packages, frontend, providers, brokers, deployment, production, live, and money paths are read-only.",
    "stopping_condition": "Complete only when the owner has distinguished missing architecture from unfinished implementation, explained both failed attempts from current bytes, decided the retained 0007/0008 diff, frozen one implementable single-authority algorithm and serial capsule route for SQLite and PostgreSQL 16, and proved through evidence-only probes that a fresh bounded owner can execute it without current metadata, marker rewind, invented historical facts, silent support change, or overlapping authority. Return BLOCKED if any required fact remains unavailable or the route needs a product decision outside the accepted support matrix."
  },
  "risk_tags": [
    "critical",
    "repeated-failure-recovery",
    "research-migration",
    "postgresql-history-authority",
    "sqlite-history-authority",
    "deployability",
    "research-integrity"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": ["14. Foundation migration and market-number correction contract"]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": ["9. Foundation migration and numeric correction route"]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": ["Foundation migration and numeric correction", "Foundation blockers", "Phase 4 ownership"]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": ["DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql-history-authority-recovery.md",
      "sections": ["Phase 1-4 foundation PostgreSQL history-authority recovery"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-correction.md",
      "sections": ["Phase 1-4 foundation research migration correction"]
    }
  ],
  "dependency_gate": "migration-repair-attempt-2-blocked-accepted",
  "trigger_evidence": {
    "root_acceptance": ".agent/runs/phase1-4-foundation-critical-closure/migration-owner-attempt2-blocked-acceptance.json",
    "root_acceptance_sha256": "e4759b071ba202d0787d96d77d7f6ff5f2a318439d916cef9ca75992b022c394",
    "attempt_1_report_sha256": "6d5ef4236d3b5864ebe64959235f2ca07ed5af7a7ec7e005343a22ba49adf24c",
    "attempt_1_manifest_sha256": "c31ef58e16a079e10fb186eed7db4bb680dda64fbaec004e87fb4fe19e00cdd4",
    "postgresql_recovery_acceptance_sha256": "66f1fea2789eb336967b0726c62491d608ec9c5b9faba920d64af224e8cda249",
    "attempt_2_report_sha256": "b074af1a26598a5cfbf4a8fb8e58d15ecea6d4d81da64fbe221a0711d94d7515",
    "attempt_2_manifest_sha256": "1dd5f134f9da85ef960d8507cb06de4d4cd4f6962a14276fadb8fa205a0555de",
    "retained_0007_sha256": "1dddeb3b9913a6d00291e112880180b488238db11058448a557884628a6cb6dc",
    "retained_0008_sha256": "76ab8f6dcd5f6cd4019702a5737250720f1982d113cac16e2958afeb939717c2"
  },
  "supported_start_matrix": {
    "sqlite": ["empty", "exact-unversioned-legacy", "0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008", "0009", "0010", "0011"],
    "postgresql16_supported": ["empty", "exact-populated-0010", "exact-0011"],
    "postgresql16_refused_before_write": ["0003", "0004", "0005", "0006", "0007", "0008", "0009", "unknown-marker", "catalog-drift"],
    "target_head": "0011",
    "authority": "Root-accepted explicit support revision; this recovery may not silently widen or narrow it."
  },
  "architecture_questions": [
    "Which exact missing fact, if any, prevents implementation of each required file, and which missing files are merely deliverables the implementation owner was expected to create?",
    "Why did each of the two attempts stop, and does the evidence identify one persistent architecture gap, an over-broad implementation slice, or an execution failure?",
    "Are the retained 0007 and 0008 trigger installers correct, complete, and safe to keep, or must a later authorized owner replace or remove them?",
    "What is the sole frozen SQLite projection authority for every supported prefix, and which existing current-metadata projection helpers must be replaced rather than wrapped?",
    "What exact Python structures and SQL declarations form the sole PostgreSQL 0010 product authority, and how can an independent test builder consume them without defining a second schema?",
    "What exact preflight, transactional upgrade, certification, enumerated repair, marker, restart, rollback, and refusal algorithm reaches 0011 on each supported state?",
    "Can the correction remain one coherent Terra-medium slice, or must it become a serial set of smaller capsules with explicit integration and no concurrent overlap?",
    "Which direct, transitive, mutation, protected-boundary, migration, and deployability evidence must be produced before independent review?"
  ],
  "required_decisions": {
    "failure_diagnosis": "Classify every attempt-1 and attempt-2 stop as missing authority, unresolved architecture, unfinished implementation, invalid evidence, or scope/ownership failure. Bind each conclusion to current bytes and logs.",
    "retained_diff": "Return KEEP_UNACCEPTED, REPLACE_IN_NEXT_CAPSULE, or REMOVE_IN_NEXT_CAPSULE for each retained 0007/0008 file. Architecture recovery itself may not change those product bytes.",
    "single_authority": "Specify one version-owned SQLite projection source per supported prefix and one PostgreSQL 0010 product contract. Tests consume those sources and cannot define or infer an alternate schema.",
    "implementation_algorithm": "Name every product function, data structure, validation boundary, transaction boundary, refusal code, restart state, and marker transition needed for empty, supported prefix, exact head, exact enumerated repair, and refused state behavior.",
    "capsule_decomposition": "Either prove the existing capsule is bounded and executable or replace it with an exact serial capsule DAG. Every capsule must state objective, dependencies, allowed and review paths, model and effort, tests, mutations, stopping conditions, owner gates, evidence, and deployability impact.",
    "fresh_ownership": "Name only fresh implementation owners. Neither prior implementation owner may resume. Parallel implementation budget is zero wherever files or authority decisions overlap.",
    "root_gate": "No implementation resumes until root independently validates and accepts the recovery report, evidence manifest, changed documentation, frozen audit hashes, protected hashes, and exact next capsule."
  },
  "required_outputs": [
    ".agent/runs/phase1-4-foundation-research-migration-repeated-failure-recovery/owner/report.md",
    ".agent/runs/phase1-4-foundation-research-migration-repeated-failure-recovery/owner/evidence-manifest.json",
    ".agent/runs/phase1-4-foundation-research-migration-repeated-failure-recovery/foundation_research_migration_repeated_failure_architect/failure-ledger.json",
    ".agent/runs/phase1-4-foundation-research-migration-repeated-failure-recovery/foundation_research_migration_repeated_failure_architect/implementation-source-map.json",
    ".agent/runs/phase1-4-foundation-research-migration-repeated-failure-recovery/foundation_research_migration_repeated_failure_architect/capsule-dag.json"
  ],
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-repeated-failure-recovery.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-runtime-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-evidence-integration.md",
    ".agent/runs/phase1-4-foundation-research-migration-repeated-failure-recovery"
  ],
  "read_only_paths": [
    ".git",
    ".agent/runs/phase1-4-foundation-audit",
    ".agent/runs/phase1-4-foundation-critical-closure",
    ".agent/runs/phase1-4-foundation-migration-numeric-architecture-correction",
    ".agent/runs/phase1-4-foundation-postgresql-history-authority-recovery",
    ".agent/runs/phase1-4-foundation-research-migration-correction",
    ".agent/review-package.json",
    "paper-trader/backend/research/domain",
    "paper-trader/backend/research_tests",
    "paper-trader/backend/tests",
    "paper-trader/backend/scripts/run_disposable_postgres.py",
    "paper-trader/backend/app",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json"
  ],
  "acceptance": [
    "The owner reproduces the current stopping state and binds both failed attempts, the accepted PostgreSQL support revision, the retained two-file diff, and the unchanged audit/protected baseline by exact hash.",
    "The failure ledger names the causal failure in each attempt and rejects missing-to-be-created implementation files as an architecture blocker unless a specific unavailable authority fact makes them impossible to create.",
    "The implementation source map specifies all SQLite projections, PostgreSQL 0010 contract declarations, builder consumption seams, 0011 certification and repair states, pre-write refusals, transaction boundaries, marker transitions, process-reopen boundaries, and exact-byte preservation checks.",
    "An evidence-only feasibility probe proves the proposed single-authority declarations and algorithms can construct or inspect the required SQLite and disposable PostgreSQL 16 states without importing current ResearchBase.metadata, translating SQLite SQL, creating later head and rewinding it, or inventing historical facts.",
    "Each retained 0007/0008 change has a hash-bound disposition; no retained byte receives acceptance from this architecture task.",
    "The capsule DAG is serial wherever ownership overlaps, uses only fresh owners, and leaves no architecture decision to a bounded implementation owner.",
    "Every next executable capsule contains one durable goal, exact allowed paths, tests, mutations, failure triggers, owner gates, deployability impact, and direct stopping evidence. Numeric correction remains blocked behind accepted migration integration.",
    "Capsule JSON, repository architecture, scoped documentation diff, frozen audit hashes, protected hashes, evidence manifest, and all machine-readable outputs validate from final bytes."
  ],
  "test_plan": [
    "Re-run the focused migration selector only to reproduce and classify current failures; do not relabel an inherited failure as new implementation evidence.",
    "Trace every current ResearchBase.metadata consumer and every current-head rewind fixture into the failure ledger and exact replacement source map.",
    "Use ignored evidence-only prototypes and disposable SQLite/PostgreSQL 16 databases to test constructibility, catalog inspection, read-only refusal, and transaction boundaries. Do not write prototypes into product or test paths.",
    "Map every required acceptance row and mutation to one exact future capsule and command, including direct trigger behavior, interruption, restart, drift, downgrade, row and stored-byte preservation, and source-provenance rejection.",
    "Validate final documentation scope, capsule JSON, programme architecture, audit freeze, protected hashes, and manifest hash attestation."
  ],
  "owner_gates": [
    "Stop and return BLOCKED if any supported state requires invented durable objects, stored facts, constraints, functions, triggers, sequences, owner attribution, or canonical bytes.",
    "Stop for root and user direction if contrary evidence shows the accepted PostgreSQL matrix revision could strand a released, deployed, production, or externally promised 0003-0009 database.",
    "Stop before changing product, tests, schemas, migrations, packages, CURRENT, PROGRAMME, review packages, dependencies, configuration, services, providers, frontend, credentials, deployment, production data, destructive state, live behavior, orders, or money behavior.",
    "Stop if the route relies on current metadata as historical authority, current-head rewind, SQLite-to-PostgreSQL translation, later-head dumps, semantic-only JSON comparison, silent support changes, or multiple authorities for one state.",
    "Stop if a proposed next owner is either prior implementation owner or if concurrent capsules share any write path or schema authority."
  ],
  "stop_conditions": [
    "Any causal failure, authority source, implementation seam, retained-diff disposition, capsule dependency, refusal path, restart boundary, mutation, or evidence owner remains implicit.",
    "The design reduces acceptance to unit mocks, same-interpreter checks, hybrid fixtures, or current-head validation.",
    "The recovery begins implementation, self-certifies retained product bytes, or claims deployment or production readiness."
  ],
  "deployment_impact": {
    "classification": "architecture-only; migration-required downstream",
    "highest_claim": "an implementable local correction route",
    "unchanged": ["dependencies", "configuration", "services", "providers", "frontend", "execution schema", "deployment", "production", "live authority", "money authority"],
    "downstream_gates": ["SQLite compatibility evidence", "disposable PostgreSQL 16 parity", "backup-first upgrade and refusal procedure", "Phase 6 production-shaped rehearsal", "V1 exact-build release gate"]
  },
  "nonclaims": [
    "This capsule changes no product, test, schema, migration, runtime, provider, frontend, deployment, production, live, order, or money behavior.",
    "A feasibility prototype under ignored evidence is not product implementation or migration acceptance.",
    "The retained 0007/0008 changes remain unaccepted until a later authorized implementation and independent review close them.",
    "An accepted recovery route does not make numeric correction, transitive evidence, Phase 5, or release deployability current."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "priority",
    "routing_basis": "Fresh repeated-failure architecture recovery required by the owner handoff after two evidence-backed implementation attempts. The primary owner's Ultra exception does not propagate."
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_research_migration_repeated_failure_architect",
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
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-repeated-failure-recovery.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-correction.md",
      ".agent/runs/phase1-4-foundation-research-migration-repeated-failure-recovery"
    ],
    "exclude_paths": ["paper-trader/backend", "paper-trader/frontend"],
    "output": ".agent/runs/phase1-4-foundation-research-migration-repeated-failure-recovery/owner/report.md",
    "verdicts": ["RECOVERY_ARCHITECTURE_ACCEPTABLE", "BLOCKED"]
  }
}
---

# Phase 1-4 foundation research-migration repeated-failure recovery

Two evidence-backed implementation attempts left the same Critical migration
defect unresolved. This capsule stops patch iteration and gives one fresh
architecture owner a read-only recovery task. The owner must make the next
implementation route executable from frozen authority, or reject it with the
exact missing fact and gate.
