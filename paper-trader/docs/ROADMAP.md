# ROADMAP

**The agenda across workstreams. Detail lives in the workstream documents, not here.**

This file used to be 1,279 lines and every session parsed all of it to find one item. It is now
an index and a sequencing decision. If you are implementing, go straight to your workstream
document — see [`engineering/WORKSTREAMS.md`](engineering/WORKSTREAMS.md).

**Last verified: 2026-08-03** · branch `feat/exec-completeness` · backend suites
(`tests` + `research_tests`) **2,685 collected, PYTEST EXIT 0** · `dryrun.py 700` LEDGER OK ·
`backtest_smoke.py` SWEEP OK · `PT_RESEARCH_ENABLED=0` · VPS build **not measured** —
`curl /api/health` is the only answer.

---

## 1. Order of work

Set by the owner 2026-08-01 and still current: **research plane → UI → futures/MTF → exit
tuning**. The Strategy OS work (WS-01) sits ahead of all of it as the foundation the research
plane now builds on, and is complete as a language.

| Priority | Workstream | Next item | Blocked? |
|---|---|---|---|
| 1 | [WS-04 Editor](engineering/workstreams/WS-04-editor.md) | read-only graph rendering in the app | no |
| 2 | [WS-08 Cockpit UI](engineering/workstreams/WS-08-cockpit-ui.md) | typography and palette pass | **needs the owner's reference site** |
| 3 | [WS-02 Execution](engineering/workstreams/WS-02-execution.md) | index-futures segment (E2) | **deploy blocked on owner** |
| 4 | [WS-03 Research Plane](engineering/workstreams/WS-03-research-plane.md) | a week of unattended nightly runs on real candles | no |
| — | [WS-01 Component IR](engineering/workstreams/WS-01-component-ir.md) | complete as a language; adoption is owner-gated | — |
| — | [WS-07 Infrastructure](engineering/workstreams/WS-07-infrastructure.md) | reactive to the others | no |
| — | [WS-06 Deployment](engineering/workstreams/WS-06-deployment.md) | owner actions only | **owner** |
| — | [WS-05 Marketplace](engineering/workstreams/WS-05-marketplace.md) | not started, by design | trigger |

The earlier order (B → E → C → D → A, from the owner's 2026-07-24 directive) is superseded.
Workstream B (safety backlog) is closed apart from the VPS OS reboot.

## 2. Waiting on the owner

Nothing below can be resolved by implementation. Everything else can proceed today.

1. **Deploy the eight-phase architecture migration.** Committed, verified, not on the box, for
   several sessions. Touches sizing, exits and order routing — the live-money rule stops it
   regardless of green tests. → WS-02, WS-06
2. **Adopt the IR runtime in a live path.** RFC 0001 Appendix C(d). The parity evidence now
   exists: `expanding_z_v4` expressed in the IR produces identical signals bar for bar. → WS-01,
   WS-02
3. **VPS OS reboot** (5 ESM security updates) and **droplet resize 1 GB → 2 GB**. → WS-06

## 3. Parked deliberately

Do not spend sessions here.

- UI→deployed-Python codegen bridge — owner 2026-07-20: hand-coding approved strategies is
  fine, and the approve→deploy bridge that exists is enough.
- Stock-specific options work — equity/index first; options are index-only and later.
- Product avenues from the 2026-07-18 review — revisit after the research plane ships.

## 4. Session protocol

1. Read [`PROGRESS.md`](PROGRESS.md) for state, then your workstream document. You should not
   need to read this file to implement anything.
2. TDD. Both backend suites plus `dryrun.py 700` green before any "done" claim, and the
   workstream's own §6 acceptance criteria on top.
3. A checked box means verified evidence, ticked in the same commit as the work.
4. Prove new guards can go red. A green test can be vacuous — five shapes have been caught here
   by suppressing the implementation and checking the guard's own test fails.
5. Deploys go through `scripts/deploy.sh` and nothing else. It refuses during market hours and
   on a dirty tree, and builds the SPA locally. Never bare-rsync — that has taken the VPS down
   twice. Full mechanics in [`operations.md`](operations.md).
6. Model split (owner): Fable advises and reviews, Sonnet builds, Opus judges optimisation.

## 5. Where the implementation history went

Nothing was deleted. Every completed item, with its date, commit and acceptance evidence, moved
into the §4 Completed section of the workstream that owns it:

| Was | Now |
|---|---|
| Strategy OS — Component IR | WS-01 §4 |
| Workstream A — Research plane, Phases 0–5 · Research Plane Gen 2 | WS-03 §4 |
| Workstream B — Safety backlog · C — Exit tuning · E — P&L, profit-lock, futures, MTF | WS-02 §4 |
| Workstream D — UI | WS-08 §4 |
| Workstream F — Infrastructure, persistence & deploy safety | WS-07 §4 and WS-06 §4 |

Architectural rationale that belongs to no workstream is in
[`ARCHITECTURE.md`](ARCHITECTURE.md) and
[`rfcs/0001-component-ir.md`](rfcs/0001-component-ir.md).
