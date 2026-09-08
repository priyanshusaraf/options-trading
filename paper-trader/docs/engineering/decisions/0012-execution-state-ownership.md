# ADR 0012: Execution-state ownership across graphs, evidence, candidates and deployments

Read the relevant section below. The content was split for bounded reading on 6 September 2026; technical decisions and historical evidence were not re-approved by this refactor. Earlier status, commands and permission wording apply only to their original scope.

| Section | Words |
| --- | ---: |
| [ADR 0012: Execution-state ownership across graphs, evidence, candidates and deployments](0012-execution-state-ownership-sections/01-adr-0012-execution-state-ownership-across-graphs-evidence-candidates-a.md) | 1585 |
| [2.4 The registry of mechanisms](0012-execution-state-ownership-sections/02-24-the-registry-of-mechanisms.md) | 802 |
| [4. What this ADR does not change](0012-execution-state-ownership-sections/03-4-what-this-adr-does-not-change.md) | 816 |
| [5. Owner gates](0012-execution-state-ownership-sections/04-5-owner-gates.md) | 843 |
| [7. L1.3C — IR paper authority](0012-execution-state-ownership-sections/05-7-l13c--ir-paper-authority.md) | 889 |

## Existing section links

These anchors preserve incoming links. Follow the section link to read its content.

<a id="adr-0012-execution-state-ownership-across-graphs-evidence-candidates-and-deployments"></a>

