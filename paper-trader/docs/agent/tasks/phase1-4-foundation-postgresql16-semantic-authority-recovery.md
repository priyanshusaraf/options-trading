---
{
  "id": "phase1-4-foundation-postgresql16-semantic-authority-recovery",
  "phase": "interphase-4-5",
  "status": "active",
  "goal": "Produce one immutable, independently authenticated PostgreSQL 16 semantic catalog authority package from disposable loopback databases so native-state contract architecture can resume without inventing catalog facts.",
  "risk_tags": [
    "critical",
    "evidence-authority-recovery",
    "research-migration",
    "postgresql",
    "catalog-semantics",
    "false-green-evidence",
    "research-integrity",
    "deployability"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "14. Foundation migration and market-number correction contract"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "9. Foundation migration and numeric correction route"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Foundation migration and numeric correction",
        "Foundation blockers",
        "Phase 4 ownership"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-state-contract-core-recovery.md",
      "sections": [
        "Native-state contract-core recovery"
      ]
    }
  ],
  "goal_contract": {
    "create_before_work": true,
    "durable_goal": "Construct and independently validate a closed receipt wire and canonicalization contract, a fixed PostgreSQL 16 structural query registry, two isolated reference-run receipts, one stable semantic projection, a real owner mutation and restoration receipt, and complete lifecycle cleanup evidence without changing product or test bytes.",
    "stopping_condition": "Complete only when two independently created disposable PostgreSQL 16 databases yield the same stable semantic projection from the same frozen source DDL and fixed query registry; each run uses a fresh authenticated observer login distinct from the object owner; one run proves a real owner mutation, mismatch, restoration, and equality through the unchanged observer connection; both databases and clusters are destroyed; every receipt, validator, log, and manifest is same-byte hash bound; and root can accept the package without choosing or inventing a semantic fact. Return BLOCKED if any required fact, canonical rule, authentication boundary, mutation, restoration, cleanup fact, or reproducibility result is absent or ambiguous.",
    "recovery_rule": "This capsule creates evidence authority only. It may open only fresh disposable loopback PostgreSQL 16 instances. It may not edit product, tests, migrations, runtime, configuration, dependencies, CURRENT, PROGRAMME, the review package, or prior evidence; it may not connect to any external, shared, deployed, production, credential-bearing, or non-disposable database."
  },
  "dependency_gate": "native-state-contract-core-recovery-blocked-stopping-condition-root-accepted",
  "trigger_evidence": {
    "root_blocker_acceptance": {
      "path": ".agent/runs/phase1-4-foundation-critical-closure/native-state-contract-core-recovery-blocker-acceptance.json",
      "sha256": "ec46dcace3977a4a5587c840414c80121af30fe1e89684f501fdd06fa2b167fe"
    },
    "blocked_report": {
      "path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/owner/report.md",
      "sha256": "4eaa3fa8206d9429979dfaef89ea2f8e7cc6229486fc520357b901649e9ae344"
    },
    "blocked_manifest": {
      "path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/owner/evidence-manifest.json",
      "sha256": "3e79cdf07a4c68b79427bb973756be321d599ba3d37d948231289910dbfee0d9"
    },
    "missing_authority_contract": {
      "path": ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery/foundation_native_state_contract_core_recovery_architect/blocked-postgresql16-semantic-authority-gate.json",
      "sha256": "d8708aa5f6a78865410cfa991aff4a0d73af5854597f1310a00d6d4286e634cb"
    },
    "toolchain_availability": {
      "path": ".agent/runs/phase1-4-foundation-critical-closure/root/pg16-toolchain-independent-probe.log",
      "sha256": "eece1485338e00d35a755aaf16e861b7369e636e695db9e6093a381f36d6314d",
      "classification": "availability only; not semantic authority"
    }
  },
  "authority_inputs": {
    "postgresql_0010_contract": {
      "path": "paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py",
      "sha256": "1b399e20e48977a2ceae4cca75f0d3989f2d7558782354a23ebbf95d576256b8",
      "durable_ddl_sha256": "cf0975f9e03d98587c5d5e671a335fb17a0ac5703198000b6b3dceeae4e1b9b2",
      "role": "sole frozen DDL provenance input; source text and its parsers are not semantic catalog authority"
    },
    "disposable_harness": {
      "path": "paper-trader/backend/scripts/run_disposable_postgres.py",
      "sha256": "103937cb6cded3669bc55d54e85191f0f97330a2a265d8dd1a37e9c7383ac9f8",
      "role": "loopback lifecycle harness only; it is not expected semantic authority"
    },
    "server": {
      "required_major": 16,
      "available_version_num": 160014,
      "available_path": "/opt/homebrew/Cellar/postgresql@16/16.14_1"
    }
  },
  "required_contracts": {
    "wire_and_canonicalization": [
      "Define every receipt record, field, type, field order, tuple order, duplicate refusal, scalar encoding, length framing, nullable encoding, identifier encoding, bytes encoding, uint encoding, boolean encoding, and sha256 encoding in one immutable machine-readable contract before database creation.",
      "Use the exact domain prefix STRATEGY_OS_POSTGRESQL16_INDEPENDENT_SEMANTIC_AUTHORITY_V1 followed by one NUL byte. The prefix hex must equal 53545241544547595f4f535f504f535447524553514c31365f494e444550454e44454e545f53454d414e5449435f415554484f524954595f563100.",
      "The receipt digest excludes only receipt_digest itself. JSON object serialization, sorted map keys, implicit host-language repr, whole deparser text, and self-digest inclusion are forbidden.",
      "The authority package may define this closed evidence encoding because root will accept or reject its exact bytes together with the receipts. No downstream contract may consume it before that root acceptance."
    ],
    "query_registry": [
      "Write query-registry.json before either reference database is created. Each ordered row contains query_id, server_major, result_record_type, ordered_result_columns, exact SQL UTF-8 bytes, and SQL SHA-256. The receipt carries the declared row projection plus the registry digest; the manifest binds the full registry artifact.",
      "Query only current_setting('server_version_num') and structural pg_catalog sources named by the missing-authority contract: pg_proc, pg_namespace, pg_language, pg_roles, pg_trigger, pg_class, pg_sequence, pg_depend, pg_attribute, pg_index, pg_am, pg_opclass, pg_collation, pg_get_function_identity_arguments, pg_get_function_result, and pg_get_expr.",
      "Do not use pg_get_indexdef, pg_get_functiondef, pg_get_triggerdef, source-DLL parsing, or a target observation to define expected semantics.",
      "Function rows cover identity, argument types, return type, language, prosrc, volatility, strictness, security definer, parallel safety, cost, rows, config, and owner. Trigger rows cover identity, table, timing, events, function identity, exact tgargs, tgenabled, and pg_get_expr WHEN. Sequence rows cover identity, table-column binding, seqtypid, start, min, max, increment, cache, and cycle. Index rows cover identity, table, uniqueness, access method, ordered structural keys or expressions, opclasses, collations, and pg_get_expr predicate. Owner rows cover TABLE, INDEX, SEQUENCE, and FUNCTION.",
      "Each query declares a total stable result order and rejects duplicate semantic identities. All objects in the isolated authority schema matching the registered kinds are observed; a source-name allowlist may not silently omit an object."
    ],
    "authentication_and_independence": [
      "Each run creates opaque random database, schema, cluster, observer-role, owner-role, and nonce identities that encode no expected object name, owner, scenario, marker, row, or digest.",
      "The observer login role and object owner role differ. The observer connects through a fresh authenticated connection as session_user and current_user; SET ROLE on an administrator or harness connection receives no credit.",
      "The observer has read-only catalog visibility and no DDL, ownership, role-membership, or object-mutation authority. An administrator and object-owner connection remain outside observer inputs.",
      "The frozen literal durable DDL is applied without translating its semantics. If a helper executes it, the owner must prove exact statement-byte and aggregate-DDL-hash equality before use. Parsing source DDL may locate executable statements but may not supply expected semantic values.",
      "Both semantic payloads are sealed before any downstream target locator, target credential, target catalog, target owner, or native-state expected builder is available."
    ],
    "owner_mutation_and_restoration": [
      "In the first run an administrator changes one registered object's owner to a distinct temporary role. The unchanged authenticated observer connection re-runs the fixed owner query and records a different digest plus COMPARISON_FACT_MISMATCH at the exact CAT-PG-17 object-kind/schema/identity/owner path.",
      "The administrator restores the original owner. The same observer connection re-observes it. Pre and restored facts and digests must match exactly; mutated facts and digest must differ; every ALTER and observation must succeed and be recorded.",
      "The receipt records observer connection nonce, session_user, current_user, backend pid, original owner, temporary owner, admin mutation nonce, pre/mutated/restored facts, and pre/mutated/restored digests. A literal or synthesized mutation record receives no credit."
    ],
    "two_stage_lifecycle_seal": [
      "Stage A seals the immutable semantic payload and its digest while the isolated reference database exists. That payload contains the fixed registry digest, server version, source hashes, semantic facts, authenticated observer facts, and completed owner mutation/restoration facts, but no cleanup or log hash.",
      "After Stage A, the run drops the reference database, stops the private cluster, removes disposable resources, closes the complete run log, and computes that log's SHA-256. The log must terminate before the final envelope is assembled and must not contain the final receipt bytes or final receipt digest.",
      "Stage B assembles the final Postgresql16IndependentSemanticAuthorityReceipt from the Stage-A payload and lifecycle receipt, including database_dropped, cluster_stopped, cleanup_exit_code, and full_log_sha256, then computes the final domain-separated receipt digest. The missing-authority contract's receipt-sealing independence event means the Stage-A semantic seal; this two-stage rule prevents a self-referential log hash while preserving cleanup proof.",
      "A cleanup failure, live process, remaining database, remaining role, remaining cluster directory, or missing final log is a failed run and cannot be repaired by editing the receipt."
    ],
    "reproducibility": [
      "Run the complete construction twice from separate cluster directories, ports, opaque identities, roles, databases, schemas, connections, and nonces. Do not clone the first data directory or database.",
      "Define semantic-projection.json before comparing runs. It includes only stable structural semantic facts and the source/query-registry/server-major bindings; it excludes run nonce, database, schema alias, generated role names, port, pid, timestamps, and lifecycle identifiers while preserving owner relationships through explicit stable role classes.",
      "The two stable semantic projections and their canonical digests must match exactly. Both full receipts remain distinct and independently lifecycle-complete. Any unexplained semantic difference is BLOCKED, not normalized away."
    ]
  },
  "required_outputs": [
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/report.md",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/evidence-manifest.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/receipt-wire-and-canonicalization-contract.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/query-registry.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/semantic-projection-contract.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/reference-run-1-semantic-payload.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/reference-run-1-receipt.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/reference-run-2-semantic-payload.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/reference-run-2-receipt.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/owner-mutation-receipt.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/postgresql16-semantic-authority-reproducibility-receipt.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/semantic-projection.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery/owner/negative-test-matrix.json"
  ],
  "allowed_paths": [
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery"
  ],
  "read_only_paths": [
    ".git",
    ".agent/runs/phase1-4-foundation-audit",
    ".agent/runs/phase1-4-foundation-critical-closure",
    ".agent/runs/phase1-4-foundation-postgresql-history-authority-recovery",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-contract-core-recovery",
    "paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py",
    "paper-trader/backend/scripts/run_disposable_postgres.py",
    "paper-trader/backend/tests/foundation_postgresql_0010_builder.py",
    "paper-trader/backend/tests/foundation_native_state_contract.py",
    "paper-trader/backend/tests/foundation_native_state_declarations.py",
    "paper-trader/backend/tests/test_foundation_native_state_contract_core.py",
    "paper-trader/backend/tests/test_foundation_research_projection_contracts.py",
    "paper-trader/backend/app",
    "paper-trader/backend/research",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql16-semantic-authority-recovery.md",
    ".agent/review-package.json"
  ],
  "tests": [
    "Before opening PostgreSQL, verify every trigger-evidence, capsule, source, harness, CURRENT, PROGRAMME, critical-closure, frozen failed-input, and protected-file hash supplied by root dispatch.",
    "Validate the receipt wire/canonicalization contract, exact registry SQL bytes and hashes, closed record fields, canonical order, domain prefix, duplicate refusal, and digest preimages before database creation.",
    "Use the repository disposable harness or a byte-attested evidence-only wrapper to run two independent loopback PostgreSQL 16 constructions. Record complete command output under the capsule evidence path.",
    "Prove fresh observer authentication from session_user/current_user, observer-owner inequality, fixed-registry structural observation, full schema-kind inventory, real owner mutation visibility, exact restoration, and process/resource cleanup.",
    "Mutate one registry SQL byte, one ordered result column, every receipt field family, observer identity, owner fact, sequence binding, index structural fact, function semantic field, trigger semantic field, semantic-projection inclusion rule, Stage-A payload digest, lifecycle fact, log hash, and final receipt digest one at a time; every mutation must be rejected and restored.",
    "Run independent same-byte validators that consume only sealed outputs, not in-memory collector objects. Recompute all artifact hashes, source/harness/protected hashes, manifest bindings, and the two stable semantic projection digests.",
    "Run capsule JSON validation, repository architecture validation, scoped status/diff checks, git diff --check, and final manifest attestation."
  ],
  "test_plan": [
    "Apply architecting-strategy-os-phases to keep semantic authority singular, executing-strategy-os-slices to enforce this evidence-only boundary, and auditing-strategy-os-deployability to bind disposable-local nonclaims and cleanup.",
    "Retain and classify every failed collector, query, harness, mutation, cleanup, or validator log. Only final same-byte receipts from complete runs support the verdict.",
    "Use one durable goal and no children. The owner may make bounded evidence-script repairs, but a repeated material authority or independence defect after two evidence-backed attempts must stop and return to root for fresh recovery architecture.",
    "Do not run broad product tests. The only executable target is the disposable authority collector and its independent validators."
  ],
  "acceptance": [
    "The exact missing-authority record and every nested field from the root-accepted blocked gate are represented in the closed wire contract without weakening or omission.",
    "The query registry exists and is hash sealed before database creation, contains exact SQL bytes and ordered structural results, uses only authorized pg_catalog sources, and contains no forbidden deparser or source-semantic inference.",
    "Two isolated PostgreSQL 16 runs authenticate fresh observer connections distinct from object owners and yield identical stable semantic projections while retaining distinct run and lifecycle facts.",
    "One complete run proves a real owner change, exact CAT-PG-17 mismatch through the unchanged observer connection, exact restoration, and restored equality.",
    "Both Stage-A semantic payloads are sealed before cleanup; both databases and clusters are then destroyed; both logs close; both Stage-B receipts bind cleanup and log hashes without a digest cycle.",
    "Independent validators reject every negative family and recompute registry, semantic, mutation, lifecycle, receipt, reproducibility, and manifest hashes from final bytes.",
    "Only the PostgreSQL 16 semantic authority evidence package is eligible for root acceptance. No prior recovery architecture, implementation, migration, runtime, integration, deployability, foundation, Phase 5, or Phase 6 claim is accepted."
  ],
  "owner_gates": [
    "Stop if any trigger, dispatch, source, harness, frozen failed-input, protected-file, CURRENT, PROGRAMME, critical-closure, or active-capsule hash differs.",
    "Stop before connecting to any host other than loopback or any database not freshly created and owned by this evidence run. Never read credentials or use an existing service database.",
    "Stop if expected semantic facts would come from source parsing, a target observation, a previous receipt, a deparser, current metadata, a rewind, a later dump, or an invented default.",
    "Stop if the observer is not a freshly authenticated distinct login, if its authority exceeds read-only observation, if the owner mutation is not real and restored, or if cleanup cannot be proved.",
    "Return to root for exact-byte acceptance. The owner may not activate or amend downstream architecture or implementation capsules."
  ],
  "stop_conditions": [
    "Any receipt field, wire rule, canonical preimage, query byte, result ordering, semantic projection rule, authentication fact, mutation fact, restoration fact, lifecycle fact, or cleanup fact remains implicit or is inferred after observation.",
    "The two independent stable semantic projections differ, an observed object is omitted, a duplicate identity is accepted, or a negative mutation survives.",
    "The receipt or log creates a hash cycle, the final receipt predates cleanup, or the semantic payload is not sealed before cleanup.",
    "Any product, test, migration, runtime, configuration, dependency, service, provider, frontend, CURRENT, PROGRAMME, review-package, deployment, production, live, order, or money path changes.",
    "Same-byte report, manifest, contracts, registry, two run receipts, mutation receipt, reproducibility receipt, semantic projection, negative matrix, scope, architecture, and hash validation do not pass."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority",
    "fresh_owner_required": true,
    "assignment_id": "foundation_postgresql16_semantic_authority_owner"
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_postgresql16_semantic_authority_owner",
    "base_sha": "HEAD",
    "review_paths": [
      ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery"
    ],
    "exclude_paths": [
      "paper-trader/backend",
      "paper-trader/frontend",
      "paper-trader/docs/agent/CURRENT.md",
      "paper-trader/docs/agent/programme/PROGRAMME.json",
      "paper-trader/docs/agent/tasks",
      ".agent/review-package.json"
    ],
    "verdicts": [
      "POSTGRESQL16_SEMANTIC_AUTHORITY_EVIDENCE_ACCEPTABLE",
      "BLOCKED"
    ]
  },
  "deployment_impact": {
    "classification": "local disposable database evidence only",
    "highest_claim": "independently authenticated PostgreSQL 16 semantic authority receipt eligible for root acceptance",
    "deployable": false,
    "unchanged": [
      "product runtime",
      "schema",
      "migrations",
      "configuration",
      "dependencies",
      "services",
      "providers",
      "frontend",
      "infrastructure"
    ],
    "downstream": "fresh contract-core recovery architecture must consume a root-accepted exact receipt package before contract implementation, observer, obligations, mutation attestation, runtime correction, integration, numeric correction, transitive revalidation, and critical review can resume"
  },
  "nonclaims": [
    "This capsule accepts no prior diagnostic receipt or recovery architecture.",
    "It changes and accepts no product, test, migration, runtime, schema, configuration, dependency, service, provider, frontend, deployment, or production behavior.",
    "Local disposable PostgreSQL evidence proves no backup, restore, upgrade, release, capacity, operational, live, order, money, Phase 1-4 foundation, Phase 5, or Phase 6 readiness."
  ]
}
---

# PostgreSQL 16 semantic authority recovery

This capsule closes one evidence gap. It observes PostgreSQL 16 semantics from two fresh disposable reference databases through fixed structural catalog queries and a separately authenticated read-only observer. It produces an immutable authority package for later root acceptance. It does not repair or accept product code.
