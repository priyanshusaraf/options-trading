---
{
  "id": "strategy-os-v0-static-scope-capability-enum-correction",
  "phase": "v0",
  "status": "accepted_first_slice_static_stage_active",
  "kind": "critical_static_scope_capability_guard_correction",
  "goal": "Make the static-scope API consume the canonical release-profile capability enum exactly and prove authenticated BLOCKED, ENABLED and absent behavior without opening the production capability or contacting a provider.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "The current uppercase ENABLED counterexample changes from refusal to the existing owner-scoped static-scope behavior, BLOCKED/absent/limited states still refuse before writes, tenant and role boundaries pass on both API mounts, an isolated lowercase/guard mutation is killed and restored, and one independent Critical reviewer returns SPEC PASS and QUALITY PASS."
  },
  "risk_tags": [
    "critical",
    "authorization",
    "tenant-isolation",
    "release-capability",
    "provider-gate"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/strategy-os-v0-static-scope-foundation/closure/report.md",
      "sections": ["Accepted boundary", "Mandatory qualifications"]
    },
    {
      "path": ".agent/runs/post-phase5-indicator-accuracy-multi-output-source-replan/coordinator/static-capability-enum-finding.json",
      "sections": ["all"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/strategy-os-v0-data-only-connection-contract.md",
      "sections": ["Owner-scoped data-only provider connection"]
    },
    {
      "path": "paper-trader/docs/strategy-os-v1-v2-v3/STRATEGY_OS_V0_V6_OWNER_DIRECTION_RECONCILIATION_2026-08-29.md",
      "sections": ["Current V0 programme reconciliation"]
    }
  ],
  "dependency_gate": "Accepted static-scope foundation closure, accepted data-only connection contract, and accepted integrated frontend recovery. This correction closes only V0_STATIC_SCOPE_CAPABILITY_ENUM_001 and does not satisfy provider conformance, data-rights, capture, reconnect or public-opening gates.",
  "allowed_paths": [
    "paper-trader/backend/app/api/static_scope_routes.py",
    "paper-trader/backend/tests/test_static_scope_routes.py",
    "paper-trader/backend/tests/test_api_auth.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-static-scope-capability-enum-correction.md",
    ".agent/runs/strategy-os-v0-static-scope-capability-enum-correction"
  ],
  "new_paths": [
    "paper-trader/docs/agent/tasks/strategy-os-v0-static-scope-capability-enum-correction.md",
    ".agent/runs/strategy-os-v0-static-scope-capability-enum-correction"
  ],
  "protected_paths": [
    "paper-trader/backend/app/core/release_profile.py",
    "paper-trader/backend/app/core/static_scopes.py",
    "paper-trader/backend/app/api/principal.py",
    "paper-trader/backend/app/api/product_object_routes.py",
    "paper-trader/backend/app/api/connection_routes.py",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/market_data",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ledger",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Use CapabilityState.ENABLED.value from the existing release-profile authority; do not create a second capability vocabulary or normalize arbitrary caller text.",
    "Replace lowercase synthetic success evidence with the real canonical enum value and directly cover BLOCKED, ENABLED_WITH_LIMIT, absent and malformed state refusal.",
    "Exercise owner, member, viewer and foreign principals through both authenticated HTTP mounts. The existing static-scope service, persistence, CAS and canonical instrument authority remain unchanged.",
    "Keep the real V0 manifest BLOCKED. No Zerodha credential, provider network, adapter, data capture, release-profile opening, frontend, schema, migration or deployment write is permitted."
  ],
  "acceptance": [
    "A RED test proves that the pre-correction lowercase comparison refuses the canonical uppercase ENABLED value; GREEN succeeds only for exact CapabilityState.ENABLED.value.",
    "BLOCKED, ENABLED_WITH_LIMIT, absent, lowercase and unknown states all return the same typed 403 capability refusal before static-scope writes.",
    "Exact ENABLED preserves owner/member/viewer/foreign behavior, private absence and CSRF/session policy on /api and /api/v1.",
    "An isolated reverted-lowercase mutation fails the intended enum regression and the restored source passes focused and affected static/auth suites.",
    "One independent Critical review returns SPEC PASS and QUALITY PASS with capability_open=false and deployment=false."
  ],
  "test_plan": [
    "Run the exact uppercase counterexample RED before implementation, then focused static-scope route tests on the repository virtual environment.",
    "Run affected static-scope, release-profile, API-auth and tenant-isolation selectors after GREEN.",
    "Kill and restore one isolated guard mutation; compare protected release-profile/static-service hashes before closure.",
    "Do not run a provider network, browser frontend, migration or full repository suite for this source-local correction."
  ],
  "risk_classification": {
    "tier": "Critical",
    "reason": "A one-line capability mismatch can either deny every legitimate static-scope request or accidentally broaden a tenant-facing provider capability gate."
  },
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "owner_task": "/root",
  "review": {
    "required": true,
    "assignment_id": "v0_static_scope_capability_enum_correction_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "The corrected guard is an authenticated tenant capability boundary and must not weaken BLOCKED or absent behavior.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-static-scope-capability-enum-correction/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/api/static_scope_routes.py",
      "paper-trader/backend/tests/test_static_scope_routes.py",
      "paper-trader/backend/tests/test_api_auth.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-static-scope-capability-enum-correction.md",
      ".agent/runs/strategy-os-v0-static-scope-capability-enum-correction"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/core/release_profile.py",
      "paper-trader/backend/app/core/static_scopes.py",
      "paper-trader/backend/app/providers",
      "paper-trader/backend/app/market_data",
      "paper-trader/backend/app/db",
      "paper-trader/backend/migrations",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/app/ledger",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-static-scope-capability-enum-correction/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "first_review": {
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "finding_ids": ["V0-SSC-CR-001", "V0-SSC-CR-002", "V0-SSC-CR-003"],
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "final_review": {
    "review_task": "/root/static_scope_enum_review",
    "verdict": "SPEC PASS / QUALITY PASS",
    "finding_ids_closed": ["V0-SSC-CR-001", "V0-SSC-CR-002", "V0-SSC-CR-003"],
    "rechecks_used": 1,
    "rechecks_remaining": 0,
    "capability_open": false,
    "deployment": false
  },
  "correction_scope": [
    "V0-SSC-CR-001: fail closed with the same typed 403 before writes when manifest, capabilities or static_watchlists containers are missing or malformed.",
    "V0-SSC-CR-002: bind protected release-profile, static-service, principal, product-route and connection-route hashes to accepted predecessor evidence and final current bytes.",
    "V0-SSC-CR-003: record isolated-copy path and baseline/mutated/restored hashes plus failing and restored test executions."
  ],
  "owner_gates": [
    "Standing V0 development authority permits this exact mandatory pre-opening correction after the accepted frontend successor.",
    "No provider credential/network, vendor/data-right decision, public capability opening, release-profile state change, external frontend change, schema/migration, deployment, live, order or money action."
  ],
  "stop_conditions": [
    "Correct behavior requires changing the release-profile enum or manifest, static-scope service/persistence, principal, provider adapter, schema or migration.",
    "Exact ENABLED cannot be distinguished from limited, absent or malformed states without broad string normalization.",
    "Concurrent work changes either owned product/test file without exact attribution."
  ],
  "deployment_impact": {
    "classification": "compatible unpublished API guard correction",
    "required_evidence": "Focused authenticated HTTP behavior and protected-source equality only. Highest claim is locally runnable; provider opening and release deployability remain separate exact capsules."
  },
  "nonclaims": [
    "No static-watchlist public opening, Zerodha provider conformance, expiry/quota/reconnect proof, data capture, frontend integration, release deployability, production rehearsal, deployment, live execution or V0 completion."
  ]
}
---

# Static-scope canonical capability-enum correction

Close the exact uppercase capability-state defect while keeping the real product
capability blocked. This is the first bounded implementation slice of the active
Zerodha/static-scope stage; later provider, capture and public-opening gates remain.
