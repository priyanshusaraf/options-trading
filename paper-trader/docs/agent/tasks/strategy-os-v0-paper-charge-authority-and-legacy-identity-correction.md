---
{
  "id": "strategy-os-v0-paper-charge-authority-and-legacy-identity-correction",
  "phase": "v0",
  "status": "accepted_via_fresh_entry_lifecycle_successor",
  "kind": "critical_paper_money_schema_and_historical_identity_correction",
  "goal": "Persist leg-specific Paper charge schedule authority across restart and exits, keep valid risk-reducing Paper exits available for truthful legacy NULL rows, and make each admitted legacy result identity yield one verified v1 answer or refuse before cache reuse or publication.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Additive revision 0045 and the one existing PaperBroker/result-cache paths persist and consume exact per-leg Paper charge authority; historical NULL stays unknown without backfill; collision-valued full/partial positions retain risk-reducing exits after restart; one frozen legacy preimage yields one v1 answer; SQLite/PostgreSQL migration/restore, money conservation, cache/publication, mutations and one fresh independent Critical SPEC/QUALITY review pass."
  },
  "risk_tags": ["critical", "money", "paper-trading", "exit-availability", "restart", "schema", "migration", "historical-identity", "cache-identity", "paper-live-separation"],
  "depends_on": [
    "strategy-os-v0-paper-charge-authority-and-legacy-identity-replan",
    "strategy-os-v0-monitoring-persistence"
  ],
  "dependency_gate": {
    "replan": "strategy-os-v0-paper-charge-authority-and-legacy-identity-replan accepted with successor SHA-256 1f72cb51d9112790162fd2b6c7cc61160c46d57b353b010636ccdb7047781468",
    "immutable_recheck_sha256": "443b4eb6d7012165b8d1af9a1dfda0fd2e3035a1c361907e8c49dff53bb02094",
    "shared_schema": "strategy-os-v0-monitoring-persistence must pass its focused recheck and release shared models/copy/restore/schema-test paths",
    "required_execution_head": "0044",
    "activation_rule": "Root assigns one serial owner only after monitoring acceptance/path release and a fresh collision scan. The owner must query one exact migration head of 0044 before creating 0045; any mismatch or competing 0045 owner stops and replans."
  },
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/report.md", "sections": ["Decision", "Chosen authority model", "Successor boundary", "Dependencies and dispatch gate"]},
    {"path": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/authority-map.md", "sections": ["Current authority flow", "Chosen authority flow", "Legacy NULL exit flow", "Historical compatibility authority"]},
    {"path": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/failure-hypothesis-matrix.md", "sections": ["Failure hypotheses"]},
    {"path": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-replan/deployment-migration-obligations.md", "sections": ["Migration contract", "Deployment and rollback obligations"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-monitoring-persistence.md", "sections": ["V0 monitoring persistence"]},
    {"path": "paper-trader/docs/engineering/decisions/0012-execution-state-ownership.md", "sections": ["2.1 Ownership — who owns which fact", "3. The smallest safe paper/shadow deployment architecture"]},
    {"path": "paper-trader/docs/engineering/decisions/0017-sizing-target-position-and-reservation.md", "sections": ["Decision", "Deterministic policy", "Rollout boundary"]},
    {"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Current verdict", "Open obligations", "V1 release gate"]}
  ],
  "schema_contract": {
    "plane": "execution/user money tables",
    "revision": "0045",
    "migration_path": "paper-trader/backend/migrations/versions/20260830_0045_paper_charge_authority.py",
    "down_revision": "0044",
    "columns": {
      "positions": ["paper_entry_charge_schedule_id VARCHAR(96) NULL", "paper_entry_charge_schedule_address VARCHAR(71) NULL"],
      "trades": ["paper_entry_charge_schedule_id VARCHAR(96) NULL", "paper_entry_charge_schedule_address VARCHAR(71) NULL", "paper_exit_charge_schedule_id VARCHAR(96) NULL", "paper_exit_charge_schedule_address VARCHAR(71) NULL"]
    },
    "null_semantics": "NULL means historical unknown and is never backfilled, inferred or treated as v1/v2",
    "backfill": "none",
    "mixed_writers": "unsupported; writer quiescence is required",
    "downgrade": "refuse; use verified restore or forward repair"
  },
  "allowed_paths": [
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/app/db/copy_contract.py",
    "paper-trader/backend/app/monitoring/repository.py",
    "paper-trader/backend/app/engine/broker.py",
    "paper-trader/backend/app/backtest/identity.py",
    "paper-trader/backend/app/backtest/cache.py",
    "paper-trader/backend/app/backtest/public_computation.py",
    "paper-trader/backend/migrations/versions/20260830_0045_paper_charge_authority.py",
    "paper-trader/backend/tests/test_charge_schedule_correction.py",
    "paper-trader/backend/tests/test_v0_monitoring_migration.py",
    "paper-trader/backend/tests/test_backtest_identity.py",
    "paper-trader/backend/tests/test_backtest_cache.py",
    "paper-trader/backend/tests/test_public_backtest_computation.py",
    "paper-trader/backend/tests/test_schema_migrations.py",
    "paper-trader/backend/tests/test_postgresql_restore_contract.py",
    "paper-trader/backend/tests/test_postgresql_restore_live.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction.md",
    ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction"
  ],
  "new_paths": [
    "paper-trader/backend/migrations/versions/20260830_0045_paper_charge_authority.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction.md",
    ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction"
  ],
  "protected_paths": [
    "paper-trader/backend/app/engine/charges.py",
    "paper-trader/backend/app/engine/live_broker.py",
    "paper-trader/backend/app/engine/runner.py",
    "paper-trader/backend/app/ledger",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/db/restore_contract.py",
    "paper-trader/backend/research",
    "paper-trader/backend/research_tests",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Persist and validate Paper entry schedule id/address on Position and per-leg entry/exit schedule id/address on Trade before any cash, row, money-outbox or cache/publication effect.",
    "Advance the accepted monitoring schema marker compatibility from exact 0044 to the explicit closed set {0044, 0045}; both heads must retain full monitoring table/trigger/CHECK manifest validation, while 0043, 0046, branch, multiple, unknown and malformed heads refuse before repository writes.",
    "Remove expected-label authority and all rounded schedule inference from new Paper effects. A complete id/address pair must match one frozen schedule document; incomplete, unknown or mismatched pairs refuse before effects.",
    "Allow valid full and partial risk-reducing exits for historical NULL-entry Paper Positions without relabelling the entry; persist only the newly selected exit-leg authority and keep entry authority NULL/unknown in the Trade receipt.",
    "Keep v2 integer-paise allocation, owner/account/deployment attribution, reconciliation and structural paper/live separation unchanged. Live calculations and live rows remain on v1 behavior with new Paper authority columns NULL.",
    "Replace caller-supplied legacy base/legs with a frozen, duplicate-refusing exact-preimage manifest lookup in the one canonical identity module. Recompute the old identity and exact v1 answer before admitting compatibility.",
    "Keep current cache/publication identities current-only and reject any legacy compatibility alias, unknown identity, second answer or incomplete manifest before cache reuse or publication.",
    "Extend the shared copy/restore content validator for complete schedule pairs. `restore_contract.py` remains protected unless direct evidence proves the shared validator is insufficient, in which case stop and replan exact ownership."
  ],
  "acceptance": [
    "FH-01 through FH-15 in the sealed replan failure-hypothesis matrix have direct RED-to-GREEN evidence and non-vacuous killed/restored mutations.",
    "No cash, Position, Trade, money outbox, cache or publication effect occurs before new Paper schedule authority is complete and valid.",
    "MonitoringRepository opens on exact compatible heads 0044 and 0045, validates the complete accepted monitoring manifest on both, and refuses every unlisted head or drift before monitoring writes.",
    "Collision-valued full and partial Paper positions reconstruct after restart and always retain a valid risk-reducing exit; expected-label bypass and rounded schedule inference are absent.",
    "Historical NULL entry authority stays NULL through 0044-to-0045 upgrade, close, copy and restore. Receipts state unknown instead of inventing v1/v2, while the newly selected exit leg has exact authority.",
    "Every new Paper Trade has exact exit-leg authority and every known entry leg copies the exact Position authority. Id/address pairs are content-verified on write, read, copy and restore.",
    "Paise conservation and reconciliation pass across full close, partial partitions, restart and retry with one business effect.",
    "Live v1 calculations and rows remain behavior compatible and new Paper authority columns remain NULL for live mode; no live exit or order path is widened.",
    "One legacy identity maps to one frozen answer; duplicate identity, base/preimage mismatch, incomplete manifest, unknown identity and caller-only claims refuse before reuse/publication.",
    "SQLite and disposable PostgreSQL 16 fresh/0044-upgrade/interruption/restart/copy/restore evidence passes, including model/migration agreement and rollback by verified restore/forward repair.",
    "One fresh independent Critical reviewer returns SPEC PASS and QUALITY PASS on the new lineage."
  ],
  "test_plan": [
    "Query actual migration head and path ownership; capture protected hashes and immutable V0-CS-001/V0-CS-003 RED fixtures before product edits.",
    "Run focused schedule-pair, collision, restart, partial-close, risk-reducing-exit, legacy exact-preimage, cache/publication and paper/live separation tests.",
    "Run monitoring repository marker compatibility on 0044 and 0045 plus stale/future/branch/multiple/unknown head refusals and the complete accepted monitoring manifest/mutation controls.",
    "Run SQLite and disposable PostgreSQL fresh/0044-upgrade/interruption/restart/copy/restore/model parity plus affected paper-authority/money/research suites.",
    "Kill and restore expected-label bypass, rounded inference, incomplete pair, legacy duplicate/preimage bypass, NULL backfill and exit-blocking mutations; seal protected bytes and a fresh Critical review package."
  ],
  "parallel_budget": 1,
  "assignments": [
    {
      "id": "nmt004_paper_charge_authority_correction_owner",
      "agent": "worker",
      "model": "gpt-5.6-sol",
      "reasoning_effort": "medium",
      "fork_turns": "none",
      "mode": "write-product-and-evidence",
      "depends_on": [],
      "write_paths": [
        "paper-trader/backend/app/db/models.py",
        "paper-trader/backend/app/db/copy_contract.py",
        "paper-trader/backend/app/monitoring/repository.py",
        "paper-trader/backend/app/engine/broker.py",
        "paper-trader/backend/app/backtest/identity.py",
        "paper-trader/backend/app/backtest/cache.py",
        "paper-trader/backend/app/backtest/public_computation.py",
        "paper-trader/backend/migrations/versions/20260830_0045_paper_charge_authority.py",
        "paper-trader/backend/tests/test_charge_schedule_correction.py",
        "paper-trader/backend/tests/test_v0_monitoring_migration.py",
        "paper-trader/backend/tests/test_backtest_identity.py",
        "paper-trader/backend/tests/test_backtest_cache.py",
        "paper-trader/backend/tests/test_public_backtest_computation.py",
        "paper-trader/backend/tests/test_schema_migrations.py",
        "paper-trader/backend/tests/test_postgresql_restore_contract.py",
        "paper-trader/backend/tests/test_postgresql_restore_live.py",
        "paper-trader/docs/agent/tasks/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction.md",
        ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction"
      ],
      "output": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction/report.md"
    }
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority",
    "routing_note": "Programme-routed Critical implementation uses Sol medium. The user-owned root may retain its selected effort, but no child inherits it."
  },
  "owner_task": "/root/paper_charge_authority_correction",
  "review": {
    "required": true,
    "assignment_id": "nmt004_paper_charge_authority_correction_critical_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Integrated Paper money, risk-reducing exit, shared-schema migration and historical cache identity boundary.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/db/models.py",
      "paper-trader/backend/app/db/copy_contract.py",
      "paper-trader/backend/app/monitoring/repository.py",
      "paper-trader/backend/app/engine/broker.py",
      "paper-trader/backend/app/backtest/identity.py",
      "paper-trader/backend/app/backtest/cache.py",
      "paper-trader/backend/app/backtest/public_computation.py",
      "paper-trader/backend/migrations/versions/20260830_0045_paper_charge_authority.py",
      "paper-trader/backend/tests/test_charge_schedule_correction.py",
      "paper-trader/backend/tests/test_v0_monitoring_migration.py",
      "paper-trader/backend/tests/test_backtest_identity.py",
      "paper-trader/backend/tests/test_backtest_cache.py",
      "paper-trader/backend/tests/test_public_backtest_computation.py",
      "paper-trader/backend/tests/test_schema_migrations.py",
      "paper-trader/backend/tests/test_postgresql_restore_contract.py",
      "paper-trader/backend/tests/test_postgresql_restore_live.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction.md",
      ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/engine/charges.py",
      "paper-trader/backend/app/engine/live_broker.py",
      "paper-trader/backend/app/engine/runner.py",
      "paper-trader/backend/app/ledger",
      "paper-trader/backend/app/providers",
      "paper-trader/backend/app/api",
      "paper-trader/backend/app/db/restore_contract.py",
      "paper-trader/backend/research",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "The read-only replan is accepted; monitoring revision 0044 must pass its focused Critical recheck and release the shared schema paths before root assigns this successor.",
    "The implementation owner must re-query exact head 0044 and confirm no 0045 owner or branch head. Any mismatch stops and replans.",
    "No live IR, live sizing/routing/risk/execution, provider, credential, VPS, frontend or deployment authority follows.",
    "Any need to backfill unknown history, change live behavior, create a second ledger/cache, or overlap an active schema owner stops the slice."
  ],
  "activation_receipt": {
    "monitoring_acceptance_successor_verdict_sha256": "95a4f27ebb10961eefa36156fc92f398078abf0de3fe55da5f039b74c259b208",
    "execution_head_rechecked": "0044",
    "execution_head_log": ".agent/runs/root-v0-convergence/root/monitoring-0044-acceptance-head-recheck.log",
    "revision_0045_absent": true,
    "shared_path_collision": false,
    "owner_task": "/root/paper_charge_authority_correction",
    "monitoring_marker_compatibility_expansion": {
      "authorized_paths": ["paper-trader/backend/app/monitoring/repository.py", "paper-trader/backend/tests/test_v0_monitoring_migration.py"],
      "accepted_heads": ["0044", "0045"],
      "future_heads_allowed": false,
      "reason": "The additive 0045 migration leaves the accepted monitoring manifest unchanged but exact-0044 pinning otherwise refuses the valid current database."
    }
  },
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL / final FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction/review/verdict.json",
    "verdict_sha256": "26ef4116143ab68cd6659f0a45799330656838661accc274f1107ddf1262d85b",
    "finding_ids": ["V0-PCA-CR-001"],
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "Make Trade charge-receipt reconstruction product-aware: options may derive stored entry allocation under the premium-cost contract, while equity/futures/margined products must validate persisted exact entry-charge allocation without applying options-only margin arithmetic.",
    "Add full and partial Paper equity-intraday and futures authority/receipt/restart tests, including remaining-position exit after partial close and stale retry one-effect behavior.",
    "Prove an exact 0044-upgraded historical NULL Position can exit under 0045 without relabelling entry authority, and prove SQLite and PostgreSQL broker restart/reload receipt behavior with known and NULL authority rows.",
    "Rerun paise/reconciliation, paper/live separation, cache/publication, migration/copy/restore and protected gates; reseal the same fresh lineage for the one focused recheck."
  ],
  "focused_recheck": {
    "verdict": "SPEC FAIL / QUALITY FAIL / final FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction/review/recheck-verdict.json",
    "verdict_sha256": "064ea0541651503214f2d11abc4e4308bcac9d890fae8b50db807cf626b029ea",
    "corrected_package_sha256": "dda3e31cafd49ae40150d88be92b9d3d89daeddba893843376ef2dcc5fe66032",
    "closed_findings": ["V0-PCA-CR-001"],
    "open_findings": ["V0-PCA-R1-001"],
    "rechecks_remaining": 0,
    "next_state": "REPLAN_REQUIRED",
    "successor_replan": "strategy-os-v0-paper-entry-lifecycle-identity-replan"
  },
  "terminal_state": {
    "accepted": true,
    "same_lineage_corrections_permitted": false,
    "same_lineage_rechecks_permitted": false,
    "migration_head": "0045",
    "blocking_reason": "Distinct equal-valued Paper entries can share the heuristic lifecycle tuple and be merged during charge-allocation reconstruction.",
    "deployment": false,
    "acceptance_route": "strategy-os-v0-paper-entry-lifecycle-identity-correction"
  },
  "successor_acceptance": {
    "capsule": "strategy-os-v0-paper-entry-lifecycle-identity-correction",
    "verdict": "SPEC PASS / QUALITY PASS / final PASS",
    "verdict_sha256": "531519fa266b1e2bf568461de3d96c360c5a7ef8ea9d0d582837693bf9ab289b",
    "package_sha256": "07f027f311833b39f4446aefda4180e81f9ed3652328ccebb2c0aa5b9fdcac4b",
    "migration_head": "0045",
    "shared_paths_released": true,
    "deployment": false
  },
  "stop_conditions": [
    "Monitoring 0044 is not accepted/released, actual head differs from 0044, a 0045 owner exists, or shared path hashes drift after reservation.",
    "A safe implementation requires relabelling historical NULL, inferring a schedule from rounded money, blocking a risk-reducing Paper exit, or accepting caller-only legacy claims.",
    "A safe implementation requires changing live order/routing/sizing/risk authority, provider/credential access, a second money/cache model, protected restore logic, dependency/lock files, frontend or deployment."
  ],
  "deployment_impact": {
    "classification": "migration-required additive Paper money attribution and current cache/publication hardening",
    "schema_migration": true,
    "dependency_change": false,
    "service_topology_change": false,
    "required_evidence": "Exact 0044-to-0045 expand-contract upgrade, historical NULL preservation, writer quiescence, SQLite/PostgreSQL fresh/upgrade/interruption/copy/restore, model agreement, deterministic build/source identity, rollback by verified restore or forward repair and old-code compatibility before release-owner acceptance.",
    "ceiling": "locally_runnable after named evidence only",
    "release_deployable": false,
    "production_rehearsed": false,
    "deployed": false
  },
  "nonclaims": [
    "No NMT-004 acceptance, public Paper runtime, real contract-note equality, live execution, provider conformance, deployment, production readiness or V0 completion follows until implementation and fresh Critical review pass."
  ]
}
---

