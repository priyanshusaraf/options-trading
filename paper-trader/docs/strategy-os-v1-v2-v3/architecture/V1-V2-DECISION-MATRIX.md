# V1 to V2 architecture decision matrix

> **Scope timing superseded.** Rows that defer Dynamic Watchlists, bounded reference/events, activation planning or chart semantics conflict with the 24 August hybrid addendum. Use [V0–V6 scope matrix](../V0-V1-V1.5-V2-V3-V4-V5-V6-SCOPE-DECISION-MATRIX.md) for current targets. Retain this file only as prior architecture evidence.

## Decision rule

A V1 change is justified only when at least one condition holds:

- current V1 correctness or safety needs it;
- a current persisted fact would otherwise need destructive reinterpretation;
- an existing V1 interface would block an additive V2 implementation;
- a small seam now removes a future authority split.

A V1 change is rejected when it only pre-builds V2 behavior.

## Findings

| ID | Decision | Current evidence | Disposition | Product timing | Invariants and required proof | Future home |
| --- | --- | --- | --- | --- | --- | --- |
| A-01 | Bind a new deployment to an immutable static Universe snapshot | Deployment stores mutable watchlist_id and mode | REFACTOR | must change in V1 | Old deployments retain legacy behavior; snapshot uses canonical instrument addresses; mutation mints a new version; replay proves exact members | v1-static-universe-version-binding |
| A-02 | Keep editable watchlists as aliases, not authority | Watchlists are useful UI and organizing facts | KEEP + HARDEN | must change in V1 | Editing an alias cannot mutate a running binding | v1-static-universe-version-binding |
| A-03 | Add dynamic filters, rankings, top-K, hysteresis, and staged scans | No product implementation exists | DEFER | V2 | Point-in-time data, membership event, rank tie-break, and budget tests precede implementation | v2-dynamic-universe-engine |
| A-04 | Add set, map, cross-section, and ranked-set types through the existing v2 registry | Type references and exact many-input assemblies already exist | KEEP + HARDEN | safe extension seam already exists | Deterministic ordering, canonical instrument addresses, exact type matching, no wildcard, stable tie-break | v2-cross-sectional-type-pack |
| A-05 | Create a second screener DSL | One IR and registry are hard invariants | REJECT | never | A screener view must consume the same Universe graph and evaluation receipt | none |
| A-06 | Give Universe, Strategy, Workflow, and Deployment separate durable identities | Current Strategy and Deployment are separate; Universe and Workflow are not | REFACTOR | must change in V1 architecture | No product object may impersonate another; references use exact versions and addresses | v1-product-object-boundaries |
| A-07 | Let a Workflow invoke research, admission, and deployment through one command interface | Durable research operations and deployment services exist | KEEP + HARDEN | must change in V1 | Workflow cannot write authority or money tables; every command is idempotent and produces a receipt | v1-workflow-invocation-boundary |
| A-08 | Build a general visual Workflow builder | No V1 need | DEFER | V2 | Start with deterministic templates and measured user demand | v2-workflow-templates |
| A-09 | Add a durable candidate-instance identity | Current deployment and intent facts lack discovery lineage | REFACTOR | must change in V1 | Identity joins Universe evaluation, rank, research, approval, deployment, signal, intent, and fill | v1-dynamic-candidate-lineage |
| A-10 | Add durable portfolio admission batches | Current allocator returns in-memory funded and skipped lists | REFACTOR | must change in V1 | Candidate set frozen; deterministic policy; why-not receipt; account scope; idempotent replay | v1-portfolio-admission-reservation |
| A-11 | Add account capital reservations | No reservation table or state machine exists | REFACTOR | must change in V1 | Account lease remains owner; transactionally admitted amount; fence epoch; expiry; broker reconciliation; risk-reducing exits never blocked | v1-portfolio-admission-reservation |
| A-12 | Keep current priority-subset policy as safe default | Current allocator is deterministic and never resizes | KEEP + HARDEN | must change in V1 evidence | Freeze rank tuple and policy version in each batch | v1-portfolio-admission-reservation |
| A-13 | Add silent proportional resizing | User intent and current policy reject this | REJECT | never as default | Resizing requires explicit group semantics and sizing rule | future opt-in only |
| A-14 | Complete operational canonical-instrument adoption | Canonical Phase 4 types exist; legacy Instrument remains provider-shaped | KEEP + HARDEN | must change in V1 | Provider tokens never enter strategy identity; held position keeps exact physical contract | v1-canonical-instrument-operational-binding |
| A-15 | Preserve data-provider and execution-broker separation | Connection and broker registry already split roles | KEEP + HARDEN | must change in V1 completion | Split routing, account ownership, capability checks, and conformance for every supported broker | v1-five-broker-capability-closure |
| A-16 | Mark five target brokers complete | Kite and Dhan execute; Upstox is data only; Groww and Angel One are planned | REJECT current claim | must change in V1 implementation | Each adapter must pass exact role conformance and lifecycle evidence | three broker-specific capsules |
| A-17 | Add a dynamic subscription planner | Data requirement plans and capability profiles provide a clean insertion point | DEFER | V2 | Desired versus actual state, quotas, priority, hysteresis, held-position protection, restart | v2-subscription-resource-planner |
| A-18 | Add dependency-driven multi-rate runtime | Current normal evaluation is whole-graph; causal prefix evaluator exists | KEEP + HARDEN | safe seam exists, implementation V2 | Runtime plan stays derived; graph identity unchanged; state schemas versioned; vector and incremental parity | v2-multi-rate-runtime |
| A-19 | Rewrite V1 runtime for performance now | No profile supports the need | REJECT | wait for V2 measurements | Record realistic cross-sectional workload before any runtime change | v2-runtime-capacity-spike |
| A-20 | Add non-OHLCV product support now | Owner deferred it | DEFER | V2 | New versioned data-domain contract, point-in-time publication/revision semantics, storage and replay | v2-external-data-domains |
| A-21 | Mutate candle identity and blob formats in place for new data | Existing identities are stable V1 evidence | REJECT | never | Add new versioned schemas and readers | v2-external-data-domains |
| A-22 | Add immutable external-artifact dependency references | Current binding has exact addresses for known domains but no generic chart artifact | KEEP + HARDEN | safe seam in V1 architecture | Dependency kind, schema version, owner, address, validity interval, and material-change rules | v1-external-artifact-dependency-seam |
| A-23 | Build semantic chart annotations | Absent and not required for V1 | DEFER | V2 | Strategy OS owns identity and semantics; chart vendor owns rendering only | v2-chart-thesis-artifacts |
| A-24 | Add TradingView webhooks | External signals have no public typed ingress | DEFER | V2 | Authenticate, freshness check, deduplicate, map to normal admission; never direct order | v2-external-signal-ingress |
| A-25 | Extend replay beyond candles | Current ReplayProvider is candle only | DEFER | V2 | Versioned event envelope with event, knowledge, availability, correction, Universe membership, and artifact changes | v2-general-event-replay |
| A-26 | Package a reconstruction receipt | Identity ingredients exist across several facts | KEEP + HARDEN | must change in V1 architecture | Exact export, independent runner, first-divergence result, licence check | v1-reconstruction-receipt-export |
| A-27 | Replace current durable research operations with a workflow dependency | Current operations already provide leases and checkpoints | REJECT without spike | can wait for V2 | A bounded non-money kill/restart spike must outperform current contract and preserve domain identity | v2-durable-work-backend-spike |
| A-28 | Use DBOS, Temporal, or Restate in the live order path | Generic durable work cannot prove broker exactly-once behavior | REJECT | never without separate critical evidence | Orders remain Strategy OS domain commands, events, leases, and reconciliation | none |
| A-29 | Adopt the standalone frontend prototype directly | Frontend implementation is owner-gated | DEFER | future V1 frontend capsule | Connect canonical APIs, preserve accepted styling, prove behavior, accessibility, desktop and 390 px | v1-frontend-prototype-adoption |
| A-30 | Add Kafka, Kubernetes, or a new database now | No measured need | REJECT | demand dependent | Measured failure or capacity evidence must force the change | exact future evidence only |
| A-31 | Add MT5, Bloomberg, international markets, and meta-strategies | Demand not proven | DEFER | V3 | Commercial, licence, legal, rulebook, and unit-economics gates | V3 owner decision |

## Persisted-schema hazards

The following existing shapes must not become the permanent V2 authority:

- Deployment.universe_mode plus watchlist_id as the only Universe identity.
- WatchlistMembership as a mutable execution binding.
- ExecutionIntent constrained to one ENTRY without a parent decision batch.
- BacktestRun.instruments as comma-separated current symbols.
- UniverseInstrument.key as both product identity and provider-facing legacy key.
- DatasetStore's fixed candle blob as a universal data format.
- ReplayProvider's candle JSON as a universal event record.
- Flat provider capability booleans as complete Strategy Preflight.

The safe migration pattern is additive:

1. Add new immutable facts and nullable references.
2. Keep legacy rows on the legacy path.
3. Mint new authority only through the new path.
4. Dual-read for compatibility, never dual-write across authorities.
5. Prove exact old behavior before switching new writes.
6. Refuse ambiguous backfills.
7. Retire legacy write paths only after an explicit release gate.
