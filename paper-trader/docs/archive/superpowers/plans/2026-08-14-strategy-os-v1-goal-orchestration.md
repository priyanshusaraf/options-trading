# Strategy OS V1 Goal Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install a repository-backed, token-bounded sequence of durable Codex goals from the rejected Phase 3 Task 12 gate through Phase 10 and the V1 release gate.

**Architecture:** Preserve owner steers and programme state as tracked inputs, keep controller leases and detailed evidence ignored, and use a deterministic dispatcher to select one active capsule. A Luna-medium scheduled task dispatches; Sol-medium goals architect phases, Terra-medium goals implement or correct slices, and one Sol-high goal reviews every phase.

**Tech Stack:** JSON, Markdown, Python 3.11 standard library, Codex project configuration, Codex scheduled tasks, repository hooks, and unittest.

**Spec:** `paper-trader/docs/superpowers/specs/2026-08-14-strategy-os-v1-goal-orchestration-design.md`

## Global Constraints

- Preserve the dirty Phase 3 worktree and the four protected inherited-file hashes exactly during this migration.
- Do not load or adopt Component IR v2 during Phase 3 correction; enforce it only after Phase 3 acceptance.
- Use repository state instead of conversation history; every executable capsule becomes one durable goal.
- Use Luna medium for the scheduled dispatcher, Sol medium for phase architecture, Terra medium for implementation/correction, and one Sol high reviewer at every phase gate.
- Allow zero to five clean-fork children only for declared disjoint assignments.
- Do not access live credentials, VPS, production data, deployment, live authority, or frontend scope.

---

### Task 1: Preserve the six owner steers and source map

**Files:**
- Create: `paper-trader/docs/program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md`
- Create: `paper-trader/docs/program/owner-steers/01-STRATEGY-LANGUAGE-NODE-SYSTEM.md`
- Create: `paper-trader/docs/program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md`
- Create: `paper-trader/docs/program/owner-steers/03-DEPLOYMENT-EXECUTION-TRUST.md`
- Create: `paper-trader/docs/program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md`
- Create: `paper-trader/docs/program/owner-steers/05-V1-IMPLEMENTATION-PRIORITIES-VERIFICATION.md`
- Create: `paper-trader/docs/agent/programme/SOURCE_MAP.json`
- Test: `.codex/tests/test_programme_orchestration.py`

**Interfaces:**
- Consumes: the exact six files under `/Users/priyanshusaraf/Downloads/strategy-os-steer-documents/`.
- Produces: immutable in-repository sources keyed by SHA-256 and section-to-phase routing.

- [ ] **Step 1: Write a failing source-integrity test**

Assert that all six tracked files exist, match their recorded SHA-256 hashes, and that every parsed `##`/`###` heading appears exactly once in `SOURCE_MAP.json` with at least one consumer.

- [ ] **Step 2: Run the focused test and observe missing-file failure**

Run: `python3 -m unittest .codex.tests.test_programme_orchestration.SourceMapTests -v`

- [ ] **Step 3: Add byte-for-byte copies and the complete map**

Use the phase routing approved in the design. Store exact heading strings rather than informal paraphrases.

- [ ] **Step 4: Run the focused source tests**

Expected: every file, digest, heading, and consumer validates.

### Task 2: Define the tracked programme and goal templates

**Files:**
- Create: `paper-trader/docs/agent/programme/PROGRAMME.json`
- Create: `paper-trader/docs/agent/programme/GOAL_TEMPLATES.md`
- Create: `paper-trader/docs/agent/tasks/phase3-task12-correction-1.md`
- Create: `paper-trader/docs/agent/tasks/phase3-task12-review-2.md`
- Create: `paper-trader/docs/agent/tasks/phase3-4-ir-v2-acceptance.md`
- Create: `paper-trader/docs/agent/tasks/phase3-4-ir-v2-review.md`
- Create: `paper-trader/docs/agent/tasks/phase4-architecture.md` through `phase10-architecture.md`
- Modify: `paper-trader/docs/agent/CURRENT.md`
- Modify: `paper-trader/docs/agent/ROUTER.md`
- Test: `.codex/tests/test_programme_orchestration.py`

**Interfaces:**
- Consumes: `SOURCE_MAP.json`, the master sequence, the rejected Phase 3 verdict, and existing capsule schema.
- Produces: `PROGRAMME.json` schema version 1 and prompts for architecture, implementation, correction, and review goals.

- [ ] **Step 1: Write failing state-machine contract tests**

Cover exact stage order, a ready Phase 3 correction, blocked Component IR v2 and later phases, mandatory Sol review per phase, model/effort routes, owner gates, and absence of placeholders.

- [ ] **Step 2: Run the tests and observe missing-programme failure**

Run: `python3 -m unittest .codex.tests.test_programme_orchestration.ProgrammeContractTests -v`

- [ ] **Step 3: Add programme state and goal templates**

Every template instructs the task to call `create_goal` first. The objective names the capsule and states when to complete, when to leave active, and when to stop for an owner gate.

- [ ] **Step 4: Add the Phase 3 corrective capsule**

Name all current reviewer findings, current dirty-state fingerprint checks, proportional tests, one broad phase gate, evidence regeneration, and the Sol-high recheck.

- [ ] **Step 5: Add the interphase IR v2 acceptance capsule**

