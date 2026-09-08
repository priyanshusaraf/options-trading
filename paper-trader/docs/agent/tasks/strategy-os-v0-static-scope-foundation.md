---
{
  "id": "strategy-os-v0-static-scope-foundation",
  "phase": "v0",
  "kind": "bounded_parallel_implementation",
  "status": "active",
  "goal": "Persist canonical static research scope revisions",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Real persistent static scope backend with immutable canonical revisions; capability remains closed until serial integration. No fixture-backed watchlist UI. Required local checks and independent SPEC/QUALITY review must pass; protected drift attributed; no release claim."
  },
  "risk_tags": [
    "critical",
    "v0",
    "parallel-owned"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/03-V0-SCOPE-AND-GOLDEN-PATH.md",
      "sections": [
        "Public V0 scope",
        "Canonical V0 objects",
        "V0 signal semantics",
        "Golden path",
        "Instrument-capability matrix",
        "V0 golden five"
      ]
    },
    {
      "path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/05-ARCHITECTURE-AND-RELEASE-PROFILE.md",
      "sections": [
        "Architecture decision",
        "Canonical identities preserved",
        "Chart and annotation architecture",
        "Provider and data architecture",
        "Static scope and future Dynamic Watchlists",
        "Research compatibility",
        "Schema and migration approach",
        "No-rewrite guarantee and limit",
        "Deployment impact"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-frontend-convergence/implementation-sequence.md",
      "sections": [
        "Sequence decision",
        "Capability opening rule",
        "Static watchlist contract",
        "Research robustness contract",
        "Chart contract",
        "Deployment contract"
      ]
    }
  ],
  "dependency_gate": "strategy-os-v0-precision-slate-shell-foundation",
  "programme_assignment": {
    "assignment_id": "v0_static_scope_foundation",
    "parent_stage": "post-phase5-indicator-accuracy-multi-output",
    "primary_programme_owner": false,
    "coordinator": "01a04997-52e4-79c3-ad87-9c896b560920",
    "prerequisite": "Coordinator materializes exact assignment and seals narrow successor orchestration test before START; no repeated user permission."
  },
  "allowed_paths": [
    "paper-trader/backend/app/core/static_scopes.py",
    "paper-trader/backend/app/api/static_scope_routes.py",
    "paper-trader/backend/app/api/product_object_routes.py",
    "paper-trader/backend/app/db/models.py",
    "paper-trader/backend/app/db/planes.py",
    "paper-trader/backend/app/db/copy_contract.py",
    "paper-trader/backend/migrations/versions/20260828_0042_static_instrument_scopes.py",
    "paper-trader/backend/tests/test_static_scopes.py",
    "paper-trader/backend/tests/test_static_scope_routes.py",
    "paper-trader/backend/tests/test_static_scope_migration.py",
    "paper-trader/backend/tests/test_schema_migrations.py",
    "paper-trader/backend/tests/test_db_planes.py",
    "paper-trader/backend/tests/test_postgresql_restore_contract.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-static-scope-foundation.md",
    ".agent/runs/strategy-os-v0-static-scope-foundation"
  ],
  "new_paths": [
    "paper-trader/backend/app/core/static_scopes.py",
    "paper-trader/backend/app/api/static_scope_routes.py",
    "paper-trader/backend/migrations/versions/20260828_0042_static_instrument_scopes.py",
    "paper-trader/backend/tests/test_static_scopes.py",
    "paper-trader/backend/tests/test_static_scope_routes.py",
    "paper-trader/backend/tests/test_static_scope_migration.py"
  ],
  "protected_paths": [
    "AGENTS.md",
    ".codex",
    ".agents",
    "paper-trader/frontend",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/strategy",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/research",
    "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27",
    ".agent/runs/post-phase5-indicator-accuracy-*",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx",
    "paper-trader/backend/app/api/principal.py",
    "paper-trader/backend/tests/test_user_sessions.py",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/tests/test_health_endpoint.py",
    "paper-trader/backend/tests/test_v0_release_profile.py",
    "paper-trader/backend/tests/test_v0_private_diagnostics.py",
    "paper-trader/backend/app/market_truth/identity.py",
    "paper-trader/backend/app/ir/hashing.py",
    "paper-trader/backend/app/api/principal.py",
    "paper-trader/backend/app/core/watchlists.py",
    "paper-trader/backend/app/db/migrate.py",
    "paper-trader/backend/app/db/session.py",
    "paper-trader/backend/migrations/versions/20260825_0041_capital_admission.py",
    "paper-trader/backend/app/core/release_profile.py"
  ],
  "stable_input_hashes": [
    {
      "path": "paper-trader/backend/app/market_truth/identity.py",
      "sha256": "c990e27bcb314f9b9a11d47144374edda2199fae244868184c43602b2f1867b7"
    },
    {
      "path": "paper-trader/backend/app/ir/hashing.py",
      "sha256": "5c1b834af7684cc4c0a7525966cb5497cf723a2d4f4c9a50261bb6beb5053fbf"
    },
    {
      "path": "paper-trader/backend/app/api/principal.py",
      "sha256": "dbf38f6a619fb549d2476e25d5b5e40040ec735b01f6072cd2660a07641fc957"
    },
    {
      "path": "paper-trader/backend/app/core/watchlists.py",
      "sha256": "b0e5a533e3590d280ee02bfaa167e1de47bec9e18c134afc135586db468a86a0"
    },
    {
      "path": "paper-trader/backend/app/db/migrate.py",
      "sha256": "74db77b770548ebccde676ff838f29433da453ae54e8394e647732c23eb939d6"
    },
    {
      "path": "paper-trader/backend/app/db/session.py",
      "sha256": "416445e1130433e91d2d01087acfdb7c5982a3b444ea0a1e012adfa770a758e3"
    },
    {
      "path": "paper-trader/backend/migrations/versions/20260825_0041_capital_admission.py",
      "sha256": "a5c1fb060ed0f8021a16305a842cafebfceb019b0d424547ebd80517f33eb6a3"
    },
    {
      "path": "paper-trader/backend/app/core/release_profile.py",
      "sha256": "bac0d0b76af0711e44d98af7e819cc42db0addce70b6658b251aaca23026b0a5"
    }
  ],
  "scope": [
    "Implement one long-term static research scope service, not a second instrument master: owner + project + opaque scope ID/name and immutable revision snapshots of canonical physical-instrument addresses. Name/presentation are not the semantic membership digest. Use the existing canonical_json/content_address helpers and a schema-discriminated static snapshot document.",
    "Freeze static snapshot contract: non-empty bounded unique canonical physical-instrument addresses, deterministic sorted membership independent of display ordering, owner/project attribution, monotone revision and predecessor, deterministic snapshot address. Validate through load_canonical_instrument; accept no provider symbol/token, strategy key, broker account, deployment, capital or ARM field. Freeze local implementation bounds: 1\u201332 members per snapshot (matching the existing graph-experiment dataset count ceiling), scope name 1\u2013128 characters, opaque ID at most 64 characters, list pages at most 50, and positive revision integers. These are technical safety bounds, not subscription entitlements; larger scopes require a separately tested contract change.",
    "Persist named roots plus immutable revisions in USER tables on existing Base. Owner/project foreign keys stay within USER; MARKET instrument addresses are value references, not cross-plane FKs. Editing creates successor under expected revision/CAS; cannot mutate a used revision. Archive root without deleting historical snapshots. Persist/reload/restore must recompute hashes and reject mismatched owner/predecessor/membership.",
    "Add routes under /api/ir/projects/{project_id}/static-scopes in the existing product router via one included subrouter; preserve action_for_request project read/write semantics and server-derived owner. No principal.py or main.py edits. Guard endpoints with the existing static_watchlists server capability, which stays BLOCKED in this leaf. Service persistence is independently executable now; API feature opening happens only after acceptance and coordinator manifest update. Tests of future-enabled handlers must label the test-only capability override.",
    "Reserve additive revision 0042 only after worker queries the actual Alembic head and coordinator confirms no other schema writer. Preserve research head and every historical migration. Extend total table-plane map and existing copy/restore digest checks. No new database, migration framework, research ledger or provider authority.",
    "No frontend, dataset/run binding change, monitoring assignment, dynamic scope evaluation, registry publication or legacy watchlist mutation. Integration owner later snapshots this exact revision into dataset/experiment/monitoring references without recalculating membership from the editable root."
  ],
  "source_failure_hypothesis": "Existing create_watchlist calls assert_may_execute at core/watchlists.py:24-35 and cannot be reused as research-only scope. No StaticInstrumentScope definition exists in searched app/research source. CanonicalPhysicalInstrument/CanonicalFact already exist (market_truth/identity.py:55-84,198+); USER plane and restore rules require one exclusive schema writer.",
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "fork_turns": "none",
  "owner_gates": [
    "Standing V0 development and parallel-work authority applies; do not ask for a routine token.",
    "No live credentials/providers/orders, VPS, hosting/remote/CI changes, licence-sensitive adoption, production data or deployment.",
    "You are not alone in the codebase. Do not revert others; no stash/reset/clean/rebase/stage/commit. Only named paths; no hidden helper edits.",
    "A critical reviewer may start only after integrated evidence, by the sole coordinator; zero implementation subagents."
  ],
  "test_plan": [
    "Add service RED\u2192GREEN tests for normalization, bounds, noncanonical/unknown instruments, owner/project substitution, CAS contention, idempotency, immutable revisions, archive/readback, canonical digest tamper and deterministic reopen in a fresh process.",
    "Add HTTP tests for versioned/unversioned denied state with actual frozen manifest, plus synthetic enabled-capability tests for two owners/viewer/member permissions, unknown IDs, input bounds and expected-revision conflicts. No execution fields/actions or lease/broker/runner access.",
    "From backend: .venv/bin/python -m pytest -q tests/test_static_scopes.py tests/test_static_scope_routes.py tests/test_static_scope_migration.py tests/test_schema_migrations.py tests/test_db_planes.py tests/test_postgresql_restore_contract.py tests/test_user_plane_tenant_isolation.py tests/test_v0_precision_slate_shell.py tests/test_market_truth_domain.py. Extend existing schema/plane/restore fixtures where natural.",
    "Prove SQLite and real local PostgreSQL16 clean install and 0041\u21920042 upgrade, repeated/interrupted migration, malformed partial schema refusal, two-writer CAS, source/restore row-key-digest verification and compatibility with preserved 0041 money tables. Existing pg_sandbox fixture/runtime only; no shipped databases. Historical capital-schema tests stay unchanged.",
    "Reversible isolated mutations must remove owner filtering or allow revision rewriting and make exact tests fail. Seal migration/model parity and explicit writer-quiescence/forward-repair policy; no destructive downgrade or production rollout."
  ],
  "review": {
    "required": true,
    "assignment_id": "v0_static_scope_foundation_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "One independent integrated critical review after persistence/HTTP/migration/restore evidence. Sol high reason: tenancy, immutable identity and additive schema/recovery boundary.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-static-scope-foundation/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/core/static_scopes.py",
      "paper-trader/backend/app/api/static_scope_routes.py",
      "paper-trader/backend/app/api/product_object_routes.py",
      "paper-trader/backend/app/db/models.py",
      "paper-trader/backend/app/db/planes.py",
      "paper-trader/backend/app/db/copy_contract.py",
      "paper-trader/backend/migrations/versions/20260828_0042_static_instrument_scopes.py",
      "paper-trader/backend/tests/test_static_scopes.py",
      "paper-trader/backend/tests/test_static_scope_routes.py",
      "paper-trader/backend/tests/test_static_scope_migration.py",
      "paper-trader/backend/tests/test_schema_migrations.py",
      "paper-trader/backend/tests/test_db_planes.py",
      "paper-trader/backend/tests/test_postgresql_restore_contract.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/strategy-os-v0-static-scope-foundation/review.md",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "deployment_impact": {
    "classification": "migration-required",
    "prove_now": [
      "Add service RED\u2192GREEN tests for normalization, bounds, noncanonical/unknown instruments, owner/project substitution, CAS contention, idempotency, immutable revisions, archive/readback, canonical digest tamper and deterministic reopen in a fresh process.",
      "Add HTTP tests for versioned/unversioned denied state with actual frozen manifest, plus synthetic enabled-capability tests for two owners/viewer/member permissions, unknown IDs, input bounds and expected-revision conflicts. No execution fields/actions or lease/broker/runner access.",
      "From backend: .venv/bin/python -m pytest -q tests/test_static_scopes.py tests/test_static_scope_routes.py tests/test_static_scope_migration.py tests/test_schema_migrations.py tests/test_db_planes.py tests/test_postgresql_restore_contract.py tests/test_user_plane_tenant_isolation.py tests/test_v0_precision_slate_shell.py tests/test_market_truth_domain.py. Extend existing schema/plane/restore fixtures where natural.",
      "Prove SQLite and real local PostgreSQL16 clean install and 0041\u21920042 upgrade, repeated/interrupted migration, malformed partial schema refusal, two-writer CAS, source/restore row-key-digest verification and compatibility with preserved 0041 money tables. Existing pg_sandbox fixture/runtime only; no shipped databases. Historical capital-schema tests stay unchanged.",
      "Reversible isolated mutations must remove owner filtering or allow revision rewriting and make exact tests fail. Seal migration/model parity and explicit writer-quiescence/forward-repair policy; no destructive downgrade or production rollout."
    ],
    "integration_owner": "strategy-os-v0-zerodha-data-static-scope",
    "release_assembly_owner": "strategy-os-v0-security-operations-deployability",
    "rollback": "No deployment. Compatible changes revert only own code after owner decision; static-scope migration requires writer quiescence and retained readable facts/forward repair, never destructive schema downgrade."
  },
  "stop_conditions": [
    "Unattributed protected drift; shared-contract change outside paths; missing required proof; first compaction handoff before a second.",
    "Any numerical catalogue publication, new authority or external action required to finish must be returned to coordinator, not guessed."
  ],
  "nonclaims": [
    "No implementation acceptance from source reading or draft status.",
    "No indicator, dataset, provider, beta, live or deployment acceptance. No fixture-backed fake product."
  ],
  "acceptance": [
    "Implement one long-term static research scope service, not a second instrument master: owner + project + opaque scope ID/name and immutable revision snapshots of canonical physical-instrument addresses. Name/presentation are not the semantic membership digest. Use the existing canonical_json/content_address helpers and a schema-discriminated static snapshot document.",
    "Freeze static snapshot contract: non-empty bounded unique canonical physical-instrument addresses, deterministic sorted membership independent of display ordering, owner/project attribution, monotone revision and predecessor, deterministic snapshot address. Validate through load_canonical_instrument; accept no provider symbol/token, strategy key, broker account, deployment, capital or ARM field. Freeze local implementation bounds: 1\u201332 members per snapshot (matching the existing graph-experiment dataset count ceiling), scope name 1\u2013128 characters, opaque ID at most 64 characters, list pages at most 50, and positive revision integers. These are technical safety bounds, not subscription entitlements; larger scopes require a separately tested contract change.",
    "Persist named roots plus immutable revisions in USER tables on existing Base. Owner/project foreign keys stay within USER; MARKET instrument addresses are value references, not cross-plane FKs. Editing creates successor under expected revision/CAS; cannot mutate a used revision. Archive root without deleting historical snapshots. Persist/reload/restore must recompute hashes and reject mismatched owner/predecessor/membership.",
    "Add routes under /api/ir/projects/{project_id}/static-scopes in the existing product router via one included subrouter; preserve action_for_request project read/write semantics and server-derived owner. No principal.py or main.py edits. Guard endpoints with the existing static_watchlists server capability, which stays BLOCKED in this leaf. Service persistence is independently executable now; API feature opening happens only after acceptance and coordinator manifest update. Tests of future-enabled handlers must label the test-only capability override.",
    "Reserve additive revision 0042 only after worker queries the actual Alembic head and coordinator confirms no other schema writer. Preserve research head and every historical migration. Extend total table-plane map and existing copy/restore digest checks. No new database, migration framework, research ledger or provider authority.",
    "No frontend, dataset/run binding change, monitoring assignment, dynamic scope evaluation, registry publication or legacy watchlist mutation. Integration owner later snapshots this exact revision into dataset/experiment/monitoring references without recalculating membership from the editable root.",
    "Real persistent static scope backend with immutable canonical revisions; capability remains closed until serial integration. No fixture-backed watchlist UI."
  ],
  "owner_task": "01a049a7-7df8-7d40-8dde-8e466949802d",
  "accepted_replan": {
    "schema": "v0-parallel-leaf-authority/1",
    "replan_seal": ".agent/runs/strategy-os-v0-parallel-workstream-replan/closure-seal.json",
    "replan_seal_sha256": "37fe5c736a1ae169e08be985ec27fcf615b377419977e577da4445ff1da334ec",
    "ownership": ".agent/runs/strategy-os-v0-parallel-workstream-replan/leaf-ownership.json",
    "ownership_sha256": "91a4265c258a515075ed3c2c6d0dbdf86587ecfd8901e7cf7a688d390ad6dfa6",
    "coordinator": "01a04997-52e4-79c3-ad87-9c896b560920",
    "permitted_assignment_ids": [
      "v0_shell_access_revalidation",
      "v0_session_credential_hygiene",
      "v0_private_diagnostics",
      "v0_static_scope_foundation"
    ],
    "maximum_active_owners": 4,
    "primary_stage": "post-phase5-indicator-accuracy-multi-output",
    "numerical_parallel_budget": 0,
    "stage_acceptance": "unchanged serial main programme",
    "public_capability_opening": false,
    "publication": false,
    "deployment": false
  },
  "v0_standing_development_authorization": {
    "date": "2026-08-28",
    "owner_instruction": "bro remove these requirements you have full authority to do as needed to continue developing this application, nothing should stop you from delivering v0. don't stop till the end of v0 now",
    "scope": "Execute the accepted development programme through strategy-os-v0-review, including the isolated pinned reference executor, bounded local corrections, independent assurance, registry/lineage integration, V0 frontend/catalogue implementation, necessary reviewed development dependencies and local test migrations under their declared capsules. Routine repeated authorization phrases are no longer required.",
    "reference_environment_approval": {
      "approved": true,
      "native_core_commit": "2247d599bddf37ed37e3a709371517e46efc66f6",
      "python_wrapper_commit": "a9ff1b47b3ddbd57274116645d688c0ed677338b",
      "version": "0.7.1",
      "isolation": "reference-only local environment; product venv and requirements/locks unchanged by this provisioning",
      "network": "public upstream/package retrieval for the isolated reference build"
    },
    "retained_evidence_gates": [
      "exact scope/ownership and source identity",
      "correctness and complete-array validity proof",
      "independent assurance and required SPEC/QUALITY review",
      "honest refusals and no fabricated parity",
      "deployment readiness evidence before readiness claims"
    ],
    "external_action_boundary": "Development authority does not require or imply orders, money movement, live trading activation, changes to the trading bot/VPS, destructive production data work, paid subscriptions, private-library access, or a live deployment. Do not perform these as a shortcut to V0 development."
  },
  "parallel_development_authorization": {
    "date": "2026-08-28",
    "source_task": "01a04977-e974-7d41-b09d-393159514bc8",
    "owner_instruction": "can we have a parallel workflow running for parts of the application which are unrelated to this indicator verification? i think that overall v0 isn't just gated by indicators there are a lot of steps which can progress without just the nodes as well right lets go ahead with all of them on the side",
    "scope": "Identify and execute accepted V0 work that is independent of indicator correctness, under exact disjoint assignments. Keep numerical evidence, shared identity, frontend truth, independent assurance, convergence and external-action gates. No routine authorization pause.",
    "immediate_assignment": "One read-only architecture owner identifies executable independent leaves and exact shared-contract freezes. Numerical implementation parallelism remains zero.",
    "stage_acceptance": "Main programme acceptance remains serial. Parallel leaves do not advance a dependent stage or consume unpublished indicators. Existing declared-assignment support is used; no second programme controller or scheduler is created."
  },
  "concurrent_ownership": {
    "main_numerical_paths": [
      "paper-trader/backend/app/ir/first_party/analytical_v2/multi_output.py",
      "paper-trader/backend/tests/test_indicator_accuracy_multi_output.py"
    ],
    "peer_paths": {
      "v0_shell_access_revalidation": [
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
        "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx",
        "paper-trader/docs/agent/tasks/strategy-os-v0-shell-access-revalidation.md",
        ".agent/runs/strategy-os-v0-shell-access-revalidation"
      ],
      "v0_session_credential_hygiene": [
        "paper-trader/backend/app/api/principal.py",
        "paper-trader/backend/tests/test_user_sessions.py",
        "paper-trader/docs/agent/tasks/strategy-os-v0-session-credential-hygiene.md",
        ".agent/runs/strategy-os-v0-session-credential-hygiene"
      ],
      "v0_private_diagnostics": [
        "paper-trader/backend/app/main.py",
        "paper-trader/backend/tests/test_health_endpoint.py",
        "paper-trader/backend/tests/test_v0_release_profile.py",
        "paper-trader/backend/tests/test_v0_private_diagnostics.py",
        "paper-trader/docs/agent/tasks/strategy-os-v0-private-diagnostics.md",
        ".agent/runs/strategy-os-v0-private-diagnostics"
      ]
    },
    "rule": "Protected means do not write. Peers may change exactly their named paths; record hashes and attribution, preserve interface freezes, and reconcile unexplained drift. Never restore another owner."
  },
  "migration_slot": {
    "source_head_observed": "0041",
    "reserved_successor": "0042",
    "sole_schema_owner": "v0_static_scope_foundation",
    "head_evidence": ".agent/runs/post-phase5-indicator-accuracy-multi-output/coordinator/reserved-migration-head.log",
    "required_before_edit": "Requery the actual head in the sanitized environment; stop on a mismatch. No production migration."
  },
  "routing_seal": ".agent/runs/post-phase5-indicator-accuracy-multi-output/coordinator/parallel-routing-seal.json"
}
---

