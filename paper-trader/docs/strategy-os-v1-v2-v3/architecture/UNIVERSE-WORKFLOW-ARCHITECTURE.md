# Universe and Workflow architecture

> **Timing amendment, 24 August 2026.** The object separation remains valid. Bounded Dynamic Watchlists now belong in V1; the general Workflow engine/builder remains V2. The static snapshot is still the required foundation.

## Decision

Introduce Universe and Workflow as first-class product objects without creating a second strategy language, validator, resolver, registry, hash, research ledger, deployment authority, or execution authority.

V1 implements only the seams required to keep this additive:

- immutable static Universe binding for new deployments;
- durable candidate-instance lineage;
- idempotent deployment command boundary;
- exact references between Strategy, Universe, evidence, Workflow context, and Deployment.

V2 implements dynamic selection, rankings, subscriptions, general Workflow templates, and multi-rate evaluation.

## Product objects

### StrategyVersion

Owns trading logic.

It answers:

    Given valid inputs and one exact context, what action does this strategy request?

It does not own candidate discovery, research workflow, capital admission, or deployment lifecycle.

### UniverseDefinition

Owns the eligibility and ranking policy.

Minimum identity:

- owner;
- stable Universe identifier;
- version;
- definition kind: STATIC or DYNAMIC;
- Component IR graph address for dynamic logic;
- static member addresses for the V1 adapter;
- evaluation policy address;
- enter, leave, cooldown, and hysteresis policy;
- resource-budget policy;
- content address;
- parent version;
- created time.

The editable name is an alias. It is not identity.

### UniverseEvaluation

Records one point-in-time application of a Universe definition.

Minimum identity:

- Universe definition address;
- evaluation time;
- knowledge cutoff;
- input dataset and market-truth addresses;
- provider capability assessment;
- complete candidate population;
- filter decisions;
- rank values;
- tie-break rule;
- selected top-K;
- enter and leave decisions;
- budget consumption;
- evaluation algorithm and version;
- content address.

The evaluation is immutable. A current screener view is a projection of the latest accepted evaluation.

### UniverseSnapshot

Records the exact concrete members and rank facts used by research or execution.

Minimum identity:

- Universe evaluation address or V1 static-definition address;
- purpose: RESEARCH or EXECUTION;
- exact canonical physical or economic member addresses;
- ordered rank facts where order matters;
- eligibility and exclusion reasons;
- content address.

A Deployment binds a snapshot, not a mutable watchlist.

### WorkflowDefinition

Owns a versioned process template:

- allowed step kinds;
- ordering and branch predicates;
- retry and timeout policy;
- required human gates;
- resource budgets;
- invalidation and retirement policy;
- content address.

V1 should not build a general Workflow graph. A closed deterministic template is sufficient for the command seam.

Pure predicates may use the existing Component IR type system. Workflow effects remain commands handled by domain services.

### WorkflowInstance

Owns durable process state:

- definition address;
- owner;
- trigger;
- exact Strategy and Universe inputs;
- current stage;
- step receipts;
- pending human gate;
- cancellation request and outcome;
- deadline;
- retry count;
- terminal result.

It never owns a graph, dataset, research result, approval, deployment, reservation, order, or money fact. It references them.

### CandidateInstance

Joins discovery to later decisions.

Proposed content identity:

    owner
    + Universe evaluation address
    + canonical member address
    + frozen rank and tie-break
    + Strategy version
    + Workflow definition and instance context
    + research policy address

The identity remains stable across retries. A material input change creates a new candidate.

### Deployment

Owns the operational binding:

- exact Strategy version and admission;
- exact Universe snapshot;
- candidate identity where dynamic;
- Workflow instance where applicable;
- data provider and execution connection;
- broker account;
- mode;
- capital and risk policy;
- schedule;
- resource plan;
- preflight receipt;
- lifecycle state.

Deployment authority remains the current Strategy OS deployment and execution path.

## One IR, several product profiles

Universe selection needs sets, maps, rankings, and top-K. Strategy logic needs series, state, and execution intent. Both should use one Component IR and registry.

Recommended type additions for V2:

- instrument_set;
- ranked_instrument_set;
- instrument_float_map;
- cross_section_float;
- eligibility_decision;
- rank_score;

Rules:

- values use canonical instrument addresses;
- set identity sorts canonical addresses;
- ranked identity stores score, rank, and explicit stable tie-break;
- unordered iteration cannot affect output;
- top-K names the cutoff and tie policy;
- all types are exact and versioned;
- no wildcard or string overlap typing;
- no provider token enters the graph.

