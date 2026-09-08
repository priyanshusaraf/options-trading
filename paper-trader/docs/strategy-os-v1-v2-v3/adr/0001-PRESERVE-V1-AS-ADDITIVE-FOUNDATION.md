# ADR 0001: Preserve V1 as the additive foundation

Status: PROPOSED; timing amended by the 24 August hybrid addendum

Date: 22 August 2026

The additive-foundation decision remains valid. Its blanket deferral of Dynamic Universe, non-OHLCV and chart artifacts is superseded for the bounded V1 surfaces defined in the revised scope matrix.

## Context

Strategy OS has made substantial progress across Component IR, research identity, market truth, dataset authority, tenancy, deployment, execution leases, order lifecycle, providers, database planes, backup, restore, and the frontend interaction prototype.

The V1 to V3 memo introduces major future capabilities. Treating those capabilities as a reason to reopen the whole foundation would slow V1, invalidate evidence without cause, and create parallel replacement systems.

Future issues are real. They should influence today's seams and tests without becoming speculative V2 implementation.

## Decision

V1 remains the accepted base.

Apply these rules:

1. No giant V2 rewrite.
2. No second IR, validator, resolver, hash, registry, research ledger, provider model, deployment authority, or money authority.
3. Do not reopen accepted work without a named contradiction and transitive evidence.
4. Record a future risk at the smallest stable boundary.
5. Change V1 now only for current correctness, safety, or a persisted shape that would force destructive reinterpretation.
6. Keep full V2 product behavior out of the V1 critical path.
7. Preserve existing compatibility paths and historical records.
8. Route each accepted change through one bounded capsule with exact tests, migration, rollback, and deployability impact.
9. Keep non-OHLCV product support in V2.
10. Let current foundation work continue in its established dependency order.

## Consequences

Positive:

- protects completed work;
- makes V2 additive;
- keeps V1 shippable;
- prevents competing abstractions;
- turns future risk into named tests and migration duties.

Costs:

- some V1 seams need extra architecture work;
- legacy paths remain during migration;
- future capsules must prove compatibility instead of replacing code wholesale.

## V1 refactors accepted in principle

- immutable static Universe snapshot for new deployments;
- durable candidate-instance lineage;
- portfolio admission and capital reservation;
- operational canonical-instrument completion;
- Workflow-safe command boundary;
- reconstruction receipt contract.

## V2 implementation deferred

- Dynamic Universe product;
- general Workflow engine and builder;
- non-OHLCV data;
- dynamic subscriptions;
- multi-rate runtime;
- chart artifacts;
- general event replay.

## Rejected alternatives

- build V2 inside V1;
- freeze all V1 work until the memo is implemented;
- create a separate screener or Workflow language;
- declare the current system future-proof without evidence;
- ignore future persisted-schema risks.

## Evidence required to change this ADR

A replacement proposal must show:

- a current V1 invariant cannot be met by the existing foundation;
- the failure affects a complete claimed universe;
- a bounded additive correction cannot close it;
- migration and rollback are safer under replacement;
- independent review supports the conclusion.
