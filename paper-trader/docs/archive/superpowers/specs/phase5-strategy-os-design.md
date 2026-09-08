# Phase 5 Strategy OS architecture

Status: `ACCEPTED_ARCHITECTURE`\
Decision: `KEEP + HARDEN`\
Active capsule: `phase5-architecture`

## Operator outcome

A trader authors one immutable strategy through the five visible node families, researches the same semantics through scalable batch execution, and receives an explicit resource and provider requirement plan before any future deployment decision. Strategy OS refuses unsupported data, invalid numbers, hidden resource demand, and undeclared custom-node behavior. Phase 5 does not grant deployment, broker, live, order, or money authority.

## Architecture decision

Phase 5 keeps the accepted typed IR, canonical hash, validator, resolver, component registry, research lineage, dataset authority, and sole authority loader. It does not create a second strategy language, node registry, research ledger, cache identity, provider identity, deployment model, or execution runtime.

The first-party language grows through registered component descriptors and deterministic lowering into the existing IR. Five-family classification is mandatory user-facing metadata and accounting provenance. It is not a parallel executable representation.

The compiler emits a separately content-addressed `ResourcePlan`. The plan describes physical demand derived from exact strategy semantics, instrument roles, node versions, provider requirements, and lowering. It never grants authority. A tier-policy decision compares a ResourcePlan to a separately versioned policy. Tier and capacity-calibration versions stay outside strategy semantic identity.

## Contracts retained from the foundation

- One immutable semantic IR, validator, resolver, canonical hash, and component registry.
- One candle-to-frame path and one numeric validity rule.
- Completed-bar causality, declared alignment, explicit missing-data behavior, and next-bar execution where required.
- Canonical instruments belong to Strategy OS; provider products and broker tokens stay at adapters.
- Strategy, graph, admission, dataset, result, cache, requested binding, resolved deployment, authority, order, fill, position, and money records remain distinct facts.
- An immutable strategy version may describe several future instrument bindings, but bindings cannot mutate the graph or inherit authority from it.
- Paper and live books remain separate. ARM gates new entries only; risk-reducing exits remain available.

## First-party node contract

Every registered first-party node must declare at least:

- stable node identifier and immutable semantic version;
- one originating visible family from Type 1 through Type 5;
- typed inputs, outputs, and output mapping;
- market fields, canonical instrument roles, timeframe, resolution, history, warmup, session, and alignment requirements;
- stateless, rolling, recursive, or stateful classification plus initialization and reset policy;
- completed/partial-bar policy, missing-data policy, numeric-validity policy, and causal declaration;
- evaluation triggers and bounded trigger-rate model;
- batch/vector and incremental-streaming eligibility;
- research, paper, and live eligibility without granting any of those authorities;
- provider product/contract requirements;
- bounded compute, memory, history, state, storage, subscription, and fan-out profiles;
- independent mathematical or behavior reference provenance and conformance cases.

The canonical `first-party-node-contract/1` field universe is exactly:

1. `stable_node_id`;
2. `semantic_version`;
3. `visible_family` (`TYPE_1` through `TYPE_5`);
4. `input_types`;
5. `output_types` and named output mapping;
6. `required_market_fields`;
7. `required_resolution`;
8. `warmup_history`;
9. `execution_form` (`STATELESS`, `ROLLING`, or `RECURSIVE`);
10. `state_initialization`;
11. `state_reset_policy`;
12. `bar_policy`;
13. `missing_data_policy`;
14. `numeric_validity_policy`;
15. `causal_declaration`;
16. `evaluation_triggers`;
17. `streaming_support`;
18. `batch_support`;
19. `mode_eligibility`;
20. `provider_requirements`;
21. `resource_profile`;
22. `reference_provenance`.

The existing technical `domain_family` and `structural_role` fields remain compiler metadata. `visible_family` is an additional closed user-facing classification in the same registry descriptor, not a replacement registry or executable identity. Every node-contract document and its address enter the registry snapshot and ResourcePlan input identity.