# V0 Paper charge authority and legacy identity correction

This fresh implementation lineage is materialized but blocked. It may start only
after monitoring revision 0044 is independently accepted and releases the shared
schema paths, followed by an exact-head and collision recheck. It preserves
historical NULL as unknown, keeps risk-reducing Paper exits available and never
infers charge authority from rounded amounts.

## Implementation evidence receipt

The sole implementation owner completed revision 0045, Paper per-leg schedule
authority, historical NULL risk-reducing exits, frozen legacy result identity,
current cache/publication refusal, shared copy/restore validation and the bounded
monitoring marker compatibility expansion. SQLite and disposable PostgreSQL 16
fresh/0044-upgrade/interruption/restart/copy/restore evidence passes. Ten combined
mutants fail and the restored selected gate passes. Architecture validation checks
418 files with zero failures.

Evidence is rooted at
`.agent/runs/strategy-os-v0-paper-charge-authority-and-legacy-identity-correction/`.
The implementation owner issues no independent SPEC, QUALITY, NMT-004 acceptance,
release, production, live-authority or deployment verdict. The fresh Critical
review remains unlaunched and owns the next decision.

## Evidence-only current-tree reseal receipt

The first implementation package and seal remain immutable superseded lineage:

- package SHA-256 `d3a27fa1c1023386a7603f908aa13a9b72a125f63f38cb28fe51af7d891e7eda`;
- seal SHA-256 `622c6262ae89b741e75b5b6df951d50770bae13de0230be9c79cdd3cdae86a40`;
- sealed whole-tree fingerprint `6b4cc86c2597bac8298cbb4b2169dbd32a7373b82cdb89cbfcee21085505cf5b`.

