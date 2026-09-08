---
{
  "id": "phase1-4-foundation-postgresql16-semantic-authority-cleanup-recovery",
  "phase": "interphase-4-5",
  "status": "ready",
  "goal": "Implement fresh PostgreSQL 16 semantic-authority evidence under the recovered closed lifecycle, deletion, containment, and durable-claim contracts without reusing or patching S15.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after the fresh collector and all database-free gates pass, root accepts the pre-database same-byte package, root separately authorizes every PostgreSQL invocation, and the authorized run produces complete exact evidence; otherwise return BLOCKED."
  },
  "risk_tags": ["critical", "postgresql", "migration-evidence", "lifecycle-cleanup", "secret-containment"],
  "dependency_gate": "root-same-byte-acceptance-and-explicit-activation-of-phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery",
  "required_docs": [
    {
      "path": "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery.md",
      "sections": ["PostgreSQL 16 cleanup repeated-failure recovery"]
    },
    {
      "path": "paper-trader/docs/agent/DEPLOYABILITY.md",
      "sections": ["Foundation migration and numeric correction", "Foundation blockers"]
    },
    {
      "path": "paper-trader/docs/agent/DEFECT_PATTERNS.md",
      "sections": ["Status and evidence rules", "DP-003 — Mocked seam presented as lifecycle evidence", "DP-010 — Current-head or hybrid fixtures presented as supported-old migration evidence"]
    }
  ],
  "architecture_inputs": {
    "status_authority": ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/status-authority-contract.json",
    "cleanup_state_machine": ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/cleanup-state-machine.json",
    "redaction_and_persistence": ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/redaction-and-persistence-contract.json",
    "negative_registry": ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/actual-branch-negative-matrix.json"
  },
  "root_activation": {
    "acceptance": ".agent/runs/phase1-4-foundation-critical-closure/postgresql16-semantic-authority-cleanup-repeated-failure-recovery-acceptance.json",
    "acceptance_sha256": "4051eacfd4759d63af74080fbd0668d22ee725a50c64884b6ef1db24e8b925d8",
    "preactivation_capsule_sha256": "66d2dc7c8c8ae25e1041a3b73af757d4362d1550ca0cdb2314ee622a5d3c9df1",
    "database_free_work_authorized": true,
    "postgresql_invocation_authorized": false
  },
  "allowed_paths": [
    "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql16-semantic-authority-cleanup-recovery.md",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-recovery"
  ],
  "read_only_paths": [
    ".git",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery",
    ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery",
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/tasks/phase1-4-foundation-critical-closure.md"
  ],
  "execution_contract": {
    "fresh_assignment": "foundation_postgresql16_semantic_authority_cleanup_recovery_owner",
    "attempt_limit": {"initial_patch": 1, "bounded_repair": 1},
    "children": 0,
    "failed_s15_bytes_may_be_modified_or_imported": false,
    "pre_database_root_audit_required": true,
    "root_authorization_required_before_each_postgresql_invocation": true,
    "database_command_default": "forbidden_until_exact_root_authorization",
    "closed_status_algebra": {"0": "RUNNING", "3": "ABSENT", "every_other_result": "OBSERVATION_FAILED"},
    "cleanup_claim_rule": "derive only after exact absence, typed durable intent receipts, identity-bound dirfd deletion, typed post-delete and final absence receipts, durable false-claim removal fact, and independent readback validation",
    "frozen_target_authority": "The controlled creator captures the exact target dev/inode/path into immutable DeletionBoundary.expected_target_identity before any simulated start and before locator readiness. Initial, prepared, ready, observer, and dirfd-delete checks consume that frozen identity; cleanup observations never establish expected authority.",
    "absence_observer": {"source": ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-repeated-failure-recovery/foundation_postgresql16_semantic_authority_cleanup_repeated_failure_architect/proposed_successor_cleanup.py", "sha256": "72b1be42b44d281a7134cdf711e7be3333f2737c35a5e7ca3cd4dbc2421fdf92", "required_behavior": "O_NOFOLLOW-open frozen parent, fstat exact frozen parent dev/inode, stat exact child component by that dirfd without following symlinks, accept ABSENT only for child ENOENT, require ordered independently constructed POST_DELETE and PRE_FINAL_CLAIM receipts"}
  },
  "tests": [
    "Revalidate all architecture-input and protected hashes before work and at every root gate.",
    "Implement a fresh collector under the new ignored run path; do not copy or patch S15.",
    "Run the closed database-free mutation registry through the actual fresh collector branch before requesting PostgreSQL authority.",
    "Prove exact command, executable digest, locator, namespace, parent inode, target inode, sentinel, timeout, transcript, two-secret raw/hex, atomic durability, and final claim bindings.",
    "Submit an exact pre-database package to root and stop. Invoke PostgreSQL only after a separate exact root authorization for that command and run.",
    "Run scope, repository architecture, diff-check, report/manifest, protected hash, and same-byte validations."
  ],
  "test_plan": [
    "Rebuild the collector from fresh bytes under the successor run path and execute the inherited closed database-free registry through its actual cleanup branch.",
    "Submit exact hashes and database-free results to root; stop before every PostgreSQL command until root authorizes that exact invocation.",
    "Retain failed diagnostics and reject any result that cannot prove the frozen command, namespace, containment, durability, observation, and claim bindings."
  ],
  "acceptance": [
    "The fresh actual collector branch rejects every inherited database-free mutation without importing or patching failed S15 code.",
    "Root accepts the exact pre-database package and separately authorizes each PostgreSQL invocation before it occurs.",
    "The authorized evidence run, scope checks, repository architecture, report, manifest, and final same-byte validation all pass without product or runtime changes."
  ],
  "stop_conditions": [
    "Any status other than exact identity-bound exit 3 can authorize absence, deletion, or cleanup success.",
    "Any observer uses pathname disappearance without an O_NOFOLLOW parent dirfd bound to the frozen parent identity.",
    "Any secret, persistence, deletion, observation, or claim mutation escapes rejection.",
    "Any PostgreSQL command lacks separate exact root authorization, or any failed S15/product/runtime byte would be changed."
  ],
  "owner_gates": [
    "Stop before any PostgreSQL or server executable until root authorizes that exact invocation.",
    "Stop if the frozen disposable parent/namespace/ownership identity is unavailable or derived from the observed target.",
    "Stop if any status other than exact exit 3 could authorize absence or deletion.",
    "Stop if any false-claim intent or removal fact lacks atomic write, file fsync, rename, parent fsync, and independent readback evidence.",
    "Stop before product, test, schema, migration, runtime, dependency, configuration, service, provider, frontend, deployment, production, live, order, or money changes."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority",
    "fresh_owner_required": true,
    "assignment_id": "foundation_postgresql16_semantic_authority_cleanup_recovery_owner"
  },
  "parallel_budget": 0,
  "assignments": [],
  "review": {
    "required": false,
    "assignment_id": "foundation_postgresql16_semantic_authority_cleanup_recovery_review",
    "base_sha": "HEAD",
    "review_paths": [
      "paper-trader/docs/agent/tasks/phase1-4-foundation-postgresql16-semantic-authority-cleanup-recovery.md",
      ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-cleanup-recovery"
    ],
    "exclude_paths": [
      ".agent/runs/phase1-4-foundation-postgresql16-semantic-authority-recovery",
      "paper-trader/backend",
      "paper-trader/frontend"
    ]
  },
  "deployment_impact": {
    "classification": "evidence-only; downstream migration evidence correction",
    "highest_claim": "none until root-authorized evidence passes",
    "deployable": false,
    "product_runtime_unchanged": true
  },
  "nonclaims": [
    "Activation does not accept S14, S15, PostgreSQL semantics, migration behavior, native-state behavior, deployability, release, production, live, order, or money claims.",
    "Database-free success cannot substitute for the separately root-authorized PostgreSQL evidence run."
  ]
}
---

# PostgreSQL 16 semantic-authority cleanup recovery

This fresh successor implements the recovered authority once, submits database-free evidence for root audit, and stops at every PostgreSQL authorization gate.
