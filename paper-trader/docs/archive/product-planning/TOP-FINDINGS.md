# Top findings

> **Timing superseded on 24 August 2026.** Repository findings remain evidence. Product targets and capsule order now come from the hybrid addendum, revised progress mapper and scope matrix. In particular, Dynamic Watchlists and bounded chart/reference/event work are V1.

These are the material findings that govern the proposed sequence. They are recommendations only. Each proposed change still needs its owner gate, capsule, implementation evidence, migration proof, rollback proof, and deployability update.

## F1: a mutable watchlist can define a deployment's instrument set

- Severity: High.
- Final priority: MUST FIX BEFORE DEPENDENT FEATURE WORK.
- Evidence: a deployment can retain `watchlist_id` while membership remains editable. The current records do not freeze the exact eligible set for that deployment.
- Relevant prior art: LEAN separates Universe selection from subscriptions; DVC Data shows child-first immutable publication; Freqtrade documents the historical bias risk of current dynamic pairlists.
- Strategy OS files: `paper-trader/backend/app/db/models.py`, `paper-trader/backend/app/core/watchlists.py`, `paper-trader/backend/app/core/deployments.py`, and `paper-trader/backend/app/core/deploy_bridge.py`.
- Failure scenario: F-016. Editing a watchlist changes the effective members below an existing deployment, so research and operations can no longer reconstruct the same set.
- Recommendation: keep editable watchlists as aliases and bind every new deployment to an immutable, content-addressed static `UniverseSnapshot`.
- Required tests: edit-after-bind, member-order permutation, canonical-instrument substitution, held-position removal, old-row compatibility, PostgreSQL install/upgrade/restart, and rollback or restore.
- Migration and rollback: add nullable version and snapshot references. Keep old rows on the legacy path. Do not infer historical snapshots. Stop new writes to the legacy path only after parity evidence.
- Current backend safety: current foundation work can continue. Dynamic Universe implementation must wait for this boundary.

## F2: portfolio admission and capital use have no durable batch or reservation fact

- Severity: Critical.
- Final priority: MUST FIX BEFORE DEPENDENT FEATURE WORK.
- Evidence: `allocator.py` returns funded and skipped candidates in memory. The account lease provides a strong single-writer base, but no durable record reserves capital between admission and broker outcome.
- Relevant prior art: Optuna separates study, trial, storage, and state transitions; Hummingbot separates policy from order execution and preserves lost-order states; OpenFGA and Casbin reinforce explicit scoped decisions without becoming money authority.
- Strategy OS files: `paper-trader/backend/app/engine/allocator.py`, `paper-trader/backend/app/engine/runner.py`, `paper-trader/backend/app/core/execution_book.py`, and `paper-trader/backend/app/db/models.py`.
- Failure scenarios: F-001, F-003 through F-009, and F-011.
- Recommendation: persist `DecisionBatch`, `CandidateIntent`, `AdmissionDecision`, and `CapitalReservation`. Let the account lease holder mutate reservations in one PostgreSQL transaction. Keep priority-subset as the default and refuse silent resizing.
- Required tests: two-actor contention, stale fence, crash before send, ambiguous broker outcome, partial fill, cancel-fill crossing, manual broker order, atomic basket, and exit during ARM or reservation block.
- Migration and rollback: add new tables and nullable intent references. New-path writes stop cleanly on rollback; existing execution rows remain authoritative. Live sizing, routing, and risk semantics require an owner decision.
- Current backend safety: non-dependent foundation work can continue. Broader live concurrency and dynamic candidate admission must wait.

## F3: dynamic candidates lack one durable lifecycle identity

- Severity: High.
- Final priority: MUST FIX BEFORE DEPENDENT FEATURE WORK.
- Evidence: deployment names and intent identifiers cannot join discovery rank, Universe evaluation, Strategy version, research policy, admission, deployment, signal, intent, and fill.
- Relevant prior art: LEAN models Universe selection as first-class state; Kestra pins nested invocations; Airflow preserves execution history against graph versions.
- Strategy OS files: `paper-trader/backend/app/core/deployments.py`, `paper-trader/backend/app/core/deploy_bridge.py`, `paper-trader/backend/app/core/research_read.py`, and `paper-trader/backend/app/db/models.py`.
- Failure scenarios: F-017, F-023, and F-025.
- Recommendation: define a content-addressed `CandidateInstanceAddress` that references exact immutable inputs but never becomes deployment or execution authority.
- Required tests: duplicate discovery, one material-input change, two Workflows selecting the same instrument, owner substitution, stale approval, duplicate command delivery, and signal-to-fill attribution.
- Migration and rollback: add nullable lineage references for new rows. Leave manual and legacy static deployments explicit with null lineage. Never synthesize historical discovery facts.
- Current backend safety: static V1 flows can continue. Workflow-driven candidate creation must wait.

## F4: operational instrument use has not completed the move to canonical identity

