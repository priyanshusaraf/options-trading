# Temporal and identity model audit

Date: 2026-08-31\
Scope: current repository bytes, canonical V0 research path, and legacy reachability\
Verdict: FAIL for complete V0 research truth; strong bounded foundations retained

## Time vocabulary

| Term | Current representation | What it may prove | What it may not prove |
| --- | --- | --- | --- |
| Event time | `event_time` on observations; bar-open label in Q03 | The market interval an observation describes | When the completed value became knowable |
| Completion time | `completed_at` | Earliest instant a completed interval could exist under the declared resolution | Provider publication or local receipt |
| Availability/publication time | `available_at` | Declared earliest instant the value could be consumed | Truth of that declaration without provider evidence |
| Recording/ingestion time | `recorded_at` | Strategy OS evidence custody | Original publication time |
| Effective time | rulebook and provider half-open intervals | When a rule, contract, or alias applies | When Strategy OS learned the revision |
| Knowledge cutoff | market-truth snapshot | Latest included recorded revision | Market completeness outside the snapshot scope |
| Replay cutoff | canonical selection `as_of` | Server-checked dependency and row cutoff | A guarantee that captured timestamps match real historical publication |
| Processing time | run/job lifecycle clocks | Operational execution timing | Market event order or executable identity unless explicitly bound |
| Elapsed time | monotonic process clock where correctly used | Duration on one process | Cross-node or durable business order |

`published_at` is not a separate field. The current model treats `available_at` as the knowability boundary and `recorded_at` as local custody. Any provider whose publication and delivery differ needs direct evidence or an additive distinction; the code must not backdate availability to completion for convenience.

## Identity matrix

| Identity | Answer-changing inputs currently bound | Status | Failure if omitted |
| --- | --- | --- | --- |
| Canonical physical instrument | authority namespace/version, venue, asset class, contract kind, currency, underlier, expiry, strike, right, multiplier | CLEAN | Today's token or selector can replace the actual contract |
| Provider product/contract/alias | provider entity/product, mode, rights evidence, temporal token/symbol mapping, adapter schema, observation namespace | CLEAN structurally | Provider remap or token reuse changes economic meaning |
| Market-truth snapshot | schema v3, effective range, recorded time, knowledge cutoff, quality, reconstruction, instruments, revisions, source evidence | CLEAN after NMT-001 | A snapshot reports knowledge it did not contain or cannot reconstruct its recording fact |
| Provider observation | exact raw segment/range/digest, mapping, token, field, resolution, event/completion/availability/recording, validity, correction | AT RISK | Availability can precede completion |
| Normalized observation | provider input addresses, transform, policy, algorithm, market truth, field/resolution, four times, numeric validity, correction lineage | AT RISK | Same ordering gap; general consumer drops revision metadata |
| Dataset segment/manifest | owner, bytes, rows, instruments, fields, event/availability ranges, gaps, corrections, provider inputs, transforms, truth, policies, algorithms, evidence, created/recorded | CLEAN structurally | Mutated dataset or policy can reuse old evidence |
| Canonical Q03 binding | full manifest/instrument/segment/object addresses, `as_of`, time interpretation, adapter, cash cost/sizing projection | CLEAN WITH NARROW SCOPE | Provider fallback, hash truncation, or future rows enter a run |
| Authored graph | canonical IR bytes and content address | CLEAN in inspected v1/v2 paths | Presentation or mutable draft changes executable meaning |
| Resolved/implementation graph | registry snapshot, implementation closure, declarations, resource/data plan | CLEAN in Phase 4 binding | Same authored graph runs with different semantics under one identity |
| Legacy ordered dataset | provider/instrument context, interval, windows, ordered OHLCV bytes | AT RISK outside Phase 4 | Rulebook, adjustment, historical universe, or publication policy may be absent |
| Backtest execution result | dataset, admission, strategy/source, parameters, costs, event/exit/premium policies; optional Phase 4 binding | CLEAN when Phase 4 is present; AT RISK on legacy route | Old result is reused after semantic change |
| Experiment recipe | programme, hypothesis, build, strategy, params, datasets, costs, charge schedule, gates, seed, method versions, graph provenance | VIOLATED on collision handling | Run points to a different immutable recipe |
| Optimization trial | fold, params, objective, IS/OOS trade counts, selected | PARTIAL | Search population/statistics cannot be reconstructed exactly after code change |
| Static scope revision | immutable membership address under owner/project/scope revision | CLEAN structurally | Present membership replaces point-in-time selection |
| Legacy provider-derived universe | current dump or curated fallback | VIOLATED for V0 canonical-only truth if reachable | Survivorship, current tokens, grids, lots, or membership enter historical research |

