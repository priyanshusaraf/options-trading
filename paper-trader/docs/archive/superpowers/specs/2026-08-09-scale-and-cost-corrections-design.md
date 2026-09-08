# Scale and cost corrections

Owner direction, 2026-08-09, correcting three numbers and adding one concern to the
[execution-first product roadmap](2026-08-09-execution-first-product-roadmap-design.md).
This note supersedes the figures it names; it does not change the phase order.

## 1. What changed

| Item | Roadmap said | Owner corrects to |
|---|---|---|
| Initial user target | 100 users, 50 concurrently live | **500 users from the start** |
| Backtest tier ceiling | 100 × 5 baseline, 1,000 × 5 expansion | **10,000 × 5 in a few minutes** |
| Deployment cost | Named as a target set, never priced | **A first-class constraint with a budget** |
| Backtest frontend | Not addressed | **Explicitly in scope, deferred to the frontend phase** |

## 2. The 10,000 × 5 target, measured against reality

The target is 50,000 cells in "a few minutes". Three separate floors decide whether that is
reachable, and only one of them is about writing faster code.

**Provider I/O makes it impossible as a live fetch, by arithmetic.** `_MIN_INTERVAL` in
`app/providers/kite.py` sets the historical endpoint to **0.40 s per request**, serialised per
connection, because that is Kite's documented 3 req/s limit with a safety margin. 50,000 datasets
is therefore:

```
50,000 × 0.40 s = 20,000 s = 5 h 33 m of pure I/O floor, one connection
```

No amount of concurrency in our process moves this; the throttle exists because the far side
enforces it. A second data connection halves it and is still hours.

**Conclusion: a local content-addressed candle store stops being an optimisation and becomes
the primary read path.** Task 4 of the sweep plan ("pinned immutable warm path") was scheduled
as a nicety after batching. It is now the load-bearing item. Datasets are fetched once, stored
by content address, and every sweep after the first reads from disk. The provider becomes an
incremental top-up for the trailing window, not the source of a sweep.

This does not weaken the truthfulness rule the cache design established. A *refresh* still costs
one read per dataset and may find revised history. A *pinned* run against a stored dataset
address makes zero provider reads, and that claim is honest precisely because the address pins
the exact bytes.

**Compute is reachable, but not single-threaded.** The measured simulator cost is 6.61 ms/cell:

```
50,000 × 6.61 ms = 330 s = 5.5 min   single-threaded, one strategy, spot only
```

That already misses "a few minutes" before the premium replay is counted. Multiprocess fan-out
across cores brings it to roughly 40–60 s on 8 cores. Concurrency was previously deferred until
throttles were measured — they are now measured, and this is the measurement that justifies it.
It must still be proven byte-identical against the serial path on a frozen dataset.

**Persistence becomes a real bottleneck.** 50,000 result rows through one SQLite writer, with
premium trade JSON per row, is a write volume the current path has never seen. Batching (Task 3)
is necessary but may not be sufficient; measure before assuming it is.

**One scoping question for the owner.** NSE lists roughly 1,900 equities, so "10,000
instruments" exceeds the tradable cash universe. The 50,000-cell figure is being designed for
regardless, on the reading that the axis is instrument × interval × **parameter variation**
rather than 10,000 distinct securities. If that reading is wrong, say so — it changes what is
cached, not how much work there is.

## 3. Deployment cost at 500 users

The owner's constraint is explicit: 500 users must be servable without the hosting bill
becoming the reason the product cannot ship. Cost is a design input from here, not an
operational afterthought.

### The assumption that was quietly expensive

The roadmap's "maximum five active accounts per worker process" was never measured — it was a
conservative placeholder. Carried to 500 users it means **100 worker processes**. At a modest
256 MB each that is 25 GB of RAM before the control plane, which on DigitalOcean is a
several-hundred-dollar monthly line item for execution alone. That is the outcome the owner is
trying to avoid, and it arrives by assumption rather than by measurement.

### What actually costs money, in order

**1. Market data must be fanned in once, not per user.** This is the single largest lever. 500
users watching overlapping instruments need **one** market-data connection per distinct
instrument set, not 500 broker sessions. The architecture already permits this — "data provider
≠ execution broker" is a standing invariant, and it is why a data-only second provider has
commercial value beyond redundancy. Per-account credentials are required for *orders*, not for
prices.

**2. Strategy evaluation is cheap and multiplexable.** At 6.61 ms/cell, one core evaluates
thousands of instrument-strategy pairs per minute. Five accounts per process is not a measured
limit; it is a guess. The gate must be a measured accounts-per-core number under a real market
session, and the expectation is that it is far above five.

