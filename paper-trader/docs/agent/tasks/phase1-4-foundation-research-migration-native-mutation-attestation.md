---
{
  "id": "phase1-4-foundation-research-migration-native-mutation-attestation",
  "phase": "interphase-4-5",
  "status": "blocked_pending_native_state_obligation_evidence_acceptance",
  "goal": "Execute every accepted DATA and CAT mutation through the root-accepted native-state oracle, prove effective committed fresh-process divergence and exact restoration, and seal one omission-sensitive aggregate ClaimAttestation.",
  "goal_contract": {
    "create_before_work": true,
    "durable_goal": "Execute and directly prove every sealed DATA and CAT mutation through the accepted contract, observer, and obligation boundaries, including effective distinct-process divergence, exact final-consumer rejection, restoration, and omission-sensitive aggregate attestation.",
    "stopping_condition": "Complete only when all 96 DATA and 78 CAT receipts exist at exact registry slots, each proves the named operation was effective, the committed mutated state survived close/dispose/fresh-process reopen, the exact rejection code came from the final native-state consumer, and another fresh-process reopen reproduced the baseline digest after exact restoration; ClaimAttestation must reject every one-at-a-time omission or substitution and seal exact accepted input and final output hashes. Return BLOCKED after the initial patch plus one evidence-backed repair of one material defect; do not begin a third patch."
  },
  "dependencies": [
    "root acceptance of phase1-4-foundation-research-migration-native-state-implementation-repeated-failure-recovery",
    "root acceptance of phase1-4-foundation-research-migration-native-state-contract-core report, manifest, source hashes, and exact final bytes",
    "root acceptance of phase1-4-foundation-research-migration-native-state-observer report, manifest, process receipts, source hashes, and exact final bytes",
    "root acceptance of phase1-4-foundation-research-migration-native-state-obligation-evidence report, manifest, 174 baseline receipts, 378 binding rejections, source hashes, and exact final bytes"
  ],
  "risk_tags": [
    "critical",
    "research-migration",
    "native-mutation-attestation",
    "sqlite-postgresql-parity",
    "omission-sensitive-evidence",
    "research-integrity"
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
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Foundation migration and numeric correction"
      ]
    }
  ],
  "immutable_input_gate": "Before editing, bind the root-accepted SHA-256 of both core modules, all observer and builder modules, the obligation registry, the projection suite, all 174 baseline receipts and 378 binding rejections, and all three predecessor manifests. Any mismatch returns BLOCKED to root; this owner cannot repair an accepted predecessor.",
  "allowed_paths": [
    "paper-trader/backend/tests/foundation_native_mutation_attestation.py",
    "paper-trader/backend/tests/test_foundation_research_projection_contracts.py",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-mutation-attestation.md",
    ".agent/runs/phase1-4-foundation-research-migration-native-mutation-attestation"
  ],
  "read_only_paths": [
    "paper-trader/backend/tests/foundation_native_state_contract.py",
    "paper-trader/backend/tests/foundation_native_state_declarations.py",
    "paper-trader/backend/tests/foundation_native_state_observer_protocol.py",
    "paper-trader/backend/tests/foundation_native_state_sqlite_observer.py",
    "paper-trader/backend/tests/foundation_native_state_postgresql_observer.py",
    "paper-trader/backend/tests/foundation_native_state_observer_child.py",
    "paper-trader/backend/tests/foundation_native_state_obligations.py",
    "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py",
    "paper-trader/backend/tests/foundation_postgresql_0010_builder.py",
    "paper-trader/backend/research/domain",
    "paper-trader/backend/research_tests",
    "paper-trader/backend/app",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    ".agent/review-package.json"
  ],
  "authority": {
    "registry": ".agent/runs/phase1-4-foundation-research-migration-native-state-implementation-repeated-failure-recovery/foundation_research_migration_native_state_implementation_repeated_failure_architect/obligation-to-code-matrix.json",
    "validator": "root-accepted phase1-4-foundation-research-migration-native-state-obligation-evidence manifest and exact registry tests",
    "mutation_api": "MutationOperation.execute(disposable_database, scenario, registry_entry) -> MutationCommitReceipt",
    "effective_receipt_api": "EffectiveMutationReceipt.from_reopens(registry_entry, pre, mutated, rejection) -> EffectiveMutationReceipt",
    "restoration_receipt_api": "RestorationReceipt.from_reopens(registry_entry, pre, restored) -> RestorationReceipt",
    "attestation_api": "ClaimAttestation.seal(registry, baseline_receipts, mutation_receipts, command_logs, final_byte_hashes) -> ClaimAttestation"
  },
  "receipt_contract": {
    "data": "24 identifiers x 2 corpora x 2 dialects = 96 unique receipts",
    "catalog": "16 SQLite identifiers x 2 corpora plus 23 PostgreSQL identifiers x 2 corpora = 78 unique receipts",
    "total": 174,
    "effective": "pre_digest != mutated_digest == reopened_mutated_digest; operation rowcount/object effect and exact final-consumer rejection code are separately recorded",
    "restored": "restored_digest == reopened_restored_digest == pre_digest after exact reverse mutation or disposable reconstruction",
    "forbidden_credit": ["statement failure", "rollback", "no-op", "setup failure", "guard disabled", "copied-object comparison", "same-process reread", "generic assertion", "selected slice"],
    "attestation": "Exact set equality for registry digest, 63 IDs, two corpora, two dialects, 24 tables, four baseline receipts, 174 mutation receipts, every reopen/restoration receipt, command log hash, accepted input hash, and final byte hash; no missing or extra slot is accepted."
  },
  "tests": [
    "Run DATA-01 through DATA-24 in each corpus and dialect. Every operation must succeed against a disposable database with guards enabled before rejection credit.",
    "Run CAT-SQLITE-01 through CAT-SQLITE-16 and CAT-PG-01 through CAT-PG-23 against each corpus using the exact accepted operation and final-consumer seam.",
    "For protected immutable data, reconstruct only the disposable database/schema from frozen declarations and caller corpus; never disable a guard or delete protected product data.",
    "Run the complete focused suite in SQLite and the repository disposable PostgreSQL 16 harness through run_logged.py.",
    "Mutate every registry and attestation dimension one at a time: ID, duplicate, corpus, dialect, table/fact class, operation, effectiveness, rejection code, reopen, restoration, receipt field, receipt slot, registry digest, command/log hash, accepted input hash, and final hash must fail.",
    "Run exact accepted-state hashes, protected/frozen hashes, scoped diff, compile, JSON validation, and git diff --check."
  ],
  "test_plan": [
    "Execute every command in tests with full output logged through run_logged.py.",
    "Run every exact DATA and CAT slot against both declared corpora and its assigned dialects, with committed fresh-process mutation and restoration receipts.",
    "Reject every one-at-a-time registry or attestation omission before sealing final hashes and the aggregate ClaimAttestation."
  ],
  "acceptance": [
    "Every registry entry has its exact executable operation, fact target, dialect, both corpora, effectiveness proof, fresh-process receipt, named rejection, restoration, and unique attestation slot.",
    "All 174 mutations are effective and rejected only by the final accepted native-state consumer after reopen.",
    "All restored states reproduce the exact pre-digest after a second reopen.",
    "The sealed ClaimAttestation and independent one-at-a-time omission tests pass from frozen accepted state bytes."
  ],
  "owner_gates": [
    "Stop if native-state root acceptance, accepted hashes, four baseline receipts, complete registry, or safe disposable PostgreSQL 16 harness is absent.",
    "Route any native-state/product defect to root; this capsule cannot patch its read-only dependency.",
    "Stop before schema, migration, runtime, dependency, configuration, service, provider, frontend, deployment, production, live, order, or money work."
  ],
  "stop_conditions": [
    "Any required DATA or CAT slot, corpus, dialect, effectiveness proof, reopen receipt, rejection code, restoration receipt, or final attestation field remains absent or implicit.",
    "Any receipt receives credit from statement failure, rollback, no-op, setup failure, a disabled guard, copied observation, same-process reread, generic assertion, or selected slice.",
    "The owner changes accepted native-state dependencies, starts runtime migration work, or begins a third patch after the one permitted repair."
  ],
  "model_route": {"owner": "gpt-5.6-terra", "owner_reasoning_effort": "medium", "service_tier": "priority", "fresh_owner_required": true, "assignment_id": "foundation_research_migration_native_mutation_attestation_owner"},
  "attempt_limit": 2,
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_research_migration_native_mutation_attestation_owner",
    "base_sha": "HEAD",
    "review_paths": [
      "paper-trader/backend/tests/foundation_native_mutation_attestation.py",
      "paper-trader/backend/tests/test_foundation_research_projection_contracts.py",
      ".agent/runs/phase1-4-foundation-research-migration-native-mutation-attestation"
    ],
    "exclude_paths": [
      "paper-trader/backend/tests/foundation_native_state_contract.py",
      "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py",
      "paper-trader/backend/tests/foundation_postgresql_0010_builder.py",
      "paper-trader/backend/research/domain",
      "paper-trader/backend/research_tests",
      "paper-trader/backend/app",
      "paper-trader/frontend"
    ],
    "verdicts": [
      "IMPLEMENTATION_ACCEPTABLE",
      "BLOCKED"
    ]
  },
  "deployment_impact": {"classification": "evidence-only for migration-required downstream change", "highest_claim": "focused locally executable native mutation attestation", "unchanged": ["product runtime", "schema", "migration", "dependencies", "configuration", "services", "providers", "frontend", "deployment", "production", "live authority", "money authority"]},
  "nonclaims": ["Mutation-attestation acceptance does not accept runtime migration, integration, numeric correction, deployability, release, production, live, order, or money claims."]
}
---

# Phase 1-4 foundation research migration native mutation attestation

This fresh serial owner consumes root-accepted native-state bytes without modifying
them. It owns complete DATA/CAT execution, effective reopen/restoration receipts,
and the aggregate claim attestation.
