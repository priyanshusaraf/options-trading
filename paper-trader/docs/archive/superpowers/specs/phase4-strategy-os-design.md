# Phase 4 Strategy OS design

## 1. Decision and boundary

Phase 4 adds market truth, numeric validity, and data-capability contracts to the accepted Strategy OS architecture. It extends Component IR v2 and the existing research, backtest, cache, ownership, and admission seams. It does not create a parallel strategy language, resolver, hash, registry, provider authority, research ledger, or deployment authority.

The operator outcome is a refusal-first answer to four questions before research or activation:

1. Which canonical instruments and market rules existed at the evaluation time?
2. Are every node's inputs valid, causal, sufficiently warm, and aligned?
3. Can the selected data source supply the required fields, history, resolution, and freshness for the requested research, paper, or live mode?
4. Which immutable dataset and rule identities produced the answer?

Phase 4 product implementation, frontend work, provider adapters, authoritative live IR, money authority, deployment, credentials, production data, and destructive work remain blocked until their own capsules and owner gates open them.

## 2. Existing architecture verdicts

| Contract | Verdict | Phase 4 treatment |
| --- | --- | --- |
| Component IR v2 schema, validator, resolver, hash, registry, and prefix runtime | KEEP + HARDEN | Add closed validity/data-requirement declarations through the accepted registry and format dispatch. Do not fork evaluation or identity. |
| Canonical candle-to-frame conversion in `app/market_data/candles.py` | KEEP + HARDEN | Preserve the single conversion seam and attach explicit observation/validity metadata around it. |
| Backtest content-addressed identity and cache | KEEP + HARDEN | Extend answer-changing identity with dataset, instrument-master, rulebook, adjustment, missing-data, alignment, and component implementation digests. |
| Admission receipts and owner-scoped immutable research lineage | KEEP + HARDEN | Bind Phase 4 assessment and provenance digests without treating admission as capability, deployment, or live authority. |
| Broker registry and venue capability declarations | DEFER | Frozen provider/execution files remain unchanged. Phase 4 defines data-capability contracts only; Phase 9 owns adapter implementation and broad provider conformance. |
| String instrument keys and current-symbol convenience paths | REFACTOR | Keep compatibility at adapters while new market-truth seams use canonical physical identity and explicit economic selectors. Do not rewrite held-position attribution in this phase. |
| NaN-to-false and scattered finite-value checks | REPLACE at the IR/data boundary | Retain local defensive checks where needed, but executable Phase 4 values use one closed validity envelope. No second numeric engine is permitted. |
| Present-time schedules or inferred derivative universes used as historical truth | REJECT | Historical paths must use immutable point-in-time snapshots or identify reconstruction explicitly and fail any ground-truth claim. |
| Frontend readiness or capability presentation | DEFER | Phase 8 owns operator workflow after backend truth exists. Phase 4 exposes no frontend implementation authority. |

The final audit report may refine file-level evidence, but it may not change these invariant-level dispositions without an owner gate.

## 3. One accepted executable architecture

The accepted flow remains:

`IR document -> validate -> resolve with PlatformRegistry -> resolved graph/implementation identity -> evaluate/admit`

Phase 4 adds inputs and receipts around that flow:

`MarketTruthSnapshot + DatasetManifest + CapabilityProfile + EvaluationPolicy -> DataRequirementPlan -> CapabilityAssessment -> EvaluationContext`

The existing resolver remains pure. It accepts immutable Phase 4 identities or returns structured refusal; it does not query providers, databases, clocks, or research services. The data-requirement compiler reads the resolved graph and registry metadata. It does not reinterpret graph topology. Evaluation consumes an already resolved context. Admission records Phase 4 digests but does not manufacture them.

Presentation state, provider transport symbols, connection secrets, current clock time, requested deployment assignment, and mutable cache state never enter graph identity. Answer-changing market/data identities enter the resolution or result receipt that owns the answer.

The authored IR content address remains the identity of the authored document alone. Registry declarations, implementation addresses, bound data requirements, market truth, and datasets do not enter or rewrite that address. A Phase 4 resolution receipt binds the authored IR address to a separate registry snapshot address, resolved graph address, and implementation-closure address. Every later plan, assessment, result/cache record, and admission names those separate facts rather than collapsing them into a second executable identity.

## 4. Closed numeric validity contract

### 4.1 Vocabulary

Every Phase 4 executable scalar, series element, and boolean has one closed validity state:

- `VALID`
- `MISSING`
- `STALE`
- `INSUFFICIENT_HISTORY`
- `MATHEMATICALLY_UNDEFINED`
- `PROVIDER_UNAVAILABLE`
- `NOT_IN_SESSION`
- `NOT_LISTED`
- `NO_TRADE`
- `INVALID`

Unknown states fail validation. `VALID` carries a finite typed value. Every other state carries no executable value and may carry canonical, non-secret diagnostic facts. NaN and infinity are never valid transport or receipt values. `INVALID` means malformed input, an explicitly rejected policy result, or multiple different invalid causes; it is not a substitute for a more precise known state.

### 4.2 Propagation

- Operators declare validity behavior in the accepted component registry alongside type, warmup, causality, and ports.
- A unary operator propagates its invalid input unless its declared policy handles that exact state. Domain failures return `MATHEMATICALLY_UNDEFINED`.
- A multi-input operator returns the shared invalid state when all invalid inputs agree. Different invalid states return `INVALID` with a canonical sorted cause set. It never selects one cause by accidental argument order.
- Comparisons and boolean operators preserve invalidity. They do not coerce invalid to false.
- Explicit fallback is a typed graph operator with declared accepted states, output provenance, and identity. There is no implicit forward fill, zero fill, or provider substitution.
- Required warmup is computed before evaluation. Shortening a window or treating a partial warmup as valid is forbidden.

For entry gating, only `VALID(true)` may authorize a new entry. `VALID(false)` declines entry. Any invalid state blocks entry and records the reason. Phase 4 does not change exit authority: existing risk-reducing exits, kill switches, and protection paths remain available when entry inputs are invalid.

## 5. Canonical instrument and market-truth model

### 5.1 Identity separation

- `CanonicalInstrumentId` identifies an exact physical instrument or listed contract under Strategy OS authority. Its canonical fields include venue, asset class, economic underlying, contract kind, currency, and the contract-defining expiry, strike, option right, multiplier, or series terms that apply. Decimal fields use canonical decimal strings, never binary floats.
- `InstrumentSelector` expresses durable economic intent such as nearest eligible weekly call, target delta band, or front-month future. It is executable strategy input and remains separate from the resolved physical instrument.
- `ProviderInstrumentMapping` maps a canonical physical identity to a provider symbol/token over a non-overlapping effective interval and provider-adapter version. Provider identifiers never appear in strategy documents.
- A held position retains the exact canonical physical identity resolved at entry. Later selector movement cannot rewrite it.

### 5.2 Point-in-time truth

Market truth records use half-open effective intervals `[effective_from, effective_to)` plus recorded-at revision identity. Records within one authoritative snapshot may not overlap on their natural key. The domain covers sessions and special sessions, actual listed contracts and strikes, expiry cycles, lot/tick/freeze quantities, listing/delisting, settlement terms used by modeled outcomes, corporate-action effects, and explicit fee/adjustment schedules where consumed.

`MarketTruthSnapshot` is an immutable canonical manifest of instrument-master and rulebook records. It has a content digest, source classification, effective range, recording time, and quality:

- `OBSERVED`: imported actual point-in-time records;
- `RECONSTRUCTED`: derived from stated rules with algorithm/version and unresolved gaps;
- `UNKNOWN`: insufficient evidence.

Only `OBSERVED` may support a ground-truth claim. Research may use `RECONSTRUCTED` only through an explicit policy and must preserve the nonclaim. `UNKNOWN`, gaps, overlaps, current-rule substitution, token reuse ambiguity, or an invented contract fail closed.

Continuous futures keep signal series and tradable contracts separate. The roll and adjustment policy is explicit, versioned, and included in dataset identity. Dynamic option windows declare recenter policy; subscription hysteresis is a later runtime concern and never changes semantic window identity.

## 6. Data observations, alignment, and causality

A normalized `DataObservation` binds canonical instrument, field, timeframe/resolution, event timestamp, availability timestamp, completion timestamp, provider/dataset identity, rulebook snapshot, and numeric validity. The canonical candle converter remains the only raw-candle-to-frame seam.

An `AlignmentPolicy` declares timezone/session calendar, completed-bar rule, maximum age, maximum timestamp skew, resampling rule, and invalid-input behavior. Evaluation at time `T` may consume only observations whose availability and completion times are no later than `T`. The default higher-timeframe value is the last completed observation. Forming/repainting bars require a distinct declared policy and are outside authoritative Phase 4 live use.

Cross-instrument alignment never treats last-known values as contemporaneous by default. A stale or materially skewed required input blocks new entries. Forward fill, interpolation, provider fallback, and local derivation are explicit policy decisions included in provenance and cache identity.

Prefix comparison remains the causality proof for every new Phase 4 evaluator. Appending future observations must not change any earlier output, validity state, selector resolution, or aligned timestamp.

## 7. Data requirement and provider capability contracts

### 7.1 Registry-closure declaration

The architecture verdict is `KEEP + HARDEN`. Add one optional constructor input and immutable property named `data_requirement_declarations` to the accepted `PlatformRegistry`; do not add a descriptor field or another registry. Its keys are exact v2 `(component_id, component_version)` leaf references already present in `PlatformRegistry.v2_components`. Its values use the closed `data-requirement-declaration/1` vocabulary below. `PlatformRegistry` deep-copies, validates, freezes, and content-addresses the map during construction. Caller-held containers, post-construction attributes, free sidecars, test maps, component names, ports, domain families, and implementation inspection are not declaration sources.

Each declaration is exactly this JSON object; `requirements` is an array, never an object map or set:

```json
{
  "schema": "data-requirement-declaration/1",
  "classification": "REQUIRES_DATA",
  "requirements": [
    {
      "requirement_id": "primary_close",
      "instrument": {"literal": {"role": "primary", "type": "PHYSICAL"}},
      "field": {"literal": "CLOSE"},
      "timeframe": {"parameter": "bar_seconds"},
      "history": {"literal": {"minimum_bars": 1, "warmup_bars": 20}},
      "freshness": {"literal": {"maximum_age_seconds": 60}},
      "depth": {"literal": {"kind": "NONE", "levels": null}},
      "session": {"literal": "INSTRUMENT_CALENDAR"},
      "alignment": {"literal": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 60}},
      "derived_local": {"literal": false}
    }
  ]
}
```

The declaration object has exactly `schema`, `classification`, and `requirements`:

- `schema` is exactly `data-requirement-declaration/1`;
- `classification` is exactly `NO_DATA` or `REQUIRES_DATA`; `NO_DATA` requires an empty requirements array and `REQUIRES_DATA` requires at least one row;
- each requirements-array row has exactly ten keys: `requirement_id`, `instrument`, `field`, `timeframe`, `history`, `freshness`, `depth`, `session`, `alignment`, and `derived_local`;
- `requirement_id` is a literal non-empty lower-snake-case row field matching `[a-z][a-z0-9_]{0,63}`. It is never an expression. It is unique within the declaration.

