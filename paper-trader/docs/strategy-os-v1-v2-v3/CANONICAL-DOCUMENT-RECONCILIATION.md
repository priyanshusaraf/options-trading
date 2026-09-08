# Strategy OS canonical document reconciliation

Date: 24 August 2026; amended 29 August 2026
Purpose: remove contradictory scope, timing, status and startup guidance after the hybrid-product V1 rebase and the later V0–V6 owner-direction reconciliation

## Authority and precedence

Use this order for product scope and timing:

1. Latest explicit owner decision in the active user-owned task.
2. `STRATEGY_OS_V0_V6_OWNER_DIRECTION_RECONCILIATION_2026-08-29.md` and the exact preserved 29 August owner-direction sections for product scope and maturity timing.
3. Current `CURRENT.md` → matching `PROGRAMME.json` stage → active capsule for implementation state and permission.
4. `STRATEGY_OS_HYBRID_PRODUCT_DIRECTION_AND_V1_PROGRAMME_REBASE_2026-08-24.md` and its revised programme package where not superseded.
5. `strategyos-v1-v1.1-v1.5-v2-v3-product-architecture-memo-2026-08-24.md` only where not superseded.
6. Accepted technical steers and ADRs for invariants, unless a later owner decision explicitly amends them.
7. The Grand Product Vision and August 11 V1 scope as historical direction where not superseded.
8. Older roadmap, progress, workstream and inspection documents as evidence/history only.

Implementation authority remains separate: `paper-trader/docs/agent/CURRENT.md` → `PROGRAMME.json` → active capsule → exact required sections. No scope document grants product, frontend, provider, deployment, live, order or money authority.

## Contradictions introduced by the latest owner direction

| File / section | Contradiction | Reconciliation |
| --- | --- | --- |
| 24 August architecture memo §§4.1, 4.2, 5.3, 6, 20, 25–28 | Keeps Dynamic Watchlists in V1.1; chart/reference/event semantics in V2; ten phases fixed. | Retain invariants and prior analysis. Supersede timing with the hybrid addendum and revised mapper. |
| Architecture memo §4.1 | Says public Dynamic Watchlists are not V1. | Superseded: bounded Dynamic Watchlists are V1. |
| Architecture memo §4.4/§20 | Places chart semantics and fundamentals/events in V2. | Superseded: bounded forward chart semantics and bounded point-in-time reference/events are V1; deep terminals/replay remain later. |
| `README.md` Scope decisions and reading order | Describes Dynamic Watchlists as V1.1 and chart semantics/reference/events as V2. | Replace with the new canonical reading order and scope summary. |
| `EXECUTIVE-SYNTHESIS.md` Timing authority/product timing/smallest slices | Retains V1.1 and old deferrals. | Mark as 22 August inspection evidence with timing superseded; use the new mapper for programme decisions. |
| `CURRENT-STATE-AND-RISK-MAP.md` R-06/R-12 and “must stop” | Defers Dynamic Universe/non-OHLCV V1 work. | Retain repository facts; supersede timing and use the new gap map. |
| `REMEDIATION-PLAN.md` V2 sequence and explicit deferrals | Routes Dynamic Universe/reference/events/chart artifacts to V2. | Preserve bounded architecture proposals; supersede programme sequence with Phases 5–13. |
| `architecture/V1-V2-DECISION-MATRIX.md` A-03, A-17, A-20, A-23, A-25 | Defers dynamic filters/subscriptions/non-OHLCV/chart semantics/general replay as a group. | A-03 and bounded activation/reference/chart contracts move to V1. General replay/automatic optimization stay later. |
| `architecture/UNIVERSE-WORKFLOW-ARCHITECTURE.md` opening Decision and verdict | V1 only static seam; dynamic selection V2. | Amend timing: bounded Dynamic Watchlist is V1; general Workflow remains V2. |
| `architecture/DEPLOYABILITY-IMPACT.md` V2 rows | Routes Dynamic Universe, non-OHLCV and chart artifacts to V2. | Reassign bounded V1 contracts to Phases 7–9; keep deployment obligations. |
| `adr/0001-PRESERVE-V1-AS-ADDITIVE-FOUNDATION.md` Decisions 9, V2 implementation deferred | Says non-OHLCV and Dynamic Universe/chart artifacts are V2. | Keep additive/no-rewrite rules; supersede timing for bounded V1 subsets. |
| `adr/0002-ONE-IR-DISTINCT-PRODUCT-OBJECTS.md` | Calls all Universe selection later. | Keep object/IR separation; move bounded Universe product to V1. |
| `ux/TASK-BENCHMARK.md` T-19/T-20 | Labels Universe and Workflow both V2 prototypes. | T-19 becomes a V1 benchmark; T-20 remains V2 Workflow. |
| `SOURCE-REGISTER.md` baseline/status | Records old active foundation stage and nine-source state. | Update source register with addendum, controlling assignment hash, current stage, audits and current limits. |
| `ROADMAP.md`, `PROGRESS.md` | August 13 state and ten-phase sequence; claims Phase 3 open and exposes obsolete resume guidance. | Replace with concise current pointers. Do not use for implementation truth. |
| `superpowers/plans/2026-08-13-strategy-os-v1-master-sequence.md` | Treats ten phases as durable and assigns sizing to Phase 6. | Replace with a supersession record pointing to the revised mapper. |
| Phase 5 accepted design/plan | Language/resource programme omits the owner-mandated Phase 5 sizing/admission foundation. | Preserve its accepted contracts as reusable architecture input; supersede implementation ordering and move language/resource implementation to revised Phase 6 after Phase 5 capital correctness. |
| Engineering ADR 0014 | Defers PostgreSQL until topology trigger. | Retain historical analysis; current three-plane/migration/deployability truth comes from the programme and deployability ledger. |
| Engineering ADR 0015 plane classification | Treats market plane as re-fetchable while current code flags authority-fact uncertainty. | Require the authority-fact durability ADR before new retention/topology claims. |
| Hybrid addendum §§5, 15 and the old scope matrix | Assign Dynamic Watchlists to V1 and retire V1.1 around that decision. | V1.1 remains retired, but the later 29 August maturity map moves Dynamic Watchlists to V1.5 discovery/derivatives depth. V0 retains static scopes. |
| 27 August V0 roadmap `V0.1` and `V1` Dynamic Watchlist rows | Permit Dynamic Watchlists in V0.1/V1. | Retain the V0 delivery evidence and static-scope work; supersede the capability timing with V1.5 unless a later explicit owner decision re-enters a bounded pilot. |
| 27 August V0 signal transition/projection model | Does not freeze a distinct durable `SignalAlert`, delivery attempts or attention state. | Add a monitoring-domain event distinct from legacy execution `SignalEvent`, one canonical alert, delivery attempts and separate attention events before shared monitoring persistence starts. |
| Current invited browser-auth scope | Does not include Google external identity or account linking. | Add Google sign-in where compatible through the existing product session/account seam. Keep it separate from broker OAuth and preserve a non-Google path. |
| Old V2/V3 product labels | Place multi-leg in V2 and institutional/fund breadth in V3, with no enterprise horizon. | V2 becomes active Portfolio/hedge intelligence; V3 has Strategy Asset Marketplace plus Managed Model Allocation; V4 owns multi-leg/institutional/fund infrastructure; V5/V6 is enterprise treasury. |
| ADR 0018 `PositionCampaign` and the 29 August multi-leg `Position Campaign / Economic Position` | Reuse one noun for a single-instrument lineage aggregate and a future multi-leg economic parent. | Freeze ADR 0018 meaning. Prefer an additive future `EconomicPosition` parent over one or more current campaigns/legs; never reinterpret historical rows. |

