# Strategy OS Component IR v2 implementation execution prompt

Status: PROPOSED FOR INDEPENDENT ARCHITECTURE REVIEW\
Derived from: 2026-08-13-strategy-os-ir-v2-port-contract-design.md\
Date: 2026-08-16\
Execution authority: none until phase3-4-ir-v2-review returns separate SPEC: PASS and QUALITY: PASS

## 1. Role and objective

Act as the bounded owner of exactly one active capsule in the Component IR v2 sequence. Do not execute this whole plan in one task.

The programme objective is to add Component IR v2 as a lossless versioned extension of the accepted Phase 3 causal strategy contract. Preserve one typed immutable IR façade, one PlatformRegistry, one validator, one resolver, one vector evaluator, one independent prefix evaluator, one implementation-identity closure, one research lineage, and one admission authority.

Reject completion claims until the named evidence exists. A successful local test is not proof of migration safety, frontend support, deployability, production readiness, or live authority.

Model route:

- architecture owner: GPT-5.6 Sol, medium reasoning;
- implementation and integration owner: GPT-5.6 Terra, medium reasoning;
- exact mechanical child: Luna medium through luna-worker;
- judgment-heavy child, only when declared: Terra medium through terra-worker;
- one independent critical reviewer after integration: Sol high;
- no Ultra, xhigh, max, Fast mode, reviewer swarm, or permanent Sol controller.

## 2. Worktree, project root, and command roots

Use only:

- canonical checkout: /Users/priyanshusaraf/dev/options-trading
- active worktree: /Users/priyanshusaraf/dev/options-trading/.claude/worktrees/codex-execution-foundation
- product root: paper-trader
- backend command root: paper-trader/backend
- branch: codex/execution-foundation

The Desktop clone and the detached Codex snapshot are not write targets.

At the start of every task:

1. read paper-trader/docs/agent/CURRENT.md;
2. confirm active stage and dependency in paper-trader/docs/agent/programme/PROGRAMME.json;
3. read the exact active capsule;
4. read only its required_docs sections and applicable AGENTS.md files;
5. read the matching repository skills;
6. record git status, relevant diff, HEAD, protected hashes, and inherited dirty paths;
7. create one durable goal before product work.

Run full commands through .codex/scripts/run_logged.py and retain output under the capsule’s ignored .agent/runs directory.

## 3. Accepted baseline

The only accepted baseline is:

- Phase 3 dual verdict at .agent/runs/phase3-task12-review-2/verdict.json;
- reusable disposable PostgreSQL 16 developer harness evidence under .agent/runs/post-phase3-postgresql-harness/;
- current HEAD and dirty-tree binding captured by the active capsule;
- exact source sections declared by the active capsule and SOURCE_MAP.json.

Treat the current v1 contract as frozen compatibility behavior:

- format_version 1 socket and wire_type grammar;
- one source per target input;
- current validation and deterministic resolution;
- vector and independently implemented prefix-stream evaluation;
- transitive implementation identity;
- immutable causal admission receipts;
- admission_address references across downstream facts;
- current backend APIs and React/Vite authoring behavior.

Do not inherit claims from the preserved v2 draft. Challenge them against current code, accepted evidence, the owner steers, and the reviewed v2 architecture.

The exact 22 category-D baseline failures remain unaccepted. Do not broaden a capsule’s suite merely to rediscover them.

## 4. Architectural context

The reviewed design is the controlling technical contract:

paper-trader/docs/superpowers/specs/2026-08-13-strategy-os-ir-v2-port-contract-design.md

Implementation must keep these fact boundaries distinct:

- source strategy document;
- canonical executable graph identity;
- registry and implementation closure;
- research evidence and lineage;
- immutable admission receipt;
- requested deployment assignment;
- resolved execution authority;
- order intent;
- position and trade facts;
- presentation state.

Only admission_address binds an admitted strategy to downstream execution facts. Other hashes prove content or provenance; they do not grant authority.