## What changes executable strategy identity

The inspected canonical path changes identity for:

- authored semantic graph bytes;
- component semantic versions and registry snapshot;
- implementation closure/source;
- resolved graph and declared data/resource plan;
- admission receipt;
- exact dataset manifest, physical instrument, truth snapshot, policies, algorithms, source evidence, and replay cutoff;
- parameters, capital, cost/slippage/sizing, event/exit/premium assumptions;
- method versions, seed, and build.

Presentation state is separately stored and does not enter graph identity. Current tests cover this split.

The legacy experiment spec reduces the canonical recipe digest to 128 bits and does not compare stored bytes on reuse. That is the direct identity violation in KPV5-A-001.

## Revision and correction behavior

Rulebook resolution uses effective intervals plus the latest `recorded_at` not later than `knowledge_cutoff`. It refuses gaps and ambiguous latest revisions. Market-truth v3 preserves its own recording fact separately from cutoff.

Provider observations form an explicit `supersedes_address` chain. Normalized observations carry correction lineage. The canonical Q03 loader walks prior provider revisions to prove their cutoff but rejects any normalized correction lineage for its initial subset.

The general `DataObservation` alignment seam does not carry `recorded_at`, `supersedes`, or correction lineage. It cannot choose the latest known revision when two observations share event/completion time. It returns no result for an equal-rank tie. This is safe refusal but leaves the broader revision model incomplete.

## Forming and higher-timeframe bars

- General alignment requires `completed_at <= evaluation at` and policy `COMPLETED_ONLY`.
- Q03 requires `completed_at = event_time + resolution` and `available_at = completed_at`.
- Canonical graph provenance refuses context/session/multi-timeframe requirements outside the admitted subset.
- IR prefix checks and an independent completed-prefix evaluator compare vector and stream semantics.
- Backtest trades enter at the next bar open.

Status: CLEAN for the tested subset. Forming-bar semantics, provider delayed publication, real sessions, and higher-timeframe aggregation remain unavailable, not proven.

## Missing-state model

The numeric validity contract distinguishes valid, missing, stale, provider unavailable, not listed, not in session, no trade, insufficient history, and invalid states. Alignment accepts only `VALID`; Q03 refuses gaps and nonvalid values. NaN, infinity, boolean-as-number, incoherent OHLC, negative volume, implicit fill, sorting, deduplication, and repair refuse.

Status: CLEAN for current constructors and the canonical loader.

## Point-in-time universe and rulebook

Immutable static-scope revisions and typed market-truth records provide the long-term seam. The Q03 subset names exactly one physical instrument and never resolves it from a current provider symbol.

The legacy sweep remains reachable under the V0 route policy and calls `liquid_universe` or `full_universe`, which use today's provider dump or a curated fallback. That path has no point-in-time universe or historical rulebook binding. This is KPV5-A-003.

## Required next proofs

1. Refuse or canonically route the V0 legacy sweep.
2. Correct spec collision behavior with compatibility evidence.
3. Seal qualification/train/embargo/OOS boundaries before any selection.
4. Inventory observation producers before enforcing availability-after-completion.
5. Characterize exact search-space and PBO/DSR reconstruction from stored facts.
6. Keep Monte Carlo, provider capture, derivatives, corporate actions, historical universe membership, and forming bars unavailable until their exact owners provide evidence.

No current file proves complete historical contract masters, corporate-action handling, point-in-time index membership, real provider publication latency, or universal session coverage. Those rows remain `UNVERIFIABLE`, not clean.