The direct value type of each semantic field is closed. `instrument` is exactly `{"role": role_token, "type": instrument_type}` where `role_token` matches `[a-z][a-z0-9_]{0,63}` and `instrument_type` is `PHYSICAL`, `ECONOMIC_SELECTOR`, or `CONTINUOUS_FUTURE`. `field` is one of `OPEN`, `HIGH`, `LOW`, `CLOSE`, `LAST`, `BID`, `ASK`, `BID_SIZE`, `ASK_SIZE`, `TRADE`, `VOLUME`, `OPEN_INTEREST`, `IMPLIED_VOLATILITY`, `DELTA`, `GAMMA`, `VEGA`, or `THETA`. `timeframe` is a positive integral number of seconds. `history` is exactly `{"minimum_bars": non_negative_integer, "warmup_bars": non_negative_integer}`. `freshness` is exactly `{"maximum_age_seconds": non_negative_integer}`; this is a policy quantity, not a clock reading. `depth` is always exactly `{"kind": depth_kind, "levels": levels}`: `depth_kind` is `NONE`, `TOP_OF_BOOK`, or `BOOK`; `levels` is null for `NONE` and `TOP_OF_BOOK` and is a positive integer for `BOOK`. `session` is exactly `INSTRUMENT_CALENDAR`, `CONTINUOUS`, or `ALL_RECORDED`. `alignment` is always exactly `{"kind": alignment_kind, "maximum_skew_seconds": non_negative_integer}`, where `alignment_kind` is `EXACT`, `ASOF_BACKWARD`, or `COMPLETED_RESAMPLE`. `derived_local` is boolean. Booleans do not satisfy integer fields.

Exactly the nine semantic row fields, from `instrument` through `derived_local`, are expression sites. Each is exactly one of `{"literal": direct_value}` or `{"parameter": parameter_id}` with one key. An expression wraps the whole semantic field. Expressions are forbidden inside a literal composite, so `instrument`, `history`, `freshness`, `depth`, and `alignment` cannot mix literal and parameterized scalar leaves. A `parameter` value is a non-empty parameter id declared by that same leaf descriptor and supplies the whole direct value after binding. Literals receive the direct-value validation above at registry construction. After resolution, every expression is replaced by its direct value and the resulting bound row has the same ten keys and direct value types, with no `literal` or `parameter` objects; the complete row is validated again and deep-frozen.

Input array order has no meaning. Registry construction first validates every input row and rejects a repeated `requirement_id` before normalization; duplicate ids never overwrite, merge, or use first/last-wins behavior. It then sorts rows lexicographically by the UTF-8 bytes of `requirement_id`. The canonical declaration bytes are exactly the UTF-8 encoding of the existing `canonical_json` output for the normalized declaration: recursively sorted object keys, the normalized requirements array, JSON null for the two non-book depth forms, and no whitespace, set, tuple, or insertion-order semantics. The existing `content_address` over that normalized declaration computes `declaration_address`. Unknown keys, enum values, malformed expressions, unbound parameters, non-finite numbers, mutable values, transport symbols, provider names, credentials, entitlements, execution capability, clock values, or runtime state are refused. The registry computes the overall `registry_snapshot_address`; neither address is caller input.

The registry snapshot payload includes canonical addresses for the v1 component/body/kernel closure, v2 type and component descriptors, v1 and v2 implementation identities, and the sorted component-reference-to-declaration-address map. Any declaration, descriptor, implementation, or closure membership change produces a different snapshot address. The snapshot contains no callable bytes, secrets, provider transport, clock, or mutable state.

### 7.2 Leaf resolution, compounds, and opt-in

Declarations attach only to v2 leaves. A declaration on a compound, an unknown component, or a v1 component is rejected at registry construction. The single accepted `resolve_v2` path lowers compounds first, binds each leaf declaration against that leaf's resolved parameters, and records on every resolved leaf: authored node id, full lowered component path, leaf component reference, parameter values and existing parameter-binding provenance, declaration address, bound requirement tuple, and registry snapshot address. Parent-to-child compound parameter propagation remains visible through the existing `target_paths` provenance; the bound requirement retains that provenance rather than replacing it with the final value.

V1 registry construction, validation, resolution, runtime, dispatch, and authored identity remain byte-compatible and make no Phase 4 capability claim. Existing v2 graphs also remain valid and resolvable when declarations are absent. Phase 4 is an explicit v2 opt-in: `compile_data_requirement_plan` accepts a resolved v2 graph only when every lowered leaf has exactly one valid `NO_DATA` or `REQUIRES_DATA` declaration bound under the same registry snapshot. Missing, malformed, parameter-unbound, stale, duplicate, compound-owned, or snapshot-mismatched declarations return a closed structured refusal. They never mean `NO_DATA` and cannot be inferred.

The compiler reduces the bound leaf facts into one immutable `DataRequirementPlan` ordered by authored node id, lowered path, leaf component reference, requirement id, and canonical requirement bytes. The plan records authored IR address, resolved graph address, implementation-closure address, registry snapshot address, all declaration addresses, all parameter-binding provenance, and `plan_address`. It neither re-resolves the graph nor changes graph meaning.

### 7.3 Capability and identity chain

`CapabilityProfile` is immutable, versioned, and role-separated:

- data: live fields, historical fields, resolution, retention/range, depth, OI/volume/Greeks, rate and subscription limits, timestamps/timezones, expired-contract and point-in-time-master support;
- execution: declared separately and unchanged by this phase;
- mode: research, paper, and live are assessed independently.

`CapabilityAssessment` compares one plan to one selected data profile and dataset manifest. Each requirement is `SATISFIED`, `UNAVAILABLE`, `INSUFFICIENT_RANGE`, `INSUFFICIENT_RESOLUTION`, `INSUFFICIENT_FRESHNESS`, or `UNKNOWN`. Unknown profile fields and provider claims without conformance evidence fail closed. No Phase 4 profile selects a provider, opens a connection, or authorizes execution.

An assessment records and addresses the exact owner, mode, plan address, registry snapshot address, capability-profile address, dataset-manifest address, market-truth-snapshot address, per-requirement result, and evidence address. A missing address, owner or mode mismatch, plan/snapshot mismatch, stale profile, unverifiable entitlement, or declaration mismatch refuses assessment. The assessment does not infer entitlement or execution support.

Capability changes are classified as levels 0 through 3. Level 0 keeps meaning; level 1 changes operations while requirements remain satisfied; level 2 requires reassessment of affected bindings; level 3 fails the affected capability assessment. This architecture records affected identities and reasons but does not implement live deployment blocking.

## 8. Dataset provenance and cache identity

`DatasetManifest` is immutable and content-addressed. It records owner, provider/dataset version, canonical instruments and fields, time range, segment digests, instrument-master and rulebook snapshot digests, adjustment/roll policy, missing-data/fallback policy, alignment/resampling policy, timezone, collection/import algorithm version, and known gaps or reconstructed regions.

Research results bind the authored IR address, registry snapshot address, resolved graph and implementation-closure addresses, declaration addresses, plan address, manifest address, market-truth snapshot address, evaluation-policy address, and capability-assessment address. Cross-database references use immutable digests and owner identifiers rather than unsupported foreign keys.

The existing backtest cache remains the only result cache. Its answer key must include every answer-changing Phase 4 address, including registry snapshot, resolved graph, implementation closure, declarations, plan, assessment, dataset manifest, market truth, and evaluation policy. A change to a declaration, parameter binding, registry closure, provider correction, market-truth snapshot, missing-data handling, adjustment, alignment, or component implementation cannot hit an old result. Cache rows without complete Phase 4 identity cannot satisfy a Phase 4 request.

## 9. Ownership, authority, and persistence

Canonical public instrument and market-rule records are shared reference facts with immutable provenance. Provider connection profiles, capability snapshots derived from a connection, dataset manifests, assessments, and research results are owner-scoped. Every lookup derives owner server-side where ownership applies. Lists are bounded and no secret or provider credential enters a manifest, receipt, log, or cache key.

Phase 4 persistence is additive. Execution/control-plane migrations own canonical instrument, market-truth, provider-mapping metadata, and capability-profile metadata needed by admission. Research-plane migrations own dataset manifests and result provenance. Migration tests cover empty install, supported SQLite upgrade/restart for local compatibility, and disposable PostgreSQL 16 upgrade/restart to exact heads. Partial, stale, overlapping, or digest-invalid state fails closed. No historical attribution backfill or data cutover is authorized.

Research JSON persistence declares top-level shape rather than generic validity. Graph-version, admission, and legacy-manifest documents are objects; the five typed-manifest segment, instrument, field, gap, and dependency collections are arrays. Forward research migration `0010` repairs accepted immutable `0009` without rewriting canonical bytes, and resumes only from an exact old state, exact new state, or validated structural prefix. Marker-only claims and arbitrary old/new hybrids refuse.

The durable v2 graph correction adds immutable, owner-scoped graph-version records to both planes at execution head `0037` and research head `0008`. Each record binds the exact authored document, resolved graph, implementation closure, registry snapshot, complete canonical admission receipt, and persisted capability assessment used by that receipt. Graph-version and receipt writes are atomic. Reuse of an address is accepted only when every persisted canonical field is identical. Supported restart recovery may complete an interrupted research `0008` upgrade only after proving the exact expected table, columns, constraints, indexes, and triggers; arbitrary partial schema or trigger drift is refused. Downgrade would destroy immutable graph history and is therefore refused rather than advertised as rollback.

Persisted execution and research loading dispatches by `format_version`. Legacy v1 keeps its established loader and runtime behavior. A verified v2 chain deliberately stops with stable `V2_RUNTIME_UNAVAILABLE` because Phase 4 does not own a v2 runtime. Phase 5 must provide the component catalogue, output mapping, Strategy adapter, and worker execution before that refusal can be replaced.

Restart evidence must cross a real process boundary: persist both plane-local records to durable databases, terminate the writer, reconstruct the accepted registry in a fresh interpreter, reload and verify both graph/receipt chains, and reach the stable refusal through the real execution loader. A JSON round trip in the writer process or a monkeypatched loader does not prove this contract.

The execution loader owns that complete proof. Its one accepted Phase 4 chain is `load_verified_admission` -> `reconstruct_phase4_artifact` -> `require_phase4_current` -> `research.domain.admissions.require_admission` -> dataset/assessment verification -> terminal `V2_RUNTIME_UNAVAILABLE`. The research verifier must prove the exact `ResearchStrategyAdmission` and `ResearchIrV2GraphVersion` against the reconstructed artifact before dataset or assessment authority can contribute to a terminal decision. A caller-side query, copied-column comparison, second verifier, second hash, generic dispatcher, or diagnostic performed after the loader returns cannot substitute for any link.

Admission remains an immutable, owner-scoped approval consumed at activation. `backend/app/strategy/admission.py` remains the sole artifact-construction authority. Its accepted `V2AdmittedStrategyArtifact` and `admit_v2_strategy` remain byte-compatible for v1 and non-opted v2 and make no Phase 4 claim. The capability capsule adds, in that same module, one `Phase4V2AdmittedStrategyArtifact` wrapper and one sole `admit_phase4_v2_strategy` construction seam. That function takes the canonical document, opted-in registry, accepted v2 evidence, one accepted immutable `DataRequirementPlan`, one validated `CapabilityAssessment`, and the exact evaluation-policy address; it calls the existing v2 constructor, requires that base receipt's registry snapshot to be the full opted-in `PlatformRegistry` snapshot, and then wraps it. No caller may supply a precomputed wrapper address.

