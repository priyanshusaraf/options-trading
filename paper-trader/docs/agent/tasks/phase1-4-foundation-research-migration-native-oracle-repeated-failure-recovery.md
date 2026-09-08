---
{
  "id": "phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery",
  "phase": "interphase-4-5",
  "status": "ready",
  "goal": "Recover an executable, independently falsifiable native round-trip implementation route after the fresh projection owner stopped on two failed repairs of the same SQLite caller-derived expected-state helper, without beginning a third product or test patch.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "Root accepted only the stopping condition in .agent/runs/phase1-4-foundation-critical-closure/native-round-trip-owner-blocked-acceptance.json. The mission requires a fresh Sol-high recovery after two evidence-backed repairs of one material defect. This capsule authorizes read-only source analysis, local disposable SQLite and PostgreSQL 16 evidence-only probes, architecture and capsule documentation, and ignored evidence. It authorizes no product, test, schema, migration, runtime, CURRENT, PROGRAMME, review-package, dependency, configuration, service, provider, frontend, deployment, production, live, order, or money edit.",
    "stopping_condition": "Complete only when the owner has classified both failed repairs and every frozen input, proved a caller-derived 24-table SQLite and PostgreSQL 16 expected-state route can be implemented without observed-state inference, bound a safe disposable PostgreSQL 16 command, specified exact sequence and internal-table handling, emitted a fresh executable implementation capsule and serial dependency route, and produced a final report plus machine-attested evidence manifest. Return BLOCKED if any required native fact, frozen authority, or safe harness remains unavailable."
  },
  "risk_tags": [
    "critical",
    "repeated-failure-recovery",
    "research-migration",
    "native-oracle",
    "false-green-evidence",
    "sqlite",
    "postgresql16",
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
      "sections": ["Phase 1-4 foundation research migration projection correction"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-repeated-failure-recovery.md",
      "sections": ["Phase 1-4 foundation research migration projection repeated-failure recovery"]
    }
  ],
  "dependency_gate": "native-round-trip-owner-blocker-accepted",
  "trigger_evidence": {
    "root_blocker_acceptance": ".agent/runs/phase1-4-foundation-critical-closure/native-round-trip-owner-blocked-acceptance.json",
    "root_blocker_acceptance_sha256": "88bd4edeaf679941b6a1bd68ff6d85254405cbc8a7577a4eb327080eb0124ccf",
    "blocked_owner_report": ".agent/runs/phase1-4-foundation-research-migration-projection-correction/foundation_research_migration_native_round_trip_owner/BLOCKED-report.md",
    "blocked_owner_report_sha256": "4dad14f2141da0e703abb8bce53f3ffac3ff5618d47a794488484e74c744d754",
    "blocked_owner_manifest": ".agent/runs/phase1-4-foundation-research-migration-projection-correction/foundation_research_migration_native_round_trip_owner/evidence-manifest.json",
    "blocked_owner_manifest_sha256": "8fe2d4d41c62b7e22f636ce3b7176d8196e6848ffa2ccda77607f733757d55fc",
    "repair_1_sha256": "645907151ddd5833af30fb680c92e1cc309fa79e9755b665b1913962a814bbf5",
    "repair_2_sha256": "76444c33e1128a01119e8d4c653ddb2f4649ba85427aa4560288ded2732830eb",
    "root_validation_sha256": "48137995cfa34763fc2212ec75486a4604bdf474dbd2ca9cdf866e3c16d3d803",
    "accepted_projection_recovery_sha256": "cff201778460bd9ed59b18079586539343f526101e4b0eab35e526df2ce75680",
    "accepted_native_round_trip_contract_sha256": "2b22e7aa4f90da667da314f92c1b0192625ccf6ad21573f114e1cd3467d0ba37",
    "accepted_mutation_coverage_matrix_sha256": "632f50ad19e37217966a490152680381b16a25ce653c9b33962ac4a79dea0c9a"
  },
  "frozen_unaccepted_inputs": {
    "paper-trader/backend/research/domain/migrations/sqlite_catalog_contract.py": "e34b6de36bafe994ea4422570267cb30beb6996e9f9d2c505788e4f3ecb800a0",
    "paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py": "1b399e20e48977a2ceae4cca75f0d3989f2d7558782354a23ebbf95d576256b8",
    "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py": "5c4b7b6be149a427018c8020de128cbb192b1d500ed4710e57df3ef589be3bf1",
    "paper-trader/backend/tests/foundation_postgresql_0010_builder.py": "c846cde111341f06dcb3b5ed218fe4ef1ef9604d470840da320e86f468847bc5",
    "paper-trader/backend/tests/test_foundation_research_projection_contracts.py": "f4e000eb3883f47c7c248a8fa00ed76469bb636eb2dd474a1104eca7413d02b5",
    "paper-trader/backend/research/domain/migrations/0007_phase4_dataset_provenance.py": "1dddeb3b9913a6d00291e112880180b488238db11058448a557884628a6cb6dc",
    "paper-trader/backend/research/domain/migrations/0008_ir_v2_graph_versions.py": "76ab8f6dcd5f6cd4019702a5737250720f1982d113cac16e2958afeb939717c2"
  },
  "known_facts": {
    "sqlite_table_classes": "The frozen SQLite inventory contains 26 tables: 24 caller-populated durable tables, the research_schema_version marker table, and SQLite's internal sqlite_sequence table. Caller corpora must declare exactly the 24 durable tables.",
    "sqlite_declaration_split": "INVENTORY.tables carries table_xinfo, foreign_key_list, index_list, and index_xinfo facts. Literal SQL resides in INVENTORY.sqlite_schema. A helper may join those two frozen declarations by explicit object name and type; it may not assume each table inventory member carries a sql field.",
    "sqlite_sequence_rule": "Expected sequence state must come from caller keys plus frozen AUTOINCREMENT identity declared by the literal sqlite_schema authority. It must not come from an observed sqlite_sequence read, an advancing next-value call, or a current ORM model.",
    "postgresql_harness": "The root validator proved scripts.run_disposable_postgres.locate_postgres_16_tools resolves /opt/homebrew/Cellar/postgresql@16/16.14_1/bin. PT_TEST_POSTGRES_URL need not be pre-set because the repository harness creates and supplies a loopback-only disposable URL to its child."
  },
  "architecture_questions": [
    "Did the two failed repairs expose a missing architecture fact or only an implementation that failed to consume already frozen declarations correctly?",
    "What one explicit dialect-neutral caller-state input and two dialect adapters produce exact expected marker, sequences, native values, row ordering, keys, foreign keys, owner attribution, textual JSON bytes, Unicode, binary, booleans, timestamps, dates, nulls, and classifications for all 24 tables without reading observed rows or inventory?",
    "How will SQLite identify the 24 caller tables, the marker table, the internal sqlite_sequence table, and AUTOINCREMENT identities from the accepted literal contract without adding a second schema authority?",
    "How will PostgreSQL derive exact sequence names, serial bindings, last values, is_called states, timestamp and boolean adapters, and all 24 expected rows from frozen declarations plus caller values?",
    "What smallest evidence-only probe proves both current SQLite failure causes are absent and proves the repository disposable PostgreSQL 16 harness executes the same complete caller-derived route?",
    "Which current bytes should a fresh implementation keep, replace, or remove, and what exact ownership prevents another informal patch series?",
    "What machine receipt and negative mutation prove the implementation executed both corpora, both dialects, all 24 tables, required reopen boundaries, every DATA and CAT identifier, exact restoration, and final byte hashes?"
  ],
  "required_decisions": {
    "failure_lineage": "Bind both failed helper repairs to one material expected-state construction defect. Distinguish the helper defect from the earlier selected-slice false green and preserve prior accepted architecture facts.",
    "retained_bytes": "Return KEEP_UNACCEPTED_FOR_NEXT_CAPSULE, REPLACE_IN_NEXT_CAPSULE, or REMOVE_IN_NEXT_CAPSULE for every frozen input. Architecture cannot accept or edit any of them.",
    "caller_oracle": "Specify one complete expected-state API, exact allowed inputs, forbidden observed inputs, dialect adapters, ordering, native type rules, marker rules, sequence rules, fresh-process reopen rules, and failure codes.",
    "sqlite_authority_consumption": "Define a mechanical join from the frozen sqlite_schema object list to the frozen per-table inventory and caller corpus. Treat sqlite_sequence as an internal derived fact and research_schema_version as a contract marker, not caller data.",
    "postgresql_execution": "Bind the exact safe disposable PostgreSQL 16 command and prove it starts, executes an evidence-only complete-state probe, tears down, and leaves no external database or inherited URL dependency.",
    "successor_capsule": "Emit exact successor capsule bytes for one fresh implementation owner, with bounded overlapping ownership, parallel budget zero, two-attempt stopping rule, direct tests, mutation coverage, report/manifest contract, and root acceptance gate.",
    "serial_dag": "Preserve projection implementation, runtime migration, evidence integration, numeric correction, transitive revalidation, and one critical review in serial order."
  },
  "required_outputs": [
    ".agent/runs/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery/owner/report.md",
    ".agent/runs/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery/owner/evidence-manifest.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery/foundation_research_migration_native_oracle_repeated_failure_architect/failure-lineage.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery/foundation_research_migration_native_oracle_repeated_failure_architect/authority-consumption-map.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery/foundation_research_migration_native_oracle_repeated_failure_architect/implementation-contract.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery/foundation_research_migration_native_oracle_repeated_failure_architect/capsule-dag.json"
  ],
  "allowed_paths": [
    "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
    "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-runtime-correction.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-evidence-integration.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-transitive-revalidation.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-review.md",
    ".agent/runs/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery"
  ],
  "read_only_paths": [
    ".git",
    ".agent/runs/phase1-4-foundation-audit",
    ".agent/runs/phase1-4-foundation-critical-closure",
    ".agent/runs/phase1-4-foundation-postgresql-history-authority-recovery",
    ".agent/runs/phase1-4-foundation-research-migration-correction",
    ".agent/runs/phase1-4-foundation-research-migration-projection-correction",
    ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery",
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
    "The owner verifies every trigger, dispatch, accepted architecture, frozen product/test, protected boundary, CURRENT, PROGRAMME, and audit-freeze hash before analysis.",
    "Failure lineage proves the two repairs failed at the same expected-state construction boundary and states whether any architecture fact is genuinely missing.",
    "An evidence-only SQLite probe derives expected state from the two caller corpora plus frozen declarations, covers exactly 24 caller tables, handles marker and sqlite_sequence separately, survives a real close and fresh-process reopen, and rejects at least one effective durable-row mutation before exact restoration.",
    "An evidence-only PostgreSQL probe runs through paper-trader/backend/scripts/run_disposable_postgres.py against PostgreSQL 16, derives expected state without observed-row inference, covers both corpora and all 24 tables, and proves a real close/reopen rejection and restoration boundary.",
    "Authority-consumption-map.json maps every expected output field to caller corpus, accepted SQLite declaration, accepted PostgreSQL declaration, or exact deterministic adapter and maps no field to an observed row or current metadata.",
    "Every frozen input receives a hash-bound disposition, and no product, test, schema, migration, or retained byte receives architecture acceptance.",
    "The exact fresh successor capsule contains no remaining architecture choice, preserves all accepted DATA and CAT mutation obligations, limits implementation to one owner with parallel budget zero, and binds a two-attempt stop rule plus root acceptance gate.",
    "Final capsule JSON, repository architecture, docs scope, diff check, machine outputs, evidence manifest, protected hashes, and frozen hashes pass from the same bytes."
  ],
  "test_plan": [
    "Reproduce both helper failures from their immutable logs. Do not edit or rerun the blocked implementation as a third repair.",
    "Write evidence-only oracle prototypes under the ignored run path. They may import frozen declarations and caller corpus values read from frozen test bytes, but they cannot change or grant acceptance to those bytes.",
    "Prove SQLite table-class partitioning, literal SQL lookup, AUTOINCREMENT identity, expected sequence values, marker state, native row values, exact ordering, process-independent reopen, effective mutation rejection, and restoration.",
    "Invoke the repository disposable PostgreSQL 16 harness without relying on a pre-set PT_TEST_POSTGRES_URL. Prove start, isolated execution, two-corpus complete-state comparison, effective mutation rejection, restoration, and cleanup.",
    "Trace all 24 tables and every caller/native fact to the successor implementation API, direct test, mutation identifier, evidence receipt, and owner.",
    "Validate final docs, capsules, exact hashes, protected files, audit freeze, ignored evidence manifest, scoped diff, and repository architecture."
  ],
  "owner_gates": [
    "Stop and return BLOCKED if any required expected native fact cannot be derived from accepted frozen declarations plus caller-owned values without observed-state inference or invented authority.",
    "Stop if the repository PostgreSQL 16 harness fails after checking its supported versioned package-manager paths; retain full diagnostics and distinguish an environment fault from a contract fault.",
    "Stop for root and user direction only if evidence shows an accepted support decision would strand a released, deployed, production, supported-database, customer, or externally promised state.",
    "Stop before product, test, schema, migration, runtime, CURRENT, PROGRAMME, review-package, dependency, configuration, service, provider, frontend, credential, deployment, production-data, destructive, live, order, or money changes.",
    "Stop if any prior projection implementation owner is proposed to resume, if a third local patch begins, or if concurrent owners share a write path or acceptance claim."
  ],
  "stop_conditions": [
    "Any expected-state input, table class, sequence rule, marker rule, native adapter, ordering rule, reopen boundary, mutation, receipt, byte disposition, future owner, dependency, or rejection seam remains implicit.",
    "Any expected value comes from an observed row, repeated read, current ResearchBase.metadata, current-head rewind, later dump, cross-dialect translation, or normalization that erases exact bytes.",
    "The recovery edits product or tests, grants retained bytes implementation acceptance, or claims runtime, release, deployment, production, live, order, or money readiness."
  ],
  "deployment_impact": {
    "classification": "architecture-only; migration-required downstream",
    "highest_claim": "a locally executable and independently falsifiable recovery route",
    "unchanged": ["product behavior", "tests", "schema head", "dependencies", "configuration", "services", "providers", "frontend", "deployment", "production", "live authority", "order authority", "money authority"],
    "downstream_gates": ["projection implementation acceptance", "runtime migration acceptance", "SQLite and disposable PostgreSQL 16 evidence integration", "numeric correction", "transitive evidence revalidation", "independent critical review", "backup-first production-shaped rehearsal", "exact-build release gate"]
  },
  "nonclaims": [
    "This capsule changes no product, test, schema, migration, runtime, provider, frontend, deployment, production, live, order, or money behavior.",
    "A passing evidence-only oracle prototype proves route feasibility, not implementation acceptance.",
    "No prior owner report, green count, contract declaration, builder, suite, retained 0007/0008 edit, or blocked-attempt byte becomes accepted here.",
    "Foundation closure, Phase 5, Phase 6, release, supported-database, and production readiness remain blocked."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "service_tier": "default",
    "fresh_owner_required": true,
    "repeated_failure_exception": "The same material implementation defect survived two evidence-backed repair attempts."
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_research_migration_native_oracle_repeated_failure_architect",
    "base_sha": "HEAD",
    "review_paths": [
      "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-runtime-correction.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-evidence-integration.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-transitive-revalidation.md",
      "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-review.md",
      ".agent/runs/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery"
    ],
    "exclude_paths": [
      "paper-trader/backend",
      "paper-trader/frontend",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      ".agent/review-package.json"
    ],
    "verdicts": ["RECOVERY_ARCHITECTURE_ACCEPTABLE", "BLOCKED"]
  }
}
---

# Phase 1-4 foundation research migration native-oracle repeated-failure recovery

This capsule resolves the expected-state construction route after the fresh native round-trip owner stopped at the mandatory two-repair boundary. It owns architecture, executable evidence-only feasibility, downstream capsule contracts, and ignored evidence only.

The owner must not repair the three frozen builder and suite files. A successful result gives a fresh implementation owner mechanical instructions and a safe two-dialect harness. Root acceptance is required before that owner starts.
