Reference: [section index](../08-REPOSITORY-BACKEND-ATLAS.md). Read with its scope; this is not a new assignment.

# Strategy OS repository backend atlas

Baseline: branch `codex/execution-foundation`, HEAD `de6faae3e97cf5537338bee2143350e53f70da1c`, plus inherited dirty bytes. This is a read-only map of current code. It is not a clean-HEAD, deployed, live, or production-readiness claim.

## Process and dependency boundaries

| Boundary | Current implementation | Authority / dependency direction |
|---|---|---|
| Browser client | TypeScript/React/Vite under `frontend/src/` | Presentation only. It calls the API and consumes derived realtime frames; it has no durable authority. |
| HTTP/realtime service | Python FastAPI assembly in `backend/app/main.py:71-194,430-448`; routes under `backend/app/api/` | Routes resolve principal/owner and call application/domain services. WebSockets are disabled in V0. |
| Execution domain | `backend/app/engine/`, `app/execution/`, `app/ledger/` | Legacy/internal broker and money seams. V0 boot refuses execution-worker authority. |
| Canonical strategy runtime | `backend/app/ir/`, especially schema, registry, resolver, hashing, ResourcePlan, batch and incremental runtimes | One canonical graph/registry/resolver/hash. Research bridges depend on this layer; IR must not depend on broker/runner/database sessions. |
| Research domain | `backend/research/` plus research routes | Orchestration, datasets, operations, optimization, validation and evidence. It consumes accepted IR/data authority. |
| Data and market truth | `backend/app/market_data/`, `app/market_truth/`, `app/providers/` | Strategy OS owns canonical instruments; provider mappings/evidence are separate inputs. Provider and broker roles remain separate. |
| Persistence | SQLAlchemy models in `backend/app/db/models.py`; execution Alembic chain in `backend/migrations/`; research migrations in `backend/research/domain/migrations/` | Execution, research, and ledger database URLs are checked as distinct when enabled (`app/main.py:91-124`). SQLite and PostgreSQL code exist; PostgreSQL was not available in this audit. |
| Durable change delivery | `backend/app/events/outbox.py`, `delivery.py`, `planes.py`, producer modules | A transaction-bound outbox per plane. PostgreSQL notifications are hints; durable polling/cursors are authority. |
| Deployment | `paper-trader/scripts/deploy.sh` | Sole sanctioned deploy path. Not run. |

No Redis, Kafka, Celery, dedicated message broker, or workflow engine appears in the declared application topology. No need for one was proved.

## Durable authorities by domain object

| Domain object | Current durable authority | Derived/recoverable views | Limits |
|---|---|---|---|
| User, organization, membership, session | Account/session/membership rows in `app/db/models.py`; resolution in `app/api/principal.py:379-466` and browser auth under `app/accounts/` | Request principal | WebSocket connected-session revocation is unspecified outside V0 denial. |
| Broker/provider connection | Owner-scoped connection/account rows and `app/providers/connection_store.py` | Adapter/client objects | No credential or provider connection was opened. |
| Canonical instrument/provider alias | Phase 4 authority facts loaded by `app/market_data/instruments.py`, `observations.py`, `dataset_authority.py` | Provider tokens and labels | Current accepted V0 dataset subset is narrow. |
| Market-truth snapshot/rulebook | Addressed rulebook, session, alias, observation, correction, and snapshot facts under `app/market_truth/` and `app/market_data/` | Aligned bars / canonical datasets | General completed/available invariant and correction projection gaps are KPV5-A-004/A-006. |
| Dataset segment/manifest | `ResearchDatasetSegmentV2`, `ResearchDatasetManifestV2`, links and canonical bytes in the research plane | `CanonicalDataset`/DataFrame | No current user CSV upload/mapping/admission journey was found. Existing V0 route selects persisted manifests. |
| Strategy graph/version/layout | Owner-scoped immutable graph/version rows; separate presentation rows through editor/product routes | Resolved graph and UI layout | Presentation contamination is explicitly refused in graph experiment provenance. |
| Admission receipt | Immutable strategy admission artifact and stored mirror | Verified runtime/research admission object | Research ResourcePlan is missing on the published graph route. |
| Experiment spec/run/trial/evidence | Research-domain rows in `research/domain/models.py` | Reports, plots, caches | Spec collision, OOS contamination and reconstruction gaps are KPV5-A-001/A-002/A-007. |
| Job/operation lifecycle | Backtest run/resume-cell rows and research operation/item rows | Worker-local objects | PostgreSQL failover/takeover unproved here. |
| ResourcePlan | Immutable canonical resource document plus policy/calibration identities | Recompiled accepted research plan | Not consumed by canonical graph experiment, KPV5-B-001/F03. |
| Deployment/binding | Deployment, strategy receipt, binding and release-profile facts | Runner configuration | V0 requires API-only, paper, empty live assignments. No live authority. |
| Capital/admission | Capital state, reservation head, batch/candidate/decision/reservation/event rows | Held-pending digest | Deterministic foundation is unwired; paper recovery only. |
| Order/fill lifecycle | Immutable execution intent and order-event rows plus broker order book | Reduced `ExecutionState`, in-memory pending maps | Terminal observation conflict KPV5-B-002; live provider behavior untested. |
| Position ownership | Position/campaign/tranche/ledger facts scoped to owner/account/strategy revision | Cockpit summaries | Exact contract and revision attribution are preserved in foundation; broker net views cannot transfer ownership. |
| Realtime projection | Plane outbox, cursor and receipts plus durable domain rows | Per-process invalidator and bounded WebSocket queues | Can lag/resync; cannot authorize business state. |

## Jobs, queues, caches, schedulers, and retry rules

- Backtest jobs: `app/backtest/repository.py:332-570,692-900` owns claim, heartbeat, pinned reads, resume cells, cancellation, completion and failure. Database predicates and tokens, not the Python worker, are intended to own state. The current first SQLite claim-race test times out and blocks a final working claim.
- Research operations: `research/domain/operations.py:283-989` owns pending/running/terminal states, owner quotas, item claims, heartbeat, cancellation and evidence binding.
- Outbox delivery: `app/events/delivery.py:193-288` polls bounded batches, heartbeats a lease, records effect receipts and backs off to a 30-second maximum.
- WebSocket queue: `app/ws/manager.py:69-168` keeps two latest-wins slots plus a 200-frame bounded deque per client; slow sends are evicted after ten seconds.
- Backtest caches: `app/backtest/cache.py:45-124` are derived, owner-scoped, and identity-bound for inspected Phase 4 inputs. Complete consumer coverage was not proved.
- Scheduling: no shared priority scheduler proves P0/P1 isolation. V0 has no live protection worker; V1 must measure before adopting new infrastructure.
