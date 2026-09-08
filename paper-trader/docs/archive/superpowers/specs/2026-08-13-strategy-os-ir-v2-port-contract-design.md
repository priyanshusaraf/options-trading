# Strategy OS Component IR v2 port-contract design

Status: PROPOSED FOR INDEPENDENT REVIEW\
Architecture goal: phase3-4-ir-v2-acceptance\
Date: 2026-08-16\
Authority boundary: architecture only; no product code, migration, frontend, deployment, credential, production-data, or live-authority change

## 1. Decision

Component IR v2 is a versioned extension of the accepted Phase 3 causal strategy contract. It is not a second strategy language, registry, validator, resolver, evaluator, research ledger, executable identity, or deployment authority.

The accepted design has these properties:

1. One public IR façade dispatches an immutable document by explicit format_version.
2. Version 1 behavior and persisted evidence remain readable, resolvable, evaluable, and admissible without reinterpretation.
3. Version 2 adds exact component classification, typed ports, explicit input cardinality, stable edge bindings, and deterministic compound resolution.
4. PlatformRegistry remains the single authority for component versions, component bodies, implementation identities, and type descriptors.
5. A graph has fixed topology. Runtime values may select data or conditions, but they do not add nodes, ports, or edges.
6. One canonical executable graph address identifies v2 semantics. The admission_address remains the only execution-authority binding.
7. Phase 4 owns canonical market identity, effective-time rulebooks, provider observation truth, provenance, missingness, and numerical-validity semantics. IR v2 supplies typed seams only.
8. Version 2 cannot grant live authority, produce broker effects, or bypass Phase 3 admission.

The preserved draft is rejected where it proposed generic object payloads, duplicated domain/structural labels on ports, action-flow sinks, runtime branch manifests, immediately read-only v1 writers, several competing semantic identities, or new identity columns on every money record.

## 2. Current accepted boundary

Phase 3 is accepted only at the evidence named by CURRENT.md. The current repository implements:

- format_version 1 graph documents with sockets and wire_type;
- closed validation and component-registry resolution;
- one source per target input;
- vector and independent prefix-stream evaluation;
- transitive implementation identity;
- immutable admission receipts addressed by admission_address;
- owner-scoped execution and research persistence;
- an admission_address link on downstream execution, research, deployment, position, intent, and trade facts.

The React/Vite editor and backend APIs currently author and exchange the v1 socket shape. Disabling v1 writes before a separately authorized frontend transition would break an accepted product path. IR v2 therefore starts as an additive backend capability.

The following claims remain false:

- Phase 4 market truth exists;
- v2 is implemented;
- v2 is the product default;
- the frontend can author v2;
- any deployment is release-ready;
- any live strategy has authoritative v2 IR;
- the 22 exact category-D baseline failures are accepted.

## 3. Scope and exclusions

### 3.1 In scope

- document version dispatch;
- intrinsic component classification;
- exact type descriptors in the existing registry;
- closed port contracts;
- explicit edge binding and cardinality;
- deterministic compound boundaries and nested provenance;
- v2 validation, resolution, evaluation, hashing, admission, persistence, and versioned backend API contracts;
- lossless coexistence with v1;
- evidence and migration requirements;
- the dependency gate before Phase 4.

### 3.2 Out of scope

- broker commands, order intents, execution effects, or action sinks;
- authoritative live IR;
- live sizing, routing, risk, protection, or execution changes;
- dynamic graph topology or runtime-created ports;
- provider adapters, canonical instrument implementation, market-data normalization, missingness rules, or numeric-validity implementation;
- frontend implementation or v1 writer retirement;
- production deployment, infrastructure, credentials, VPS access, or production data;
- licence, legal, regulatory, pricing, and commercial decisions;
- removing v1 compatibility.

## 4. One public architecture

### 4.1 Public façade

Existing public entry points remain the single conceptual path:

- validate(document, registry)
- resolve(document, registry)
- evaluate(resolved_graph, inputs)
- evaluate_prefix(resolved_graph, inputs)
- build_admission(document, registry, evidence)

They dispatch on format_version. Format-specific modules may exist as private implementations, but callers do not choose a second registry, resolver, evaluator, receipt builder, or authority model.

Dispatch rules:

- missing format_version is rejected;
- integer 1 selects the frozen v1 contract;
- integer 2 selects the v2 contract only after the relevant implementation capsule is accepted;
- booleans, strings, floats, unknown integers, and negotiated guesses are rejected;
- no automatic upgrade or downgrade occurs;
- the source document bytes and selected format are retained in evidence.

### 4.2 One PlatformRegistry

PlatformRegistry remains immutable after construction and remains the only registry passed to validation, resolution, hashing, and admission. It gains version-aware descriptors; it does not gain a sibling V2Registry.

