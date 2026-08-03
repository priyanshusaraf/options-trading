# ADR 0002: Immutable graph-version research binding

- **Status:** Accepted
- **Date:** 2026-08-03
- **Scope:** S4.1 graph-version experiment provenance
- **Implements:** ADR 0001, RFC 0001 F14, execution-plan slice S4.1

## Context

Strategy OS already has two durable authorities. The application database owns Project, graph
artefact and immutable GraphVersion. The isolated research database owns the immutable
ExperimentSpec and its ExperimentRun, Findings and PromotionCandidates. The research orchestrator
already owns qualification, walk-forward validation, statistical gates, scoring and promotion.

S4.1 must connect those authorities without inventing a third experiment record, weakening
research isolation or pretending SQLite can enforce a foreign key across two database files.

The current experiment recipe is content addressed and stores dataset content hashes, but it does
not persist the graph version or all result-affecting assumptions. Capital, fold-stability,
slippage stress, PBO threshold and sibling-trial count can currently change without all of them
changing the immutable recipe identity. That is insufficient provenance for a project-owned graph
experiment.

## Rejected models

| Rejected model | Reason for rejection |
|---|---|
| A new application-database Experiment table | It duplicates the accepted research ledger and creates two experiment identities. |
| A cross-database SQL foreign key | SQLite cannot enforce it. Claiming otherwise would create false integrity. |
| Binding an experiment to the graph artefact head | A later edit would silently change what the run appears to have evaluated. |
| Accepting graph JSON, version or content address in the request body | The client could select content that is not the project-owned immutable row named by the route. |
| Re-resolving a draft or the newest version at worker time | Results could follow mutable or newer content after the user selected a version. |
| A second graph-specific gate pipeline | It would disagree with the existing qualification, walk-forward, DSR, PBO and slippage gates. |
| Persisting only dataset keys or time ranges | Provider corrections could change the bytes without changing the apparent dataset identity. |
| Treating presentation revision as experiment provenance | Layout and visual groups are non-executable under F13. |
| A distributed transaction between the application and research databases | No transaction manager exists. The immutable source row makes a read-copy safe; no application state is written. |

## Accepted contract

### API

`POST /api/ir/projects/{project_id}/graphs/{identifier}/versions/{version}/experiments`
is mirrored under `/api/v1`. It is available only while the research plane is enabled.

The route path is the only graph selector. The body is closed and contains:

- program and hypothesis text;
- one to 32 bounded dataset selections (`instrument_key`, `interval`, `days`);
- explicit gate settings;
- explicit cost assumptions: capital, slippage basis points, slippage multiplier, and the fixed
  server-declared charge and sizing models;
- a deterministic seed and the bounded optimization flag.

The body cannot contain graph JSON, graph identifier, graph version, content address, component
versions, node identities, dataset hashes, executable code or deployment state.

The application boundary verifies that the project is active, owns the graph artefact and owns the
named published version. Unknown projects, artefacts and versions return exact `404` errors;
archived projects and unpublished artefacts return exact `409` errors; closed-body or value errors
return `422`. Raw graph or client-selected identity fields are rejected by the request model.

### Cross-database publication

The application transaction is read-only. It copies the already immutable GraphVersion JSON and
its server-derived content address, then closes. The research transaction creates or reuses one
immutable ExperimentSpec and creates one ExperimentRun through the existing orchestrator. If the
research transaction fails, no application state has changed. Retrying the same inputs reuses the
same spec and creates a new run, which is the existing retry contract.

There is deliberately no cross-database atomicity claim and no cross-database foreign key. The
copied reference is checked at the boundary and is safe because GraphVersion rows reject update
and delete at the database layer.

### Immutable recipe

The existing `ExperimentSpec.recipe_json` remains the sole experiment specification. For a graph
experiment it contains these canonical sections:

1. `graph`: project id, graph identifier, exact version and content address;
2. `resolution`: component versions and authored-node cache identities derived by the existing IR
   resolver, never supplied by the client;
3. `datasets`: instrument, interval, requested window, bar count, start/end timestamps, candle
   content hash, and the F14 input-data digest derived from the exact series passed to the graph;
4. `cost_assumptions`: capital, slippage basis points and multiplier, plus explicit charge and
   sizing model identifiers;
5. `gates`: every result-affecting qualification, fold, stability, optimization, PBO and
   sibling-trial input;
6. existing code/rule versions, seed, strategy key and bound parameters.

All six sections feed `ExperimentSpec.id`. A change to graph bytes, dataset bytes, costs, gates,
seed, rule versions or parameters creates a different immutable spec.

The graph content address is checked against the canonical GraphVersion JSON before research
starts. F14 records are derived from the resolved graph and each materialized dataset. Resolution
evidence cannot be passed in from the API.

### Existing experiment flow

The published graph is adapted to the existing Strategy interface with the accepted IR resolver
and runtime implementations. `run_experiment` remains the only qualifier, optimizer, validator,
gate, score, Finding and PromotionCandidate pipeline. S4.1 adds provenance inputs to that function;
it does not copy its behavior.

The exact graph version is loaded once. Neither the route nor the orchestrator asks for the latest
version after that point. Layout revision, positions and visual groups are absent from the recipe.

### Safety boundary

This slice evaluates research data only. It does not create or activate a Deployment, import the
IR graph into live execution, place orders, arm execution or change the research promotion gate.
Any later runtime adoption remains separately owner gated.

## Consequences

An ExperimentSpec can now answer which immutable executable graph, resolved components, node
identities, exact dataset bytes, cost model and statistical assumptions produced a run. Reloading
research.db preserves that evidence, and later graph publication cannot move the binding. The
cost is an explicit API bridge and duplicated immutable identifiers across databases; that is the
accepted price of keeping the research plane isolated and the provenance honest.
