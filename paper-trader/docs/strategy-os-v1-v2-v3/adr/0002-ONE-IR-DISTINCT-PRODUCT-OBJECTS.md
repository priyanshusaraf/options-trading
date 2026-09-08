# ADR 0002: One IR with distinct product objects

Status: PROPOSED

Date: 22 August 2026

Timing amendment: bounded Dynamic Watchlists are V1. The one-IR/distinct-object decision remains unchanged; the general Workflow product stays V2.

## Context

V2 needs Strategy, Universe, Workflow, and Deployment.

Collapsing them into one object hides authority and lifecycle. Giving each a separate computation language creates multiple validators, registries, hashes, and runtimes.

## Decision

Keep these product facts distinct:

- StrategyVersion;
- UniverseDefinition and UniverseEvaluation;
- WorkflowDefinition and WorkflowInstance;
- Deployment;
- evidence, approval, portfolio admission, reservation, order, fill, and money facts.

Keep one Component IR for pure typed computation:

- one format family;
- one type registry;
- one component registry;
- one validator;
- one resolver;
- one hash discipline;
- one authored-to-resolved lineage.

Universe selection may use Component IR graphs with cross-sectional types.

Strategy uses Component IR graphs for market decisions.

Workflow uses a separate durable orchestration plan derived from a closed Workflow definition. Pure predicates may use the Component IR. Effects invoke domain commands and never run as graph kernels.

## Consequences

- A screener becomes a view of UniverseEvaluation.
- Universe selection does not become a second DSL.
- Workflow cannot bypass deployment, admission, risk, or money services.
- Strategy does not own research jobs or human approvals.
- Deployment binds exact versions of the other objects.
- Runtime engines may differ by operating need while authored computation identity remains unified.

## Rejected alternatives

- separate screener engine with its own filters;
- one giant market and Workflow graph;
- workflow steps that call brokers directly;
- mutable watchlist as Universe authority;
- provider tokens inside Strategy or Universe graphs.
