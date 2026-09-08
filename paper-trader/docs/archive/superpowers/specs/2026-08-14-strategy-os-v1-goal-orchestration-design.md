# Strategy OS V1 Goal Orchestration Design

**Status:** approved on 2026-08-14

## 1. Outcome

Strategy OS work from the rejected Phase 3 Task 12 gate through Phase 10 runs as a bounded sequence of durable Codex goals. The repository, not a permanent controller conversation, owns programme memory. A scheduled Luna-medium dispatcher may start or monitor one goal at a time, but it never implements product code.

The programme does not advance because an agent says it is finished. It advances only after the required evidence exists and a Sol-high phase gate returns separate passing `SPEC` and `QUALITY` verdicts.

## 2. Current boundary

The canonical active worktree is `/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation` on `codex/execution-foundation`.

Phase 3 is `REJECTED / OPEN`. The first programme goal is a Terra-medium corrective slice for the findings already recorded in `.agent/runs/phase3-task12/critical_review/verdict.json`:

- broad backend and research evidence failed and did not complete;
- evidence lineage predates the packaged diff;
- schema heads were hard-coded instead of queried from their owning migration tools;
- generated descriptor construction commits a caller-owned session.

The two Component IR v2 documents remain excluded from Phase 3. After Phase 3 passes, they form a mandatory interphase acceptance gate before Phase 4.

## 3. Authoritative inputs

The six owner-authored steer documents are copied byte-for-byte into `paper-trader/docs/program/owner-steers/`. `SOURCE_MAP.json` records the expected SHA-256, every heading, and the phases that consume each section. The originals remain immutable programme inputs; summaries and phase plans may interpret them but never replace them.

The routing policy is:

| Source | Mandatory consumers |
| --- | --- |
| Product Architecture Steer | every phase architecture goal, every phase gate, V1 release gate |
| Strategy Language & Node System | Component IR v2 and Phases 5, 6, 7, 8 |
| Market Truth & Data Contracts | Phases 4, 6, 7, 9 and the release gate |
| Deployment, Execution & Trader Trust | Phase 3 correction and Phases 6 through 10 |
| Runtime Economics & Provider Capability | Phases 4, 5, 6, 7, 9, 10 |
| V1 Priorities & Verification | every task capsule, phase architecture goal, phase gate, and release gate |

Workers read only the exact sections named by the active capsule. Phase architects and phase reviewers validate that the phase's entire mapped source surface is covered.

## 4. State machine

The tracked `PROGRAMME.json` is the authoritative sequence and current pointer. It contains these ordered gates:

1. Phase 3 Task 12 correction;
2. Phase 3 Sol-high recheck;
3. Component IR v2 interphase acceptance;
4. Phase 4 architecture, implementation slices, and Sol-high phase gate;
5. Phase 5 architecture, implementation slices, and Sol-high phase gate;
6. Phase 6 architecture, implementation slices, and Sol-high phase gate;
7. Phase 7 architecture, implementation slices, and Sol-high phase gate;
8. Phase 8 architecture, implementation slices, and Sol-high phase gate;
9. Phase 9 architecture, implementation slices, and Sol-high phase gate;
10. Phase 10 architecture, implementation slices, and Sol-high phase gate;
11. V1 release verification against the three canonical scenarios and all retained nonclaims.

Each stage is in exactly one of `blocked`, `ready`, `active`, `correction`, `review`, `accepted`, or `paused_owner_gate`. Only the first unfinished dependency may become ready. A later phase cannot start early.

Architecture goals append bounded implementation-slice capsules for their phase. They may not change prior accepted phases or unlock their own phase gate. A phase gate is unlocked only after every declared slice is accepted and its integrated evidence package is current.

## 5. Goal contract

Every executable capsule is one durable goal. Its objective includes a concrete stopping condition. A task must create that goal before product work, keep it active while useful work remains, and mark it complete only after the capsule acceptance evidence is present. A rejected goal creates or activates a correction capsule; it does not advance the programme.

The standard routes are:

| Task kind | Model and effort | Authority |
| --- | --- | --- |
| Dispatcher | Luna medium | Read programme state, create or continue one task, write ignored controller state only |
| Phase architecture | Sol medium | Write phase design, plan, capsules, and source-coverage matrix only |
| Implementation slice | Terra medium | Implement one bounded capsule |
| Mechanical assignment | Luna medium through `luna-worker` | Exact declared assignment; no architecture decisions |
| Corrective slice | Terra medium | Resolve named rejected findings without widening scope |
| Phase gate | Sol high | Read-only critical review; separate `SPEC` and `QUALITY` verdicts |

Spawned children always use `fork_turns: none`, exact declared assignment IDs, and zero to five disjoint ownership partitions. One implementation writer owns each file. No xhigh, ultra, max, Fast mode, live reviewer, speculative future-phase worker, or permanent Sol controller is allowed.

## 6. Dispatcher contract

`.codex/scripts/programme_dispatcher.py` is deterministic and side-effect free with respect to tracked files. It validates the programme, source map, active capsule, phase ordering, route, and controller lease, then emits exactly one action. A dispatch first creates an atomic reserved lease. The scheduled controller must bind the created task ID to that claim and record later task-state transitions under the same lease:

- `dispatch`: start the active capsule as a new goal task;
- `monitor`: an active goal already owns the programme;
- `pause`: an owner gate, invalid state, stale lease, or missing evidence requires attention;
- `complete`: the V1 release gate is accepted.

The scheduled task runs every two hours in the saved backend project. Each run first queries authoritative Codex task state and passes the exact active-programme-goal count to the atomic claim; unavailable or ambiguous state pauses rather than assuming zero. Each run performs one state transition at most. It exits immediately when another goal is active. It never edits application code, retries a rejected phase as if it passed, or bypasses an owner gate.

Controller leases live under ignored `.agent/programme/`; detailed task and test logs remain under ignored `.agent/runs/`. The tracked programme state and capsules remain sufficient to reconstruct the work if runtime state is deleted.

## 7. Phase construction and review

For Phases 4 through 10, the phase-architecture goal must:

1. audit the accepted preceding contracts and existing implementation;
2. load the exact source-map sections assigned to that phase;
3. write a phase-specific design and implementation plan;
4. declare bounded, dependency-ordered implementation capsules with explicit allowed paths and proportional tests;
5. define integrated phase evidence and the Sol-high review package;
6. retain owner gates and nonclaims that the phase does not prove.

Focused tests run during a slice, the affected subsystem suite runs at its gate, and the broad backend plus research suite runs once at a backend phase gate. Frontend phases add typecheck/build and focused workflow evidence. Full release verification runs once after Phase 10.

Every phase ends with one Sol-high reviewer, even when Sol performed phase architecture. The reviewer is read-only and receives only the active phase capsule, source-coverage matrix, review package, integrated diff, and named evidence. One recheck is permitted. A second rejection pauses the phase for replanning.

## 8. Owner gates and safety

Automation does not broaden authority. It pauses before:

- enabling authoritative live IR;
- changing material live sizing, routing, risk, protection, or execution semantics;
- accessing live credentials, the live VPS, or production data;
- deployment, destructive data or infrastructure work;
- licence-sensitive adoption or legal, regulatory, and commercial decisions;
- frontend implementation until a phase capsule explicitly opens that path.

Risk-reducing exits remain available. Rejection is a valid state and never becomes acceptance through retries, elapsed time, or narrative confidence.

## 9. Acceptance

The orchestration migration is accepted when:

- all six sources are present with the recorded hashes and complete heading coverage;
- structured files parse and every referenced file exists;
- dispatcher tests prove ordering, single-goal ownership, rejected-phase correction, owner-gate pause, mandatory Sol review, and the Component IR v2 interphase gate;
- existing architecture tests and validators pass;
- the active dirty Phase 3 work and four protected hashes are unchanged across integration;
- a Luna-medium scheduled dispatcher is installed for the backend project;
- the first Terra-medium Phase 3 corrective task exists and has created its durable goal;
- no application, live, deployment, VPS, credential, or frontend work occurs during this migration.

The broader token-efficiency rollout remains empirical. Three comparable implementation slices must show at least 50% lower median weighted usage, no more than 10% wall-clock regression, zero xhigh/max/Fast calls, no live reviewers, clean forks, and unchanged safety/eval results.
