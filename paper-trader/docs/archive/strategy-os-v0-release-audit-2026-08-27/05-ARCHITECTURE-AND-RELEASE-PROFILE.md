# Architecture and release profile

## Architecture decision

`KEEP ONE STRATEGY OS; ADD A SERVER-ENFORCED V0 CAPABILITY PROFILE.`

V0 does not branch the domain architecture. It contracts reachability and product
claims.

## Required V0 profile

One immutable deployment/configuration fact must identify the release profile and
service role. Environment-only flags cannot be the sole truth exposed to users.

```text
release_profile = V0_RESEARCH_SIGNAL
service_role ∈ {api, research_worker, monitor, scheduler}
execution_worker = absent
live_authority = impossible
```

The capability manifest names every public route/surface and one of:

- `ENABLED`;
- `ENABLED_WITH_LIMIT`;
- `INTERNAL`;
- `UNAVAILABLE`;
- `BLOCKED` with typed reason.

Frontend route gating reflects backend truth. It never serves as authorization.

## Execution hard-disable

For V0:

- no process constructs `LiveBroker`, order clients or an account execution lease;
- execution mutation routers are absent or return one typed unavailable response;
- no API input can name execution mode, broker order, capital assignment or arm state;
- no WebSocket sends private execution state;
- V0 navigation contains no LIVE, ARM, KILL, positions, order or execution settings;
- monitoring and signals cannot import execution engine/order modules;
- tests enumerate every current mutation route and prove it unreachable;
- safe exits are irrelevant because V0 cannot create positions; existing V1 books
  remain preserved and are not reinterpreted.

“Disarmed” is not sufficient. The current browser run is disarmed but still exposes
execution controls and starts an execution-shaped runner.

## Canonical identities preserved

- One Strategy graph/version/admission chain.
- One PlatformRegistry/component library.
- One validator/resolver/hash.
- One candle-to-frame and validity path.
- One dataset/market-truth/provider-evidence chain.
- One backtest/research result model and cache identity.
- One provider-connection model with separate data/execution roles.
- One future deployment/execution binding seam.

Corrected indicators use new semantic versions. V0 never changes the meaning of an
accepted v1 component address or cached result.

## Chart and annotation architecture

Store two facts:

1. opaque vendor/presentation artifact for workspace restoration;
2. normalized semantic annotation revision for strategy/research use.

Presentation state never enters strategy identity. Normalized geometry does.
Trendlines/channels store anchors and line equations, not one fixed price. Fibonacci
stores anchors, direction, ratios and derived levels. A lock creates an immutable
revision. An edit creates a successor.

Historical replay binds an `as_of` event and hides future data. A locked annotation
may affect only subsequent evaluation events.

## Provider and data architecture

V0 supports Zerodha as one user-facing connection but retains role separation:

```text
canonical instrument
→ data-provider mapping/capability
→ read-only observations/datasets

execution-provider mapping
→ preserved but unavailable in V0
```

Use the encrypted owner-scoped connection model and a read-only Kite client. Do not
request order/fund/position credentials or scopes that V0 does not need. Record token
expiry/reconnect as provider state.

Options, VIX and depth facts carry source, observed/exchange timestamps,
availability, freshness, contract identity and exact captured range. Data absence is
typed. No current instrument dump or current expiry list is projected backward.

## Static scope and future Dynamic Watchlists

V0 `StaticInstrumentScope` is immutable/versioned at use. Existing editable
watchlists may remain user conveniences but an experiment/monitoring assignment binds
an exact snapshot. The object retains the same `InstrumentScope` seam that V0.1/V1
extends with dynamic definitions/evaluations/snapshots.

## Research compatibility

One admitted strategy executes through:

- batch/vector research;
- incremental monitoring;
- prefix/causality conformance;
- exact state snapshot/restart.

Research methods consume immutable ExperimentSpecs and datasets. Parameter search,
OOS, walk-forward, neighbourhood and Monte Carlo records share trial lineage and
cannot overwrite a prior conclusion.

## Schema and migration approach

- Additive forward-only migrations.
- Never drop Phase 5 execution/capital facts for V0.
- V0 tables are long-term objects, not temporary launch tables.
- Test clean install and upgrade from the accepted 0041/0011 heads.
- Code rollback disables new writers and keeps facts readable.
- Destructive downgrade remains unsupported; forward repair is explicit.

## Code and release-line strategy

Use the canonical repository and main programme. Do not create a long-lived V0 fork.
After a reviewed clean release candidate exists, a short-lived V0 release branch may
receive release blockers only; changes merge forward into the active programme.

Every Phase 6+ change must pass the V0 regression/profile suite before entering a
release line. Feature isolation occurs through capability profiles and contracts,
not divergent strategy formats.

## No-rewrite guarantee and limit

V0 preserves architectural identity, but it does not guarantee every current
implementation survives unchanged. Incorrect indicator v1 semantics, the old bot UI,
the execution-shaped FastAPI startup and fixture-only prototype surfaces require
replacement or refactoring behind the same contracts.

## Deployment impact

The V0 implementation programme is architecture-changing and migration/config/service
affecting. This planning package is read-only. Release claims remain:

- locally runnable: `yes`, under safe mock evidence;
- release-deployable: `no`;
- production-rehearsed: `no`;
- deployed V0: `no`.
