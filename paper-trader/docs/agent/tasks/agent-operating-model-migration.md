---
{
  "id": "agent-operating-model-migration",
  "phase": "agent-architecture-migration",
  "status": "implemented-pending-integration",
  "goal": "Replace the tracked Claude harness with a native, bounded, repository-scoped Codex operating model while preserving the dirty Phase 3 work exactly.",
  "risk_tags": [
    "critical",
    "agent-routing",
    "context-budget",
    "dirty-tree-integration"
  ],
  "required_docs": [
    {
      "path": "AGENTS.md",
      "sections": [
        "Start every task",
        "Routing and session limits",
        "Invariants and gates"
      ]
    },
    {
      "path": "paper-trader/docs/agent/CLAUDE_MIGRATION_AUDIT.md",
      "sections": [
        "Claude harness migration audit",
        "Explicit policy changes"
      ]
    },
    {
      "path": "paper-trader/docs/agent/ROUTER.md",
      "sections": [
        "Route",
        "Model policy",
        "Evidence interface"
      ]
    }
  ],
  "allowed_paths": [
    ".agents",
    ".codex",
    ".gitignore",
    "AGENTS.md",
    "paper-trader/AGENTS.md",
    "paper-trader/backend/AGENTS.md",
    "paper-trader/frontend/AGENTS.md",
    "paper-trader/docs/agent",
    "paper-trader/CLAUDE.md",
    ".claude/README.md",
    ".claude/agents",
    ".claude/rules",
    ".claude/skills",
    ".claude/evals",
    ".claude/workflows"
  ],
  "nonclaims": [
    "This migration does not complete Phase 3 Task 12 or alter its application code.",
    "Prompt-size reduction is measured on the installed local Codex build and is not a universal billing guarantee.",
    "The three-slice usage target remains a rollout gate; one installation session cannot establish it.",
    "The installed Codex build exposes only Sol and Terra to spawned agents, so the narrow luna-worker role temporarily uses Terra medium; Luna is not claimed available.",
    "The installed build skips project hook discovery in linked worktrees, so a user-level dispatcher scoped only to Strategy OS is a temporary compatibility layer; tracked repository scripts remain authoritative."
  ],
  "owner_gates": [
    "Do not modify global model, reasoning, tool, plugin, or memory defaults for another project. User-level changes are limited to the explicit GitHub credential remediation, Strategy OS trust records, and the Strategy OS-only worktree hook dispatcher.",
    "The exposed GitHub token must be revoked by the owner before the GitHub MCP server is re-enabled.",
    "Do not deploy, access the live VPS, or touch live-money configuration."
  ],
  "stop_conditions": [
    "An architecture path overlaps the preserved Phase 3 dirty paths.",
    "The active Phase 3 diff, untracked manifest, or four protected hashes change during integration.",
    "The rendered startup prompt exceeds 22000 bytes or includes retired Claude/plugin metadata.",
    "Codex Doctor reports a project configuration, role, hook, plugin, or MCP warning.",
    "A critical reviewer returns FAIL or UNVERIFIABLE."
  ],
  "model_route": {
    "owner": "gpt-5.6-terra",
    "owner_reasoning_effort": "medium",
    "reviewer": "gpt-5.6-sol",
    "reviewer_reasoning_effort": "high"
  },
  "parallel_budget": 1,
  "assignments": [],
  "acceptance": [
    "Before review, the dirty worktree has a private recovery snapshot and its tracked diff, untracked manifest, and four protected hashes match that snapshot; the owner repeats the same check after cherry-pick before declaring integration complete.",
    "Project defaults route Terra medium, declare up to five clean children, use a Terra-medium safe fallback until Luna becomes locally available, disable broad surfaces, and cap stored tool output and instruction bytes.",
    "Native AGENTS chains, four progressive-disclosure skills, twelve behavioral evals, three custom roles, task capsules, hooks, audit tools, and compact state documents validate.",
    "A prompt-free native probe proves the worktree dispatcher sees collaborationspawn_agent, enforces fork_turns none, supplies the declared Terra-medium route, and starts the declared custom role.",
    "The eight Claude evals and every durable Claude rule have an explicit migration disposition before the tracked Claude harness is retired.",
    "Hook tests cover five workers, a sixth rejection, duplicate and overlapping ownership, dirty forks, forbidden effort, premature review, stale fingerprints, review rechecks, and compaction boundaries.",
    "The deepest AGENTS chain is at most 12288 bytes and the model-visible startup prompt is at most 22000 serialized bytes in every required directory.",
    "Strict Codex Doctor and all repository architecture tests pass, with no static credentials or retired harness metadata.",
    "One Sol-high read-only reviewer returns separate passing SPEC and QUALITY verdicts before commit and integration."
  ],
  "test_plan": [
    "Run the complete .codex unittest suite with the backend virtual environment.",
    "Run quick_validate.py for each repository skill and parse all eval JSON files.",
    "Run the twelve read-only Codex behavioral evals at Terra medium.",
    "Run validate_agent_architecture.py and strict Codex Doctor.",
    "Run one prompt-free native hook/role contract probe through the worktree compatibility dispatcher.",
    "Run codex debug prompt-input from repository root, paper-trader, backend, IR, and engine and inspect instruction/plugin metadata.",
    "Run git diff --check, secret scan, architecture-path overlap check, dirty fingerprint comparison, and protected hash comparison before and after cherry-pick."
  ],
  "review": {
    "required": true,
    "assignment_id": "agent_operating_model_critical_review",
    "agent": "critical-reviewer",
    "model": "gpt-5.6-sol",
    "reasoning_effort": "high",
    "base_sha": "932691549672f34575e7ce737df90a2295880e5f",
    "package": ".agent/review-package.json",
    "review_paths": [
      ".agents",
      ".codex",
      ".gitignore",
      "AGENTS.md",
      "paper-trader/AGENTS.md",
      "paper-trader/backend/AGENTS.md",
      "paper-trader/frontend/AGENTS.md",
      "paper-trader/docs/agent",
      "paper-trader/CLAUDE.md",
      ".claude/README.md",
      ".claude/agents",
      ".claude/rules",
      ".claude/skills",
      ".claude/evals",
      ".claude/workflows"
    ],
    "exclude_paths": [],
    "output": ".agent/runs/agent-operating-model-migration/critical-review/verdict.md",
    "verdicts": [
      "SPEC",
      "QUALITY"
    ],
    "max_rechecks": 1
  }
}
---

# Agent operating-model migration capsule

The implementation lives on `codex/agent-operating-model` from `9326915`. It may be integrated into `codex/execution-foundation` only after all checks and the independent review pass, and only when architecture paths remain disjoint from Task 12's dirty paths.
