---
{
  "id": "strategy-os-v0-worker-quota-recovery",
  "phase": "v0",
  "kind": "bounded_parallel_implementation",
  "status": "assigned_waiting_start",
  "goal": "Prove and harden only reproduced failures in existing research operation quota, claim, cancellation and process recovery",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Exact scoped implementation/evidence, preservation and genuine guard proof plus the one independent SPEC PASS/QUALITY PASS. No public capability, indicator, deployment or whole-V0 acceptance."
  },
  "risk_tags": [
    "critical",
    "tenancy-recovery",
    "parallel-owned"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/03-V0-SCOPE-AND-GOLDEN-PATH.md",
      "sections": [
        "Public V0 scope",
        "Canonical V0 objects"
      ]
    },
    {
      "path": "paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md",
      "sections": [
        "1. Risk-weighted verification",
        "2. Test rule",
        "3. Test cadence"
      ]
    },
    {
      "path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/06-TEST-SECURITY-DATA-AND-DEPLOYMENT-GATES.md",
      "sections": [
        "Backtest and robustness",
        "Security and tenancy",
        "Frontend and operations",
        "Deployability gates"
      ]
    }
  ],
  "dependency_gate": "strategy-os-v0-release-profile-foundation",
  "programme_assignment": {
    "assignment_id": "v0_worker_quota_recovery",
    "parent_stage": "post-phase5-indicator-accuracy-multi-output-assurance",
    "primary_programme_owner": false,
    "coordinator": "01a04a11-4342-7ae0-97cf-95c27ee7ef37",
    "prerequisite": "Read-only orientation until exact owner/metadata seal and actual START; no routine user token."
  },
  "allowed_paths": [
    "paper-trader/backend/research/domain/operations.py",
    "paper-trader/backend/research/operations.py",
    "paper-trader/backend/research_tests/test_operation_repository.py",
    "paper-trader/backend/research_tests/test_operation_claim_contract.py",
    "paper-trader/backend/research_tests/test_postgres_operation_concurrency.py",
    "paper-trader/backend/research_tests/test_operations.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-worker-quota-recovery.md",
    ".agent/runs/strategy-os-v0-worker-quota-recovery"
  ],
  "new_paths": [],
  "protected_paths": [
    "AGENTS.md",
    ".codex",
    ".agents",
    "paper-trader/docs/agent/CURRENT.md",
    "paper-trader/docs/agent/programme/PROGRAMME.json",
    "paper-trader/docs/agent/DEPLOYABILITY.md",
    "paper-trader/backend/app/ir",
    "paper-trader/backend/app/market_truth",
    "paper-trader/backend/app/db",
    "paper-trader/backend/migrations",
    "paper-trader/backend/app/main.py",
    "paper-trader/backend/app/api",
    "paper-trader/backend/app/providers",
    "paper-trader/backend/app/engine",
    "paper-trader/backend/app/execution",
    "paper-trader/frontend",
    "/Users/priyanshusaraf/dev/strategy-os-frontend",
    "paper-trader/backend/research/domain/base.py",
    "paper-trader/backend/research/domain/models.py",
    "paper-trader/backend/research/domain/migrations",
    "paper-trader/backend/tests/conftest.py",
    "paper-trader/backend/research_tests/conftest.py",
    "paper-trader/backend/requirements.lock",
    "paper-trader/backend/scripts/run_research_worker.py",
    "paper-trader/scripts/deploy.sh",
    "paper-trader/backend/app/chart/__init__.py",
    "paper-trader/backend/app/chart/annotation_geometry.py",
    "paper-trader/backend/tests/test_annotation_geometry.py"
  ],
  "stable_input_hashes": [
    {
      "path": "paper-trader/backend/research/domain/base.py",
      "sha256": "887b76ec30fd31778e1646481ba0cf470c69c99ba1aa7838b7b8024b45a59a80"
    },
    {
      "path": "paper-trader/backend/research/domain/models.py",
      "sha256": "54a438809170ede0a085b0ff846bb189a46446d6cb7a2cf94ae6971335decb07"
    },
    {
      "path": "paper-trader/backend/app/db/concurrency.py",
      "sha256": "1e355d79f393db3b00433713d90244921a655525713d5e47f17ebdec99f45343"
    },
    {
      "path": "paper-trader/backend/app/events/planes.py",
      "sha256": "03b9c2852b359b6d602284654ab3071a803cdb5f9ef490124b530068de4691c2"
    },
    {
      "path": "paper-trader/backend/app/core/release_profile.py",
      "sha256": "bac0d0b76af0711e44d98af7e819cc42db0addce70b6658b251aaca23026b0a5"
    },
    {
      "path": "paper-trader/backend/scripts/run_research_worker.py",
      "sha256": "67999ef07aee9cc7dab29e3848287bbb3804f5855fa19253d5859bd08737f2c6"
    }
  ],
  "scope": [
    "Exercise the existing ResearchOperationRepository, DurableOperationRecorder and optional file mirror, including real SQLite and disposable PostgreSQL16 transactions/processes. Correct only reproduced defects inside the two named product files. Do not create a new queue, scheduler, worker service or provider runner.",
    "Preserve exact owner isolation, admission/claim quota constants, persisted plan/seed/build identity, lease fencing, cancellation terminality, item/run atomic finalization, restart/reclaim and canonical file receipts. No schema/model/concurrency helper/migration/IR/runtime/entrypoint change without a separately declared serial correction.",
    "Use existing synthetic/no-provider jobs through actual repository/recorder consumers; demonstrate process death/restart and stale-worker refusal. Never call these exactly-once provider calls or uninterruptible-job preemption. Resource/cancellation latency observations are local bounds, not production capacity promises."
  ],
  "acceptance": [
    "Exercise the existing ResearchOperationRepository, DurableOperationRecorder and optional file mirror, including real SQLite and disposable PostgreSQL16 transactions/processes. Correct only reproduced defects inside the two named product files. Do not create a new queue, scheduler, worker service or provider runner.",
    "Preserve exact owner isolation, admission/claim quota constants, persisted plan/seed/build identity, lease fencing, cancellation terminality, item/run atomic finalization, restart/reclaim and canonical file receipts. No schema/model/concurrency helper/migration/IR/runtime/entrypoint change without a separately declared serial correction.",
    "Use existing synthetic/no-provider jobs through actual repository/recorder consumers; demonstrate process death/restart and stale-worker refusal. Never call these exactly-once provider calls or uninterruptible-job preemption. Resource/cancellation latency observations are local bounds, not production capacity promises.",
    "Complete exact boundary, source/contract and local evidence with one independent critical review; all deferred integration owners and negative evidence are explicit."
  ],
  "test_plan": [
    "Run the four owned operation test files and existing operation migration/recovery plus tests/test_research_operation_routes.py as compatibility, preserving all historical tests/skips/raw failures.",
    "Add bounded real consumer/process/concurrency tests in existing test files: queue/active/item owner and host caps, trigger/exact-job claim, competing workers, process death before/after durable item checkpoint, cancelled/expired/replaced tokens, watchdog exception, duplicate completion, rollback and owner-local outbox/events. Real PG16 evidence, no stub-only PG PASS.",
    "Measure representative bounded owner/host workloads without changing quota policy to pass. Isolated genuine fencing/cancel/quota mutations must reach intended assertion failures0errors/skips and restore exact copies. If no product defect reproduces, preserve product and close only the tested recovery contract after independent review."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "fork_turns": "none",
  "owner_task": "01a04a21-3da1-7fd0-81ba-44b511b4eb2c",
  "owner_gates": [
    "Standing V0 development and explicit parallel-work authority applies. You are not alone; preserve all inherited/peer work. No stash/reset/clean/rebase/stage/commit.",
    "Use safe existing .venv/run_logged, mock/paper/disabled dotenv/empty live ack/distinct temporary databases. No HOME/CODEX_HOME override. No provider/broker networks, live credentials, VPS, money/orders, deployment, dependency adoption or shared-file shortcut.",
    "Zero implementation agents. Coordinator alone routes one critical reviewer after integrated evidence; no live reviewer or duplicate review."
  ],
  "stop_conditions": [
    "Undeclared shared contract/source or schema change is needed: retain reproduction and return exact correction scope to coordinator.",
    "No invented expected values, unverified PASS or placeholder public capability.",
    "First automatic compaction requires fresh-context handoff before a second."
  ],
  "nonclaims": [
    "No public chart/replay/annotation integration or provider/data/numerical acceptance.",
    "No production-shaped worker or deployment guarantee from local process/PG proof."
  ],
  "deployment_impact": {
    "classification": "compatible-local-research-recovery-hardening-no-schema",
    "required_evidence": "Exact local dependency/source/resource/restart facts; geometry integration belongs to strategy-os-v0-chart-annotation-replay, research service/capacity and release assembly to strategy-os-v0-security-operations-deployability before their acceptance."
  },
  "review": {
    "required": true,
    "assignment_id": "v0_worker_quota_recovery_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "One final independent review of owner-scoped fencing, durable recovery and quota integrity.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-worker-quota-recovery/review-package.json",
    "review_paths": [
      "paper-trader/backend/research/domain/operations.py",
      "paper-trader/backend/research/operations.py",
      "paper-trader/backend/research_tests/test_operation_repository.py",
      "paper-trader/backend/research_tests/test_operation_claim_contract.py",
      "paper-trader/backend/research_tests/test_postgres_operation_concurrency.py",
      "paper-trader/backend/research_tests/test_operations.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/strategy-os-v0-worker-quota-recovery/review.md",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "routing_seal": ".agent/runs/strategy-os-v0-parallel-next-leaf-materialization/closure-seal.json"
}
---

# Prove and harden only reproduced failures in existing research operation quota, claim, cancellation and process recovery

Exact queued V0 development only. Await sealed START before product work.
