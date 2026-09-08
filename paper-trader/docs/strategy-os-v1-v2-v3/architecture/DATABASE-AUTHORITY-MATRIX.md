# Database authority matrix

## Decision

Keep three physical database authorities:

1. execution database: control, user, market-authority copies, and real-money operational facts;
2. research database: research definitions, jobs, trials, evidence, and authoritative research dataset manifests;
3. journal ledger database: the trader's journal snapshot, binary artifacts, and captured manual fills.

The journal ledger database is not the canonical order, fill, position, or capital ledger. Those live in the execution database's MONEY plane.

Do not use synchronous dual-writes across databases. Use a durable outbox and idempotent consumer when one plane needs a verified copy or projection.

## Matrix

| Entity | Authoritative database and plane | Only permitted writer | Derived copies | Consistency and lag | Transaction and reconciliation | Backup, restore, retention |
| --- | --- | --- | --- | --- | --- | --- |
| Users, organizations, memberships, sessions | execution, USER | authentication and membership repository | redacted UI session | synchronous per request | active user, organization, membership checked together | user backup and PITR; session retention bounded |
| Broker accounts and connections | execution, MONEY | owner-scoped connection repository | redacted UI connection view | synchronous; credential reads at command time | account owner predicate plus encrypted credential; revoke through outbox | strict backup, audit, key-rotation plan |
| Project and Strategy aliases | execution, USER | project and graph repository | navigation projections | synchronous | optimistic revisions | user-plane backup and export |
| Immutable graph versions | execution, USER | graph publication service | research address references | immutable | one content address; no in-place edit | permanent while referenced |
| Component and node versions | repository registry plus immutable graph bodies; execution USER where stored | platform registry and publication service | descriptor projections | release-bound | registry snapshot and implementation closure | artifact retention follows referenced graph |
| Layout and presentation | execution, USER | layout repository | browser view state | optimistic, non-authoritative | separate revision from semantic graph | user backup; may prune orphan archives by policy |
| UniverseDefinition | execution, USER, proposed | Universe publication service | current screener alias | immutable version | same graph registry and content hash | retain while snapshot or deployment references it |
| UniverseEvaluation | research, proposed | Universe evaluator under research operation lease | execution-side verified snapshot copy by outbox | eventual across planes; no live claim before copy verifies | exact definition, data, truth, capability, policy | research evidence retention |
| UniverseSnapshot for deployment | execution, USER or MONEY binding copy, proposed | deployment preflight consumer | UI member view | synchronous with deployment creation after verification | verify research source before local copy; bind by content address | retain for deployment and trade attribution |
| WorkflowDefinition | execution, USER, proposed | Workflow publication service | UI template catalogue | immutable version | content address and stable step identifiers | user-plane backup |
| WorkflowInstance | execution, USER control, proposed | Workflow command coordinator | research operation and deployment step references | durable step progression; cross-plane effects eventual | each step commits one local receipt then emits command | retain through review and audit period |
| Raw market data | object or market storage plus execution MARKET metadata | provider ingestion | research dataset segments | append or content addressed | raw bytes verified before manifest publication | cheapest durable tier; replay rights and licence govern retention |
| Normalized market observations | execution, MARKET authority | normalization service | research segment references | immutable correction chain | source, transform, truth, policy, time, validity | retain while any dataset manifest references them |
| Dataset segments and manifest | research | dataset authority service | verified execution copy or address | immutable; execution copy after verification | child segments verify before parent manifest | evidence-grade retention; object garbage collection only after reachability proof |
| Market truth and rulebook | execution, MARKET authority | market-truth authority service | research references | immutable point-in-time snapshots | no current-rule substitution | retain all referenced versions |
| Provider conformance and capability profile | execution, MARKET authority | conformance and capability services | deployment preflight view | expiry and change-level aware | assessment binds one complete offer per requirement | retain through dependent deployment and review |
| Research programme and hypothesis | research | research repositories | summary UI | synchronous in research plane | owner scoped | user research retention |
| ExperimentSpec | research | experiment publication service | execution admission references | immutable | exact graph and dataset identities | permanent while evidence or deployment refers |
| ExperimentRun | research | claimed research worker | UI progress | durable claim; heartbeat lag bounded by policy | lease token fences completion | retain raw receipt and result |
| OptimizationTrial | research | experiment worker through trial repository | comparison projections | append or terminal transition | record failed and pruned trials | retain complete search population |
| Finding and PromotionCandidate | research | evidence pipeline and human decision service | execution deployment input by verified address | immutable finding; controlled candidate status | decision binds exact evidence | retain negative and positive results |
| Research approval | research | human decision service | execution verification copy | no execution use before verified copy | exact candidate, actor, inputs, expiry | audit retention |
| Strategy admission | execution, USER authority | admission service | research mirror where required | immutable | causal receipt is necessary, not sufficient | permanent with deployment attribution |
| Deployment | execution, MONEY binding | deployment service | cockpit view | synchronous | exact owner, account, Strategy, admission, Universe snapshot, policy | retain archived deployments |
| Signal | execution, MONEY | admitted runtime | UI and journal projection | append-only evidence | authority withdrawal withdraws authored signals | retain with linked intents and fills |
| DecisionBatch and portfolio admission | execution, MONEY, proposed | account execution holder | why-trade projection | synchronous account transaction | account lock, fence epoch, exact candidate set | permanent through money audit period |
| Capital reservation | execution, MONEY, proposed | account execution holder | cockpit balance view | synchronous per account | reservation head, expiry, consumption, broker reconciliation | immutable history plus current derived view |
| Execution command | execution, MONEY | current lease holder | provider request | synchronous journal before send | idempotency, epoch, broker tag, uncertain-state recovery | strict retention |
| Execution intent | execution, MONEY | execution lifecycle store | cockpit | immutable entry request | exact deployment, Strategy, candidate, reservation | strict retention |
| Broker order event | execution, MONEY | provider event ingestion | current order projection | append-only and idempotent | source event identity and reducer | strict retention |
| Fill | execution, MONEY | order event reducer and broker reconciliation | journal projection | append-only | exact intent and broker fact | legal and accounting retention |
| Position | execution, MONEY | execution lifecycle and broker reconciliation | UI current position | strong current consistency under account holder | virtual ownership preserved despite broker netting | snapshot plus immutable supporting facts |
| Capital and accounting | execution, MONEY | broker and accounting service | analytics projections | synchronous with fills | reconcile ledger equation | strongest backup and restore |
| Journal snapshot and artifacts | journal ledger database | journal repository | UI | optimistic version | separate from execution money truth | user backup, artifact retention policy |
| Manual broker fill capture | journal ledger database | broker capture and claim service | journal entry | idempotent by broker order ID | cross-check execution bot ownership before manual claim | retain raw evidence under privacy policy |
| Outbox events | one outbox in each plane | local transaction producer | consumer projections | ordered within one plane only | lease, cursor, idempotent effect, resync | retention watermarks and lag monitoring |
| UI projections | source-owning plane or browser | projection consumer only | none | bounded eventual lag | drift and resync visible | rebuildable |
| Audit and support diagnostics | source-owning plane plus structured logs | domain services | redacted support view | consequence dependent | actor, action, resource, policy or authority version | defined legal and incident retention |