- Severity: High.
- Final priority: HIGH-PRIORITY HARDENING.
- Evidence: Phase 4 defines canonical physical instruments and effective provider aliases, while operational paths still expose provider-era symbol fields.
- Relevant prior art: CCXT distinguishes shared intent from native capability; LEAN uses stable security identifiers; DhanHQ and Kite SDKs show why provider transport identifiers must stay at adapter edges.
- Strategy OS files: `paper-trader/backend/app/market_truth/identity.py`, `paper-trader/backend/app/market_truth/authority.py`, `paper-trader/backend/app/providers/instrument_resolver.py`, `paper-trader/backend/app/core/instruments.py`, and `paper-trader/backend/app/db/models.py`.
- Failure scenarios: F-012, F-013, F-040, and F-041.
- Recommendation: use canonical physical addresses on new operational paths and preserve the legacy `Instrument` model as an adapter until exact parity passes.
- Required tests: Kite parity, two-provider mapping, token reuse intervals, symbol rename, observation-target versus execution-target separation, and held-contract identity after selector change.
- Migration and rollback: add nullable canonical references, dual-read for compatibility, and keep one authority for new writes. Refuse ambiguous backfills.
- Current backend safety: current Phase 4 closure can continue. New broker completion should depend on this boundary.

## F5: the five-broker V1 target remains incomplete

- Severity: High.
- Final priority: HIGH-PRIORITY HARDENING.
- Evidence: the registry honestly supports Kite and Dhan execution, Upstox data, and planned Groww and Angel One states. It does not support a five-broker completion claim.
- Relevant prior art: CCXT's native, absent, emulated, and constrained capability states; OpenAlgo's broker breadth as product evidence; official Dhan, Upstox, Groww, Angel One, and Kite contracts.
- Strategy OS files: `paper-trader/backend/app/providers/brokers.py`, `paper-trader/backend/app/providers/capabilities.py`, `paper-trader/backend/app/providers/factory.py`, and `paper-trader/backend/tests/provider_conformance.py`.
- Failure scenarios: F-042 through F-044.
- Recommendation: preserve data-provider and execution-broker separation. Close each missing role in a separate adapter capsule against current official contracts and mutation-tested capability claims.
- Required tests: authentication rotation, instrument mapping, field and history limits, order types, protection, correlation, partial fill, cancel and replace, reconnect, restart reconciliation, and split routing.
- Migration and rollback: provider and configuration changes may require additive schema and service changes. A failed adapter remains refused in the registry. Credentials and production connections stay owner-gated.
- Current backend safety: all unrelated V1 work can continue. Do not label the target complete until every named role passes.

## F6: reconstruction ingredients exist, but no closed receipt proves the full causal chain

- Severity: High.
- Final priority: HIGH-PRIORITY HARDENING.
- Evidence: graph, admission, dataset, binding, signal, intent, event, and fill identities exist across separate facts. No packaged export runs an independent reference path and reports the first divergence.
- Relevant prior art: DVC Data's content-addressed publication, OpenLineage's explicit lineage events, and Hypothesis's generated counterexamples.
- Strategy OS files: `paper-trader/backend/app/backtest/identity.py`, `paper-trader/backend/app/market_data/dataset_authority.py`, `paper-trader/backend/app/core/execution_binding.py`, `paper-trader/backend/app/core/execution_book.py`, and `paper-trader/backend/app/ir/streaming_reference.py`.
- Failure scenarios: F-035 through F-037 and F-070.
- Recommendation: assemble a closed reconstruction receipt from existing authority facts, add licence-aware export, run an independent reference evaluator, and report first divergence rather than final-P&L equality alone.
- Required tests: the three canonical acceptance scenarios, simultaneous contention, corrupted artifact, missing dependency, changed provider mode, fee mismatch, and equal final P&L with earlier divergence.
- Migration and rollback: an export-only first slice is compatible. New retained receipt tables require additive migration and retention policy. Rollback must leave source facts unchanged.
- Current backend safety: current work can continue, but broad reconstructibility and release claims remain rejected.

## F7: browser transport state can be mistaken for market-data health

- Severity: Medium.
- Final priority: HIGH-PRIORITY HARDENING.
- Evidence: the backend models more health facts than the current client exposes. The browser can report a connected socket without proving authorization, subscription acceptance, first data, or freshness.
- Relevant prior art: XState makes state transitions explicit; Hummingbot distinguishes active, cached, and lost operational states; Centrifugo and NATS provide fan-out references without becoming domain truth.
- Strategy OS files: `paper-trader/backend/app/ws/manager.py`, `paper-trader/backend/app/engine/health.py`, and `paper-trader/frontend/src/state/LiveContext.tsx`.
- Failure scenarios: F-045 through F-049.
- Recommendation: expose separate transport, authorization, subscription, snapshot, freshness, and provider-health states. Preserve one WebSocket and backend-owned truth.
- Required tests: connected-with-no-first-event, stale feed on live socket, reconnect snapshot, out-of-order sequence, slow client, coalesced state frame, and durable order-event non-coalescing.
- Migration and rollback: compatible API and frontend state change if old fields remain during transition. Frontend implementation remains owner-gated.
- Current backend safety: backend work can continue. The UI must not make stronger health claims before this contract lands.
