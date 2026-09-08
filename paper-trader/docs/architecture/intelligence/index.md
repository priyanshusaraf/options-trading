# Strategy OS backend intelligence

Date: 2026-08-31
Baseline: `codex/execution-foundation` at `de6faae3e97cf5537338bee2143350e53f70da1c` plus inherited dirty bytes
Purpose: internal navigation and diagnosis; no release or deployment claim

## Start here

- [Chat 1 Kleppmann handoff](../../research/professional-engineering-v5/12-KLEPPMANN-REAUDIT-HANDOFF-FOR-CHAT-2.md)
- [Broader source catalog](../../research/professional-engineering-v5/13-BROADER-SOURCE-CATALOG.md)
- [Source-to-code matrix](../../research/professional-engineering-v5/19-SOURCE-TO-CODE-MATRIX.md)
- [Confirmed risk register](../../research/professional-engineering-v5/21-CONFIRMED-BACKEND-RISK-REGISTER.md)
- [Implementation gate](../../research/professional-engineering-v5/22-IMPLEMENTATION-CANDIDATE-GATE.md)
- [Future release seams](../FUTURE-RELEASE-BACKEND-SEAMS-AND-ADOPTION-TRIGGERS.md)
- [Scale and measured triggers](../SCALE-50-TO-10000-MEASURED-TRIGGERS.md)
- [Current programme pointer](../../agent/CURRENT.md)

## Product and system context

```mermaid
flowchart LR
    U[Trader / researcher] --> F[Precision Slate frontend]
    F --> A[Versioned authenticated API]
    A --> IR[Canonical IR / editor / registry]
    A --> D[Dataset and market-truth authority]
    A --> R[Research jobs and evidence]
    A --> M[Monitoring-only signals and alerts]
    IR --> R
    D --> R
    R --> E[Immutable result and review evidence]
    IR -. V1 gate .-> X[Execution binding]
    X -. certified authority only .-> B[Execution broker]
    B -. observations .-> O[Orders / fills / reconciliation]
    O --> L[Ledger and position attribution]
    P[Market-data provider] --> D
    P -. never execution authority .-> A
```

V0 ends at research/evidence and monitoring-only alerts. Execution, broker, capital,
orders, positions and money are present as protected foundations but remain denied
to the public V0 profile.

## Current process and deployment topology

```mermaid
flowchart TB
    Browser[Browser] --> FE[Separate Strategy OS frontend]
    FE --> API[FastAPI backend profile]
    API --> ExecDB[(Execution/user PostgreSQL or SQLite test DB)]
    API --> ResearchDB[(Research PostgreSQL or SQLite test DB)]
    API --> LedgerDB[(Ledger PostgreSQL or SQLite test DB)]
    API --> Workers[Bounded in-process / worker job loops]
    Workers --> ResearchDB
    API --> Outbox[Plane-local transactional outbox]
    Outbox --> Delivery[Polling delivery / projections]
    Delivery --> WS[Bounded WebSocket queues]
    Obj[Content-addressed datasets/artifacts] --> ResearchDB
    Provider[Provider adapters] -. V0 data-only / capability gated .-> API
    Broker[Broker adapters] -. V0 denied .-> API
```

No Kafka, Redis, workflow service, analytics database, service mesh or Kubernetes
is part of the accepted topology. The canonical deployment script remains
`paper-trader/scripts/deploy.sh`; this document does not authorize running it.

## Strategy lifecycle

```mermaid
flowchart LR
    Draft[Owned graph draft] --> Edit[Canonical semantic/presentation edits]
    Edit --> Validate[Validator]
    Validate --> Resolve[Pure resolver + component closure]
    Resolve --> Publish[Immutable graph version]
    Publish --> Admit[Research admission]
    Admit --> Plan[Canonical ResourcePlan]
    Plan --> Experiment[ExperimentSpec + durable job]
    Experiment --> Evidence[Trials / folds / result / review]
    Evidence --> Monitor[Monitoring-only admission]
    Monitor --> Signal[Signal transition / alert]
    Signal -. V1 transaction-time gates .-> Execution[Execution binding]
```

Current gap: published-graph experiments do not consume or persist the accepted
`ResourcePlan`. The V0 legacy sweep also bypasses this canonical journey.

## Dataset and market-truth lifecycle

