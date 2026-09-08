# ADR 0011: Staged adoption of the Component IR runtime in the live path

Read the relevant section below. The content was split for bounded reading on 6 September 2026; technical decisions and historical evidence were not re-approved by this refactor. Earlier status, commands and permission wording apply only to their original scope.

| Section | Words |
| --- | ---: |
| [ADR 0011: Staged adoption of the Component IR runtime in the live path](0011-l1-ir-runtime-adoption-sections/01-adr-0011-staged-adoption-of-the-component-ir-runtime-in-the-live-path.md) | 878 |
| [4. What the current parity evidence is actually worth](0011-l1-ir-runtime-adoption-sections/02-4-what-the-current-parity-evidence-is-actually-worth.md) | 1522 |
| [Stage 3 — live adoption **(OWNER-GATED, one instrument, reversible in one command)**](0011-l1-ir-runtime-adoption-sections/03-stage-3--live-adoption-owner-gated-one-instrument-reversible-in-one-co.md) | 701 |

## Existing section links

These anchors preserve incoming links. Follow the section link to read its content.

<a id="adr-0011-staged-adoption-of-the-component-ir-runtime-in-the-live-path"></a>

[ADR 0011: Staged adoption of the Component IR runtime in the live path](0011-l1-ir-runtime-adoption-sections/01-adr-0011-staged-adoption-of-the-component-ir-runtime-in-the-live-path.md#adr-0011-staged-adoption-of-the-component-ir-runtime-in-the-live-path)

<a id="1-why-this-is-not-a-small-change"></a>

[1. Why this is not a small change](0011-l1-ir-runtime-adoption-sections/01-adr-0011-staged-adoption-of-the-component-ir-runtime-in-the-live-path.md#1-why-this-is-not-a-small-change)

<a id="2-what-the-live-path-actually-is"></a>

[2. What the live path actually is](0011-l1-ir-runtime-adoption-sections/01-adr-0011-staged-adoption-of-the-component-ir-runtime-in-the-live-path.md#2-what-the-live-path-actually-is)

<a id="3-every-place-the-live-path-bypasses-or-conflicts-with-strategy-os"></a>

[3. Every place the live path bypasses or conflicts with Strategy OS](0011-l1-ir-runtime-adoption-sections/01-adr-0011-staged-adoption-of-the-component-ir-runtime-in-the-live-path.md#3-every-place-the-live-path-bypasses-or-conflicts-with-strategy-os)

<a id="4-what-the-current-parity-evidence-is-actually-worth"></a>

[4. What the current parity evidence is actually worth](0011-l1-ir-runtime-adoption-sections/02-4-what-the-current-parity-evidence-is-actually-worth.md#4-what-the-current-parity-evidence-is-actually-worth)

<a id="4a-a-correction-this-adr-must-carry-the-cache-is-not-an-optimisation"></a>

[4a. A correction this ADR must carry: the cache is not an optimisation](0011-l1-ir-runtime-adoption-sections/02-4-what-the-current-parity-evidence-is-actually-worth.md#4a-a-correction-this-adr-must-carry-the-cache-is-not-an-optimisation)

<a id="5-the-staged-sequence"></a>

[5. The staged sequence](0011-l1-ir-runtime-adoption-sections/02-4-what-the-current-parity-evidence-is-actually-worth.md#5-the-staged-sequence)

<a id="stage-0--make-the-adapter-production-grade-and-honestly-tested-no-live-effect"></a>

[Stage 0 — make the adapter production-grade and honestly tested (no live effect)](0011-l1-ir-runtime-adoption-sections/02-4-what-the-current-parity-evidence-is-actually-worth.md#stage-0--make-the-adapter-production-grade-and-honestly-tested-no-live-effect)

<a id="stage-1-acceptance-criteria-quantitative-and-structural"></a>

[Stage 1 acceptance criteria (quantitative and structural)](0011-l1-ir-runtime-adoption-sections/02-4-what-the-current-parity-evidence-is-actually-worth.md#stage-1-acceptance-criteria-quantitative-and-structural)

<a id="stage-1--shadow-lane-computed-but-never-acted-on-no-live-effect"></a>

[Stage 1 — shadow lane, computed but never acted on (no live effect)](0011-l1-ir-runtime-adoption-sections/02-4-what-the-current-parity-evidence-is-actually-worth.md#stage-1--shadow-lane-computed-but-never-acted-on-no-live-effect)

<a id="stage-2--paper-mode-adoption-no-real-money"></a>

[Stage 2 — paper-mode adoption (no real money)](0011-l1-ir-runtime-adoption-sections/02-4-what-the-current-parity-evidence-is-actually-worth.md#stage-2--paper-mode-adoption-no-real-money)

<a id="stage-3--live-adoption-owner-gated-one-instrument-reversible-in-one-command"></a>

[Stage 3 — live adoption **(OWNER-GATED, one instrument, reversible in one command)**](0011-l1-ir-runtime-adoption-sections/03-stage-3--live-adoption-owner-gated-one-instrument-reversible-in-one-co.md#stage-3--live-adoption-owner-gated-one-instrument-reversible-in-one-command)

<a id="6-what-stays-authoritative-at-each-stage"></a>

[6. What stays authoritative at each stage](0011-l1-ir-runtime-adoption-sections/03-stage-3--live-adoption-owner-gated-one-instrument-reversible-in-one-co.md#6-what-stays-authoritative-at-each-stage)

<a id="7-non-vacuous-safety-proofs-required"></a>

[7. Non-vacuous safety proofs required](0011-l1-ir-runtime-adoption-sections/03-stage-3--live-adoption-owner-gated-one-instrument-reversible-in-one-co.md#7-non-vacuous-safety-proofs-required)

<a id="8-honest-scope-and-risk"></a>

[8. Honest scope and risk](0011-l1-ir-runtime-adoption-sections/03-stage-3--live-adoption-owner-gated-one-instrument-reversible-in-one-co.md#8-honest-scope-and-risk)

<a id="9-boundary"></a>

[9. Boundary](0011-l1-ir-runtime-adoption-sections/03-stage-3--live-adoption-owner-gated-one-instrument-reversible-in-one-co.md#9-boundary)