The wrapper's canonical `to_dict()` has exactly the common persistence-protocol keys `scheme`, `contract_suite`, `parity_suite`, `format_version`, `owner_id`, `graph_identifier`, `graph_version`, `graph_address`, and `content_address`, plus exactly the three wrapper keys `base_v2_admission`, `base_v2_admission_address`, and `phase4_data_binding`. `scheme` is exactly `strategy-admission/phase4-data/1`; `format_version` is 2; the common graph and authored-content identity values exactly equal the embedded base receipt. `base_v2_admission` is the complete canonical `V2AdmittedStrategyArtifact.to_dict()` mapping and `base_v2_admission_address` is its recomputed address. `phase4_data_binding` is exactly:

```json
{
  "owner_id": "owner-id",
  "mode": "RESEARCH",
  "authored_ir_address": "sha256:...",
  "registry_snapshot_address": "sha256:...",
  "resolved_graph_address": "sha256:...",
  "implementation_closure_address": "sha256:...",
  "declaration_addresses": ["sha256:..."],
  "plan_address": "sha256:...",
  "capability_assessment_address": "sha256:...",
  "dataset_manifest_address": "sha256:...",
  "market_truth_snapshot_address": "sha256:...",
  "evaluation_policy_address": "sha256:..."
}
```

`mode` is exactly `RESEARCH`, `PAPER`, or `LIVE`; `declaration_addresses` is an array sorted by address UTF-8 bytes with duplicates rejected; every other address value is a valid content address. The wrapper's computed `admission_address` addresses its complete canonical `to_dict()` bytes and is distinct from `base_v2_admission_address`; its top-level v2 `content_address` remains the authored document identity. The constructor recomputes the embedded base receipt address, requires every binding address to agree with the plan, assessment, owner, mode, and the full registry snapshot embedded in the base receipt, and refuses a missing, stale, malformed, unbound, or mismatched fact.

`backend/app/core/strategy_admissions.py` and `backend/research/domain/admissions.py` remain generic persistence seams, not artifact constructors or admission authorities. They accept the wrapper through their existing artifact protocol, recompute its complete canonical bytes and top-level admission address, and persist those exact bytes through the existing immutable `artifact_json` fields; no schema or second admission table is required. They must not assemble, repair, or infer `phase4_data_binding`. Research result/cache identity cites that wrapper admission address as well as the same plan, assessment, manifest, market-truth, and evaluation-policy addresses; the receipt does not cite a future result, so no identity cycle exists. Promotion or activation refuses when the result's admission address or any repeated fact differs. A Phase 4 receipt proves only the exact market/data assessment it records. It does not prove provider behavior, resource fit, protection compatibility, release deployability, production rehearsal, or live authority.

The durable record verifies the persisted receipt and assessment bytes it names; it does not repair upstream authority. Final independent architecture checking finds four unresolved Critical authority collapses: DatasetManifest is not loaded and proved as the canonical owner/content/coverage/provenance source; canonical instruments and economic underliers remain labels or opaque JSON; provider observations and normalized observations lack separate durable typed identity; and market-truth/capability rows preserve hashes without reconstructing typed authority or reconciling copied fields. Those findings block Phase 4 integration and final-review readiness. They are serial correction dependencies, not authority granted by durable graph persistence. The checker also finds that the current resolved-graph address omits executable topology; that High finding must close before Phase 5 execution or cache authority.

## 10. Acceptance scenarios and refusals

### Reusable equity

One admitted graph can bind to several canonical equity instruments. Each assessment uses the correct session/rule snapshot, finite completed bars, declared warmup, and a distinct manifest/cache identity without editing the graph.

### Weekly options/order flow

At historical time `T`, a selector resolves only over actual listed weekly contracts and strikes from the snapshot, with historical lot/session rules. Missing historical depth or OI produces an unavailable assessment; it is never synthesized. The held-position identity remains the filled contract after the selector recenters.

### Cross-market

One execution market observes multiple canonical instruments across providers, timezones, and sessions. Completed observations satisfy explicit age/skew policy. A closed market, stale leg, unavailable provider, or missing field remains distinct and blocks entry without changing exit availability.

The phase gate must demonstrate refusal of present-day rule substitution, invented contracts, token reuse ambiguity, silent forward fill, invalid-to-false coercion, future-bar access, stale/misaligned entry, capability overclaim, incomplete provenance, cross-owner access, and stale cache hits. It must also exercise the actual loader with a missing research receipt, missing research graph, tampered receipt, tampered graph, tampered copied columns, wrong owner, and execution/research-plane substitution. Complete current companion records alone may reach exact `V2_RUNTIME_UNAVAILABLE`, after every authority verifier and before every consumer side effect. Each critical guard needs a reversible mutation that its own test kills.

## 11. Deployment contract

The architecture correction is documentation-only and changes the prospective application/admission contract; it changes no running artifact. The registry correction implementation is `architecture-changing` with no schema, service, dependency, configuration, provider, or secret change. The already accepted persistence slice retains ownership of its additive PostgreSQL migrations.

The research-receipt authority correction is `schema-free-phase4-research-receipt-authority-hardening`. It wires the already accepted research admission verifier into the existing complete-current execution verifier and changes no schema, migration head, dependency, configuration, service, provider, frontend, infrastructure, deployment artifact, or runtime availability. SQLite compatibility and disposable PostgreSQL 16 evidence must prove the same refusal order. Local evidence cannot establish release deployability or production readiness.

| Dimension | Phase 4 obligation and owner |
| --- | --- |
| Build/configuration | No new service or provider dependency. Each slice records dependency impact; integration verifies installability and no secret-bearing configuration. |
| Registry/admission contract | The registry correction owns immutable closure, compatibility, deterministic-address, binding, and refusal evidence. The capability slice owns assessment and admission propagation. Integration and final review must cover both evidence sets. |
| PostgreSQL/migrations | The persistence capsules own execution and research empty-install, supported-upgrade, exact-head, restart-idempotence, and stale/partial-schema refusal. Current Phase 4 heads are execution `0039` and research `0010`; the research JSON repair is forward-only from immutable `0009`. Evidence remains local SQLite compatibility plus disposable PostgreSQL 16, not a production rehearsal. |
| Data cutover | No production cutover is authorized. The persistence capsule proves deterministic fixture import and integrity only; V1 release retains frozen-source rehearsal. |
| Backup/restore | The persistence capsule proves local logical backup/clean restore for new tables where the existing harness supports it. Encryption, retention, managed PITR, and production RPO/RTO remain V1 release obligations. |
| Services/health | Phase 4 adds no service. The integration capsule verifies existing local roles still start and assigns schema/capability readiness exposure to Phase 6/8 without claiming it now. |
| Security | Ownership and secret-exclusion tests belong to persistence and assessment slices. Network/TLS/rotation remain release or provider-phase obligations. |
| Observability/capacity | Refusal reasons and bounded manifest/assessment queries are required. Subscription, storage, queue, and production capacity ceilings remain exact Phase 7 and V1 release obligations. |
| Rollout/rollback | Additive migration rollback/forward-repair evidence belongs to persistence. Production rollout remains owner-gated and unproven. |

The highest permitted Phase 4 implementation claim is `locally_runnable` unless a later owner-gated, production-shaped capsule supplies stronger evidence.

## 12. Deferred homes and nonclaims

- Phase 5 owns broad first-party node declarations and scalable research consumers of these contracts.
- Phase 5 also owns the v2 component catalogue, output mapping, Strategy adapter, and worker execution required to replace the deliberate post-verification `V2_RUNTIME_UNAVAILABLE` refusal.
- Phase 6 owns deployment binding, preflight, configuration, service topology, and authoritative activation decisions.
- Phase 7 owns dynamic subscription execution, resource planning, capacity, degradation, and cost telemetry.
- Phase 8 owns truthful operator UI and readiness workflows; frontend implementation remains blocked here.
- Phase 9 owns provider adapters, credentials, fallback behavior, network recovery, rate limits, and provider conformance.
- Phase 10 and the V1 release gate own production operations, retention, security, backup/restore, capacity, rollout, and support evidence.

Phase 4 does not claim complete market data, real provider correctness, deployment safety, production readiness, live authority, broker-resident protection, resource fit, or broad instrument/provider coverage.

## 13. Authority-foundation correction contract

The independent architecture check rejects the earlier broad Phase 4 PASS. The accepted verdict is `KEEP + HARDEN`: keep the single Component IR v2, validator, resolver, registry, canonical hash, admission path, research lineage, and cache identity, then replace address-shaped claims with closed typed facts and verified loaders. CUR-C1 through CUR-C4 and CUR-H2 remain open until the serial correction capsules and final integration gate produce direct evidence. Historical reports remain evidence of what ran, not current acceptance evidence.

### 13.1 Fact and equality matrix

Each row is an immutable fact. An address from another row cannot substitute for it.