The registry owns:

- component_id and component_version;
- component classification;
- public parameter schema;
- public input and output port contracts;
- optional compound body;
- implementation identity closure;
- type_id and type_version descriptors;
- deterministic registry snapshot identity.

A registry snapshot must fail construction when a referenced type, component, compound body, or implementation identity is absent or conflicting.

## 5. Canonical v2 document

### 5.1 Top-level shape

A v2 document is an immutable closed object with these required document fields:

    {
      "format_version": 2,
      "strategy_id": "owner-defined-stable-id",
      "strategy_version": 7,
      "metadata": {
        "metadata_version": 1,
        "name": "Momentum crossover",
        "description": null,
        "tags": []
      },
      "graph_inputs": [],
      "graph_outputs": [],
      "nodes": [],
      "edges": []
    }

All eight top-level keys are required and every other top-level key is rejected. metadata is the only v2 descriptive envelope. It is a closed object with exactly metadata_version, name, description, and tags. metadata_version is the integer 1; booleans are not integers here. name and description are either null or NFC-normalized Unicode strings. tags is a duplicate-free array of non-empty NFC-normalized Unicode strings; canonicalization sorts it by Unicode code point. Unknown metadata keys, unknown metadata versions, invalid UTF-8, non-NFC strings, and duplicate tags fail validation. Input ordering of tags has no stored meaning.

Metadata is structurally validated and enters content_address, but cannot influence executable validation, resolution, evaluation, graph_address, evidence sufficiency, or admission semantics. Viewport, node coordinates, colors, editor groups, comments, and every other presentation field are forbidden in metadata and live only in a separately stored presentation document with an optional presentation_address. The initial v2 backend contract does not define that presentation document; frontend design remains owner-gated.

strategy_id and strategy_version are lineage labels. metadata and those lineage labels are non-executable document facts. They do not enter graph_address and do not grant deployment authority.

### 5.2 Node reference

Each node has:

    {
      "node_id": "stable-within-document",
      "component": {
        "component_id": "sma",
        "component_version": 3
      },
      "parameters": {}
    }

node_id is unique inside the document and participates in canonical topology. A node cannot override its component classification, ports, parameter schema, body, or implementation identity.

### 5.3 Intrinsic component classification

Every registered v2 component version has two independent required axes:

- domain_family: market_data, transform, indicator, signal, condition, temporal, state, portfolio, risk, intent_description, utility, or another accepted closed registry value;
- structural_role: source, transform, decision, stateful, selector, aggregator, boundary, or sinkless_terminal.

These axes classify a component version, not each port and not a graph instance. Resolved nodes inherit them from the registry. A future extension of either vocabulary requires an architecture change, registry-version evidence, and compatibility analysis.

intent_description may describe a typed intended action as data. It cannot submit, route, size, or authorize an order. No execution_effect or broker_action structural role exists in v2.

## 6. Type system

### 6.1 Exact type references

Every port references one exact immutable type descriptor:

    {
      "type_id": "strategy-os.float64",
      "type_version": 1
    }

The descriptor is resolved from PlatformRegistry. Generic object, any, wildcard, duck typing, and implicit numeric widening are forbidden.

A descriptor defines:

- canonical serialization;
- equality and hashing;
- runtime representation;
- permitted shape;
- missingness representation, if any;
- exact validation;
- compatibility identifiers, if explicitly declared.

IR v2 initially needs only types that can be proven against the current runtime. Phase 4 adds market-identity, observation, provenance, validity, and rulebook types through reviewed registry changes.

### 6.2 Shape

Port shape is one closed value:

- scalar;
- series;
- event_stream.

Shape is part of the type contract and must agree with the registered descriptor. Shape is not a substitute for input cardinality. A series payload can still arrive through one input connection; bounded_many describes several connections, not a vector value.

### 6.3 Compatibility and conversion

Compatibility is exact type_id, type_version, and shape equality unless an input contract names a finite allow-list of exact compatible descriptors. A compatible descriptor must share the same canonical runtime representation and semantics. The validator records which allow-list member matched.

Semantic conversion uses an explicit registered conversion component. Validation cannot silently cast, align, broadcast, fill, truncate, resample, or coerce.

## 7. Port contract

### 7.1 Common fields

Every public port has:

    {
      "port_id": "stable-within-component-version",
      "direction": "input",
      "semantic_flow": "value",
      "semantic_role": "lookback_series",
      "type_ref": {
        "type_id": "strategy-os.float64-series",
        "type_version": 1
      },
      "shape": "series"
    }

Closed semantic_flow values are:

