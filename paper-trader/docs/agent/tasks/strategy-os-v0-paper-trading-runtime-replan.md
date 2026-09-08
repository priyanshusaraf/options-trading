---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-paper-trading-runtime-replan",
  "phase": "v0",
  "status": "accepted",
  "kind": "critical_read_only_paper_runtime_architecture_replan",
  "goal": "Define the smallest complete Strategy OS paper-trading runtime over accepted graph, dataset, charge, lifecycle, capital, alert and frontend foundations without provider keys, live authority, shared routes or deployment.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "A paper runtime authority/data/state/restart/orchestration matrix maps exact existing code, gaps and collisions; one paper-only local successor is sealed with zero product writes and all provider/live/shared/deployment gates explicit."},
  "risk_tags": ["critical", "paper-trading", "execution", "reconciliation", "restart", "alerts", "deployability"],
  "depends_on": ["strategy-os-v0-paper-entry-lifecycle-identity-correction", "strategy-os-v0-paper-guard-semantic-manifest-correction", "strategy-os-v0-frontend-product-acceptance-recovery", "strategy-os-v0-platform-operations-persistence", "strategy-os-v0-post-foundations-launch-convergence-replan"],
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-owner-direction-extension-2026-08-29/report.md", "sections": ["Alerts, Paper and Both orchestration", "Paper state and reconciliation contract", "Staged graph execution and cache contract", "Verification and deployment decision"]},
    {"path": ".agent/runs/strategy-os-v0-paper-entry-lifecycle-identity-replan/report.md", "sections": ["Chosen lifecycle contract", "Current path coverage", "Successor boundary", "Remaining claims"]},
    {"path": ".agent/runs/strategy-os-v0-frontend-product-acceptance-recovery/report.md", "sections": ["Outcome", "Evidence summary", "Truthful unavailable states", "Review and release status"]},
    {"path": ".agent/runs/strategy-os-v0-post-foundations-launch-convergence-replan/decision.json", "sections": ["accepted_local_foundations", "missing_local_integrations", "next_local_safe_capsule", "deployment_matrix", "effects"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-paper-trading-runtime-replan.md", ".agent/runs/strategy-os-v0-paper-trading-runtime-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-paper-trading-runtime-replan.md", ".agent/runs/strategy-os-v0-paper-trading-runtime-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json"],
  "scope": ["Trace accepted graph/deployment binding through canonical data trigger, completed-bar schedule, signal, paper intent, deterministic admission, order/fill/position/charges/ledger/reconciliation and restart.", "Separate alert-only, paper-only and both preferences without duplicating SignalEvent or execution intent.", "Inventory existing paper broker/runtime/worker/repositories and name the smallest additive integration seam; preserve live fail-closed and risk-reducing exits.", "Use canonical/mock/replay datasets and synthetic accounts only; real provider capability/right remains external.", "Define exact API/frontend/deployment boundaries but do not edit shared routes, frontend or deploy target."],
  "acceptance": ["Matrix names one authority for graph, trigger, signal, paper intent, position campaign, charges, ledger and reconciliation; no second IR/resolver.", "Paper/live books remain separate and live is structurally unavailable.", "SL/TP and signal context preserve exact strategy/deployment/event attribution; alerts and paper effects are independent idempotent outcomes.", "Restart/reclaim/reconciliation/kill-switch/degraded behavior and resource ceilings have exact successor tests.", "Next successor paths avoid shared API/frontend/provider/deploy collisions; architecture passes with zero product writes."],
  "test_plan": ["Read-only source/task/evidence/collision/deployability inspection and architecture validation; runtime tests belong to successor."],
  "risk_classification": {"tier": "Critical", "reason": "Paper runtime defects can corrupt user-visible PnL, duplicate positions, cross books or create a path toward live execution."},
  "parallel_budget": 0,
  "assignments": [],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_paper_trading_runtime_replan", "agent": "owner", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only Critical architecture routing; implementation gets execution/reconciliation Critical review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-paper-trading-runtime-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-paper-trading-runtime-replan.md", ".agent/runs/strategy-os-v0-paper-trading-runtime-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-paper-trading-runtime-replan/decision.json", "verdicts": ["ARCHITECTURE", "EXECUTION_SAFETY", "DEPLOYABILITY"], "max_rechecks": 1},
  "owner_gates": ["No real provider credentials/network/data rights, live IR/assignment/order/capital authority, shared API/frontend, production account/data, VPS/deployment or live money action."],
  "stop_conditions": ["Safe paper runtime requires live/provider authority, second IR/resolver, shared route collision or unowned money semantics.", "Existing paper runtime path ownership conflicts."],
  "deployment_impact": {"classification": "none; read-only paper runtime replan", "highest_current_claim": "locally_runnable", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "replan_result": {"verdict": "KEEP + HARDEN / ADD PAPER SIGNAL ORCHESTRATION RUNTIME", "decision_sha256": "8ad5a2766eda593f4a2a6c40c3c86f761d905860c920861888b752c71f1c0575", "authority_matrix_sha256": "da7deefde944f92e54506febfc1889fd58c6f2460a978f71b25465f65359f774", "successor": "strategy-os-v0-paper-trading-runtime-foundation", "product_writes": 0, "release_deployable": false, "deployment": false},
  "nonclaims": ["No paper runtime integration, provider opening, live/order/money authority, API/frontend, deployment or V0 completion."
  ]
}
---

# Paper trading runtime replan

Compose accepted paper-only authorities into one restart-safe Strategy OS runtime.

## Replan evidence receipt

The successor is additive: no second IR, deployment, capital, position or ledger
authority. It binds immutable monitoring signals to deterministic paper intents and
independent alert/paper effects. Live and real-provider authority remain closed.