Phase 4 owns market truth. IR v2 may define type-reference seams, but it must not invent canonical instrument rules, provider observation truth, effective-time rulebooks, missingness, numerical validity, data licensing, or capability policy.

## 5. Scope boundaries

Allowed programme work:

- private version adapters behind one public façade;
- exact v2 schemas and registered descriptors;
- stable edge and input-bundle contracts;
- deterministic resolution and evaluation;
- compound public/body equality;
- canonical serialization and v2 graph identity;
- additive v2 admission and persistence;
- versioned backend API contracts;
- targeted compatibility, migration, parity, and mutation evidence;
- documentation and programme state owned by the active capsule.

Forbidden:

- frontend source changes;
- disabling or silently rewriting v1;
- provider or broker implementation;
- order actions, live sizing, routing, risk, protection, or execution semantics;
- authoritative live IR;
- production deployment or infrastructure;
- VPS, live credentials, production data, or live money;
- destructive data operations;
- licence, legal, regulatory, pricing, or commercial decisions;
- a second registry, resolver, evaluator, identity authority, provider registry, or research ledger;
- broad future-phase implementation.

## 6. Required IR v2 contract

Every implementation capsule must preserve all of the following.

### 6.1 Format dispatch

- format_version is explicit and strictly typed;
- v1 selects unchanged v1 behavior;
- v2 selects reviewed v2 behavior only after its implementation stage exists;
- missing, boolean, float, string, and unknown versions fail closed;
- no automatic upgrade or downgrade;
- one public validate, resolve, evaluate, prefix-evaluate, and admission path.

### 6.2 Component and type registry

- PlatformRegistry remains the sole immutable registry;
- domain_family and structural_role are independent intrinsic fields on a component version;
- a graph node cannot override registry declarations;
- every type is an exact type_id and type_version;
- generic object, wildcard, implicit coercion, hidden fill, resample, broadcast, and alignment are forbidden;
- conversions are explicit registered components.

### 6.3 Ports

- every port has stable port_id, direction, semantic_flow, semantic_role, type_ref, and shape;
- semantic_flow is value, condition, event, or non-effectful control;
- action and broker effects are absent;
- input connections use one exact cardinality: single, optional, bounded_many, or variadic;
- min and max follow the reviewed table;
- assembly is single, ordered, keyed, or proven order-independent unordered;
- a default exists only when min is zero and is exact-type valid;
- outputs do not declare input cardinality.

### 6.4 Edges and cardinality

- every edge has stable edge_id;
- endpoints name scope, node where required, and port_id;
- binding is single, ordered position, keyed key, or unordered;
- ordered positions and keyed keys are unique;
- document array order never supplies semantics;
- edge identity survives validation, resolution, evaluation evidence, and admission provenance;
- the resolved input bundle preserves all members and defaults;
- no target-to-single-source map is used for v2.

### 6.5 Topology and compound components

- all v2 topology is fixed before admission;
- dynamic derivative selection is typed Phase 4 data through fixed nodes, not runtime rewiring;
- runtime branch manifests are absent;
- compound mapped public ports exactly equal their body boundary ports; parameter schema and classification are not boundary-port fields;
- every compound public parameter has one closed, transform-free binding entry with one or more unique direct body-node parameter targets whose complete descriptors are canonically byte-equal;
- a body parameter is literal or bound, never both, and binding-table/body/public-schema changes require a new component_version;
- recursive expansion propagates the same canonical present/default/absent parameter state, detects cycles, and retains full nested node, parameter-target, port, and edge provenance;
- transitive component and implementation identities close through one registry.

### 6.6 Validation and evaluation

- validators reject unknown keys and incompatible types deterministically;
- error codes, paths, node paths, port ids, and edge ids are stable;
- v2 initial graphs are acyclic;
- vector and prefix evaluators remain independent implementations;
- both consume the reviewed resolved input bundle;
- no evaluator reads providers, brokers, implicit wall-clock time, mutable global registry state, or editor metadata;
- no result is admissible without existing causal/parity gates.

