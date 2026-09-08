# Strategy OS Component IR v2 architecture acceptance report

Status: REVIEW READY, NOT ACCEPTED\
Date: 2026-08-16\
Goal: phase3-4-ir-v2-acceptance\
Baseline HEAD: de6faae3e97cf5537338bee2143350e53f70da1c\
Next authority: one independent phase3-4-ir-v2-review critical reviewer

## 1. Outcome

The preserved Component IR v2 draft required material correction before implementation. Review iteration 1 then rejected two remaining ambiguities: compound public-parameter binding and the canonical full-document metadata/content-address contract. This single bounded correction closes both while preserving one public version-dispatching IR architecture and keeping Phase 4, frontend, execution effects, deployment, and live authority closed.

The proposed programme sequence uses separate durable goals:

1. architecture acceptance and review;
2. v1 dispatch compatibility;
3. v2 schema and fixed topology;
4. v2 resolution and independent runtime parity;
5. v2 admission and additive persistence;
6. versioned backend API;
7. serial integration gate;
8. independent implementation review;
9. Phase 4 architecture only after dual PASS.

Implementation capsules use Terra-medium owners. Mechanical tests and inventories may use up to four disjoint Luna-medium children after shared interfaces exist. Governing migrations, integration, and critical review remain serial. No task uses Ultra, xhigh, max, Fast mode, a reviewer swarm, or a permanent Sol controller.

This report does not accept the architecture. It records the owner task’s corrected resolution and evidence for the one permitted focused SPEC and QUALITY recheck.

## 2. Evidence binding

The task bound itself to:

- CURRENT.md: Phase 3 ACCEPTED/CLOSED; reusable disposable PostgreSQL 16 harness ACCEPTED; active stage phase3-4-ir-v2-acceptance;
- PROGRAMME.json stage 5 and its accepted dependency;
- active capsule and exact required_docs sections;
- preserved v2 design and plan;
- current backend IR, registry, evaluator, admission, persistence, API, and React/Vite coupling;
- accepted Phase 3 verdict at .agent/runs/phase3-task12-review-2/verdict.json;
- pre-edit status, diff, HEAD, and protected hashes under .agent/runs/phase3-4-ir-v2-acceptance/owner/.

The working tree was already materially dirty. The final package binds the complete dirty tree, every scoped file, and every named evidence log to one snapshot. Pre-edit evidence recorded path/status state but did not hash every already-dirty tracked blob, so it cannot independently prove architecture-owner attribution for all out-of-scope tracked files.

The owner explicitly designated the canonical dirty worktree and its inherited work as the authoritative handoff for this task. A same-HEAD user-provided preserved snapshot gives additional bounded evidence: 123 of 139 out-of-scope dirty tracked paths are byte-identical; 16 differ and are listed with both hashes in `.agent/runs/phase3-4-ir-v2-review/owner/correction-snapshot-comparison.log`. No trusted pre-owner blob manifest closes those 16. The correction therefore withdraws the categorical no-out-of-scope-edit claim and records the owner disposition in `.agent/runs/phase3-4-ir-v2-review/correction-owner-disposition.md`: use the inherited canonical worktree as input, review only the declared architecture paths, and do not reuse this limitation as product-code acceptance, provenance, or readiness evidence. The architecture owner reports no intentional product-code edit, but that statement is not promoted to a cryptographically established fact.

Evidence classification:

| Class | Meaning here |
| --- | --- |
| Accepted fact | named accepted verdict or programme state |
| Repository fact | directly inspected current code or file |
| Proposed policy | architecture decision awaiting independent review |
| Deferred requirement | assigned to an exact later architecture/capsule |
| Nonclaim | expressly not proved or authorized |

## 3. Repository findings

### 3.1 Accepted foundations

Repository inspection found:

