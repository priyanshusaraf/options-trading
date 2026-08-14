# Runtime Economics & Provider Capability Steer

## Goal

Prevent sophisticated strategies from becoming unbounded infrastructure liabilities. Compute economics, broker limits and subscription behaviour are architecture concerns now, not deployment cleanup later.

---

## 1. Compile a resource plan with every strategy

Every node declares static/dynamic resource characteristics.

### Static
- subscriptions required;
- data resolution;
- history required;
- state size;
- expected memory window;
- instrument fan-out;
- storage requirement;
- compute class.

### Dynamic
- event/tick frequency;
- ladder update rate;
- option-window churn;
- custom-code runtime;
- active-position fan-out;
- deployment count.

Deployment preflight produces:
- physical subscriptions;
- derived streams;
- provider quota usage;
- compute class;
- expected memory/state;
- expected storage;
- historical-data demand;
- estimated internal cost class.

---

## 2. Incremental streaming runtime

Do not reevaluate the whole graph on every event.

Use dependency-aware incremental invalidation:
- one changed input;
- recompute only affected descendants.

Indicators such as EMA/ATR/RSI should use incremental state updates live rather than repeatedly scanning full history.

---

## 3. Batch/vector research runtime

Use vector/batch execution for historical research and parameter sweeps where beneficial.

One strategy definition, two optimized execution modes:
- vector/batch research;
- incremental streaming live.

They must remain semantically equivalent.

---

## 4. Evaluation clocks/triggers

Nodes run only on relevant events.

Triggers may include:
- tick;
- quote;
- depth update;
- trade;
- candle close;
- timer;
- order event;
- position event;
- session event;
- expiry/roll event.

A daily indicator must not recompute for every option-depth update.

---

## 5. Shared calculations

Within a permitted user/data boundary, deduplicate identical data subscriptions and derived computations.

If many nodes/deployments require:
`NIFTY + 5m + EMA(50) + same node/data policies`
compute once and fan out.

Likewise for:
- ATR;
- RSI;
- VWAP;
- option-chain aggregates;
- book imbalance;
- normalized market data.

Do not redistribute one customer's licensed feed to another customer unless explicitly permitted.

---

## 6. Cache identity

Never cache by indicator name alone.

Identity should include where relevant:
- node semantic version;
- parameters;
- canonical instrument;
- timeframe;
- session policy;
- adjustment policy;
- missing-data policy;
- provider/dataset version;
- historical range or segment identity.

Fast-but-wrong caching is unacceptable.

---

## 7. Order-book/ladder processing

Build one current book per subscribed instrument.

Prefer passing derived scalar features through the graph rather than copying full ladders repeatedly.

Examples:
- imbalance;
- spread;
- microprice;
- depth slope;
- concentration.

Expose raw ladder objects only to advanced nodes that explicitly need them.

Separate:
- strategy evaluation rate;
- UI visualization rate.

Do not render every market-depth event simply because the strategy engine consumes it.

---

## 8. Dynamic option-window subscription management

For ATM ± N structures:
- maintain a buffer outside visible/current window;
- subscribe new contracts before dropping old ones;
- use hysteresis to avoid repeated churn near strike boundaries;
- share overlapping contracts among the same user's strategies;
- prioritize held-position data over exploratory window data.

---

## 9. Resource QoS priorities

Suggested hierarchy:

P0 — existing-position protection, kill switch, order-state reconciliation  
P1 — live execution-critical data and strategy evaluation  
P2 — paper/shadow  
P3 — interactive research  
P4 — batch optimization/Monte Carlo  
P5 — UI visualization/nonessential analytics

Under load, slow/defer lower priorities before affecting P0/P1.

---

## 10. Per-deployment resource ceilings

Each deployment should have hard internal limits for:
- subscriptions;
- depth feeds;
- custom-node CPU;
- memory/state;
- event rate;
- storage;
- concurrent expensive operators.

A heavy custom node may be:
- research eligible;
- paper eligible;
- not live eligible.

Do not allow one customer/deployment to consume unbounded infrastructure.

Internal cost telemetry should eventually support pricing tiers, but do not expose raw infra cost unless product strategy calls for it.

---

## 11. Provider capability matrix

Track separately:

### Data
- live fields;
- historical fields;
- resolutions;
- retention;
- market-depth levels;
- Greeks/OI/volume;
- websocket/subscription limits;
- request rate limits;
- session/auth properties.

### Execution
- order types;
- product types;
- GTT/trigger/protection facilities;
- modify/cancel semantics;
- partial-fill behaviour;
- margin APIs;
- position/order reconciliation.

### Historical market support
- expired futures;
- expired options;
- point-in-time contract masters;
- timestamps/timezone quality.

The compiler compares strategy requirements to the user's actual connected providers.

---

## 12. Provider fallback

Do not silently switch market-data providers mid-session.

A fallback is allowed only when:
- user approved it;
- semantic compatibility is known;
- resynchronization policy is defined;
- strategy state can be safely resumed.

Different providers may produce materially different bars or timestamps.

---

## 13. Cost telemetry

Measure:
- subscription counts;
- events/sec;
- evaluations/sec;
- compute time by node type;
- cache hit ratio;
- shared-computation savings;
- custom-code time;
- memory by deployment;
- storage growth;
- websocket reconnect/churn;
- research job cost.

Use these metrics to prevent architecture drift and tune pricing/capability tiers.
