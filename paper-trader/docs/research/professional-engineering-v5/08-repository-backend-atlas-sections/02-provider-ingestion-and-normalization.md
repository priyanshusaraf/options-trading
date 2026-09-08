Reference: [section index](../08-REPOSITORY-BACKEND-ATLAS.md). Read with its scope; this is not a new assignment.

## Provider ingestion and normalization

`app/market_data/provider_evidence.py:47-220` maps a closed fixture provider contract into canonical evidence. `ProviderObservation`, `NormalizedMarketObservation`, and `DataObservation` are defined in `app/market_data/observations.py:116-422`. The Q03 canonical loader reconstructs exact manifest dependencies in `research/data/canonical_dataset.py:291-658`.

No production route was found that starts with a real provider payload and ends in an accepted V0 canonical manifest. No user CSV import/mapping route was found. Those journeys must be recorded as unavailable, not inferred from model classes.

## Strategy and research execution

- Graph resolution and stable node identity: `app/ir/resolve.py`; component/library authority: `app/ir/library.py` and registry modules.
- Vector/batch evaluator and causal-prefix checks: `app/ir/runtime.py:59-409`; reference streaming: `app/ir/streaming_reference.py`; accepted stateful research runtime: `app/ir/incremental_runtime.py`.
- Published graph bridge: `research/orchestrator/graph_experiment.py:43-222`; existing orchestrator: `research/orchestrator/run.py:124-649`.
- Optimization/validation: `research/pipeline/optimize.py`, `qualify.py`, `validate.py`; statistical evidence: `research/stats/evidence.py`; durable rows: `research/domain/models.py`.
- Current gaps: same-history qualification/OOS contamination, omitted ResourcePlan on the canonical bridge, and under-proved exact optimization reconstruction. Monte Carlo is not integrated and must remain unavailable.

## Signal, money, order, fill, position, reconciliation

The current release stops before this journey. The retained foundation is:

```text
strategy admission/binding
  -> sizing and target request
  -> closed-batch capital admission/reservation
  -> execution intent committed before submit
  -> single broker send / durable acknowledgement when possible
  -> immutable cumulative observations
  -> protection then position booking
  -> exact owner/account/contract reconciliation
```

Representative paths: `app/strategy/admission.py`, `app/core/execution_binding.py`, `app/execution/sizing.py`, `app/execution/capital_admission.py`, `app/engine/live_broker.py:193-325`, `app/engine/execution_lifecycle.py:180-514`, `app/engine/reconcile.py:1-89`, `app/execution/position_lineage.py`, and `app/ledger/service.py`. Capital admission is not wired into a production runner. V0 denial is in `app/core/release_profile.py:213-246` and `app/main.py:256-277`.

## Auth, tenancy, credentials, support, and observability

- HTTP principals are resolved from active, unexpired, unrevoked sessions and active membership in `app/api/principal.py:379-443`; owner IDs are server-derived in route dependencies.
- Worker and outbox queries inspected here carry owner and, where money/account data is involved, broker-account scope.
- WebSocket private channels use server-derived `(owner_id, broker_account_id)` and signed scope-bound cursors (`app/api/routes.py:1197-1263`).
- Credential storage is separate from strategy artifacts under connection/account models and provider stores. No credential values were read.
- Support/admin break-glass behavior was not proved repository-wide. Logs were not exhaustively scanned for payload leakage in this audit.
- Monitoring and release operations live under `app/monitoring/`, `app/platform_operations/`, migrations `0044_v0_monitoring` and `0046_v0_platform_operations`, and deployment documentation. No external monitoring service was exercised.
- CI is repository-defined; backup/restore and deployability are documented but were not executed.

## Representative journeys

Each row records the required identity, time, authority, transaction, retry, recovery, tenant and visible consequence. “Missing” is a result.

### A. CSV/user dataset to evidence

| Step | Identity/time | Truth and transaction | Idempotency/retry/failure/recovery | Tenant/user consequence |
|---|---|---|---|---|
| CSV upload/mapping/admission | **Missing current route** | No accepted durable transaction found | Cannot claim retry or recovery | V0 user cannot import an arbitrary CSV into canonical evidence. |
| Persisted manifest selection | owner + manifest content address; event/availability/recorded times | Research manifest rows plus execution-plane dependency facts; read-only selection | Exact addresses; invalid/missing dependency refuses | User sees exact dataset or a refusal. |
| Backtest/evidence | graph/admission/data/policy/engine/spec identities | Research DB transaction boundaries in orchestrator/repository | Claim token, resume cell, terminal evidence | Results persist; A-001/A-002/A-007 limit identity and validity claims. |

