---
{
  "id": "phase1-4-foundation-research-migration-native-state-obligation-evidence",
  "phase": "interphase-4-5",
  "status": "blocked",
  "goal": "Implement and execute the exact immutable registry for all 24 DATA and 39 CAT native-state obligations against the root-accepted core and observers.",
  "risk_tags": ["critical", "research-migration", "native-state-obligations", "false-green-evidence", "sqlite-postgresql-parity", "research-integrity"],
  "required_docs": [
    {"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["14. Foundation migration and market-number correction contract"]},
    {"path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "sections": ["9. Foundation migration and numeric correction route"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Foundation migration and numeric correction", "Foundation blockers", "Phase 4 ownership"]},
    {"path": "paper-trader/docs/agent/DEFECT_PATTERNS.md", "sections": ["DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"]}
  ],
  "goal_contract": {
    "create_before_product_work": true,
    "durable_goal": "Implement every sealed DATA and CAT spec and typed consumer, execute 174 fact-specific baseline invocations, prove all 378 isolated binding rejections, and aggregate only exact typed receipts into ClaimAttestation.",
    "stopping_condition": "Complete only when the reference-registry and every reference/projection hash match, the 24 DATA and 39 CAT enums and immutable registries are exact bijections, all 174 executions emit nonempty fact-specific ObligationReceipt values, all 378 isolated binding mutations reject, catalog consumers use projection-selected independent facts rather than aggregate catalog digests, and root reruns the exact SQLite and disposable PostgreSQL 16 evidence.",
    "attempt_limit": "one initial patch plus at most one repair"
  },
  "dependency_gate": "root-accepted-native-state-observer-exact-bytes",
  "dispatch_contract": "Root dispatch must bind this capsule SHA-256, accepted core and observer reports/manifests/file hashes, sealed recovery contract hashes, predecessor acceptance hash, HEAD, reference-registry hash, and frozen/protected hashes before activation.",
  "owner": {
    "assignment_id": "foundation_native_state_obligation_evidence_owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "fresh_owner_required": true,
    "children": 0,
    "parallel_budget": 0
  },
  "model_route": {"owner": "gpt-5.6-terra", "owner_reasoning_effort": "medium", "service_tier": "priority", "fresh_owner_required": true, "assignment_id": "foundation_native_state_obligation_evidence_owner"},
  "parallel_budget": 0,
  "assignments": [],
  "write_ownership": [
    "paper-trader/backend/tests/foundation_native_state_obligations.py",
    "paper-trader/backend/tests/test_foundation_native_state_obligations.py",
    "paper-trader/backend/tests/test_foundation_research_projection_contracts.py"
  ],
  "allowed_paths": [
    "paper-trader/backend/tests/foundation_native_state_obligations.py",
    "paper-trader/backend/tests/test_foundation_native_state_obligations.py",
    "paper-trader/backend/tests/test_foundation_research_projection_contracts.py",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-state-obligation-evidence.md",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-obligation-evidence"
  ],
  "read_only_dependencies": [
    "paper-trader/backend/tests/foundation_native_state_contract.py",
    "paper-trader/backend/tests/foundation_native_state_declarations.py",
    "paper-trader/backend/tests/foundation_native_state_observer_protocol.py",
    "paper-trader/backend/tests/foundation_native_state_sqlite_observer.py",
    "paper-trader/backend/tests/foundation_native_state_postgresql_observer.py",
    "paper-trader/backend/tests/foundation_native_state_observer_child.py",
    "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py",
    "paper-trader/backend/tests/foundation_postgresql_0010_builder.py",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-implementation-repeated-failure-recovery"
  ],
  "required_implementation": {
    "registry": "MappingProxyType over exact DataObligation and CatalogObligation enums; duplicate, missing, extra, dead, or spec/projection mismatch rejects at import",
    "data": "24 exact entries and typed consumers from obligation-to-code-matrix.json, each invoked for two corpora and two dialects, producing 96 receipts",
    "catalog": "39 exact entries and typed consumers from obligation-to-code-matrix.json, each invoked for two corpora in its accepted dialect, producing 78 receipts",
    "binding_rejections": "126 omission/dead + 96 DATA wrong binding + 156 CAT wrong binding = 378 isolated rejections",
    "claim": "ClaimAttestation validates exact receipt identities, scenarios, dialects, consumer names, input digests, fact-specific observed digests, rejection codes, and executed=true",
    "forbidden": ["builder changes", "observer changes", "core changes", "mutable registry", "identifier constants without calls", "aggregate catalog digest as CAT credit", "static token coverage", "mutation-attestation credit", "product runtime"]
  },
  "test_plan": [
    "test_native_state_exact_reference_registry_and_projection_hashes",
    "test_native_state_typed_coverage_executes_174_fact_specific_consumers",
    "test_each_coverage_omission_and_dead_consumer_rejects",
    "test_each_catalog_wrong_fact_class_target_dialect_rejection_binding_rejects",
    "test_each_data_wrong_table_fact_class_dialects_rejection_code_binding_rejects",
    "Run SQLite directly and PostgreSQL only through paper-trader/backend/scripts/run_disposable_postgres.py; retain complete typed receipts and outputs under ignored .agent/runs through run_logged.py.",
    "Root independently validates the complete obligation map, all receipt cardinalities, all rejection cardinalities, the three-file write-set diff, and frozen/protected hashes."
  ],
  "acceptance": ["The immutable registry is an exact 24-DATA and 39-CAT bijection to the sealed machine map.", "All 174 fact-specific consumers execute and all 378 isolated binding mutations reject.", "Root validates exact scope, hashes, receipts, and same-byte two-dialect evidence before successor dispatch."],
  "root_acceptance_gate": "Root must accept the exact obligation report, evidence manifest, three written file hashes, registry/spec/projection hashes, 174 typed receipts, 378 isolated rejection receipts, two-dialect logs, scope validation, and frozen/protected hash attestation before native-mutation attestation may activate.",
  "deployment_impact": {
    "classification": "test-evidence implementation only; migration-required downstream",
    "highest_claim": "local native-state obligation execution evidence",
    "deployable": false,
    "downstream": "native mutation, runtime correction, integrated evidence, numeric correction, transitive revalidation, and critical review remain blocked"
  },
  "owner_gates": ["Stop if any of 63 identities or hashes differs from obligation-to-code-matrix.json.", "Stop if any obligation lacks a fact-specific independent observed slice.", "Stop before editing accepted core/observer bytes or any path outside write_ownership.", "Stop after the second failed attempt and return exact blocker evidence to root."],
  "stop_conditions": ["Any DATA or CAT identity, authority, consumer, receipt, test, rejection, or owner remains implicit.", "Coverage comes from tokens, aggregate digests, or uncalled consumers.", "The owner edits an accepted dependency or begins a third attempt."],
  "review": {"required": false, "assignment_id": "foundation_native_state_obligation_evidence_owner", "base_sha": "HEAD", "review_paths": ["paper-trader/backend/tests/foundation_native_state_obligations.py", "paper-trader/backend/tests/test_foundation_native_state_obligations.py", "paper-trader/backend/tests/test_foundation_research_projection_contracts.py", ".agent/runs/phase1-4-foundation-research-migration-native-state-obligation-evidence"], "exclude_paths": ["paper-trader/backend/tests/foundation_native_state_contract.py", "paper-trader/backend/tests/foundation_native_state_declarations.py", "paper-trader/backend/tests/foundation_native_state_observer_protocol.py", "paper-trader/backend/tests/foundation_native_state_sqlite_observer.py", "paper-trader/backend/tests/foundation_native_state_postgresql_observer.py", "paper-trader/backend/tests/foundation_native_state_observer_child.py", "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py", "paper-trader/backend/tests/foundation_postgresql_0010_builder.py", "paper-trader/backend/research", "paper-trader/backend/app", "paper-trader/frontend"], "verdicts": ["IMPLEMENTATION_ACCEPTABLE", "BLOCKED"]},
  "nonclaims": ["No DATA/CAT mutation attestation, migration, runtime, supported-old fixture, deployability, release, production, live, order, money, foundation, or phase acceptance follows from this slice."]
}
---

# Native-state obligation evidence

This third serial slice binds every accepted identity to executable typed evidence. It cannot repair core or observer code.