- v1 strict schema and socket/wire_type contract in backend/app/ir/schema.py;
- one immutable PlatformRegistry and compound-body closure in backend/app/ir/registry.py;
- deterministic validation and resolution in backend/app/ir/validate.py and resolve.py;
- vector and independent prefix evaluation in runtime.py and streaming_reference.py;
- transitive implementation identities in implementation_identity.py;
- one immutable causal admission receipt and admission_address in strategy/admission.py;
- execution and research receipt persistence after migration heads 0034 and 0005;
- downstream deployment and money facts already bind admission_address;
- backend graph/editor routes and React/Vite code still depend on v1 sockets and wire_type.
- backend/app/core/instruments.py currently combines present-day instrument facts with Kite-oriented names such as spot_symbol and option_name; it is an implementation fact, not accepted canonical historical identity;
- backend/app/providers/instrument_resolver.py already states the correct ownership seam, and backend/app/providers/upstox_instruments.py demonstrates provider-owned mappings, but neither proves the complete effective-dated Phase 4 contract;
- backend/app/backtest/dataset_store.py and backtest/identity.py provide a reusable ordered content-addressed dataset seam with finite-value checks and pinned request/source bytes, but not yet point-in-time rulebook, provider-contract, knowledge-time, or closed-validity semantics; and
- backend/research/data/store.py has a simpler present research content hash that Phase 4 must reconcile without creating a second dataset authority.

### 3.2 Consequences

- V1 cannot become read-only during backend v2 work.
- A second registry or public v2 evaluation stack is unnecessary and unsafe.
- V2 many-input resolution must replace the v1 single-source internal map only for v2, behind one public resolver.
- Consumer money rows do not need another v2 graph authority column.
- Frontend v2 authoring needs a later owner-authorized capsule.
- Phase 4 market types cannot be implemented during this interphase architecture task.
- Phase 4 must separate durable economic identity from current symbols/tokens and extend the accepted dataset seam rather than blessing present-day provider fields or introducing a parallel cache identity.

### 3.3 Present but not newly accepted

The accepted Phase 3 snapshot contains substantial causal-admission, principal, credential-vault, and ordered-outbox foundations. Their existence does not broaden this task’s authority or prove production readiness. The exact 22 category-D baseline failures remain unaccepted.

## 4. Preserved-draft conflict disposition

| Preserved proposal | Disposition | Replacement |
| --- | --- | --- |
| separate v1/v2 public paths | reject | one public façade with private version handlers |
| domain and structural class repeated per port | reject | two independent intrinsic component-version axes |
| generic object payload | reject | exact registry type_id and type_version |
| shape/cardinality conflation | reject | payload shape separate from input connection cardinality |
| input cardinality one/optional/fixed/range/variadic | replace | single, optional, bounded_many, variadic with canonical min/max |
| fan-in inferred from array order | reject | explicit single, ordered position, keyed key, or unordered binding |
| unstable edges | reject | stable edge_id retained through evidence |
| action semantic flow and sink | reject | typed non-effectful intent description only; no broker effect |
| runtime branch manifest | reject | fixed topology; dynamic instruments are Phase 4 typed values |
| immediate v1 read-only writers | reject | full v1 coexistence until later frontend transition |
| automatic v1-to-v2 conversion | reject | no semantic guess; explicit future migration design |
| semantic, port-plan, and dispatch authorities | reject | one v2 graph_address plus provenance inside admission receipt |
| identity columns on deployments, intents, positions, and trades | reject | retain admission_address as downstream authority |
| implementation before architecture review | reject | dual architecture PASS gates all implementation |
| Phase 4 after architecture review alone | reject | Phase 4 depends on accepted v2 implementation review |
| broad suites and direct commits per draft task | replace | focused logged evidence, bounded integration gate, no agent commits |

## 5. Six owner-steer disposition

The ir_v2 SOURCE_MAP view directly maps three owner steers: 00, 01, and 05. The other steers remain additive programme authority but are not falsely presented as direct IR-v2 content.

| Steer | IR v2 disposition |
| --- | --- |
| 00 Product architecture | direct: named roles, dynamic derivative identity, lifecycle/state boundaries, and non-negotiable product invariants shape typed seams and fixed topology |
| 01 Strategy language and node system | direct: component contract, types, ports, custom-node boundary, validity seam, and node versioning |
| 02 Data/provider | deferred to Phase 4 architecture: canonical instruments, provider observations, provenance, sufficiency, and licensing; IR v2 supplies exact type refs only |
| 03 Execution/deployment | cross-cutting authority boundary: no action sink, broker effect, live IR, deployment, or credential work; exact execution semantics remain later-phase owner gates |
| 04 Research/backtest/commercial runtime | deferred to mapped later phases: IR v2 preserves deterministic causal evaluation and research lineage but does not claim capacity or commercial economics |
| 05 Verification | direct: rejection-first, risk-weighted tests, killed mutations, bounded suite cadence, and independent reviews |

