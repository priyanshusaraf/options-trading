# Ground-truth audit — 2026-07-28

Read the relevant section below. The content was split for bounded reading on 6 September 2026; technical decisions and historical evidence were not re-approved by this refactor. Earlier status, commands and permission wording apply only to their original scope.

| Section | Words |
| --- | ---: |
| [Ground-truth audit — 2026-07-28](ground-truth-2026-07-28-sections/01-ground-truth-audit--2026-07-28.md) | 963 |
| [2. Starting capital / equity anchoring](ground-truth-2026-07-28-sections/02-2-starting-capital--equity-anchoring.md) | 970 |
| [4. Test counts](ground-truth-2026-07-28-sections/03-4-test-counts.md) | 784 |
| [6. Deploy reality](ground-truth-2026-07-28-sections/04-6-deploy-reality.md) | 1136 |
| [Could not be established](ground-truth-2026-07-28-sections/05-could-not-be-established.md) | 568 |

## Existing section links

These anchors preserve incoming links. Follow the section link to read its content.

<a id="ground-truth-audit--2026-07-28"></a>

[Ground-truth audit — 2026-07-28](ground-truth-2026-07-28-sections/01-ground-truth-audit--2026-07-28.md#ground-truth-audit--2026-07-28)

<a id="summary-table"></a>

[Summary table](ground-truth-2026-07-28-sections/01-ground-truth-audit--2026-07-28.md#summary-table)

<a id="1-equity-intraday-position-sizing"></a>

[1. Equity intraday position sizing](ground-truth-2026-07-28-sections/01-ground-truth-audit--2026-07-28.md#1-equity-intraday-position-sizing)

<a id="reality"></a>

[Reality](ground-truth-2026-07-28-sections/01-ground-truth-audit--2026-07-28.md#reality)

<a id="is-there-a-leverage-cap"></a>

[Is there a leverage cap?](ground-truth-2026-07-28-sections/01-ground-truth-audit--2026-07-28.md#is-there-a-leverage-cap)

<a id="latent-code-inconsistency-not-a-doc-issue"></a>

[Latent code inconsistency (not a doc issue)](ground-truth-2026-07-28-sections/01-ground-truth-audit--2026-07-28.md#latent-code-inconsistency-not-a-doc-issue)

<a id="2-starting-capital--equity-anchoring"></a>

[2. Starting capital / equity anchoring](ground-truth-2026-07-28-sections/02-2-starting-capital--equity-anchoring.md#2-starting-capital--equity-anchoring)

<a id="reality-on-this-branch"></a>

[Reality on this branch](ground-truth-2026-07-28-sections/02-2-starting-capital--equity-anchoring.md#reality-on-this-branch)

<a id="the-guards-make-it-inert-in-production"></a>

[The guards make it inert in production](ground-truth-2026-07-28-sections/02-2-starting-capital--equity-anchoring.md#the-guards-make-it-inert-in-production)

<a id="has-it-shipped"></a>

[Has it shipped?](ground-truth-2026-07-28-sections/02-2-starting-capital--equity-anchoring.md#has-it-shipped)

<a id="3-live-order-path--has-a-real-order-ever-been-placed"></a>

[3. Live order path — has a real order ever been placed?](ground-truth-2026-07-28-sections/02-2-starting-capital--equity-anchoring.md#3-live-order-path--has-a-real-order-ever-been-placed)

<a id="reality-false-50-real-orders-and-34-booked-live-trades"></a>

[Reality: **false.** 50 real orders and 34 booked live trades.](ground-truth-2026-07-28-sections/02-2-starting-capital--equity-anchoring.md#reality-false-50-real-orders-and-34-booked-live-trades)

<a id="4-test-counts"></a>

[4. Test counts](ground-truth-2026-07-28-sections/03-4-test-counts.md#4-test-counts)

<a id="reality-1"></a>

[Reality](ground-truth-2026-07-28-sections/03-4-test-counts.md#reality-1)

<a id="5-options-stop--target-and-the-ratcheting-trail"></a>

[5. Options stop / target and the ratcheting trail](ground-truth-2026-07-28-sections/03-4-test-counts.md#5-options-stop--target-and-the-ratcheting-trail)

<a id="reality-the-stop-is-30-not-35-the-target-and-the-ratchet-claims-are-correct"></a>

[Reality: the stop is **−30%**, not −35%. The target and the ratchet claims are correct.](ground-truth-2026-07-28-sections/03-4-test-counts.md#reality-the-stop-is-30-not-35-the-target-and-the-ratchet-claims-are-correct)

<a id="the-ratchet--claim-is-accurate"></a>

[The ratchet — claim is accurate](ground-truth-2026-07-28-sections/03-4-test-counts.md#the-ratchet--claim-is-accurate)

<a id="6-deploy-reality"></a>

[6. Deploy reality](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#6-deploy-reality)

<a id="does-scriptsdeploysh-exist-no"></a>

[Does `scripts/deploy.sh` exist? **No.**](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#does-scriptsdeploysh-exist-no)

<a id="is-there-an---exclude-env-guard-anywhere-no--prose-only"></a>

[Is there an `--exclude .env` guard anywhere? **No — prose only.**](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#is-there-an---exclude-env-guard-anywhere-no--prose-only)

<a id="how-deploys-actually-happen"></a>

[How deploys actually happen](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#how-deploys-actually-happen)

<a id="7-other-claims-contradicted-by-the-code"></a>

[7. Other claims contradicted by the code](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#7-other-claims-contradicted-by-the-code)

<a id="71-localhost--single-local-process--the-bot-runs-on-a-vps"></a>

[7.1 "localhost" / "single local process" — the bot runs on a VPS](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#71-localhost--single-local-process--the-bot-runs-on-a-vps)

<a id="72-no-real-capital-ever-moves-by-default"></a>

[7.2 "No real capital ever moves by default"](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#72-no-real-capital-ever-moves-by-default)

<a id="73-options-paper-trading-platform--the-book-is-97-equity"></a>

[7.3 "options paper-trading platform" — the book is 97% equity](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#73-options-paper-trading-platform--the-book-is-97-equity)

<a id="74-persisted-order-journal-is-described-as-deferred-but-is-built-and-in-use"></a>

[7.4 Persisted order journal is described as "deferred" but is built and in use](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#74-persisted-order-journal-is-described-as-deferred-but-is-built-and-in-use)

<a id="75-one-risk-toggle-ships-disabled--it-was-enabled-11-days-ago"></a>

[7.5 "One risk toggle ships disabled" — it was enabled 11 days ago](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#75-one-risk-toggle-ships-disabled--it-was-enabled-11-days-ago)

<a id="76-documented-defaults--production-behaviour-runtime_config-overrides"></a>

[7.6 Documented defaults ≠ production behaviour (runtime_config overrides)](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#76-documented-defaults--production-behaviour-runtime_config-overrides)

<a id="77-stale-line-references-in-the-arm-gate-note"></a>

[7.7 Stale line references in the ARM-gate note](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#77-stale-line-references-in-the-arm-gate-note)

<a id="78-incomplete-key-tables-list"></a>

[7.8 Incomplete key-tables list](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#78-incomplete-key-tables-list)

<a id="79-the-hardened-code-is-not-yet-deployed--unverifiable-as-written"></a>

[7.9 "the hardened code is not yet deployed" — unverifiable as written](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#79-the-hardened-code-is-not-yet-deployed--unverifiable-as-written)

<a id="710-pytest-as-documented-does-not-run-the-research-suite"></a>

[7.10 `pytest` as documented does not run the research suite](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#710-pytest-as-documented-does-not-run-the-research-suite)

<a id="711-options-1-lot--confirmed-accurate"></a>

[7.11 Options "1 lot" — confirmed accurate](ground-truth-2026-07-28-sections/04-6-deploy-reality.md#711-options-1-lot--confirmed-accurate)

<a id="could-not-be-established"></a>

[Could not be established](ground-truth-2026-07-28-sections/05-could-not-be-established.md#could-not-be-established)

<a id="appendix-a--production-runtime_config-2026-07-23-snapshot"></a>

[Appendix A — production `runtime_config` (2026-07-23 snapshot)](ground-truth-2026-07-28-sections/05-could-not-be-established.md#appendix-a--production-runtime_config-2026-07-23-snapshot)

<a id="appendix-b--commands-used"></a>

[Appendix B — commands used](ground-truth-2026-07-28-sections/05-could-not-be-established.md#appendix-b--commands-used)

<a id="recommended-follow-ups-not-performed--this-was-read-only"></a>

[Recommended follow-ups (not performed — this was read-only)](ground-truth-2026-07-28-sections/05-could-not-be-established.md#recommended-follow-ups-not-performed--this-was-read-only)
