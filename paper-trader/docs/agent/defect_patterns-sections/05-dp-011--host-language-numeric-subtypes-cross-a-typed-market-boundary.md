Reference: [section index](../DEFECT_PATTERNS.md). Read with its scope; this is not a new assignment.

## DP-011 — Host-language numeric subtypes cross a typed market boundary

- Severity: Critical when coercion can influence dataset identity, research
  results, sizing, routing, execution price, or money behavior.
- Status: CLOSED at the finite direct local boundary. Python and installed
  NumPy boolean scalars refuse before assigned OHLCV values can create research
  or backtest dataset, cache, signal, sizing, or executable-price authority.
  Valid finite hashes, bytes, addresses, objects, types, and causal behavior
  remain compatible. Direct guards fail under mutation and restore exactly.
- Closure evidence: `.agent/runs/phase1-4-foundation-direct-closure/foundation_direct_numeric_owner/`,
  `.agent/runs/phase1-4-foundation-direct-closure/root/recheck-root-numeric-research.log`,
  and independent recheck SHA-256
  `d43994cc2d4d1d6e9b827a0f6169a1a75128b24d862e3ac3461ded7fca153069`.
- Incident: foundation audit A-02 passed `True` as candle open. Raw candle
  validation converted it to `1.0`, dataset preparation retained it, and the
  malformed value became executable input.
- Root cause: candle validation, sweep preparation, and binary dataset encoding
  call `float(value)` before inspecting the source type. Python and NumPy treat
  boolean values as numeric subtypes, so the closed typed numeric envelope
  receives an ordinary float after the original type evidence has disappeared.
- Prevention invariant: one authoritative market-number conversion inspects the
  raw source before coercion. Python `bool` and boolean scalar values are never
  OHLCV numbers. Every assigned provider, normalization, dataframe, preparation,
  storage, identity, cache, causal, evaluation, sizing, and execution-price
  ingress calls the rule or consumes a value already certified by it. Storage
  revalidates before minting bytes or an address.
- Searched surfaces: `backend/app/market_data/candles.py`,
  `backend/app/backtest/dataset_store.py`, `backend/app/backtest/identity.py`,
  `backend/app/backtest/sweep.py`, cache and repository entry points, provider
  controls, NumPy/pandas conversions, binary and JSON encoding, causal
  evaluation, signal handoff, sizing, and execution-price boundaries. The
  correction must repeat the search after final product bytes freeze.
- Permanent regression: inject `True`, `False`, and boolean scalars into every
  OHLCV field through every registered assigned path. No case may mint dataset
  bytes, an address, cache entry, result, signal, sized request, or executable
  price. A compatibility corpus must prove byte-identical encoding and
  addresses for all ordinary finite values accepted before the correction.
  Kill and restore the shared boolean guard and one caller adoption; both
  mutations must fail.
- Invalidation rule: any assigned raw ingress that coerces before the shared
  guard, any boolean case that reaches identity or effects, any change to valid
  finite bytes or addresses, or any changed numeric product byte makes the
  affected causality, cache, result, execution-containment, package, and review
  claims `STALE/REQUIRES RECHECK`.
- Owner: `phase1-4-foundation-direct-closure` owns the shared numeric rule,
  every assigned caller including research materialization, direct evidence,
  bounded correction, integration, and independent review.
- Evidence requirements: refreshed review package SHA-256
  `0e67dfcebb0b85161efa34501a8a3a6a953c4bed5a9e66bc93b2ffe481a56cfc`,
  exact command metadata, killed/restored mutation logs, and reviewed current
  source/test hashes under the direct-closure evidence root.

## DP-012 — Producer-chosen fixture baseline mistaken for independent selection authority

- Severity: Critical when the evidence controls migration, persistence,
  research-integrity, authority, deployability, or review acceptance.
- Status: CONTAINED. The invalid replay and its successor fail closed. Root
  accepted the authority-gap diagnosis and retired the blanket exact-literal
  mutation model. Authority partition architecture, fresh correction evidence,
  transitive revalidation, and independent review remain open.
- Incident: the PostgreSQL 16 trigger-fixture evidence model treated
  `fixture-owner-v1` as an exact expected fact. Its DDL authority requires only
  `VARCHAR(64) NOT NULL`; it does not select that literal over the equally legal
  `fixture-owner-v2`. A complete, internally consistent substitution with all
  derived hashes resealed could be rejected only by comparing against the
  producer's own frozen baseline. The proposed independent consumer therefore
  shared the producer's unsupported selection assumption.
- Root cause: freezing and hashing a legal producer choice was mistaken for
  authority that independently selected that exact choice. Source facts,
  root-selected facts, external observations, free candidate choices, derived
  values, and relational constraints were collapsed into one byte-equality
  rule. The source-authority registry then derived its expected literal from
  the artifact it was meant to judge.
