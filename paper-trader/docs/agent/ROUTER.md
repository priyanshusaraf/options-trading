# Strategy OS task router

`CURRENT.md` and one tracked task capsule are the resume interface. No init command is required.

This installed Codex build does not discover project hook files from linked Git worktrees. The current machine therefore has a user-level compatibility dispatcher in `~/.codex/hooks.json` that matches only the canonical Strategy OS checkout and its worktrees, then executes the tracked `.codex/hooks/agent_guard.py` or `compaction_guard.py`. The repository scripts remain the policy source. Open `/hooks` after a dispatcher change and trust only those two scoped commands. This is a one-time security review, not initialization. Never bypass hook trust for routine Desktop work; the bypass flag is reserved for the affected non-interactive `codex exec` verification path.

## Route

1. Open `CURRENT.md` and read its JSON frontmatter.
2. Open only `active_capsule`.
3. Audit the dirty tree before changing it.
4. Read the exact files and sections under `required_docs`.
5. Load one repo skill only when its description matches the work.
6. Follow the capsule's model route, assignment dependencies, owner gates, stop conditions, and test plan.

## Model policy

| Work | Route |
|---|---|
| Phase architecture | Fresh Sol medium task, only when a capsule requests it |
| Slice owner or code judgment | Terra medium |
| Mechanical declared assignment | `luna-worker` role on Terra medium until local diagnostics expose Luna |
| Critical integrated review | One Sol high read-only reviewer |

Every child uses `fork_turns: none`. Assignment IDs use lowercase letters, numbers, and underscores so they are valid `spawn_agent` task names. Multi-agent V2 is exposed on the direct, hook-visible path while ordinary code-mode tools stay enabled. The hook supplies the declared custom route when the model-visible tool omits optional model or effort fields. Use no child when the owner can finish cheaply; use parallel children only for declared independent ownership. Never run a live reviewer or a future-phase worker.

## Evidence interface

Full logs belong under ignored `.agent/runs/<task>/<assignment>/`. The owner receives compact results and integrates once. At a critical gate, generate `.agent/review-package.json`; the reviewer reads the package, named evidence, relevant checklist, and diff. If the same reviewer rejects a second time, stop and replan.

When one automatic compaction occurs, finish the current safe boundary and start a new task from the capsule. The second automatic compaction is blocked.
