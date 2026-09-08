---
{
  "id": "strategy-os-v0-precision-slate-shell-foundation",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_cross_repository_frontend_foundation",
  "goal": "Promote Precision Slate Direction 7 into the separate Strategy OS production shell over the accepted V0 release profile and real owner-scoped project/graph selection, without touching or deploying the trading bot.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Complete only after the separate production entrypoint is fixture-free, manifest-first and fail-closed; one typed API client and real project/graph selection work; unsupported capabilities are absent or truthfully blocked; deterministic build/type/test and desktop/390px browser evidence pass; protected bot/product paths remain exact; and one independent critical review returns SPEC PASS and QUALITY PASS."
  },
  "risk_tags": [
    "critical",
    "frontend",
    "cross-repository",
    "capability-authority",
    "v0"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/strategy-os-v0-frontend-convergence/architecture-decision.md",
      "sections": [
        "Verdict",
        "Frontend contract",
        "Precision Slate decisions",
        "Invariants"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-frontend-convergence/surface-api-matrix.json",
      "sections": [
        "bootstrap_shell",
        "strategies"
      ]
    },
    {
      "path": "/Users/priyanshusaraf/dev/strategy-os-frontend/docs/REFINED_VARIANTS.md",
      "sections": [
        "Shared structural corrections",
        "Variant A \u2014 Precision Slate"
      ]
    }
  ],
  "dependency_gate": "strategy-os-v0-frontend-convergence",
  "allowed_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package-lock.json",
    "paper-trader/backend/app/api/product_object_routes.py",
    "paper-trader/backend/app/api/release_profile_routes.py",
    "paper-trader/backend/app/core/release_profile.py",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/tests/test_v0_precision_slate_shell.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-precision-slate-shell-foundation.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    ".agent/runs/strategy-os-v0-precision-slate-shell-foundation"
  ],
  "external_review_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package-lock.json"
  ],
  "protected_paths": [
    "paper-trader/frontend",
    "paper-trader/backend/app/ir",
    "paper-trader/backend/research",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/migrations",
    "paper-trader/scripts/deploy.sh",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/data/fixtures.ts"
  ],
  "nonclaims": [
    "No indicator/node correction, builder catalogue/editor integration, backtest/research method, data credential/provider, watchlist, chart, annotation/replay, robustness, monitoring/signal, auth production, deployment, VPS, broker, order, position, capital, money, later V0 stage or Phase 6 implementation."
  ],
  "owner_gates": [
    "Start only after exact owner authorization `AUTHORIZE V0 PRECISION SLATE SHELL FOUNDATION`.",
    "Stop before adding or changing a dependency, Git remote/CI, hosting/deployment target, auth product, schema/migration, provider credential/network, bot/VPS or legal/licence-sensitive adoption not already approved by the capsule evidence."
  ],
  "owner_authorization_required": "AUTHORIZE V0 PRECISION SLATE SHELL FOUNDATION",
  "stop_conditions": [
    "The production entrypoint imports fixtures or exposes Deploy, execution Live, money/position Portfolio or custom Workspace.",
    "Any direct component fetch or second REST/WebSocket client appears.",
    "A hardcoded project/graph or invented metric substitutes for server truth.",
    "A non-V0/malformed manifest mounts product surfaces.",
    "Protected bot/IR/research/execution/provider/migration/deploy bytes change.",
    "A deployment or external network action starts."
  ],
  "deployment_impact": {
    "classification": "architecture-changing frontend/build and compatible bounded API read model",
    "required_evidence": "locked dependency/SBOM inventory without adoption, deterministic frontend artifact, current V0 API config, safe local browser, no bot/VPS path, and exact V0-I deployment owner"
  },
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "Direction 7 is the production `/` entrypoint; prototype directions are development-only and absent from the production graph/artifact.",
    "The first request validates the server release manifest deeply; failure/malformed/standard profile exposes no Strategy OS product surface.",
    "One typed API client owns all REST and no application WebSocket opens.",
    "Owner-scoped projects and graph identities come from real APIs; a minimal graph-index read model is bounded and tenant-tested.",
    "V0 navigation initially exposes only server-enabled shell/strategy facts; all later surfaces are absent or display a typed blocked reason with no fixture value.",
    "Every visible value is real or explicitly Unknown/empty/error.",
    "Desktop and 390px browser journeys, console/network, loading/error/empty states, typecheck, tests and production build pass.",
    "Frontend dependency/lock/licence/SBOM evidence is current; no dependency changes in this slice unless separately authorized.",
    "Bot frontend/runtime/VPS/deploy behavior and every protected path remain exact.",
    "Independent SPEC PASS and QUALITY PASS."
  ],
  "test_plan": [
    "Freeze both repositories, locks and protected path groups before/after.",
    "Behaviorally mount loading, malformed, standard, V0 empty and V0 real-project states.",
    "Prove one bounded owner-scoped graph-index API and cross-owner denial.",
    "Static bundle/import gate proves production entrypoint cannot reach fixtures or excluded surfaces.",
    "Mutation removes manifest barrier and must make the browser/component gate fail before exact restoration.",
    "Safe local V0 API with mock/no credentials and separate temporary databases; desktop and 390px browser network contains only release/project/graph reads and no `/ws`.",
    "Run external frontend lint/typecheck/test/build, focused backend tests, ordinary V0-A/standard compatibility selectors and metadata contracts."
  ],
  "review": {
    "required": true,
    "assignment_id": "strategy_os_v0_precision_slate_shell_foundation_reviewer",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "HEAD",
    "package": ".agent/runs/strategy-os-v0-precision-slate-shell-foundation/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/api/product_object_routes.py",
      "paper-trader/backend/app/core/release_profile.py",
      "paper-trader/backend/tests/test_v0_precision_slate_shell.py",
      ".agent/runs/strategy-os-v0-precision-slate-shell-foundation"
    ],
    "exclude_paths": [
      "paper-trader/frontend",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/migrations"
    ],
    "output": ".agent/runs/strategy-os-v0-precision-slate-shell-foundation/review/verdict.json",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1,
    "reason": "Independent final review of manifest fail-closed behavior, cross-owner graph reads, and production bundle exclusion; only after integrated sealed evidence."
  },
  "owner_authorization": "AUTHORIZE V0 PRECISION SLATE SHELL FOUNDATION",
  "acceptance_receipt": {
    "SPEC": "PASS",
    "QUALITY": "PASS",
    "review_package_sha256": "a3df73cf057c144beca1a1489d9dfed946e7e20dfc8c5770a55bbbc004d5236d",
    "review_verdict_sha256": "79bed2dc039eed4469a2ca42f299988de378ceb11fc2a86f6a3524d425b44616",
    "evidence": ".agent/runs/strategy-os-v0-precision-slate-shell-foundation/evidence.json",
    "deployment_authority": false,
    "later_feature_authority": false
  }
}

---

# V0 Precision Slate shell foundation

This is the first implementation capsule after the separate-application replan. It
promotes the standalone visual prototype into a truthful shell only. It cannot make
later node, research, watchlist, chart, signal or deployment capabilities true.
