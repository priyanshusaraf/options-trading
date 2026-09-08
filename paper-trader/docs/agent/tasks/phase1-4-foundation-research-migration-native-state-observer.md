---
{
  "id": "phase1-4-foundation-research-migration-native-state-observer",
  "phase": "interphase-4-5",
  "status": "blocked",
  "goal": "Implement the fresh-process SQLite and PostgreSQL 16 native-state observers and full-PK builders against the root-accepted immutable core.",
  "risk_tags": ["critical", "research-migration", "native-state-observer", "sqlite-postgresql-parity", "process-isolation", "research-integrity"],
  "required_docs": [
    {"path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md", "sections": ["14. Foundation migration and market-number correction contract"]},
    {"path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md", "sections": ["9. Foundation migration and numeric correction route"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Foundation migration and numeric correction", "Foundation blockers", "Phase 4 ownership"]},
    {"path": "paper-trader/docs/agent/DEFECT_PATTERNS.md", "sections": ["DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"]}
  ],
  "goal_contract": {
    "create_before_product_work": true,
    "durable_goal": "Implement and directly prove the sealed JSON exec boundary, independent dialect observations, declared full-primary-key row ordering, owner resolution, native scalar verification, catalog facts, sequence states and bindings, and all process/owner/sequence/catalog rejection seams.",
    "stopping_condition": "Complete only when both dialects produce distinct ObservedNativeState values in fresh child interpreters, every FreshProcessReceipt field validates, expected values and digests never cross the request, full-PK and paired SQLite typeof ordering is exact, owner policies resolve or reject exactly, SQLite exposes only seq, PostgreSQL exposes last_value and is_called without advancing a sequence, and the exact observer tests pass on ignored SQLite and repository disposable PostgreSQL 16.",
    "attempt_limit": "one initial patch plus at most one repair"
  },
  "dependency_gate": "root-accepted-native-state-contract-core-exact-bytes",
  "dispatch_contract": "Root dispatch must bind this capsule SHA-256, root-accepted core report/manifest and file hashes, sealed recovery contract hashes, predecessor acceptance hash, HEAD, and frozen/protected hashes before activation.",
  "owner": {
    "assignment_id": "foundation_native_state_observer_owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "fresh_owner_required": true,
    "children": 0,
    "parallel_budget": 0
  },
  "model_route": {"owner": "gpt-5.6-terra", "owner_reasoning_effort": "medium", "service_tier": "priority", "fresh_owner_required": true, "assignment_id": "foundation_native_state_observer_owner"},
  "parallel_budget": 0,
  "assignments": [],
  "write_ownership": [
    "paper-trader/backend/tests/foundation_native_state_observer_protocol.py",
    "paper-trader/backend/tests/foundation_native_state_sqlite_observer.py",
    "paper-trader/backend/tests/foundation_native_state_postgresql_observer.py",
    "paper-trader/backend/tests/foundation_native_state_observer_child.py",
    "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py",
    "paper-trader/backend/tests/foundation_postgresql_0010_builder.py",
    "paper-trader/backend/tests/test_foundation_native_state_observer.py"
  ],
  "allowed_paths": [
    "paper-trader/backend/tests/foundation_native_state_observer_protocol.py",
    "paper-trader/backend/tests/foundation_native_state_sqlite_observer.py",
    "paper-trader/backend/tests/foundation_native_state_postgresql_observer.py",
    "paper-trader/backend/tests/foundation_native_state_observer_child.py",
    "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py",
    "paper-trader/backend/tests/foundation_postgresql_0010_builder.py",
    "paper-trader/backend/tests/test_foundation_native_state_observer.py",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-research-migration-native-state-observer.md",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-observer"
  ],
  "read_only_dependencies": [
    "paper-trader/backend/tests/foundation_native_state_contract.py",
    "paper-trader/backend/tests/foundation_native_state_declarations.py",
    "paper-trader/backend/research/domain/migrations/sqlite_catalog_contract.py",
    "paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py",
    "paper-trader/backend/scripts/run_disposable_postgres.py",
    ".agent/runs/phase1-4-foundation-research-migration-native-state-implementation-repeated-failure-recovery"
  ],
  "required_implementation": {
    "apis": ["observe_fresh(request, locator_lease)", "observe_sqlite_child(plan, locator)", "observe_postgresql16_child(plan, locator)", "foundation_native_state_observer_child.main"],
    "transport": "strict JSON files across subprocess exec using the same repository virtualenv interpreter",
    "ordering": "all tables by exact declaration-owned full primary-key tuple; SQLite rows and typeof vectors remain paired",
    "owner_resolution": "exact direct, classified outbox, declared join, and explicit ownerless policies from authority-map.json",
    "sequence_rules": "SQLite {name,seq} plus separate AUTOINCREMENT binding; PostgreSQL {name,last_value,is_called} plus pg_get_serial_sequence binding and object owner",
    "forbidden": ["expected constructors", "expected values or digests in request", "same-process reconnect", "pickle", "mutable adapter registry", "ORDER BY rowid", "ORDER BY 1", "row-position owner guesses", "invented SQLite is_called", "nextval or default consumption", "obligation registry", "product runtime"]
  },
  "test_plan": [
    "test_sqlite_fresh_process_native_state",
    "test_postgresql16_fresh_process_native_state",
    "test_process_receipt_rejection_matrix",
    "test_full_primary_key_and_paired_storage_order",
    "test_owner_policy_rejection_matrix",
    "test_sequence_and_catalog_rejection_matrix",
    "Run SQLite directly and PostgreSQL only through paper-trader/backend/scripts/run_disposable_postgres.py; retain full output under ignored .agent/runs through run_logged.py.",
    "Root independently checks the seven-file write-set diff, process receipts, disposable cleanup, and frozen/protected hashes."
  ],
  "acceptance": ["Both dialect observers execute in distinct child interpreters through strict JSON files.", "All process, full-PK, owner, sequence, and catalog rejections pass at exact seams.", "Root validates exact scope, hashes, and same-byte two-dialect evidence before successor dispatch."],
  "root_acceptance_gate": "Root must accept the exact observer report, evidence manifest, seven written file hashes, SQLite and disposable PG16 logs and receipts, rejection evidence, scope validation, and frozen/protected hash attestation before the obligation-evidence capsule may activate.",
  "deployment_impact": {
    "classification": "test-observer implementation only; migration-required downstream",
    "highest_claim": "local two-dialect fresh-process observation evidence",
    "deployable": false,
    "downstream": "obligations, mutation, runtime correction, integrated evidence, numeric correction, transitive revalidation, and critical review remain blocked"
  },
  "owner_gates": ["Stop for any expected or observed authority not fixed by sealed recovery contracts.", "Stop before external or non-loopback PostgreSQL access.", "Stop before editing the accepted core or any path outside write_ownership.", "Stop after the second failed attempt and return exact blocker evidence to root."],
  "stop_conditions": ["Any dialect, process, owner, sequence, catalog, native-scalar, or ordering choice remains implicit.", "The child receives expected values or runs in the parent process.", "The owner edits an accepted dependency, accesses non-loopback PostgreSQL, or begins a third attempt."],
  "review": {"required": false, "assignment_id": "foundation_native_state_observer_owner", "base_sha": "HEAD", "review_paths": ["paper-trader/backend/tests/foundation_native_state_observer_protocol.py", "paper-trader/backend/tests/foundation_native_state_sqlite_observer.py", "paper-trader/backend/tests/foundation_native_state_postgresql_observer.py", "paper-trader/backend/tests/foundation_native_state_observer_child.py", "paper-trader/backend/tests/foundation_sqlite_catalog_builder.py", "paper-trader/backend/tests/foundation_postgresql_0010_builder.py", "paper-trader/backend/tests/test_foundation_native_state_observer.py", ".agent/runs/phase1-4-foundation-research-migration-native-state-observer"], "exclude_paths": ["paper-trader/backend/tests/foundation_native_state_contract.py", "paper-trader/backend/tests/foundation_native_state_declarations.py", "paper-trader/backend/research", "paper-trader/backend/app", "paper-trader/frontend"], "verdicts": ["IMPLEMENTATION_ACCEPTABLE", "BLOCKED"]},
  "nonclaims": ["No 63-obligation execution, mutation attestation, migration, runtime, fixture, deployability, release, production, live, order, money, foundation, or phase acceptance follows from this slice."]
}
---

# Native-state observer

This second serial slice implements independent observation. It reads the accepted core but cannot change it or claim obligation coverage.