| Fact | Closed canonical document and equality | Authority and owner rule | Durable representation and verified loader |
| --- | --- | --- | --- |
| Canonical physical instrument | `canonical-instrument/1`: authority namespace/version, reviewed venue code, asset class, contract kind, currency, exact contract terms, and `economic_underlier_address`. Equality is byte equality of this document. | Strategy OS market-identity authority mints it. A derivative names the exact canonical underlying instrument address; a display name, provider symbol, index label, or free string is invalid. A non-derivative root has a typed null underlier. | Execution rows store canonical bytes, address, schema/version, and duplicated venue/contract columns. The loader parses the closed document, reconstructs the typed value, recomputes the address, checks every duplicate, and resolves the underlier without cycles. |
| Provider entity, product, and owner contract | Separate `provider-entity/1`, `provider-product/1`, and `provider-contract/1` documents. A product names its entity; a contract names exact owner, product, permitted use, effective interval, and evidence address. | Provider identity is descriptive. Only a verified owner contract can establish entitlement for that owner and mode. A profile cannot infer entitlement from reachability or conformance. | Execution rows store all three canonical documents and foreign-key the chain. Loaders recompute addresses, enforce owner/product/effective-time equality, and reject missing, expired, overlapping, or cross-owner chains. Credentials never enter these facts. |
| Provider instrument alias | `provider-instrument-mapping/1`: product address, provider token/symbol, canonical instrument address, adapter schema version, half-open effective interval, observation namespace, and source evidence. | The mapping belongs to one provider product. A contract permits access but cannot change alias identity. One token cannot overlap across physical identities within a product namespace. | Execution rows store the full document and copied product, instrument, token, and interval columns. Reload checks bytes, columns, non-overlap, and referenced typed facts. |
| Provider observation | `provider-observation/1`: owner, provider entity/product/contract, mapping and token, raw schema, field, resolution, event/completion/availability/recorded times, sequence/correction identity, immutable raw-segment address plus byte range/digest, validity, and supersedes address. | It records what one permitted provider product supplied. It is separate from normalized market data. Owner and contract equality are exact. | Execution rows and immutable segment records preserve full bytes and copied lookup columns. Reload verifies segment length/digest/range, contract, mapping interval, timestamps, correction chain, canonical bytes, and address. |
| Normalized market observation | `normalized-market-observation/1`: canonical instrument, provider-observation addresses, transform/policy/algorithm addresses and versions, truth snapshot, normalized schema/field/resolution/times, typed value/validity, correction lineage, and recorded time. | The sole normalized constructor loads raw observations and all named dependencies. Different transform, rulebook, raw input, correction, or instrument creates a different fact. | Execution rows store the closed document and copied instrument/time/field columns. Reload reconstructs dependencies, reruns deterministic normalization where declared, recomputes bytes/address, and checks copied columns. |
| Dataset dependency authorities | Nine separate documents: `raw-schema/1`, `normalization-transform/1`, `alignment-policy/1`, `missing-data-policy/1`, `adjustment-policy/1`, `roll-policy/1`, `dataset-correction/1`, `dataset-creation-evidence/1`, and `deterministic-algorithm/1`. Together they close provider-product/contract and typed-field schema, exact transform inputs/output/parameters, session/calendar/truth alignment, explicit gap handling, instrument/truth adjustments, futures roll selection, ordered supersession, producer/source/artifact evidence, and versioned implementation/test-vector identity. | Each manifest or segment role selects exactly one canonical schema and authority constructor. No caller-provided fact kind, optional resolver, generic row, or syntactically valid address grants authority. Corrections are owner-scoped, ordered, acyclic, and fork-free; missing-data policy permits only refusal or explicit gaps, never implicit fill. | Execution uses nine separate immutable tables and closed role-specific loaders. Every loader parses canonical bytes, recomputes the domain-separated address, reconciles copied owner/product/contract/schema/time columns, and recursively loads its fixed typed dependencies. There is no public `load(address)` dispatcher. Research stores exact addresses and identical canonical bytes in manifest/segment roles and cannot translate or repair them. |
| Market-truth snapshot | `market-truth-snapshot/2`: authority scope, knowledge cutoff, effective interval, quality, sorted typed instrument/rule records, source evidence, and a typed reconstruction block or typed null. | `OBSERVED` requires immutable source evidence. `RECONSTRUCTED` requires algorithm/version, inputs, unresolved gaps, and policy permission. `UNKNOWN` cannot authorize ground-truth use. | Execution rows store full bytes, schema/version, address, quality, scope, cutoff, and interval. The loader reconstructs each record, enforces knowledge/effective time, source or reconstruction requirements, copied-column equality, and address. |
| Capability conformance evidence | `provider-conformance/1`: exact product, tested schema/fields/ranges/resolutions, test method/version, observed interval, evidence artifacts, and result. | It describes a product test. It grants no owner entitlement and contains no contract or credential. | Execution rows store canonical bytes and address. Load verifies artifact digests and effective interval before profile use. |
| Capability profile | `capability-profile/2`: exact owner, mode, entity/product/contract, conformance evidence, observed/expires times, change level, and sorted closed offers. | The canonical constructor loads contract and conformance evidence. An offer is usable only when entitlement and conformance cover the same complete requirement. | Execution rows store bytes and copied owner/mode/product/contract/time fields. The loader reconstructs dependencies, address, copied columns, freshness, and secret exclusion. |
| Capability assessment | `capability-assessment/2`: exact owner/mode, plan and registry snapshot, typed profile, dataset, truth, evaluation policy, algorithm/version, assessment time, and one result per requirement selector. | Only the assessment authority loader may return an authoritative assessment. It loads every dependency and recomputes coverage and results. Constructor tokens and copied digests grant no authority. | Both planes store identical bytes/address plus copied owner/mode/dependency columns. Each loader rebuilds the typed chain and recomputes results. Cross-plane bytes and address must match before admission. |
| Dataset segment and bytes | `dataset-segment/1`: immutable object address, byte digest/length, media/schema identity, ordered row range, instruments, fields, event/availability range, provider products/contracts, correction set, and creation evidence. | A segment belongs to the exact dataset owner and permitted contract chain. Object location is metadata; digest plus length identify bytes. | Research stores segment facts and immutable object references. Load streams and verifies exact bytes before use. |
| Dataset manifest | `dataset-manifest/2`: owner, purpose/mode, sorted segment addresses, aggregate byte digest/length, exact instruments/fields/event and availability coverage, explicit gaps, corrections, provider entity/product/contracts and raw schemas, normalization transforms, truth snapshots, capability profile, alignment/missing-data/adjustment/roll policies, algorithm versions, and created/recorded times. It never contains a capability-assessment address. | Research dataset authority constructs it only from verified segments and dependencies. A minimal generic manifest or caller address has no authority. Coverage requires exact instrument/field sets and complete requested range after declared gaps/corrections. | Research stores bytes, address, copied owner/coverage/dependency fields, and segment links. The loader verifies segment bytes, dependency chain, aggregate digest/length, columns, coverage, and address. Execution may store only an identical verified projection. |
| Authored graph | Existing Component IR v2 canonical document and authored address. | Existing validator and admission remain sole authority. | Existing graph-version records and loader remain authoritative after their present checks. |
| Resolved topology | `resolved-v2-topology/2`: authored address; registry snapshot/payload; implementation and declaration closures; lowered nodes with parameters/provenance; every bundle with assembly, ordered members, edge ids, endpoints, binding, member type/provenance and defaults; graph inputs with defaults/types; graph outputs with binding/type/provenance. | The existing resolver constructs it from the validated graph and immutable registry. Layout and presentation stay excluded. Every semantic topology mutation changes bytes/address. | Existing graph records retain the resolved address and proof closure. Fresh-process reload reruns the resolver and compares the complete topology document/address. |
| Admission, result, and cache | Existing distinct typed records extended only with verified Phase 4 dependency addresses. | None can create or repair a missing instrument, dataset, truth, capability, observation, graph, or owner fact. Every consumer loads the chain first. | Existing owner-scoped planes retain separate records. Reuse requires exact dataset bytes/manifest, observations, truth, policy, algorithm, topology, registry, and implementation identities. |

All documents use UTF-8 canonical JSON from `app.ir.hashing`: closed keys, NFC strings, sorted object keys, semantic array order, canonical decimal strings, UTC timestamps with offsets, integers without boolean substitution, and no NaN or infinity. The address is `sha256:` plus SHA-256 of domain-separated canonical bytes `{"schema": <schema>, "fact": <closed document>}`. A bare digest, constructor token, ORM instance, generic JSON, copied status, or syntactically valid address has no authority.

The dataset and assessment graph is acyclic. Verified source facts, segments, policies, algorithms, truth, and the capability profile produce `dataset-manifest/2`; the final manifest address plus the plan and remaining assessment inputs produce `capability-assessment/2`; admission, result, and cache records then bind both final addresses. The manifest must reject a `capability_assessment_address` field, while the assessment must name and reload the exact final manifest. Admission and cache load both facts and prove that the assessment's manifest address equals the separately bound manifest address. This causal break preserves complete transitive identity without a pair of content-addressed documents hashing each other.

### 13.2 Persistence, reconstruction, and refusal

The execution plane owns canonical instruments, provider identities, aliases, raw and normalized observations, truth, conformance, profiles, the execution assessment projection, and the nine role-specific dataset-dependency authorities. The research plane owns dataset segments/manifests, research assessment/admission, results, and cache lineage. Cross-plane references carry the same address and canonical bytes. Neither plane creates a translated authority document. Integration compares bytes, address, owner, mode, product, contract, and dependencies. Dataset loading is mandatory role dispatch: each manifest field calls its fixed execution loader with the execution session. An optional callback or generic address dispatcher is forbidden.

Execution migrations advance from accepted `0038` to `0039` for the nine role-specific dataset-dependency authorities; `0038` already contains canonical market identity, observations, truth, conformance, profile, and assessment persistence. Research advances from `0008` to amended, still-unaccepted `0009` for typed segments, manifests, assessment/admission references, and cache/result dependencies. Each migration is additive. Existing generic rows remain `LEGACY_UNVERIFIED`; they never gain typed authority through a synthetic backfill. A backfill may mark `VERIFIED_V2` only when complete original canonical bytes and every immutable dependency exist and the current loader reconstructs the same fact. Otherwise migration preserves the row for audit and authoritative consumers refuse it.

Each migration capsule proves model-DDL parity, empty install, supported upgrade, exact head, interrupted-upgrade restart, constraints/triggers, and destructive-downgrade refusal on SQLite compatibility and separate disposable PostgreSQL 16 execution and research databases. PostgreSQL lengths, JSON, foreign keys, transactions, and triggers are acceptance evidence. Partial writes roll back. Missing tables, columns, triggers, segments, foreign rows, or dependencies fail closed.

#### Caller-owned savepoint boundary

ADV-003 rejects `Session.in_transaction()` and `Session.begin()` as proof that a
real outer database transaction exists. On SQLite's legacy transaction mode a
clean or read-only Session can have a SQLAlchemy root transaction while the
driver still reports `in_transaction = false`. A first `begin_nested()` then
emits a top-level `SAVEPOINT`; `RELEASE SAVEPOINT` commits its writes, so a
later caller commit refusal and rollback cannot remove them. PostgreSQL starts
a real transaction before the same savepoint and retains the writes until the
outer commit. The supported dialects must nevertheless expose one identical
caller-ownership contract.

`app/db/concurrency.py` owns the only API:
`caller_owned_savepoint(session, *, scope)`. The context manager enlists the
Session's existing connection, proves or materializes a physical outer
transaction on that exact connection, records the proof against the current
root `SessionTransaction`, and only then opens the nested savepoint. For
SQLite, it issues explicit `BEGIN` when the same driver connection is not in a
transaction and verifies `in_transaction` before `SAVEPOINT`. For PostgreSQL,
it issues a harmless statement when the driver is idle and verifies `INTRANS`
before `SAVEPOINT`. A failed/invalid driver transaction, unsupported dialect,
connection substitution, or unverifiable state refuses before the nested
write. The helper never calls Session or connection commit, rollback, close,
or invalidate; it never creates a hidden Session or connection; and `scope` is
diagnostic only.

The proof marker contains the root transaction identity, enlisted connection
identity, and dialect. It is cleared when that root transaction ends, whether
by commit, rollback, close, or failed-transaction cleanup; ending an inner
savepoint does not clear it. The helper rechecks current driver state on every
entry, so a marker cannot revive a failed or replaced connection. A recursive
call may create another savepoint only when the same live root proof remains.
An already nested SQLite Session without that proof is an unproved external
top-level savepoint and must refuse; the helper cannot insert `BEGIN` beneath
it. An externally owned root transaction is accepted when the exact connection
has a real outer transaction before the first helper savepoint. PostgreSQL may
prove that condition from driver state; SQLite external nesting must enter the
shared helper before its first savepoint.

The caller retains the sole authority to commit or roll back the outer unit of
work. With no prior SQL or only a clean SELECT, the helper establishes the
physical root without committing. A prior caller write remains in the same
outer transaction. Pending ORM work may be flushed by SQLAlchemy before the
nested savepoint, but remains caller-owned and survives only the local
savepoint rollback, not an outer rollback. A nested flush or collision rolls
back only the savepoint and propagates the existing exact-retry or conflicting-
bytes decision; the helper performs no retry. A successful outer commit makes
the complete unit durable. A commit refusal before the DB accepts COMMIT,
followed by caller rollback, leaves zero target and zero unrelated rows. An
ambiguous post-COMMIT disconnect is never reported as rollback-safe: discard
the failed Session and reconstruct the canonical identity in a fresh Session.
A rollback failure also invalidates the Session and requires fresh-process
reconstruction; it cannot be converted into success.

