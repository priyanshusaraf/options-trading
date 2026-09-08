---
{
  "id": "phase5-research-runtime-packaging",
  "phase": "phase5",
  "status": "review",
  "kind": "runtime_packaging",
  "goal": "Produce reproducible locked research-worker packaging with explicit API/worker/queue/cache/artifact roles, bounded concurrency, restart, health, observability and production-shaped local evidence.",
  "goal_contract": {"create_before_work": true, "stopping_condition": "Complete only after locked clean install, explicit service roles, bounded database/queue/cache/artifact resources, graceful stop/restart, schema/build health, failure visibility and identical output pass in a production-shaped local environment without claiming deployment readiness."},
  "risk_tags": ["high", "packaging", "services", "dependencies", "deployability"],
  "required_docs": [{"path": "paper-trader/docs/agent/DEPLOYABILITY.md", "sections": ["Current verdict", "Phase 5 ownership", "V1 release gate"]}, {"path": "paper-trader/docs/superpowers/specs/phase5-strategy-os-design.md", "sections": ["Deployment impact and nonclaims"]}],
  "dependency_gate": "phase5-bounded-sweeps-cache-artifacts",
  "allowed_paths": ["paper-trader/backend/requirements.lock", "paper-trader/backend/app/backtest/worker.py", "paper-trader/backend/scripts/run_research_worker.py", "paper-trader/backend/tests/test_phase5_research_runtime_packaging.py", "paper-trader/docs/agent/DEPLOYABILITY.md", ".agent/runs/phase5-research-runtime-packaging", "paper-trader/docs/agent/tasks/phase5-research-runtime-packaging.md", "paper-trader/docs/agent/programme/PROGRAMME.json", "paper-trader/docs/agent/CURRENT.md"],
  "nonclaims": ["No deployment, production rehearsal, managed PostgreSQL/object store, TLS, production credentials, provider, live, order, or money authority.", "Production topology, backup/restore, rollback, security, capacity and exact-build smoke remain V1 gates."],
  "owner_gates": ["Stop before production services/data/credentials, VPS, deployment, managed infrastructure, destructive retention, network exposure, or unreviewed dependency/licence adoption."],
  "stop_conditions": ["Dependencies are mutable/unlocked; API and research work share an unbounded process/queue; health can be false green; restart loses or duplicates work; database/cache/artifact limits are absent; local evidence is labelled release-deployable."],
  "deployment_impact": {"classification": "architecture-changing", "required_evidence": "Build, dependencies, configuration, PostgreSQL connections, service roles, health, observability, capacity bounds and restart evidence at locally_runnable only; all V1 release rows remain owned."},
  "model_route": {"owner": "gpt-5.6-sol", "owner_reasoning_effort": "medium", "service_tier": "priority"},
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": ["A pinned lock installs reproducibly from a clean local environment and records exact build identity.", "API, worker, queue, cache and artifact roles and dependency order are explicit; research saturation cannot occupy risk-reducing execution resources.", "Concurrency, connections, queue, cache, memory, disk and retention are bounded with typed degradation/refusal.", "Graceful stop, forced worker death, restart, stale claim, duplicate delivery and artifact failure remain safe and visible.", "Health reports build, execution/research heads, database/queue/cache/artifact readiness and worker capacity without false green.", "Deployment ledger records every remaining release/production obligation and exact owner."],
  "test_plan": ["Clean locked install and import/build identity.", "Local production-shaped API/worker topology with temporary databases/artifacts.", "Restart, process death, duplicate delivery and health failure matrix.", "Connection/queue/cache/disk/memory ceilings and degradation.", "No-live/provider/credential checks and deployability ledger validation."],
  "review": {"required": true, "assignment_id": "phase5_runtime_packaging_reviewer", "agent": "critical-reviewer", "model": "gpt-5.6-sol", "reasoning_effort": "high", "base_sha": "HEAD", "package": ".agent/runs/phase5-research-runtime-packaging/review-package.json", "review_paths": ["paper-trader/backend/requirements.lock", "paper-trader/backend/app/backtest/worker.py", "paper-trader/backend/app/backtest/artifacts.py", "paper-trader/backend/scripts/run_research_worker.py", "paper-trader/backend/tests/test_phase5_research_runtime_packaging.py", "paper-trader/docs/agent/DEPLOYABILITY.md"], "exclude_paths": [], "output": ".agent/runs/phase5-research-runtime-packaging/review/recheck-verdict.json", "verdicts": ["SPEC", "QUALITY"], "max_rechecks": 1},
  "implementation": {"status": "focused_recheck_evidence_ready", "prior_review_verdict_sha256": "64df021079e8f698a3d08c240ee60c8beb8088ee5550bae86b798c8d33cf705d", "report_sha256": "309db79d50c978908fad18250f69bb410bbf34f5c82aed08ccb2a0799391d38c", "deployability_sha256": "13a74b4e787f0b9fa8fa686d095d82f7467f254a2a1bbed540423bc3b3d76c0d", "evidence_sha256": "5985df94c09017b37b4c87b97376e6476e52e0251b09f70290fcb1845edafed1", "lock_packages": 59, "focused_passed": 19, "lifecycle_passed": 50, "mutations": 5}
}
---

# Phase 5 research runtime packaging

This capsule may prove a production-shaped local research topology. It cannot deploy or claim production rehearsal.