Custom nodes must declare the same family and bounded resource profile or refuse admission. Fork and formula levels reuse declared inputs. Sandboxed Python and external signals may consume only declared inputs under explicit resource, data, causality, and tenant limits. Custom code cannot connect to brokers, fetch undeclared data, bypass authority, or place orders.

Level 3 sandboxed Python and Level 4 external signals default to unavailable or research-only. Runtime enablement requires an explicit security and owner-gated capsule covering process isolation, imports, network denial or allowlists, secrets, tenancy, bounded CPU/memory/state/rate, cancellation, audit, and external-signal authentication and replay. The Phase 5 language contract alone grants no executable custom-code or network authority.

## Five-family lowering and complexity accounting

Family consumption is charged to every fully lowered atomic node by the originating user-visible family. Reusable components, nested compounds, custom nodes, and common-subexpression sharing cannot hide structural cost. Runtime sharing may reduce measured physical work but never reduces lowered structural counts.

All limits are conjunctive. A family maximum never overrides authored total, fully lowered total, authored edges, compound depth, single-output fan-out, weighted resource demand, provider limits, tenant limits, or concurrency limits.

### Provisional beta complexity hypotheses — 2026-08-24

| Tier | Type 1 | Type 2 | Type 3 | Type 4 | Type 5 | Authored total | Lowered total | Authored edges | Compound depth | Fan-out |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Standard | 32 | 128 | 32 | 64 | 192 | 256 | 1,024 | 1,024 | 16 | 32 |
| Pro | 96 | 384 | 128 | 192 | 576 | 768 | 4,096 | 4,096 | 32 | 64 |
| Desk | 256 | 1,024 | 384 | 512 | 1,536 | 2,048 | 12,288 | 16,384 | 48 | 128 |

These values are dated beta hypotheses, not commercial promises. Architecture acceptance requires representative at-limit classification and stable first-above-limit refusal for every family and aggregate dimension. Absolute parser/compiler safety ceilings remain separate from tier entitlements.

## ResourcePlan

`ResourcePlan` is immutable and separately addressed from strategy semantics. Its complete field universe must include:

- exact source strategy and registry snapshot addresses;
- originating-family counts and fully lowered atomic counts;
- authored and lowered edge counts, compound depth, output fan-out, and custom-node classifications;
- canonical instrument roles and the future binding inputs required per role;
- evaluation clocks and bounded trigger-rate estimates;
- state initialization/reset classes, history windows, warmup, and memory windows;
- physical and derived subscription demand;
- provider product and provider contract addresses without adapter tokens;
- compute, memory, state, queue, cache, artifact, and storage demand;
- batch/vector and incremental-streaming support and parity obligations;
- dynamic option-window, ladder, shared-calculation, and deployment fan-out demand;
- exact plan algorithm/version and source evidence addresses.

Changing semantic nodes, lowering, resource profiles, provider requirements, instrument roles, or physical demand changes the ResourcePlan address. Changing a tier entitlement or calibration threshold does not change strategy semantic identity; it produces a new policy decision bound to the unchanged plan and policy versions.

### Canonical ResourcePlan schema

`resource-plan/1` is canonical JSON encoded by the existing content-address helper. Object keys are schema-fixed, arrays are sorted by their declared identity keys, addresses use the existing 71-character content-address grammar, counts and byte quantities are non-negative integers, and booleans never substitute for integers.

The exact top-level fields are:

- `schema`, `algorithm_version`, `authored_ir_address`, `resolved_graph_address`, `implementation_closure_address`, `registry_snapshot_address`, and `data_requirement_plan_address`;
- sorted `node_contract_addresses` and `provider_requirement_addresses`;
- `family_counts` with exactly `TYPE_1` through `TYPE_5`;
- `authored_node_count`, `lowered_node_count`, `authored_edge_count`, `lowered_edge_count`, `maximum_compound_depth`, and `maximum_single_output_fanout`;
- sorted `instrument_role_requirements`, `trigger_requirements`, `state_requirements`, `history_requirements`, `subscription_requirements`, `compute_requirements`, and `dynamic_window_requirements`;
- `memory_bytes_upper_bound`, `storage_bytes_per_day_upper_bound`, `cache_bytes_upper_bound`, `artifact_bytes_upper_bound`, and `queue_concurrency_upper_bound`;
- `mode_support`, sorted `assumption_addresses`, and `plan_address`.