Documentation mismatch: any statement that V0 already supports CSV mapping/admission exceeds code evidence.

### B. Provider data to evaluation

| Step | Identity/time | Truth/transaction | Retry/failure/recovery | Tenant/user consequence |
|---|---|---|---|---|
| Provider fact mapping | provider contract, alias, raw segment, observation address; event/completion/availability/recorded | Fixture-only Phase 4 authority writers | Reject forged/stale dependencies | No general provider-capture claim. |
| Normalization/alignment | normalized observation + rulebook/session/alignment policy | Addressed immutable facts, then derived aligned series | Missing/stale/ambiguous values refuse | Research unavailable rather than silently filled. |
| Graph evaluation | accepted graph/data/evaluation policy | Research execution | Restart requires exact context where incremental path is used | Same-owner evidence; ResourcePlan missing on canonical bridge. |

### C. Graph/version to vector/stream parity

| Step | Identity/time | Truth/transaction | Retry/failure/recovery | Tenant/user consequence |
|---|---|---|---|---|
| Publish/version | owner/project/identifier/version/content address | Immutable graph row; layout separate | Collision/stale revision refuses | Semantic versions remain attributable. |
| Resolve/lower | registry, component versions, node instance/cache IDs | Pure canonical resolver | Deterministic rebuild or refusal | Same executable graph across views. |
| Vector/prefix/stream | graph/data/policy/plan/context/event sequence | Pure/accepted research runtimes | Snapshot reconstructs or refuses | Focused parity exists; repository-wide parity not rerun. |

### D. Optimization lifecycle

| Step | Identity/time | Truth/transaction | Retry/failure/recovery | Tenant/user consequence |
|---|---|---|---|---|
| Operation/claim | owner/project/operation/item/token; queue/heartbeat times | Research operation rows and DB lock | Token heartbeat/reclaim/cancel | Static contract is explicit; current backtest claim-race suite times out and PostgreSQL is unavailable. |
| Trials/candidate | spec, data, seed, params, objective, trial | Research rows | Resume must retain pinned inputs | Search order/is_sharpe/PBO reconstruction under-proved. |
| OOS/walk-forward/Monte Carlo | Fold times and method identity | Current orchestrator | OOS is contaminated; Monte Carlo absent | Locked/untouched OOS and Monte Carlo must not be claimed. |

### E. Signal to reconciled position

| Step | Identity/time | Truth/transaction | Retry/failure/recovery | Tenant/user consequence |
|---|---|---|---|---|
| Authority/sizing/reservation | strategy revision, graph, admission, target, account/book/currency, batch/head | Fenced database transaction | Conflicting/stale snapshot refuses | Deterministic whole-unit admission foundation; unwired. |
| Intent/broker | client intent, broker tag/order ID; signal/intent/submit/ack/fill times | Intent/event DB plus broker | Send once; timeout blocks; exact-tag recovery | No duplicate retry; uncertainty visible/manual. |
| Position/reconcile | exact owner/account/contract/campaign/revision | Ledger/position facts plus broker observation | Duplicate/out-of-order events reduce with anomalies | Terminal conflict B-002 can mislabel a full fill; V0 denies reachability. |

### F. Provider outage/reconnect

Provider-specific adapters contain reconnect behavior, but no provider was opened and no common capability-degradation receipt was exercised. Durable facts remain authoritative; new evaluations must block on stale/insufficient evidence. Exact backoff, subscription churn, and recovery are **unverified**.

### G. Process restart

Research work is reclaimed from durable claim state (`app/main.py:204-251`). Standard execution startup replays the order journal and refuses startup on recovery failure (`app/main.py:330-355`); V0 cannot construct that runner. Safe research restart requires exact input/context reconstruction; safe broker restart requires owner/account/connection/deployment-scoped reconciliation before new entries.

### H. Future Dynamic Watchlist

Only static watchlist code exists in `app/core/watchlists.py`. A replayable future design needs addressed definition, point-in-time input snapshot, ranking method, membership snapshot, hysteresis state, refresh lease, candidate lifecycle, and explicit open-position leave policy. Hot cache loss must rebuild from those facts. No Redis or destructive migration is justified now.