```mermaid
flowchart LR
    Source[Provider/upload source fact] --> Observe[Typed observation]
    Observe --> Normalize[Canonical instrument + field + validity]
    Normalize --> Persist[Immutable segment/object]
    Persist --> Manifest[Owner-scoped manifest + evidence]
    Manifest --> Bind[Canonical dataset binding]
    Bind --> Load[Verified causal loader]
    Load --> Frame[Single candle-to-frame path]
    Frame --> Eval[Research/runtime evaluation]
    Correction[Provider correction] --> Revision[Revision + recorded/publication time]
    Revision --> Persist
    Cutoff[Knowledge cutoff] --> Bind
```

```mermaid
flowchart LR
    Event[event/effective time] --> Complete[completed time]
    Complete --> Available[available/publication time]
    Available --> Recorded[recorded/transaction time]
    Recorded --> Revision[revision identity]
    Cutoff[knowledge cutoff] --> Select{revision admissible?}
    Revision --> Select
    Select -->|yes| Historical[historical result]
    Select -->|no/ambiguous| Refuse[typed refusal]
```

For a completed observation, `available_at < completed_at` is invalid unless the
producer uses a separately declared forming-snapshot contract. The current Q03 path
is narrow and contained; broad real-provider capture is not proved.

## Sources of truth and derived state

```mermaid
flowchart TB
    subgraph Durable authority
      Graph[Graph/version/admission]
      Dataset[Dataset/manifest/provider evidence]
      Spec[Experiment spec/trials/results]
      Intent[Execution intent/attempt]
      Raw[Raw order/fill observations]
      Position[Exact position/tranche ownership]
      Ledger[Ledger events]
      OutboxFact[Transactional outbox fact]
    end
    subgraph Rebuildable or volatile
      Frame[DataFrame/materialization]
      Cache[Evaluation/read cache]
      Runtime[Incremental runtime state]
      Projection[API/WebSocket projection]
      Metrics[Metrics/logs/traces]
    end
    Graph --> Runtime
    Dataset --> Frame --> Cache
    Graph --> Spec
    Dataset --> Spec
    Raw --> Position --> Ledger
    OutboxFact --> Projection
    Durable authority --> Metrics
```

Derived state may accelerate or explain authority. It never replaces authority.
Loss must cause deterministic rebuild or a visible degraded/unavailable state.

## Research job lifecycle

```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Claimed: owner/token/expiry predicate
    Claimed --> Running
    Running --> Checkpointed
    Checkpointed --> Running: resume same spec/build/data/seed
    Running --> Completed: terminal evidence transaction
    Running --> Failed
    Running --> Cancelled
    Claimed --> Pending: expired/reclaimed
    Completed --> [*]
    Failed --> [*]
    Cancelled --> [*]
```

Claim and stale-write predicates exist, but the final current-tree SQLite race test
does not terminate inside 45 seconds and PostgreSQL process-kill/takeover remains
unproved. Do not call this lifecycle release-ready.

## Research selection and evidence boundary

```mermaid
flowchart LR
    Train[Train / warmup] --> Qualify[Qualification]
    Qualify --> Search[Complete candidate population]
    Search --> Select[Selection rule]
    Select --> OOS[Locked OOS]
    OOS --> DSR[DSR/PBO and robustness]
    DSR --> Admit[Evidence/admission decision]
    Peek[OOS access] --> Contaminated[Contaminated / exploratory status]
```

Current legacy `run_experiment` violates this sequence by passing full history to
qualification before later OOS validation. Old evidence must not be relabelled.

## Signal, authority, order, fill and reconciliation lifecycle

```mermaid
flowchart LR
    Eval[Completed causal evaluation] --> Signal[Signal transition]
    Signal --> Explain[Reason / evidence / validity]
    Signal --> Monitor[Monitoring alert, no money authority]
    Signal -. V1 only .-> Request[Sizing request]
    Request --> Admit[Transactional capital admission]
    Admit --> Intent[Durable economic/execution intent]
    Intent --> Attempt[Broker request attempt]
    Attempt --> Unknown{acknowledged?}
    Unknown -->|unknown| Reconcile[Reconciliation required]
    Unknown -->|broker ID| Order[Broker-observed order]
    Order --> Fill[Raw trades/fills]
    Fill --> Position[Exact position/tranche]
    Position --> Ledger[Charges/P&L/ledger]
    Reconcile --> Order
    Reconcile --> NoEffect[Proven no effect]
```

Transport timeout is not rejection. A cancel/complete observation sequence currently
can produce a contradictory `CANCELLED` full fill; this is a V1 execution defect.

## Provider capability and preflight flow