## 6. SOURCE_MAP ir_v2 coverage

Every heading below is present in the ir_v2 view of SOURCE_MAP.json.

| Source | Exact mapped heading | Coverage or conflict disposition |
| --- | --- | --- |
| product_architecture | Strategy OS — Product Architecture Steer | governing product boundary; reflected in design sections 1–3 |
| product_architecture | Purpose | one composable, researchable, admissible strategy language; no deployment conflation |
| product_architecture | 4. Named secondary instrument roles | Phase 4 typed canonical instrument-role values through fixed ports |
| product_architecture | 5. Dynamic derivative identity | fixed selector topology; runtime identity is typed Phase 4 data |
| product_architecture | Critical invariant | exact identity and lifecycle evidence retained; no silent symbol substitution |
| product_architecture | 6. Options lifecycle model | lifecycle events are future typed observations, not graph rewiring |
| product_architecture | 7. Position and strategy state | state is distinct from document, admission, deployment, position, and trade facts |
| product_architecture | 10. Non-negotiable product rules | one IR/registry/identity authority; paper/live and strategy/deployment separation preserved |
| strategy_language | Strategy Language & Node System Steer | governing language source; reflected in exact v2 component contract |
| strategy_language | Goal | one coherent typed node system with deterministic composition |
| strategy_language | 1. Node contract required for every first-party node | exact classification, params, ports, types, implementation identity, and version |
| strategy_language | 3. Type 3 derivative/microstructure library | type seam only; concrete market types deferred to Phase 4 |
| strategy_language | Option structure | Phase 4 registered instrument/observation types, not generic objects |
| strategy_language | Options analytics | later registered components with exact validity and provenance |
| strategy_language | Futures | later canonical instrument and observation types in Phase 4 |
| strategy_language | Order book / ladder | later provider-capability-gated observation types |
| strategy_language | Trade-flow features where the provider truly supplies enough data | explicit Phase 4 sufficiency/provenance gate; no inferred capability |
| strategy_language | 4. Type 1 execution starter pack | typed intent description may be data; execution effects excluded |
| strategy_language | Entry/exit | later non-effectful intent description; no broker authority |
| strategy_language | Order type | later exact typed intent field outside direct v2 implementation |
| strategy_language | Position sizing | money/risk authority remains later phase and owner gated |
| strategy_language | Protection | risk-reducing execution semantics remain later phase and owner gated |
| strategy_language | Pyramiding / scaling | later state/intent semantics; no IR-side live authority |
| strategy_language | Position/portfolio inputs | typed immutable input seam; canonical truth deferred |
| strategy_language | 5. Type 5 logic, temporal and state pack | exact registered fixed-topology components |
| strategy_language | Boolean / comparison | exact condition types; no truthiness coercion |
| strategy_language | Arithmetic | exact numeric types; validity rules deferred to Phase 4 |
| strategy_language | Reducers | many-input assembly is explicit and deterministic |
| strategy_language | Temporal | no implicit wall clock; effective-time semantics deferred |
| strategy_language | Confirmation | ordinary fixed component with exact typed inputs |
| strategy_language | Noise/state control | explicit state contract required; no process-global hidden state |
| strategy_language | Scheduling | typed control data only; no implicit scheduler or broker effect |
| strategy_language | Validity | exact type seam; missingness and propagation owned by Phase 4 |
| strategy_language | 6. Custom-node hierarchy | levels remain policy; v2 cannot bypass registry/admission |
| strategy_language | Level 1 — Fork first-party node | new pinned component version and implementation identity |
| strategy_language | Level 2 — Formula node | future constrained component with exact types and canonical expression identity |
| strategy_language | Level 3 — Sandboxed custom Python | deferred security/runtime design; no arbitrary code authority in v2 |
| strategy_language | Level 4 — External signal | future typed provider observation with provenance and capability gate |
| strategy_language | 7. Numerical validity | exact Phase 4 dependency; no hidden NaN/fill/coercion |
| strategy_language | 8. Node versioning | every executable contract or implementation change pins a new version |
| verification_policy | V1 Implementation Priorities & Verification Policy | governs staged evidence and independent review |
| verification_policy | Goal | risk-weighted confidence without broad unbounded suites |
| verification_policy | 1. Risk-weighted verification | critical language/identity/migration boundaries receive strongest evidence |
| verification_policy | Critical | architecture and final integration require independent critical review |
| verification_policy | Important | focused compatibility, API, runtime, and persistence tests |
| verification_policy | Routine | deterministic schema and round-trip cases stay bounded |
| verification_policy | Trivial | mechanical docs/path checks may use Luna children |
| verification_policy | 2. Test rule | every changed claim has direct positive, negative, and relevant mutation evidence |
| verification_policy | 3. Test cadence | focused per slice; broad bounded gate once at integration |
| verification_policy | 5. V1 product priorities | v1 authoring/evaluation/admission remains operational |
| verification_policy | Must have | exact identity, typed ports, causal parity, persistence, and authority separation |
| verification_policy | Can be deferred | frontend migration, dynamic market semantics, custom Python, live authority |
| verification_policy | 6. Implementation sequencing | serial dependency graph encoded in plan, capsules, and PROGRAMME |
| verification_policy | 8. Guard against scope drift | hard stops and exact allowed paths per capsule |
| verification_policy | Core-abstraction issue | stop and amend reviewed architecture; do not patch around it |
| verification_policy | Local implementation edge case | bounded correction within current capsule and evidence |