[ADR 0012: Execution-state ownership across graphs, evidence, candidates and deployments](0012-execution-state-ownership-sections/01-adr-0012-execution-state-ownership-across-graphs-evidence-candidates-a.md#adr-0012-execution-state-ownership-across-graphs-evidence-candidates-and-deployments)

<a id="1-the-problem-stated-as-it-actually-is"></a>

[1. The problem, stated as it actually is](0012-execution-state-ownership-sections/01-adr-0012-execution-state-ownership-across-graphs-evidence-candidates-a.md#1-the-problem-stated-as-it-actually-is)

<a id="2-decision"></a>

[2. Decision](0012-execution-state-ownership-sections/01-adr-0012-execution-state-ownership-across-graphs-evidence-candidates-a.md#2-decision)

<a id="20-the-wiring-and-why-the-contract-had-to-be-split-in-two"></a>

[2.0 The wiring, and why the contract had to be split in two](0012-execution-state-ownership-sections/01-adr-0012-execution-state-ownership-across-graphs-evidence-candidates-a.md#20-the-wiring-and-why-the-contract-had-to-be-split-in-two)

<a id="20b-two-paths-that-must-not-converge-and-one-that-must"></a>

[2.0b Two paths that must not converge, and one that must](0012-execution-state-ownership-sections/01-adr-0012-execution-state-ownership-across-graphs-evidence-candidates-a.md#20b-two-paths-that-must-not-converge-and-one-that-must)

<a id="20c-rfc-0001-c13-and-why-this-does-not-violate-it"></a>

[2.0c RFC 0001 C13, and why this does not violate it](0012-execution-state-ownership-sections/01-adr-0012-execution-state-ownership-across-graphs-evidence-candidates-a.md#20c-rfc-0001-c13-and-why-this-does-not-violate-it)

<a id="21-ownership--who-owns-which-fact"></a>

[2.1 Ownership — who owns which fact](0012-execution-state-ownership-sections/01-adr-0012-execution-state-ownership-across-graphs-evidence-candidates-a.md#21-ownership--who-owns-which-fact)

<a id="22-the-authority-gate"></a>

[2.2 The authority gate](0012-execution-state-ownership-sections/01-adr-0012-execution-state-ownership-across-graphs-evidence-candidates-a.md#22-the-authority-gate)

<a id="23-failure-posture-which-differs-by-layer-on-purpose"></a>

[2.3 Failure posture, which differs by layer on purpose](0012-execution-state-ownership-sections/01-adr-0012-execution-state-ownership-across-graphs-evidence-candidates-a.md#23-failure-posture-which-differs-by-layer-on-purpose)

<a id="24-the-registry-of-mechanisms"></a>

[2.4 The registry of mechanisms](0012-execution-state-ownership-sections/02-24-the-registry-of-mechanisms.md#24-the-registry-of-mechanisms)

<a id="3-the-smallest-safe-papershadow-deployment-architecture"></a>

[3. The smallest safe paper/shadow deployment architecture](0012-execution-state-ownership-sections/02-24-the-registry-of-mechanisms.md#3-the-smallest-safe-papershadow-deployment-architecture)

<a id="31a-why-l13a-did-not-overload-deploymentsstrategy_key"></a>

[3.1a Why L1.3A did not overload `deployments.strategy_key`](0012-execution-state-ownership-sections/02-24-the-registry-of-mechanisms.md#31a-why-l13a-did-not-overload-deploymentsstrategy_key)

<a id="31b-what-l13a-verifies-and-when"></a>

[3.1b What L1.3A verifies, and when](0012-execution-state-ownership-sections/02-24-the-registry-of-mechanisms.md#31b-what-l13a-verifies-and-when)

<a id="4-what-this-adr-does-not-change"></a>

[4. What this ADR does not change](0012-execution-state-ownership-sections/03-4-what-this-adr-does-not-change.md#4-what-this-adr-does-not-change)

<a id="41-execution-attribution--found-here-closed-in-the-next-slice"></a>

[4.1 Execution attribution — found here, closed in the next slice](0012-execution-state-ownership-sections/03-4-what-this-adr-does-not-change.md#41-execution-attribution--found-here-closed-in-the-next-slice)

<a id="41a-a-shared-state-leak-the-slice-uncovered"></a>

[4.1a A shared-state leak the slice uncovered](0012-execution-state-ownership-sections/03-4-what-this-adr-does-not-change.md#41a-a-shared-state-leak-the-slice-uncovered)

<a id="41b-historical-rows-measured-not-assumed"></a>

[4.1b Historical rows: measured, not assumed](0012-execution-state-ownership-sections/03-4-what-this-adr-does-not-change.md#41b-historical-rows-measured-not-assumed)

<a id="42-remaining-unconsumed-mechanisms"></a>

[4.2 Remaining unconsumed mechanisms](0012-execution-state-ownership-sections/03-4-what-this-adr-does-not-change.md#42-remaining-unconsumed-mechanisms)

<a id="5-owner-gates"></a>

[5. Owner gates](0012-execution-state-ownership-sections/04-5-owner-gates.md#5-owner-gates)

<a id="6-l13b--the-execution-book"></a>

[6. L1.3B — the execution book](0012-execution-state-ownership-sections/04-5-owner-gates.md#6-l13b--the-execution-book)

<a id="61-the-inventory-before-any-semantics-changed"></a>

[6.1 The inventory, before any semantics changed](0012-execution-state-ownership-sections/04-5-owner-gates.md#61-the-inventory-before-any-semantics-changed)

<a id="62-is-mode-sufficient"></a>

[6.2 Is `mode` sufficient?](0012-execution-state-ownership-sections/04-5-owner-gates.md#62-is-mode-sufficient)

<a id="63-final-semantics-per-query"></a>

[6.3 Final semantics per query](0012-execution-state-ownership-sections/04-5-owner-gates.md#63-final-semantics-per-query)

<a id="64-the-one-tension-resolved-deliberately"></a>

[6.4 The one tension, resolved deliberately](0012-execution-state-ownership-sections/04-5-owner-gates.md#64-the-one-tension-resolved-deliberately)

<a id="65-authority-is-now-a-source-mode-pair"></a>

[6.5 Authority is now a (source, mode) pair](0012-execution-state-ownership-sections/04-5-owner-gates.md#65-authority-is-now-a-source-mode-pair)

<a id="7-l13c--ir-paper-authority"></a>

[7. L1.3C — IR paper authority](0012-execution-state-ownership-sections/05-7-l13c--ir-paper-authority.md#7-l13c--ir-paper-authority)

<a id="71-the-grant-and-what-makes-it-safe-to-make"></a>

[7.1 The grant, and what makes it safe to make](0012-execution-state-ownership-sections/05-7-l13c--ir-paper-authority.md#71-the-grant-and-what-makes-it-safe-to-make)

<a id="72-the-grant-is-necessary-and-deliberately-not-sufficient"></a>

[7.2 The grant is necessary and deliberately not sufficient](0012-execution-state-ownership-sections/05-7-l13c--ir-paper-authority.md#72-the-grant-is-necessary-and-deliberately-not-sufficient)

<a id="73-where-authority-lives-and-why-it-is-a-third-table"></a>

[7.3 Where authority lives, and why it is a third table](0012-execution-state-ownership-sections/05-7-l13c--ir-paper-authority.md#73-where-authority-lives-and-why-it-is-a-third-table)

<a id="74-exact-version-semantics"></a>

[7.4 Exact-version semantics](0012-execution-state-ownership-sections/05-7-l13c--ir-paper-authority.md#74-exact-version-semantics)

<a id="75-rollback"></a>

[7.5 Rollback](0012-execution-state-ownership-sections/05-7-l13c--ir-paper-authority.md#75-rollback)

<a id="76-two-defects-this-slice-found"></a>

[7.6 Two defects this slice found](0012-execution-state-ownership-sections/05-7-l13c--ir-paper-authority.md#76-two-defects-this-slice-found)

<a id="77-what-remains-before-live-authority-can-even-be-designed"></a>

[7.7 What remains before live authority can even be designed](0012-execution-state-ownership-sections/05-7-l13c--ir-paper-authority.md#77-what-remains-before-live-authority-can-even-be-designed)
