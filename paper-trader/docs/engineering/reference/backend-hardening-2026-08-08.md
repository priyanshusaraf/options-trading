# Backend hardening phase — 2026-08-08

Read the relevant section below. The content was split for bounded reading on 6 September 2026; technical decisions and historical evidence were not re-approved by this refactor. Earlier status, commands and permission wording apply only to their original scope.

| Section | Words |
| --- | ---: |
| [Backend hardening phase — 2026-08-08](backend-hardening-2026-08-08-sections/01-backend-hardening-phase--2026-08-08.md) | 1085 |
| [4. Performance — measured](backend-hardening-2026-08-08-sections/02-4-performance--measured.md) | 1010 |
| [6a. Provider architecture — 2026-08-09](backend-hardening-2026-08-08-sections/03-6a-provider-architecture--2026-08-09.md) | 874 |
| [7. What is next](backend-hardening-2026-08-08-sections/04-7-what-is-next.md) | 1524 |
| [10. Sweep cost, per stage, and the premium-pricing bottleneck (2026-08-09)](backend-hardening-2026-08-08-sections/05-10-sweep-cost-per-stage-and-the-premium-pricing-bottleneck-2026-08-09.md) | 1284 |
| [12. Sweep persistence and fan-out, measured (2026-08-10)](backend-hardening-2026-08-08-sections/06-12-sweep-persistence-and-fan-out-measured-2026-08-10.md) | 945 |
| [14. Moving the pinned store read into the workers (2026-08-10)](backend-hardening-2026-08-08-sections/07-14-moving-the-pinned-store-read-into-the-workers-2026-08-10.md) | 800 |

## Existing section links

These anchors preserve incoming links. Follow the section link to read its content.

<a id="backend-hardening-phase--2026-08-08"></a>

