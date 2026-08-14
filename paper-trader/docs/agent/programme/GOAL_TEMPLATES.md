# Strategy OS goal templates

The dispatcher substitutes bracketed fields from `PROGRAMME.json` and the active capsule. Every executable task calls `create_goal` before product work. A task may finish a safe boundary without completing its goal; it marks the goal complete only when the capsule's stopping condition is proven.

## Dispatcher task

Run `.codex/scripts/programme_dispatcher.py --claim --json` once from the repository root. The atomic ignored lease prevents a second scheduled run from dispatching the same stage. If the action is `monitor`, `pause`, or `complete`, report it and stop. If the action is `dispatch`, create one new local task in the saved backend project with the returned model, reasoning effort, title, capsule, and goal objective. Immediately bind it with `.codex/scripts/programme_dispatcher.py --bind-thread [CLAIM_ID] [THREAD_ID] --json`. On a later run, inspect only the bound task and record `running`, `needs_input`, `completed`, or `failed` with `.codex/scripts/programme_dispatcher.py --update-lease [CLAIM_ID] [STATUS] --json`. Never edit product or tracked programme files. Never create a second task while the controller reports an active goal.

## Phase architecture goal

First call `create_goal` with the exact objective below:

> Architect [STAGE_ID] from [CAPSULE]. The goal completes only when the phase design, implementation plan, bounded slice capsules, source-coverage matrix, phase-review capsule, and programme transition are validated and committed without implementing product code. Stop with the goal active for an owner gate or unresolved contract conflict.

Read `AGENTS.md`, `CURRENT.md`, the capsule, and only its exact required source sections. Audit the accepted dependencies and existing implementation before proposing new abstractions. Use Sol medium. Do not implement future phases.

## Implementation or correction goal

First call `create_goal` with the exact objective below:

> Execute [STAGE_ID] from [CAPSULE]. The goal completes only when every acceptance criterion has current evidence, proportional tests pass, the integrated review package is current, and the next declared gate is ready. A failed gate creates correction state and does not advance the programme. Stop with the goal active for an owner gate or an unresolved required environment.

Use Terra medium. Audit the inherited tree before editing. Use zero to five clean-fork children only for declared disjoint assignments. Keep full output under `.agent/runs/`; return compact evidence paths. Do not run the broad suite more than the capsule permits.

## Critical phase-review goal

First call `create_goal` with the exact objective below:

> Review [STAGE_ID] from [CAPSULE]. The goal completes only when the integrated diff and named evidence receive separate final SPEC and QUALITY verdicts and the programme records either accepted next-stage readiness or a bounded correction state. Do not implement product code. Stop for an owner gate or unverifiable evidence.

Use Sol high. Read only the capsule, source-coverage matrix, review package, integrated diff, relevant checklist, and named evidence. Product paths are read-only. Write only the verdict and programme transition. One recheck is allowed; a second rejection requires replanning.

## Gate recording rules

- `SPEC=PASS` and `QUALITY=PASS` are both required for acceptance.
- A missing, stale, partial, timed-out, skipped, or failed required command is rejection evidence.
- A rejected phase activates a Terra-medium correction stage before the same Sol reviewer may recheck it.
- Component IR v2 must pass after Phase 3 and before Phase 4.
- Every Phase 4–10 architecture goal expands its implementation placeholder into fresh bounded slice goals and creates the exact phase-review capsule.
- V1 completion requires all three canonical scenarios, every phase report, broad release verification, and truthful nonclaim resolution.