Rates use the canonical `bounded-rate/1` pair `{events, per_seconds}` with positive integer denominator and greatest-common-divisor normalization. Compute uses integer microseconds per event. Memory, state, cache, artifact, storage, and network quantities use bytes. History uses bars plus timeframe seconds. Ladder demand uses levels. Option windows use maximum contracts and maximum churn events per bounded rate. No locale-dependent number, NaN, infinity, free-form unit, or observed telemetry enters ResourcePlan identity.

`provider-requirement/1` names required capability classes, exact fields, timeframe/history/freshness/depth/session/alignment, product and contract classes, and whether a value must be provider-supplied or may be locally derived. It selects no provider and carries no token, credential, entitlement, or adapter identity.

`resource-calibration/1` stores measured workload evidence separately. `resource-tier-policy/1` stores a dated provisional or accepted limit table plus measurement evidence addresses. `resource-tier-decision/1` binds one ResourcePlan address, one policy address, one calibration address, one owner/tier context, and a typed accept/refuse result. Policy or calibration changes can change only the decision address, never strategy semantics or ResourcePlan identity.

## Research execution and cache boundary

Historical research may use batch/vector execution and bounded parallel workers. Live-compatible components also need incremental state semantics. A shared conformance harness must compare independent references, batch output, streaming output, warmup, missing/invalid values, causality, reset behavior, and representative hostile inputs.

Cache identity includes semantic node version, parameters, canonical instruments, registry snapshot, dataset and provider evidence, time range/segment, adjustment, session, resampling, missing-data, alignment, and implementation/lowering versions. Cache reuse never grants admission, deployment, or execution authority.

Worker packaging, dependency locking, queue/artifact storage, bounded concurrency, cancellation, failure, retry, result finalization, and cost telemetry are Phase 5 implementation concerns. Architecture must assign each to an exact capsule and deployment evidence level.

Stateful nodes need one immutable snapshot contract before catalogue or runtime acceptance. It must define snapshot schema/version, source strategy/node addresses, last consumed causal event, state bytes, validity, reset policy, reset event, and creation evidence. Restart first reloads and verifies the exact snapshot, then applies any ordered session, position-close, expiry/roll, elapsed-window, or explicit reset event before consuming a newer input. Batch initialization and incremental initialization must produce the same prefix state. This contract remains a Phase 5 design blocker until the exact ordering and identity rules are frozen.

The accepted V1 reset rule is order-independent: every reset returns the node to its declared initial state. All reset reasons applicable after the snapshot and before the next causal input are collected into a sorted unique reason set and applied once before that input. Partial or non-commuting resets are outside V1 and refuse registration. Snapshots may be written only after a completed causal event and bind the exact strategy, resolved graph, node contract, implementation closure, dataset/evaluation context, last event address/time, state-byte digest, validity state, reset policy, and creation evidence. A stale identity, future event, invalid byte digest, or missing reset reason refuses restore. Batch and streaming engines consume the same canonical reset schedule and must produce identical prefix state.

## Instrument roles and future bindings

The semantic strategy records durable named roles such as `SELF`, observation roles, baskets, option structures, or execution targets. Phase 5 ResourcePlan retains their exact data, history, provider, state, trigger, and fan-out demands.

One immutable strategy version may later bind to several distinct canonical instruments. Each deployment binding, resolved contract, provider route, account, mode, capital, reservation, entry authority, and money record remains separate and is not created by Phase 5 architecture.

