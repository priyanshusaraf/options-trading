---
{
  "id": "strategy-os-v0-frontend-production-convergence-foundation",
  "phase": "v0",
  "status": "rejected_replan_required",
  "kind": "critical_cross_repository_frontend_foundation",
  "goal": "Turn the accepted manifest/auth/read-only Precision Slate shell into a stable desktop product-route and feature-module foundation without opening any unaccepted capability or importing prototype fixtures.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "One production route registry, direct-load/refresh/not-found behavior, closed capability gating, generalized single REST transport with typed error envelopes, route-level error boundaries, unchanged accepted Strategies behavior, deterministic production artifact exclusion and desktop/narrow-safety evidence pass. No new product capability opens."
  },
  "risk_tags": [
    "critical",
    "frontend",
    "release-profile",
    "auth-session",
    "tenant-isolation",
    "cross-repository",
    "production-artifact"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/architecture-decision.md",
      "sections": [
        "Five-family and desktop palette mapping",
        "Desktop-first frontend",
        "Deployment architecture and evidence"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/agents/precision-slate-desktop/report.md",
      "sections": [
        "Production shell versus fixture prototype",
        "Real client and backend contracts",
        "Desktop and narrow-screen boundary",
        "Disjoint implementation slices and dependency order"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-precision-slate-shell-foundation/report.md",
      "sections": [
        "Scope and result",
        "Complete claimed universe",
        "Limits and next gates"
      ]
    }
  ],
  "dependency_gate": "strategy-os-v0-launch-convergence-replan",
  "programme_assignment": {
    "parent_stage": "post-phase5-indicator-accuracy-session-data",
    "assignment_id": "v0_frontend_production_convergence_foundation",
    "owner_task": "/root/v0_frontend_production_convergence",
    "primary_programme_owner": false,
    "authority": "Latest explicit owner desktop-first/frontend/subagent instruction and accepted launch-convergence queue."
  },
  "allowed_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/main.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/productionBoundary.test.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product",
    "paper-trader/docs/agent/tasks/strategy-os-v0-frontend-production-convergence-foundation.md",
    ".agent/runs/strategy-os-v0-frontend-production-convergence-foundation"
  ],
  "new_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product"
  ],
  "protected_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package-lock.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/PrototypeApp.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/prototype-entry.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/components",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/data",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/pages",
    "paper-trader/backend",
    "paper-trader/frontend",
    "paper-trader/scripts/deploy.sh",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/tasks/post-phase5-indicator-accuracy-session-data.md"
  ],
  "stable_input_hashes": {
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/main.tsx": "fa4a5437cd89e8195c0a80abd96afe73aa6440db5dfcef39cd7a004fe12801d9",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx": "0026b300ac6ca0b1e8efe83096ee2b8e610a883a38ae614bccf0ebda97af2814",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx": "736f3bd9d16ddc6d28c0533539bd9e46702fec4bdad3adfbf63b93371ba1f5db",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts": "a3a69e720fe9a1e055a669a88c177c6502a041e38f52386d7dc59fb0a6652da7",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.ts": "fd13fed90f45d3ec67763434ce379983f0a33aad64c32e6df527cf883713548d",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx": "22757eac9b8f2c3744e3f3f47233b7faa5b60c26fa0bebb4d0d31dbecb7d39d7",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx": "0300f93a22cf124cb28a42e069fdd73e7512f76efe80ae9eea7cd2e4d2a13fec",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/productionBoundary.test.ts": "498df446acd4c11530a75500ea5f07e15d7d6a618bfbab86b021aa8d906ab406",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css": "1334185979cf1738140f8350f643825078062b7705b1c8b70d3dd2a706ed7093",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package.json": "2527a0c0ff35a87135c4a7eb8a2e59ea82e32045d19aa51af447c2392bc2b46c",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package-lock.json": "ab97fef6291e442557a3d487a9358c3bf2e9f987bd7c3ffa89d682c9cd961d69"
  },
  "scope": [
    "Keep release-manifest verification as the outermost product gate and browser authentication as the next gate.",
    "Add one stable production route registry and route-level module contract. Only the accepted Strategies route is enabled in this slice; later capabilities have no reachable module or optimistic placeholder.",
    "Use existing react-router-dom only if current lock/package evidence remains exact. Add no dependency and do not change package manifests.",
    "Generalize the sole StrategyApi transport to explicit GET/POST/PATCH/PUT/DELETE, bounded bodies, current generation cancellation, CSRF on mutations and closed typed error envelopes. Preserve all current auth/session behavior.",
    "Add direct-load, refresh, back/forward, unknown-route and route-render error behavior with accessible focus/announcement. Do not swallow async or render errors.",
    "Preserve current Precision Slate palette, typography, density and record-first visual language. This is structural convergence, not a new visual direction.",
    "Desktop is the construction target. Narrow widths retain login/account/alert foundations and show a truthful desktop-required boundary for future authoring routes; do not build mobile construction."
  ],
  "acceptance": [
    "Manifest failure or unaccepted capability mounts no product route or feature module.",
    "Direct load/refresh/back/forward resolve the same accepted Strategies state and owner-scoped project/graph selection without fixture or cross-tenant leakage.",
    "Unknown routes and route render failures show focused, announced, recoverable errors without losing the verified release/session boundary.",
    "The sole API client supports explicit methods and preserves current cancellation, timeout, access invalidation, in-memory CSRF and closed contract behavior; malformed typed errors never become trusted UI facts.",
    "Current project/graph tests and auth tests pass unchanged or with exact intentional route assertions.",
    "Production bundler inventory still excludes prototype, fixtures, paper/live/portfolio/deploy/order/position/PnL modules. No application WebSocket exists.",
    "Lint, typecheck, focused/full frontend tests and deterministic production build pass. Desktop browser direct-load/error/keyboard evidence passes; narrow evidence is limited to gate/account safety.",
    "Package and lock hashes, backend/prototype/protected hashes and both repository HEAD/index baselines are preserved."
  ],
  "test_plan": [
    "Add RED/GREEN route registry, direct-load, method/error-envelope, render-boundary, capability-denial and artifact-exclusion tests.",
    "Run npm lint, typecheck, focused tests, full tests and production build in the separate frontend through logged commands.",
    "Use the safe local runtime only if browser behavior beyond synthetic client tests is required; mock/paper, disabled dotenv, empty live acknowledgement, temporary databases and loopback only."
  ],
  "risk_classification": {
    "tier": "Critical",
    "reason": "A manifest, auth, routing or error-boundary regression can expose unaccepted surfaces, cross tenant context or false authority across every later frontend feature."
  },
  "owner_gates": [
    "Latest owner instruction authorizes desktop frontend implementation and bounded subagents. No repeated token is required.",
    "Stop before any backend/API/schema/dependency change, prototype promotion, new product capability, provider/payment network, deployment or live/order/money behavior."
  ],
  "stop_conditions": [
    "An accepted route cannot be implemented without changing backend capability or response authority.",
    "A new dependency or package/lock edit is required.",
    "Prototype/fixture modules, paper/live/deploy/portfolio/order/position/PnL semantics enter the production artifact.",
    "A second REST client, token store, WebSocket or routing authority appears."
  ],
  "deployment_impact": {
    "classification": "architecture-changing frontend foundation",
    "required_evidence": "Deterministic artifact/source identity, clean install/build inputs, CSP/origin route behavior, static-host deep-link contract, bundle inventory and rollback to the accepted shell. Final release assembly remains V0-I."
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "fork_turns": "none",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "owner_task": "/root/v0_frontend_production_convergence",
  "review": {
    "required": true,
    "assignment_id": "v0_frontend_production_convergence_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "The shared manifest/auth/router/API/artifact boundary gates every later product surface.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-frontend-production-convergence-foundation/review-package.json",
    "review_paths": [
      "paper-trader/docs/agent/tasks/strategy-os-v0-frontend-production-convergence-foundation.md",
      ".agent/runs/strategy-os-v0-frontend-production-convergence-foundation"
    ],
    "exclude_paths": [
      "paper-trader/backend",
      "paper-trader/frontend"
    ],
    "output": ".agent/runs/strategy-os-v0-frontend-production-convergence-foundation/review/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "first_review": {
    "review_task": "01a04cf2-5070-7fb3-8e14-f70a26a01d9d",
    "verdict": "SPEC FAIL / QUALITY FAIL",
    "verdict_path": ".agent/runs/strategy-os-v0-frontend-production-convergence-foundation/review/verdict.json",
    "verdict_sha256": "eb098400b343e9e2a6c22320a28b8abef22ebb03e592b1b3a248dd5fc6dea513",
    "finding_ids": [
      "V0-FPC-REV-001",
      "V0-FPC-REV-002",
      "V0-FPC-REV-003"
    ],
    "rechecks_used": 0,
    "rechecks_remaining": 1
  },
  "correction_scope": [
    "Make project/graph route attribution atomic so no intermediate committed DOM can display a graph from one project while URL/picker identify another; cover picker and history transitions with a MutationObserver-style regression.",
    "Expand the sole-transport guard to the complete production module graph including AuthGate and kill a reversible auth second-transport mutation in an isolated copy.",
    "Produce baseline/final content manifests for every capsule-protected path. Attribute coordinator-owned CURRENT/PROGRAMME/active-capsule drift explicitly instead of claiming it unchanged, and prove product/backend/bot/prototype/package/deploy bytes outside ownership remained exact.",
    "Rebuild the corrected review package and route only the one allowed same-reviewer recheck. No new feature, route or dependency."
  ],
  "nonclaims": [
    "No builder, validation, backtest, connection, chart, monitoring, alert, billing, account, support, admin, analytics, deployment or V0 completion capability.",
    "No mobile construction optimisation or accessibility conformance claim.",
    "No backend, schema, migration, dependency, provider, payment, credential, VPS, order, money or deployment change."
  ]
}
---

# Precision Slate production convergence foundation

Create the shared desktop route, error and API module foundation while keeping every unaccepted feature unreachable and prototype fixtures out of production.
