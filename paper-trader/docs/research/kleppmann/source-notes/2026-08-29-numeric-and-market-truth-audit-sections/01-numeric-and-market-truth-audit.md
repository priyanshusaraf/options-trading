Reference: [section index](../2026-08-29-numeric-and-market-truth-audit.md). Read with its scope; this is not a new assignment.

# Numeric and market-truth audit

Date: 29 August 2026. Capsule: `kleppmann-numeric-and-market-truth-audit`.
Repository HEAD at inspection: `de6faae3e97cf5537338bee2143350e53f70da1c`.

## Scope and method

This packet continues the accepted 373-record first-party inventory and the
2,016-record one-hop triage. It did not rerun either collection. It used selected
lawful public sources, the accepted Kleppmann packet, direct code inspection and
six isolated read-only probes. It changed no product, schema, test, dependency,
frontend, programme, provider, deployment, live, order or money byte.

Every disposition below follows this chain:

```text
source and assumptions
-> repository failure hypothesis
-> current code and evidence countercheck
-> smallest safe response
-> falsifiable verification
-> migration and rollback
-> exact owner
```

The high-risk findings use an independent or conceptual source plus an official
implementation source or direct experiment. A source does not authorize a code
change. The source receipts and probe hashes are recorded in the professional
reference registry and refresh report.

## Evaluation clocks and numeric domains

The audit treats these as different facts:

- `event_time`: the market event or bar-open label;
- `completed_at`: the instant the declared observation is complete;
- `available_at`: the earliest instant the observation can be consumed;
- `recorded_at`: the instant Strategy OS recorded the fact;
- `knowledge_cutoff`: the latest information admitted to a snapshot;
- monotonic elapsed time: process-local duration only.

Research signals consume completed observations available at the decision time.
Current Q03 fills a decision at the next bar open. Locale and display timezone do
not enter canonical strategy, dataset or evidence identity.

The numeric audit separates analytical binary64 values from financial and
identity values. Analytical indicators may use finite binary64 under their
declared formulas. Money, charge schedules, currency, quantity, rate scaling,
rounding policy and canonical decimal identity need explicit domain contracts.

## NMT-001: snapshot identity drops `recorded_at`

- **Classification:** `CONFIRMED CURRENT BUG` in reconstructible market-truth
  identity. No live or provider behavior was exercised.
- **Sources:** RFC 8785, sections 3.2 and Appendix B, requires one invariant
  representation before hashing. The accepted *Making Sense of Stream
  Processing* packet, pages 82-100 and 152-164, keeps source facts and derived
  state distinct. The repository probe is the required direct countercheck.
- **Assumptions:** `recorded_at` and `knowledge_cutoff` are distinct causal facts.
  Two snapshots may admit the same cutoff while being recorded at different
  instants.
- **Failure hypothesis:** If `recorded_at` is absent from canonical bytes, two
  distinct snapshots can share an address. Loading the bytes can then invent a
  different `recorded_at`, so the original causal fact cannot be reconstructed.
- **Repository evidence:** `app/market_truth/rulebook.py:123-139` omits snapshot
  `recorded_at` from `fact()`. Lines 174-178 pass `knowledge_cutoff` into both the
  `recorded_at` and `knowledge_cutoff` constructor positions. The probe
  `.agent/runs/kleppmann-numeric-and-market-truth-audit/owner/probe-market-truth-snapshot-identity.log`
  creates snapshots recorded at 01:00 and 01:30 with the same 02:00 cutoff. They
  have identical bytes and addresses, and a round trip returns 02:00 as
  `recorded_at`.
- **Consequence:** A source publication or capture order can be lost inside an
  apparently valid content address. Any later point-in-time explanation can
  report a timestamp that was never the original recording fact.
- **Smallest safe response:** Under a separate product capsule, define an
  additive snapshot schema that includes both times in canonical bytes. Refuse
  new authoritative use of ambiguous old snapshots unless independent source
  evidence reconstructs the missing fact. Do not rewrite old addresses.
- **Verification:** Prove that changing only `recorded_at` changes bytes and the
  address; round trip preserves both timestamps; copied SQL columns match the
  bytes; an isolated mutation that aliases the two fields fails; old ambiguous
  rows fail closed for new authority.
- **Migration and rollback:** Inventory stored v2 rows first. Add a new schema and
  forward-read path rather than mutating immutable v2 bytes. Rollback stops new
  writes but retains any new immutable rows. It must not map them back to the old
  address.
- **Owner:** `strategy-os-v0-canonical-research-spine` before its market-truth
  binding closes, with `strategy-os-v0-zerodha-data-static-scope` consuming the
  corrected contract before real capture.
- **Disposition:** `IMPLEMENT IN SEPARATE CAPSULE`; this audit makes no fix claim.

## NMT-002: observation authority accepts availability before completion

- **Classification:** `MISSING INVARIANT`. The current inspected alignment
  consumer is already safe, so no current lookahead result is claimed.
- **Sources:** Freqtrade 2023.6 lookahead analysis explains that full-frame future
  access can falsify a backtest. pandas 3.0.5 `merge_asof` defines backward
  matching as selecting a key less than or equal to the decision key. The direct
  probe checks the Strategy OS boundary.
- **Assumptions:** A completed-bar observation cannot be available as that
  completed value before `completed_at`.
- **Failure hypothesis:** Persisted authority that says `available_at` precedes
  `completed_at` is internally false. A future consumer that checks availability
  alone could use the completed value early.
- **Repository evidence:** `app/market_data/observations.py:22-29` requires both
  completion and availability after event time but does not order them against
  each other. `DataObservation` repeats that incomplete rule at lines 294-300.
  The probe `probe-availability-order.log` constructs a five-minute observation
  available after one minute. Construction succeeds. The current
  `align_observation` at lines 344-376 still blocks the row until both clocks have
  passed. Q03 separately requires `available_at == completed_at`.
- **Consequence:** Current alignment does not leak. The authority contract still
  admits an impossible causal fact that could mislead a future loader, capability
  receipt or external export.
- **Smallest safe response:** At the real-capture boundary, require
  `available_at >= completed_at` for completed observations and preserve delayed
  availability when the provider publishes later. Keep instant observations on
  an explicit instant-observation contract rather than weakening the bar rule.
- **Verification:** Add constructor, persistence and loader refusals for
  availability-before-completion; prove delayed availability blocks until the
  real instant; append future data and show prior outputs do not change; kill an
  isolated mutation that removes the ordering check.
- **Migration and rollback:** First inventory whether any persisted facts violate
  the rule. Until that inventory exists, migration impact is `UNVERIFIABLE`.
  Preserve old bytes as evidence and exclude invalid rows from new authority.
- **Owner:** `strategy-os-v0-zerodha-data-static-scope` before any real capture or
  provider capability activation.
- **Disposition:** `DEFER TO EXACT OWNER`; current Q03 equality and alignment
  guards remain unchanged.