The GOLD/CRUDEOIL simultaneous-strategy case and one-strategy/three-instrument case must remain expressible and fully accounted. Phase 6 owns binding and account authority. Phase 7 owns measured capacity and runtime economics.

### Canonical role and binding-input vocabulary

Phase 5 reuses the existing data-requirement `instrument` record: a role ID matching the accepted lowercase identifier grammar plus one accepted instrument type: `PHYSICAL`, `ECONOMIC_SELECTOR`, or `CONTINUOUS_FUTURE`.

Each `instrument-role-requirement/1` adds only closed requirement metadata:

- `role_id`;
- `role_kind`: `EXECUTION_TARGET`, `OBSERVATION`, `REFERENCE`, `BASKET`, `DERIVATIVE_SELECTOR`, or `CONTINUOUS_RESEARCH`;
- `instrument_type` from the accepted three-value vocabulary;
- `cardinality`: `EXACT_ONE`, `BOUNDED_MANY`, or `DYNAMIC_WINDOW`;
- `maximum_members` (`1` for `EXACT_ONE`);
- sorted source requirement and provider-requirement addresses;
- `binding_input_kind`: `CANONICAL_PHYSICAL_ADDRESS`, `SELECTOR_POLICY_ADDRESS`, or `CONTINUOUS_SERIES_POLICY_ADDRESS`;
- `execution_eligible` and `research_only` booleans.

The role ID `primary` is the canonical lowering of legacy `SELF`. Other role IDs remain authored stable identifiers; their meaning comes from the closed `role_kind`, not naming conventions. A role cannot be both execution-eligible and research-only. `OBSERVATION`, `REFERENCE`, `BASKET`, and `CONTINUOUS_RESEARCH` never gain order authority. A dynamic window requires an explicit finite maximum. Unknown kinds, incompatible instrument/binding types, duplicate role IDs, or undeclared provider demand refuse compilation.

`binding-input-requirement/1` describes what a future Phase 6 binding must supply; it contains no resolved account, provider route, capital, mode, lease, order, or authority. Phase 6 alone writes a separately addressed resolved binding.

## Closed V1 catalogue inventory

`paper-trader/docs/reports/phase5-v1-catalogue.json` is the architecture authority for every named steer primitive. Each entry is assigned to `V1_REQUIRED`, `V1_CAPABILITY_GATED`, or `WAVE_2_DEFERRED`, with one visible family, subgroup, reference class, and owning implementation capsule. Production currently has zero v2 catalogue entries; the inventory is a contract, not an implementation claim. Catalogue size is never an acceptance gate: the shared conformance harness and complete registered universe are.

## Required runtime ordering

`phase5-graph-paper-attribution-schema` is a necessary, non-enabling dependency. It must separate full graph addresses from strategy-version labels on SQLite and disposable PostgreSQL 16 before graph-to-paper attribution can become reachable.

Phase 5 architecture must generate exactly one exclusive implementation capsule with contract identifier `P5-ADV-006-RUNTIME`. It depends on accepted graph-paper attribution schema and precedes every v2 claim, reclaim, worker, result, cache, broker, order, or money consumer.

That capsule must preserve the existing job lifecycle and sole authority loader. Direct SQLite and disposable PostgreSQL 16 evidence must cover claim, real process death, ownership loss, public-seam reclaim, exact current persisted-authority reload, stale-claimant fencing, and current-claimant-only exactly-once finalization. The schema alone grants no reachability.

## Verification and complete-universe gates

Every critical implementation capsule must name its complete claimed universe and an independently authored consumer:

- every registered first-party component and output;
- every node-contract field and family classification;
- every lowering rule and lowered leaf;
- every ResourcePlan field and resource-profile source;
- every provider requirement and canonical instrument role;
- every cache-key input;
- every job lifecycle state, transition, consumer, and side effect;
- every v2 claim/reclaim/worker/result/cache/broker/order/money entry point.

