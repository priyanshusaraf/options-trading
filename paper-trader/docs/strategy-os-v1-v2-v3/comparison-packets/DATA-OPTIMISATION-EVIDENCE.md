# Data, optimisation, and evidence comparison packet

## Owner scope decision

Non-OHLCV product support stays in V2. This packet assesses the future seam only. It does not recommend widening V1 storage, replay, providers, or UI.

## Current Strategy OS data position

Strong current contracts:

- content-addressed ordered candle identity;
- fixed V1 candle blob with numeric ingress validation;
- typed raw and normalized Phase 4 observations;
- event, completed, available, recorded, and knowledge times;
- canonical instrument and market-truth addresses;
- immutable dataset segments and manifests;
- explicit gaps, corrections, policies, provider contracts, and capability assessments;
- owner-scoped research authority;
- cache identity tied to graph, implementation, data, market truth, policy, assessment, and admission.

Current limits:

- public dataset bytes remain fixed OHLCV;
- legacy dataset identity remains candle shaped;
- generic DataObservation is numeric;
- data requirement fields are a closed market-data vocabulary;
- ReplayProvider reads candle JSON only;
- no point-in-time fundamental, event, macro, news, or chart artifact exists.

## Comparison

| Source | Strong pattern | Strategy OS decision |
| --- | --- | --- |
| DVC data | path separate from object identity; child-first manifest publication | keep object addresses below Strategy OS semantic manifests |
| Optuna | ask-and-tell sampler boundary, trial storage, heartbeat | adapt later; Strategy OS keeps research validity |
| Riskfolio-Lib | compile reviewable policy to mathematical constraints; expose risk contribution | bounded future portfolio-risk spike |
| vectorbt | efficient whole-series execution and named outputs | reference only under current licence |
| LEAN | subscription semantics and canonical security identity | keep data binding separate from strategy identity |
| Pandera | typed dataframe validation across common engines | future V2 data-admission spike, not a core authority |
| Great Expectations | expressive data expectations and validation documents | reference only unless V2 operating needs exceed the current validator |
| OpenLineage | job, run, dataset, and extensible facet vocabulary | reference; do not replace Strategy OS exact provenance |
| Hypothesis | generated edge cases and shrinking | adopt for bounded pure-contract tests where it improves failure discovery |

## Research lineage model

Keep these facts distinct:

    ResearchProgram
      → Hypothesis
      → ExperimentSpec
      → ExperimentRun
      → OptimizationTrial
      → Finding
      → PromotionCandidate
      → Approval
      → Deployment

Every link references exact immutable versions and owner scope. A Workflow may coordinate the chain but cannot replace the facts.

## Optimisation trial contract

Each trial should retain:

- experiment and search-space identity;
- sampler name, version, configuration, and seed;
- proposal order;
- worker and attempt identity;
- exact graph and parameters;
- exact dataset and window;
- costs, slippage, market truth, and evaluation policy;
- completed, failed, pruned, or cancelled state;
- intermediate values only when their statistical meaning is declared;
- result metrics;
- qualification decision;
- inclusion in the multiple-testing population.

Parallel completion order must never silently change a claimed deterministic search.

## Cache audit

Current Phase 4 cache identity is strong. Future V2 identities should add:

- Universe definition and evaluation address;
- rank and top-K policy address;
- Workflow research policy address;
- event or external-data revision addresses;
- chart artifact address;
- runtime-plan version only when it changes semantics;
- portfolio admission policy where a result includes portfolio outcomes.

Do not include:

- node coordinates;
- open inspector;
- browser layout;
- worker hostname;
- mutable path;
- provider token;
- unversioned latest alias.

## Future non-OHLCV contract

When V2 starts, add new versioned data artifacts rather than modifying candle identities in place.

The future observation envelope should support:

- value type reference;
- semantic unit;
- subject or canonical instrument;
- source product and contract;
- event time;
- period end where relevant;
- published time;
- effective time;
- available time;
- ingested or recorded time;
- revision and supersession;
- validity and freshness;
- raw evidence address;
- normalization and algorithm address.

Fundamental, event, macro, OI, news, and chart data may specialize this envelope. They must not create unrelated provenance systems.

## Tool decisions

| Tool | Verdict | Reason |
| --- | --- | --- |
| Optuna | ADAPT / WRAP after bounded spike | useful sampler and trial coordination, not research authority |
| Riskfolio-Lib | REQUIRES BOUNDED SPIKE | solved portfolio math, but request and receipt must remain Strategy OS facts |
| Pandera | SPIKE in V2 data admission | focused dataframe validation with MIT licence |
| Great Expectations | REFERENCE | heavier operating surface than current need |
| OpenLineage | REFERENCE | generic model cannot replace exact trading provenance |
| Hypothesis | ADOPT selectively | strong for closed pure invariants and adversarial generation |
| vectorbt | REJECT dependency | Commons Clause conflicts with hosted-product use |
| TimescaleDB | REJECT now | no measured database need and mixed licence surface |

## Candidate tests

1. Two byte-identical objects under different paths share an object address.
2. Parent manifest cannot publish before every child exists and verifies.
3. Dataset correction invalidates cache and prior capability assessment.
4. Owner substitution fails even when all public data bytes match.
5. Same graph on different market-rule snapshot produces a different result identity.
6. Sampler seed and completion order are retained.
7. Failed and pruned trials remain in the search population under an explicit rule.
8. OOS stays hidden until the candidate is frozen.
9. A revised external observation does not rewrite the historical value known at time T.
10. A future chart edit cannot mutate a live strategy dependency.

## Verdict

KEEP + HARDEN current V1 data and evidence contracts. DEFER non-OHLCV product support to v2-external-data-domains.