Root later observed whole-tree fingerprint
`64a59dfde58ba831d08a09bf69244660caf88cedea758c26a4cfa3b7bb8e8e96`
after accepted read-only audit/control documents and platform-queue metadata changed.
The evidence-only reseal owner rechecked all 16 scoped product/test/schema files
and five protected files against the implementation seal: all 21 hashes match.
No product, test, schema, migration, monitoring, broker, charge, cache, restore,
provider, frontend, dependency, lock, live or deployment byte changed during the
reseal. The replacement package and seal are stored alongside, not over, the
superseded artifacts. No reviewer was launched and no deployment occurred.

## V0-PCA-CR-001 correction receipt

The bounded correction preserves immutable first Critical verdict SHA-256
`26ef4116143ab68cd6659f0a45799330656838661accc274f1107ddf1262d85b`.
Trade receipt reconstruction is now product-aware: fully funded options retain
the premium-cost allocation proof, while known Paper equity and futures receipts
validate exact persisted entry-charge slices across sibling Trades and any
remaining Position against the original frozen schedule answer. Paper margined
partial allocations use integer paise; live allocation behavior is unchanged.

Direct evidence now covers full and partial equity/futures receipt reconstruction,
fresh-session restart, remaining Position exit after partial close, stale retry
with one effect, an exact 0044-to-0045 historical NULL Position exit, and
PostgreSQL 16 fresh-session known/NULL authority reconstruction. The options-only
cost mutant fails both equity and futures tests and exact restored bytes pass.
All affected paper/live, cache/publication, migration, copy/restore, monitoring
head, architecture and protected gates pass. The implementation owner does not
issue SPEC or QUALITY, consume the focused recheck, launch a reviewer or deploy.
