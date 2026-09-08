# F02/F03 numerical reference index

This is a bounded documentation follow-up requested by V0 coordinator task `01a0487e-b73b-76a0-bffd-870f6f6bc6af`. It indexes the correction owner's already checked receipt; it does not reopen the Kleppmann review or provide numerical assurance.

## Scope and stopping condition

Allowed changes: append source/claim records in the professional-reference registries, add this note and its [index receipt](../refresh-reports/2026-08-28-core-numerical-index.json), and record checks under `.agent/runs/professional-reference-numerical-index-20260828/`. No agents, product/test edits, `AGENTS.md`, `CURRENT.md`, `PROGRAMME.json`, original intake files, correction evidence, or assurance evidence may be changed.

Complete when source/claim links and hashes validate, all prior registry records survive, sealed intake/correction evidence remains unchanged, and the coordinator receives the receipt. Deployment impact and migration: none. Rollback removes only these appended records and new follow-up files; it must not overwrite newer work or original evidence.

## Provenance and authority

Input: `.agent/runs/post-phase5-indicator-accuracy-core-return-stability-correction/reference-claims.md`, checked by the correction owner on 28 August 2026, SHA-256 `16ce66e26b31ffc8b75d0294650a42381c797da0536677a44717401f9fa857f1`.

The input is transitively sealed: `closure-seal.json` binds `evidence.json`, which binds `reference-claims.md`. The same closure binds the report, source proof, arithmetic-executor receipt, mutation receipt and resource evidence. This index checks those file hashes; it does not rerun or independently accept their scientific conclusions.

The local verdict remains `LOCAL_CORRECTION_PASS_PENDING_INDEPENDENT_ASSURANCE`. Independent acceptance is **PENDING** in `post-phase5-indicator-accuracy-core-correction-assurance`, owned by task `01a04883-7dc6-71a1-bb51-9e9dff45c450`. Publication, deployment and V0-completion authority remain false.

## Indexed source and claim distinctions

| Record | Attributed evidence | Meaning and limits |
| --- | --- | --- |
| `PYTHON_STDLIB_3_13` | Official `math.log1p`, `decimal.Decimal` and `decimal.Context` documentation, as checked by the correction owner | The receipt identifies maintenance documentation **3.13.15**. The indexer read the receipt, not these upstream pages; no new reading or current-version verification is claimed. |
| `STRATEGY_OS_CORE_MATH_SPEC` | Different-owner original assurance, retained REJECT, exact counterchecks and accepted mathematical definitions | Independent specification evidence is distinct from the implementation owner's local tests. The old REJECT is not converted into acceptance of the new candidate. |
| `NUM-001` | `log1p` source claim and local correction evidence | Near-one logarithm stabilization within the declared return semantics; no newly invented domain or return floor. |
| `NUM-002` | Exact binary-float conversion and explicit Decimal context claims | Temporary precision arithmetic must not inherit caller precision, rounding, exponent or trap settings; float64 input/output/state envelopes remain as declared. |
| `NUM-003` | Exact rational level-regression argument and direct correction evidence | Large-coordinate residual cancellation is addressed through rational moments. This is not attributed to an unreviewed Python `fractions` documentation page. |
| `NUM-004` | Independent specification plus local direct experiments and rejected changes | RED/GREEN, mutation, complete-array, consumer and resource evidence remain owner-reported local results. No epsilon/mask relaxation, provider fallback, broad Decimal rewrite or dependency adoption is inferred. |

The measured executable is **Python 3.13.5**, separately identified by its recorded executable, `math`, Decimal shim/native module, `fractions`, and linked libmpdec hashes. The documentation's maintenance version does not describe the binary that ran. Exact runtime attribution is in the index receipt and linked arithmetic-executor record.

## Preservation and verification limits

The prior 31 source records and two claim records remain unchanged. Two source records and four claims are added. The original intake report and sealed evidence remain a historical snapshot; they are not rewritten to show the new totals. Before-images of the two registries and a new scope/hash receipt live under the follow-up evidence directory.

Only document identity, link resolution, append preservation and stated verification boundaries are checked here. No numerical tests, source retrieval, source-code review, dependency installation or new architecture decision occurred. The reference receipt supplies upstream URLs and a reported maintenance version, but no per-page content digest; this index leaves that field unknown rather than fabricating a source snapshot.

Machine result: `.agent/runs/professional-reference-numerical-index-20260828/root/validation.json`. This documentation result must never be read as an assurance PASS.
