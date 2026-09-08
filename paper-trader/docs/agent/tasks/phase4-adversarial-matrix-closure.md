---
{
  "id": "phase4-adversarial-matrix-closure",
  "phase": "phase4",
  "status": "accepted",
  "goal": "Close the normative Phase 4 ADV-001..ADV-027 matrix with current-byte, real-seam, independently attributable evidence under the corrected ADV-006 containment contract, without changing product behavior, narrowing any row, or claiming the later operational reclaim lifecycle.",
  "goal_contract": {
    "create_before_work": true,
    "owner_authorization": "The owner authorized all bounded work required to finish Phase 4, but this capsule is blocked until phase4-authority-transaction-correction is root-accepted. After that acceptance, one fresh Sol-medium repeated-failure assurance owner may use only the five declared focused adversarial test/support paths and evidence, and one declared Luna-medium evidence-only child after the owner freezes the complete test/source map. The three stopped owners supply no completion credit. The stopped third owner created phase4_adversarial_support.py and test_phase4_adversarial_transactions.py; those two paths remain writable only inside this capsule and their current bytes are starting fixtures, not accepted evidence. Existing product, schema, migration, other production test, programme, CURRENT, capsule, package, provider, frontend, runtime, deployment, live, and money bytes remain read-only.",
    "stopping_condition": "Complete only when every normative row ADV-001..ADV-027 has a current-byte FULL disposition with no residual, skip, xfail, deselection, historical-evidence upgrade, or manually verified substitute; ADV-006 is FULL only for explicit-context authority verification and exact V2_RUNTIME_UNAVAILABLE before every named side effect and carries an explicit P5-ADV-006-RUNTIME nonclaim; all shared rows exercise both execution and research planes where the design requires both; ADV-014 uses separate disposable PostgreSQL 16 databases; every row is independently attributable; and all added tests pass with exact protected/scoped hashes. If any real seam cannot satisfy its row without a product, schema, migration, or existing-test change, stop at the owner gate, keep the goal active, and report one exact bounded correction. Do not patch the defect in this capsule."
  },
  "risk_tags": [
    "critical",
    "adversarial-matrix",
    "authority",
    "persistence",
    "migration",
    "resource-recovery",
    "evidence-attribution"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md",
      "sections": [
        "9. Ownership, authority, and persistence",
        "10. Acceptance scenarios and refusals",
        "11. Deployment contract",
        "13.1 Fact and equality matrix",
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
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": [
        "DP-001 — Distinct facts collapsed into one representation",
        "DP-002 — Syntactic self-consistency mistaken for authority",
        "DP-003 — Mocked seam presented as lifecycle evidence",
        "DP-004 — Immutable envelope over mutable or time-incoherent facts",
        "DP-005 — Address-bearing metadata mistaken for a typed authoritative fact",
        "DP-006 — Database session timezone changed copied authority instants",
        "DP-007 — Cross-dialect JSON constraint changed authoritative field shape",
        "DP-008 — Manual prerequisite verification substituted for the consuming seam"
      ]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": [
        "Current verdict",
        "Open obligations",
        "Phase 4 ownership"
      ]
    }
  ],
  "dependency_gate": "phase4-authority-transaction-correction",
  "allowed_paths": [
    "paper-trader/backend/tests/phase4_adversarial_support.py",
    "paper-trader/backend/tests/test_phase4_adversarial_transactions.py",
    "paper-trader/backend/tests/test_phase4_adversarial_authority.py",
    "paper-trader/backend/tests/test_phase4_adversarial_migration_matrix.py",
    "paper-trader/backend/tests/test_phase4_adversarial_resource_recovery.py",
    ".agent/runs/phase4-adversarial-matrix-closure"
  ],
  "product_paths_read_only": [
    "paper-trader/backend/app",
    "paper-trader/backend/research",
    "paper-trader/backend/migrations",
    "paper-trader/frontend"
  ],
  "preexisting_test_policy": "The stopped third owner created phase4_adversarial_support.py and test_phase4_adversarial_transactions.py before routing ADV-003; those two declared paths remain writable starting fixtures and supply zero completion credit. Every other file that existed before this capsule under paper-trader/backend/tests and paper-trader/backend/research_tests is read-only. The only writable test paths are the five exact files listed in allowed_paths.",
  "nonclaims": [
    "This is a test-and-evidence closure stage. It does not repair a discovered defect, change accepted product or migration bytes, or make Phase 4 accepted by itself.",
    "A passing unit helper, dots-only log, same-process serialization round-trip, SQLite-only migration result, mocked authority seam, manual prerequisite check, or source-token scan cannot replace the named real lifecycle or PostgreSQL requirement.",
    "This stage does not implement Component IR v2 execution, Phase 5, frontend, providers, deployment, credentials, production data/use, capacity, release, live, or money authority.",
    "Resource and cancellation tests use deterministic bounded fault injection against local disposable resources. They do not exhaust or damage the host and do not prove production capacity.",
    "ADV-006 FULL proves only Phase 4 public-seam containment. It does not prove successful v2 claim, ownership loss, reclaim, worker execution, result finalization, or P5-ADV-006-RUNTIME."
  ],
  "owner_gates": [
    "Stop immediately if a residual row exposes a product, schema, migration, accepted-test, authority, identity, atomicity, concurrency, cache, migration, or recovery defect. Record the exact failing public seam and smallest bounded correction; do not patch it here.",
    "Stop before any production/test fixture compatibility shim, weakened assertion, row narrowing, historical PASS inheritance, skip/xfail/deselection, generic authority dispatcher, hidden session, deployment, credentials, provider network, production data/use, frontend, live, money, destructive, legal, or commercial action."
  ],
  "stop_conditions": [
    "Any ADV-001..ADV-027 row remains RESIDUAL-GAP, NARROWED, BLOCKED, skipped, xfailed, deselected, dependent on historical evidence, or unsupported by exact current-byte test attribution.",
    "A shared execution/research row is demonstrated on only one plane; ADV-014 lacks real separate-database disposable PostgreSQL 16 evidence; or an old-head/mixed-version case uses a synthetic shape that cannot arise from the supported migration chain.",
    "A test proves only a helper, manually loads authority beside the consumer, monkeypatches the decisive authority loader, avoids process death where required, or observes an exception before reaching the named public seam.",
    "A bounded fault-injection case leaves partial authority, a survivor mutation, changed existing/product bytes, a protected hash mismatch, frontend delta, or an inaccurate row ledger."
  ],
  "deployment_impact": {
    "classification": "test-only-local-phase4-adversarial-assurance",
    "required_evidence": "Use current SQLite for bounded deterministic cases and separate disposable PostgreSQL 16 execution/research databases for ADV-014 plus dialect-dependent transaction, concurrency, migration, trigger, or constraint cases. Verify exact heads 0039/0010, unchanged migrations/product bytes, protected hashes, frontend exclusion, and local-only nonclaims. Do not infer deployment or production readiness."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "children": "gpt-5.6-luna",
    "child_reasoning_effort": "medium",
    "child_agent_role": "luna-worker",
    "next_reviewer": "gpt-5.6-sol",
    "next_reviewer_reasoning_effort": "high",
    "service_tier": "default"
  },
  "parallel_budget": 1,
  "owner_milestones": [
    "owner_residual_contract_frozen",
    "owner_test_source_map_frozen",
    "owner_full_adv_evidence_frozen"
  ],
  "work_groups": [
    {
      "id": "transaction_retry_cache_worker",
      "rows": ["ADV-002", "ADV-003", "ADV-004", "ADV-005", "ADV-006", "ADV-007", "ADV-008", "ADV-021", "ADV-026", "ADV-027"]
    },
    {
      "id": "canonical_dependency_tenancy_bounds",
      "rows": ["ADV-009", "ADV-010", "ADV-016", "ADV-017", "ADV-018", "ADV-019", "ADV-020", "ADV-021", "ADV-022", "ADV-023", "ADV-024", "ADV-025", "ADV-026", "ADV-027"]
    },
    {
      "id": "migration_and_mixed_version",
      "rows": ["ADV-011", "ADV-012", "ADV-013", "ADV-014", "ADV-015"]
    },
    {
      "id": "loader_transitive_staleness",
      "rows": ["ADV-005", "ADV-008", "ADV-019", "ADV-020"]
    }
  ],
  "assignments": [
    {
      "id": "phase4_adversarial_attributable_evidence",
      "agent": "luna-worker",
      "model": "gpt-5.6-luna",
      "reasoning_effort": "medium",
      "mode": "write-evidence-only",
      "depends_on": [
        "owner_test_source_map_frozen"
      ],
      "read_paths": [
        "paper-trader/backend/tests/phase4_adversarial_support.py",
        "paper-trader/backend/tests/test_phase4_adversarial_transactions.py",
        "paper-trader/backend/tests/test_phase4_adversarial_authority.py",
        "paper-trader/backend/tests/test_phase4_adversarial_migration_matrix.py",
        "paper-trader/backend/tests/test_phase4_adversarial_resource_recovery.py",
        "paper-trader/docs/superpowers/specs/phase4-strategy-os-design.md"
      ],
      "write_paths": [
        ".agent/runs/phase4-adversarial-matrix-closure/luna_evidence"
      ],
      "output": ".agent/runs/phase4-adversarial-matrix-closure/luna_evidence/report.md"
    }
  ],
  "review": {
    "required": false,
    "assignment_id": "phase4_adversarial_matrix_closure",
    "agent": "owner",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "medium",
    "base_sha": "HEAD",
    "package": ".agent/review-package.json",
    "review_paths": [
      "paper-trader/backend/tests/phase4_adversarial_support.py",
      "paper-trader/backend/tests/test_phase4_adversarial_transactions.py",
      "paper-trader/backend/tests/test_phase4_adversarial_authority.py",
      "paper-trader/backend/tests/test_phase4_adversarial_migration_matrix.py",
      "paper-trader/backend/tests/test_phase4_adversarial_resource_recovery.py"
    ],
    "exclude_paths": [
      "paper-trader/backend/app",
      "paper-trader/backend/research",
      "paper-trader/backend/migrations",
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/phase4-adversarial-matrix-closure/owner/report.md",
    "verdicts": [
      "FULL",
      "BLOCKED"
    ]
  },
  "acceptance": [
    "The owner freezes a row-by-row residual contract from the accepted loader audit before writing tests. Each ADV-002..ADV-027 residual phrase becomes one or more exact observable cases; no residual is silently dropped, merged away, or reclassified.",
    "ADV-001 is rerun against the exact final source hash. ADV-002..ADV-027 each finish FULL with an empty residual list. Shared rows prove all required execution and research planes and the actual authority-consuming public seam, not a parallel helper.",
    "Transaction, crash, commit, replay, stale-worker, cache restart/poisoning, concurrency, resource, and cancellation cases use deterministic injection at every named Phase 4 boundary and prove rollback, exact current identity, no partial authority, and recoverable retry/restart behavior.",
    "ADV-006 calls the real public v2 reclaim-dispatch seam with explicit current authority context. It proves the complete current chain is verified and exact V2_RUNTIME_UNAVAILABLE occurs before claim, reclaim, provider, cache, worker, claim-token, result, broker, order, or money side effects; stale or missing authority refuses earlier. Its FULL record contains the explicit nonclaim that P5-ADV-006-RUNTIME remains unproved.",
    "Malformed, hostile, missing, duplicate, forged, deleted/replaced, owner-crossed, temporal, empty, and huge cases cover every fact family named by the row and prove exact refusal or distinct bounded identity without fallback or disclosure.",
    "Migration rows use exact supported old heads and mixed states. ADV-014 installs execution head 0039 and research head 0010 from zero on SQLite and on separate disposable PostgreSQL 16 databases, verifies constraints/triggers/model parity, and contains no PostgreSQL skip.",
    "ADV-019 independently mutates topology, registry, implementation, dataset, truth, capability, policy, owner, product, and contract through admission, cache, and actual pre-runtime loader contexts. Every stale chain refuses before terminal runtime or side effects; the current companion alone reaches V2_RUNTIME_UNAVAILABLE.",
    "ADV-026 and ADV-027 use bounded local fault injection for pool/write/disk-like/query/file-descriptor/memory-budget/outbox failures and cancellation during every named stage. Tests leave the host intact and prove rollback or resumable non-authoritative state after restart.",
    "Each row has a separate machine-readable record with source hashes, canonical cwd, full command, timestamp, selected and collected node IDs, exit code, expectation, semantic observation, decisive addresses/refusal, database/process boundary, and an empty residual list. Aggregate or dots-only logs do not count.",
    "The owner independently audits the Luna ledger against the frozen source map and rejects empty, duplicated, mislabeled, skipped, or semantically narrowed records. A validator proves exactly 27 unique FULL rows, zero residual/blocked/skipped rows, and hash closure over every cited log.",
    "Only the five new test/support paths and ignored evidence change. Existing product, migration, accepted test, frontend, provider, programme, CURRENT, capsule, and package bytes remain unchanged; protected hashes, exact heads, syntax, scoped diff, and report accuracy pass.",
    "The matrix remains exactly ADV-001..ADV-027. P5-ADV-006-RUNTIME is a separate mandatory Phase 5 lifecycle, not a twenty-eighth row and not Phase 4 evidence.",
    "Completion makes only phase4-final-review-4 eligible for root package preparation. It does not accept Phase 4, open the foundation audit or Phase 5, or make any deployment, production, live, or money claim."
  ],
  "test_plan": [
    "Use the accepted transitive audit as the residual source of truth, then map every residual phrase to exact new test node IDs before implementation. Reuse existing constructors and public seams; do not duplicate production logic in fixtures.",
    "Run narrow SQLite selectors while authoring. Use the existing disposable PostgreSQL harness only for the exact migration/dialect/concurrency cases that require it. Do not run a broad suite for confidence.",
    "After the owner freezes all five new test/support files and their source map, dispatch exactly the declared Luna child to run separately attributable commands and build the machine ledger. The child may not edit tests or product.",
    "Independently audit every evidence row, rerun bounded counterexamples as needed, verify exact product/existing-test/protected hashes, and write an owner report that either closes all 27 rows or stops on the first exact product-correction gate."
  ],
  "protected_hashes": {
    "paper-trader/backend/app/engine/kite_venue.py": "2fd450b6fd433129a543df8d5f04670251e9c3796feb159b138481a9a5a99240",
    "paper-trader/backend/app/engine/venue.py": "c8a39f0e8986e2484fe4b4b3d3cbe4bb829302896b288ba5e22a8fa51f525dae",
    "paper-trader/backend/app/providers/brokers.py": "d5e6b8367a4703311e0fad4562911f8a37f7ead9d8e438bfb8b18f215d691d38",
    "paper-trader/backend/tests/test_broker_registry.py": "13a174e3e15c24ec174eb198eeea86dd2f263f9b09f00582b7b96224527491e3"
  }
}
---

