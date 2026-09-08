---
{
  "id": "phase4-authority-transaction-correction",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Implement the accepted dialect-safe authority transaction contract so execution and research graph-plus-receipt writes, and every same-pattern Phase 1-4 seam classified as impacted, remain caller-owned and fully roll back after flush, commit, collision, or retry failure on SQLite and PostgreSQL.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "After phase4-authority-transaction-architecture-correction is root-accepted, one fresh Terra-medium implementation owner may edit only the architecture-frozen exact product, test, report, deployability, defect-pattern, capsule-evidence paths and may dispatch exactly one declared Luna-medium evidence-only child after product/test/source-map freeze. No schema, migration, provider, frontend, runtime enablement, deployment, credentials, production, live, or money work is authorized.",
    "stopping_condition": "Complete only when the shared accepted transaction boundary is used by every architecture-classified impacted seam; both execution and research graph-plus-receipt writers prove zero durable rows after caller commit refusal and rollback; unrelated pending caller work is neither committed nor discarded by the nested writer; SQLite and PostgreSQL lifecycle, collision/retry, process restart, mutation kills, exact restoration, transitive selectors, and protected/scoped evidence pass. Stop if the architecture is not accepted, any same-pattern Critical remains uncorrected, or implementation needs a schema, migration, broad rewrite, hidden commit, provider/runtime change, deployment, production state, or live/money authority."
  },
  "risk_tags": [
    "critical",
    "transaction-boundary",
    "authority-atomicity",
    "execution-research-parity",
    "sqlite-postgresql-parity",
    "pattern-closure"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "9. Ownership, authority, and persistence",
        "13.2 Persistence, reconstruction, and refusal",
        "13.3 Adversarial owner matrix",
        "13.5 Stale evidence and revalidation"
      ]
    },
    {
      "path": "paper-trader/docs/superpowers/plans/phase4-strategy-os.md",
      "sections": [
        "5. Verification cadence",
        "8. Authority-correction serial route"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "Phase 4 ownership"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "DP-008 — Manual prerequisite verification substituted for the consuming seam"
      ]
    },
    {
      "path": "paper-trader/docs/agent/tasks/phase4-authority-transaction-architecture-correction.md",
      "sections": [
        "Phase 4 authority transaction architecture correction"
      ]
    }
  ],
  "dependency_gate": "phase4-authority-transaction-architecture-correction",
  "allowed_paths": [
    "paper-trader/backend/app/db/concurrency.py",
    "paper-trader/backend/app/core/strategy_admissions.py",
    "paper-trader/backend/research/domain/admissions.py",
    "paper-trader/backend/research/domain/strategy_admissions.py",
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/app/backtest/public_computation.py",
    "paper-trader/backend/app/ledger/service.py",
    "paper-trader/backend/tests/test_phase4_authority_transaction_boundary.py",
    "paper-trader/backend/research_tests/test_phase4_authority_transaction_boundary.py",
    "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
    "paper-trader/backend/research_tests/test_phase4_v2_graph_persistence.py",
    "paper-trader/backend/tests/test_public_backtest_computation.py",
    "paper-trader/backend/tests/test_phase4_authority_integration.py",
    "paper-trader/docs/reports/phase4-implementation.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/docs/agent/DEFECT_PATTERNS.md",
    "paper-trader/docs/agent/tasks/phase4-authority-transaction-correction.md",
    ".agent/runs/phase4-authority-transaction-correction"
  ],
  "architecture_promoted_paths": [
    "paper-trader/backend/research/domain/strategy_admissions.py",
    "paper-trader/backend/app/backtest/repository.py",
    "paper-trader/backend/app/backtest/public_computation.py",
    "paper-trader/backend/app/ledger/service.py",
    "paper-trader/backend/tests/test_phase4_authority_transaction_boundary.py",
    "paper-trader/backend/research_tests/test_phase4_authority_transaction_boundary.py"
  ],
  "scope_amendment_2026_08_18": "Root authorized exactly two transitive test-only fixture corrections after the first current-byte selector reached stale pre-seam interfaces: test_public_backtest_computation.py may add the optional phase4_binding field to its fake verified admission, and test_phase4_authority_integration.py may use the current internally reconstructed-plan ReclaimAuthorityContext loader contract. No product, schema, migration, runtime, provider, frontend, deployment, production, live, or money scope expands.",
  "product_paths_read_only_until_promoted_by_accepted_architecture": [
    "paper-trader/backend/migrations",
    "paper-trader/frontend"
  ],
  "frozen_api": {
    "symbol": "app.db.concurrency.caller_owned_savepoint",
    "signature": "caller_owned_savepoint(session, *, scope)",
    "outer_owner": "caller",
    "owned_by_helper": "one nested savepoint only",
    "forbidden_helper_actions": ["commit", "rollback", "close", "invalidate", "hidden Session", "hidden connection", "retry"],
    "proof": "Same live Session root transaction, same enlisted connection, supported dialect, and physical DBAPI outer transaction before SAVEPOINT. Root proof clears at outer transaction end and is rechecked on every entry.",
    "nested_rule": "Recursive helper calls are valid only under the same live root proof. An unproved already-nested SQLite Session refuses before write; an external root is accepted only when the exact connection proves the physical outer transaction existed before the helper savepoint.",
    "failure_rule": "Nested failure rolls back only the savepoint and propagates. Commit or rollback remains caller-owned. A failed or ambiguous Session is discarded and canonical state is reconstructed through a fresh Session."
  },
  "classified_seams": [
    {"path": "paper-trader/backend/app/core/strategy_admissions.py", "symbol": "put", "classification": "critical_authority_impacted", "test_owner": "paper-trader/backend/tests/test_phase4_authority_transaction_boundary.py", "mutation": "remove shared boundary at execution admission"},
    {"path": "paper-trader/backend/research/domain/admissions.py", "symbol": "store_admission", "classification": "critical_authority_impacted", "test_owner": "paper-trader/backend/research_tests/test_phase4_authority_transaction_boundary.py", "mutation": "remove shared boundary at research admission"},
    {"path": "paper-trader/backend/research/domain/strategy_admissions.py", "symbol": "persist_verified_dataset_authority", "classification": "critical_authority_impacted", "test_owner": "paper-trader/backend/research_tests/test_phase4_authority_transaction_boundary.py", "mutation": "remove shared boundary at dataset authority"},
    {"path": "paper-trader/backend/app/backtest/repository.py", "symbol": "append_claimed_result_batch", "classification": "critical_fenced_result_impacted", "test_owner": "paper-trader/backend/tests/test_phase4_authority_transaction_boundary.py", "mutation": "remove shared boundary at claimed batch"},
    {"path": "paper-trader/backend/app/backtest/repository.py", "symbol": "complete_claim", "classification": "critical_terminal_outbox_impacted", "test_owner": "paper-trader/backend/tests/test_phase4_authority_transaction_boundary.py", "mutation": "remove shared boundary at terminal outbox"},
    {"path": "paper-trader/backend/app/backtest/public_computation.py", "symbol": "put_immutable", "classification": "non_authoritative_persistence_impacted", "test_owner": "paper-trader/backend/tests/test_phase4_authority_transaction_boundary.py", "mutation": "remove shared boundary at public computation"},
    {"path": "paper-trader/backend/app/ledger/service.py", "symbol": "write_snapshot", "classification": "critical_snapshot_outbox_impacted_transaction_hardening_only", "test_owner": "paper-trader/backend/tests/test_phase4_authority_transaction_boundary.py", "mutation": "remove direct shared boundary under outbox.writer"}
  ],
  "nonclaims": [
    "A passing correction proves caller-owned atomic persistence and dialect parity only. It does not close the adversarial matrix, accept Phase 4, enable Component IR v2 runtime, or prove deployment or production readiness.",
    "No schema, migration, dependency, service, configuration, provider, frontend, deployment, production data/use, capacity, live, or money claim follows.",
    "The matrix must restart from current bytes under a fresh owner after root accepts this correction; stopped matrix evidence cannot be upgraded into completion credit."
  ],
  "owner_gates": [
    "Stop if any product or test path outside the accepted architecture's exact promoted set must change; the implementation owner may not expand scope.",
    "Stop before schema, migration, provider, broker, frontend, deployment, credentials, production data/use, runtime enablement, live, money, destructive, legal, or commercial action.",
    "Stop if the proposed helper commits or rolls back caller-owned unrelated work, hides a Session/connection, creates a second persistence API, or diverges across SQLite and PostgreSQL without a frozen reason."
  ],
  "stop_conditions": [
    "A caller commit refusal followed by rollback leaves any graph, receipt, or classified authority row durable in execution or research.",
    "A clean/read-only SQLite Session reaches a top-level SAVEPOINT without a real outer DB transaction, or a nested writer commits/rolls back unrelated caller pending work.",
    "Collision, retry, flush failure, commit failure, process restart, SQLite, PostgreSQL 16, or same-pattern impacted seams lack direct current-byte regression evidence.",
    "A required mutation survives, restoration hashes differ, a dependent selector remains stale, a protected hash changes, or frontend/deployment scope changes."
  ],
  "deployment_impact": {
    "classification": "schema-free-phase4-authority-transaction-hardening",
    "required_evidence": "Prove caller-owned transaction semantics on current SQLite and disposable PostgreSQL 16 for both authority planes and every architecture-classified impacted seam; preserve exact migration heads, configuration, dependencies, services, provider/frontend exclusions, protected hashes, and local-only nonclaims."
  },
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "children": "gpt-5.6-luna",
    "child_reasoning_effort": "medium",
    "child_agent_role": "luna-worker",
    "service_tier": "default"
  },
  "parallel_budget": 1,
  "owner_milestones": [
    "owner_transaction_interfaces_frozen",
    "owner_product_test_source_map_frozen",
    "owner_attributable_evidence_frozen"
  ],
  "assignments": [
    {
      "id": "phase4_authority_transaction_evidence",
      "agent": "luna-worker",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "medium",
      "mode": "write-evidence-only",
      "depends_on": [
        "owner_product_test_source_map_frozen"
      ],
      "read_paths": [
        "paper-trader/backend/app/db/concurrency.py",
        "paper-trader/backend/app/core/strategy_admissions.py",
        "paper-trader/backend/research/domain/admissions.py",
        "paper-trader/backend/research/domain/strategy_admissions.py",
        "paper-trader/backend/app/backtest/repository.py",
        "paper-trader/backend/app/backtest/public_computation.py",
        "paper-trader/backend/app/ledger/service.py",
        "paper-trader/backend/tests/test_phase4_authority_transaction_boundary.py",
        "paper-trader/backend/research_tests/test_phase4_authority_transaction_boundary.py",
        "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
        "paper-trader/backend/research_tests/test_phase4_v2_graph_persistence.py"
      ],
      "write_paths": [
        ".agent/runs/phase4-authority-transaction-correction/luna_evidence"
      ],
      "output": ".agent/runs/phase4-authority-transaction-correction/luna_evidence/report.md"
    }
  ],
  "acceptance": [
    "The implementation follows the accepted architecture's single shared transaction-boundary contract. It establishes a real caller-owned outer DB transaction before any nested SQLite SAVEPOINT without committing or rolling back caller work and preserves equivalent PostgreSQL semantics.",
    "Execution put and research store_admission each prove graph and receipt atomicity for clean sessions, prior reads, prior writes, explicit caller transactions, nested callers, unrelated pending writes, flush failure, DBAPI commit refusal, collision, retry, caller rollback, and process restart.",
    "Every architecture-classified impacted same-pattern seam uses the same contract and has exact real-seam current-byte evidence; safe or non-authoritative seams retain explicit disposition evidence and are not silently claimed corrected.",
    "Caller commit refusal followed by caller rollback leaves zero graph and zero receipt rows in both planes. Successful caller commit persists both exact canonical rows; no intermediate observer or restarted process can see a partial fact.",
    "SQLite and separate disposable PostgreSQL 16 databases pass dialect-dependent transaction, visibility, locking, rollback, and retry cases; exact migration heads remain unchanged and no schema or migration bytes change.",
    "At least eleven controlled reversible mutations kill physical-root establishment, root-marker cleanup, unproved-external-nesting refusal, the no-helper-commit/rollback/close rule, and one direct adoption guard at each of all seven seams; all owned product/test bytes restore exactly before final selectors.",
    "After product/test/source-map freeze, only the declared Luna-medium evidence child runs exact attributable commands. The owner independently audits its output, transitive selectors, protected hashes, frontend/deployment exclusions, and report accuracy.",
    "Root acceptance may only unblock a fresh adversarial-matrix owner. It does not make final review, Phase 4, Phase 5, deployment, production, live, or money authority ready."
  ],
  "test_plan": [
    "Retain the exact ADV-003 counterexample before editing, then implement only the architecture-frozen transaction boundary and classified impacted seams.",
    "Run focused execution/research authority transaction selectors on SQLite while authoring, then proportional disposable PostgreSQL 16 cases for real dialect semantics. Avoid broad suites for confidence.",
    "Freeze product/tests/source map, dispatch only the declared Luna evidence child, run reversible mutations, restore exact bytes, rerun transitive affected selectors, and seal command/cwd/node/exit evidence."
  ],
  "transitive_selectors": [
    "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
    "paper-trader/backend/research_tests/test_phase4_v2_graph_persistence.py",
    "paper-trader/backend/tests/test_phase4_dataset_assessment_authority.py",
    "paper-trader/backend/tests/test_backtest_job_claims.py",
    "paper-trader/backend/tests/test_public_backtest_computation.py",
    "paper-trader/backend/tests/ledger/test_routes.py",
    "paper-trader/backend/tests/test_outbox_contract.py",
    "paper-trader/backend/tests/test_phase4_authority_integration.py",
    "paper-trader/backend/tests/test_phase4_adversarial_transactions.py::test_adv_002_every_named_transaction_boundary_is_atomic",
    "paper-trader/backend/tests/test_phase4_adversarial_transactions.py::test_adv_003_commit_failure_leaves_no_graph_or_receipt_orphan"
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_authority_transaction_owner",
    "agent": "owner",
    "model": "gpt-5.6-terra",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/db/concurrency.py",
      "paper-trader/backend/app/core/strategy_admissions.py",
      "paper-trader/backend/research/domain/admissions.py",
      "paper-trader/backend/research/domain/strategy_admissions.py",
      "paper-trader/backend/app/backtest/repository.py",
      "paper-trader/backend/app/backtest/public_computation.py",
      "paper-trader/backend/app/ledger/service.py",
      "paper-trader/backend/tests/test_phase4_authority_transaction_boundary.py",
      "paper-trader/backend/research_tests/test_phase4_authority_transaction_boundary.py",
      "paper-trader/backend/tests/test_phase4_v2_graph_persistence.py",
      "paper-trader/backend/research_tests/test_phase4_v2_graph_persistence.py",
      "paper-trader/backend/tests/test_public_backtest_computation.py",
      "paper-trader/backend/tests/test_phase4_authority_integration.py",
      "paper-trader/docs/reports/phase4-implementation.md",
      "paper-trader/docs/agent/DEPLOYABILITY.md",
      "paper-trader/docs/agent/DEFECT_PATTERNS.md"
    ],
    "exclude_paths": [
      "paper-trader/frontend",
      "paper-trader/backend/migrations",
      "paper-trader/backend/app/engine/kite_venue.py",
      "paper-trader/backend/app/engine/venue.py",
      "paper-trader/backend/app/providers/brokers.py"
    ],
    "output": ".agent/runs/phase4-authority-transaction-correction/owner/report.md",
    "verdicts": [
      "CORRECTED",
      "BLOCKED"
    ]
  },
  "protected_files": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 4 authority transaction correction

This capsule opens only after the architecture contract is root-accepted. It
repairs the caller-owned transaction boundary for the execution and research
authority writers and any same-pattern foundation seams the architect marks
as impacted. It does not change schemas or enable runtime authority.