- value: a data value;
- condition: a typed truth/condition value;
- event: a typed occurrence record;
- control: a typed non-effectful selection or lifecycle signal.

action is not a v2 semantic flow. Broker side effects remain outside the graph contract.

display_name and help text may exist in metadata. They are not executable.

port_id stability is scoped to one component version. Removing, renaming, or changing an executable port requires a new component_version.

### 7.2 Input connection contract

An input port adds:

    {
      "connections": {
        "cardinality": "bounded_many",
        "min": 1,
        "max": 4,
        "assembly": "ordered"
      }
    }

Allowed cardinalities and exact bounds:

| cardinality | min | max |
| --- | ---: | ---: |
| single | 1 | 1 |
| optional | 0 | 1 |
| bounded_many | integer at least 0 | finite integer at least min and at least 2 |
| variadic | integer at least 0 | null |

The bounds are canonical. A separate required flag is forbidden because it can contradict min.

Allowed assembly values:

- single for single and optional;
- ordered for bounded_many or variadic when position is meaningful;
- keyed for bounded_many or variadic when a unique key is meaningful;
- unordered for bounded_many or variadic only when the component contract proves order independence.

An input default is permitted only when min is zero. The default is part of the component version, must validate as the exact input type, and is used only when the resolved incoming set is empty. An edge and a default never both provide a value. Hidden environment defaults and default_source are forbidden.

### 7.3 Output contract

An output has no connections object and no default. Output fan-out is topology: several edges may reference an output if every target contract accepts the exact type and shape. The resolver preserves every edge.

### 7.4 Component parameter contract

Parameters use a closed versioned schema owned by the registered component version. Requiredness, default, enum, numeric domain, units, and canonical serialization must be explicit. Runtime environment values cannot alter parameters after admission.

## 8. Edge and binding contract

### 8.1 Endpoint

Each edge has a stable edge_id and two explicit endpoints:

    {
      "edge_id": "price-to-fast-1",
      "source": {
        "scope": "node",
        "node_id": "price",
        "port_id": "close"
      },
      "target": {
        "scope": "node",
        "node_id": "fast_sma",
        "port_id": "values"
      },
      "binding": {
        "kind": "single"
      }
    }

Endpoint scope is one of node, graph_input, or graph_output. node_id is present only for node scope. Direction is interpreted at the named scope:

- a node source names a registered component output and a node target names a registered component input;
- a graph_input keeps direction input because it is the graph's external input contract, but it is a source inside that graph and can never be an edge target;
- a graph_output keeps direction output because it is the graph's external output contract, but it is a target inside that graph and can never be an edge source;
- every graph_output has exactly one internal producer; and
- a graph_input-to-graph_output edge is permitted only when the exact type, shape, and semantic contract agree.

graph_inputs and graph_outputs use the same executable public-port fields as a component boundary. A compound component's public input must equal its body graph_input, and its public output must equal its body graph_output. This scope rule preserves exact compound boundary equality without relabelling an external input as an output merely because it fans out inside the body.

edge_id is unique inside the document, participates in canonical topology, and survives validation, resolution, evaluation traces, parity evidence, and admission provenance.

### 8.2 Binding

Binding must agree with the target assembly:

- single: no position or key;
- ordered: non-negative integer position;
- keyed: non-empty canonical string key;
- unordered: no position or key.

A graph_output target always uses single binding. Its exactly-one-producer boundary invariant replaces a component input's connections object. Resolved input bundles are produced for component inputs; a graph output records its one resolved producer with edge_id and exact type evidence.

For one target input:

- ordered positions must be unique and contiguous from zero after resolution;
- keyed keys must be unique;
- duplicate source-target-binding tuples are rejected;
- every edge counts toward min and max;
- unordered evaluation receives a canonically edge_id-sorted collection, while the component contract must prove output independence from collection order.

The document array order never supplies semantic order. Reordering JSON fields, nodes, or edges cannot change graph_address or evaluation.

### 8.3 Resolved input bundle

The resolver does not collapse a target to one source. It produces an immutable bundle:

    {
      "target": {
        "scope": "node",
        "node_id": "combine",
        "port_id": "values"
      },
      "assembly": "ordered",
      "members": [
        {
          "edge_id": "edge-a",
          "binding": {"kind": "ordered", "position": 0},
          "source": {
            "scope": "node",
            "node_id": "price",
            "port_id": "close"
          },
          "type_ref": {
            "type_id": "strategy-os.float64-series",
            "type_version": 1
          }
        }
      ],
      "default": null
    }

Vector and prefix-stream evaluators consume the same resolved bundle type through independent implementations. Each evaluator records edge_id in diagnostic provenance.

## 9. Fixed topology and dynamic instruments

IR v2 topology is fully known at validation:

- all nodes and component versions are pinned;
- all public ports are registry-defined;
- all edges and bindings are present;
- all compound bodies are pinned;
- no runtime branch creates, removes, or rewires topology.

Dynamic derivative identity is a Phase 4 data problem, not graph mutation. A fixed selector component can consume canonical candidate observations and emit one canonical instrument reference as a typed value. Downstream fixed nodes consume that value. Lifecycle and roll events are typed data with provenance. They do not create new graph ports.

Conditional behavior uses ordinary fixed components that select typed values or conditions. A future switch component must be a normal registered component whose input/output and evaluation semantics are deterministic. Runtime branch manifests from the preserved draft are rejected.

## 10. Compound components

A compound component version has:

- one public component contract;
- one immutable v2 body template;
- a deterministic mapping from each public input to exactly one body graph input;
- a deterministic mapping from each body graph output to exactly one public output;
- one closed parameter_bindings table mapping every public parameter to one or more direct body-node parameter slots;
- pinned nested component versions;
- a transitive implementation-identity closure.

The body template uses the ordinary v2 graph, node, edge, and parameter shapes but is not independently publishable. A body-node parameter key is either a literal in that node's parameters object or a target in parameter_bindings, never both. One binding has exactly public_parameter_id and a non-empty targets array; each target has exactly node_id and parameter_id. Unknown keys are rejected. A target may name the public parameter of a directly nested compound node; that nested component applies its own closed table during recursive resolution.

Registry construction rejects a compound unless all of these parameter rules hold:

- every public parameter has exactly one binding entry and every target slot is unique across the table;
- every public parameter and target parameter exists at the pinned component version;
- the public and target parameter descriptors are canonically byte-equal, including type, requiredness, default, enum/domain, units, and scalar serialization;
- a body literal cannot occupy a bound target and an omitted body parameter is legal only when ordinary schema/default rules allow it or exactly one binding supplies it;
- no binding contains a transform, expression, coercion, default override, environment lookup, or runtime lookup; conversion requires an explicit registered component; and
- the body template, binding table, public schema, nested component closure, and their canonical bytes enter the compound component definition, implementation identity, and registry snapshot identity. Any change requires a new component_version.

Ordinary component parameter binding first validates the compound node's public parameter object and produces a canonical present value, explicit default, or canonical absence for every public parameter. Compound resolution copies that exact state to every target slot. It does not re-default, coerce, or reinterpret the value at the target. Internal literal parameters remain immutable. Resolved provenance records the public parameter id, its canonical value or absence, the compound instance path, and every full nested target node/parameter path. Vector and prefix evaluators consume the same resolved parameters through independent implementations.

The registry separately rejects a compound when any mapped public port field differs from its body boundary port, including:

- port_id;
- direction;
- semantic_flow;
- semantic_role;
- type_ref and shape;
- connection cardinality, bounds, and assembly;
- default.

Parameter schemas and component classification are component-level facts, not body-boundary port fields, so no public/body equality rule applies to either. Resolution recursively expands compound body templates and parameter bindings, detects component and body cycles, and retains the full nested instance path plus public/internal edge_id and parameter-target provenance. graph_address contains the outer node's exact component version and canonical public parameters; the pinned version closes the immutable body and binding semantics through the registry. Flattening may change an internal representation, but it cannot change graph_address, output, resolved parameters, or provenance.

## 11. Validation

Validation is pure, deterministic, and closed. It returns either a canonical validated document or ordered structured errors. At minimum it proves:

1. exact format dispatch;
2. closed top-level and nested keys;
3. canonical identifier syntax and uniqueness;
4. every component and type exists at an exact version;
5. component parameters validate;
6. endpoints exist and directions agree;
7. source and target type, shape, and semantic flow are compatible;
8. every target satisfies cardinality min and max;
9. every binding agrees with target assembly;
10. ordered positions and keyed keys are unique;
11. defaults are legal and type-valid;
12. graph inputs and outputs have exact boundary contracts;
13. no cycle exists unless a separately accepted explicit state-cycle contract is present; v2 initial implementation accepts only acyclic graphs;
14. compound mapped-port equality and complete, exact, conflict-free public-parameter binding hold;
15. all implementation identities close transitively;
16. metadata cannot affect executable projection;
17. serialization round-trips without semantic drift.

Errors are stable codes with precise document paths, component references, node paths, port ids, and edge ids. Validation order is deterministic.

## 12. Evaluation

The evaluator operates only on a validated resolved graph and exact typed external inputs. It cannot:

- read unpinned registry state;
- call a provider or broker;
- consult wall-clock time implicitly;
- mutate graph topology;
- coerce missing or invalid values;
- use display or layout metadata;
- produce a broker effect.

