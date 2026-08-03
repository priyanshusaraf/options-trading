# ADR 0003: Persisted research evidence and candidate decisions

- **Status:** Accepted
- **Date:** 2026-08-03
- **Scope:** S4.2 evidence, comparison and human-decision boundary
- **Implements:** ADR 0001/0002 and execution-plan slice S4.2

## Context

S4.1 binds an immutable ExperimentSpec to one project-owned GraphVersion, exact datasets, costs,
gate inputs and build provenance. The existing orchestrator returns richer result evidence, but
much of it is transient: full rejected gate values, regimes and explanations live in the returned
report or a markdown file; only selected Finding text and successful-candidate scorecards reach
`research.db`. A product read API cannot reconstruct the original decision without recomputing it.

The current approval bridge also has a bypass. The approval queue lists only `pending` candidates,
but direct `get_promotion(id)` and `approve_candidate(id)` accept any status. A caller who knows a
candidate id can therefore stage a `shadow` candidate before it has earned admission to the human
queue. The accepted shadow contract already forbids this; S4.2 must enforce it at every path.

## Rejected models

| Rejected model | Reason for rejection |
|---|---|
| Recompute evidence when the UI reads a run | Provider data, code, costs or gates may have changed. A read would create new evidence while claiming to show old evidence. |
| A second evidence or experiment ledger in the application database | It duplicates research truth and cannot be atomically synchronized across database files. |
| Treat Finding prose as complete run evidence | It omits full gate values, scorecards, regimes, breadth, explanation and failure structure. |
| Put final evidence in mutable graph or presentation state | Result evidence belongs to the run and must never affect executable graph identity. |
| Add an unplanned generic JSON table | `ExperimentRun.checkpoint_json` already owns resumable/final run state. A second generic row adds identity without adding integrity. |
| Compare only headline return or DSR | A graph, dataset, cost or gate change can make the numbers incomparable even when the headline happens to match. |
| Let a client submit evidence, status, scorecard or graph provenance | Evidence is produced by the server pipeline. Accepting it would let a decision cite facts that were never measured. |
| Approve or deploy a `shadow` candidate by direct id | It bypasses the prospective-evidence gate. Queue filtering alone is not authorization. |
| Let approval arm or activate execution | Research decisions and runtime adoption remain separate owner-gated actions. |

## Accepted contract

### Terminal evidence envelope

`ExperimentRun.checkpoint_json` remains the run-owned persistence field and gains one closed final
shape:

```json
{
  "schema_version": 1,
  "content_address": "sha256:...",
  "evidence": { "...server-derived final report evidence...": "..." }
}
```

The content address is derived from canonical `evidence`; it is never accepted from a request.
Completed and failed runs receive a terminal envelope in the same research transaction as their
terminal status. A reader recalculates the address and fails closed on malformed or mismatched
evidence. Legacy runs with no envelope remain explicitly `legacy_unbound`; they are visible as
history but cannot support comparison, candidate decisions or deployment.

The success evidence contains:

- spec/run identity and terminal decision;
- complete graph, resolution, dataset, cost, gate, hypothesis and build provenance copied from the
  immutable ExperimentSpec;
- per-instrument qualification outcome, trade count and exact rejection reason;
- per-instrument walk-forward gates, including slippage stress and PBO when applicable;
- scorecards, DSR, breadth/N_eff and the selected proposal;
- regimes and the exact server-generated strategy explanation;
- total bars and timestamps.

Failure evidence contains the immutable spec provenance, stage, stable error code and bounded
message. It never stores a traceback, credentials, provider payload or arbitrary exception object.

### Read surface

Closed project-owned routes list and load graph-bound runs from `research.db` by verifying the
copied `graph.project_id` in the immutable recipe and terminal evidence. Cross-project lookups are
reported as not found. Detail responses render persisted evidence only; they never call a data
provider, resolver, evaluator or gate.

Legacy, running, failed and completed states are explicit. Missing or corrupted evidence fails
closed with a stable response and cannot be treated as an empty successful result.

### Comparison

Comparison is a pure deterministic function over two verified immutable recipes and terminal
evidence envelopes. It reports exact differences in:

1. graph identifier, version, content address and authored executable graph identity;
2. component versions and resolved node identities;
3. dataset keys, spans, counts, content hashes and F14 digests;
4. costs, gates, seed, rule versions, hypothesis and build;
5. per-instrument qualification, validation, score and final-decision evidence.

The result names incomparable dimensions instead of coercing them into a performance delta. It
does not claim that different datasets, costs or gates are like-for-like.

### Candidate state and decisions

The existing `PromotionCandidate` remains the only candidate record. Legal transitions are:

`shadow -> pending -> approved | rejected`.

Only `promote_if_ready` may perform `shadow -> pending`. Human decisions require the exact expected
`pending` status and a non-empty bounded reason. The update is compare-and-swap: a stale or terminal
decision returns conflict and does not overwrite the first decision. Decision evidence is appended
to the candidate's existing scorecard JSON in canonical form; no client may replace the scorecard.

Every direct read or write used by the deployment bridge must require `pending`. Knowing a shadow,
approved or rejected id grants nothing. Approval in S4.2 records the research decision only. Any
later draft deployment creation remains a separate idempotent bridge, and activation/arming remains
owner gated.

### Product boundary

S4.2 may surface evidence, comparisons and decision controls in the Strategy OS UI. It may not
execute a graph, create orders, arm execution, activate a deployment, accept Python or recompute
historical evidence on read.

## Consequences

A user can inspect and compare the evidence that actually produced a research decision after a
reload, including negative results. The system closes the direct-id shadow bypass. The cost is a
versioned JSON envelope in the existing mutable run row; integrity therefore depends on canonical
address verification and closed write paths rather than a new immutable SQL table. If evidence
later needs independent retention or streaming, a migration can promote this accepted envelope to
its own table without changing its content contract.
