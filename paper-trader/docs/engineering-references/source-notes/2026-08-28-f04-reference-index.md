# F04 level-moment reference index

Bounded documentation follow-up requested by coordinator `01a048c2-42d6-7850-94e9-af0f2ed5e0e1`. Correction owner: `01a0487e-b73b-76a0-bffd-870f6f6bc6af`. Index owner: `01a04855-b00a-7cc1-b783-767ae026d5e5`. New independent assurance owner: `01a048c6-8031-7c93-9b05-2fef7b25c499`.

## Scope and closure

Append three sources and four claims to the professional-reference registries, add this note and its [index receipt](../refresh-reports/2026-08-28-f04-reference-index.json), validate their links/hashes and preservation, and return the receipt to the requesting coordinator. All earlier registry records, index receipts and sealed evidence remain unchanged. This is a new bookkeeping capsule, not a reopening of the broader review.

No agents, numerical tests, source retrieval, product/test edits, `AGENTS.md`, `CURRENT.md`, `PROGRAMME.json`, publication or deployment. Write scope is these two registry additions, this follow-up note/receipt and `.agent/runs/professional-reference-f04-index-20260828/`. Deployment impact and migration: none. Rollback removes only this follow-up's additions, preserving prior and subsequent work.

## Input and evidence state

Input: `.agent/runs/post-phase5-indicator-accuracy-core-level-moment-correction/reference-application.md`, SHA-256 `e4a4a0fd34c546f3eca88b095de02b940f1aca14e4a3db8750a39d304ac9b045`.

The supplied closure seal has SHA-256 `417c9e7e5ca7cc6bad47b24f069c096cc20f76b7e830d3c4e4cb4136eeb83c00`. It binds `evidence.json`, which binds the source-application receipt. The index checks that chain and the referenced report/source/runtime/resource/mutation evidence hashes. It does not independently validate the mathematics or rerun the correction's tests.

Exact local verdict: **`F04_LOCAL_CORRECTION_PASS_PENDING_INDEPENDENT_ASSURANCE`**. Current assurance is **PENDING** in `post-phase5-indicator-accuracy-core-level-moment-assurance`. Independent acceptance, publication, deployment and V0 completion remain false. The earlier F04 REJECT from `01a04883-7dc6-71a1-bb51-9e9dff45c450` stays immutable negative evidence.

## Source reuse, not fresh reading

| Source ID | Exact authority | Reading / retrieval state |
| --- | --- | --- |
| `NIST_LEAST_SQUARES_CAPTURE` | Existing `nist-least-squares` record in the correction-replan source authority; captured digest `6646a579694dd7ebe304c8d281c46f60d6b038f1b4626691c4381742853edd98` | Previously captured primary documentation, reused by F04. Indexer verifies local bytes and metadata only. No new retrieval or claimed fresh reading. |
| `TA_LIB_0_7_1_LEVEL_REFERENCES` | Official commit `2247d599bddf37ed37e3a709371517e46efc66f6`; captured CORREL, LINEARREG_SLOPE and LINEARREG_INTERCEPT files and licence record | Reference only; no runtime adoption or universal parity claim. The receipt's “LINEARREG sources” maps to the two registered slope/intercept files, not an invented generic `ta_LINEARREG.c` record. |
| `STRATEGY_OS_F04_SPEC` | Sealed F04 REJECT, its pre-inspection rational oracle and the accepted seven semantic definitions, as attributed by the correction receipt | Independent specification evidence, separate from implementation-owner checks and the new pending assurance. No oracle/formula code is read by this indexer. |

NIST and TA-Lib content hashes are copied from existing authority records and checked against local captured files. No upstream digest is invented. Original capture/reading timestamps are not established by this indexing pass and are not replaced with today's metadata-check date. Earlier Python documentation records remain unchanged; the sealed arithmetic receipt identifies the reused measured Python 3.13.5 environment separately from the previously reported maintenance documentation.

## Indexed claims

- `NUM-005`: exact rational, n-scaled level moments preserve the declared centered covariance and OLS formulas while avoiding rounded means and premature squared-deviation underflow.
- `NUM-006`: the existing explicit Decimal context is reserved for the final irrational correlation square root; zero-divisor/constant-covariance semantics stay explicit, with no epsilon, clipping, floor or fallback introduced.
- `NUM-007`: the correction owner's impact and verification chain covers all seven consumers, retains independent expectations, records the scope amendment before edits, and distinguishes local RED/GREEN/resource/mutation results from acceptance.
- `NUM-008`: captured primary references and independent specification/counterexamples support the bounded correction; source reuse, direct experiments, dependency identity and later acceptance are separate facts.

These claims are indexed from the sealed owner receipt. Numerical truth is not inferred from their presence in a registry. The full report, exact local totals, candidate/source identity and runtime/resource/mutation links live in the machine receipt rather than being turned into new independent results here.

## Remaining limits

No indexing blocker was found. Original capture/fresh-reading dates remain unknown where not supplied; reused-source hashes identify captured bytes, not current upstream contents. New independent numerical acceptance remains pending. Metadata checks are recorded in `.agent/runs/professional-reference-f04-index-20260828/root/validation.json`; a bookkeeping PASS is never an assurance PASS.
