---
{
  "id": "strategy-os-v0-frontend-convergence",
  "phase": "v0",
  "status": "accepted",
  "kind": "separate_application_precision_slate_architecture_replan",
  "goal": "Replan the V0 frontend as a separate Strategy OS application using Precision Slate over real APIs, with an independent deployment target and no trading-bot or VPS change.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after repository ownership, shared-backend boundaries, real-API shell contracts, incremental V0 feature-surface ownership, test/deployability evidence and the no-bot/no-VPS boundary are exact enough for separately authorized implementation capsules."},
  "risk_tags": ["critical", "architecture", "frontend", "deployment-boundary", "v0"],
  "required_docs": [{"path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/09-REVISED-V0-V1-V1.5-V2-V3-ROADMAP.md", "sections": ["V0-H — Precision Slate convergence"]}, {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/README.md", "sections": ["Directions", "Product boundary"]}, {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/docs/REFINED_VARIANTS.md", "sections": ["Shared structural corrections", "Variant A — Precision Slate"]}],
  "dependency_gate": "strategy-os-v0-release-profile-foundation",
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-frontend-convergence.md", "paper-trader/docs/agent/tasks/strategy-os-v0-precision-slate-shell-foundation.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md", ".codex/tests/test_programme_orchestration.py", ".agent/runs/strategy-os-v0-frontend-convergence"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend/src", "/Users/priyanshusaraf/dev/strategy-os-frontend/package.json", "/Users/priyanshusaraf/dev/strategy-os-frontend/package-lock.json"],
  "nonclaims": ["No frontend or backend implementation, dependency adoption, fixture promotion, deployment, VPS access, provider network, credential, broker, order, money, indicator correction, later V0 feature or Phase 6 work."],
  "owner_gates": ["Start only after exact owner authorization `AUTHORIZE V0 SEPARATE PRECISION SLATE ARCHITECTURE REPLAN`.", "Stop before choosing a repository merge/move, dependency, hosting provider, production topology, commercial/legal position or deployment action."],
  "owner_authorization_required": "AUTHORIZE V0 SEPARATE PRECISION SLATE ARCHITECTURE REPLAN",
  "owner_authorization": "AUTHORIZE V0 SEPARATE PRECISION SLATE ARCHITECTURE REPLAN",
  "stop_conditions": ["Any product, prototype source, dependency or deployment file changes.", "The plan treats fixture values as product truth or makes the trading bot/VPS a Strategy OS target.", "A second IR, API authority, research ledger or provider model is proposed.", "Repository or hosting ownership is selected without its later owner gate."],
  "deployment_impact": {"classification": "read-only architecture and release replan", "required_evidence": "separate application/deployment boundary, no bot/VPS path, real-API contract, incremental surface ownership and exact later deployment owner"},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["One separate Strategy OS application boundary and one future deployment owner are explicit; the bot/VPS are excluded.", "Precision Slate information architecture is mapped to real canonical API/data/evidence contracts with every prototype fixture removed or replaced by Unknown.", "The early shell, incremental feature-surface ownership and final convergence/release gates are dependency-ordered without a frontend big bang.", "Backend tooling, static research watchlists, charts, robustness, monitoring/signals and golden benchmarks retain exact later owners.", "No product or deployment byte changes."],
  "test_plan": ["Freeze the product, prototype source and dependency hashes before/after.", "Validate every Precision Slate surface against an existing real API, a named missing contract or an explicit deferred owner.", "Validate one REST client, one application WebSocket and server-owned readiness truth.", "Validate desktop/390px, loading/error/empty/Unknown and accessibility ownership in later implementation capsules.", "Validate programme order and separate deployment/no-VPS nonclaims."],
  "review": {"required": false, "assignment_id": "strategy_os_v0_frontend_convergence_owner", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "base_sha": "HEAD", "package": ".agent/runs/strategy-os-v0-frontend-convergence/evidence.json", "review_paths": [".agent/runs/strategy-os-v0-frontend-convergence", "paper-trader/docs/agent/tasks/strategy-os-v0-frontend-convergence.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/DEPLOYABILITY.md"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend"], "output": ".agent/runs/strategy-os-v0-frontend-convergence/report.md", "verdicts": ["ARCHITECTURE_REPLAN"]},
  "acceptance_evidence": {"status": "ARCHITECTURE_REPLAN_PASS", "decision": "KEEP_AND_HARDEN", "report_sha256": "3da36d64829730ea2641a09763b73a419cf5a3f4c14ca57ab7f96326ff0f314c", "evidence_sha256": "fcc2097bf1790ec9e63bc39b6d7fe6332976676250e74a6879bd6f03405c3d2c", "protected_hashes_unchanged": true, "product_changes": 0, "prototype_source_changes": 0, "dependency_changes": 0, "deployment_changes": 0, "successor": "strategy-os-v0-precision-slate-shell-foundation"}
}
---

# V0 separate application and Precision Slate replan

Accepted with `KEEP + HARDEN`. The separate Strategy OS frontend remains in
`strategy-os-frontend`; the canonical backend/IR/research authority remains in
options-trading under a separate V0 deployment. Product/prototype/dependency bytes
were unchanged. The trading bot and VPS remain untouched.
