---
{
  "id": "phase1-4-foundation-research-migration-state-contract-recovery",
  "phase": "interphase-4-5",
  "status": "blocked",
  "blocking_condition": "This owner correctly stopped on missing SQLite authority. The later SQLite history-authority recovery supersedes its provisional SQLite matrix with a smaller exact matrix; root acceptance of that recovery remains required before implementation dispatch.",
  "provisional_contract": "The state model remains useful, but its SQLite support claims are superseded by the unaccepted history-authority recovery result.",
  "sqlite_recovery_resolution": {"verdict": "RECOVERY_ARCHITECTURE_ACCEPTABLE", "activation": "pending root acceptance", "ledger_sha256": "874cc53fc1e455428915359a1253e225467bbe5d3057cd94abd153b3f4c9e7b8", "source_closure_sha256": "15e4882d086d88ea6fe9afdde11d9c688cf2c7f4b36981e7c6b40d20e1832ea9", "support_matrix_sha256": "63aa4c648d5a20298671810012dabaee690f886c52d562cb0dcc05cd270fd8e0", "supported": ["empty", "exact_or_enumerated_five_guard_0010", "exact_0011"], "unsupported": ["unversioned", "0001-0009", "unknown_or_drifted"], "external_stranding_gate": "inactive on bounded repository evidence; activate root and user gate on affirmative contrary fact"},
  "goal": "Correct the research-migration architecture's conflation of immutable versioned catalog authority, arbitrary valid user data, and synthetic populated test witnesses before projection implementation resumes.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The current projection owner found that the accepted PostgreSQL ledger explicitly marks populated-fact authority incomplete while the projection capsule simultaneously demands an exact immutable row corpus and prohibits invented facts. This capsule authorizes one fresh Sol-medium architecture owner to resolve that contradiction in documentation and downstream capsule contracts only. Product, tests, migrations, CURRENT, PROGRAMME, review packages, deployment, production, live, and money paths are read-only.",
    "stopping_condition": "Complete only when the owner defines one executable state-support contract that keeps schema and catalog history immutable, treats valid user rows and sequence state without inventing a universal historical snapshot, assigns deterministic synthetic witness data a non-authoritative test role, preserves exact stored bytes and attribution across migration, corrects every affected downstream capsule and acceptance claim, and proves the route through evidence-only SQLite and PostgreSQL 16 probes. Return BLOCKED if safe support still requires unavailable historical schema facts, production data, destructive repair, a second authority, or a silent start-matrix change."
  },
  "risk_tags": [
    "critical",
    "architecture-recovery",
    "research-migration",
    "schema-authority",
    "data-preservation",
    "postgresql",
    "sqlite",
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
      "sections": ["Foundation migration and numeric correction"]
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
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-repeated-failure-recovery.md",
      "sections": ["Phase 1-4 foundation research-migration repeated-failure recovery"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
      "sections": ["Phase 1-4 foundation research migration projection correction"]
    }
  ],
  "dependency_gate": "projection-owner-populated-authority-contradiction",
  "trigger_evidence": {
    "postgresql_authority_ledger": ".agent/runs/phase1-4-foundation-postgresql-history-authority-recovery/foundation_postgresql_history_architect/postgresql-history-authority-ledger.log",
    "postgresql_authority_ledger_sha256": "32a3735b5fe992e193a0e053b7940d77937fcfd7d86377a0f45b118bd828e0b1",
    "accepted_recovery_report_sha256": "26f49011c91fdbb19992ea6a466980b2a7ede2a5d81644472a19920fb36317c3",
    "accepted_recovery_manifest_sha256": "4a68d4ded9e6c5c28a6972d6ad9edd76357a2a7285075a3cf12c520513878078",
    "projection_owner_audit": ".agent/runs/phase1-4-foundation-research-migration-projection-correction/foundation_research_migration_projection_owner/corpus-authority-audit.log"
  },
  "architecture_questions": [
    "Which parts of a supported migration start are immutable version authority, which are parameterized valid database state, and which are test-only witness values?",
    "Can a migration honestly support arbitrary contract-valid populated 0010 databases while preserving rows, owner attribution, sequence state, and exact stored bytes, or must PostgreSQL support narrow further?",
    "What exact catalog, marker, row-validity, guard, and sequence predicates distinguish a supported 0010 or 0011 start from drift without requiring a singleton row snapshot?",
    "How must SQLite version-owned projections express historical schemas and permitted legacy states without deriving from current metadata or treating synthetic fixture literals as historical facts?",
    "Where may deterministic witness rows live, what coverage must they provide, and how do validators prevent those witnesses from becoming a second schema or historical authority?",
    "Which recovery claims, capsule stopping conditions, tests, mutations, fixture labels, and review questions became invalid because they demanded exact universal populated facts?"
  ],
  "required_decisions": {
    "state_model": "Define immutable catalog authority, parameterized user-data domain, marker state, guard state, sequence state, and preservation obligations for every supported SQLite and PostgreSQL start.",
    "fixture_taxonomy": "Give deterministic synthetic witness corpora an explicit non-authoritative label and distinguish them from exact historical schema projections, hybrid fault injection, current-contract regression, and production or release evidence.",
    "support_matrix": "Keep or explicitly revise the accepted marker matrix. A wording change from singleton exact rows to contract-valid arbitrary rows is not allowed to silently weaken catalog, constraint, guard, marker, preservation, or refusal checks.",
    "validators": "Specify pre-write catalog and data predicates, before/after row and byte digests, key and owner preservation, sequence-state preservation, targeted 0011 repair predicates, restart behavior, and refusal codes.",
    "capsule_repair": "Correct the projection, runtime, integration, transitive, and critical-review capsules so each owner receives an executable contract and no task must invent historical facts or universal user rows.",
    "root_gate": "Projection implementation remains paused until root independently accepts the final report, manifest, semantic matrix, documentation diff, frozen audit hashes, protected hashes, and amended projection capsule."
  },
  "required_outputs": [
    ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery/owner/report.md",
    ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery/owner/evidence-manifest.json",
    ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery/foundation_research_migration_state_contract_architect/state-contract-matrix.json",
    ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery/foundation_research_migration_state_contract_architect/claim-invalidation-map.json"
  ],
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-state-contract-recovery.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-runtime-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-evidence-integration.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-transitive-revalidation.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-review.md",
    ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery"
  ],
  "read_only_paths": [
    ".git",
    ".agent/runs/phase1-4-foundation-audit",
    ".agent/runs/phase1-4-foundation-critical-closure",
    ".agent/runs/phase1-4-foundation-postgresql-history-authority-recovery",
    ".agent/runs/phase1-4-foundation-research-migration-correction",
    ".agent/runs/phase1-4-foundation-research-migration-projection-correction",
    ".agent/runs/phase1-4-foundation-research-migration-repeated-failure-recovery",
    ".agent/review-package.json",
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md"
  ],
  "acceptance": [
    "The owner binds the contradiction to exact ledger, recovery, projection-capsule, frozen-audit, and protected-file hashes and states which prior architecture claims are invalidated without rewriting immutable evidence.",
    "One machine-readable state model names every immutable catalog fact and every parameterized data, marker, guard, and sequence variable for SQLite and PostgreSQL 16.",
    "The support contract accepts at least two materially different valid populated witness corpora for the same exact catalog and proves exact preservation of each, while rejecting catalog drift, invalid data, owner/key corruption, sequence corruption, and unenumerated guard states.",
    "Synthetic fixture literals are explicitly non-authoritative and cannot define schema, historical support, production state, release state, or user facts.",
    "Every SQLite historical catalog declaration cites an exact named product source authority; no source may be inferred from witness values or current metadata.",
    "Projection-owned product contract modules declare the exact forward 0011 = 0010 + guard-only delta targets; runtime migration bytes consume and must match those declarations and cannot become a second authority.",
    "SQLite predicates validate storage class and affinity and preserve textual JSON and BLOB bytes; PostgreSQL predicates distinguish text/varchar JSON byte preservation from dialect-native json/jsonb representation.",
    "Direct guard attempts run only inside rollback-only savepoints or subtransactions, commit no test write, and leave the complete preflight digest byte-identical; sequence inspection never advances a sequence.",
    "No current ResearchBase.metadata subtraction, later-head rewind, cross-dialect translation, later dump, semantic-only JSON comparison, or invented historical schema is permitted.",
    "All downstream capsules, design, plan, deployability record, and defect-pattern guidance use the same corrected terms and preserve the serial owner DAG.",
    "Evidence-only SQLite and disposable PostgreSQL 16 probes show the corrected model is implementable without touching product or tests.",
    "Capsule JSON, repository architecture, scoped documentation diff, frozen audit hashes, protected hashes, machine outputs, and manifest attestation pass on final bytes."
  ],
  "test_plan": [
    "Audit the accepted ledger and recovery package for every singleton-populated-corpus or populated-fact-authority claim and emit an exact invalidation map.",
    "Use ignored evidence-only probes to construct two different valid populated databases from one exact versioned catalog declaration and prove migration-preservation predicates are data-parametric.",
    "Mutate catalog, marker, guard inventory, one key or owner relation, one stored Unicode/JSON/binary byte, and sequence state; use isolated clones or transactionally reversible setup, prove the validator either preserves the exact pre-state through the no-data-change migration or refuses before writes, and never use an advancing sequence call for inspection.",
    "Validate all amended capsules and architecture files, frozen audit and protected hashes, scoped diff, machine-readable outputs, and evidence manifest."
  ],
  "owner_gates": [
    "Stop and return BLOCKED if a supported schema or historical semantic state still requires unavailable or invented authority.",
    "Stop for root and user direction if evidence shows a support change could strand a released, deployed, production, or externally promised database state.",
    "Stop before product, test, schema, migration, dependency, configuration, service, provider, frontend, CURRENT, PROGRAMME, review-package, credential, deployment, production-data, destructive, live, order, or money changes.",
    "Stop if the correction weakens exact catalog validation, row/key/owner/byte preservation, sequence handling, targeted repair limits, transaction boundaries, restart safety, or pre-write refusal."
  ],
  "stop_conditions": [
    "Any supported-state predicate, authority source, fixture role, preservation invariant, mutation, downstream owner, or invalidated claim remains implicit.",
    "A synthetic witness is relabelled as historical, user, production, release, or schema authority.",
    "The owner begins implementation, self-accepts prior product bytes, or claims deployability or production readiness."
  ],
  "deployment_impact": {
    "classification": "architecture-only; migration-required downstream",
    "highest_claim": "an executable data-parametric migration state contract",
    "unchanged": ["product", "tests", "runtime behavior", "research head", "dependencies", "configuration", "services", "providers", "frontend", "deployment", "production", "live authority", "money authority"],
    "downstream_gates": ["projection root acceptance", "runtime root acceptance", "integration root acceptance", "transitive revalidation", "critical review", "production-shaped release rehearsal"]
  },
  "nonclaims": [
    "This capsule changes no product, test, schema, migration, runtime, provider, frontend, deployment, production, live, order, or money behavior.",
    "A deterministic synthetic witness corpus proves coverage and preservation only; it is not historical or production authority.",
    "Accepted architecture does not accept the paused projection implementation, retained 0007/0008 edits, runtime, integration, numeric correction, foundation closure, Phase 5, release, or deployability."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority",
    "fresh_owner_required": true,
    "routing_basis": "Bounded architecture correction under the programme phase-architecture route; the primary owner's Ultra exception does not propagate."
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_research_migration_state_contract_architect",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-state-contract-recovery.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-runtime-correction.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-evidence-integration.md",
      ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery"
    ],
    "exclude_paths": ["paper-trader/backend", "paper-trader/frontend"],
    "output": ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery/owner/report.md",
    "verdicts": ["STATE_CONTRACT_ARCHITECTURE_ACCEPTABLE", "BLOCKED"]
  }
}
---

# Phase 1-4 foundation research-migration state-contract recovery

The accepted recovery route incorrectly asked a versioned migration contract to
freeze one universal populated database. Real supported databases share an
exact catalog and validity rules, but their user rows and sequence positions
vary. This capsule must correct that category error without weakening catalog
authority, data preservation, or refusal behavior and without inventing any
historical fact.
