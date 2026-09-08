---
{
  "id": "strategy-os-v0-zerodha-data-static-scope",
  "lineage_id": "strategy-os-v0-paper-trading-runtime-foundation",
  "phase": "v0",
  "status": "rejected_after_exhausted_recheck",
  "kind": "critical_paper_only_signal_orchestration_runtime",
  "goal": "Implement an additive local Strategy OS runtime that translates exact monitoring signals into deterministic paper-only intent/effect outcomes with SL/TP attribution, independent alert/paper branches and restart-safe idempotency.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Paper-only contracts/planner/service process legitimate ALERTS/PAPER/BOTH synthetic signals, produce or resume one exact paper effect, preserve alerts independently, reject live/foreign/stale/duplicate mismatches, reconstruct after failure and pass Critical execution/reconciliation review."},
  "risk_tags": ["critical", "paper-trading", "execution", "money", "reconciliation", "idempotency", "restart", "alerts"],
  "depends_on": ["strategy-os-v0-paper-trading-runtime-replan", "strategy-os-v0-paper-entry-lifecycle-identity-correction", "strategy-os-v0-paper-guard-semantic-manifest-correction", "strategy-os-v0-monitoring-persistence-orchestration-foundation"],
  "dependency_gate": {"decision": ".agent/runs/strategy-os-v0-paper-trading-runtime-replan/decision.json", "policy": "Paper-only mock/replay local runtime may proceed; real provider/live/shared publication/deployment remain closed."},
  "required_docs": [
    {"path": ".agent/runs/strategy-os-v0-paper-trading-runtime-replan/decision.json", "sections": ["existing_accepted_authorities", "rejected_options", "missing_runtime_seams", "chosen_architecture", "state_and_recovery_requirements", "external_gates"]},
    {"path": ".agent/runs/strategy-os-v0-paper-trading-runtime-replan/authority-matrix.md", "sections": ["V0 paper runtime authority and recovery matrix"]},
    {"path": ".agent/runs/strategy-os-v0-owner-direction-extension-2026-08-29/report.md", "sections": ["Alerts, Paper and Both orchestration", "Paper state and reconciliation contract"]}
  ],
  "allowed_paths": ["paper-trader/backend/app/paper_runtime/__init__.py", "paper-trader/backend/app/paper_runtime/contracts.py", "paper-trader/backend/app/paper_runtime/service.py", "paper-trader/backend/app/engine/broker.py", "paper-trader/backend/app/db/migrate.py", "paper-trader/backend/app/db/schema_semantics.py", "paper-trader/backend/tests/test_v0_paper_runtime.py", "paper-trader/backend/tests/test_v0_paper_runtime_recovery.py", "paper-trader/backend/tests/test_paper_guard_semantic_manifest.py", "paper-trader/docs/agent/tasks/strategy-os-v0-paper-trading-runtime-foundation.md", ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation"],
  "new_paths": ["paper-trader/backend/app/paper_runtime/__init__.py", "paper-trader/backend/app/paper_runtime/contracts.py", "paper-trader/backend/app/paper_runtime/service.py", "paper-trader/backend/tests/test_v0_paper_runtime.py", "paper-trader/backend/tests/test_v0_paper_runtime_recovery.py", "paper-trader/docs/agent/tasks/strategy-os-v0-paper-trading-runtime-foundation.md", ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation"],
  "protected_paths": ["paper-trader/backend/app/db/models.py", "paper-trader/backend/migrations", "paper-trader/backend/app/core/paper_authority.py", "paper-trader/backend/app/core/execution_binding.py", "paper-trader/backend/app/execution", "paper-trader/backend/app/monitoring", "paper-trader/backend/app/ledger", "paper-trader/backend/app/engine/live_broker.py", "paper-trader/backend/app/providers", "paper-trader/backend/app/api", "paper-trader/backend/app/main.py", "paper-trader/backend/research", "paper-trader/frontend", "/Users/priyanshusaraf/dev/strategy-os-frontend", "paper-trader/scripts/deploy.sh"],
  "scope": [
    "Create immutable runtime assignment, effect preference, canonical instrument/admission authority, paper command and per-branch result contracts with strict codecs and complete use-time validation.",
    "Plan BUY/SELL/EXIT/HOLD from exact immutable MonitoringSignalEvent data; preserve event/assignment/deployment/graph/implementation/instrument/entry/SL/TP/time/validity attribution.",
    "Derive deterministic 32-lower-hex paper client intent ID from domain, assignment address, monitoring event address and action; full addresses remain in canonical context JSON.",
    "Extend PaperBroker only to accept and validate exact paper-runtime context JSON while preserving legacy default and every paper entry/charge/exit guard.",
    "Service accepts exact PaperBroker/book and synthetic mock/replay provider only. It consumes exact approved quantity/admission address; no sizing or provider selection authority.",
    "ALERTS, PAPER and BOTH branches are independent/idempotent. HOLD has no paper effect. Entry/exit retry verifies exact existing intent/position/trade before returning already-applied; mismatch/unknown requires reconciliation and never blind resend.",
    "Entries fail closed on paused/expired/foreign/stale assignment, admission, kill/ARM or fence. Risk-reducing EXIT remains available under entry disarm according to existing authority.",
    "No schema/migration, live broker/mode, network, real provider, shared API/frontend, worker activation or deployment."
  ],
  "acceptance": [
    "Legitimate synthetic BUY and SELL open exact paper positions with entry/SL/TP/source attribution; EXIT closes the held campaign/position, HOLD does nothing.",
    "ALERTS/PAPER/BOTH invoke exactly selected branches; failure/retry of one branch cannot duplicate/regress the other.",
    "Duplicate and concurrent signal retries produce one intent, one position/campaign/tranche/fill/cash effect and one alert; exact retry returns already-applied and mismatched reuse refuses.",
    "Death checkpoints before intent, after intent, after paper commit/before return and restart/reclaim reconstruct without blind resend or duplicated ledger/charges.",
    "Partial/close retry, stale fence, paused/withdrawn binding, expired event, unknown provider state, capital refusal, ARM/kill entry and risk-reducing exit matrices pass.",
    "Static/live/network poison and source/import guards prove live unreachable; existing affected paper/money/monitoring suites remain green.",
    "Resource/capacity bound, deployability impact and one Critical SPEC/QUALITY execution/reconciliation review pass."
  ],
  "test_plan": ["RED/GREEN strict runtime assignment/planner/context codecs and deterministic IDs.", "SQLite actual PaperBroker entries/exits with synthetic instruments/provider and exact money/charge/lineage assertions.", "Alerts/Paper/Both idempotency/concurrency/restart checkpoint matrix.", "Kill/ARM/fence/capital/expiry/foreign/mismatch/live/network poison and isolated mutations.", "Affected paper authority/broker/lifecycle/capital/lineage/monitoring/charge suites, architecture and protected manifests."],
  "risk_classification": {"tier": "Critical", "reason": "This slice creates user-visible paper money, positions, PnL and execution effects and sits adjacent to structurally forbidden live execution."},
  "parallel_budget": 2,
  "assignments": [{"id": "v0_paper_trading_runtime_correction_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-product-test-evidence", "depends_on": [], "write_paths": ["paper-trader/backend/app/paper_runtime/__init__.py", "paper-trader/backend/app/paper_runtime/contracts.py", "paper-trader/backend/app/paper_runtime/service.py", "paper-trader/backend/app/engine/broker.py", "paper-trader/backend/tests/test_v0_paper_runtime.py", "paper-trader/backend/tests/test_v0_paper_runtime_recovery.py", ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation/correction-runtime"], "output": ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation/correction-runtime/report.md"}, {"id": "v0_paper_manifest_authority_correction_owner", "agent": "worker", "model": "gpt-5.6-sol", "reasoning_effort": "medium", "fork_turns": "none", "mode": "write-product-test-evidence", "depends_on": [], "write_paths": ["paper-trader/backend/app/db/migrate.py", "paper-trader/backend/app/db/schema_semantics.py", "paper-trader/backend/tests/test_paper_guard_semantic_manifest.py", ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation/correction-manifest"], "output": ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation/correction-manifest/report.md"}],
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "fork_turns": "none", "service_tier": "priority"},
  "owner_task": "/root",
  "review": {"required": true, "assignment_id": "v0_paper_trading_runtime_review", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "reason": "Paper money, intent idempotency, position ownership, shared manifest authority and live adjacency require integrated Critical review.", "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c", "package": ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation/review-package.json", "review_paths": ["paper-trader/backend/app/paper_runtime/__init__.py", "paper-trader/backend/app/paper_runtime/contracts.py", "paper-trader/backend/app/paper_runtime/service.py", "paper-trader/backend/app/engine/broker.py", "paper-trader/backend/app/db/migrate.py", "paper-trader/backend/app/db/schema_semantics.py", "paper-trader/backend/tests/test_v0_paper_runtime.py", "paper-trader/backend/tests/test_v0_paper_runtime_recovery.py", "paper-trader/backend/tests/test_paper_guard_semantic_manifest.py", "paper-trader/docs/agent/tasks/strategy-os-v0-paper-trading-runtime-foundation.md", ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation"], "exclude_paths": ["paper-trader/backend/app/db/models.py", "paper-trader/backend/migrations", "paper-trader/backend/app/core", "paper-trader/backend/app/execution", "paper-trader/backend/app/monitoring", "paper-trader/backend/app/ledger", "paper-trader/backend/app/engine/live_broker.py", "paper-trader/backend/app/providers", "paper-trader/backend/app/api", "paper-trader/backend/app/main.py", "paper-trader/backend/research", "paper-trader/frontend", "paper-trader/scripts/deploy.sh"], "output": ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation/review/verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "correction": {"first_verdict": ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation/review/verdict.json", "first_verdict_sha256": "b0ebccad02d6395021489176ca19d8e1a49cac7ddae7fdea5f8bda90f37587f6", "finding_ids": ["SPEC-P0-001", "SPEC-P0-002", "SPEC-P0-003", "SPEC-P1-004", "SPEC-P1-005", "QUALITY-P0-001", "QUALITY-P1-002", "QUALITY-P1-003"], "runtime_report": ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation/correction-runtime/report.md", "runtime_report_sha256": "5fb388d0c0ed6ddcdf7e222a57369d143e9ada8e170d27935585327a03fc0628", "manifest_report": ".agent/runs/strategy-os-v0-paper-trading-runtime-foundation/correction-manifest/report.md", "manifest_report_sha256": "b2491c09fa8046aa6b7580de2654feae4dd14c427a30786e868b5b4ac43f2da1", "rechecks_used": 0, "rechecks_remaining": 1, "policy": "Route only the declared focused recheck against the frozen package path; the package hash is sealed outside the dirty-tree fingerprint."},
  "owner_gates": ["No real provider/network/data rights, live IR/assignment/order/capital authority, shared API/frontend, production account/data, VPS/deployment or live money action."],
  "stop_conditions": ["Implementation needs schema/shared route/live/provider authority, changes canonical money/position meaning or cannot make branch effects independently idempotent.", "Broker path ownership conflicts."],
  "deployment_impact": {"classification": "architecture-changing local paper-only runtime", "highest_claim": "locally_runnable", "release_deployable": false, "production_rehearsed": false, "deployed": false},
  "nonclaims": ["No real provider, live execution, public API/frontend, deployment, release readiness or V0 completion."
  ]
}
---

# Paper trading runtime foundation

One deterministic, restart-safe paper-only event-to-effect runtime.

## Implementation checkpoint

Status: `implementation_complete_pending_critical_review`.

The exact owner assignment materialized the additive `app.paper_runtime` contracts,
planner and service, the canonical PaperBroker runtime-context seam, and the two
declared Critical test modules. No schema, migration, shared route, provider
selection, live path, frontend, worker activation or deployment changed.

The focused matrix is green. The wider affected paper/money suite has two inherited
protected-boundary failures in `test_paper_guard_semantic_manifest.py`; they are
recorded in the owner report and remain outside this assignment's write authority.
Critical SPEC/QUALITY review is still required before acceptance.