Each component implementation accepts its parameter values and resolved input bundles. Stateful components must declare state schema and deterministic transition rules in a later accepted component contract; no implicit process-global state is allowed.

Vector and prefix-stream evaluators remain independent parity oracles. A v2 result is admissible only when supported components pass causal prefix parity under the same canonical inputs, costs, and validity policy. Phase 4 supplies the validity policy; v2 does not invent it.

## 13. Serialization and identity

### 13.1 Canonical projections

V2 has distinct facts, not competing authorities:

- content_address: hash of the canonical bytes of the complete immutable published document, including required non-executable lineage and metadata fields;
- graph_address: hash of the canonical executable projection;
- presentation_address: optional hash of editor-only presentation state;
- admission_address: hash of the immutable causal admission receipt.

graph_address is the one canonical executable graph identity. content_address proves which canonical document value was stored, not the incidental whitespace or object-key order of an HTTP request. presentation_address cannot be used for admission. admission_address remains the only authority referenced by deployment and money records.

### 13.2 Canonical executable projection

The executable projection includes only document-owned executable semantics:

- format_version;
- canonical graph inputs and outputs;
- nodes by node_id with exact component versions and canonical parameter values;
- edges by edge_id with exact endpoints and bindings;

Exact component and type references are part of that projection. The full registry snapshot, implementation identities, evidence, ownership, presentation state, and admission facts are not graph-owned semantics and do not enter graph_address. A component implementation change must publish a new component_version rather than silently changing the meaning of an existing reference.

It excludes display names, descriptions, comments, viewport, node coordinates, colors, editor groups, and timestamps.

The one serializer for both canonical projections is backend/app/ir/hashing.py canonical_json: UTF-8 JSON, object keys sorted lexicographically, no incidental whitespace, ensure_ascii false, no NaN or infinity, normalized integer representation, and registry-defined scalar encoding. Arrays retain order where this contract assigns semantic order and are sorted before serialization where this contract declares set semantics; metadata tags, nodes by node_id, and edges by edge_id are such canonical sorts. Validation rejects duplicate semantic keys before sorting. Golden cross-process vectors pin exact bytes so a later non-Python client cannot choose a different escaping or number representation.

content_address is the lowercase `sha256:` address produced by backend/app/ir/hashing.py content_address over the complete canonical validated document value: format_version, lineage labels, the required closed metadata envelope, graph boundaries, nodes, and edges. Raw request bytes are transport evidence only and never this identity. graph_address uses the same serializer over only the executable projection and its explicit v2 identity_scheme_version. Reordering JSON object keys or metadata tags therefore preserves both addresses; changing descriptive metadata changes content_address only; changing executable semantics changes content_address and graph_address. Exact golden vectors and API read-after-write tests must prove these relations.

V1 graph_address behavior remains unchanged. V1 and v2 addresses can never be silently compared as the same identity because receipts include format_version and identity_scheme_version.

### 13.3 No duplicate authority

Resolved topology hashes, port-plan hashes, registry hashes, code identities, dataset identities, and evidence hashes may be embedded in the admission receipt as provenance. None becomes a second execution authority. Deployment, intent, position, and trade rows continue to reference admission_address.

## 14. Admission and persistence

### 14.1 V2 admission receipt

The v2 receipt extends the existing immutable Phase 3 receipt and includes:

- receipt schema version;
- format_version 2;
- content_address;
- graph_address;
- registry snapshot identity;
- exact component and type-version closure;
- transitive implementation identities;
- resolved topology with node paths, port ids, edge ids, bindings, and defaults;
- canonical input, dataset, fee, slippage, risk, parity, and causal-evidence identities required by Phase 3;
- owner identity and existing distinct research/deployment facts.

Admission fails closed when any required identity or evidence is absent, malformed, mutable, mismatched, or unverified.

### 14.2 Additive persistence

Implementation uses additive, reversible schema changes:

- execution migration after current head 0034;
- research migration after current head 0005;
- format_version and v2 semantic identity fields only where needed to query and verify immutable graph or receipt facts;
- no v2 identity columns added to every deployment, intent, position, or trade;
- existing admission_address references remain canonical;
- no admitted v1 receipt or graph row is rewritten;
- v1 backfill occurs only for facts deterministically derivable from stored canonical bytes;
- unverifiable legacy rows remain explicitly legacy, never guessed.

SQLite developer evidence and disposable PostgreSQL 16 evidence are both required for migration, rollback, restart, uniqueness, immutability, and populated-upgrade cases. Destructive downgrade refusal remains intact.

### 14.3 Compatibility matrix

