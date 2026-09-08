---
{
  "id": "phase1-4-foundation-transitive-revalidation",
  "phase": "interphase-4-5",
  "status": "blocked",
  "provisional_contract": "This amended capsule is unaccepted and cannot activate until root accepts native-state, native-mutation attestation, runtime, evidence integration, and numeric correction in strict serial order.",
  "goal": "Freeze the integrated migration and numeric correction bytes, revalidate every audit-invalidated claim and mutation from those exact bytes, and build one precise current review package without patching product or tests.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "After the projection, runtime, evidence-integration, and numeric correction owners are separately root-accepted, the root coordinator may write only this capsule, its ignored evidence, and .agent/review-package.json. All product, tests, migrations, historical audit/review evidence, programme state, and CURRENT are read-only.",
    "stopping_condition": "Complete only when final product and test hashes are frozen; A-01 through A-05, DP-010, DP-011, every named FND/ADV/Phase 4 dependent selector, every critical mutation, package lineage, protected hash, deployment nonclaim, and scoped diff has exact current-byte evidence; and one review package names every input and exclusion. Route any product or test defect back to its owner and do not patch it here."
  },
  "risk_tags": [
    "critical",
    "transitive-evidence",
    "currentness",
    "review-package",
    "migration-numeric-integration"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": ["14. Foundation migration and market-number correction contract"]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": ["DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence", "DP-011 — Host-language numeric subtypes cross a typed market boundary"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-state-contract-recovery.md",
      "sections": ["Phase 1-4 foundation research migration state-contract recovery"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-projection-correction.md",
      "sections": ["Phase 1-4 foundation research migration projection correction"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-runtime-correction.md",
      "sections": ["Phase 1-4 foundation research migration runtime correction"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-evidence-integration.md",
      "sections": ["Phase 1-4 foundation research migration evidence integration"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-numeric-ingress-correction.md",
      "sections": ["Phase 1-4 foundation numeric ingress correction"]
    }
  ],
  "dependency_gate": "root acceptance of native-state final bytes and four baseline receipts, native-mutation final bytes and 174-receipt attestation, runtime final bytes, independent evidence integration, then numeric-ingress-correction",
  "audit_binding": {
    "report_sha256": "cec0bdc931632b9297d733fa58f6057a60b32820882af5e90b3184fd88d54d6d",
    "manifest_sha256": "4933505aa93b9a9fc03a08617b933944c28a409269602f53d9060d563f2143c5",
    "findings": ["A-01", "A-02", "A-03", "A-04", "A-05"]
  },
  "allowed_paths": [
    ".agent/review-package.json",
    ".agent/runs/phase1-4-foundation-transitive-revalidation",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-transitive-revalidation.md"
  ],
  "read_only_paths": [
    "paper-trader/backend",
    "paper-trader/frontend",
    ".agent/runs/phase1-4-foundation-audit",
    ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery",
    ".agent/runs/phase1-4-foundation-research-migration-projection-correction",
    ".agent/runs/phase1-4-foundation-research-migration-runtime-correction",
    ".agent/runs/phase1-4-foundation-research-migration-evidence-integration",
    ".agent/runs/phase1-4-foundation-numeric-ingress-correction",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md"
  ],
  "invalidation_matrix": [
    "A-01: FND-05 upgraded-row reconstruction, FND-06 migration integrity, FND-10 manifest persistence, FND-11 upgraded research dependency authority, FND-12 manifest/graph lineage, ADV-015 actual-old migration, Phase 4 final-review-5 migration portion, Phase 5 prerequisite, and deployability nonclaim.",
    "A-02: FND-09 raw numeric validity, FND-08 hostile-value causality, FND-12 dataset identity, ADV-010 hostile numeric breadth, Phase 4 numeric-validity raw ingress, and Phase 5 prerequisite.",
    "A-03: every unsupported SQLite unversioned or 0001 through 0009 claim, every unsupported PostgreSQL 16 marker 0003 through 0009 claim, and every cross-dialect or production-upgrade inference.",
    "A-04: retained migration fixture provenance, stale head assertions, grouped suite claims, and any evidence that did not distinguish exact historical, current head, hybrid, and retired fixtures.",
    "A-05: SQLite version-plus-cookie and PostgreSQL version-only marker parity, exact-head trust, interruption/restart, stale marker, and drift claims."
  ],
  "acceptance": [
    "Record SHA-256 for every changed product, test, migration, capsule, defect, design, plan, and deployability input before running integrated evidence; any later byte change invalidates the package.",
    "Rerun the exact supported migration matrix and numeric ingress matrix from the separately accepted projection, runtime, evidence-integration, and numeric owner evidence, including fresh processes, exact catalog projections, both materially distinct non-authoritative synthetic corpora per dialect, caller-derived expected values for all 24 tables, exact marker and sequence values, rollback-only direct SQL guard probes, non-advancing sequence inspection, valid-input golden identity, and all killed/restored data and catalog mutations.",
    "Prove the complete upgraded research owner/plan/dataset/assessment/truth/policy/manifest/graph chain reloads after process death and reaches the existing terminal consumer refusal without inferred authority.",
    "Prove boolean observations cannot mint dataset, cache, computation, signal, sizing, or execution-price facts while valid finite paths remain byte-identical.",
    "Attribute ADV-015 and ADV-010 cases separately; do not reuse historical FULL labels as current evidence.",
    "Run all affected focused selectors and only the bounded integration selectors named in owner reports; record command, exit, duration, environment, exact hashes, and full log path.",
    "Recompute protected files, audit freeze, migration and numeric source maps, capsule JSON/frontmatter, repository architecture, import direction, scoped diff, and git diff --check.",
    "Build one .agent/review-package.json that binds the audit, SQLite recovery package, repeated-failure recovery report/manifest/machine contracts, node 1 table/corpus/dialect/reopen/catalog/data mutation receipts and claim attestation, node 2 runtime, node 3 independent attestation, numeric owner reports/manifests, integrated logs, frozen final hashes, exclusions, nonclaims, and exact reviewer capsule."
  ],
  "required_selectors": [
    "research_tests/test_ir_v2_research_migration.py",
    "tests/test_phase4_authority_research_migration.py",
    "tests/test_phase4_adversarial_migration_matrix.py",
    "tests/test_foundation_research_migration_matrix.py",
    "tests/test_candle_validation.py",
    "tests/test_dataset_store.py",
    "tests/test_phase4_cache_identity.py",
    "tests/test_phase4_alignment_causality.py",
    "tests/test_handwritten_strategy_causality.py",
    "tests/test_foundation_numeric_ingress.py",
    "the exact consumer-containment selector named by the numeric owner report"
  ],
  "package_contract": {
    "base": "the final integrated current tree, never the pre-correction audit tree",
    "required_inputs": ["immutable audit hashes", "SQLite history-authority recovery report, manifest, ledger, source closure, and matrix", "repeated-failure recovery report, manifest, failure lineage, native round-trip contract, mutation matrix, and serial DAG", "node 1 projection owner report, manifest, machine claim attestation, exact 24-table and two-corpus/two-dialect receipts", "node 2 runtime owner report and manifest", "node 3 evidence-attestation owner report and manifest", "numeric owner report and manifest", "integrated command logs", "data and catalog mutation kill and restoration hashes", "protected hashes", "scoped diff", "deployment nonclaims"],
    "excluded_claims": ["foundation acceptance", "release deployability", "production rehearsal", "deployment", "runtime enablement", "live authority", "money authority"]
  },
  "failure_routing": [
    "Catalog, builder, caller-native oracle, or node-1 attestation failure returns to foundation_research_migration_native_round_trip_owner through root; runner or 0011 failure returns to foundation_research_migration_runtime_owner_2; fixture or independent-attestation failure returns to foundation_research_migration_evidence_attestation_owner. Never resume either blocked prior projection owner.",
    "Numeric product or numeric-test failure returns to phase1-4-foundation-numeric-ingress-correction through a bounded correction turn.",
    "Package or evidence-only defect stays with this capsule. Do not edit product or tests.",
    "A changed protected file, audit hash, unsupported PostgreSQL prefix, valid identity change, or owner-gate scope need stops for owner disposition."
  ],
  "test_plan": [
    "Verify final hashes, then rerun the bounded migration and numeric selectors and mutations named by all four accepted correction owner reports.",
    "Reconstruct the exact upgraded authority chain after process death and exercise the hostile numeric containment lifecycle.",
    "Validate audit/protected hashes, capsule frontmatter, architecture, import direction, scoped diff, deployment nonclaims, and package completeness."
  ],
  "owner_gates": [
    "Stop on any final product or test byte change after freeze; route it to the owning correction.",
    "Stop on support narrowing, identity change, protected/audit hash drift, production access, deployment, live, or money scope."
  ],
  "stop_conditions": [
    "Any invalidated claim, supported prefix, critical mutation, final hash, or evidence path is missing or ambiguous.",
    "The package cites historical evidence as current without a final-byte rerun or contains an unsupported deployment or foundation claim.",
    "The evidence-only owner would need to patch product or tests."
  ],
  "nonclaims": [
    "EVIDENCE_CURRENT means only that the bounded correction package matches final bytes; it is not the independent critical verdict.",
    "This capsule grants no foundation, Phase 5, release, deployment, runtime, live, or money acceptance."
  ],
  "deployment_impact": {
    "classification": "evidence-only for a migration-required correction",
    "highest_claim": "integrated locally_runnable evidence and package-ready currentness",
    "open": ["production-shaped clean install and upgrade", "backup and clean restore", "configuration and role preflight", "three-plane health", "rollout/rollback", "exact-build post-upgrade smoke"]
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_transitive_revalidation_owner_2",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      ".agent/review-package.json",
      ".agent/runs/phase1-4-foundation-migration-numeric-architecture-correction",
      ".agent/runs/phase1-4-foundation-research-migration-state-contract-recovery",
      ".agent/runs/phase1-4-foundation-research-migration-projection-correction",
      ".agent/runs/phase1-4-foundation-research-migration-runtime-correction",
      ".agent/runs/phase1-4-foundation-research-migration-evidence-integration",
      ".agent/runs/phase1-4-foundation-numeric-ingress-correction",
      ".agent/runs/phase1-4-foundation-transitive-revalidation",
      "paper-trader/backend/research/domain",
      "paper-trader/backend/app/market_data/candles.py",
      "paper-trader/backend/app/backtest",
      "paper-trader/backend/research_tests",
      "paper-trader/backend/tests"
    ],
    "exclude_paths": ["paper-trader/frontend", "paper-trader/backend/app/engine", "paper-trader/backend/app/providers"],
    "output": ".agent/runs/phase1-4-foundation-transitive-revalidation/owner/report.md",
    "verdicts": ["EVIDENCE_CURRENT", "BLOCKED"]
  }
}
---

# Phase 1-4 foundation transitive revalidation

This evidence-only capsule makes no historical result current by assertion. It
binds every rerun to the final integrated bytes and routes product failures back
to their owning correction.
