# ADR 0004: Project-owned findings use verified run lineage

- **Status:** Accepted for S4.3
- **Date:** 2026-08-03
- **Owners:** WS-03 Research with WS-04/WS-08 product surface
- **Depends on:** ADR 0001 product objects, ADR 0002 graph research binding, ADR 0003 evidence and decisions

## Context

`research.domain.models.Finding` already stores statement, polarity, confidence,
`evidence_run_id`, `superseded_by` and timestamps. The orchestrator creates positive and negative
findings from experiment outcomes. No project-owned API or product history exists, and callers can
currently see neither the exact graph/evidence binding nor revision lineage.

ADR 0001 requires one existing Finding ledger, one completed evidence run per finding and successor
revision. S4.2 now makes the linked run trustworthy: an immutable `ExperimentSpec` contains exact
graph/F14 provenance and the terminal run contains verified content-addressed evidence.

## Rejected approaches

| Approach | Reason rejected |
|---|---|
| Copy findings into the application database | Two ledgers cannot be updated atomically and will disagree. |
| Add graph or binding JSON to `Finding.statement` | It corrupts prose semantics, weakens validation and makes identity client-editable. |
| Accept a client binding, run status, confidence or evidence address | Those are server facts, not interpretation intent. |
| Recompute the experiment or F14 binding on finding reads | Historical reads could drift with code/data and would no longer report persisted evidence. |
| Update statement/polarity/confidence in place | The original interpretation and review history disappear. |
| Treat failed, running, corrupt or legacy-unbound runs as valid evidence | A Finding claims an interpretation of a completed verified result; incomplete or unverifiable evidence cannot support it. |
| Create a second knowledge/event ledger for revisions | `Finding.id` plus `superseded_by` already expresses the accepted lifecycle. |

## Decision

### Canonical lineage

`Finding.evidence_run_id` remains the persisted binding. Because Finding, ExperimentRun and
ExperimentSpec live in one database, the foreign key is the canonical relationship rather than a
copied JSON reference. A project-owned read resolves that link and returns a server-derived binding:

- finding id, evidence run id and immutable spec id;
- verified terminal-evidence content address;
- project, graph identifier, graph version and executable content address copied in the immutable
  recipe;
- active/superseded lineage.

The route recalculates the terminal-evidence address from persisted evidence. It never resolves a
current graph head, fetches data or reruns research. A finding whose linked recipe/evidence does not
verify is unavailable for product decisions rather than partially rendered.

### Creation

One closed project-owned route accepts interpretation intent only: bounded non-blank statement and
`positive | negative` polarity. It names a server-owned completed run in the path. The server:

1. verifies project ownership from immutable graph provenance;
2. requires `status=completed` and verified terminal evidence;
3. uses the run's existing hypothesis and derives confidence from persisted trade evidence through
   the existing research confidence rule;
4. inserts one Finding linked to that run in `research.db`.

No request may supply a finding id, hypothesis id, graph/binding/evidence identity, confidence,
timestamp or successor.

### Revision

Revision accepts the new statement/polarity plus `expected_superseded_by=null`. In one transaction
it inserts a successor against the same hypothesis and evidence run, then compare-and-swaps the old
row from active to that successor id. A stale or terminal revision rolls back the inserted successor
and returns conflict. The old statement, polarity, confidence, binding and timestamp never change.

The chain cannot jump to a different run or project. Revising an interpretation against new evidence
requires creating a new finding from that run; it is not a revision of the old evidence claim.

### Read and product surface

List/detail responses are project-owned and include automated and human-created findings. They show
active/superseded state, exact server binding and ordered successor history. The S4.2 evidence panel
can create an interpretation for the selected completed verified run and show/revise its history.
Controls are keyboard accessible and retain exact server validation/conflict feedback.

## Transaction and rollback

Finding creation is one research-database transaction. Revision inserts the successor and advances
`superseded_by` in one transaction; failure after either write rolls back both. A software rollback
needs no schema downgrade because S4.3 adds no table or column. Existing rows remain valid research
records; legacy-unbound rows stay excluded from project-owned decisions.

## Guard proofs

S4.3 must prove:

1. client-supplied graph, binding, confidence, evidence, id or successor fields are rejected;
2. cross-project, running, failed, corrupt and legacy-unbound runs cannot create findings;
3. reads call no provider, graph resolver, evaluator, gate or orchestrator;
4. a stale revision leaves no orphan successor;
5. revision cannot change the evidence run or mutate the original statement/polarity/confidence;
6. a failure after successor insertion rolls back both insertion and `superseded_by`;
7. reload reconstructs the same binding and complete ordered lineage from persisted rows/evidence.

## Boundary

S4.3 adds interpretation and history only. It does not change experiment execution, candidate shadow
or decision rules, deployment, runtime, orders, Python input, reusable subgraphs or marketplace
semantics.
