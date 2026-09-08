---
{
  "id": "phase1-4-foundation-research-migration-projection-repeated-failure-recovery",
  "phase": "interphase-4-5",
  "status": "completed",
  "result": {
    "verdict": "RECOVERY_ARCHITECTURE_ACCEPTABLE",
    "activation": "pending root acceptance at .agent/runs/phase1-4-foundation-critical-closure/projection-repeated-failure-recovery-acceptance.json",
    "failure_classification": "ONE_MATERIAL_FALSE_GREEN_COMPLETENESS_DEFECT_SURVIVED_TWO_REPAIRS",
    "decisive_full_oracle_log": ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/foundation_research_migration_projection_repeated_failure_architect/full-caller-oracle-probe-final-2.log",
    "decisive_immutable_insert_log": ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/foundation_research_migration_projection_repeated_failure_architect/immutable-insert-probe-2.log",
    "machine_contracts": ["failure-lineage.json", "native-round-trip-contract.json", "mutation-coverage-matrix.json", "capsule-dag.json"],
    "retained_byte_summary": {"KEEP_UNACCEPTED_FOR_NEXT_CAPSULE": 4, "REPLACE_IN_NEXT_CAPSULE": 3, "REMOVE_IN_NEXT_CAPSULE": 0},
    "serial_nodes": 6,
    "next_assignment": "foundation_research_migration_native_round_trip_owner",
    "owner_gate": "No successor starts before root independently validates the report, manifest, machine contracts, actual frozen/protected path hashes, and exact successor capsule bytes."
  },
  "goal": "Recover one independently falsifiable projection-contract correction route after two bounded repairs retained the same material false-green completeness defect, without continuing local product patching or accepting any retained bytes.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The mission requires a fresh Sol-high architecture/recovery capsule when the same material implementation defect survives two evidence-backed repair attempts. Root rejection 77d4b77f99048c1be990f8e74546bcb26a1affbe26f653ee847327f9b09ec292 activates that route. This capsule authorizes read-only source analysis, disposable evidence-only probes, architecture and capsule documentation, and ignored evidence. It authorizes no product, test, schema, migration, runtime, CURRENT, PROGRAMME, review-package, provider, frontend, deployment, production, live, order, or money edit.",
    "stopping_condition": "Complete only when the owner has explained how both repairs remained false green, independently classified every retained projection byte, specified an exact per-table native round-trip and mutation oracle that covers all durable caller facts and every catalog fact class in SQLite and PostgreSQL 16 after real close/reopen boundaries, proved the oracle can reject the root's reproduced mismatch, and emitted a serial executable capsule DAG with fresh ownership and no remaining acceptance decision delegated to implementation. Return BLOCKED if any required catalog, native-value rule, fact class, or authority remains unavailable."
  },
  "risk_tags": [
    "critical",
    "repeated-failure-recovery",
    "research-migration",
    "projection-authority",
    "false-green-evidence",
    "postgresql16",
    "sqlite",
    "research-integrity",
    "deployability"
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
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
      "sections": ["Phase 1-4 foundation research-migration projection correction"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-sqlite-history-authority-recovery.md",
      "sections": ["Phase 1-4 foundation SQLite history-authority recovery"]
    }
  ],
  "dependency_gate": "projection-owner-2-attempt2-rejected",
  "trigger_evidence": {
    "root_rejection": ".agent/runs/phase1-4-foundation-critical-closure/projection-owner-2-attempt2-rejection.json",
    "root_rejection_sha256": "77d4b77f99048c1be990f8e74546bcb26a1affbe26f653ee847327f9b09ec292",
    "attempt_1_root_audit": ".agent/runs/phase1-4-foundation-critical-closure/root/projection-owner-2-repair-attempt-1-independent-audit.log",
    "attempt_1_root_audit_sha256": "328ddfbd0022601638aec5b24642b7dc5bd724313c3b2362af9340a58b652613",
    "attempt_2_root_validator": ".agent/runs/phase1-4-foundation-critical-closure/root/validate_projection_attempt2_rejection.py",
    "attempt_2_root_validator_sha256": "41a14be5613c71cf5d91a4884e4a0f07f93bc439a3b4bc74d2ca8e40f26fa83f",
    "attempt_2_root_evidence": ".agent/runs/phase1-4-foundation-critical-closure/root/projection-attempt-2-rejection-rerun.log",
    "attempt_2_root_evidence_sha256": "48b76a4e3f978d92a5a69a14cc7b28c5a599691a2e307edb798dfe6872c407eb",
    "attempt_2_owner_report_sha256": "dccc4128668f3da0966fea9c2d48d146649090f100d3856f99003d38c8c84e02",
    "attempt_2_owner_manifest_sha256": "28072e807eaf9fed9c4bb0454be300e7c45209b1b8d31820ea41c0032f71b8c8",
    "accepted_sqlite_recovery_sha256": "adefbe96d826d4eef330b344f85a64f76922075af5a253d27fd259c0d6f46aed",
    "accepted_sqlite_ledger_sha256": "874cc53fc1e455428915359a1253e225467bbe5d3057cd94abd153b3f4c9e7b8",
    "accepted_postgresql_ledger_sha256": "32a3735b5fe992e193a0e053b7940d77937fcfd7d86377a0f45b118bd828e0b1"
  },
  "frozen_unaccepted_inputs": {
    "paper-trader/backend/research/domain/migrations/sqlite_catalog_contract.py": "e34b6de36bafe994ea4422570267cb30beb6996e9f9d2c505788e4f3ecb800a0",
    "paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py": "1b399e20e48977a2ceae4cca75f0d3989f2d7558782354a23ebbf95d576256b8",
    "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py": "f5fa3d3460a21c7de80e623204193bddf1ce2f4a38761fd1f93c616aef209e8a",
    "paper-trader/backend/tests/foundation_postgresql_0010_builder.py": "14b1e73a604bdaf760cc4eb3c5e31714a2c0ce57e39415498fe8fedb62e4f0c0",
    "paper-trader/backend/tests/test_foundation_research_projection_contracts.py": "8a0e7ce4951d482ca330e0e322d1a25818d6f11df4c7e83421268d928b4ce8a8",
    "paper-trader/backend/research/domain/migrations/0007_phase4_dataset_provenance.py": "1dddeb3b9913a6d00291e112880180b488238db11058448a557884628a6cb6dc",
    "paper-trader/backend/research/domain/migrations/0008_ir_v2_graph_versions.py": "76ab8f6dcd5f6cd4019702a5737250720f1982d113cac16e2958afeb939717c2"
  },
  "architecture_questions": [
    "Which retained product declarations exactly match their accepted ledgers, and which retained helper or test bytes must be replaced rather than repaired?",
    "What single data-parametric expected-native-state function maps every caller corpus row to exact SQLite and PostgreSQL database-returned values without granting the corpus authority or normalizing away textual JSON, Unicode, binary, owner, classification, key, foreign-key, timestamp, boolean, null, or sequence facts?",
    "How will validation compare every row of every one of the 24 durable witness tables, the marker, all keys and foreign keys, native sequence state and bindings, storage classes/types, columns/defaults/nullability, constraints/check expressions, indexes/predicates, functions, and triggers after commit, process-independent engine disposal, and reopen?",
    "What exact mutation matrix changes one real stored fact or one observed inventory fact for each required class, proves rejection through the production-contract consumer rather than a self-comparison, restores it, and proves final native state equality?",
    "How will tests prove that mutating any one currently untested table such as research_hypothesis or research_finding fails, closing the root's reproduced false-green seam?",
    "How will report and manifest claims be generated or independently checked against exact collected tests and mutation identifiers so a partial suite cannot claim complete coverage?",
    "Should the next implementation replace the five retained paths in one bounded capsule or use a serial comparator/evidence decomposition, and what ownership prevents a third informal patch iteration?"
  ],
  "required_decisions": {
    "failure_lineage": "Bind attempt 1 and attempt 2 to one material false-green completeness pattern while distinguishing repaired catalog coverage from the surviving data-oracle gap.",
    "retained_bytes": "Return KEEP_UNACCEPTED_FOR_NEXT_CAPSULE, REPLACE_IN_NEXT_CAPSULE, or REMOVE_IN_NEXT_CAPSULE for every one of the seven frozen inputs. This architecture task cannot accept or edit them.",
    "native_round_trip_oracle": "Define exact input, output, dialect adaptation, ordering, table coverage, row coverage, stored-byte, storage/type, key, FK, sequence, function, trigger, and reopen semantics with no self-comparison as evidence of caller fidelity.",
    "mutation_oracle": "Name each mutation identifier, concrete target, mutation layer, expected rejection seam, restoration proof, and evidence owner. Every required fact class must have at least one effective mutation; no shape-preserving no-op counts.",
    "claim_attestation": "Define a machine-checkable coverage manifest that binds all 24 tables, every catalog fact class, both corpora, both dialects, reopen boundaries, mutation IDs, exact commands, and final hashes.",
    "capsule_decomposition": "Emit a serial capsule DAG with fresh owners, exact paths, dependencies, tests, mutations, owner gates, stopping conditions, and deployability impact. Product/test overlap has parallel budget zero.",
    "root_gate": "No implementation resumes until root validates and accepts the recovery report, evidence manifest, architecture docs, capsule DAG, immutable inputs, protected hashes, and exact next capsule bytes."
  },
  "required_outputs": [
    ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/owner/report.md",
    ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/owner/evidence-manifest.json",
    ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/foundation_research_migration_projection_repeated_failure_architect/failure-lineage.json",
    ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/foundation_research_migration_projection_repeated_failure_architect/native-round-trip-contract.json",
    ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/foundation_research_migration_projection_repeated_failure_architect/mutation-coverage-matrix.json",
    ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/foundation_research_migration_projection_repeated_failure_architect/capsule-dag.json"
  ],
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-repeated-failure-recovery.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-runtime-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-evidence-integration.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-transitive-revalidation.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-review.md",
    ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery"
  ],
  "read_only_paths": [
    ".git",
    ".agent/runs/phase1-4-foundation-audit",
    ".agent/runs/phase1-4-foundation-critical-closure",
    ".agent/runs/phase1-4-foundation-postgresql-history-authority-recovery",
    ".agent/runs/phase1-4-foundation-research-migration-correction",
    ".agent/runs/phase1-4-foundation-research-migration-projection-correction",
    ".agent/runs/phase1-4-foundation-research-migration-repeated-failure-recovery",
    ".agent/runs/phase1-4-foundation-sqlite-history-authority-recovery",
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
    "The owner reproduces the root's PostgreSQL false green on current frozen bytes and proves an evidence-only proposed oracle rejects the same mismatch after real commit, close, engine disposal, and reopen.",
    "The failure lineage binds both bounded repairs and identifies the exact surviving material defect without erasing improvements made to catalog inspection.",
    "Every retained input receives a hash-bound disposition and no retained product or test byte receives architecture acceptance.",
    "The native round-trip contract enumerates all 24 durable tables and every required caller and catalog fact class for both dialects, including exact rules for database-native timestamp and boolean values without weakening byte-sensitive text, JSON, Unicode, or binary comparison.",
    "The mutation matrix contains concrete, effective, independently checkable mutations for every required data and catalog fact class; it identifies and forbids no-op, self-comparison, selected-slice, same-connection, and report-only evidence.",
    "A machine-checkable claim-attestation design prevents a report or manifest from claiming coverage absent from the executed final-byte tests.",
    "The serial DAG uses only fresh owners, makes the next implementation capsule executable without architecture judgment, and preserves runtime, integration, numeric, transitive, and review gates in order.",
    "Capsule JSON, repository architecture, scoped documentation diff, frozen inputs, protected hashes, audit freeze, evidence manifest, and all machine-readable outputs validate from final bytes."
  ],
  "test_plan": [
    "Re-run the current owner suite and the root mismatch probe only to reproduce the false-green boundary; do not relabel green owner counts as acceptance.",
    "Trace every caller corpus table and every native inventory field to an exact comparator, mutation, dialect, reopen boundary, evidence path, and future owner in machine-readable matrices.",
    "Use ignored evidence-only SQLite and disposable PostgreSQL 16 probes to demonstrate the proposed full-state oracle rejects changed rows in previously untested tables and restores exact native state.",
    "Audit every mutation for effectiveness by proving pre-mutation and post-mutation digests differ, the named oracle rejects, restoration returns the original digest, and a no-op mutation itself is rejected by the test harness.",
    "Validate all final docs and capsules, exact hashes, protected bytes, scope, machine-readable outputs, and evidence-manifest attestation."
  ],
  "owner_gates": [
    "Stop and return BLOCKED if any exact native representation, durable table, row, key, foreign key, sequence, owner, classification, Unicode, textual JSON, binary, timestamp, boolean, null, function, trigger, constraint, index, or default fact cannot be derived from the accepted catalog plus caller-owned synthetic corpus without invented authority.",
    "Stop for root and user direction only if evidence shows the accepted SQLite or PostgreSQL support matrix would strand a released, deployed, production, supported-database, customer, or externally promised state.",
    "Stop before changing product, tests, migrations, schemas, packages, CURRENT, PROGRAMME, review packages, dependencies, configuration, services, providers, frontend, credentials, deployment, production data, destructive state, live behavior, orders, or money behavior.",
    "Stop if the route uses current metadata, current-head rewind, cross-dialect translation, later-head dump, selected-row slices presented as complete, state compared only to a repeated read of itself, normalization that erases authority bytes, or a report claim not bound to executable evidence.",
    "Stop if any prior projection owner is proposed to resume, or if concurrent capsules share a write path, comparator, catalog authority, or acceptance claim."
  ],
  "stop_conditions": [
    "Any retained-byte disposition, native-value rule, durable table, catalog fact class, mutation, comparator, reopen boundary, claim-attestation field, future owner, dependency, or rejection seam remains implicit.",
    "The recovery begins a third local product patch, accepts green counts without adversarial falsification, or grants its own retained bytes implementation acceptance.",
    "The recovery claims runtime migration, release, deployment, production, supported-database, live, order, or money readiness."
  ],
  "deployment_impact": {
    "classification": "architecture-only; migration-required downstream",
    "highest_claim": "an independently falsifiable local projection-correction route",
    "unchanged": ["runtime behavior", "schema head", "dependencies", "configuration", "services", "providers", "frontend", "deployment", "production", "live authority", "order authority", "money authority"],
    "downstream_gates": ["projection implementation acceptance", "runtime migration acceptance", "SQLite and disposable PostgreSQL 16 integration", "transitive evidence revalidation", "independent critical review", "backup-first production-shaped rehearsal", "exact-build release gate"]
  },
  "nonclaims": [
    "This capsule changes no product, test, schema, migration, runtime, provider, frontend, deployment, production, live, order, or money behavior.",
    "An evidence-only oracle prototype is not product implementation or projection acceptance.",
    "The seven frozen product and test inputs remain unaccepted unless a later fresh implementation owner and independent review close the exact capsule.",
    "Accepted recovery architecture would not accept runtime migration, integration, numeric correction, transitive evidence, foundation closure, Phase 5, Phase 6, or release deployability."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "priority",
    "fresh_owner_required": true,
    "routing_basis": "Mandatory fresh architecture recovery after the same material projection-evidence defect survived two evidence-backed repairs. The primary owner's Ultra exception does not propagate."
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_research_migration_projection_repeated_failure_architect",
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
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-repeated-failure-recovery.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
      ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery"
    ],
    "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", ".agent/review-package.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
    "output": ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/owner/report.md",
    "verdicts": ["RECOVERY_ARCHITECTURE_ACCEPTABLE", "BLOCKED"]
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 1-4 foundation research-migration projection repeated-failure recovery

Two bounded repairs improved the projection implementation but did not close
the same material false-green completeness defect. The second final-byte suite
still accepted a changed durable PostgreSQL row after a real database reopen
because it compared caller state for only four of twenty-four tables. This
capsule ends local patch iteration and gives one fresh architecture owner the
task of defining an independently falsifiable correction route before any new
implementation owner is dispatched.
