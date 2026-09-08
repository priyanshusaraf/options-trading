Reference: [section index](../2026-08-29-numeric-and-market-truth-audit.md). Read with its scope; this is not a new assignment.

## NMT-006: inspected identity, causality and capability controls already hold

- **Classification:** `ALREADY CORRECT` for the exact inspected boundaries.
- **Sources:** Kite Connect 3 warns that exchanges may reuse derivative instrument
  tokens after expiry. Freqtrade and pandas support completed-prefix and backward
  alignment checks. The direct repository probes and accepted tests supply the
  implementation countercheck.
- **Repository evidence:**
  - `canonical_decimal` stores strike and multiplier as canonical finite strings.
  - `CanonicalPhysicalInstrument` includes venue, asset class, contract kind,
    currency, underlier, expiry, strike, option right and multiplier.
  - `ProviderInstrumentAlias` keeps token and symbol outside physical identity and
    uses half-open effective intervals; overlap validation catches token, symbol
    and physical remaps.
  - Q03 `instrument_key` reversibly encodes all 256 address bits. The probe
    `probe-full-address-roundtrip.log` decodes the 46-character key to the exact
    32-byte digest.
  - Numeric validity distinguishes missing, stale, unavailable, not-in-session,
    not-listed, no-trade, insufficient-history and invalid values. Alignment
    refuses implicit fill.
  - V0 resampling and timeframe records remain typed refusals. Q03 accepts one
    contiguous spot timeframe, requires completed availability and next-open
    fills, and its inspected prefix test compares full and truncated inputs.
  - Capability profiles separate `RESEARCH`, `PAPER` and `LIVE`, bind provider
    product/contract/conformance evidence, expire, and represent unknown offers.
- **Limit:** These controls do not prove real provider conformance, historical
  contract-master completeness, broader sessions, derivatives or live authority.
- **Smallest safe response:** Preserve them. Do not introduce a second identity,
  provider abstraction, hash, missing-data fallback or resampler.
- **Verification:** Retain full-address round trips, temporal token-reuse
  fixtures, held-contract exit identity, prefix checks, stale capability refusal
  and explicit missing-state mutations under their exact future owners.
- **Migration and rollback:** None for this audit.
- **Owners:** `strategy-os-v0-canonical-research-spine` for the bounded bridge,
  `strategy-os-v0-zerodha-data-static-scope` for real capture and
  `phase6-temporal-resource-catalogue` for broader timeframe/session semantics.
- **Disposition:** `KEEP`; no product change.

## NMT-007: locale remains presentation state; multi-currency input is a future seam

- **Classification:** `ALREADY CORRECT` for canonical V0 currency separation and
  `UX/TRUST FUTURE SEAM` for localized input and display precision.
- **Sources:** Unicode LDML 48.2 separates locale formatting from the currency
  code and warns that a numeric amount without currency context is ambiguous.
  ISO 4217:2015 defines three-letter currency codes and minor-unit relationships.
  The official ISO page was readable through the public index; direct shell
  retrieval returned HTTP 403 and was not bypassed.
- **Assumptions:** V0 is India-first and INR-only. A future locale change may
  alter formatting but not canonical amount, currency, timestamp or address.
- **Repository evidence:** V1 sizing and capital admission carry uppercase
  three-letter currency with integer minor units and ppm rates. The separate V0
  frontend uses `Intl.NumberFormat('en-IN')` and INR symbols for display, while
  the research workspace sends a finite numeric capital assumption. Market-truth
  canonical timestamps normalize to aware UTC. Q03 accepts only whole UTC
  seconds. No inspected display value feeds the canonical hash.
- **Limit:** The frontend currently rounds some displayed INR values to whole
  rupees and uses browser number-input grammar. No accepted multi-currency or
  locale-aware import contract exists, so decimal-comma and DST import behavior
  remain `UNVERIFIABLE`, not silently supported.
- **Smallest safe response:** Keep canonical `{currency, amount_minor}` and aware
  UTC facts. At the real frontend integration gate, label any rounded display and
  reject ambiguous localized import unless an explicit locale and timezone are
  supplied. Use CLDR only for presentation.
- **Verification:** Change display locale/timezone and prove strategy, dataset and
  evidence addresses remain identical; round-trip INR minor units exactly; reject
  ambiguous dates and decimal separators; cover DST only when a global venue is
  in scope.
- **Migration and rollback:** None for V0 canonical storage. A future locale or
  currency expansion needs an additive API/version and explicit conversion facts.
- **Owners:** `strategy-os-v0-frontend-integration-closure` for honest V0 display,
  and `phase11-browser-realtime-contract` for future localized realtime input.
- **Disposition:** `KEEP V0 / DEFER EXPANSION`; no multi-currency promise.

## Rejected responses

This audit rejects a universal Decimal rewrite, a new currency service, a second
canonical serializer, provider tokens as instrument identity, current contract
masters as historical truth, implicit forward fill, same-bar execution, a new
streaming platform, a workflow engine and a repository-wide units framework in
V0. None is the smallest response to the reproduced failures.

## Audit verdict and limits

Verdict: `REFERENCE_AUDIT`.

The packet confirms two current identity/financial bugs, two missing invariants,
one language-contract gap, and two groups of controls that already hold. It does
not fix or accept any finding. It does not establish numerical publication,
provider conformance, historical derivative completeness, deployment, release,
live, order or money authority.