The complete current `begin_nested()` inventory is closed as follows:

| Seam | Fact and transaction owner | Disposition and required correction evidence |
| --- | --- | --- |
| `app/core/strategy_admissions.py::put` | Execution graph version plus admission receipt; caller commits or rolls back. | Critical authority seam, impacted. Use the shared context and prove clean, read, write, explicit-root, recursive, collision/retry, flush/commit/rollback failure, unrelated-work, and restart cases. |
| `research/domain/admissions.py::store_admission` | Research graph version plus admission receipt; caller commits or rolls back. | Critical authority seam, impacted. It has the same required two-plane cases and exact zero-row ADV-003 result. |
| `research/domain/strategy_admissions.py::persist_verified_dataset_authority` | Typed segments, manifest, and dependency links; caller commits or rolls back. | Critical multi-row dataset authority, impacted. Prove no visible or durable prefix at each failure boundary. |
| `app/backtest/repository.py::append_claimed_result_batch` | Lease heartbeat, result batch, and progress under the worker caller's transaction. | Critical fenced result/lease fact, impacted. Prove target and unrelated work roll back together and exact replay converges. |
| `app/backtest/repository.py::complete_claim` | Terminal run state and execution outbox event under the worker caller's transaction. | Critical terminal/outbox fact, impacted. Prove neither side survives commit refusal and retry emits one exact event. |
| `app/backtest/public_computation.py::put_immutable` | Ownerless provenance-neutral immutable public cache artifact; publisher caller commits. | Non-authoritative cache, but its persistence contract is impacted. Use the same boundary and prove failed publish leaves no artifact while identical retry converges. |
| `app/ledger/service.py::write_snapshot` | Ledger snapshot version and outbox event; `outbox.writer` declares the caller-owned unit. | Critical snapshot/outbox atomicity, impacted. `outbox.writer` is a logical ownership wrapper, not physical SQLite proof; `write_snapshot` must enter the shared boundary directly before its savepoint. This is transaction hardening only and changes no money authority or ledger business rule. |

Source search found no other Phase 1-4 `begin_nested()` or literal SAVEPOINT
seam in `backend/app` or `backend/research`. `begin_reservation` and
`locked_mutation` are already-safe transaction-establishment primitives where
their callers invoke them before a savepoint, but none substitutes for the
shared boundary at these seven sites. Other `outbox.writer` callers perform
ordinary DML without a nested first write and do not share ADV-003; their
existing state-plus-event contract is still a transitive regression selector.

The required lifecycle is:

1. Construct and admit each source fact through its canonical constructor.
2. Persist bytes, address, copied query columns, and dependency links atomically; use the existing outbox for cross-plane handoff.
3. Terminate the writer interpreter and sessions. No token, object identity, registry instance, or monkeypatch survives.
4. A fresh interpreter loads exact heads, rebuilds the registry, streams dataset bytes, parses closed documents, reconstructs dependencies, recomputes addresses and derived assessments/results, and checks copied columns.
5. Consume through real admission, result/cache, and `V2_RUNTIME_UNAVAILABLE` pre-runtime paths. A mismatch refuses before claim/reclaim or reuse.

The Phase 4 reclaim authority-context correction applies that lifecycle to the
real public dispatcher without adding another verifier. Application lifespan
owns one current immutable `PlatformRegistry` and, only when research is
enabled, the existing synchronous research SQLAlchemy `sessionmaker`. It passes those two
objects as one immutable `ReclaimAuthorityContext` through
`dispatch_all_reclaimable` to `dispatch_reclaimable`. The context contains no
plan, cutoff, admission, owner, dataset, assessment, mode, or mutable session.
The lifespan-owned research engine and synchronous factory outlive startup
reclaim and are disposed through the existing lifespan cleanup. Each owner
dispatch opens at most one synchronous research `Session` lazily when a v2
candidate requires verification, reuses that exact session for both existing
loader sites, and closes it on every successful return, authority refusal, and
exception. Disabled research passes no context and opens no hidden engine,
factory, or session.

`dispatch_reclaimable` creates one timezone-aware UTC cutoff at its public
entry and reuses the exact context, research session, and cutoff for its
pre-claim and post-claim `load_verified_admission` calls. The loader accepts no
caller-provided Phase 4 plan. Its existing receipt reconstructor parses the
exact persisted receipt, resolves that receipt's embedded document against the
explicit current registry, compiles the sole canonical `DataRequirementPlan`,
and returns that plan in the immutable reconstructed artifact. The loader
passes that exact plan to the sole `require_phase4_current` verifier. No second
plan builder, verifier, callback, registry fallback, or process-global
authority is permitted. Legacy v1 loading neither requires nor consumes this
context and retains its existing call shape, values, and persistence effects.

Authority verification precedes every reclaim mutation and is atomic with the
classification that authorizes a legacy mutation. In particular,
`dispatch_all_reclaimable` must not call `reconcile_stale_runs` before entering
`dispatch_reclaimable`. One execution transaction closes the candidate set.
SQLite acquires `begin_reservation(..., scope="backtest:admission")`, hence
`BEGIN IMMEDIATE`, before enumeration. PostgreSQL selects the exact candidate
rows `FOR UPDATE` in deterministic `(queued_at, id)` order. The locked snapshot
records id, owner, state, admission address, cancellation state, claim token,
and claim expiry for every pending, expired-running, and claimless-running row.
Every v2 candidate then passes through the actual loader before mutation.

An all-v1 startup dispatch reconciles only the explicit locked legacy row ids,
with every classified owner/state/admission/cancellation/claim predicate still
present in the conditional update, and claims only an explicit classified row
through the same conditional seam. It never invokes a broad owner update or a
fresh post-classification selector. A concurrent insert is outside that closed
id set. A state, owner, admission, cancellation, token, or expiry transition
causes a zero-row conditional mutation, transaction rollback, and refusal so a
new invocation must classify it. Direct `dispatch_reclaimable` retains its
legacy no-pre-reconcile policy; startup supplies an internal startup policy
that performs only this explicit-id reconciliation. The policy is not caller
authority. This preserves direct and startup v1 values and effects while
closing the former snapshot-to-broad-reconcile TOCTOU.

Before any owner-wide reconciliation, claim, rollback-to-pending, error
transition, claim-token write, provider construction, cache access, worker
start, result write, broker, order, or money effect, every v2 row in that set
must pass through the pre-claim loader with the closed context. Any v2 row
therefore returns `PHASE4_CONTEXT_REQUIRED`, an earlier missing/stale authority
refusal, or, for a complete current chain, exact `V2_RUNTIME_UNAVAILABLE`; the
whole owner dispatch returns without mutating any v1 or v2 row. Deterministic
queue order is `(queued_at, id)`, but one v2 anywhere in the locked owner set
causes accepted owner-level head-of-line refusal and zero mutation for all rows.
Only when the locked snapshot proves the complete mutation set is v1 may the
explicit-id legacy reconciliation and dispatch sequence commit.
This deliberate mixed-set fail-closed rule is
Phase 4 containment, not operational v2 reclaim. The post-claim loader remains
wired to the same session, context, and cutoff so a future control-flow change
cannot create a contextless bypass, but Phase 4 current v2 state cannot reach
claim.

### 13.3 Adversarial owner matrix

Every row below is a separate Phase 4 acceptance obligation. The named primary owner must produce its real-path evidence before the next serial capsule starts. `phase4-authority-integration-gate` must rerun every row after all four corrections and record the evidence address or exact refusal. A shared row is not satisfied by one plane alone. No row is assigned to a future phase.