```mermaid
flowchart LR
    Requirement[Graph data/execution requirements] --> Canonical[Canonical instrument roles]
    Canonical --> Binding[Explicit provider/broker binding]
    Binding --> Capability[Versioned capability receipt]
    Capability --> Rights[Range/field/entitlement/data-rights check]
    Rights --> Fresh[Freshness/session/limits/resource check]
    Fresh --> Decision{complete?}
    Decision -->|yes| Dataset[Historical manifest or forward subscription]
    Decision -->|no| Refusal[Typed refusal, no fallback]
```

Provider names, tokens and quirks stay at adapters. A configured but unknown provider
must never fall through to Mock. Current provider pages do not prove conformance,
historical rights or actual account behavior.

## Failure, degraded and recovery states

```mermaid
stateDiagram-v2
    [*] --> Ready
    Ready --> Stale: late/missing input
    Ready --> Degraded: provider/job/cache failure
    Ready --> Ambiguous: external effect timeout/conflict
    Stale --> Ready: fresh complete evidence
    Degraded --> Rebuilding: durable inputs available
    Rebuilding --> Ready: identity and invariant checks pass
    Rebuilding --> Unavailable: missing/corrupt authority
    Ambiguous --> Reconciling
    Reconciling --> Ready: exact observed state
    Reconciling --> Blocked: unresolved external effect
    Unavailable --> [*]
    Blocked --> [*]
```

Degraded mode must not change provider, data, fill or research semantics. Entry
authority fails closed; authorized risk-reducing exits remain available in future
execution profiles.

## Tenancy and security boundaries

```mermaid
flowchart TB
    Principal[Authenticated principal] --> Membership[Membership / role]
    Membership --> Action[Typed authorized action]
    Action --> Repo[Owner-scoped repository predicate]
    Repo --> Object[Project/graph/dataset/job/result/signal]
    Object --> Artifact[Artifact/download]
    Object --> Event[Outbox/WebSocket event]
    Object --> Cache[Owner-complete cache key]
    Support[Operator/support] --> Diagnostic[Redacted diagnostic receipt]
    Diagnostic -. never raw strategy/credential .-> Support
```

Positive same-owner controls and unrelated-owner/private-absence tests are required
for every affected surface. Authentication alone is never object authorization.

## Release and scale sequence

```mermaid
flowchart LR
    V0[V0 research / evidence / alerts] --> V1[V1 controlled execution]
    V1 --> V15[V1.5 discovery + bounded index options]
    V15 --> V2[V2 portfolio / hedge intelligence]
    V2 --> V3[V3 marketplace / managed allocation]
    V3 --> V4[V4 multi-leg / institutional / fund]
    V4 --> V56[V5/V6 enterprise treasury]
    Measure[Measured workload + maturity gates] --> V0
    Measure --> V1
    Measure --> V15
    Measure --> V2
```

V1.1 is retired. Dynamic Watchlists belong to V1.5 under the accepted 29 August
reconciliation. No later box grants implementation authority.

## Subsystem diagnosis

Status vocabulary:

```text
PROVEN WORKING
PROBABLY WORKING BUT UNDER-TESTED
PARTIAL
PLACEHOLDER / NOT INTEGRATED
DOCUMENTATION-ONLY
BROKEN
UNKNOWN
DEFERRED BY DESIGN
```

