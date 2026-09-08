---
{
  "id": "phase1-4-foundation-research-migration-native-state-contract-core",
  "phase": "interphase-4-5",
  "status": "blocked",
  "goal": "Replace the frozen failed native-state core bytes with the exact closed algebra, authority, encoding, digest, state-machine, comparison, and negative contracts sealed by recovery architecture.",
  "risk_tags": ["critical", "research-migration", "native-state-contract", "research-integrity"],
  "required_docs": [
    {"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["14. Foundation migration and market-number correction contract"]},
    {"path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "sections": ["9. Foundation migration and numeric correction route"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Foundation migration and numeric correction", "Foundation blockers", "Phase 4 ownership"]},
    {"path": "paper-trader/docs/agent/DEFECT_PATTERNS.md", "sections": ["DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"]}
  ],
  "goal_contract": {
    "create_before_product_work": true,
    "durable_goal": "Replace all three frozen failed files and prove every closed type, identity, byte rule, declaration source, state transition, mismatch, and rejection family without database or observer code.",
    "stopping_condition": "Complete only when the exact core node and recovery validator pass, every positive and negative matrix row has direct evidence, source and protected hashes match, and root accepts the same-byte report and manifest.",
    "attempt_limit": "one initial patch plus at most one repair"
  },
  "dependency_gate": "root-accepted-native-state-contract-core-recovery-exact-bytes",
  "dispatch_contract": "Root dispatch binds this capsule SHA-256, accepted recovery report and manifest hashes, all seven machine-contract hashes, retained-negative-control hash, serial-DAG hash, predecessor acceptance hash, HEAD, and frozen/protected hashes.",
  "owner": {"assignment_id": "foundation_native_state_contract_core_owner_2", "model": "gpt-5.6-terra", "reasoning_effort": "medium", "fresh_owner_required": true, "children": 0, "parallel_budget": 0},
  "model_route": {"owner": "gpt-5.6-terra", "owner_reasoning_effort": "medium", "service_tier": "priority", "fresh_owner_required": true, "assignment_id": "foundation_native_state_contract_core_owner_2"},
  "parallel_budget": 0,
  "assignments": [],
  "write_ownership": [
    "paper-trader/backend/tests/foundation_native_state_contract.py",
    "paper-trader/backend/tests/foundation_native_state_declarations.py",
    "paper-trader/backend/tests/test_foundation_native_state_contract_core.py"
  ],
  "allowed_paths": [
    "paper-trader/backend/tests/foundation_native_state_contract.py",
    "paper-trader/backend/tests/foundation_native_state_declarations.py",
    "paper-trader/backend/tests/test_foundation_native_state_contract_core.py",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core"
  ],
  "read_only_dependencies": [
    "paper-trader/backend/research/domain/migrations/sqlite_catalog_contract.py",
    "paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-implementation-repeated-failure-recovery/foundation_research_migration_native_state_implementation_repeated_failure_architect/authority-map.json",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery"
  ],
  "sealed_contracts": {
    "wire_and_types": {"path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/wire-and-type-authority-contract.json", "sha256": "6533ee880d5ca933b9c603cefe3f1459918c72fbd3bc8dbb0019c33a8f2b6dfd"},
    "digest_and_comparison": {"path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/digest-and-comparison-contract.json", "sha256": "b1cae2f482408c89663ac22a6004b85da37dfdebaa2808686f345be099a55ec0"},
    "expected_state_machine": {"path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/expected-state-machine.json", "sha256": "53f53005e2a878f4d123cd25ddb9f0a83861e7fd4cd69d2b80b75c286be585e2"},
    "negative_matrix": {"path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/negative-test-matrix.json", "sha256": "a76a27b5221c057275fbc9f94685b16a517bad5c38c79c73c014238bb399133d"},
    "failure_lineage": {"path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/failure-lineage.json", "sha256": "5443c245918e6d30c3bce2ac7a13da7520be29a6ea7d72d0a1da37a59843a1dc"},
    "byte_disposition": {"path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/byte-disposition.json", "sha256": "f2b3382bc27a73f87c43c401af6e75d67bd5c6c122b1ca2b78ac27dd521a4dbc"},
    "capsule_dag": {"path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/capsule-dag.json", "sha256": "7a7c6d9beb6d58dddaf1413c3c253af5fc0c1b4eba75ab5e5a04a55291b77db9"}
  },
  "required_implementation": {
    "types": "Implement every enum in wire-and-type-authority-contract.json closed_enums and every frozen slotted record in closed_record_schemas, with the exact field declaration order, type expression, cardinality, optionality, and constraint list. No local rename, field omission, helper substitution, or open enum is allowed.",
    "apis": ["strict_to_wire", "strict_from_wire", "canonical_bytes", "domain_digest", "ExpectedNativeState.from_caller", "seal_expectation_set", "compile_observation_plan", "issue_locator_lease", "seal_observation_request", "compare_native_state"],
    "wire_boundary": "Public wire roots are registered frozen dataclasses only. A separate module-private canonical-value encoder handles named digest preimages. Never send a tuple root through strict_to_wire.",
    "identities": "Use the exact 24 DATA and 39 CAT identities and enum members from negative-test-matrix.json. Placeholders reject.",
    "declaration_authority": "Independently hash and reconstruct the immutable modules and the accepted authority-map input 9b5d6530a447bc310348ffaeeaece8cd163a1191bccb37ae6ee10d2e2109e247 before construction. Exact equality with declaration_authority.source_projection.materialized_frozen_declarations is mandatory, using validate_materialized.py as the independent reconstruction specification: all 24 tables, 113 constraints per dialect, exact columns/FKs/checks/indexes/functions/triggers/sequences/bindings/policies, every field of all 35 resolved envelope payloads, and ordinal ordering. SQLite PK/unique authority is structural by origin and columns; reject every engine-assigned sqlite_autoindex name. Apply the exact expanded 24-table OwnerPolicy map and kind-presence matrix, declared-type adapter tables, catalog-attestation semantics, and CallerSequenceValue rules. SQLite base and post-migration schema_cookie are 68; each supported-old subset is exactly 68 minus the number of missing guards because every repairable guard is one omitted DDL statement. Bind construct_sql count=68/u64be byte framing. FrozenDialectDeclaration.construct_sql_sha256 is dialect-specific: the SQLite framed preimage and the compact UTF-8 PostgreSQL durable_ddl JSON array are the only formulas. Immutable FrozenCatalogDeclaration.owners and ResolvedCatalogDeclaration.owners are empty. PostgreSQL CatalogComparisonProjection.owners is derived from CallerScenario.expected_disposable_owner plus the exact ordered 188 materialized object identities, while observed owners are independently queried into that same field. SQLite CatalogComparisonProjection.owners is empty. SQLite must be e34b6de36bafe994ea4422570267cb30beb6996e9f9d2c505788e4f3ecb800a0 and owns exact base 0010 plus the exact five REPAIRABLE_GUARDS target authority. SQLITE_SUPPORTED_OLD carries an exact caller-selected, declaration-ordered missing subset and its total certified set is the complement, including empty; SQLITE_POST_MIGRATION has the complete five. PostgreSQL16 must be 1b399e20e48977a2ceae4cca75f0d3989f2d7558782354a23ebbf95d576256b8 and owns exact base 0010 plus GUARD_ONLY_DELTA. Both PostgreSQL envelopes contain the same immutable research_dataset_manifests_refuse_mutation and research_ir_v2_graph_versions_refuse_mutation pairs already present in CATALOG_0010; target 0011 is marker change plus certification, never a missing/add repair. Use the exact source authorities and dialect-specific CATALOG_DIGEST/CATALOG_ATTESTATION meanings in wire_and_types. Never trust generated self-claims.",
    "digest_contract": "Implement all 13 domain prefix byte strings, exact explicit preimage lists, and derivation_formulas in digest_and_comparison. TABLE, CATALOG, and STATE preimages are the closed TableComparisonProjection, CatalogComparisonProjection, and StateComparisonProjection record schemas, not prose field selections. Each private preimage uses sealed framing and declaration order. ObservationPlan and ObservationRequest declaration, plan, and locator digests must be independently recomputed by the exact named formulas, never accepted as caller authority. Implement every digest_roles formula, exclude every output digest from its own preimage, and bind STATE to scenario_id, envelope_kind, catalog_version, dialect, declaration, table, catalog, sequence, binding, and common authority projections.",
    "state_machine": "Construct the exact four ExpectedEnvelopeKind states, then seal one ExpectationSetReceipt carrying four positional envelope receipts, four expected digests, and four canonical hashes. Compile the declaration-only plan separately. issue_locator_lease consumes and independently verifies both aggregate receipt and plan, and binds both digests. Verify the FreshProcessReceipt carried by ObservationResponse after child exit and before comparison.",
    "rejections": "Implement the closed RejectionCode enum exactly. ComparisonResult unequal always carries COMPARISON_FACT_MISMATCH and nonempty mismatches sorted by closed MismatchKind declaration ordinal then exact path UTF-8 bytes. Every negative-test-matrix.json row asserts its exact expected_rejection_code; include each individual DATA/CAT omission and dead-consumer row.",
    "forbidden": ["sqlite3", "sqlalchemy", "subprocess", "database open", "builders", "dialect observers", "mutable registries", "product runtime", "observed-state expected inference", "request-carried expected payload", "tuple-only patch"]
  },
  "test_plan": [
    "Round-trip every required type through strict public dataclass-root wire encoding and assert exact declared field order.",
    "Assert all 24 DATA and 39 CAT identities, all closed enum members, all record fields, and every 24-table declaration ordinal.",
    "Prove private canonical-value vectors, framing, NativeScalar tags, tuple, map, row and table ordering, every digest domain, and exact preimage.",
    "Run one isolated exact-code rejection for all 310 rows of negative-test-matrix.json, including 48 DATA and 78 CAT identity-specific omission/dead-consumer rows, 12 resolved-record field-family rows, and 64 SQLite cookie/subset binding rows.",
    "Prove all four expected states and their receipt precede plan and locator; reject every observed or locator-bearing expected source.",
    "Mutate each MismatchKind fact and digest domain independently and assert the exact RejectionCode plus complete ComparisonResult including observed_digest, canonical hashes, ordered mismatch records, and aggregate digest.",
    "Run the exact core file and recovery validator in the repository venv with full output retained through run_logged.py.",
    "Root checks write-set diff, byte disposition, frozen/protected hashes, and same-byte manifest before acceptance."
  ],
  "acceptance": [
    "All three frozen failed files have REPLACE_IN_SUCCESSOR disposition; no old byte gains acceptance by inheritance.",
    "Every sealed type, authority, byte, digest, order, state transition, mismatch, and negative family has direct passing evidence.",
    "No database module is imported or opened and no observed value can enter expected construction.",
    "Root validates exact scope, hashes, and same-byte evidence before observer dispatch."
  ],
  "root_acceptance_gate": "Root accepts the exact owner-2 report, manifest, three written hashes, test and recovery-validator logs, scope validation, frozen/protected attestation, and no-third-attempt evidence before observer activation.",
  "deployment_impact": {"classification": "test-contract implementation only; migration-required downstream", "highest_claim": "local immutable contract-core evidence", "deployable": false, "downstream": "observer, obligations, mutation, runtime correction, integration, numeric correction, transitive revalidation, critical review, and foundation acceptance remain blocked"},
  "owner_gates": [
    "Stop if root dispatch does not bind accepted recovery hashes or any frozen/protected hash differs.",
    "Stop for any choice not fixed by the seven sealed machine contracts.",
    "Stop before editing a path outside write_ownership.",
    "Stop after the second failed attempt and return exact blocker evidence to root."
  ],
  "stop_conditions": [
    "Any wire root, canonical encoding, type, field, identity, authority, digest, preimage, order, state transition, comparison, or negative row remains implicit.",
    "Expected construction can read observed state or a locator can issue before all four expected receipts.",
    "The owner edits outside allowed paths or begins a third attempt."
  ],
  "review": {"required": false, "assignment_id": "foundation_native_state_contract_core_owner_2", "base_sha": "HEAD", "review_paths": ["paper-trader/backend/tests/foundation_native_state_contract.py", "paper-trader/backend/tests/foundation_native_state_declarations.py", "paper-trader/backend/tests/test_foundation_native_state_contract_core.py", ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core"], "exclude_paths": ["paper-trader/backend/research", "paper-trader/backend/app", "paper-trader/frontend"], "verdicts": ["IMPLEMENTATION_ACCEPTABLE", "BLOCKED"]},
  "nonclaims": ["No observer, DATA/CAT execution, migration, runtime, fixture, deployability, release, production, live, order, money, foundation, Phase 5, or Phase 6 claim follows from this slice."]
}
---

# Native-state contract core successor

This fresh serial successor replaces all three failed bytes under the exact recovery contracts. Root acceptance of the recovery evidence is its only activation route.
