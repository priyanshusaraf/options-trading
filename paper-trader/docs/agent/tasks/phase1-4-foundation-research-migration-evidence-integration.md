---
{
  "id": "phase1-4-foundation-research-migration-evidence-integration",
  "phase": "interphase-4-5",
  "status": "blocked_pending_runtime_acceptance",
  "provisional_contract": "This amended capsule is unaccepted and cannot activate until root accepts repeated-failure recovery node 2 runtime final bytes.",
  "goal": "Independently integrate the accepted native round-trip attestation and runtime, recompute every obligation, and prove the complete SQLite/PostgreSQL migration matrix, preservation, restart, refusal, and mutations from frozen product bytes.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only when every fixture has one provenance label; node 1 claim obligations are independently derived and match its exact collected nodes, logs, hashes, table/corpus/dialect/reopen receipts, catalog/data mutation registry, expected failure codes, and restorations; every supported state and refusal passes through process reopen; and product/projection/runtime bytes remain at accepted hashes."},
  "dependencies": ["root acceptance of phase1-4-foundation-research-migration-native-state-implementation", "root acceptance of phase1-4-foundation-research-migration-native-mutation-attestation", "root acceptance of phase1-4-foundation-research-migration-runtime-correction final bytes under foundation_research_migration_runtime_owner_2"],
  "risk_tags": ["critical", "research-migration", "adversarial-evidence", "sqlite-postgresql-parity", "research-integrity"],
  "required_docs": [
    {"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["14. Foundation migration and market-number correction contract"]},
    {"path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "sections": ["9. Foundation migration and numeric correction route"]},
    {"path": "paper-trader/docs/agent/DEFECT_PATTERNS.md", "sections": ["DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Foundation migration and numeric correction"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/tests/test_phase4_authority_research_migration.py",
    "paper-trader/backend/tests/test_phase4_adversarial_migration_matrix.py",
    "paper-trader/backend/tests/test_phase4_migration_fixture_provenance.py",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-evidence-integration.md",
    ".agent/runs/phase1-4-foundation-research-migration-evidence-integration"
  ],
  "read_only_paths": [
    "paper-trader/backend/research/domain",
    "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py",
    "paper-trader/backend/tests/foundation_postgresql_0010_builder.py",
    "paper-trader/backend/tests/test_foundation_research_projection_contracts.py",
    "paper-trader/backend/research_tests/test_foundation_research_migration_runtime.py",
    ".agent/runs/phase1-4-foundation-research-migration-projection-correction",
    ".agent/runs/phase1-4-foundation-research-migration-runtime-correction",
    "paper-trader/backend/app",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    ".agent/review-package.json"
  ],
  "fixture_taxonomy": ["EXACT_HISTORICAL_CATALOG_PROJECTION", "SYNTHETIC_CONTRACT_VALID_WITNESS", "CURRENT_HEAD", "HYBRID_FAULT_INJECTION", "RETIRED"],
  "tests": [
    "From paper-trader/backend: .venv/bin/python -m pytest -q tests/test_phase4_authority_research_migration.py tests/test_phase4_adversarial_migration_matrix.py tests/test_phase4_migration_fixture_provenance.py tests/test_foundation_research_projection_contracts.py research_tests/test_foundation_research_migration_runtime.py",
    "Run SQLite empty direct construction, exact 0010, all 31 nonempty five-guard repair subsets, exact 0011 no-op, interruption rollback, reopen, every unsupported marker, guard/catalog/data/sequence drift, downgrade, and repeated restart.",
    "Run disposable PostgreSQL 16 empty, exact 0010 and exact 0011 catalogs with at least two materially different contract-valid synthetic corpora under one catalog, 0003-0009 and drift refusal, transaction rollback, and process reopen.",
    "Independently derive node 1 obligations from its accepted contract, not from claim-attestation.json, then require exact equality for 24 tables, two corpora, two dialects, marker and sequence state, reopen receipts, every catalog class, DATA-01..DATA-24, every CAT mutation, expected failure codes, exact restorations, collected node IDs, logs, and final hashes.",
    "Compare tables, columns, constraints, indexes, functions, triggers, marker/cookie, row counts, PK/FK, sequences, attribution, classification, and exact text/JSON/binary bytes. Expected rows remain caller-derived and cannot use observed rows or inventory.",
    "Run protected/frozen hashes, accepted dependency hashes, scoped diff, taxonomy scan, manifest attestation, and git diff --check."
  ],
  "test_plan": ["Execute every command in tests with full output logged through run_logged.py.", "Bind each fixture to one provenance label and every matrix row to process-reopen evidence; synthetic witnesses receive no schema, historical, or user-fact authority.", "Independently recompute node 1 obligation sets and reject one-at-a-time removals of a table, corpus, dialect, reopen, catalog class, data mutation, catalog mutation, expected failure code, restoration, collected node, command, log hash, and final byte hash.", "Run direct guard test writes only in rollback-only savepoints or subtransactions and prove the complete preflight digest is byte-identical afterward.", "Inspect sequences without advancing them.", "Run and restore every mutation before final hashes."],
  "acceptance": ["Every fixture has exactly one taxonomy label; hybrid fixtures receive no historical credit and synthetic witnesses define no catalog or facts.", "The sole SQLite target cites its exact literal product authority and no unsupported historical projection exists.", "The full SQLite and PostgreSQL support/refusal matrix passes from frozen product bytes.", "SQLite storage class and affinity, textual JSON bytes, and BLOB bytes receive exact checks; PostgreSQL text/varchar JSON bytes receive exact checks while catalog-declared json/jsonb uses dialect-native representation rather than claimed original input text.", "Every preservation class and direct guard passes across reopen with no committed guard-probe writes.", "All mutations fail and exact dependency hashes restore."],
  "mutations": ["Relabel a current-head rewind as EXACT_HISTORICAL_CATALOG_PROJECTION or relabel synthetic witness values as historical facts; taxonomy gate must fail.", "Remove one supported 0010 guard; direct behavior and route classification must fail unless it is the exact enumerated repair state.", "Bypass 0011 certification; complete and defect-state tests must fail.", "Permit one arbitrary drift or unsupported SQLite or PostgreSQL marker; pre-write digest must fail.", "Change one row/key/sequence/owner/classification/stored byte; preservation must fail.", "Restore every mutated byte before final validation."],
  "failure_triggers": ["Any fixture lacks exactly one label.", "Hybrid evidence receives historical credit.", "Any frozen product or contract hash changes.", "Any supported state, refusal, process reopen, preservation class, or mutation is absent."],
  "stop_conditions": ["Any matrix row, provenance label, preservation check, or mutation remains implicit.", "Any product fix is required inside this evidence-only owner.", "Any mutation survives final validation."],
  "owner_gates": ["Stop if SQLite recovery, projection, or runtime root acceptance and exact hashes are absent.", "Route any product failure back to its completed owner; this capsule cannot patch product.", "Stop before review-package, production, dependency, configuration, provider, frontend, deployment, live, or money work."],
  "deployment_impact": {"classification": "evidence-only for migration-required change", "highest_claim": "integrated locally runnable migration matrix", "unchanged": ["product", "schema", "dependencies", "configuration", "services", "providers", "frontend", "deployment", "production", "live authority", "money authority"], "future_gates": ["numeric correction", "transitive revalidation", "independent critical review", "Phase 6 production rehearsal", "V1 exact-build release gate"]},
  "reviewer_prerequisites": ["root-accepted implementation recovery report, manifest, machine contracts, serial DAG, and frozen-byte dispositions", "root-accepted native-state report, manifest, source/builder hashes, and four complete baseline receipts", "root-accepted native-mutation report, manifest, claim attestation, and exact 96 DATA plus 78 CAT receipts", "root-accepted runtime report, manifest, runner and 0011 hashes", "root-accepted independent evidence-attestation report, manifest, full matrix and mutation logs", "accepted numeric correction", "transitive report and exact integrated hashes", "frozen audit and protected checks", "root-built .agent/review-package.json"],
  "model_route": {"owner": "gpt-5.6-terra", "owner_reasoning_effort": "medium", "service_tier": "priority", "fresh_owner_required": true},
  "parallel_budget": 0,
  "assignments": [],
  "review": {"required": false, "assignment_id": "foundation_research_migration_evidence_attestation_owner", "base_sha": "HEAD", "review_paths": ["paper-trader/backend/tests/test_phase4_authority_research_migration.py", "paper-trader/backend/tests/test_phase4_adversarial_migration_matrix.py", "paper-trader/backend/tests/test_phase4_migration_fixture_provenance.py", ".agent/runs/phase1-4-foundation-research-migration-evidence-integration"], "exclude_paths": ["paper-trader/backend/research/domain", "paper-trader/frontend"], "verdicts": ["INTEGRATION_ACCEPTABLE", "BLOCKED"]},
  "nonclaims": ["Integration acceptance does not make the audit current, accept numeric behavior, authorize the reviewer, prove release deployability, or authorize deployment."]
}
---

# Phase 1-4 foundation research migration evidence integration

This capsule owns existing migration fixtures and evidence only. Product,
contracts, builders, review package, programme state, and retained migration
bytes are frozen inputs.