### 6.7 Serialization and identity

- the required closed metadata envelope has exactly metadata_version 1, name, description, and canonical tags; editor layout is a separate deferred presentation document;
- content_address is `sha256:` over backend/app/ir/hashing.py canonical_json bytes for the complete canonical validated document, not raw request formatting;
- graph_address is the sole canonical v2 executable graph identity;
- presentation_address is optional and never executable;
- admission_address remains the sole authority binding;
- v1 graph-address semantics remain unchanged;
- receipts include format_version and identity_scheme_version;
- object-key/tag reordering preserves content_address after canonicalization; descriptive metadata mutations change content_address but not graph_address;
- editor presentation state cannot enter the v2 document or alter content_address or graph_address;
- executable changes must alter v2 graph_address.

## 7. Migration and compatibility

### 7.1 Persistence policy

Use additive migrations after execution head 0034 and research head 0005. The persistence capsule owns exact migration identifiers after re-reading the then-current heads.

Required behavior:

- add format and semantic identity fields only on immutable graph or admission records where query/integrity needs them;
- keep admission_address as the downstream money and deployment reference;
- do not add duplicate v2 identity columns to every deployment, intent, position, or trade;
- never rewrite an admitted v1 receipt or graph;
- backfill only deterministic facts derived from stored canonical bytes;
- mark unverifiable rows as legacy rather than guessing;
- preserve destructive-downgrade refusal;
- prove SQLite and disposable PostgreSQL behavior.

### 7.2 Compatibility policy

Throughout this sequence:

- stored v1 graphs remain readable;
- v1 validation, resolution, vector evaluation, prefix evaluation, and admission remain byte/behavior compatible;
- existing backend v1 writers stay operational;
- existing React/Vite authoring stays operational;
- v2 is not the default frontend format;
- there is no v1 auto-upgrade;
- a v1-to-v2 conversion tool is deferred until semantic equivalence can be separately designed and reviewed;
- v1 write retirement requires a later owner-authorized frontend capsule.

### 7.3 Recovery and rollback

The persistence capsule must prove:

- empty and populated upgrade;
- restart after upgrade;
- concurrent duplicate insert behavior;
- immutability conflict behavior;
- rollback where non-destructive;
- explicit refusal where rollback would destroy accepted facts;
- recovery from a failed migration without partial authority;
- identical invariant behavior on SQLite and PostgreSQL where promised.

## 8. Phase 4 decomposition

Do not implement Phase 4 in this sequence. After accepted IR v2 implementation review, phase4-architecture must audit current code, reconcile the following contract, and create exact capsules. These are required planning decisions, not a claim that Phase 4 is designed or implemented.

### 8.1 Required market-truth contract

Phase 4 must define one opaque durable Strategy OS instrument_id that is never a provider symbol or token. Defining economic terms are immutable for an identity: asset class, contract kind, exact underlier or issuer relationship, distinguishing venue/segment, currency and settlement/deliverable terms, and exact derivative terms. An option contract pins right, exact decimal strike and scale, expiry plus timezone/convention, and underlying instrument_id. A future pins contract month, expiry, settlement, and underlying instrument_id. A changed defining term creates a new identity. Each listed strike is a distinct contract; ATM selection is policy. A continuous or adjusted series is a distinct non-tradable derived identity with pinned roll/adjustment policy.

Symbols, tokens, provider mappings, listings, eligibility, lot/tick/freeze/strike-grid facts, sessions, auctions, holidays, expiry conventions, fees, corporate actions, and universe membership are effective-dated assertions. Use half-open market-valid intervals and separate recorded-at/superseded-at knowledge intervals. Resolvers accept as_of_market_time and as_known_at, return exact fact/rulebook addresses, reject overlaps, and represent gaps. Typed relationships cover underlying, derivative, listing, series, adjustment, and membership. Prefer observed historical contract masters. Reconstructed facts pin method, sources, confidence, and knowledge time and stay labelled reconstructed. Never substitute the present symbol master or rulebook into historical replay.