| Capability | v1 during IR v2 implementation | v2 before frontend transition |
| --- | --- | --- |
| read stored document | required | required |
| validate and resolve | required unchanged | added by accepted capsules |
| vector/prefix evaluate | required unchanged | added for supported components |
| build admission receipt | required unchanged | added after parity/evidence gates |
| backend API read | required unchanged | versioned read added |
| backend API write | required unchanged | versioned write added only after API capsule |
| React/Vite authoring | required unchanged | unsupported |
| default new graph format | v1 | not default |
| auto migration | forbidden | forbidden |
| live authority | not changed | forbidden |

V1 writer retirement requires a separate owner-authorized frontend and compatibility capsule after all stored artifacts and receipts can be proved migrated or intentionally retained.

## 15. Versioning

A component_version changes for any executable change to:

- classification;
- port or parameter contract;
- type reference or shape;
- cardinality, assembly, or default;
- compound body;
- evaluation semantics;
- state schema;
- implementation identity.

Documentation-only display text may change without a component version only when it is demonstrably outside executable projection.

A format_version changes only for a document-language compatibility break. New components and types normally extend the registry without changing format_version.

Registry snapshot identity pins the exact set and implementation closure admitted. Mutable latest aliases are forbidden in executable documents.

## 16. Backend API and frontend boundary

The backend API must expose format_version explicitly in request and response schemas. Endpoints either:

- preserve their accepted v1 schema and behavior; or
- use a versioned discriminator and return an exact v1 or v2 document.

Unknown versions return a stable client error and do not persist partial state. A v2 write validates and canonicalizes the complete closed document before hashing or persistence. Read-after-write returns that canonical document value and preserves its exact content_address and graph_address; it does not promise the request's incidental whitespace, object-key order, or pre-canonical tag order.

No frontend source file is in scope for IR v2 implementation. A read-only frontend contract audit records all socket/wire_type coupling. A later owner-authorized frontend capsule must design authoring, rendering, error display, layout separation, compatibility, and rollback before v2 becomes a product default.

## 17. Phase 4 handoff

Phase 4 begins only after IR v2 architecture and implementation have separate accepted reviews. The following requirements are a binding handoff, not accepted Phase 4 design or implementation. The Phase 4 architecture goal must reconcile them with current code and produce exact implementation capsules.

### 17.1 Canonical instrument identity and point-in-time facts

Canonical instrument_id is an opaque, durable Strategy OS identity. A provider symbol, token, display name, current registry key, or broker account never becomes canonical identity. Defining economic terms are immutable for one identity; changing one creates a new instrument_id. They include, as applicable:

- asset class and contract kind;
- exact economic underlier or issuer relationship;
- venue and segment where those distinguish separately tradable contracts;
- contract currency and settlement or deliverable terms;
- for options, exact underlying instrument_id, right, exact decimal strike with currency and scale, and expiry instant or expiry date plus timezone and convention reference; and
- for futures, exact underlying instrument_id, contract month, expiry, settlement, and deliverable terms.

Each actually listed derivative contract has its own identity, including deep in- or out-of-the-money strikes. An ATM window is a data-selection policy, not an identity restriction. A continuous future or adjusted series is a separate non-tradable derived-series identity with pinned roll and adjustment policy; it never masquerades as the executable contract.

Mutable market facts are separate effective-dated assertions: symbols and aliases, provider mappings and tokens, listing and delisting, venue eligibility, tradability, lot size, tick size, freeze quantity, strike grid, sessions, auctions, holidays, expiry conventions, settlement rules, fees, corporate actions, and universe membership. Each assertion uses a half-open market-valid interval [valid_from, valid_to) and a separate knowledge interval recorded_at/superseded_at. Resolution requires both as_of_market_time and as_known_at, returns the exact assertion and rulebook addresses used, rejects overlaps, and represents gaps explicitly.

Underlying, derivative, listing, continuous-series, adjusted-series, and membership relationships are typed and effective-dated. Actual historical contract-master observations are preferred. A reconstructed contract or rulebook assertion is labelled reconstructed, pins method, input addresses, source, confidence, and knowledge time, and cannot claim observed historical truth. Historical replay must never substitute today's symbol master, strike grid, contract token, session calendar, or lot size.

### 17.2 Provider contracts, mappings, and observations

Data provider and execution broker remain separate roles. ProviderContract is immutable and versioned by provider, data product, schema, field meanings, units, source clocks, timezone convention, bar convention, adjustment policy, missing-value sentinels, granularity, limits, licence classification, and adapter implementation identity. Provider mappings are effective-dated facts from provider symbol/token space to canonical instrument_id and are scoped to the relevant provider product; account or connection entitlements are separate facts.

