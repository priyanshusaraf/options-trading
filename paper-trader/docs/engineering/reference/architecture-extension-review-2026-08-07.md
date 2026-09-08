# Architecture extension review — 2026-08-07

Read the relevant section below. The content was split for bounded reading on 6 September 2026; technical decisions and historical evidence were not re-approved by this refactor. Earlier status, commands and permission wording apply only to their original scope.

| Section | Words |
| --- | ---: |
| [Architecture extension review — 2026-08-07](architecture-extension-review-2026-08-07-sections/01-architecture-extension-review--2026-08-07.md) | 1041 |
| [B. Capability compatibility matrix](architecture-extension-review-2026-08-07-sections/02-b-capability-compatibility-matrix.md) | 802 |
| [C. Extension-drill results](architecture-extension-review-2026-08-07-sections/03-c-extension-drill-results.md) | 1596 |
| [Drill 5 — a stateful predicate ("condition has remained true for 10 observations")](architecture-extension-review-2026-08-07-sections/04-drill-5--a-stateful-predicate-condition-has-remained-true-for-10-obser.md) | 1507 |
| [G-4 — `runtime.evaluate` is domain-blind.](architecture-extension-review-2026-08-07-sections/05-g-4--runtimeevaluate-is-domain-blind.md) | 1193 |
| [F. Scaling assessment — roughly 100 serious users](architecture-extension-review-2026-08-07-sections/06-f-scaling-assessment--roughly-100-serious-users.md) | 847 |
| [Appendix — files inspected](architecture-extension-review-2026-08-07-sections/07-appendix--files-inspected.md) | 114 |

## Existing section links

These anchors preserve incoming links. Follow the section link to read its content.

<a id="architecture-extension-review--2026-08-07"></a>

