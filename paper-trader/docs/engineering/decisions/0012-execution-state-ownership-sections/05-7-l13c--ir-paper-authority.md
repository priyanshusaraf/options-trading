Reference: [section index](../0012-execution-state-ownership.md). Read with its scope; this is not a new assignment.

## 7. L1.3C — IR paper authority

### 7.1 The grant, and what makes it safe to make

The owner granted `(ir_graph, paper, authoritative)` on 2026-08-07. `(ir_graph, live,
authoritative)` remains **absent** and is the next owner gate.

The grant was a one-line edit because L1.3B had already done the expensive part. Paper
authority is only meaningful if a paper fill cannot touch the live ledger, and §6 made that
structural: separate `capital_state` rows, a mandatory book predicate on every position
read, book-scoped risk controls. Without it, granting IR paper authority would have meant
granting it access to the same cash the live book spends.

### 7.2 The grant is necessary and deliberately not sufficient

This slice registers graph adapters, so `ir.<identifier>` now resolves in the one strategy
registry. If membership in `GRANTS` were the whole test, `POST /api/instruments/NIFTY/
strategy {ir.…}` would be an authoritative paper assignment — the exact hazard L1.2 closed.

So a graph-backed binding must pass two further checks at the point of use, both recomputed
rather than read off the binding:

1. **Origin.** Only `ORIGIN_PAPER_AUTHORITY` — a verified `ir_paper_deployments` record. An
   instrument row, a watchlist, the platform default and the fail-safe fallback all refuse.
2. **Exact content address.** The adapter's `version` *is* the graph's content address, so
   comparing it against the address the deployment approved binds authority to bytes rather
   than to a name.

`AUTHORITY_BY_SOURCE` is unchanged and still maps `ir_graph` to `SHADOW`. It answers a
different question — "may anyone with route access assign this source to an instrument" —
and the answer is still no. Collapsing the two maps is how the write-side gate would open.

### 7.3 Where authority lives, and why it is a third table

`ir_paper_deployments` (migration `0013`) binds eleven identities: project, deployment,
instrument, interval, graph identifier, graph version, content address, stable strategy key,
evidence lineage, paper mode, authoritative verdict, plus revision and lifecycle state.

**Not a wider CHECK on `ir_shadow_deployments`.** That object is an observer — no capital,
no orders, no arm state, no authority, and a service with no mode parameter. One row meaning
either "watched" or "traded" depending on a column is the collapse this ADR keeps refusing.

**Not a second deployment model.** The `Deployment` row still owns the account, universe,
parameters, allocation and arm. This attaches to one and adds only what a `Deployment`
cannot carry.

**Why the lifecycle is per-binding rather than `Deployment.status`.** The engine pins
`deployment_id = LEGACY_DEPLOYMENT_ID`; one deployment runs and every instrument in the book
shares its status, so pausing one graph by pausing that deployment would stop the whole
book. Same finding as §3.1a, same resolution.

### 7.4 Exact-version semantics

The content address is verified in **three independent places**: at activation, on every
reload (`active_bindings`), and at the authority gate against the adapter the registry
actually resolves. The first two protect the record; the last protects the trade.

Publishing a new graph version does nothing to an existing deployment — it names v1 and
keeps naming v1. Authority is re-granted by staging and activating a new binding, or it is
gone. A mismatch fails closed: the instrument stops trading rather than silently trading the
default, which is the posture a deployment pin already takes.

No client may supply `execution_mode`, `authority`, `runtime_source`, `strategy_key` or
`graph_content_address`. The mode and authority are the reviewed grant; the key and the
address are derived from the artefact the request names.

### 7.5 Rollback

`retire(..., restore_strategy_key=...)` is the only place authority is handed back, and the
argument is **required** — `None` means "there was no previous authority", a key means "put
this back". Neither is inferred. A target that cannot itself hold authority is refused, so
rolling back onto a graph key cannot re-grant through the door left shut. Retirement is
terminal, money records are never rewritten, and the API gives it its own route rather than
a shared transition shape that would let the target be omitted.

### 7.6 Two defects this slice found

**Option fills were unattributed.** All three entry paths resolved the canonical binding and
refused to open without it (L1.2b), but the options path never carried it onto the row —
every option `Position` was written with `strategy_key=NULL`. Latent, because production
runs `max_open_positions=0`; reachable the moment a graph became authoritative.
`strategy_version` was stamped on **no** path at all, which meant no money record could name
the graph version that produced it — precisely what exact-version authority is for. Both are
now carried through options, equity and futures, and onto the `Trade` row at close.

**`LiveBroker` would have raised `TypeError` on every real order.** Adding those parameters
updated `PaperBroker` and the `Broker` protocol — and `test_broker_protocol` compared the
protocol only against the *paper* implementation, so the live override's signature drifted
invisibly. `test_the_live_broker_accepts_everything_the_paper_broker_does` closes it. This is
the same shape as the unconsumed-mechanism defect class: a guard that checks the safe half.

### 7.7 What remains before live authority can even be designed

- Zero paper coverage in production today; this slice makes it possible, not present.
- The live grant would need its own `(ir_graph, live, authoritative)` entry, a table whose
  CHECK permits it, and a service able to write it — three reviewed changes, by design.
- Live authority additionally reaches `LiveBroker`, `KiteOrderClient` and the real order
  seam, none of which paper authority touches. That is a different risk surface and a
  separate design.