| ID | Edge class | Classification | Required real-path evidence, refusal, or identity change | Primary serial owner(s) |
| --- | --- | --- | --- | --- |
| ADV-001 | Process restart | persistence / lifecycle | Writer exits; a fresh interpreter and fresh database sessions reconstruct exact typed dependencies and either reach the real consumer or the declared refusal with identical bytes/address. | `phase4-resolved-topology-identity-correction`, `phase4-canonical-market-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-002 | Crash between writes | persistence / atomicity | Kill after each fact, copied-column, dependency-link, and outbox write boundary; restart exposes the complete committed chain or no authoritative chain, never a usable prefix. | `phase4-canonical-market-identity-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-003 | Partial transaction | persistence / atomicity | Force the last statement or commit to fail in execution and research transactions; all authoritative writes roll back and loaders refuse orphan rows. | `phase4-canonical-market-identity-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-004 | Duplicate or replayed request | authority / idempotency | Replay identical and conflicting create, admission, and cache requests through public seams; identical canonical facts converge, while an idempotency-key/body conflict refuses without replacing prior bytes. | `phase4-dataset-assessment-authority-correction` |
| ADV-005 | Stale worker | concurrency / authority | A worker carrying an earlier receipt, dependency head, or assessment cannot publish or consume after replacement/expiry; compare-and-set or exact dependency verification refuses it. | `phase4-dataset-assessment-authority-correction` |
| ADV-006 | Worker reclaim dispatch containment | concurrency / authority containment | Call the real public v2 reclaim-dispatch seam with explicit current authority context. The seam verifies the complete current authority chain, then terminates at exact `V2_RUNTIME_UNAVAILABLE` before claim, reclaim, provider, cache, worker, claim-token, result, broker, order, or money side effects; stale or missing authority refuses earlier. A Phase 4 `FULL` disposition proves only this containment and does not prove successful v2 reclaim. | `phase4-adversarial-matrix-closure` |
| ADV-007 | Cache hit after restart | cache / persistence | Warm a cache, terminate the process, reload through durable storage, and prove the hit revalidates complete dataset, observation, truth, policy, topology, registry, implementation, owner, product, and contract identities. | `phase4-dataset-assessment-authority-correction` |
| ADV-008 | Cache poisoning or collision | cache / identity | Insert the wrong bytes or dependencies under a syntactically valid or colliding lookup key; digest and full-key reconstruction refuse the entry, and no result is returned. | `phase4-dataset-assessment-authority-correction` |
| ADV-009 | Malformed serialized state | serialization / authority | Corrupt JSON, omit/duplicate closed fields, use invalid UTF-8/type/decimal/time/address forms, and damage segment ranges; closed parsers refuse before ORM or copied metadata can grant authority. | `phase4-canonical-market-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-010 | Valid-but-hostile values | validation / identity | Exercise NaN-like strings, infinities, booleans as integers, extreme decimals, Unicode confusables, traversal-like labels, hostile but valid addresses, and inverted ranges; canonical construction refuses or produces a distinct bounded identity without code/data interpretation. | `phase4-canonical-market-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-011 | v1 to v2 migration | migration / authority | Upgrade supported v1 rows through real migrations; complete source bytes reconstruct as `VERIFIED_V2`, while incomplete rows remain `LEGACY_UNVERIFIED` and refuse authoritative use. | `phase4-canonical-market-identity-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-012 | Mixed v1/v2 state | migration / versioning | Seed interleaved legacy and typed rows plus cross-version references; loaders dispatch exactly, never synthesize missing authority, and refuse a v2 chain that depends on unverifiable v1 state. | `phase4-canonical-market-identity-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-013 | Upgrade, downgrade, or version skew | migration / compatibility | Run old-reader/new-schema and new-reader/old-schema boundaries plus destructive downgrade attempts; unsupported heads and schemas refuse with no partial rewrite or silent coercion. | `phase4-canonical-market-identity-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-014 | Migration from zero | migration / deployability | Install execution `0038` and research `0009` from empty SQLite and separate disposable PostgreSQL 16 databases; exact heads, constraints, triggers, and model-DDL parity match. | `phase4-canonical-market-identity-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-015 | Migration from an actual old database | migration / deployability | Upgrade copied fixtures created by the supported real old heads `0037` and `0008`, restart, reconstruct typed/legacy classifications, and prove old audit rows survive without gaining authority. | `phase4-canonical-market-identity-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-016 | Missing catalogue or provider | dependency / availability | Remove canonical instrument, underlier, provider entity/product/contract, alias, conformance, or dataset catalogue dependencies; real loaders refuse without label fallback, inferred entitlement, or provider substitution. | `phase4-canonical-market-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-017 | Duplicate identity | identity / uniqueness | Attempt two different canonical byte documents at one logical unique identity and overlapping aliases/tokens; constraints or constructor equality refuse, while truly identical bytes converge. | `phase4-resolved-topology-identity-correction`, `phase4-canonical-market-identity-correction` |
| ADV-018 | Forged identity | identity / authority | Supply a well-formed arbitrary address, recompute an outer envelope around non-canonical bytes, or forge copied status/digest columns; authority loaders reconstruct from trusted dependencies and refuse. | `phase4-resolved-topology-identity-correction`, `phase4-canonical-market-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-019 | Stale receipt | authority / lifecycle | Mutate topology, registry, implementation, dataset, truth, capability, policy, owner, product, or contract after issuing a receipt; the real admission/cache/pre-runtime path refuses the old receipt. | `phase4-resolved-topology-identity-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-020 | Deleted or replaced dependency | dependency / referential integrity | Delete, tombstone, or replace each named dependency after persistence; fresh reload refuses the chain, and replacement bytes always have a new address rather than inheriting authority. | `phase4-resolved-topology-identity-correction`, `phase4-canonical-market-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-021 | Concurrency races | concurrency / consistency | Race same/different facts, alias intervals, corrections, assessments, admissions, cache fills, and outbox delivery on independent sessions; unique/transaction/CAS rules yield one exact fact or explicit conflict with no mixed chain. | `phase4-canonical-market-identity-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-022 | Owner or tenant mismatch | tenancy / authority | Cross owner-scoped rows, receipts, datasets, cache entries, provider contracts, and assessments in both directions; equality and database queries refuse before reuse or disclosure. | `phase4-canonical-market-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-023 | Clock or timezone boundary | time / causality | Exercise UTC offset changes, midnight/session boundaries, DST inputs, equal event/availability cutoffs, expiry, and future recorded times; canonical UTC conversion is stable and causal/stale violations refuse. | `phase4-canonical-market-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-024 | Empty inputs | validation / coverage | Empty graph collections, bytes, segments, instruments, fields, offers, requirements, and coverage ranges either form an explicitly permitted typed empty fact or refuse; absence never implies full coverage. | `phase4-resolved-topology-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-025 | Huge inputs | resource / boundedness | Submit oversized graphs, canonical documents, dependency lists, segments, offers, requirements, and correction chains through public seams; declared limits refuse before unbounded persistence or evaluation and leave no partial authority. | `phase4-resolved-topology-identity-correction`, `phase4-canonical-market-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-026 | Resource exhaustion | resource / recovery | Induce database pool, disk/write, memory-budget, file-descriptor, and bounded-query failures at real seams; work fails closed, transactions/outbox remain recoverable, and retry reloads rather than trusting partial in-memory state. | `phase4-canonical-market-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |
| ADV-027 | Cancellation midway through work | cancellation / atomicity | Cancel during streaming, normalization, assessment, admission, cache fill, migration step, and outbox handoff; cancellation unwinds or leaves resumable non-authoritative state, and restart proves no usable partial chain. | `phase4-canonical-market-identity-correction`, `phase4-typed-market-authority-correction`, `phase4-dataset-assessment-authority-correction` |

The exact row inheritance is normative: resolved topology owns `ADV-001, ADV-017, ADV-018, ADV-019, ADV-020, ADV-024, ADV-025`; canonical market owns `ADV-001, ADV-002, ADV-003, ADV-009, ADV-010, ADV-011, ADV-012, ADV-013, ADV-014, ADV-015, ADV-016, ADV-017, ADV-018, ADV-020, ADV-021, ADV-022, ADV-023, ADV-025, ADV-026, ADV-027`; typed market owns `ADV-001, ADV-009, ADV-010, ADV-016, ADV-018, ADV-020, ADV-022, ADV-023, ADV-024, ADV-025, ADV-026, ADV-027`; dataset and assessment owns `ADV-001` through `ADV-027` except `ADV-017`; integration owns `ADV-001` through `ADV-027`. Evidence must name the row ID, real seam, database/process boundary, expected refusal or identity change, observed result, and artifact address. Grouped test names do not reduce the row count.

The original operational lifecycle remains mandatory under the exact identifier `P5-ADV-006-RUNTIME`: claim, lose ownership, reclaim through the public seam after process death, reload the exact current persisted authority chain, fence the stale claimant, and allow only the current claimant to finalize exactly once. This lifecycle is not a twenty-eighth Phase 4 row and cannot be inferred from a Phase 4 `ADV-006 FULL` result. Phase 5 architecture must generate one exclusive runtime capsule for `P5-ADV-006-RUNTIME`. That capsule depends on accepted `phase5-graph-paper-attribution-schema`, must use direct SQLite and disposable PostgreSQL 16 evidence with real process restart and adversarial ownership loss, and must close before any v2 claim, reclaim, worker, result, cache, broker, order, or money consumer becomes reachable.

### 13.4 High findings and blocked use

CUR-H1 closes in `phase4-canonical-market-identity-correction`; provider entity, product, and owner entitlement contract become separate typed identities required by every raw observation, capability, and dataset chain.

CUR-H3 remains contained by `V2_RUNTIME_UNAVAILABLE` and a hard prohibition on placing a 71-character graph address in any 64-character `strategy_version` column. `phase5-graph-paper-attribution-schema`, owned by a fresh Sol-medium owner, must separate graph address from strategy version and migrate affected records before graph-to-paper execution, job claim/reclaim, cache authority, deployment binding, or any money record. Schema acceptance is necessary but grants no runtime reachability. After schema acceptance, the single exclusive `P5-ADV-006-RUNTIME` capsule generated by Phase 5 architecture must prove the successful reclaim lifecycle before any named v2 consumer becomes reachable.

CUR-H4 remains contained by blocking generated-strategy replay, promotion, activation, deployment, and current-slot replacement as immutable-version evidence. `phase6-generated-strategy-version-lineage`, owned by a fresh Sol-medium owner, must introduce immutable version identity and append-only lineage before any generated strategy crosses admission into replay, paper/live assignment, deployment, or release evidence. Its deadline is before the first Phase 6 activation or deployment-binding capsule.

`phase5-provider-evidence-compatibility` may map real provider evidence into the accepted typed contracts only after all Phase 4 corrections integrate. It cannot change canonical schemas, infer entitlement, access credentials without its owner gate, or restore a Phase 4 claim.

### 13.5 Stale evidence and revalidation

These claims are `STALE/REQUIRES RECHECK`: typed dataset authority/coverage; canonical instrument/underlier identity; raw-versus-normalized provenance; typed truth/profile/assessment reconstruction; topology-complete graph identity; and every admission, result, cache, scenario, migration, fresh-process, cross-plane, or review PASS that depends on them. Durable v2 integration remains current only for bounded graph-row/receipt persistence, fresh-process verification, legacy-v1 dispatch, and `V2_RUNTIME_UNAVAILABLE` refusal.

ADV-003 additionally makes every current-byte atomicity PASS that crosses one
of the seven savepoint seams stale. The transaction implementation must rerun
both graph-persistence planes, dataset-authority atomic failure, fenced result
batch and terminal outbox, public computation convergence, ledger
snapshot/outbox, the portable outbox contract, Phase 4 authority integration,
and ADV-002/ADV-003. It must kill and byte-restore one real guard at each of the
seven seams plus physical-root establishment, root-marker cleanup, unproved
external-nesting refusal, and the prohibition on helper commit/rollback/close.
The stopped matrix logs remain counterexample evidence only. After root accepts
the correction, a fresh matrix owner restarts all 27 rows from current bytes;
the official review package and final review remain stale until that matrix is
accepted.

`phase4-resolved-topology-identity-correction` owns graph identity revalidation. `phase4-canonical-market-identity-correction` owns instrument/provider/raw-normalized observation revalidation. `phase4-typed-market-authority-correction` owns truth/capability/assessment revalidation. `phase4-dataset-assessment-authority-correction` owns dataset/coverage/admission/result/cache revalidation. `phase4-authority-integration-gate` owns cross-plane lifecycle, scenarios, migration heads, transitive cache/result checks, and stale-verdict disposition. Only a later independent critical review may restore review readiness.

The forward `phase4-research-json-shape-parity-correction` closes only the cross-dialect constraint split at research head `0010`. Its real-row and original-seam evidence does not revive the stopped integration verdict; the integration owner must rerun the final tree and the later independent review must issue a fresh verdict.

### 13.6 Research receipt and graph authority at the execution loader

`phase4-final-review-4` is an immutable historical FAIL. It proved that `load_verified_admission` could reach terminal `V2_RUNTIME_UNAVAILABLE` while both `ResearchStrategyAdmission` and `ResearchIrV2GraphVersion` were absent. The integration test then checked those records only after loader return, which is a DP-008 false green.

The accepted correction is `KEEP + HARDEN`, with no schema work. Keep the existing loader, reconstruction seam, complete-current verifier, research admission verifier, canonical hashes, and terminal refusal. Harden only their composition into the sole chain `load_verified_admission` -> `reconstruct_phase4_artifact` -> `require_phase4_current` -> `research.domain.admissions.require_admission` -> dataset/assessment verification -> `V2_RUNTIME_UNAVAILABLE`. `require_admission` remains the only research receipt-and-graph verifier. No caller may preverify the research rows, no second hash or verifier may be added, and no v2 runtime path becomes reachable.

The same defect pattern reaches every current production consumer of `load_verified_admission`: enqueue admission, retry and reclaim classification, pinned-worker and cache/job reads, deployment creation and activation, runner entry, and broker evaluation. Static reachability is not acceptance evidence. After the verifier order changes, all prior consumer no-side-effect evidence, the decisive two-plane fresh-process lifecycle, relevant adversarial rows, the official review package, and any review-readiness inference are `STALE/REQUIRES RECHECK` until current-byte dynamic evidence proves refusal before each consumer effect.

The serial route is architecture correction, implementation plus integrated evidence/package rebuild, then fresh independent `phase4-final-review-5`. A separate integration capsule is unnecessary because the bounded implementation can honestly own the affected integration selector and package regeneration after product/test bytes freeze. Missing receipt, missing graph, receipt/graph/copied-column tampering, wrong owner, cross-plane substitution, fresh-process reconstruction, and exact complete-current terminal refusal must pass on SQLite and disposable PostgreSQL 16. Killed-and-restored guards must prove invocation and ordering at the actual loader and verifier seams. Dual review PASS remains the only route beyond Phase 4; none of these steps claims Phase 4 closure, review readiness before packaging, deployability, runtime enablement, live authority, or money authority.