Presence counts do not prove coverage. At-limit and first-above-limit cases, omission tests, wrong-binding cases, real guard mutations, exact restoration, batch/streaming parity, process-boundary lifecycles, and one independent phase review provide acceptance evidence in proportion to risk.

## Deployment impact and nonclaims

The architecture is `architecture-changing`; each implementation capsule must declare its affected deployment dimensions and evidence ceiling. Phase 5 owns reproducible research-worker packaging, dependency locking, queue/cache/artifact storage, bounded concurrency, and production-shaped research-runtime design evidence. Local or disposable tests establish no release or production readiness.

This provisional start does not implement or accept Phase 5. It grants no frontend work, provider/broker integration, credentials, deployment, production data, live authority, sizing, routing, risk, orders, money movement, commercial pricing, or legal/regulatory decision.

## Architecture work completed for acceptance

Two capsule-declared audits completed:

1. existing implementation capability and reuse audit;
2. complete owner-steer source-coverage audit.

Their reports define the smallest dependency-ordered implementation capsules, exact deferrals, proportional tests, and seams to refactor or harden. No implementation capsule activates from this document until the programme handoff selects it.

## Audit assimilation and current blockers

The existing-capability audit SHA-256 is `c6784211611defcabebb61aaa3a7d638f85db3a1553c6047fdf2d3be3a4d2330`. The source-coverage audit SHA-256 is `30eb896d5bbbcc5403c6974fa796b6cf3df3e7d89f319e3cf6f74c1d48d7af10`. Both return `KEEP + HARDEN`; neither accepts the Phase 5 design.

Current implementation facts:

- `PlatformRegistry`, v2 schema/validation, resolver/lowering, authored attribution, canonical hashes, vector evaluator, prefix-stream oracle, Phase 4 dataset/cache authority, and sole authority loader are reuse seams.
- The technical v2 `domain_family` vocabulary is not the required five user-visible families.
- Production constructs one registry with v1 contributors only. The production v2 catalogue universe is exactly zero entries; test registries grant no product catalogue claim.
- `DataRequirementPlan` is the predecessor for exact instrument role/type, field, timeframe, history, freshness, depth, session, alignment, provenance, and plan identity. It is not a complete ResourcePlan.
- Canonical physical instruments and provider entity/product/contract facts already exist. Phase 5 requirements must address those facts, not copy provider strings or tokens.
- `BacktestRun` has one five-state lifecycle: `pending`, `running`, `done`, `error`, and `cancelled`. Existing claim, heartbeat, fenced result, completion, cancellation, and reclaim seams must be hardened, not duplicated.
- The sole v2 loader correctly ends at `V2_RUNTIME_UNAVAILABLE`. No implementation slice may remove that terminal boundary except the exclusive `P5-ADV-006-RUNTIME` capsule.

This revision closes the audit decisions as follows:

1. The canonical role and binding-input vocabulary extends the accepted data-requirement instrument record and current instrument-type enum; it introduces no parallel instrument identity.
2. `resource-plan/1`, bounded-rate normalization, provider requirements, calibration, tier policy, and decision identities now have exact fields and units above.
3. `phase5-v1-catalogue.json` freezes every named steer primitive by family, subgroup, risk disposition, owner, and exact wave-2 home. Catalogue count alone remains non-authoritative.
4. `state-snapshot/1` and the order-independent reset-set rule freeze restart, expiry/roll, and batch/incremental initialization semantics.
5. Level 3/4 contracts remain required, while runtime stays disabled until a separate security and owner gate passes.
6. Provider compatibility stays fixture-only; release, production, credentials, network, and commercial claims remain closed.

The strict runtime ordering resolves the audit-plan tension: `phase5-graph-paper-attribution-schema` closes first. The sole `phase5-adv-006-runtime` capsule then closes `P5-ADV-006-RUNTIME` before any named v2 consumer becomes reachable. Static language/resource contract work may proceed only when it has no v2 consumer reachability. Catalogue, custom, research, sweep/cache, packaging, broker, order, and money consumers all depend transitively on the accepted runtime capsule.
