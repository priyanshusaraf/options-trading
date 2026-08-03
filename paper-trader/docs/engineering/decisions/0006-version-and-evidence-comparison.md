# ADR 0006: Compare immutable graph documents before their experiment evidence

- **Status:** Accepted for S4.5
- **Date:** 2026-08-03
- **Owners:** WS-04 Editor, WS-03 Research and WS-08 product surface
- **Depends on:** RFC 0001, ADR 0002 graph/run binding, ADR 0003 verified evidence

## Context

S4.2 added a pure comparator for two verified terminal evidence envelopes. It reports graph,
resolution, parameters, datasets, costs, gates, build and result differences and marks changed
dataset, cost and gate contracts incomparable. Its graph section is intentionally only the
identity summary persisted in experiment provenance: project, identifier, version, content address,
component versions and node identities. It does not load or compare the immutable Component IR
documents that those identities name.

The graph store already owns canonical append-only `GraphVersion` rows and project ownership. The
layout store owns separately revisioned positions and visual groups. A version comparison must use
the former and must never load the latter. Resolving or executing graphs during comparison would
also turn a persisted read into recomputation and make old comparisons depend on the current
component library.

## Rejected approaches

| Approach | Reason rejected |
|---|---|
| Expand the evidence envelope to copy full graph JSON | It duplicates immutable graph storage and makes old evidence carry a second graph document. |
| Accept raw left/right graph or evidence JSON | Clients could claim executable or experiment identity and compare documents the project never published. |
| Resolve both graphs before diffing | Resolution is derived, library-dependent work. The existing evidence already preserves the exact resolution used by each run. |
| Compare layouts or visual groups with executable differences | Presentation is independently revisioned and excluded from content address, experiment identity and runtime behavior. |
| Replace the S4.2 evidence comparator | Its evidence categories and like-for-like rules are already accepted and tested. Structural comparison composes with it. |
| Treat node/edge array order as structure | Order can change executable bytes/address in format v1, but it does not add/remove a node or edge. It needs an explicit identity-order diagnostic, not a false topology change. |

## Decision

### Pure graph comparison

A pure editor-side comparator consumes two already-loaded immutable graph documents. It does not
load state, resolve components, call kernels or know about research. It produces deterministic
differences in these closed dimensions:

- `structure`: authored node and edge additions/removals, keyed by instance id and exact socket
  endpoints rather than array index;
- `components`: component identifier/version changes for a retained authored node;
- `parameters`: override and secret-reference changes for a retained authored node;
- `interface`: graph interface changes;
- `metadata`: display name, parent version, domain and other executable authored metadata;
- `identity`: declared version/content address and node/edge order differences that change the
  exact immutable document without pretending topology changed.

Difference records are canonically ordered by dimension and path. Missing values use the existing
explicit `{state: "missing"}` form, distinct from `null`. Presentation state is neither an input nor
a dimension. A non-empty executable `groups` field is rejected as presentation contamination under
the accepted S3.2b/S3.3 contract rather than normalized away silently.

### Server-owned selections and optional evidence

A new closed project-owned comparison request contains two selections. Each names a graph
identifier and version and may name a run id. The server loads both immutable versions under the
path project, verifies canonical JSON and content address, and compares them. It accepts no raw
graph, content address, component identity, evidence, result or presentation fields.

Run ids are optional as a pair: either both selections include one or neither does. When present,
the server loads verified terminal evidence through the existing read seam and verifies each
evidence graph project/identifier/version/content address exactly matches its selected immutable
version. A mismatch or corrupt/unavailable/legacy run fails closed. The existing S4.2 evidence
comparator then contributes resolution, dataset, cost, gate, build and result differences. The
combined response has one deterministic difference list and the accepted incomparable reasons.

The existing run-only comparison route remains for compatibility. It delegates to the same
evidence comparator and is not widened to accept graph documents.

### Product reads

A closed version-list read exposes server-owned version number and content address for selection.
The comparison surface offers immutable version selection and optional persisted run selection,
shows exact categories and incomparable reasons, and reloads from server state. It contains no
publish, execute, deploy, arm, order, raw graph or presentation control.

## Failure behavior

- missing/wrong-project graph or run: 404 without cross-project disclosure;
- corrupt graph canonical bytes/address or corrupt evidence: stable 409;
- unavailable legacy/running evidence, one-sided run selection or run/version binding mismatch:
  stable 409/422 as appropriate;
- request extras or client identity/evidence claims: closed 422;
- same exact selections: an equivalent response with no differences.

## Rollback

No schema or stored document changes. Reverting removes the new comparison/list reads and UI while
leaving immutable versions, layouts, experiments, findings and the S4.2 run-only comparator intact.

## Guard proofs

S4.5 must prove:

1. same versions compare equivalent and response ordering is deterministic;
2. node/edge order-only change is not reported as topology change but remains an identity change;
3. visual positions/groups cannot enter the comparison or affect its result;
4. changed component versions and overrides have distinct exact categories;
5. different graph JSON cannot share one accepted declared content address;
6. supplied run ids must bind to the selected server-owned graph versions;
7. raw graph/evidence/content-address/presentation input is rejected;
8. comparison invokes no resolver, provider, orchestrator, evaluator, kernel or state mutation.

## Boundary

S4.5 adds immutable version/evidence comparison only. It does not add reusable subgraphs, graph
merging, fork/restore, execution, scheduling, dataset replay, Python input, deployment, marketplace
or live IR-runtime adoption.