[Backend hardening phase — 2026-08-08](backend-hardening-2026-08-08-sections/01-backend-hardening-phase--2026-08-08.md#backend-hardening-phase--2026-08-08)

<a id="1-commits"></a>

[1. Commits](backend-hardening-2026-08-08-sections/01-backend-hardening-phase--2026-08-08.md#1-commits)

<a id="2-security"></a>

[2. Security](backend-hardening-2026-08-08-sections/01-backend-hardening-phase--2026-08-08.md#2-security)

<a id="21-auth-posture--accurate-deliberate-and-untenable-for-v1-no-fix-owner-gate"></a>

[2.1 Auth posture — accurate, deliberate, and untenable for V1 (no fix; owner gate)](backend-hardening-2026-08-08-sections/01-backend-hardening-phase--2026-08-08.md#21-auth-posture--accurate-deliberate-and-untenable-for-v1-no-fix-owner-gate)

<a id="22-generated-strategy-sandbox--audited-found-sound-no-change"></a>

[2.2 Generated-strategy sandbox — audited, found sound (no change)](backend-hardening-2026-08-08-sections/01-backend-hardening-phase--2026-08-08.md#22-generated-strategy-sandbox--audited-found-sound-no-change)

<a id="23-injection-and-unsafe-primitive-sweep--clean"></a>

[2.3 Injection and unsafe-primitive sweep — clean](backend-hardening-2026-08-08-sections/01-backend-hardening-phase--2026-08-08.md#23-injection-and-unsafe-primitive-sweep--clean)

<a id="24-unbounded-reads--real-fixed-837febe"></a>

[2.4 Unbounded reads — REAL, FIXED (`837febe`)](backend-hardening-2026-08-08-sections/01-backend-hardening-phase--2026-08-08.md#24-unbounded-reads--real-fixed-837febe)

<a id="3-data-integrity-and-test-evidence-integrity"></a>

[3. Data integrity and test-evidence integrity](backend-hardening-2026-08-08-sections/01-backend-hardening-phase--2026-08-08.md#3-data-integrity-and-test-evidence-integrity)

<a id="31-the-suite-was-order-dependent--fixed-e6b9bbf"></a>

[3.1 The suite was order-dependent — FIXED (`e6b9bbf`)](backend-hardening-2026-08-08-sections/01-backend-hardening-phase--2026-08-08.md#31-the-suite-was-order-dependent--fixed-e6b9bbf)

<a id="32-a-vacuous-test-caught-in-my-own-work--worth-recording"></a>

[3.2 A vacuous test caught in my own work — worth recording](backend-hardening-2026-08-08-sections/01-backend-hardening-phase--2026-08-08.md#32-a-vacuous-test-caught-in-my-own-work--worth-recording)

<a id="4-performance--measured"></a>

[4. Performance — measured](backend-hardening-2026-08-08-sections/02-4-performance--measured.md#4-performance--measured)

<a id="41-recent_trades--the-2026-07-23-outage-shape-in-a-second-place-fixed"></a>

[4.1 `recent_trades` — the 2026-07-23 outage shape, in a second place (FIXED)](backend-hardening-2026-08-08-sections/02-4-performance--measured.md#41-recent_trades--the-2026-07-23-outage-shape-in-a-second-place-fixed)

<a id="42-the-connection-pool-has-a-measured-cliff-not-yet-changed--see-6"></a>

[4.2 The connection pool has a measured cliff (NOT yet changed — see §6)](backend-hardening-2026-08-08-sections/02-4-performance--measured.md#42-the-connection-pool-has-a-measured-cliff-not-yet-changed--see-6)

<a id="5-quant--research-leakage"></a>

[5. Quant / research leakage](backend-hardening-2026-08-08-sections/02-4-performance--measured.md#5-quant--research-leakage)

<a id="51-causality-of-the-hand-written-strategies--audited-no-defect-now-guarded-ce72249"></a>

[5.1 Causality of the hand-written strategies — audited, no defect, now guarded (`ce72249`)](backend-hardening-2026-08-08-sections/02-4-performance--measured.md#51-causality-of-the-hand-written-strategies--audited-no-defect-now-guarded-ce72249)

<a id="52-look-ahead-discipline-elsewhere--inspected-healthy"></a>

[5.2 Look-ahead discipline elsewhere — inspected, healthy](backend-hardening-2026-08-08-sections/02-4-performance--measured.md#52-look-ahead-discipline-elsewhere--inspected-healthy)

<a id="53-not-yet-audited"></a>

[5.3 Not yet audited](backend-hardening-2026-08-08-sections/02-4-performance--measured.md#53-not-yet-audited)

<a id="6-architecture-conclusions-so-far"></a>

[6. Architecture conclusions so far](backend-hardening-2026-08-08-sections/02-4-performance--measured.md#6-architecture-conclusions-so-far)

<a id="6a-provider-architecture--2026-08-09"></a>

[6a. Provider architecture — 2026-08-09](backend-hardening-2026-08-08-sections/03-6a-provider-architecture--2026-08-09.md#6a-provider-architecture--2026-08-09)

<a id="done-capabilities-replace-provider-name-branching-553d871-7442e69"></a>

[Done: capabilities replace provider-name branching (`553d871`, `7442e69`)](backend-hardening-2026-08-08-sections/03-6a-provider-architecture--2026-08-09.md#done-capabilities-replace-provider-name-branching-553d871-7442e69)

<a id="found-and-fixed-the-index-futures-segment-had-no-price-feed-latent-p1"></a>

[Found AND fixed: the index-futures segment had no price feed (latent P1)](backend-hardening-2026-08-08-sections/03-6a-provider-architecture--2026-08-09.md#found-and-fixed-the-index-futures-segment-had-no-price-feed-latent-p1)

<a id="done-instrument-identity-has-a-seam-and-kite-is-behind-it-0a55b3a"></a>

[Done: instrument identity has a seam, and Kite is behind it (`0a55b3a`)](backend-hardening-2026-08-08-sections/03-6a-provider-architecture--2026-08-09.md#done-instrument-identity-has-a-seam-and-kite-is-behind-it-0a55b3a)

<a id="7-what-is-next"></a>

[7. What is next](backend-hardening-2026-08-08-sections/04-7-what-is-next.md#7-what-is-next)

<a id="8-method-notes-worth-keeping"></a>

[8. Method notes worth keeping](backend-hardening-2026-08-08-sections/04-7-what-is-next.md#8-method-notes-worth-keeping)

<a id="9-the-provider-conformance-contract-and-what-it-found-2026-08-09"></a>

[9. The provider conformance contract, and what it found (2026-08-09)](backend-hardening-2026-08-08-sections/04-7-what-is-next.md#9-the-provider-conformance-contract-and-what-it-found-2026-08-09)

<a id="91-why-a-second-contract-was-needed"></a>

[9.1 Why a second contract was needed](backend-hardening-2026-08-08-sections/04-7-what-is-next.md#91-why-a-second-contract-was-needed)

<a id="92-four-defects-all-found-by-the-contract-on-its-first-runs"></a>

[9.2 Four defects, all found by the contract on its first runs](backend-hardening-2026-08-08-sections/04-7-what-is-next.md#92-four-defects-all-found-by-the-contract-on-its-first-runs)

<a id="93-evidence"></a>

[9.3 Evidence](backend-hardening-2026-08-08-sections/04-7-what-is-next.md#93-evidence)

<a id="94-still-open--named-not-solved"></a>

[9.4 Still open — named, not solved](backend-hardening-2026-08-08-sections/04-7-what-is-next.md#94-still-open--named-not-solved)

<a id="10-sweep-cost-per-stage-and-the-premium-pricing-bottleneck-2026-08-09"></a>

[10. Sweep cost, per stage, and the premium-pricing bottleneck (2026-08-09)](backend-hardening-2026-08-08-sections/05-10-sweep-cost-per-stage-and-the-premium-pricing-bottleneck-2026-08-09.md#10-sweep-cost-per-stage-and-the-premium-pricing-bottleneck-2026-08-09)

<a id="the-661-mscell-figure-was-measured-on-the-wrong-workload"></a>

[The 6.61 ms/cell figure was measured on the wrong workload](backend-hardening-2026-08-08-sections/05-10-sweep-cost-per-stage-and-the-premium-pricing-bottleneck-2026-08-09.md#the-661-mscell-figure-was-measured-on-the-wrong-workload)

<a id="the-dominant-cost-was-a-scipy-wrapper-not-arithmetic"></a>

[The dominant cost was a scipy wrapper, not arithmetic](backend-hardening-2026-08-08-sections/05-10-sweep-cost-per-stage-and-the-premium-pricing-bottleneck-2026-08-09.md#the-dominant-cost-was-a-scipy-wrapper-not-arithmetic)

<a id="what-the-tier-maths-now-says"></a>

[What the tier maths now says](backend-hardening-2026-08-08-sections/05-10-sweep-cost-per-stage-and-the-premium-pricing-bottleneck-2026-08-09.md#what-the-tier-maths-now-says)

<a id="11-websocket-fan-out-cost-at-500-users-2026-08-09"></a>

[11. WebSocket fan-out cost at 500 users (2026-08-09)](backend-hardening-2026-08-08-sections/05-10-sweep-cost-per-stage-and-the-premium-pricing-bottleneck-2026-08-09.md#11-websocket-fan-out-cost-at-500-users-2026-08-09)

<a id="the-bandwidth-is-not-the-problem-the-serialisation-is"></a>

[The bandwidth is not the problem. The serialisation is.](backend-hardening-2026-08-08-sections/05-10-sweep-cost-per-stage-and-the-premium-pricing-bottleneck-2026-08-09.md#the-bandwidth-is-not-the-problem-the-serialisation-is)

<a id="two-corrections-neither-of-them-use-polling"></a>

[Two corrections, neither of them "use polling"](backend-hardening-2026-08-08-sections/05-10-sweep-cost-per-stage-and-the-premium-pricing-bottleneck-2026-08-09.md#two-corrections-neither-of-them-use-polling)

<a id="12-sweep-persistence-and-fan-out-measured-2026-08-10"></a>

[12. Sweep persistence and fan-out, measured (2026-08-10)](backend-hardening-2026-08-08-sections/06-12-sweep-persistence-and-fan-out-measured-2026-08-10.md#12-sweep-persistence-and-fan-out-measured-2026-08-10)

<a id="one-sqlite-writer-sustains-both-tiers"></a>

[One SQLite writer sustains both tiers](backend-hardening-2026-08-08-sections/06-12-sweep-persistence-and-fan-out-measured-2026-08-10.md#one-sqlite-writer-sustains-both-tiers)

<a id="fan-out-gives-2x-and-the-reason-is-measured"></a>

[Fan-out gives 2x, and the reason is measured](backend-hardening-2026-08-08-sections/06-12-sweep-persistence-and-fan-out-measured-2026-08-10.md#fan-out-gives-2x-and-the-reason-is-measured)

<a id="a-method-note-that-cost-a-suppression"></a>

[A method note that cost a suppression](backend-hardening-2026-08-08-sections/06-12-sweep-persistence-and-fan-out-measured-2026-08-10.md#a-method-note-that-cost-a-suppression)

<a id="13-tiered-sweep-benchmark-task-7-2026-08-10"></a>

[13. Tiered sweep benchmark (Task 7, 2026-08-10)](backend-hardening-2026-08-08-sections/06-12-sweep-persistence-and-fan-out-measured-2026-08-10.md#13-tiered-sweep-benchmark-task-7-2026-08-10)

<a id="per-cell-stage-cost-5000-bar-datasets-12-repeats"></a>

[Per-cell stage cost, 5,000-bar datasets, 12 repeats](backend-hardening-2026-08-08-sections/06-12-sweep-persistence-and-fan-out-measured-2026-08-10.md#per-cell-stage-cost-5000-bar-datasets-12-repeats)

<a id="projected-tiers--projections-not-capacity"></a>

[Projected tiers — projections, not capacity](backend-hardening-2026-08-08-sections/06-12-sweep-persistence-and-fan-out-measured-2026-08-10.md#projected-tiers--projections-not-capacity)

<a id="operation-counts-end-to-end"></a>

[Operation counts, end-to-end](backend-hardening-2026-08-08-sections/06-12-sweep-persistence-and-fan-out-measured-2026-08-10.md#operation-counts-end-to-end)

<a id="two-harness-guards-both-proven-able-to-fail"></a>

[Two harness guards, both proven able to fail](backend-hardening-2026-08-08-sections/06-12-sweep-persistence-and-fan-out-measured-2026-08-10.md#two-harness-guards-both-proven-able-to-fail)

<a id="14-moving-the-pinned-store-read-into-the-workers-2026-08-10"></a>

[14. Moving the pinned store read into the workers (2026-08-10)](backend-hardening-2026-08-08-sections/07-14-moving-the-pinned-store-read-into-the-workers-2026-08-10.md#14-moving-the-pinned-store-read-into-the-workers-2026-08-10)

<a id="before--after"></a>

[Before / after](backend-hardening-2026-08-08-sections/07-14-moving-the-pinned-store-read-into-the-workers-2026-08-10.md#before--after)

<a id="the-parent-is-no-longer-the-bottleneck"></a>

[The parent is no longer the bottleneck](backend-hardening-2026-08-08-sections/07-14-moving-the-pinned-store-read-into-the-workers-2026-08-10.md#the-parent-is-no-longer-the-bottleneck)

<a id="what-this-does-and-does-not-buy"></a>

[What this does and does not buy](backend-hardening-2026-08-08-sections/07-14-moving-the-pinned-store-read-into-the-workers-2026-08-10.md#what-this-does-and-does-not-buy)

<a id="reproducing-the-refusals-worker-side-was-the-whole-risk-and-it-cost-one-design-decision"></a>

[Reproducing the refusals worker-side was the whole risk, and it cost one design decision](backend-hardening-2026-08-08-sections/07-14-moving-the-pinned-store-read-into-the-workers-2026-08-10.md#reproducing-the-refusals-worker-side-was-the-whole-risk-and-it-cost-one-design-decision)

<a id="suppressions-both-proven-able-to-redden"></a>

[Suppressions, both proven able to redden](backend-hardening-2026-08-08-sections/07-14-moving-the-pinned-store-read-into-the-workers-2026-08-10.md#suppressions-both-proven-able-to-redden)