The same validator and resolver validate Universe graphs. A derived Universe evaluation plan may run on a different schedule from a Strategy evaluation plan, but it remains derived from the one authored IR.

Workflow execution is different. It coordinates long-running effects. It may call pure predicates represented by the IR, but it does not execute broker or database effects as graph kernels.

## V1 static adapter

Current editable watchlists remain useful. The V1 adapter should:

1. read one owner-scoped watchlist;
2. resolve every member to canonical instrument authority;
3. sort the set canonically;
4. bind the exact Strategy version and intended purpose;
5. mint an immutable UniverseDefinition and UniverseSnapshot;
6. bind a new Deployment to the snapshot;
7. leave the editable watchlist free to change later.

Existing deployments remain on the explicit legacy path. Do not fabricate historical snapshots for them.

## V2 dynamic evaluation

Suggested stages:

1. Catalog eligibility: listing, venue, asset class, permissions.
2. Cheap broad filters: price, market cap, coarse liquidity, static classifications.
3. Bar-level technical filters.
4. Expensive live or specialist inputs.
5. Cross-sectional ranking and top-K.
6. Candidate research.
7. Portfolio admission.

Each stage produces a receipt and consumes a declared budget.

## Hysteresis

UniverseDefinition should separate:

- enter threshold;
- leave threshold;
- minimum residence;
- cooldown;
- debounce;
- rank persistence;
- maximum daily churn.

These rules are part of the definition address. A runtime configuration row must not silently change their meaning.

## Research and execution Universes

Keep them separate:

- Research Universe: what may be observed and studied.
- Execution Universe: what may be traded through the selected account and provider capabilities.

Execution eligibility is a narrower fact. A research candidate may remain useful even when current execution capability is absent.

## Workflow command boundary

Allowed command families:

- start research operation;
- reveal exact OOS evidence;
- request approval;
- expire approval;
- request portfolio admission;
- create or release reservation;
- create deployment;
- run preflight;
- activate, pause, invalidate, or retire deployment;
- request review.

Each command:

- names exact immutable inputs;
- has an idempotency key;
- returns a receipt;
- checks owner and current authority;
- refuses stale inputs;
- writes through the existing domain service;
- emits a durable outbox fact where required.

Workflow code cannot:

- write graph, admission, deployment, lease, intent, order, position, fill, capital, or ledger tables;
- call a broker directly;
- bypass preflight;
- arm an account by implication;
- convert a research PASS into execution authority.

## Candidate lifecycle

    DISCOVERED
      → RESEARCH_PENDING
      → RESEARCHING
      → RESEARCH_PASS or RESEARCH_FAIL or INSUFFICIENT_EVIDENCE
      → AWAITING_APPROVAL when required
      → ADMISSION_PENDING
      → ADMITTED or REJECTED
      → DEPLOYMENT_PENDING
      → ACTIVE
      → INVALIDATED
      → RETIRED

Every transition is idempotent and carries a reason.

## Migration path

1. Add immutable Universe tables and snapshot references.
2. Leave legacy Deployment rows unchanged.
3. Mint snapshots only for new or explicitly migrated deployments.
4. Add nullable candidate and Workflow lineage references.
5. Make new command paths consume exact addresses.
6. Prove old static behavior through compatibility tests.
7. Introduce Dynamic Universe definitions in V2.
8. Add historical evaluations and replay before claiming dynamic backtests.
9. Add Workflow templates after command idempotency passes.
10. Add general Workflow authoring only after observed demand.

## Open product questions and recommended defaults

| Question | Default recommendation |
| --- | --- |
| Does a Workflow own a Universe? | Reference exact versions; ownership stays with the owner, not the Workflow |
| Can one Workflow use several Universe stages? | Yes in V2, each stage produces an exact evaluation |
| Where does cross-sectional logic live? | Eligibility and rank in Universe; per-candidate trade logic in Strategy |
| Can Strategy consume a rank? | Yes as a typed immutable input from the Universe evaluation |
| Who retires a candidate? | Workflow policy requests retirement; Deployment service and position policy decide effect |
| Can membership removal close a position? | No by default; it blocks new entry and leaves explicit position management |
| Can a screen become a Strategy directly? | No; the screen is a view of a Universe evaluation |
| Can a Workflow change live semantics? | Only by creating a new exact Strategy or Deployment version through normal gates |

## Verdict

REFACTOR the V1 binding and lineage seams. DEFER the Dynamic Universe and general Workflow products to V2.
