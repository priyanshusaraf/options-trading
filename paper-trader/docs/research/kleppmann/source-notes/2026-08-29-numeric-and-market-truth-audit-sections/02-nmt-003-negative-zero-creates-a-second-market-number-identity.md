Reference: [section index](../2026-08-29-numeric-and-market-truth-audit.md). Read with its scope; this is not a new assignment.

## NMT-003: negative zero creates a second market-number identity

- **Classification:** `LATENT BUG / MISSING IDENTITY INVARIANT`.
- **Sources:** RFC 8785 Appendix B serializes both IEEE 754 positive and negative
  zero as JSON `0`. Python 3.13.15 documents explicit decimal contexts and
  rounding. The direct repository probe establishes the current behavior.
- **Assumptions:** Signed zero has no distinct Strategy OS meaning for OHLCV,
  quantity, charge or evidence identity.
- **Failure hypothesis:** If numeric ingress keeps `-0.0`, semantically equal zero
  observations can produce different content addresses and dataset/cache keys.
- **Repository evidence:** `app/market_data/numeric.py:31-49` accepts finite
  `-0.0`; `app/ir/validity.py:94-105` also accepts it. `app/ir/hashing.py:14-29`
  serializes through Python JSON. `canonical_decimal` in
  `app/market_truth/identity.py:87-102` already rejects the noncanonical `-0`
  spelling. The probe `probe-negative-zero-identity.log` records `-0.0`, accepts
  it as valid and produces a different address from `0.0`.
- **Consequence:** A provider spelling or transform detail can fragment immutable
  observation and manifest identity without changing the numeric result.
- **Smallest safe response:** Choose and version one ingress rule: normalize any
  numeric zero to positive zero, or refuse negative zero. Keep the raw provider
  bytes unchanged for provenance. Do not replace analytical floats with Decimal.
- **Verification:** Prove positive and negative zero have one normalized identity,
  raw bytes remain attributable, all non-finite refusals remain, and a negative-
  zero guard mutation fails. Repeat after database reopen and canonical dataset
  reconstruction.
- **Migration and rollback:** Do not rewrite immutable old observations. A new
  normalization algorithm version produces new observation and manifest
  addresses. Old results retain their original algorithm and dataset binding.
- **Owner:** `strategy-os-v0-canonical-research-spine` for canonical dataset
  identity, before numerical publication.
- **Disposition:** `IMPLEMENT IN SEPARATE CAPSULE`; no existing receipt is relabelled.

## NMT-004: charge rates are stale and unknown segments fall through

- **Classification:** `CONFIRMED CURRENT BUG` for the inspected research charge
  projection, plus `MISSING INVARIANT` for rounding and effective dating.
- **Sources:** The public Zerodha charges page captured on 29 August 2026 lists
  F&O futures STT at 0.05 percent on the sell side, options STT at 0.15 percent
  on sell premium, NSE futures transaction charges at 0.00183 percent and NSE
  options at 0.03553 percent. Python 3.13.15 `decimal` documents exact decimal
  construction, explicit rounding modes and `quantize()` for monetary
  applications. The direct probe checks current code.
- **Assumptions:** The current public broker schedule is a changeable reference,
  not proof of a historical rate or a contract-note result. Research results must
  bind the schedule and rounding policy they actually used.
- **Failure hypothesis:** A stale or implicit schedule understates charges and
  overstates net returns. An unknown segment silently priced as NFO can apply the
  wrong tax, exchange and brokerage semantics.
- **Repository evidence:** `app/engine/charges.py:31-90` stores unversioned binary
  float rates. Lines 23-25 call them indicative. Line 106 maps an unknown segment
  to NFO. Lines 128-140 apply Python `round(..., 2)` without a named domain
  rounding policy. `probe-charge-boundaries.log` records code rates 0.10 percent
  for NFO options and 0.02 percent for NFO futures. At sample turnovers, code
  returns tax of INR 15 instead of INR 22.50 and INR 360 instead of INR 900 under
  the captured public schedule. The probe also proves `TYPO` uses NFO charges.
- **Consequence:** The two samples understate tax by INR 7.50 and INR 540. The
  difference flows directly into net P&L. The current unit tests pin the old
  constants and approximate totals; `test_an_unknown_segment_does_not_silently_cost_zero`
  never calls an unknown segment.
- **Smallest safe response:** Fail closed on unknown segments. Bind charge policy,
  effective interval, source receipt, currency, minor-unit scale and component
  rounding rules into research identity. Verify current values against lawful
  public material and synthetic golden vectors; reserve real contract-note
  conformance for a separately authorized private evidence gate.
- **Verification:** Use exact decimal or integer-minor arithmetic at named
  rounding boundaries; run official public examples where available; compare
  synthetic vectors independently; refuse unknown and out-of-interval schedules;
  prove a rate or rounding-policy change makes the result cold; kill a fallback
  mutation. No real account or order test is required by this audit.
- **Migration and rollback:** Existing immutable results keep their original
  implementation and schedule identity and must not be recomputed silently. A
  corrected schedule produces new results. Rollback retains both result sets and
  restores only the active policy selection.
- **Owners:** `strategy-os-v0-canonical-research-spine` for V0 net-of-charges
  research evidence, and `phase8-provider-price-coherence` before any V1
  execution-price or charge authority.
- **Disposition:** `IMPLEMENT IN SEPARATE CAPSULE`; no live schedule was changed.

## NMT-005: units are documented but erased from analytical port types

- **Classification:** `MISSING INVARIANT`. A current executable mismatched-unit
  result was not reproduced, so this is not labelled a current wrong-result bug.
- **Sources:** NASA's Mars Climate Orbiter Phase II report attributes the loss to
  pound-second data where the interface required newton-seconds and recommends
  checking consistent units at interfaces. The repository type probe establishes
  the current Strategy OS seam.
- **Assumptions:** Price, decimal return, percentage points, variance, quantity and
  time are distinct dimensions even when their runtime scalar is binary64.
- **Failure hypothesis:** A future graph consumer that sees only
  `analytical.float64/series` can connect a decimal return where price points are
  required and still pass structural type validation.
- **Repository evidence:** The indicator specifications declare detailed units.
  `app/ir/first_party/analytical_v2/core_math.py:1054-1057` collapses every numeric
  output to `analytical.float64`; lines 1093-1097 repeat that type in the source
  contract. `probe-unit-type-erasure.log` shows `PERCENT_RETURN`, `SMA` and
  `ROLLING_VARIANCE` declare three different units while exposing the same port
  and contract types.
- **Consequence:** The present catalogue retains useful documentation but the
  compiler cannot use it to reject a dimensional mismatch. Actual reachability
  through the accepted graph language remains `UNVERIFIABLE` in this read-only
  packet.
- **Smallest safe response:** Let `phase6-language-resource-contracts` decide the
  smallest closed dimension vocabulary and connection rule. Do not add a general
  units library or rewrite every analytical value in V0.
- **Verification:** Build one accepted compatible graph and one deliberately
  mismatched graph for rate, price and variance. Prove the mismatch refuses at
  compile time, compatible legacy graphs retain identity or pass an explicit
  versioned migration, and presentation labels do not become executable types.
- **Migration and rollback:** Version any widened type IDs and keep explicit
  adapters at real conversion boundaries. Do not reinterpret existing graph
  bytes. Rollback leaves migrated versions readable but stops new use.
- **Owner:** `phase6-language-resource-contracts`.
- **Disposition:** `DEFER`; reject a repository-wide type rewrite in V0.