ProviderObservation is immutable source evidence. It retains provider contract, provider instrument key, raw or losslessly decoded payload address, provider event/source time, received time, sequence or quality fields, and adapter identity. It is not normalized market truth.

NormalizedMarketObservation is a separate canonical record containing canonical instrument_id, field/type, exact unit and scale, normalized value or a closed validity state, event/effective interval, availability and knowledge times, provider-observation address, transformation identity, provider-contract address, rulebook address, and adjustment, resampling, and missingness policy addresses. Normalization never erases or rewrites source evidence.

Provider capability is versioned independently for live data, historical data, and execution. Capability claims name exact markets, instruments, fields, depth, resolutions, history, freshness, rate and subscription limits, entitlements, and effective interval. There is no silent fallback to another provider or broker.

### 17.3 Time, causality, and provenance

Canonical instants are timezone-aware UTC values while the exchange timezone and session date remain explicit. Records distinguish at least event time, provider source time when supplied, received time, ingested/recorded time, available-as-of time, market-valid interval, and knowledge-valid interval. Completed bars use half-open windows and an explicit availability time. A forming bar is separately typed and cannot satisfy a completed-bar dependency. Historical replay sees only assertions and revisions available at its as_known_at cutoff.

Dataset and observation lineage pins source, owner, licence class, canonical instruments, provider contract and adapter, exact query, effective and knowledge windows, timezone/calendar, corporate-action and adjustment policy, missingness/validity policy, alignment/resampling policy, transformation chain, ordered bytes or source addresses, and ingestion code identity.

### 17.4 Closed validity and numerical policy

The minimum closed observation states are VALID, NOT_IN_SESSION, NOT_LISTED, NO_TRADE, MISSING, PROVIDER_UNAVAILABLE, STALE, INVALID, INSUFFICIENT_HISTORY, UNDEFINED, and OUT_OF_DOMAIN. A non-VALID record carries no fabricated numeric value. NO_TRADE is not zero. NaN, infinity, a provider sentinel, an empty string, or a missing row is never used as an implicit semantic state.

Validity is enforced at every boundary:

- ingestion preserves source evidence, converts a provider sentinel only under the pinned ProviderContract, and records malformed or non-finite values as INVALID with an exact reason;
- normalization may perform only documented semantics-preserving field, timezone, exact-unit, and canonical-identity transformations and must attach the rulebook and transformation versions;
- each indicator or custom component declares warm-up, domain, missing-input, invalid-operation, and propagation behavior; it cannot silently fill, clip, align, coerce, or shorten history;
- research pins the complete validity policy and records a typed no-result or blocks evaluation when a required input is not valid; and
- deployment preflight requires current capability, rulebook, freshness, alignment, and validity evidence before new exposure. A failed data gate does not disable already-authorized risk-reducing exits.

Provider semantic changes follow four levels. Level 0 is a proven representation-only normalization under unchanged meaning. Level 1 is operational change with unchanged semantics but new provenance and limit checks. Level 2 creates a new contract/capability version and requires affected revalidation. Level 3 is a semantic break and blocks affected research admission or deployment until explicitly resolved. Only Level 0 may be transparent to executable meaning.

### 17.5 CSV and user-supplied data

CSV is a distinct dataset-source class, not a pretend provider feed. Its immutable import manifest pins file hash, owner/uploader, import time, column and type mapping, canonical-instrument mapping method, timezone and calendar, units, adjustments, missingness rules, transformations, effective interval, and known provenance gaps. Unknown provenance stays explicit. Such a dataset may be used for research only under a declared policy; it cannot imply provider-grade freshness, live capability, redistribution rights, or executable suitability.

### 17.6 Cache and dataset identity

Phase 4 extends the accepted content-addressed dataset seam rather than creating another cache identity. The current ordered_dataset_address must incorporate, directly or through pinned addresses, canonical instruments, provider-contract and observation snapshot, rulebook, effective and knowledge windows, validity/missingness, alignment, resampling, corporate-action/adjustment, and transformation policies. Revised source data or revised semantics produces a new address. Mutable names, today's symbols, query labels, and unordered file sets do not identify a reusable dataset.

### 17.7 Cross-instrument requirements and later consumers

Phase 4 defines one typed DataRequirementPlan compile seam containing canonical roles or bounded selectors, exact fields and resolutions, history and warm-up, session policy, completed/forming-bar requirement, maximum age and skew, alignment rule, validity requirements, live/historical capability needs, universe breadth bounds, and subscription intent. It does not load every strike or subscribe to an unbounded universe.

- Phase 5 consumes registered market types plus field, history, warm-up, validity, and causal-completion requirements for node contracts.
- Phase 6 binds named strategy roles to canonical instruments, providers, products, accounts, capability versions, and preflight/revalidation reasons without changing graph identity.
- Phase 7 resolves reviewed dynamic selectors, option windows, recenter/roll policies, subscriptions, QoS, and resource plans against bounded fixed-topology intent.

