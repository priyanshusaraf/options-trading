---
{
  "id": "strategy-os-v0-canonical-research-spine",
  "phase": "v0",
  "status": "foundation_implementation_pass_product_ux_fail",
  "kind": "critical_cross_repository_canonical_research_spine",
  "goal": "Connect owner-scoped projects, canonical graphs, the verified five-family editor, persisted canonical datasets, graph experiments, historical backtests and research review through one data-provider-independent V0 path and truthful Precision Slate desktop surfaces.",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "A user can select a real owned strategy, inspect and edit its canonical graph using the accepted catalogue, publish an immutable revision, submit a supported canonical-manifest graph experiment, reopen exact result/evidence records and compare revisions from Precision Slate without fixtures, execution-cell/provider fetch, capital affordability or authority leakage; affected backend/frontend/browser gates and one independent Critical SPEC/QUALITY review pass."
  },
  "risk_tags": [
    "critical",
    "research-integrity",
    "tenant-isolation",
    "canonical-identity",
    "cross-repository",
    "frontend",
    "api-contract"
  ],
  "required_docs": [
    {
      "path": ".agent/runs/strategy-os-v0-frontend-convergence/architecture-decision.md",
      "sections": ["Repository and artifact ownership", "Frontend contract", "Precision Slate decisions", "Invariants"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-frontend-convergence/surface-api-matrix.json",
      "sections": ["home", "strategies", "overview", "build", "backtest", "research_validate", "activity_review"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-frontend-convergence/implementation-capsules.json",
      "sections": ["strategy-os-v0-canonical-research-spine"]
    },
    {
      "path": "paper-trader/docs/agent/tasks/strategy-os-v0-verified-language-catalogue.md",
      "sections": ["Terminal Critical-review receipt"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-q03-cold-admission-clarification/dataset-contract.md",
      "sections": ["Scope and authority", "Selection and persisted trust", "Executable segment interpretation", "Instrument projection and recipe identity", "Real consumers and evidence", "Deployment and remaining gates"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-canonical-dataset-research-bridge/report.md",
      "sections": ["Verdict", "Delivered contract", "Causal and research-validity evidence", "Tenant and consumer evidence", "Preserved gates"]
    },
    {
      "path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/03-V0-SCOPE-AND-GOLDEN-PATH.md",
      "sections": ["Public V0 scope", "Canonical V0 objects", "Golden path"]
    },
    {
      "path": ".agent/runs/strategy-os-v0-launch-convergence/architecture-decision.md",
      "sections": ["Observable V0 outcome", "Options-data and backtest eligibility", "Desktop-first frontend", "Architecture invariant matrix"]
    }
  ],
  "dependency_gate": "strategy-os-v0-verified-language-catalogue accepted with terminal verdict SHA-256 76ac68d907fc69866e94d9ab2a82c67c0ec45469ebc304ae30668b008ce09e11; accepted Q03 bridge remains the sole canonical-manifest adapter.",
  "allowed_paths": [
    "paper-trader/backend/app/api/research_spine_routes.py",
    "paper-trader/backend/app/api/product_object_routes.py",
    "paper-trader/backend/app/api/ir_experiment_routes.py",
    "paper-trader/backend/app/api/research_review_routes.py",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/tests/test_v0_canonical_research_spine.py",
    "paper-trader/backend/tests/test_ir_experiment_routes.py",
    "paper-trader/backend/tests/test_research_review_routes.py",
    "paper-trader/backend/research_tests/test_graph_experiment.py",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/PrecisionShell.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/api.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/contracts.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/precision.css",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/productionBoundary.test.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell/shell.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product/routes.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product/routes.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/research",
    "paper-trader/docs/agent/tasks/strategy-os-v0-canonical-research-spine.md",
    ".agent/runs/strategy-os-v0-canonical-research-spine"
  ],
  "new_paths": [
    "paper-trader/backend/app/api/research_spine_routes.py",
    "paper-trader/backend/tests/test_v0_canonical_research_spine.py",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/research",
    ".agent/runs/strategy-os-v0-canonical-research-spine"
  ],
  "external_review_paths": [
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/App.test.tsx",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/shell",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/product",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/research"
  ],
  "protected_paths": [
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/editor/v2_catalogue.py",
    "paper-trader/backend/app/api/catalogue_routes.py",
    "paper-trader/backend/research/data/canonical_dataset.py",
    "paper-trader/backend/research/orchestrator/graph_experiment.py",
    "paper-trader/backend/app/backtest",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/backend/app/ledger",
    "paper-trader/backend/requirements.lock",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/src/data/fixtures.ts",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package.json",
    "/Users/priyanshusaraf/dev/strategy-os-frontend/package-lock.json",
    "paper-trader/scripts/deploy.sh"
  ],
  "scope": [
    "Implement one owner-scoped research spine over existing canonical project, graph, edit/version, catalogue, canonical-manifest experiment and research-review authorities. Add a bounded aggregate read model only where coordinated existing reads cannot truthfully support the desktop journey.",
    "Replace every production hardcoded project, graph, strategy, backtest and evidence fixture on the owned surfaces with authenticated server records or explicit loading, empty, unavailable and error states.",
    "The Build surface consumes `/api/v1/ir/catalogue` and existing canonical batch edit/version APIs. It must not clone node descriptors, registry membership, validation or hashing in the client.",
    "The V0 Backtest surface submits only a published graph version plus accepted `canonical_manifest_v2` selections to the existing graph-experiment route. It never fetches through `local_execution_cell`, broker/provider adapters, arbitrary CSV or client-supplied market bytes.",
    "The exact Q03 supported subset remains one canonical NSE/BSE INR equity-spot instrument and contiguous 15/30/60-minute OHLCV. Unsupported options/derivatives, unknown codecs, gaps, multi-instrument manifests and absent history return typed unavailable/refusal states; catalogue presence is not backtest eligibility.",
    "Display exact graph/component/registry/dataset/spec/run/cost/fold/comparison/review identities supplied by the server. Do not attach execution capital, affordability, order, position, account, balance or PnL facts.",
    "Desktop is the acceptance viewport. Preserve existing responsive behavior but add no mobile-specific optimization in this capsule.",
    "No schema, migration, dependency, provider, capture, chart, annotation, monitoring, billing, deployment, live, order or money work."
  ],
  "acceptance": [
    "Owner-scoped project and graph indexes contain no hardcoded identity; foreign-owner and guessed identifiers have the same private absence shape with zero side effects.",
    "A real empty-database browser journey can create/select a project and graph, edit from the verified catalogue, publish an immutable version, and retain exact selection after reload without fixture imports.",
    "A persisted synthetic canonical-manifest authority can run through the accepted resolver/admission → HTTP route → verified loader → graph experiment → immutable spec/run path and reopen after backend/frontend restart with identical identities and response content.",
    "Supported graph experiments do not reach execution-cell/provider fetch, execution capital affordability or legacy OHLC-only identity. Unsupported options/history and data-shape requests refuse before writes/evaluation with stable typed reasons.",
    "Overview, Backtest and research review display only real server values or explicit Unknown/empty/error states; no profitability, PnL, deployment or provider-support claim is synthesized.",
    "Production frontend static import/bundle gates prove no route from the entrypoint to fixture strategy/backtest/research data, excluded execution/portfolio/deploy surfaces, a second API client or a WebSocket.",
    "Backend auth/version mirrors, tenant isolation, causal completed-bar behavior, immutable identity, replay/restart, bounded pagination/payload/query/memory and exact error-state tests pass.",
    "Frontend lint, typecheck, deterministic test/build and desktop browser loading/empty/error/supported/refused/reload journeys pass with no unexpected console or network activity.",
    "Genuine isolated mutations for hardcoded identity, fixture import, provider fallback, truncated dataset identity, missing owner predicate, future-bar access and invented result value are killed and exact bytes restored.",
    "One independent Critical reviewer returns SPEC PASS and QUALITY PASS over both repository diffs and the sealed evidence package."
  ],
  "test_plan": [
    "Freeze both repository states, relevant accepted input hashes and external source/config manifests before RED tests; attribute all inherited dirty bytes and stop on unexplained overlap.",
    "Run focused backend and frontend RED/GREEN tests, accepted Q03/canonical catalogue compatibility selectors, real SQLite and disposable PostgreSQL 16 where the existing experiment path supports them, then deterministic browser tests against safe temporary databases.",
    "Measure bounded project/graph/result pages, response bytes, query counts, cold/restart latency, client bundle and browser network; do not convert local measurements into production capacity claims.",
    "Build an evidence-indexed Critical package with exact commands, JUnit/JSON counts, protected manifests, mutation restoration and an explicit deployment-impact/nonclaim matrix."
  ],
  "risk_classification": {
    "tier": "Critical",
    "reason": "This slice joins tenant-owned strategy identity, causal dataset truth, research evidence and a public desktop workflow; a false join can expose another tenant or present invalid research as executable truth."
  },
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "high",
    "fork_turns": "none",
    "service_tier": "priority",
    "routing_note": "The implementation owner is a user-owned root task at the owner's requested high effort; it may not spawn product children."
  },
  "owner_task": "01a04e67-bce7-7a13-bbe2-66eed851e9a4",
  "review": {
    "required": true,
    "assignment_id": "strategy_os_v0_canonical_research_spine_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "Independent integrated review of cross-tenant privacy, research causality, canonical identity and fixture-free cross-repository behavior.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-canonical-research-spine/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/api/research_spine_routes.py",
      "paper-trader/backend/app/api/product_object_routes.py",
      "paper-trader/backend/app/api/ir_experiment_routes.py",
      "paper-trader/backend/app/api/research_review_routes.py",
      "paper-trader/backend/app/main.py",
      "paper-trader/backend/tests/test_v0_canonical_research_spine.py",
      "paper-trader/backend/tests/test_ir_experiment_routes.py",
      "paper-trader/backend/tests/test_research_review_routes.py",
      "paper-trader/backend/research_tests/test_graph_experiment.py",
      "paper-trader/docs/agent/tasks/strategy-os-v0-canonical-research-spine.md",
      ".agent/runs/strategy-os-v0-canonical-research-spine"
    ],
    "exclude_paths": [
      "paper-trader/backend/app/db",
      "paper-trader/backend/migrations",
      "paper-trader/backend/app/providers",
      "paper-trader/backend/app/engine",
      "paper-trader/backend/app/execution",
      "paper-trader/backend/app/ledger",
      "paper-trader/frontend",
      "paper-trader/scripts/deploy.sh"
    ],
    "output": ".agent/runs/strategy-os-v0-canonical-research-spine/review/verdict.json",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  },
  "owner_gates": [
    "Standing V0 development authority permits this exact serial stage after accepted catalogue closure; no repeated token is required.",
    "The accepted Q03 bridge and catalogue are immutable inputs. Any indispensable change to either requires a separate bounded correction and new review lineage.",
    "No external provider network, real customer data, production credential, paid action, deployment, live/order/money action or dependency adoption."
  ],
  "stop_conditions": [
    "A schema/migration, dependency/lock, provider/capture, execution, money or deployment change is required.",
    "The supported V0 experiment cannot remain on the accepted canonical-manifest adapter without modifying its immutable contract.",
    "A frontend value cannot be sourced from an authenticated canonical server fact or shown honestly as unavailable.",
    "Concurrent changes overlap an owned path without exact attribution and preserved-byte reconciliation."
  ],
  "deployment_impact": {
    "classification": "compatible authenticated API and separate frontend artifact; no schema/dependency/provider/service topology change",
    "required_evidence": "Deterministic backend/frontend builds and safe local runtime/browser evidence on temporary databases, exact config/static bundle inspection, restart behavior, resource receipts and rollback by prior compatible artifact. Release deployability remains owned by strategy-os-v0-security-operations-deployability."
  },
  "nonclaims": [
    "No broad historical options backtesting, live provider capture, chart/annotation/replay, robustness completion, monitoring runtime/alerts UI, billing, admin, deployment, production readiness, live orders, money or whole-V0 completion.",
    "A supported synthetic canonical dataset proves contract behavior, not real provider availability, data rights, market completeness or strategy profitability."
  ]
}
---

# V0 canonical research spine

Connect the accepted five-family language and canonical persisted-dataset experiment path to one fixture-free, owner-scoped Precision Slate desktop journey. Preserve causal research truth and keep execution, providers and money outside V0 research.