[Architecture extension review — 2026-08-07](architecture-extension-review-2026-08-07-sections/01-architecture-extension-review--2026-08-07.md#architecture-extension-review--2026-08-07)

<a id="amendments--2026-08-07-after-owner-review"></a>

[Amendments — 2026-08-07, after owner review](architecture-extension-review-2026-08-07-sections/01-architecture-extension-review--2026-08-07.md#amendments--2026-08-07-after-owner-review)

<a id="a-current-architecture-map"></a>

[A. Current architecture map](architecture-extension-review-2026-08-07-sections/01-architecture-extension-review--2026-08-07.md#a-current-architecture-map)

<a id="b-capability-compatibility-matrix"></a>

[B. Capability compatibility matrix](architecture-extension-review-2026-08-07-sections/02-b-capability-compatibility-matrix.md#b-capability-compatibility-matrix)

<a id="c-extension-drill-results"></a>

[C. Extension-drill results](architecture-extension-review-2026-08-07-sections/03-c-extension-drill-results.md#c-extension-drill-results)

<a id="drill-1--add-one-ordinary-new-indicator-depthweightedmidprice"></a>

[Drill 1 — add one ordinary new indicator (`DepthWeightedMidPrice`)](architecture-extension-review-2026-08-07-sections/03-c-extension-drill-results.md#drill-1--add-one-ordinary-new-indicator-depthweightedmidprice)

<a id="drill-2--observe-nifty-execute-sensex"></a>

[Drill 2 — observe NIFTY, execute SENSEX](architecture-extension-review-2026-08-07-sections/03-c-extension-drill-results.md#drill-2--observe-nifty-execute-sensex)

<a id="drill-3--produce-a-two-leg-option-spread"></a>

[Drill 3 — produce a two-leg option spread](architecture-extension-review-2026-08-07-sections/03-c-extension-drill-results.md#drill-3--produce-a-two-leg-option-spread)

<a id="drill-4--package-a-subgraph-as-a-reusable-component"></a>

[Drill 4 — package a subgraph as a reusable component](architecture-extension-review-2026-08-07-sections/03-c-extension-drill-results.md#drill-4--package-a-subgraph-as-a-reusable-component)

<a id="drill-5--a-stateful-predicate-condition-has-remained-true-for-10-observations"></a>

[Drill 5 — a stateful predicate ("condition has remained true for 10 observations")](architecture-extension-review-2026-08-07-sections/04-drill-5--a-stateful-predicate-condition-has-remained-true-for-10-obser.md#drill-5--a-stateful-predicate-condition-has-remained-true-for-10-observations)

<a id="d-architecture-gap-register"></a>

[D. Architecture gap register](architecture-extension-review-2026-08-07-sections/04-drill-5--a-stateful-predicate-condition-has-remained-true-for-10-obser.md#d-architecture-gap-register)

<a id="g-1--there-is-no-platform-component-library-one-strategys-library-is-standing-in-for-one"></a>

[G-1 — There is no platform component library. One strategy's library is standing in for one.](architecture-extension-review-2026-08-07-sections/04-drill-5--a-stateful-predicate-condition-has-remained-true-for-10-obser.md#g-1--there-is-no-platform-component-library-one-strategys-library-is-standing-in-for-one)

<a id="g-2--the-signal--intent--order-boundary-is-real-but-unnamed"></a>

[G-2 — The signal → intent → order boundary is real but unnamed.](architecture-extension-review-2026-08-07-sections/04-drill-5--a-stateful-predicate-condition-has-remained-true-for-10-obser.md#g-2--the-signal--intent--order-boundary-is-real-but-unnamed)

<a id="g-3--backtests-are-a-process-global-singleton"></a>

[G-3 — Backtests are a process-global singleton.](architecture-extension-review-2026-08-07-sections/04-drill-5--a-stateful-predicate-condition-has-remained-true-for-10-obser.md#g-3--backtests-are-a-process-global-singleton)

<a id="g-8--stateful-nodes-are-supported-is-true-only-of-data-derived-state"></a>

[G-8 — "Stateful nodes are supported" is true only of data-derived state.](architecture-extension-review-2026-08-07-sections/04-drill-5--a-stateful-predicate-condition-has-remained-true-for-10-obser.md#g-8--stateful-nodes-are-supported-is-true-only-of-data-derived-state)

<a id="g-4--runtimeevaluate-is-domain-blind"></a>

[G-4 — `runtime.evaluate` is domain-blind.](architecture-extension-review-2026-08-07-sections/05-g-4--runtimeevaluate-is-domain-blind.md#g-4--runtimeevaluate-is-domain-blind)

<a id="g-5--graph_artifactsidentifier-is-a-global-primary-key"></a>

[G-5 — `graph_artifacts.identifier` is a global primary key.](architecture-extension-review-2026-08-07-sections/05-g-4--runtimeevaluate-is-domain-blind.md#g-5--graph_artifactsidentifier-is-a-global-primary-key)

<a id="g-6--narrower-config-scopes-can-widen-a-safety-limit"></a>

[G-6 — Narrower config scopes can widen a safety limit.](architecture-extension-review-2026-08-07-sections/05-g-4--runtimeevaluate-is-domain-blind.md#g-6--narrower-config-scopes-can-widen-a-safety-limit)

<a id="g-7--the-strategy-language-cannot-see-market-data-the-platform-already-has"></a>

[G-7 — The strategy language cannot see market data the platform already has.](architecture-extension-review-2026-08-07-sections/05-g-4--runtimeevaluate-is-domain-blind.md#g-7--the-strategy-language-cannot-see-market-data-the-platform-already-has)

<a id="e-reuse-matrix"></a>

[E. Reuse matrix](architecture-extension-review-2026-08-07-sections/05-g-4--runtimeevaluate-is-domain-blind.md#e-reuse-matrix)

<a id="f-scaling-assessment--roughly-100-serious-users"></a>

[F. Scaling assessment — roughly 100 serious users](architecture-extension-review-2026-08-07-sections/06-f-scaling-assessment--roughly-100-serious-users.md#f-scaling-assessment--roughly-100-serious-users)

<a id="g-recommended-sequence"></a>

[G. Recommended sequence](architecture-extension-review-2026-08-07-sections/06-f-scaling-assessment--roughly-100-serious-users.md#g-recommended-sequence)

<a id="closure--2026-08-07"></a>

[Closure — 2026-08-07](architecture-extension-review-2026-08-07-sections/06-f-scaling-assessment--roughly-100-serious-users.md#closure--2026-08-07)

<a id="appendix--files-inspected"></a>

[Appendix — files inspected](architecture-extension-review-2026-08-07-sections/07-appendix--files-inspected.md#appendix--files-inspected)