| Subsystem | Code/source of truth | Inputs/outputs and invariant | Failure/debug entry | Current status |
| --- | --- | --- | --- | --- |
| Auth/session/tenant seam | `app/api/principal.py`, user/membership/session repositories | Server-derived principal/owner; private absence; CSRF/origin/session revocation | Synthetic A/B HTTP tests, membership/session events | `PROBABLY WORKING BUT UNDER-TESTED`; active-socket revocation unspecified |
| Canonical IR/editor | `app/ir`, `app/editor`, graph/version/admission rows | One language/registry/validator/resolver/hash; immutable graph identity | Corpus, resolution, edit/version and mutation gates | `PROVEN WORKING` for accepted bounded catalogue; active frontend integration changes continue |
| ResourcePlan | `app/ir/resource_plan.py` | One plan/policy/calibration; unknown demand refuses | Plan characterization and nine F03 consumers | `PARTIAL`; graph research bridge is `BROKEN` |
| Market truth/observations | `app/market_truth`, `app/market_data` | Canonical physical identity, causal times, validity and provider evidence | Prefix/availability/revision fixtures | `PARTIAL`; impossible completion/availability ordering accepted |
| Q03 canonical dataset bridge | `research/data/canonical_dataset.py`, persisted manifests | Exact one-series NSE/BSE cash 15/30/60m path; no provider fetch/gaps/corrections | Accepted Q03 tests and reopen | `PROVEN WORKING` only for declared narrow scope |
| Legacy backtest sweep | `app/api/backtest_routes.py`, `app/backtest/universe.py` | Standard-profile legacy path; must be denied in V0 | Release-policy RED before dispatch | `BROKEN` V0 boundary |
| Experiment spec/result identity | `research/orchestrator/run.py`, `research/domain/models.py` | Exact graph/data/cost/method/search/seed evidence | Forced collision and restart reconstruction | `PARTIAL`; byte-equality guard absent and optimization reconstruction incomplete |
| Research validity | `research/pipeline`, `research/stats` | Selection-free OOS, complete trial population, explicit method assumptions | OOS suffix mutation, DSR/PBO reconstruction, dependent trades | `BROKEN` confirmatory OOS; other methods `PARTIAL/UNKNOWN` |
| Backtest/research jobs | repositories and operation rows | Durable claim/token/expiry, retry/cancel/checkpoint/finalize | Isolated race, kill/restart and PostgreSQL takeover | `PARTIAL`; current race gate times out |
| Outbox/realtime projection | `app/events/outbox.py`, `delivery.py`, `app/ws/manager.py` | Transaction-bound fact, at-least-once projection, bounded queue | Lost wakeup, duplicate effect, cursor/resync, revoke socket | `PROBABLY WORKING BUT UNDER-TESTED`; full restore/revocation open |
| Monitoring/alerts | programme-owned monitoring capsules | Signal transition distinct from alert/delivery/attention | Restart/dedup/cooldown/stale/review tests | `PARTIAL`; active V0 work outside this packet |
| Provider adapters | `app/providers`, broker/data capability contracts | Canonical identity outside adapter; explicit capability/refusal | Provider-specific fixtures, rate/reconnect/semantic-change | `PARTIAL`; no real conformance/data-rights proof |
| Execution lifecycle | `app/engine/execution_lifecycle.py`, attempts/orders/fills | Raw events immutable; coherent terminal/reconciliation state | Cancel/fill/duplicate/out-of-order property tests | `BROKEN` terminal conflict; `DEFERRED BY DESIGN` from V0 |
| Capital admission | `app/execution/capital_admission.py`, reservations/recovery | One deterministic fenced predicate; risk reduction exempt | PostgreSQL simultaneous/restart/unknown-submit | `PLACEHOLDER / NOT INTEGRATED`; foundation exists |
| Position and ledger attribution | execution/position/ledger rows and services | Exact strategy/deployment/revision/tranche; full charges; no duplicate effects | Partial close/netting/reconciliation/conservation | `PROBABLY WORKING BUT UNDER-TESTED`; no live claim |
| Database migration/restore | execution/research/ledger migrations and restore contracts | Expand-contract, exact heads, backup/restore/reconstruction | Zero/current-state migration, rollback, three-plane restore | `UNKNOWN` for current release environment |
| Frontend product journey | separate `/Users/priyanshusaraf/dev/strategy-os-frontend` | One typed client over canonical facts; explicit Unknown/error/refusal | Type/test/build and safe browser journey | `PARTIAL`; concurrently owned by V0 convergence task |
| Scale/capacity | ResourcePlan, workers, DB pools and measurement receipts | Admission from measured demand; no user-count architecture | [Scale trigger document](../SCALE-50-TO-10000-MEASURED-TRIGGERS.md) | `UNKNOWN`; no production-shaped baseline |

## How to debug without creating false evidence

1. Read `CURRENT.md`, matching programme stage and exact capsule.
2. Freeze hashes and attribute inherited bytes before mutation.
3. Identify the durable source of truth and its identity.
4. Reproduce one concrete failure with a small fixture or concurrent history.
5. Keep source principle, repository observation and inference separate.
6. Run focused checks from the documented entry point and keep failed harness logs.
7. Do not infer PostgreSQL, provider, browser, restore or deployment behavior from
   SQLite/unit tests or prose.
8. Stop at live, money, schema, dependency, provider, deployment and legal gates.

## Known next steps

1. Serialize V0 correction capsules for OOS isolation, legacy-route denial and the
   existing F03 ResourcePlan bridge.
2. Add collision-safe experiment recipe comparison under a separate identity slice.
3. Reconcile the inherited claim-race timeout before relying on job fencing.
4. Complete reports 23–25 after authorized implementation decisions are known.
5. Run the exact release/security/deployability matrices before any release claim.