## 14. Foundation migration and market-number correction contract

This section supersedes only the dependent migration and raw-candle claims
invalidated by foundation-audit findings A-01 through A-05. It binds to audit
report SHA-256
`cec0bdc931632b9297d733fa58f6057a60b32820882af5e90b3184fd88d54d6d`
and audit manifest SHA-256
`4933505aa93b9a9fc03a08617b933944c28a409269602f53d9060d563f2143c5`.
The immutable Phase 4 review records retain their historical meaning. They do
not prove the corrected paths until the new serial revalidation and review
close.

The native-oracle implementation is a strict four-boundary serial route. The
first fresh owner defines only the immutable scalar, declaration,
expected-state, receipt, rejection, process, owner, catalog, sequence, and
attestation contracts. The second fresh owner consumes those accepted
contracts and owns the two dialect builders plus distinct-process observers.
It constructs each expected state from one caller scenario and one dialect
declaration before locating or opening the database. Root accepts the exact
hashes at each boundary before the next owner starts.

The third fresh owner owns the sealed 24-DATA and 39-CAT obligation registry,
the four complete baseline envelopes for two corpora by SQLite and PostgreSQL
16, and omission, dead-binding, and wrong-binding rejection evidence. Each
envelope covers all 24 tables, exact native rows and types, marker, schema
cookie where applicable, keys, foreign keys, sequences and bindings, owners,
complete catalog facts, per-table digests, and one whole-state digest after
commit, close, dispose, and distinct-process reopen. Only after root accepts
all 174 baseline receipt slots may the fourth owner execute 96 DATA plus 78 CAT
effective mutation receipts, exact restoration receipts, and one
omission-sensitive `ClaimAttestation`. Observed rows, observed inventory,
repeated reads, current metadata, cross-dialect translation, and later-head
dumps cannot construct the expectation.

A focused suite pass is ineligible until a same-byte coverage validator proves
exact registry set equality and the required typed APIs. Mutation credit needs
a successful committed operation, changed digest after fresh-process reopen,
the exact final-consumer rejection code, and another reopened state equal to
the original digest after exact restoration. Statement failure, rollback,
no-op, setup failure, in-memory corruption, selected slices, or a generic
assertion earns no credit. The current frozen implementation remains
unaccepted because its validator finds zero of the 63 named obligations even
though the repaired SQLite declaration join and focused SQLite and disposable
PostgreSQL 16 selector are green. The PostgreSQL harness exists and ran; the
missing full sealed contract, not harness availability, is the blocker.

### 14.1 Architecture dispositions

| Surface | Disposition | Accepted boundary |
| --- | --- | --- |
| One typed immutable IR, canonical identity, attribution, owner isolation, and fail-closed authority | KEEP | The correction cannot add an alternate IR, infer missing authority, rewrite user facts, merge tenants, or enable runtime or money behavior. |
| Research version marker and forward-only runner | KEEP + HARDEN | Retain one marker row and destructive-downgrade refusal. Validate an exact version-owned state before work and a complete target state before every marker advance. |
| Historical SQLite `0001` through `0009` starts | EXPLICIT MATRIX REVISION REQUIRED | None has the complete immutable transitive catalog/compiler closure and arbitrary-data direct transition required for support. They must refuse before writes. The retained current `0007`/`0008` bytes receive no historical-authority credit. PostgreSQL markers `0003` through `0009` remain unsupported for the same authority class of reason. |
| Historical projections derived by subtracting fields from current model metadata | REPLACE | SQLite keeps version-owned projections. PostgreSQL freezes only the exact accepted `0010` contract as its historical source; neither runtime metadata nor a reconstructed `0003` through `0009` projection can become authority. |
| Current-head rewind fixtures used as old-database proof | REFACTOR | Relabel them as hybrid fault injection or retire them. They cannot prove upgrade support. |
| Existing PostgreSQL installations carrying `0003` through `0009` markers | EXPLICIT MATRIX REVISION REQUIRED | Repository history, accepted dirty bytes, tests, and release evidence do not provide complete version-owned catalog and transition contracts for arbitrary valid user and sequence state. The application must refuse read-only. The revision becomes active only after root-owner architecture acceptance; a user gate applies only if later evidence shows a released, deployed, production, or externally promised state. |
| Existing installations carrying exact `0010` | REFACTOR | Add forward migration `0011` to certify or repair only the enumerated defect state, validate the complete contract, and then stamp the new head. PostgreSQL support requires the frozen `0010` catalog contract and data-parametric witness builder named below. |
| Permissive `float(value)` before source-type validation at OHLCV boundaries | REPLACE | One shared market-number conversion rejects boolean source values before conversion, then preserves the current conversion and finite/range rules for other inputs. |
| Provider expansion, frontend work, deployment, production repair, live authority, sizing, routing, and money changes | DEFER | They remain outside this correction and retain their existing owner gates. |

### 14.2 Supported research start matrix

This matrix is an architecture result, not an active support statement. The
SQLite history-authority recovery independently constructed the smallest
honest route and returned `RECOVERY_ARCHITECTURE_ACCEPTABLE`. It remains
inactive until root accepts the recovery report, manifest, ledger, source
closure, matrix, final capsule bytes, audit freeze, and protected hashes.

Support means that a database with the exact version-owned catalog and any
contract-valid user and sequence state can reach `0011` without changing an
existing row, key, owner relation, classification, stored byte, or sequence
state. Catalog authority and user state are separate. Deterministic synthetic
witnesses exercise the contract but define no schema, historical fact, user
fact, support promise, or deployability claim. A start outside the matrix
refuses before schema, row, sequence, guard, or marker mutation.

| Dialect | Supported starts | Required source contract | Marker and completion rule |
| --- | --- | --- | --- |
| SQLite compatibility, proposed after root acceptance | Empty database; exact frozen current `0010`; any `0010` state missing any subset of exactly the five named guards and otherwise equal to the frozen catalog; exact target `0011` | `sqlite_catalog_contract.py` owns one literal target declaration: frozen logical `0010` catalog plus the guard-only `0011` marker/delta. Empty constructs that target directly. Exact and enumerated-repair `0010` preserve arbitrary contract-valid rows, owner/key relations, storage-class bytes, and `sqlite_sequence`. `foundation_sqlite_catalog_builder.py` imports this declaration and cannot redefine DDL. Unversioned, `0001` through `0009`, unknown markers, and every other drifted state are unsupported. | Read-only preflight validates marker, support route, guards, exact catalog, relational/type predicates, then sequence state in that precedence. Supported `0010` runs one guard-only transaction and stamps `0011` after complete validation; exact `0011` validates then no-ops. Unsupported states refuse before any schema, row, sequence, trigger, or marker write. |
| PostgreSQL 16 with the repository driver, proposed after root acceptance | Empty unmanaged database; exact catalog `0010` with arbitrary contract-valid state; exact current `0011` | `paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py` owns the sole frozen PostgreSQL `0010` catalog contract from accepted ledger SHA-256 `32a3735b5fe992e193a0e053b7940d77937fcfd7d86377a0f45b118bd828e0b1`. The same product contract module owns the exact `0011 = 0010 + guard-only delta` target declaration. The runtime migration consumes and must match that declaration; its DDL is implementation, not a second authority. `paper-trader/backend/tests/foundation_postgresql_0010_builder.py` imports only that catalog and accepts parameterized rows, owner relations, and sequence state. Synthetic values cannot define historical facts. It cannot import current `ResearchBase.metadata`, create a current/later head and rewind its marker, translate SQLite SQL, use a later-head dump, or invent facts. | Markers `0003` through `0009`, unknown markers, and catalog drift refuse before schema, data, sequence, guard, or marker writes. For supported starts, PostgreSQL DDL, data changes, validation, and marker advance share one transaction; interruption rolls back the whole stage. Every start and head receives exact validation. |

For SQLite, `paper-trader/backend/research/domain/migrations/sqlite_catalog_contract.py`
will own the sole literal catalog authority. The runtime consumer
`paper-trader/backend/research/domain/migrations/0011_sqlite_catalog_guard.py`
and test consumer `paper-trader/backend/tests/foundation_sqlite_catalog_builder.py`
must import it and cannot redeclare DDL. Runtime must never import tests. No
historical projection for unversioned or `0001` through `0009` may be added
without a new immutable-authority decision.

The data predicate is dialect-exact. SQLite validates each value's storage
class against declared affinity and checks constraints on the stored value. It
reads textual JSON as text and compares its UTF-8 bytes without parsing and
reserializing; it compares BLOB bytes directly. PostgreSQL validates the exact
declared column type. Text or varchar JSON remains textual and receives the
same UTF-8 byte comparison. A catalog-declared `json` or `jsonb` column uses
the database-returned dialect-native representation and cannot support a claim
that original input whitespace or key order survived. The accepted PostgreSQL
0010 catalog contains no binary column, so binary preservation is not
applicable there and cannot be claimed from a synthetic substitute.

Sequence validation reads identity, ownership, `last_value`, and called state
without `nextval`, default-consuming inserts, or another advancing operation.
SQLite reads every applicable `sqlite_sequence` row. A negative setup must use
an isolated clone or a transactionally reversible state change and must prove
the baseline sequence digest after rollback.

Recovery ledger SHA-256
`32a3735b5fe992e193a0e053b7940d77937fcfd7d86377a0f45b118bd828e0b1`
returns `EXPLICIT_MATRIX_REVISION_REQUIRED`. Exact committed source bytes can
reproduce empty PostgreSQL schemas at `0003` through `0005`, but they do not
provide complete version-owned catalog and transition contracts for arbitrary
valid user and sequence state. Versions `0006` through `0009` have accepted
delta bytes but no frozen full PostgreSQL catalog independent of current
metadata. Exact accepted current `0010` bytes provide the complete retained
catalog, so the supported start is exact catalog `0010` plus arbitrary valid
user and sequence state after the data-parametric witness builder passes.

This revision is explicit and inactive until root-owner architecture
acceptance. Repository tags, source history, accepted audit records, and
deployability records show no released, deployed, production, or externally
promised PostgreSQL `0003` through `0009` state. The recovery capsule requires
root and user direction only if a revision could strand such a state; current
evidence therefore creates a root-owner decision, not an extra user gate. If
later evidence establishes one of those states, work stops for root and user
direction before the revision takes effect.

The read-only refusal reports the observed marker and drift without mutating
schema, rows, sequences, or marker. The operator keeps the database untouched,
records that report, preserves a verified backup, and clones the backup to an
isolated diagnostic target. The operator must not rewrite the marker or ask the
application to rebuild. Any separately authorized recovery starts only after
root direction, plus user direction when the conditional stranding gate
applies.

SQLite needs the schema cookie because its supported recovery may expose
committed DDL boundaries and restart with an old marker. The cookie binds the
certified schema inventory to the marker and forces full validation after DDL
drift. PostgreSQL uses transactional catalog and marker changes, so a committed
version row names a committed stage. Tests must prove this dialect distinction;
version alone never permits PostgreSQL to skip exact validation.

### 14.3 Forward repair, interruption, and data preservation

