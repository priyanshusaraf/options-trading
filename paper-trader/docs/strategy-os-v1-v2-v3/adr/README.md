# Strategy OS ADR index

Date reviewed: 2026-08-31

These ADRs are proposed records. The accepted 29 August V0–V6 reconciliation and
the active programme/capsule control release timing and implementation permission.
An ADR does not authorize product, schema, dependency, provider, execution, money
or deployment work.

| ADR | Status | Durable decision | Current timing note |
| --- | --- | --- | --- |
| [0001 — Preserve V1 as the additive foundation](0001-PRESERVE-V1-AS-ADDITIVE-FOUNDATION.md) | Proposed | No rewrite or second IR/authority; change the foundation only for current correctness or a destructive persisted assumption. | Research/alerts now belong to V0; later releases follow the 29 August matrix. |
| [0002 — One IR with distinct product objects](0002-ONE-IR-DISTINCT-PRODUCT-OBJECTS.md) | Proposed | Strategy, universe, workflow, deployment, evidence and money facts remain distinct while pure computation uses one IR. | Its older Dynamic Watchlist timing is superseded; Dynamic Watchlists are V1.5. |
| [0003 — Durable portfolio admission and capital reservation](0003-DURABLE-PORTFOLIO-ADMISSION-AND-RESERVATION.md) | Proposed, critical | Simultaneous admission and capital reservation are durable, deterministic, fenced facts. | Controlled execution is V1; active portfolio/hedge intelligence is V2. |
| [0004 — Keep domain jobs before a Workflow dependency](0004-KEEP-DOMAIN-JOBS-BEFORE-WORKFLOW-DEPENDENCY.md) | Proposed | Existing domain jobs remain authoritative until a measured ceiling and bounded comparison justify a dependency. | Chat 2 retained this decision after reviewing Temporal, DBOS and Restate. |

## Chat 2 decision packets

Chat 2 created no new ADR because no new architecture component or authority model
was accepted. The current decisions remain `KEEP + HARDEN` and `DEFER/REJECT`:

- [source conflicts and rejected machinery](../../research/professional-engineering-v5/18-SOURCE-CONFLICTS-AND-REJECTED-CARGO-CULT.md)
- [consolidated source-to-decision matrix](../../research/professional-engineering-v5/20-CONSOLIDATED-SOURCE-TO-DECISION-MATRIX.md)
- [implementation candidate gate](../../research/professional-engineering-v5/22-IMPLEMENTATION-CANDIDATE-GATE.md)
- [future release seams](../../architecture/FUTURE-RELEASE-BACKEND-SEAMS-AND-ADOPTION-TRIGGERS.md)
- [scale and measured triggers](../../architecture/SCALE-50-TO-10000-MEASURED-TRIGGERS.md)

A future correction may need a new or amended ADR only if it changes a real schema,
authority, provider, runtime or migration policy. Local bug fixes that preserve these
decisions do not need decorative ADRs.