## Cross-plane rules

1. A local transaction changes one database only.
2. A committed local outbox event announces the change.
3. A consumer verifies the source identity before writing a copy.
4. A copy records the source address and consumer algorithm.
5. Duplicate delivery is a no-op.
6. A missing or stale copy cannot grant authority.
7. A projection never becomes financial or research truth.
8. No cross-plane timestamp order is inferred.

## Maximum tolerated lag

| Flow | Lag rule |
| --- | --- |
| execution money facts | no asynchronous lag inside the owning transaction |
| risk-reducing exit state | current account-holder loop; stale is critical |
| research progress UI | seconds, with explicit last update |
| research evidence to deployment preflight | zero at use; verification must complete before command |
| market capability to preflight | profile must be current at use |
| general UI projection | seconds; stale marker required |
| support diagnostics | minutes where safe; never used for authority |

## Backup and restore

One coherent generation requires writers to stop across all three databases. Three dumps taken while writers continue are not one atomic product generation.

The current runbook correctly requires:

- PostgreSQL 16 tools;
- fresh target;
- three plane heads;
- table, primary-key, digest, and sequence checks;
- signed manifest for production claims;
- old-primary isolation;
- execution lease takeover at a higher epoch;
- broker reconciliation before activation.

Current status:

- local logical restore evidence exists;
- release deployability remains rejected and open;
- managed PITR, off-account retention, production RPO and RTO remain unproven.

## V2 migration impact

| New fact | Impact |
| --- | --- |
| UniverseDefinition and Snapshot | additive USER schema |
| CandidateInstance | additive USER or MONEY lineage schema |
| DecisionBatch and reservation | additive critical MONEY schema |
| WorkflowDefinition and Instance | additive USER control schema |
| Non-OHLCV data | new versioned MARKET and research schemas in V2 |
| General event replay | new MARKET object and manifest versions in V2 |

No existing row should be reinterpreted as one of these facts.
