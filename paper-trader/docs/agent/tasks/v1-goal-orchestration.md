---
{
  "id": "v1-goal-orchestration",
  "phase": "agent-architecture-migration",
  "status": "review",
  "goal": "Install and verify the durable Strategy OS goal programme from the rejected Phase 3 gate through V1 release without widening product scope.",
  "risk_tags": [
    "critical",
    "agent-authority",
    "programme-orchestration",
    "dirty-tree-integration"
  ],
  "required_docs": [
    {
      "path": "paper-trader/docs/superpowers/specs/2026-08-14-strategy-os-v1-goal-orchestration-design.md",
      "sections": ["Goal contract", "Dispatcher contract", "Acceptance and rollout"]
    },
    {
      "path": "paper-trader/docs/agent/programme/PROGRAMME.json",
      "sections": ["Complete programme state"]
    },
    {
      "path": "paper-trader/docs/agent/programme/GOAL_TEMPLATES.md",
      "sections": ["Dispatcher task", "Critical phase-review goal"]
    }
  ],
  "allowed_paths": [
    ".agents",
    ".codex",
    ".gitattributes",
    "AGENTS.md",
    "paper-trader/AGENTS.md",
    "paper-trader/backend/AGENTS.md",
    "paper-trader/frontend/AGENTS.md",
    "paper-trader/docs/agent",
    "paper-trader/docs/superpowers/plans/2026-08-14-strategy-os-v1-goal-orchestration.md",
    "paper-trader/docs/superpowers/specs/2026-08-14-strategy-os-v1-goal-orchestration-design.md"
  ],
  "nonclaims": [
    "This capsule does not accept Phase 3 Task 12 or implement product code.",
    "It does not authorize live money, deployment, credentials, VPS access, frontend implementation, or owner-gated product decisions.",
    "The three-slice token-reduction target remains a measured rollout gate rather than a pre-install claim."
  ],
  "owner_gates": [
    "Stop if integration changes the preserved Phase 3 dirty diff, untracked manifest, or protected hashes.",
    "Stop if the installed automation cannot query authoritative Codex task state.",
    "Stop before any live, deployment, credential, VPS, or frontend action."
  ],
  "stop_conditions": [
    "The architecture package or evidence is missing, stale, partial, or not bound to the reviewed commit.",
    "The native reviewer launch is not authorized by this exact tracked capsule route.",
    "Either final SPEC or QUALITY verdict fails."
  ],
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "reviewer": "gpt-5.6-sol",
    "reviewer_reasoning_effort": "high"
  },
  "parallel_budget": 0,
  "assignments": [],
  "acceptance": [
    "The complete architecture diff and evidence are commit-bound and pass the native reviewer guard through this exact route.",
    "The dispatcher validates source hashes and headings, capsule identity, source view, stage route, dependencies, lease state, and authoritative active-goal count before dispatch.",
    "The preserved Phase 3 state matches its private recovery snapshot after integration.",
    "A Luna-medium scheduled dispatcher is installed and a Terra-medium Phase 3 correction task creates its durable goal.",
    "One final Sol-high reviewer returns separate passing SPEC and QUALITY verdicts."
  ],
  "test_plan": [
    "Run the complete .codex unit-test suite with Python 3.11 or newer.",
    "Run the native hook probe with v1_goal_orchestration_critical_review and the exact package.",
    "Run validate_agent_architecture.py, prompt_input_audit.py, Codex Doctor, and git diff --check.",
    "Verify recovery fingerprints and protected hashes before and after integration.",
    "Record installed automation and first durable-goal task evidence before final review."
  ],
  "review": {
    "required": true,
    "assignment_id": "v1_goal_orchestration_critical_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "db77593e3d3a278c0d1fdd7504b25b8080543f23",
    "package": ".agent/review-package.json",
    "review_paths": [],
    "exclude_paths": [],
    "output": ".agent/runs/v1-goal-orchestration/critical-review/verdict.md",
    "verdicts": ["SPEC", "QUALITY"],
    "max_rechecks": 1
  }
}
---

# V1 goal-orchestration review capsule

This capsule is the explicit authority route for the installation review. It does not replace the active Phase 3 correction capsule in `CURRENT.md`; the guard selects it only for the unique `v1_goal_orchestration_critical_review` assignment.
