# Strategy OS architecture map

Strategy OS uses one strategy language across editing, research and supported runtime evaluation. V0 is the research-and-alerts product; controlled public execution belongs to later releases. Existing trading-bot code is a separate operational concern, not evidence that V0 is safe to trade.

## Feature relationships

| Producer | Consumer | Contract that crosses the boundary |
| --- | --- | --- |
| Editor and component registry | Validator, resolver and research | Immutable strategy revision and resolved semantic versions; layout does not change executable identity. |
| Data providers and canonical instrument store | Research and monitoring | Attributable datasets/observations, completed-bar timing, instrument identity, coverage and capability limits. |
| Research operations | Comparison, evidence and review | Exact strategy/data/implementation/cost identity and separate selection/holdout evidence. |
| Monitoring evaluation | Alerts Inbox and delivery | Immutable signal event; derived alert; separate delivery and mutable attention records. |
| Approved research and execution binding | Sizing, admission and execution | Evidence is an admission prerequisite, not a live authority lease. Account, mode and exact revision remain explicit. |
| Execution and inventory | Later portfolio/campaign products | Durable position ownership, reservations, fills and reconciliation. Future portfolio proposals cannot bypass current capital admission. |
| Strategy packages | Later marketplace | Versioned content, provenance, rights and local preflight. Distribution grants no order authority. |

## Shared invariants

- One canonical IR, validator, resolver, executable hash and component registry. Editors are views; presentation state is separate.
- Strategies, revisions, datasets, experiments, evidence, monitoring events, alerts, deployments, authority and money records have distinct identities and owners.
- Use causal completed-bar inputs, canonical instruments and configured costs. A strategy may observe another instrument; missing or stale inputs need explicit reasons.
- Separate data providers from execution brokers. Declared capability and public data availability do not establish commercial rights.
- Keep tenant boundaries across API, persistence, jobs and caches. Preserve sufficient immutable evidence to reconstruct decisions.
- Keep paper/live books separate and live authority closed by default. ARM gates entries; risk-reducing exits remain available. Research and local tests grant no execution authority.
- Strategy intent does not encode broker implementation. Executors must not branch on component provenance. Packages do not transport live execution state.

## Read the relevant contract

| Concern | Sources |
| --- | --- |
| Product objects and five node families | [Product steer](program/owner-steers/00-STRATEGY-OS-PRODUCT-STEER.md), [object ADR](engineering/decisions/0001-product-object-contract.md) |
| Language and numerical semantics | [Language steer](program/owner-steers/01-STRATEGY-LANGUAGE-NODE-SYSTEM.md), [IR RFC](rfcs/0001-component-ir.md) and accepted amendments |
| Data identity and causality | [Market-truth steer](program/owner-steers/02-MARKET-TRUTH-DATA-CONTRACTS.md) |
| Execution, ownership and recovery | [Execution steer](program/owner-steers/03-DEPLOYMENT-EXECUTION-TRUST.md), [ADRs](engineering/decisions/) |
| Resource plans and provider capabilities | [Runtime steer](program/owner-steers/04-RUNTIME-ECONOMICS-PROVIDER-CAPABILITIES.md) |
| Later-release continuity | [Architecture evolution](program/owner-directions/2026-08-29/03-ARCHITECTURE-EVOLUTION-AND-NO-DEAD-END-INVARIANTS.md), [future adoption triggers](architecture/FUTURE-RELEASE-BACKEND-SEAMS-AND-ADOPTION-TRIGGERS.md) |

These sources retain detailed contracts; this map does not amend them. Resolve conflicts using the latest scoped owner decision and accepted technical amendments. Historical release labels do not repeal invariants.

## Repository orientation

The V0 interface lives in `paper-trader/strategy-frontend`; `paper-trader/frontend` retains the bot UI. Backend language, APIs, providers and execution live under `paper-trader/backend/app`; research is under `paper-trader/backend/research`. Check nearby code/tests for the actual integration before claiming a path is usable.

Use the [working plan](agent/WORKING-PLAN.md) for priorities, [status](agent/STATUS.md) for recorded evidence and the [V0–V6 roadmap](strategy-os-v1-v2-v3/V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md) for release classification.