Data provider and execution broker remain independent. Immutable ProviderContract versions pin data product, schema, field meaning, units, clocks/timezone, bar/adjustment/missing-sentinel conventions, granularity, limits, licence class, and adapter implementation. Effective-dated provider mappings connect provider keys to canonical instruments. ProviderObservation preserves raw or losslessly decoded evidence, provider contract/key, event/source/received times, sequence/quality, payload address, and adapter. NormalizedMarketObservation is separate and pins canonical instrument, field/type/unit/scale, value or validity state, event/effective/availability/knowledge times, source-observation, transformation, provider-contract, rulebook, adjustment, resampling, and missingness addresses. Raw evidence is never overwritten.

Canonical instants are aware UTC with exchange timezone and session date retained. Distinguish event, source, received, recorded, available-as-of, market-valid, and knowledge-valid times. Completed bars use half-open windows and explicit availability; forming bars are separately typed. Replay sees only data and revisions known by its as_known_at cutoff.

The minimum closed states are VALID, NOT_IN_SESSION, NOT_LISTED, NO_TRADE, MISSING, PROVIDER_UNAVAILABLE, STALE, INVALID, INSUFFICIENT_HISTORY, UNDEFINED, and OUT_OF_DOMAIN. A non-VALID observation has no fabricated numeric value. NO_TRADE is not zero; NaN, infinity, sentinels, empty strings, and absent rows are not implicit states.

Enforce validity by stage:

- ingestion preserves source evidence and interprets sentinels only under the pinned ProviderContract;
- normalization permits only documented semantics-preserving mapping, timezone, unit, and identity transformations and pins their versions;
- indicators declare warm-up, domain, missing-input, invalid-operation, and propagation behavior, with no silent fill, clipping, alignment, coercion, or history shortening;
- research pins the policy and records a typed no-result or blocks evaluation when required input is invalid; and
- deployment preflight checks capability, rulebook, freshness, alignment, and validity before new exposure while preserving already-authorized risk-reducing exits.

Provider semantic change Level 0 is proven representation-only normalization. Level 1 is operational change under unchanged semantics with new provenance and limit checks. Level 2 creates a new version and forces affected revalidation. Level 3 blocks affected research admission or deployment. There is no silent provider fallback.

CSV is a separate source class with an immutable manifest: file hash, owner/uploader, import time, column/types, canonical-instrument mapping, timezone/calendar, units, adjustments, missingness, transformations, effective interval, licence status, and provenance gaps. Unknown provenance remains explicit. CSV can support declared research policy but cannot imply provider-grade, live, redistribution, or execution capability.

Extend the existing ordered_dataset_address instead of creating another cache identity. It must pin canonical instruments, provider-contract/observation snapshot, rulebook, effective and knowledge windows, validity/missingness, alignment/resampling, corporate-action/adjustment, transformations, source bytes, and code identities. A source or semantic revision creates a new address.

One typed DataRequirementPlan compile seam carries bounded canonical roles/selectors, fields, resolution, history/warm-up, session and completed/forming-bar policy, max age/skew, alignment, validity, live/historical capability, universe bounds, and subscription intent. It must not load every strike or subscribe to an unbounded universe. Phase 5 consumes types/history/validity requirements; Phase 6 binds roles to instruments/providers/products/accounts/capability and preflight reasons; Phase 7 resolves reviewed selectors, option windows, recenter/roll, subscriptions, QoS, and resource plans without mutating graph topology.

### 8.2 Required Phase 4 goals

phase4-architecture must generate these dependency-ordered durable goals:

1. canonical economic identity, effective-dated mappings/relationships, and point-in-time rulebook storage and resolution;
2. provider contracts, source observations, capability/provenance, CSV trust, and licence boundaries;
3. normalization, closed validity, numerical policy, and provider-change revalidation;
4. cross-instrument/timeframe alignment, data sufficiency, DataRequirementPlan, content-addressed dataset reuse, and end-to-end market-truth gates;
5. a serial integration goal; and
6. one independent Sol-high critical review returning separate SPEC and QUALITY verdicts.