# Persist canonical static research scope revisions

Materialized from the sealed independent V0 dependency replan under standing authority. Await the exact owner assignment and START. Development is parallel; feature opening and final acceptance remain separate.

## Implementation note: bounded route materialization

Coordinator 01a04997-52e4-79c3-ad87-9c896b560920 explicitly accepted public
`add_api_route` materialization of this one six-endpoint module on 2026-08-29.
Installed FastAPI lazy `include_router` is not traversed by the existing direct
APIRoute version mirror. The original /api/v1 404 is retained in
`.agent/runs/strategy-os-v0-static-scope-foundation/owner/routes-first.log`.
No generic cloning helper, main.py or versioning.py change is authorized. The
original capsule bytes remain in this task's baseline copy.

The protected historical `test_capital_admission_schema.py` clean-init pin stays
at 0041. Record its current-head incompatibility without silently skipping or
weakening the test. Current-source release test reconciliation belongs to
`strategy-os-v0-security-operations-deployability` before that capsule's acceptance.

Opaque static IDs use `scope.` plus a URL-safe suffix (total at most 64). This
prevents route-family words such as `review`, `graphs`, `layouts`, `experiments`
and `status` from changing the unchanged principal path parser's project actions.
The default ID is `scope.<uuid4 hex>`. Unprefixed client IDs fail validation.