SQLite does not replay a historical prefix. Empty constructs exact `0011`
directly. Exact `0010`, or an `0010` catalog missing any subset of the five
named guards and no other object or behavior, runs one guard-only transaction
to exact `0011`. Exact `0011` validates and no-ops. Unversioned, `0001` through
`0009`, unknown markers, non-enumerated guard states, catalog drift, invalid
data, and invalid sequence state refuse read-only. The inherited `0007` and
`0008` bytes remain frozen `KEEP_UNACCEPTED` inputs and receive no support
credit. PostgreSQL runs `0011` only from empty or its exact frozen `0010`
contract; `0003` through `0009` refuse before writes. The five SQLite guard
names are:

- `research_dataset_manifests_refuse_secret_key`
- `trg_research_dataset_manifests_no_delete`
- `trg_research_dataset_manifests_no_update`
- `trg_research_ir_v2_graph_versions_no_delete`
- `trg_research_ir_v2_graph_versions_no_update`

Catalog presence is not guard-behavior proof. Direct guard probes attempt the
prohibited test write inside a rollback-only SQLite savepoint or PostgreSQL
subtransaction, observe the expected refusal, roll back that scope, and compare
the complete preflight catalog, marker, row, key-owner, stored-byte, and
sequence digest. The probe records attempted test writes separately from
committed writes. Acceptance requires zero committed probe writes and a
byte-identical preflight digest after every attempt. Guard inventory or state
failure returns `RESEARCH_MIGRATION_GUARD_STATE_INVALID` before generic catalog
drift; the runtime does not repair a renamed, altered, extra, disabled, or
otherwise permissive guard.

These are five logical guards and the exact SQLite object names. PostgreSQL
`0010` represents the same guards with the frozen
`research_dataset_manifests_refuse_mutation` and
`research_ir_v2_graph_versions_refuse_mutation` function/trigger pairs. The
`0011` PostgreSQL path certifies or repairs only those exact dialect-owned
pairs. It does not rename them to SQLite objects or redefine the accepted
`0010` ledger.

The target-stage validator, not `checkfirst=True`, decides completion. It checks
the exact declared inventory and executes direct mutation probes for secret-key
and immutability guards. It stamps the marker only after those checks pass.

On SQLite, the guard delta and marker share one transaction. Interruption rolls
both back to the exact preflight `0010` state; reopen validates that same route
and retries. An exact complete `0011` validates and no-ops. Any other partial,
hybrid, duplicate, missing, altered, or unexpected object refuses without
writes. On PostgreSQL, a failed or interrupted transaction
rolls back schema, rows, sequences, triggers, and marker together; restart
begins from the exact prior version.

No migration rewrites an existing authority fact to make it pass. Additive
steps preserve row count, primary keys, foreign keys, sequence next values,
owner attribution, legacy classification, and the exact stored bytes of every
pre-existing text, JSON, and binary value. Table rebuilds require before/after
row and key digests plus direct byte comparisons; semantic JSON equality does
not satisfy canonical-byte preservation. Downgrade remains a read-only
refusal. Rollback means restore a verified pre-upgrade backup into a clean
target; production-shaped backup and restore evidence remains a later release
gate. Arbitrary schema, trigger, marker, or row-shape drift refuses before
repair.

### 14.4 Fixture taxonomy and permanent migration evidence

Every migration fixture records one of five labels:

- `EXACT_HISTORICAL_CATALOG_PROJECTION`: independently creates one supported
  version's catalog from named source authority and may prove catalog-level
  actual-old support.
- `SYNTHETIC_CONTRACT_VALID_WITNESS`: supplies deterministic contract-valid
  user and sequence state for behavior and preservation coverage. Its values
  define no schema, historical fact, user fact, or production state.
- `CURRENT_HEAD`: creates the current model and may prove fresh/head parity,
  never an old upgrade.
- `HYBRID_FAULT_INJECTION`: deliberately drops, adds, or rewinds part of a
  later schema and may prove drift refusal only.
- `RETIRED`: has stale or ambiguous provenance and receives no acceptance
  credit.

The permanent matrix runs both named, materially different synthetic corpora
under every supported catalog. Expected rows come only from the active caller
corpus plus the frozen ordered column/type declaration. An observed database
row or inventory can never contribute to expected state. The matrix compares
every row and column of the exact 24-table durable set, both marker versions,
the exact requested sequence name/value/called-state maps, keys, foreign-key
relationships, type/storage tags, ownership, classification, Unicode, textual
JSON, and binary bytes. Timestamp and boolean values use declared
dialect-native adaptation; the observer cannot silently normalize them.
The matrix upgrades one stage at a time, commits, closes every handle, disposes
the engine, and reads final bytes in a fresh process. It covers fresh and current
head, interruption before and after every durable boundary, repeated restart,
downgrade refusal, unknown future head, stale cookie, arbitrary drift, each
enumerated defect state, and clean idempotent restart. A reversible mutation
removes each 0007/0008 trigger installer and the 0011 certification guard; the
focused test must fail before marker advancement, then pass after exact byte
restoration.

The PostgreSQL fixture path
`paper-trader/backend/tests/foundation_postgresql_0010_builder.py` is a consumer,
not a second schema authority. It must import only
`paper-trader/backend/research/domain/migrations/postgresql_0010_contract.py`.
Its parameterized witnesses collectively span every durable `0010` table and
cover keys, foreign keys, owner attribution, non-default sequence states,
legacy nullable and classification states, Unicode text, and JSON arrays and
objects. At least two materially different contract-valid corpora must pass
under the same catalog. Text and varchar JSON retain exact stored bytes;
catalog-declared json or jsonb values use PostgreSQL's native representation.
Frozen BYTEA declarations preserve every binary byte and length. A reversible test
that imports current metadata, rewinds a marker, omits required catalog or
state coverage, or alters a stored byte must fail provenance or preservation
acceptance.

### 14.5 One pre-coercion market-number rule

`app.market_data.candles` owns one public source-value conversion used by every
assigned OHLCV ingress. It inspects the raw value before calling `float` or
constructing a NumPy, pandas, binary, JSON, hash, cache, causal, sizing, or
execution value. Python `bool` and boolean scalar values are not market
numbers. Both `True` and `False` refuse in every open, high, low, close, and
volume field.

For every non-boolean source value that the current code accepts, the helper
applies the same conversion, finiteness, positivity, and OHLC relationship
rules and returns the same float bytes. This correction does not narrow strings,
decimal values, integers, or other currently accepted finite inputs. It does
not change dataset encoding, dataset address, cache key, causal alignment,
signal result, sizing, or execution semantics for valid inputs. Any broader
numeric-type closure or identity change requires a separate versioned contract
and owner approval.

Provider validation, candle normalization, dataframe construction, sweep
preparation and pinned reload, dataset encoding and addressing, cache and
computation entry, causal evaluation, and the execution-price handoff must use
the shared rule or consume values already proven by it without another
permissive raw conversion. Storage does not trust callers and validates again
before minting bytes or an address. A boolean failure cannot create a dataset,
cache entry, evaluation result, signal, sized request, or executable price.

The permanent regression injects `True`, `False`, and boolean scalar values in
each OHLCV field through every assigned path and proves refusal before identity
or side effects. A compatibility corpus proves identical encoded bytes and
addresses for ordinary valid finite values. Reversible mutations remove the
shared source-type guard and replace one assigned caller with direct `float`;
both mutations must fail, then the exact bytes must be restored.

### 14.6 Serial currentness and deployability boundary

Attempt 1 did not prove a complete PostgreSQL catalog observer and did not bind
SQLite to an explicit close/dispose/reopen consumer. Attempt 2 hardened catalog
inspection for columns, constraints, indexes, functions, triggers, sequences,
and serial bindings, but its caller comparison still selected only four of the
24 durable tables. A committed change to `research_hypothesis` or
`research_finding` survived engine disposal and reopen while that selected
consumer stayed green. Both repairs therefore share one material false-green
class: a subset consumer was presented as complete caller-state evidence. The
catalog hardening remains useful, but neither repair nor any retained byte is
accepted.

The seven frozen inputs have hash-bound dispositions. The SQLite contract
`e34b6de36bafe994ea4422570267cb30beb6996e9f9d2c505788e4f3ecb800a0`
and PostgreSQL contract
`1b399e20e48977a2ceae4cca75f0d3989f2d7558782354a23ebbf95d576256b8`
are `KEEP_UNACCEPTED_FOR_NEXT_CAPSULE`. The SQLite builder
`f5fa3d3460a21c7de80e623204193bddf1ce2f4a38761fd1f93c616aef209e8a`,
PostgreSQL builder
`14b1e73a604bdaf760cc4eb3c5e31714a2c0ce57e39415498fe8fedb62e4f0c0`,
and projection test
`8a0e7ce4951d482ca330e0e322d1a25818d6f11df4c7e83421268d928b4ce8a8`
are `REPLACE_IN_NEXT_CAPSULE`. Migrations `0007`
`1dddeb3b9913a6d00291e112880180b488238db11058448a557884628a6cb6dc`
and `0008`
`76ab8f6dcd5f6cd4019702a5737250720f1982d113cac16e2958afeb939717c2`
are `KEEP_UNACCEPTED_FOR_NEXT_CAPSULE` and remain read-only. These
dispositions preserve inputs for one fresh implementation owner; they grant no
product, test, migration, runtime, or deployability acceptance.

The executable route is strictly serial after root accepts the repeated-failure
recovery report, machine contracts, immutable hashes, and exact next capsule.
Fresh assignment `foundation_research_migration_native_round_trip_owner`
replaces both builders and the projection tests as one completeness boundary.
It implements separate expected and observed functions, exact 24/24 table
coverage for both corpora and dialects, complete native catalogs, and a
machine-attested mutation registry. Runtime correction consumes but cannot
redefine those authorities, replaces current-metadata helpers, adds `0011`, and
implements refusal and restart; evidence integration owns existing fixtures,
retires rewind as historical evidence, and proves the complete matrix and
mutations. Numeric correction, root transitive revalidation, and one independent
critical review follow only after root accepts all three migration stages.

Each migration stage has one different fresh Terra-medium owner, parallel
budget zero, one durable goal, and non-overlapping write paths. The reviewer
requires accepted reports, manifests, and exact hashes from all three stages,
numeric correction, transitive integration, frozen-audit and protected checks,
and the root-built review package before starting.
Migration and numeric owners have disjoint product and test paths. Neither may
rebuild `.agent/review-package.json` or change programme state. The revalidation
owner freezes the integrated product and test hashes, reruns every invalidated
selector and mutation from current bytes, and builds one review package. The
reviewer reads that package and returns the critical verdict; it cannot patch
product or evidence.

The architecture impact is `migration-required`: research head changes to
`0011`, PostgreSQL `0003` through `0009` claims are invalidated by an explicit
proposed matrix revision, retained starts require new exact evidence, and
operators need a backup-first forward-upgrade procedure with refusal and
restore instructions.
No dependency, configuration, service, provider, frontend, credential, live,
or money contract changes. The implementation may prove only locally runnable
SQLite and disposable PostgreSQL 16 behavior. Release deployability remains
blocked on production-shaped clean install and supported upgrade, exact build
identity, PostgreSQL topology and roles, backup and clean restore, restart,
health, rollout/rollback, and post-upgrade smoke evidence at the existing Phase
6 and V1 release gates.
