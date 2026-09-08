---
{
  "id": "strategy-os-v0-chart-annotation-replay",
  "lineage_id": "strategy-os-v0-chart-annotation-replay-replan",
  "phase": "v0",
  "status": "accepted_replan_corrected_dependency_ready",
  "kind": "critical_read_only_chart_annotation_replay_replan",
  "goal": "Freeze the smallest useful V0 chart-context and annotation-replay product slice, while deferring executable annotation-derived strategy inputs and automatic chart interpretation to V1.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "One zero-product-write decision classifies V0 versus V1 chart capabilities, inventories the accepted normalized geometry and existing research/alert/frontend seams, and seals one exact implementation successor with privacy, causality, data-rights, desktop UX, deployability and ablation gates."},
  "risk_tags": ["critical", "research", "market-truth", "chart", "annotations", "privacy", "frontend", "data-rights", "deployability"],
  "depends_on": ["strategy-os-v0-data-provider-key-onboarding-local-foundation", "strategy-os-v0-normalized-annotation-geometry", "strategy-os-v0-frontend-product-acceptance-recovery"],
  "dependency_gate": {"provider_package_sha256": "c353370d7cdd55ddecd61fbb76b15f1eb523c684b2ec0d0a4f44ff829d53cc5d", "provider_recheck_verdict_sha256": "86e103fcf6503093db8d814c3f42ee43fe85763170e157656895931798e3c717", "annotation_geometry_closure_sha256": "ba1d10e0105db915a63d59e0bd2107d590621942e91302f29f04419a084adbeb", "policy": "The provider local foundation and normalized geometry are accepted. This replan may inspect but not publish provider readiness, mutate product/schema/frontend bytes, or infer chart/vendor data rights."},
  "scope_classification": {"v0": "Desktop chart and market context that helps explain saved research and alerts; bounded non-executable annotation display/replay may proceed only if it reuses accepted geometry and existing identities.", "v1": "Annotations referenced as executable node inputs, derived chart features, automatic interpretation, advanced TradingView-style tooling and wider provider/chart integrations.", "external_gate": "Commercial chart-library adoption, hosted widget/API use, market-data redistribution and provider-specific annotation import require exact licence and data-rights decisions."},
  "required_docs": [
    {"path": "paper-trader/docs/strategy-os-v1-v2-v3/V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md", "sections": ["Matrix", "Release-claim rule"]},
    {"path": "paper-trader/docs/program/owner-directions/2026-08-29/01-UPDATED-OWNER-VISION-V0-TO-V6.md", "sections": ["Immediate product: V0 research, evidence, monitoring, and alerts", "Alerts as the proper V0 operational endpoint"]},
    {"path": "paper-trader/docs/program/owner-directions/2026-08-29/02-V0-COMMERCIAL-RESEARCH-AND-ALERTS-RELEASE-DIRECTIVE.md", "sections": ["Alert detail", "Alert correctness"]},
    {"path": "paper-trader/docs/agent/tasks/strategy-os-v0-normalized-annotation-geometry.md", "sections": ["goal", "scope", "acceptance", "deployment_impact", "nonclaims"]},
    {"path": ".agent/runs/strategy-os-v0-normalized-annotation-geometry/closure-seal.json", "sections": ["all"]},
    {"path": ".agent/runs/strategy-os-v0-launch-convergence/architecture-decision.md", "sections": ["Desktop-first frontend", "Deployment architecture and evidence"]},
    {"path": ".agent/runs/strategy-os-v0-launch-convergence/capsule-queue.json", "sections": ["frontend_feature_wave", "final_convergence"]},
    {"path": "paper-trader/backend/app/chart/annotation_geometry.py", "sections": ["public value types", "normalization", "applicability"]},
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/research/BacktestWorkspace.tsx", "sections": ["results visualization", "run detail navigation"]},
    {"path": "/Users/priyanshusaraf/dev/strategy-os-frontend/src/features/alerts/AlertDetail.tsx", "sections": ["alert detail", "strategy and evidence navigation"]}
  ],
  "allowed_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-chart-annotation-replay-replan.md", ".agent/runs/strategy-os-v0-chart-annotation-replay-replan"],
  "new_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-chart-annotation-replay-replan.md", ".agent/runs/strategy-os-v0-chart-annotation-replay-replan"],
  "protected_paths": ["paper-trader/backend", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/docs/agent/CURRENT.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Inventory the accepted normalized annotation geometry, chart/result surfaces, research/evidence identities, alert detail navigation and current APIs. Identify exact missing seams without creating a second IR, candle converter, data identity, research ledger or execution authority.",
    "Classify each requested capability separately: chart viewing, drawing/editing, persisted presentation annotations, historical replay, alert-linked chart context, annotations referenced from nodes, automatic chart interpretation and third-party chart/provider integration.",
    "Keep any V0 annotation fact outside executable strategy identity unless a present accepted contract proves otherwise. A V0 chart may explain data and alerts but cannot silently alter strategy signals, backtest inputs, monitoring authority or order behavior.",
    "Preserve completed-bar causality, point-in-time instrument/timeframe/data identity, UTC/session semantics, owner isolation, bounded payloads and exact strategy/research/alert linkage. Never treat screen pixels as market truth.",
    "Define the smallest serial implementation successor, exact backend/frontend/schema paths, rollout/rollback and supported desktop browser evidence. Require plain user-facing vocabulary and keep technical hashes/codes behind explicit technical details.",
    "Record V1 deferred homes for executable annotation references, automatic chart-derived signals and advanced chart tooling. Record separate licence/commercial/data-rights gates for any TradingView or external chart/data integration."
  ],
  "acceptance": [
    "The decision returns KEEP, KEEP + HARDEN, REFACTOR, REPLACE or DEFER for each chart capability with exact V0/V1/external-gate classification and controlling evidence.",
    "One present V0 operator outcome is defined without broadening monitoring into execution or making annotations part of executable identity by accident.",
    "Existing geometry, market-truth, research, alert and frontend seams are mapped to exact files and identities; missing persistence/API/rendering work has one serial owner and no shared-path collision.",
    "The successor defines desktop loading/error/empty/replay/navigation/accessibility behavior, owner isolation, causal replay, privacy and bounded resource evidence plus at least one meaningful RED/restoration/GREEN ablation.",
    "Third-party chart/library/data adoption remains closed until exact licence and data-rights review; no product, schema, dependency, provider-network, frontend or deployment byte changes in this replan."
  ],
  "test_plan": ["Read-only source/route/schema/frontend inventory and current-hash capture.", "Trace one saved research result and one alert context through existing identities; identify where chart and annotation state may attach without entering executable identity.", "Seal decision, capability matrix, collision map, implementation successor and evidence hashes; run the repository architecture validator."],
  "risk_classification": {"tier": "Critical", "reason": "Chart-derived facts can introduce look-ahead, alter executable identity, leak private strategy context, or create unlicensed data/chart dependencies if the boundary is not frozen first."},
  "parallel_budget": 1,
  "assignments": [{"id": "v0_chart_annotation_replay_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "read-only-chart-annotation-replay-replan", "depends_on": [], "write_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-chart-annotation-replay-replan.md", ".agent/runs/strategy-os-v0-chart-annotation-replay-replan"], "output": ".agent/runs/strategy-os-v0-chart-annotation-replay-replan/decision.json"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": false, "assignment_id": "v0_chart_annotation_replay_replan_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "reason": "Read-only Critical replan; any schema/frontend/runtime successor receives proportional independent review after implementation.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-chart-annotation-replay-replan/decision.json", "review_paths": ["paper-trader/docs/agent/tasks/strategy-os-v0-chart-annotation-replay-replan.md", ".agent/runs/strategy-os-v0-chart-annotation-replay-replan"], "exclude_paths": ["paper-trader/backend", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-chart-annotation-replay-replan/decision.json", "verdicts": ["SCOPE", "ARCHITECTURE", "CAUSALITY", "PRIVACY", "DATA_RIGHTS", "SUCCESSOR"], "max_rechecks": 0},
  "owner_gates": ["No product/schema/migration/dependency/frontend edit, external chart/provider request, licence/data-rights conclusion, execution/live/money, production data, commit, deploy or V0 completion claim."],
  "stop_conditions": ["A present V0 chart outcome cannot be separated from executable annotation semantics.", "A second strategy/data identity or candle conversion path would be required.", "Commercial chart/library or data-rights permission is required before the smallest local successor can be defined.", "A protected path moves under concurrent ownership."],
  "deployment_impact": {"classification": "none for read-only replan; successor may be schema/frontend/runtime changing", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No public chart, annotation editor, replay, executable annotation node, automatic chart interpretation, provider/chart rights, release deployability, deployment or V0 completion."],
  "result": {
    "decision": "KEEP + HARDEN",
    "present_v0_outcome": "Owner-scoped desktop Market context for verified saved research, with completed-bar replay and private non-executable review drawings; alert entry is a later monitoring-owned addendum.",
    "decision_path": ".agent/runs/strategy-os-v0-chart-annotation-replay-replan/decision.json",
    "decision_sha256": "95e77177d8b0f4685efd3755fcc25dba6ec5992f536069f396345e52cc405fe4",
    "inventory_path": ".agent/runs/strategy-os-v0-chart-annotation-replay-replan/evidence-inventory.md",
    "inventory_sha256": "d9ae11b102bd9c051e0aa99b48a11018565f6e2802f8f030500bef79137614d7",
    "report_path": ".agent/runs/strategy-os-v0-chart-annotation-replay-replan/report.md",
    "report_sha256": "45b411b019b84b6a0f7ea19fecd3d0ab3e07b1b33a4c2a2270057f96a330d1e3",
    "successor": "strategy-os-v0-research-market-context-annotation-replay-implementation",
    "successor_path": ".agent/runs/strategy-os-v0-chart-annotation-replay-replan/successor-capsule.json",
    "successor_sha256": "974dc0c9e1fb8198b864d4486778fb7e7b080dcd573a2ede04fba3dbe1a7a52e",
    "orientation_sha256": "14ad1f0009fa0f411a32724723c92cbeeb7b1b6f0b7772ce3442da5674113305",
    "closure_seal_path": ".agent/runs/strategy-os-v0-chart-annotation-replay-replan/closure-seal.json",
    "v1_deferred": [
      "strategy-os-v1-executable-annotation-input-contract",
      "strategy-os-v1-chart-interpretation-research-contract",
      "strategy-os-v1-advanced-chart-tooling",
      "strategy-os-v1-licensed-chart-and-provider-integration",
      "strategy-os-v1-provider-chart-data-expansion"
    ],
    "migration_path": "0051 provisional on a fresh sole-0050 head and collision recheck",
    "alert_integration_addendum": "strategy-os-v0-desktop-monitoring-alerts-market-context-addendum after strategy-os-v0-monitoring-api",
    "third_party_chart_dependency": false,
    "product_writes": 0,
    "schema_writes": 0,
    "frontend_writes": 0,
    "provider_requests": 0,
    "review_run": false,
    "deployment": false,
    "v0_complete": false
  }
}
---

# Chart, annotation and replay replan

Freeze a useful V0 chart-context boundary before any product integration. Keep
annotation-derived strategy logic and automatic chart interpretation in V1.
