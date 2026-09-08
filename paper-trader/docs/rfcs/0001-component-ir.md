# RFC 0001 — The Component IR

Read the relevant section below. The content was split for bounded reading on 6 September 2026; technical decisions and historical evidence were not re-approved by this refactor. Earlier status, commands and permission wording apply only to their original scope.

| Section | Words |
| --- | ---: |
| [RFC 0001 — The Component IR](0001-component-ir-sections/01-rfc-0001--the-component-ir.md) | 937 |
| [1. Scope, principle, and planes](0001-component-ir-sections/02-1-scope-principle-and-planes.md) | 1537 |
| [Continuation 3](0001-component-ir-sections/03-continuation-3.md) | 893 |
| [4. Contract clauses (normative — free to add)](0001-component-ir-sections/04-4-contract-clauses-normative--free-to-add.md) | 1004 |
| [5. Non-goals](0001-component-ir-sections/05-5-non-goals.md) | 1507 |
| [A.4 A nested subgraph](0001-component-ir-sections/06-a4-a-nested-subgraph.md) | 885 |
| [Appendix C — Open questions carried forward (informative)](0001-component-ir-sections/07-appendix-c--open-questions-carried-forward-informative.md) | 325 |

## Existing section links

These anchors preserve incoming links. Follow the section link to read its content.

<a id="rfc-0001--the-component-ir"></a>

