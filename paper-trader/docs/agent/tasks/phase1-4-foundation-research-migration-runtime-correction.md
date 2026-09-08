---
{
  "id": "phase1-4-foundation-research-migration-runtime-correction",
  "phase": "interphase-4-5",
  "status": "blocked_pending_native_mutation_attestation_acceptance",
  "provisional_contract": "This capsule cannot activate until root separately accepts the recovery architecture, native-state node, and native-mutation-attestation node in that strict order.",
  "goal": "Replace dynamic historical derivation with the accepted projection contracts, implement forward head 0011, exact restart, and pre-write PostgreSQL refusal without redefining authority.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only when the runner consumes accepted immutable catalog contracts while treating rows and sequences as parameterized state, reaches exact 0011 from every supported route without changing any pre-existing row, key, owner, classification, stored byte, or sequence state, refuses unsupported PostgreSQL markers and drift before writes, and proves declared SQLite restart and PostgreSQL rollback boundaries in the dedicated runtime suite."},
  "dependencies": ["root acceptance of phase1-4-foundation-research-migration-native-state-implementation exact final bytes and four baseline receipts", "root acceptance of phase1-4-foundation-research-migration-native-mutation-attestation exact final bytes, 174 mutation receipts, and claim-attestation.json"],
  "risk_tags": ["critical", "research-migration", "forward-repair", "sqlite-postgresql-parity", "research-integrity"],
  "required_docs": [
    {"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["14. Foundation migration and market-number correction contract"]},
    {"path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "sections": ["9. Foundation migration and numeric correction route"]},
    {"path": "paper-trader/docs/agent/DEFECT_PATTERNS.md", "sections": ["DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Foundation migration and numeric correction"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/research/domain/migrate.py",
    "paper-trader/backend/research/domain/migrations/0011_sqlite_catalog_guard.py",
    "paper-trader/backend/research/domain/migrations/__init__.py",
    "paper-trader/backend/research_tests/test_foundation_research_migration_runtime.py",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-runtime-correction.md",
    ".agent/runs/phase1-4-foundation-research-migration-runtime-correction"
  ],
  "read_only_paths": [
    "paper-trader/backend/research/domain/migrations/sqlite_catalog_contract.py",
    "paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py",
    "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py",
    "paper-trader/backend/tests/foundation_postgresql_0010_builder.py",
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
    "paper-trader/backend/tests/test_foundation_research_projection_contracts.py",
    "paper-trader/backend/tests/test_phase4_authority_research_migration.py",
    "paper-trader/backend/tests/test_phase4_adversarial_migration_matrix.py",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    ".agent/review-package.json"
  ],
  "implementation_contract": [
    "HEAD_VERSION becomes 0011 and every former ResearchBase.metadata historical helper is removed or made current-head-only.",
    "SQLite preflight precedence is marker shape, support route, guard state, catalog, data, then sequence. It accepts only empty direct construction, exact or enumerated-five-guard 0010, and exact 0011; every unsupported or drifted state refuses before writes.",
    "PostgreSQL validates marker, exact catalog and guards, contract-valid data, owner relations, and non-advancing sequence state before routing; 0003-0009, unknown marker, and drift refuse before writes.",
    "PostgreSQL empty, exact 0010, and exact 0011 use the projection-owned product contract without modification; the contract module's 0011 = 0010 + guard-only delta declaration is authority, the runtime migration is its consumer rather than a second authority, and stage work and marker share one transaction.",
    "0011 repairs the five logical guards using five SQLite names and the frozen two PostgreSQL function/trigger pairs.",
    "The runtime consumes the root-accepted native-state ExpectedNativeState, ObservedNativeState, exact 24-table registry, dialect adapters, marker and sequence obligations, plus the serial native-mutation ClaimAttestation as read-only inputs. It may not copy observed rows or inventory into expected state, weaken textual JSON or binary byte comparison, or omit a caller table."
  ],
  "tests": [
    "From paper-trader/backend: .venv/bin/python -m pytest -q research_tests/test_foundation_research_migration_runtime.py",
    "Run isolated disposable PostgreSQL 16 exact-0010 upgrade, exact-0011 no-op, 0003-0009 pre-write refusal, drift refusal, injected rollback, and process reopen with at least two materially different contract-valid synthetic corpora under the same catalog.",
    "Run SQLite empty direct construction, exact 0010, all 31 nonempty five-guard repair subsets, exact 0011 no-op, unsupported markers, invalid guard/data/sequence states, interruption rollback, and process reopen.",
    "Run the accepted node-1 contract consumer over every supported post-runtime state and require all 24 tables, both corpora, both dialects, exact markers/sequences, and fresh-process receipts without recreating node-1 expected state from observations.",
    "Run protected/frozen hashes, node-1 claim-attestation and final-byte hashes, scoped diff, source-map checks, JSON validation, and git diff --check."
  ],
  "test_plan": ["Execute every command in tests with full output logged through run_logged.py.", "Prove each route, refusal, restart boundary, and transaction boundary from accepted contracts.", "Run and restore every mutation before final hashes."],
  "acceptance": ["Runtime imports accepted catalog contracts and contains no dynamic historical or witness-derived authority.", "SQLite reaches 0011 only from declared exact states and validates storage class, affinity, textual JSON bytes, binary values, owner relations, and sqlite_sequence without advancing it.", "PostgreSQL 0003-0009 and drift refuse before writes; exact 0010 reaches 0011 transactionally while preserving declared text/varchar JSON bytes and dialect-native json/jsonb representation where the catalog declares those types.", "Direct guard test writes run only inside rollback-only savepoints or subtransactions, commit nothing, and leave the full preflight digest byte-identical.", "Every mutation fails and exact product bytes restore."],
  "mutations": ["Reintroduce one current-metadata historical helper; provenance test must fail.", "Allow one PostgreSQL 0003-0009 marker to write; pre-write digest must fail.", "Stamp 0011 before direct guard validation; restart test must fail.", "Bypass one repair-prefix refusal or rollback; runtime test must fail.", "Restore exact bytes before final validation."],
  "failure_triggers": ["Runtime needs a second projection authority.", "PostgreSQL runtime changes the accepted 0010 contract.", "An undeclared partial state resumes.", "A refusal mutates catalog, data, sequence, or marker."],
  "stop_conditions": ["Any route, marker transition, restart state, or refusal remains implicit.", "Any current-metadata historical helper remains.", "Any mutation survives final validation."],
  "owner_gates": ["Stop if the accepted recovery, native-state, or native-mutation reports, manifests, source hashes, receipts, claim attestation, or root acceptances are absent.", "Stop for root and user direction only on contrary released, deployed, production, supported-database, customer, or external-promise evidence for a removed SQLite or PostgreSQL state.", "Stop before destructive, production, dependency, configuration, service, frontend, deployment, live, or money work."],
  "deployment_impact": {"classification": "migration-required", "changes": ["research head 0011", "fail-closed SQLite and PostgreSQL support matrices", "SQLite restart validation"], "highest_claim": "focused locally runnable runtime", "unchanged": ["dependencies", "configuration", "services", "providers", "frontend", "execution schema", "production", "deployment", "live authority", "money authority"]},
  "model_route": {"owner": "gpt-5.6-terra", "owner_reasoning_effort": "medium", "service_tier": "priority", "fresh_owner_required": true},
  "parallel_budget": 0,
  "assignments": [],
  "review": {"required": false, "assignment_id": "foundation_research_migration_runtime_owner_2", "base_sha": "HEAD", "review_paths": ["paper-trader/backend/research/domain/migrate.py", "paper-trader/backend/research/domain/migrations/0011_sqlite_catalog_guard.py", "paper-trader/backend/research/domain/migrations/__init__.py", "paper-trader/backend/research_tests/test_foundation_research_migration_runtime.py", ".agent/runs/phase1-4-foundation-research-migration-runtime-correction"], "exclude_paths": ["paper-trader/backend/research/domain/migrations/sqlite_catalog_contract.py", "paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py", "paper-trader/frontend"], "verdicts": ["IMPLEMENTATION_ACCEPTABLE", "BLOCKED"]},
  "nonclaims": ["Focused runtime passes do not accept retained edits, the full matrix, release, or deployability."]
}
---

# Phase 1-4 foundation research migration runtime correction

This capsule owns migration routing and the forward repair only. Projection
contracts, builders, retained migrations, and integration fixtures are read-only.
