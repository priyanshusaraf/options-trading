---
{
  "id": "strategy-os-v0-normalized-annotation-geometry",
  "phase": "v0",
  "kind": "bounded_parallel_implementation",
  "status": "assigned_waiting_start",
  "goal": "Implement immutable normalized geometry and pure causal applicability without renderer, persistence or graph publication",
  "goal_contract": {
    "create_before_work": true,
    "stopping_condition": "Exact scoped implementation/evidence, preservation and genuine guard proof plus the one independent SPEC PASS/QUALITY PASS. No public capability, indicator, deployment or whole-V0 acceptance."
  },
  "risk_tags": [
    "critical",
    "causal-research",
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
      "path": "paper-trader/docs/strategy-os-v0-release-audit-2026-08-27/05-ARCHITECTURE-AND-RELEASE-PROFILE.md",
      "sections": [
        "Chart and annotation architecture"
      ]
    },
    {
      "path": ".agent/runs/strategy-os-v0-parallel-next-leaf-materialization/geometry-contract.md",
      "sections": [
        "Scope and precedence",
        "Representation and identity",
        "Geometry",
        "Causal applicability",
        "Proof and nonclaims"
      ]
    }
  ],
  "dependency_gate": "strategy-os-v0-release-profile-foundation",
  "programme_assignment": {
    "assignment_id": "v0_annotation_geometry",
    "parent_stage": "post-phase5-indicator-accuracy-multi-output-assurance",
    "primary_programme_owner": false,
    "coordinator": "01a04a11-4342-7ae0-97cf-95c27ee7ef37",
    "prerequisite": "Read-only orientation until exact owner/metadata seal and actual START; no routine user token."
  },
  "allowed_paths": [
    "paper-trader/backend/app/chart/__init__.py",
    "paper-trader/backend/app/chart/annotation_geometry.py",
    "paper-trader/backend/tests/test_annotation_geometry.py",
    "paper-trader/docs/agent/tasks/strategy-os-v0-normalized-annotation-geometry.md",
    ".agent/runs/strategy-os-v0-normalized-annotation-geometry"
  ],
  "new_paths": [
    "paper-trader/backend/app/chart/__init__.py",
    "paper-trader/backend/app/chart/annotation_geometry.py",
    "paper-trader/backend/tests/test_annotation_geometry.py"
  ],
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
    "paper-trader/backend/research/domain/operations.py",
    "paper-trader/backend/research/operations.py",
    "paper-trader/backend/research_tests/test_operation_repository.py",
    "paper-trader/backend/research_tests/test_operation_claim_contract.py",
    "paper-trader/backend/research_tests/test_postgres_operation_concurrency.py",
    "paper-trader/backend/research_tests/test_operations.py"
  ],
  "stable_input_hashes": [
    {
      "path": "paper-trader/backend/app/ir/hashing.py",
      "sha256": "5c1b834af7684cc4c0a7525966cb5497cf723a2d4f4c9a50261bb6beb5053fbf"
    },
    {
      "path": "paper-trader/backend/app/market_truth/identity.py",
      "sha256": "c990e27bcb314f9b9a11d47144374edda2199fae244868184c43602b2f1867b7"
    },
    {
      "path": "paper-trader/backend/app/market_truth/temporal.py",
      "sha256": "eb52ae1599003c3dd40ed1abf6280054996bd860a60786ee87459ec571a3d1a2"
    },
    {
      "path": "paper-trader/backend/app/core/release_profile.py",
      "sha256": "bac0d0b76af0711e44d98af7e819cc42db0addce70b6658b251aaca23026b0a5"
    }
  ],
  "scope": [
    "Implement only the closed normalized geometry/applicability contract in the exact named new module/package and focused test. Before edits record the exact canonical decimal/derived-value representation; keep that bounded decision consistent with geometry-contract.md. No renderer, provider, persistence, IR/registry or public API.",
    "Reuse the sole canonical hashing functions and existing UTC/authority conventions. Exact local mathematical vectors, closed serialization, input/resource bounds and causal boundaries must pass. No numerical indicator or executable graph publication."
  ],
  "acceptance": [
    "Implement only the closed normalized geometry/applicability contract in the exact named new module/package and focused test. Before edits record the exact canonical decimal/derived-value representation; keep that bounded decision consistent with geometry-contract.md. No renderer, provider, persistence, IR/registry or public API.",
    "Reuse the sole canonical hashing functions and existing UTC/authority conventions. Exact local mathematical vectors, closed serialization, input/resource bounds and causal boundaries must pass. No numerical indicator or executable graph publication.",
    "Complete exact boundary, source/contract and local evidence with one independent critical review; all deferred integration owners and negative evidence are explicit."
  ],
  "test_plan": [
    "First reproduce absence/import boundary and add meaningful exact mathematical/identity/causal tests; do not claim absent code is a runtime product defect.",
    "Run tests/test_annotation_geometry.py plus existing IR hashing and market-truth identity affected tests. Independently author exact expected geometry; complete slope/channel/Fibonacci/extension and applicability boundary coverage, zero/nonfinite/reversed/unknown/oversized inputs.",
    "Measure max declared ratio/input payload demand. Mutate a real geometry calculation and the lock/as_of guard in isolated copies, demonstrate intended assertion failures0errors/skips, restore and rerun."
  ],
  "model_route": {
    "owner": "gpt-5.6-sol",
    "owner_reasoning_effort": "medium",
    "service_tier": "priority"
  },
  "parallel_budget": 0,
  "assignments": [],
  "fork_turns": "none",
  "owner_task": "01a04a20-fbcd-7571-a24b-26ab5367ba67",
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
    "classification": "compatible-unpublished-value-module",
    "required_evidence": "Exact local dependency/source/resource/restart facts; geometry integration belongs to strategy-os-v0-chart-annotation-replay, research service/capacity and release assembly to strategy-os-v0-security-operations-deployability before their acceptance."
  },
  "review": {
    "required": true,
    "assignment_id": "v0_annotation_geometry_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "reason": "One final independent review of causal semantic identity.",
    "base_sha": "de6faae3e97cf5537338bee2143350e53f70da1c",
    "package": ".agent/runs/strategy-os-v0-normalized-annotation-geometry/review-package.json",
    "review_paths": [
      "paper-trader/backend/app/chart/__init__.py",
      "paper-trader/backend/app/chart/annotation_geometry.py",
      "paper-trader/backend/tests/test_annotation_geometry.py"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/strategy-os-v0-normalized-annotation-geometry/review.md",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  },
  "routing_seal": ".agent/runs/strategy-os-v0-parallel-next-leaf-materialization/closure-seal.json"
}
---

# Implement immutable normalized geometry and pure causal applicability without renderer, persistence or graph publication

Exact queued V0 development only. Await sealed START before product work.