[RFC 0001 — The Component IR](0001-component-ir-sections/01-rfc-0001--the-component-ir.md#rfc-0001--the-component-ir)

<a id="preface-informative"></a>

[Preface (informative)](0001-component-ir-sections/01-rfc-0001--the-component-ir.md#preface-informative)

<a id="why-the-component-ir-exists"></a>

[Why the Component IR exists](0001-component-ir-sections/01-rfc-0001--the-component-ir.md#why-the-component-ir-exists)

<a id="why-we-are-introducing-a-language"></a>

[Why we are introducing a language](0001-component-ir-sections/01-rfc-0001--the-component-ir.md#why-we-are-introducing-a-language)

<a id="why-every-subsystem-speaks-it"></a>

[Why every subsystem speaks it](0001-component-ir-sections/01-rfc-0001--the-component-ir.md#why-every-subsystem-speaks-it)

<a id="why-this-document-distinguishes-format-clauses-from-contract-clauses"></a>

[Why this document distinguishes Format clauses from Contract clauses](0001-component-ir-sections/01-rfc-0001--the-component-ir.md#why-this-document-distinguishes-format-clauses-from-contract-clauses)

<a id="1-scope-principle-and-planes"></a>

[1. Scope, principle, and planes](0001-component-ir-sections/02-1-scope-principle-and-planes.md#1-scope-principle-and-planes)

<a id="11-the-central-principle"></a>

[1.1 The central principle](0001-component-ir-sections/02-1-scope-principle-and-planes.md#11-the-central-principle)

<a id="12-the-five-planes"></a>

[1.2 The five planes](0001-component-ir-sections/02-1-scope-principle-and-planes.md#12-the-five-planes)

<a id="13-specification--resolution--execution"></a>

[1.3 Specification → Resolution → Execution](0001-component-ir-sections/02-1-scope-principle-and-planes.md#13-specification--resolution--execution)

<a id="14-what-this-rfc-does-not-cover"></a>

[1.4 What this RFC does not cover](0001-component-ir-sections/02-1-scope-principle-and-planes.md#14-what-this-rfc-does-not-cover)

<a id="2-terminology-and-conformance"></a>

[2. Terminology and conformance](0001-component-ir-sections/02-1-scope-principle-and-planes.md#2-terminology-and-conformance)

<a id="21-conformance-language"></a>

[2.1 Conformance language](0001-component-ir-sections/02-1-scope-principle-and-planes.md#21-conformance-language)

<a id="22-terms"></a>

[2.2 Terms](0001-component-ir-sections/02-1-scope-principle-and-planes.md#22-terms)

<a id="3-format-clauses-normative--every-clause-here-is-migrated-forever"></a>

[3. Format clauses (normative — every clause here is migrated forever)](0001-component-ir-sections/02-1-scope-principle-and-planes.md#3-format-clauses-normative--every-clause-here-is-migrated-forever)

<a id="31-grammar"></a>

[3.1 Grammar](0001-component-ir-sections/02-1-scope-principle-and-planes.md#31-grammar)

<a id="32-clauses"></a>

[3.2 Clauses](0001-component-ir-sections/02-1-scope-principle-and-planes.md#32-clauses)

<a id="4-contract-clauses-normative--free-to-add"></a>

[4. Contract clauses (normative — free to add)](0001-component-ir-sections/04-4-contract-clauses-normative--free-to-add.md#4-contract-clauses-normative--free-to-add)

<a id="5-non-goals"></a>

[5. Non-goals](0001-component-ir-sections/05-5-non-goals.md#5-non-goals)

<a id="6-amendment-procedure"></a>

[6. Amendment procedure](0001-component-ir-sections/05-5-non-goals.md#6-amendment-procedure)

<a id="61-change-classes"></a>

[6.1 Change classes](0001-component-ir-sections/05-5-non-goals.md#61-change-classes)

<a id="62-process"></a>

[6.2 Process](0001-component-ir-sections/05-5-non-goals.md#62-process)

<a id="63-errata"></a>

[6.3 Errata](0001-component-ir-sections/05-5-non-goals.md#63-errata)

<a id="appendix-a--worked-examples-informative"></a>

[Appendix A — Worked examples (informative)](0001-component-ir-sections/05-5-non-goals.md#appendix-a--worked-examples-informative)

<a id="a1-the-ema-z-strategy-expanding_z_v4"></a>

[A.1 The EMA-z strategy (`expanding_z_v4`)](0001-component-ir-sections/05-5-non-goals.md#a1-the-ema-z-strategy-expanding_z_v4)

<a id="a2-a-decomposed-atr-indicator"></a>

[A.2 A decomposed ATR indicator](0001-component-ir-sections/05-5-non-goals.md#a2-a-decomposed-atr-indicator)

<a id="a3-a-generated-strategy-from-the-block-grammar"></a>

[A.3 A generated strategy from the block grammar](0001-component-ir-sections/05-5-non-goals.md#a3-a-generated-strategy-from-the-block-grammar)

<a id="a4-a-nested-subgraph"></a>

[A.4 A nested subgraph](0001-component-ir-sections/06-a4-a-nested-subgraph.md#a4-a-nested-subgraph)

<a id="a5-a-multi-timeframe-case"></a>

[A.5 A multi-timeframe case](0001-component-ir-sections/06-a4-a-nested-subgraph.md#a5-a-multi-timeframe-case)

<a id="appendix-b--traceability-informative"></a>

[Appendix B — Traceability (informative)](0001-component-ir-sections/06-a4-a-nested-subgraph.md#appendix-b--traceability-informative)

<a id="b1-terminology-mapping"></a>

[B.1 Terminology mapping](0001-component-ir-sections/06-a4-a-nested-subgraph.md#b1-terminology-mapping)

<a id="appendix-c--open-questions-carried-forward-informative"></a>

[Appendix C — Open questions carried forward (informative)](0001-component-ir-sections/07-appendix-c--open-questions-carried-forward-informative.md#appendix-c--open-questions-carried-forward-informative)

<a id="ca-fork-semantics-beyond-a-parent-pointer"></a>

[C(a) Fork semantics beyond a parent pointer](0001-component-ir-sections/07-appendix-c--open-questions-carried-forward-informative.md#ca-fork-semantics-beyond-a-parent-pointer)

<a id="cb-field-and-structure-inference-rules-in-our-domain"></a>

[C(b) Field and structure inference rules in our domain](0001-component-ir-sections/07-appendix-c--open-questions-carried-forward-informative.md#cb-field-and-structure-inference-rules-in-our-domain)

<a id="cc-migration-machinery"></a>

[C(c) Migration machinery](0001-component-ir-sections/07-appendix-c--open-questions-carried-forward-informative.md#cc-migration-machinery)

<a id="cd-whether-and-when-the-live-engine-executes-ir-graphs"></a>

[C(d) Whether and when the live engine executes IR graphs](0001-component-ir-sections/07-appendix-c--open-questions-carried-forward-informative.md#cd-whether-and-when-the-live-engine-executes-ir-graphs)

<a id="ce-tick-level-and-intrabar-strategies"></a>

[C(e) Tick-level and intrabar strategies](0001-component-ir-sections/07-appendix-c--open-questions-carried-forward-informative.md#ce-tick-level-and-intrabar-strategies)

<a id="cf-marketplace-trust-and-sandboxing-at-scale"></a>

[C(f) Marketplace trust and sandboxing at scale](0001-component-ir-sections/07-appendix-c--open-questions-carried-forward-informative.md#cf-marketplace-trust-and-sandboxing-at-scale)
