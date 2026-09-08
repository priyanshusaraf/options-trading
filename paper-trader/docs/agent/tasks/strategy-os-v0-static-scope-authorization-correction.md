---
{
  "id": "strategy-os-v0-static-scope-authorization-correction",
  "phase": "v0",
  "kind": "bounded_parallel_implementation",
  "status": "active",
  "goal": "Correct static-scope request action classification without narrowing Project IDs",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "All declared static-scope route/action mappings and actual authorization regressions pass with unchanged non-static/credential semantics, isolated guard mutation, exact protected-byte proof and independent SPEC/QUALITY PASS. No capability/deployment opening."
  },
  "risk_tags": [
    "critical",
    "v0",
    "parallel-owned"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/06-TEST-SECURITY-DATA-AND-DEPLOYMENT-GATES.md",
      "sections": [
        "V0 test matrix",
        "Security findings",
        "Data and licensing gates",
        "V0 deployment topology to prove",
        "Deployability gates"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-static-scope-foundation/path-mapping.json",
      "sections": [
        "schema",
        "product_requests_executed",
        "routes",
        "cases",
        "mismatches",
        "unmatched",
        "conclusion"
      ]
    }
  ],
  "dependency_gate": "strategy-os-v0-precision-slate-shell-foundation",
  "programme_assignment": {
    "assignment_id": "v0_static_scope_authorization",
    "parent_stage": "post-phase5-indicator-accuracy-multi-output",
    "primary_programme_owner": false,
    "coordinator": "01a04997-52e4-79c3-ad87-9c896b560920",
    "prerequisite": "Coordinator materializes exact assignment and seals narrow successor orchestration test before START; no repeated user permission."
  },
  "allowed_paths": [
    "paper-trader/backend/app/api/principal.py",
    "paper-trader/backend/tests/test_api_auth.py",
    "paper-trader/backend/app/main.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-static-scope-authorization-correction.md",
    ".agent/runs/strategy-os-v0-static-scope-authorization-correction"
  ],
  "new_paths": [],
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
    "paper-trader/backend/tests/test_health_endpoint.py",
    "paper-trader/backend/tests/test_v0_release_profile.py",
    "paper-trader/backend/tests/test_v0_private_diagnostics.py",
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
    "paper-trader/backend/app/api/auth.py",
    "paper-trader/backend/tests/test_user_sessions.py",
    "paper-trader/backend/app/api/versioning.py"
  ],
  "stable_input_hashes": [
    {
      "path": "paper-trader/backend/app/api/principal.py",
      "sha256": "2ac5312fa2795d10f7f6b5a4d54c42761287c54ef1f4e21a74d698e95f65be15"
    },
    {
      "path": "paper-trader/backend/app/main.py",
      "sha256": "6cfc9b72cefcde83a60fa640013fc10277a0b4ecef26975c5c45faaf749fed8e"
    },
    {
      "path": "paper-trader/backend/app/api/versioning.py",
      "sha256": "116c5240cdb393b61e5b2fead686f9750ad169012ba1079ed3a9b7cded8bd263"
    },
    {
      "path": "paper-trader/backend/app/api/static_scope_routes.py",
      "sha256": "435b446db7ce07f89639f1e3dc75d6bedd81e20b1dbef0fec90022f7dd5b3cf7"
    },
    {
      "path": "paper-trader/backend/app/api/product_object_routes.py",
      "sha256": "6b33b6e3b9854920c2e13c9aa079c58705bd10887ccbf863bc4fb9c76269f79e"
    },
    {
      "path": "paper-trader/backend/app/db/models.py",
      "sha256": "a0898a01f8d9d87d3c8cd2795689a8ec8fe845d3a055b1564c6856a7aa2750a4"
    },
    {
      "path": "paper-trader/backend/app/core/release_profile.py",
      "sha256": "bac0d0b76af0711e44d98af7e819cc42db0addce70b6658b251aaca23026b0a5"
    },
    {
      "path": "paper-trader/backend/tests/test_user_sessions.py",
      "sha256": "5d6aacced3a9201bed586f27a4ad4b6f369d19a10880ca81569684f00c1161c5"
    }
  ],
  "scope": [
    "Correct only action_for_request, optionally one private _static_scope_action helper and necessary existing/stdlib imports in principal.py, to classify the exact six static-scope route/method shapes as read:project or write:project before unrelated substring families. Preserve existing API-version normalization; no double URL decoding or second route/authority registry.",
    "Preserve the established Project identity domain and opaque scope/revision validation. Prove actual HTTPX to ASGI to route-match to action behavior across both mounts, every variable and reserved fragments/encodings. A matched endpoint must receive its project action before handler validation, even when a scope/revision value later refuses. Unmatched paths and unsupported methods must not gain authority.",
    "All non-static request action mappings, Principal/UserSession/IssuedBearerCredential classes, credential representation suppression, token/role/owner/resource semantics, execution/ARM/provider routes and public capability gates remain unchanged. Keep static_watchlists blocked. Do not edit versioning.py, static scope files or migrations.",
    "Add permanent regressions to test_api_auth.py, reproduce the complete mapping failure from the frozen receipt, and prove actual middleware/HTTP behavior for owner/member/viewer and invalid/foreign IDs using isolated fixtures. Use existing principal policy and actual static endpoints; label any test-only capability enablement.",
    "After local evidence and isolated mutation, request the one declared independent critical reviewer. Static owner resumes full mapping/HTTP verification only after this correction is independently accepted.",
    "Additionally change only auth_gate in main.py to pass the exact ASGI path used for route matching through the existing version normalization, instead of lossy request.url.path reconstruction. Preserve routing/exemptions/role/capability policies and the accepted diagnostic handlers; no double decoding or URL-query confusion. Compare ordinary requests, query strings and encoded path delimiters across both mounts and declared root-path assumptions. Existing non-static method/path classifier decisions remain exact; any changed transport decisions must be explained by the corrected actual path, never a broader permission.",
    "Reuse the exact installed router get_route_path callable for ASGI path/root_path selection (including exact segment-boundary stripping), followed by existing API-version normalization. A necessary main.py import is allowed; do not copy a normalizer. Prove callable coupling, root-mounted/mount-prefixed/proxy-stripped cases and prefix lookalikes. Record the private API/version dependency and require these regressions on framework upgrades."
  ],
  "source_failure_hypothesis": "358 actual raw-URL/ASGI probes include116 matched-route action-family mismatches;96 arise from valid existing Project IDs,18 invalid scope values and2 invalid revision values. Greedy substring dispatch runs before route dependencies.",
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
    "Initial RED: reproduce reserved project IDs and all matched mapping discrepancies in the pinned358-probe receipt without dispatching handlers, then add actual HTTP authorization regressions.",
    "Run tests/test_api_auth.py, tests/test_user_sessions.py, tests/test_static_scope_routes.py and the named V0 diagnostics/health compatibility tests in sanitized isolated databases. Preserve every historical test and raw failure.",
    "AST/source comparison proves all existing top-level functions/classes except action_for_request remain exact, plus the permitted new helper/import. Verify the accepted credential repr regression and auth/role/expiry/revoke semantics.",
    "Isolated source mutation removes only the exact-family precedence guard; expected mapping/HTTP consumer tests must fail with zero collection/setup errors/skips, then restore and rerun.",
    "Seal the exact two-file incremental diff, input/static source hashes, complete route/action matrix, tests and deployment-impact nonclaims for separate SPEC/QUALITY review.",
    "Close all394 expanded probes and real status%3Ftail owner201/viewer200 cases with a labeled enabled capability fixture, while real capability remains blocked. Include encoded question/hash path data versus ordinary query strings, both mounts, root-path assumptions and unmatched routes; source/AST proof allows only main.auth_gate in addition to the declared principal function/helper/import."
  ],
  "review": {
    "required": true,
    "assignment_id": "v0_static_scope_authorization_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Authorization classification across shared middleware and tenant-owned resource paths; one independent final critical review after this bounded correction is integrated.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-static-scope-authorization-correction/path-input/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/api/principal.py",
      "paper-trader/backend/tests/test_api_auth.py",
      "paper-trader/backend/app/main.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/strategy-os-v0-static-scope-authorization-correction/review.md",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "deployment_impact": {
    "classification": "compatible",
    "prove_now": [
      "Initial RED: reproduce reserved project IDs and all matched mapping discrepancies in the pinned358-probe receipt without dispatching handlers, then add actual HTTP authorization regressions.",
      "Run tests/test_api_auth.py, tests/test_user_sessions.py, tests/test_static_scope_routes.py and the named V0 diagnostics/health compatibility tests in sanitized isolated databases. Preserve every historical test and raw failure.",
      "AST/source comparison proves all existing top-level functions/classes except action_for_request remain exact, plus the permitted new helper/import. Verify the accepted credential repr regression and auth/role/expiry/revoke semantics.",
      "Isolated source mutation removes only the exact-family precedence guard; expected mapping/HTTP consumer tests must fail with zero collection/setup errors/skips, then restore and rerun.",
      "Seal the exact two-file incremental diff, input/static source hashes, complete route/action matrix, tests and deployment-impact nonclaims for separate SPEC/QUALITY review."
    ],
    "integration_owner": "strategy-os-v0-static-scope-foundation",
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
    "Correct only action_for_request, optionally one private _static_scope_action helper and necessary existing/stdlib imports in principal.py, to classify the exact six static-scope route/method shapes as read:project or write:project before unrelated substring families. Preserve existing API-version normalization; no double URL decoding or second route/authority registry.",
    "Preserve the established Project identity domain and opaque scope/revision validation. Prove actual HTTPX to ASGI to route-match to action behavior across both mounts, every variable and reserved fragments/encodings. A matched endpoint must receive its project action before handler validation, even when a scope/revision value later refuses. Unmatched paths and unsupported methods must not gain authority.",
    "All non-static request action mappings, Principal/UserSession/IssuedBearerCredential classes, credential representation suppression, token/role/owner/resource semantics, execution/ARM/provider routes and public capability gates remain unchanged. Keep static_watchlists blocked. Do not edit versioning.py, static scope files or migrations.",
    "Add permanent regressions to test_api_auth.py, reproduce the complete mapping failure from the frozen receipt, and prove actual middleware/HTTP behavior for owner/member/viewer and invalid/foreign IDs using isolated fixtures. Use existing principal policy and actual static endpoints; label any test-only capability enablement.",
    "After local evidence and isolated mutation, request the one declared independent critical reviewer. Static owner resumes full mapping/HTTP verification only after this correction is independently accepted.",
    "Additionally change only auth_gate in main.py to pass the exact ASGI path used for route matching through the existing version normalization, instead of lossy request.url.path reconstruction. Preserve routing/exemptions/role/capability policies and the accepted diagnostic handlers; no double decoding or URL-query confusion. Compare ordinary requests, query strings and encoded path delimiters across both mounts and declared root-path assumptions. Existing non-static method/path classifier decisions remain exact; any changed transport decisions must be explained by the corrected actual path, never a broader permission.",
    "Reuse the exact installed router get_route_path callable for ASGI path/root_path selection (including exact segment-boundary stripping), followed by existing API-version normalization. A necessary main.py import is allowed; do not copy a normalizer. Prove callable coupling, root-mounted/mount-prefixed/proxy-stripped cases and prefix lookalikes. Record the private API/version dependency and require these regressions on framework upgrades."
  ],
  "required_receipts": {
    "mapping": ".agent/runs/strategy-os-v0-static-scope-foundation/path-mapping.json",
    "mapping_sha256": "05056e6c8f67c07073106d5d3cbcb5cdd56c5803965725d33bf19b0611b23d32",
    "static_source_manifest": ".agent/runs/strategy-os-v0-static-scope-foundation/final-test-source-hashes-v3.json",
    "static_source_manifest_sha256": "46922441ef1773ebecbb5791be3147bedeeda17dee96bbe85cad5feb351f67ac",
    "session_acceptance_seal": ".agent/runs/strategy-os-v0-session-credential-hygiene/closure-seal.json",
    "session_acceptance_sha256": "e8c0c127f0911630ca2cbd5fe293f9ea7ed4a9d88165f08230b20552afe5bdd9"
  },
  "requires_leaf_acceptance": "v0_session_credential_hygiene",
  "owner_task": "01a049cf-cec3-7bf0-9004-cead1647938a",
  "concurrent_ownership": {
    "static_source_interfaces_frozen": true,
    "numerical_owner": "01a04997-52e4-79c3-ad87-9c896b560920",
    "rule": "No overlapping principal writer. Session implementation and review are complete; preserve its repr suppression. Other owners may update their own capsules/run only; main numerical files and coordinator controls may change with exact attribution."
  },
  "routing_seal": ".agent/runs/post-phase5-indicator-accuracy-multi-output/coordinator/static-authorization/path-input/routing-seal.json",
  "path_input_amendment": {
    "finding_receipts": {
      "mapping": ".agent/runs/strategy-os-v0-static-scope-authorization-correction/mapping-encoded-delimiter.json",
      "mapping_sha256": "576f5aecbd8ad7f46a2e5c0d9f9c61c034a850b49e79dd585ad83b74de84a9da",
      "http": ".agent/runs/strategy-os-v0-static-scope-authorization-correction/delimiter-http-finding.json",
      "http_sha256": "b1945ae1f3d7515958239524b15970dfa07e3d0383895cfa6ef443b47b5a6e30"
    },
    "diagnostics_writer_completed": true,
    "diagnostics_closure_sha256": "715f6972b5858f92e4bf01b6d0f3ae426b70539c251a05e3ade22a7f1108681f",
    "main_before_sha256": "6cfc9b72cefcde83a60fa640013fc10277a0b4ecef26975c5c45faaf749fed8e",
    "scope": "auth_gate path-source selection only; all other main.py bytes/functions, particularly accepted redaction, stay exact.",
    "router_path_semantics": {
      "callable": "starlette.routing.get_route_path",
      "same_callable_as": "starlette._utils.get_route_path used by Route.matches",
      "installed_starlette": "1.6.0",
      "utils_module_sha256": "7cb67fa5195ca7ec0fe33122c9e5ce225edfa3297fcc82f9026e84f9c56583cb",
      "helper_source_sha256": "243011d2a68ca7fec43c3f1d4cecedfa2f8997d87ce97dbe1ac8c27013910889",
      "coupling": "Private framework seam; no dependency/lock change. Explicit adapter regression required at dependency upgrades."
    }
  },
  "accepted_path_input_decision": {
    "path": ".agent/runs/post-phase5-indicator-accuracy-multi-output/coordinator/static-authorization/path-input/decision.json",
    "sha256": "345be871b2762caf5f1a54b33f2c197ab0d9769d8d98e7cb974e994f562f50a3"
  },
  "local_evidence": {
    "verdict": "LOCAL_INTEGRATED_PASS_PENDING_INDEPENDENT_REVIEW",
    "report": ".agent/runs/strategy-os-v0-static-scope-authorization-correction/path-input/report.md",
    "seal": ".agent/runs/strategy-os-v0-static-scope-authorization-correction/path-input/local-evidence-seal.json",
    "mapping_cases": 394,
    "compatibility_tests": 259,
    "source_hashes": {
      "paper-trader/backend/app/api/principal.py": "b3d1f45c64e9d36a057f17698d8c3896dc5c5446b9c2f5f3bc6eef84f13f8884",
      "paper-trader/backend/app/main.py": "2adfabd1d4f0837428f84b8eca134ce33c13110e8ceb6e056f1d8cfa20632b68",
      "paper-trader/backend/tests/test_api_auth.py": "ba9d7ef97847d947e5eb287bc4f894b9be31011b121cae6d64de5904cfbd7bf3"
    },
    "independent_acceptance": false,
    "public_capability_opening": false,
    "deployment": false
  }
}
---

# Static-scope authorization correction

Exact serial shared-parser correction. Await sealed assignment and START.
