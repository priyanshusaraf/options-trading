Reference: [section index](../codex-supervisor-review-2026-08-09.md). Read with its scope; this is not a new assignment.

## 10. Security and tenancy threat model

The code scan found no high-severity secret pattern in `backend/app` or `frontend/src`. The harness scan reported 54 Twilio-key matches, all npm package-lock integrity strings in generated Claude worktrees. They are false positives. Local `.env` and `access_token.json` are ignored by Git, but both have mode `0644`; other local users can read them.

### Highest-priority STRIDE cases

| Threat | Current path | Risk | Required control | Owner |
|---|---|---:|---|---|
| Spoofing | Optional shared bearer token; no user identity | Critical for commercial V1 | OIDC/passkeys or managed auth, short sessions, MFA for execution, service principals | Identity |
| Elevation of privilege | Wildcard owner policy and no resource ownership | Critical | Owner columns, membership, one policy engine, deny-by-default scopes | API/security |
| Tampering | Journal writes can fail while order placement continues | Critical | Mandatory durable entry intent, append-only events, integrity checks | Execution |
| Repudiation | No immutable fill/event history or actor on many changes | High | Actor, request ID, event ID, timestamps, immutable audit log | Platform |
| Information disclosure | Tenantless objects/caches; credentials in world-readable local files | High | Tenant-keyed queries/caches, encrypted secret references, `0600`, log redaction | Platform/ops |
| Denial of service | Unbounded or heavy jobs share the process with exits | High | Bounded reads, durable job state, quotas, separate execution loop resources | Runtime |
| Cross-account execution | `Deployment.account_id` is an unbound string | Critical once accounts multiply | Foreign keys to owner-scoped broker accounts and activation-time capability checks | Execution |

Before any hosted pilot, run migrations that backfill the legacy owner, enforce ownership at the database query boundary, move secrets to a secret manager or OS key store, and separate customer research workloads from the money-management loop.

## 11. External reference decisions

Only primary repositories, official documentation, or the local review prose informed these decisions.

| Reference | Licence | Classification | Decision |
|---|---|---|---|
| Strategy OS IR, resolver, graph versions, authority | Project code | **DIRECT REUSE** | Extend the existing spine. A second graph, validator, hash, research ledger, or authority is rejected. |
| React Flow / xyflow | MIT | **DIRECT REUSE when the graph editor needs it** | Use it as a view layer. Keep layout beside semantic graph content. It is not yet a dependency. |
| QuantConnect LEAN | Apache-2.0 | **REFERENCE ONLY** | Its separate data-handler and brokerage interfaces, brokerage events, and durable security identifiers support the connection-role and canonical-contract direction. Do not import a C# trading engine into this Python product. [Repository](https://github.com/QuantConnect/Lean), [data interface](https://github.com/QuantConnect/Lean/blob/master/Common/Interfaces/IDataQueueHandler.cs), [brokerage interface](https://github.com/QuantConnect/Lean/blob/master/Common/Interfaces/IBrokerage.cs). |
| NautilusTrader | LGPL-3.0 | **REFERENCE ONLY** | Use its event-sourced order/fill, reconciliation, instrument-ID, deterministic-clock, warmup, and reset lessons. Do not introduce its engine or Rust core. [Repository](https://github.com/nautechsystems/nautilus_trader). |
| vn.py | MIT | **REFERENCE ONLY** | Its `BaseGateway` and separate order/trade events confirm thin venue gateways. Direct reuse would create a second engine and Chinese-market vocabulary. [Gateway](https://github.com/vnpy/vnpy/blob/master/vnpy/trader/gateway.py). |
| OpenAlgo | AGPL-3.0 | **REFERENCE ONLY; REJECT CODE REUSE** | Learn adapter shape, Indian broker problem catalogues, mapping, and stream recovery. Hosted AGPL obligations conflict with the commercial path. [Repository](https://github.com/marketcalls/openalgo). |
| Prefect | Apache-2.0 | **REFERENCE ONLY** | Adapt the idea of declarative cache policies. Reject a workflow dependency and graph-by-executing-Python model. |
| vectorbt | Apache-2.0 plus Commons Clause | **REJECT DEPENDENCY** | Hosted commercial restriction is incompatible. Its vectorized research ideas may inform independently written code. |
| Backtrader / Freqtrade | GPL-3.0 | **REJECT CODE REUSE** | No unsolved need justifies a second strategy/runtime model or copyleft dependency. |
| Upstox official API | Proprietary service API | **ADAPT-WRAP** | Write a thin local adapter from official contracts. Use `instrument_key`, not reusable exchange tokens; v3 historical candles have explicit unit/interval paths. [Instruments](https://upstox.com/developer/api-documentation/instruments/), [Historical V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/). |

Upstox’s official documentation says `instrument_key` is the stable API identifier and exchange tokens may be reused after expiry. That supports an opaque provider-mapping table and rejects `exchange:symbol` as the universal provider key.

## 12. Required modification sequence

### Slice 0: close proven correctness gaps

1. Fix token-latch recovery against concrete Kite behaviour.
2. Separate candle transport success from usable-frame freshness.
3. Add the `KiteProvider -> SafePaperKite` construction invariant and remove raw Kite SDK use from the read-only reconciliation script.
4. Make the DSR breadth score either decide promotion or remove the false claim; then schedule an independent statistical audit before admission uses DSR.

### Slice 1: runtime connection-role composition

1. Add explicit runtime role bindings for market data, execution, account, and resolver.
2. Preserve today’s one-Kite configuration as the compatibility case.
3. Change broker construction to consume the execution/account binding, not infer it from the market-data provider.
4. Prove distinct market-data and execution connections through tests.
5. Do not add Upstox code in this slice.

### Slice 2: canonical contract and provider mappings

1. Introduce canonical economic contract identity for underlying, equity, option, and future.
2. Persist provider mappings with opaque provider keys and validity/version provenance.
3. Move Kite symbology off canonical `Instrument` only after two resolvers prove equivalent Kite behaviour.
4. Make `ResolvedInstrument` carry opaque addressing; remove the universal `exchange:symbol` method.

### Slice 3: durable order and fill identity

1. Add decision, intent, order-leg, order-event, and fill entities.
2. Make entry intent persistence mandatory.
3. Add idempotent, out-of-order event reduction and account-scoped recovery.
4. Keep `Position` and `Trade` as economic/accounting projections.
5. Migrate existing journal rows without rewriting history.

### Slice 4: second data adapter

1. Implement Upstox history and quotes only.
2. Use official v3 interval semantics and provider instrument keys.
3. Pass the shared conformance contract and runtime role-selection proof.
4. Live API verification remains an owner credential gate.

### Slice 5: product lanes

1. Add typed product intent and a broker capability matrix.
2. Implement delivery with CNC lifecycle and corporate-action handling.
3. Implement live futures open/close and remove tolerated paper inheritance.
4. Implement MTF last, after funding interest, settlement, corporate actions, broker product support, and reconciliation are complete.
5. Add multi-leg intent before spreads or hedged strategies.

### Slice 6: commercial tenancy

Land tenant ownership, connection/account storage, authorization, secret management, tenant-keyed caches, job quotas, and migration backfills before a second customer receives access. This can progress beside product lanes after the shared data model is settled, but it must finish before commercial V1.

### Slice 7: research throughput and cache correctness

Content-address datasets, fetch once per instrument/interval/window, share frames across strategies, reuse pure graph nodes, batch writes, and benchmark again. Add concurrency only after the serial I/O waste is removed.
