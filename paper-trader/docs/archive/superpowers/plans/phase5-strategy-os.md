# Phase 5 Strategy OS implementation plan

Status: `ACCEPTED_IMPLEMENTATION_HANDOFF`\
Date: 2026-08-24

This plan records the accepted Phase 5 implementation handoff. It activates only the first ready capsule through the programme. Every later capsule still needs its dependency gate, durable goal, exact paths, exclusive ownership, observable rejection-first evidence, deployment impact, and owner gates before dispatch.

## Dependency order

1. `phase5-graph-paper-attribution-schema` (`C0`)
   - Separate full graph addresses from strategy-version labels across required paper and backtest attribution.
   - Prove SQLite and disposable PostgreSQL 16 migration, preservation, restart, and refusal.
   - End with `V2_RUNTIME_UNAVAILABLE` unchanged. Schema acceptance grants no consumer reachability.
2. `phase5-adv-006-runtime` (`C1`)
   - The only capsule carrying `P5-ADV-006-RUNTIME`.
   - Depend on accepted `C0`.
   - Preserve the existing five-state job lifecycle and sole authority loader.
   - Prove claim, real process death, ownership loss, public reclaim, exact current-authority reload, stale fencing, and current-only exactly-once finalization on SQLite and PostgreSQL 16 before any named v2 consumer becomes reachable.
3. `phase5-language-resource-contracts` (`C2`)
   - Extend the one registry/component contract with the exact first-party node fields, five visible families, lowered-leaf accounting, state contract, ResourcePlan, provider requirements, provisional tier policy, and typed refusals.
   - Depend on accepted runtime assurance, which already depends on `C0`; Phase 5 stays serial at shared runtime and registry boundaries.
4. `phase5-provider-evidence-compatibility` (`C3`)
   - Map fixtures into accepted Phase 4 provider facts only.
   - Depend on `C2` and accepted Phase 4 authority. No network, credentials, fallback, or real-provider conformance.
5. `phase5-first-party-analytical-catalogue` (`C4`)
   - Populate the sole registry with the frozen Type 2/4 V1 inventory and one shared conformance harness.
   - Depend on accepted `C1` and `C2`.
6. `phase5-state-execution-derivatives-catalogue` (`C5`)
   - Type 1/3/5 intent, selectors, validity, temporal, and state primitives.
   - Depend on `C1`, `C2`, and `C3`; no broker calls or money authority.
7. `phase5-custom-node-contracts` (`C6`)
   - Define Levels 1–4 admission, family, resource, provenance, and security contracts.
   - Depend on `C1` and `C2`. Level 3/4 runtime remains unavailable without a separate owner/security gate.
8. `phase5-research-execution` (`C7`)
   - Vector research, incremental semantics, trigger scheduling, state snapshots, causality, and parity over verified datasets.
   - Depend on `C1`, `C4`, `C5`, and `C6`.
9. `phase5-bounded-sweeps-cache-artifacts` (`C8`)
   - Bounded parallel sweeps, cache identity, result/artifact lineage, sharing limits, and research cost accounting.
   - Depend on `C7` and retain existing dataset/cache authorities.
10. `phase5-research-runtime-packaging` (`C9`)
    - Locked dependencies, explicit worker/queue/cache/artifact roles, bounded concurrency, restart, health, and production-shaped local evidence.
    - Depend on `C8`; retain release and production nonclaims.
11. `phase5-canonical-scenario-gate` (`C10`)
    - Reusable equity, weekly options/order-flow, and cross-market architecture scenarios plus GOLD/CRUDEOIL and one-strategy/three-binding resource facts.
    - Depend on `C3` through `C9`.
12. `phase5-review` (`C11`)
    - One Sol-high review with separate SPEC and QUALITY verdicts.
    - Depend on accepted `C10` and one current package.

## Independent assurance ownership

- `phase5-language-resource-assurance`: complete node fields, families, lowering leaves, complexity dimensions, ResourcePlan fields, roles, and policy separation.
- `phase5-adv-006-runtime-assurance`: all claim/reclaim/worker/result/cache/broker/order/money entry points and the real process-death lifecycle.
- `phase5-research-parity-assurance`: cache/provenance dimensions plus batch/incremental state, causality, warmup, and invalidity.
- `phase5-scenario-assurance`: all canonical scenarios and Phase 5 carry-through seed cases.

Implementation owners cannot certify these Critical boundaries. Missing, stale, reordered, selectively sampled, or self-derived universe members invalidate dependent evidence.

## Exact programme stage order

1. `phase5-graph-paper-attribution-schema`
2. `phase5-adv-006-runtime`
3. `phase5-adv-006-runtime-assurance`
4. `phase5-language-resource-contracts`
5. `phase5-language-resource-assurance`
6. `phase5-provider-evidence-compatibility`
7. `phase5-first-party-analytical-catalogue`
8. `phase5-state-execution-derivatives-catalogue`
9. `phase5-custom-node-contracts`
10. `phase5-research-execution`
11. `phase5-research-parity-assurance`
12. `phase5-bounded-sweeps-cache-artifacts`
13. `phase5-research-runtime-packaging`
14. `phase5-canonical-scenario-gate`
15. `phase5-scenario-assurance`
16. `phase5-implementation`
17. `phase5-review`

The language/resource contract stage follows accepted runtime assurance. All catalogue, custom, research, cache/artifact, packaging, scenario, broker, order, and money consumers depend transitively on that assurance. Shared runtime, registry and schema boundaries remain serial.

## Architecture handoff gate

The design now closes canonical role/binding vocabulary, ResourcePlan identity and units, the V1 catalogue inventory and wave-2 deferral, state restart/reset semantics, and Level 3/4 security scope. Implementation dispatch remains blocked only until architecture artifacts, all capsule frontmatter, SOURCE_MAP coverage, programme dependencies, deployment ownership, and the handoff validate. The source-coverage and existing-capability reports under `.agent/runs/phase5-architecture/` remain bound architecture inputs.

No step grants frontend implementation, provider/broker integration, credentials, deployment, production data, live authority, sizing/routing/risk changes, orders, money movement, commercial pricing, or release readiness.
