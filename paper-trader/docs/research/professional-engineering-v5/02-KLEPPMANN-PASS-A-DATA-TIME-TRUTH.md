# Kleppmann Pass A: data, time, identity, transactions, and derived state

Read the relevant section below. The content was split for bounded reading on 6 September 2026; technical decisions and historical evidence were not re-approved by this refactor. Earlier status, commands and permission wording apply only to their original scope.

| Section | Words |
| --- | ---: |
| [Kleppmann Pass A: data, time, identity, transactions, and derived state](02-kleppmann-pass-a-data-time-truth-sections/01-kleppmann-pass-a-data-time-identity-transactions-and-derived-state.md) | 887 |
| [Current authority and identity reconstruction](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md) | 1484 |
| [Research-method matrix](02-kleppmann-pass-a-data-time-truth-sections/03-research-method-matrix.md) | 397 |

## Existing section links

These anchors preserve incoming links. Follow the section link to read its content.

<a id="kleppmann-pass-a-data-time-identity-transactions-and-derived-state"></a>

[Kleppmann Pass A: data, time, identity, transactions, and derived state](02-kleppmann-pass-a-data-time-truth-sections/01-kleppmann-pass-a-data-time-identity-transactions-and-derived-state.md#kleppmann-pass-a-data-time-identity-transactions-and-derived-state)

<a id="decision"></a>

[Decision](02-kleppmann-pass-a-data-time-truth-sections/01-kleppmann-pass-a-data-time-identity-transactions-and-derived-state.md#decision)

<a id="transferable-source-principles"></a>

[Transferable source principles](02-kleppmann-pass-a-data-time-truth-sections/01-kleppmann-pass-a-data-time-identity-transactions-and-derived-state.md#transferable-source-principles)

<a id="source-of-record-and-derived-state"></a>

[Source of record and derived state](02-kleppmann-pass-a-data-time-truth-sections/01-kleppmann-pass-a-data-time-identity-transactions-and-derived-state.md#source-of-record-and-derived-state)

<a id="stable-identity"></a>

[Stable identity](02-kleppmann-pass-a-data-time-truth-sections/01-kleppmann-pass-a-data-time-identity-transactions-and-derived-state.md#stable-identity)

<a id="explicit-inputs-and-caches"></a>

[Explicit inputs and caches](02-kleppmann-pass-a-data-time-truth-sections/01-kleppmann-pass-a-data-time-identity-transactions-and-derived-state.md#explicit-inputs-and-caches)

<a id="time-domains"></a>

[Time domains](02-kleppmann-pass-a-data-time-truth-sections/01-kleppmann-pass-a-data-time-identity-transactions-and-derived-state.md#time-domains)

<a id="transactions-and-named-guarantees"></a>

[Transactions and named guarantees](02-kleppmann-pass-a-data-time-truth-sections/01-kleppmann-pass-a-data-time-identity-transactions-and-derived-state.md#transactions-and-named-guarantees)

<a id="formal-verification"></a>

[Formal verification](02-kleppmann-pass-a-data-time-truth-sections/01-kleppmann-pass-a-data-time-identity-transactions-and-derived-state.md#formal-verification)

<a id="actual-evaluation-timeline"></a>

[Actual evaluation timeline](02-kleppmann-pass-a-data-time-truth-sections/01-kleppmann-pass-a-data-time-identity-transactions-and-derived-state.md#actual-evaluation-timeline)

<a id="current-authority-and-identity-reconstruction"></a>

[Current authority and identity reconstruction](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#current-authority-and-identity-reconstruction)

<a id="market-truth-and-instruments"></a>

[Market truth and instruments](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#market-truth-and-instruments)

<a id="observations-and-causal-alignment"></a>

[Observations and causal alignment](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#observations-and-causal-alignment)

<a id="dataset-and-q03-canonical-research-binding"></a>

[Dataset and Q03 canonical research binding](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#dataset-and-q03-canonical-research-binding)

<a id="graph-identity-and-causal-parity"></a>

[Graph identity and causal parity](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#graph-identity-and-causal-parity)

<a id="backtest-and-research-result-identity"></a>

[Backtest and research result identity](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#backtest-and-research-result-identity)

<a id="direct-findings"></a>

[Direct findings](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#direct-findings)

<a id="kpv5-a-001-truncated-experiment-spec-collision-silently-reuses-another-recipe"></a>

[KPV5-A-001: truncated experiment-spec collision silently reuses another recipe](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#kpv5-a-001-truncated-experiment-spec-collision-silently-reuses-another-recipe)

<a id="kpv5-a-002-full-history-qualification-contaminates-later-oos-evidence"></a>

[KPV5-A-002: full-history qualification contaminates later OOS evidence](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#kpv5-a-002-full-history-qualification-contaminates-later-oos-evidence)

<a id="kpv5-a-003-v0-permits-the-legacy-current-universe-sweep-route"></a>

[KPV5-A-003: V0 permits the legacy current-universe sweep route](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#kpv5-a-003-v0-permits-the-legacy-current-universe-sweep-route)

<a id="kpv5-a-004-completed-observation-authority-permits-availability-before-completion"></a>

[KPV5-A-004: completed-observation authority permits availability before completion](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#kpv5-a-004-completed-observation-authority-permits-availability-before-completion)

<a id="kpv5-a-005-iid-trade-bootstrap-lacks-a-dependency-assumption"></a>

[KPV5-A-005: IID trade bootstrap lacks a dependency assumption](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#kpv5-a-005-iid-trade-bootstrap-lacks-a-dependency-assumption)

<a id="kpv5-a-006-revision-aware-general-alignment-remains-undefined"></a>

[KPV5-A-006: revision-aware general alignment remains undefined](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#kpv5-a-006-revision-aware-general-alignment-remains-undefined)

<a id="kpv5-a-007-optimization-search-reconstruction-is-under-proven"></a>

[KPV5-A-007: optimization search reconstruction is under-proven](02-kleppmann-pass-a-data-time-truth-sections/02-current-authority-and-identity-reconstruction.md#kpv5-a-007-optimization-search-reconstruction-is-under-proven)

<a id="research-method-matrix"></a>

[Research-method matrix](02-kleppmann-pass-a-data-time-truth-sections/03-research-method-matrix.md#research-method-matrix)

<a id="rejected-responses"></a>

[Rejected responses](02-kleppmann-pass-a-data-time-truth-sections/03-research-method-matrix.md#rejected-responses)

<a id="evidence-and-limits"></a>

[Evidence and limits](02-kleppmann-pass-a-data-time-truth-sections/03-research-method-matrix.md#evidence-and-limits)
