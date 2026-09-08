---
{
  "id": "phase1-4-foundation-direct-closure",
  "phase": "interphase-4-5",
  "status": "accepted",
  "goal": "Close the Phase 1-4 foundation gate through finite direct migration and numeric product evidence, one independent critical review, and no recursive evidence language, then permit the Phase 5 architecture stage to start.",
  "owner_direction": {
    "source": "/Users/priyanshusaraf/.codex/attachments/0db8186b-1df8-45f7-883c-9bc979ae972d/pasted-text-1.txt",
    "sha256": "eb66946c5f7a8807ab116883b9847e337122dd3ebf6e118de2bf7d45d3322d01",
    "decision": "REPLACE_RECURSIVE_PROOF_ROUTE_WITH_FINITE_DIRECT_FOUNDATION_CLOSURE",
    "historical_capsule": "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md",
    "historical_capsule_sha256": "ad43a03f8befd956f412042ce119942d867c1b8ade4ef64175b31cf9c7bace31",
    "historical_evidence_disposition": "Immutable historical evidence. Preserve every file and verdict, do not continue or accept the closed-JSON, selector-observation, proof-package, or validator-of-validator lineages, and do not use them as current acceptance evidence."
  },
  "risk_tags": [
    "critical",
    "migration-required",
    "persistence",
    "numeric-authority",
    "programme-gate"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "Strategy OS defect-pattern register",
        "Status and evidence rules",
        "DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence",
        "DP-011 — Host-language numeric subtypes cross a typed market boundary"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-audit.md",
      "sections": [
        "Phase 1-4 foundation audit"
      ]
    }
  ],
  "dependency_gate": "phase1-4-foundation-audit",
  "support_matrix": {
    "sqlite": {
      "supported_starts": ["clean", "0010", "0011"],
      "target": "0011",
      "marker": ["version", "schema_cookie"]
    },
    "postgresql16": {
      "supported_starts": ["clean", "0010", "0011"],
      "target": "0011",
      "marker": ["version"]
    },
    "refused_before_write": [
      "unversioned",
      "0001-0009",
      "unknown",
      "future",
      "downgraded",
      "corrupted",
      "drifted",
      "hybrid-current-schema-rewind"
    ],
    "operator_path": "Refusal must name backup plus diagnostic/export or clean-rebuild handling. It must not rewrite a marker, infer historical schema from current models, repair an arbitrary database, or promise downgrade support."
  },
  "deployment_impact": {
    "classification": "migration-required",
    "evidence_level_ceiling": "locally_runnable",
    "affected_dimensions": ["migrations", "PostgreSQL", "data cutover", "backup/restore", "rollout/rollback"],
    "nonclaim": "Direct SQLite and disposable PostgreSQL 16 evidence does not prove release deployability, a production rehearsal, deployment, backup retention, production rollback, capacity, security, observability, or any production-data upgrade."
  },
  "allowed_paths": [
    "paper-trader/backend/research/domain/migrate.py",
    "paper-trader/backend/research/domain/migrations/0011_foundation_guard_contract.py",
    "paper-trader/backend/research/domain/migrations/__init__.py",
    "paper-trader/backend/research_tests/test_foundation_direct_migration_0011.py",
    "paper-trader/backend/research/data/store.py",
    "paper-trader/backend/research_tests/test_datastore.py",
    "paper-trader/backend/research_tests/test_foundation_a01_migration_upgrade.py",
    "paper-trader/backend/research_tests/test_ir_v2_research_migration.py",
    "paper-trader/backend/research_tests/test_operation_migration_recovery.py",
    "paper-trader/backend/research_tests/test_phase4_research_json_shape_parity.py",
    "paper-trader/backend/research_tests/test_strategy_admissions.py",
    "paper-trader/backend/tests/test_ir_experiment_routes.py",
    "paper-trader/backend/tests/test_ir_finding_routes.py",
    "paper-trader/backend/tests/test_research_review_routes.py",
    "paper-trader/backend/tests/test_research_review_sources.py",
    "paper-trader/backend/tests/test_phase4_authority_integration.py",
    "paper-trader/backend/tests/test_phase4_authority_research_migration.py",
    "paper-trader/backend/tests/test_phase4_adversarial_migration_matrix.py",
    "paper-trader/backend/tests/test_phase4_market_truth_persistence.py",
    "paper-trader/backend/tests/test_research_tenant_isolation.py",
    "paper-trader/backend/tests/test_outbox_plane_models.py",
    "paper-trader/backend/app/market_data/numeric.py",
    "paper-trader/backend/app/market_data/candles.py",
    "paper-trader/backend/app/backtest/dataset_store.py",
    "paper-trader/backend/app/backtest/identity.py",
    "paper-trader/backend/app/backtest/sweep.py",
    "paper-trader/backend/tests/test_market_numeric_ingress.py",
    "paper-trader/backend/tests/test_candle_validation.py",
    "paper-trader/backend/tests/test_dataset_store.py",
    "paper-trader/backend/tests/test_phase4_cache_identity.py",
    "paper-trader/backend/tests/test_phase4_alignment_causality.py",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-direct-closure.md",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md",
    "paper-trader/docs/agent/tasks/post-v1-test-order-isolation-hardening.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    ".agent/review-package.json",
    ".agent/runs/phase1-4-foundation-direct-closure"
  ],
  "parallel_budget": 2,
  "assignments": [
    {
      "id": "foundation_direct_migration_owner",
      "route": {
        "agent_type": "worker",
        "model": "gpt-5.6-sol",
        "reasoning_effort": "medium",
        "fork_turns": "none"
      },
      "owns": [
        "paper-trader/backend/research/domain/migrate.py",
        "paper-trader/backend/research/domain/migrations/0011_foundation_guard_contract.py",
        "paper-trader/backend/research/domain/migrations/__init__.py",
        "paper-trader/backend/research_tests/test_foundation_direct_migration_0011.py",
        "paper-trader/backend/research_tests/test_foundation_a01_migration_upgrade.py",
        "paper-trader/backend/research_tests/test_ir_v2_research_migration.py",
        "paper-trader/backend/research_tests/test_operation_migration_recovery.py",
        "paper-trader/backend/research_tests/test_phase4_research_json_shape_parity.py",
        "paper-trader/backend/research_tests/test_strategy_admissions.py",
        "paper-trader/backend/tests/test_ir_experiment_routes.py",
        "paper-trader/backend/tests/test_ir_finding_routes.py",
        "paper-trader/backend/tests/test_research_review_routes.py",
        "paper-trader/backend/tests/test_research_review_sources.py",
        "paper-trader/backend/tests/test_phase4_authority_integration.py",
        "paper-trader/backend/tests/test_phase4_authority_research_migration.py",
        "paper-trader/backend/tests/test_phase4_adversarial_migration_matrix.py",
        "paper-trader/backend/tests/test_phase4_market_truth_persistence.py",
        "paper-trader/backend/tests/test_research_tenant_isolation.py",
        "paper-trader/backend/tests/test_outbox_plane_models.py",
        ".agent/runs/phase1-4-foundation-direct-closure/foundation_direct_migration_owner"
      ],
      "must_not_edit": [
        "paper-trader/backend/app",
        "paper-trader/docs",
        ".agent/review-package.json"
      ],
      "outcome": "Implement and directly prove clean and exact 0010 to 0011 migration on SQLite and disposable PostgreSQL 16, exact 0011 current-state behavior, complete guards, preservation, atomic interruption/restart, and digest-identical pre-write refusal for every unsupported class."
    },
    {
      "id": "foundation_direct_numeric_owner",
      "route": {
        "agent_type": "worker",
        "model": "gpt-5.6-sol",
        "reasoning_effort": "medium",
        "fork_turns": "none"
      },
      "owns": [
        "paper-trader/backend/app/market_data/numeric.py",
        "paper-trader/backend/research/data/store.py",
        "paper-trader/backend/app/market_data/candles.py",
        "paper-trader/backend/app/backtest/dataset_store.py",
        "paper-trader/backend/app/backtest/identity.py",
        "paper-trader/backend/app/backtest/sweep.py",
        "paper-trader/backend/tests/test_market_numeric_ingress.py",
        "paper-trader/backend/tests/test_candle_validation.py",
        "paper-trader/backend/tests/test_dataset_store.py",
        "paper-trader/backend/tests/test_phase4_cache_identity.py",
        "paper-trader/backend/tests/test_phase4_alignment_causality.py",
        "paper-trader/backend/research_tests/test_datastore.py",
        ".agent/runs/phase1-4-foundation-direct-closure/foundation_direct_numeric_owner"
      ],
      "must_not_edit": [
        "paper-trader/backend/research/domain",
        "paper-trader/docs",
        ".agent/review-package.json"
      ],
      "outcome": "Reject True and False before every assigned OHLCV coercion and before dataset, cache, signal, or executable-price authority while preserving all ordinary valid finite numeric values, encoded bytes, addresses, and causal behavior."
    }
  ],
  "acceptance": [
    "The recursive proof engine is absent from the active route and all of its historical files and verdicts remain byte-preserved and unaccepted.",
    "Clean SQLite and clean disposable PostgreSQL 16 installations reach exact research head 0011.",
    "Exact SQLite 0010 and exact PostgreSQL 0010 each reach 0011 for at least two materially different populated fixed datasets per dialect.",
    "Rows, primary and foreign keys, owners, SQLite and PostgreSQL sequence state, JSON, Unicode, binary data, and canonical stored bytes are preserved exactly.",
    "Every required trigger and guard rejects its forbidden real SQL INSERT, UPDATE, or DELETE operation before the 0011 marker advances.",
    "An interrupted migration leaves a safe transactional state and a restart deterministically reaches 0011.",
    "Exact 0011 is deterministic and idempotent; unsupported or corrupted states refuse before any schema, marker, row, trigger, or sequence write and retain identical preflight digests.",
    "The deliberate marker difference is documented and directly tested: SQLite binds version to schema_cookie for fast-path drift detection, while PostgreSQL relies on transactionally validated version-only state.",
    "True and False refuse across every assigned open, high, low, close, and volume field before dataset, cache, computation, signal, or executable-price authority.",
    "Ordinary valid finite numeric values retain prior float behavior, binary dataset bytes, dataset addresses, cache identities, and causal next-bar results.",
    "The affected Phase 1-4 migration, numeric, subsystem, and integration selectors pass without exclusions.",
    "Removing each actual migration and numeric product guard kills its direct regression; exact byte restoration makes the regression pass again.",
    "The final product and direct-test bytes are frozen by source and evidence hashes, and stale or hybrid fixtures and claims are retired or accurately relabelled.",
    "One independent Sol-high critical reviewer returns separate SPEC PASS and QUALITY PASS from the frozen integrated review package."
  ],
  "test_plan": [
    "Use reviewed repository tests and fixed, independently inspected fixtures. Do not create a proof DSL, selector grammar, self-verifying package language, or validator of validators.",
    "Run focused implementation selectors, then direct SQLite and disposable PostgreSQL 16 migration matrices and the numeric boundary matrix with full logs under the capsule evidence root.",
    "Run the relevant Phase 1-4 subsystem and integration selectors once from frozen integrated bytes with no skips, exclusions, xfails, or deselection in the claimed set.",
    "Mutate each actual product guard reversibly, require its direct regression to fail, restore exact source bytes, and rerun the passing baseline.",
    "Generate one precise review package only after final source and test hashes are frozen, then dispatch one independent critical reviewer with one permitted recheck."
  ],
  "bounded_correction": {
    "maximum": 1,
    "used": 1,
    "rule": "After integration, correct only a genuine product or direct-evidence defect through the smallest owning assignment. Any broader architecture, support, identity, authority, or production issue stops for owner direction."
  },
  "acceptance_result": {
    "decision": "ACCEPT_FINITE_DIRECT_PHASE1_4_FOUNDATION_CLOSURE",
    "review_package_sha256": "0e67dfcebb0b85161efa34501a8a3a6a953c4bed5a9e66bc93b2ffe481a56cfc",
    "dirty_tree_fingerprint": "97ab34d99165171d6d0b025bffeac20dac4ce7c235e6b1735d199a15e31b73c0",
    "initial_review": ".agent/runs/phase1-4-foundation-direct-closure/review/verdict.json",
    "recheck_review": ".agent/runs/phase1-4-foundation-direct-closure/review/recheck-verdict.json",
    "recheck_review_sha256": "d43994cc2d4d1d6e9b827a0f6169a1a75128b24d862e3ac3461ded7fca153069",
    "spec": "PASS",
    "quality": "PASS",
    "research_head": "0011",
    "execution_head": "0039",
    "historical_member_count": 97,
    "historical_aggregate_sha256": "582ec04f0737084743cd2fb99430ba864a9b63281ad1209f38a6628876a1d8b8",
    "deployment_evidence_level": "locally_runnable"
  },
  "review": {
    "required": true,
    "assignment_id": "foundation_direct_closure_critical_reviewer",
    "agent_type": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "fork_turns": "none",
    "reason": "The integrated slice changes a research migration head and a market numeric authority boundary that gate Phase 5.",
    "package": ".agent/review-package.json",
    "output": ".agent/runs/phase1-4-foundation-direct-closure/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  },
  "owner_gates": [
    "Stop for owner direction before using a database that contains production or customer data, credentials, deployed state, live authority, orders, money, or evidence that an old database is genuinely valuable and must be preserved.",
    "Stop before destructive data or infrastructure work, deployment, frontend implementation, provider or broker changes, live IR authority, sizing, routing, risk, execution semantics, legal, regulatory, or commercial decisions.",
    "Stop if the supported matrix cannot be narrowed without contradicting an actual released or externally promised database contract."
  ],
  "nonclaims": [
    "This capsule does not reopen V2 or V3 work and does not enable the existing terminally refused V2 runtime.",
    "It grants no frontend, provider, broker, credential, deployment, production, live-authority, order, money, release-deployability, production-rehearsal, backup-retention, rollback, capacity, security, or observability claim.",
    "A theoretical test-machinery weakness is outside the V1 critical path unless ordinary reviewed repository code can make a required direct test report a false result."
  ],
  "stopping_condition": "Accept phase1-4-foundation-critical-closure only after every finite acceptance item has current frozen-byte evidence and one independent reviewer returns SPEC PASS and QUALITY PASS. Then activate phase5-architecture; no other hypothetical proof-harness attack may extend this gate."
}
---

# Phase 1-4 finite direct foundation closure

This capsule replaces the recursive evidence-engine route with direct tests of product behavior. It preserves the historical proof-engine files and verdicts without accepting or repairing them. The finite boundary is reviewed test code, fixed fixtures, real SQLite, disposable PostgreSQL 16, exact source and evidence hashes, reversible mutations of product guards, and one independent critical review.
