---
{
  "id": "strategy-os-v0-monitoring-check-expression-semantics-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_schema_validator_correction",
  "goal": "Harden the one monitoring schema-manifest comparator so exact revision-0044 SQLite and PostgreSQL CHECK semantics preserve grouping and literals, while every same-token regrouping refuses before repository, copy or restore writes.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "The one existing monitoring CHECK comparator uses grouping/literal-preserving conservative comparison across all 112 SQLite and PostgreSQL forms; immutable regrouping and literal-collision probes go RED/GREEN; both dialect mutation matrices, valid-row controls, startup/repository/copy/restore fail-before-write, unchanged 0044 hashes, protected bytes and one fresh independent Critical SPEC/QUALITY review pass."
  },
  "risk_tags": ["critical", "schema-validation", "sqlite", "postgresql", "startup", "copy", "restore", "constraint-semantics"],
  "depends_on": ["strategy-os-v0-monitoring-check-expression-semantics-replan"],
  "dependency_gate": "The read-only replan is accepted with report SHA-256 e2daa86ee6b364e48c4e1f71bfba376ddfd0c970cbc92bc6cf733d15fc0c86ab. The exhausted monitoring-persistence review lineage is immutable and cannot be reused. Revision 0044 and dependent 0045 remain blocked until this fresh correction passes a fresh Critical review.",
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-replan/report.md", "sections": ["Decision", "Observed dialect inventory", "Successor boundary", "Dependency release"]},
    {"path": ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-replan/normalization-decision.md", "sections": ["Decision", "Accepted rewrites", "Rejected designs", "Proof obligations"]},
    {"path": ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-replan/dialect-matrix.md", "sections": ["SQLite 0044", "PostgreSQL 16 0044", "Candidate comparator"]},
    {"path": ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-replan/failure-hypothesis-matrix.md", "sections": ["Failure hypotheses"]},
    {"path": ".agent/runs/strategy-os-v0-monitoring-persistence/review/recheck-verdict.json", "sections": ["all output"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Current verdict", "Open obligations", "V1 release gate"]}
  ],
  "allowed_paths": [
    "paper-trader/backend/app/monitoring/repository.py",
    "paper-trader/backend/tests/test_v0_monitoring_migration.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-check-expression-semantics-correction.md",
    ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-correction"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-check-expression-semantics-correction.md",
    ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-correction"
  ],
  "protected_paths": [
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/migrations/versions/20260829_0044_v0_monitoring.py",
    "paper-trader/backend/migrations",
    "paper-trader/backend/requirements.txt",
    "paper-trader/backend/requirements.lock",
    "paper-trader/backend/tests/test_v0_monitoring_persistence.py",
    "paper-trader/backend/tests/test_schema_migrations.py",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Replace only the CHECK-expression comparison seam with a quote-aware, literal-preserving, pairwise conservative comparator derived from table metadata and the closed observed PostgreSQL 16 deparser forms.",
    "Delete the global all-parentheses, all-whitespace/literal-case, all-double-quote and generic-cast erasures. Preserve exact operators, literal bytes, load-bearing grouping and authoritative casts.",
    "Keep one model-derived manifest and exact comparator. Add no dependency, parser package, second dialect manifest, scratch-schema oracle, arbitrary SQL evaluation, schema/model/migration change or runtime/API/frontend authority.",
    "Add direct tests and evidence only in the named monitoring migration test and evidence directory. Preserve all non-CHECK repository behavior and the five findings already closed by the predecessor review."
  ],
  "acceptance": [
    "Current V0-MP-002-R1 and literal-case/whitespace/quote collision probes are RED on frozen bytes and GREEN only after the comparator correction.",
    "All 112 model-compiled/reflected forms compare on migrated SQLite and disposable PostgreSQL 16 at marker 0044.",
    "Withdrawal, failure-code, nullable-address, timestamp and arithmetic/check same-token regrouping pairs are distinguished on both dialect routes; representative actual-schema mutations refuse at startup/repository/copy/restore before writes.",
    "Whitespace outside literals, metadata-known lowercase quotes, exact PostgreSQL casts, redundant outer wrappers and closed IN/ANY forms compare. Literal case/whitespace, unknown quotes/casts, internal regrouping, reordered terms, changed operators and changed literals refuse.",
    "Valid-row controls preserve current ACTIVE/WITHDRAWN, DELIVERED/FAILED, nullable-address, timestamp and JSON numeric outcomes.",
    "SQLite restores exact database bytes after every mutation. PostgreSQL rolls back every DDL mutation and proves exact raw catalog, rows and marker afterward.",
    "Revision-0044 migration SHA-256 remains e14f8501dd417607ea1d648f06a3d8bd00126e571578b1f1f156ffc19332de9a; raw dialect inventory digests remain bound to the accepted replan evidence.",
    "One fresh Critical review package binds exact files, logs, mutation restoration, protected-byte equality and local-only deployability; independent SPEC and QUALITY both pass."
  ],
  "test_plan": [
    "Run focused comparator unit matrix for all normalization/refusal hypotheses and five same-token regrouping families per dialect.",
    "Run SQLite fresh and exact 0043-upgrade mutation matrix with pre-write counts, marker, valid-row controls, copy gate, exact byte restoration and rerun.",
    "Run disposable PostgreSQL 16 fresh and exact 0043-upgrade mutation matrix with repository/startup/copy/clean-restore gates, valid-row controls, transactional rollback and exact manifest rerun.",
    "Run affected monitoring migration tests and the relevant schema-migration subsystem; kill/restore destructive-normalization and grouping-bypass mutations; seal protected bytes and fresh Critical package."
  ],
  "parallel_budget": 1,
  "assignments": [
    {
      "id": "v0_monitoring_check_expression_semantics_correction_owner",
      "agent": "worker",
      "model": "gpt-5.6-sol",
      "reasoning_effort": "medium",
      "fork_turns": "none",
      "mode": "write-product-and-evidence",
      "depends_on": [],
      "write_paths": [
        "paper-trader/backend/app/monitoring/repository.py",
        "paper-trader/backend/tests/test_v0_monitoring_migration.py",
        "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-check-expression-semantics-correction.md",
        ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-correction"
      ],
      "output": ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-correction/report.md"
    }
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority",
    "routing_note": "Programme-routed Critical implementation uses Sol medium; review remains independent Sol high."
  },
  "owner_task": "/root/monitoring_semantics_correction",
  "review": {
    "required": true,
    "assignment_id": "v0_monitoring_check_expression_semantics_correction_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Shared SQLite/PostgreSQL migration, startup and restore trust boundary.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-correction/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/monitoring/repository.py",
      "paper-trader/backend/tests/test_v0_monitoring_migration.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-check-expression-semantics-correction.md",
      ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-correction"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/db/models.py",
      "paper-trader/backend/migrations",
      "paper-trader/backend/requirements.txt",
      "paper-trader/backend/requirements.lock",
      "paper-trader/backend/tests/test_v0_monitoring_persistence.py",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-correction/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "The accepted replan and exact frozen 0044 inventory authorize only this two-file comparator correction and evidence.",
    "Monitoring persistence 0044 is accepted only after the fresh independent review passes; the unowned 0045 Paper charge successor, monitoring runtime and monitoring API remain blocked until root integration.",
    "No dependency/parser adoption, schema/model/migration change, production database, API/runtime/frontend, execution, money, provider, credential, VPS or deployment authority."
  ],
  "stop_conditions": [
    "A valid-row control proves an actual 0044 CHECK is wrong; stop for a migration replan.",
    "Correctness requires a new parser/dependency, scratch-schema write authority, second dialect manifest or another owner's path.",
    "Safe comparison cannot remain fail-closed on both supported dialects or product/protected hashes drift."
  ],
  "deployment_impact": {
    "classification": "compatible startup/copy/restore validator correction; no schema revision or dependency change",
    "schema_revision_changed": false,
    "required_evidence": "Unchanged 0044 migration/schema hashes, SQLite/PostgreSQL fresh/0043-upgrade/startup/copy/restore mutation matrix, deterministic source identity and rollback by prior application artifact. No deployment claim.",
    "highest_claim": "locally_runnable after fresh review",
    "deployment_authority": false
  },
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL / final FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-correction/review/verdict.json",
    "verdict_sha256": "3b096e76bcaf617eee771367c4dd3c6e1f2d3822e65edeefade340c665ea4b09",
    "finding_ids": ["V0-MCS-CR-001", "V0-MCS-CR-002", "V0-MCS-CR-003"],
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "Make every PostgreSQL deparser rewrite operate only on tokens outside quoted literal spans and bind each accepted rewrite to the exact expected/reflected pair shape; reproduce and close the lifecycle_state::text literal collision.",
    "Parametrize literal case, literal whitespace, known/unknown quote, safe-cast and authoritative-cast acceptance/refusal pairs over both SQLite and PostgreSQL routes, including metadata identifier text inside literals.",
    "Seed a deterministic retained PostgreSQL corpus before every schema mutation and bind the marker, ordered primary-key/row digests and raw catalog manifest before mutation and after rollback.",
    "Rerun all 112 forms, five grouping families, actual-schema/startup/repository/copy/restore gates, mutants and 293-case affected subsystem; reseal the same fresh lineage for the one focused recheck."
  ],
  "focused_recheck": {
    "verdict": "SPEC PASS / QUALITY PASS / final PASS",
    "verdict_path": ".agent/runs/strategy-os-v0-monitoring-check-expression-semantics-correction/review/recheck-verdict.json",
    "verdict_sha256": "95a4f27ebb10961eefa36156fc92f398078abf0de3fe55da5f039b74c259b208",
    "corrected_package_sha256": "ea178bc0292fc8b59e6b98a213d8c2e59a2dc871553f74cdbd4967e17401fbce",
    "corrected_package_seal_sha256": "d7dab904199e0daf16519fd3019b9e7b1ca43fda7919a83d4664a43ff1ac7edd",
    "closed_findings": ["V0-MCS-CR-001", "V0-MCS-CR-002", "V0-MCS-CR-003"],
    "rechecks_remaining": 0
  },
  "nonclaims": [
    "No monitoring 0044 acceptance, 0045 path release, API/runtime/Alerts Inbox, execution, money, deployment, production readiness or V0 completion follows until implementation and fresh Critical review pass."
  ]
}
---

# V0 monitoring CHECK-expression semantics correction

Implement only the conservative comparator and its exact repository validation
tests. Preserve revision 0044 and all monitoring persistence behavior outside
schema comparison.

## Implementation receipt — 2026-08-30

Status: `ready_for_one_focused_critical_recheck`.

After immutable first-review FAIL SHA-256
`3b096e76bcaf617eee771367c4dd3c6e1f2d3822e65edeefade340c665ea4b09`,
the assigned owner corrected V0-MCS-CR-001 through V0-MCS-CR-003. Every
PostgreSQL rewrite now operates on shielded literal spans and exact literal
bytes/order bind the expected/reflected pair before normalization. The direct
matrix covers both dialect routes for five regrouping families and eleven
literal, quote, shield-token, safe-cast, authoritative-cast and unknown-cast
pairs. Every PostgreSQL DDL mutation retains rows in all nine monitoring tables
and proves exact marker, raw manifest, ordered primary-key digest and row digest
after rollback.

Both dialects prove 112/112 current forms, actual schema mutations,
startup/repository/copy/restore refusal, valid-row compatibility and exact
restoration. Grouping, literal-shield and exact reviewer-collision mutants were
killed and restored. The final monitoring persistence/schema subsystem is
293/293 green.

Revision 0044 remains SHA-256
`e14f8501dd417607ea1d648f06a3d8bd00126e571578b1f1f156ffc19332de9a`;
models, migrations, locks, protected tests, control files, frontend, and deploy
bytes match their pre-edit hashes. Deployment impact remains compatible and
local-only. Full evidence is under
`.agent/runs/strategy-os-v0-monitoring-check-expression-semantics-correction/`,
with the owner report at `report.md` and the corrected same-lineage package at
`review-package.json`.

V0-MP-002-R1 and the three first-review findings remain open until the declared
reviewer returns both SPEC PASS and QUALITY PASS on the one permitted focused
recheck. The implementation owner did not launch the reviewer. Monitoring 0044
acceptance, dependent 0045, runtime/API/frontend, execution, money, production,
and deployment remain blocked.
