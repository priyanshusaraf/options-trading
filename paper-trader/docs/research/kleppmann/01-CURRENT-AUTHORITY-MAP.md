# Current authority map

Snapshot: 28 August 2026, branch `codex/execution-foundation`, starting HEAD `de6faae3e97cf5537338bee2143350e53f70da1c`. Worktree: `/Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation`. The initial dirty snapshot contained 633 status entries and 1,853 file hashes. These are inherited work, not this review's changes.

All nine original documents were read in full; hashes and exact successor sections are in [the reading record](authority-reading-record.json). The memo's `(1).md` name maps to the accepted repository copy without that suffix, as recorded by the canonical reconciliation. No duplicate source was invented.

## Controlling decisions

| Question | Current source and section | Result for this review |
| --- | --- | --- |
| V0 scope | `docs/strategy-os-v0-release-audit-2026-08-27/03-V0-SCOPE-AND-GOLDEN-PATH.md`, Public V0 scope; accepted `PROGRAMME.json` v0_replan | Research, bounded annotations/replay, static scopes, robustness, monitoring and signal review remain required. Public execution is denied. These are requirements, not current capability claims. |
| Current implementation | `docs/agent/CURRENT.md` and matching `PROGRAMME.json` stage | Product owner retains `post-phase5-indicator-accuracy-core-return-stability-correction` (F02). This side review does not advance the programme. |
| V1 execution | Accepted V0 scope, Internal/deferred sections; hybrid addendum §15 | Preserve existing capital, attribution and execution foundations for controlled later execution. No live authority follows from this task. |
| Dynamic Watchlists | Canonical reconciliation, Contradictions; hybrid addendum §§5/15; V0 scope, Deferred | Bounded Watchlists are outside V0, assigned V0.1/V1. The supplied reference programme's V1.1 label is a topic label, not an instruction to undo that rebase. |
| V1.5 | August 24 memo §§4.3/9; hybrid §15; V0 deferred scope | Certified index-options execution remains a later gate. Preserve exact held-contract truth; no live options audit or activation here. |
| Data truth | Technical steer 02 §§1–14 | Point-in-time rules, canonical instruments, explicit missing/freshness/alignment policy and dataset lineage remain invariants. |
| Capital | Technical steer 03 §§3–5; memo §§5.1/10.1/24B | Concurrent capital cannot be reserved twice; durable attribution and creating-version ownership remain mandatory. This slice does not alter money paths. |
| Runtime/cache | Technical steer 04 §§1–13; memo §7 | Durable storage owns authoritative state; cache loss cannot erase evidence or financial facts. Redis adoption requires measured need and separate gates. |
| Providers | Technical steers 02 §14 and 04 §§11–12; V0 public scope | Separate data provider from execution broker; initial V0 Zerodha data path; no silent provider substitution. |
| Verification | Technical steer 05 §§1–3; current root contract | Risk-weighted, direct tests; full critical acceptance needs independent review. Passing a small SQLite probe is not a release or PostgreSQL guarantee. |
| Confidentiality | Technical steers 00 §8 and 03 §10 | Owner-scoped data; support receipts must not casually expose strategy content or credentials. No production inspection in this review. |
| References | Owner's present request; preserved professional programme; V2 mandate §§19–21 | Install durable instructions and evidence registries. External sources inform reasoning, not scope or execution authority. |

Paths beginning `docs/` above are relative to `paper-trader/`; the reading record provides full repository paths and hashes.

## Conflicts retained explicitly

| Competing claims | Controlling decision | Retained invariant / unresolved question |
| --- | --- | --- |
| Older V1.1 Watchlists vs hybrid/V0 successor timing | Accepted reconciliation and V0 scope | Keep reference reading topics; no release rescheduling without an explicit scope decision. |
| Older ten-phase plans vs rebased programme | Current programme and hybrid §16 | Dependency order and evidence gates survive; no hardcoded ten-phase route. |
| Hybrid defers general annotation backtesting vs V0 requires bounded causal replay | Later accepted V0 scope | Bounded replay must be temporally honest; general hindsight annotation claims remain excluded. |
| New mandate's broad audit/fixes vs active F02 allowed paths | Owner permits this separate review; product capsule remains protected | Record findings and bounded next work. This task does not silently take ownership of product correction. |
| Old test totals/readiness prose vs current bytes | Direct new evidence only | No release-readiness conclusion from historical counts. |

No canonical source, product capsule or programme gate was rewritten. No complete current-code capability audit is claimed by this authority map.