Keep it blocked until Phase 3 passes. Its scope is to reconcile, validate, and accept or reject the two preserved documents before Phase 4.

- [ ] **Step 6: Update the compact resume interface**

Point `CURRENT.md` at the corrective capsule and programme file. Keep `CURRENT.md` and `ROUTER.md` below 4 KiB each.

- [ ] **Step 7: Rerun state-machine contract tests**

Expected: exact ordering, routing, gates, and compact resume state pass.

### Task 3: Implement the deterministic dispatcher

**Files:**
- Create: `.codex/scripts/programme_dispatcher.py`
- Test: `.codex/tests/test_programme_dispatcher.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: repository root, `PROGRAMME.json`, `SOURCE_MAP.json`, current capsule, and optional ignored controller state.
- Produces: one JSON action with `action`, `stage_id`, `capsule`, `model`, `reasoning_effort`, `goal_objective`, and `reason`.

- [ ] **Step 1: Write failing dispatcher tests**

Tests must cover ready dispatch, one-active-goal monitor, rejected-stage correction, rejected phase refusing advancement, blocked IR v2 ordering, mandatory Sol review, paused owner gate, missing capsule, stale controller lease, and completed V1.

- [ ] **Step 2: Run tests and observe missing-script failure**

Run: `python3 -m unittest .codex.tests.test_programme_dispatcher -v`

- [ ] **Step 3: Implement validation and pure action selection**

Use only Python 3.11 standard library. Never mutate tracked files. Exit nonzero with a compact JSON `pause` action for invalid state.

- [ ] **Step 4: Add ignored controller state**

Ignore `.agent/programme/` explicitly and accept a controller-state path only inside that directory.

- [ ] **Step 5: Run dispatcher tests**

Expected: all state transitions and failure cases pass.

### Task 4: Extend repository validation and hook policy

**Files:**
- Modify: `.codex/scripts/validate_agent_architecture.py`
- Modify: `.codex/tests/test_repository_contract.py`
- Modify: `.codex/tests/test_tools.py`
- Modify: `.codex/config.toml`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: source map, programme, capsules, dispatcher, existing agent guard, and compact instruction chain.
- Produces: fail-closed validation of all orchestration artifacts and an explicit project-scoped goals feature.

- [ ] **Step 1: Write failing validator and configuration tests**

Require all orchestration artifacts, source hashes, referenced capsules, phase review routes, and `features.goals = true`.

- [ ] **Step 2: Run focused tests and observe failures**

Run: `python3 -m unittest .codex.tests.test_repository_contract .codex.tests.test_tools -v`

- [ ] **Step 3: Extend the validator and compact root instructions**

Add validation without loading full owner steers into startup context. Root instructions name only the programme entrypoint and routing rule.

- [ ] **Step 4: Run focused and complete architecture suites**

Run: `python3 -m unittest discover -s .codex/tests -v`

### Task 5: Validate and integrate the isolated migration

**Files:**
- Evidence: ignored `.agent/runs/v1-goal-orchestration/`
- Commit: all tracked orchestration paths only

**Interfaces:**
- Consumes: complete isolated diff and preserved dirty-worktree snapshot.
- Produces: one validated orchestration commit cherry-picked onto `codex/execution-foundation` without overlapping Phase 3 paths.

- [ ] **Step 1: Run all structured-file, reference, hash, secret, and architecture tests**

Run the complete `.codex` unittest suite, architecture validator, `git diff --check`, and secret scan.

- [ ] **Step 2: Run prompt and Codex diagnostics**

Audit repository root, `paper-trader`, backend, IR, and engine startup inputs; keep the deepest AGENTS chain at most 12,288 bytes and rendered startup input at most 22,000 bytes.

- [ ] **Step 3: Commit the isolated architecture**

Commit only after fresh verification.

- [ ] **Step 4: Compare active dirty state to the recovery snapshot**

Require identical pre-integration tracked patch, untracked manifest/archive, and protected hashes. Reject any architecture-path overlap.

- [ ] **Step 5: Cherry-pick and repeat the integrity checks**

Do not stash, reset, clean, or commit the inherited Phase 3 work.

### Task 6: Install automation and launch the first goal

**Files:**
- External: Codex scheduled task for the saved backend project
- External: new backend task `Phase 3 Task 12 Corrective Goal 1`

**Interfaces:**
- Consumes: integrated dispatcher and backend project ID.
- Produces: one Luna-medium two-hour dispatcher and one Terra-medium local task that creates a durable corrective goal.

- [ ] **Step 1: Create the scheduled dispatcher**

Configure a standalone local task every two hours. Its prompt runs the dispatcher once, dispatches or monitors at most one goal, never edits product code, and pauses on invalid state or owner gates.

- [ ] **Step 2: Create the first corrective task in the backend project**

Use Terra medium in the saved local project so it sees the inherited dirty Phase 3 work. Its first required action is `create_goal` using the capsule objective.

- [ ] **Step 3: Wait for startup evidence**

Verify the task read `CURRENT.md`, created its durable goal, audited the dirty tree before editing, and preserved the protected hashes.

- [ ] **Step 4: Record rollout boundaries**

Keep the orchestration goal active until both automation and first-goal evidence exist. Phase 3 product completion remains the corrective task's responsibility, not this migration's completion claim.