**3. Per-account isolation should be a tier, not the default.** Isolation is bought for accounts
that need it. The default should be multiplexed execution with per-account fencing in the
database, which the durable intent/event schema from phase 1 already supports — `account_scope`
and `connection_scope` are columns on `execution_intents` today.

### WebSockets, specifically

The owner has been stuck here before and wants the picture stated plainly. **Nothing below
proposes replacing WebSockets with HTTP polling.** Polling 500 dashboards is strictly worse on
both cost and latency.

- **Connection count is a non-issue.** 500 concurrent WebSockets is small. A single uvicorn
  process handles thousands; the per-connection memory is tens of kilobytes, so roughly 25 MB
  total. This is not what makes real-time expensive.
- **Payload volume is measurable, and it has now been measured** — hardening record §11. The
  estimate below was written before that measurement and the measurement corrected it in an
  important way, so read §11 rather than this bullet. Summary: at 50 instruments a push is
  25.9 KiB and 500 users is ~2.7 TB/month, which is only ~$17/month of DigitalOcean overage.
  **The bandwidth is not the problem.** The problem is that `manager.py` sends with
  `ws.send_json` *per client*, so the same dict is JSON-encoded once per connected browser —
  ~24 MB/s of encoding at 500 users to transmit ~10 MB/s. That is a CPU cliff wearing a
  bandwidth costume, and it is the 2026-07-23 outage shape. Serialise once and `send_text` the
  same string to every client; then push **deltas, not full state**.
- **The precedent is on record and it was not infrastructure.** The 2026-07-23 outage was a
  dashboard-open leak at +100 MB/min that took a 1 GB droplet into OOM and collapsed the DB
  pool. Two causes, both application-level: the WebSocket hub, and analytics routes doing
  full-table ORM scans on a 5-second poll. Both are fixed. The lesson stands — at this scale
  the failure mode is a fanout bug, not a bandwidth bill.
- **Fan-out belongs behind one hub.** One process owning the market-data subscription and
  broadcasting to subscribers keeps the cost linear in *distinct data*, not in users. A message
  bus is only needed once fan-out spans more than one host.

### Cost budget to prove

Not yet measured. These are the numbers a deployment gate must produce before 500 users are
admitted:

| Measurement | Why it decides the bill |
|---|---|
| Accounts per core under a live session | Replaces the five-per-worker guess; sets the worker count |
| Resident memory per active account | Sets droplet size and therefore the largest line item |
| Sustained WebSocket bytes/user/hour | Sets bandwidth overage, the invisible cost |
| Peak concurrent live accounts vs. connected | 500 connected is not 500 trading at once |
| DB write throughput at peak entries | Decides when SQLite must become PostgreSQL |
| Backtest burst cost per user-initiated sweep | The one workload that can spike cost on demand |

**Target to hold the design against:** 500 users served from a small number of right-sized
hosts, in the low hundreds of dollars per month, with per-user isolation available as a paid
tier rather than the default. If a design cannot be stated in those terms, it is not ready to
deploy.

## 4. Backtest experience — noted, deferred

Explicitly in scope and explicitly **not** now; it belongs to the frontend phase.

**The frontend is owner-gated (2026-08-09).** No agent may change frontend code until the owner
takes it up directly. This section is a requirements note to be handed to that work, not a
licence to start it. Backend work stops at the API boundary.

Recorded here so it is not rediscovered:

- A 50,000-cell sweep cannot be a blocking spinner. Progress must be durable and resumable, and
  the view must survive a page reload without restarting work.
- Results must be explorable while the sweep is still running — sort, filter and drill into
  completed cells before the tail finishes.
- The warm/cold distinction must be visible. A user needs to know whether they are looking at a
  fresh computation or a reused result, and pinned-versus-refresh must be an explicit choice in
  the UI, never inferred.
- Cell count is a cost signal. The user should see the shape of what they asked for before it
  runs.
- Rendering tens of thousands of rows needs virtualisation and server-side aggregation; the
  browser must never receive 50,000 result payloads to filter locally.

## 5. What this changes in the plan

| Phase | Change |
|---|---|
| 5 — sweep | Reordered: the local content-addressed dataset store (was Task 4) is promoted ahead of batching, because the provider floor makes it the only path to the target. Tiers become 100 × 5, 1,000 × 5, 10,000 × 5. Measured multiprocess fan-out is now in scope, with byte-identical output as its gate. |
| 7 — topology | Retargeted to 500 users. Five-accounts-per-worker is withdrawn as an assumption and becomes a measurement. A cost budget joins latency, RPO and RTO as a gate. |
| 8 — frontend | Gains the backtest-experience requirements in §4. |

Phase order is unchanged.
