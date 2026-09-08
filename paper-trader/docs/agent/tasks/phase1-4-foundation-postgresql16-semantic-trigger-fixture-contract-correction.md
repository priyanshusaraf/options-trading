---
{
  "id": "phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction",
  "phase": "interphase-4-5",
  "status": "blocked",
  "goal": "Correct the database-free trigger-fixture materialization harness, reproduce the accepted source-closed fixture package from an explicit immutable input manifest, and independently validate every generated binding without opening PostgreSQL or changing product, test, migration, runtime, or predecessor bytes.",
  "goal_contract": {
    "create_before_work": true,
    "durable_goal_count": 1,
    "stopping_condition": "Complete only when one explicit immutable input manifest reproduces all eight source-derived fixture graphs, the accepted finite lineage, every legal absent-trigger UPDATE and DELETE witness, exact PQ command bindings, independently derived mutation counts, every isolated rejection and restoration record, report, manifest, scope proof, and final same-byte hashes. Otherwise return BLOCKED."
  },
  "dependency_gate": "BLOCKED_UNTIL_ROOT_ACCEPTS_THE_PRIOR_OWNER_BLOCKER_AND_ACTIVATES_THIS_EXACT_CAPSULE_HASH",
  "dispatch_contract": "Root dispatch binds this capsule SHA-256, the prior blocked-owner acceptance SHA-256, the accepted fixture-consumer recovery SHA-256, the failed-owner capsule and dispatch hashes, the decisive blocker evidence hashes, HEAD, CURRENT, PROGRAMME, frozen PostgreSQL 0010 source, and protected hashes.",
  "root_blocker_acceptance_gate": {
    "path": ".agent/runs/phase1-4-foundation-critical-closure/postgresql16-semantic-trigger-fixture-contract-owner-blocked-acceptance.json",
    "ownership": "root-only outside successor allowed_paths",
    "hash_authority": "exact SHA-256 supplied by root dispatch and consumed read-only"
  },
  "ownership_contract": {
    "owns": "fresh database-free materialization, independent validation, and evidence sealing of source-derived fixture facts and exact source-derived protocol command values",
    "forbids": "generic PQ API, wire, parser, digest, migration, product, runtime, semantic-package, PostgreSQL, root-acceptance, and successor authority"
  },
  "required_docs": [],
  "risk_tags": ["critical", "postgresql", "trigger-fixture", "research-integrity", "false-green-evidence", "bounded-correction"],
  "allowed_paths": [
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction"
  ],
  "read_only_paths": [
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/docs/agent",
    ".agent/review-package.json",
    ".agent/runs/phase1-4-foundation-critical-closure",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-recovery",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-fixture-consumer-repeated-failure-recovery"
  ],
  "required_outputs": [
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction/foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner/materialization-input-manifest.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction/foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner/fixture-package.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction/foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner/independent-fixture-validator.py",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction/foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner/negative-mutation-registry.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction/foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner/mutation-execution-records.jsonl",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction/foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner/mutation-execution-receipt.json",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction/foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner/database-free-validation.log",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction/foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner/report.md",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction/foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner/evidence-manifest.json"
  ],
  "materialization_contract": {
    "dedicated_output_root": ".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction/foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner",
    "input_rule": "Before generation, write and independently validate one closed manifest containing every predecessor path, SHA-256, semantic role, declared lineage record, frozen source, capsule, acceptance, dispatch, and protected input. Read no undeclared filesystem artifact and reject any ambient file that changes materialization.",
    "lineage_rule": "The accepted recovery failure-lineage.json is the sole lineage authority. Reproduce its local_false_starts list exactly, including the one retained inspect-frozen-contract-rerun-2.log record, rather than discovering false starts from the destination directory.",
    "count_rule": "Derive source-authority, provenance-leaf, leaf-mutation, ordering-mutation, binding-mutation, and total execution counts from generated bytes only after the complete input manifest matches. Then reconcile the derived values with the accepted recovery contract; do not use a hand-entered minimum or ambient prior count.",
    "path_rule": "Every generated executable resolves its artifact root from its own exact file location or a manifest-bound explicit argument. Preflight every referenced file before the producer, validator, or mutation driver runs.",
    "interpreter_rule": "Bind the actual interpreter executable and version in the input manifest. Reject unsupported syntax or runtime features before materialization; do not rely on zip(strict=True) where the bound interpreter does not support it."
  },
  "source_authority": {
    "accepted_recovery": ".agent/runs/phase1-4-foundation-critical-closure/postgresql16-semantic-authority-fixture-consumer-recovery-acceptance.json",
    "accepted_failure_lineage": ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-fixture-consumer-repeated-failure-recovery/foundation_postgresql16_semantic_fixture_consumer_recovery_architect/failure-lineage.json",
    "accepted_ddl_closure": ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-fixture-consumer-repeated-failure-recovery/foundation_postgresql16_semantic_fixture_consumer_recovery_architect/ddl-source-closure.json",
    "accepted_fixture_authority": ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-fixture-consumer-repeated-failure-recovery/foundation_postgresql16_semantic_fixture_consumer_recovery_architect/trigger-fixture-authority.json",
    "failed_owner_disposition": "diagnostic-only; no generated package, validator result, mutation count, or seal from the failed owner is accepted"
  },
  "execution_boundary": {
    "initial_attempts": 1,
    "bounded_repairs": 1,
    "repair_rule": "At most one repair may follow the initial database-free execution. If the repaired execution retains the same material defect, or exposes any second material defect requiring another edit, stop immediately and return BLOCKED. Do not start a third implementation patch.",
    "parallel_budget": 0,
    "children": 0,
    "postgresql_allowed": false
  },
  "tests": [
    "Validate the closed materialization-input manifest, actual interpreter identity, every declared predecessor hash, and exact accepted failure-lineage bytes before generation.",
    "Generate into the dedicated empty logical output root and prove an undeclared ambient file cannot alter lineage, package, provenance, registry, receipt, or count bytes.",
    "Re-derive all 67 source statements and all eight target, function, and installer triples from the frozen literal without importing or executing migration code.",
    "Validate declaration-order columns, native types, null and default rules, PK, unique, FK, checks, source hashes, dependency order, distinct support keys, projections, literal predicates, legal updates, legal deletes, exact SQLSTATE and message, equality, and cleanup for every fixture.",
    "Derive and execute one isolated negative mutation for every concrete fixture leaf, ordering edge, source binding, constraint witness, legal-absent-trigger assertion, PQ binding, and cleanup edge; persist exact caught and restoration records.",
    "Use a separately implemented independent validator that resolves only its manifest-bound output root. No PostgreSQL, database driver connection, selected projection test, producer expectation, prior pass count, or observed row receives evidence credit.",
    "Run scope, git diff --check, frozen and protected hashes, manifest attestation, repository architecture validation, and final same-byte validation."
  ],
  "test_plan": [
    "Freeze and independently validate the exact materialization inputs, interpreter, lineage, output root, and predecessor hashes before executing any copied producer or validator.",
    "Materialize all source-derived fixture and protocol artifacts in the dedicated correction directory, then run the separate validator and exhaustive mutation driver from paths anchored to that directory.",
    "Independently derive all counts, reconcile them to the accepted recovery only after the full manifest matches, prove ambient-file independence and exact restoration, and seal report and manifest on unchanged bytes.",
    "Stop for root same-byte acceptance; do not open PostgreSQL or activate the semantic-package capsule."
  ],
  "acceptance": [
    "All eight database-free fixture graphs pass exhaustive independent consumption and exact mutation rejection from one closed input manifest.",
    "The accepted lineage is reproduced exactly and ambient prior evidence cannot change any authority, provenance, package, registry, receipt, or count byte.",
    "Target deletes have no incoming fixture references, target support keys are distinct, and link UPDATE reaches a second valid segment parent.",
    "Root accepts the report, manifest, outputs, logs, source and protected hashes, and this capsule's completed bytes before the semantic-package successor can be dispatched."
  ],
  "owner_gates": [
    "Stop on any predecessor, source, protected, CURRENT, PROGRAMME, HEAD, dispatch, blocker-acceptance, or capsule hash mismatch.",
    "Stop if a fixture fact requires observed-state inference or invention, if an undeclared file affects materialization, or if an unrelated refusal could receive trigger credit.",
    "Return to root for exact same-byte acceptance; do not activate the semantic-package capsule."
  ],
  "stop_conditions": [
    "Any PostgreSQL, server, database, product, test, migration, runtime, dependency, provider, frontend, deployment, production, live, order, or money action is proposed.",
    "Any hand-entered minimum mutation count, generic source binding, ambient lineage discovery, destination-relative path escape, or non-distinct delete target remains.",
    "The sole bounded repair fails or any further material repair would be needed."
  ],
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority",
    "fresh_owner_required": true,
    "assignment_id": "foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner"
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_postgresql16_semantic_trigger_fixture_contract_correction_owner",
    "base_sha": "HEAD",
    "review_paths": [".agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-correction"],
    "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/docs/agent", ".agent/review-package.json"],
    "verdicts": ["TRIGGER_FIXTURE_CONTRACT_CORRECTION_ACCEPTABLE", "BLOCKED"]
  },
  "deployment_impact": {
    "classification": "database-free evidence-contract correction only",
    "highest_claim": "local deterministic fixture materialization and constructibility",
    "deployable": false,
    "unchanged": ["product", "tests", "migrations", "runtime", "configuration", "dependencies", "services", "providers", "frontend", "infrastructure"]
  },
  "nonclaims": [
    "No PostgreSQL behavior, semantic fact, real semantic package, DATA or CAT obligation, migration behavior, foundation acceptance, deployability, release, production, live, order, or money claim follows.",
    "This capsule cannot activate its successor or authorize a PostgreSQL command.",
    "The failed owner's generated outputs remain unaccepted diagnostics; only exact source-derived facts regenerated and independently validated under this capsule may be proposed for root acceptance."
  ]
}
---

# PostgreSQL 16 semantic trigger-fixture contract correction

This blocked serial correction owns only deterministic database-free regeneration and independent validation of the eight accepted source-derived fixture graphs. Root acceptance of the prior owner's blocked result and this exact capsule is its only activation route.
