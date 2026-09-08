# Numeric and market-truth reference application

Date: 29 August 2026. Owner task:
`01a04e7e-0dc6-74e0-92af-bc64725d9877`.

## Corpus continuity

This review preserves the accepted corpus lineage:

- 373 first-party records before and after;
- no HTML recrawl;
- 2,016 existing one-hop records remain triaged;
- no competing manifest or registry;
- no claim that DDIA second-edition book text was read.

The packet selected nine public external artifacts and one direct repository
evidence group. Public access permitted analysis and citation. No external code,
book text, PDF or data was copied into tracked paths.

## Exact source receipts

| Source ID | Exact identity and location | Access and licence evidence | Receipt |
| --- | --- | --- | --- |
| `RFC8785_JCS_2020` | RFC 8785, June 2020, sections 3.2.2.3, Appendix B and Appendix D | Public RFC; IETF Trust legal provisions in the artifact; analysis only | body SHA-256 `63d52294eb0e3f0014174288186d388b4ddbf2c67d1ce8af1d9726eb0c3ab240` |
| `PYTHON_DECIMAL_3_13_15` | Python 3.13.15 `decimal` documentation, Decimal construction, Context, rounding modes and `quantize()` | Public official documentation; no code reuse or new dependency; Python documentation terms not treated as implementation permission | body SHA-256 `af64c18f9b57328647ac6890c829f423d6fca4a70be5cf39d2f2ba253c618c61` |
| `PANDAS_MERGE_ASOF_3_0_5` | pandas 3.0.5 `merge_asof`, backward direction and tolerance | Public official API documentation; no code reuse; tag `v3.0.5` resolves to commit `e68db09ecf6427d1b62e565bacf17f2e525a3032` | body SHA-256 `1e80cb2752a42018c674989c3813eadafce1cc97b0e6ca1358898ccc80369e13` |
| `FREQTRADE_LOOKAHEAD_2023_6` | Freqtrade tag `2023.6`, commit `eea95f79aac8a77758dfbde52f681c7d86a7d7b7`, `docs/lookahead-analysis.md` | Public GitHub tag; GPL-3.0 licence inspected; reference behavior only and no code copied | doc SHA-256 `e2b946cbf71f3dbd615033890f14409a9ad8ab3ff7febae71e6001c44b2d5d6e`; licence SHA-256 `589ed823e9a84c56feb95ac58e7cf384626b9cbf4fda2a907bc36e103de1bad2` |
| `ZERODHA_KITE_INSTRUMENTS_V3_20260829` | Kite Connect 3, Market quotes and instruments, instrument list and token-reuse note | Public official provider documentation; no API call, credential, private data or reuse licence inferred | body SHA-256 `63c947c4c6c1f32fe64c2bca1e127efa10d864b74bbcad86b4298d3a3282a453` |
| `ZERODHA_CHARGES_20260829` | Zerodha public charges page captured 2026-08-29 | Public official broker page; dynamic schedule, analysis only; not historical or contract-note proof | body SHA-256 `a93bf79732b9b6d4f6df756f14d05bb4a94d08a5951a20439d874aafb` |
| `UNICODE_LDML_NUMBERS_48_2` | Unicode Technical Standard 35, LDML Part 3, version 48.2, currency formatting and parsing | Public stable specification governed by Unicode Terms of Use; no CLDR data vendored | body SHA-256 `43aed410d67e349c0550b0d5fb36a36636e60ee7324efa57f068d8c668d2860a` |
| `ISO_4217_2015_PUBLIC` | ISO 4217:2015 Edition 8 public overview, currency code and minor-unit scope | Official indexed overview read; ISO states codes may be used free of charge; direct shell access returned HTTP 403 and was not bypassed; standard text not read | access receipt SHA-256 `dd11db406ba29c9af00e1a02accacebcf7c5a2654b4162ef12e709fec8e5688a` |
| `NASA_MCO_PHASE2_2000` | Mars Climate Orbiter Phase II report, root-cause units section | Public NASA report; direct PDF access succeeded; analysis only and no report text vendored | remote PDF SHA-256 `a533a8acd3637446d238dd55c8509ec30a9ecf29e552527820192087569d154d` |
| `STRATEGY_OS_NUMERIC_MARKET_TRUTH_PROBES_20260829` | Six direct probes at repository HEAD `de6faae3e97cf5537338bee2143350e53f70da1c` | Internal evidence; read-only imports and pure construction, no product tests or writes | individual hashes in the refresh report |

The pandas retrieval label says `3-0-4`, but the captured official page identifies
itself as 3.0.5. The registry records 3.0.5. The two failed shell receipts for ISO
and the NASA landing page contain only access errors. The NASA PDF digest receipt
uses the successful public report URL.

## Source admission decisions

| Claim | Independent or conceptual source | Official implementation source or direct experiment | Decision |
| --- | --- | --- | --- |
| Snapshot identity must preserve `recorded_at` separately from cutoff | RFC 8785 invariant representation; accepted Kleppmann stream-processing packet | `probe-market-truth-snapshot-identity.log` | `IMPLEMENT IN SEPARATE CAPSULE` as `NMT-001` |
| Completed observations cannot be available before completion | Freqtrade lookahead failure model | pandas backward as-of semantics and `probe-availability-order.log` | `DEFER TO EXACT CAPTURE OWNER` as `NMT-002` |
| Negative zero needs one declared identity | RFC 8785 Appendix B | `probe-negative-zero-identity.log` | `IMPLEMENT IN SEPARATE CAPSULE` as `NMT-003` |
| Financial charges need current, versioned rates and explicit rounding | Python Decimal monetary and rounding contract | current Zerodha page and `probe-charge-boundaries.log` | `IMPLEMENT IN SEPARATE CAPSULE` as `NMT-004` |
| Compiler-visible units must survive a port boundary before output chaining | NASA MCO interface-units failure | `probe-unit-type-erasure.log` | `DEFER TO PHASE 6` as `NMT-005`; current wrong-result path unverified |
| Provider tokens must not become physical identity | Kite Connect 3 token-reuse warning | temporal alias code and `probe-full-address-roundtrip.log` | `KEEP` as `NMT-006` |
| Locale formats a currency amount but does not define its currency | Unicode LDML 48.2 and ISO 4217 public overview | fixed-point currency code/minor-unit code inspection | `KEEP V0 / DEFER EXPANSION` as `NMT-007` |

## Rejected interpretations

The sources do not justify a universal Decimal conversion, RFC 8785 adoption as a
second serializer, a new units dependency, multi-currency V0, current tokens as
historical contract truth, real broker access, a provider connection, a new data
platform or any change to live execution.

The current Zerodha page proves only the public schedule captured on 29 August
2026. It does not prove past rates, actual contract-note rounding, private account
fees or future rates. The ISO standard text and DDIA second-edition book text were
not available and are not cited as read.

## Verification state

The source and claim records are complete only when JSON/YAML/JSONL parsing,
source-ID links, claim-ID uniqueness, local Markdown links, two-source chains,
architecture validation and protected-byte attribution all pass. Product findings
remain open under their named owners even after this reference packet validates.
