---
{
  "id": "phase1-4-foundation-research-migration-projection-correction",
  "phase": "interphase-4-5",
  "status": "superseded_by_serial_native_oracle_chain",
  "activation_forbidden": "This combined implementation route is exhausted and cannot be dispatched. The accepted recovery architecture must activate phase1-4-foundation-research-migration-native-state-implementation, then phase1-4-foundation-research-migration-native-mutation-attestation, with independent root acceptance of the first node's exact bytes before the second starts.",
  "serial_successors": [
    "phase1-4-foundation-research-migration-native-state-implementation",
    "phase1-4-foundation-research-migration-native-mutation-attestation"
  ],
  "repeated_failure_rejection": {
    "path": ".agent/runs/phase1-4-foundation-critical-closure/projection-owner-2-attempt2-rejection.json",
    "sha256": "77d4b77f99048c1be990f8e74546bcb26a1affbe26f653ee847327f9b09ec292",
    "disposition": "Attempt 1 improved inventory comparison but did not prove a real reopen or full caller state. Attempt 2 added real reopen and broader catalogs but compared caller rows for only 4 of 24 tables. Both are rejected false greens. foundation_research_migration_projection_owner and foundation_research_migration_projection_owner_2 are permanently retired; neither may resume."
  },
  "recovery_architecture_gate": {
    "required_acceptance_path": ".agent/runs/phase1-4-foundation-critical-closure/native-oracle-repeated-failure-recovery-acceptance.json",
    "acceptance_sha256": "335b8ab0f4232fc61b57771f25427b713c27adec970293bab80a0d872dfdfec3",
    "accepted_pretransition_capsule_sha256": "8a32cbc8a93725189c26e61b2f1bd77f6b881ad12badfd787a9c38552d623c7f",
    "status": "accepted_architecture_only",
    "recovery_capsule": "phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery",
    "implementation_contract": ".agent/runs/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery/foundation_research_migration_native_oracle_repeated_failure_architect/implementation-contract.json",
    "implementation_contract_sha256": "a84f10df4c9e0854c15923130c588b6ece68c67c0e941a2cbcde333e1d4bf97f",
    "authority_consumption_map_sha256": "ce09d92d231da550d6cb7abc19f97d5f724261461daa648d139cf2fc849ad5ce",
    "failure_lineage_sha256": "cc3ed0268021d5ddf09bfbaf6f49f153276f80929df5261477c554529c213ed8",
    "capsule_dag_sha256": "e4b9be39199bd0f152361a75e4a02188bfc03baa45968c9cbbf79e62dc76e824",
    "dispatch_rule": "Root accepted the exact pretransition recovery report, manifest, implementation contract, and successor capsule bytes. Dispatch only fresh owner foundation_research_migration_native_oracle_owner_2 with parallel budget zero under a root dispatch that binds these activated capsule bytes."
  },
  "native_round_trip_owner_blocker": {
    "root_acceptance_path": ".agent/runs/phase1-4-foundation-critical-closure/native-round-trip-owner-blocked-acceptance.json",
    "root_acceptance_sha256": "88bd4edeaf679941b6a1bd68ff6d85254405cbc8a7577a4eb327080eb0124ccf",
    "blocked_report_sha256": "4dad14f2141da0e703abb8bce53f3ffac3ff5618d47a794488484e74c744d754",
    "blocked_manifest_sha256": "8fe2d4d41c62b7e22f636ce3b7176d8196e6848ffa2ccda77607f733757d55fc",
    "required_recovery_capsule": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery.md",
    "disposition": "Root accepts the stopping condition and repeated-failure route only. No product, test, schema, migration, runtime, support, deployability, release, or foundation claim is accepted."
  },
  "root_acceptance": {"path": ".agent/runs/phase1-4-foundation-critical-closure/sqlite-history-authority-recovery-acceptance.json", "sha256": "adefbe96d826d4eef330b344f85a64f76922075af5a253d27fd259c0d6f46aed", "scope": "SQLite recovery architecture and narrowed support route only"},
  "prior_owner_disposition": "foundation_research_migration_projection_owner, foundation_research_migration_projection_owner_2, and foundation_research_migration_native_round_trip_owner are BLOCKED and must never resume. Only fresh owner foundation_research_migration_native_oracle_owner_2 may start after root accepts these exact successor bytes.",
  "goal": "Implement one caller-derived native round-trip oracle that constructs and reopens the literal SQLite 0011 and PostgreSQL 0010 catalogs, verifies all 24 durable tables and complete catalog state for two materially distinct corpora, and makes every named data and catalog mutation fail closed.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only when both materially distinct caller corpora pass in SQLite and disposable PostgreSQL 16 through a table-complete 24/24 expected-state mapping derived only from that corpus plus frozen per-dialect ordered column/type declarations or caller-native typed values; exact marker, sequence values and bindings, rows, keys, foreign keys, owner attribution, legacy classification, nulls, Unicode, textual JSON bytes, BLOB/BYTEA bytes, documented timestamp/boolean adaptation, and complete catalog inventories survive commit, connection close, engine disposal, fresh-process reopen, and native comparison; every DATA-01..DATA-24 and CAT mutation records an effective digest delta, expected failure code, durable reopen where applicable, and exact restore; and a machine claim attestation rejects any missing corpus, dialect, table, mutation, receipt, or final-byte hash."
  },
  "dependencies": ["root acceptance of phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery exact report, manifest, implementation contract, and successor capsule bytes", "root acceptance of phase1-4-foundation-research-migration-projection-repeated-failure-recovery", "root acceptance of phase1-4-foundation-sqlite-history-authority-recovery"],
  "sqlite_recovery_binding": {"ledger_sha256": "874cc53fc1e455428915359a1253e225467bbe5d3057cd94abd153b3f4c9e7b8", "source_closure_sha256": "15e4882d086d88ea6fe9afdde11d9c688cf2c7f4b36981e7c6b40d20e1832ea9", "support_matrix_sha256": "63aa4c648d5a20298671810012dabaee690f886c52d562cb0dcc05cd270fd8e0", "catalog_digest": "bad35ce3288953c8b26ffdc0ea1906617d305b3f4a82da1d953f52070bf54635", "supported": ["empty", "exact_or_enumerated_five_guard_0010", "exact_0011"], "unsupported": ["unversioned", "0001-0009", "unknown_or_drifted"]},
  "risk_tags": ["critical", "research-migration", "schema-authority", "sqlite-postgresql-parity", "research-integrity"],
  "required_docs": [
    {"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["14. Foundation migration and market-number correction contract"]},
    {"path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "sections": ["9. Foundation migration and numeric correction route"]},
    {"path": "paper-trader/docs/agent/DEFECT_PATTERNS.md", "sections": ["DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Foundation migration and numeric correction"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/research/domain/migrations/sqlite_catalog_contract.py",
    "paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py",
    "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py",
    "paper-trader/backend/tests/foundation_postgresql_0010_builder.py",
    "paper-trader/backend/tests/test_foundation_research_projection_contracts.py",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
    ".agent/runs/phase1-4-foundation-research-migration-projection-correction"
  ],
  "read_only_paths": [
    "paper-trader/backend/research/domain/migrate.py",
    "paper-trader/backend/research/domain/migrations/0001_owner_scoped_roots.py",
    "paper-trader/backend/research/domain/migrations/0002_owner_operations.py",
    "paper-trader/backend/research/domain/migrations/0003_operation_item_checkpoints.py",
    "paper-trader/backend/research/domain/migrations/0004_transactional_outbox.py",
    "paper-trader/backend/research/domain/migrations/0005_strategy_admissions.py",
    "paper-trader/backend/research/domain/migrations/0006_ir_v2_admissions.py",
    "paper-trader/backend/research/domain/migrations/0007_phase4_dataset_provenance.py",
    "paper-trader/backend/research/domain/migrations/0008_ir_v2_graph_versions.py",
    "paper-trader/backend/research/domain/migrations/0009_phase4_dataset_authority.py",
    "paper-trader/backend/research/domain/migrations/0010_research_json_shape_parity.py",
    "paper-trader/backend/research/domain/models.py",
    "paper-trader/backend/research_tests",
    "paper-trader/backend/tests/test_phase4_authority_research_migration.py",
    "paper-trader/backend/tests/test_phase4_adversarial_migration_matrix.py",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    ".agent/review-package.json"
  ],
  "authority_contract": {
    "sqlite": "sqlite_catalog_contract.py contains the sole literal immutable logical target declaration: exact frozen current 0010 plus the five-guard delta and 0011 marker contract. Empty constructs this target directly. Exact or enumerated-five-guard 0010 transitions to it. Exact 0011 validates and no-ops. foundation_sqlite_catalog_builder.py imports this declaration and cannot redeclare DDL; runtime never imports tests. Unversioned, 0001-0009, unknown, and drifted states have no projection and refuse before writes.",
    "postgresql": "postgresql_0010_contract.py is a literal catalog freeze of accepted authority-ledger SHA-256 32a3735b5fe992e193a0e053b7940d77937fcfd7d86377a0f45b118bd828e0b1 and owns the forward 0011 = 0010 + guard-only delta target declaration. The later runtime migration consumes and must match that declaration; its DDL is not a second authority. The data-parametric witness builder consumes that catalog plus parameterized contract-valid data and cannot redefine schema or present witness values as historical facts.",
    "retained_edits": "sqlite_catalog_contract.py and postgresql_0010_contract.py are KEEP_UNACCEPTED_FOR_NEXT_CAPSULE inputs. foundation_sqlite_catalog_builder.py, foundation_postgresql_0010_builder.py, and test_foundation_research_projection_contracts.py are REPLACE_IN_NEXT_CAPSULE. 0007_phase4_dataset_provenance.py and 0008_ir_v2_graph_versions.py are KEEP_UNACCEPTED_FOR_NEXT_CAPSULE and read-only. No frozen byte receives acceptance from the recovery architecture."
  },
  "native_round_trip_contract": {
    "contract": ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/foundation_research_migration_projection_repeated_failure_architect/native-round-trip-contract.json",
    "mutation_matrix": ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/foundation_research_migration_projection_repeated_failure_architect/mutation-coverage-matrix.json",
    "failure_lineage": ".agent/runs/phase1-4-foundation-research-migration-projection-repeated-failure-recovery/foundation_research_migration_projection_repeated_failure_architect/failure-lineage.json",
    "authority_consumption_map": ".agent/runs/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery/foundation_research_migration_native_oracle_repeated_failure_architect/authority-consumption-map.json",
    "implementation_contract": ".agent/runs/phase1-4-foundation-research-migration-native-oracle-repeated-failure-recovery/foundation_research_migration_native_oracle_repeated_failure_architect/implementation-contract.json",
    "claim_attestation_rule": "Expected rows may use only the active caller corpus plus frozen ordered dialect declarations or caller-native typed values. They must never use an observed database row, observed inventory, repeated read, or normalized observed value. Execute both corpora, both dialects, all 24 tables, every catalog class, and every effective mutation from the recovery matrices; emit machine receipts and fail on any cardinality or digest mismatch.",
    "postgresql_function_repair": "Replace the frozen builder's PostgreSQL 16-incompatible _function_definition_signature and prove CAT-PG-10 and CAT-PG-20 with a declaration-derived semantic signature. The evidence-only recovery failure log grants no implementation acceptance."
  },
  "tests": [
    "From paper-trader/backend: .venv/bin/python -m pytest -q tests/test_foundation_research_projection_contracts.py",
    "Construct and reopen the sole SQLite target and exact PostgreSQL 0010 in isolated databases; run both recovery-defined corpora and compare the caller-derived complete expected state for every row of all 24 tables plus exact marker and sequence state after a fresh-process reopen.",
    "Execute DATA-01 through DATA-24 under both corpora and both dialects. Each operation must commit with guards enabled, change the expected-versus-observed digest, produce the named failure code after the required reopen, restore, and return to the exact baseline digest. Use the recovery-defined valid extra-row inserts for trigger-protected immutable tables; statement failure or guard disabling earns no credit.",
    "Execute every catalog mutation class in mutation-coverage-matrix.json against both corpora: table and column type/null/default, PK/FK/unique/check, index/predicate, sequence/serial binding, function body/identity/language, trigger table/event/function, and extra/missing objects.",
    "Generate claim-attestation.json from executed receipts and independently reject an attestation with either corpus, either dialect, one table, one mutation, one reopen receipt, or one final-byte hash removed.",
    "Run provenance rejection checks for current ResearchBase.metadata, current-head rewind, SQLite translation, later-head dump, omitted durable fact class, and invented facts.",
    "Run protected/frozen hashes, scoped diff, compile/import direction, JSON validation, and git diff --check."
  ],
  "test_plan": ["Execute every command in tests with full output logged through run_logged.py.", "Bind every supported catalog to a named source authority and execute corpus owner-alpha-id-7 and corpus owner-beta-id-101 without granting either authority.", "Compute expected native rows before observation from caller values plus frozen dialect declarations; preserve textual JSON and BLOB/BYTEA bytes exactly and document timestamp and boolean adapters.", "For each DATA mutation, prove the named operation commits with guards enabled before awarding digest-delta, reopen-rejection, and restore receipts. DATA-15 must insert native FLOAT 0.5, INTEGER 0, INTEGER 0, and BOOLEAN false for is_objective, is_trades, oos_trades, and selected.", "Inspect sequence state without nextval, inserts that consume defaults, or any other advancing call, and attest exact marker plus per-sequence values.", "Run and restore every catalog and data mutation before final hashes, then negative-test the machine attestation."],
  "acceptance": ["The sole SQLite target has one complete immutable literal catalog contract; unsupported historical states have no projection and no inferred or invented catalog fact is accepted.", "PostgreSQL 0010 matches the accepted authority ledger exactly and its builder defines no second authority.", "Both materially distinct synthetic corpora pass a table-complete 24/24 expected-to-native round trip in SQLite and PostgreSQL 16 without using observed rows or inventory to construct expected values.", "SQLite validates storage class and affinity and preserves textual JSON and BLOB bytes exactly. PostgreSQL validates declared column types, preserves text/varchar JSON and BYTEA bytes exactly, and uses documented caller-to-native timestamp and boolean adapters rather than normalizing observed values.", "Exact marker/version and sequence values and bindings, schema, every row, keys, foreign keys, owner attribution, classification, and stored bytes pass after actual commit, close, disposal, and fresh-process reopen.", "Every DATA and CAT mutation is effective, rejected with its expected code, restored exactly, and represented in a machine attestation whose independent negative tests pass."],
  "mutations": ["Execute the exact DATA-01..DATA-24 and CAT mutation IDs, operations, expected failure codes, reopen rules, and restore rules in mutation-coverage-matrix.json; substitutions require architecture re-acceptance.", "A mutation earns credit only when the operation succeeds, its committed observed digest differs from the caller-derived expected digest, the production-contract consumer returns the named failure code after required reopen, and exact restoration is proven.", "The matrix must cover table/column type-null-default, PK/FK/unique/check, index/predicate, sequence/serial binding, function body/identity/language, trigger table/event/function, extra/missing objects, and one effective data mutation for every table including research_hypothesis and research_finding.", "Restore exact bytes and native state before final validation."],
  "failure_triggers": ["Any state has two catalog authorities.", "Any SQLite catalog lacks a named source authority.", "Any witness value is treated as schema, historical, or user-fact authority.", "Any required stored fact must be invented.", "Any retained 0007/0008 byte changes.", "Any PostgreSQL 0010 declaration differs from the accepted ledger."],
  "stop_conditions": ["Any supported projection or fact class remains implicit.", "Any builder imports current metadata or declares schema.", "Any mutation survives final validation.", "Stop after the second evidence-backed failure of the same material implementation defect. Do not begin a third patch; return BLOCKED for a fresh recovery route."],
  "owner_gates": ["Stop for root and user direction only on evidence of a released, deployed, production, supported-database, customer, or externally promised removed SQLite or PostgreSQL state.", "Stop before production data, credentials, destructive repair, dependency, configuration, service, provider, frontend, deployment, live, or money work."],
  "deployment_impact": {"classification": "migration-required downstream; authority construction only", "highest_claim": "independently constructible local contracts", "unchanged": ["runtime behavior", "research head", "dependencies", "configuration", "services", "providers", "frontend", "deployment", "production", "live authority", "money authority"]},
  "model_route": {"owner": "gpt-5.6-terra", "owner_reasoning_effort": "medium", "service_tier": "priority", "fresh_owner_required": true, "assignment_id": "foundation_research_migration_native_oracle_owner_2"},
  "parallel_budget": 0,
  "assignments": [],
  "review": {"required": false, "assignment_id": "foundation_research_migration_native_oracle_owner_2", "activation": "Fresh owner route activated by root acceptance and the exact root dispatch; no retired owner may resume.", "base_sha": "HEAD", "review_paths": ["paper-trader/backend/research/domain/migrations/sqlite_catalog_contract.py", "paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py", "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py", "paper-trader/backend/tests/foundation_postgresql_0010_builder.py", "paper-trader/backend/tests/test_foundation_research_projection_contracts.py", ".agent/runs/phase1-4-foundation-research-migration-projection-correction"], "exclude_paths": ["paper-trader/backend/research/domain/migrate.py", "paper-trader/frontend"], "verdicts": ["IMPLEMENTATION_ACCEPTABLE", "BLOCKED"]},
  "nonclaims": ["Constructible contracts do not accept the runtime, retained edits, full migration matrix, release, or deployability."]
}
---

# Phase 1-4 foundation research migration projection correction

This capsule owns immutable projection authority and data-parametric witness builders only.
It cannot patch migration runtime or existing integration fixtures.