## Unresolved shared authorization mapping gate

The expanded 358-case HTTPX/ASGI mapping receipt found116 matched-route action
family mismatches, including valid legacy Project IDs such as `review`. The
coordinator confirmed a separate serial correction in principal.py/test_api_auth.py
with another implementation owner and independent review. This owner will not
narrow Project IDs or change those protected files. Static source/interfaces are
frozen at `final-test-source-hashes-v3.json` (SHA46922441ef1773ebecbb5791be3147bedeeda17dee96bbe85cad5feb351f67ac).
Persistence/subsystem evidence is398 PASS; mapping acceptance and this slice's
independent SPEC/QUALITY acceptance remain open. Capability remains BLOCKED.

## Accepted shared correction and local integration

On resumption by coordinator01a04a11-4342-7ae0-97cf-95c27ee7ef37, the shared
authorization correction closure c37680cb0b20435e58297a77b370f2e643c1153a73097f52b21e1dd75abcb3f1
and coordinator acceptance f0e370e554e738c6ac53d9845950133d5d67cf9e5203444de52658938d2b1fd5
were verified with actual independent SPEC/QUALITY PASS and259-test XML.
All13 static inputs stayed frozen. Local integration revalidation passed
146 HTTP/policy tests and all358 mapping vectors (zero matched-route action
mismatches). Historical RED mapping/copy/head artifacts remain unchanged.
Integrated local report: `.agent/runs/strategy-os-v0-static-scope-foundation/integrated-report.md`.
Independent static SPEC/QUALITY acceptance remains pending; no capability opens.
