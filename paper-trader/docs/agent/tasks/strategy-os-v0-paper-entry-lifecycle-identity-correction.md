---
{
  "id": "strategy-os-v0-paper-entry-lifecycle-identity-correction",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_paper_entry_lifecycle_identity_and_charge_allocation_correction",
  "goal": "Make the existing ExecutionIntent client_intent_id the mandatory unique durable identity of every new Paper entry, copy it to the Position and every Trade slice, reconstruct charge allocation only through that identity, and preserve truthful legacy NULL with risk-reducing exits available.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "The immutable V0-PCA-R1-001 counterexample is GREEN for Paper options, equity and futures; manual and strategy opens persist distinct intents; full, partial, remainder, retry, concurrency, restart, copy and restore preserve exact identity and paise; historical NULL is unchanged and exits remain available; amended single-head 0045 and one fresh Critical SPEC/QUALITY review pass."},
  "risk_tags": ["critical", "paper-money", "entry-intent", "lifecycle-identity", "partial-close", "restart", "concurrency", "schema", "migration", "historical-null"],
  "depends_on": ["strategy-os-v0-paper-entry-lifecycle-identity-replan"],
  "dependency_gate": {
    "required_replan": "strategy-os-v0-paper-entry-lifecycle-identity-replan accepted",
    "immutable_predecessor_recheck_sha256": "064ea0541651503214f2d11abc4e4308bcac9d890fae8b50db807cf626b029ea",
    "migration_lineage": "One unaccepted 0045 has down_revision 0044; no accepted/deployed rejected-0045 database and no competing schema owner.",
    "activation_rule": "One serial owner may amend unaccepted 0045 after confirming exact source head 0045/down 0044, target DB head 0044 or clean install, writer quiescence, backup readiness and no 0046/branch."
  },
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/report.md", "sections": ["Decision", "Chosen lifecycle contract", "Successor boundary", "Stopping condition"]},
    {"path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/authority-map.md", "sections": ["Current authority and state flow", "Chosen authority flow", "Legacy NULL exit flow", "Object meaning and ownership"]},
    {"path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/failure-hypothesis-matrix.md", "sections": ["Failure hypothesis and proof matrix"]},
    {"path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/deployment-migration-obligations.md", "sections": ["Unaccepted 0045 amendment", "Copy and restore", "Mixed version and cutover", "Rollback and forward recovery"]},
    {"path": "paper-trader/docs/engineering/decisions/0018-position-campaign-tranche-lineage.md", "sections": ["Decision", "Invariants", "Legacy rows and migration", "Required evidence"]}
  ],
  "schema_contract": {
    "plane": "execution money", "revision": "0045", "down_revision": "0044", "new_revision_forbidden": true, "new_lifecycle_table_or_column": false,
    "canonical_identity": "execution_intents.client_intent_id",
    "existing_links": ["positions.entry_intent_id nullable FK execution_intents.client_intent_id ON DELETE RESTRICT", "trades.entry_intent_id nullable FK execution_intents.client_intent_id ON DELETE RESTRICT"],
    "amended_checks": ["positions: mode != 'paper' OR paper_entry_charge_schedule_id IS NULL OR entry_intent_id IS NOT NULL", "trades: mode != 'paper' OR paper_entry_charge_schedule_id IS NULL OR entry_intent_id IS NOT NULL"],
    "legacy_null": "Preserve NULL entry_intent_id and NULL entry schedule authority exactly; no backfill or inference.",
    "uniqueness": "ExecutionIntent primary key is global. One intent is created per new Paper entry; supplied/replayed intent refuses when any Position or Trade already references it.",
    "stale_same_revision": "Rejected-0045 catalog without amended constraints refuses; restore exact 0044 or clean rebuild under owner direction.",
    "mixed_writers": "unsupported", "downgrade": "refuse; verified pre-write restore or owner-directed forward repair"
  },
  "scope": [
    "Create one existing ExecutionIntent at the Paper broker entry seam after exact admission validation and before capital/Position mutation; it is lifecycle identity, not new execution authority.",
    "Cover strategy/manual options, equity and futures without changing runner or API authority; add entry_intent_id to the existing futures broker seam.",
    "Copy intent ID to Position and every full/partial Trade; preserve it on remainder and stop/target reinforcement.",
    "Group current Paper charge reconstruction only by non-NULL intent ID; scope facts validate but never become fallback identity.",
    "Bump Paper receipt scheme to v2 and include entry_intent_id plus lifecycle state; add no second lifecycle address.",
    "Refuse intent reuse before money mutation, including after full close and same-intent concurrency; different intents never merge.",
    "Legacy NULL skips sibling aggregation, remains explicit unknown and permits full/partial/remaining risk-reducing exits.",
    "Amend only unaccepted 0045 and prove clean/0044 upgrade, stale rejected-0045 refusal, copy/restore, restart and mixed-version gates.",
    "Do not create/infer PositionCampaign, PositionTranche or FillAllocation or synthesize broker events merely to obtain identity."
  ],
  "acceptance": [
    "Exact reviewer fixture plus options/equity/futures variants prove independent equal-valued entries get different non-NULL intents and reconstruct after restart.",
    "Same intent across partial Trades and remaining Position reconstructs one lifecycle with exact quantity/paise; remaining full close keeps the ID.",
    "Same-intent sequential/concurrent reuse yields one effect and deterministic replay/refusal; different intents never merge.",
    "Manual and strategy paths converge at Paper broker; live broker, runner, API and ADR 0018 lineage stay unchanged.",
    "Known-schedule current Paper rows require an existing intent FK; cross-owner/account/deployment/content mismatches refuse before effects.",
    "Exact 0044 legacy rows retain NULL through migration/copy/restore; full/partial exits remain available and no receipt scans sibling NULL rows.",
    "Receipt v2 changes when intent changes and is stable across sessions/restore.",
    "SQLite/PostgreSQL prove amended 0045 model/catalog, stale rejected-0045 refusal, interruption, restart, concurrency, copy/restore and mutations.",
    "One fresh Critical reviewer returns SPEC PASS and QUALITY PASS."
  ],
  "test_plan": [
    "Run immutable V0-PCA-R1-001 RED then options/equity/futures and manual/strategy equal-value variants.",
    "Run lifecycle identity, full/partial/remainder, reinforcement, stale retry, restart, two-owner/account/deployment and receipt-address tests.",
    "Run same/different-intent concurrency on SQLite/PostgreSQL including generated-ID collision retry.",
    "Run 0044-to-amended-0045, clean install, interruption, stale rejected-0045 refusal, model parity, monitoring marker, copy and restore.",
    "Kill/restore intent generation/copy/reuse/scope/schema/receipt/legacy-exit mutations and affected Paper money/execution/migration suites."
  ],
  "allowed_paths": [
    "paper-trader/backend/app/db/models.py", "paper-trader/backend/app/db/copy_contract.py", "paper-trader/backend/app/engine/broker.py", "paper-trader/backend/migrations/versions/20260830_0045_paper_charge_authority.py",
    "paper-trader/backend/tests/test_charge_schedule_correction.py", "paper-trader/backend/tests/test_execution_lifecycle.py", "paper-trader/backend/tests/test_execution_lifecycle_recovery.py", "paper-trader/backend/tests/test_manual_broker.py", "paper-trader/backend/tests/test_routes_manual.py", "paper-trader/backend/tests/test_equity_partial_close.py", "paper-trader/backend/tests/test_futures_entries.py", "paper-trader/backend/tests/test_futures_lifecycle.py", "paper-trader/backend/tests/test_schema_migrations.py", "paper-trader/backend/tests/test_postgresql_restore_contract.py", "paper-trader/backend/tests/test_postgresql_restore_live.py", "paper-trader/backend/tests/test_v0_monitoring_migration.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-paper-entry-lifecycle-identity-correction.md", ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-correction"
  ],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-paper-entry-lifecycle-identity-correction.md", ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-correction"],
  "protected_paths": [
    "paper-trader/backend/app/engine/live_broker.py", "paper-trader/backend/app/engine/runner.py", "paper-trader/backend/app/engine/execution_lifecycle.py", "paper-trader/backend/app/engine/charges.py", "paper-trader/backend/app/execution/position_lineage.py", "paper-trader/backend/app/db/restore_contract.py", "paper-trader/backend/app/ledger", "paper-trader/backend/app/providers", "paper-trader/backend/app/api", "paper-trader/backend/research", "paper-trader/backend/research_tests", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"
  ],
  "parallel_budget": 1,
  "assignments": [{
    "id": "v0_paper_entry_lifecycle_identity_correction_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-product-test-schema-and-evidence", "depends_on": [],
    "write_paths": ["paper-trader/backend/app/db/models.py", "paper-trader/backend/app/db/copy_contract.py", "paper-trader/backend/app/engine/broker.py", "paper-trader/backend/migrations/versions/20260830_0045_paper_charge_authority.py", "paper-trader/backend/tests/test_charge_schedule_correction.py", "paper-trader/backend/tests/test_execution_lifecycle.py", "paper-trader/backend/tests/test_execution_lifecycle_recovery.py", "paper-trader/backend/tests/test_manual_broker.py", "paper-trader/backend/tests/test_routes_manual.py", "paper-trader/backend/tests/test_equity_partial_close.py", "paper-trader/backend/tests/test_futures_entries.py", "paper-trader/backend/tests/test_futures_lifecycle.py", "paper-trader/backend/tests/test_schema_migrations.py", "paper-trader/backend/tests/test_postgresql_restore_contract.py", "paper-trader/backend/tests/test_postgresql_restore_live.py", "paper-trader/backend/tests/test_v0_monitoring_migration.py", "paper-trader/docs/agent/tasks/strategy-os-v0-paper-entry-lifecycle-identity-correction.md", ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-correction"],
    "output": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-correction/report.md"
  }],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root/paper_entry_lifecycle_correction",
  "review": {
    "required": true, "assignment_id": "v0_paper_entry_lifecycle_identity_correction_critical_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Integrated Paper money identity, restart/concurrency, legacy exit and amended migration boundary.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-correction/review-package.json",
    "review_paths": ["paper-trader/backend/app/db/models.py", "paper-trader/backend/app/db/copy_contract.py", "paper-trader/backend/app/engine/broker.py", "paper-trader/backend/migrations/versions/20260830_0045_paper_charge_authority.py", "paper-trader/backend/tests/test_charge_schedule_correction.py", "paper-trader/backend/tests/test_execution_lifecycle.py", "paper-trader/backend/tests/test_execution_lifecycle_recovery.py", "paper-trader/backend/tests/test_manual_broker.py", "paper-trader/backend/tests/test_routes_manual.py", "paper-trader/backend/tests/test_equity_partial_close.py", "paper-trader/backend/tests/test_futures_entries.py", "paper-trader/backend/tests/test_futures_lifecycle.py", "paper-trader/backend/tests/test_schema_migrations.py", "paper-trader/backend/tests/test_postgresql_restore_contract.py", "paper-trader/backend/tests/test_postgresql_restore_live.py", "paper-trader/backend/tests/test_v0_monitoring_migration.py", "paper-trader/docs/agent/tasks/strategy-os-v0-paper-entry-lifecycle-identity-correction.md", ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-correction"],
    "exclude_paths": ["paper-trader/backend/app/engine/live_broker.py", "paper-trader/backend/app/engine/runner.py", "paper-trader/backend/app/engine/execution_lifecycle.py", "paper-trader/backend/app/engine/charges.py", "paper-trader/backend/app/execution/position_lineage.py", "paper-trader/backend/app/db/restore_contract.py", "paper-trader/backend/app/ledger", "paper-trader/backend/app/providers", "paper-trader/backend/app/api", "paper-trader/backend/research", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"],
    "output": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-correction/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1
  },
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL / final FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-correction/review/verdict.json",
    "verdict_sha256": "44513a1043fe1b92ba157282d399bd9d451eed19521d54119e0648454dc08fc0",
    "finding_ids": ["V0-PELI-CR-001", "V0-PELI-CR-002", "V0-PELI-EG-001"],
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "Make Position.entry_intent_id and Trade.entry_intent_id immutable after insert at the SQLite and PostgreSQL database boundary; direct SQL NULL/non-NULL/equal-content rebind attempts must refuse and restore exactly. Historical NULL remains NULL and is never inferred.",
    "Close V0-PELI-CR-001 by proving the original intent remains durably consumed after any attempted Position/Trade rebind, including full close/restart and same-intent sequential/concurrent retry.",
    "For an exact owned risk-reducing exit, treat lifecycle receipt quantity/scope corruption as an unavailable receipt and logged integrity fault, not as permission to block the close or invent attribution. Entry/new-money paths remain fail-closed.",
    "Add options/equity/futures full/partial/remaining exit tests for corrupted intent quantity/scope and prove one money effect, exact paise/reconciliation and unavailable receipt semantics.",
    "Seal actual protected-file hashes inside the named evidence manifest/package, rerun SQLite/real PostgreSQL migration/trigger/restore plus affected suites and mutations, and reseal for the one focused recheck."
  ],
  "focused_recheck": {
    "verdict": "SPEC PASS / QUALITY PASS / final PASS",
    "verdict_path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-correction/review/recheck-verdict.json",
    "verdict_sha256": "531519fa266b1e2bf568461de3d96c360c5a7ef8ea9d0d582837693bf9ab289b",
    "corrected_package_sha256": "07f027f311833b39f4446aefda4180e81f9ed3652328ccebb2c0aa5b9fdcac4b",
    "corrected_package_seal_sha256": "69f9e7a62537f85bef0f3ccdf9b7168be1b27fdd5d9c4e10b413ee23208ae732",
    "closed_findings": ["V0-PELI-CR-001", "V0-PELI-CR-002", "V0-PELI-EG-001"],
    "rechecks_remaining": 0,
    "deployment": false
  },
  "owner_gates": [
    "Root accepted the replan and confirmed one exact unaccepted 0045 schema owner.",
    "Accepted/deployed rejected-0045 DB, competing migration, second identity, PositionCampaign repurposing, historical inference or 0046/branch stops for owner direction.",
    "No live IR/sizing/routing/risk/execution, provider, credential, VPS, frontend, production or deployment authority.",
    "Risk-reducing exits remain available."
  ],
  "stop_conditions": ["Safe identity requires a second execution/deployment/current-position authority.", "Legacy correctness requires inferred/backfilled identity or blocks a risk-reducing exit.", "Correction requires 0046/branch, live behavior, protected paths or overlapping schema ownership.", "Exact 0044/clean-install provenance cannot be established."],
  "deployment_impact": {"classification": "migration-required amended unaccepted 0045 plus Paper runtime identity", "required_evidence": "Exact single-head 0045/down-0044; quiescence; stale rejected-0045 refusal; clean/0044 upgrade; SQLite/PostgreSQL interruption/restart/concurrency/copy/restore; build/schema compatibility; verified backup; restore/forward repair; fresh Critical review.", "ceiling": "locally runnable after named evidence only", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No 0045/NMT-004 acceptance, public Paper runtime, campaign/tranche activation, live execution, provider conformance, frontend acceptance, release deployability, production readiness, deployment or V0 completion until implementation and fresh Critical review pass."]
}
---

# V0 Paper entry lifecycle identity correction

Amend only the unaccepted 0045 lineage so every new Paper entry has one durable
ExecutionIntent identity. Preserve historical NULL and risk-reducing exits.