Each Phase 4 implementation goal uses one Terra-medium owner and at most four Luna-medium children. The owner first freezes the shared interface. Luna work must then be mechanical, exact-path, disjoint, and dependency-aware. Instrument identity, rulebook policy, provider semantics, numeric validity, causal alignment, migrations, integration, and acceptance claims cannot be delegated to Luna.

Phase 4 may register reviewed types and components only through PlatformRegistry. It cannot create a second IR, instrument identity, provider registry, observation truth, dataset identity, or research ledger. It defers the Phase 5 node catalogue, Phase 6 deployment binding, Phase 7 dynamic selector/subscription/QoS runtime, Phase 8 frontend, Phase 9 adapter breadth, Phase 10 commercial controls, and confidentiality system.

Reject unless disproved by direct evidence: provider token as identity; current symbol master as history; provider equal to broker; one strategy graph equal to one instrument; timestamps with unspecified clocks; NaN as validity; no trade as zero; ATM-only contract truth; inferred contracts as observed; silent provider fallback; name/symbol cache identity; and mutable rulebook/provider contracts as reproducible evidence.

## 9. Dependency order and chat structure

Every row is a separate durable goal and a separate Codex task. Start only the first ready row in PROGRAMME.json.

| Order | Goal | Owner | Children | Dependency |
| ---: | --- | --- | --- | --- |
| 1 | phase3-4-ir-v2-acceptance | Sol medium | none | accepted Phase 3 and PG harness |
| 2 | phase3-4-ir-v2-review | one Sol-high critical reviewer | none | architecture review package |
| 3 | phase3-4-ir-v2-dispatch-compatibility | Terra medium | up to four Luna medium | architecture dual PASS |
| 4 | phase3-4-ir-v2-schema-topology | Terra medium | up to four Luna medium | dispatch accepted |
| 5 | phase3-4-ir-v2-resolution-runtime | Terra medium | up to four Luna medium | schema/topology accepted |
| 6 | phase3-4-ir-v2-admission-persistence | Terra medium | up to four Luna medium after owner migration scaffold | runtime accepted |
| 7 | phase3-4-ir-v2-api-contract | Terra medium | up to four Luna medium | persistence accepted |
| 8 | phase3-4-ir-v2-integration-gate | Terra medium | none | API accepted |
| 9 | phase3-4-ir-v2-implementation-review | one Sol-high critical reviewer | none | current package from integration |
| 10 | phase4-architecture | Sol medium | declared architecture readers only | v2 implementation dual PASS |

“Up to four” reflects four child slots while the owner occupies the fifth active slot. A parent must not spawn a child merely to fill capacity. A child begins only after its declared dependency exists, owns exact non-overlapping paths, and has a mechanical acceptance target.

Children use fork_turns: none. The parent gives each child:

- capsule id and assignment id;
- exact allowed paths;
- exact prohibited paths;
- dependency milestone;
- commands and evidence path;
- instruction that other agents share the tree and inherited work must not be reverted.

The parent integrates, inspects every child diff, runs cross-cutting tests, and owns final claims. Children do not commit, edit programme state, build review packages, touch migrations unless explicitly assigned, or decide architecture.

## 10. Per-task requirements

### 10.1 phase3-4-ir-v2-dispatch-compatibility

Owner responsibility:

- create the single format-dispatch seam behind existing public APIs;
- isolate existing v1 implementation without semantic change;
- reject unsupported versions;
- migrate only central backend call sites declared by the capsule;
- keep v2 unimplemented and rejected in this task.

Mechanical children after the owner dispatch scaffold:

1. v1 schema and validation golden corpus;
2. v1 resolution and vector/prefix output golden corpus;
3. v1 admission, identity, and handwritten-equivalence golden corpus;
4. backend/frontend v1 contract inventory and exact API compatibility tests.

Acceptance:

- golden v1 bytes, errors, addresses, resolution, outputs, and receipts are unchanged;
- unsupported versions fail before persistence;
- no v2 behavior, frontend source change, migration, or live path appears;
- one public façade is evident and no duplicate registry exists.

### 10.2 phase3-4-ir-v2-schema-topology

Owner responsibility:

- implement registered type descriptors and component classification in PlatformRegistry;
- implement the closed v2 document and metadata envelope, port, cardinality, edge, binding, compound parameter-binding declaration, canonical full-document bytes, and canonical executable projection;
- add v2 validation through the single public façade;
- keep evaluator and admission unsupported for v2 until later capsules.

Mechanical children after shared schema interfaces stabilize:

1. port and type validation cases;
2. edge, binding, cardinality, default, and canonical-order cases;
3. full-document/content-address, graph-address, metadata canonicalization, and presentation-separation cases;
4. registry and compound port/parameter-binding declaration construction cases.

Acceptance:

- every reviewed schema rule has a positive and negative case;
- generic payloads and hidden coercion fail;
- unknown metadata, noncanonical strings, duplicate tags, invalid compound targets, descriptor mismatch, literal/binding conflict, duplicate targets, and transform attempts fail;
- canonical JSON/tag reordering preserves content_address and graph_address; descriptive metadata changes only content_address and presentation data is rejected from the v2 document;
- every executable mutation changes graph_address;
- v1 golden evidence remains unchanged.

### 10.3 phase3-4-ir-v2-resolution-runtime

Owner responsibility:

- resolve v2 into immutable input bundles retaining edge identity;
- expand compounds with exact mapped-port equality, public-parameter binding, and nested edge/parameter-target provenance;
- update vector evaluation for supported v2 components;
- independently update prefix-stream evaluation;
- preserve current v1 behavior.

Mechanical children after resolver interfaces stabilize:

1. ordered, keyed, unordered, default, fan-out, and rejection resolution tests;
2. compound mapped-port equality, parameter propagation, nesting, cycle, and provenance tests;
3. vector evaluator many-input and determinism tests;
4. independent prefix evaluator and prefix-parity mutation tests.

Acceptance:

- no v2 target-to-single-source collapse remains;
- ordered/keyed identity survives to traces and receipts-in-waiting;
- compound public values, defaults, and absence propagate unchanged to every unique target while internal literals remain immutable;
- independent vector and prefix paths agree for accepted fixtures;
- killed parity mutations demonstrate the oracle can fail;
- no provider, broker, action sink, or runtime topology exists.

### 10.4 phase3-4-ir-v2-admission-persistence

This is one governing migration and authority task. The Terra owner alone owns migrations, models, repository invariants, and admission semantics.

Owner responsibility:

- extend the existing admission receipt for v2, including compound parameter-target provenance and exact canonical content bytes;
- add only the reviewed additive persistence fields;
- preserve admission_address as downstream authority;
- implement exact SQLite and PostgreSQL upgrades and recovery;
- refuse incomplete, mismatched, or mutable v2 evidence;
- leave live authority closed.

Mechanical children begin only after owner-created migration and model interfaces:

1. admission receipt, identity, immutability, and evidence-mismatch tests;
2. execution SQLite/PostgreSQL populated-migration tests;
3. research SQLite/PostgreSQL populated-migration tests;
4. legacy-v1, restart, concurrency, rollback, and downstream compatibility tests.

Children may own new test files only. They cannot edit migration files, models, admission builders, money paths, or programme state.

Acceptance:

- no admitted v1 row is rewritten;
- v2 receipts are reproducible and immutable from exact content/graph addresses and resolved compound parameter provenance;
- duplicate/concurrent writes are idempotent or conflict closed;
- failure cannot leave partial authority;
- downstream facts still bind only admission_address;
- disposable PostgreSQL evidence passes;
- a reversible migration mutation is killed;
- deployability impact is recorded without a readiness claim.

### 10.5 phase3-4-ir-v2-api-contract

Owner responsibility:

- expose explicit v1/v2 discriminated backend request and response contracts;
- preserve all accepted v1 endpoints and writers;
- add v2 read/write only for capabilities accepted by prior capsules and return the complete canonical document value rather than preserving incidental request formatting;
- reject unknown versions atomically;
- keep React/Vite v2 authoring unsupported.

Mechanical children after API schemas stabilize:

1. v2 create/read round-trip, closed metadata, canonical-byte, and identity tests;
2. v1 API golden compatibility and unknown-version refusal tests;
3. editor descriptor and product-object backend contract tests;
4. read-only React/Vite coupling audit written to the capsule evidence directory.

Acceptance:

- API round-trip preserves the canonical complete document, content_address, and graph_address across object-key and tag reordering; unknown metadata is rejected;
- failures do not persist partial data;
- current v1 frontend contract still works;
- no frontend source file changes;
- v2 remains opt-in backend capability, not the product default.

### 10.6 phase3-4-ir-v2-integration-gate

This task is serial. Do not spawn children.

Owner responsibility:

- audit the integrated diff and all prior evidence;
- run the bounded final v1/v2 IR, admission, research, migration, and API gate;
- run the disposable PostgreSQL gate once;
- run exact killed mutations for dispatch, type compatibility, binding order, compound parameter propagation, full-document/graph identity separation, prefix parity, admission immutability, and migration safety;
- reconcile documentation, CURRENT, PROGRAMME, capsule statuses, protected hashes, and deployability obligations;
- create the official review package from the exact dirty snapshot.

Acceptance:

- every prior capsule is accepted with evidence;
- no unresolved protected-file or inherited-work conflict exists;
- all package paths and evidence hashes bind to the same snapshot;
- review-package verification and git diff --check pass;
- the implementation-review capsule is ready;
- no release, production, live, or frontend claim is made.

### 10.7 phase3-4-ir-v2-implementation-review

One read-only critical-reviewer performs independent SPEC and QUALITY review from the package. No reviewer swarm.

The reviewer must:

- verify package lineage and evidence hashes before claims;
- challenge v1 compatibility, identity uniqueness, resolver/evaluator independence, compound closure, migration safety, API atomicity, and authority separation;
- inspect killed mutation evidence;
- return separate SPEC and QUALITY verdicts;
- permit at most one bounded correction/recheck under a new correction capsule.

Only dual PASS may make phase4-architecture ready.

## 11. Tests and evidence

Use focused evidence per capsule. Do not run the entire repository merely for confidence.

Required evidence classes across the sequence:

- strict format-version dispatch;
- v1 golden schema, errors, canonical bytes, addresses, resolution, evaluation, prefix parity, receipts, persistence, and API behavior;
- v2 positive/negative schema corpus;
- type, shape, semantic-flow, cardinality, default, edge, order, key, fan-out, and duplicate rejection;
- canonicalization metamorphic tests;
- compound mapped-port boundary, public-parameter binding, recursion, cycle, provenance, and implementation-closure tests;
- closed metadata, canonical full-document bytes, content/graph identity separation, and API round-trip golden vectors;
- independent vector/prefix parity and killed mutations;
- admission reproducibility, provenance, mismatch, immutability, concurrency, and owner isolation;
- SQLite and PostgreSQL empty/populated migration, restart, rollback/refusal, and recovery;
- API atomicity and versioned round-trip;
- protected-file hashes and relevant diff;
- documentation links, JSON parsing, section coverage, and programme DAG validation;
- current official review package and independent verdict.

Every command log records:

- timestamp;
- working directory;
- exact command;
- HEAD and relevant dirty snapshot identity;
- exit code;
- full stdout/stderr;
- environmental assumptions;
- whether the result is established fact, measured local evidence, policy, estimate, or unresolved.

No evidence from another snapshot may be called fresh.

## 12. Documentation and programme state

Only the active capsule owner edits:

- its declared design or plan paths;
- its task capsule;
- its evidence and report paths;
- CURRENT.md;
- PROGRAMME.json;
- .agent/review-package.json when its stopping condition requires a package.