# Phase 4 adversarial matrix closure

This capsule closes evidence obligations, not product scope. The accepted
loader correction deliberately reports only `ADV-001` as full. Every residual
phrase for `ADV-002` through `ADV-027` remains binding under design section
13.3.

The explicit reclaim authority-context correction is root-accepted. The third
fresh matrix owner then reproduced ADV-003 against both real persistence planes:
after a DBAPI commit refusal and caller rollback, SQLite retained both graph and
receipt rows. That owner stopped and supplies no completion credit. This capsule
is blocked until the serial transaction architecture and implementation
corrections are root-accepted. One later fresh owner must rerun all 27 rows from
current bytes, may use only the five declared adversarial test/support files,
and must stop when any real seam fails. A failed test is a routed product defect,
not permission to patch production or dilute the row. The single Luna worker is
mechanical and may run only after the owner freezes the complete test/source map.

The accepted transaction architecture classifies exactly seven impacted
savepoint seams: execution admission, research admission, research dataset
authority, fenced result batch, terminal run/outbox, public computation cache,
and ledger snapshot/outbox. The correction must use the same caller-owned
boundary at every seam and root-accept its SQLite/PostgreSQL evidence before
this capsule opens. The matrix must rerun ADV-002 and ADV-003 through the real
writers, including a clean Session, prior SELECT/write, nested caller, DBAPI
commit refusal plus rollback, exact retry/collision, and fresh-process outcome;
helper-only evidence or a historical PASS is insufficient.

ADV-006 evidence must exercise the accepted exact-row transaction contract,
not a helper preflight: one synchronous research Session and aware cutoff are
shared by both loader sites; any mixed v1/v2 owner set refuses with zero
mutation; concurrent inserts stay outside explicit classified legacy ids; and
state, owner, admission, cancellation, token, or expiry transitions roll back.
The matrix must reject a restored broad owner reconciliation update, missing
SQLite reservation or PostgreSQL row lock, or any dropped conditional predicate.

No result from this capsule accepts Phase 4. A complete, attributable 27-row
FULL matrix permits only root package preparation and the separate read-only
`phase4-final-review-4` gate.
