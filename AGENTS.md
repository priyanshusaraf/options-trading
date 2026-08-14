# Strategy OS agent contract

This repository is Strategy OS: a visual platform for composing, researching, admitting, deploying, and operating trading strategies. It is not the older autonomous options bot. One path trades real money, so reject safety and completion claims until the named evidence exists.

## Start every task

1. Work only in the `dev/options-trading` checkout. The active Phase 3 worktree is `/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation`; the Desktop clone is frozen.
2. Read `paper-trader/docs/agent/CURRENT.md`, confirm its stage in `paper-trader/docs/agent/programme/PROGRAMME.json`, then read the active capsule.
3. Read only the capsule's exact `required_docs` sections and the applicable local `AGENTS.md` files. Do not load `docs/CONTINUE.md`, large handoff documents, whole phase plans, or future-phase findings by default.
4. Audit `git status`, the relevant diff, and protected-file hashes before editing a dirty tree. Never stash, reset, clean, or overwrite inherited work.
5. Treat the repository, capsule, evidence logs, and commit history as the handoff. Do not request an old task transcript or paste one into a new task.

## Routing and session limits

- A phase architecture capsule may route one fresh Sol-medium task. Implementation slice owners use Terra medium. Mechanical children use Luna medium through the narrow `luna-worker` role; judgment-heavy children use `terra-worker`.
- Children require `fork_turns: none` and an exact assignment declared in the active capsule. Run zero to five only when their dependencies and write ownership are disjoint. Do not create speculative, overlapping, or future-scope workers.
- Use one `critical-reviewer` only for a critical slice, after integration and an evidence-backed review package exist. No live reviewer, reviewer swarm, permanent Sol controller, Fast mode, xhigh, ultra, or max effort.
- Keep a task bounded to one capsule or coherent slice. A first automatic compaction is the handoff warning; start a fresh task before a second.
- Every executable capsule is one durable goal. Create that goal before product work and complete it only when the capsule stopping condition has direct evidence.
- Put full command output under ignored `.agent/runs/` with `.codex/scripts/run_logged.py`. Return compact results and evidence paths to the slice owner.

## Invariants and gates

- Keep one typed immutable IR, validator, resolver, hash, component registry, research lineage, and canonical execution binding. Presentation state never enters executable identity.
- Strategy, graph, deployment, evidence, requested assignment, resolved authority, and money records are distinct facts. Preserve exact attribution from scan through fill.
- Paper and live books remain separate and fail closed to live. ARM gates entries only; risk-reducing exits stay available. Never silently enable authoritative live IR.
- Strategy OS owns canonical instruments. Data provider and execution broker are separate roles. Preserve owner isolation, deterministic replay, causal completed-bar behavior, and net-of-charges accounting where promised.
- Stop for owner direction before live IR authority, material live sizing/routing/risk/execution changes, live VPS or credential access, destructive data/infrastructure work, licence-sensitive adoption, legal/regulatory/commercial decisions, or frontend implementation.
- Deploy only through `paper-trader/scripts/deploy.sh`, after its owner gate and exact-head evidence. Local development and safe tests do not authorize deployment.

Use the four repo skills under `.agents/skills/` only when their descriptions match. Record a discovered later-phase issue as a finding; do not implement it in the current capsule.
