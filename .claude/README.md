# Claude Code harness for Strategy OS

Configured 2026-08-08. This directory is the engineering harness: what loads always, what loads
by path, what loads on request, and what reviews the result.

## The four layers, and why the split matters

| Layer | Where | Loads | Purpose |
|---|---|---|---|
| **Permanent guidance** | `paper-trader/CLAUDE.md` | every session | Product identity, core invariants, owner gates, how-to-work rules, doc map |
| **Contextual constraints** | `.claude/rules/*.md` | when a matching path is touched | Deep domain rules — execution, research, tenancy, providers, migrations, frontend, performance, IR |
| **Task procedures** | `.claude/skills/*/SKILL.md` | on invocation | Workflows: architecture review, implementation slice, ship gate, provider adapter, benchmarking, UI acceptance, running the app |
| **Specialist reasoning** | `.claude/agents/*.md` | on dispatch | Independent reviewers, mostly read-only |
| **Enforcement** | `.claude/settings.local.json` | always | Permission `ask`/`deny` for actions that must not happen casually |

**Only the first layer costs context every session.** `CLAUDE.md` went from 24,318 to ~7,700
characters by moving detail into layers 2–4; measured always-resident context dropped from
~15,400 to ~7,300 est. tokens (−53%) while *adding* nine skills and six agents.

## Rules — path-scoped, so they cost nothing until relevant

| Rule | Loads when you touch |
|---|---|
| `execution-safety.md` | `app/engine/**`, `execution_*`, `paper_authority`, `shadow_deployments`, `app/strategy/**`, `deploy.sh` |
| `research-integrity.md` | `research/**`, `app/backtest/**`, `app/market_data/**`, IR kernels/runtime |
| `tenancy-security.md` | `app/api/**`, config, `app/ws/**` |
| `providers-brokers.md` | `app/providers/**`, `broker*`, `kite_venue`, `app/options/**`, instruments |
| `migrations-database.md` | `migrations/**`, `app/db/**`, `app/ledger/**` |
| `frontend-ui.md` | `frontend/**` |
| `performance.md` | `analytics.py`, `app/backtest/**`, IR runtime/resolve |
| `ir-language.md` | `app/ir/**`, `app/editor/**`, `app/api/ir_*` |

## Skills

`strategy-os-architecture-review` · `implementation-slice` · `execution-safety-review` ·
`research-integrity` · `provider-adapter` · `performance-benchmark` · `ui-acceptance` ·
`ship-gate` · `run-strategy-os`

`implementation-slice` is the default for substantial work; `ship-gate` closes it. Neither is for
trivial edits — running the whole repo for a typo is waste, not rigour.

## Agents — reviewers are independent by construction

`architecture-critic` · `security-tenancy-reviewer` · `execution-safety-reviewer` ·
`research-leakage-reviewer` · `performance-profiler` · `ui-verifier`

All read-only except `performance-profiler` (scratchpad benchmark scripts only) and `ui-verifier`
(browser tools). **The agent that wrote the code is not the agent that approves it.**

## Guardrails

`ask` on: `ssh`, `scp`, `rsync`, `deploy.sh`, `git push`, `git reset`, `git stash`,
`git checkout --`, `git clean`, `alembic downgrade`, `npm publish`.
`deny` on: reading `~/.ssh/**`, `git push --force`.

Deliberately **no new hooks**. The existing ones are fast (PostToolUse:Edit 88 ms median) and
§12's rule holds: hooks are for hard guarantees, not review loops. The `security-guidance` plugin
was rejected for spawning a Python interpreter on every `PostToolUse`.

## Running the app

`.claude/skills/run-strategy-os` starts a **mock-provider, paper-mode, temp-database** instance.
Never the live ledger, never a real broker session, never ARMed. The production bot runs 24/7 on
the VPS and holds real positions — one live engine only.

## Harness evals

`.claude/evals/` holds eight realistic Strategy OS prompts and `run-evals.sh`. They test the
*configuration*, not the codebase: does the guidance actually reach the model and change what it
does? Run with `bash .claude/evals/run-evals.sh [case-prefix …]`; transcripts land in
`results/`.

They are behavioural smoke tests, not proofs. A pass means the guidance routed correctly, not
that execution would be flawless.

### State as of 2026-08-08 — read the transcripts, not the score

Automated marker scoring is a **weak instrument** and its numbers understate the harness. Judged
by reading `results/`, the guidance demonstrably loaded in every case that ran:

| Case | Scored | What the transcript actually showed |
|---|---|---|
| 01 trivial typo | FAIL | Correct. "one edit, one line", explicitly refused the full suite as disproportionate, flagged that sibling headers are sentence-case |
| 02 execution binding | FAIL | Correct. Cited **ADR 0012 §2.0 by file:line** and applied the "settled in an ADR isn't re-litigated" rule from CLAUDE.md |
| 03 cross-instrument | **PASS** | Correct. Quoted the rules file — "cross-instrument alignment is look-ahead wearing a join" — and stated the bar-close invariant |
| 04 cockpit UI | FAIL | Correct. Read three surfaces, corrected the premise, quoted `frontend-ui.md`'s 390px one-handed case |
| 05–08 | not run | **Session limit**, not a harness failure. Re-run after reset |

Why the false failures: markers are prose substrings. Case 01 was first scored FAIL for "leaked:
full suite" when the sentence was *"doesn't warrant the full suite"* — a negation. Markers are now
`|`-alternations, which helps but does not fix the underlying weakness: a single `-p` answer may
simply not reach the section a marker looks for.

**Treat a FAIL as "go read the transcript", never as a verdict.** The suite catches routing
failures — guidance that never loaded at all — and nothing subtler.

**`env -u ANTHROPIC_API_KEY` is required in the runner.** An `ANTHROPIC_API_KEY` in the
environment takes precedence over the claude.ai login, and a stale one makes every headless run
fail `401 API key is invalid` while interactive sessions keep working — the exact failure hit on
2026-08-08.

## Known gaps

- Ownership/tenancy does not exist in the product yet, so `security-tenancy-reviewer` reports
  "becomes exploitable when ownership lands" more often than "exploitable today". That
  distinction is deliberate — see `.claude/rules/tenancy-security.md`.
- `pyright` runs clean on spot checks but has not been run repo-wide; expect findings when it is.
- The eval suite asserts on markers in prose. It catches routing failures, not subtle bad
  judgement.
