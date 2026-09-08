# ADR 0013 — Research approval is an admission prerequisite, not an authority lease

Read the relevant section below. The content was split for bounded reading on 6 September 2026; technical decisions and historical evidence were not re-approved by this refactor. Earlier status, commands and permission wording apply only to their original scope.

| Section | Words |
| --- | ---: |
| [ADR 0013 — Research approval is an admission prerequisite, not an authority lease](0013-research-approval-is-admission-not-a-lease-sections/01-adr-0013--research-approval-is-an-admission-prerequisite-not-an-author.md) | 757 |
| [2. The decision](0013-research-approval-is-admission-not-a-lease-sections/02-2-the-decision.md) | 848 |
| [5. Consequences](0013-research-approval-is-admission-not-a-lease-sections/03-5-consequences.md) | 933 |
| [6. Outcome](0013-research-approval-is-admission-not-a-lease-sections/04-6-outcome.md) | 37 |

## Existing section links

These anchors preserve incoming links. Follow the section link to read its content.

<a id="adr-0013--research-approval-is-an-admission-prerequisite-not-an-authority-lease"></a>

[ADR 0013 — Research approval is an admission prerequisite, not an authority lease](0013-research-approval-is-admission-not-a-lease-sections/01-adr-0013--research-approval-is-an-admission-prerequisite-not-an-author.md#adr-0013--research-approval-is-an-admission-prerequisite-not-an-authority-lease)

<a id="1-what-the-code-actually-does"></a>

[1. What the code actually does](0013-research-approval-is-admission-not-a-lease-sections/01-adr-0013--research-approval-is-an-admission-prerequisite-not-an-author.md#1-what-the-code-actually-does)

<a id="11-evidence-records-are-immutable-and-verified-rather-than-trusted"></a>

[1.1 Evidence records are immutable, and verified rather than trusted](0013-research-approval-is-admission-not-a-lease-sections/01-adr-0013--research-approval-is-an-admission-prerequisite-not-an-author.md#11-evidence-records-are-immutable-and-verified-rather-than-trusted)

<a id="12-approval-decisions-are-write-once"></a>

[1.2 Approval decisions are write-once](0013-research-approval-is-admission-not-a-lease-sections/01-adr-0013--research-approval-is-an-admission-prerequisite-not-an-author.md#12-approval-decisions-are-write-once)

<a id="13-what-a-later-negative-decision-actually-changes"></a>

[1.3 What a later negative decision actually changes](0013-research-approval-is-admission-not-a-lease-sections/01-adr-0013--research-approval-is-an-admission-prerequisite-not-an-author.md#13-what-a-later-negative-decision-actually-changes)

<a id="14-an-activated-deployment-persists-the-whole-admission-fact"></a>

[1.4 An activated deployment persists the whole admission fact](0013-research-approval-is-admission-not-a-lease-sections/01-adr-0013--research-approval-is-an-admission-prerequisite-not-an-author.md#14-an-activated-deployment-persists-the-whole-admission-fact)

<a id="15-reload-is-already-independent-of-the-research-plane--measured"></a>

[1.5 Reload is already independent of the research plane — measured](0013-research-approval-is-admission-not-a-lease-sections/01-adr-0013--research-approval-is-an-admission-prerequisite-not-an-author.md#15-reload-is-already-independent-of-the-research-plane--measured)

<a id="2-the-decision"></a>

[2. The decision](0013-research-approval-is-admission-not-a-lease-sections/02-2-the-decision.md#2-the-decision)

<a id="why-this-direction-and-not-the-other"></a>

[Why this direction and not the other](0013-research-approval-is-admission-not-a-lease-sections/02-2-the-decision.md#why-this-direction-and-not-the-other)

<a id="3-the-a8--a14-scenario-resolved"></a>

[3. The A8 / A14 scenario, resolved](0013-research-approval-is-admission-not-a-lease-sections/02-2-the-decision.md#3-the-a8--a14-scenario-resolved)

<a id="4-failed-refresh-semantics"></a>

[4. Failed-refresh semantics](0013-research-approval-is-admission-not-a-lease-sections/02-2-the-decision.md#4-failed-refresh-semantics)

<a id="5-consequences"></a>

[5. Consequences](0013-research-approval-is-admission-not-a-lease-sections/03-5-consequences.md#5-consequences)

<a id="51-the-l14-evidence-reload-gap-is-not-a-defect"></a>

[5.1 The L1.4 "evidence reload gap" is not a defect](0013-research-approval-is-admission-not-a-lease-sections/03-5-consequences.md#51-the-l14-evidence-reload-gap-is-not-a-defect)

<a id="52-admission-must-bind-the-exact-graph-content--closed-2026-08-08"></a>

[5.2 Admission must bind the exact graph *content* — closed 2026-08-08](0013-research-approval-is-admission-not-a-lease-sections/03-5-consequences.md#52-admission-must-bind-the-exact-graph-content--closed-2026-08-08)

<a id="53-newer-contradicting-research-is-an-operator-visible-fact--built-2026-08-08"></a>

[5.3 Newer contradicting research is an operator-visible fact — built 2026-08-08](0013-research-approval-is-admission-not-a-lease-sections/03-5-consequences.md#53-newer-contradicting-research-is-an-operator-visible-fact--built-2026-08-08)

<a id="53a-research-availability-affects-observability-not-authority"></a>

[5.3a Research availability affects observability, not authority](0013-research-approval-is-admission-not-a-lease-sections/03-5-consequences.md#53a-research-availability-affects-observability-not-authority)

<a id="53b-operator-response"></a>

[5.3b Operator response](0013-research-approval-is-admission-not-a-lease-sections/03-5-consequences.md#53b-operator-response)

<a id="54-the-withdrawal-invariant-is-strengthened-not-weakened"></a>

[5.4 The withdrawal invariant is strengthened, not weakened](0013-research-approval-is-admission-not-a-lease-sections/03-5-consequences.md#54-the-withdrawal-invariant-is-strengthened-not-weakened)

<a id="6-outcome"></a>

[6. Outcome](0013-research-approval-is-admission-not-a-lease-sections/04-6-outcome.md#6-outcome)