- Violated invariant: an expected exact value must be selected by authority
  independent of the candidate and every same-model derivative that records
  it. Candidate-chosen legal values must be judged by their type, range,
  checks, keys, foreign keys, owner consistency, and cross-record relations,
  not by equality to one producer baseline.
- Why prior evidence missed it: producer, registry, mutation driver, and
  consumers shared the same frozen fixture values. Hundreds of thousands of
  local mutations could prove stale-edit detection while never exercising a
  fully resealed, semantically equivalent candidate. Aggregate counts hid the
  missing independent authority boundary.
- False assumption: a deterministic producer choice becomes an independent
  exact fact once it is serialized, hashed, copied into a registry, and checked
  by another program.
- Prevention invariant: classify every expectation as `SOURCE_EXACT`,
  `ROOT_EXACT`, `EXTERNAL_OBSERVATION_EXACT`, `CHOICE_VARIABLE`, `DERIVED`, or
  `RELATIONAL_CONSTRAINT` before defining mutations. Reject an unresealed local
  tamper, an illegal fully resealed candidate, and a fully resealed change to a
  true source-exact semantic fact. Accept a legal fully resealed
  reparameterization and a canonical nonsemantic reordering. A derived digest
  must be recomputed and cross-bound, but baseline digest equality receives no
  independent semantic credit.
- Searched surfaces and current result: the blocked architect traced the
  trigger-fixture authority, provenance, source registry, mutation registry,
  producer, validators, aggregate receipts, and successor capsule. The exact
  owner-literal witness proves the flaw. The replay never launched, PostgreSQL
  never opened, the work-in-progress consumers receive zero credit, and no
  product, test, migration, runtime, or deployability byte is accepted by this
  incident record. The fresh recovery must repeat the search across every
  fixture literal, generated identifier, default, digest, count, ordering fact,
  source fact, and external observation.
- Permanent regressions: (1) substitute a legal choice throughout a complete
  candidate, reseal every derived binding, and require a separately authored
  lower-authority consumer to accept it; (2) make an illegal choice and fully
  reseal, then reject it at the named type or relational consumer; (3) change a
  true source-exact semantic fact and fully reseal, then reject it from an
  independently reconstructed source; (4) make an unresealed local tamper and
  reject it; (5) reorder canonically unordered data and accept equivalent
  meaning; (6) omit or misclassify one authority leaf and reject the evidence
  package. Each case records changed-state and exact-restoration receipts.
- Adversarial generalization: apply the same fully resealed substitution to
  producer-selected fixture rows, generated IDs, owner labels, synthetic
  timestamps, ports, paths, sequence starts, corpus values, and derived counts.
  Ask whether the producer and validator can share one wrong assumption, and
  include the analogue of a claim marked complete after checking only a subset
  of its declared universe.
- Transitive evidence map: fixture-selection authority -> trigger-fixture
  source/provenance/package and mutation contracts -> semantic package and
  complete PostgreSQL evidence -> native-state and migration evidence ->
  numeric/transitive foundation package -> independent Critical review ->
  Phase 1-4 acceptance -> combined Phase 5/6 planning. Every downstream PASS
  that used blanket baseline equality is `STALE/REQUIRES RECHECK` until the
  fresh route closes its named gate.
- Proportionality: block false acceptance of material authority and research
  claims. Do not require redundant permutations once an independently derived
  equivalence partition proves the complete concrete universe. Rederive case
  counts after the authority partition; never preserve `391840` as an axiom.
- Owner: `phase1-4-foundation-postgresql16-semantic-trigger-fixture-mutation-authority-partition-recovery`
  defines the corrected evidence architecture. A fresh trigger-fixture evidence
  correction owner implements it only after root same-byte acceptance.
  Transitive revalidation and one Critical reviewer alone can restore the
  Phase 1-4 acceptance chain.
- Evidence: root acceptance
  `.agent/runs/phase1-4-foundation-critical-closure/postgresql16-semantic-trigger-fixture-contract-evidence-authority-gap-acceptance.json`
  SHA-256
  `ff90300f5466dea943c635c2a33ee0a419c349db16f4add6e4b3cd54f9966d56`;
  blocker
  `.agent/runs/phase1-4-foundation-postgresql16-semantic-trigger-fixture-contract-evidence-repeated-failure-recovery/foundation_postgresql16_semantic_trigger_fixture_contract_evidence_repeated_failure_architect/authority-gap-blocker.json`
  SHA-256
  `06b0bbbd9424f048d81458992ca3c7becdcdaf65d95fff279d1e41a7e5cd70ab`;
  blocked report and manifest SHA-256
  `78a7894776ed30266259057a16fdc40ac759f63bb87cbd931922e1af7bda61c6`
  and
  `60a6b3ee1b6a2a0a2572931e8deae6c36649542ccf39b352a918d7b067c041db`.