Cross-instrument and cross-timeframe observations must name max age, max skew, alignment, session, stale-data, and missingness behavior. Last completed bar is the default higher-timeframe input. Any forming-bar use is explicit, causal, and replayable.

### 17.8 Ordered Phase 4 programme

The Phase 4 architecture goal must create dependency-ordered durable goals for:

1. canonical economic identity, effective-dated mappings, relationships, and rulebook storage/resolution;
2. provider contracts, raw observations, capability/provenance, CSV import contracts, and licence boundaries;
3. normalization, closed validity, numerical policy, and provider-change revalidation;
4. cross-instrument/timeframe alignment, DataRequirementPlan, content-addressed dataset integration, and end-to-end market-truth gates;
5. one serial integration goal; and
6. one independent Sol-high critical review with separate SPEC and QUALITY verdicts.

Each implementation goal has one Terra-medium owner. It may use at most four Luna-medium children only for declared disjoint mechanical work after the owner freezes the shared interface. Instrument identity, rulebook semantics, provider contracts, validity policy, causal alignment, migrations, integration, and acceptance claims remain with the owner. Phase 4 may add reviewed type descriptors and components through the same PlatformRegistry; it cannot create a second IR, identity, provider registry, observation truth, dataset identity, or research ledger.

### 17.9 Explicit deferrals and rejected assumptions

Phase 4 does not implement the Phase 5 node catalogue, Phase 6 deployment binding, Phase 7 dynamic runtime selection/subscription/QoS, Phase 8 frontend, Phase 9 broad adapter catalogue, Phase 10 commercial controls, or confidentiality system. It defines only the exact consumer seams those phases require.

The Phase 4 architecture must reject these assumptions unless direct evidence overturns them: provider token equals instrument identity; a current symbol master proves history; provider equals execution broker; one graph means one traded instrument; every timestamp means event time; float/NaN encodes validity; no printed trade means zero; ATM-only data defines the option universe; inferred contracts are observed contracts; provider fallback is harmless; cache names or symbols are identities; and a mutable rulebook or provider contract can reproduce past research.

## 18. Deployability impact

This design changes no runtime or deployment today. Its implementation would affect application code, API schemas, database migrations, stored artifacts, registry construction, and resource use. Each implementation capsule must therefore:

- state config, dependency, service, schema, migration, rollback, and resource effects;
- prove SQLite and PostgreSQL behavior where persistence changes;
- preserve the current safe local runtime;
- keep all live and deployment gates closed;
- assign any unproved production/capacity/recovery obligation to an exact future capsule.

No local test, migration success, or architecture acceptance proves deployability or production readiness.

## 19. Rejected alternatives

| Alternative | Decision | Reason |
| --- | --- | --- |
| Separate V2Registry and v2 public evaluator stack | reject | duplicates accepted authority and invites drift |
| domain_family and structural_role on every port | reject | classification belongs to the component version |
| generic object payload | reject | cannot validate, hash, or replay exact semantics |
| one cardinality field for both payload shape and incoming connections | reject | conflates independent contracts |
| array order as many-input semantics | reject | unstable under canonicalization and editors |
| action flow and execution sink | reject | crosses money and live-authority boundary |
| runtime branch manifest | reject | dynamic topology weakens determinism and admission |
| immediate v1 read-only mode | reject | breaks current API and frontend consumers |
| automatic v1-to-v2 upgrade | reject | cannot prove semantic equivalence |
| new v2 identity on every money row | reject | admission_address already binds canonical authority |
| v2 implementation before independent architecture review | reject | critical language and identity change needs rejection-first review |
| Phase 4 before accepted v2 implementation | reject | market-truth types would target an unsettled port contract |

## 20. Acceptance conditions

This architecture can pass only when:

- every mapped ir_v2 source section has a coverage or conflict disposition;
- every preserved-draft conflict is resolved explicitly;
- v1 compatibility and frontend non-support are unambiguous;
- schema, ports, edges, identity, compounds, admission, persistence, and versioning are internally consistent;
- implementation capsules are serially dependency-ordered and have exact ownership;
- Luna children are mechanical, disjoint, dependency-aware, and bounded to at most the available concurrency;
- migrations and final integration remain under one accountable Terra owner;
- Phase 4 depends on accepted IR v2 implementation review;
- targeted validators, structured-example parsing, path checks, and diff checks pass;
- one evidence-backed review package is independently reviewed with separate SPEC and QUALITY verdicts.

Until that review passes, this document is proposed architecture and grants no implementation or production authority.