State transitions are atomic:

1. dependency accepted;
2. one stage becomes ready;
3. owner creates the durable goal;
4. task completes its stopping condition;
5. evidence/report/package is current;
6. review stage becomes ready;
7. only an accepted verdict unlocks the next implementation stage.

Never mark work accepted because code exists or tests pass locally. Acceptance requires the stage’s named review or integration evidence.

## 13. Protected files and inherited work

At task entry, hash every protected path named by the capsule. At task exit, compare hashes and inspect any intentional change.

Never stash, reset, clean, checkout, or overwrite inherited dirty work. Other agents share the tree. Stop if an allowed-path edit overlaps an unexplained inherited change that cannot be reconciled.

The architecture goal protects all product code. Later capsules must specifically list money, broker, venue, provider, deployment, migration, registry, validator, resolver, evaluator, admission, and API files they may touch.

Changes to live broker/venue/provider implementations, deployment scripts, credentials, frontend source, and unrelated phase code remain prohibited unless a later owner-authorized capsule explicitly opens them.

## 14. Stop and owner gates

Stop immediately and report the exact blocker before:

- authoritative live IR;
- any material live sizing, routing, risk, protection, or execution change;
- action sinks or broker effects in IR;
- deployment, VPS, credentials, production data, or live money;
- destructive data or infrastructure work;
- licence-sensitive provider adoption or legal/regulatory/commercial decisions;
- frontend implementation;
- v1 compatibility removal, auto migration, or writer retirement;
- a second executable identity, registry, validator, resolver, evaluator, provider truth, or research ledger;
- changing accepted Phase 3 authority semantics;
- an unplanned migration head, destructive downgrade, or guessed legacy backfill;
- a material PROGRAMME dependency change not explicitly authorized by the owner;
- a protected-file or dirty-tree conflict;
- a required PostgreSQL or independent review gate that cannot run.

Record a later-phase issue as a finding with an exact target capsule. Do not implement it early.

## 15. Required nonclaims

Every capsule report states:

- this task does not prove production readiness;
- this task does not authorize deployment or live money;
- v2 is not authoritative live IR;
- the React/Vite frontend cannot author v2 unless a later accepted capsule proves it;
- v1 remains supported;
- Phase 4 market truth is not implemented by IR v2;
- local SQLite or PostgreSQL evidence does not prove production capacity, recovery, security, cost, or provider compliance;
- the exact 22 category-D baseline failures remain unaccepted unless a later exact capsule resolves them;
- no untested provider, component, strategy family, data mode, or execution path is implied.

## 16. Final gate

The Component IR v2 interphase is complete only when:

1. architecture review has SPEC: PASS and QUALITY: PASS;
2. every implementation capsule has met its stopping condition;
3. integration evidence binds to the exact reviewed snapshot;
4. v1 golden compatibility passes;
5. v2 schema, topology, content/graph identity, compound port/parameter binding, evaluation, admission, migration, and API gates pass;
6. required killed mutations pass;
7. disposable PostgreSQL evidence passes;
8. no unresolved source conflict, protected-file drift, or deployability obligation remains vague;
9. the independent implementation reviewer returns SPEC: PASS and QUALITY: PASS;
10. CURRENT and PROGRAMME then, and only then, make phase4-architecture ready.

A FAIL, REJECT, UNVERIFIABLE, stale package, missing log, or mismatched hash keeps Phase 4 blocked.

## 17. Final report

The owner of each task returns a concise report containing:

- capsule id and durable-goal status;
- exact files changed;
- decisions made and rejected alternatives;
- child assignments used, dependency timing, and integration result;
- commands run and evidence paths;
- test and mutation results;
- migration and deployability impact;
- protected-file and dirty-tree result;
- remaining nonclaims and findings;
- review-package or verdict path where applicable;
- the exact next ready stage;
- any owner decision required.

Do not call a proposal accepted, implementation complete, phase unlocked, release deployable, or system production-ready without the exact authority named above.