Coverage count: 56 mapped headings, 56 explicit rows.

## 7. Architecture decisions

### 7.1 Schema

- Explicit format_version 2.
- Eight required top-level fields and a closed metadata_version 1 envelope with name, description, and canonical tags.
- Editor layout and presentation fields are excluded from the v2 document and remain a separately gated presentation contract.
- Exact component references and parameters.
- Exact graph inputs, outputs, nodes, edges, and bindings.

### 7.2 Ports and types

- Component classification is intrinsic.
- Port semantic role is separate from component class.
- Payload shape is separate from incoming-connection cardinality.
- Type compatibility is exact or a finite reviewed compatibility allow-list.
- Conversion is an explicit component.

### 7.3 Many-input semantics

- single 1..1;
- optional 0..1;
- bounded_many finite min..max;
- variadic min..unbounded;
- explicit single, ordered, keyed, or proven order-independent unordered assembly;
- stable edge identity and deterministic resolved bundles.

### 7.4 Compound parameters

- Each public parameter has one closed, transform-free binding entry and one or more unique direct body-node targets.
- Public and target parameter descriptors are canonically byte-equal; a body slot is literal or bound, never both.
- Present values, explicit defaults, and absence propagate unchanged through nested compounds with full parameter-target provenance.
- Body templates, binding tables, public schemas, and nested closure enter the component definition, implementation identity, and registry snapshot; any change requires a new component_version.
- Public/body equality applies to mapped ports, not component-level parameter schemas or classification.

### 7.5 Identity and authority

- content_address is lowercase `sha256:` over the existing canonical_json UTF-8 bytes of the complete canonical validated document, not raw request formatting;
- graph_address is the one v2 executable graph identity;
- presentation_address is non-executable;
- admission_address is the sole downstream execution-authority binding;
- object-key/tag reordering preserves both document identities, descriptive metadata changes content_address only, and executable changes alter both content_address and graph_address;
- v1 identity semantics remain unchanged.

### 7.6 Migration

- additive execution and research migrations only;
- no rewrite of admitted v1 facts;
- deterministic backfill only;
- no duplicate authority on every money record;
- SQLite and PostgreSQL upgrade/recovery evidence required.

### 7.7 Phase 4 binding handoff

The reconciled documents now answer the market-truth planning questions without implementing them:

- canonical instrument_id is an opaque Strategy OS economic identity, never a provider token or symbol; exact derivative contracts are individually identified and continuous/adjusted series remain non-tradable derived identities;
- defining contract terms are immutable while symbols, provider mappings, listings, lot/tick/freeze/strike-grid rules, calendars, fees, corporate actions, and eligibility are bitemporal effective-dated assertions resolved by market time and knowledge time;
- observed ProviderObservation evidence is separate from NormalizedMarketObservation truth, with immutable versioned provider contracts, mappings, clocks, adapters, transformation/rulebook addresses, capability, licence, and provenance;
- closed validity states and stage-specific ingestion, normalization, indicator, research, and deployment-preflight rules forbid hidden NaN/sentinel/fill/coercion semantics;
- CSV is a separately labelled source with an immutable trust manifest and cannot imply live or provider-grade capability;
- the existing ordered_dataset_address is extended with canonical identity, rulebook, provider-contract, knowledge-time, validity, alignment, adjustment, and transformation inputs rather than replaced;
- one bounded DataRequirementPlan seam supplies Phase 5 node requirements, Phase 6 deployment binding/preflight, and Phase 7 selectors/subscriptions/resource planning; and
- Phase 4 must be split into four ordered implementation goals, serial integration, and one independent critical review, with Terra-medium ownership and no more than four post-interface mechanical Luna children per implementation goal.

These are proposed downstream constraints awaiting this architecture review and the later Phase 4 architecture goal. They do not accept a Phase 4 schema or implementation.

## 8. Programme amendment

The owner’s instruction to begin and structure the chats authorizes the bounded programme amendment recorded by this goal. The amendment inserts explicit blocked implementation and review stages and moves phase4-architecture behind phase3-4-ir-v2-implementation-review.

This does not authorize product implementation in the architecture task. Each later stage remains blocked until its exact dependency is accepted.

The active architecture capsule stays serial with parallel_budget 0. Later implementation capsules declare up to four mechanical Luna assignments, matching the four child slots available while a Terra owner is active. They do not require every slot to be filled.

## 9. Risk-weighted gate

| Boundary | Risk | Required gate |
| --- | --- | --- |
| language and identity | critical | architecture dual PASS, metamorphic identity tests, killed mutation |
| compound parameter semantics | critical | declaration rejection matrix, nested propagation/provenance parity, killed mutation |
| stored-document identity | critical | closed metadata, canonical-byte golden vectors, content/graph separation, API round-trip |
| resolver/evaluator independence | critical | independent implementations, prefix parity, killed mutation |
| admission authority | critical | receipt reproducibility, mismatch refusal, immutability, owner isolation |
| schema migrations | critical | one owner, SQLite and PG populated upgrade/recovery, mutation |
| API versioning | important | v1 golden contract, v2 round-trip, atomic unknown-version refusal |
| frontend coupling | important | read-only inventory; no implementation |
| documentation/programme | routine | JSON/path/coverage/DAG validation and diff check |

## 10. Deployment impact

This architecture goal changes documentation and programme state only. It changes no dependency, schema, configuration, service, runtime, provider, or infrastructure.

Later implementation affects runtime, API schemas, database migrations, registry construction, and stored artifacts. Each capsule must record exact impact and either prove its affected local gate or name the exact later capsule. Production capacity, recovery, security, provider compliance, and cost remain unproved.

## 11. Nonclaims

- Component IR v2 is not implemented or accepted.
- Phase 4 is not unlocked.
- Market truth, canonical instrument semantics, numerical validity, provider sufficiency, and licensing are not implemented.
- React/Vite cannot author v2.
- V1 remains supported.
- No deployment or live authority is granted.
- No production readiness, capacity, recovery, security, cost, or commercial claim is established.
- The 22 category-D baseline failures remain unaccepted.
- No provider, component family, strategy family, or execution path beyond named evidence is implied.

## 12. Review request

The independent reviewer should reject the proposal if it finds:

- a second executable stack or authority;
- ambiguous many-input ordering;
- duplicate component/port classification;
- generic or coercive type semantics;
- v1 writer breakage;
- runtime topology;
- action or broker effects;
- incomplete, coercive, or provenance-losing compound parameter binding;
- an open metadata envelope or non-reproducible content-address byte contract;
- identity ambiguity;
- migration guesses or money-row identity proliferation;
- Phase 4 leakage;
- a stale or unverifiable evidence package.

Only separate SPEC: PASS and QUALITY: PASS may unlock the first implementation capsule.
