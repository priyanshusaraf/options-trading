# Find the guidance for the task

Start with the latest user direction and applicable local `AGENTS.md`. Consult [WORKING-PLAN.md](WORKING-PLAN.md) for product scope and priorities. A direct bounded assignment or an explicitly resumed capsule defines the work. Do not load every historical plan.

## Instruction and evidence map

| Source | Use it for |
| --- | --- |
| Root and local `AGENTS.md` | Shared rules and subsystem-specific hazards. |
| `WORKING-PLAN.md` | Current user journey, priorities, ownership and completion criteria. |
| `STATUS.md` | Recorded integration evidence, open defects and the current handoff. |
| `docs/README.md` | Short roadmap and architecture entry points. |
| `.agents/skills/*/references/` | Historical domain references; these directories are not installed skills without a `SKILL.md` entry point. |
| Installed personal/plugin skills | Specialist capabilities. Preserve them; do not run every tool automatically. |
| `CURRENT.md`, `programme/PROGRAMME.json`, `tasks/` | Recorded phase/capsule history and evidence links. Acceptance labels need current verification. |
| `docs/program/owner-steers/` and accepted reconciliations | Product meaning and invariants where the latest user direction is silent. |
| `docs/engineering-references/` | Source-backed failure hypotheses and checked guidance. No automatic technology adoption. |
| `.agent/runs/` | Full commands and reproductions. Keep the findings themselves in the integrated audit. |

## Choose available skills by the affected work

Use installed skills listed in the current session when their instructions apply.
For UI work, use the available `frontend-design` and `ui-ux-pro-max` skills.
For changes to skills themselves, use the available `skill-creator` guidance.
Preserve the user's model and reasoning choices.

The old names under `.agents/skills` identify retained reference material, not
callable skills: their entry points have been retired. Consult a specific
reference when relevant; do not reconstruct an automatic startup procedure.

## Bounded reading

Read the affected section, not every linked file. Large maintained references now
have section indexes. Historical plans, task capsules and programme records are
excluded from ordinary `rg` searches by root `.ignore`; inspect an explicit past
decision with `rg --no-ignore <pattern> <history-path>`. Original owner documents
remain intact; retrieve only the relevant heading or field. Do not reconstruct a
startup chain through archive indexes.

## Parallel work

Follow root `AGENTS.md` for delegation and model selection. Custom role files override spawn model/effort, so use the default agent with explicit settings when a fixed role conflicts with the user's choice. The root owns integration and heavy checks. Direct assignments are sufficient; explicitly resumed capsules retain their declared contract. Use distinct task names for new assignments rather than reusing historical capsule assignment IDs.
