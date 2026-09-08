# Adversarial failure hypotheses

Read the relevant section below. The content was split for bounded reading on 6 September 2026; technical decisions and historical evidence were not re-approved by this refactor. Earlier status, commands and permission wording apply only to their original scope.

| Section | Words |
| --- | ---: |
| [Adversarial failure hypotheses](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md) | 1512 |
| [KPV5-B-004 — P0/P1 resource isolation is not implemented](10-adversarial-failure-hypotheses-sections/02-kpv5-b-004--p0p1-resource-isolation-is-not-implemented.md) | 1401 |

## Existing section links

These anchors preserve incoming links. Follow the section link to read its content.

<a id="adversarial-failure-hypotheses"></a>

[Adversarial failure hypotheses](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#adversarial-failure-hypotheses)

<a id="central-finding-register"></a>

[Central finding register](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#central-finding-register)

<a id="kpv5-a-001--experiment-specification-identity-collision"></a>

[KPV5-A-001 — experiment specification identity collision](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#kpv5-a-001--experiment-specification-identity-collision)

<a id="kpv5-a-002--qualification-consumes-later-oos-rows"></a>

[KPV5-A-002 — qualification consumes later OOS rows](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#kpv5-a-002--qualification-consumes-later-oos-rows)

<a id="kpv5-a-003--legacy-sweep-remains-reachable-in-v0"></a>

[KPV5-A-003 — legacy sweep remains reachable in V0](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#kpv5-a-003--legacy-sweep-remains-reachable-in-v0)

<a id="kpv5-a-004--completed-observations-permit-impossible-availability-ordering"></a>

[KPV5-A-004 — completed observations permit impossible availability ordering](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#kpv5-a-004--completed-observations-permit-impossible-availability-ordering)

<a id="kpv5-a-005--iid-trade-bootstrap-assumption-is-unstated"></a>

[KPV5-A-005 — IID trade bootstrap assumption is unstated](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#kpv5-a-005--iid-trade-bootstrap-assumption-is-unstated)

<a id="kpv5-a-006--correction-lineage-is-absent-from-the-general-projection"></a>

[KPV5-A-006 — correction lineage is absent from the general projection](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#kpv5-a-006--correction-lineage-is-absent-from-the-general-projection)

<a id="kpv5-a-007--optimization-reconstruction-is-under-proved"></a>

[KPV5-A-007 — optimization reconstruction is under-proved](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#kpv5-a-007--optimization-reconstruction-is-under-proved)

<a id="kpv5-b-001--published-graph-execution-omits-resourceplan"></a>

[KPV5-B-001 — published graph execution omits ResourcePlan](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#kpv5-b-001--published-graph-execution-omits-resourceplan)

<a id="kpv5-b-002--terminal-order-conflict-mislabels-a-complete-fill"></a>

[KPV5-B-002 — terminal order conflict mislabels a complete fill](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#kpv5-b-002--terminal-order-conflict-mislabels-a-complete-fill)

<a id="kpv5-b-003--current-claim-race-validation-times-out-postgresql-evidence-is-unavailable"></a>

[KPV5-B-003 — current claim-race validation times out; PostgreSQL evidence is unavailable](10-adversarial-failure-hypotheses-sections/01-adversarial-failure-hypotheses.md#kpv5-b-003--current-claim-race-validation-times-out-postgresql-evidence-is-unavailable)

<a id="kpv5-b-004--p0p1-resource-isolation-is-not-implemented"></a>

[KPV5-B-004 — P0/P1 resource isolation is not implemented](10-adversarial-failure-hypotheses-sections/02-kpv5-b-004--p0p1-resource-isolation-is-not-implemented.md#kpv5-b-004--p0p1-resource-isolation-is-not-implemented)

<a id="kpv5-b-005--active-websocket-session-revocation-is-unspecified"></a>

[KPV5-B-005 — active WebSocket session revocation is unspecified](10-adversarial-failure-hypotheses-sections/02-kpv5-b-004--p0p1-resource-isolation-is-not-implemented.md#kpv5-b-005--active-websocket-session-revocation-is-unspecified)

<a id="kpv5-b-006--deterministic-capital-admission-is-not-runtime-authority"></a>

[KPV5-B-006 — deterministic capital admission is not runtime authority](10-adversarial-failure-hypotheses-sections/02-kpv5-b-004--p0p1-resource-isolation-is-not-implemented.md#kpv5-b-006--deterministic-capital-admission-is-not-runtime-authority)

<a id="answers-to-the-48-adversarial-questions"></a>

[Answers to the 48 adversarial questions](10-adversarial-failure-hypotheses-sections/02-kpv5-b-004--p0p1-resource-isolation-is-not-implemented.md#answers-to-the-48-adversarial-questions)

<a id="time-and-market-truth-1-8"></a>

[Time and market truth (1-8)](10-adversarial-failure-hypotheses-sections/02-kpv5-b-004--p0p1-resource-isolation-is-not-implemented.md#time-and-market-truth-1-8)

<a id="identity-and-provenance-9-16"></a>

[Identity and provenance (9-16)](10-adversarial-failure-hypotheses-sections/02-kpv5-b-004--p0p1-resource-isolation-is-not-implemented.md#identity-and-provenance-9-16)

<a id="transactions-concurrency-money-17-25"></a>

[Transactions, concurrency, money (17-25)](10-adversarial-failure-hypotheses-sections/02-kpv5-b-004--p0p1-resource-isolation-is-not-implemented.md#transactions-concurrency-money-17-25)

<a id="jobs-and-runtime-26-34"></a>

[Jobs and runtime (26-34)](10-adversarial-failure-hypotheses-sections/02-kpv5-b-004--p0p1-resource-isolation-is-not-implemented.md#jobs-and-runtime-26-34)

<a id="security-tenancy-future-seams-35-48"></a>

[Security, tenancy, future seams (35-48)](10-adversarial-failure-hypotheses-sections/02-kpv5-b-004--p0p1-resource-isolation-is-not-implemented.md#security-tenancy-future-seams-35-48)