## Current navigation

This record preserves the August reconciliation and its technical conflict decisions. Its earlier fifteen-document reading chain is retired by the approved September 6 cleanup.

Use the [V0–V6 matrix](V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md) for release classification, [working plan](../agent/WORKING-PLAN.md) for priorities and [status](../agent/STATUS.md) for delivery evidence. Read an original owner source only for a specific unresolved detail. Accepted technical steers and ADRs retain invariants where not amended.

The older V1–V3 matrix and redundant ROADMAP/PROGRESS summaries were removed. Older phase plans, gap maps and handoffs are [historical references](../archive/README.md). Machine programme/capsule records remain for explicit historical queries and tooling compatibility, not as the default startup sequence.

## Source-copy integrity

| Source copied into docs | SHA-256 |
| --- | --- |
| Hybrid product addendum | `26d2c9b37aa67ae52217a55db5940c0605831125b90dc2c2671e230ae8227b41` |
| Grand Product Vision | `32ea36c1410b55f703d63caf11841c8a116534df0d02cc277906272f33c288c0` |
| August 11 V1 scope/sequence | `5ea8a7c68ac8e734e0e5898c0c28d8ae1f945326b616b0941505293764a0baec` |
| 24 August architecture memo | `087d87df2658398f89ef6b3b5a4551bac28efa2855a2d7e1e2693d63047657d8` |
| 29 August owner-direction vision | `d972263765893cf770ab2460f30d18056227b02a69bc89629c82ac4e93bd21c5` |
| 29 August V0 commercial/alerts directive | `12c38c98022697335c0fcd463fa5e1f13d6cb42fb7c648cc3a4e85f57e6d4437` |
| 29 August architecture-evolution addendum | `c93347cae7b1b2d2bd8fc1ddd7e1dbc46f9e5bb00f6fe106ccf964e4a131b7a8` |
| 29 August maturity-gated sequence | `2803365a01ed250d8c313fc55bb7d9dbeca91dbc29dfa05d7becaaa1182c70a2` |

## Nonclaims

This reconciliation changes documentation authority only. It does not implement Dynamic Watchlists, reference/events, chart integration, Operator Thesis, proposal approval, capital reservations, provider coherence, frontend work, deployment, live authority, orders or money behavior. A future capsule must prove each implementation claim directly.
